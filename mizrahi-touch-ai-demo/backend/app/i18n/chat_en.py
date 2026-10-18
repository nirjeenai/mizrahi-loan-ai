"""English of the conversational questionnaire (workflow/onboarding_chat.py and workflow/loan_sim.py).

Every function here mirrors one Hebrew sentence-builder and takes the same inputs; none of them changes the draft, the
answers or the scenario. `onboarding_chat.turn` composes its Hebrew reply exactly as before, records what it already knew
(the changes, refusals, conflicts, unclear fields, topics, scenario events) and then calls `compose` for the English
wording of the same outcome, stored beside it as `text_en`. Figures come from the same engine calls, so the English and
the Hebrew always state the same numbers."""
from __future__ import annotations

from typing import Any, Optional

from ..config import settings
from ..policy import store
from ..review import deterministic as det
from ..review import rubrics
from ..workflow import indication, loan_products as lp, loan_sim as LS, onboarding
from . import en


def ils(n: Any) -> str:
    return f"₪{int(round(float(n))):,}"


def and_(items: list[str]) -> str:
    return en.join([i for i in items if i])


FORM = {"vat_exempt": "exempt dealer (Osek Patur)", "vat_registered": "licensed dealer (Osek Murshe)", "company": "limited company"}
A_FORM = {"vat_exempt": "an exempt dealer (Osek Patur)", "vat_registered": "a licensed dealer (Osek Murshe)",
          "company": "a limited company"}
KEEP_CASE = {"name", "co_name", "signatory", "company_name", "national_id", "co_national_id", "signatory_id"}
FORM_TITLE = {"vat_exempt": "Exempt dealer (Osek Patur)", "vat_registered": "Licensed dealer (Osek Murshe)", "company": "Limited company"}
FIELD = {"loan_type": "the loan type", "business_form": "the business type", "entity": "the application type", "name": "the name",
         "national_id": "the ID number", "purpose": "the loan's purpose", "amount": "the amount", "payments": "the number of payments",
         "income": "the income source", "registration": "the dealer type", "net": "the monthly income",
         "co_borrower": "the co-borrower", "co_name": "the co-borrower's name", "co_national_id": "the co-borrower's ID number",
         "co_income": "the co-borrower's income source", "co_registration": "the co-borrower's dealer type",
         "co_net": "the co-borrower's income", "accounts": "the accounts", "company_name": "the company's name",
         "signatory": "the authorized signatory", "signatory_id": "the signatory's ID number",
         "company_purpose": "the financing's purpose", "business_amount": "the financing amount", "simulation": "the simulation"}
STAGES = {"intro": "Getting started", "loan": "Loan details", "profile": "Your profile", "summary": "Summary and confirmation"}
OPENING = ("Hi, I'm Mizrahi-Tefahot's digital assistant. I'm here to help you prepare a loan application. "
           "You can pick an answer or just write to me in your own words.")


def _first(a: dict, key: str = "name") -> str:
    return en.name(((a.get(key) or {}).get("first") or "").strip())


def _full(a: dict, key: str) -> str:
    v = a.get(key) or {}
    return f"{en.name(v.get('first', ''))} {en.name(v.get('last', ''))}".strip()


def purpose(key: Optional[str]) -> str:
    return en.PURPOSES.get(key or "", ("",))[0]


def income(sources: Optional[list[str]], reg: Optional[str] = None) -> str:
    s = sources or []
    biz = f"Business ({FORM[reg]})" if reg in ("vat_exempt", "vat_registered") else "Business"
    if s == ["salaried"]:
        return "Salary"
    if s == ["self_employed"]:
        return biz
    return f"Salary + {biz.lower()}" if s else ""


def _co(a: dict) -> str:
    return _first(a, "co_name") or "the co-borrower"


# ---------------------------------------------------------------- questions, replies, values
def prompt(qid: str, conv: dict, a: dict) -> str:
    from ..workflow import onboarding_chat as C
    if C._sim_question(qid, conv, a):
        return intro(conv, a) if not LS._sim(conv)["shown"] else reprompt()
    first, co = _first(a), _co(a)
    sources = a.get("income") or []
    p = a.get("purpose")
    prompts = {
        "loan_type": "What kind of loan are you interested in?",
        "business_form": "How is the business registered: exempt dealer, licensed dealer or limited company?",
        "name": "What's your name? (first and last name)",
        "national_id": "What's your ID number?",
        "purpose": "What does the business need the financing for?" if C._sole(conv, a) else f"{first + ', ' if first else ''}what's the loan for?",
        "amount": {"car": "How much do you need to finance the car?", "renovation": "How much do you need for the renovation?",
                   "celebration": "How much do you need for the event?"}.get(p or "", "How much would you like to apply for?"),
        "payments": "Over how many payments would you like to spread the repayment?",
        "income": "Where does your income come from today: a salary, a business or both?",
        "registration": "Is your business registered as an exempt dealer or a licensed dealer?",
        "net": ("Roughly how much comes in each month, net, from your salary and business together?" if len(sources) > 1 else
                "Roughly how much does the business leave you each month, net?" if sources == ["self_employed"] else
                "What's your monthly net salary, roughly?") + " (a declaration only; the documents will verify it later)",
        "co_borrower": "Is anyone else signing the loan with you, such as a spouse or partner?",
        "co_name": "What's the co-borrower's name? (first and last name)",
        "co_national_id": f"And what's {co}'s ID number?",
        "co_income": f"Where does {co}'s income come from: a salary, a business or both?",
        "co_registration": f"Is {co}'s business registered as an exempt dealer or a licensed dealer?",
        "co_net": f"And roughly how much comes in to {co} each month, net? (a declaration only)",
        "accounts": f"Do you and {co} share a current account, or does each of you have your own?",
        "company_name": "What's the company's name?",
        "signatory": "Who is the authorized signatory submitting the application? (first and last name)",
        "signatory_id": "What's the authorized signatory's ID number?",
        "company_purpose": f"What does {a.get('company_name') or 'the company'} need the financing for?",
        "business_amount": "How much financing are you asking for?",
    }
    return prompts[qid]


SHORT = {"loan_type": "Is it a personal or a business loan?", "name": "What's your name?",
         "national_id": "What's your ID number?", "amount": "How much do you need?", "payments": "Over how many payments?",
         "income": "Where does your income come from: a salary, a business or both?", "net": "Roughly how much comes in net each month?",
         "co_borrower": "Is there a co-borrower, or is the application in your name only?"}


def short(qid: str, conv: dict, a: dict) -> str:
    from ..workflow import onboarding_chat as C
    if C._sim_question(qid, conv, a):
        return reprompt()
    return SHORT.get(qid) or prompt(qid, conv, a).split(" (")[0]


def option_label(qid: str, value: Any) -> Optional[str]:
    """The English label of a quick reply / questionnaire option (onboarding_chat.*_REPLIES, onboarding.QUESTIONS)."""
    if qid == "loan_type":
        return {"personal": "Personal loan", "business": "Business loan"}.get(value)
    if qid == "business_form":
        return FORM_TITLE.get(value)
    if qid in ("income", "co_income"):
        key = tuple(value) if isinstance(value, list) else (value,)
        return {("salaried",): "Salary (employee)", ("self_employed",): "Business (self-employed)",
                ("salaried", "self_employed"): "Both salary and business"}.get(key)
    if qid == "entity":
        return {"individual": "A personal loan, for me (or for me and a co-borrower)",
                "company": "Financing for a limited company I'm an authorized signatory of"}.get(value)
    if qid in ("purpose", "company_purpose"):
        return purpose(value) or None
    if qid in ("registration", "co_registration"):
        return FORM_TITLE.get(value)
    if qid in ("net", "co_net") and isinstance(value, int):
        return f"About {ils(value)}"
    if qid == "co_borrower":
        return {"yes": "Yes, there's a co-borrower", "no": "No, just me"}.get(value)
    if qid == "accounts":
        return {"joint": "Yes, a joint account for both of us", "separate": "No, each has their own"}.get(value)
    if qid in ("amount", "business_amount") and isinstance(value, int):
        return ils(value)
    if qid == "payments" and isinstance(value, int):
        return f"{value} payments"
    return None


