"""The case-event outbox (`case_events`): append-only, versioned facts the timeline, the ops panel and later the bank's
event bus read. The `audit` table stays the record of who did what; an event is the integration-facing fact.

Types are a closed list. A new type is appended to its owner's tuple; a published type is never renamed or reused."""
from __future__ import annotations

import sqlite3
from typing import Any, Optional

from . import db
from .util import new_id, now_iso

DOCUMENT_EVENTS = ("document.uploaded.v1", "document.evaluated.v1")
FOLLOWUP_EVENTS = (
    "completion.required.v1", "completion.resolved.v1", "customer.presence_changed.v1",
    "followup.policy_evaluated.v1", "followup.scheduled.v1", "followup.deferred.v1", "followup.canceled.v1",
    "talk.call.status_changed.v1", "case.ready_for_banker.v1", "contact.permission_changed.v1", "case.profile_changed.v1",
    "case.override_applied.v1", "integration.reconciliation_required.v1", "demo.clock_changed.v1",
)
SETTINGS_EVENTS = (
    "settings.draft_saved.v1", "settings.policy_published.v1", "settings.prompt_published.v1",
    "settings.rollback_applied.v1", "policy.simulation_completed.v1", "settings.kill_switch_changed.v1",
    "settings.draft_discarded.v1",
)
EVENT_TYPES = DOCUMENT_EVENTS + FOLLOWUP_EVENTS + SETTINGS_EVENTS

_INSERT = ("INSERT INTO case_events(event_id, type, case_id, occurred_at, actor, correlation_id, payload)"
           " VALUES (?,?,?,?,?,?,?)")


def emit(event_type: str, case_id: Optional[str], actor: str, payload: Optional[dict[str, Any]] = None,
         correlation_id: Optional[str] = None, occurred_at: Optional[str] = None,
         conn: Optional[sqlite3.Connection] = None) -> str:
    """Append one event; inside a caller's transaction when `conn` is given (db.tx does not nest)."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {event_type}")
    event_id = new_id("EVT")
    row = (event_id, event_type, case_id, occurred_at or now_iso(), actor, correlation_id, db.jdump(payload or {}))
    if conn is not None:
        conn.execute(_INSERT, row)
    else:
        with db.tx() as c:
            c.execute(_INSERT, row)
    return event_id


def recent(case_id: Optional[str] = None, types: Optional[tuple[str, ...]] = None, limit: int = 200) -> list[dict]:
    """Newest first. `case_id=None` means every case (settings events carry no case)."""
    where, params = [], []
    if case_id is not None:
        where.append("case_id=?")
        params.append(case_id)
    if types:
        where.append(f"type IN ({','.join('?' * len(types))})")
        params += list(types)
    sql = "SELECT * FROM case_events" + (" WHERE " + " AND ".join(where) if where else "")
    rows = db.query(sql + " ORDER BY occurred_at DESC, rowid DESC LIMIT ?", (*params, limit))
    for r in rows:
        r["payload"] = db.jload(r["payload"], {})
    return rows
