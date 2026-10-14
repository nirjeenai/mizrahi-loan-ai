"""Secure upload links (CONTRACTS §8, 03 §5 S31–S32 → L01–L02): only the token's SHA-256 is stored, a link works until
it expires or its tasks resolve, an unknown token is invalid, and a redeemed link gives a session for that case only."""
from __future__ import annotations

import hashlib
from datetime import timedelta

from fastapi.testclient import TestClient

from app import auth, clock, db
from app.followup import links
from app.main import app
from tests.test_followup_flow import JOURNEY, NO_CONSENT, clean, dispatched_call, wall  # noqa: F401  (fixtures)


def sent_token() -> str:
    return links.sent(JOURNEY)[0]["token"]


def test_the_token_is_stored_as_a_hash_only(wall, monkeypatch):
    dispatched_call(wall)
    token = sent_token()
    row = db.one("SELECT * FROM upload_links WHERE case_id=?", (JOURNEY,))
    assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest() and len(token) >= 40
    dump = " ".join(str(v) for t in ("contact_attempts", "case_events", "policy_decisions", "provider_events")
                    for r in db.query(f"SELECT * FROM {t}") for v in r.values())
    assert token not in dump
    monkeypatch.setenv("APP_ENV", "prod")                      # outside the demo the clear token is never kept
    with db.tx() as c:
        _, other = links.create(c, JOURNEY, [], "PURPOSE_PROOF", 60, clock.now())
    assert db.one("SELECT demo_token FROM upload_links WHERE token_hash=?",
                  (hashlib.sha256(other.encode()).hexdigest(),))["demo_token"] is None


def test_works_twice_then_expires(wall):
    dispatched_call(wall)
    token = sent_token()
    phone = TestClient(app)
    assert phone.post("/api/links/redeem", json={"token": token}).json()["state"] == "ok"
    assert phone.post("/api/links/redeem", json={"token": token}).json()["state"] == "ok"      # not single-use
    wall.advance(minutes=1441)                                                                  # L02
    assert TestClient(app).post("/api/links/redeem", json={"token": token}).json() == {"state": "expired"}


def test_unknown_token_is_invalid_and_sets_no_session():
    r = TestClient(app).post("/api/links/redeem", json={"token": "made-up"})
    assert r.json() == {"state": "invalid"} and auth.COOKIES["customer"] not in r.cookies


def test_resolved_link_still_lands_in_the_app(wall):
    dispatched_call(wall)
    token = sent_token()
    with db.tx() as c:
        c.execute("UPDATE completion_tasks SET status='RESOLVED' WHERE case_id=?", (JOURNEY,))
    r = TestClient(app).post("/api/links/redeem", json={"token": token})                        # L01
    assert r.json()["state"] == "resolved" and r.json()["target"].startswith("/customer/documents")


def test_the_session_is_bound_to_one_case(wall):
    dispatched_call(wall)
    phone = TestClient(app)
    phone.post("/api/links/redeem", json={"token": sent_token()})
    session = auth.verify(phone.cookies.get(auth.COOKIES["customer"]), "customer")
    assert session["s"] == [JOURNEY]
    assert phone.get(f"/api/cases/{JOURNEY}").status_code == 200
    assert phone.get(f"/api/cases/{NO_CONSENT}").status_code == 403
    assert phone.get(f"/api/banker/cases/{JOURNEY}/followup").status_code == 401


def test_link_ttl_comes_from_the_policy(wall):
    dispatched_call(wall)
    row = db.one("SELECT created_at, expires_at FROM upload_links WHERE case_id=?", (JOURNEY,))
    from datetime import datetime
    assert datetime.fromisoformat(row["expires_at"]) - datetime.fromisoformat(row["created_at"]) == timedelta(minutes=1440)