SUGGESTIONS = {"מה ההחזר ביחס להכנסה שלי?": "What's the repayment relative to my income?", "למה צריך את זה?": "Why do you need this?"}


def placeholder(qid: Optional[str]) -> str:
    return {"name": "First and last name", "co_name": "First and last name", "signatory": "First and last name",
            "national_id": "ID number", "co_national_id": "ID number", "signatory_id": "ID number",
            "company_name": "Company name"}.get(qid or "", "You can write here in your own words…")


def value(qid: str, v: Any, a: dict, short: bool = False) -> str:
    if qid == "loan_type":
        return "Personal loan" if v == "personal" else "Business loan"
    if qid == "business_form":
        return FORM_TITLE.get(v, "")
    if qid in ("income", "co_income"):
        reg = a.get("registration" if qid == "income" else "co_registration")
        if short:
            return income(v, reg)
        biz = f"a business ({FORM[reg]})" if reg in ("vat_exempt", "vat_registered") else "a business"
        return ("Income from a salary" if v == ["salaried"] else f"Income from {biz}" if v == ["self_employed"]
                else f"Income from a salary and {biz}")
    if qid in ("net", "co_net"):
        return f"about {ils(v)} net a month"
    if qid in ("amount", "business_amount"):
        return ils(v)
    if qid == "payments":
        return f"{v} payments"
    if qid == "entity":
        return "Personal loan" if v == "individual" else "Company financing"
    if qid == "co_borrower":
        return "with a co-borrower" if v == "yes" else "without a co-borrower"
    if qid in ("purpose", "company_purpose"):
        return purpose(v)
    if qid in ("name", "co_name", "signatory") and isinstance(v, dict):
        return f"{v.get('first', '')} {v.get('last', '')}".strip()
    return option_label(qid, v) or str(v)


# ---------------------------------------------------------------- acknowledgements
def ack(changes: list[tuple[str, Any, Any]], a: dict, conv: dict, skip_new: frozenset = frozenset()) -> str:
    from ..workflow import onboarding_chat as C
    new = [(q, v) for q, old, v in changes if old is None and v is not None and q not in skip_new]
    upd = [(q, old, v) for q, old, v in changes if old is not None and v is not None]
    parts: list[str] = []
    ids = {q for q, _ in new}
    loan = C._loan(conv, a)
    if "loan_type" in ids or "business_form" in ids:
        if loan.get("type") == "personal":
            parts.append("A personal loan — happy to help.")
        elif loan.get("form") == "company":
            parts.append("A business loan for a limited company. That's a limited path handled with a banker, so I'll only "
                         "collect what's needed to get started here.")
        elif loan.get("form"):
            parts.append(f"A business loan as {A_FORM[loan['form']]}: the application will be opened in your name as the "
                         "business owner, with your business documents.")
        else:
            parts.append("A business loan, got it.")
    if "name" in ids:
        parts.append(f"Nice to meet you, {_first(a)}.")
    if "co_name" in ids:
        parts.append(f"Nice to meet {_first(a, 'co_name')} too.")
    skip = {"name", "co_name", "entity", "national_id", "co_national_id", "signatory_id", "registration",
            "co_registration", "loan_type", "business_form"}
    if C._sole(conv, a):
        skip |= {"income"}
    listed = sorted([(q, v) for q, v in new if q not in skip], key=lambda x: C.ORDER.index(x[0]))
    if any(q == "purpose" and v == "car" for q, v in listed) and len(listed) <= 2:
        extra = [value(q, v, a) for q, v in listed if q != "purpose"]
        parts.append("Got it — let's look at financing for the car together" + (f", {and_(extra)}." if extra else "."))
    elif len(listed) >= 2:
        parts.append(ack_many(dict(listed), a))
    elif len(listed) == 1:
        parts.append(ack_one(*listed[0], a))
    income_changed = any(q.endswith("income") for q, _ in listed) or any(q.endswith("income") for q, _, _ in upd)
    if any(q in ("registration", "co_registration") for q, _ in new) and not income_changed and "business_form" not in ids:
        reg = next(v for q, v in new if q in ("registration", "co_registration"))
        parts.append(f"{FORM_TITLE[reg]}, noted.")
    if any(q in ("national_id", "co_national_id", "signatory_id") for q, _ in new) and not parts:
        parts.append("Thanks, noted.")
    for q, old, v in upd:
        if q in ("income", "co_income"):
            reg_q = "registration" if q == "income" else "co_registration"
            more = " I'll ask one more short question to match the documents." if "self_employed" in v and reg_q not in a else ""
            if len(v) > 1:
                parts.append(ack_one(q, v, a))
            else:
                parts.append(f"Updated: {_lv(q, value(q, v, a))} only, instead of {_lv(q, value(q, old, a, short=True))}.{more}")
        elif q not in ("entity", "registration") or not income_changed:
            parts.append(f"I updated {FIELD[q]}: {_lv(q, value(q, v, a, short=True))} instead of "
                         f"{_lv(q, value(q, old, a, short=True))}.")
    return " ".join(parts)


def ack_many(f: dict, a: dict) -> str:
    to = {"car": " for the car", "renovation": " for the renovation", "celebration": " for the event"}.get(f.get("purpose") or "", "")
    loan = (f"financing of {ils(f['amount'])}{to}" if "amount" in f else
            f"financing{to}" if to else purpose(f["purpose"]) if "purpose" in f else "")
    if "payments" in f:
        loan = (loan + " " if loan else "") + f"over {f['payments']} payments"
    inc = ""
    sources = f.get("income")
    if sources:
        inc = ("income from a salary" if sources == ["salaried"] else "income from a business" if sources == ["self_employed"]
               else "two incomes, from a salary and the business")
    if "net" in f:
        inc = (inc + " of" if inc and len(sources or []) < 2 else inc + ", together" if inc else "income of") \
            + f" about {ils(f['net'])} net a month"
    rest = [value(q, v, a) for q, v in f.items() if q not in ("purpose", "amount", "payments", "income", "net")]
    bits = [b for b in [loan, inc] + rest if b]
    out = f"Got it: {and_(bits)}."
    if sources and len(sources) > 1:
        out += " I'll take both incomes into account when we build the application."
    return out


