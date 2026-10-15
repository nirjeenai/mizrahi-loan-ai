"""The loan simulator inside the conversational application (/customer/apply): state, evaluation, product rules and
what a customer's words change in a scenario. The conversation layer (`onboarding_chat`) calls this module; the
numbers come from `loan_calc` and the rules from `loan_products`. Nothing here calls a model.

One source of truth. The requested amount and the number of payments are questionnaire answers
(`onboarding.answer`): once recorded they ARE the confirmed scenario, for the summary, the case and the banker. Next
to them the draft's conversation keeps `conv["sim"]`:
  product   the candidate product the customer explores (None → the first candidate for the purpose);
  draft     the unconfirmed scenario on the card (amount, term and the product's extra inputs);
  confirmed the extra inputs that were confirmed with the answers (vehicle price, deferral, …) — never amount/term;
  context   customer-declared figures the questionnaire has no question for (existing monthly repayments, a target
            monthly payment). Customer statements, never verified data.
Moving a slider changes only `draft` (saved without a message); confirming records amount and payments through the
questionnaire and resumes the conversation."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from ..config import settings
from . import loan_calc as calc, loan_products as lp, onboarding, onboarding_nlu as nlu
from .onboarding import OnboardingError

SIM_FIELDS = ("amount", "business_amount", "payments")
POLICY_HE = {"capitalized": "הריבית בתקופת הדחייה מצטברת ומתווספת לקרן",
             "interest_only": "בתקופת הדחייה משלמים ריבית בלבד",
             "accrued_first_payment": "הריבית בתקופת הדחייה משולמת עם התשלום הראשון"}
MODEL_HE = {"annuity": "שפיצר, תשלום חודשי קבוע", "equal_principal": "קרן שווה, תשלום יורד"}
DECLARED = "CUSTOMER_DECLARED"


def _ils(n: Any) -> str:
    return f"{int(round(float(n))):,} ₪"


# ---------------------------------------------------------------- state
def _sim(conv: dict) -> dict:
    s = conv.setdefault("sim", {})
    for k, v in (("product", None), ("draft", {}), ("confirmed", None), ("context", {}), ("shown", 0), ("rev", 0),
                 ("hint", None)):
        s.setdefault(k, v)
    return s


def _flags(conv: dict, a: dict) -> tuple[bool, bool]:
    loan = conv.get("loan") or {}
    company = a.get("entity") == "company"
    sole = not company and loan.get("type") == "business" and loan.get("form") in ("vat_exempt", "vat_registered")
    return sole, company


def purpose_of(a: dict) -> Optional[str]:
    return a.get("company_purpose") if a.get("entity") == "company" else a.get("purpose")


def applies(conv: dict, a: dict) -> bool:
    """The simulator has a configuration once the loan's purpose (or the company's purpose) is known."""
    return bool(a.get("entity")) and bool(purpose_of(a))


def candidates(conv: dict, a: dict) -> list[str]:
    sole, company = _flags(conv, a)
    return lp.candidates(a.get("purpose"), sole, company)


def product(conv: dict, a: dict) -> dict:
    s, cands = _sim(conv), candidates(conv, a)
    pid = s["product"] if s["product"] in cands else s["hint"] if s["hint"] in cands else cands[0]
    return lp.product(pid)


def amount_field(conv: dict, a: dict) -> str:
    return "business_amount" if a.get("entity") == "company" else "amount"


def _int(v: Any, lo: int, hi: int) -> Optional[int]:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def clean(raw: Optional[dict]) -> dict:
    """Only the known inputs, typed and bounded; anything else is dropped."""
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}
    for k, lo, hi in (("amount", 1, 10_000_000), ("term", 1, 600), ("asset_price", 1000, 20_000_000),
                      ("deferral_months", 0, 24), ("rate_change_from", 2, 600)):
        if raw.get(k) is not None:
            v = _int(raw[k], lo, hi)
            if v is not None:
                out[k] = v
    if raw.get("rate_change_pct") is not None:
        try:
            v = round(float(raw["rate_change_pct"]), 2)
            if -5 <= v <= 10:
                out["rate_change_pct"] = v
        except (TypeError, ValueError):
            pass
    if raw.get("deferral_policy") in calc.DEFERRAL_POLICIES:
        out["deferral_policy"] = raw["deferral_policy"]
    if raw.get("model") in ("annuity", "equal_principal"):
        out["model"] = raw["model"]
    if isinstance(raw.get("asset_unknown"), bool):
        out["asset_unknown"] = raw["asset_unknown"]
    if raw.get("asset_price") is None and "asset_price" in raw:
        out["asset_price"] = None
    if lp.exists(raw.get("product")):
        out["product"] = raw["product"]
    return out


def _params(p: dict, base: dict) -> dict:
    """Fill a scenario with the product's defaults and drop what the product does not support."""
    feats = p["features"]
    d = feats.get("deferral")
    out = {"amount": base.get("amount") or p["defaults"]["amount"], "term": base.get("term") or p["defaults"]["term"],
           "asset_price": base.get("asset_price") if p.get("asset") else None,
           "asset_unknown": bool(base.get("asset_unknown")) if p.get("asset") else False,
           "deferral_months": min(base.get("deferral_months") or 0, d["max_months"]) if d else 0,
           "deferral_policy": (base.get("deferral_policy") if d and base.get("deferral_policy") in d["illustrative_policies"]
                               else d["default_policy"] if d else None),
           "model": base.get("model") if base.get("model") in feats["repayment_models"] else "annuity",
           "rate_change_pct": (base.get("rate_change_pct") or 0) if feats.get("variable_rate") else 0,
           "rate_change_from": base.get("rate_change_from") or 13}
    return out


