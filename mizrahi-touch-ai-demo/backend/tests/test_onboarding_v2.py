"""Conversational questionnaire (V2): free text and quick replies write the one onboarding draft through
`onboarding.answer`; the preliminary indication is deterministic, explained, recalculated and withdrawn; questions
in the middle of the flow resume the exact pending question; confirmation is V1's (one case, same checklist)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.policy import store
from app.workflow import indication, onboarding_nlu as nlu


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


class Chat:
    def __init__(self):
        self.c = TestClient(app)
        self.d = self.c.post("/api/demo/onboarding/v2").json()
        self.id = self.d["draft_id"]

    def say(self, text: str) -> dict:
        r = self.c.post(f"/api/demo/onboarding/{self.id}/v2/turn", json={"text": text})
        assert r.status_code == 200, r.text
        self.d = r.json()
        return self.d

    def pick(self, qid: str, value) -> dict:
        r = self.c.post(f"/api/demo/onboarding/{self.id}/v2/turn", json={"question_id": qid, "value": value})
        assert r.status_code == 200, r.text
        self.d = r.json()
        return self.d

    @property
    def pending(self) -> str | None:
        return (self.d["pending"] or {}).get("question_id")

    def answers(self) -> dict:
        return {a["question_id"]: a["answer"] for a in self.c.get(f"/api/demo/onboarding/{self.id}").json()["asked"]}

    def insights(self) -> list[dict]:
        return [m for m in self.d["messages"] if m["kind"] == "insight"]


def test_parser_reads_several_facts_from_one_sentence_and_nothing_from_a_question():
    u = nlu.understand("אני שכיר, יש לי גם עוסק פטור, מרוויח בערך 16 אלף נטו ורוצה הלוואה של 80 אלף לרכב.", {}, "entity")
    assert u["values"] == {"entity": "individual", "purpose": "car", "income": ["salaried", "self_employed"],
                           "registration": "vat_exempt", "net": 16000, "amount": 80000}
    assert nlu.understand("למה צריך לדעת אם אני עוסק פטור?", {"entity": "individual"}, "registration")["values"] == {}
    gross = nlu.understand("20 אלף ברוטו", {"entity": "individual"}, "net")
    assert gross["values"] == {} and gross["notes"][0]["kind"] == "gross"
    assert nlu.understand("בין 14 ל-15 אלף", {"entity": "individual"}, "net")["values"] == {"net": 14000}
    assert nlu.understand("מיכל ברק", {"entity": "individual"}, "name")["values"] == {"name": {"first": "מיכל", "last": "ברק"}}
    added = nlu.understand("בעצם יש לי גם עסק קטן כעוסק פטור", {"entity": "individual", "income": ["salaried"]}, None)
    assert added["values"] == {"income": ["salaried", "self_employed"], "registration": "vat_exempt"}


def test_indication_needs_every_input_and_follows_the_documented_formula():
    base = {"entity": "individual", "amount": 80000, "payments": 60, "income": ["salaried"]}
    missing = indication.compute(base, 250000)
    assert not missing["available"] and missing["missing"] == ["net"]
    ind = indication.compute({**base, "net": 16000}, 250000)
    factor = (1 - (1 + 0.005) ** -60) / 0.005
    assert ind["max_monthly_ils"] == 4800 and ind["max_amount_ils"] == int(4800 * factor // 1000 * 1000) == 248000
    mixed = indication.compute({**base, "net": 16000, "income": ["salaried", "self_employed"]}, 250000)
    assert mixed["ratio"] == indication.DEMO_RATIO_WITH_BUSINESS and mixed["max_amount_ils"] < ind["max_amount_ils"]
    assert not indication.compute({"entity": "company"}, 250000)["available"]


def test_salaried_car_loan_by_free_text_and_quick_replies_creates_one_case():
    ch = Chat()
    assert ch.pending == "entity" and [s["state"] for s in ch.d["stages"]] == ["current", "upcoming", "upcoming", "upcoming"]
    ch.say("אני רוצה לקנות רכב ב־80 אלף שקל")
    assert ch.answers() == {"entity": "individual", "purpose": "car", "amount": 80000} and ch.pending == "name"
    ch.say("מיכל ברק")
    ch.say("DEMO-ID-201")
    ch.pick("payments", 60)
    assert ch.d["indication"] is None and not ch.insights()                      # no number without income
    ch.say("אני שכירה, מרוויחה בערך 16 אלף נטו")
    assert ch.d["indication"]["max_amount_ils"] == 248000 and len(ch.insights()) == 1
    assert "לא הצעה ולא אישור" in ch.insights()[0]["text_he"] and ch.pending == "co_borrower"
    ch.say("לא, רק אני")
    assert ch.pending is None and ch.d["summary"]
    codes = [r["code"] for r in ch.d["summary"]["requirements"]]
    assert codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"]
    assert [s["state"] for s in ch.d["stages"]] == ["done", "done", "done", "current"]
    first = ch.c.post(f"/api/demo/onboarding/{ch.id}/confirm").json()
    again = ch.c.post(f"/api/demo/onboarding/{ch.id}/confirm").json()
    assert first["created"] and not again["created"] and first["case_id"] == again["case_id"]
    assert [r["code"] for r in first["requirements"]] == codes
    assert ch.c.post(f"/api/demo/onboarding/{ch.id}/v2/turn", json={"text": "40 אלף"}).status_code == 409


def test_a_question_mid_flow_is_answered_from_policy_and_resumes_the_same_question():
    ch = Chat()
    ch.say("אני עצמאית, צריכה הלוואה לשיפוץ")
    ch.say("מיכל ברק")
    ch.say("DEMO-ID-201")
    ch.say("80 אלף")
    ch.pick("payments", 48)
    assert ch.pending == "registration"
    before = ch.answers()
    ch.say("למה בכלל צריך את זה?")
    reply = ch.d["messages"][-2]["text_he"]
    assert "אישור עוסק פטור" in reply and "תעודת עוסק מורשה" in reply              # labels from the published policy
    last = ch.d["messages"][-1]
    assert last["kind"] == "question" and last["question_id"] == "registration" and last["text_he"].startswith("נמשיך")
    assert ch.pending == "registration" and ch.answers() == before
    assert [r["value"] for r in ch.d["pending"]["replies"]] == ["vat_exempt", "vat_registered"]
    ch.say("מה מזג האוויר מחר?")
    assert "אין לי מידע מאומת" in ch.d["messages"][-2]["text_he"] and ch.pending == "registration"


def test_changes_update_dependent_state_and_recalculate_or_withdraw_the_indication():
    ch = Chat()
    for t in ("אני שכירה, מרוויחה 16 אלף נטו ורוצה 80 אלף לרכב", "מיכל ברק", "DEMO-ID-201", "60 תשלומים", "לא, רק אני"):
        ch.say(t)
    assert ch.pending is None and len(ch.insights()) == 1
    ch.say("בעצם יש לי גם עסק קטן כעוסק פטור")
    assert ch.answers()["income"] == ["salaried", "self_employed"] and ch.answers()["registration"] == "vat_exempt"
    assert {"TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= {r["code"] for r in ch.d["summary"]["requirements"]}
    assert ch.d["indication"]["max_amount_ils"] == 206000 and len(ch.insights()) == 2
    assert ch.insights()[0]["stale"] and not ch.insights()[1]["stale"]
    ch.say("אפשר לשנות את הסכום ל-120 אלף?")
    assert ch.answers()["amount"] == 120000 and ch.d["indication"]["requested_amount_ils"] == 120000
    r = ch.c.post(f"/api/demo/onboarding/{ch.id}/v2/turn", json={"question_id": "payments", "action": "edit"}).json()
    assert r["pending"]["question_id"] == "payments" and r["pending"]["editing"]
    assert [s["state"] for s in r["stages"]][1] == "current"
    ch.say("84")
    assert ch.answers()["payments"] == 84 and ch.pending is None
    ch.pick("entity", "company")                                                     # individual answers no longer apply
    assert ch.d["indication"] is None and any(m["kind"] == "withdrawn" for m in ch.d["messages"])
    assert all(m["stale"] for m in ch.insights())
    assert ch.pending == "company_name"


def test_reload_restores_the_transcript_and_the_pending_question():
    ch = Chat()
    ch.say("אני רוצה לקנות רכב ב־80 אלף שקל")
    ch.say("מיכל ברק")
    again = ch.c.get(f"/api/demo/onboarding/{ch.id}/v2").json()
    assert again["messages"] == ch.d["messages"] and again["pending"]["question_id"] == "national_id"
    assert again["stages"] == ch.d["stages"]


def test_text_that_is_not_understood_records_nothing():
    ch = Chat()
    ch.say("אני רוצה לקנות רכב")
    ch.say("מיכל ברק")
    before = ch.answers()
    ch.say("אולי")
    assert ch.answers() == before and ch.pending == "national_id"
    assert ch.d["messages"][-2]["text_he"].startswith("לא בטוח שהבנתי")
    ch.say("1000000")                                                                # out of bounds: validation refuses
    assert "amount" not in ch.answers() or ch.answers()["amount"] != 1000000
