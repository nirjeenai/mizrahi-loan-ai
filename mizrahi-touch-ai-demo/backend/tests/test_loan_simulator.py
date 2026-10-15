"""Loan simulator in the application chat: the deterministic engine (loan_calc), the product registry and its rules
(loan_products), the conversation integration (loan_sim + onboarding_chat through the real routes) and the parity of the
browser port (frontend/src/loanCalc.ts) with the server engine. No model is called; Gemini tests mock the transport."""
from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.llm import gemini as g
from app.main import app
from app.policy import store
from app.workflow import loan_calc as calc, loan_products as lp, loan_sim, onboarding_llm as llm


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


def _sum(rows, k):
    return sum(Decimal(str(r[k])) for r in rows)


# ---------------------------------------------------------------- engine: standard amortization
def test_reference_annuity_100k_48_months_8pct():
    s = calc.schedule(100000, 48, 8)
    assert s["monthly_payment"] == 2441.29
    assert s["total_paid"] == 117182.03 and s["total_interest"] == 17182.03
    assert len(s["rows"]) == 48 and all(r["payment"] == 2441.29 for r in s["rows"][:-1])
    assert s["rows"][-1]["payment"] == 2441.40                       # the last installment reconciles the rounding
    assert _sum(s["rows"], "payment") == Decimal("117182.03") and _sum(s["rows"], "interest") == Decimal("17182.03")
    assert _sum(s["rows"], "principal") == Decimal("100000.00") and s["rows"][-1]["balance"] == 0


def test_zero_interest_divides_the_principal():
    s = calc.schedule(12000, 12, 0)
    assert s["monthly_payment"] == 1000.0 and s["total_interest"] == 0 and s["total_paid"] == 12000.0
    odd = calc.schedule(10000, 3, 0)
    assert [r["payment"] for r in odd["rows"]] == [3333.33, 3333.33, 3333.34]


def test_rate_conventions_nominal_and_effective():
    assert calc.monthly_rate(12) == Decimal("0.01")
    eff = calc.monthly_rate(12, "effective")
    assert abs(float(eff) - 0.0094887929345830) < 1e-15            # (1.12)^(1/12) − 1, not 12% / 12
    assert calc.schedule(100000, 48, 12, convention="effective")["monthly_payment"] < calc.schedule(100000, 48, 12)["monthly_payment"]
    with pytest.raises(calc.CalcError):
        calc.monthly_rate(5, "simple")


@pytest.mark.parametrize("p,n,r", [(5000, 2, 6), (80000, 60, 6), (123457, 71, 7.35), (250000, 120, 11), (99999, 13, 0.5)])
def test_totals_are_exact_to_the_agora(p, n, r):
    s = calc.schedule(p, n, r)
    assert _sum(s["rows"], "payment") == Decimal(str(s["total_paid"]))
    assert _sum(s["rows"], "interest") == Decimal(str(s["total_interest"]))
    assert Decimal(str(s["total_paid"])) - Decimal(str(s["total_interest"])) == Decimal(str(p)).quantize(Decimal("0.01"))


@pytest.mark.parametrize("bad", [dict(principal=0), dict(principal=-5), dict(months=0), dict(months=1.5), dict(months=601),
                                 dict(annual_rate_pct=-1), dict(model="bullet_magic"),
                                 dict(deferral={"months": 3, "policy": "free"}),
                                 dict(deferral={"months": 12, "policy": "capitalized", "term_includes_deferral": True}, months=12),
                                 dict(balloon=100000), dict(rate_changes=[{"from_period": 1, "annual_rate_pct": 9}])])
def test_invalid_inputs_raise_instead_of_guessing(bad):
    args = {"principal": 100000, "months": 12, "annual_rate_pct": 6, **bad}
    with pytest.raises(calc.CalcError):
        calc.schedule(args.pop("principal"), args.pop("months"), args.pop("annual_rate_pct"), **args)