def draft_params(conv: dict, a: dict) -> dict:
    p, s = product(conv, a), _sim(conv)
    base = {**(s["confirmed"] or {}), **s["draft"]}
    if base.get("amount") is None:
        base["amount"] = a.get(amount_field(conv, a))
    if base.get("term") is None:
        base["term"] = a.get("payments")
    return _params(p, base)


def confirmed_params(conv: dict, a: dict) -> Optional[dict]:
    f = amount_field(conv, a)
    if a.get(f) is None or a.get("payments") is None:
        return None
    s = _sim(conv)
    return _params(product(conv, a), {**(s["confirmed"] or {}), "amount": a[f], "term": a["payments"]})


def status(conv: dict, a: dict, pending: Optional[str]) -> str:
    if not applies(conv, a):
        return "inactive"
    if pending in SIM_FIELDS:
        return "pending"
    return "confirmed" if confirmed_params(conv, a) else "inactive"


def sync_answers(conv: dict, a: dict, changes: list[tuple[str, Any, Any]]) -> bool:
    """An amount or term recorded in the conversation becomes the card's draft value too (one value, not two)."""
    s, moved = _sim(conv), False
    for q, _, new in changes:
        if q in ("amount", "business_amount") and new is not None:
            s["draft"]["amount"], moved = new, True
        elif q == "payments" and new is not None:
            s["draft"]["term"], moved = new, True
    if moved:
        s["rev"] += 1
    return moved


# ---------------------------------------------------------------- evaluation
def _start_month() -> str:
    return calc.first_month(date.fromisoformat(settings.simulation_date))


def compute(p: dict, prm: dict) -> Optional[dict]:
    """The schedule of a scenario at the product's rate, or None when no rate may be used."""
    rate = lp.rate_for(p)
    if not rate["available"]:
        return None
    changes = ([{"from_period": prm["rate_change_from"], "annual_rate_pct": rate["annual_rate_pct"] + prm["rate_change_pct"]}]
               if prm.get("rate_change_pct") and prm["rate_change_from"] < prm["term"] + prm["deferral_months"] else [])
    deferral = ({"months": prm["deferral_months"], "policy": prm["deferral_policy"],
                 "term_includes_deferral": p["features"]["deferral"]["term_includes_deferral"]}
                if prm.get("deferral_months") else None)
    try:
        return calc.schedule(prm["amount"], prm["term"], rate["annual_rate_pct"], convention=rate["convention"],
                             model=prm["model"], rate_changes=changes, deferral=deferral, start_month=_start_month())
    except calc.CalcError:
        return None


def _summary(s: Optional[dict]) -> Optional[dict]:
    if s is None:
        return None
    keep = ("principal", "term_months", "amortizing_months", "deferral_months", "deferral_policy", "periods", "model",
            "annual_rate_pct", "monthly_payment", "first_payment", "first_payment_month", "first_repayment_month",
            "last_payment", "max_payment", "min_payment", "total_paid", "total_interest", "total_fees", "total_cost",
            "rate_changes")
    return {**{k: s[k] for k in keep}, "yearly": calc.yearly(s["rows"])}


def _issues(conv: dict, a: dict, p: dict, prm: dict, confirming: bool = False) -> list[dict]:
    out = lp.issues(p, prm["amount"], prm["term"], prm.get("asset_price"), prm.get("deferral_months") or 0)
    if confirming and p.get("asset") and p["amount"].get("max_financing_ratio") and not prm.get("asset_price") \
            and not prm.get("asset_unknown"):
        pct = int(p["amount"]["max_financing_ratio"] * 100)
        out.append({"code": "asset_required", "field": "asset_price", "fix": None,
                    "message_he": f"כדי לבדוק את שיעור המימון ב{p['label_he']} (עד {pct}% ממחיר הרכב) צריך את מחיר הרכב. "
                                  "אפשר להזין אותו, או לציין שעוד אין מחיר סופי."})
    return out