def ack_one(q: str, v: Any, a: dict) -> str:
    co = _co(a)
    if q in ("income", "co_income"):
        reg_q = "registration" if q == "income" else "co_registration"
        reg = {"vat_exempt": ", as an exempt dealer", "vat_registered": ", as a licensed dealer"}.get(a.get(reg_q) or "", "")
        who = "you have" if q == "income" else f"{co} has"
        more = " I'll ask one more short question to match the documents." if "self_employed" in v and reg_q not in a else ""
        if len(v) > 1:
            return f"Got it, {who} two incomes, from a salary and the business{reg}. I'll take both into account.{more}"
        return "Got it, income from a salary." if v == ["salaried"] else f"Got it, income from a business{reg}.{more}"
    if q in ("purpose", "company_purpose"):
        return f"{purpose(v)}, noted."
    if q == "amount":
        return f"{ils(v)}{' to finance the car' if a.get('purpose') == 'car' else ''}, noted."
    if q == "business_amount":
        return f"{ils(v)}, noted."
    if q == "payments":
        return f"{v} payments{f', that is {v // 12} years' if v % 12 == 0 else ''}."
    if q == "net":
        return f"Thanks, I noted about {ils(v)} net a month."
    if q == "co_net":
        return f"Thanks, I noted about {ils(v)} net a month for {co}."
    if q == "co_borrower":
        return "Fine, we'll add a co-borrower to the application." if v == "yes" else "Fine, the application is in your name only."
    if q == "accounts":
        return "A joint account, noted." if v == "joint" else "Separate accounts, noted."
    if q == "company_name":
        return f"{v}, noted."
    return "Thanks, noted."


# ---------------------------------------------------------------- policy-grounded answers
def _req(rid: str) -> tuple[str, str, str, list[str]]:
    return en.REQUIREMENTS.get(rid, ("", "", "", []))


def _label(rid: str) -> str:
    from ..workflow import onboarding_chat as C
    r = C._rule(rid)
    return _req(rid)[0].replace("{months}", str(r.rules.months or 3)) if r else ""


def payslip_months() -> tuple[int, str]:
    from ..workflow import onboarding_chat as C
    r = C._rule("PAYSLIPS")
    count = (r.rules.months if r and r.rules.months else 3)
    payday = rubrics.for_case()["policy"]["payday_day_of_next_month"]
    from datetime import date
    months = det.requested_months(date.fromisoformat(settings.simulation_date), count, payday)
    return count, and_([en.month(m) for m in months])


def why(qid: str, conv: dict, a: dict) -> str:
    pol = store.policy()[0]
    reg = [r for r in pol.document_requirements if r.condition and r.condition.registration]
    exempt = [_req(r.id)[0] for r in reg if "vat_exempt" in r.condition.registration]
    registered = [_req(r.id)[0] for r in reg if "vat_registered" in r.condition.registration]
    p = a.get("purpose") or "car"
    w = {
        "loan_type": "Because personal and business loans follow different paths with different documents.",
        "business_form": ("Because each registration type needs different documents: for an exempt or licensed dealer the "
                          "application is opened in your name with your business documents, and a limited company has a "
                          "separate path handled with a banker."),
        "name": "So I can address you by name and match each document to the right borrower.",
        "national_id": f"The ID number is used to {_lower(_req('ID_CARD')[2])}.",
        "purpose": (f"Each purpose needs a different proof: {_lower(_req('PURPOSE_PROOF')[2])}. For example, for "
                    f"{_lower(purpose(p))}: {_lower(en.PURPOSES.get(p, ('', ''))[1])}."),
        "amount": ("The amount is part of the application, and it also lets me give you a preliminary indication for "
                   "illustration. It doesn't change the document list."),
        "payments": "The number of payments sets the monthly repayment, and so the preliminary indication too.",
        "income": (f"Because the income source affects the documents we'll need: from a salary, {_lower(_label('PAYSLIPS'))}; "
                   f"from a business, {_lower(_label('TAX_ASSESSMENT'))} and proof of the business's registration. Someone with "
                   "both is asked for both kinds."),
        "registration": (f"The VAT registration type decides which business documents are requested: for an exempt dealer, "
                         f"{and_([_lower(x) for x in exempt])}; for a licensed dealer, {and_([_lower(x) for x in registered])}. "
                         f"Both also need {_lower(_label('TAX_ASSESSMENT'))}."),
        "net": ("The declared income is kept as a declaration only, and the banker compares it with the documents. It also "
                "lets me give you a preliminary indication."),
        "co_borrower": ("Each co-borrower needs their own documents — an ID card and income documents — so it's important to "
                        "know this now."),
        "accounts": f"The bank statements are checked for each account. {_req('BANK_STATEMENTS')[2]}.",
        "company_name": "The company path is handled with a banker, and the name appears on all the company's documents.",
        "signatory": "Only an authorized signatory can submit an application on the company's behalf.",
        "signatory_id": f"The ID number is used to {_lower(_req('ID_CARD')[2])}.",
        "company_purpose": "The financing's purpose is part of the application, and the banker reviews it.",
        "business_amount": "The amount is part of the application; there's no automatic indication on the company path.",
    }
    for k in ("co_national_id", "co_income", "co_registration", "co_net"):
        w[k] = w[k[3:]]
    w["co_name"] = w["co_borrower"]
    return w.get(qid) or "This question decides which documents the application will need."


def _lv(qid: str, text: str) -> str:
    """A recorded value in the middle of a sentence: lower case, except names, IDs and company names."""
    return text if qid in KEEP_CASE else _lower(text)


def _lower(s: str) -> str:
    return s[:1].lower() + s[1:] if s and not s[:2].isupper() else s


def why_registration(a: dict, conv: dict) -> str:
    from ..workflow import onboarding_chat as C
    reg = a.get("registration") or (C._loan(conv, a).get("form") if C._sole(conv, a) else None)
    if reg in ("vat_exempt", "vat_registered"):
        rules = [r for r in store.policy()[0].document_requirements
                 if r.condition and r.condition.registration and reg in r.condition.registration]
        if rules:
            return (f"Because you have business income as {A_FORM[reg]}, the policy asks for "
                    f"{and_([_lower(_req(r.id)[0]) for r in rules])}: {_lower(_req(rules[0].id)[2])}.")
    return why("registration", conv, a)


def provisional_documents(a: dict) -> Optional[list[str]]:
    """onboarding_chat._provisional_documents in English: the same preview, worded from the requirement ids."""
    from ..workflow import onboarding_chat as C, requirements
    if a.get("entity") == "individual":
        need = ["income"] + (["registration"] if "self_employed" in (a.get("income") or []) else [])
        if a.get("co_borrower") == "yes":
            need += ["co_income"] + (["co_registration"] if "self_employed" in (a.get("co_income") or []) else [])
        if any(k not in a for k in need):
            return None
        fill = {"name": {"first": "הלקוח", "last": "הלקוח"}, "national_id": "DEMO-ID-000", "purpose": "other",
                "net": 0, "co_borrower": "no", "amount": 5000, "payments": 36,
                "co_name": {"first": "הלווה", "last": "הנוסף"}, "co_national_id": "DEMO-ID-001", "co_net": 0,
                "accounts": "joint"}
    elif a.get("entity") == "company":
        fill = {"company_name": a.get("company_name") or "החברה", "signatory": {"first": "מורשה", "last": "החתימה"},
                "signatory_id": "DEMO-ID-000", "company_purpose": "working_capital", "business_amount": 20000,
                "payments": 36}
    else:
        return None
    case = onboarding.build_case({**fill, **a}, "PREVIEW", "000000000", "PREVIEW")
    reqs, _ = requirements.preview(case)
    labels = [_label(r["requirement_id"]) + (" (for each borrower)" if r["owner_type"] == "applicant" and a.get("co_borrower") == "yes"
                                             and r["requirement_id"] == "ID_CARD" else "") for r in reqs]
    return [x[:1].lower() + x[1:] if not x.startswith("ID") else x for x in dict.fromkeys(labels)]


MISSING = {"amount": "the amount", "payments": "the number of payments", "income": "the income source", "net": "the monthly net income"}


