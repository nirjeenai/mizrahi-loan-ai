"""Deterministic loan arithmetic for the chat's loan simulator. Pure functions, no I/O, no model, no bank data.

Every figure the simulator shows comes from here (and from its port, frontend/src/loanCalc.ts — change both together).
`Decimal` throughout, 34 significant digits.

Rates: a nominal annual rate is divided by 12; an effective annual rate is converted, (1 + EAR)^(1/12) − 1.
Rounding policy (one rule for every model): the exact cash flow is computed first; totals are rounded once to agorot
(ROUND_HALF_UP); each installment and its interest are rounded to agorot, and the LAST installment reconciles the
rounded rows to the rounded totals. For a plain annuity this keeps the exact total (₪100,000 · 48 · 8% nominal →
2,441.29 a month, 117,182.03 in total) and the monthly figure the customer sees.

Models: annuity (Shpitzer, re-amortized when the rate changes), equal_principal, interest_only (bullet) and a
balloon on the annuity. A deferral (grace) before repayment is one of three explicit policies — it is never a free
holiday:
  capitalized            no payment; the month's interest is added to the balance;
  interest_only          the month's interest is paid;
  accrued_first_payment  no payment; the accrued interest is paid with the first installment.
`term_includes_deferral` says whether the deferral months are part of the stated term."""
from __future__ import annotations

from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext
from typing import Any, Optional

CENT = Decimal("0.01")
MODELS = ("annuity", "equal_principal", "interest_only")
DEFERRAL_POLICIES = ("capitalized", "interest_only", "accrued_first_payment")
CONVENTIONS = ("nominal", "effective")
MAX_MONTHS = 600


class CalcError(ValueError):
    def __init__(self, code: str, message_he: str):
        super().__init__(code)
        self.code, self.message_he = code, message_he


def _d(x: Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool) or x is None:
        raise CalcError("invalid_number", "ערך מספרי חסר או לא תקין")
    try:
        return Decimal(str(x))
    except Exception:
        raise CalcError("invalid_number", "ערך מספרי לא תקין") from None


def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_rate(annual_rate_pct: Any, convention: str = "nominal") -> Decimal:
    a = _d(annual_rate_pct)
    if a < 0 or a > 100:
        raise CalcError("invalid_rate", "שיעור הריבית צריך להיות בין 0% ל־100%")
    if convention not in CONVENTIONS:
        raise CalcError("invalid_convention", "סוג הריבית אינו מוכר")
    with localcontext() as ctx:
        ctx.prec = 34
        a = a / 100
        if convention == "nominal":
            return a / 12
        return (1 + a) ** (Decimal(1) / Decimal(12)) - 1


def annuity_payment(principal: Any, rate_m: Decimal, months: int, future_value: Any = 0) -> Decimal:
    """Exact level payment that turns `principal` into `future_value` (a balloon) after `months` periods."""
    p, fv = _d(principal), _d(future_value)
    if months <= 0:
        raise CalcError("invalid_term", "מספר התשלומים צריך להיות חיובי")
    with localcontext() as ctx:
        ctx.prec = 34
        if rate_m == 0:
            return (p - fv) / months
        f = (1 + rate_m) ** months
        return (p * f - fv) * rate_m / (f - 1)