def comparison(p: dict, prm: dict) -> list[dict]:
    """The same scenario at shorter / the chosen / longer terms inside the product's range."""
    b, rows, seen = lp.bounds(p), [], set()
    for t in (prm["term"] - 12, prm["term"], prm["term"] + 12):
        t = max(b["term_min"], min(b["term_max"], t))
        if t in seen:
            continue
        seen.add(t)
        s = compute(p, {**prm, "term": t})
        if s:
            rows.append({"term": t, "monthly_payment": s["monthly_payment"], "total_interest": s["total_interest"],
                         "chosen": t == prm["term"]})
    return rows


def context(conv: dict, a: dict) -> dict:
    s = _sim(conv)
    nets = [("primary", a.get("net"))]
    if a.get("co_borrower") == "yes" and a.get("co_net") is not None:
        nets.append(("co", a.get("co_net")))
    known = [n for _, n in nets if n is not None]
    return {"net_income": sum(known) if known else None, "net_parts": [{"who": w, "net_ils": n} for w, n in nets if n is not None],
            "co_borrower_pending": a.get("co_borrower") == "yes" and a.get("co_net") is None,
            "obligations": s["context"].get("obligations"), "target_monthly": s["context"].get("target"),
            "source": DECLARED}


def target_solution(p: dict, prm: dict, target: Optional[int]) -> Optional[dict]:
    """Reverse simulation for a monthly-payment target: keep the amount and search the product's terms first, then a
    lower amount. Annuity at the product's rate; with a deferral the regular installment is compared."""
    if not target:
        return None
    rate = lp.rate_for(p)
    if not rate["available"]:
        return {"status": "no_rate", "target": target}
    b = lp.bounds(p)
    current = compute(p, prm)
    if current and current["monthly_payment"] <= target:
        return {"status": "met", "target": target, "monthly_payment": current["monthly_payment"]}
    term = calc.term_for_target(prm["amount"], target, rate["annual_rate_pct"], b["term_min"], b["term_max"], rate["convention"])
    if term is not None:
        s = compute(p, {**prm, "term": term})
        return {"status": "term", "target": target, "term": term, "monthly_payment": s["monthly_payment"] if s else None,
                "total_interest": s["total_interest"] if s else None,
                "current_total_interest": current["total_interest"] if current else None}
    amount = int(calc.principal_for_target(target, b["term_max"], rate["annual_rate_pct"], rate["convention"], b["amount_step"]))
    if amount < b["amount_min"]:
        return {"status": "none", "target": target, "term_max": b["term_max"]}
    s = compute(p, {**prm, "amount": amount, "term": b["term_max"]})
    return {"status": "amount", "target": target, "amount": amount, "term": b["term_max"],
            "monthly_payment": s["monthly_payment"] if s else None}


def evaluate(conv: dict, a: dict, p: dict, prm: dict, confirming: bool = False) -> dict:
    s = compute(p, prm)
    ctx = context(conv, a)
    afford = (calc.affordability(s["monthly_payment"], ctx["net_income"], ctx["obligations"])
              if s and ctx["net_income"] else None)
    return {"result": _summary(s), "issues": _issues(conv, a, p, prm, confirming), "affordability": afford,
            "comparison": comparison(p, prm) if s else [], "target": target_solution(p, prm, ctx["target_monthly"]),
            "rate": lp.rate_for(p)}


def view(conv: dict, a: dict, pending: Optional[str]) -> Optional[dict]:
    st = status(conv, a, pending)
    if st == "inactive":
        return None
    s, p = _sim(conv), product(conv, a)
    draft = draft_params(conv, a)
    conf = confirmed_params(conv, a)
    reg = lp.registry()
    return {
        "status": st, "editing": st == "pending" and conf is not None, "rev": s["rev"], "product_id": p["id"],
        "candidates": [lp.public(lp.product(c)) for c in candidates(conv, a)],
        "amount_field": amount_field(conv, a), "purpose": purpose_of(a),
        "draft": draft, "draft_eval": evaluate(conv, a, p, draft),
        "confirmed": conf, "confirmed_eval": evaluate(conv, a, p, conf) if conf else None,
        "context": context(conv, a), "start_month": _start_month(),
        "config_version": reg["config_version"], "checked_on": reg["checked_on"],
    }


