"""Offline tests of the assistant → app action contract and the after-upload wording (no DB, no model calls)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent import actions, continuation
from app.agent.agent import _contents

CASE = {"case_id": "C-1", "banker": {"name_he": "דנה כהן"},
        "borrowers": [{"borrower_id": "BRW-A", "first_name_he": "עידו"}, {"borrower_id": "BRW-B", "first_name_he": "נועה"}]}
REQUESTED = ["2026-07", "2026-08", "2026-09"]
NAMES = {"BRW-A": "עידו", "BRW-B": "נועה"}


def req(bid: str, missing=(), requested=(), state: str = "required_missing") -> dict:
    return {"code": f"PAYSLIPS:{bid}", "evaluated_by_ai": True, "borrower_id": bid, "ai_state": state,
            "requested_months": list(requested), "missing": list(missing)}


def state(*reqs: dict, pending=()) -> dict:
    return {"requirements": [*reqs, {"code": "APPRAISAL", "evaluated_by_ai": False, "borrower_id": None}],
            "pending_jobs": list(pending)}


def finding(fid: str, bid: str, review_state: str, document_id=None, period=None, title: str = "ממצא") -> dict:
    return {"finding_id": fid, "borrower_id": bid, "review_state": review_state, "document_id": document_id,
            "period": period, "title_he": title, "detail": {}}


def doc(document_id: str, bid: str, status: str = "reviewed", filename: str = "ido.pdf") -> dict:
    return {"document_id": document_id, "borrower_id": bid, "status": status, "filename": filename}


def test_fresh_case_offers_one_upload_per_borrower_with_every_month_open():
    acts = actions.derive(CASE, state(req("BRW-A"), req("BRW-B")), [], [], [], REQUESTED)
    uploads = [a for a in acts if a.type == "NAVIGATE_TO_DOCUMENT_UPLOAD"]
    assert [a.label_he for a in uploads] == ["העלאת תלושים לעידו", "העלאת תלושים לנועה"]
    assert all(a.params["missing_periods"] == REQUESTED and a.params["period"] is None for a in uploads)
    assert uploads[1].params["borrower_id"] == "BRW-B" and uploads[1].params["requirement_code"] == "PAYSLIPS:BRW-B"
    assert uploads[1].params["document_type"] == "PAYSLIP" and uploads[1].case_id == "C-1"
    assert [a.action_id for a in acts] == ["upload:PAYSLIPS:BRW-A", "upload:PAYSLIPS:BRW-B", "documents:missing", "case:details"]


def test_a_single_missing_month_is_preselected_and_complete_borrowers_get_no_upload():
    st = state(req("BRW-A", ["2026-09"], REQUESTED, "needs_customer_action"), req("BRW-B", [], REQUESTED, "extracted"))
    acts = actions.derive(CASE, st, [finding("F-1", "BRW-A", "CUSTOMER_ACTION_REQUIRED", period="2026-09")], [], [], REQUESTED)
    first = acts[0]
    assert (first.label_he, first.detail_he, first.params["period"]) == ("העלאת תלוש ספטמבר לעידו", "חסר תלוש ספטמבר 2026", "2026-09")
    assert first.params["finding_ids"] == ["F-1"]
    assert "upload:PAYSLIPS:BRW-B" not in [a.action_id for a in acts]


def test_several_missing_months_are_listed_without_choosing_one():
    acts = actions.derive(CASE, state(req("BRW-B", ["2026-07", "2026-09"], REQUESTED, "needs_customer_action")), [], [], [], REQUESTED)
    assert acts[0].params["period"] is None and acts[0].detail_he == "חסרים: יולי וספטמבר 2026"


def test_document_findings_banker_handoff_and_priority_order():
    st = state(req("BRW-A", ["2026-09"], REQUESTED, "needs_customer_action"), req("BRW-B", [], REQUESTED, "needs_banker_review"))
    found = [finding("F-1", "BRW-A", "CUSTOMER_ACTION_REQUIRED", period="2026-09", title="חסר תלוש"),
             finding("F-2", "BRW-A", "INFO", document_id="DOC-1", title="שם הקובץ אינו תואם"),
             finding("F-3", "BRW-B", "NEEDS_BANKER_REVIEW", title="פער בהכנסה")]
    acts = actions.derive(CASE, st, found, [doc("DOC-1", "BRW-A")], [], REQUESTED)
    assert [a.action_id for a in acts] == ["upload:PAYSLIPS:BRW-A", "review:DOC-1", "documents:missing", "banker:handoff", "case:details"]
    assert acts[1].params == {"document_id": "DOC-1", "finding_ids": ["F-2"]} and "ido.pdf" in acts[1].detail_he
    assert acts[3].params["message_he"].startswith("אני מאשר/ת להעביר את התיק") and acts[3].params["finding_ids"] == ["F-3"]
    queued = [{"status": "IN_BANKER_QUEUE_DEMO", "banker_decision": None}]
    assert "banker:handoff" not in [a.action_id for a in actions.derive(CASE, st, found, [doc("DOC-1", "BRW-A")], queued, REQUESTED)]


def test_documents_under_review_are_reported_honestly():
    acts = actions.derive(CASE, state(req("BRW-A"), req("BRW-B"), pending=[{"kind": "review_document"}]), [],
                          [doc("DOC-1", "BRW-A", "processing")], [], REQUESTED)
    assert acts[0].detail_he.endswith("מסמך אחד בבדיקה")
    assert "documents:status" in [a.action_id for a in acts]


def test_the_model_cannot_invent_or_duplicate_actions():
    available = actions.derive(CASE, state(req("BRW-A"), req("BRW-B")), [], [], [], REQUESTED)
    chosen, rejected = actions.choose(available, ["documents:missing", "upload:PAYSLIPS:BRW-Z", "upload:PAYSLIPS:BRW-B",
                                                  "documents:missing", "route:/banker"])
    assert [a.action_id for a in chosen] == ["upload:PAYSLIPS:BRW-B", "documents:missing"]
    assert rejected == ["upload:PAYSLIPS:BRW-Z", "route:/banker"]


def test_the_contract_rejects_unknown_types_and_malformed_params():
    with pytest.raises(ValidationError):
        actions.AppAction(action_id="x", type="NAVIGATE_TO_DOCUMENT_UPLOAD", case_id="C", label_he="x", priority=1,
                          params={"borrower_id": "BRW-A", "requirement_code": "R", "document_type": "SELFIE"})
    with pytest.raises(ValidationError):
        actions.AppAction(action_id="x", type="VIEW_CASE_DETAILS", case_id="C", label_he="x", priority=1, params={"route": "/banker"})
    with pytest.raises(ValidationError):
        actions.AppAction(action_id="x", type="OPEN_URL", case_id="C", label_he="x", priority=1)


def test_merge_keeps_backend_priority_and_caps_the_offer():
    offered = [{"action_id": f"a{i}", "priority": p} for i, p in enumerate([50, 10, 90, 20, 35])]
    assert [a["action_id"] for a in actions.merge(offered[:2], offered[1:])] == ["a1", "a3", "a4", "a0"]


def test_hebrew_month_lists():
    assert actions.months_he(["2026-07", "2026-08", "2026-09"]) == "יולי, אוגוסט וספטמבר 2026"
    assert actions.months_he(["2026-09"]) == "ספטמבר 2026"
    assert actions.months_he(["2025-12", "2026-01"]) == "דצמבר 2025 וינואר 2026"


def test_history_alternates_and_opens_with_the_customer():
    history = [{"role": "assistant", "text": "a"}, {"role": "user", "text": "q1"}, {"role": "assistant", "text": "r1"},
               {"role": "assistant", "text": "app note"}]
    contents = _contents(history, "q2", "text")
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert [p["text"] for p in contents[1]["parts"]] == ["r1", "app note"]


def test_after_upload_wording_comes_from_review_results():
    noa = doc("DOC-1", "BRW-B", filename="noa.pdf")
    valid = {"doc_type": "payslip", "period": "2026-09", "verdict": "VALID", "matched_borrower_id": "BRW-B"}
    assert continuation._document_sentence(noa, valid, {"created_new": 1}, [], NAMES) == "התלוש של נועה לספטמבר 2026 התקבל ונבדק — נמצא תקין."
    ido = doc("DOC-2", "BRW-A", filename="ido_payslip_2026-09.pdf")
    august = {**valid, "period": "2026-08", "file_name_period": "2026-09", "matched_borrower_id": "BRW-A"}
    assert continuation._document_sentence(ido, august, {"expected_period": "2026-09"}, [], NAMES) == \
        "התלוש של עידו התקבל ונבדק: מודפס בו אוגוסט 2026, ולא ספטמבר 2026 כפי שבחרתם."
    wrong_person = {**valid, "matched_borrower_id": "BRW-A"}
    mismatch = finding("F-9", "BRW-B", "CUSTOMER_ACTION_REQUIRED", document_id="DOC-1", title="המסמך אינו של נועה")
    mismatch["message_he"] = "המסמך noa.pdf הועלה עבור נועה, אך הוא של עידו."
    assert continuation._document_sentence(noa, wrong_person, {}, [mismatch], NAMES).startswith(
        "המסמך שהועלה עבור נועה לספטמבר 2026 התקבל ונבדק, ונדרש תיקון:")
    assert "נבדק" not in continuation._document_sentence({**noa, "status": "failed"}, None, {}, [], NAMES)
    open_state = {"requirements": [{"evaluated_by_ai": True, "borrower_id": "BRW-A", "missing": ["2026-09"]},
                                   {"evaluated_by_ai": True, "borrower_id": "BRW-B", "missing": []}]}
    assert continuation._remaining_sentence(open_state, NAMES, []) == "נותר להעלות את תלוש ספטמבר 2026 של עידו."
