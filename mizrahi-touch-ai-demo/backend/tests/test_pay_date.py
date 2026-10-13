"""PS-10 payment-date rule, its precedence over the judge, the income-comparison selection, rubric versions and the
pay-date fixtures (no model calls)."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pymupdf

from app.review import case_review, rubrics
from app.review import deterministic as det
from app.review.contract import CaseReviewRequest, EvidenceRef, ExtractedFact, ProviderIdentity
from app.review.gemini_provider import GeminiReviewProvider

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN = FIXTURES / "presenter" / "golden_set"
PAY_DATE = FIXTURES / "pay_date" / "out"
GOLDEN_PAYSLIPS = ["01_INITIAL_UPLOADS/ido_2026_07.pdf", "01_INITIAL_UPLOADS/ido_2026_08.pdf", "01_INITIAL_UPLOADS/ido_2026_09.pdf",
                   "01_INITIAL_UPLOADS/noa_2026_07.pdf", "01_INITIAL_UPLOADS/noa_2026_08.pdf", "01_INITIAL_UPLOADS/noa_2026_09.pdf",
                   "02_CORRECTION/ido_2026_09_CORRECTED.pdf"]


def test_absent_payment_date_stays_unknown_and_is_not_a_defect():
    outcome, text = det.pay_date_check("2026-09", None, None, False, 9)
    assert outcome == "NOT_APPLICABLE"
    assert "לא ידוע" in text and "תאריך ההפקה" in text
    assert det.pay_date_check("2026-09", "  ", None, False, 9)[0] == "NOT_APPLICABLE"


def test_printed_payment_date_is_checked_against_the_salary_period():
    def outcome(printed: str) -> str:
        day, month, year = (int(x) for x in printed.split("."))
        return det.pay_date_check("2026-09", printed, date(year, month, day), True, 9)[0]

    assert outcome("25.08.2026") == "FAIL"              # paid before the period started
    assert outcome("15.09.2026") == "NEEDS_REVIEW"      # paid inside the period, before it ended
    assert outcome("27.09.2026") == "PASS"              # within 3 days of the period end
    assert outcome("09.10.2026") == "PASS"              # by the 9th of the following month
    assert outcome("20.10.2026") == "PASS"              # late: an information note, not a document defect
    assert "הערת מידע" in det.pay_date_check("2026-09", "20.10.2026", date(2026, 10, 20), True, 9)[1]


def test_unparseable_or_unverified_printed_dates_go_to_the_judge():
    assert det.pay_date_check("2026-09", "אמצע אוקטובר", None, True, 9)[0] == "JUDGE"
    assert det.pay_date_check("2026-09", "09.10.2026", date(2026, 10, 9), False, 9)[0] == "JUDGE"
    assert det.pay_date_check(None, "09.10.2026", date(2026, 10, 9), True, 9)[0] == "JUDGE"


def _fact(name: str, raw, normalized) -> ExtractedFact:
    ref = EvidenceRef(evidence_id=f"DOC-T:{name}", document_id="DOC-T", field=name, page=1, witness="text_layer_exact")
    return ExtractedFact(field=name, label_he=name, value_raw=str(raw), value_normalized=normalized, evidence=ref)


def test_code_decision_outranks_a_judge_that_reads_the_issue_date():
    rubric = rubrics.latest("payslip.il.salaried")
    spec = {c["id"]: c for c in rubric["criteria"]}
    facts = {n: _fact(n, v, v) for n, v in (("employee_name", "עידו לוי"), ("employee_id", "DEMO-ID-001"),
                                            ("salary_period", "2026-08"), ("gross_pay", 21100.0), ("net_pay", 14700.0))}
    facts["issue_date"] = _fact("issue_date", "08.09.2026", "2026-09-08")
    outcomes = {cid: ("PASS", "") for cid in ("PS-03", "PS-04", "PS-05", "PS-06", "PS-07", "PS-09")}
    outcomes |= {"PS-08": ("JUDGE", ""), "PS-10": det.pay_date_check("2026-08", None, None, False, 9)}
    judged = {"criteria": [{"criterion_id": cid, "outcome": "PASS", "explanation_he": "", "cited_fields": []}
                           for cid in ("PS-01", "PS-02", "PS-03", "PS-08")]
              + [{"criterion_id": "PS-10", "outcome": "FAIL", "explanation_he": "תאריך ההפקה 08.09.2026", "cited_fields": ["issue_date"]}]}
    merged = {c.criterion_id: c for c in GeminiReviewProvider()._merge(rubric, spec, {}, facts, {"outcomes": outcomes, "unreadable": False}, judged)}
    assert merged["PS-10"].outcome == "NOT_APPLICABLE" and merged["PS-10"].decided_by == "code"
    assert not any(c.outcome in ("FAIL", "NEEDS_REVIEW") for c in merged.values())     # → document verdict VALID


def test_income_comparison_needs_income_relevant_criteria_not_an_overall_valid():
    policy = rubrics.latest("income-set.salaried")["policy"]

    def review(verdict: str, **failing: str) -> dict:
        return {"verdict": verdict, "criteria": [{"criterion_id": f"PS-{i:02d}", "outcome": failing.get(f"PS{i:02d}", "PASS")}
                                                 for i in range(1, 11)]}

    assert case_review.income_comparable(review("NEEDS_REVIEW", PS10="FAIL"), policy)
    assert case_review.income_comparable(review("NEEDS_REVIEW", PS07="FAIL"), policy)
    assert not case_review.income_comparable(review("NEEDS_REVIEW", PS06="FAIL"), policy)
    assert not case_review.income_comparable(review("NEEDS_REVIEW", PS09="NEEDS_REVIEW"), policy)
    assert not case_review.income_comparable(review("INVALID", PS03="FAIL"), policy)
    assert not case_review.income_comparable(review("NEEDS_REVIEW", PS10="FAIL"), {})      # rubric 1.0.0: VALID only


def _slip(doc_id: str, borrower_id: str, period: str, net: float, ps10: str, minute: int) -> dict:
    def fact(name: str, value) -> dict:
        return {"field": name, "label_he": name, "value_raw": str(value), "value_normalized": value,
                "evidence": {"evidence_id": f"{doc_id}:{name}", "document_id": doc_id, "field": name, "page": 1,
                             "witness": "text_layer_exact"}}

    criteria = [{"criterion_id": f"PS-{i:02d}", "title_he": f"PS-{i:02d}", "outcome": "PASS", "severity": "minor",
                 "reason_code": None, "explanation_he": "", "evidence_ids": [], "escalation": "banker"} for i in range(1, 11)]
    criteria[9].update(outcome=ps10, reason_code="PAY_DATE_INCONSISTENT")
    verdict = "VALID" if ps10 in ("PASS", "NOT_APPLICABLE") else "NEEDS_REVIEW"
    return {"document_id": doc_id, "borrower_id": borrower_id, "filename": f"{doc_id}.pdf", "uploaded_at": f"2026-10-12T10:{minute:02d}:00",
            "review": {"run_id": f"RUN-{doc_id}", "doc_type": "payslip", "period": period, "file_name_period": None, "verdict": verdict,
                       "criteria": criteria, "facts": [fact("salary_period", period), fact("net_pay", net), fact("gross_pay", net + 6000)]}}


def test_payment_date_findings_do_not_suppress_the_declared_income_variance(monkeypatch):
    monkeypatch.setattr(case_review, "_semantic", lambda *args: {"borrowers": [], "limitations_he": []})
    borrowers = [{"borrower_id": "BRW-A", "name_he": "עידו לוי", "declared_net_monthly_ils": 14700, "declared_income_provenance": "CUSTOMER_DECLARED"},
                 {"borrower_id": "BRW-B", "name_he": "נועה לוי", "declared_net_monthly_ils": 18500, "declared_income_provenance": "CUSTOMER_DECLARED"}]
    docs = [_slip("NOA-07", "BRW-B", "2026-07", 16800, "FAIL", 1), _slip("NOA-08", "BRW-B", "2026-08", 16900, "NEEDS_REVIEW", 2),
            _slip("NOA-09", "BRW-B", "2026-09", 17000, "FAIL", 3)]
    req = CaseReviewRequest(case_id="T", run_id="RUN-T", case_context={"simulation_date": "2026-10-12", "borrowers": borrowers},
                            documents=docs, statements=[], rubric=rubrics.latest("income-set.salaried"))
    result = case_review.run(ProviderIdentity(provider="test", mode="STUB", prompt_version="t"), req, lambda stage: None)
    noa = result.income["BRW-B"]
    assert noa["months_compared"] == ["2026-07", "2026-08", "2026-09"]
    assert noa["average_documented_net_ils"] == 16900 and noa["difference_ils"] == -1600
    assert noa["declared_provenance"] == "CUSTOMER_DECLARED"
    variance = [f for f in result.findings if f.code == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"]
    assert len(variance) == 1 and variance[0].borrower_id == "BRW-B" and variance[0].review_state == "NEEDS_BANKER_REVIEW"


def test_rubric_versions_keep_history():
    latest = rubrics.latest("payslip.il.salaried")
    assert latest["version"] == "1.2.0"
    assert next(c for c in latest["criteria"] if c["id"] == "PS-10")["method"] == "hybrid"
    previous = rubrics.all_rubrics()["payslip.il.salaried@1.1.0"]
    assert next(c for c in previous["criteria"] if c["id"] == "PS-10")["method"] == "judge"
    case = rubrics.latest("income-set.salaried")
    assert case["version"] == "1.1.0"
    assert not {"PS-07", "PS-10"} & set(case["policy"]["income_comparison_requires_pass"])


def test_golden_payslips_print_an_issue_date_but_no_payment_date_and_stay_unmodified():
    listed = {r.split(",")[0]: r.split(",")[-1] for r in (GOLDEN / "MANIFEST.csv").read_text(encoding="utf-8-sig").splitlines()[1:]}
    for rel in GOLDEN_PAYSLIPS:
        data = (GOLDEN / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == listed[rel]
        text = pymupdf.open(stream=data, filetype="pdf")[0].get_text()
        assert "תאריך הפקה" in text and "תאריך תשלום" not in text


def test_pay_date_fixtures_print_both_dates_as_separate_fields():
    manifest = json.loads((PAY_DATE / "manifest.json").read_text(encoding="utf8"))
    assert {f["expect"]["PS-10"] for f in manifest["files"]} == {"PASS", "FAIL", "NEEDS_REVIEW"}
    for f in manifest["files"]:
        data = (PAY_DATE / f["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == f["sha256"]
        text = pymupdf.open(stream=data, filetype="pdf")[0].get_text()
        assert "תאריך תשלום" in text and f["payment_date"] in text and f["issue_date"] in text
        assert f["payment_date"] != f["issue_date"]
