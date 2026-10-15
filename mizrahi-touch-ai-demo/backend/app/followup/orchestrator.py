"""The follow-up orchestrator: builds the evaluator's facts from the database, keeps one contact plan per case, and
is the only code that starts a customer contact.

- `on_event(case_id, trigger, now)` re-syncs the case's tasks and evaluates it right away (presence, preferences,
  overrides, a finished review). `tick(now)` runs everything that is due: mock-call script steps, reconciliation of
  calls of unknown status, kill-switch cancellation, and plans whose `next_eligible_at` has passed. Before G5 the
  tests and `POST /api/demo/tick` drive both; at G5 the worker loop calls `tick` and the review path `on_event`.
- **The pre-dispatch gate**: the context is re-read and re-evaluated inside one `db.tx()`. Only DISPATCH_NOW creates
  the attempt, with its idempotency key and its upload link, in that same transaction. The provider is called after
  the commit; the kill switch is checked once more just before, and a contact past that point is cancelled best-effort.
- Every evaluation that changes the decision (and every non-tick evaluation) writes a `policy_decisions` row and a
  `followup.policy_evaluated.v1` event; plan transitions emit their own events.
- A Talk failure never touches documents: uploads and reviews run on their own path (AC 13)."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

from .. import clock, db, events, flags
from ..bank.mock_bank import bank
from ..comms import mock_talk, registry, webhook
from ..comms.contract import CallRequest, MessageRequest
from ..policy import store
from ..policy.schema import LoanPolicy
from ..store import repo
from ..util import new_id
from ..workflow import readiness
from . import links, presence, tasks
from .contract import ATTEMPT_RANK, FINAL_ATTEMPT_STATUSES, AttemptSummary, Decision, FollowupContext, OpenTask
from .policy import evaluate

ACTOR = "followup"
LIVE_PLAN = ("IN_APP", "WAITING", "SCHEDULED", "DISPATCHING", "IN_CALL", "AWAITING_CUSTOMER", "BLOCKED", "PAUSED")
IN_PROGRESS = tuple(s for s, rank in ATTEMPT_RANK.items() if rank < 9)
CANCELING = {"HG-KILL-SWITCH", "HG-OPT-OUT", "HG-NO-CONSENT", "HG-CASE-CLOSED"}
TASK_STATUS = {"IN_APP_ONLY": "IN_APP_PROMPTED", "IN_APP_NUDGE": "IN_APP_PROMPTED", "SCHEDULE_CALL": "FOLLOWUP_SCHEDULED",
               "DISPATCH_NOW": "CONTACT_ATTEMPTED", "ESCALATE": "ESCALATED", "SNOOZE": "PAUSED_BY_CUSTOMER"}
NEXT_STEP_HE = "להעלות את המסמך המבוקש דרך הקישור המאובטח שנשלח אליך"
CUSTOMER_STATE_HE = {
    "IDLE": "אפשר להשלים את המסמכים כאן באפליקציה", "IN_APP": "אפשר להשלים את המסמכים כאן באפליקציה",
    "WAITING": "אפשר להשלים את המסמכים כאן באפליקציה", "BLOCKED": "אפשר להשלים את המסמכים כאן באפליקציה",
    "PAUSED": "אפשר להשלים את המסמכים כאן באפליקציה", "CANCELED": "אפשר להשלים את המסמכים כאן באפליקציה",
    "SCHEDULED": "אם לא תספיקו להשלים, נחזור אליכם בשיחה", "DISPATCHING": "אנחנו מתקשרים אליכם כעת",
    "IN_CALL": "אנחנו בשיחה איתכם כעת", "AWAITING_CUSTOMER": "שלחנו לכם קישור מאובטח להעלאת המסמך",
    "ESCALATED": "נציג הבנק יחזור אליכם", "COMPLETED": "כל המסמכים התקבלו ונבדקו",
}


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


def _t(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


# ---------------------------------------------------------------- policy, preferences, overrides
def published_policy() -> tuple[Optional[LoanPolicy], str]:
    """(policy, label). An invalid published configuration evaluates as None: CFG-INVALID, contact only."""
    try:
        pol, row = store.policy()
        return pol, row["label"]
    except store.InvalidConfig:
        return None, store.published("loan_policy")["label"]


def _prefs_row(case_id: str) -> dict:
    row = db.one("SELECT * FROM contact_preferences WHERE case_id=?", (case_id,))
    if row:
        return row
    contact = bank.get_case(case_id).get("contact") or {}
    return {"case_id": case_id, "consent_voice": int(bool(contact.get("consent_voice"))),
            "consent_message": int(bool(contact.get("consent_message"))), "opt_out_voice": 0, "opt_out_message": 0,
            "snooze_until": None, "preferred_channel": None, "updated_at": None, "updated_by": None}


def preferences(case_id: str) -> dict:
    """The case's contact preferences, seeded from the bank's contact record on first use."""
    if not db.one("SELECT 1 FROM contact_preferences WHERE case_id=?", (case_id,)):
        r = _prefs_row(case_id)
        with db.tx() as c:
            c.execute("INSERT OR IGNORE INTO contact_preferences(case_id, consent_voice, consent_message, opt_out_voice,"
                      " opt_out_message, updated_at, updated_by) VALUES (?,?,?,0,0,?,?)",
                      (case_id, r["consent_voice"], r["consent_message"], clock.now_iso(), "system:bank"))
    r = _prefs_row(case_id)
    return {k: (bool(r[k]) if k in ("consent_voice", "consent_message", "opt_out_voice", "opt_out_message") else r[k])
            for k in ("consent_voice", "consent_message", "opt_out_voice", "opt_out_message", "snooze_until",
                      "preferred_channel", "updated_at", "updated_by")}


def set_preferences(case_id: str, actor: str, conn: Optional[sqlite3.Connection] = None, **changes: Any) -> dict:
    """Customer (or provider) preference changes; inside `conn` when given (the row must already exist then)."""
    if conn is None:
        preferences(case_id)
    allowed = {"opt_out_voice", "opt_out_message", "preferred_channel", "snooze_until"}
    changes = {k: (int(v) if isinstance(v, bool) else v) for k, v in changes.items() if k in allowed}
    if not changes:
        return preferences(case_id)
    now = clock.now_iso()

    def write(c: sqlite3.Connection) -> None:
        sets = ", ".join(f"{k}=?" for k in changes)
        c.execute(f"UPDATE contact_preferences SET {sets}, updated_at=?, updated_by=? WHERE case_id=?",
                  (*changes.values(), now, actor, case_id))
        kind = "followup.deferred.v1" if set(changes) == {"snooze_until"} else "contact.permission_changed.v1"
        events.emit(kind, case_id, actor, {k: (bool(v) if k.startswith("opt_out") else v) for k, v in changes.items()},
                    occurred_at=now, conn=c)
    if conn is not None:
        write(conn)
        return {}
    with db.tx() as c:
        write(c)
    return preferences(case_id)


def overrides(case_id: str, now: Optional[datetime] = None, active_only: bool = True) -> list[dict]:
    rows = db.query("SELECT * FROM case_overrides WHERE case_id=? ORDER BY created_at, rowid", (case_id,))
    out = []
    for r in rows:
        r["detail"] = db.jload(r["detail"], {})
        live = r["revoked_at"] is None and (r["expires_at"] is None or now is None or _t(r["expires_at"]) > now)
        if live or not active_only:
            out.append({**r, "active": live})
    return out


def add_override(c: sqlite3.Connection, case_id: str, kind: str, reason: str, actor: str, now: datetime,
                 expires_at: Optional[datetime] = None, detail: Optional[dict] = None) -> str:
    oid = new_id("OVR")
    c.execute("INSERT INTO case_overrides(override_id, case_id, type, reason, actor, created_at, expires_at, detail)"
              " VALUES (?,?,?,?,?,?,?,?)", (oid, case_id, kind, reason, actor, _iso(now), _iso(expires_at),
                                            db.jdump(detail or {})))
    events.emit("case.override_applied.v1", case_id, actor, {"override_id": oid, "type": kind, "reason": reason},
                occurred_at=_iso(now), conn=c)
    return oid


def revoke_overrides(c: sqlite3.Connection, case_id: str, kinds: tuple[str, ...], actor: str, now: datetime) -> int:
    cur = c.execute(f"UPDATE case_overrides SET revoked_at=? WHERE case_id=? AND revoked_at IS NULL AND type IN"
                    f" ({','.join('?' * len(kinds))})", (_iso(now), case_id, *kinds))
    if cur.rowcount:
        events.emit("case.override_applied.v1", case_id, actor, {"type": "revoke", "revoked": list(kinds)},
                    occurred_at=_iso(now), conn=c)
    return cur.rowcount


# ---------------------------------------------------------------- the evaluator's facts
def attempts(case_id: str) -> list[dict]:
    rows = db.query("SELECT * FROM contact_attempts WHERE case_id=? ORDER BY created_at, rowid", (case_id,))
    for r in rows:
        r["task_ids"], r["history"] = db.jload(r["task_ids"], []), db.jload(r["history"], [])
        r["request"] = db.jload(r["request"], {})
        r["simulated"] = bool(r["simulated"])
    return rows


def _customer_attempts_today(case: dict, now: datetime) -> int:
    nid = next((b["national_id"] for b in case["borrowers"] if b.get("role") == "primary"), case["borrowers"][0]["national_id"])
    cases = bank.customer_cases(nid) or [case["case_id"]]
    rows = db.query(f"SELECT created_at, status FROM contact_attempts WHERE case_id IN ({','.join('?' * len(cases))})",
                    tuple(cases))
    today = clock.local_date(now)
    return sum(1 for r in rows if r["status"] != "CANCELED" and clock.local_date(_t(r["created_at"])) == today)


def _statement_at(case_id: str, open_tasks: list[dict]) -> Optional[datetime]:
    """The customer's latest "I already sent it" after the oldest open task (statements are stamped in wall time)."""
    if not open_tasks:
        return None
    oldest = min(_t(t["created_at"]) for t in open_tasks)
    shift = timedelta(seconds=clock.offset_seconds())
    stamps = [_t(s["created_at"]) + shift for s in repo.statements(case_id) if s.get("created_at")]
    later = [s for s in stamps if s >= oldest]
    return max(later) if later else None


