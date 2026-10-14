"""The Talk status receiver (CONTRACTS §8, 03 §5 S19–S20, S35–S36 → W01–W06): dedupe, forward-only ranks, a final
status is never overwritten, orphans raise a reconciliation event; the HTTP route is off until a secret is set."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import db, events
from app.comms import webhook
from app.followup import orchestrator
from app.main import app
from tests.test_followup_flow import JOURNEY, clean, dispatched_call, wall  # noqa: F401  (fixtures)


def event(attempt: dict, event_id: str, status: str, sequence: int, outcome=None, **data) -> dict:
    return {"event_id": event_id, "event_type": "call.status_changed", "client_reference": attempt["attempt_id"],
            "provider_call_id": attempt["provider_call_id"], "sequence": sequence, "status": status, "outcome": outcome,
            "occurred_at": "2026-10-13T08:30:00+00:00", "data": data}


def status(attempt_id: str) -> str:
    return db.one("SELECT status FROM contact_attempts WHERE attempt_id=?", (attempt_id,))["status"]


def test_duplicates_lower_ranks_and_finals(wall):
    a = dispatched_call(wall)
    assert orchestrator.handle_talk_event(event(a, "E1", "CONNECTED", 2), "jeen-talk") == "applied"
    assert orchestrator.handle_talk_event(event(a, "E1", "CONNECTED", 2), "jeen-talk") == "duplicate"      # W01
    assert orchestrator.handle_talk_event(event(a, "E0", "DIALING", 1), "jeen-talk") == "ignored"         # W02: late
    assert status(a["attempt_id"]) == "CONNECTED"
    assert orchestrator.handle_talk_event(event(a, "E2", "NO_ANSWER", 3, "NO_ANSWER"), "jeen-talk") == "applied"
    assert orchestrator.handle_talk_event(event(a, "E3", "COMPLETED", 4, "LINK_SENT"), "jeen-talk") == "ignored"  # W03
    assert status(a["attempt_id"]) == "NO_ANSWER"
    results = {r["event_id"]: r["result"] for r in db.query("SELECT event_id, result FROM provider_events")}
    assert results == {**{k: v for k, v in results.items() if k.startswith("MOCK-")},
                       "E1": "applied", "E0": "ignored", "E2": "applied", "E3": "ignored"}


def test_orphan_is_stored_and_raises_reconciliation():
    orphan = {"event_id": "E-ORPHAN", "client_reference": "ATT-NOT-OURS", "status": "COMPLETED", "outcome": "LINK_SENT"}
    assert orchestrator.handle_talk_event(orphan, "jeen-talk") == "orphan"
    assert db.one("SELECT result FROM provider_events WHERE event_id='E-ORPHAN'")["result"] == "orphan"
    assert events.recent(None, ("integration.reconciliation_required.v1",), 1)[0]["payload"]["client_reference"] == "ATT-NOT-OURS"


def test_unknown_status_holds_further_contact(wall):
    a = dispatched_call(wall)
    orchestrator.handle_talk_event(event(a, "E-U", "UNKNOWN", 2), "jeen-talk")                            # W04
    orchestrator.on_event(JOURNEY, "test")
    assert orchestrator.plan(JOURNEY)["decision"]["blocked_by"] == ["OP-ATTEMPT-UNKNOWN"]
    assert len(orchestrator.attempts(JOURNEY)) == 1


def test_callback_requested_and_refused(wall):
    a = dispatched_call(wall)
    later = "2026-10-13T14:00:00+00:00"                                                                  # 17:00 Israel
    orchestrator.handle_talk_event(event(a, "E-CB", "COMPLETED", 3, "CALLBACK_REQUESTED", callback_at=later), "mock-talk")
    d = orchestrator.plan(JOURNEY)["decision"]                                                          # W05
    assert d["action"] == "SCHEDULE_CALL" and "PREF-CALLBACK" in d["rule_ids"]
    assert datetime.fromisoformat(d["next_eligible_at"]) == datetime.fromisoformat(later)
    wall.advance(hours=6, minutes=10)
    orchestrator.tick()
    second = orchestrator.attempts(JOURNEY)[-1]
    assert len(orchestrator.attempts(JOURNEY)) == 2
    orchestrator.handle_talk_event(event(second, "E-REF", "COMPLETED", 3, "REFUSED"), "mock-talk")       # W06
    assert orchestrator.preferences(JOURNEY)["opt_out_voice"] is True and orchestrator.plan(JOURNEY)["state"] == "CANCELED"


def test_malformed_events_are_rejected():
    for bad in ({}, {"event_id": "x", "client_reference": "y"}, {"event_id": "x", "client_reference": "y", "status": "MADE_UP"},
                {"event_id": "x", "client_reference": "y", "status": "COMPLETED", "outcome": "MADE_UP"}):
        with pytest.raises(webhook.Malformed):
            webhook.apply(bad, "jeen-talk")


def test_http_receiver_is_off_until_a_secret_is_set(wall, monkeypatch):
    a = dispatched_call(wall)
    http = TestClient(app)
    body = event(a, "E-HTTP", "CONNECTED", 2)
    monkeypatch.delenv("TALK_WEBHOOK_SECRET", raising=False)
    assert http.post("/api/webhooks/jeen-talk", json=body).status_code == 404
    monkeypatch.setenv("TALK_WEBHOOK_SECRET", "s3cret-for-tests")
    assert http.post("/api/webhooks/jeen-talk", json=body).status_code == 401
    assert http.post("/api/webhooks/jeen-talk", json=body, headers={"X-Talk-Secret": "wrong"}).status_code == 401
    ok = {"X-Talk-Secret": "s3cret-for-tests"}
    r = http.post("/api/webhooks/jeen-talk", json=body, headers=ok)
    assert (r.status_code, r.json()) == (200, {"result": "applied"})
    assert http.post("/api/webhooks/jeen-talk", json=body, headers=ok).json() == {"result": "duplicate"}
    orphan = {**body, "event_id": "E-HTTP-2", "client_reference": "ATT-NOPE"}
    assert http.post("/api/webhooks/jeen-talk", json=orphan, headers=ok).status_code == 202
    assert http.post("/api/webhooks/jeen-talk", content=b"not json", headers=ok).status_code == 400
