"""A customer's financial-profile change after the application was confirmed.

The checklist is never edited by hand: the new profile is stored as the case's overlay (bank/mock_bank._overlay) and
`requirements.compose` recomposes it under the policy version already pinned to the case. Newly applicable requirements
appear at once. A requirement the profile no longer needs becomes inactive: its documents and review history stay
(they are only left out of the set the AI evaluates), while the open items that asked for it are closed with a reason —
the customer-action findings, the customer requests and the follow-up tasks — and a simulated call that only concerned
such tasks is canceled before it can run. Banker-review findings stay open: only the banker closes them. Borrower ids
never change, so ownership stays stable."""
from __future__ import annotations

from typing import Any, Optional

from .. import clock, db, events
from ..bank.mock_bank import bank
from ..followup import orchestrator, tasks
from ..store import repo
from ..util import now_iso
from . import engine, requirements

INCOME = ("salaried", "self_employed")
REGISTRATION = ("vat_exempt", "vat_registered")
REASON_HE = "פרופיל ההכנסה עודכן — המסמך אינו נדרש עוד"


class ProfileError(ValueError):
    def __init__(self, message_he: str, status: int = 422):
        super().__init__(message_he)
        self.message_he, self.status = message_he, status


def _validate(case: dict, changes: dict[str, dict]) -> dict[str, dict]:
    if requirements.entity_of(case) != "individual":
        raise ProfileError("במסלול העסקי שינוי פרופיל נעשה מול הבנקאי המלווה", 409)
    people = {b["borrower_id"]: b for b in case["borrowers"]}
    out: dict[str, dict] = {}
    for bid, ch in changes.items():
        if bid not in people:
            raise ProfileError("הלווה אינו שייך לתיק", 404)
        sources = [s for s in INCOME if s in (ch.get("income_sources") or [])]
        if not sources or len(sources) != len(set(ch.get("income_sources") or [])):
            raise ProfileError("נא לבחור לפחות מקור הכנסה אחד")
        reg = ch.get("business_registration")
        if "self_employed" in sources and reg not in REGISTRATION:
            raise ProfileError("לעצמאי/ת נדרש סוג רישום במע״מ (עוסק פטור או עוסק מורשה)")
        out[bid] = {"income_sources": sources, "business_registration": reg if "self_employed" in sources else None,
                    "employment": "self_employed" if sources == ["self_employed"] else "salaried"}
    return out


def change(case_id: str, changes: dict[str, dict], actor: str = "customer") -> dict[str, Any]:
    case = bank.get_case(case_id)
    patch = _validate(case, changes)
    current = {b["borrower_id"]: {k: b.get(k) for k in ("income_sources", "business_registration")} for b in case["borrowers"]}
    if all({k: current[bid][k] for k in ("income_sources", "business_registration")}
           == {k: p[k] for k in ("income_sources", "business_registration")} for bid, p in patch.items()):
        return {"changed": False, "added": [], "removed": [], "requirements": requirements.for_case(case_id)}
    before = {r["code"]: r for r in requirements.for_case(case_id)}
    now = now_iso()
    overlay = (db.one("SELECT overlay FROM profile_overlays WHERE case_id=?", (case_id,)) or {}).get("overlay")
    overlay = db.jload(overlay) if overlay else {"borrowers": {}}
    for bid, p in patch.items():
        overlay["borrowers"][bid] = p
    overlay["changed_at"] = now
    with db.tx() as c:
        c.execute("INSERT INTO profile_overlays(case_id, overlay, updated_at) VALUES (?,?,?) ON CONFLICT(case_id) DO UPDATE"
                  " SET overlay=excluded.overlay, updated_at=excluded.updated_at", (case_id, db.jdump(overlay), now))
    after = {r["code"]: r for r in requirements.for_case(case_id)}
    added = [c for c in after if c not in before]
    removed = [c for c in before if c not in after]
    closed = _close_obsolete(case_id, set(removed), actor, now)
    repo.audit(case_id, actor, "customer_profile_changed", case_id, {
        "before": {bid: current[bid] for bid in patch}, "after": {bid: {k: p[k] for k in ("income_sources", "business_registration")}
                                                                  for bid, p in patch.items()},
        "added": added, "removed": removed, **closed})
    events.emit("case.profile_changed.v1", case_id, actor, {"added": added, "removed": removed, **closed})
    if repo.documents(case_id):
        engine.request_case_review(case_id, "customer profile changed", actor)
    engine.followup_event(case_id, "profile_changed")
    return {"changed": True, "added": [after[c]["title_he"] for c in added], "removed": [before[c]["title_he"] for c in removed],
            "added_codes": added, "removed_codes": removed, **closed, "requirements": list(after.values())}


def _close_obsolete(case_id: str, removed: set[str], actor: str, now: str) -> dict[str, Any]:
    if not removed:
        return {"findings_closed": 0, "requests_closed": 0, "tasks_canceled": [], "calls_canceled": 0}
    docs = {d["document_id"]: d for d in repo.documents(case_id)}
    findings = [f for f in repo.findings(case_id, status="open") if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"
                and tasks.requirement_of(f, docs) in removed]
    for f in findings:
        repo.upsert_finding({**f, "status": "superseded", "resolution": "requirement_inactive", "resolution_note": REASON_HE,
                             "resolved_at": now, "updated_at": now,
                             "history": f["history"] + [{"at": now, "event": "requirement_inactive", "note": REASON_HE}]})
    requests = [q for q in repo.customer_requests(case_id, status="OPEN") if q.get("requirement_code") in removed]
    open_tasks = [t["task_id"] for t in tasks.open_for(case_id) if t["requirement_code"] in removed]
    with db.tx() as c:
        for q in requests:
            c.execute("UPDATE customer_requests SET status='CLOSED', closed_reason='PROFILE_CHANGED', updated_at=?"
                      " WHERE customer_request_id=? AND status='OPEN'", (now, q["customer_request_id"]))
        tasks.set_status(c, case_id, open_tasks, "CANCELED", actor, REASON_HE)
    return {"findings_closed": len(findings), "requests_closed": len(requests), "tasks_canceled": open_tasks,
            "calls_canceled": _cancel_obsolete_calls(case_id)}


def _cancel_obsolete_calls(case_id: str, now: Optional[Any] = None) -> int:
    """A simulated call still queued or ringing whose every task is now closed must not run."""
    now = now or clock.now()
    live = {t["task_id"] for t in tasks.open_for(case_id)}
    stale = [a for a in orchestrator._in_progress(case_id) if not set(a["task_ids"] or []) & live]
    canceled = 0
    for a in stale:
        if a["status"] in ("CONNECTED", "CANCEL_REQUESTED", "CANCEL_FAILED"):
            continue
        orchestrator.handle_talk_event({"event_id": f"{a['attempt_id']}:profile", "event_type": "call.status_changed",
                                        "client_reference": a["attempt_id"], "provider_call_id": a["provider_call_id"],
                                        "sequence": 99, "status": "CANCELED", "occurred_at": orchestrator._iso(now),
                                        "data": {}}, a["provider"], now)
        canceled += 1
    return canceled