def explain(ind: dict, a: dict) -> str:
    if not ind["available"]:
        if ind["reason"] == "company":
            return "There's no automatic indication on the company path; the application is reviewed with a banker."
        if ind["reason"] == "no_income":
            return "Without a declared monthly income I have no basis for an indication, so I'm not showing a figure."
        return (f"I don't have an indication yet — I still need {and_([MISSING.get(k, k) for k in ind.get('missing', [])])}. "
                "Once I have them, I'll calculate it and explain exactly how.")
    parts = [f"{ils(p['net_ils'])} yours" if p["who"] == "primary" else f"{ils(p['net_ils'])} {_co(a)}'s" for p in ind["net_parts"]]
    inc = f"{ils(ind['declared_net_ils'])} ({' + '.join(parts)})" if len(parts) > 1 else ils(ind["declared_net_ils"])
    ratio = int(round(ind["ratio"] * 100))
    lines = [
        "Here's how I calculated it (general calculation assumptions, not the bank's underwriting rules):",
        f"• The monthly net income you gave: {inc} — a declaration, not yet verified.",
        f"• Up to {ratio}% of it for a monthly repayment → up to about {ils(ind['max_monthly_ils'])} a month."
        + (f" ({ratio}% rather than {int(indication.DEMO_RATIO_SALARIED * 100)}%, because part of the income is from a business.)"
           if ind["business_income"] else ""),
        f"• An illustrative rate of {ind['annual_rate'] * 100:g}% a year and {ind['payments']} payments: on {ils(ind['requested_amount_ils'])} "
        f"the estimated repayment is about {ils(ind['requested_monthly_ils'])} a month.",
        f"• The theoretical ceiling in this formula is about {ils(ind['max_amount_ils'])}"
        + (f" (capped at {ils(ind['cap_ils'])}, the application path's ceiling)" if ind["capped"] else "")
        + " — this is not an approved credit limit.",
    ]
    if ind["co_borrower_pending"]:
        lines.append("• The co-borrower's income isn't included yet.")
    lines.append("I didn't use credit data, bank accounts or obligations — I have no access to them, and they weren't checked.")
    return "\n".join(lines)


def answer(topic: str, q: str, a: dict, conv: dict, pending: Optional[str]) -> str:
    """onboarding_chat._answer in English. Pure: the Hebrew call already made any change the topic implies."""
    from ..workflow import onboarding_chat as C
    ind = C._indication(a)
    if topic == "explain_indication":
        return explain(ind, a)
    if topic == "scenario":
        return scenario_answer(conv, a, pending)
    if topic == "approval":
        return ("I can't promise an approval, but we can check the application and prepare it for review; the bank makes "
                "the decision after reviewing the application and the documents.")
    if topic == "interest":
        return ("The bank sets the actual interest rate only after reviewing the application, and I don't have that figure. "
                f"In the simulation and the preliminary indication I use an illustrative rate of {indication.DEMO_ANNUAL_RATE * 100:g}% only.")
    if topic == "calculate":
        if ind["available"]:
            return "The preliminary indication is already shown in the conversation, and you can ask me how I calculated it."
        if ind["reason"] == "company":
            return "There's no automatic indication on the company path; the application is reviewed with a banker."
        return f"I'll calculate a preliminary indication as soon as I have {and_([MISSING.get(k, k) for k in ind.get('missing') or []]) or 'a few more details'}."
    if topic == "missing_payslip":
        count, months = payslip_months()
        return (f"The policy asks for the last {count} payslips: {months}. If a payslip is missing you can still open the "
                "application and upload what you have; a missing month is flagged, and the banker can ask for it or for an "
                "explanation. A written explanation doesn't replace the payslip, and I can't approve an alternative here.")
    if topic == "why_payslips":
        count, months = payslip_months()
        return (f"Payslips verify salary income. The policy asks for the last {count} payslips: {months}. "
                f"{_req('PAYSLIPS')[2]}.")
    if topic == "why_registration":
        return why_registration(a, conv)
    if topic == "change":
        target = C._change_target(q, conv, a)
        if target and target in C._v2(conv, a):
            return f"Sure. Currently recorded: {value(target, C._v2(conv, a)[target], a)}."
        if target:
            return "We haven't got to that yet — I'll ask about it later."
        return "What would you like to change? You can tap \"Change\" next to any detail in the summary, or write to me, e.g. \"change the amount to 90,000\"."
    if topic == "add_coborrower":
        if a.get("entity") == "company":
            return "A company application has no co-borrower; the authorized signatory submits it."
        if a.get("co_borrower") == "yes":
            return f"We've already added {_co(a)}. This application can include one co-borrower."
        return ("Yes, one co-borrower can be added to the application, such as a spouse or partner. Their documents will be "
                "needed too" + (", and I'll ask about it in the profile step." if a.get("co_borrower") != "no" else "."))
    if topic == "documents":
        docs = provisional_documents(a)
        if docs:
            return f"Based on what you've told me so far, {len(docs)} documents will be needed: {and_(docs)}. I'll show the final list in the summary."
        return "The document list depends on the loan type and the income source; once I know them, I'll show exactly what's needed."
    if topic == "remaining":
        left = [x for x in C._applicable(conv, C._assume(a)) if x not in C._v2(conv, a)]
        if not left:
            return "We've finished the questions; what's left is to review the summary and confirm, then we'll move on to documents."
        stages = [STAGES[sid] for sid, _, qs in C.STAGES if any(x in qs for x in left)]
        return f"{len(left)} short questions are left ({and_([s.lower() for s in stages])}), followed by a summary to confirm."
    if topic == "banker":
        return "I'm a digital assistant, not a banker. Once the application is opened it goes to the banker handling it, and the decisions are made there."
    if topic == "privacy":
        return ("The details you give are used only to prepare the application: your answers decide which documents are "
                "needed, and once the application is opened they go to the banker handling it.")
    if topic == "why_pending" and pending:
        return why(pending, conv, a)
    if topic == "smalltalk":
        return ""
    if topic == "off_topic":
        weather = any(w in q for w in ("מזג אוויר", "מזג האוויר", "תחזית", "גשם"))
        return "I'm focused on your loan application right now, so I can't give " + ("a weather forecast." if weather else "an answer on that.")
    return "I don't have verified information on that, and I don't want to guess."


NOTES = {
    "range_low": lambda n: f"I noted {ils(n['value'])}, the low end of the range you wrote, so as not to overstate the estimate.",
    "conflicting_numbers": lambda n: f"I saw several numbers for {FIELD.get(n['field'], 'the same detail')}; which one is right?",
    "unplaced_number": lambda n: f"I'm not sure what you meant by {n['value']:,} — is it the amount, the income or something else?",
    "ambiguous_purpose": lambda n: "You mentioned more than one purpose; what's the loan's main purpose?",
    "unsupported_income": lambda n: ("This questionnaire can record income from a salary or a business. Another kind of income "
                                     "(such as an allowance or rent) isn't supported yet."),
    "partial_name": lambda n: "I'd also like your last name.",
    "no_income_left": lambda n: "If there's no income from a salary or a business, this questionnaire doesn't support that kind of income yet.",
}


def gross(pending: Optional[str]) -> str:
    return ("To calculate a preliminary indication I need to know your net income, not your gross."
            + (" Roughly how much is it?" if pending in ("net", "co_net") else " We'll get to that later."))


