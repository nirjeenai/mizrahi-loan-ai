"""Conversational questionnaire (V2). Every value — quick reply, parser or Gemini proposal — is recorded through
`onboarding.answer`; every turn ends in exactly one assistant message; the loan category is asked first and maps onto
the entity correctly; the indication is deterministic; confirmation is V1's (one case, same checklist).

The Gemini tests replace `llm.gemini.generate` with canned answers: they cover the schema handling, validation and
fallbacks around the model, not the model's own understanding (that needs a live, authorised evaluation)."""
from __future__ import annotations

import dataclasses
import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.llm import gemini as g
from app.main import app
from app.policy import store
from app.workflow import indication, onboarding_llm as llm, onboarding_nlu as nlu


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


class Chat:
    def __init__(self):
        self.c = TestClient(app)
        self.d = self.c.post("/api/demo/onboarding/v2").json()
        self.id = self.d["draft_id"]

    def _turn(self, body: dict) -> dict:
        r = self.c.post(f"/api/demo/onboarding/{self.id}/v2/turn", json=body)
        assert r.status_code == 200, r.text
        self.d = r.json()
        return self.d

    def say(self, text: str, turn_id: str | None = None) -> dict:
        return self._turn({"text": text, **({"turn_id": turn_id} if turn_id else {})})

    def pick(self, qid: str, value) -> dict:
        return self._turn({"question_id": qid, "value": value})

    @property
    def pending(self) -> str | None:
        return (self.d["pending"] or {}).get("question_id")

    @property
    def last(self) -> dict:
        return self.d["messages"][-1]

    def answers(self) -> dict:
        return {a["question_id"]: a["answer"] for a in self.c.get(f"/api/demo/onboarding/{self.id}").json()["asked"]}

    def insights(self) -> list[dict]:
        return [m for m in self.d["messages"] if m.get("indication")]


def personal(ch: Chat) -> None:
    ch.pick("loan_type", "personal")
    ch.say("מיכל ברק")
    ch.say("DEMO-ID-201")


# ---------------------------------------------------------------- parser and formula
def test_parser_reads_facts_corrections_and_uncertainty():
    i = {"entity": "individual", "loan_type": "personal"}
    u = nlu.understand("אני שכיר ויש לי גם עוסק פטור, אני מרוויח בערך 16 אלף נטו ורוצה 80 אלף לרכב לחמש שנים.", i, "income")
    assert u["values"] == {"purpose": "car", "income": ["salaried", "self_employed"], "registration": "vat_exempt",
                           "net": 16000, "amount": 80000, "payments": 60}
    assert nlu.understand("למה צריך לדעת אם אני עוסק פטור?", i, "registration")["values"] == {}
    assert nlu.understand("אני מרוויח 19 אלף ברוטו", i, "net")["values"] == {}
    side = nlu.understand("אני עובד פה ושם, לפעמים כשכיר ולפעמים עושה עבודות מהצד. לא ממש יודע איך להגדיר את עצמי.", i, "income")
    assert side["values"] == {} and side["notes"][0]["kind"] == "income_side_jobs"
    assert nlu.understand("אני עצמאי אבל בעבר הייתי שכיר.", i, "income")["values"] == {"income": ["self_employed"]}
    fix = nlu.understand("בעצם אני רוצה 120 אלף במקום 80.", {**i, "amount": 80000}, "net")
    assert fix["values"] == {"amount": 120000} and fix["corrections"] == {"amount"}
    assert nlu.understand("אני רוצה 80 אלף לרכב", {}, "loan_type")["values"] == {"purpose": "car", "amount": 80000}


def test_indication_formula_is_unchanged():
    base = {"entity": "individual", "amount": 80000, "payments": 60, "income": ["salaried"]}
    assert indication.compute(base, 250000)["missing"] == ["net"]
    ind = indication.compute({**base, "net": 16000}, 250000)
    assert ind["max_monthly_ils"] == 4800 and ind["max_amount_ils"] == 248000 and ind["requested_monthly_ils"] == 1550
    assert indication.compute({**base, "net": 16000, "income": ["salaried", "self_employed"]}, 250000)["max_amount_ils"] == 206000


