"""Executive demo: PASS / REVIEW / BLOCKER in cases 006–008, the customer's replacement of a document the AI review sent
back, uncertain classification, the scoped "start a new demo" reset and the worker guards — through the real routes.

Gemini is never called: document reviews are stored results shaped like the provider's (helpers from test_review_desk)
and the semantic income judgement is a fixed stand-in. Coverage, arithmetic, findings, the derived outcomes, banker
transitions and the reset are the production code. These tests prove the workflow, not the model's accuracy."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.api import routes
from app.bank.mock_bank import bank
from app.config import settings
from app.main import app
from app.review import case_review, registry
from app.review.contract import DocumentReviewResult, ReviewHandle, ReviewStatus
from app.store import repo
from app.util import new_id, now_iso
from app.workflow import engine, outcomes, requirements
from tests.test_review_desk import DANA, add_doc, case_run, finish_review, review

pytestmark = pytest.mark.usefixtures("payslip_scope")    # the payslip workflow on its own (see conftest)
PASS_CASE, REVIEW_CASE, BLOCKER_CASE = "DEMO-MTZ-2026-006", "DEMO-MTZ-2026-007", "DEMO-MTZ-2026-008"
DEMO = (PASS_CASE, REVIEW_CASE, BLOCKER_CASE)
JOURNEY_CASE, NO_CONSENT_CASE, INCOME_CASE = "DEMO-MTZ-2026-009", "DEMO-MTZ-2026-010", "DEMO-MTZ-2026-011"
EXECUTIVE = (*DEMO, JOURNEY_CASE, NO_CONSENT_CASE, INCOME_CASE)
ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "fixtures" / "presenter" / "golden_set"
PRESENTER_MANIFEST = ROOT / "fixtures" / "presenter" / "presenter_scenarios_manifest.json"
INCOME = "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"


def signed_in(cases: list[str]) -> TestClient:
    """A customer session bound to these cases (what the app obtains for the case picked in its selector)."""
    c = TestClient(app)
    c.cookies.set(auth.COOKIES["customer"], auth.issue("customer", cases))
    return c


ido, noa, anon = signed_in([PASS_CASE, BLOCKER_CASE]), signed_in([REVIEW_CASE]), TestClient(app)
staff = TestClient(app)
staff.cookies.set(auth.COOKIES["staff"], auth.issue("staff", "STAFF-DANA"))


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for c in DEMO:
        repo.reset_case(c)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")

    def semantic(req, borrowers, income):          # stand-in for the model; the 5% band is still decided by code
        return {"borrowers": [{"borrower_id": bid, "definitions_equivalent": True,
                               "income_assessment": "INCONSISTENT" if abs(s.get("difference_pct") or 0) > 5 else "CONSISTENT",
                               "explanation_he": "הסבר המודל", "evidence_needed_he": ["אישור מעסיק על רכיבי שכר משתנים"],
                               "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
                "limitations_he": []}

    monkeypatch.setattr(case_review, "_semantic", semantic)
    yield


# ---------------------------------------------------------------- helpers
def snap(c: TestClient, case: str) -> dict:
    r = c.get(f"/api/cases/{case}")
    assert r.status_code == 200, r.text
    return r.json()


def workspace(case: str) -> dict:
    r = staff.get(f"/api/banker/cases/{case}/workspace")
    assert r.status_code == 200, r.text
    return r.json()


def doc_item(ws: dict, did: str) -> dict:
    return next(i for i in ws["items"] if i["id"] == f"doc:{did}")


def group_of(ws: dict, item_id: str) -> str:
    return next(g["key"] for g in ws["groups"] if item_id in g["items"])


def decide(case: str, did: str, action: str, **body):
    return staff.post(f"/api/banker/cases/{case}/documents/{did}/decision", json={"action": action, **body}, headers=DANA)


def rule(case: str, fid: str, action: str, **body):
    return staff.post(f"/api/banker/cases/{case}/findings/{fid}/decision", json={"action": action, **body}, headers=DANA)


def bare_doc(case: str, borrower: str, filename: str) -> str:
    did = new_id("DOC")
    repo.insert_document({"document_id": did, "case_id": case, "borrower_id": borrower, "requirement_code": f"PAYSLIPS:{borrower}",
                          "filename": filename, "mime": "application/pdf", "sha256": new_id("SHA"), "bytes": 1000, "pages": 2,
                          "text_layer_chars": 900, "storage_path": str(GOLDEN / "03_SUPPORTING_DOCS" / "bank_statement_Jul_Sep_2026.pdf"),
                          "uploaded_at": now_iso(), "uploaded_by": "customer", "channel": "customer_app", "status": "reviewed",
                          "stage": "done"})
    return did


def not_a_payslip(case: str, borrower: str = "BRW-A", ps01: str = "FAIL", **criteria: str) -> str:
    """A bank statement uploaded into a payslip slot, as the provider records it: classified bank_statement, PS-01 decided."""
    did = bare_doc(case, borrower, "bank_statement_Jul_Sep_2026.pdf")
    r = review(did, borrower, "2026-09", 0.0, verdict="INVALID" if ps01 == "FAIL" else "NEEDS_REVIEW", PS_01=ps01,
               PS_04="FAIL", PS_05="FAIL", PS_09="FAIL", **criteria)
    r.update(doc_type="bank_statement" if ps01 == "FAIL" else "other", doc_type_he="דף חשבון בנק", period=None,
             file_name_period=None, facts=[], matched_borrower_id=None)
    finish_review(did, r)
    return did


def upload(c: TestClient, case: str, borrower: str, path: Path, **data):
    with path.open("rb") as fh:
        return c.post(f"/api/cases/{case}/documents", data={"borrower_id": borrower, **data},
                      files={"file": (path.name, fh, "application/pdf")})


def ido_months(case: str, months=(("2026-07", 14400), ("2026-08", 14700), ("2026-09", 15000))) -> list[str]:
    return [add_doc("BRW-A", m, net, f"ido_{m.replace('-', '_')}.pdf", case=case) for m, net in months]


# ---------------------------------------------------------------- the cases
def test_three_isolated_single_borrower_cases_with_golden_identities():
    assert bank.executive_demo_case_ids() == list(EXECUTIVE)
    people = {cid: [(b["borrower_id"], b["name_he"], b["national_id"]) for b in bank.get_case(cid)["borrowers"]] for cid in DEMO}
    assert people[PASS_CASE] == people[BLOCKER_CASE] == [("BRW-A", "עידו לוי", "DEMO-ID-001")]
    assert people[REVIEW_CASE] == [("BRW-B", "נועה לוי", "DEMO-ID-002")]
    for cid in DEMO:
        c = bank.get_case(cid)
        assert c["banker"]["staff_id"] == "STAFF-DANA" and c["bank_stage"]["authoritative"] is False
        assert [r["code"] for r in bank.requirements(cid) if r["evaluated_by_ai"]] == [f"PAYSLIPS:{people[cid][0][0]}"]
    for cid in ("DEMO-MTZ-2026-001", "DEMO-MTZ-2026-002", "DEMO-MTZ-2026-003", "DEMO-MTZ-2026-004", "DEMO-MTZ-2026-005"):
        assert not bank.get_case(cid).get("executive_demo")
    assert ido.get(f"/api/cases/{REVIEW_CASE}").status_code == 403          # a session reaches only its own cases
    assert anon.get(f"/api/cases/{PASS_CASE}").status_code == 401


# ---------------------------------------------------------------- PASS
def test_pass_valid_payslips_wait_for_the_bankers_acceptance_and_nothing_is_approved():
    docs = ido_months(PASS_CASE)
    case_run(PASS_CASE)
    s = snap(ido, PASS_CASE)
    assert s["readiness"]["customer_status"] == "CHECKS_COMPLETE"
    assert not [f for f in s["findings"] if f["status"] == "open"]
    assert s["outcomes"]["borrowers"]["BRW-A"] == {"outcome": "PASS", "label_he": "עבר בדיקת AI — ממתין לקבלת הבנקאי"}
    assert {s["outcomes"]["documents"][d]["outcome"] for d in docs} == {"PASS"}
    ws = workspace(PASS_CASE)
    for d in docs:                                   # the banker sees the same route the customer sees
        it = doc_item(ws, d)
        assert group_of(ws, it["id"]) == "decide" and it["outcome"]["outcome"] == "PASS" and not it["attention"]
    stage = s["case"]["bank_stage"]
    for d in docs:
        assert decide(PASS_CASE, d, "accept", acknowledged_finding_ids=[]).status_code == 200
    s = snap(ido, PASS_CASE)
    assert {s["outcomes"]["documents"][d]["outcome"] for d in docs} == {"ACCEPTED"}
    assert all("לא אישור הלוואה" in s["outcomes"]["documents"][d]["label_he"] for d in docs)
    assert s["case"]["bank_stage"] == stage and s["readiness"]["state"] != "PREPARATION_CONFIRMED"
    assert s["readiness"]["counts"]["documents_accepted"] == 3
    assert not re.search(r"ההלוואה אושרה|אישור ההלוואה ניתן", json.dumps(s, ensure_ascii=False))


# ---------------------------------------------------------------- REVIEW
def test_review_valid_payslips_with_an_income_gap_go_to_banker_judgment_and_a_reply_never_closes_it():
    docs = [add_doc("BRW-B", m, net, f"noa_{m.replace('-', '_')}.pdf", case=REVIEW_CASE)
            for m, net in (("2026-07", 16800), ("2026-08", 16900), ("2026-09", 17000))]
    case_run(REVIEW_CASE)
    gap = [f for f in repo.findings(REVIEW_CASE, "open") if f["code"] == INCOME]
    assert len(gap) == 1 and gap[0]["review_state"] == "NEEDS_BANKER_REVIEW"
    detail = gap[0]["detail"]
    assert detail["basis"] == "complete" and detail["months_compared"] == ["2026-07", "2026-08", "2026-09"]
    assert detail["stats"]["average_documented_net_ils"] == 16900 and detail["stats"]["difference_ils"] == -1600
    assert {e["document_id"] for e in gap[0]["evidence"]} == set(docs)
    s = snap(noa, REVIEW_CASE)
    assert s["readiness"]["customer_status"] == "BANKER_REVIEW"
    assert s["outcomes"]["borrowers"]["BRW-B"]["label_he"] == "נדרש בירור בנקאי — נמצא פער בהכנסה"
    assert {s["outcomes"]["documents"][d]["outcome"] for d in docs} == {"REVIEW"}
    ws = workspace(REVIEW_CASE)
    finding = next(i for i in ws["items"] if i["kind"] == "case_finding" and i["finding"]["code"] == INCOME)
    assert group_of(ws, finding["id"]) == "judgment" and finding["income"] and finding["recommendation"]["action"] == "request_explanation"
    fid = finding["finding"]["finding_id"]
    msg = finding["drafts"]["explanation"]["message_he"]
    assert rule(REVIEW_CASE, fid, "request_explanation", customer_message=msg).status_code == 200
    q = next(x for x in snap(noa, REVIEW_CASE)["customer_requests"] if x["kind"] == "explanation")
    r = noa.post(f"/api/cases/{REVIEW_CASE}/customer-requests/{q['customer_request_id']}/reply",
                 json={"text": "יש לי מענק שנתי שמשולם בדצמבר."})
    assert r.status_code == 200
    case_run(REVIEW_CASE)
    assert repo.finding(fid)["status"] == "open"                             # an unverified explanation is context only
    assert rule(REVIEW_CASE, fid, "resolve").status_code == 422              # a human decision needs a basis
    long = "ההכנסה המתועדת בשלושת התלושים תשמש לחישוב; המענק לא נכלל ללא אסמכתה"
    assert rule(REVIEW_CASE, fid, "resolve", reason_code="professional_judgment", rationale=long).status_code == 200
    assert repo.finding(fid)["resolution"] == "resolved_by_banker"


# ---------------------------------------------------------------- BLOCKER and the customer's replacement
def test_blocker_a_document_that_is_not_a_payslip_returns_to_the_customer_and_cannot_be_accepted():
    ido_months(BLOCKER_CASE, (("2026-07", 14400), ("2026-08", 14700)))
    wrong = not_a_payslip(BLOCKER_CASE)
    case_run(BLOCKER_CASE)
    mine = [f for f in repo.findings(BLOCKER_CASE, "open") if f["document_id"] == wrong]
    assert [(f["code"], f["review_state"]) for f in mine] == [("UNEXPECTED_DOCUMENT_TYPE", "CUSTOMER_ACTION_REQUIRED")]
    s = snap(ido, BLOCKER_CASE)
    assert s["readiness"]["customer_status"] == "CORRECTION_REQUIRED"
    assert s["outcomes"]["documents"][wrong] == {"outcome": "BLOCKER", "label_he": outcomes.OUTCOME_HE["BLOCKER"], "by": "ai"}
    assert s["outcomes"]["borrowers"]["BRW-A"]["outcome"] == "BLOCKER"
    req = next(r for r in s["readiness"]["requirements"] if r["code"] == "PAYSLIPS:BRW-A")
    assert req["missing"] == ["2026-09"]                                     # a non-payslip covers no month
    ws = workspace(BLOCKER_CASE)
    assert group_of(ws, f"doc:{wrong}") == "correction" and doc_item(ws, wrong)["outcome"]["outcome"] == "BLOCKER"
    r = decide(BLOCKER_CASE, wrong, "accept", acknowledged_finding_ids=[])
    assert r.status_code == 409 and "סמנו אותו כשגוי" in r.json()["detail"]


def test_the_customer_replaces_the_rejected_document_it_is_revalidated_and_the_history_is_kept():
    july, august = ido_months(BLOCKER_CASE, (("2026-07", 14400), ("2026-08", 14700)))
    wrong = not_a_payslip(BLOCKER_CASE)
    case_run(BLOCKER_CASE)
    finding = next(f for f in repo.findings(BLOCKER_CASE, "open") if f["document_id"] == wrong)
    corrected = GOLDEN / "02_CORRECTION" / "ido_2026_09_CORRECTED.pdf"
    r = upload(ido, BLOCKER_CASE, "BRW-A", corrected, expected_period="2026-09", replaces_document_id=wrong)
    assert r.status_code == 202, r.text
    assert r.json()["replaces"] == wrong and r.json()["intent"]["replaces_document_id"] == wrong
    new = r.json()["document"]["document_id"]
    s = snap(ido, BLOCKER_CASE)                      # replaced at once; the new file is still being reviewed
    assert s["outcomes"]["documents"][wrong]["outcome"] == "REPLACED" and s["outcomes"]["documents"][new]["outcome"] == "IN_PROGRESS"
    finish_review(new, review(new, "BRW-A", "2026-09", 15000))
    case_run(BLOCKER_CASE)
    f = repo.finding(finding["finding_id"])
    assert (f["status"], f["resolution"], f["superseded_by"]) == ("superseded", "replaced_by_customer_upload", new)
    assert f["history"][-1]["event"] == "superseded_by_replacement" and "אחרי שבדיקת ה-AI" in f["history"][-1]["note"]
    s = snap(ido, BLOCKER_CASE)
    assert s["readiness"]["customer_status"] == "CHECKS_COMPLETE"
    assert s["outcomes"]["documents"][new]["outcome"] == "PASS" and s["outcomes"]["borrowers"]["BRW-A"]["outcome"] == "PASS"
    assert s["document_status"][wrong]["status"] == "REPLACED" and s["document_status"][new]["status"] == "REPLACEMENT"
    assert {d["document_id"] for d in ido.get(f"/api/cases/{BLOCKER_CASE}/documents").json()} == {july, august, wrong, new}
    ws = workspace(BLOCKER_CASE)
    assert doc_item(ws, new)["replaces"] == {"document_id": wrong, "filename": "bank_statement_Jul_Sep_2026.pdf", "by": "customer"}
    assert group_of(ws, f"doc:{new}") == "decide" and group_of(ws, f"doc:{wrong}") == "done"
    actions = [e["action"] for e in repo.audit_events(BLOCKER_CASE, 200)]
    assert "customer_replaced_document" in actions and actions.count("document_uploaded") == 1   # the seeded files have no upload event
    again = upload(ido, BLOCKER_CASE, "BRW-A", GOLDEN / "01_INITIAL_UPLOADS" / "ido_2026_07.pdf", replaces_document_id=wrong)
    assert again.status_code == 409 and "כבר הוחלף" in again.json()["detail"]


def test_a_replacement_is_refused_unless_it_replaces_a_rejected_document_of_the_same_borrower():
    (july,) = ido_months(BLOCKER_CASE, (("2026-07", 14400),))
    wrong = not_a_payslip(BLOCKER_CASE)
    case_run(BLOCKER_CASE)
    pdf = GOLDEN / "02_CORRECTION" / "ido_2026_09_CORRECTED.pdf"
    assert upload(ido, BLOCKER_CASE, "BRW-A", pdf, replaces_document_id=july).status_code == 409        # a VALID payslip
    assert upload(ido, BLOCKER_CASE, "BRW-A", pdf, replaces_document_id="DOC-NOPE").status_code == 404
    other = add_doc("BRW-A", "2026-07", 14400, "ido.pdf", case=PASS_CASE)
    assert upload(ido, BLOCKER_CASE, "BRW-A", pdf, replaces_document_id=other).status_code == 404       # another case
    assert upload(ido, BLOCKER_CASE, "BRW-B", pdf, replaces_document_id=wrong).status_code == 422       # another borrower
    assert len(repo.documents(BLOCKER_CASE)) == 2                                                       # nothing was stored
    assert not repo.replacement_intents(BLOCKER_CASE)


def test_the_customers_replacement_closes_only_customer_findings_never_a_banker_finding():
    did = bare_doc(BLOCKER_CASE, "BRW-A", "ido_slip.pdf")
    r = review(did, "BRW-A", "2026-09", 15000, verdict="NEEDS_REVIEW", PS_04="FAIL", PS_06="FAIL")
    finish_review(did, r)
    case_run(BLOCKER_CASE)
    states = {f["code"]: f["review_state"] for f in repo.findings(BLOCKER_CASE, "open") if f["document_id"] == did}
    assert states == {"PERIOD_UNCLEAR": "CUSTOMER_ACTION_REQUIRED", "INTERNAL_ARITHMETIC_MISMATCH": "NEEDS_BANKER_REVIEW"}
    new = upload(ido, BLOCKER_CASE, "BRW-A", GOLDEN / "02_CORRECTION" / "ido_2026_09_CORRECTED.pdf",
                 replaces_document_id=did).json()["document"]["document_id"]
    finish_review(new, review(new, "BRW-A", "2026-09", 15000))
    case_run(BLOCKER_CASE)
    left = {f["code"]: f for f in repo.findings(BLOCKER_CASE) if f["document_id"] == did}
    assert left["PERIOD_UNCLEAR"]["status"] == "superseded"
    assert left["INTERNAL_ARITHMETIC_MISMATCH"]["status"] == "open"          # the banker decides it
    assert left["INTERNAL_ARITHMETIC_MISMATCH"]["detail"].get("not_reproduced_by")


def test_an_exact_copy_of_a_file_already_in_the_case_replaces_nothing():
    wrong = not_a_payslip(BLOCKER_CASE)
    case_run(BLOCKER_CASE)
    pdf = GOLDEN / "02_CORRECTION" / "ido_2026_09_CORRECTED.pdf"
    first = upload(ido, BLOCKER_CASE, "BRW-A", pdf, replaces_document_id=wrong).json()["document"]["document_id"]
    finish_review(first, review(first, "BRW-A", "2026-09", 15000))
    case_run(BLOCKER_CASE)
    second = not_a_payslip(BLOCKER_CASE)
    case_run(BLOCKER_CASE)
    dup = upload(ido, BLOCKER_CASE, "BRW-A", pdf, replaces_document_id=second)
    assert dup.status_code == 202 and dup.json()["created"] is False and dup.json()["replaces"] is None
    assert [i["replaces_document_id"] for i in repo.replacement_intents(BLOCKER_CASE)] == [wrong]


# ---------------------------------------------------------------- uncertainty goes to a person
def test_an_uncertain_classification_goes_to_the_banker_not_back_to_the_customer():
    unsure = not_a_payslip(BLOCKER_CASE, ps01="NEEDS_REVIEW")
    case_run(BLOCKER_CASE)
    f = next(x for x in repo.findings(BLOCKER_CASE, "open") if x["document_id"] == unsure)
    assert (f["code"], f["review_state"]) == ("UNEXPECTED_DOCUMENT_TYPE", "NEEDS_BANKER_REVIEW")
    assert f["title_he"] == "לא ברור אם המסמך הוא תלוש שכר" and "אינו תלוש שכר" not in f["message_he"]
    s = snap(ido, BLOCKER_CASE)
    assert s["outcomes"]["documents"][unsure]["outcome"] == "REVIEW"
    assert s["readiness"]["customer_status"] != "CORRECTION_REQUIRED"
    assert group_of(workspace(BLOCKER_CASE), f"doc:{unsure}") == "decide"


def test_an_uncertain_legibility_also_goes_to_the_banker_and_a_failed_one_to_the_customer():
    did = bare_doc(BLOCKER_CASE, "BRW-A", "scan.pdf")
    finish_review(did, review(did, "BRW-A", "2026-09", 15000, verdict="NEEDS_REVIEW", PS_02="NEEDS_REVIEW"))
    failed = bare_doc(BLOCKER_CASE, "BRW-A", "blurred.pdf")
    finish_review(failed, review(failed, "BRW-A", "2026-08", 14700, verdict="NEEDS_REVIEW", PS_02="FAIL"))
    case_run(BLOCKER_CASE)
    by_doc = {f["document_id"]: f["review_state"] for f in repo.findings(BLOCKER_CASE, "open") if f["code"] == "DOCUMENT_UNREADABLE"}
    assert by_doc == {did: "NEEDS_BANKER_REVIEW", failed: "CUSTOMER_ACTION_REQUIRED"}


# ---------------------------------------------------------------- derived outcomes: precedence
def test_outcome_precedence_human_decisions_first_then_blocker_then_review():
    doc = {"document_id": "D", "status": "reviewed"}
    valid, unsure = {"verdict": "VALID"}, {"verdict": "NEEDS_REVIEW"}
    banker = [{"document_id": None, "review_state": "NEEDS_BANKER_REVIEW", "code": INCOME, "evidence": [{"document_id": "D"}]}]
    o = lambda status, review=valid, found=(): outcomes.document_outcome(doc, review, status, list(found))["outcome"]  # noqa: E731
    assert o("AWAITING_DECISION") == "PASS"
    assert o("AWAITING_DECISION", unsure) == "REVIEW" and o("AWAITING_DECISION", valid, banker) == "REVIEW"
    assert outcomes.document_outcome(doc, valid, "AWAITING_DECISION", banker)["label_he"] == outcomes.INCOME_REVIEW_HE
    assert o("AWAITING_CUSTOMER_FIX", unsure) == "BLOCKER" and o("CORRECTION_REQUESTED") == "BLOCKER"
    assert o("ACCEPTED", unsure, banker) == "ACCEPTED" and o("ESCALATED") == "REVIEW" and o("REPLACED") == "REPLACED"
    assert outcomes.document_outcome({"document_id": "D", "status": "failed"}, None, "FAILED", [])["outcome"] == "NOT_COMPLETED"
    assert outcomes.document_outcome({"document_id": "D", "status": "processing"}, None, "PROCESSING", [])["outcome"] == "IN_PROGRESS"
    assert outcomes.set_outcome("MISSING_DOCUMENTS", [])["outcome"] == "INCOMPLETE"       # missing is neither PASS nor BLOCKER
    assert outcomes.set_outcome("NO_PAYSLIPS_REQUIRED", []) is None


# ---------------------------------------------------------------- "start a new demo"
def _rows(case: str) -> dict:
    return {t: db.one(f"SELECT COUNT(*) AS n FROM {t} WHERE case_id=?", (case,))["n"] for t in repo.CASE_TABLES}


def test_start_a_new_demo_wipes_only_cases_006_to_008_and_their_files():
    other_case = "DEMO-MTZ-2026-004"
    repo.reset_case(other_case)
    add_doc("BRW-A", "2026-07", 14400, "keep.pdf", case=other_case)
    case_run(other_case)
    ido_months(PASS_CASE)
    case_run(PASS_CASE)
    not_a_payslip(BLOCKER_CASE)
    case_run(BLOCKER_CASE)
    upload(noa, REVIEW_CASE, "BRW-B", GOLDEN / "01_INITIAL_UPLOADS" / "noa_2026_07.pdf")   # real file on disk, job queued
    repo.add_turn(REVIEW_CASE, "text", "user", "שלום", {})
    with db.tx() as c:
        c.execute("INSERT INTO llm_calls(at, model, purpose, ok) VALUES (?,?,?,1)", (now_iso(), "test", "extract"))
    keep, ledger = _rows(other_case), db.one("SELECT COUNT(*) AS n FROM llm_calls")["n"]
    assert (settings.uploads_dir / REVIEW_CASE).exists()
    assert anon.post("/api/presenter/demo-reset").status_code == 401
    r = ido.post("/api/presenter/demo-reset")
    assert r.status_code == 200, r.text
    assert r.json()["reset"] == list(EXECUTIVE)
    for cid in EXECUTIVE:
        assert not any(_rows(cid).values()), cid
        assert not (settings.uploads_dir / cid).exists()
    assert _rows(other_case) == keep and db.one("SELECT COUNT(*) AS n FROM llm_calls")["n"] == ledger
    s = snap(ido, PASS_CASE)
    assert s["readiness"]["state"] == "NOT_CHECKED" and s["readiness"]["customer_status"] == "AWAITING_UPLOAD"
    assert not s["updates"] and not s["findings"] and s["outcomes"]["documents"] == {}
    record = db.one("SELECT * FROM audit WHERE action='executive_demo_reset' ORDER BY event_id DESC LIMIT 1")
    assert record["case_id"] is None and json.loads(record["detail"])["cases"] == list(EXECUTIVE)


def test_start_a_new_demo_waits_for_a_running_review_and_can_be_switched_off(monkeypatch):
    ido_months(PASS_CASE)
    with db.tx() as c:
        c.execute("INSERT INTO jobs(job_id, kind, case_id, document_id, idempotency_key, status, attempts, not_before,"
                  " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("JOB-RUN", "review_document", PASS_CASE, None, "k-running", "running", 1, now_iso(), now_iso(), now_iso()))
    r = ido.post("/api/presenter/demo-reset")
    assert r.status_code == 409 and "האיפוס יתבצע" in r.json()["detail"]
    assert len(repo.documents(PASS_CASE)) == 3                               # nothing was deleted
    monkeypatch.setattr(routes, "settings", dataclasses.replace(routes.settings, demo_reset=False))
    assert ido.post("/api/presenter/demo-reset").status_code == 403


# ---------------------------------------------------------------- worker guards: no ghost events after a reset
class _ResetWhileReviewing:
    """A provider double whose review is interrupted by a case reset, the way a presenter's reset can land mid-review."""
    name = "gemini"

    def __init__(self, case_id: str, fail: bool = False):
        self.case_id, self.fail, self.results = case_id, fail, {}

    def identity(self):
        from app.review.contract import ProviderIdentity
        return ProviderIdentity(provider="gemini", mode="LIVE", prompt_version="test", models={"extract": "test"})

    def start_document_review(self, req, progress):
        repo.reset_case(self.case_id)
        if self.fail:
            raise RuntimeError("provider failed after the reset")
        self.results[req.run_id] = DocumentReviewResult(**review(req.document_id, "BRW-A", "2026-07", 14400) | {"run_id": req.run_id})
        return ReviewHandle(provider="gemini", run_id=req.run_id)

    def get_status(self, handle):
        return ReviewStatus(state="succeeded")

    def get_document_result(self, handle):
        return self.results.pop(handle.run_id)

    def review_case(self, req, progress):
        repo.reset_case(self.case_id)
        return case_review.run(self.identity(), req, progress)


