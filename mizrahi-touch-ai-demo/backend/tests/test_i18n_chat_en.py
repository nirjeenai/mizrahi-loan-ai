"""The conversational questionnaire in English (i18n/chat_en, workflow/onboarding_nlu_en).

- The Hebrew is untouched: every recorded Hebrew journey (tests/golden/chat_v2_*.json), run again with `X-MZ-Lang: he`
  or `en`, gives the golden back byte for byte once the English siblings and the message's `lang` are removed.
- Every English rendering is English. The only Hebrew allowed inside it is what the customer typed (a name, a company).
- An English session typed in English records the same answers, simulation and documents as the Hebrew journey: the
  phrase shim feeds the same tested parser, and the figures come from the same engine.
- Without the header nothing is stored or shown in English."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.policy import store
from app.workflow import onboarding_nlu_en as nlu_en

from .golden_util import check
from .test_golden_hebrew_chat import JOURNEYS, Journey

HEBREW = re.compile(r"[֐-׿]")
ADDED = re.compile(r"_en$")
TYPED_HEBREW = ("מיכל", "ברק", "דנה", "רז", "יוסי", "שרון", "לוי", "מיזוג בעמ", "גלעד", "ששון", "אבי", "כהן")


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


def strip(v):
    if isinstance(v, dict):
        return {k: strip(x) for k, x in v.items() if not ADDED.search(k) and k != "lang"}
    if isinstance(v, list):
        return [strip(x) for x in v]
    return v


def english(v, path=""):
    if isinstance(v, dict):
        for k, x in v.items():
            if k.endswith("_en"):
                yield from ((f"{path}.{k}", s) for s in (x if isinstance(x, list) else [x]) if isinstance(s, str))
            yield from english(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from english(x, f"{path}[{i}]")


@pytest.mark.parametrize("lang", ["he", "en"])
@pytest.mark.parametrize("name", sorted(JOURNEYS))
def test_hebrew_journey_with_the_language_header_is_the_golden(name, lang):
    j = Journey({"X-MZ-Lang": lang})
    steps = j.run(JOURNEYS[name])
    check(f"chat_v2_{name}", strip(steps), tuple(x for x in j.literals if x))
    for path, text in english(steps):
        for typed in TYPED_HEBREW:
            text = text.replace(typed, "")
        assert not HEBREW.search(text), f"{name} {path}: {text}"
    assistant = [m for m in j.d["messages"] if m["role"] == "assistant"]
    assert assistant and all(m.get("text_en") for m in assistant), name
    assert all(m.get("lang") == lang for m in j.d["messages"])


def test_without_the_header_the_english_stays_stored_but_is_not_shown():
    j = Journey({"X-MZ-Lang": "en"})
    j.run(JOURNEYS["car_salaried_sim"][:5])
    plain = TestClient(app).get(f"/api/demo/onboarding/{j.id}/v2").json()
    assert not list(english(plain)) and all("lang" not in m for m in plain["messages"])
    assert plain == strip(TestClient(app, headers={"X-MZ-Lang": "he"}).get(f"/api/demo/onboarding/{j.id}/v2").json())


EN_CAR = [("pick", "loan_type", "personal"), ("say", "Michal Barak"), ("say", "DEMO-ID-201"), ("say", "I want to buy a car"),
          ("confirm", {"amount": 170000, "term": 48, "asset_price": 200000, "product": "car"}),
          ("pick", "income", ["salaried"]), ("say", "I earn 12k net a month"), ("say", "why do you need this?"),
          ("say", "no, just me")]
HE_CAR = [("pick", "loan_type", "personal"), ("say", "מיכל ברק"), ("say", "DEMO-ID-201"), ("say", "רכישת רכב"),
          ("confirm", {"amount": 170000, "term": 48, "asset_price": 200000, "product": "car"}),
          ("pick", "income", ["salaried"]), ("say", "12 אלף נטו"), ("say", "למה צריך את זה?"), ("say", "לא, רק אני")]


def _outcome(j: Journey) -> dict:
    s = j.d["summary"]
    return {"lines": [(l["question_id"], l["value_he"]) for l in s["lines"] if l["question_id"] != "name"],
            "requirements": [r["code"] for r in s["requirements"]], "simulation": strip(j.d["simulation"])}


def test_an_english_session_typed_in_english_records_what_the_hebrew_one_does():
    en_j, he_j = Journey({"X-MZ-Lang": "en"}), Journey()
    en_j.run(EN_CAR)
    he_j.run(HE_CAR)
    assert _outcome(en_j) == _outcome(he_j)
    assert en_j.d["summary"]["lines"][1]["value_he"] == "Michal Barak"          # typed in English, stored as typed
    texts = [m["text_en"] for m in en_j.d["messages"] if m["role"] == "assistant"]
    assert "Great, I noted ₪170,000 over 48 payments, car loan: an estimated monthly repayment of about ₪3,992." in texts[5]
    assert "Each co-borrower needs their own documents" in texts[8]
    assert texts[-1].startswith("Fine, the application is in your name only. We're done!")
    users = [m for m in en_j.d["messages"] if m["role"] == "user"]
    assert users[3]["text_he"] == "I want to buy a car" and "text_en" not in users[3]       # the customer's own words
    assert users[0]["text_he"] == "הלוואה פרטית" and users[0]["text_en"] == "Personal loan"
    s = en_j.d["summary"]
    assert [r["title_en"] for r in s["requirements"]] == [
        "ID card — Michal", "Last 3 payslips — Michal", "Bank statements for the last 3 months — Current account 1 (Michal)",
        "Proof of the loan's purpose — Buying a car"]


@pytest.mark.parametrize("text,pending,expected", [
    ("I earn 12k net a month", "net", {"net": 12000}),
    ("12,000 net", "net", {"net": 12000}),
    ("about 1,250,000", "amount", {"amount": 1250000}),
    ("80 thousand", "amount", {"amount": 80000}),
    ("I'm salaried", "income", {"income": ["salaried"]}),
    ("both salary and business", "income", {"income": ["salaried", "self_employed"]}),
    ("no, just me", "co_borrower", {"co_borrower": "no"}),
    ("a personal loan", "loan_type", {"loan_type": "personal"}),
    ("renovation", "purpose", {"purpose": "renovation"}),
    ("60 payments", "payments", {"payments": 60}),
    ("five years", "payments", {"payments": 60}),
    ("one hundred thousand", "amount", {"amount": 100000}),
    ("two hundred thousand", "amount", {"amount": 200000}),
    ("one hundred and twenty thousand", "amount", {"amount": 120000}),
    ("one hundred twenty payments", "payments", {"payments": 120}),
    ("forty-eight payments", "payments", {"payments": 48}),
    ("both", "income", {"income": ["salaried", "self_employed"]}),
])
def test_the_english_shim_feeds_the_hebrew_parser(text, pending, expected):
    from app.workflow import onboarding_nlu as nlu
    u = nlu.understand(nlu_en.to_parser(text, pending), {"entity": "individual"}, pending)
    for k, v in expected.items():
        assert u["values"].get(k) == v, (text, u)


def test_the_shim_guesses_nothing():
    from app.workflow import onboarding_nlu as nlu
    for text, pending in [("five five", "amount"), ("both of us", "co_borrower"), ("that is correct", "co_borrower")]:
        u = nlu.understand(nlu_en.to_parser(text, pending), {"entity": "individual"}, pending)
        assert "amount" not in u["values"] and "income" not in u["values"] and not u["corrections"], (text, u)


def test_a_label_the_server_did_not_offer_is_not_echoed():
    j = Journey({"X-MZ-Lang": "en"})
    j.run(P_EN + [("say", "buying a car")])
    j.turn({"text": "למה צריך את זה?", "label_en": "Something the client made up"})
    assert "text_en" not in j.d["messages"][-2]
    j.turn({"question_id": "income", "value": ["salaried"], "label_he": "משכורת (שכיר/ה)", "label_en": "<b>forged</b>"})
    assert j.d["messages"][-2]["text_en"] == "Income from a salary"            # the server's own wording instead


def test_the_shim_never_rewrites_hebrew_or_a_name():
    assert nlu_en.to_parser("12 אלף נטו", "net") == "12 אלף נטו"
    assert nlu_en.to_parser("My name is Rose Price", "name") == "Rose Price"


def test_english_validation_messages():
    j = Journey({"X-MZ-Lang": "en"})
    j.run([("pick", "loan_type", "personal"), ("say", "Michal Barak"), ("say", "123")])
    last = j.d["messages"][-1]
    assert last["text_en"] and not HEBREW.search(last["text_en"]), last
    r = j.c.post(f"/api/demo/onboarding/{j.id}/v2/turn", json={"text": "   "})
    assert r.status_code == 422 and r.json()["detail_en"] == "The message is empty"


P_EN = [("pick", "loan_type", "personal"), ("say", "Michal Barak"), ("say", "DEMO-ID-201")]


def test_english_corrections_targets_deferral_and_gross_reach_the_same_engine():
    j = Journey({"X-MZ-Lang": "en"})
    j.run(P_EN + [("say", "buying a car"), ("confirm", {"amount": 100000, "term": 48, "product": "car", "asset_unknown": True}),
                  ("say", "actually I only want 80k"), ("say", "I want to spread it over 60 payments")])
    assert (j.d["simulation"]["confirmed"]["amount"], j.d["simulation"]["confirmed"]["term"]) == (80000, 60)
    j.run([("say", "I earn 12k net, and I don't want to pay more than 2,000")])
    last = j.d["messages"][-1]
    assert "To pay up to ₪2,000 a month on ₪80,000" in last["text_en"] or "already within your target" in last["text_en"], last

    k = Journey({"X-MZ-Lang": "en"})
    k.run([("say", "instant loan"), ("say", "Dana Raz"), ("say", "DEMO-ID-202"), ("say", "a vacation"),
           ("say", "defer the first payment by 3 months"), ("say", "I confirm")])
    assert k.d["simulation"]["confirmed"]["deferral_months"] == 3 and k.d["simulation"]["product_id"] == "express"
    assert k.d["messages"][-1]["text_en"].startswith("Great, I noted ₪50,000 over 36 payments, instant loan")

    g = Journey({"X-MZ-Lang": "en"})
    g.run([("say", "will the bank approve my loan?"), ("say", "I earn 19k gross, can you calculate from that?"), ("say", "hello")])
    texts = [m["text_en"] for m in g.d["messages"] if m["role"] == "assistant"]
    assert texts[1].startswith("I can't promise an approval")
    assert texts[2].startswith("To calculate a preliminary indication I need to know your net income, not your gross.")
    assert texts[3].startswith("Hello!")
    assert g.c.get(f"/api/demo/onboarding/{g.id}").json()["asked"] == []        # nothing was recorded from a gross figure


def test_a_button_that_sends_text_echoes_its_english_label():
    j = Journey({"X-MZ-Lang": "en"})
    j.run(P_EN + [("say", "buying a car")])
    j.turn({"text": "למה צריך את זה?", "label_en": "Why do you need this?"})
    user = j.d["messages"][-2]
    assert (user["text_he"], user["text_en"]) == ("למה צריך את זה?", "Why do you need this?")
