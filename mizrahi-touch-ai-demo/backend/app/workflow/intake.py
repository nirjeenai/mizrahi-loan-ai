"""Customer-started personal-loan applications (demo intake).

The customer states what the application is about — purpose, amount, payments, employment, declared income — and the
case is created with synthetic bank-side data. Nothing here assesses eligibility or prices credit: the requirements
the case must satisfy come from the published loan policy (workflow/requirements.py), conditions included (a
self-employed applicant gets a tax assessment instead of payslips). Stored in DATA_DIR; a demo convenience only."""
from __future__ import annotations

import secrets
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .. import db
from ..bank import mock_bank
from ..policy import store
from ..util import now_iso


class Application(BaseModel):
    first_name_he: str = Field(..., min_length=2, max_length=30)
    last_name_he: str = Field(..., min_length=2, max_length=30)
    purpose: str = Field(..., max_length=30)
    requested_amount_ils: int = Field(..., ge=5000, le=250000)
    payments: int = Field(..., ge=2, le=120)
    employment: Literal["salaried", "self_employed"]
    employer_he: str = Field("", max_length=60)
    declared_net_monthly_ils: int = Field(..., ge=0, le=200000)

    @field_validator("first_name_he", "last_name_he", "employer_he")
    @classmethod
    def _plain(cls, v: str) -> str:
        v = " ".join(v.split())
        if any(ch in v for ch in "<>{}\\"):
            raise ValueError("תווים לא מורשים")
        return v


class IntakeRefused(ValueError):
    pass


def options() -> dict:
    pol, row = store.policy()
    return {"product_he": pol.product.label_he, "policy_version": row["label"],
            "purposes": [{"id": k, "label_he": p.label_he, "proof_he": p.proof_he} for k, p in pol.product.purposes.items()
                         if p.entity == "individual"],
            "amount": {"min": 5000, "max": 250000}, "payments": {"min": 2, "max": 120},
            "note_he": "פרטי הבקשה משמשים רק לקביעת המסמכים הנדרשים. הם אינם בדיקת זכאות ואינם הצעת אשראי."}


def create(app: Application) -> str:
    pol, _ = store.policy()
    purpose = pol.product.purposes.get(app.purpose)
    if purpose is None or purpose.entity != "individual":
        raise IntakeRefused("מטרת ההלוואה אינה אחת מהמטרות של המסלול")
    count = (db.one("SELECT COUNT(*) AS n FROM demo_applications") or {"n": 0})["n"]
    if count >= 200:
        raise IntakeRefused("הגעתם למספר המרבי של בקשות פתוחות")
    case_id = f"DEMO-LN-{count + 1:04d}-{secrets.token_hex(2).upper()}"
    borrower = {"borrower_id": "BRW-A", "name_he": f"{app.first_name_he} {app.last_name_he}", "first_name_he": app.first_name_he,
                "national_id": f"DEMO-ID-{500 + count:03d}", "employment": app.employment, "role": "primary",
                "employer_declared_he": app.employer_he or ("עסק עצמאי" if app.employment == "self_employed" else ""),
                "declared_net_monthly_ils": app.declared_net_monthly_ils, "declaration_note_he": "הוצהר בבקשה המקוונת"}
    case = mock_bank._case(case_id, f"4388{secrets.randbelow(90000) + 10000}", f"{pol.product.label_he} · {purpose.label_he}",
                           [borrower], mock_bank._loan(app.purpose, purpose.label_he, app.requested_amount_ils, app.payments),
                           mock_bank._accounts(["BRW-A"]), submitted_at=now_iso(), customer_started=True,
                           persona_id=f"PRS-NEW-{case_id[-4:]}", applicant_type="individual")
    case["stage_index"] = 1
    with db.tx() as c:
        c.execute("INSERT INTO demo_applications(case_id, created_at, application) VALUES (?,?,?)",
                  (case_id, now_iso(), db.jdump(case)))
    return case_id
