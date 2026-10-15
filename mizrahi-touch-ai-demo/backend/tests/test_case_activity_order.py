"""Every case list (the banker's "תיקים בתור", the customer app's case drawer, a customer's own cases) puts the case
worked on most recently first; opening or viewing a case never moves it, and a reset case drops back."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import auth
from app.main import app

A, B = "DEMO-MTZ-2026-003", "DEMO-MTZ-2026-005"


def clients() -> tuple[TestClient, TestClient]:
    staff, customer = TestClient(app), TestClient(app)
    staff.cookies.set(auth.COOKIES["staff"], auth.issue("staff", "STAFF-DANA"))
    customer.cookies.set(auth.COOKIES["customer"], auth.issue("customer", [A, B]))
    return staff, customer


def lists(staff: TestClient, customer: TestClient) -> dict[str, list[str]]:
    ids = lambda path, c: [r["case_id"] for r in c.get(path).json() if r["case_id"] in (A, B)]  # noqa: E731
    return {"banker": ids("/api/banker/cases", staff), "drawer": ids("/api/session/demo/cases", customer),
            "customer": ids("/api/cases", customer)}


def work(staff: TestClient, case_id: str) -> None:
    assert staff.post(f"/api/banker/cases/{case_id}/notes", json={"text": "בדיקת סדר"}).status_code == 200


def test_the_case_worked_on_last_heads_every_case_list():
    staff, customer = clients()
    work(staff, A)
    work(staff, B)
    assert lists(staff, customer) == {"banker": [B, A], "drawer": [B, A], "customer": [B, A]}
    rows = staff.get("/api/banker/cases").json()
    assert rows[0]["case_id"] == B and rows[0]["last_activity_at"]
    assert all(rows[i]["last_activity_at"] >= rows[i + 1]["last_activity_at"]
               for i in range(len(rows) - 1) if rows[i + 1]["last_activity_at"])

    # opening and reading A, as the banker (V1, V2, V3, package) and as the customer, does not move it
    for path in (f"/api/banker/cases/{A}/workspace", f"/api/banker/cases/{A}/intelligence", f"/api/banker/cases/{A}/package",
                 f"/api/banker/cases/{A}/followup", f"/api/banker/cases/{A}/timeline"):
        assert staff.get(path).status_code == 200, path
    for path in (f"/api/cases/{A}", f"/api/cases/{A}/documents", f"/api/cases/{A}/conversation"):
        assert customer.get(path).status_code == 200, path
    assert customer.post("/api/session/demo/customer", json={"case_id": A}).status_code == 200
    assert lists(staff, customer)["banker"] == [B, A]

    # a customer's contact-preference change is work on the case too
    assert customer.post(f"/api/cases/{A}/contact-preferences", json={"preferred_channel": "message"}).status_code == 200
    assert lists(staff, customer) == {"banker": [A, B], "drawer": [A, B], "customer": [A, B]}

    # a reset wipes the work: the case falls back behind the one still worked on
    work(staff, B)
    work(staff, A)
    assert staff.post(f"/api/cases/{A}/reset").status_code == 200
    assert lists(staff, customer)["banker"] == [B, A]