def context(case_id: str, now: datetime, manual: bool = False) -> tuple[FollowupContext, Optional[LoanPolicy], dict]:
    """Everything the evaluator may know, read from the database (no writes, so it runs inside the gate's tx)."""
    pol, label = published_policy()
    case = bank.get_case(case_id)
    open_tasks = tasks.open_for(case_id)
    ttl = pol.followup.presence_ttl_seconds if pol else 90
    snap = presence.snapshot(case_id, now, ttl, tuple(t["requirement_code"] for t in open_tasks))
    prefs = _prefs_row(case_id)
    active = overrides(case_id, now)
    kinds = {o["type"] for o in active}
    callback = next((o for o in reversed(active) if o["type"] == "customer_callback"), None)
    provider = registry.active(pol)
    plan_row = plan(case_id)
    # no presence on record (the customer never opened the app): grace counts from when the oldest issue was raised
    last_activity = snap["last_activity_at"] or min((_t(t["created_at"]) for t in open_tasks), default=None)
    ctx = FollowupContext(
        case_id=case_id, policy_version=label, environment=clock.environment(), case_open=not case.get("closed"),
        kill_switch=flags.get(flags.KILL_SWITCH),
        open_tasks=tuple(OpenTask(task_id=t["task_id"], requirement_code=t["requirement_code"],
                                  reason_code=t["reason_code"], status=t["status"], verified=t["verified"])
                         for t in open_tasks),
        human_requested="human_requested" in kinds, banker_paused=bool(kinds & {"pause", "cancel"}),
        presence=snap["presence"], on_task_screen=snap["on_task_screen"], last_activity_at=last_activity,
        last_seen_at=snap["last_seen_at"], upload_in_flight=snap["upload_in_flight"],
        evaluation_in_flight=snap["evaluation_in_flight"], live_sessions=snap["live_sessions"],
        consent_voice=bool(prefs["consent_voice"]), consent_message=bool(prefs["consent_message"]),
        opt_out_voice=bool(prefs["opt_out_voice"]), opt_out_message=bool(prefs["opt_out_message"]),
        contact_verified=bool((case.get("contact") or {}).get("phone_ref")),
        snooze_until=_t(prefs["snooze_until"]), preferred_channel=prefs["preferred_channel"],
        callback_at=_t((callback or {}).get("detail", {}).get("callback_at")),
        customer_statement_at=_statement_at(case_id, open_tasks),
        attempts=tuple(AttemptSummary(attempt_id=a["attempt_id"], channel=a["channel"], status=a["status"],
                                      created_at=_t(a["created_at"]), outcome=a["outcome"]) for a in attempts(case_id)),
        customer_attempts_today=_customer_attempts_today(case, now),
        provider_healthy=provider.health().ok if provider else True,
        plan_state=(plan_row or {}).get("state", "IDLE"), manual=manual)
    return ctx, pol, {"case": case, "tasks": open_tasks, "presence": snap}