def snapshot(conv: dict, a: dict, pending: Optional[str]) -> Optional[dict]:
    """What a message keeps of the scenario it showed: enough to render an older card as a one-line record."""
    st = status(conv, a, pending)
    if st == "inactive":
        return None
    p = product(conv, a)
    prm = (confirmed_params(conv, a) if st == "confirmed" else None) or draft_params(conv, a)
    res = compute(p, prm)
    return {"status": st, "product_he": p["label_he"], "amount": prm["amount"], "term": prm["term"],
            "monthly_payment": res["monthly_payment"] if res else None, "rev": _sim(conv)["rev"]}


# ---------------------------------------------------------------- product rules for recorded answers
def check_answer(conv: dict, a: dict, qid: str, value: Any) -> Optional[tuple[str, list[dict]]]:
    """An amount or term stated in the conversation must fit the candidate product, like a slider value does.
    Returns (reason, fix actions) or None. Before the purpose is known there is no product to check against."""
    if qid not in SIM_FIELDS or not applies(conv, a) or not isinstance(value, int):
        return None
    p = product(conv, a)
    prm = draft_params(conv, a)
    if qid == "payments":
        found = lp.issues(p, None, value)
    else:
        found = lp.issues(p, value, None, prm.get("asset_price"))
    if not found:
        return None
    i = found[0]
    acts = []
    if i.get("fix"):
        label = f"{i['fix']} תשלומים" if i["field"] == "term" else _ils(i["fix"])
        acts.append({"label_he": label, "question_id": qid, "value": i["fix"]})
    other = next((c for c in candidates(conv, a) if c != p["id"] and not (
        lp.issues(lp.product(c), None, value) if qid == "payments" else lp.issues(lp.product(c), value, None))), None)
    if other:
        acts.append({"label_he": f"לבדוק {lp.product(other)['label_he']}", "text": lp.product(other)["label_he"]})
    return i["message_he"], acts


# ---------------------------------------------------------------- understanding a message
PRODUCT_WORDS = [("express", re.compile(r"ברגע|מיידית|הלוואה מהירה")), ("electric_car", re.compile(r"חשמלי")),
                 ("solar", re.compile(r"סולאר|סולר|פאנל|פוטו.?וולט")), ("happy_event", re.compile(r"לשמחות")),
                 ("all_purpose", re.compile(r"לכל מטרה")), ("car", re.compile(r"הלוואה לרכב(?!\s+חשמלי)|מסלול (?:ה)?רכב(?!\s+חשמלי)"))]
TARGET_CUE = {"עד", "מקסימום", "לעבור", "מעל", "היותר", "יותר"}
MONTHLY_CUE = {"בחודש", "לחודש", "חודשי", "חודשית", "החזר", "תשלום", "לשלם", "ההחזר", "החזרים"}
DEBT_NOUN = {"הלוואה", "הלוואות", "התחייבויות", "התחייבות", "משכנתא", "משכנתה", "החזרים", "ליסינג"}
DEBT_EXIST = {"יש", "קיימת", "קיימות", "קיים", "כבר", "משלם", "משלמת", "משלמים", "מחזיר", "מחזירה"}
ASSET_CUE = {"מחיר", "עולה", "עולים", "שווי", "שווה", "מחירו"}
VEHICLE = {"רכב", "מכונית", "אוטו"}
CONFIRM = re.compile(r"^(?:כן,?\s*)?(?:אני\s+)?(?:מאשר|מאשרת|מאשרים)(?:\s|$|[.!,])|זה מתאים לי|מתאים לי(?:\s|$|[.!,])"
                     r"|^(?:אישור|לאשר)(?:\s|$|[.!,])|זה התרחיש")
NO_DEBT = re.compile(r"אין לי (?:הלוואות|התחייבויות|החזרים|הלוואה)|בלי התחייבויות|אין התחייבויות")
NO_DEFERRAL = re.compile(r"בלי דחי|ללא דחי|לא לדחות")
# "אני רוצה לפרוס ל־60", "תוריד ל־80 אלף": a new amount or term for the scenario, not a contradiction to ask about
CHANGE_INTENT = re.compile(r"(?:^|\s)(?:רוצה|רוצים|מעדיף|מעדיפה|לפרוס|תפרוס|תפרסי|לעדכן|תעדכן|תעדכני|לשנות|תשנה|תשני"
                           r"|להוריד|תוריד|תורידי|להעלות|תעלה|תעלי|להקטין|תקטין|להגדיל|תגדיל|רק)(?=\s|$)")


def _has(words: list[str], kw: set[str]) -> bool:
    return any(nlu.stems(w) & kw for w in words)


