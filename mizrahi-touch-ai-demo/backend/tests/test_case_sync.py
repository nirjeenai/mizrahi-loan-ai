"""One case catalogue for the whole app: every prepared case and every application confirmed in the customer chat is in
the banker's case list, the customer app's case selector and the banker's three views (V1 review and V3 case
workspace read /workspace, V2 reads /intelligence) — at once, without a restart or a sync step."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.bank import mock_bank
from app.bank.mock_bank import bank
from app.config import BACKEND_DIR, settings
from app.main import app
from app.policy import store

from tests.test_onboarding_v2 import Chat, personal

PAYSLIP = Path(__file__).resolve().parents[2] / "fixtures" / "out" / "main" / "ido_payslip_2026-07.pdf"


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


def staff() -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIES["staff"], auth.issue("staff", "STAFF-DANA"))
    return c


def views_open(c: TestClient, case_id: str) -> dict:
    for path in (f"/api/banker/cases/{case_id}/workspace", f"/api/banker/cases/{case_id}/intelligence"):
        assert c.get(path).status_code == 200, path
    return c.get(f"/api/banker/cases/{case_id}/workspace").json()


def test_every_prepared_case_is_in_the_banker_list_and_opens_in_every_view():
    c = staff()
    rows = {r["case_id"]: r for r in c.get("/api/banker/cases").json()}
    assert set(mock_bank._CASES) <= set(rows)
    picker = {r["case_id"] for r in c.get("/api/session/demo/cases").json()}
    for case_id, prepared in mock_bank._CASES.items():
        assert case_id in picker
        assert rows[case_id]["borrowers"] == [b["name_he"] for b in prepared["borrowers"]]
        ws = views_open(c, case_id)
        assert ws["case"]["display_number"] == prepared["display_number"]
        assert [b["name_he"] for b in ws["case"]["borrowers"]] == [b["name_he"] for b in prepared["borrowers"]]


def test_a_case_confirmed_in_the_chat_reaches_the_banker_at_once():
    ch = Chat()
    personal(ch)
    ch.say("אני שכירה, מרוויחה 16 אלף נטו, רוצה הלוואה של 80 אלף לרכב לחמש שנים.")
    ch.say("לא, רק אני")
    confirmed = ch.c.post(f"/api/demo/onboarding/{ch.id}/v2/confirm").json()
    case_id = confirmed["case_id"]
    assert confirmed["created"] and case_id in bank.case_ids()

    c = staff()
    first = c.get("/api/banker/cases").json()[0]
    assert first["case_id"] == case_id and first["borrowers"] == ["מיכל ברק"]
    assert first["readiness"] == "NOT_CHECKED" and first["banker"]["staff_id"] == "STAFF-DANA"
    assert c.get("/api/session/demo/cases").json()[0]["case_id"] == case_id
    assert [r["case_id"] for r in ch.c.get("/api/cases").json()] == [case_id]

    ws = views_open(c, case_id)
    assert ws["case_status"] == "AWAITING_DOCUMENTS" and [b["name_he"] for b in ws["case"]["borrowers"]] == ["מיכל ברק"]
    assert [r["code"] for r in ws["requirement_matrix"]] == [r["code"] for r in confirmed["requirements"]]
    assert ws["can_confirm"]["allowed"] is False and ws["can_confirm"]["reason_he"]

    # the customer's first upload is in the banker's list and workspace on the next read
    with PAYSLIP.open("rb") as f:
        r = ch.c.post(f"/api/cases/{case_id}/documents", data={"requirement_code": "PAYSLIPS:BRW-A", "borrower_id": "BRW-A"},
                      files={"file": (PAYSLIP.name, f, "application/pdf")})
    assert r.status_code in (200, 201, 202), r.text
    first = c.get("/api/banker/cases").json()[0]
    assert first["case_id"] == case_id and first["counts"]["documents"] == 1
    assert c.post(f"/api/banker/cases/{case_id}/notes", json={"text": "בדיקת סנכרון"}).status_code == 200


def test_health_tells_the_main_data_from_an_isolated_one():
    assert TestClient(app).get("/api/health").json()["data"] == "isolated"
    assert dataclasses.replace(settings, data_dir=BACKEND_DIR / "data").main_data
