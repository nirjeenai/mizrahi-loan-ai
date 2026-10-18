"""Hebrew baseline of the customer API: every customer-facing endpoint on seeded cases (stored reviews, findings, a
banker request, the assistant's no-model answer, upload refusals). Recorded before the bilingual work and compared
byte for byte after normalizing ids and timestamps (tests/golden_util.py). `X-MZ-Lang` is not sent here: without
it the service must answer exactly as before."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db, util
from app.policy import store
from app.review import case_review
from app.store import repo
from tests.loan_helpers import FIX, client_for, id_card, purpose, run_case, statement
from tests.test_review_desk import add_doc

from .golden_util import check

FULL, GAPS, EMPTY = "DEMO-MTZ-2026-009", "DEMO-MTZ-2026-011", "DEMO-MTZ-2026-101"


@pytest.fixture(autouse=True)
def seeded(monkeypatch):
    db.connect()
    store.ensure_seeded()
    for case in (FULL, GAPS, EMPTY):
        repo.reset_case(case)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
    # one second per timestamp: rows written in the same second would otherwise come back in random-id order
    tick = iter(range(1, 100000))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc) + timedelta(seconds=next(tick))
    monkeypatch.setattr(util, "datetime", Clock)
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})


def _customer_views(c, case: str) -> dict:
    out = {"snapshot": c.get(f"/api/cases/{case}").json(), "documents": c.get(f"/api/cases/{case}/documents").json(),
           "followup": c.get(f"/api/cases/{case}/followup").json()}
    out["document_pages"] = {}
    for d in out["documents"]:
        did = d["document_id"]
        out["document_pages"][d["filename"]] = {"document": c.get(f"/api/documents/{did}").json(),
                                                "outcome": c.get(f"/api/cases/{case}/documents/{did}/outcome").json()}
    return out


def customer_api(headers: dict | None = None) -> dict:
    """Seeds the cases and reads every customer endpoint (with `headers` on every customer request)."""
    # FULL: the whole package, every review VALID
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=FULL)
    id_card(FULL)
    statement(FULL)
    purpose(FULL)
    run_case(FULL)
    # GAPS: September missing, an unreadable ID card, a purpose proof that fails, a banker request for the statement
    for m in ("2026-07", "2026-08"):
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=GAPS)
    id_card(GAPS, verdict="INVALID", ID_02="FAIL")
    purpose(GAPS, verdict="NEEDS_REVIEW", PP_03="FAIL")
    run_case(GAPS)
    staff = client_for()
    staff.post(f"/api/banker/cases/{GAPS}/missing-requests", json={
        "borrower_id": "BRW-A", "period": "2026-09", "request_id": "REQ-GOLDEN-1",
        "customer_message": "שלום עידו, חסר לנו תלוש ספטמבר 2026. אפשר להעלות אותו כאן."})

    c = client_for(FULL, GAPS, EMPTY)
    c.headers.update(headers or {})
    out = {case: _customer_views(c, case) for case in (FULL, GAPS, EMPTY)}
    # the prepared cases only, by id: the list's order and the applications in it depend on what else ran in the session
    out["session_cases"] = sorted((x for x in c.get("/api/session/demo/cases").json() if x["case_id"].startswith("DEMO-MTZ")),
                                  key=lambda x: x["case_id"])
    out["stage_dictionary"] = c.get("/api/stage-dictionary").json()
    out["application_options"] = c.get("/api/demo/applications/options").json()
    # the assistant without a model: the reply is built from the case tools
    for case in (FULL, GAPS):
        r = c.post(f"/api/cases/{case}/agent/messages", json={"text": "מה חסר לי?", "channel": "text"})
        out[f"agent_{case}"] = {"status": r.status_code, "body": r.json(),
                                "conversation": c.get(f"/api/cases/{case}/conversation").json()}
    # refusals and validation the customer can meet
    pdf = (FIX / "ido_payslip_2026-07.pdf").read_bytes()
    r = c.post(f"/api/cases/{EMPTY}/documents", files={"file": ("note.txt", b"hello", "text/plain")},
               data={"requirement_code": "PAYSLIPS:BRW-A"})
    out["upload_wrong_type"] = {"status": r.status_code, "body": r.json()}
    r = c.post(f"/api/cases/{EMPTY}/documents", files={"file": ("p.pdf", pdf, "application/pdf")},
               data={"requirement_code": "PAYSLIPS:BRW-A", "borrower_id": "BRW-A"})
    out["upload_wrong_borrower"] = {"status": r.status_code, "body": r.json()}
    first = c.post(f"/api/cases/{GAPS}/documents", files={"file": ("p.pdf", pdf, "application/pdf")},
                   data={"requirement_code": "PAYSLIPS:BRW-A", "borrower_id": "BRW-A", "expected_period": "2026-09"})
    again = c.post(f"/api/cases/{GAPS}/documents", files={"file": ("p.pdf", pdf, "application/pdf")},
                   data={"requirement_code": "PAYSLIPS:BRW-A", "borrower_id": "BRW-A"})
    out["upload_first"] = {"status": first.status_code, "body": first.json()}
    out["upload_duplicate"] = {"status": again.status_code, "body": again.json()}
    assert first.status_code == 202, first.text
    out["upload_queued_outcome"] = c.get(
        f"/api/cases/{GAPS}/documents/{first.json()['document']['document_id']}/outcome").json()
    r = c.post(f"/api/cases/{FULL}/actions/resolve", json={"action_id": "ACT-NOPE"})
    out["resolve_unknown_action"] = {"status": r.status_code, "body": r.json()}
    r = c.post("/api/demo/onboarding/OBD-NOPE/v2/turn", json={"text": "שלום"})
    out["unknown_draft"] = {"status": r.status_code, "body": r.json()}
    return out


def test_hebrew_customer_api_is_unchanged():
    check("api_customer", customer_api())