# ---------------------------------------------------------------- the plan
def plan(case_id: str) -> Optional[dict]:
    row = db.one("SELECT * FROM contact_plans WHERE case_id=?", (case_id,))
    if row:
        row["decision"] = db.jload(row["decision"])
    return row


def _plan_state(prev: str, d: Decision, ctx: FollowupContext) -> str:
    a = d.action
    if a in ("IN_APP_ONLY", "IN_APP_NUDGE"):
        state = "IN_APP"
    elif a in ("WAIT", "SUPPRESS", "SNOOZE"):
        state = "WAITING"
    elif a == "SCHEDULE_CALL":
        state = "SCHEDULED"
    elif a == "DISPATCH_NOW":
        state = "DISPATCHING"
    elif a == "BLOCK":
        if "HG-BANKER-PAUSE" in d.blocked_by:
            state = "PAUSED"
        elif set(d.blocked_by) & CANCELING and prev in ("SCHEDULED", "WAITING", "DISPATCHING", "IN_CALL", "CANCELED"):
            state = "CANCELED"
        else:
            state = "BLOCKED"
    elif a == "ESCALATE":
        state = "ESCALATED"
    elif a == "RESOLVE_AND_CANCEL":
        state = "COMPLETED"
    else:
        state = prev if prev in ("COMPLETED", "CANCELED") else "IDLE"
    if any(x.status in IN_PROGRESS for x in ctx.attempts) and state not in ("COMPLETED", "CANCELED", "ESCALATED"):
        state = "IN_CALL"
    if prev == "AWAITING_CUSTOMER" and state in ("WAITING", "IN_APP"):
        state = "AWAITING_CUSTOMER"
    return state


def _write_plan(c: sqlite3.Connection, case_id: str, state: str, d: Decision, plan_version: int, nudge: bool,
                now: datetime) -> None:
    c.execute("INSERT INTO contact_plans(case_id, state, decision, next_eligible_at, policy_version, plan_version, nudge,"
              " updated_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET state=excluded.state,"
              " decision=excluded.decision, next_eligible_at=excluded.next_eligible_at,"
              " policy_version=excluded.policy_version, plan_version=excluded.plan_version, nudge=excluded.nudge,"
              " updated_at=excluded.updated_at",
              (case_id, state, db.jdump(d.model_dump(mode="json")), _iso(d.next_eligible_at), d.policy_version,
               plan_version, int(nudge), _iso(now)))


def _set_plan_state(c: sqlite3.Connection, case_id: str, state: str, now: datetime) -> None:
    c.execute("UPDATE contact_plans SET state=?, updated_at=? WHERE case_id=?", (state, _iso(now), case_id))


