"""Data access — every read and write of the Mortgage Case Service goes through here."""
from __future__ import annotations

from typing import Any, Optional

from .. import db
from ..util import new_id, now_iso


# ---------------------------------------------------------------- audit
def audit(case_id: Optional[str], actor: str, action: str, target: str = "", detail: Any = None,
          trace_id: str = "") -> None:
    with db.tx() as c:
        c.execute("INSERT INTO audit(at, case_id, actor, action, target, detail, trace_id) VALUES (?,?,?,?,?,?,?)",
                  (now_iso(), case_id, actor, action, target, db.jdump(detail) if detail is not None else None, trace_id))


def audit_events(case_id: str, limit: int = 200) -> list[dict]:
    rows = db.query("SELECT * FROM audit WHERE case_id=? ORDER BY event_id DESC LIMIT ?", (case_id, limit))
    for r in rows:
        r["detail"] = db.jload(r["detail"])
    return rows


# audit actions that are not work on the case: opening it, reads and tool chatter, assistant notes written while a
# conversation is viewed, a refused duplicate upload, and a reset (which wipes the case's audit before it is logged)
NOT_ACTIVITY = ("demo_session_started", "followup_link_redeemed", "mcp_call", "tool_call", "assistant_action_opened",
                "assistant_action_refused", "assistant_actions_offered", "assistant_followup_posted",
                "agent_guard_blocked", "document_upload_duplicate_file", "case_reset")


def last_activity(case_ids: list[str]) -> dict[str, dict]:
    """{case_id: {"event_id", "at"}} of each case's latest audited activity; cases with none are absent."""
    if not case_ids:
        return {}
    # SQLite returns `at` from the row that holds MAX(event_id)
    rows = db.query(f"SELECT case_id, MAX(event_id) AS event_id, at FROM audit"
                    f" WHERE case_id IN ({','.join('?' * len(case_ids))}) AND action NOT IN ({','.join('?' * len(NOT_ACTIVITY))})"
                    " GROUP BY case_id", (*case_ids, *NOT_ACTIVITY))
    return {r["case_id"]: {"event_id": r["event_id"], "at": r["at"]} for r in rows}


def by_latest_activity(case_ids: list[str], last: Optional[dict[str, dict]] = None) -> list[str]:
    """Every case list's order: the most recently worked-on case first (audit order, so ties are impossible); cases
    with no activity keep their given order after them. `last` is `last_activity(case_ids)` when already read."""
    last = last_activity(case_ids) if last is None else last
    return sorted(case_ids, key=lambda cid: -last[cid]["event_id"] if cid in last else 0)


# ---------------------------------------------------------------- documents
def insert_document(row: dict) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO documents(document_id, case_id, borrower_id, requirement_code, filename, mime, sha256,"
                  " bytes, pages, text_layer_chars, storage_path, uploaded_at, uploaded_by, channel, status, stage)"
                  " VALUES (:document_id,:case_id,:borrower_id,:requirement_code,:filename,:mime,:sha256,:bytes,:pages,"
                  ":text_layer_chars,:storage_path,:uploaded_at,:uploaded_by,:channel,:status,:stage)", row)


def document(document_id: str) -> Optional[dict]:
    return db.one("SELECT * FROM documents WHERE document_id=?", (document_id,))


def documents_by_sha(case_id: str, sha: str) -> list[dict]:
    return db.query("SELECT * FROM documents WHERE case_id=? AND sha256=? ORDER BY uploaded_at", (case_id, sha))


def documents(case_id: str) -> list[dict]:
    return db.query("SELECT * FROM documents WHERE case_id=? ORDER BY uploaded_at", (case_id,))


def set_document(document_id: str, **fields: Any) -> None:
    keys = ", ".join(f"{k}=:{k}" for k in fields)
    with db.tx() as c:
        c.execute(f"UPDATE documents SET {keys} WHERE document_id=:document_id", {**fields, "document_id": document_id})


# ---------------------------------------------------------------- review runs
def start_run(run: dict) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO review_runs(run_id, case_id, document_id, scope, provider, models, rubric_id, rubric_version,"
                  " prompt_version, status, stage, started_at, input_hash, trigger) VALUES (:run_id,:case_id,:document_id,"
                  ":scope,:provider,:models,:rubric_id,:rubric_version,:prompt_version,:status,:stage,:started_at,"
                  ":input_hash,:trigger)", run)


def update_run(run_id: str, **fields: Any) -> None:
    keys = ", ".join(f"{k}=:{k}" for k in fields)
    with db.tx() as c:
        c.execute(f"UPDATE review_runs SET {keys} WHERE run_id=:run_id", {**fields, "run_id": run_id})


def run(run_id: str) -> Optional[dict]:
    row = db.one("SELECT * FROM review_runs WHERE run_id=?", (run_id,))
    if row:
        row["result"], row["models"] = db.jload(row["result"]), db.jload(row["models"])
    return row


