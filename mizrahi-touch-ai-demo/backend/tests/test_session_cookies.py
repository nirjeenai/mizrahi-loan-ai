"""Sessions of different app instances on one host never overwrite each other, and every 401 names the session that
would satisfy it, the cause of the intermittent "נדרש חיבור לתיק." when a preview or isolated stack ran beside the
main instance on 127.0.0.1 (cookies are scoped by host, not port)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import auth
from app.main import app

CASE = "DEMO-MTZ-2026-001"


def test_cookie_names_follow_the_instance_secret(monkeypatch):
    own = (auth.COOKIES["customer"], auth.COOKIES["staff"])
    assert own[0].startswith("mzl_customer_") and own[1].startswith("mzl_staff_") and own[0] != own[1]
    assert auth.COOKIES["customer"] == own[0]                       # stable for the same secret (survives restarts)
    monkeypatch.setenv("SESSION_SECRET", "another-instance")
    assert auth.COOKIES["customer"] not in own and auth.COOKIES["staff"] not in own


def test_another_instances_cookie_leaves_this_session_intact(monkeypatch):
    c = TestClient(app)
    assert c.post("/api/session/demo/customer", json={"case_id": CASE}).status_code == 200
    assert c.get(f"/api/cases/{CASE}").status_code == 200
    # a second instance (its own secret) signs a session for the same host: a different cookie, not a replacement
    monkeypatch.setenv("SESSION_SECRET", "another-instance")
    other_name = auth.COOKIES["customer"]
    other_token = auth.issue("customer", [CASE])
    monkeypatch.delenv("SESSION_SECRET")
    c.cookies.set(other_name, other_token)
    assert c.get(f"/api/cases/{CASE}").status_code == 200


def test_every_401_names_the_session_to_renew():
    anon = TestClient(app)
    r = anon.get(f"/api/cases/{CASE}")
    assert r.status_code == 401 and r.headers[auth.AUTH_HEADER] == "customer" and r.json()["detail"] == auth.NEED_CUSTOMER
    r = anon.get("/api/banker/cases")
    assert r.status_code == 401 and r.headers[auth.AUTH_HEADER] == "staff" and r.json()["detail"] == auth.NEED_STAFF
    r = anon.get("/api/documents/DOC-NOPE")                         # staff or customer may read a document
    assert r.status_code == 401 and r.headers[auth.AUTH_HEADER] == "staff, customer"