# ---------------------------------------------------------------- loan category
def test_the_first_question_is_the_loan_type_and_maps_onto_the_entity():
    ch = Chat()
    assert ch.pending == "loan_type" and "איזו הלוואה מעניינת אותך" in ch.last["text_he"]
    assert [r["label_he"] for r in ch.d["pending"]["replies"]] == ["הלוואה פרטית", "הלוואה עסקית"]
    ch.pick("loan_type", "business")
    assert ch.pending == "business_form" and "entity" not in ch.answers()       # business is not automatically a company
    ch.pick("business_form", "vat_exempt")
    a = ch.answers()
    assert a["entity"] == "individual" and a["income"] == ["self_employed"] and a["registration"] == "vat_exempt"
    assert ch.d["loan"] == {"type": "business", "form": "vat_exempt"} and ch.pending == "name"
    ch.pick("business_form", "company")
    assert ch.answers()["entity"] == "company" and ch.pending == "company_name"
    ch.pick("loan_type", "personal")
    assert ch.answers()["entity"] == "individual" and ch.d["loan"] == {"type": "personal", "form": None}


def test_a_business_loan_for_a_sole_proprietor_refuses_income_without_the_business():
    ch = Chat()
    ch.say("אני צריך הלוואה לעסק שלי, אני עוסק מורשה")
    assert ch.d["loan"] == {"type": "business", "form": "vat_registered"}
    ch.say("אני רק שכיר")
    assert ch.answers()["income"] == ["self_employed"]
    assert any(act["question_id"] == "loan_type" for act in ch.last.get("actions", []))


# ---------------------------------------------------------------- one coherent answer per turn
def test_gross_income_gets_one_reply_per_submission_and_records_nothing():
    ch = Chat()
    for _ in range(2):
        before = len(ch.d["messages"])
        ch.say("אני מרוויח 19 אלף ברוטו, אפשר לחשב לי לפי זה?")
        assert len(ch.d["messages"]) == before + 2                                  # the customer's message + one reply
        assert "נטו, ולא ברוטו" in ch.last["text_he"] and "מידע מאומת" not in ch.last["text_he"]
        assert ch.last["text_he"].endswith("מדובר בהלוואה פרטית או עסקית?")
    assert ch.answers() == {} and ch.pending == "loan_type" and ch.d["indication"] is None


def test_a_repeated_turn_id_is_ignored():
    ch = Chat()
    ch.say("הלוואה פרטית", turn_id="T-1")
    n = len(ch.d["messages"])
    ch.say("הלוואה פרטית", turn_id="T-1")
    assert len(ch.d["messages"]) == n


def test_direct_questions_get_direct_answers_and_the_pending_question_stays():
    ch = Chat()
    ch.say("אתה מבטיח לי שהבנק יאשר את ההלוואה?")
    assert ch.last["text_he"].startswith("אני לא יכול להבטיח אישור, אבל אפשר לבדוק את הבקשה") and ch.pending == "loan_type"
    ch.say("מה מזג האוויר בתל אביב מחר?")
    assert "לא אוכל לתת תחזית מזג אוויר" in ch.last["text_he"] and ch.pending == "loan_type"
    ch.say("אני רוצה הלוואה של 300 אלף שקל.")
    assert "עד 250,000 ₪" in ch.last["text_he"] and ch.answers() == {}


def test_ambiguous_side_jobs_are_clarified_not_classified():
    ch = Chat()
    personal(ch)
    ch.say("אני רוצה 80 אלף לרכב")
    ch.pick("payments", 60)
    assert ch.pending == "income"
    ch.say("אני עובד פה ושם, לפעמים כשכיר ולפעמים עושה עבודות מהצד. לא ממש יודע איך להגדיר את עצמי.")
    assert "income" not in ch.answers() and ch.pending == "income"
    assert "עסק עצמאי" in ch.last["text_he"]
    labels = [act["label_he"] for act in ch.last["actions"]]
    assert labels[:2] == ["יש לי גם עסק עצמאי", "הכול כשכיר"]
    ch.pick("income", ["salaried", "self_employed"])
    assert ch.answers()["income"] == ["salaried", "self_employed"] and ch.pending == "registration"


def test_policy_question_mid_flow_resumes_without_the_robotic_repeat():
    ch = Chat()
    personal(ch)
    ch.say("אני עצמאית, רוצה 80 אלף לשיפוץ")
    ch.pick("payments", 48)
    assert ch.pending == "registration"
    ch.say("למה אני צריך גם אישור עוסק?")
    reply = ch.last["text_he"]
    assert "אישור עוסק פטור" in reply and "תעודת עוסק מורשה" in reply and "נמשיך מהנקודה" not in reply
    assert ch.pending == "registration" and len([m for m in ch.d["messages"] if m["role"] == "assistant"][-1:]) == 1


