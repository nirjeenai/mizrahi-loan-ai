"""Banker Intelligence V2: deterministic loan arithmetic, the synthetic bank context, and the briefing built through the
real route for a complete, an income-gap and an incomplete case. Gemini is never called: reviews are stored results."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.bank import financial_context
from app.main import app
from app.review import case_review
from app.store import repo
from app.workflow import finance
from tests.loan_helpers import client_for, id_card, purpose, run_case, statement
from tests.test_review_desk import add_doc

COMPLETE, GAP, NO_CONTEXT = "DEMO-MTZ-2026-009", "DEMO-MTZ-2026-011", "DEMO-MTZ-2026-007"
staff = client_for()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for case in (COMPLETE, GAP, NO_CONTEXT):
        repo.reset_case(case)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})
    yield


def package(case: str, net: float = 14700) -> None:
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-A", m, net, f"ido_{m}.pdf", case=case)
    id_card(case)
    statement(case)
    purpose(case)
    run_case(case)


def brief(case: str) -> dict:
    r = staff.get(f"/api/banker/cases/{case}/intelligence")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- arithmetic
def test_the_annuity_payment_matches_the_standard_formula_and_rounds_to_agorot():
    assert finance.monthly_payment(90000, 60, 6.0) == 1739.95
    assert finance.monthly_payment(120000, 60, 6.0) == 2319.94
    s = finance.schedule(90000, 60, 6.0)
    # the last payment absorbs the agorot rounding: interest comes from the unrounded annuity
    assert s["total_interest_ils"] == 14397.13 and s["total_payments_ils"] == 104397.13
    assert abs(s["total_payments_ils"] - 1739.95 * 60) < 60 * 0.005


def test_zero_interest_divides_the_principal_and_invalid_input_gives_no_number():
    assert finance.monthly_payment(12000, 12, 0) == 1000.0
    for term in (12, 84, 108):                       # 90,000 / 84 and / 108 do not divide into whole agorot
        s = finance.schedule(90000, term, 0)
        assert s["total_interest_ils"] == 0 and s["total_payments_ils"] == 90000
    for bad in ((0, 60, 6), (-1, 60, 6), (90000, 0, 6), (90000, 12.5, 6), (90000, 60, -1), (None, 60, 6)):
        assert finance.monthly_payment(*bad) is None and finance.schedule(*bad) is None


def test_ratios_need_an_income_and_max_principal_inverts_the_payment():
    assert finance.ratio_pct(2977.25, 21050) == 14.1
    assert finance.ratio_pct(1000, None) is None and finance.ratio_pct(1000, 0) is None
    cap = finance.max_principal(finance.monthly_payment(90000, 60, 6.0), 60, 6.0)
    assert cap == 89000 or cap == 90000
    assert finance.max_principal(1000, 12, 0) == 12000


def test_scenarios_stay_inside_the_demo_bounds_and_unknown_debt_is_not_zero():
    assert [t for _, t in finance.scenario_terms(60)] == [36, 60, 84]
    assert [t for _, t in finance.scenario_terms(12)] == [12, 36]
    assert [t for _, t in finance.scenario_terms(110)] == [86, 110, 120]
    rows = finance.scenarios(90000, 60, 6.0, 21050, None, 132000)
    assert all(not r["combined_includes_existing"] for r in rows)
    with_debt = finance.scenarios(90000, 60, 6.0, 21050, 1237.30, 132000)
    mid = next(r for r in with_debt if r["key"] == "requested")
    assert mid["combined_debt_service_ils"] == 2977.25 and mid["combined_dsr_pct"] == 14.1 and mid["ltv_pct"] == 68.2
    assert finance.scenarios(90000, 60, 6.0, None, 1237.30, None)[0]["combined_dsr_pct"] is None


def test_the_bank_context_keeps_balances_payments_and_credit_lines_apart():
    ctx = financial_context.for_borrower({"borrower_id": "BRW-C", "national_id": "311204572"})
    assert ctx["synthetic"] is True and ctx["authoritative"] is False and ctx["observed_at"] == "2026-10-11"
    t = ctx["totals"]
    assert t["monthly_debt_service_ils"] == 1237.30 and t["loans_outstanding_ils"] == 27917.03
    assert t["exposure_approved_ils"] == round(27917.03 + 15000 + 25000, 2)
    assert t["exposure_utilized_ils"] == round(27917.03 + 0 + 4850, 2)
    assert financial_context.for_borrower({"borrower_id": "BRW-B", "national_id": "DEMO-ID-002"}) is None


# ---------------------------------------------------------------- the briefing
def test_a_complete_package_is_ready_for_credit_review_with_sourced_numbers_and_no_double_counting():
    package(COMPLETE)
    b = brief(COMPLETE)
    rec, a = b["recommendation"], b["analysis"]
    assert rec["state"] == "READY_FOR_CREDIT_REVIEW" and a["availability"] == "full"
    assert "אישור" not in rec["headline_he"].replace("אישור הכנת", "")
    assert a["income"]["value"] == 14700 and b["income"]["borrowers"][0]["quality"] == "verified"
    # existing debt service = loan payments only; card spending and credit lines are not added
    assert a["existing_debt"]["value"] == 2160.62
    assert b["bank_context"]["card_spending"][0]["avg_monthly_ils"] == 4320.51
    assert a["combined_dsr"]["value"] == finance.ratio_pct(2319.94 + 2160.62, 14700) == 30.5
    # over the 30% demo assumption at the requested term → the shortest term that fits is suggested, labelled as illustrative
    sug = b["simulation"]["suggested"]
    assert sug["key"] == "long" and sug["term_months"] == 84 and "לא החלטת אשראי" in sug["label_he"]
    # the requested amount above the quote is surfaced, with both sources
    gap = next(d for d in b["discrepancies"] if d["kind"] == "purpose_amount")
    assert gap["declared"]["value"] == 120000 and gap["documented"]["value"] == 118000
    # every source id a number points to exists; document facts carry their evidence
    used = [c["source_ids"] for c in rec["considerations"]]
    assert all(s in b["sources"] for ids in used for s in ids)
    net = next(s for s in b["sources"].values() if s["kind"] == "document" and s["field"] == "net_pay")
    assert net["verified"] and net["has_location"] and net["v1_item"].startswith("doc:")
    assert b["sources"]["calc:existing_debt"]["inputs"][0]["source_id"].startswith("bank:BFC-DEMO-LEVY-01")
    kinds = {d["kind"] for d in b["drafts"]}
    assert kinds == {"complete_documentation", "conditional_financing"} and b["recommended_draft"] == "complete_documentation"
    for d in b["drafts"]:
        assert "יחס" not in d["message_he"] and "%" not in d["message_he"].replace("6.0%", "")


def test_an_open_income_gap_makes_the_analysis_provisional_on_the_lower_income():
    package(GAP)
    b = brief(GAP)
    gap = next((d for d in b["discrepancies"] if d["kind"] == "income"), None)
    assert gap and gap["open"], [f["code"] for f in repo.findings(GAP, "open")]
    rec, a = b["recommendation"], b["analysis"]
    assert rec["state"] == "CLARIFICATION_REQUIRED" and a["availability"] == "provisional"
    assert a["income"]["value"] == 14700                       # min(declared 16,500, documented 14,700)
    assert a["declared_alternative"]["combined_dsr_pct"] == finance.ratio_pct(2319.94 + 2160.62, 16500)
    assert b["simulation"]["suggested"] is None
    assert b["recommended_draft"] == "financial_clarification"
    assert not any(d["kind"] == "conditional_financing" for d in b["drafts"])
    assert gap["v1_item"].startswith("finding:")


def test_an_incomplete_package_asks_for_documents_and_offers_no_financing_draft():
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=COMPLETE)
    run_case(COMPLETE)
    b = brief(COMPLETE)
    assert b["recommendation"]["state"] == "DOCUMENTS_INCOMPLETE"
    assert b["simulation"]["suggested"] is None
    assert [d["kind"] for d in b["drafts"]] == ["missing_documents"]
    assert len(b["documents"]["missing"]) == 3 and all(m["v1_item"].startswith("missing:") for m in b["documents"]["missing"])


def test_without_bank_context_the_ratio_says_it_covers_the_new_loan_only():
    b = brief(NO_CONTEXT)
    assert b["recommendation"]["state"] == "NO_DOCUMENTS"
    assert b["analysis"]["existing_debt"]["value"] is None and not b["bank_context"]["available"]
    assert all(not s["combined_includes_existing"] for s in b["simulation"]["scenarios"])
    assert b["analysis"]["availability"] == "partial"


def test_the_briefing_is_staff_only_and_writes_nothing():
    package(COMPLETE)
    tables = ("audit", "banker_decisions", "customer_requests", "findings", "review_runs", "case_state", "jobs")
    before = {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in tables}
    brief(COMPLETE)
    assert {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in tables} == before
    anonymous = TestClient(app)
    assert anonymous.get(f"/api/banker/cases/{COMPLETE}/intelligence").status_code == 401
    customer = TestClient(app)
    customer.cookies.set(auth.COOKIES["customer"], auth.issue("customer", [COMPLETE]))
    assert customer.get(f"/api/banker/cases/{COMPLETE}/intelligence").status_code in (401, 403)