def unclear(field: str, kind: str, conv: dict, a: dict) -> str:
    if field in ("income", "co_income"):
        if kind == "income_side_jobs":
            return ("I understand you sometimes have salaried income and also extra jobs. Are the side jobs done as a "
                    "self-employed business, or are those salaried too?")
        return ("That's fine — it isn't always clear. If you issue an invoice or receipt for the work, it's business income; "
                "if you get a payslip for it, it's salaried income. Which fits you?")
    return {"amount": "Roughly how much would you like to apply for? An estimate is enough.",
            "business_amount": "Roughly how much are you asking for? An estimate is enough.",
            "net": "Roughly how much comes in net each month? An estimate is enough.",
            "co_net": "Roughly how much comes in net to the co-borrower each month?",
            "payments": "Over how many payments would you like to spread it? For example 36, 48 or 60.",
            "loan_type": "Is it a personal or a business loan?",
            "purpose": "What's the loan for — for example a car, a renovation or something else?",
            "name": "I'd like your full name, first and last."}.get(field, f"Could you tell me a bit more about {FIELD.get(field, 'that')}?")


def _error_message(msg: str) -> str:
    """An OnboardingError message (Hebrew) in English, or '' when it is not a known one."""
    return en.error(msg) or ""


def error(qid: str, msg: str, v: Any = None) -> str:
    if qid == "payments":
        lo, hi = onboarding.PAYMENT_BOUNDS
        return f"You can choose between {lo} and {hi} payments. What suits you?"
    if qid in ("amount", "business_amount") and isinstance(v, int):
        lo, hi = onboarding.NUMBER_BOUNDS[qid]
        limit = f"of up to {ils(hi)}" if v > hi else f"of at least {ils(lo)}"
        return f"On this application path you can currently enter an amount {limit}. If that works for you, let's continue with an amount in the supported range."
    if msg == "השאלה אינה רלוונטית לתשובות הקודמות":
        return f"I didn't record {FIELD.get(qid, 'that detail')}; it doesn't fit the current application type."
    lead = "I didn't record the income: " if qid in ("net", "co_net") else ""
    english = _error_message(msg)
    return (lead + english + ".") if english else ""


def not_understood(pending: Optional[str]) -> str:
    from ..workflow import onboarding_chat as C
    if pending is None:
        return "I'm not sure I understood. You can ask to change a detail, e.g. \"change the amount\", or confirm the summary below."
    kind = "choice" if pending in C.LOAN_FIELDS else C.BY_ID[pending][1]
    hint = {"choice": "You can pick one of the options or write in your own words.",
            "multi": "You can pick one of the options or write, e.g. \"I'm salaried\".",
            "number": "You can pick from the options or write a number, e.g. \"80,000\".",
            "name": "I'd like a first and last name, e.g. Michal Barak.",
            "text": "You can write the answer below."}[kind]
    return f"I'm not sure I understood. {hint}"


def indication_sentence(event: Optional[str], snap: Optional[dict], ind: dict) -> str:
    """onboarding_chat._indication_event's sentence for the same event and snapshot."""
    if event in ("new", "updated") and snap:
        req = ils(snap["requested_amount_ils"])
        co = " (based on your income only, until I know the co-borrower's)" if snap["co_borrower_pending"] else ""
        core = (f"your request for {req} looks possible to take forward for an initial review{co}" if snap["within"] else
                f"the amount you asked for ({req}) is higher than the preliminary assessment shows as possible{co}; you can "
                "continue as is, and the bank will review it")
        if event == "updated":
            return f"I updated the indication after the change: {core}."
        return (f"By the way, based on the income you gave and general calculation assumptions, {core}. This is not yet an "
                "eligibility check or an approval from the bank.")
    if event == "withdrawn":
        why_ = ("There's no automatic indication on the company path." if ind.get("reason") == "company" else
                f"I'll come back to it once I have {and_([MISSING.get(k, k) for k in ind.get('missing') or []])}."
                if ind.get("reason") == "missing" else "")
        return f"The earlier indication no longer fits the details, so I removed it. {why_}".strip()
    return ""


SUMMARY_TEXT = {"עדכנתי, הסיכום למטה מעודכן.": "Updated — the summary below is up to date.",
                "סיימנו! ריכזתי למטה את כל הפרטים ואת המסמכים שיידרשו, אפשר לעבור עליהם, לשנות ולאשר. פתיחת הבקשה אינה אישור הלוואה.":
                "We're done! Below are all the details and the documents you'll need — you can review them, change anything "
                "and confirm. Opening the application is not a loan approval."}


def summary_lines(conv: dict, a: dict) -> dict[str, tuple[str, str]]:
    """question_id → (label, value) of onboarding_chat._summary_lines."""
    from ..workflow import onboarding_chat as C
    loan = C._loan(conv, a)
    kind = "Personal loan" if loan.get("type") == "personal" else f"Business loan · {FORM_TITLE.get(loan.get('form'), '')}"
    if a.get("entity") == "company":
        rows = [("Loan type", kind, "loan_type"), ("The company", a["company_name"], "company_name"),
                ("Authorized signatory", _full(a, "signatory"), "signatory"),
                ("Purpose", purpose(a["company_purpose"]), "company_purpose"),
                ("Amount", ils(a["business_amount"]), "business_amount"), ("Payments", f"{a['payments']} payments", "payments")]
    else:
        rows = [("Loan type", kind, "loan_type"), ("Name", _full(a, "name"), "name"), ("ID number", a["national_id"], "national_id"),
                ("Purpose", purpose(a["purpose"]), "purpose"), ("Amount", ils(a["amount"]), "amount"),
                ("Payments", f"{a['payments']} payments", "payments"),
                ("Income", income(a["income"], a.get("registration")), "income"),
                ("Monthly net income (declared)", f"about {ils(a['net'])}", "net")]
        if a.get("co_borrower") == "yes":
            rows += [("Co-borrower", f"{_full(a, 'co_name')} · {income(a['co_income'], a.get('co_registration'))} · about "
                                     f"{ils(a['co_net'])} net", "co_borrower"),
                     ("Current account", "Joint" if a["accounts"] == "joint" else "Separate for each borrower", "accounts")]
        else:
            rows.append(("Co-borrower", "None — the application is in your name only", "co_borrower"))
    out = {q: (l, v) for l, v, q in rows}
    sim = summary_line(conv, a)
    if sim:
        out["simulation"] = sim
    return out


def question_line(t: dict, conv: dict, a: dict) -> str:
    nxt = t["next"]
    if nxt is None or t["clarifying"]:
        return ""
    if nxt != conv.get("asked") or t["changes"] or t.get("edit"):
        return prompt(nxt, conv, a)
    lead = ("Meanwhile, " if t["gross"] else "Shall we continue? " if t.get("off_topic") else
            ("", "So, ", "Back to the application: ")[conv["seq"] % 3] if t["interrupted"] else "")
    q = short(nxt, conv, a)
    return lead + (q[:1].lower() + q[1:] if lead.endswith(", ") or lead.endswith(": ") else q)