def test_corrections_update_dependent_state_and_the_indication():
    ch = Chat()
    personal(ch)
    ch.say("אני שכירה, מרוויחה 16 אלף נטו, רוצה הלוואה של 80 אלף לרכב לחמש שנים.")
    assert ch.answers()["payments"] == 60 and ch.pending == "co_borrower"
    first = ch.insights()[-1]
    assert first["indication"]["max_amount_ils"] == 248000
    assert "הבקשה שלך ל־80,000 ₪ נראית אפשרית להמשך בדיקה ראשונית" in first["text_he"]
    assert "לא בדיקת זכאות או אישור" in first["text_he"]
    ch.say("בעצם אני רוצה 120 אלף במקום 80.")
    assert ch.answers()["amount"] == 120000 and ch.d["indication"]["requested_amount_ils"] == 120000
    r = ch._turn({"question_id": "income", "action": "edit"})
    assert r["pending"]["question_id"] == "income" and r["pending"]["editing"]
    ch.say("אני לא שכיר, אני רק עצמאי.")
    assert ch.answers()["income"] == ["self_employed"] and ch.pending == "registration"
    assert ch.answers()["amount"] == 120000                                             # unrelated answers kept
    assert ch.insights()[0]["stale"] and not ch.insights()[-1]["stale"]


def test_salaried_car_loan_creates_one_case_with_the_category():
    ch = Chat()
    personal(ch)
    ch.say("אני שכירה, מרוויחה 16 אלף נטו, רוצה הלוואה של 80 אלף לרכב לחמש שנים.")
    ch.say("איך הגעת לסכום שהצגת לי?")
    assert "16,000" in ch.last["text_he"] and "30%" in ch.last["text_he"] and ch.pending == "co_borrower"
    ch.say("לא, רק אני")
    assert ch.pending is None and ch.d["summary"]
    codes = [r["code"] for r in ch.d["summary"]["requirements"]]
    assert codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"]
    assert ch.d["summary"]["lines"][0] == {"label_he": "סוג ההלוואה", "value_he": "הלוואה פרטית", "question_id": "loan_type"}
    again = TestClient(app)
    first = ch.c.post(f"/api/demo/onboarding/{ch.id}/v2/confirm").json()
    second = again.post(f"/api/demo/onboarding/{ch.id}/v2/confirm").json()
    assert first["created"] and not second["created"] and first["case_id"] == second["case_id"]
    assert [r["code"] for r in first["requirements"]] == codes
    app_row = db.one("SELECT application FROM demo_applications WHERE case_id=?", (first["case_id"],))
    assert json.loads(app_row["application"])["loan_category"] == "personal"
    assert ch.c.post(f"/api/demo/onboarding/{ch.id}/v2/turn", json={"text": "40 אלף"}).status_code == 409


def test_reload_restores_the_conversation():
    ch = Chat()
    ch.pick("loan_type", "personal")
    ch.say("מיכל ברק")
    again = ch.c.get(f"/api/demo/onboarding/{ch.id}/v2").json()
    assert again["messages"] == ch.d["messages"] and again["pending"]["question_id"] == "national_id"
    assert again["stages"] == ch.d["stages"]


# ---------------------------------------------------------------- Gemini around the workflow (mocked transport)
def _llm_on(monkeypatch, answers: list, seen: list | None = None):
    monkeypatch.setattr(llm, "settings", dataclasses.replace(llm.settings, onboarding_llm=True, gemini_api_key="test-key"))

    def fake(model, contents, *, purpose, **kw):
        if seen is not None:
            seen.append((purpose, contents[0]["parts"][0]["text"]))
        nxt = answers.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(nxt, ensure_ascii=False)}]}}]}
    monkeypatch.setattr(g, "generate", fake)


def _interp(facts=(), unclear=(), topics=(), gross=False, reply="", next_field=""):
    return {"facts": [dict(zip(("field", "value", "kind", "certain"), f)) for f in facts],
            "unclear": [{"field": u, "note_he": ""} for u in unclear], "topics": list(topics), "gross_income_mentioned": gross,
            "reply_he": reply, "next_field": next_field}


