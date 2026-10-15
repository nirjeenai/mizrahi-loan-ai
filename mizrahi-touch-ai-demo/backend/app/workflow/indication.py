"""The preliminary financing indication of the conversational questionnaire (V2): a deterministic, explainable DEMO
illustration computed from the customer's own declarations and the fixed assumptions below.

It is not an eligibility check, an offer or an underwriting result. It reads no credit bureau, bank account or
existing obligation — the demo has none of them, and nothing here pretends otherwise. The customer sees the inputs
and the assumptions with every number, and a number is shown only when every input it needs was declared."""
from __future__ import annotations

import math
from typing import Any

DEMO_ANNUAL_RATE = 0.06            # illustrative annual interest rate (not a bank rate)
DEMO_RATIO_SALARIED = 0.30         # share of declared net income assumed available for the monthly repayment
DEMO_RATIO_WITH_BUSINESS = 0.25    # more conservative when any declared income comes from a business
ROUND_DOWN_TO = 1000

NEEDED_HE = {"amount": "הסכום שמבקשים", "payments": "מספר התשלומים", "income": "מקור ההכנסה",
             "net": "ההכנסה החודשית נטו"}


def _annuity_factor(months: int, rate: float = DEMO_ANNUAL_RATE) -> float:
    r = rate / 12
    return (1 - (1 + r) ** -months) / r


def monthly_payment(principal: int, months: int) -> int:
    return int(round(principal / _annuity_factor(months), -1))


def compute(a: dict, cap: int) -> dict[str, Any]:
    """`a` holds the questionnaire's cleaned answers; `cap` is the questionnaire's upper bound for a requested amount.
    A co-borrower's income counts only once it was declared, so a missing co-borrower answer never raises the number."""
    if a.get("entity") == "company":
        return {"available": False, "reason": "company", "missing": []}
    missing = [k for k in ("amount", "payments", "income", "net") if a.get(k) in (None, [], "")]
    if missing:
        return {"available": False, "reason": "missing", "missing": missing,
                "missing_he": [NEEDED_HE[k] for k in missing]}
    sources = list(a["income"])
    nets = [("primary", int(a["net"]))]
    co = a.get("co_borrower") == "yes"
    co_counted = co and a.get("co_net") is not None and bool(a.get("co_income"))
    if co_counted:
        sources += list(a["co_income"])
        nets.append(("co", int(a["co_net"])))
    total = sum(n for _, n in nets)
    if total <= 0:
        return {"available": False, "reason": "no_income", "missing": []}
    business = "self_employed" in sources
    ratio = DEMO_RATIO_WITH_BUSINESS if business else DEMO_RATIO_SALARIED
    months = int(a["payments"])
    max_monthly = int(round(total * ratio))
    raw = max_monthly * _annuity_factor(months)
    capped = raw > cap
    max_amount = int(math.floor(min(raw, cap) / ROUND_DOWN_TO) * ROUND_DOWN_TO)
    requested = int(a["amount"])
    return {
        "available": True, "max_amount_ils": max_amount, "requested_amount_ils": requested,
        "within": requested <= max_amount, "requested_monthly_ils": monthly_payment(requested, months),
        "max_monthly_ils": max_monthly, "payments": months, "declared_net_ils": total,
        "net_parts": [{"who": w, "net_ils": n} for w, n in nets], "co_borrower_pending": co and not co_counted,
        "business_income": business, "ratio": ratio, "annual_rate": DEMO_ANNUAL_RATE, "capped": capped, "cap_ils": cap,
        "key": f"{max_amount}|{requested}|{months}|{total}|{ratio}",
    }