@pytest.mark.parametrize("fail", [False, True])
def test_a_review_finishing_after_a_reset_writes_nothing(monkeypatch, fail):
    did = bare_doc(PASS_CASE, "BRW-A", "ido.pdf")
    repo.set_document(did, status="queued", stage="queued")
    monkeypatch.setattr(registry, "active", lambda: _ResetWhileReviewing(PASS_CASE, fail))
    engine._run_document({"job_id": "JOB-X", "case_id": PASS_CASE, "document_id": did, "attempts": 3})
    assert not any(_rows(PASS_CASE).values())                                # no audit, no run, no case job


def test_a_case_review_finishing_after_a_reset_writes_no_findings(monkeypatch):
    ido_months(PASS_CASE, (("2026-07", 14400),))
    monkeypatch.setattr(registry, "active", lambda: _ResetWhileReviewing(PASS_CASE))
    engine._run_case({"job_id": "JOB-Y", "case_id": PASS_CASE, "payload": None})
    assert not any(_rows(PASS_CASE).values())


# ---------------------------------------------------------------- the golden set stays reference truth only
def test_the_review_pipeline_never_reads_the_golden_set_or_expected_outputs():
    app_dir = ROOT / "backend" / "app"
    for sub in ("review", "workflow", "agent", "llm", "mcp"):
        for py in (app_dir / sub).glob("*.py"):
            text = py.read_text(encoding="utf8")
            assert not re.search(r"golden_set|05_EXPECTED|presenter_scenarios_manifest|expectedDocumentVerdict", text), py