def test_an_ordinary_turn_uses_the_interpretations_reply_in_one_call(monkeypatch):
    ch = Chat()
    ch.pick("loan_type", "personal")
    seen: list = []
    _llm_on(monkeypatch, [_interp([("name", "מיכל ברק", "answer", True)], reply="נעים להכיר, מיכל. מה מספר תעודת הזהות שלך?",
                                  next_field="national_id")], seen)
    ch.say("קוראים לי מיכל ברק")
    assert [p for p, _ in seen] == ["onboarding_interpret"] and ch.last["llm_calls"] == "1"
    assert ch.last["text_he"] == "נעים להכיר, מיכל. מה מספר תעודת הזהות שלך?" and ch.last["engine"] == "llm"


def test_the_assistant_says_meula_never_achla(monkeypatch):
    ch = Chat()
    ch.pick("loan_type", "personal")
    _llm_on(monkeypatch, [_interp([("name", "מיכל ברק", "answer", True)], reply="אחלה, מיכל. מה מספר תעודת הזהות שלך?",
                                  next_field="national_id")])
    ch.say("קוראים לי מיכל ברק")
    assert ch.last["text_he"] == "מעולה, מיכל. מה מספר תעודת הזהות שלך?"


def test_a_candidate_that_does_not_fit_the_outcome_gets_the_second_call(monkeypatch):
    ch = Chat()
    personal(ch)
    seen: list = []
    _llm_on(monkeypatch, [
        _interp([("amount", "1000000", "answer", True)], reply="מיליון שקל, בשמחה. בכמה תשלומים?", next_field="payments"),
        {"reply_he": "במסלול הזה אפשר לבקש עד 250,000 ₪. כמה תרצו לבקש בטווח הזה?"},
    ], seen)
    ch.say("אני רוצה מיליון שקל")
    assert [p for p, _ in seen] == ["onboarding_interpret", "onboarding_reply"] and "amount" not in ch.answers()
    assert "250,000" in ch.last["text_he"] and "בשמחה" not in ch.last["text_he"]


def test_the_indication_turn_can_take_one_call_and_an_approval_claim_never_passes(monkeypatch):
    ch = Chat()
    personal(ch)
    ch.say("רוצה 80 אלף לרכב ל-60 תשלומים")
    seen: list = []
    _llm_on(monkeypatch, [
        _interp([("income", "salaried", "answer", True), ("net", "16000", "extra", True)],
                reply="תודה. מישהו נוסף חותם איתך על ההלוואה?", next_field="co_borrower"),
        _interp([("co_borrower", "no", "answer", True)], reply="מצוין, ההלוואה מאושרת! הנה הסיכום.", next_field="summary"),
        {"reply_he": "הבקשה רק על שמך. הסיכום מוכן למטה לבדיקה ולאישור, פתיחת הבקשה אינה אישור הלוואה."},
    ], seen)
    ch.say("אני שכירה ומרוויחה בערך 16 אלף נטו")
    assert ch.last["llm_calls"] == "1" and ch.last["indication"]["requested_amount_ils"] == 80000
    ch.say("לא, רק אני")
    assert [p for p, _ in seen][-2:] == ["onboarding_interpret", "onboarding_reply"] and "מאושרת" not in ch.last["text_he"]


def test_business_form_and_salary_in_one_message_is_not_a_contradiction(monkeypatch):
    ch = Chat()
    _llm_on(monkeypatch, [_interp([("loan_type", "business", "answer", True), ("business_form", "vat_exempt", "extra", True),
                                   ("income", "salaried,self_employed", "extra", True)]), g.GeminiError("x")])
    ch.say("אני צריך הלוואה לעסק, יש לי עוסק פטור ואני גם שכיר בחצי משרה")
    a = ch.answers()
    assert a["income"] == ["salaried", "self_employed"] and a["registration"] == "vat_exempt"
    assert "מה נכון" not in ch.last["text_he"] and ch.pending == "name"


def test_approximate_numbers_survive_a_hesitant_model(monkeypatch):
    ch = Chat()
    personal(ch)
    _llm_on(monkeypatch, [_interp([("purpose", "car", "answer", True)], unclear=["amount"]), g.GeminiError("x"),
                          _interp(unclear=["net"], gross=True), g.GeminiError("x")])
    ch.say("רכב, צריכה בערך 80 אלף")
    assert ch.answers()["amount"] == 80000 and "לא הייתי בטוח" not in ch.last["text_he"]
    ch.say("אני מרוויחה 19 אלף ברוטו")
    assert "net" not in ch.answers() and "ולא ברוטו" in ch.last["text_he"] and "בערך נכנס" not in ch.last["text_he"]


