"""The personal-loan document package: requirements from the published policy, per-family deterministic checks,
missing requirements, statement coverage, wrong types and uncertainty — through the real case review and routes.
Gemini is never called: document reviews are stored results shaped like the provider's."""
from __future__ import annotations

from datetime import date

import pytest

from app import db
from app.policy import store
from app.review import case_review, family_checks, rubrics
from app.review import deterministic as det
from app.store import repo
from app.workflow import readiness, requirements
from tests.loan_helpers import CODES, JOURNEY, client_for, id_card, purpose, run_case, statement
from tests.test_review_desk import add_doc

ido = client_for(JOURNEY)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    repo.reset_case(JOURNEY)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})
    yield


def payslips() -> list[str]:
    return [add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=JOURNEY) for m in ("2026-07", "2026-08", "2026-09")]


def reqs() -> dict[str, dict]:
    return {r["code"]: r for r in readiness.compute(JOURNEY)["requirements"]}


# ---------------------------------------------------------------- requirements come from the published policy
def test_the_default_policy_asks_for_the_published_mizrahi_package():
    codes = [r["code"] for r in requirements.for_case(JOURNEY)]
    assert codes == [CODES["id"], CODES["pay"], CODES["bank"], CODES["purpose"]]       # no tax form: a salaried applicant
    assert all(r["evaluated_by_ai"] for r in requirements.for_case(JOURNEY))
    assert requirements.pin(JOURNEY) == store.published("loan_policy")["version_id"]
    assert "רכישת רכב" in requirements.requirement(JOURNEY, "PURPOSE_PROOF")["title_he"]


def test_a_self_employed_applicant_gets_the_conditional_tax_requirement(monkeypatch):
    from app.bank.mock_bank import bank
    real = bank.get_case

    def self_employed(case_id):
        c = real(case_id)
        c["borrowers"][0]["employment"] = "self_employed"
        return c
    monkeypatch.setattr(bank, "get_case", self_employed)
    codes = [r["code"] for r in requirements.for_case(JOURNEY)]
    assert "TAX_ASSESSMENT:BRW-A" in codes and "PAYSLIPS:BRW-A" not in codes


def test_a_published_change_reaches_new_cases_only_until_the_banker_repins():
    pinned = requirements.pin(JOURNEY)
    config = store.published("loan_policy")["config"]
    config["document_requirements"] = [r for r in config["document_requirements"] if r["id"] != "PURPOSE_PROOF"]
    draft = store.create_draft("loan_policy", "tests", config=config)
    store.publish(draft["version_id"], draft["revision"], "tests")
    try:
        assert requirements.pin(JOURNEY) == pinned and "PURPOSE_PROOF" in [r["code"] for r in requirements.for_case(JOURNEY)]
        old, new = requirements.repin(JOURNEY)
        assert old == pinned and new == draft["version_id"]
        assert "PURPOSE_PROOF" not in [r["code"] for r in requirements.for_case(JOURNEY)]
    finally:
        store.rollback("loan_policy", pinned, "tests", "restore")


# ---------------------------------------------------------------- deterministic family checks
def test_israeli_id_check_digit_and_synthetic_identifiers():
    assert det.israeli_id_check("000000018") == "valid"
    assert det.israeli_id_check("123456789") == "invalid"
    assert det.israeli_id_check("DEMO-ID-001") == "synthetic"
    assert det.israeli_id_check(None) == "unknown"


def test_statement_gaps_ignore_weekends_but_report_a_missing_month():
    lo, hi = det.window(date(2026, 9, 30), 90)
    full = [(date(2026, 7, 1), date(2026, 7, 31)), (date(2026, 8, 1), date(2026, 8, 31)), (date(2026, 9, 1), date(2026, 9, 30))]
    assert det.coverage_gaps(full, lo, hi) == []
    gaps = det.coverage_gaps([full[0], full[2]], lo, hi)
    assert gaps == [(date(2026, 8, 1), date(2026, 8, 31))]


def _outcomes(family: str, **facts):
    borrowers = {"BRW-A": {"borrower_id": "BRW-A", "name_he": "עידו לוי", "national_id": "DEMO-ID-001"}}
    return family_checks.outcomes(
        family, rubrics.for_family(family), val=lambda n: facts.get(n), norm=lambda n: facts.get(n),
        as_of=date(2026, 10, 12), borrowers=borrowers, assigned=borrowers["BRW-A"], matched=None, hits=[],
        unverified=[], present_decisive=["holder_name"], rules={"max_age_days": 30, "check_expiry": True},
        allowed_holders=None, labels={"issuer_name": "שם הספק", "total_amount": "סכום"})