def test_featured_loan_scenarios_point_at_real_unmodified_files_and_the_demo_cases(monkeypatch):
    from app.policy import store
    monkeypatch.setattr(requirements, "pin", lambda case_id: store.published("loan_policy")["version_id"])  # the product default
    manifest = json.loads(PRESENTER_MANIFEST.read_text(encoding="utf8"))
    docs = {d["id"]: d for d in manifest["documents"]}
    featured = manifest["featured"]
    assert [f["outcome"] for f in featured] == ["PASS", "REVIEW", "BLOCKER", "CORRECTION"]
    assert [f["caseId"] for f in featured] == [PASS_CASE, INCOME_CASE, BLOCKER_CASE, JOURNEY_CASE]
    for f in featured:
        assert f["caseId"] in bank.executive_demo_case_ids()
        codes = {r["code"] for r in requirements.for_case(f["caseId"])}
        for step in f["steps"]:
            d = docs[step["file"]]
            assert hashlib.sha256((GOLDEN.parent / d["downloadPath"]).read_bytes()).hexdigest() == d["sha256"]
            assert step["borrower"] in {b["borrower_id"] for b in bank.get_case(f["caseId"])["borrowers"]}
            assert (f.get("uploadAs") or {}).get(step["file"], d["uploadAs"]) in codes      # a real card of that case
    bundle = TestClient(app).get("/api/presenter/scenarios").json()
    assert len(bundle["manifest"]["scenarios"]) == 10 and len(bundle["manifest"]["documents"]) == 14
    assert all(v["sha256_matches_manifest"] for v in bundle["files"].values())
    assert {r["rubric_id"] for r in bundle["rubrics"]} >= {"payslip.il.salaried", "id_document.il", "bank_statement.il"}
    # every golden-set payslip the scenarios use is the original, byte for byte
    golden = [d for d in manifest["documents"] if d["downloadPath"].startswith("golden_set/")]
    assert golden and all(hashlib.sha256((GOLDEN.parent / d["downloadPath"]).read_bytes()).hexdigest() == d["sha256"] for d in golden)
