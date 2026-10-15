"""Banker V3 "שאל את JEEN": the route sends one scoped case to the model, keeps only real source ids, returns a draft
revision only after the code check passes (one repair call at most), and never pretends to answer without a model.
Gemini is replaced by a stub that records what it was sent."""
from __future__ import annotations

import dataclasses
import json

import pytest

from app import db
from app.api import banker_chat
from app.bank.mock_bank import bank
from app.llm import gemini as g
from app.review import case_review
from app.store import repo
from tests.loan_helpers import client_for
from tests.test_banker_intelligence import COMPLETE, GAP, brief, package

staff = client_for()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for case in (COMPLETE, GAP):
        repo.reset_case(case)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})
    monkeypatch.setattr(banker_chat, "settings", dataclasses.replace(banker_chat.settings, gemini_api_key="test-key"))
    yield


def model(monkeypatch, *answers: dict) -> list[dict]:
    """Gemini answers in order; returns the request bodies it received."""
    sent: list[dict] = []

    def generate(model_id, contents, **kw):
        sent.append({"contents": contents, **kw})
        if len(sent) > len(answers):
            raise AssertionError("more model calls than expected")
        a = answers[len(sent) - 1]
        if isinstance(a, Exception):
            raise a
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(a, ensure_ascii=False)}]}, "finishReason": "STOP"}]}

    monkeypatch.setattr(banker_chat.g, "generate", generate)
    return sent


def reply(intent="question", answer="תשובה", sources=(), revised="", summary="") -> dict:
    return {"intent": intent, "answer_he": answer, "source_ids": list(sources), "revised_draft_he": revised, "change_summary_he": summary}


def ask(message: str, draft: dict | None, history=(), case=COMPLETE):
    return staff.post(f"/api/banker/cases/{case}/chat", json={"message": message, "history": list(history), "draft": draft})


def ready_draft() -> tuple[dict, dict]:
    package(COMPLETE)
    b = brief(COMPLETE)
    d = next(x for x in b["drafts"] if x["kind"] == "complete_documentation")
    return b, {"kind": d["kind"], "text": d["message_he"]}


def test_a_question_is_answered_from_this_case_only_with_real_source_ids(monkeypatch):
    b, draft = ready_draft()
    draft["text"] += "\nשורה שהבנקאית הוסיפה ידנית."
    sent = model(monkeypatch, reply(answer="היחס 14.1%", sources=["calc:combined_dsr", "calc:invented", "calc:combined_dsr"]))
    r = ask("מאיפה הגיע יחס ההחזר?", draft, history=[{"role": "user", "text": "שאלה קודמת"}, {"role": "model", "text": "תשובה קודמת"}])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["intent"] == "question" and out["edit"] is None
    assert out["source_ids"] == ["calc:combined_dsr"] and out["sources"]["calc:combined_dsr"]["kind"] == "calculated"
    assert len(sent) == 1 and sent[0]["purpose"] == "banker_chat" and sent[0]["schema"]["required"]
    prompt = sent[0]["contents"][-1]["parts"][0]["text"]
    assert "<case_data>" in prompt and "calc:combined_dsr" in prompt and "formula_he" in prompt
    assert "שורה שהבנקאית הוסיפה ידנית." in prompt                     # the CURRENT draft, manual edits included
    assert [c["role"] for c in sent[0]["contents"]] == ["user", "model", "user"]
    borrower = bank.get_case(COMPLETE)["borrowers"][0]
    assert borrower["national_id"] not in prompt
    other = bank.get_case("DEMO-MTZ-2026-101")["borrowers"][0]["name_he"]          # another customer's case
    assert other not in prompt


def test_a_checked_revision_comes_back_for_the_editor(monkeypatch):
    _, draft = ready_draft()
    revised = draft["text"].replace("ייתכן שנבקש", "הבקשה כפופה לאימות הנתונים ולאישור הבנק. ייתכן שנבקש")
    sent = model(monkeypatch, reply("draft_edit", "הוספתי משפט על אימות ואישור הבנק.", revised=revised, summary="נוסף משפט"))
    out = ask("תוסיף שהבקשה כפופה לאימות ואישור הבנק", draft).json()
    assert len(sent) == 1
    assert out["edit"] == {"kind": "complete_documentation", "text": revised, "summary_he": "נוסף משפט"}
    assert out["rejected_issues_he"] == []