def understand(text: str, conv: dict, a: dict, pending: Optional[str]) -> dict:
    """What a message says about the scenario. Numbers it claims (a target monthly payment, existing repayments, a
    vehicle price, deferral months) are removed from `masked`, so the questionnaire's parser does not read them as an
    amount or an income."""
    norm = nlu.normalize(text)
    toks = nlu.tokens(norm)
    out: dict[str, Any] = {"masked": norm, "numbers": set(), "change_intent": bool(CHANGE_INTENT.search(norm))}
    for pid, rx in PRODUCT_WORDS:
        if rx.search(norm):
            out["product"] = pid
            break
    if pending in SIM_FIELDS and CONFIRM.search(norm) and not nlu.is_question(norm):
        out["confirm"] = True
    if NO_DEBT.search(norm):
        out["obligations"] = 0
    if NO_DEFERRAL.search(norm):
        out["deferral_months"] = 0
    drop: set[int] = set()
    for n in nlu.numbers(toks):
        before, after = nlu._window(toks, n["start"], n["end"])
        bw, aw = [t for _, t in before], [t for _, t in after]
        near = [t for d, t in before if d <= 3]            # the words just before the number decide what it is
        wants = _has(near, {"רוצה", "צריך", "צריכה", "מבקש", "מבקשת", "ללוות"})
        nxt = toks[n["end"]] if n["end"] < len(toks) else ""
        if nlu.stems(nxt) & {"תשלומים", "תשלום"}:
            continue
        months_after = bool(nlu.stems(nxt) & {"חודשים", "חודש"})
        clause = bw + aw
        v = n["value"]
        if months_after and ("לדחות" in norm or "דחי" in norm) and 0 <= v <= 24:
            out["deferral_months"] = v
        elif _has([t for d, t in before if d <= 4], TARGET_CUE) and _has(clause, MONTHLY_CUE) and not months_after \
                and 100 <= v <= 100_000:
            out["target"] = v
        elif _has(clause, DEBT_NOUN) and _has(clause, DEBT_EXIST) and (_has(clause, MONTHLY_CUE) or
                                                                         _has(clause, {"משלם", "משלמת", "משלמים"})) \
                and not wants and 0 <= v <= 100_000:
            out["obligations"] = v
        elif _has(near + aw[:2], ASSET_CUE) and not wants and not months_after and 1000 <= v <= 20_000_000 \
                and (_has(toks, VEHICLE) or (applies(conv, a) and product(conv, a).get("asset"))):
            out["asset_price"] = v
        elif re.search(r"(?:^|\s)(?:לשלם|החזר(?:\s+חודשי)?\s+של)(?=\s|$)", " ".join(near[::-1])) \
                and _has(aw, {"בחודש", "לחודש"}) and 100 <= v <= 100_000:
            out["target"] = v
        else:
            continue
        out["numbers"].add(v)
        drop.update(range(n["start"], n["end"]))
    if drop:
        out["masked"] = " ".join(t for i, t in enumerate(toks) if i not in drop)
    return out


def apply_text(conv: dict, a: dict, u: dict) -> list[str]:
    """Record what a message says about the scenario (never amount or term, which are questionnaire answers) and return
    the change notes for the reply."""
    s, notes = _sim(conv), []
    if s["confirmed"] is None and applies(conv, a) and confirmed_params(conv, a) is not None:
        s["confirmed"] = {}                    # amount and term were stated in words: their extras start empty
    if "product" in u:
        if applies(conv, a) and u["product"] in candidates(conv, a):
            if product(conv, a)["id"] != u["product"]:
                s["product"] = u["product"]
                notes.append("product")
        elif not applies(conv, a):
            s["hint"] = u["product"]
    if "asset_price" in u:
        s["draft"]["asset_price"], s["draft"]["asset_unknown"] = u["asset_price"], False
        if s["confirmed"] is not None:
            s["confirmed"]["asset_price"], s["confirmed"]["asset_unknown"] = u["asset_price"], False
        notes.append("asset_price")
    if "deferral_months" in u:
        s["draft"]["deferral_months"] = u["deferral_months"]
        if s["confirmed"] is not None:
            s["confirmed"]["deferral_months"] = u["deferral_months"]
        notes.append("deferral")
    for k in ("obligations", "target"):
        if k in u and s["context"].get(k) != u[k]:
            s["context"][k] = u[k]
            notes.append(k)
    if notes:
        s["rev"] += 1
    return notes


def save_draft(conv: dict, a: dict, raw: dict) -> None:
    """The card's unconfirmed scenario (slider moves): stored without a message and without touching the answers."""
    s = _sim(conv)
    c = clean(raw)
    if c.get("product") and c["product"] in candidates(conv, a):
        s["product"] = c["product"]
    s["draft"] = {**s["draft"], **{k: v for k, v in c.items() if k != "product"}}
    if isinstance(raw, dict) and "obligations" in raw:
        ob = _int(raw["obligations"], 0, 100_000) if raw["obligations"] not in (None, "") else None
        s["context"]["obligations"] = ob


