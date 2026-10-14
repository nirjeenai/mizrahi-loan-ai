"""The Talk status receiver. `apply` holds every functional rule; the mock calls it in-process and the HTTP route
(`api/followup.py`) is a thin wrapper that is off until `TALK_WEBHOOK_SECRET` is set (CONTRACTS §8).

- A duplicate `event_id` changes nothing (`duplicate`).
- An attempt only moves forward (`ATTEMPT_RANK`); a lower or equal rank, or anything after a final status, is
  `ignored`.
- An unknown `client_reference` is stored as an `orphan` and raises `integration.reconciliation_required.v1`.
The event payload stored and emitted never holds a phone number, token or document content."""
from __future__ import annotations

import hmac
import os
from typing import Any, Optional

from .. import clock, db, events
from ..followup.contract import ATTEMPT_RANK, CALL_OUTCOMES

REQUIRED = ("event_id", "client_reference", "status")


class Malformed(ValueError):
    pass


def secret() -> str:
    return os.environ.get("TALK_WEBHOOK_SECRET", "")


def secret_ok(header: Optional[str]) -> bool:
    return bool(secret()) and hmac.compare_digest((header or "").encode(), secret().encode())


def validate(event: Any) -> dict:
    if not isinstance(event, dict) or any(not isinstance(event.get(k), str) or not event.get(k) for k in REQUIRED):
        raise Malformed("event_id, client_reference and status are required")
    if event["status"] not in ATTEMPT_RANK:
        raise Malformed(f"unknown status {event['status']}")
    if event.get("outcome") not in (None, *CALL_OUTCOMES):
        raise Malformed(f"unknown outcome {event['outcome']}")
    return event


def _safe(event: dict) -> dict:
    keep = ("event_id", "event_type", "client_reference", "provider_call_id", "sequence", "status", "outcome", "occurred_at")
    data = {k: v for k, v in (event.get("data") or {}).items() if k in ("link_sent", "callback_at", "identity_verified")}
    return {**{k: event.get(k) for k in keep}, "data": data}


def apply(event: dict, provider: str) -> tuple[str, Optional[dict]]:
    """(result, the attempt row after the event) — result is applied | duplicate | ignored | orphan."""
    event = validate(event)
    now = clock.now_iso()
    safe = _safe(event)
    with db.tx() as c:
        if c.execute("SELECT 1 FROM provider_events WHERE event_id=?", (event["event_id"],)).fetchone():
            return "duplicate", None
        row = c.execute("SELECT * FROM contact_attempts WHERE attempt_id=?", (event["client_reference"],)).fetchone()
        if row is None:
            c.execute("INSERT INTO provider_events(event_id, provider, received_at, attempt_id, payload, result)"
                      " VALUES (?,?,?,?,?,?)", (event["event_id"], provider, now, None, db.jdump(safe), "orphan"))
            events.emit("integration.reconciliation_required.v1", None, f"provider:{provider}",
                        {"event_id": event["event_id"], "client_reference": event["client_reference"],
                         "status": event["status"]}, occurred_at=now, conn=c)
            return "orphan", None
        attempt = dict(row)
        current = ATTEMPT_RANK.get(attempt["status"], 0)
        incoming = ATTEMPT_RANK[event["status"]]
        if current >= 9 or incoming <= current:
            c.execute("INSERT INTO provider_events(event_id, provider, received_at, attempt_id, payload, result)"
                      " VALUES (?,?,?,?,?,?)", (event["event_id"], provider, now, attempt["attempt_id"], db.jdump(safe),
                                               "ignored"))
            return "ignored", attempt
        history = db.jload(attempt["history"], []) + [{"at": now, "status": event["status"],
                                                       "outcome": event.get("outcome"), "event_id": event["event_id"]}]
        c.execute("UPDATE contact_attempts SET status=?, outcome=COALESCE(?, outcome), provider_call_id=COALESCE(?,"
                  " provider_call_id), updated_at=?, history=? WHERE attempt_id=?",
                  (event["status"], event.get("outcome"), event.get("provider_call_id"), now, db.jdump(history),
                   attempt["attempt_id"]))
        c.execute("INSERT INTO provider_events(event_id, provider, received_at, attempt_id, payload, result)"
                  " VALUES (?,?,?,?,?,?)", (event["event_id"], provider, now, attempt["attempt_id"], db.jdump(safe),
                                           "applied"))
        events.emit("talk.call.status_changed.v1", attempt["case_id"], f"provider:{provider}",
                    {"attempt_id": attempt["attempt_id"], "status": event["status"], "outcome": event.get("outcome"),
                     "simulated": bool(attempt["simulated"])}, occurred_at=now, conn=c)
        attempt.update(status=event["status"], outcome=event.get("outcome") or attempt["outcome"], history=history)
    return "applied", attempt