def _record(c: sqlite3.Connection, case_id: str, d: Decision, trigger: str, now: datetime, actor: str) -> None:
    c.execute("INSERT INTO policy_decisions(decision_id, case_id, action, blocked_by, rule_ids, next_eligible_at,"
              " policy_version, explanation_he, trigger, evaluated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (new_id("PDC"), case_id, d.action, db.jdump(list(d.blocked_by)), db.jdump(list(d.rule_ids)),
               _iso(d.next_eligible_at), d.policy_version, d.explanation_he, trigger, _iso(now)))
    events.emit("followup.policy_evaluated.v1", case_id, actor,
                {"action": d.action, "blocked_by": list(d.blocked_by), "rule_ids": list(d.rule_ids),
                 "next_eligible_at": _iso(d.next_eligible_at), "policy_version": d.policy_version, "trigger": trigger},
                occurred_at=_iso(now), conn=c)


def _same(prev: Optional[dict], d: Decision) -> bool:
    if not prev:
        return False
    keys = ("action", "blocked_by", "next_eligible_at", "task_ids", "policy_version")
    now_d = d.model_dump(mode="json")
    return all(prev.get(k) == now_d.get(k) for k in keys)


def _transition(c: sqlite3.Connection, case_id: str, ctx: FollowupContext, d: Decision, trigger: str, now: datetime,
                actor: str) -> str:
    row = c.execute("SELECT * FROM contact_plans WHERE case_id=?", (case_id,)).fetchone()
    prev = dict(row) if row else {"state": "IDLE", "plan_version": 0, "decision": None}
    prev_decision = db.jload(prev["decision"]) if isinstance(prev["decision"], str) else prev["decision"]
    state = _plan_state(prev["state"], d, ctx)
    version = prev["plan_version"] + (1 if state == "SCHEDULED" and prev["state"] != "SCHEDULED" else 0)
    changed = not _same(prev_decision, d) or state != prev["state"]
    if trigger != "tick" or changed:
        _record(c, case_id, d, trigger, now, actor)
    if changed or not row:
        _write_plan(c, case_id, state, d, version, d.action == "IN_APP_NUDGE", now)
    if state != prev["state"]:
        payload = {"from": prev["state"], "to": state, "next_eligible_at": _iso(d.next_eligible_at),
                   "plan_version": version, "blocked_by": list(d.blocked_by)}
        if state == "SCHEDULED":
            events.emit("followup.scheduled.v1", case_id, actor, payload, occurred_at=_iso(now), conn=c)
        elif state in ("CANCELED", "COMPLETED", "ESCALATED"):
            events.emit("followup.canceled.v1", case_id, actor, payload, occurred_at=_iso(now), conn=c)
        elif prev["state"] in ("SCHEDULED", "DISPATCHING") and state in ("WAITING", "IN_APP", "BLOCKED", "PAUSED"):
            events.emit("followup.deferred.v1", case_id, actor, payload, occurred_at=_iso(now), conn=c)
    status = TASK_STATUS.get(d.action)
    if d.action == "BLOCK":
        status = "PAUSED_BY_BANKER" if "HG-BANKER-PAUSE" in d.blocked_by else "POLICY_BLOCKED"
    if d.action in ("WAIT", "SUPPRESS") and ctx.evaluation_in_flight:
        status = "RECHECKING"
    if status and (state != "AWAITING_CUSTOMER" or status in ("ESCALATED", "RECHECKING")):
        tasks.set_status(c, case_id, d.task_ids, status, actor, d.explanation_he)
    elif d.action in ("WAIT", "SUPPRESS", "SCHEDULE_CALL"):
        paused = [t.task_id for t in ctx.open_tasks if t.status in ("PAUSED_BY_BANKER", "PAUSED_BY_CUSTOMER", "POLICY_BLOCKED")]
        tasks.set_status(c, case_id, paused, "OPEN", actor, "חזרה לטיפול")
    return state


# ---------------------------------------------------------------- evaluation and the gate
def on_event(case_id: str, trigger: str, now: Optional[datetime] = None, actor: str = ACTOR) -> dict:
    """Re-sync tasks and evaluate the case now. Returns {decision, state, attempt?}."""
    now = now or clock.now()
    bank.get_case(case_id)
    preferences(case_id)
    published_policy()
    tasks.sync(case_id)
    result = _evaluate(case_id, trigger, now, actor)
    if result["changed"] and result["state"] == "COMPLETED" and \
            readiness.compute(case_id)["state"] == "READY_FOR_HUMAN_REVIEW":
        events.emit("case.ready_for_banker.v1", case_id, actor, {"trigger": trigger}, occurred_at=_iso(now))
    return result


def _evaluate(case_id: str, trigger: str, now: datetime, actor: str, manual: bool = False) -> dict:
    sent: Optional[tuple[dict, Any, Any]] = None
    with db.tx() as c:
        prev_state = (plan(case_id) or {}).get("state", "IDLE")
        ctx, pol, extra = context(case_id, now, manual=manual)
        d = evaluate(ctx, pol, now)
        state = _transition(c, case_id, ctx, d, trigger, now, actor)
        if d.action == "SCHEDULE_CALL" and d.next_eligible_at and d.next_eligible_at <= now:
            ctx, pol, extra = context(case_id, now)           # eligible now: straight through the gate
            d = evaluate(ctx, pol, now)
            state = _transition(c, case_id, ctx, d, "gate", now, actor)
        if d.action == "DISPATCH_NOW":
            sent = _gate(c, ctx, d, pol, extra, now, actor, manual)
    attempt = _send(*sent, now) if sent else None
    return {"decision": d, "state": (plan(case_id) or {}).get("state", state), "attempt": attempt,
            "changed": prev_state != state}