def confirm(draft_id: str, conv: dict, a: dict, raw: dict) -> tuple[list[dict], dict]:
    """Confirm a scenario from the card: product rules first, then amount and payments through the questionnaire.
    Returns (issues, params). Nothing is recorded when there is an issue."""
    s = _sim(conv)
    c = clean(raw)
    cands = candidates(conv, a)
    pid = c.get("product") if c.get("product") in cands else product(conv, a)["id"]
    p = lp.product(pid)
    prm = _params(p, {**draft_params(conv, a), **{k: v for k, v in c.items() if k != "product"}})
    found = _issues(conv, a, p, prm, confirming=True)
    if found:
        s["product"], s["draft"] = pid, {k: v for k, v in prm.items()}
        s["rev"] += 1
        return found, prm
    try:
        onboarding.answer(draft_id, amount_field(conv, a), prm["amount"])
        onboarding.answer(draft_id, "payments", prm["term"])
    except OnboardingError as exc:
        return [{"code": "flow", "field": "amount", "fix": None, "message_he": exc.message_he}], prm
    s["product"] = pid
    s["confirmed"] = {k: v for k, v in prm.items() if k not in ("amount", "term")}
    s["draft"] = dict(prm)
    s["rev"] += 1
    return [], prm


# ---------------------------------------------------------------- wording (deterministic)
def intro(conv: dict, a: dict) -> str:
    p, purpose = product(conv, a), purpose_of(a)
    if p["id"] == "company":
        return ("בואו נגדיר את סכום המימון ואת התקופה. במסלול לחברות אין חישוב החזר אוטומטי, "
                "אז כאן בוחרים סכום ותקופה, והבנקאי/ת יחזרו עם הצעה.")
    if p["id"] == "express":
        lead = "הלוואה ברגע, בואו נבדוק איך היא יכולה להיראות."
    elif purpose == "car":
        lead = "מעולה 🚗 בואו נראה איך אפשר לתכנן את ההלוואה לרכב."
    elif purpose == "celebration":
        lead = "מזל טוב! 🎉 בואו נראה איך אפשר לפרוס את ההוצאה בצורה שנוחה לך."
    elif purpose == "renovation":
        lead = "בואו נתכנן את ההלוואה לשיפוץ."
    else:
        lead = "בואו נראה איך ההלוואה יכולה להיראות."
    return f"{lead} אפשר לשנות את הסכום ואת תקופת ההחזר ולראות מיד איך הם משפיעים על התשלום החודשי."


def reprompt() -> str:
    return "אפשר להמשיך לכוון את הסכום והתקופה בסימולציה, וללחוץ על אישור כשזה מתאים."


def monthly_sentence(conv: dict, a: dict, prm: Optional[dict] = None) -> str:
    p = product(conv, a)
    prm = prm or confirmed_params(conv, a) or draft_params(conv, a)
    s = compute(p, prm)
    if not s:
        return ""
    lead = f"ההחזר החודשי המשוער על {_ils(prm['amount'])} ב־{prm['term']} תשלומים הוא כ־{_ils(s['monthly_payment'])}"
    return lead + f" (ריבית להמחשה של {s['annual_rate_pct']:g}%)."


def scenario_answer(conv: dict, a: dict, pending: Optional[str]) -> str:
    st = status(conv, a, pending)
    if st == "inactive":
        return "עוד אין סימולציה, אציג אותה אחרי שאדע למה מיועדת ההלוואה."
    p = product(conv, a)
    prm = (confirmed_params(conv, a) if st == "confirmed" else None) or draft_params(conv, a)
    ev = evaluate(conv, a, p, prm)
    r = ev["result"]
    if not r:
        return f"בסימולציה: {_ils(prm['amount'])} ב־{prm['term']} תשלומים. {ev['rate']['label_he']}"
    parts = [f"בסימולציה ({p['label_he']}): {_ils(prm['amount'])} ב־{prm['term']} תשלומים, החזר חודשי של כ־"
             f"{_ils(r['monthly_payment'])}, ובסך הכול כ־{_ils(r['total_paid'])}, מתוכם כ־{_ils(r['total_interest'])} ריבית. "
             f"החישוב לפי ריבית להמחשה של {r['annual_rate_pct']:g}%, לא ריבית של הבנק."]
    af = ev["affordability"]
    if af:
        parts.append(_afford_sentence(af))
    return " ".join(parts)


