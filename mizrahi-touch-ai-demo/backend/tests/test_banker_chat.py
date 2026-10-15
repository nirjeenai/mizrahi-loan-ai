"""Banker V3 "שאל את JEEN": the route sends one scoped case to the model, keeps only real source ids, returns a draft
revision only after the code check passes (one repair call at most), and never pretends to answer without a model.
Gemini is replaced by a stub that records what it was sent."""
from __future__ import annotations

import dataclasses
import json

import pytest

from app import auth, db
from app.api import banker_chat
from app.api import banker_demo_letter as letter
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
    monkeypatch.setattr(letter, "settings", dataclasses.replace(letter.settings, gemini_api_key="test-key"))
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
    customer.cookies.delete(auth.COOKIES["staff"])
    r = customer.post(f"/api/banker/cases/{COMPLETE}/chat", json={"message": "x", "history": [], "draft": None})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------- the third reply: approval letter for a SIMULATED decision
def sections(**over) -> dict:
    s = {"opening_he": "בהמשך לפנייתך, ולאחר שבחנו את בקשתך ואת המסמכים שצירפת, ברצוננו לעדכן אותך.",
         "approval_he": "בקשתך אושרה על ידי הבנקאית המטפלת, בכפוף לתנאים שלהלן.",
         "terms_note_he": "הסכומים הם אומדן להמחשה, והתנאים בפועל ייקבעו במסמכי ההלוואה.",
         "conditions_intro_he": "העמדת ההלוואה כפופה לתנאים הבאים:",
         "conditions_he": ["השלמת הבדיקות הנדרשות בבנק.", "הצגת אסמכתה עדכנית למטרת ההלוואה, ככל שתידרש.", "חתימה על מסמכי ההלוואה."],
         "next_steps_he": "ניצור איתך קשר לתיאום המשך הטיפול ולהצגת מסמכי ההלוואה.", "closing_he": "נשמח ללוות אותך."}
    return {**s, **over}


def make(case=COMPLETE, **body):
    return staff.post(f"/api/banker/cases/{case}/demo-approval-letter", json=body)


def test_the_demo_letter_takes_its_terms_from_the_calculation_and_its_prose_from_the_model(monkeypatch):
    package(COMPLETE)
    b = brief(COMPLETE)
    sent = model(monkeypatch, sections())
    r = make(acknowledge_open_issues=False, use_ai=True)
    assert r.status_code == 200, r.text
    out = r.json()
    a = b["analysis"]
    assert out["source"] == "ai" and len(sent) == 1 and sent[0]["purpose"] == "banker_demo_letter"
    text = out["text"]
    for v in (a["proposed_payment"]["value"], a["total_payments"]["value"], a["total_interest"]["value"], b["loan"]["amount"]["value"]):
        assert (f"₪{v:,.0f}" if float(v).is_integer() else f"₪{v:,.2f}") in text
    assert text.startswith(letter.TITLE_HE) and letter.NOTICE_HE in text
    assert "בקשתך אושרה" in text and out["scenario"]["term_months"] == b["loan"]["term"]["value"]
    assert brief(COMPLETE)["recommendation"]["state"] == b["recommendation"]["state"]          # the case is unchanged


def test_a_model_section_with_an_invented_figure_falls_back_to_the_labelled_base_letter(monkeypatch):
    package(COMPLETE)
    bad = sections(next_steps_he="הכסף כבר הועבר לחשבונך, ושעבוד על הרכב בסך 45,000 נרשם.")
    sent = model(monkeypatch, bad, bad)
    out = make().json()
    assert len(sent) == 2 and out["source"] == "base" and out["model"] is None and out["check_issues_he"]
    assert "45,000" not in out["text"] and "הועבר לחשבונך" not in out["text"]


def test_prose_that_repeats_the_demo_framing_gets_one_repair(monkeypatch):
    package(COMPLETE)
    sent = model(monkeypatch, sections(approval_he="בתרחיש ההדמיה, בקשתך אושרה בכפוף לתנאים."), sections())
    out = make().json()
    assert len(sent) == 2 and out["source"] == "ai" and "תרחיש" not in out["text"]
    assert out["text"].count("הדמיה") == 2                                                 # the title and the notice


def test_a_case_that_is_not_ready_needs_an_explicit_choice_and_keeps_its_open_items(monkeypatch):
    package(GAP)
    sent = model(monkeypatch)
    r = make(GAP, use_ai=False)
    assert r.status_code == 409 and "במפורש" in r.json()["detail"]
    out = make(GAP, acknowledge_open_issues=True, use_ai=False).json()
    assert out["source"] == "base" and not sent and out["case_ready"] is False
    assert "השלמת המסמכים והבירורים שעדיין פתוחים בבקשה." in out["text"]
    assert any("פער" in i for i in out["open_issues_he"])
    assert brief(GAP)["recommendation"]["state"] == "CLARIFICATION_REQUIRED"


def test_approval_wording_is_accepted_only_in_the_demo_letter_and_only_with_its_markers():
    package(COMPLETE)
    b = brief(COMPLETE)
    base = letter.base_letter(COMPLETE, b)
    k = letter.DEMO_KIND
    assert banker_chat.check_revision(base, base, b, k, base) == []
    tab1 = next(d["message_he"] for d in b["drafts"] if d["kind"] == "complete_documentation")
    assert any("אישור" in i for i in banker_chat.check_revision(tab1 + "\nבקשתך אושרה.", tab1, b, "complete_documentation"))
    assert banker_chat.check_revision(base.replace(letter.NOTICE_HE, ""), base, b, k, base)
    assert banker_chat.check_revision(base.replace(letter.TITLE_HE, "הודעה בדבר אישור בקשת הלוואה")
                                      .replace(letter.NOTICE_HE, "מכתב זה אינו החלטת אשראי ואינו הסכם הלוואה."), base, b, k, base)
    for claim in ("הכסף כבר הועבר לחשבונך.", "מסמכי ההלוואה נחתמו.", "חתמת על ההסכם."):
        assert any("שלבים עתידיים" in i for i in banker_chat.check_revision(base + "\n" + claim, base, b, k, base)), claim


def test_the_chat_edits_the_demo_letter_with_its_scenario_in_the_prompt(monkeypatch):
    package(COMPLETE)
    b = brief(COMPLETE)
    base = letter.base_letter(COMPLETE, b)
    revised = base.replace("השלבים הבאים\n", "השלבים הבאים\nההחזר ייעשה בתשלומים חודשיים שווים לאורך 60 חודשים.\n")
    sent = model(monkeypatch, reply("draft_edit", "הוספתי הסבר על תנאי ההחזר.", revised=revised, summary="נוסף הסבר"))
    out = ask("תוסיף הסבר על תנאי ההחזר", {"kind": letter.DEMO_KIND, "text": base}).json()
    assert out["edit"]["kind"] == letter.DEMO_KIND and out["edit"]["text"] == revised
    prompt = sent[0]["contents"][-1]["parts"][0]["text"]
    assert "<demo_scenario>" in prompt and '"kind": "demo_approval"' in prompt