def add_months(ym: str, k: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    t = y * 12 + (m - 1) + k
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def first_month(on: date) -> str:
    """The first installment month: the month after the loan is paid out (a stated assumption, not a bank rule)."""
    return add_months(f"{on.year:04d}-{on.month:02d}", 1)


def _validate(principal: Decimal, months: int, model: str, deferral: Optional[dict], balloon: Decimal,
              rate_changes: list[dict]) -> tuple[int, str, bool]:
    if principal <= 0 or principal > Decimal("1000000000"):
        raise CalcError("invalid_principal", "סכום ההלוואה צריך להיות חיובי")
    if not isinstance(months, int) or isinstance(months, bool) or not 1 <= months <= MAX_MONTHS:
        raise CalcError("invalid_term", "מספר התשלומים צריך להיות מספר שלם בין 1 ל־600")
    if model not in MODELS:
        raise CalcError("invalid_model", "שיטת ההחזר אינה נתמכת")
    d, policy, inclusive = 0, "capitalized", False
    if deferral:
        d = deferral.get("months") or 0
        policy = deferral.get("policy") or "capitalized"
        inclusive = bool(deferral.get("term_includes_deferral"))
        if not isinstance(d, int) or isinstance(d, bool) or not 0 <= d <= 24:
            raise CalcError("invalid_deferral", "תקופת הדחייה צריכה להיות בין 0 ל־24 חודשים")
        if policy not in DEFERRAL_POLICIES:
            raise CalcError("invalid_deferral_policy", "אופן חישוב הדחייה אינו מוגדר")
        if inclusive and d >= months:
            raise CalcError("invalid_deferral", "תקופת הדחייה ארוכה מתקופת ההלוואה")
    if balloon < 0 or balloon >= principal:
        raise CalcError("invalid_balloon", "תשלום הבלון צריך להיות קטן מסכום ההלוואה")
    if balloon and model != "annuity":
        raise CalcError("invalid_balloon", "תשלום בלון נתמך רק בהחזר שפיצר")
    total = months if inclusive else months + d
    last = 0
    for ch in rate_changes:
        k = ch.get("from_period")
        if not isinstance(k, int) or isinstance(k, bool) or not 2 <= k <= total or k <= last:
            raise CalcError("invalid_rate_change", "שינוי הריבית צריך לחול בחודש עתידי בתוך תקופת ההלוואה, בסדר עולה")
        last = k
    return d, policy, inclusive


def schedule(principal: Any, months: int, annual_rate_pct: Any, *, convention: str = "nominal",
             model: str = "annuity", rate_changes: Optional[list[dict]] = None, deferral: Optional[dict] = None,
             monthly_fee: Any = 0, upfront_fee: Any = 0, balloon: Any = 0, start_month: str = "2026-11") -> dict:
    """The full repayment schedule. `months` is the number of repayment installments (the stated term); with
    `term_includes_deferral` the deferral months are counted inside it. `rate_changes` = [{from_period, annual_rate_pct}]
    (period 1 is the first month after payout) — a what-if path, never a forecast."""
    p, b = _d(principal), _d(balloon)
    rate_changes = sorted(rate_changes or [], key=lambda c: c.get("from_period") or 0)
    d, policy, inclusive = _validate(p, months, model, deferral, b, rate_changes)
    fee_m, fee_0 = _d(monthly_fee), _d(upfront_fee)
    if fee_m < 0 or fee_0 < 0:
        raise CalcError("invalid_fee", "עמלה לא יכולה להיות שלילית")
    base = monthly_rate(annual_rate_pct, convention)
    rates = {c["from_period"]: monthly_rate(c["annual_rate_pct"], convention) for c in rate_changes}
    amort = months - d if inclusive else months
    total_periods = d + amort
    with localcontext() as ctx:
        ctx.prec = 34
        bal, accrued, r = p, Decimal(0), base
        rows: list[dict] = []
        pmt: Optional[Decimal] = None
        level: Optional[Decimal] = None
        for k in range(1, total_periods + 1):
            changed = k in rates
            if changed:
                r = rates[k]
            i = bal * r
            if k <= d:
                if policy == "capitalized":
                    pay, bal = Decimal(0), bal + i
                elif policy == "interest_only":
                    pay = i
                else:
                    pay, accrued = Decimal(0), accrued + i
                rows.append({"k": k, "pay": pay + fee_m, "int": i, "fee": fee_m, "bal": bal, "phase": "deferral"})
                continue
            j = k - d
            remaining = amort - j + 1
            if model == "annuity":
                if pmt is None or changed:
                    pmt = annuity_payment(bal, r, remaining, b)
                pay = bal + i if j == amort else pmt
            elif model == "equal_principal":
                if level is None:
                    level = bal / amort
                pay = bal + i if j == amort else level + i
            else:
                pay = bal + i if j == amort else i
            bal = bal + i - pay
            if j == 1 and accrued:
                pay, accrued = pay + accrued, Decimal(0)
            rows.append({"k": k, "pay": pay + fee_m, "int": i, "fee": fee_m, "bal": bal, "phase": "repay"})
        interest_exact = sum((x["int"] for x in rows), Decimal(0))
        fees_exact = fee_m * total_periods
    total_interest = money(interest_exact)
    total_fees = money(fees_exact) + money(fee_0)
    total_paid = money(p) + total_interest + money(fees_exact)
    out_rows = _reconcile(rows, total_paid, total_interest, start_month)
    repay = [x for x in out_rows if x["phase"] == "repay"]
    paying = [x for x in out_rows if x["payment"] > 0]
    # the regular installment: with accrued deferral interest the first one also carries that interest
    regular = repay[1] if d and policy == "accrued_first_payment" and len(repay) > 1 else repay[0]
    return {
        "principal": float(money(p)), "term_months": months, "amortizing_months": amort, "deferral_months": d,
        "deferral_policy": policy if d else None, "term_includes_deferral": inclusive if d else None,
        "periods": total_periods, "model": model, "convention": convention,
        "annual_rate_pct": float(_d(annual_rate_pct)), "monthly_rate": float(base),
        "rate_changes": [{"from_period": c["from_period"], "annual_rate_pct": float(_d(c["annual_rate_pct"]))}
                         for c in rate_changes],
        "monthly_payment": regular["payment"], "last_payment": out_rows[-1]["payment"],
        "max_payment": max(x["payment"] for x in repay), "min_payment": min(x["payment"] for x in repay),
        "first_payment": paying[0]["payment"] if paying else 0.0,
        "first_payment_month": paying[0]["month"] if paying else None,
        "first_repayment_month": repay[0]["month"], "start_month": start_month,
        "total_paid": float(total_paid), "total_interest": float(total_interest),
        "total_fees": float(total_fees), "upfront_fee": float(money(fee_0)),
        "total_cost": float(total_interest + total_fees),
        "balloon": float(money(b)),
        "rows": out_rows,
    }


def _reconcile(rows: list[dict], total_paid: Decimal, total_interest: Decimal, start_month: str) -> list[dict]:
    out, paid, interest = [], Decimal(0), Decimal(0)
    for n, x in enumerate(rows):
        last = n == len(rows) - 1
        pay = total_paid - paid if last else money(x["pay"])
        i = total_interest - interest if last else money(x["int"])
        paid, interest = paid + pay, interest + i
        fee = money(x["fee"])
        out.append({"period": x["k"], "month": add_months(start_month, x["k"] - 1), "phase": x["phase"],
                    "payment": float(pay), "interest": float(i), "fee": float(fee),
                    "principal": float(pay - i - fee), "balance": float(Decimal(0) if last else money(x["bal"]))})
    return out


def yearly(rows: list[dict]) -> list[dict]:
    """The schedule folded into 12-installment blocks (what a phone can show without a nested scroll)."""
    out: list[dict] = []
    for n in range(0, len(rows), 12):
        block = rows[n:n + 12]
        out.append({"year": n // 12 + 1, "from_month": block[0]["month"], "to_month": block[-1]["month"],
                    "paid": float(sum(Decimal(str(x["payment"])) for x in block)),
                    "interest": float(sum(Decimal(str(x["interest"])) for x in block)),
                    "principal": float(sum(Decimal(str(x["principal"])) for x in block)),
                    "balance": block[-1]["balance"]})
    return out


# ---------------------------------------------------------------- reverse simulation
def payment_for(principal: Any, months: int, annual_rate_pct: Any, convention: str = "nominal") -> Decimal:
    return money(annuity_payment(principal, monthly_rate(annual_rate_pct, convention), months))


def term_for_target(principal: Any, target: Any, annual_rate_pct: Any, term_min: int, term_max: int,
                    convention: str = "nominal") -> Optional[int]:
    """The SHORTEST term in [term_min, term_max] whose annuity payment is at most `target` (the least interest that
    meets it), or None when even the longest term is above the target."""
    t = _d(target)
    for n in range(max(1, term_min), term_max + 1):
        if payment_for(principal, n, annual_rate_pct, convention) <= t:
            return n
    return None


def principal_for_target(target: Any, months: int, annual_rate_pct: Any, convention: str = "nominal",
                         step: int = 1000) -> Decimal:
    """The largest principal, rounded DOWN to `step`, whose annuity payment over `months` is at most `target`."""
    t = _d(target)
    if t <= 0:
        return Decimal(0)
    r = monthly_rate(annual_rate_pct, convention)
    with localcontext() as ctx:
        ctx.prec = 34
        raw = t * months if r == 0 else t * (1 - (1 + r) ** -months) / r
    p = (raw / step).to_integral_value(rounding=ROUND_FLOOR) * step
    while p > 0 and payment_for(p, months, annual_rate_pct, convention) > t:
        p -= step
    return p


# ---------------------------------------------------------------- personal indicators (informational only)
def ratio_pct(numerator: Any, denominator: Any) -> Optional[float]:
    num, den = _d(numerator), _d(denominator)
    if den <= 0:
        return None
    return float((num / den * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def affordability(new_monthly: Any, net_income: Any, existing_monthly: Any = None) -> Optional[dict]:
    """Budget indicators from declared figures. No threshold and no verdict: the numbers only."""
    if net_income is None or _d(net_income) <= 0:
        return None
    new = money(_d(new_monthly))
    existing = money(_d(existing_monthly)) if existing_monthly is not None else None
    total = new + (existing or 0)
    net = money(_d(net_income))
    return {"new_monthly": float(new), "existing_monthly": float(existing) if existing is not None else None,
            "existing_known": existing is not None, "total_monthly": float(total), "net_income": float(net),
            "ratio_pct": ratio_pct(total, net), "new_only_ratio_pct": ratio_pct(new, net),
            "remaining": float(net - total)}