def _afford_sentence(af: dict) -> str:
    if af["existing_known"] and af["existing_monthly"]:
        lead = (f"יחד עם ההחזרים הקיימים שסיפרת עליהם ({_ils(af['existing_monthly'])}), ההחזר החודשי הכולל יהיה כ־"
                f"{_ils(af['total_monthly'])}, כ־{af['ratio_pct']:g}% מההכנסה נטו שמסרת")
    else:
        lead = f"ההחזר החדש הוא כ־{af['ratio_pct']:g}% מההכנסה נטו שמסרת"
    tail = (", ונשארים כ־" + _ils(af["remaining"]) + " בחודש." if af["remaining"] >= 0 else ".")
    unknown = "" if af["existing_known"] else " לא כללתי הלוואות קיימות, כי עוד לא סיפרת עליהן."
    return lead + tail + unknown + " זה מדד תקציבי לפי מה שסיפרת, לא בדיקת זכאות."


def notes_text(conv: dict, a: dict, notes: list[str], pending: Optional[str]) -> tuple[str, list[dict]]:
    """The reply sentences (and quick actions) for what this turn changed in the scenario."""
    if not notes:
        return "", []
    st = status(conv, a, pending)
    p = product(conv, a)
    prm = (confirmed_params(conv, a) if st == "confirmed" else None) or draft_params(conv, a)
    ev = evaluate(conv, a, p, prm)
    parts, acts = [], []
    if "product" in notes:
        parts.append(f"עברתי בסימולציה ל{p['label_he']}.")
        found = ev["issues"]
        if found:
            parts.append(f"שימו לב: {found[0]['message_he']}")
            if found[0].get("fix"):
                q = "payments" if found[0]["field"] == "term" else amount_field(conv, a)
                acts.append({"label_he": f"לעדכן ל־{found[0]['fix']} תשלומים" if q == "payments" else f"לעדכן ל־{_ils(found[0]['fix'])}",
                             "question_id": q, "value": found[0]["fix"]})
    if "asset_price" in notes and prm.get("asset_price"):
        ratio = round(prm["amount"] / prm["asset_price"] * 100, 1)
        ratio_issue = next((i for i in ev["issues"] if i["code"] == "financing_ratio"), None)
        if ratio_issue:
            parts.append(ratio_issue["message_he"])
            q = amount_field(conv, a)
            acts.append({"label_he": f"להפחית ל־{_ils(ratio_issue['fix'])}", "question_id": q, "value": ratio_issue["fix"]})
        elif p["amount"].get("max_financing_ratio"):
            parts.append(f"מחיר הרכב {_ils(prm['asset_price'])}: הסכום הוא {ratio:g}% ממנו, בתוך שיעור המימון במסלול "
                         f"(עד {int(p['amount']['max_financing_ratio'] * 100)}%).")
        else:
            parts.append(f"רשמתי את המחיר, {_ils(prm['asset_price'])}.")
    if "deferral" in notes:
        d = p["features"].get("deferral")
        if not d:
            parts.append(f"ב{p['label_he']} אין דחיית תשלום ראשון.")
        elif prm["deferral_months"]:
            r = ev["result"]
            if r:
                parts.append(f"עם דחייה של {prm['deferral_months']} חודשים התשלום הראשון יהיה ב{_month_he(r['first_repayment_month'])}, "
                             f"וההחזר החודשי כ־{_ils(r['monthly_payment'])}. בהמחשה {POLICY_HE[prm['deferral_policy']]}, "
                             "כך שהדחייה מגדילה את סך הריבית. זה לא חישוב רשמי של הבנק.")
        else:
            parts.append("בלי דחייה, התשלום הראשון כחודש אחרי קבלת ההלוואה.")
    if "obligations" in notes:
        ob = _sim(conv)["context"].get("obligations")
        parts.append("רשמתי שאין לך החזרי הלוואות קיימים." if ob == 0 else
                     f"רשמתי החזרי הלוואות קיימים של כ־{_ils(ob)} בחודש, כהצהרה שלך.")
    if "target" in notes:
        text, more = target_text(conv, a, ev["target"], prm, p)
        parts.append(text)
        acts += more
    elif ev["affordability"] and ("obligations" in notes):
        parts.append(_afford_sentence(ev["affordability"]))
    return " ".join(x for x in parts if x), acts