# ---------------------------------------------------------------- engine: V1.1
def test_deferral_policies_are_explicit_and_never_free():
    none = calc.schedule(50000, 36, 6)
    cap = calc.schedule(50000, 36, 6, deferral={"months": 3, "policy": "capitalized"})
    io = calc.schedule(50000, 36, 6, deferral={"months": 3, "policy": "interest_only"})
    acc = calc.schedule(50000, 36, 6, deferral={"months": 3, "policy": "accrued_first_payment"})
    assert none["first_repayment_month"] == "2026-11" and cap["first_repayment_month"] == "2027-02"
    assert cap["periods"] == 39 and [r["payment"] for r in cap["rows"][:3]] == [0, 0, 0]
    assert cap["total_interest"] > none["total_interest"] and cap["monthly_payment"] > none["monthly_payment"]
    assert io["rows"][0]["payment"] == 250.0 and io["monthly_payment"] == none["monthly_payment"]
    assert io["first_payment_month"] == "2026-11"
    assert acc["first_payment"] > acc["monthly_payment"] == none["monthly_payment"]
    assert acc["total_interest"] == io["total_interest"]
    inside = calc.schedule(50000, 36, 6, deferral={"months": 3, "policy": "capitalized", "term_includes_deferral": True})
    assert inside["periods"] == 36 and inside["amortizing_months"] == 33


def test_alternate_repayment_models():
    ep = calc.schedule(100000, 48, 8, model="equal_principal")
    assert ep["max_payment"] == ep["rows"][0]["payment"] == round(100000 / 48 + 100000 * 0.08 / 12, 2)
    assert ep["rows"][-1]["payment"] < ep["rows"][0]["payment"] and ep["total_interest"] < 17182.03
    io = calc.schedule(100000, 12, 6, model="interest_only")
    assert io["rows"][0]["payment"] == 500.0 and io["rows"][-1]["payment"] == 100500.0
    bal = calc.schedule(100000, 48, 8, balloon=30000)
    assert bal["monthly_payment"] < 2441.29 and bal["rows"][-1]["payment"] > 30000 and bal["rows"][-1]["balance"] == 0
    grace = calc.schedule(100000, 48, 8, deferral={"months": 6, "policy": "interest_only", "term_includes_deferral": True})
    assert grace["periods"] == 48 and grace["rows"][0]["payment"] == round(100000 * 0.08 / 12, 2)


def test_variable_rate_path_re_amortizes_from_the_change():
    flat = calc.schedule(100000, 48, 6)
    up = calc.schedule(100000, 48, 6, rate_changes=[{"from_period": 13, "annual_rate_pct": 8}])
    assert up["rows"][11]["payment"] == flat["monthly_payment"] < up["rows"][12]["payment"]
    assert up["total_interest"] > flat["total_interest"] and up["rows"][-1]["balance"] == 0
    assert _sum(up["rows"], "payment") == Decimal(str(up["total_paid"]))


def test_fees_are_separate_from_interest():
    s = calc.schedule(100000, 48, 8, monthly_fee=10, upfront_fee=500)
    assert s["total_interest"] == 17182.03 and s["total_fees"] == 980.0
    assert s["total_cost"] == round(17182.03 + 980, 2) and s["monthly_payment"] == 2451.29
    assert s["total_paid"] == round(117182.03 + 480, 2)              # monthly fees are paid with the installments


# ---------------------------------------------------------------- reverse simulation and personal indicators
def test_target_monthly_payment_search():
    n = calc.term_for_target(100000, 2500, 8, 12, 60)
    assert n == 47 and calc.payment_for(100000, 47, 8) <= 2500 < calc.payment_for(100000, 46, 8)
    assert calc.term_for_target(100000, 1000, 8, 12, 60) is None
    p = calc.principal_for_target(2500, 48, 8)
    assert p == 102000 and calc.payment_for(p, 48, 8) <= 2500 < calc.payment_for(p + 1000, 48, 8)


def test_affordability_is_numbers_only():
    a = calc.affordability(2441.29, 12000, 1000)
    assert a["total_monthly"] == 3441.29 and a["ratio_pct"] == 28.7 and a["remaining"] == 8558.71
    assert "eligible" not in json.dumps(a) and calc.affordability(2441, None) is None
    assert calc.affordability(2441, 12000)["existing_known"] is False


