"""Completion tasks: one open task per (case, requirement, reason), derived from the open customer-facing findings and
the banker's open requests. Nothing here talks to the customer; the orchestrator decides what a task leads to.

- An AI finding and a banker request on the same requirement merge into one task, worded as the banker wrote it (S29).
- A task is *unverified* while a banker item is open on its requirement or a review of its documents failed: such a
  task routes to human review, never to contact (S15, S33).
- A task resolves only when a document uploaded after the task was opened, for its requirement, passed review (no open
  finding on it). An issue that disappears any other way (a banker dismissal, a reset) cancels the task instead."""
from __future__ import annotations

import sqlite3
from typing import Any, Optional

from .. import clock, db, events
from ..review.reason_codes import CUSTOMER_SHORT
from ..store import repo
from ..util import new_id
from .contract import TASK_STATUSES

CLOSED = ("RESOLVED", "CANCELED")
OPEN = tuple(s for s in TASK_STATUSES if s not in CLOSED)
BANKER_REQUEST = "BANKER_REQUEST"


def requirement_of(finding: dict, docs: dict[str, dict]) -> Optional[str]:
    code = (finding.get("detail") or {}).get("requirement_code")
    if code:
        return code
    if finding.get("document_id") and finding["document_id"] in docs:
        return docs[finding["document_id"]]["requirement_code"]
    return f"PAYSLIPS:{finding['borrower_id']}" if finding.get("borrower_id") else None


def _issues(case_id: str, docs: dict[str, dict], open_f: list[dict]) -> dict[str, dict]:
    issues: dict[str, dict] = {}
    for f in open_f:
        if f["review_state"] != "CUSTOMER_ACTION_REQUIRED":
            continue
        req = requirement_of(f, docs)
        if not req:
            continue
        key = f"{req}|{f['code']}"
        item = issues.setdefault(key, {"requirement_code": req, "reason_code": f["code"], "title_he": f["title_he"],
                                       "customer_text_he": CUSTOMER_SHORT.get(f["code"], f["title_he"]),
                                       "finding_ids": []})
        item["finding_ids"].append(f["finding_id"])
    for q in repo.customer_requests(case_id, status="OPEN"):
        req = q.get("requirement_code") or (f"PAYSLIPS:{q['borrower_id']}" if q.get("borrower_id") else None)
        if not req:
            continue
        same = [i for i in issues.values() if i["requirement_code"] == req]
        target = same[0] if same else issues.setdefault(f"{req}|{BANKER_REQUEST}", {
            "requirement_code": req, "reason_code": BANKER_REQUEST, "finding_ids": []})
        target.update({"title_he": q.get("title_he") or q["message_he"][:80], "customer_text_he": q["message_he"],
                       "request_id": q["customer_request_id"]})
    return issues


def _unverified(docs: dict[str, dict], open_f: list[dict]) -> set[str]:
    out = {requirement_of(f, docs) for f in open_f if f["review_state"] == "NEEDS_BANKER_REVIEW"}
    out |= {d["requirement_code"] for d in docs.values() if d["status"] == "failed"}
    return {r for r in out if r}


def _passed(case_id: str, task: dict, docs: dict[str, dict], open_f: list[dict]) -> Optional[str]:
    """A document for the task's requirement that arrived after the task opened and has no open finding."""
    known = set((task.get("history") or [{}])[0].get("known_documents") or [])
    flagged = {f["document_id"] for f in open_f if f.get("document_id")}
    for d in docs.values():
        if (d["requirement_code"] == task["requirement_code"] and d["document_id"] not in known
                and d["status"] == "reviewed" and d["document_id"] not in flagged):
            return d["document_id"]
    return None


def _row(r: dict) -> dict:
    r["history"] = db.jload(r.get("history"), [])
    return r


def all_for(case_id: str) -> list[dict]:
    return [_row(r) for r in db.query("SELECT * FROM completion_tasks WHERE case_id=? ORDER BY created_at, rowid",
                                      (case_id,))]