def target_text(conv: dict, a: dict, sol: Optional[dict], prm: dict, p: dict) -> tuple[str, list[dict]]:
    if not sol:
        return "", []
    t = _ils(sol["target"])
    if sol["status"] == "no_rate":
        return f"רשמתי יעד של עד {t} בחודש. במסלול הזה אין לי ריבית לחישוב, אז הבנקאי/ת יתייחסו אליו.", []
    if sol["status"] == "met":
        return f"ההחזר בסימולציה, כ־{_ils(sol['monthly_payment'])}, כבר בתוך היעד של עד {t} בחודש.", []
    q_amount = amount_field(conv, a)
    if sol["status"] == "term":
        more = ""
        if sol.get("total_interest") and sol.get("current_total_interest") is not None and sol["term"] > prm["term"]:
            more = (f" תקופה ארוכה יותר מקטינה את ההחזר החודשי אבל מגדילה את סך הריבית, כ־{_ils(sol['total_interest'])} "
                    f"במקום כ־{_ils(sol['current_total_interest'])}.")
        return (f"כדי לשלם עד {t} בחודש על {_ils(prm['amount'])}, אפשר לפרוס ל־{sol['term']} תשלומים לפחות "
                f"(כ־{_ils(sol['monthly_payment'])} בחודש).{more}",
                [{"label_he": f"לפרוס ל־{sol['term']} תשלומים", "question_id": "payments", "value": sol["term"]}])
    if sol["status"] == "amount":
        return (f"גם בתקופה הארוכה ביותר בסימולציה ({sol['term']} חודשים) ההחזר על {_ils(prm['amount'])} גבוה מ־{t}. "
                f"כדי לעמוד ביעד אפשר להקטין את הסכום לכ־{_ils(sol['amount'])} ולפרוס ל־{sol['term']} תשלומים "
                f"(כ־{_ils(sol['monthly_payment'])} בחודש).",
                [{"label_he": f"{_ils(sol['amount'])} ב־{sol['term']} תשלומים",
                  "simulation": {"amount": sol["amount"], "term": sol["term"]}}])
    return (f"גם בסכום הנמוך בסימולציה ובתקופה הארוכה ביותר ({sol['term_max']} חודשים) ההחזר גבוה מ־{t}, "
            "ולכן אין תרחיש במסלול הזה שעומד ביעד."), []


def confirmed_text(conv: dict, a: dict, prm: dict) -> str:
    p = product(conv, a)
    s = compute(p, prm)
    base = f"{_ils(prm['amount'])} ב־{prm['term']} תשלומים, {p['label_he']}"
    if not s:
        return f"מעולה, רשמתי {base}."
    extra = ""
    if prm.get("deferral_months"):
        extra = f", התשלום הראשון ב{_month_he(s['first_repayment_month'])}"
    return f"מעולה, רשמתי {base}: החזר חודשי משוער של כ־{_ils(s['monthly_payment'])}{extra}. זו המחשה, לא הצעה של הבנק."


def issues_text(found: list[dict]) -> tuple[str, list[dict]]:
    acts = []
    for i in found:
        if i.get("fix") and i["field"] in ("amount", "term"):
            acts.append({"label_he": f"{i['fix']} תשלומים" if i["field"] == "term" else _ils(i["fix"]),
                         "simulation": {"term" if i["field"] == "term" else "amount": i["fix"]}})
    return "לא רשמתי עדיין: " + " ".join(i["message_he"] for i in found), acts


MONTHS_HE = ["", "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]


def _month_he(ym: str) -> str:
    return f"{MONTHS_HE[int(ym[5:7])]} {ym[:4]}"


def summary_line(conv: dict, a: dict) -> Optional[dict]:
    conf = confirmed_params(conv, a)
    if not conf or not applies(conv, a):
        return None
    p = product(conv, a)
    s = compute(p, conf)
    bits = [p["label_he"]]
    if s:
        bits.append(f"החזר משוער כ־{_ils(s['monthly_payment'])} (המחשה)")
    if conf.get("asset_price"):
        bits.append(f"מחיר הרכב {_ils(conf['asset_price'])}")
    if conf.get("deferral_months"):
        bits.append(f"דחייה של {conf['deferral_months']} חודשים")
    return {"label_he": "מסלול בסימולציה", "value_he": " · ".join(bits), "question_id": "simulation"}


def for_case(conv: dict, a: dict) -> Optional[dict]:
    """The confirmed scenario as stored on the case: a candidate product and an illustration, never a bank offer."""
    conf = confirmed_params(conv, a)
    if not conf or not applies(conv, a):
        return None
    p = product(conv, a)
    s = compute(p, conf)
    rate = lp.rate_for(p)
    ctx = context(conv, a)
    return {"candidate_product": p["id"], "candidate_product_he": p["label_he"], "product_selected_by_bank": False,
            "config_version": lp.registry()["config_version"], "rate_source": rate["source"],
            "annual_rate_pct": rate["annual_rate_pct"], "monthly_payment_ils": s["monthly_payment"] if s else None,
            "total_interest_ils": s["total_interest"] if s else None,
            "asset_price_ils": conf.get("asset_price"), "asset_price_source": DECLARED if conf.get("asset_price") else None,
            "deferral_months": conf.get("deferral_months") or 0,
            "deferral_policy": conf.get("deferral_policy") if conf.get("deferral_months") else None,
            "repayment_model": conf["model"],
            "existing_monthly_obligations_ils": ctx["obligations"], "obligations_source": DECLARED if ctx["obligations"] is not None else None}
