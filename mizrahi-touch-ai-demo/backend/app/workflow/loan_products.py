"""Loan product registry for the chat's loan simulator: which products a conversation can simulate, their limits,
the features each one exposes, and where every rule comes from. Data lives in
`backend/loan_products/products.demo.v1.json`; this module only loads, validates and reads it.

A limit has a basis: "verified" (read from the bank's public product page on `checked_on`), "demo" (an engineering
default of this demo) or "flow" (the bounds of the application flow, `onboarding.NUMBER_BOUNDS`). A product the
customer explores is a *candidate*: the bank decides the actual product.

Rate source hierarchy (`rate_for`): a valid bank quote → an authorised pricing configuration → a labelled
illustrative assumption (demo, `LOAN_SIM_ILLUSTRATIVE_RATE`) → unknown. This demo has neither a quote integration
nor pricing data, so it uses the illustration — the same 6% nominal rate as the preliminary indication and the
banker's briefing (`finance.DEMO_ANNUAL_RATE_PCT`) — or, for the banker-assisted company path, no rate at all."""
from __future__ import annotations

import json
from decimal import ROUND_FLOOR, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from ..config import settings
from . import finance

PATH = Path(__file__).resolve().parents[2] / "loan_products" / "products.demo.v1.json"
BASES = {"verified", "demo", "flow"}


@lru_cache(maxsize=1)
def registry() -> dict:
    data = json.loads(PATH.read_text(encoding="utf8"))
    ids = [p["id"] for p in data["products"]]
    assert len(ids) == len(set(ids)), "duplicate product id"
    for p in data["products"]:
        t = p["term"]
        assert 1 <= t["min"] <= t["max"] <= data["flow_bounds"]["term"]["max"], p["id"]
        assert t["min_basis"] in BASES and t["max_basis"] in BASES, p["id"]
        assert p["rate"] in ("illustrative", "unavailable"), p["id"]
        assert set(p["features"]["repayment_models"]) <= {"annuity", "equal_principal"}, p["id"]
        ratio = p["amount"].get("max_financing_ratio")
        assert ratio is None or (0 < ratio <= 1 and p.get("asset")), p["id"]
        d = p["features"].get("deferral")
        assert d is None or (d["default_policy"] in d["illustrative_policies"] and d["max_months"] >= 1), p["id"]
    for key, cands in data["candidates"].items():
        assert cands and all(c in ids for c in cands), key
    return data


def product(pid: str) -> dict:
    return next(p for p in registry()["products"] if p["id"] == pid)


def exists(pid: Optional[str]) -> bool:
    return any(p["id"] == pid for p in registry()["products"])


def candidates(purpose: Optional[str], sole_business: bool, company: bool) -> list[str]:
    c = registry()["candidates"]
    if company:
        return c["_company"]
    if sole_business:
        return c["_sole_business"]
    return c.get(purpose or "", c["other"])


def amount_field(p: dict) -> str:
    return p.get("amount_field") or "amount"


def bounds(p: dict) -> dict[str, Any]:
    """Slider bounds and the basis of each one. A financing ratio is a rule, not a bound: it is checked separately."""
    flow = registry()["flow_bounds"][amount_field(p)]
    hi, hi_basis = flow["max"], "flow"
    if p["amount"].get("max") is not None and p["amount"]["max"] <= hi:
        hi, hi_basis = p["amount"]["max"], p["amount"].get("max_basis", "verified")
    t = p["term"]
    return {"amount_min": flow["min"], "amount_max": hi, "amount_max_basis": hi_basis, "amount_step": flow["step"],
            "term_min": t["min"], "term_min_basis": t["min_basis"], "term_max": t["max"], "term_max_basis": t["max_basis"]}


def rate_for(p: dict, quote: Optional[dict] = None) -> dict[str, Any]:
    """The rate the simulator may use, with its source. `quote` is the slot for a real bank quote (none in this demo)."""
    if quote and quote.get("annual_rate_pct") is not None:
        return {"available": True, "source": "bank_quote", "annual_rate_pct": float(quote["annual_rate_pct"]),
                "convention": quote.get("convention", "nominal"), "label_he": "הצעת ריבית אישית מהבנק"}
    if p.get("pricing"):
        pr = p["pricing"]
        return {"available": True, "source": "pricing_config", "annual_rate_pct": float(pr["annual_rate_pct"]),
                "convention": pr.get("convention", "nominal"), "label_he": "ריבית לפי תמחור המסלול"}
    if p["rate"] == "illustrative" and settings.loan_sim_illustrative_rate:
        return {"available": True, "source": "illustrative", "annual_rate_pct": finance.DEMO_ANNUAL_RATE_PCT,
                "convention": "nominal",
                "label_he": f"ריבית להמחשה {finance.DEMO_ANNUAL_RATE_PCT:g}% לשנה (נומינלית, קבועה, לא צמודה). זו לא ריבית של הבנק"}
    reason = ("במסלול לחברות אין חישוב החזר אוטומטי, הבנקאי/ת יחזרו עם הצעה." if p["id"] == "company"
              else "אין לנו ריבית למסלול הזה, ולכן לא מוצג החזר חודשי.")
    return {"available": False, "source": "unavailable", "annual_rate_pct": None, "convention": None, "label_he": reason}


