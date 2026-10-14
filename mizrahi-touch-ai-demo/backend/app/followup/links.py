"""Secure upload links sent during a follow-up contact (CONTRACTS §8).

The token is 32 random bytes; only its SHA-256 is stored. A link is scoped to one case and the tasks it was sent for,
expires after `talk.link_ttl_minutes`, and works until then or until its tasks are resolved (it is not single-use, so a
presenter can open it twice). In the demo environment the clear token is also kept (`demo_token`) so the presenter
can open the link that was "sent"; outside the demo that column stays NULL."""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .. import clock, db
from ..util import new_id

TARGET = "/customer/documents?req={code}"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def url(token: str) -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}/customer/link#t={token}"


def create(c: sqlite3.Connection, case_id: str, task_ids: list[str], requirement_code: Optional[str],
           ttl_minutes: int, now: datetime, attempt_id: Optional[str] = None) -> tuple[str, str]:
    """(link_id, clear token) inside the caller's transaction. The token is returned once and never stored in clear
    outside the demo."""
    token = secrets.token_urlsafe(32)
    link_id = new_id("LNK")
    c.execute("INSERT INTO upload_links(link_id, token_hash, case_id, task_ids, requirement_code, created_at, expires_at,"
              " attempt_id, demo_token) VALUES (?,?,?,?,?,?,?,?,?)",
              (link_id, _hash(token), case_id, db.jdump(task_ids), requirement_code, now.isoformat(timespec="seconds"),
               (now + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds"), attempt_id,
               token if clock.environment() == "demo" else None))
    return link_id, token


def _resolved(task_ids: list[str]) -> bool:
    if not task_ids:
        return False
    rows = db.query(f"SELECT status FROM completion_tasks WHERE task_id IN ({','.join('?' * len(task_ids))})",
                    tuple(task_ids))
    return bool(rows) and all(r["status"] in ("RESOLVED", "CANCELED") for r in rows)


def state(row: dict, now: datetime) -> str:
    if _resolved(db.jload(row["task_ids"], [])):
        return "resolved"
    if now >= datetime.fromisoformat(row["expires_at"]):
        return "expired"
    return "ok"


def redeem(token: str, now: Optional[datetime] = None) -> dict:
    """{state: ok|resolved|expired|invalid, case_id?, target?}. The caller issues the case-bound session for ok and
    resolved (so the customer lands on "already received" in the app)."""
    now = now or clock.now()
    row = db.one("SELECT * FROM upload_links WHERE token_hash=?", (_hash(token or ""),)) if token else None
    if row is None:
        return {"state": "invalid"}
    st = state(row, now)
    out = {"state": st, "case_id": row["case_id"]}
    if st in ("ok", "resolved"):
        out["target"] = TARGET.format(code=row["requirement_code"] or "")
    return out


def sent(case_id: str, now: Optional[datetime] = None) -> list[dict]:
    """Links of a case for the demo presenter (clear token only where the demo kept it)."""
    now = now or clock.now()
    rows = db.query("SELECT * FROM upload_links WHERE case_id=? ORDER BY created_at DESC", (case_id,))
    return [{"link_id": r["link_id"], "requirement_code": r["requirement_code"], "created_at": r["created_at"],
             "expires_at": r["expires_at"], "attempt_id": r["attempt_id"], "state": state(r, now),
             "token": r["demo_token"], "url": url(r["demo_token"]) if r["demo_token"] else None} for r in rows]