# ---------------------------------------------------------------- product registry and rules
def test_registry_keeps_verified_rules_apart_from_demo_defaults():
    car, happy, express, solar, ap = (lp.product(x) for x in ("car", "happy_event", "express", "solar", "all_purpose"))
    assert car["amount"] == {"max_financing_ratio": 0.85, "ratio_basis": "verified"} and car["term"]["max"] == 60
    assert lp.bounds(car)["amount_max_basis"] == "flow"               # no invented absolute maximum for a car loan
    assert lp.bounds(happy)["amount_max"] == 100000 and happy["term"]["max"] == 84
    assert lp.bounds(express)["amount_max"] == 125000 and (express["term"]["min"], express["term"]["max"]) == (2, 72)
    assert express["features"]["deferral"]["max_months"] == 3 and express["features"]["deferral"]["verified_policy"] is None
    assert lp.bounds(solar)["amount_max"] == 100000 and solar["term"]["max"] == 120 and solar["features"]["variable_rate"]
    assert "max_financing_ratio" not in ap["amount"]                  # the property-secured 70% rule is not applied
    assert all(not p["features"]["fees"] and not p.get("pricing") for p in lp.registry()["products"])


def test_car_financing_ratio_rule():
    car = lp.product("car")
    found = lp.issues(car, 180000, 60, 200000)
    assert [i["code"] for i in found] == ["financing_ratio"] and found[0]["fix"] == 170000 and found[0]["ratio_pct"] == 90.0
    assert "גבוה משיעור המימון במסלול זה" in found[0]["message_he"]
    assert lp.issues(car, 170000, 60, 200000) == [] and lp.issues(car, 180000, 60, None) == []
    assert lp.issues(car, 80000, 72)[0]["code"] == "term_above_max"


def test_rate_source_hierarchy(monkeypatch):
    car = lp.product("car")
    assert lp.rate_for(car)["source"] == "illustrative" and lp.rate_for(car)["annual_rate_pct"] == 6.0
    assert lp.rate_for(car, {"annual_rate_pct": 4.2})["source"] == "bank_quote"
    assert lp.rate_for({**car, "pricing": {"annual_rate_pct": 5.1}})["source"] == "pricing_config"
    assert lp.rate_for(lp.product("company"))["available"] is False
    monkeypatch.setattr(lp, "settings", dataclasses.replace(lp.settings, loan_sim_illustrative_rate=False))
    off = lp.rate_for(car)
    assert off["available"] is False and off["annual_rate_pct"] is None


def test_a_config_change_is_picked_up_without_code(monkeypatch):
    reg = json.loads(lp.PATH.read_text(encoding="utf8"))
    for p in reg["products"]:
        if p["id"] == "happy_event":
            p["amount"]["max"], p["term"]["max"] = 80000, 60
    monkeypatch.setattr(lp, "registry", lambda: reg)
    happy = lp.product("happy_event")
    assert lp.bounds(happy)["amount_max"] == 80000 and lp.issues(happy, 90000, 72)[0]["code"] == "amount_above_max"


# ---------------------------------------------------------------- conversation integration
class Chat:
    def __init__(self):
        self.c = TestClient(app)
        self.d = self.c.post("/api/demo/onboarding/v2").json()
        self.id = self.d["draft_id"]

    def turn(self, body: dict) -> dict:
        r = self.c.post(f"/api/demo/onboarding/{self.id}/v2/turn", json=body)
        assert r.status_code == 200, r.text
        self.d = r.json()
        return self.d

    def say(self, text):
        return self.turn({"text": text})

    def pick(self, qid, value):
        return self.turn({"question_id": qid, "value": value})

    def confirm(self, **sim):
        return self.turn({"action": "simulate_confirm", "simulation": sim})

    def save(self, **draft):
        r = self.c.post(f"/api/demo/onboarding/{self.id}/v2/simulation", json={"draft": draft})
        assert r.status_code == 200, r.text
        return r.json()["simulation"]

    @property
    def last(self):
        return self.d["messages"][-1]

    @property
    def pending(self):
        return self.d["pending"] and self.d["pending"]["question_id"]

    def answers(self):
        return {a["question_id"]: a["answer"] for a in self.c.get(f"/api/demo/onboarding/{self.id}").json()["asked"]}