# ---------------------------------------------------------------- the loan simulator (workflow/loan_sim.py)
PRODUCTS = {
    "car": ("Car loan", "Car", "The car's price", "To check the financing rate on this product"),
    "electric_car": ("Electric car loan", "Electric car", "The car's price", "To check the financing rate on this product"),
    "happy_event": ("Celebrations loan", "Celebrations", None, None),
    "express": ("Instant loan", "Instant", None, None),
    "solar": ("Solar installation loan", "Solar", None, None),
    "all_purpose": ("All-purpose loan", "All-purpose", None, None),
    "business_sole": ("Business owners' loan", "Business", None, None),
    "company": ("Company financing, with a banker", "Company", None, None),
}
PRODUCT_VERIFIED = {
    "עד 85% מימון": "Up to 85% financing", "תקופה עד 60 חודשים": "Term up to 60 months",
    "לרכב חדש או יד שנייה": "For a new or used car", "עד 100,000 ₪": "Up to ₪100,000",
    "תקופה עד 7 שנים (84 חודשים)": "Term up to 7 years (84 months)", "עד 125,000 ₪": "Up to ₪125,000",
    "תקופה של 2 עד 72 חודשים": "Term of 2 to 72 months", "אפשר לדחות את התשלום הראשון בעד 3 חודשים": "The first payment can be deferred by up to 3 months",
    "תקופה עד 120 חודשים": "Term up to 120 months", "ריבית במסלולים מגוונים": "Interest on various tracks",
    "לכל מטרה, לטווח קצר או ארוך": "For any purpose, short or long term",
    "פטור מעמלת פירעון מוקדם": "No early-repayment fee",
}
POLICY = {"capitalized": "the interest during the deferral accrues and is added to the principal",
          "interest_only": "only interest is paid during the deferral",
          "accrued_first_payment": "the deferral's interest is paid with the first payment"}


def plabel(p: dict) -> str:
    return PRODUCTS.get(p["id"], (p.get("label_he"),))[0]


def rate_label(rate: dict, pid: Optional[str] = None) -> str:
    src = rate.get("source")
    if src == "bank_quote":
        return "A personal rate offer from the bank"
    if src == "pricing_config":
        return "The rate from the product's pricing"
    if src == "illustrative":
        return (f"An illustrative rate of {rate['annual_rate_pct']:g}% a year (nominal, fixed, not index-linked). "
                "This is not the bank's rate")
    return ("There's no automatic repayment calculation on the company path; the banker will come back with an offer."
            if pid == "company" else "We don't have a rate for this product, so no monthly repayment is shown.")


def product_en(p: dict) -> dict:
    """English siblings for one product of the simulator payload (loan_products.public)."""
    label, short_, asset_label, asset_hint = PRODUCTS.get(p["id"], (None, None, None, None))
    out: dict[str, Any] = {}
    if label:
        out["label_en"], out["short_en"] = label, short_
    out["verified_en"] = [PRODUCT_VERIFIED.get(x, x) for x in p.get("verified_he") or []]
    if p.get("not_applicable_he"):
        out["not_applicable_en"] = ("The page's terms for a loan secured by an apartment (from ₪40,000, 4 to 30 years, up "
                                    "to 70% of the property's value) don't apply to an unsecured loan.")
    if p.get("asset") and asset_label:
        out["asset"] = {"label_en": asset_label, "hint_en": asset_hint}
    if (p.get("features") or {}).get("variable_rate"):
        out["variable_rate_note_en"] = ("The product page says: interest on various tracks. The tracks' terms weren't "
                                        "published, so this is only a what-if scenario.")
    if p.get("rate"):
        out["rate_label_en"] = rate_label(p["rate"], p["id"])
    return out


def intro(conv: dict, a: dict) -> str:
    p, purp = LS.product(conv, a), LS.purpose_of(a)
    if p["id"] == "company":
        return ("Let's set the financing amount and the term. There's no automatic repayment calculation on the company "
                "path, so here you choose an amount and a term, and the banker will come back with an offer.")
    if p["id"] == "express":
        lead = "An instant loan — let's see what it could look like."
    elif purp == "car":
        lead = "Great 🚗 Let's see how to plan the car loan."
    elif purp == "celebration":
        lead = "Congratulations! 🎉 Let's see how to spread the cost in a way that suits you."
    elif purp == "renovation":
        lead = "Let's plan the renovation loan."
    else:
        lead = "Let's see what the loan could look like."
    return f"{lead} You can change the amount and the repayment term and immediately see how they affect the monthly payment."


def reprompt() -> str:
    return "You can keep adjusting the amount and the term in the simulation, and tap confirm when it suits you."


def monthly_sentence(conv: dict, a: dict, prm: Optional[dict] = None) -> str:
    p = LS.product(conv, a)
    prm = prm or LS.confirmed_params(conv, a) or LS.draft_params(conv, a)
    s = LS.compute(p, prm)
    if not s:
        return ""
    return (f"The estimated monthly repayment on {ils(prm['amount'])} over {prm['term']} payments is about "
            f"{ils(s['monthly_payment'])} (an illustrative rate of {s['annual_rate_pct']:g}%).")


def scenario_answer(conv: dict, a: dict, pending: Optional[str]) -> str:
    st = LS.status(conv, a, pending)
    if st == "inactive":
        return "There's no simulation yet; I'll show it once I know what the loan is for."
    p = LS.product(conv, a)
    prm = (LS.confirmed_params(conv, a) if st == "confirmed" else None) or LS.draft_params(conv, a)
    ev = LS.evaluate(conv, a, p, prm)
    r = ev["result"]
    if not r:
        return f"In the simulation: {ils(prm['amount'])} over {prm['term']} payments. {rate_label(ev['rate'], p['id'])}"
    parts = [f"In the simulation ({_lower(plabel(p))}): {ils(prm['amount'])} over {prm['term']} payments, a monthly repayment of about "
             f"{ils(r['monthly_payment'])}, and about {ils(r['total_paid'])} in total, of which about {ils(r['total_interest'])} is "
             f"interest. The calculation uses an illustrative rate of {r['annual_rate_pct']:g}%, not the bank's rate."]
    if ev["affordability"]:
        parts.append(afford_sentence(ev["affordability"]))
    return " ".join(parts)


def afford_sentence(af: dict) -> str:
    if af["existing_known"] and af["existing_monthly"]:
        lead = (f"Together with the existing repayments you mentioned ({ils(af['existing_monthly'])}), the total monthly "
                f"repayment would be about {ils(af['total_monthly'])}, about {af['ratio_pct']:g}% of the net income you gave")
    else:
        lead = f"The new repayment is about {af['ratio_pct']:g}% of the net income you gave"
    tail = (", leaving about " + ils(af["remaining"]) + " a month." if af["remaining"] >= 0 else ".")
    unknown = "" if af["existing_known"] else " I didn't include existing loans, because you haven't mentioned any yet."
    return lead + tail + unknown + " This is a budget indicator based on what you told me, not an eligibility check."


def issue_message(i: dict, p: dict) -> str:
    """loan_products.issues' message for the same issue."""
    b = lp.bounds(p)
    label = plabel(p)
    code = i.get("code")
    if code == "amount_below_min":
        return f"The lowest amount in the simulation is {ils(b['amount_min'])}."
    if code == "amount_above_max":
        where = f"The {_lower(label)} goes up to" if b["amount_max_basis"] == "verified" else "The simulation goes up to"
        return f"{where} {ils(b['amount_max'])}. You can lower the amount or check another product."
    if code == "financing_ratio":
        return (f"The amount you chose is {i['ratio_pct']:g}% of the car's price, above this product's financing rate (up to "
                f"{i['limit_pct']}%). You can lower the loan to {ils(i['fix'])} or look at other options.")
    if code == "term_below_min":
        return f"The shortest term in the simulation is {b['term_min']} months."
    if code == "term_above_max":
        where = f"The {_lower(label)} term goes up to" if b["term_max_basis"] == "verified" else "The simulation term goes up to"
        return f"{where} {b['term_max']} months. You can shorten the term or check another product."
    if code == "deferral_not_supported":
        d = p["features"].get("deferral")
        return f"You can defer the first payment by up to {d['max_months']} months." if d else f"The {_lower(label)} has no first-payment deferral."
    if code == "asset_required":
        ratio = p["amount"].get("max_financing_ratio") or 0
        return (f"To check the financing rate of the {_lower(label)} (up to {int(ratio * 100)}% of the car's price) we need the car's "
                "price. You can enter it, or say there's no final price yet.")
    if code == "flow":
        return _error_message(i.get("message_he", "")) or "The amount or term can't be recorded on this path."
    return ""