def _hash(ids: tuple[str, ...]) -> str:
    return hashlib.sha256(",".join(sorted(ids)).encode()).hexdigest()[:12]


def _gate(c: sqlite3.Connection, ctx: FollowupContext, d: Decision, pol: LoanPolicy, extra: dict, now: datetime,
          actor: str, manual: bool) -> Optional[tuple[dict, Any, CallRequest]]:
    case_id, case = ctx.case_id, extra["case"]
    version = c.execute("SELECT plan_version FROM contact_plans WHERE case_id=?", (case_id,)).fetchone()["plan_version"]
    key = f"case:{case_id}:plan:{version}:tasks:{_hash(d.task_ids)}" + (f":manual:{len(ctx.attempts)}" if manual else "")
    if c.execute("SELECT 1 FROM contact_attempts WHERE idempotency_key=?", (key,)).fetchone():
        return None                                           # this plan already produced its contact
    provider = registry.active(pol)
    attempt_id = new_id("ATT")
    chosen = [t for t in extra["tasks"] if t["task_id"] in d.task_ids]
    link_id, token = links.create(c, case_id, list(d.task_ids), chosen[0]["requirement_code"] if chosen else None,
                                  pol.talk.link_ttl_minutes, now, attempt_id)
    first = next((b for b in case["borrowers"] if b.get("role") == "primary"), case["borrowers"][0])
    prompt = store.published("talk_prompt")
    req = CallRequest(idempotency_key=key, client_reference=attempt_id, case_ref=case_id,
                      contact_ref=(case.get("contact") or {}).get("phone_ref", ""), prompt_version=prompt["label"],
                      variables={"first_name": first["first_name_he"],
                                 "missing_documents": [t["customer_text_he"] or t["title_he"] for t in chosen],
                                 "secure_upload_link": links.url(token), "next_step": NEXT_STEP_HE},
                      expires_at=_iso(now + timedelta(minutes=pol.talk.link_ttl_minutes)))
    at = _iso(now)
    c.execute("INSERT INTO contact_attempts(attempt_id, case_id, channel, provider, simulated, idempotency_key, status,"
              " task_ids, policy_version, prompt_version, link_id, request, created_at, updated_at, history, actor)"
              " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (attempt_id, case_id, d.channel or "voice", provider.name, int(provider.simulated), key, "QUEUED",
               db.jdump(list(d.task_ids)), d.policy_version, prompt["label"], link_id,
               db.jdump({"call": req.redacted(), "mock": None, "manual": manual}), at, at,
               db.jdump([{"at": at, "status": "QUEUED"}]), actor))
    events.emit("talk.call.status_changed.v1", case_id, actor, {"attempt_id": attempt_id, "status": "QUEUED",
                "simulated": provider.simulated, "manual": manual}, occurred_at=at, conn=c)
    _set_plan_state(c, case_id, "DISPATCHING", now)
    tasks.set_status(c, case_id, d.task_ids, "CONTACT_ATTEMPTED", actor, "פנייה יצאה")
    revoke_overrides(c, case_id, ("customer_callback",), actor, now)
    return {"attempt_id": attempt_id, "case_id": case_id, "channel": d.channel or "voice"}, provider, req


def _update_attempt(attempt_id: str, **fields: Any) -> None:
    keys = ", ".join(f"{k}=?" for k in fields)
    with db.tx() as c:
        c.execute(f"UPDATE contact_attempts SET {keys} WHERE attempt_id=?", (*fields.values(), attempt_id))


def _send(attempt: dict, provider: Any, req: CallRequest, now: datetime) -> dict:
    """After the gate's commit: the provider call. The kill switch is checked once more; a failure ends the attempt
    as FAILED and the plan goes back to waiting (documents are never affected)."""
    aid, case_id = attempt["attempt_id"], attempt["case_id"]
    if flags.get(flags.KILL_SWITCH):
        _finish_locally(aid, case_id, "CANCELED", None, now, "מתג החירום הופעל לפני השליחה")
        return _attempt(aid)
    try:
        if attempt["channel"] == "message":
            ack = provider.send_message(MessageRequest(idempotency_key=req.idempotency_key, client_reference=aid,
                                                       case_ref=case_id, contact_ref=req.contact_ref,
                                                       text=_render(store.policy()[0].templates.link_message, req)))
        else:
            ack = provider.create_call(req)
    except Exception as exc:                                    # ProviderNotConfigured, a network error…
        _finish_locally(aid, case_id, "FAILED", None, now, f"{type(exc).__name__}")
        on_event(case_id, "provider_failed", now)
        return _attempt(aid)
    row = _attempt(aid)
    request = {**row["request"], "mock": mock_talk.first_step(now) if provider.simulated else None}
    _update_attempt(aid, provider_call_id=ack.provider_call_id, request=db.jdump(request))
    handle_talk_event({"event_id": f"{ack.provider_call_id}:dispatch", "event_type": "call.status_changed",
                       "client_reference": aid, "provider_call_id": ack.provider_call_id, "sequence": 0,
                       "status": "DISPATCHING", "occurred_at": _iso(now), "data": {}}, provider.name, now)
    if attempt["channel"] == "message":
        handle_talk_event({"event_id": f"{ack.provider_call_id}:sent", "event_type": "call.status_changed",
                           "client_reference": aid, "provider_call_id": ack.provider_call_id, "sequence": 1,
                           "status": "COMPLETED", "outcome": "LINK_SENT", "occurred_at": _iso(now),
                           "data": {"link_sent": True}}, provider.name, now)
    return _attempt(aid)