def _ils(n: float) -> str:
    return f"{int(n):,} ₪"


def max_by_ratio(p: dict, asset_price: Optional[float], step: int) -> Optional[int]:
    ratio = p["amount"].get("max_financing_ratio")
    if not ratio or not asset_price:
        return None
    raw = Decimal(str(ratio)) * Decimal(str(asset_price))
    return int((raw / step).to_integral_value(rounding=ROUND_FLOOR) * step)


def issues(p: dict, amount: Optional[float], term: Optional[int], asset_price: Optional[float] = None,
           deferral_months: int = 0) -> list[dict[str, Any]]:
    """What the product rules say about a scenario, each with a constructive fix. An empty list = within the rules
    this demo knows; it is never an eligibility statement."""
    b, out = bounds(p), []
    label = p["label_he"]
    if amount is not None:
        if amount < b["amount_min"]:
            out.append({"code": "amount_below_min", "field": "amount", "fix": b["amount_min"],
                        "message_he": f"הסכום הנמוך בסימולציה הוא {_ils(b['amount_min'])}."})
        elif amount > b["amount_max"]:
            where = f"ב{label} אפשר עד" if b["amount_max_basis"] == "verified" else "בסימולציה אפשר עד"
            out.append({"code": "amount_above_max", "field": "amount", "fix": b["amount_max"],
                        "message_he": f"{where} {_ils(b['amount_max'])}. אפשר להפחית את הסכום או לבדוק מסלול אחר."})
        cap = max_by_ratio(p, asset_price, 1)
        if cap is not None and amount > cap:
            pct = round(amount / asset_price * 100, 1)
            limit = int(p["amount"]["max_financing_ratio"] * 100)
            fix = max_by_ratio(p, asset_price, b["amount_step"])
            out.append({"code": "financing_ratio", "field": "amount", "fix": fix, "ratio_pct": pct, "limit_pct": limit,
                        "message_he": f"הסכום שבחרת הוא {pct:g}% ממחיר הרכב, גבוה משיעור המימון במסלול זה (עד {limit}%). "
                                      f"אפשר להפחית את סכום ההלוואה ל־{_ils(fix)} או לבדוק אפשרויות נוספות."})
    if term is not None:
        if term < b["term_min"]:
            out.append({"code": "term_below_min", "field": "term", "fix": b["term_min"],
                        "message_he": f"התקופה הקצרה בסימולציה היא {b['term_min']} חודשים."})
        elif term > b["term_max"]:
            where = f"ב{label} התקופה עד" if b["term_max_basis"] == "verified" else "בסימולציה התקופה עד"
            out.append({"code": "term_above_max", "field": "term", "fix": b["term_max"],
                        "message_he": f"{where} {b['term_max']} חודשים. אפשר לקצר את התקופה או לבדוק מסלול אחר."})
    d = p["features"].get("deferral")
    if deferral_months and (not d or deferral_months > d["max_months"]):
        out.append({"code": "deferral_not_supported", "field": "deferral", "fix": d["max_months"] if d else 0,
                    "message_he": (f"אפשר לדחות את התשלום הראשון בעד {d['max_months']} חודשים." if d
                                   else f"ב{label} אין דחיית תשלום ראשון.")})
    return out


def public(p: dict) -> dict[str, Any]:
    """The product as the simulator UI needs it (rules, features, sources, rate) — the UI never invents a rule."""
    return {"id": p["id"], "label_he": p["label_he"], "short_he": p["short_he"], "source_url": p["source_url"],
            "verified_he": p["verified_he"], "not_applicable_he": p.get("not_applicable_he"),
            "amount_field": amount_field(p), "max_financing_ratio": p["amount"].get("max_financing_ratio"),
            "asset": p.get("asset"), "features": p["features"], "defaults": p["defaults"], "bounds": bounds(p),
            "rate": rate_for(p)}
