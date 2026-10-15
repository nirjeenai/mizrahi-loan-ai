"""Demo Bank Financial Context Adapter — existing obligations, credit lines and account context per customer.

Synthetic and deterministic: it reads one fixture (backend/bank_context/demo_financial_context.v1.json) keyed by the
customer's national id, so the same person carries the same obligations in every case. Every value it returns carries
source=DEMO_BANK_FINANCIAL_CONTEXT, authoritative=false, synthetic=true and the fixture's observation date. It reaches
no bank system, credit bureau, Bank of Israel credit register or open-banking API; a real adapter would implement
`for_borrower` against an authorized source.

Three things are kept apart on purpose: an outstanding balance (what is owed), a monthly payment (debt service) and a
credit line's limit/utilization (exposure, אובליגו). Card spending is an expense, never debt service."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

FIXTURE = Path(__file__).resolve().parents[2] / "bank_context" / "demo_financial_context.v1.json"


@lru_cache(maxsize=1)
def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf8"))


def source() -> dict[str, Any]:
    f = _fixture()
    return {"source": f["source"], "authoritative": f["authoritative"], "synthetic": f["synthetic"], "schema": f["schema"],
            "note_he": f["note_he"]}


def for_borrower(borrower: dict) -> Optional[dict[str, Any]]:
    """The borrower's synthetic bank context with derived totals, or None when the fixture has no record of them."""
    rec = _fixture()["customers"].get(borrower.get("national_id") or "")
    if not rec:
        return None
    loans = rec.get("loans", [])
    lines = rec.get("credit_lines", [])
    outstanding = round(sum(x["outstanding_ils"] for x in loans), 2)
    return {**source(), **rec, "borrower_id": borrower["borrower_id"],
            "totals": {"monthly_debt_service_ils": round(sum(x["monthly_payment_ils"] for x in loans), 2),
                       "loans_outstanding_ils": outstanding,
                       "credit_limits_ils": round(sum(x["limit_ils"] for x in lines), 2),
                       "credit_utilized_ils": round(sum(x["utilized_ils"] for x in lines), 2),
                       "exposure_approved_ils": round(outstanding + sum(x["limit_ils"] for x in lines), 2),
                       "exposure_utilized_ils": round(outstanding + sum(x["utilized_ils"] for x in lines), 2)}}
