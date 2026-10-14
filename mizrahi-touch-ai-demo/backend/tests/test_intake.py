"""Customer-started loan applications: the case is created with synthetic bank data, the requirements come from the
published policy (conditions included) and the browser's session reaches the new case — never a credit assessment."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

BASE = {"first_name_he": "מיה", "last_name_he": "כהן", "purpose": "renovation", "requested_amount_ils": 60000,
        "payments": 48, "employment": "salaried", "employer_he": "דמו בע״מ", "declared_net_monthly_ils": 12000}


def test_options_come_from_the_published_policy_and_say_it_is_not_an_eligibility_check():
    o = TestClient(app).get("/api/demo/applications/options").json()
    assert {p["id"] for p in o["purposes"]} >= {"car", "renovation"} and "אינם בדיקת זכאות" in o["note_he"]


def test_a_salaried_application_gets_the_published_package_and_a_session():
    c = TestClient(app)
    r = c.post("/api/demo/applications", json=BASE)
    assert r.status_code == 201, r.text
    case_id = r.json()["case_id"]
    snap = c.get(f"/api/cases/{case_id}")
    assert snap.status_code == 200
    codes = [q["code"] for q in snap.json()["readiness"]["requirements"]]
    assert codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"]
    assert snap.json()["case"]["loan"]["purpose_he"] == "שיפוץ" and snap.json()["readiness"]["state"] == "NOT_CHECKED"


def test_a_self_employed_applicant_gets_a_tax_assessment_instead_of_payslips():
    c = TestClient(app)
    case_id = c.post("/api/demo/applications", json={**BASE, "employment": "self_employed"}).json()["case_id"]
    codes = [q["code"] for q in c.get(f"/api/cases/{case_id}").json()["readiness"]["requirements"]]
    assert "TAX_ASSESSMENT:BRW-A" in codes and "PAYSLIPS:BRW-A" not in codes


def test_invalid_applications_are_refused():
    c = TestClient(app)
    assert c.post("/api/demo/applications", json={**BASE, "purpose": "yacht"}).status_code == 422
    assert c.post("/api/demo/applications", json={**BASE, "requested_amount_ils": 900000}).status_code == 422
    assert c.post("/api/demo/applications", json={**BASE, "first_name_he": "<script>"}).status_code == 422