def runs(case_id: str, document_id: Optional[str] = None, include_result: bool = False) -> list[dict]:
    sql = "SELECT * FROM review_runs WHERE case_id=?" + (" AND document_id=?" if document_id else "") + " ORDER BY started_at DESC"
    rows = db.query(sql, (case_id, document_id) if document_id else (case_id,))
    for r in rows:
        r["models"] = db.jload(r["models"])
        r["result"] = db.jload(r["result"]) if include_result else None
    return rows


def latest_document_result(document_id: str) -> Optional[dict]:
    row = db.one("SELECT result FROM review_runs WHERE document_id=? AND scope='document' AND status='succeeded'"
                 " ORDER BY started_at DESC LIMIT 1", (document_id,))
    return db.jload(row["result"]) if row else None


def latest_case_result(case_id: str) -> Optional[dict]:
    row = db.one("SELECT result FROM review_runs WHERE case_id=? AND scope='case' AND status='succeeded'"
                 " ORDER BY started_at DESC LIMIT 1", (case_id,))
    return db.jload(row["result"]) if row else None


# ---------------------------------------------------------------- findings
def findings(case_id: str, status: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM findings WHERE case_id=?" + (" AND status=?" if status else "") + " ORDER BY created_at"
    rows = db.query(sql, (case_id, status) if status else (case_id,))
    for r in rows:
        for k in ("detail", "evidence", "history"):
            r[k] = db.jload(r[k], [] if k != "detail" else {})
    return rows


def finding(finding_id: str) -> Optional[dict]:
    rows = db.query("SELECT * FROM findings WHERE finding_id=?", (finding_id,))
    if not rows:
        return None
    r = rows[0]
    for k in ("detail", "evidence", "history"):
        r[k] = db.jload(r[k], [] if k != "detail" else {})
    return r


def upsert_finding(row: dict) -> None:
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO findings(finding_id, case_id, key, code, severity, review_state, status,"
                  " borrower_id, document_id, period, title_he, message_he, detail, evidence, created_run_id, created_at,"
                  " updated_at, resolved_run_id, resolved_at, resolution, resolution_note, superseded_by, history)"
                  " VALUES (:finding_id,:case_id,:key,:code,:severity,:review_state,:status,:borrower_id,:document_id,"
                  ":period,:title_he,:message_he,:detail,:evidence,:created_run_id,:created_at,:updated_at,"
                  ":resolved_run_id,:resolved_at,:resolution,:resolution_note,:superseded_by,:history)",
                  {**row, "detail": db.jdump(row.get("detail") or {}), "evidence": db.jdump(row.get("evidence") or []),
                   "history": db.jdump(row.get("history") or [])})


# ---------------------------------------------------------------- statements, conversation, handoffs
def add_statement(case_id: str, finding_id: Optional[str], text: str, channel: str, actor: str,
                  request_id: Optional[str]) -> dict:
    existing = db.one("SELECT * FROM statements WHERE request_id=?", (request_id,)) if request_id else None
    if existing:
        return existing
    row = {"statement_id": new_id("ST"), "case_id": case_id, "finding_id": finding_id, "channel": channel,
           "text": text, "actor": actor, "created_at": now_iso(), "request_id": request_id}
    with db.tx() as c:
        c.execute("INSERT INTO statements VALUES (:statement_id,:case_id,:finding_id,:channel,:text,:actor,:created_at,:request_id)", row)
    return row


def statements(case_id: str) -> list[dict]:
    return db.query("SELECT * FROM statements WHERE case_id=? ORDER BY created_at", (case_id,))


def add_turn(case_id: str, channel: str, role: str, text: str, provenance: Any = None, tool_calls: Any = None) -> dict:
    row = {"turn_id": new_id("T"), "case_id": case_id, "conversation_id": f"CONV-{case_id}", "channel": channel,
           "role": role, "text": text, "provenance": db.jdump(provenance) if provenance else None,
           "tool_calls": db.jdump(tool_calls) if tool_calls else None, "created_at": now_iso()}
    with db.tx() as c:
        c.execute("INSERT INTO turns VALUES (:turn_id,:case_id,:conversation_id,:channel,:role,:text,:provenance,:tool_calls,:created_at)", row)
    return row


def turns(case_id: str, limit: int = 200) -> list[dict]:
    rows = db.query("SELECT * FROM (SELECT rowid AS rid, * FROM turns WHERE case_id=? ORDER BY created_at DESC, rid DESC LIMIT ?)"
                    " ORDER BY created_at, rid", (case_id, limit))
    for r in rows:
        r.pop("rid", None)
        r["provenance"], r["tool_calls"] = db.jload(r["provenance"]), db.jload(r["tool_calls"])
    return rows


def turn(turn_id: str) -> Optional[dict]:
    row = db.one("SELECT * FROM turns WHERE turn_id=?", (turn_id,))
    if row:
        row["provenance"], row["tool_calls"] = db.jload(row["provenance"]), db.jload(row["tool_calls"])
    return row


def handoff_by_request(request_id: str) -> Optional[dict]:
    return db.one("SELECT * FROM handoffs WHERE request_id=?", (request_id,))


def handoffs(case_id: str) -> list[dict]:
    rows = db.query("SELECT * FROM handoffs WHERE case_id=? ORDER BY created_at DESC, rowid DESC", (case_id,))
    for r in rows:
        r["package"] = db.jload(r["package"])
    return rows


def insert_handoff(row: dict) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO handoffs(package_id, case_id, status, created_at, created_by, channel, note, package, request_id)"
                  " VALUES (:package_id,:case_id,:status,:created_at,:created_by,:channel,:note,:package,:request_id)",
                  {**row, "package": db.jdump(row["package"])})