def notes_text(conv: dict, a: dict, notes: list[str], pending: Optional[str]) -> str:
    if not notes:
        return ""
    st = LS.status(conv, a, pending)
    p = LS.product(conv, a)
    prm = (LS.confirmed_params(conv, a) if st == "confirmed" else None) or LS.draft_params(conv, a)
    ev = LS.evaluate(conv, a, p, prm)
    parts = []
    if "product" in notes:
        parts.append(f"I switched the simulation to the {_lower(plabel(p))}.")
        if ev["issues"]:
            parts.append(f"Note: {_lower(issue_message(ev['issues'][0], p))}")
    if "asset_price" in notes and prm.get("asset_price"):
        ratio = round(prm["amount"] / prm["asset_price"] * 100, 1)
        ratio_issue = next((i for i in ev["issues"] if i["code"] == "financing_ratio"), None)
        if ratio_issue:
            parts.append(issue_message(ratio_issue, p))
        elif p["amount"].get("max_financing_ratio"):
            parts.append(f"The car's price is {ils(prm['asset_price'])}: the amount is {ratio:g}% of it, within the product's "
                         f"financing rate (up to {int(p['amount']['max_financing_ratio'] * 100)}%).")
        else:
            parts.append(f"I noted the price, {ils(prm['asset_price'])}.")
    if "deferral" in notes:
        d = p["features"].get("deferral")
        if not d:
            parts.append(f"The {_lower(plabel(p))} has no first-payment deferral.")
        elif prm["deferral_months"]:
            r = ev["result"]
            if r:
                parts.append(f"With a {prm['deferral_months']}-month deferral the first payment will be in "
                             f"{en.month(r['first_repayment_month'])}, and the monthly repayment about {ils(r['monthly_payment'])}. "
                             f"In this illustration {POLICY[prm['deferral_policy']]}, so the deferral increases the total "
                             "interest. This isn't the bank's official calculation.")
        else:
            parts.append("Without a deferral, the first payment is about a month after you receive the loan.")
    if "obligations" in notes:
        ob = LS._sim(conv)["context"].get("obligations")
        parts.append("I noted that you have no existing loan repayments." if ob == 0 else
                     f"I noted existing loan repayments of about {ils(ob)} a month, as you declared.")
    if "target" in notes:
        parts.append(target_text(conv, a, ev["target"], prm, p))
    elif ev["affordability"] and ("obligations" in notes):
        parts.append(afford_sentence(ev["affordability"]))
    return " ".join(x for x in parts if x)


def target_text(conv: dict, a: dict, sol: Optional[dict], prm: dict, p: dict) -> str:
    if not sol:
        return ""
    t = ils(sol["target"])
    if sol["status"] == "no_rate":
        return f"I noted a target of up to {t} a month. I have no rate to calculate with on this product, so the banker will consider it."
    if sol["status"] == "met":
        return f"The repayment in the simulation, about {ils(sol['monthly_payment'])}, is already within your target of up to {t} a month."
    if sol["status"] == "term":
        more = ""
        if sol.get("total_interest") and sol.get("current_total_interest") is not None and sol["term"] > prm["term"]:
            more = (f" A longer term lowers the monthly repayment but raises the total interest, to about "
                    f"{ils(sol['total_interest'])} instead of about {ils(sol['current_total_interest'])}.")
        return (f"To pay up to {t} a month on {ils(prm['amount'])}, you can spread it over at least {sol['term']} payments "
                f"(about {ils(sol['monthly_payment'])} a month).{more}")
    if sol["status"] == "amount":
        return (f"Even over the longest term in the simulation ({sol['term']} months) the repayment on {ils(prm['amount'])} is "
                f"above {t}. To meet your target you could lower the amount to about {ils(sol['amount'])} over {sol['term']} "
                f"payments (about {ils(sol['monthly_payment'])} a month).")
    return (f"Even at the lowest amount in the simulation and the longest term ({sol['term_max']} months) the repayment is "
            f"above {t}, so no scenario on this product meets your target.")


def confirmed_text(conv: dict, a: dict, prm: dict) -> str:
    p = LS.product(conv, a)
    s = LS.compute(p, prm)
    base = f"{ils(prm['amount'])} over {prm['term']} payments, {_lower(plabel(p))}"
    if not s:
        return f"Great, I noted {base}."
    extra = f", with the first payment in {en.month(s['first_repayment_month'])}" if prm.get("deferral_months") else ""
    return (f"Great, I noted {base}: an estimated monthly repayment of about {ils(s['monthly_payment'])}{extra}. "
            "This is an illustration, not an offer from the bank.")


def rule_message(conv: dict, a: dict, qid: str, v: Any) -> str:
    """loan_sim.check_answer's reason for the same stated amount or term."""
    p, prm = LS.product(conv, a), LS.draft_params(conv, a)
    found = lp.issues(p, None, v) if qid == "payments" else lp.issues(p, v, None, prm.get("asset_price"))
    return issue_message(found[0], p) if found else ""


SOLE_INCOME = ("A business loan for a dealer needs income from the business. If you don't have a business, you can switch "
               "to a personal loan.")


def conflict(qid: str, old: Any, new: Any, a: dict) -> str:
    return (f"Just to check: earlier I noted {value(qid, old, a, short=True)}, and now I understood "
            f"{value(qid, new, a, short=True)}. Which is right?")


def edit_answer(qid: str, conv: dict, a: dict) -> str:
    from ..workflow import onboarding_chat as C
    if qid == "simulation":
        return "Sure — you can change the scenario in the simulation and confirm it again."
    return f"Sure. Currently recorded: {value(qid, C._v2(conv, a)[qid], a)}."


def user_edit(qid: Optional[str]) -> str:
    return "Change the simulation" if qid == "simulation" else f"Change {FIELD.get(qid or '', 'a detail')}"


def user_scenario(prm: dict) -> str:
    return f"This is my scenario: {ils(prm['amount'])} over {prm['term']} payments" if prm else "Confirm the simulation"


def issues_text(found: list[dict], p: dict) -> str:
    return "I haven't recorded it yet. " + " ".join(issue_message(i, p) for i in found)


def summary_line(conv: dict, a: dict) -> Optional[tuple[str, str]]:
    conf = LS.confirmed_params(conv, a)
    if not conf or not LS.applies(conv, a):
        return None
    p = LS.product(conv, a)
    s = LS.compute(p, conf)
    bits = [plabel(p)]
    if s:
        bits.append(f"estimated repayment about {ils(s['monthly_payment'])} (illustration)")
    if conf.get("asset_price"):
        bits.append(f"car price {ils(conf['asset_price'])}")
    if conf.get("deferral_months"):
        bits.append(f"a {conf['deferral_months']}-month deferral")
    return "Simulated product", " · ".join(bits)


def sim_apply_pending(conv: dict, a: dict, prm: dict) -> str:
    return (f"I updated the simulation: {ils(prm['amount'])} over {prm['term']} payments. "
            + monthly_sentence(conv, a, prm) + " If that suits you, you can confirm.")