def test_an_approval_claim_never_reaches_the_editor_even_after_the_repair_call(monkeypatch):
    _, draft = ready_draft()
    bad = draft["text"].replace("הודעה זו אינה אישור הלוואה ואינה התחייבות לתנאים.", "שמחים לבשר שההלוואה שלך אושרה.")
    sent = model(monkeypatch, reply("draft_edit", "עודכן", revised=bad), reply("draft_edit", "עודכן", revised=bad))
    out = ask("תכתוב ללקוחה שההלוואה אושרה", draft).json()
    assert len(sent) == 2 and "rejected this revision" in sent[1]["contents"][-1]["parts"][0]["text"]
    assert out["edit"] is None and out["answer_he"].startswith("לא עדכנתי את הטיוטה")
    assert any("אישור" in i for i in out["rejected_issues_he"])


def test_a_declined_request_keeps_the_draft_and_explains(monkeypatch):
    _, draft = ready_draft()
    sent = model(monkeypatch, reply("declined", "אי אפשר לכתוב שההלוואה אושרה. אפשר לכתוב שהבקשה בבדיקה."))
    out = ask("תכתוב שהריבית שאושרה היא 6%", draft).json()
    assert len(sent) == 1 and out["intent"] == "declined" and out["edit"] is None


def test_the_repair_call_can_fix_a_rejected_revision(monkeypatch):
    _, draft = ready_draft()
    leaky = draft["text"].replace("ייתכן", "יחס ההחזר שלך 14.1%. ייתכן")
    clean_text = draft["text"].replace("ייתכן", "נעדכן אותך בהמשך. ייתכן")
    model(monkeypatch, reply("draft_edit", "א", revised=leaky), reply("draft_edit", "ב", revised=clean_text, summary="תוקן"))
    out = ask("תסביר ללקוחה את המצב", draft).json()
    assert out["edit"]["text"] == clean_text and out["repaired"] is True


def test_the_code_check_rejects_internal_figures_a_dropped_disclosure_and_new_links():
    b, draft = ready_draft()
    cur = draft["text"]
    assert banker_chat.check_revision(cur, cur, b) == []
    assert banker_chat.check_revision(cur + "\nהבקשה עדיין כפופה לאימות ולאישור הבנק.", cur, b) == []
    issues = banker_chat.check_revision(cur.replace("ייתכן", "יחס ההחזר שלך 14.1%. ייתכן"), cur, b)
    assert any("נתונים מספריים" in i for i in issues) and any("מונח פנימי" in i for i in issues)
    assert any("ההבהרה" in i for i in banker_chat.check_revision(cur.replace("הודעה זו אינה אישור הלוואה ואינה התחייבות לתנאים.", ""), cur, b))
    assert any("אישור" in i for i in banker_chat.check_revision(cur.replace("ייתכן", "הריבית שאושרה היא 6%. ייתכן"), cur, b))
    assert any("קישור" in i for i in banker_chat.check_revision(cur + "\nhttps://example.com", cur, b))
    for d in b["drafts"]:                                                 # every template passes its own check
        assert banker_chat.check_revision(d["message_he"], d["message_he"], b) == []


def test_without_a_model_the_chat_says_so_and_customers_cannot_use_it(monkeypatch):
    _, draft = ready_draft()
    model(monkeypatch, g.GeminiError("HTTP 500"))
    r = ask("מה ההכנסה?", draft)
    assert r.status_code == 503 and "הטיוטה לא השתנתה" in r.json()["detail"]
    monkeypatch.setattr(banker_chat, "settings", dataclasses.replace(banker_chat.settings, gemini_api_key=""))
    r = ask("מה ההכנסה?", draft)
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]
    customer = client_for(COMPLETE)
    customer.cookies.delete("mzl_staff")
    r = customer.post(f"/api/banker/cases/{COMPLETE}/chat", json={"message": "x", "history": [], "draft": None})
    assert r.status_code in (401, 403)