def to_purpose(ch: Chat, purpose="רכישת רכב"):
    ch.pick("loan_type", "personal")
    ch.say("ניר נקש")
    ch.say("DEMO-ID-201")
    ch.say(purpose)


def test_the_purpose_opens_the_simulator_instead_of_the_amount_question():
    ch = Chat()
    to_purpose(ch)
    assert ch.d["pending"]["kind"] == "simulator" and ch.pending == "amount"
    assert ch.last["simulator"]["live"] and ch.last["simulator"]["status"] == "pending"
    assert ch.last["text_he"].startswith("מעולה 🚗") and "איזה סכום" not in ch.last["text_he"]
    sim = ch.d["simulation"]
    assert sim["product_id"] == "car" and [c["id"] for c in sim["candidates"]] == ["car", "electric_car", "express", "all_purpose"]
    assert sim["draft_eval"]["rate"]["source"] == "illustrative" and sim["draft_eval"]["result"]["monthly_payment"] == 1546.62
    assert ch.d["pending"]["replies"] and "amount" not in ch.answers()          # nothing is recorded by showing the card


def test_slider_moves_are_saved_without_a_message_and_survive_a_reload():
    ch = Chat()
    to_purpose(ch)
    n = len(ch.d["messages"])
    sim = ch.save(amount=100000, term=48, product="electric_car")
    assert sim["draft"]["amount"] == 100000 and sim["draft_eval"]["result"]["monthly_payment"] == 2348.5
    again = ch.c.get(f"/api/demo/onboarding/{ch.id}/v2").json()
    assert len(again["messages"]) == n and again["simulation"]["product_id"] == "electric_car"
    assert again["simulation"]["draft"]["term"] == 48 and "amount" not in ch.answers()


def test_confirmation_records_both_answers_once_and_the_flow_continues():
    ch = Chat()
    to_purpose(ch)
    ch.confirm(amount=180000, term=60, asset_price=200000, product="car")
    assert "amount" not in ch.answers() and ch.pending == "amount"                     # 90% financing is refused
    assert "גבוה משיעור המימון" in ch.last["text_he"] and ch.last["actions"][0]["simulation"] == {"amount": 170000}
    ch.confirm(amount=170000, term=48, asset_price=200000, product="car")
    assert ch.answers()["amount"] == 170000 and ch.answers()["payments"] == 48 and ch.pending == "income"
    assert "3,992" in ch.last["text_he"] and ch.last["simulator"]["status"] == "confirmed"
    asked = [m.get("question_id") for m in ch.d["messages"] if m["role"] == "assistant"]
    assert "payments" not in asked and asked.count("amount") <= 2                       # no separate term question
    ch.pick("income", ["salaried"])
    ch.say("12 אלף נטו")
    ch.say("לא, רק אני")
    assert ch.pending is None
    line = next(l for l in ch.d["summary"]["lines"] if l["question_id"] == "simulation")
    assert "הלוואה לרכב" in line["value_he"] and "200,000" in line["value_he"]
    out = ch.c.post(f"/api/demo/onboarding/{ch.id}/v2/confirm").json()
    app_row = json.loads(db.one("SELECT application FROM demo_applications WHERE case_id=?", (out["case_id"],))["application"])
    assert app_row["loan"]["requested_amount_ils"] == 170000 and app_row["loan"]["payments"] == 48
    sim = app_row["loan"]["simulation"]
    assert sim["candidate_product"] == "car" and sim["product_selected_by_bank"] is False and sim["rate_source"] == "illustrative"
    assert sim["asset_price_ils"] == 200000 and sim["asset_price_source"] == "CUSTOMER_DECLARED"
    staff = TestClient(app)
    staff.post("/api/session/demo/staff", json={})
    ws = staff.get(f"/api/banker/cases/{out['case_id']}/workspace")
    body = json.dumps(ws.json(), ensure_ascii=False)
    assert ws.status_code == 200 and ("170,000" in body or "170000" in body)          # the banker sees the confirmed amount


