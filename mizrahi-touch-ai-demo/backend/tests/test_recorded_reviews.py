"""The real GeminiReviewProvider on the real fixture PDFs, with only the model's answers replayed from
e2e/replay/recordings.json (RECORDED_LIVE, 2026-10-14). Evidence verification against each PDF's text layer, the
deterministic family checks, the merge and the verdict policy run for real. No network call is made."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.bank.mock_bank import bank
from app.llm import gemini as g
from app.review import rubrics
from app.review.contract import DocumentReviewRequest
from app.review.gemini_provider import GeminiReviewProvider

ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = json.loads((ROOT / "e2e" / "replay" / "recordings.json").read_text(encoding="utf8"))["documents"]
LOAN = ROOT / "fixtures" / "presenter" / "loan_set"
GOLDEN = ROOT / "fixtures" / "presenter" / "golden_set"
CASE = "DEMO-MTZ-2026-009"


def replay(monkeypatch, path: Path, rubric_id: str) -> None:
    rec = RECORDINGS[hashlib.sha256(path.read_bytes()).hexdigest()]

    def generate(model, contents, *, purpose, run_id=None, schema=None, **kw):
        if purpose == "extract":
            answer = rec["extract"]
        elif purpose == "judge":
            judge = rec.get("judge_by_rubric", {}).get(rubric_id) or rec["judge"]
            ids = schema["properties"]["criteria"]["items"]["properties"]["criterion_id"]["enum"]
            answer = {"criteria": [{"criterion_id": cid, "cited_fields": [], "confidence": 0.9, **judge["criteria"][cid]}
                                   for cid in ids if cid in judge["criteria"]],
                      **{k: judge[k] for k in ("summary_he", "limitations_he", "uncertainty_he")}}
        else:
            raise g.GeminiError(f"no recording for {purpose}")
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(answer, ensure_ascii=False)}]}}], "usageMetadata": {}}

    monkeypatch.setattr(g, "generate", generate)


def review(monkeypatch, path: Path, family: str, code: str, case: str = CASE):
    rubric = rubrics.for_family(family)
    replay(monkeypatch, path, rubric["rubric_id"])
    req = DocumentReviewRequest(case_id=case, document_id="DOC-REC", filename=path.name, mime="application/pdf",
                                storage_path=str(path), assigned_borrower_id="BRW-A", requirement_code=code,
                                case_context=bank.case_context(case), rubric=rubric, run_id="RUN-REC")
    return GeminiReviewProvider()._review_document(req, lambda stage: None)


CASES = [
    (LOAN / "id_card_ido.pdf", "id_document", "ID_CARD:BRW-A", "VALID", set()),
    (LOAN / "id_card_ido_EXPIRED.pdf", "id_document", "ID_CARD:BRW-A", "INVALID", {"ID_EXPIRED"}),
    (LOAN / "statement_ido_2026-07_09.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1", "VALID", set()),
    (LOAN / "statement_ido_2026-07.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1", "VALID", set()),
    (LOAN / "statement_ido_2026-09.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1", "VALID", set()),
    (LOAN / "car_quote_ido.pdf", "purpose_proof", "PURPOSE_PROOF", "VALID", set()),
    (LOAN / "car_quote_ido_OLD.pdf", "purpose_proof", "PURPOSE_PROOF", "NEEDS_REVIEW", {"DOCUMENT_STALE"}),
    (GOLDEN / "01_INITIAL_UPLOADS" / "ido_2026_07.pdf", "id_document", "ID_CARD:BRW-A", "INVALID", {"UNEXPECTED_DOCUMENT_TYPE"}),
]


@pytest.mark.parametrize("path,family,code,verdict,reasons", CASES, ids=[c[0].name + ":" + c[1] for c in CASES])
def test_recorded_live_answers_through_the_real_pipeline(monkeypatch, path, family, code, verdict, reasons):
    r = review(monkeypatch, path, family, code)
    assert r.verdict == verdict, (r.verdict, r.verdict_reason_codes)
    assert reasons <= set(r.verdict_reason_codes)
    if verdict == "VALID":                       # every decisive value is verified against the PDF's own text layer
        decisive = rubrics.for_family(family)["decisive_fields"]
        assert all(f.verified for f in r.facts if f.field in decisive) and {f.field for f in r.facts} >= set(decisive)


def test_the_wrong_month_payslip_is_a_valid_august_payslip_with_verified_identity(monkeypatch):
    """Golden ido_2026_09.pdf prints August under a September file name. The identity number is printed under the
    label 'מזהה עובד', which the extractor read as employee_number; code accepts it as the identity number only on an
    exact, text-layer-verified match. The failure is the month, not the person."""
    r = review(monkeypatch, GOLDEN / "01_INITIAL_UPLOADS" / "ido_2026_09.pdf", "payslip", "PAYSLIPS:BRW-A")
    assert r.verdict == "VALID" and "BORROWER_MISMATCH" not in r.verdict_reason_codes
    assert r.period == "2026-08" and r.file_name_period == "2026-09"
    facts = {f.field: f for f in r.facts}
    assert facts["employee_id"].verified and facts["employee_id"].evidence.witness == "text_layer_exact"
    assert facts["salary_period"].evidence.quote and facts["salary_period"].verified


@pytest.mark.parametrize("month,net", [("07", 13200.0), ("08", 13500.0)])
def test_the_joint_scenario_payslips_belong_to_ido_lavi_in_the_two_applicant_case(monkeypatch, month, net):
    """L-11: the Lavi payslips, recorded live against case 003, are VALID for its first applicant (עידו לביא 039812457),
    for the month they print, with the identity and the net pay verified against the PDF's text layer."""
    path = ROOT / "fixtures" / "out" / "main" / f"ido_payslip_2026-{month}.pdf"
    r = review(monkeypatch, path, "payslip", "PAYSLIPS:BRW-A", case="DEMO-MTZ-2026-003")
    facts = {f.field: f for f in r.facts}
    assert r.verdict == "VALID" and r.matched_borrower_id == "BRW-A" and r.period == f"2026-{month}"
    assert facts["employee_id"].value_normalized == "039812457" and facts["employee_id"].verified
    assert facts["net_pay"].value_normalized == net and facts["net_pay"].evidence.witness == "text_layer_exact"
    # the same payslip is not עידו לוי's: in the single-applicant golden case the identity does not match
    other = review(monkeypatch, path, "payslip", "PAYSLIPS:BRW-A", case="DEMO-MTZ-2026-005")
    assert other.verdict == "INVALID" and "BORROWER_MISMATCH" in other.verdict_reason_codes


def test_an_unreadable_id_scan_is_never_valid(monkeypatch):
    r = review(monkeypatch, LOAN / "id_card_ido_UNREADABLE.pdf", "id_document", "ID_CARD:BRW-A")
    assert r.doc_type == "unreadable" and r.verdict != "VALID" and "DOCUMENT_UNREADABLE" in r.verdict_reason_codes
