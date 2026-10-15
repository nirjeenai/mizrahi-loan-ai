"""Deterministic financial arithmetic for the banker's intelligence view (Banker Intelligence V2).

Pure functions, no I/O and no model: a standard fixed-rate amortizing (annuity) loan, debt-service ratios and the
financing scenarios a banker can compare. Every assumption is a named DEMO constant below — none of them is a
Mizrahi-Tefahot rate, product bound or lending policy. The frontend's What-if simulator (frontend/src/finance.ts)
ports exactly these formulas and rounding rules; change both together.

Rounding: the monthly payment is shown rounded to agorot; as in a real schedule the last payment absorbs that rounding,
so interest = unrounded payment × term − principal (exactly 0 at 0%), rounded to agorot, and total payments =
principal + interest. Ratios are percentages with one decimal. Invalid input returns None, never a guessed number."""
from __future__ import annotations

from typing import Any, Optional

# Illustrative assumptions (DEMO). The same rate and repayment shares as the customer questionnaire's preliminary
# indication (feature/conversational-loan-v2, workflow/indication.py), so the two stages never contradict each other.
DEMO_ANNUAL_RATE_PCT = 6.0
DEMO_DSR_SALARIED_PCT = 30.0        # combined monthly debt service / net income, salaried income only
DEMO_DSR_WITH_BUSINESS_PCT = 25.0   # more conservative when any counted income comes from a business
DEMO_TERM_MIN, DEMO_TERM_MAX = 12, 120
SCENARIO_STEP_MONTHS = 24


def _raw_payment(principal: float, term_months: int, annual_rate_pct: float) -> Optional[float]:
    if principal is None or term_months is None or annual_rate_pct is None:
        return None
    if principal <= 0 or int(term_months) != term_months or term_months <= 0 or annual_rate_pct < 0:
        return None
    r = annual_rate_pct / 100 / 12
    return principal / term_months if r == 0 else principal * r / (1 - (1 + r) ** -term_months)


def monthly_payment(principal: float, term_months: int, annual_rate_pct: float) -> Optional[float]:
    """Annuity payment P·r / (1 − (1 + r)^−n), r = annual rate / 12; zero interest → P / n."""
    raw = _raw_payment(principal, term_months, annual_rate_pct)
    return None if raw is None else round(raw, 2)


def schedule(principal: float, term_months: int, annual_rate_pct: float) -> Optional[dict[str, Any]]:
    raw = _raw_payment(principal, term_months, annual_rate_pct)
    if raw is None:
        return None
    interest = 0.0 if annual_rate_pct == 0 else round(raw * term_months - principal, 2)
    return {"principal_ils": round(principal, 2), "term_months": int(term_months), "annual_rate_pct": annual_rate_pct,
            "monthly_payment_ils": round(raw, 2), "total_payments_ils": round(principal + interest, 2),
            "total_interest_ils": interest}


def ratio_pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or not denominator or denominator <= 0:
        return None
    return round(numerator / denominator * 100, 1)


def max_principal(monthly_budget: float, term_months: int, annual_rate_pct: float) -> Optional[float]:
    """The principal whose annuity payment equals `monthly_budget` (inverse of monthly_payment), rounded down to ₪1,000."""
    if monthly_budget is None or monthly_budget <= 0 or term_months <= 0 or annual_rate_pct < 0:
        return None
    r = annual_rate_pct / 100 / 12
    raw = monthly_budget * term_months if r == 0 else monthly_budget * (1 - (1 + r) ** -term_months) / r
    return float(int(raw // 1000) * 1000)


def scenario_terms(term_months: int) -> list[tuple[str, int]]:
    """Shorter / requested / longer terms around the requested one, inside the demo bounds, without duplicates."""
    keys = [("short", max(DEMO_TERM_MIN, term_months - SCENARIO_STEP_MONTHS)), ("requested", term_months),
            ("long", min(DEMO_TERM_MAX, term_months + SCENARIO_STEP_MONTHS))]
    out, seen = [], set()
    for key, t in keys:
        if t not in seen:
            seen.add(t)
            out.append((key, t))
    return out


def scenarios(principal: float, term_months: int, annual_rate_pct: float, income_ils: Optional[float],
              existing_debt_ils: Optional[float], asset_price_ils: Optional[float]) -> list[dict[str, Any]]:
    """One row per term. A ratio is computed only when its inputs exist; existing debt service that is unknown (None)
    is never treated as zero — the row says the combined ratio covers the proposed loan only."""
    out = []
    for key, t in scenario_terms(term_months):
        s = schedule(principal, t, annual_rate_pct)
        if s is None:
            continue
        combined = s["monthly_payment_ils"] + (existing_debt_ils or 0)
        out.append({**s, "key": key,
                    "combined_debt_service_ils": round(combined, 2),
                    "combined_dsr_pct": ratio_pct(combined, income_ils),
                    "combined_includes_existing": existing_debt_ils is not None,
                    "ltv_pct": ratio_pct(principal, asset_price_ils),
                    "remaining_after_debt_ils": round(income_ils - combined, 2) if income_ils else None})
    return out


def threshold_pct(business_income: bool) -> float:
    return DEMO_DSR_WITH_BUSINESS_PCT if business_income else DEMO_DSR_SALARIED_PCT