def test_the_car_needs_a_price_or_an_explicit_unknown():
    ch = Chat()
    to_purpose(ch)
    ch.confirm(amount=80000, term=60, product="car")
    assert "amount" not in ch.answers() and "מחיר הרכב" in ch.last["text_he"]
    ch.confirm(amount=80000, term=60, product="car", asset_unknown=True)
    assert ch.answers()["amount"] == 80000


def test_conversation_updates_an_existing_scenario():
    ch = Chat()
    to_purpose(ch)
    ch.confirm(amount=100000, term=48, product="car", asset_unknown=True)
    ch.say("בעצם אני רוצה רק 80 אלף")
    assert ch.answers()["amount"] == 80000 and ch.answers()["payments"] == 48
    assert "1,879" in ch.last["text_he"] and ch.last["simulator"]["amount"] == 80000
    ch.say("אני רוצה לפרוס את זה ל־60 תשלומים")
    assert ch.answers()["payments"] == 60 and ch.answers()["amount"] == 80000 and "מה נכון" not in ch.last["text_he"]
    ch.say("אני רוצה לפרוס את זה ל־84 תשלומים")
    assert ch.answers()["payments"] == 60 and "עד 60 חודשים" in ch.last["text_he"]
    labels = [a["label_he"] for a in ch.last["actions"]]
    assert labels[0] == "60 תשלומים" and "לבדוק הלוואה לכל מטרה" in labels
    ch.say("120 אלף")
    assert ch.answers()["amount"] == 80000 and ch.last["text_he"].endswith("?")      # a bare number is asked about, not applied


def test_personal_insights_and_reverse_simulation():
    ch = Chat()
    to_purpose(ch)
    ch.confirm(amount=100000, term=48, product="car", asset_unknown=True)
    ch.say("אני מרוויח 12 אלף נטו, ואני לא רוצה לעבור החזר של 2,500.")
    a = ch.answers()
    assert a["net"] == 12000 and a["amount"] == 100000 and a["payments"] == 48       # the target changed nothing
    sim = ch.d["simulation"]
    assert sim["context"]["target_monthly"] == 2500 and sim["confirmed_eval"]["target"]["status"] == "met"
    ch.say("יש לי הלוואה קיימת של 1,000 ש\"ח בחודש")
    af = ch.d["simulation"]["confirmed_eval"]["affordability"]
    assert af["existing_monthly"] == 1000 and af["ratio_pct"] == calc.ratio_pct(Decimal("2348.50") + 1000, 12000)
    assert "לא בדיקת זכאות" in ch.last["text_he"] and "זכאי" not in ch.last["text_he"].replace("זכאות", "")
    ch.say("אני רוצה לשלם עד 2,000 בחודש")
    t = ch.d["simulation"]["confirmed_eval"]["target"]
    term = calc.term_for_target(100000, 2000, 6, 12, 60)
    assert t["status"] == "term" and t["term"] == term and ch.answers()["payments"] == 48   # suggested, not applied
    assert ch.last["actions"] == [{"label_he": f"לפרוס ל־{term} תשלומים", "question_id": "payments", "value": term}]
    assert "תקופה ארוכה יותר" in ch.last["text_he"]
    ch.say("אני רוצה לשלם עד 1,200 בחודש")
    t = ch.d["simulation"]["confirmed_eval"]["target"]
    assert t["status"] == "amount" and calc.payment_for(t["amount"], 60, 6) <= 1200
    ch.turn({"action": "simulate_apply", "simulation": ch.last["actions"][0]["simulation"], "label_he": "x"})
    assert ch.answers()["amount"] == t["amount"] and ch.answers()["payments"] == 60