def decide_handoff(package_id: str, decision: str, note: str) -> None:
    with db.tx() as c:
        c.execute("UPDATE handoffs SET banker_decision=?, decided_at=?, decided_note=?, status=? WHERE package_id=?",
                  (decision, now_iso(), note, "DECIDED", package_id))


# ---------------------------------------------------------------- upload intents (assistant action → upload)
def save_upload_intent(row: dict) -> None:
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO upload_intents(document_id, case_id, requirement_code, expected_period, action_id,"
                  " origin_turn_id, created_new, created_at, followup_turn_id, replaces_document_id) VALUES (:document_id,"
                  ":case_id,:requirement_code,:expected_period,:action_id,:origin_turn_id,:created_new,:created_at,NULL,"
                  ":replaces_document_id)", {"replaces_document_id": None, **row})


def upload_intent(document_id: str) -> Optional[dict]:
    return db.one("SELECT * FROM upload_intents WHERE document_id=?", (document_id,))


def replacement_intents(case_id: str) -> list[dict]:
    """Uploads the customer made to replace a document the AI review sent back (no banker request involved)."""
    return db.query("SELECT document_id, replaces_document_id, created_at FROM upload_intents WHERE case_id=?"
                    " AND replaces_document_id IS NOT NULL ORDER BY created_at", (case_id,))


def upload_intents_awaiting_followup(case_id: str) -> list[dict]:
    return db.query("SELECT * FROM upload_intents WHERE case_id=? AND origin_turn_id IS NOT NULL AND followup_turn_id IS NULL"
                    " ORDER BY created_at", (case_id,))


def set_upload_followup(document_ids: list[str], turn_id: str) -> None:
    with db.tx() as c:
        c.executemany("UPDATE upload_intents SET followup_turn_id=? WHERE document_id=?", [(turn_id, d) for d in document_ids])


# ---------------------------------------------------------------- banker decisions (append-only) and customer requests
def _decision_row(r: dict) -> dict:
    r["finding_ids"], r["evidence_refs"] = db.jload(r["finding_ids"], []), db.jload(r["evidence_refs"], [])
    return r


def decision_by_request(request_id: str) -> Optional[dict]:
    row = db.one("SELECT * FROM banker_decisions WHERE request_id=?", (request_id,))
    return _decision_row(row) if row else None