def _render(template: str, req: CallRequest) -> str:
    v = {**req.variables, "missing_documents": ", ".join(req.variables["missing_documents"])}
    return re.sub(r"{{\s*(\w+)\s*}}", lambda m: str(v.get(m.group(1), "")), template)


def _finish_locally(attempt_id: str, case_id: str, status: str, outcome: Optional[str], now: datetime, note: str) -> None:
    row = _attempt(attempt_id)
    history = row["history"] + [{"at": _iso(now), "status": status, "note": note}]
    with db.tx() as c:
        c.execute("UPDATE contact_attempts SET status=?, outcome=?, updated_at=?, history=? WHERE attempt_id=?",
                  (status, outcome, _iso(now), db.jdump(history), attempt_id))
        events.emit("talk.call.status_changed.v1", case_id, ACTOR, {"attempt_id": attempt_id, "status": status,
                    "note": note, "simulated": row["simulated"]}, occurred_at=_iso(now), conn=c)


def _attempt(attempt_id: str) -> dict:
    row = db.one("SELECT * FROM contact_attempts WHERE attempt_id=?", (attempt_id,))
    row["task_ids"], row["history"] = db.jload(row["task_ids"], []), db.jload(row["history"], [])
    row["request"], row["simulated"] = db.jload(row["request"], {}), bool(row["simulated"])
    return row


# ---------------------------------------------------------------- Talk events and their effects
def handle_talk_event(event: dict, provider: str, now: Optional[datetime] = None) -> str:
    """The single receiver for provider events (mock in-process, or the HTTP route): apply, then act on outcomes."""
    now = now or clock.now()
    result, attempt = webhook.apply(event, provider)
    if result != "applied" or attempt is None:
        return result
    case_id = attempt["case_id"]
    if attempt["status"] in ("DIALING", "CONNECTED"):
        with db.tx() as c:
            _set_plan_state(c, case_id, "IN_CALL", now)
        return result
    if attempt["status"] not in FINAL_ATTEMPT_STATUSES:
        return result
    outcome, data = event.get("outcome"), event.get("data") or {}
    with db.tx() as c:
        if outcome in ("LINK_SENT", "COMPLETED_NO_ACTION") or (attempt["status"] == "COMPLETED" and not outcome):
            _set_plan_state(c, case_id, "AWAITING_CUSTOMER", now)
            tasks.set_status(c, case_id, attempt["task_ids"], "AWAITING_CUSTOMER", ACTOR, "נשלח קישור מאובטח")
        elif outcome == "CALLBACK_REQUESTED":
            at = _t(data.get("callback_at")) or now + timedelta(hours=2)
            add_override(c, case_id, "customer_callback", "הלקוח ביקש שיחה חוזרת", f"provider:{provider}", now,
                         detail={"callback_at": _iso(at)})
            _set_plan_state(c, case_id, "AWAITING_CUSTOMER", now)
        elif outcome == "REFUSED":
            set_preferences(case_id, f"provider:{provider}", conn=c, opt_out_voice=True)
        elif outcome == "HUMAN_REQUESTED":
            add_override(c, case_id, "human_requested", "הלקוח ביקש נציג אנושי בשיחה", f"provider:{provider}", now)
        else:                                                   # NO_ANSWER, IDENTITY_FAILED, FAILED, CANCELED
            _set_plan_state(c, case_id, "WAITING", now)
    on_event(case_id, "call_finished", now)
    return result


def _advance_mock(row: dict, now: datetime, force: bool = False) -> int:
    steps = 0
    while True:
        mock = (row["request"] or {}).get("mock")
        if not mock or mock["step"] >= len(mock_talk.SCRIPT) or row["status"] in FINAL_ATTEMPT_STATUSES:
            return steps
        if not force and _t(mock["next_at"]) > now:
            return steps
        event, following = mock_talk.step_event(row, mock, now)
        _update_attempt(row["attempt_id"], request=db.jdump({**row["request"], "mock": following}))
        handle_talk_event(event, row["provider"], now)
        steps += 1
        row = _attempt(row["attempt_id"])


def _in_progress(case_id: Optional[str] = None) -> list[dict]:
    sql = (f"SELECT attempt_id FROM contact_attempts WHERE status IN ({','.join('?' * len(IN_PROGRESS))})"
           + (" AND case_id=?" if case_id else "") + " ORDER BY created_at")
    return [_attempt(r["attempt_id"]) for r in db.query(sql, (*IN_PROGRESS, *((case_id,) if case_id else ())))]


