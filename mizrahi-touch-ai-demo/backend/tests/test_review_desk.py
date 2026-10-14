"""Integration tests of the banker review desk through the real HTTP routes, case review, findings
lifecycle and readiness. Only Gemini is replaced: document reviews are stored results shaped like the
provider's, and the semantic income judgement returns a fixed answer. The arithmetic, the coverage,
the rubric outcome and every state transition are the production code."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.agent import tools
from app.config import settings
from app.main import app
from app.review import case_review, rubrics
from app.store import repo
from app.util import new_id, now_iso
from app.workflow import engine

pytestmark = pytest.mark.usefixtures("payslip_scope")    # the payslip workflow on its own (see conftest)
CASE, OTHER = "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-003"


def bearer(role: str, subject) -> dict:
    return {"Authorization": f"Bearer {auth.issue(role, subject)}"}


DANA, ORI = bearer("staff", "STAFF-DANA"), bearer("staff", "STAFF-ORI")
FIX = Path(__file__).resolve().parents[2] / "fixtures" / "out" / "main"
PEOPLE = {"BRW-A": ("עידו לביא", "039812457"), "BRW-B": ("נועה לביא", "204376815")}
client = TestClient(app)
# a customer session for cases 001 and 003 and, in the same browser, Dana's staff session; a bearer overrides the cookie
client.cookies.set(auth.COOKIES["customer"], auth.issue("customer", [CASE, OTHER]))
client.cookies.set(auth.COOKIES["staff"], auth.issue("staff", "STAFF-DANA"))
anon = TestClient(app)


def test_tests_never_touch_the_demo_data():
    assert settings.data_dir == Path(os.environ["DATA_DIR"]) and "mcs-tests-" in str(settings.data_dir)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    for c in (CASE, OTHER):
        repo.reset_case(c)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")

    def semantic(req, borrowers, income):
        out = []
        for bid, stats in income.items():
            if stats.get("months"):
                out.append({"borrower_id": bid, "definitions_equivalent": True,
                            # the live model labelled a −1.1% gap INCONSISTENT; code must still decide by the tolerance
                            "income_assessment": "INCONSISTENT" if stats.get("difference_ils") else "CONSISTENT",
                            "explanation_he": "הסבר המודל", "evidence_needed_he": ["אישור מעסיק על רכיבי שכר משתנים"],
                            "identity_assessment": "CONSISTENT"})
        return {"borrowers": out, "limitations_he": []}

    monkeypatch.setattr(case_review, "_semantic", semantic)
    yield


# ---------------------------------------------------------------- building a case without Gemini
def _criteria(**overrides: str) -> list[dict]:
    out = []
    for c in rubrics.for_document("PAYSLIPS:BRW-A")["criteria"]:
        outcome = overrides.get(c["id"].replace("-", "_"), "PASS")
        out.append({"criterion_id": c["id"], "title_he": c["title_he"], "method": c["method"], "outcome": outcome,
                    "severity": c["severity"], "reason_code": c["reason_code"], "escalation": c.get("escalation"),
                    "explanation_he": "עבר" if outcome == "PASS" else f"נכשל: {c['title_he']}", "evidence_ids": [],
                    "decided_by": "code"})
    return out


def _fact(doc_id: str, field: str, label: str, raw: str, value, y: float) -> dict:
    return {"field": field, "label_he": label, "value_raw": raw, "value_normalized": value, "confidence": 1.0,
            "evidence": {"evidence_id": f"{doc_id}:{field}", "document_id": doc_id, "field": field, "page": 1, "quote": raw,
                         "bbox": [400, y, 550, y + 12], "coord_space": "pdf_points", "page_size": [595.92, 842.88],
                         "witness": "text_layer_exact", "witness_detail": "test"}}


def review(doc_id: str, borrower: str, period: str, net: float, verdict: str = "VALID", file_period: str | None = None,
           matched: str | None = None, **criteria: str) -> dict:
    name, nid = PEOPLE[matched or borrower]
    gross = net + 3800
    y, m = period.split("-")
    return {"run_id": new_id("RUN"), "document_id": doc_id, "identity": {"provider": "gemini", "mode": "LIVE",
            "models": {"judge": "test"}, "prompt_version": "test"}, "rubric_id": "payslip.il.salaried", "rubric_version": "1.1.0",
            "started_at": now_iso(), "finished_at": now_iso(), "doc_type": "payslip", "doc_type_he": "תלוש שכר",
            "is_scanned": False, "pages": 1, "legibility": "good", "matched_borrower_id": matched or borrower, "period": period,
            "file_name_period": file_period or period,
            "facts": [_fact(doc_id, "employee_name", "שם העובד", name, name, 100), _fact(doc_id, "employee_id", "ת.ז.", nid, nid, 120),
                      _fact(doc_id, "salary_period", "תקופת שכר", f"{m}/{y}", period, 140),
                      _fact(doc_id, "gross_pay", "שכר ברוטו", f"{gross:,.2f}", gross, 300),
                      _fact(doc_id, "total_deductions", "סה״כ ניכויים", "3,800.00", 3800.0, 320),
                      _fact(doc_id, "net_pay", "נטו לתשלום", f"{net:,.2f}", net, 360)],
            "criteria": _criteria(**criteria), "verdict": verdict, "verdict_reason_codes": [], "summary_he": "סיכום",
            "limitations_he": [], "uncertainty_he": [], "security_flags": [], "demo_marked": True, "payroll_lines": {}, "usage": {}}


def add_doc(borrower: str, period: str, net: float, filename: str | None = None, case: str = CASE, **kw) -> str:
    doc_id = new_id("DOC")
    repo.insert_document({"document_id": doc_id, "case_id": case, "borrower_id": borrower, "requirement_code": f"PAYSLIPS:{borrower}",
                          "filename": filename or f"{borrower}_{period}.pdf", "mime": "application/pdf", "sha256": new_id("SHA"),
                          "bytes": 1000, "pages": 1, "text_layer_chars": 500, "storage_path": str(FIX / "ido_payslip_2026-07.pdf"),
                          "uploaded_at": now_iso(), "uploaded_by": "customer", "channel": "customer_app", "status": "reviewed",
                          "stage": "done"})
    finish_review(doc_id, review(doc_id, borrower, period, net, **kw))
    return doc_id


def finish_review(doc_id: str, result: dict) -> None:
    doc = repo.document(doc_id)
    repo.start_run({"run_id": result["run_id"], "case_id": doc["case_id"], "document_id": doc_id, "scope": "document",
                    "provider": "gemini", "models": "{}", "rubric_id": "payslip.il.salaried", "rubric_version": "1.1.0",
                    "prompt_version": "test", "status": "running", "stage": "judge", "started_at": now_iso(),
                    "input_hash": doc["sha256"], "trigger": "test"})
    repo.update_run(result["run_id"], status="succeeded", stage="done", finished_at=now_iso(), result=db.jdump(result))
    repo.set_document(doc_id, status="reviewed", stage="done")
    with db.tx() as c:
        c.execute("UPDATE jobs SET status='succeeded' WHERE document_id=?", (doc_id,))


def case_run(case: str = CASE) -> None:
    with db.tx() as c:
        c.execute("UPDATE jobs SET status='succeeded' WHERE case_id=? AND kind='review_case'", (case,))
    engine._run_case({"job_id": new_id("JOB"), "case_id": case, "payload": None})


def workspace(case: str = CASE) -> dict:
    r = client.get(f"/api/banker/cases/{case}/workspace")
    assert r.status_code == 200, r.text
    return r.json()


def item(ws: dict, item_id: str) -> dict:
    return next(i for i in ws["items"] if i["id"] == item_id)


def group_of(ws: dict, item_id: str) -> str:
    return next(g["key"] for g in ws["groups"] if item_id in g["items"])


def decide(doc_id: str, action: str, case: str = CASE, headers=DANA, **body):
    return client.post(f"/api/banker/cases/{case}/documents/{doc_id}/decision", json={"action": action, **body}, headers=headers)


def snapshot(case: str = CASE) -> dict:
    return client.get(f"/api/cases/{case}").json()


def ido_set(mislabeled: bool = True) -> dict[str, str]:
    """Ido: July, August, and a file named September that prints August. Noa: three valid months."""
    docs = {"ido07": add_doc("BRW-A", "2026-07", 13200, "ido_payslip_2026-07.pdf"),
            "ido08": add_doc("BRW-A", "2026-08", 13500, "ido_payslip_2026-08.pdf")}
    if mislabeled:
        docs["ido09"] = add_doc("BRW-A", "2026-08", 13500, "ido_payslip_2026-09.pdf", file_period="2026-09")
    for m in ("2026-07", "2026-08", "2026-09"):
        docs[f"noa{m[-2:]}"] = add_doc("BRW-B", m, 18400, f"noa_payslip_{m}.pdf")
    case_run()
    return docs


# ---------------------------------------------------------------- access
def test_banker_writes_need_the_assigned_banker():
    docs = ido_set()
    url = f"/api/banker/cases/{CASE}/documents/{docs['ido07']}/decision"
    assert anon.post(url, json={"action": "accept"}).status_code == 401
    assert anon.post(url, json={"action": "accept"}, headers={"X-Staff-Id": "STAFF-DANA"}).status_code == 401   # a header is no identity
    assert decide(docs["ido07"], "accept", headers=bearer("staff", "STAFF-NOBODY")).status_code == 401
    assert decide(docs["ido07"], "accept", headers=bearer("customer", [CASE])).status_code == 401   # a customer is not staff
    assert decide(docs["ido07"], "accept", headers=ORI).status_code == 403
    other = add_doc("BRW-A", "2026-07", 13200, case=OTHER)
    assert decide(other, "accept").status_code == 404                      # a document of another case
    assert anon.post(f"/api/banker/cases/{CASE}/confirm-preparation", json={}).status_code == 401
    assert anon.post(f"/api/banker/cases/{CASE}/recheck").status_code == 401
    assert not repo.decisions(CASE)


def test_the_assistant_and_mcp_have_no_banker_decision_tools():
    writes = {n for n, spec in tools.TOOLS.items() if spec["write"]}
    assert writes == {"record_customer_statement", "request_banker_handoff", "request_revalidation"}


# ---------------------------------------------------------------- the queue tells missing from uploaded
def test_workspace_groups_missing_months_apart_from_uploaded_documents():
    docs = ido_set()
    ws = workspace()
    assert group_of(ws, f"doc:{docs['ido07']}") == "decide"
    assert group_of(ws, "missing:BRW-A:2026-09") == "missing"
    missing = item(ws, "missing:BRW-A:2026-09")
    assert missing["kind"] == "missing" and missing["allowed_actions"] == ["request_missing"]
    assert missing["related_documents"][0]["document_id"] == docs["ido09"]
    assert ws["summary"]["missing"] == 1 and ws["summary"]["payslips_required"] == 6
    assert ws["summary"]["payslips_verified"] == 5                         # the September copy is a valid August
    assert ws["bank_stage"]["label_he"] == "השלמת מסמכים" and ws["bank_stage"]["authoritative"] is False
    assert ws["can_confirm"]["allowed"] is False and "חסר תלוש אחד" in ws["can_confirm"]["reason_he"]


def test_small_income_gap_follows_the_rubric_not_the_model_label():
    ido_set()
    ido = next(b for b in workspace()["borrowers"] if b["borrower_id"] == "BRW-A")["income"]
    assert ido["difference_ils"] == -150 and ido["difference_pct"] == -1.11 and ido["months_compared"] == ["2026-07", "2026-08"]
    assert ido["tolerance_pct"] == 5.0 and ido["outcome"] == "PASS" and ido["finding_id"] is None
    assert ido["model_assessment"] == "INCONSISTENT"                       # reported, but not decisive
    assert ido["basis"] == "preliminary" and ido["months_missing"] == ["2026-09"]           # September is still missing
    assert ido["summary_he"].startswith("השוואה ראשונית על בסיס 2 מתוך 3 חודשים")
    assert "בתוך סף הסבולת של 5%" in ido["summary_he"] and ido["tone"] == "neutral"
    assert not [f for f in repo.findings(CASE, "open") if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"
                and f["borrower_id"] == "BRW-A"]


# ---------------------------------------------------------------- accept
def test_accepting_a_valid_document_is_persisted_once_and_changes_no_bank_state():
    docs = ido_set()
    stage = snapshot()["case"]["bank_stage"]
    r = decide(docs["ido07"], "accept", acknowledged_finding_ids=[], request_id="req-1")
    assert r.status_code == 200, r.text
    d = r.json()["decision"]
    assert (d["action"], d["previous_status"], d["new_status"], d["actor_id"], d["actor_name"]) == \
        ("ACCEPT_DOCUMENT", "AWAITING_DECISION", "ACCEPTED", "STAFF-DANA", "דנה כהן")
    assert d["evidence_refs"] and all(e["document_id"] == docs["ido07"] for e in d["evidence_refs"])
    again = decide(docs["ido07"], "accept", acknowledged_finding_ids=[], request_id="req-1")
    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert decide(docs["ido07"], "accept", acknowledged_finding_ids=[], request_id="req-2").status_code == 409
    assert len([x for x in repo.decisions(CASE) if x["action"] == "ACCEPT_DOCUMENT"]) == 1
    ws = workspace()
    assert group_of(ws, f"doc:{docs['ido07']}") == "done"
    assert item(ws, f"doc:{docs['ido07']}")["ai"]["verdict"] == "VALID"   # the AI verdict is untouched
    s = snapshot()
    assert s["case"]["bank_stage"] == stage and s["readiness"]["state"] != "PREPARATION_CONFIRMED"
    assert s["document_status"][docs["ido07"]]["status"] == "ACCEPTED"
    assert any(e["action"] == "banker_document_decision" for e in repo.audit_events(CASE))


def test_accepting_with_banker_findings_needs_acknowledgement_and_a_reason_and_is_not_reopened():
    doc = add_doc("BRW-B", "2026-07", 18400, verdict="NEEDS_REVIEW", PS_10="NEEDS_REVIEW")
    case_run()
    ws = workspace()
    it = item(ws, f"doc:{doc}")
    fids = it["banker"]["acknowledge_finding_ids"]
    assert len(fids) == 1 and it["banker"]["accept_requires_rationale"]
    assert decide(doc, "accept", acknowledged_finding_ids=[]).status_code == 409          # stale view
    assert decide(doc, "accept", acknowledged_finding_ids=fids).status_code == 422        # no reason
    r = decide(doc, "accept", acknowledged_finding_ids=fids, rationale="תאריך ההפקה מתאים לחודש העוקב")
    assert r.status_code == 200, r.text
    f = repo.finding(fids[0])
    assert f["status"] == "resolved" and f["resolution"] == "accepted_by_banker"
    assert f["history"][-1]["actor"] == "STAFF-DANA"
    case_run()                                                             # the AI still sees the pay-date issue
    assert not [x for x in repo.findings(CASE, "open") if x["document_id"] == doc and x["review_state"] == "NEEDS_BANKER_REVIEW"]
    req = next(r for r in snapshot()["readiness"]["requirements"] if r["code"] == "PAYSLIPS:BRW-B")
    assert "2026-07" in req["verified_months"]                             # accepted by the banker counts


def test_a_customer_fix_finding_must_be_dismissed_before_the_document_can_be_accepted():
    doc = add_doc("BRW-A", "2026-07", 18400, verdict="INVALID", matched="BRW-B", PS_03="FAIL")
    case_run()
    mismatch = next(f for f in repo.findings(CASE, "open") if f["code"] == "BORROWER_MISMATCH")
    r = decide(doc, "accept", acknowledged_finding_ids=[])
    assert r.status_code == 409 and "סמנו אותו כשגוי" in r.json()["detail"]
    dismiss = client.post(f"/api/banker/cases/{CASE}/findings/{mismatch['finding_id']}/decision",
                          json={"action": "dismiss"}, headers=DANA)
    assert dismiss.status_code == 422                                      # a dismissal needs a reason
    dismiss = client.post(f"/api/banker/cases/{CASE}/findings/{mismatch['finding_id']}/decision",
                          json={"action": "dismiss", "rationale": "נבדק מול ת״ז — המסמך של עידו"}, headers=DANA)
    assert dismiss.status_code == 200
    case_run()
    assert not [f for f in repo.findings(CASE, "open") if f["code"] == "BORROWER_MISMATCH"]   # the ruling holds
    assert decide(doc, "accept", acknowledged_finding_ids=[], rationale="אומת ידנית").status_code == 200


# ---------------------------------------------------------------- the correction loop
def test_correction_request_reaches_the_customer_and_a_replacement_is_re_reviewed():
    docs = ido_set()
    stage = snapshot()["case"]["bank_stage"]
    it = item(workspace(), f"doc:{docs['ido09']}")
    assert it["ai"]["attention_he"][0] == "הקובץ שהועלה עבור ספטמבר מכיל בפועל תלוש של חודש אוגוסט."
    assert it["draft"]["message_he"] == ("שלום עידו, המסמך שהעלית עבור ספטמבר מציג את חודש אוגוסט. "
                                         "כדי להמשיך בבדיקת מסמכי ההכנסה, נא להעלות את תלוש ספטמבר 2026.")
    assert it["draft"]["requested_period"] == "2026-09"
    edited = it["draft"]["message_he"] + " תודה!"
    r = decide(docs["ido09"], "request_correction", customer_message=edited, requested_period="2026-09",
               rationale="פנימי: שם הקובץ שגוי", request_id="corr-1")
    assert r.status_code == 200, r.text
    request = r.json()["customer_request"]
    assert (request["status"], request["kind"], request["period"], request["message_he"]) == ("OPEN", "correction", "2026-09", edited)
    assert decide(docs["ido09"], "request_correction", customer_message="x", request_id="corr-2").status_code == 409

    s = snapshot()
    assert s["readiness"]["customer_status"] == "CORRECTION_REQUIRED" and s["readiness"]["counts"]["customer_requests"] == 1
    mine = [q for q in s["customer_requests"] if q["status"] == "OPEN"]
    assert len(mine) == 1 and mine[0]["message_he"] == edited and mine[0]["created_by_name"] == "דנה כהן"
    raw = json.dumps(s, ensure_ascii=False)
    assert "פנימי: שם הקובץ שגוי" not in raw                               # the internal rationale stays internal
    assert any(u["action"] == "banker_document_decision" and u["detail"].get("customer_message") == edited for u in s["updates"])
    assert any(a["type"] == "NAVIGATE_TO_DOCUMENT_UPLOAD" and a["params"]["borrower_id"] == "BRW-A" for a in s["available_actions"])
    assert "הבנקאית ביקשה" in tools.call("list_open_items", CASE, {"audience": "customer"}, {"channel": "text"})["spoken_he"]

    with (FIX / "ido_payslip_2026-09_corrected.pdf").open("rb") as fh:
        up = client.post(f"/api/cases/{CASE}/documents", data={"borrower_id": "BRW-A", "customer_request_id": request["customer_request_id"],
                                                               "expected_period": "2026-09"},
                         files={"file": ("ido_payslip_2026-09_corrected.pdf", fh, "application/pdf")})
    assert up.status_code == 202, up.text
    new_doc = up.json()["document"]["document_id"]
    assert up.json()["answered_request"] == request["customer_request_id"]
    assert repo.customer_request(request["customer_request_id"])["status"] == "RESPONDED"
    assert workspace()["summary"]["processing"] == 1                       # the replacement waits for its review

    finish_review(new_doc, review(new_doc, "BRW-A", "2026-09", 13500))
    case_run()
    ws = workspace()
    old, new = item(ws, f"doc:{docs['ido09']}"), item(ws, f"doc:{new_doc}")
    assert old["banker"]["status"] == "REPLACED" and old["replaced_by"]["document_id"] == new_doc
    assert new["banker"]["status"] == "AWAITING_DECISION" and new["replaces"]["document_id"] == docs["ido09"]
    assert group_of(ws, f"doc:{new_doc}") == "decide" and group_of(ws, f"doc:{docs['ido09']}") == "done"
    assert not [i for i in ws["items"] if i["kind"] == "missing"]
    assert old["history"][0]["action"] == "REQUEST_CORRECTION"            # the earlier decision is kept
    mismatch = next(f for f in old["findings"] if f["code"] == "FILE_NAME_PERIOD_MISMATCH")
    assert mismatch["status"] == "superseded" and mismatch["resolution"] == "replaced_by_customer_upload"
    gap = next(f for f in repo.findings(CASE) if f["key"] == "REQUIRED_PERIOD_MISSING:BRW-A:2026-09")
    assert gap["status"] == "resolved" and gap["resolution"] == "resolved_by_new_evidence"
    s = snapshot()
    assert s["readiness"]["counts"]["customer_requests"] == 0 and s["readiness"]["customer_status"] != "CORRECTION_REQUIRED"
    ido = next(r for r in s["readiness"]["requirements"] if r["code"] == "PAYSLIPS:BRW-A")
    assert ido["ai_state"] == "extracted" and ido["verified_months"] == ["2026-07", "2026-08", "2026-09"]
    assert s["document_status"][docs["ido09"]]["status"] == "REPLACED" and s["document_status"][new_doc]["status"] == "REPLACEMENT"
    assert s["case"]["bank_stage"] == stage
    assert decide(new_doc, "accept", acknowledged_finding_ids=[]).status_code == 200


def test_upload_answering_another_borrowers_request_is_refused_before_storing():
    docs = ido_set()
    r = decide(docs["ido09"], "request_correction", customer_message="נא להעלות", requested_period="2026-09")
    request_id = r.json()["customer_request"]["customer_request_id"]
    before = len(repo.documents(CASE))
    with (FIX / "noa_payslip_2026-09.pdf").open("rb") as fh:
        up = client.post(f"/api/cases/{CASE}/documents", data={"borrower_id": "BRW-B", "customer_request_id": request_id},
                         files={"file": ("noa.pdf", fh, "application/pdf")})
    assert up.status_code == 422 and len(repo.documents(CASE)) == before
    assert repo.customer_request(request_id)["status"] == "OPEN"


# ---------------------------------------------------------------- missing documents, escalation, findings
def test_missing_document_request_and_its_rules():
    docs = ido_set()
    body = {"borrower_id": "BRW-A", "period": "2026-09", "customer_message": "נא להעלות את תלוש ספטמבר", "request_id": "m-1"}
    assert client.post(f"/api/banker/cases/{CASE}/missing-requests", json={**body, "customer_message": ""}, headers=DANA).status_code == 422
    r = client.post(f"/api/banker/cases/{CASE}/missing-requests", json=body, headers=DANA)
    assert r.status_code == 200 and r.json()["customer_request"]["kind"] == "missing_document"
    assert client.post(f"/api/banker/cases/{CASE}/missing-requests", json=body, headers=DANA).json()["duplicate"] is True
    assert client.post(f"/api/banker/cases/{CASE}/missing-requests", json={**body, "request_id": "m-2"}, headers=DANA).status_code == 409
    not_missing = {**body, "period": "2026-07", "request_id": "m-3"}
    assert client.post(f"/api/banker/cases/{CASE}/missing-requests", json=not_missing, headers=DANA).status_code == 409
    ws = workspace()
    assert item(ws, "missing:BRW-A:2026-09")["open_request"]["status"] == "OPEN"
    assert next(m for b in ws["borrowers"] if b["borrower_id"] == "BRW-A" for m in b["months"] if m["period"] == "2026-09")["state"] == "requested"
    # a correction for the same month is refused while that request is open
    assert decide(docs["ido09"], "request_correction", customer_message="x", requested_period="2026-09").status_code == 409


def test_escalation_needs_a_reason_and_can_be_followed_by_a_decision():
    docs = ido_set()
    assert decide(docs["noa07"], "escalate").status_code == 422
    assert decide(docs["noa07"], "escalate", rationale="לבדוק מול המעסיק").status_code == 200
    assert group_of(workspace(), f"doc:{docs['noa07']}") == "escalated"
    assert decide(docs["noa07"], "escalate", rationale="שוב").status_code == 409
    assert decide(docs["noa07"], "accept", acknowledged_finding_ids=[]).status_code == 200


def test_finding_rulings_are_scoped_and_audited():
    ido_set()
    gap = next(f for f in repo.findings(CASE, "open") if f["code"] == "REQUIRED_PERIOD_MISSING")
    info = next(f for f in repo.findings(CASE, "open") if f["review_state"] == "INFO")
    for f, action in ((gap, "dismiss"), (gap, "accept_explanation"), (info, "dismiss")):
        r = client.post(f"/api/banker/cases/{CASE}/findings/{f['finding_id']}/decision",
                        json={"action": action, "rationale": "x"}, headers=DANA)
        assert r.status_code == 409, (f["code"], action)
    assert repo.finding(gap["finding_id"])["status"] == "open"


def test_income_variance_goes_to_the_banker_and_a_ruling_holds_until_the_figures_change():
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-B", m, 16900)
    case_run()
    ws = workspace()
    variance = next(i for i in ws["items"] if i["kind"] == "case_finding")
    assert group_of(ws, variance["id"]) == "judgment" and variance["income"]["outcome"] in ("FAIL", "NEEDS_REVIEW")
    assert variance["income"]["difference_pct"] == -8.65 and "מעל סף הסבולת של 5%" in variance["income"]["summary_he"]
    fid = variance["finding"]["finding_id"]
    url = f"/api/banker/cases/{CASE}/findings/{fid}/decision"
    r = client.post(url, json={"action": "request_document", "customer_message": variance["draft"]["message_he"]}, headers=DANA)
    assert r.status_code == 200 and r.json()["customer_request"]["kind"] == "additional_document"
    assert repo.finding(fid)["status"] == "open"                           # asking for a document does not close it
    assert client.post(url, json={"action": "accept_explanation"}, headers=DANA).status_code == 422
    assert client.post(url, json={"action": "accept_explanation", "rationale": "רכיב משתנה מאומת"}, headers=DANA).status_code == 200
    case_run()
    assert not [f for f in repo.findings(CASE, "open") if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"]
    add_doc("BRW-B", "2026-09", 12000, "noa_extra.pdf")                    # the figures change → a new finding
    with db.tx() as c:
        c.execute("UPDATE documents SET uploaded_at='2026-01-01T00:00:00+00:00' WHERE filename='noa_extra.pdf'")
    case_run()
    assert [f for f in repo.findings(CASE, "open") if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"]


# ---------------------------------------------------------------- the case-level step
def test_preparation_confirmation_is_gated_by_open_requests_and_never_touches_the_bank_stage():
    docs = ido_set(mislabeled=False)
    add = add_doc("BRW-A", "2026-09", 13500, "ido_payslip_2026-09.pdf")
    case_run()
    r = decide(docs["noa07"], "request_correction", customer_message="נא להעלות עותק ברור")
    assert r.status_code == 200
    blocked = client.post(f"/api/banker/cases/{CASE}/confirm-preparation", json={"note": "x"}, headers=DANA)
    assert blocked.status_code == 409
    with (FIX / "noa_payslip_2026-07_scan.pdf").open("rb") as fh:
        up = client.post(f"/api/cases/{CASE}/documents", data={"borrower_id": "BRW-B"},
                         files={"file": ("noa_payslip_2026-07_scan.pdf", fh, "application/pdf")})
    new_doc = up.json()["document"]["document_id"]
    assert up.json()["answered_request"]                                   # the borrower's only open request
    finish_review(new_doc, review(new_doc, "BRW-B", "2026-07", 18400))
    case_run()
    stage = snapshot()["case"]["bank_stage"]
    ok = client.post(f"/api/banker/cases/{CASE}/confirm-preparation", json={"note": "מוכן"}, headers=DANA)
    assert ok.status_code == 200, ok.text
    s = snapshot()
    assert s["readiness"]["state"] == "PREPARATION_CONFIRMED" and s["case"]["bank_stage"] == stage
    assert any(d["action"] == "CONFIRM_PREPARATION" for d in repo.decisions(CASE))
    assert add


# ---------------------------------------------------------------- finding decisions: explicit, justified, audited
def finding_item(code: str = "DECLARED_VS_DOCUMENT_INCOME_VARIANCE") -> dict:
    return next(i for i in workspace()["items"] if i["kind"] == "case_finding" and i["finding"]["code"] == code
                and i["finding"]["status"] == "open")


def rule(fid: str, action: str, **body):
    return client.post(f"/api/banker/cases/{CASE}/findings/{fid}/decision", json={"action": action, **body}, headers=DANA)


def noa_september_only() -> str:
    add_doc("BRW-B", "2026-09", 16900, "noa_payslip_2026-09.pdf")
    case_run()
    return finding_item()["finding"]["finding_id"]


def test_one_month_is_shown_as_a_preliminary_comparison_and_a_resolution_must_say_so():
    fid = noa_september_only()
    f = repo.finding(fid)
    assert "השוואה ראשונית על בסיס 1 מתוך 3" in f["message_he"] and "ממוצע" not in f["message_he"]
    assert "חסרים עדיין: יולי 2026, אוגוסט 2026" in f["message_he"]
    it = finding_item()
    assert it["basis"]["partial"] and it["months_to_request"] == ["2026-07", "2026-08"]
    assert it["recommendation"]["action"] == "request_missing" and not it["has_customer_statement"]
    assert it["allowed_actions"] == ["request_missing", "request_explanation", "resolve", "dismiss", "escalate"]
    assert it["income"]["summary_he"].startswith("השוואה ראשונית על בסיס 1 מתוך 3 חודשים: בתלוש ספטמבר 2026 הנטו נמוך ב־1,600 ₪")
    assert it["income"]["documented_label_he"] == "בתלוש ספטמבר 2026"
    assert it["drafts"]["missing"]["message_he"].endswith("חסרים תלושי השכר של יולי ואוגוסט 2026. נא להעלות אותם באפליקציה.")
    long = "הכנסה משתנה מוכרת לפי מדיניות; מאושר בהחלטה מקצועית"
    assert rule(fid, "resolve", reason_code="explanation_supported", rationale=long).status_code in (409, 422)
    assert rule(fid, "resolve", reason_code="verified_with_documents", rationale=long).status_code == 422     # no documents
    assert rule(fid, "resolve", reason_code="professional_judgment", rationale="ok").status_code == 422       # too thin
    partial = rule(fid, "resolve", reason_code="professional_judgment", rationale=long)
    assert partial.status_code == 409 and "בסיס חלקי" in partial.json()["detail"]
    assert rule(fid, "resolve").status_code == 422                                                             # no basis chosen
    assert repo.finding(fid)["status"] == "open"
    override = rule(fid, "resolve", reason_code="professional_judgment", rationale=long, acknowledge_partial=True)
    assert override.status_code == 200 and override.json()["decision"]["reason_code"] == "professional_judgment"
    assert repo.finding(fid)["resolution"] == "resolved_by_banker"


def test_an_explanation_request_is_answered_in_the_app_and_never_closes_the_finding_by_itself():
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-B", m, 16900, f"noa_{m}.pdf")
    case_run()
    it = finding_item()
    fid = it["finding"]["finding_id"]
    assert not it["basis"]["partial"] and it["recommendation"]["action"] == "request_explanation"
    msg = it["drafts"]["explanation"]["message_he"]
    assert "18,500" in msg and "16,900" in msg
    r = rule(fid, "request_explanation", customer_message=msg, request_id="exp-1")
    assert r.status_code == 200 and r.json()["customer_request"]["kind"] == "explanation"
    assert rule(fid, "request_explanation", customer_message=msg, request_id="exp-2").status_code == 409
    q = next(x for x in snapshot()["customer_requests"] if x["kind"] == "explanation")
    assert q["status"] == "OPEN" and q["can_reply"] and snapshot()["readiness"]["counts"]["customer_requests"] == 1
    url = f"/api/cases/{CASE}/customer-requests/{q['customer_request_id']}/reply"
    assert client.post(url, json={"text": " "}).status_code == 422
    answer = "חלק מהשכר שלי הוא עמלות שמשתנות מחודש לחודש."
    assert client.post(url, json={"text": answer}).status_code == 200
    assert client.post(url, json={"text": answer}).status_code == 409
    q = next(x for x in snapshot()["customer_requests"] if x["customer_request_id"] == q["customer_request_id"])
    assert q["status"] == "RESPONDED" and q["responded_text"] == answer
    it = finding_item()
    assert it["has_customer_statement"] and it["finding"]["statements"][0]["text"] == answer
    assert it["recommendation"]["title_he"] == "הלקוח מסר הסבר — לא מאומת" and repo.finding(fid)["status"] == "open"
    docs = [o["document_id"] for o in it["evidence_options"]]
    assert rule(fid, "resolve", reason_code="explanation_supported", rationale="ההסבר נבדק").status_code == 422   # no support
    ok = rule(fid, "resolve", reason_code="explanation_supported", evidence_document_ids=docs,
              rationale="שלושת התלושים מראים רכיב עמלות משתנה; ההכנסה המתועדת תשמש לחישוב")
    assert ok.status_code == 200
    d = ok.json()["decision"]
    assert d["reason_code"] == "explanation_supported" and {e["document_id"] for e in d["evidence_refs"]} >= set(docs)
    case_run()
    assert repo.finding(fid)["status"] == "resolved" and not [f for f in repo.findings(CASE, "open")
                                                             if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"]


def test_an_explanation_given_in_chat_or_mcp_answers_the_same_request():
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-B", m, 16900, f"noa_{m}.pdf")
    case_run()
    fid = finding_item()["finding"]["finding_id"]
    rule(fid, "request_explanation", customer_message="נא להסביר את הפער")
    items = tools.call("list_open_items", CASE, {"audience": "customer"}, {"channel": "text"})
    assert items["banker_requests"][0]["finding_id"] == fid and "הבנקאית ביקשה" in items["spoken_he"]
    out = tools.call("record_customer_statement", CASE, {"finding_id": fid, "statement": "יש לי רכיב בונוס משתנה",
                                                         "customer_confirmed": True}, {"channel": "voice", "turn_id": "T-9"})
    assert out["answers_banker_request"]
    overview = tools.call("get_case_overview", CASE, {}, {"channel": "mcp"})
    assert overview["counts"] == snapshot()["readiness"]["counts"] and overview["counts"]["customer_requests"] == 0
    assert repo.finding(fid)["status"] == "open"


def test_missing_months_from_the_finding_then_the_full_comparison_links_back_to_the_earlier_ruling():
    fid = noa_september_only()
    for m in ("2026-07", "2026-08"):
        r = client.post(f"/api/banker/cases/{CASE}/missing-requests", headers=DANA,
                        json={"borrower_id": "BRW-B", "period": m, "customer_message": "נא להעלות"})
        assert r.status_code == 200
    assert finding_item()["recommendation"]["title_he"] == "ממתינים למסמכים מהלקוח"
    rule(fid, "resolve", reason_code="professional_judgment", acknowledge_partial=True,
         rationale="החלטה זמנית על בסיס חודש אחד בלבד, לפי הנחיית מנהל")
    uploaded = {}
    for m, name in (("2026-07", "noa_payslip_2026-07_scan.pdf"), ("2026-08", "noa_payslip_2026-08.pdf")):
        with (FIX / name).open("rb") as fh:
            up = client.post(f"/api/cases/{CASE}/documents", data={"borrower_id": "BRW-B", "expected_period": m},
                             files={"file": (name, fh, "application/pdf")})
        assert up.json()["answered_request"], m                            # the open request for that month
        uploaded[m] = up.json()["document"]["document_id"]
    for m, did in uploaded.items():
        finish_review(did, review(did, "BRW-B", m, 16900))
    case_run()
    it = finding_item()
    assert it["finding"]["finding_id"] != fid and it["reopened_after"]["finding_id"] == fid
    assert not it["basis"]["partial"] and "על בסיס כל 3 החודשים" in it["finding"]["message_he"]
    assert repo.finding(fid)["status"] == "resolved"                       # the earlier ruling is kept, not rewritten
    docs = [o["document_id"] for o in it["evidence_options"]]
    ok = rule(it["finding"]["finding_id"], "resolve", reason_code="verified_with_documents", evidence_document_ids=docs,
              rationale="הנטו המתועד בשלושת התלושים ישמש לחישוב ההחזר")
    assert ok.status_code == 200
    case_run()
    case_run()
    assert not [f for f in repo.findings(CASE, "open") if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"]


def test_escalation_withdrawal_and_resolution_close_requests_only_through_audited_steps():
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-B", m, 16900, f"noa_{m}.pdf")
    case_run()
    fid = finding_item()["finding"]["finding_id"]
    assert rule(fid, "escalate").status_code == 422
    assert rule(fid, "escalate", rationale="לבדוק מול מחלקת חיתום").status_code == 200
    assert group_of(workspace(), f"finding:{fid}") == "escalated"
    assert rule(fid, "escalate", rationale="שוב").status_code == 409
    rule(fid, "request_explanation", customer_message="נא להסביר")
    q = next(x for x in repo.customer_requests(CASE, "OPEN") if x["finding_id"] == fid)
    url = f"/api/banker/cases/{CASE}/customer-requests/{q['customer_request_id']}/withdraw"
    assert client.post(url, json={"rationale": ""}, headers=DANA).status_code == 422
    assert anon.post(url, json={"rationale": "נשלחה בטעות"}).status_code == 401
    assert client.post(url, json={"rationale": "נשלחה בטעות"}, headers=DANA).status_code == 200
    assert client.post(url, json={"rationale": "נשלחה בטעות"}, headers=DANA).status_code == 409
    assert repo.customer_request(q["customer_request_id"])["status"] == "CLOSED"
    assert not [x for x in snapshot()["customer_requests"] if x["customer_request_id"] == q["customer_request_id"]]
    rule(fid, "request_explanation", customer_message="נא להסביר שוב")
    q2 = next(x for x in repo.customer_requests(CASE, "OPEN") if x["finding_id"] == fid)
    impact = finding_item()["impact"]
    assert any("תיסגר ותרד מהאפליקציה" in line for line in impact["resolve"])
    rule(fid, "resolve", reason_code="professional_judgment", rationale="הוכרע בוועדת אשראי; ההסבר אינו נדרש עוד")
    closed = repo.customer_request(q2["customer_request_id"])
    assert closed["status"] == "CLOSED" and closed["closed_reason"] == "RESOLVE_FINDING"
    actions = [e["action"] for e in repo.audit_events(CASE)]
    assert "banker_request_withdrawn" in actions and actions.count("banker_finding_decision") >= 4


def test_an_ai_false_positive_is_dismissed_with_a_reason_and_stays_dismissed():
    doc = add_doc("BRW-B", "2026-07", 18400, verdict="NEEDS_REVIEW", PS_10="NEEDS_REVIEW")
    case_run()
    pay_date = next(f for f in repo.findings(CASE, "open") if f["document_id"] == doc and f["code"] == "PAY_DATE_INCONSISTENT")
    assert rule(pay_date["finding_id"], "dismiss", reason_code="rule_not_applicable", rationale="קצר").status_code == 422
    r = rule(pay_date["finding_id"], "dismiss", reason_code="rule_not_applicable",
             rationale="התאריך המודפס הוא תאריך הפקה ולא תאריך תשלום; הכלל אינו חל")
    assert r.status_code == 200 and r.json()["decision"]["reason_he"] == "הכלל אינו חל על המקרה"
    case_run()
    case_run()
    assert repo.finding(pay_date["finding_id"])["status"] == "dismissed"
    assert not [f for f in repo.findings(CASE, "open") if f["key"] == pay_date["key"]]
    event = next(e for e in repo.audit_events(CASE) if e["action"] == "banker_finding_decision")
    assert event["detail"]["reason_code"] == "rule_not_applicable" and event["actor"] == "banker:STAFF-DANA"
