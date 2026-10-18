"""Hebrew baseline of the conversational questionnaire (V2) and the classic questionnaire (V1): scripted journeys through
the real routes with the deterministic engine (Gemini is off in tests). Recorded before the bilingual work; every
Hebrew message, quick reply, stage, simulator payload and summary must stay byte-identical (tests/golden_util.py)."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.policy import store

from .golden_util import check


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


class Journey:
    """Records, after every step, the new messages and the whole view except the transcript (which is recorded once)."""

    def __init__(self, headers: dict | None = None):
        self.c = TestClient(app, headers=headers)
        self.d = self.c.post("/api/demo/onboarding/v2").json()
        self.id = self.d["draft_id"]
        self.steps: list[dict] = [{"step": "start", "view": self.d}]
        self.n = len(self.d["messages"])
        self.turns = 0
        self.literals: list[str] = []

    def _record(self, step: Any, r) -> None:
        body = r.json()
        if r.status_code != 200:
            self.steps.append({"step": step, "status": r.status_code, "body": body})
            return
        self.d = body
        new = body["messages"][self.n:]
        self.n = len(body["messages"])
        self.steps.append({"step": step, "new_messages": new, "view": {k: v for k, v in body.items() if k != "messages"}})

    def turn(self, body: dict) -> None:
        self.turns += 1
        self._record(body, self.c.post(f"/api/demo/onboarding/{self.id}/v2/turn", json={**body, "turn_id": f"G-{self.turns}"}))

    def run(self, steps: list) -> list[dict]:
        for s in steps:
            kind = s[0]
            if kind == "say":
                self.turn({"text": s[1]})
            elif kind == "pick":
                label = next((r["label_he"] for r in (self.d["pending"] or {}).get("replies", []) if r["value"] == s[2]), None)
                self.turn({"question_id": s[1], "value": s[2], **({"label_he": label} if label else {})})
            elif kind == "confirm":
                self.turn({"action": "simulate_confirm", "simulation": s[1]})
            elif kind == "save":
                r = self.c.post(f"/api/demo/onboarding/{self.id}/v2/simulation", json={"draft": s[1]})
                self.steps.append({"step": s, "status": r.status_code, "simulation": r.json().get("simulation")})
            elif kind == "edit":
                self.turn({"question_id": s[1], "action": "edit"})
            elif kind == "cancel":
                self.turn({"action": "cancel_edit"})
            elif kind == "action":                      # the last assistant message's first offered action
                a = self.d["messages"][-1]["actions"][s[1] if len(s) > 1 else 0]
                if a.get("simulation"):
                    self.turn({"action": "simulate_apply", "simulation": a["simulation"], "label_he": a["label_he"]})
                elif a.get("text"):
                    self.turn({"text": a["text"]})
                else:
                    self.turn({"question_id": a["question_id"], "value": a.get("value"), "label_he": a["label_he"]})
            elif kind == "reload":
                r = self.c.get(f"/api/demo/onboarding/{self.id}/v2")
                self.steps.append({"step": s, "status": r.status_code, "view": r.json()})
            elif kind == "open_case":
                r = self.c.post(f"/api/demo/onboarding/{self.id}/v2/confirm")
                self.steps.append({"step": s, "status": r.status_code, "body": r.json()})
                if r.status_code == 200:
                    case = r.json()["case_id"]
                    self.c.post("/api/session/demo/customer", json={"case_id": case})
                    snap = self.c.get(f"/api/cases/{case}")
                    self.literals.append(snap.json()["case"]["display_number"])
                    self.steps.append({"step": "case_snapshot", "status": snap.status_code, "body": snap.json()})
        self.steps.append({"step": "final_transcript", "messages": self.d.get("messages")})
        return self.steps


PERSONAL = [("pick", "loan_type", "personal"), ("say", "מיכל ברק"), ("say", "DEMO-ID-201")]
JOURNEYS: dict[str, list] = {
    "car_salaried_sim": PERSONAL + [
        ("say", "רכישת רכב"), ("save", {"amount": 100000, "term": 48, "product": "electric_car"}),
        ("confirm", {"amount": 180000, "term": 60, "asset_price": 200000, "product": "car"}),
        ("confirm", {"amount": 170000, "term": 48, "asset_price": 200000, "product": "car"}),
        ("pick", "income", ["salaried"]), ("say", "12 אלף נטו"), ("say", "למה צריך את זה?"), ("say", "לא, רק אני"),
        ("reload",), ("open_case",)],
    "car_corrections": PERSONAL + [
        ("say", "רכישת רכב"), ("confirm", {"amount": 80000, "term": 60, "product": "car"}),
        ("confirm", {"amount": 100000, "term": 48, "product": "car", "asset_unknown": True}),
        ("say", "בעצם אני רוצה רק 80 אלף"), ("say", "אני רוצה לפרוס את זה ל־60 תשלומים"),
        ("say", "אני רוצה לפרוס את זה ל־84 תשלומים"), ("say", "120 אלף")],
    "reverse_target": PERSONAL + [
        ("say", "רכישת רכב"), ("confirm", {"amount": 100000, "term": 48, "product": "car", "asset_unknown": True}),
        ("say", "אני מרוויח 12 אלף נטו, ואני לא רוצה לעבור החזר של 2,500."),
        ("say", "יש לי הלוואה קיימת של 1,000 ש\"ח בחודש"), ("say", "אני רוצה לשלם עד 2,000 בחודש"),
        ("say", "אני רוצה לשלם עד 1,200 בחודש"), ("action",), ("say", "מה ההחזר ביחס להכנסה שלי?")],
    "happy_event_switching": PERSONAL + [
        ("say", "חתונה"), ("confirm", {"amount": 120000, "term": 60}), ("say", "הלוואה לכל מטרה"),
        ("confirm", {"amount": 120000, "term": 60, "product": "all_purpose"}), ("say", "בעצם תעשה לי הלוואה ברגע"),
        ("say", "הלוואה לשמחות")],
    "instant_deferral": [
        ("say", "הלוואה ברגע"), ("say", "דנה רז"), ("say", "DEMO-ID-202"), ("say", "חופשה"),
        ("say", "אני רוצה לדחות את התשלום הראשון ב־3 חודשים"),
        ("confirm", {"amount": 50000, "term": 36, "deferral_months": 3, "deferral_policy": "interest_only",
                     "product": "express"}),
        ("save", {"amount": 50000, "term": 36, "deferral_months": 9, "product": "express"})],
    "free_text_indication_edits": PERSONAL + [
        ("say", "אני שכירה, מרוויחה 16 אלף נטו, רוצה הלוואה של 80 אלף לרכב לחמש שנים."),
        ("say", "איך הגעת לסכום שהצגת לי?"), ("say", "בעצם אני רוצה 120 אלף במקום 80."), ("edit", "income"),
        ("cancel",), ("edit", "income"), ("say", "אני לא שכיר, אני רק עצמאי."), ("say", "למה אני צריך גם אישור עוסק?"),
        ("pick", "registration", "vat_exempt"), ("say", "15 אלף"), ("pick", "co_borrower", True), ("say", "יוסי ברק"),
        ("say", "DEMO-ID-203"), ("pick", "co_income", ["salaried"]), ("say", "9000"), ("say", "לא")],
    "side_jobs_renovation": PERSONAL + [
        ("say", "שיפוץ"), ("save", {"amount": 60000, "term": 36, "product": "all_purpose"}), ("say", "מאשר"),
        ("say", "אני עובד פה ושם, לפעמים כשכיר ולפעמים עושה עבודות מהצד. לא ממש יודע איך להגדיר את עצמי."),
        ("pick", "income", ["salaried", "self_employed"]), ("pick", "registration", "vat_registered"), ("say", "10 אלף נטו"),
        ("say", "לא, רק אני"), ("edit", "simulation"), ("confirm", {"amount": 50000, "term": 36, "product": "all_purpose"}),
        ("open_case",)],
    "off_topic_and_gross": [
        ("say", "אתה מבטיח לי שהבנק יאשר את ההלוואה?"), ("say", "מה מזג האוויר בתל אביב מחר?"),
        ("say", "אני רוצה הלוואה של 300 אלף שקל."), ("say", "אני מרוויח 19 אלף ברוטו, אפשר לחשב לי לפי זה?"),
        ("say", "בלה בלה"), ("say", "הלוואה פרטית"), ("say", "קוראים לי אבי"), ("say", "אבי כהן"), ("say", "123")],
    "business_vat_exempt": [
        ("pick", "loan_type", "business"), ("pick", "business_form", "vat_exempt"), ("say", "שרון לוי"),
        ("say", "DEMO-ID-205"), ("say", "אני רק שכיר"), ("say", "ציוד לעסק"),
        ("confirm", {"amount": 40000, "term": 24}), ("say", "8000 נטו"), ("say", "לא"), ("open_case",)],
    "business_vat_registered_text": [
        ("say", "אני צריך הלוואה לעסק שלי, אני עוסק מורשה"), ("say", "אני רק שכיר"), ("action",)],
    "company": [
        ("pick", "loan_type", "business"), ("pick", "business_form", "company"), ("say", "מיזוג בעמ"),
        ("say", "גלעד ששון"), ("say", "DEMO-ID-204"), ("pick", "company_purpose", "business_equipment"),
        ("confirm", {"amount": 300000, "term": 60}), ("open_case",)],
}


@pytest.mark.parametrize("name", sorted(JOURNEYS))
def test_hebrew_chat_journey_is_unchanged(name):
    j = Journey()
    steps = j.run(JOURNEYS[name])
    check(f"chat_v2_{name}", steps, tuple(x for x in j.literals if x))


def test_hebrew_classic_questionnaire_is_unchanged():
    c = TestClient(app)
    steps = [c.post("/api/demo/onboarding").json()]
    draft = steps[0]["draft_id"]
    for q, v in [("entity", "individual"), ("name", {"first": "רון", "last": "גל"}), ("net", "abc"), ("national_id", "DEMO-ID-206"), ("purpose", "car"),
                 ("amount", 70000), ("payments", 48), ("income", ["salaried"]), ("net", 11000), ("co_borrower", False),
                 ("accounts", 1), ("amount", 5)]:
        r = c.post(f"/api/demo/onboarding/{draft}/answers", json={"question_id": q, "value": v})
        steps.append({"answer": [q, v], "status": r.status_code, "body": r.json()})
    r = c.post(f"/api/demo/onboarding/{draft}/confirm")
    steps.append({"confirm": r.status_code, "body": r.json()})
    check("chat_v1_classic", steps)