def cancel_in_progress(case_id: Optional[str], now: datetime, why: str) -> dict:
    """Best-effort cancellation: a mock call not yet connected is CANCELED; a connected one is TOO_LATE_TO_CANCEL."""
    out = {"canceled": 0, "too_late": 0}
    for a in _in_progress(case_id):
        if a["status"] in ("CONNECTED", "CANCEL_REQUESTED", "CANCEL_FAILED"):
            out["too_late"] += 1
            history = a["history"] + [{"at": _iso(now), "status": a["status"], "note": f"TOO_LATE_TO_CANCEL: {why}"}]
            _update_attempt(a["attempt_id"], history=db.jdump(history))
            continue
        provider = registry.by_name(a["provider"])
        if provider and a["provider_call_id"]:
            provider.cancel_call(a["provider_call_id"])
        handle_talk_event({"event_id": f"{a['attempt_id']}:cancel", "event_type": "call.status_changed",
                           "client_reference": a["attempt_id"], "provider_call_id": a["provider_call_id"],
                           "sequence": 99, "status": "CANCELED", "occurred_at": _iso(now), "data": {}}, a["provider"], now)
        out["canceled"] += 1
    return out


def tick(now: Optional[datetime] = None) -> dict:
    """Run every piece of due follow-up work once."""
    now = now or clock.now()
    out: dict[str, Any] = {"now": _iso(now), "steps": 0, "reconciled": 0, "evaluated": [], "canceled": 0}
    if flags.get(flags.KILL_SWITCH):
        out["canceled"] = cancel_in_progress(None, now, "מתג החירום")["canceled"]
    for a in _in_progress():
        if a["simulated"]:
            out["steps"] += _advance_mock(a, now)
    pol, _ = published_policy()
    reconcile = timedelta(minutes=pol.talk.reconcile_after_minutes if pol else 10)
    for a in [x for x in _in_progress() if x["status"] == "UNKNOWN" and _t(x["updated_at"]) + reconcile <= now]:
        provider = registry.by_name(a["provider"])
        try:
            st = provider.get_call(a["provider_call_id"]) if provider else None
        except Exception:
            st = None
        if st and st.status in ATTEMPT_RANK and st.status != "UNKNOWN":
            handle_talk_event({"event_id": f"{a['attempt_id']}:reconcile:{st.sequence}", "event_type": "call.status_changed",
                               "client_reference": a["attempt_id"], "provider_call_id": a["provider_call_id"],
                               "sequence": st.sequence, "status": st.status, "outcome": st.outcome,
                               "occurred_at": _iso(now), "data": st.data}, a["provider"], now)
            out["reconciled"] += 1
    kill = flags.get(flags.KILL_SWITCH)
    for p in db.query("SELECT case_id, next_eligible_at, state, decision FROM contact_plans"):
        stopped_by_switch = p["state"] == "CANCELED" and "HG-KILL-SWITCH" in (db.jload(p["decision"], {}) or {}).get(
            "blocked_by", [])
        if p["state"] not in LIVE_PLAN and not (stopped_by_switch and not kill):
            continue                                            # a plan the switch stopped resumes once it is off
        due = p["next_eligible_at"] is None or _t(p["next_eligible_at"]) <= now
        if due or p["state"] in ("IN_APP", "BLOCKED", "PAUSED", "CANCELED"):
            on_event(p["case_id"], "tick", now)
            out["evaluated"].append(p["case_id"])
    return out


# ---------------------------------------------------------------- staff and demo actions
def manual_call(case_id: str, staff_id: str, reason: str, now: Optional[datetime] = None) -> tuple[Optional[dict], Decision]:
    """A banker's call-now request through the same guards; (attempt, decision) or (None, the blocking decision)."""
    now = now or clock.now()
    preferences(case_id)
    tasks.sync(case_id)
    result = _evaluate(case_id, f"manual:{reason[:60]}", now, f"banker:{staff_id}", manual=True)
    return result["attempt"], result["decision"]


def banker_override(case_id: str, kind: str, reason: str, staff_id: str, now: Optional[datetime] = None) -> dict:
    now = now or clock.now()
    actor = f"banker:{staff_id}"
    with db.tx() as c:
        if kind in ("pause", "cancel"):
            add_override(c, case_id, kind, reason, actor, now)
        else:                                                   # resume
            revoke_overrides(c, case_id, ("pause", "cancel", "human_requested"), actor, now)
    if kind == "cancel":                                      # a pause that also stops a call already under way
        cancel_in_progress(case_id, now, "ביטול ע״י הבנקאי")
    return on_event(case_id, f"override:{kind}", now, actor)


def set_talk_outcome(case_id: str, outcome: str, callback_at: Optional[datetime], now: Optional[datetime] = None) -> Optional[dict]:
    """Demo control: the running simulated call ends now with this outcome."""
    now = now or clock.now()
    running = [a for a in _in_progress(case_id) if a["simulated"] and (a["request"] or {}).get("mock")]
    if not running:
        return None
    a = running[-1]
    mock = {**a["request"]["mock"], "outcome": outcome, "callback_at": _iso(callback_at)}
    _update_attempt(a["attempt_id"], request=db.jdump({**a["request"], "mock": mock}))
    _advance_mock(_attempt(a["attempt_id"]), now, force=True)
    return _attempt(a["attempt_id"])


