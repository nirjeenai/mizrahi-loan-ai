"""Banker V3 "שאל את JEEN" in English: the console's language reaches the prompt as one appended instruction, the
answer says it is English, and a Hebrew (or header-less) call keeps the original contract byte for byte. The chat's
refusals and the code check's reasons have English in the staff catalogue. The model is replaced by a stub."""
from __future__ import annotations

import dataclasses

import pytest

from app import db
from app.api import banker_chat
from app.i18n import staff_en
from app.review import case_review
from app.store import repo
from tests.loan_helpers import client_for
from tests.test_banker_intelligence import COMPLETE, brief, package

staff = client_for()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    repo.reset_case(COMPLETE)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})
    yield


@pytest.fixture
def calls(monkeypatch) -> list[list[dict]]:
    sent: list[list[dict]] = []

    def call(contents, trace):
        sent.append(contents)
        return {"intent": "question", "answer_he": "The combined DSR is 14.1%.", "source_ids": ["calc:combined_dsr"],
                "revised_draft_he": "", "change_summary_he": ""}

    monkeypatch.setattr(banker_chat, "settings", dataclasses.replace(banker_chat.settings, gemini_api_key="test-key"))
    monkeypatch.setattr(banker_chat, "_call", call)
    package(COMPLETE)
    return sent


def _prompt(contents: list[dict]) -> str:
    return contents[-1]["parts"][-1]["text"]


def _draft() -> dict:
    d = next(x for x in brief(COMPLETE)["drafts"] if x["kind"] == "complete_documentation")
    return {"kind": d["kind"], "text": d["message_he"]}


def test_english_appends_the_language_instruction_and_marks_the_answer(calls):
    out = banker_chat.respond(COMPLETE, "Where does the ratio come from?", [], _draft(), "en")
    prompt = _prompt(calls[-1])
    assert prompt.endswith(banker_chat.ENGLISH) and "LANGUAGE:" in prompt
    assert out["lang"] == "en" and out["answer_he"] == "The combined DSR is 14.1%."


@pytest.mark.parametrize("lang", [None, "he"])
def test_hebrew_and_headerless_calls_keep_the_original_contract(calls, lang):
    out = banker_chat.respond(COMPLETE, "מאיפה הגיע יחס ההחזר?", [], _draft(), lang)
    assert "LANGUAGE:" not in _prompt(calls[-1]) and not _prompt(calls[-1]).endswith(banker_chat.ENGLISH)
    assert "lang" not in out
    assert set(out) == {"intent", "answer_he", "source_ids", "sources", "edit", "rejected_issues_he", "repaired", "model"}


def test_the_route_passes_the_console_language(calls):
    r = staff.post(f"/api/banker/cases/{COMPLETE}/chat", json={"message": "Why?", "history": [], "draft": None},
                   headers={"X-MZ-Lang": "en"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["lang"] == "en" and _prompt(calls[-1]).endswith(banker_chat.ENGLISH)
    assert out["sources"]["calc:combined_dsr"]["label_en"] == "Combined DSR"
    r = staff.post(f"/api/banker/cases/{COMPLETE}/chat", json={"message": "למה?", "history": [], "draft": None})
    assert r.status_code == 200 and "lang" not in r.json() and "label_en" not in r.json()["sources"]["calc:combined_dsr"]


def test_an_unavailable_chat_refuses_in_english_too(monkeypatch):
    monkeypatch.setattr(banker_chat, "settings", dataclasses.replace(banker_chat.settings, gemini_api_key=""))
    package(COMPLETE)
    body = {"message": "Why?", "history": [], "draft": None}
    en = staff.post(f"/api/banker/cases/{COMPLETE}/chat", json=body, headers={"X-MZ-Lang": "en"})
    assert en.status_code == 503
    assert en.json()["detail"].startswith("Jeen אינו זמין") and en.json()["detail_en"].startswith("Jeen isn't available")
    he = staff.post(f"/api/banker/cases/{COMPLETE}/chat", json=body)
    assert he.status_code == 503 and "detail_en" not in he.json()


def test_the_code_checks_reasons_have_english():
    intel = {"drafts": [], "loan": {}, "simulation": {}}
    current = "שלום,\nהודעה זו אינה אישור הלוואה ואינה התחייבות לתנאים."
    issues = banker_chat.check_revision("ההלוואה אושרה. יחס ההחזר שלך 12345 ש״ח. https://x.example", current, intel)
    assert issues
    for issue in issues:
        assert staff_en.translate(issue), issue
    assert staff_en.translate("לא עדכנתי את הטיוטה: " + " ".join(issues)).startswith("I didn't update the draft: ")
    for message in ("Jeen הגיע למכסת הקריאות לשעה זו. נסו שוב מאוחר יותר.",
                    "Jeen לא הצליח לענות כרגע. הטיוטה לא השתנתה, אפשר לנסות שוב.",
                    "התיק אינו מוכן לבחינת אשראי. כדי להכין מכתב אישור יש לבחור בכך במפורש; הפריטים הפתוחים נשארים בתיק."):
        assert staff_en.translate(message), message