def test_product_switching_revalidates_and_keeps_valid_values():
    ch = Chat()
    to_purpose(ch, "חתונה")
    assert ch.d["simulation"]["product_id"] == "happy_event" and ch.last["text_he"].startswith("מזל טוב! 🎉")
    ch.confirm(amount=120000, term=60)
    assert "amount" not in ch.answers() and "עד 100,000" in ch.last["text_he"]
    ch.say("הלוואה לכל מטרה")
    assert ch.d["simulation"]["product_id"] == "all_purpose" and ch.d["simulation"]["draft"]["amount"] == 120000
    ch.confirm(amount=120000, term=60, product="all_purpose")
    assert ch.answers()["amount"] == 120000
    ch.say("בעצם תעשה לי הלוואה ברגע")
    assert ch.d["simulation"]["product_id"] == "express" and ch.answers()["amount"] == 120000
    ch.say("הלוואה לשמחות")
    assert ch.d["simulation"]["status"] == "pending" and ch.d["simulation"]["editing"]   # 120,000 > 100,000: re-confirm
    assert "עד 100,000" in ch.last["text_he"]


def test_instant_loan_with_a_deferral():
    ch = Chat()
    ch.say("הלוואה ברגע")
    assert ch.answers()["entity"] == "individual"
    ch.say("דנה רז")
    ch.say("DEMO-ID-202")
    ch.say("חופשה")
    assert ch.d["simulation"]["product_id"] == "express" and ch.last["text_he"].startswith("הלוואה ברגע")
    ch.say("אני רוצה לדחות את התשלום הראשון ב־3 חודשים")
    r = ch.d["simulation"]["draft_eval"]["result"]
    assert ch.d["simulation"]["draft"]["deferral_months"] == 3 and r["first_repayment_month"] == "2027-02"
    assert "לא חישוב רשמי" in ch.last["text_he"] and "amount" not in ch.answers()
    ch.confirm(amount=50000, term=36, deferral_months=3, deferral_policy="interest_only", product="express")
    c = ch.d["simulation"]["confirmed_eval"]["result"]
    assert ch.answers()["payments"] == 36 and c["first_payment"] == 250.0 and c["deferral_months"] == 3
    ch.save(amount=50000, term=36, deferral_months=9, product="express")
    assert ch.d and lp.issues(lp.product("express"), 50000, 36, None, 9)[0]["code"] == "deferral_not_supported"


def test_company_path_selects_amount_and_term_without_a_repayment_figure():
    ch = Chat()
    ch.pick("loan_type", "business")
    ch.pick("business_form", "company")
    ch.say("מיזוג בעמ")
    ch.say("גלעד ששון")
    ch.say("DEMO-ID-204")
    ch.pick("company_purpose", "business_equipment")
    sim = ch.d["simulation"]
    assert ch.pending == "business_amount" and sim["draft_eval"]["result"] is None and not sim["draft_eval"]["rate"]["available"]
    ch.confirm(amount=300000, term=60)
    assert ch.answers()["business_amount"] == 300000 and ch.pending is None
    assert "₪ בחודש" not in ch.last["text_he"] and "החזר חודשי" not in ch.last["text_he"]


def test_the_model_cannot_turn_a_target_into_an_amount_or_income(monkeypatch):
    ch = Chat()
    to_purpose(ch)
    monkeypatch.setattr(llm, "settings", dataclasses.replace(llm.settings, onboarding_llm=True, gemini_api_key="k"))
    answers = [{"facts": [{"field": "net", "value": "2500", "kind": "extra", "certain": True},
                          {"field": "amount", "value": "2500", "kind": "answer", "certain": True}],
                "unclear": [], "topics": [], "gross_income_mentioned": False, "reply_he": "", "next_field": ""}]
    monkeypatch.setattr(g, "generate", lambda *a, **k: {"candidates": [{"content": {"parts": [{"text": json.dumps(answers.pop(0))}]}}]})
    ch.say("אני לא רוצה לעבור החזר של 2,500 בחודש")
    assert "net" not in ch.answers() and "amount" not in ch.answers()
    assert ch.d["simulation"]["context"]["target_monthly"] == 2500 and ch.last["engine"] == "rules"