def case_status(case_id: str) -> str:
    """Readiness' case status, with NEEDS_COMPLETION refined by the contact plan (04 §4)."""
    status = readiness.compute(case_id)["case_status"]
    state = (plan(case_id) or {}).get("state")
    if status == "NEEDS_COMPLETION" and state in ("SCHEDULED", "DISPATCHING", "IN_CALL"):
        return "FOLLOWUP_IN_PROGRESS"
    if status == "NEEDS_COMPLETION" and state == "AWAITING_CUSTOMER":
        return "AWAITING_CUSTOMER"
    return status


# ---------------------------------------------------------------- views
def customer_view(case_id: str, now: Optional[datetime] = None) -> dict:
    """What the customer may see: no rule ids, attempts, policy versions or banker text."""
    now = now or clock.now()
    p = plan(case_id) or {"state": "IDLE", "nudge": 0}
    prefs = _prefs_row(case_id)
    open_tasks = tasks.open_for(case_id)
    nudge = bool(p.get("nudge")) and p["state"] == "IN_APP"
    text = None
    pol, _ = published_policy()
    if nudge and pol:
        first = bank.get_case(case_id)["borrowers"][0]["first_name_he"]
        v = {"first_name": first, "missing_documents": ", ".join(t["customer_text_he"] or t["title_he"] for t in open_tasks)}
        text = re.sub(r"{{\s*(\w+)\s*}}", lambda m: v.get(m.group(1), ""), pol.templates.reminder)
    snooze = prefs["snooze_until"] if prefs["snooze_until"] and _t(prefs["snooze_until"]) > now else None
    return {"state_he": CUSTOMER_STATE_HE.get(p["state"], CUSTOMER_STATE_HE["IDLE"]), "nudge": nudge, "nudge_text_he": text,
            "open_items": [{"requirement_code": t["requirement_code"], "title_he": t["title_he"],
                            "customer_text_he": t["customer_text_he"]} for t in open_tasks],
            "snooze_until": snooze,
            "contact": {"voice_allowed": bool(prefs["consent_voice"]) and not prefs["opt_out_voice"],
                        "message_allowed": bool(prefs["consent_message"]) and not prefs["opt_out_message"],
                        "preferred_channel": prefs["preferred_channel"]},
            "simulated": bool(getattr(registry.active(pol), "simulated", True))}


def banker_view(case_id: str, now: Optional[datetime] = None) -> dict:
    now = now or clock.now()
    p = plan(case_id)
    pol, _ = published_policy()
    provider = registry.active(pol)
    keep = ("attempt_id", "channel", "provider", "simulated", "status", "outcome", "created_at", "updated_at",
            "prompt_version", "link_id", "task_ids", "actor")
    return {"plan": {k: p[k] for k in ("state", "plan_version", "next_eligible_at", "policy_version", "updated_at")} if p
            else {"state": "IDLE", "plan_version": 0, "next_eligible_at": None, "policy_version": None, "updated_at": None},
            "decision": (p or {}).get("decision"),
            "case_status": case_status(case_id),
            "tasks": [{k: t[k] for k in ("task_id", "requirement_code", "reason_code", "status", "title_he",
                                         "customer_text_he", "created_at", "updated_at", "resolved_at", "document_id")}
                      for t in tasks.all_for(case_id)],
            "attempts": [{k: a[k] for k in keep} for a in attempts(case_id)],
            "preferences": preferences(case_id), "overrides": overrides(case_id, now, active_only=False),
            "kill_switch": flags.get(flags.KILL_SWITCH), "talk_mode": pol.talk.mode if pol else "off",
            "simulated": bool(getattr(provider, "simulated", True))}


SUMMARY_HE = {
    "completion.required.v1": "נפתחה דרישת השלמה", "completion.resolved.v1": "דרישת השלמה נסגרה, מסמך חדש עבר בדיקה",
    "customer.presence_changed.v1": "שינוי בנוכחות הלקוח בפורטל", "followup.policy_evaluated.v1": "החלטת מדיניות",
    "followup.scheduled.v1": "שיחה תוזמנה", "followup.deferred.v1": "הפנייה נדחתה",
    "followup.canceled.v1": "הטיפול היזום הסתיים או בוטל", "talk.call.status_changed.v1": "עדכון סטטוס שיחה",
    "case.ready_for_banker.v1": "התיק מוכן לבדיקת הבנקאי", "contact.permission_changed.v1": "שינוי בהעדפות הקשר",
    "case.override_applied.v1": "פעולת בנקאי / לקוח על הטיפול היזום",
    "integration.reconciliation_required.v1": "אירוע ספק ללא שיחה מוכרת, נדרש בירור",
}


def timeline(case_id: str, limit: int = 200) -> list[dict]:
    out = []
    for e in events.recent(case_id, None, limit):
        p = e["payload"]
        summary = SUMMARY_HE.get(e["type"], e["type"])
        if e["type"] == "followup.policy_evaluated.v1":
            summary = f"{summary}: {p.get('action')}" + (f" · {', '.join(p['blocked_by'])}" if p.get("blocked_by") else "")
        elif e["type"] == "talk.call.status_changed.v1":
            summary = f"{summary}: {p.get('status')}" + (f" · {p['outcome']}" if p.get("outcome") else "")
        out.append({"at": e["occurred_at"], "type": e["type"], "actor": e["actor"], "summary_he": summary, "payload": p})
    return out