# ---------------------------------------------------------------- actions (quick replies under a message)
ACTION_LABELS = {
    "לעבור להלוואה פרטית": "Switch to a personal loan", "להוסיף לווה נוסף": "Add a co-borrower",
    "יש לי גם עסק עצמאי": "I also have a business", "הכול כשכיר": "All salaried", "אני לא בטוח/ה": "I'm not sure",
    "רק עסק עצמאי": "Only a business",
}


def action_label(act: dict, conv: dict, a: dict) -> Optional[str]:
    he = act.get("label_he", "")
    if he in ACTION_LABELS:
        return ACTION_LABELS[he]
    if act.get("simulation"):
        s = act["simulation"]
        if "amount" in s and "term" in s:
            return f"{ils(s['amount'])} over {s['term']} payments"
        if "term" in s:
            return f"{s['term']} payments"
        if "amount" in s:
            return ils(s["amount"])
    if act.get("text") is not None:
        pid = next((pid for pid, pr in ((x, lp.product(x)) for x in ("car", "electric_car", "happy_event", "express", "solar",
                                                                     "all_purpose")) if pr["label_he"] == act["text"]), None)
        if pid:
            return f"Check the {_lower(PRODUCTS[pid][0])}"
        return None
    q, v = act.get("question_id"), act.get("value")
    if q == "payments" and isinstance(v, int):
        return f"Spread over {v} payments" if he.startswith("לפרוס") else f"Update to {v} payments" if he.startswith("לעדכן") else f"{v} payments"
    if q in ("amount", "business_amount") and isinstance(v, int):
        return f"Lower to {ils(v)}" if he.startswith("להפחית") else f"Update to {ils(v)}" if he.startswith("לעדכן") else ils(v)
    if q:
        from ..workflow import onboarding_chat as C
        return value(q, v, a, short=True) if q in C.FIELD_HE else option_label(q, v)
    return None


def offered_labels(conv: dict, a: dict, pending: Optional[str]) -> set[str]:
    """Every English label the customer app could have shown for a button at this point: the open question's quick
    replies, the last assistant message's actions, the suggestion chips. A client's label_en is echoed only when it is
    one of these — never free text the client chose."""
    from ..workflow import onboarding_chat as C
    out: set[str] = set(SUGGESTIONS.values())
    if pending:
        out |= {x for x in (option_label(pending, r["value"]) for r in C._replies(pending, conv, a)) if x}
    last = next((m for m in reversed(conv["messages"]) if m["role"] == "assistant"), None)
    for act in (last or {}).get("actions") or []:
        label = action_label(act, conv, a)
        if label:
            out.add(label)
    return out


# ---------------------------------------------------------------- the turn
def compose(t: dict, conv: dict, a: dict) -> str:
    """The English reply for a turn the Hebrew composer just worded: the same parts in the same order
    (onboarding_chat._compose_rules) from the outcome `turn` recorded in `t`."""
    from ..workflow import onboarding_chat as C
    rec = t.get("_en") or {}
    parts: list[str] = []
    ack_ = rec.get("ack", "")
    if t["held"]:
        held = and_([_lv(k, value(k, conv["held"][k], a)) for k in t["held"] if k in conv["held"]])
        ack_ = (ack_ + " " if ack_ else "") + f"Got it, {held}. I'll keep that for later."
    if ack_:
        parts.append(ack_)
    parts += [x for x in rec.get("issues", []) if x]
    parts += [x for x in rec.get("answers", []) if x]
    if rec.get("sim"):
        parts.append(rec["sim"])
    ind = indication_sentence(t["ind_event"], t["ind_snap"], C._indication(a)) if t["ind_text"] else ""
    if ind:
        parts.append(ind)
    if t["summary_text"]:
        parts.append(SUMMARY_TEXT.get(t["summary_text"], ""))
    q = question_line(t, conv, a)
    if q:
        parts.append(q)
    if not [p for p in parts if p]:
        parts.append(not_understood(t["next"]))
    return " ".join(p for p in parts if p)


def opening(conv: dict, a: dict, first: Optional[str]) -> str:
    return f"{OPENING}\nLet's start: {prompt(first, conv, a)[:1].lower() + prompt(first, conv, a)[1:]}" if first == "loan_type" \
        else prompt(first, conv, a) if first else OPENING


# ---------------------------------------------------------------- the view
def view(out: dict, conv: dict, a: dict) -> None:
    """English siblings for onboarding_chat.view (pending question, quick replies, stages, summary, simulator)."""
    from ..workflow import onboarding_chat as C
    from . import views
    p = out.get("pending")
    if p:
        q = p["question_id"]
        p["prompt_en"] = prompt(q, conv, a)
        p["placeholder_en"] = placeholder(q)
        for r in p.get("replies") or []:
            label = option_label(q, r["value"])
            if label:
                r["label_en"] = label
        if p.get("current_he") is not None:
            p["current_en"] = value(q, C._v2(conv, a)[q], a)
    for s in out.get("stages") or []:
        s["label_en"] = STAGES.get(s["id"], s.get("label_he"))
    out["suggestions_en"] = [SUGGESTIONS.get(x, x) for x in out.get("suggestions") or []]
    if out.get("first_name_he"):
        out["first_name_en"] = en.name(out["first_name_he"])
    out["note_en"] = "The questions only decide which documents are needed. They are not an eligibility check or a credit offer."
    simulation(out)
    s = out.get("summary")
    if s:
        lines = summary_lines(conv, a)
        for line in s.get("lines") or []:
            if line["question_id"] in lines:
                line["label_en"], line["value_en"] = lines[line["question_id"]]
        first = out.get("first_name_en")
        s["intro_en"] = f"{first + ', ' if first else ''}here's what I understood. You can change any detail before the application is opened."
        for r in s.get("requirements") or []:
            title = views.requirement_title(r.get("title_he") or "")
            if title:
                r["title_en"] = title
    for m in out.get("messages") or []:
        for act in m.get("actions") or []:
            if "label_en" not in act:
                label = action_label(act, conv, a)
                if label:
                    act["label_en"] = label
        if m.get("simulator") and m["simulator"].get("product_he"):
            label = next((v[0] for k, v in PRODUCTS.items() if _safe_label(k) == m["simulator"]["product_he"]), None)
            if label:
                m["simulator"]["product_en"] = label
    for act in out.get("actions") or []:
        if "label_en" not in act:
            label = action_label(act, conv, a)
            if label:
                act["label_en"] = label


def simulation(out: dict) -> None:
    """English siblings for the simulator payload (loan_sim.view) inside `out["simulation"]`: product labels, verified
    terms, the asset field, the rate's label."""
    sim = out.get("simulation")
    if not sim:
        return
    for c in sim.get("candidates") or []:
        extra = product_en(c)
        asset = extra.pop("asset", None)
        note = extra.pop("variable_rate_note_en", None)
        rl = extra.pop("rate_label_en", None)
        c.update(extra)
        if asset and c.get("asset"):
            c["asset"].update(asset)
        if note and (c.get("features") or {}).get("variable_rate"):
            c["features"]["variable_rate"]["note_en"] = note
        if rl and c.get("rate"):
            c["rate"]["label_en"] = rl
    for ev in (sim.get("draft_eval"), sim.get("confirmed_eval")):
        if ev and ev.get("rate"):
            ev["rate"]["label_en"] = rate_label(ev["rate"], sim.get("product_id"))


def _safe_label(pid: str) -> Optional[str]:
    try:
        return lp.product(pid)["label_he"]
    except Exception:
        return None