def test_text_confirmation_and_summary_edit_reopen_the_card():
    ch = Chat()
    to_purpose(ch, "שיפוץ")
    ch.save(amount=60000, term=36, product="all_purpose")
    ch.say("מאשר")
    assert ch.answers()["amount"] == 60000 and ch.answers()["payments"] == 36
    ch.pick("income", ["salaried"])
    ch.say("10 אלף נטו")
    ch.say("לא, רק אני")
    assert ch.pending is None
    ch.turn({"question_id": "simulation", "action": "edit"})
    assert ch.d["pending"]["kind"] == "simulator" and ch.d["simulation"]["editing"] and ch.last["simulator"]["live"]
    ch.confirm(amount=50000, term=36, product="all_purpose")
    assert ch.answers()["amount"] == 50000 and ch.pending is None


def test_understanding_keeps_scenario_numbers_out_of_the_questionnaire():
    a = {"entity": "individual", "purpose": "car"}
    conv = {"loan": {"type": "personal"}}
    u = loan_sim.understand("אני מרוויח 12 אלף נטו, ואני לא רוצה לעבור החזר של 2,500.", conv, a, "income")
    assert u["target"] == 2500 and "2,500" not in u["masked"] and "12" in u["masked"]
    u = loan_sim.understand("הרכב עולה 200 אלף ואני רוצה 180 אלף", conv, a, "amount")
    assert u["asset_price"] == 200000 and "180" in u["masked"]
    assert loan_sim.understand("יש לי הלוואה של 1,000 בחודש", conv, a, None)["obligations"] == 1000
    assert "obligations" not in loan_sim.understand("אני רוצה הלוואה של 80 אלף", conv, a, None)
    assert loan_sim.understand("אין לי הלוואות", conv, a, None)["obligations"] == 0
    assert "target" not in loan_sim.understand("עד 60 תשלומים", conv, a, None)


# ---------------------------------------------------------------- browser port parity
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@pytest.mark.skipif(not shutil.which("node") or not (FRONTEND / "node_modules" / ".bin" / "tsc").exists(),
                    reason="node or the frontend's TypeScript compiler is not installed")
def test_browser_engine_matches_the_server(tmp_path):
    subprocess.run([str(FRONTEND / "node_modules" / ".bin" / "tsc"), "--outDir", str(tmp_path), "--module", "es2020",
                    "--target", "es2020", "--skipLibCheck", str(FRONTEND / "src" / "loanCalc.ts")], check=True, cwd=FRONTEND)
    (tmp_path / "package.json").write_text('{"type": "module"}')
    cases = [(100000, 48, 8, "annuity", None, []), (80000, 60, 6, "annuity", None, []), (123457, 71, 7.35, "annuity", None, []),
             (50000, 36, 6, "annuity", {"months": 3, "policy": "capitalized"}, []),
             (50000, 36, 6, "annuity", {"months": 2, "policy": "interest_only"}, []),
             (50000, 36, 6, "annuity", {"months": 3, "policy": "accrued_first_payment"}, []),
             (100000, 48, 8, "equal_principal", None, []), (60000, 96, 6, "annuity", None, [{"from_period": 13, "annual_rate_pct": 8}]),
             (12000, 12, 0, "annuity", None, []), (250000, 120, 11.25, "annuity", None, [])]
    script = tmp_path / "run.mjs"
    script.write_text("import { schedule, affordability } from './loanCalc.js';\n"
                      f"const cases = {json.dumps(cases)};\n"
                      "const out = cases.map(([p, n, r, model, d, ch]) => { const s = schedule(p, n, r, { model, deferral: d && { ...d, term_includes_deferral: false }, rateChanges: ch, startMonth: '2026-11' });"
                      " return [s.monthly_payment, s.total_paid, s.total_interest, s.first_payment, s.last_payment, s.rows.map(x => x.payment)]; });\n"
                      "out.push(affordability(2441.29, 12000, 1000));\n"
                      "console.log(JSON.stringify(out));\n")
    js = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    for (p, n, r, model, d, ch), got in zip(cases, js):
        s = calc.schedule(p, n, r, model=model, deferral=d, rate_changes=ch)
        assert got[:5] == [s["monthly_payment"], s["total_paid"], s["total_interest"], s["first_payment"], s["last_payment"]], (p, n, r, model, d)
        assert got[5] == [x["payment"] for x in s["rows"]], (p, n, r, model, d)
    assert js[-1] == calc.affordability(2441.29, 12000, 1000)