def decisions(case_id: str, document_id: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM banker_decisions WHERE case_id=?" + (" AND document_id=?" if document_id else "") + \
          " ORDER BY created_at, rowid"
    return [_decision_row(r) for r in db.query(sql, (case_id, document_id) if document_id else (case_id,))]


def insert_decision(row: dict, request_row: Optional[dict] = None, finding_rows: Optional[list[dict]] = None,
                    audit_row: Optional[dict] = None, handoff_row: Optional[dict] = None,
                    handoff_decision: Optional[tuple[str, str, str]] = None) -> None:
    """One transaction: the decision, the customer request it opens, the findings it rules on, the handoff it creates or
    decides, and its audit event."""
    with db.tx() as c:
        if handoff_row:
            c.execute("INSERT INTO handoffs(package_id, case_id, status, created_at, created_by, channel, note, package, request_id,"
                      " banker_decision, decided_at, decided_note) VALUES (:package_id,:case_id,:status,:created_at,:created_by,"
                      ":channel,:note,:package,:request_id,:banker_decision,:decided_at,:decided_note)",
                      {"banker_decision": None, "decided_at": None, "decided_note": None, **handoff_row,
                       "package": db.jdump(handoff_row["package"])})
        if handoff_decision:
            package_id, decision, note = handoff_decision
            c.execute("UPDATE handoffs SET banker_decision=?, decided_at=?, decided_note=?, status=? WHERE package_id=?",
                      (decision, row["created_at"], note, "DECIDED", package_id))
        c.execute("INSERT INTO banker_decisions(decision_id, case_id, target_kind, document_id, finding_id, borrower_id, period,"
                  " action, previous_status, new_status, rationale, customer_message, customer_request_id, finding_ids,"
                  " evidence_refs, actor_id, actor_name, created_at, request_id, reason_code) VALUES (:decision_id,:case_id,"
                  ":target_kind,:document_id,:finding_id,:borrower_id,:period,:action,:previous_status,:new_status,:rationale,"
                  ":customer_message,:customer_request_id,:finding_ids,:evidence_refs,:actor_id,:actor_name,:created_at,"
                  ":request_id,:reason_code)", {**row, "reason_code": row.get("reason_code"),
                                                "finding_ids": db.jdump(row.get("finding_ids") or []),
                                                "evidence_refs": db.jdump(row.get("evidence_refs") or [])})
        if request_row:
            c.execute("INSERT INTO customer_requests(customer_request_id, case_id, kind, borrower_id, requirement_code, period,"
                      " document_id, finding_id, title_he, message_he, status, created_at, created_by, created_by_name,"
                      " decision_id, responded_document_id, responded_at, updated_at) VALUES (:customer_request_id,:case_id,"
                      ":kind,:borrower_id,:requirement_code,:period,:document_id,:finding_id,:title_he,:message_he,:status,"
                      ":created_at,:created_by,:created_by_name,:decision_id,NULL,NULL,:updated_at)", request_row)
        for request_id in row.get("closes_requests") or []:
            c.execute("UPDATE customer_requests SET status='CLOSED', closed_reason=?, updated_at=? WHERE customer_request_id=?"
                      " AND status='OPEN'", (row["action"], row["created_at"], request_id))
        for f in finding_rows or []:
            c.execute("UPDATE findings SET status=:status, resolution=:resolution, resolution_note=:resolution_note,"
                      " resolved_at=:resolved_at, updated_at=:updated_at, superseded_by=:superseded_by, history=:history"
                      " WHERE finding_id=:finding_id",
                      {k: f.get(k) for k in ("status", "resolution", "resolution_note", "resolved_at", "updated_at",
                                             "superseded_by", "finding_id")} | {"history": db.jdump(f["history"])})
        if audit_row:
            c.execute("INSERT INTO audit(at, case_id, actor, action, target, detail, trace_id) VALUES (?,?,?,?,?,?,?)",
                      (row["created_at"], audit_row["case_id"], audit_row["actor"], audit_row["action"], audit_row["target"],
                       db.jdump(audit_row["detail"]), ""))


def customer_requests(case_id: str, status: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM customer_requests WHERE case_id=?" + (" AND status=?" if status else "") + " ORDER BY created_at, rowid"
    return db.query(sql, (case_id, status) if status else (case_id,))


def customer_request(request_id: str) -> Optional[dict]:
    return db.one("SELECT * FROM customer_requests WHERE customer_request_id=?", (request_id,))


def respond_customer_request(request_id: str, document_id: Optional[str] = None, statement_id: Optional[str] = None) -> bool:
    """OPEN → RESPONDED once, with the uploaded document or the written reply; a second answer changes nothing."""
    now = now_iso()
    with db.tx() as c:
        cur = c.execute("UPDATE customer_requests SET status='RESPONDED', responded_document_id=?, responded_statement_id=?,"
                        " responded_at=?, updated_at=? WHERE customer_request_id=? AND status='OPEN'",
                        (document_id, statement_id, now, now, request_id))
        return cur.rowcount == 1


def statement(statement_id: str) -> Optional[dict]:
    return db.one("SELECT * FROM statements WHERE statement_id=?", (statement_id,))


# ---------------------------------------------------------------- case state
def case_state(case_id: str) -> Optional[dict]:
    row = db.one("SELECT * FROM case_state WHERE case_id=?", (case_id,))
    if row:
        row["readiness"] = db.jload(row["readiness"])
    return row


def save_case_state(case_id: str, readiness: dict, last_case_run_id: Optional[str]) -> None:
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO case_state(case_id, readiness, updated_at, last_case_run_id) VALUES (?,?,?,?)",
                  (case_id, db.jdump(readiness), now_iso(), last_case_run_id))


CASE_TABLES = ("documents", "review_runs", "findings", "statements", "turns", "audit", "jobs", "handoffs", "case_state",
               "upload_intents", "banker_decisions", "customer_requests", "case_profile", "completion_tasks",
               "contact_plans", "contact_attempts", "policy_decisions", "customer_presence", "contact_preferences",
               "case_events", "case_overrides", "upload_links", "profile_overlays")


def reset_case(case_id: str) -> None:
    with db.tx() as c:
        for table in CASE_TABLES:
            c.execute(f"DELETE FROM {table} WHERE case_id=?", (case_id,))
