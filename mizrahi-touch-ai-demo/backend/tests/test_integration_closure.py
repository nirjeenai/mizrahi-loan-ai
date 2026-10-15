"""Regression tests for the customer ↔ banker QA findings G-01 … G-13 (QA audit 2026-10-13), through the real routes.
Gemini is never called: reviews are stored results shaped like the provider's (helpers from test_review_desk)."""
from __future__ import annotations

import dataclasses
import json

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.agent import tools
from app.api import routes
from app.main import app
from app.store import repo
from app.util import new_id, now_iso
from tests.test_review_desk import (CASE, DANA, FIX, ORI, OTHER, add_doc, anon, bearer, case_run, client, decide, finish_review,  # noqa: F401
                              fresh, ido_set, item, review, snapshot, workspace)

pytestmark = pytest.mark.usefixtures("payslip_scope")    # the payslip workflow on its own (see conftest)
ORI_CASE = "DEMO-MTZ-2026-002"
LEVI = "DEMO-MTZ-2026-004"


def customer_client(cases: list[str]) -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIES["customer"], auth.issue("customer", cases))
    return c


def variance_set() -> str:
    """All six months present; Noa's payslips (₪16,900) are 8.6% below her declared ₪18,500 → a banker finding."""
    for m, net in (("2026-07", 13200), ("2026-08", 13500), ("2026-09", 13500)):
        add_doc("BRW-A", m, net, f"ido_{m}.pdf")
        add_doc("BRW-B", m, 16900, f"noa_{m}.pdf")
    case_run()
    return next(f["finding_id"] for f in repo.findings(CASE, "open") if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE")


def upload(c: TestClient, case: str, borrower: str, name: str, **data):
    with (FIX / name).open("rb") as fh:
        return c.post(f"/api/cases/{case}/documents", data={"borrower_id": borrower, **data},
                      files={"file": (name, fh, "application/pdf")})


# ---------------------------------------------------------------- G-01 customer identity and case isolation
def test_demo_session_is_bound_to_the_picked_case_and_extended_per_case():
    c = TestClient(app)
    denied = c.get(f"/api/cases/{CASE}")
    assert denied.status_code == 401 and denied.headers[auth.AUTH_HEADER] == "customer"   # no session, no data
    r = c.post("/api/session/demo/customer", json={"case_id": CASE})
    cookie = r.headers["set-cookie"]
    assert r.status_code == 200 and cookie.startswith(f"{auth.COOKIES['customer']}=") and "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert [x["case_id"] for x in c.get("/api/session").json()["customer"]["cases"]] == [CASE]
    assert c.get(f"/api/cases/{CASE}").status_code == 200
    assert c.get(f"/api/cases/{ORI_CASE}").status_code == 403                     # another case needs its own pick
    c.post("/api/session/demo/customer", json={"case_id": ORI_CASE})
    assert {x["case_id"] for x in c.get("/api/session").json()["customer"]["cases"]} == {CASE, ORI_CASE}
    assert c.get(f"/api/banker/cases/{CASE}/workspace").status_code == 401        # a customer session is never staff
    assert c.post("/api/session/demo/customer", json={"case_id": "NOPE"}).status_code == 404
    assert {CASE, OTHER, ORI_CASE} <= {x["case_id"] for x in c.get("/api/session/demo/cases").json()}
    assert "borrowers" not in json.dumps(c.get("/api/session/demo/cases").json())   # the selector list carries no case data
    c.post("/api/session/logout", json={"role": "customer"})
    assert c.get(f"/api/cases/{CASE}").status_code == 401


def test_demo_sessions_can_be_switched_off(monkeypatch):
    from app import auth as auth_module
    monkeypatch.setattr(auth_module, "settings", dataclasses.replace(auth_module.settings, demo_identity=False))
    c = TestClient(app)
    assert c.post("/api/session/demo/customer", json={"case_id": CASE}).status_code == 404
    assert c.post("/api/session/demo/staff", json={}).status_code == 404
    assert c.get("/api/session/demo/cases").status_code == 404
    assert c.get(f"/api/cases/{CASE}").status_code == 401 and c.get(f"/api/banker/cases/{CASE}/workspace").status_code == 401
    assert c.get("/api/session").json()["demo_identity"] is False


def test_a_customer_reaches_only_their_own_cases():
    lavi = customer_client([CASE, OTHER])
    assert [x["case_id"] for x in lavi.get("/api/cases").json()] == [CASE, OTHER]
    assert lavi.get(f"/api/cases/{CASE}").status_code == 200
    for path in (f"/api/cases/{ORI_CASE}", f"/api/cases/{ORI_CASE}/documents", f"/api/cases/{LEVI}/conversation"):
        assert lavi.get(path).status_code == 403, path
    assert upload(lavi, ORI_CASE, "BRW-C", "ido_payslip_2026-07.pdf").status_code == 403
    assert not repo.documents(ORI_CASE)
    for path in (f"/api/cases/{CASE}", f"/api/cases/{CASE}/documents", f"/api/cases/{CASE}/conversation", "/api/cases"):
        assert anon.get(path).status_code == 401, path
    assert anon.post(f"/api/cases/{CASE}/agent/messages", json={"text": "hi"}).status_code == 401
    assert anon.post(f"/api/cases/{CASE}/actions/resolve", json={"action_id": "x"}).status_code == 401
    assert upload(anon, CASE, "BRW-A", "ido_payslip_2026-07.pdf").status_code == 401


def test_documents_and_originals_are_bound_to_the_case():
    mine = add_doc("BRW-A", "2026-07", 13200)
    theirs = add_doc("BRW-A", "2026-07", 13200, case=LEVI)
    lavi = customer_client([CASE, OTHER])
    assert lavi.get(f"/api/documents/{mine}").status_code == 200
    assert lavi.get(f"/api/documents/{mine}/file").status_code == 200
    for path in (f"/api/documents/{theirs}", f"/api/documents/{theirs}/file", f"/api/documents/{theirs}/pages/1.png"):
        assert lavi.get(path).status_code == 403, path
        assert anon.get(path).status_code == 401, path
    assert anon.get("/api/documents/DOC-NOPE").status_code == 401                 # nothing revealed without a session
    staff = TestClient(app, headers=DANA)
    assert staff.get(f"/api/documents/{theirs}/pages/1.png").status_code == 200   # bank staff read evidence


def test_sessions_expire_and_cannot_be_forged_or_reused_across_roles():
    expired = auth.issue("customer", [CASE], ttl_minutes=0)
    assert anon.get(f"/api/cases/{CASE}", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    good = auth.issue("customer", [CASE])
    body, sig = good.split(".")
    forged = auth._b64(json.dumps({"r": "customer", "s": [ORI_CASE], "iat": 0, "exp": 9999999999, "n": "x"}).encode())
    assert anon.get(f"/api/cases/{ORI_CASE}", headers={"Authorization": f"Bearer {forged}.{sig}"}).status_code == 401
    as_staff = auth.issue("customer", ["STAFF-DANA"])
    assert anon.get(f"/api/banker/cases/{CASE}/workspace", headers={"Authorization": f"Bearer {as_staff}"}).status_code == 401


# ---------------------------------------------------------------- G-02 banker identity comes from a session
def test_banker_identity_cannot_be_claimed_with_a_header():
    docs = ido_set()
    url = f"/api/banker/cases/{CASE}/documents/{docs['ido07']}/decision"
    spoof = TestClient(app, headers={"X-Staff-Id": "STAFF-DANA"})
    spoof.cookies.set(auth.COOKIES["customer"], auth.issue("customer", [CASE]))   # even with a customer session
    assert spoof.post(url, json={"action": "accept"}).status_code == 401
    assert spoof.post(f"/api/banker/cases/{CASE}/confirm-preparation", json={}).status_code == 401
    assert spoof.post(f"/api/banker/cases/{CASE}/notes", json={"text": "x"}).status_code == 401
    c = TestClient(app)
    assert c.post("/api/session/demo/staff", json={"staff_id": "STAFF-NOBODY"}).status_code == 404
    assert c.post("/api/session/demo/staff", json={}).json()["staff"]["staff_id"] == "STAFF-DANA"   # the demo banker
    assert c.post(url, json={"action": "accept", "acknowledged_finding_ids": []}).status_code == 200
    assert repo.decisions(CASE)[-1]["actor_id"] == "STAFF-DANA"
    ori = TestClient(app, headers=ORI)
    assert ori.get(f"/api/banker/cases/{CASE}/workspace").status_code == 200       # other staff may read (console read-only)
    assert ori.post(f"/api/banker/cases/{CASE}/notes", json={"text": "x"}).status_code == 403


# ---------------------------------------------------------------- G-03 internal data stays inside the bank
def test_internal_reasons_and_notes_never_reach_customer_endpoints():
    docs = ido_set()
    secret = "INTERNAL-ONLY-7731"
    assert client.post(f"/api/banker/cases/{CASE}/notes", json={"text": secret, "document_id": docs["ido07"]}, headers=DANA).status_code == 200
    decide(docs["ido09"], "request_correction", customer_message="נא להעלות את תלוש ספטמבר", rationale=secret, requested_period="2026-09")
    lavi = customer_client([CASE, OTHER])
    for path in (f"/api/cases/{CASE}/audit", f"/api/cases/{CASE}/findings", f"/api/cases/{CASE}/runs"):
        assert lavi.get(path).status_code == 401, path
        assert anon.get(path).status_code == 401, path
    run_id = repo.runs(CASE)[0]["run_id"]
    assert lavi.get(f"/api/runs/{run_id}").status_code == 401
    for path in ("/api/banker/cases", f"/api/banker/cases/{CASE}/workspace", f"/api/banker/cases/{CASE}/package",
                 f"/api/banker/cases/{CASE}/conversation"):
        assert lavi.get(path).status_code == 401, path
        assert anon.get(path).status_code == 401, path
    assert secret in client.get(f"/api/cases/{CASE}/audit", headers=DANA).text        # staff still see everything
    raw = json.dumps(lavi.get(f"/api/cases/{CASE}").json(), ensure_ascii=False)
    raw += json.dumps(lavi.get(f"/api/documents/{docs['ido09']}").json(), ensure_ascii=False)
    assert secret not in raw
    assert anon.post("/api/system/mcp-selftest").status_code == 401


def test_customer_views_of_handoffs_confirmations_and_history_are_projected():
    fid = variance_set()
    tools.call("request_banker_handoff", CASE, {"customer_confirmed": True, "note": "please call"}, {"channel": "text", "turn_id": "t1"})
    r = client.post(f"/api/banker/cases/{CASE}/findings/{fid}/decision", headers=DANA,
                    json={"action": "escalate", "rationale": "SECRET-ESCALATION-NOTE"})
    assert r.status_code == 200
    r = client.post(f"/api/banker/cases/{CASE}/confirm-preparation", headers=DANA, json={"note": "SECRET-CONFIRM-NOTE"})
    assert r.status_code == 200, r.text
    s = snapshot()
    raw = json.dumps(s, ensure_ascii=False)
    assert "SECRET-CONFIRM-NOTE" not in raw and "SECRET-ESCALATION-NOTE" not in raw
    assert all(set(h) <= {"package_id", "status", "created_at", "channel", "banker_decision", "decided_at"} for h in s["handoffs"])
    assert s["readiness"]["banker_confirmation"] and "note" not in s["readiness"]["banker_confirmation"]
    explained = tools.call("explain_finding", CASE, {"finding_id": fid}, {"channel": "text"})
    assert "SECRET-ESCALATION-NOTE" not in json.dumps(explained, ensure_ascii=False)


# ---------------------------------------------------------------- G-11 cost and destructive controls
def test_retry_only_for_a_failed_document_of_your_own_case():
    ok = add_doc("BRW-A", "2026-07", 13200)
    failed = add_doc("BRW-A", "2026-08", 13500)
    repo.set_document(failed, status="failed", stage="failed", error="x")
    theirs = add_doc("BRW-A", "2026-07", 13200, case=LEVI)
    repo.set_document(theirs, status="failed", stage="failed", error="x")
    lavi = customer_client([CASE, OTHER])
    assert anon.post(f"/api/documents/{failed}/retry").status_code == 401
    assert lavi.post(f"/api/documents/{theirs}/retry").status_code == 403
    assert lavi.post(f"/api/documents/{ok}/retry").status_code == 409
    assert lavi.post(f"/api/documents/{failed}/retry").status_code == 200
    assert repo.document(failed)["status"] == "queued"


def test_demo_reset_is_scoped_to_your_case_and_can_be_switched_off(monkeypatch):
    add_doc("BRW-A", "2026-07", 13200, case=LEVI)
    lavi = customer_client([CASE, OTHER])
    assert anon.post(f"/api/cases/{LEVI}/reset").status_code == 401
    assert lavi.post(f"/api/cases/{LEVI}/reset").status_code == 403
    assert TestClient(app, headers=ORI).post(f"/api/cases/{LEVI}/reset").status_code == 403    # not Ori's case
    assert repo.documents(LEVI)
    monkeypatch.setattr(routes, "settings", dataclasses.replace(routes.settings, demo_reset=False))
    assert customer_client([LEVI]).post(f"/api/cases/{LEVI}/reset").status_code == 403
    monkeypatch.undo()
    assert customer_client([LEVI]).post(f"/api/cases/{LEVI}/reset").status_code == 200
    assert not repo.documents(LEVI)


# ---------------------------------------------------------------- G-04 a confirmation lapses when the case changes
def _confirmable() -> dict:
    docs = ido_set(mislabeled=False)
    docs["ido09"] = add_doc("BRW-A", "2026-09", 13500, "ido_payslip_2026-09.pdf")
    case_run()
    r = client.post(f"/api/banker/cases/{CASE}/confirm-preparation", headers=DANA, json={"note": "", "request_id": "c-1"})
    assert r.status_code == 200, r.text
    assert snapshot()["readiness"]["state"] == "PREPARATION_CONFIRMED"
    return docs


def test_a_new_upload_after_confirmation_needs_a_new_confirmation():
    _confirmable()
    late = add_doc("BRW-B", "2026-09", 18400, "noa_resend.pdf")
    case_run()
    s = snapshot()
    assert s["readiness"]["state"] != "PREPARATION_CONFIRMED" and s["readiness"]["customer_status"] != "PREPARATION_CONFIRMED"
    ws = workspace()
    assert ws["preparation"] is None and ws["preparation_stale"]["reason_he"] == "הועלה מסמך חדש אחרי האישור"
    assert ws["can_confirm"]["allowed"] is True
    again = client.post(f"/api/banker/cases/{CASE}/confirm-preparation", headers=DANA, json={"note": "", "request_id": "c-2"})
    assert again.status_code == 200 and again.json()["duplicate"] is False
    assert snapshot()["readiness"]["state"] == "PREPARATION_CONFIRMED"
    assert len([d for d in repo.decisions(CASE) if d["action"] == "CONFIRM_PREPARATION"]) == 2
    replay = client.post(f"/api/banker/cases/{CASE}/confirm-preparation", headers=DANA, json={"note": "", "request_id": "c-2"})
    assert replay.json()["duplicate"] is True and late


def test_reopening_after_confirmation_lapses_it_even_if_the_request_is_withdrawn():
    docs = _confirmable()
    r = decide(docs["noa08"], "request_correction", customer_message="נא להעלות שוב", request_id="re-1")
    rid = r.json()["customer_request"]["customer_request_id"]
    assert snapshot()["readiness"]["state"] == "ACTION_REQUIRED"
    client.post(f"/api/banker/cases/{CASE}/customer-requests/{rid}/withdraw", headers=DANA, json={"rationale": "נשלחה בטעות"})
    s = snapshot()
    assert s["readiness"]["state"] != "PREPARATION_CONFIRMED"
    assert workspace()["preparation_stale"]["reason_he"] == "נשלחה בקשה ללקוח אחרי האישור"


# ---------------------------------------------------------------- G-05 withdrawing a correction does not dead-end the document
def test_withdrawn_correction_returns_the_document_and_its_findings_to_the_banker():
    docs = ido_set()
    flagged = add_doc("BRW-B", "2026-09", 18400, "noa_paydate.pdf", verdict="NEEDS_REVIEW", PS_10="NEEDS_REVIEW")
    case_run()
    banker_findings = [f for f in repo.findings(CASE, "open") if f["document_id"] == flagged and f["review_state"] == "NEEDS_BANKER_REVIEW"]
    assert banker_findings
    r = decide(flagged, "request_correction", customer_message="נא להעלות תלוש עם תאריך תשלום", request_id="w-1")
    rid = r.json()["customer_request"]["customer_request_id"]
    assert all(repo.finding(f["finding_id"])["status"] == "superseded" for f in banker_findings)
    w = client.post(f"/api/banker/cases/{CASE}/customer-requests/{rid}/withdraw", headers=DANA, json={"rationale": "בדקתי טלפונית"})
    assert w.status_code == 200
    it = item(workspace(), f"doc:{flagged}")
    assert it["banker"]["status"] == "AWAITING_DECISION" and "accept" in it["banker"]["allowed_actions"]
    assert all(repo.finding(f["finding_id"])["status"] == "open" for f in banker_findings)
    assert flagged not in (snapshot().get("document_status") or {})                    # no 'correction requested' for the customer
    ack = sorted(f["finding_id"] for f in banker_findings)
    assert decide(flagged, "accept", acknowledged_finding_ids=ack, rationale="אומת מול המעסיק").status_code == 200
    assert docs


# ---------------------------------------------------------------- G-06 the customer's handoff reaches the banker
def test_customer_handoff_is_visible_to_the_banker_and_acknowledged():
    ido_set()
    out = tools.call("request_banker_handoff", CASE, {"customer_confirmed": True, "note": "אשמח לשיחה"}, {"channel": "voice", "turn_id": "t9"})
    ws = workspace()
    assert len(ws["handoffs"]) == 1 and ws["handoffs"][0]["package_id"] == out["package_id"]
    assert client.get("/api/banker/cases", headers=DANA).json()[0]["handoffs"] == 1
    url = f"/api/banker/cases/{CASE}/handoffs/{out['package_id']}/acknowledge"
    assert TestClient(app, headers=ORI).post(url, json={}).status_code == 403
    assert anon.post(url, json={}).status_code == 401
    r = client.post(url, headers=DANA, json={"note": "INTERNAL-ACK", "request_id": "ack-1"})
    assert r.status_code == 200 and r.json()["decision"]["action"] == "ACKNOWLEDGE_HANDOFF"
    assert client.post(url, headers=DANA, json={"request_id": "ack-1"}).json()["duplicate"] is True
    assert client.post(url, headers=DANA, json={"request_id": "ack-2"}).status_code == 409
    assert workspace()["handoffs"] == []
    s = snapshot()
    assert any(u["action"] == "banker_handoff_acknowledged" for u in s["updates"]) and "INTERNAL-ACK" not in json.dumps(s, ensure_ascii=False)
    again = tools.call("request_banker_handoff", CASE, {"customer_confirmed": True}, {"channel": "text", "turn_id": "t10"})
    assert again["package_id"] != out["package_id"]                                    # a new request opens a new handoff


# ---------------------------------------------------------------- G-07 no missing-month request while the AI is still reviewing
def test_missing_request_waits_for_the_review_in_progress():
    ido_set(mislabeled=False)
    ws = workspace()
    assert "request_missing" in item(ws, "missing:BRW-A:2026-09")["allowed_actions"]
    doc_id = new_id("DOC")
    repo.insert_document({"document_id": doc_id, "case_id": CASE, "borrower_id": "BRW-A", "requirement_code": "PAYSLIPS:BRW-A",
                          "filename": "ido_payslip_2026-09_corrected.pdf", "mime": "application/pdf", "sha256": new_id("SHA"),
                          "bytes": 1, "pages": 1, "text_layer_chars": 500, "storage_path": str(FIX / "ido_payslip_2026-09_corrected.pdf"),
                          "uploaded_at": now_iso(), "uploaded_by": "customer", "channel": "customer_app", "status": "queued", "stage": "queued"})
    from app.workflow import engine
    engine.enqueue("review_document", CASE, doc_id, f"review_document:{doc_id}:1")
    r = client.post(f"/api/banker/cases/{CASE}/missing-requests", headers=DANA,
                    json={"borrower_id": "BRW-A", "period": "2026-09", "customer_message": "חסר ספטמבר"})
    assert r.status_code == 409 and "עדיין בודק" in r.json()["detail"]
    assert item(workspace(), "missing:BRW-A:2026-09")["allowed_actions"] == []
    finish_review(doc_id, review(doc_id, "BRW-A", "2026-09", 13400))
    case_run()
    assert not [q for q in repo.customer_requests(CASE, "OPEN")]
    assert not [i for i in workspace()["items"] if i["kind"] == "missing"]


# ---------------------------------------------------------------- G-10 a replaced payslip no longer counts
def test_replaced_payslip_is_not_counted_as_a_duplicate():
    docs = ido_set()
    assert any(f["code"] == "DUPLICATE_PERIOD" for f in repo.findings(CASE, "open"))
    r = decide(docs["ido09"], "request_correction", customer_message="נא להעלות את ספטמבר", requested_period="2026-09")
    rid = r.json()["customer_request"]["customer_request_id"]
    up = upload(client, CASE, "BRW-A", "ido_payslip_2026-09_corrected.pdf", customer_request_id=rid, expected_period="2026-09")
    new = up.json()["document"]["document_id"]
    finish_review(new, review(new, "BRW-A", "2026-09", 13400))
    case_run()
    assert not any(f["code"] == "DUPLICATE_PERIOD" for f in repo.findings(CASE, "open"))
    ido = next(r for r in snapshot()["readiness"]["requirements"] if r.get("borrower_id") == "BRW-A")
    assert ido["duplicates"] == {} and ido["missing"] == [] and docs["ido09"] not in {
        d["document_id"] for d in repo.latest_case_result(CASE)["coverage"]["by_borrower"]["BRW-A"]["documents"]}


# ---------------------------------------------------------------- G-13 a decision and its audit row are one transaction
def test_decision_and_audit_are_written_atomically():
    docs = ido_set()
    row = {"decision_id": new_id("DEC"), "case_id": CASE, "target_kind": "document", "document_id": docs["ido07"], "finding_id": None,
           "borrower_id": "BRW-A", "period": None, "action": "NOTE", "previous_status": None, "new_status": None, "rationale": "x",
           "customer_message": None, "customer_request_id": None, "finding_ids": [], "evidence_refs": [], "actor_id": "STAFF-DANA",
           "actor_name": "דנה כהן", "created_at": now_iso(), "request_id": new_id("REQ"), "reason_code": None}
    with pytest.raises(KeyError):
        repo.insert_decision(row, audit_row={"case_id": CASE, "actor": "banker:STAFF-DANA", "action": "banker_note"})   # no target
    assert repo.decision_by_request(row["request_id"]) is None                          # rolled back with its audit row
    r = client.post(f"/api/banker/cases/{CASE}/notes", headers=DANA, json={"text": "פנימי", "request_id": "n-1"})
    dec = r.json()["decision"]
    ev = [e for e in client.get(f"/api/cases/{CASE}/audit", headers=DANA).json() if (e["detail"] or {}).get("decision_id") == dec["decision_id"]]
    assert len(ev) == 1 and ev[0]["at"] == dec["created_at"]


def test_mcp_tool_history_matches_the_customer_projection():
    fid = variance_set()
    client.post(f"/api/banker/cases/{CASE}/findings/{fid}/decision", headers=DANA, json={"action": "escalate", "rationale": "SECRET-X"})
    hist = tools.call("explain_finding", CASE, {"finding_id": fid}, {"channel": "mcp"})["history"]
    snap_hist = next(f for f in snapshot()["findings"] if f["finding_id"] == fid)["history"]
    assert hist == snap_hist[-5:] and "SECRET-X" not in json.dumps(hist, ensure_ascii=False)