def test_llm_proposals_are_validated_before_they_are_recorded(monkeypatch):
    ch = Chat()
    _llm_on(monkeypatch, [
        _interp([("loan_type", "personal", "answer", True), ("amount", "300000", "extra", True),
                 ("purpose", "car", "extra", True), ("payments", "60", "extra", False), ("national_id", "1", "extra", True)]),
        {"reply_he": "הבנתי, הלוואה פרטית לרכב. במסלול הזה אפשר לבקש עד 250,000 ₪. איך קוראים לך?"},
    ])
    ch.say("הלוואה פרטית לרכב של 300 אלף, אולי ל-60 תשלומים")
    a = ch.answers()
    assert a == {"entity": "individual", "purpose": "car"}                     # 300k refused, uncertain payments not recorded
    assert ch.last["engine"] == "llm" and ch.last["understood_by"] == "llm" and ch.pending == "name"


def test_an_ungrounded_llm_reply_falls_back_to_the_deterministic_one(monkeypatch):
    ch = Chat()
    _llm_on(monkeypatch, [_interp([("loan_type", "personal", "answer", True)]),
                          {"reply_he": "מצוין! אושרת להלוואה של 200,000 ₪ בריבית 4.5%."}])
    ch.say("פרטית בבקשה")
    assert ch.answers() == {"entity": "individual"}
    assert ch.last["engine"] == "rules" and "200,000" not in ch.last["text_he"]


def test_a_failing_model_never_loses_progress(monkeypatch):
    ch = Chat()
    _llm_on(monkeypatch, [g.GeminiError("timeout"), g.GeminiError("timeout")])
    ch.say("הלוואה פרטית")
    assert ch.answers() == {"entity": "individual"} and ch.last["understood_by"] == "rules" and ch.last["engine"] == "rules"


def test_llm_conflicts_need_a_correction_and_gross_is_never_net(monkeypatch):
    ch = Chat()
    personal(ch)
    ch.say("רוצה 80 אלף לרכב")
    _llm_on(monkeypatch, [
        _interp([("amount", "120000", "extra", True)]), g.GeminiError("x"),
        _interp([("amount", "120000", "correction", True)]), g.GeminiError("x"),
        _interp([("net", "19000", "extra", True)], gross=True), g.GeminiError("x"),
    ])
    ch.say("120 אלף")
    assert ch.answers()["amount"] == 80000 and "מה נכון" in ch.last["text_he"]
    ch.say("בעצם 120 אלף")
    assert ch.answers()["amount"] == 120000
    ch.say("מרוויח 19 אלף ברוטו")
    assert "net" not in ch.answers() and "ולא ברוטו" in ch.last["text_he"]


def test_id_numbers_never_reach_the_model_and_the_switch_turns_it_off(monkeypatch):
    ch = Chat()
    ch.pick("loan_type", "personal")
    ch.say("מיכל ברק")
    seen: list = []
    _llm_on(monkeypatch, [_interp(), {"reply_he": "תודה, רשמתי. למה מיועדת ההלוואה?"}], seen)
    ch.say("המספר שלי 123456782")
    assert ch.answers()["national_id"] == "123456782"
    assert seen and all("123456782" not in payload for _, payload in seen)
    monkeypatch.setattr(llm, "settings", dataclasses.replace(llm.settings, onboarding_llm=False))
    calls = len(seen)
    ch.say("לרכב")
    assert len(seen) == calls and ch.last["understood_by"] == "rules"


def test_schema_parsing_drops_malformed_proposals():
    out = llm.parse_interpretation({"facts": [{"field": "amount", "value": "שמונים", "kind": "answer", "certain": True},
                                              {"field": "income", "value": "salaried,pension", "kind": "answer", "certain": True},
                                              {"field": "approve_loan", "value": "yes", "kind": "answer", "certain": True},
                                              {"field": "net", "value": "16000", "kind": "answer", "certain": True}],
                                    "unclear": [], "topics": ["approval", "hack"], "gross_income_mentioned": False})
    assert out["values"] == {"net": 16000} and out["topics"] == ["approval"]
    assert {u["field"] for u in out["unclear"]} == {"amount", "income"}
    assert llm.parse_interpretation("not json") is None
    assert llm.grounded("80 אלף ב־60 תשלומים", {"x": "80,000 ₪ · 60"}) and not llm.grounded("ריבית 4.5%", {"x": "6%"})