def test_an_expired_or_foreign_id_card_fails_and_a_stale_statement_fails():
    o = _outcomes("id_document", holder_name="עידו לוי", holder_id="DEMO-ID-001", expiry_date="2025-01-01")
    assert o["ID-03"][0] == "PASS" and o["ID-04"][0] == "PASS" and o["ID-05"][0] == "FAIL"
    o = _outcomes("id_document", holder_name="דנה ישראלי", holder_id="000000018")
    assert o["ID-03"][0] == "FAIL" and o["ID-05"][0] == "NOT_APPLICABLE"
    o = _outcomes("bank_statement", holder_name="עידו לוי ונועה לוי", statement_from="2026-07-01", statement_to="2026-07-31")
    assert o["BS-03"][0] == "PASS" and o["BS-05"][0] == "PASS"           # a joint holder line matches; July is in the window
    o = _outcomes("bank_statement", holder_name="עידו לוי", statement_from="2026-03-01", statement_to="2026-05-31")
    assert o["BS-05"][0] == "FAIL"                                        # ends 134 days ago: outside 90 + 30 days


def test_statements_that_end_too_long_ago_leave_a_gap_up_to_the_recent_window():
    from datetime import timedelta
    as_of = date(2026, 10, 12)
    lo, hi = det.window(max(date(2026, 8, 31), as_of - timedelta(days=30)), 90)
    gaps = det.coverage_gaps([(date(2026, 6, 1), date(2026, 8, 31))], lo, hi)
    assert gaps and gaps[-1][1] == date(2026, 9, 12)


# ---------------------------------------------------------------- the package through the case review
def test_payslips_alone_leave_the_application_incomplete_with_one_missing_item_per_requirement():
    payslips()
    run_case()
    s = readiness.compute(JOURNEY)
    assert s["state"] == "ACTION_REQUIRED" and s["case_status"] == "NEEDS_COMPLETION"
    assert s["progress"] == {"done": 1, "total": 4, "missing_units": 3}
    missing = {f["detail"]["requirement_code"] for f in repo.findings(JOURNEY, "open") if f["code"] == "REQUIRED_DOCUMENT_MISSING"}
    assert missing == {CODES["id"], CODES["bank"], CODES["purpose"]}
    assert reqs()[CODES["id"]]["ai_state"] == "required_missing"


def test_the_full_valid_package_is_ready_for_the_banker_and_nothing_more():
    payslips()
    id_card()
    statement()
    purpose()
    run_case()
    s = readiness.compute(JOURNEY)
    assert s["state"] == "READY_FOR_HUMAN_REVIEW" and s["case_status"] == "READY_FOR_BANKER"
    assert s["progress"]["done"] == s["progress"]["total"] == 4
    snap = ido.get(f"/api/cases/{JOURNEY}").json()
    assert snap["readiness"]["customer_status"] == "CHECKS_COMPLETE"
    assert "אושר" not in snap["readiness"]["state_he"]


def test_a_payslip_in_the_id_slot_is_never_valid_and_goes_back_to_the_customer():
    payslips()
    did = id_card(verdict="INVALID", ID_01="FAIL", ID_03="FAIL")
    run_case()
    f = next(x for x in repo.findings(JOURNEY, "open") if x["document_id"] == did)
    assert f["code"] == "UNEXPECTED_DOCUMENT_TYPE" and f["review_state"] == "CUSTOMER_ACTION_REQUIRED"
    assert f["title_he"] == "המסמך אינו תעודת זהות"                     # one root cause, not the holder too
    assert reqs()[CODES["id"]]["ai_state"] == "needs_customer_action"


def test_an_undecided_type_goes_to_the_banker_and_the_customer_is_not_accused():
    payslips()
    did = id_card(verdict="NEEDS_REVIEW", ID_01="NEEDS_REVIEW")
    run_case()
    f = next(x for x in repo.findings(JOURNEY, "open") if x["document_id"] == did)
    assert f["review_state"] == "NEEDS_BANKER_REVIEW" and "לא הצליחה לקבוע" in f["message_he"]
    assert reqs()[CODES["id"]]["ai_state"] == "needs_banker_review"


def test_statements_with_a_missing_month_open_a_coverage_gap_that_the_banker_cannot_dismiss():
    payslips()
    id_card()
    purpose()
    statement(start="2026-07-01", end="2026-07-31", name="jul.pdf")
    statement(start="2026-09-01", end="2026-09-30", name="sep.pdf")
    run_case()
    gap = next(f for f in repo.findings(JOURNEY, "open") if f["code"] == "STATEMENT_PERIOD_GAP")
    assert gap["review_state"] == "CUSTOMER_ACTION_REQUIRED" and "01.08.2026" in gap["message_he"]
    assert reqs()[CODES["bank"]]["ai_state"] == "needs_customer_action"
    staff = client_for(JOURNEY)
    r = staff.post(f"/api/banker/cases/{JOURNEY}/findings/{gap['finding_id']}/decision",
                   json={"action": "dismiss", "rationale": "לא רלוונטי בכלל לבדיקה"})
    assert r.status_code == 409
    statement(start="2026-08-01", end="2026-08-31", name="aug.pdf")
    run_case()
    assert not any(f["code"] == "STATEMENT_PERIOD_GAP" for f in repo.findings(JOURNEY, "open"))
    assert reqs()[CODES["bank"]]["ai_state"] == "extracted"


def test_an_id_card_does_not_count_toward_the_payslip_months():
    for m in ("2026-07", "2026-08"):
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=JOURNEY)
    id_card()
    run_case()
    pay = reqs()[CODES["pay"]]
    assert pay["missing"] == ["2026-09"] and pay["documents"] == 2