def open_for(case_id: str) -> list[dict]:
    """Open tasks with their `verified` flag (computed now, never stored)."""
    docs = {d["document_id"]: d for d in repo.documents(case_id)}
    unverified = _unverified(docs, repo.findings(case_id, status="open"))
    return [{**t, "verified": t["requirement_code"] not in unverified} for t in all_for(case_id) if t["status"] in OPEN]


def sync(case_id: str, actor: str = "followup") -> dict[str, list[str]]:
    """Bring the task list in line with the open issues. Returns the ids opened, resolved and canceled."""
    docs = {d["document_id"]: d for d in repo.documents(case_id)}
    open_f = repo.findings(case_id, status="open")
    issues = _issues(case_id, docs, open_f)
    now = clock.now_iso()
    out: dict[str, list[str]] = {"opened": [], "resolved": [], "canceled": []}
    with db.tx() as c:
        current = {r["issue_key"]: _row(dict(r)) for r in c.execute(
            f"SELECT * FROM completion_tasks WHERE case_id=? AND status IN ({','.join('?' * len(OPEN))})",
            (case_id, *OPEN)).fetchall()}
        for key, issue in issues.items():
            task = current.get(key)
            if task:
                if (task["title_he"], task["customer_text_he"]) != (issue["title_he"], issue["customer_text_he"]):
                    c.execute("UPDATE completion_tasks SET title_he=?, customer_text_he=?, updated_at=? WHERE task_id=?",
                              (issue["title_he"], issue["customer_text_he"], now, task["task_id"]))
                continue
            tid = new_id("TSK")
            known = sorted(d for d, row in docs.items() if row["requirement_code"] == issue["requirement_code"])
            history = [{"at": now, "status": "OPEN", "by": actor, "known_documents": known,
                        "finding_ids": issue["finding_ids"], "request_id": issue.get("request_id")}]
            c.execute("INSERT INTO completion_tasks(task_id, case_id, requirement_code, reason_code, status, issue_key,"
                      " title_he, customer_text_he, created_at, updated_at, history) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (tid, case_id, issue["requirement_code"], issue["reason_code"], "OPEN", key, issue["title_he"],
                       issue["customer_text_he"], now, now, db.jdump(history)))
            events.emit("completion.required.v1", case_id, actor, {"task_id": tid, "requirement_code":
                        issue["requirement_code"], "reason_code": issue["reason_code"]}, occurred_at=now, conn=c)
            out["opened"].append(tid)
        for key, task in current.items():
            if key in issues:
                continue
            doc = _passed(case_id, task, docs, open_f)
            status = "RESOLVED" if doc else "CANCELED"
            _set(c, task, status, actor, now, document_id=doc,
                 note="מסמך חדש עבר בדיקה" if doc else "הדרישה נסגרה ללא מסמך חדש")
            if doc:
                events.emit("completion.resolved.v1", case_id, actor, {"task_id": task["task_id"],
                            "requirement_code": task["requirement_code"], "document_id": doc}, occurred_at=now, conn=c)
            out["resolved" if doc else "canceled"].append(task["task_id"])
    return out


def _set(c: sqlite3.Connection, task: dict, status: str, actor: str, now: str, document_id: Optional[str] = None,
         note: str = "") -> None:
    history = (task.get("history") or []) + [{"at": now, "status": status, "by": actor, "note": note}]
    c.execute("UPDATE completion_tasks SET status=?, updated_at=?, history=?, document_id=COALESCE(?, document_id),"
              " resolved_at=CASE WHEN ? IN ('RESOLVED','CANCELED') THEN ? ELSE resolved_at END WHERE task_id=?",
              (status, now, db.jdump(history), document_id, status, now, task["task_id"]))


def set_status(c: sqlite3.Connection, case_id: str, task_ids: Any, status: str, actor: str, note: str = "") -> None:
    """Move open tasks to `status` inside the caller's transaction (no-op for a task already there or closed)."""
    assert status in TASK_STATUSES
    now = clock.now_iso()
    for tid in task_ids:
        row = c.execute("SELECT * FROM completion_tasks WHERE task_id=? AND case_id=?", (tid, case_id)).fetchone()
        if row and row["status"] in OPEN and row["status"] != status:
            _set(c, _row(dict(row)), status, actor, now, note=note)
