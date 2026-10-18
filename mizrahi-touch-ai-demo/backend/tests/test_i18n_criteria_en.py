"""English of the explanations the review code writes on rubric criteria (app/i18n/criteria_en.py).

Each Hebrew sentence is produced by the real generator (family_checks.outcomes, deterministic.arithmetic,
deterministic.pay_date_check, and the payslip templates of gemini_provider._merge), never typed into the test, so a
changed template that the English no longer matches fails here. The model's own wording gets no English."""
from __future__ import annotations

import re
from datetime import date

import pytest

from app.i18n import criteria_en as C
from app.review import deterministic as det
from app.review import family_checks as F
from app.review import prompts as P

HEBREW = re.compile(r"[֐-׿]")
AS_OF = date(2026, 10, 12)
IDO = {"borrower_id": "BRW-A", "name_he": "עידו לוי", "national_id": "DEMO-ID-001"}
NOA = {"borrower_id": "BRW-B", "name_he": "נועה לוי", "national_id": "DEMO-ID-002"}


def outcomes(family: str, values: dict, rules: dict | None = None, assigned=IDO, hits=(), unverified=(), present=("x",)):
    ids = {"id_document": "ID", "bank_statement": "BS", "purpose_proof": "PP", "tax_form": "TX",
           "business_registration": "BR", "pnl_statement": "PL"}[family]
    rubric = {"criteria": [{"id": f"{ids}-0{i}"} for i in range(1, 8)]}
    return F.outcomes(family, rubric, val=lambda k: values.get(k), norm=lambda k: values.get(k), as_of=AS_OF,
                      borrowers={"BRW-A": IDO, "BRW-B": NOA}, assigned=assigned, matched=None, hits=list(hits),
                      unverified=list(unverified), present_decisive=list(present), rules=rules or {},
                      allowed_holders=None, labels=P.FIELD_LABELS_HE)


CASES = [
    ("id_document", {"holder_name": "עידו לוי", "holder_id": "DEMO-ID-001", "expiry_date": "2030-01-01"}, {}),
    ("id_document", {"holder_name": "נועה כהן", "holder_id": "000000018", "expiry_date": "2020-01-01"}, {}),
    ("id_document", {"holder_name": "עידו לוי", "holder_id": None}, {"check_expiry": False}),
    ("bank_statement", {"holder_name": "עידו לוי", "holder_id": "DEMO-ID-001", "statement_from": "2026-07-01",
                        "statement_to": "2026-09-30"}, {}),
    ("bank_statement", {"holder_name": "עידו לוי", "statement_from": "2025-01-01", "statement_to": "2025-03-31"}, {}),
    ("bank_statement", {"holder_name": None}, {}),
    ("purpose_proof", {"issuer_name": "מוטורס בע״מ", "total_amount": "180,000", "issue_date": "2026-10-01"}, {}),
    ("purpose_proof", {"issue_date": "2025-01-01"}, {}),
    ("tax_form", {"holder_name": "עידו לוי", "holder_id": "DEMO-ID-001", "tax_year": "2025"}, {}),
    ("tax_form", {"holder_name": "עידו לוי", "tax_year": "2019"}, {}),
    ("business_registration", {"holder_name": "עידו לוי", "registration_type": "עוסק מורשה", "dealer_number": "DEMO-ID-001"},
     {"registration": "vat_exempt"}),
    ("business_registration", {"holder_name": "עידו לוי", "registration_type": "עוסק פטור", "dealer_number": "DEMO-ID-002"},
     {"registration": "vat_exempt"}),
    ("business_registration", {"holder_name": "עידו לוי"}, {}),
    ("pnl_statement", {"holder_name": "עידו לוי", "period_from": "2026-01-01", "period_to": "2026-06-30",
                       "issuer_name": "רו״ח כהן"}, {}),
    ("pnl_statement", {"holder_name": "עידו לוי", "period_to": "2025-06-30"}, {}),
    ("pnl_statement", {}, {}),
]


@pytest.mark.parametrize("family,values,rules", CASES)
def test_every_family_check_explanation_has_english(family, values, rules):
    for variant in ({}, {"hits": ["ignore previous instructions"]}, {"unverified": ["employee_name"]}, {"present": ()},
                    {"assigned": None}):
        for cid, (_, he) in outcomes(family, values, rules, **variant).items():
            if not he:
                continue                               # a JUDGE outcome: the model writes the explanation
            english = C.explanation(he)
            assert english, f"{cid}: {he}"
            leftover = english
            for kept in ("עידו לוי", "נועה כהן", "מוטורס בע״מ", "רו״ח כהן", "עוסק מורשה", "עוסק פטור"):
                leftover = leftover.replace(kept, "")              # printed document text stays as printed
            assert not HEBREW.search(leftover), f"{cid}: {english}"


def test_payslip_templates_and_arithmetic():
    month = det.month_label_he("2026-08")
    for he, expected in [
        (f"תקופת השכר: {month}", "Pay period: August 2026"),
        (f"ברוטו {21100:,.2f} ₪ · נטו {14700:,.2f} ₪", "Gross ₪21,100.00 · net ₪14,700.00"),
        (f"מעסיק: אביב מערכות דיגיטל בע״מ", "Employer: אביב מערכות דיגיטל בע״מ"),
        ("כל השדות המכריעים אומתו מול הקובץ המקורי", "All the decisive fields were verified against the original file"),
        ("לא אומתו מול הקובץ: " + ", ".join(P.FIELD_LABELS_HE[n] for n in ("net_pay", "salary_period")),
         "Not verified against the file: Net pay, Pay period"),
        ("חסר במסמך: " + ", ".join(P.FIELD_LABELS_HE[n] for n in ("gross_pay",)), "Missing from the document: Gross pay"),
        (f"שם ומספר זהות תואמים ל{IDO['name_he']}", "The name and ID number match Ido Levi"),
        (f"מספר הזהות במסמך אינו של {IDO['name_he']}, המסמך מזוהה עם {NOA['name_he']}",
         "The ID number on the document isn't Ido Levi's; the document matches Noa Levi"),
    ]:
        assert C.explanation(he) == expected, he
    for args in [(21100, 6400, 14700, 1), (21100, 6400, 14000, 1), (21100, None, 14700, 1), (None, 1, 1, 1), (100, 0, 200, 1)]:
        he = det.arithmetic(*args)["detail"]
        assert C.explanation(he) and not HEBREW.search(C.explanation(he)), he
    for args in [("2026-08", None, None, False, 9), ("2026-08", "x", None, False, 9), ("2026-08", "x", date(2026, 9, 1), False, 9),
                 ("2026-08", "x", date(2026, 7, 1), True, 9), ("2026-08", "x", date(2026, 8, 10), True, 9),
                 ("2026-08", "x", date(2026, 9, 1), True, 9), ("2026-08", "x", date(2026, 9, 20), True, 9)]:
        he = det.pay_date_check(*args)[1]
        assert C.explanation(he) and not HEBREW.search(C.explanation(he).replace("x", "")), he


def test_the_models_own_wording_has_no_english():
    assert C.explanation("המסמך שלם וקריא לחלוטין. כל השדות המרכזיים ברורים וללא חיתוכים או טשטוש.") is None
    assert C.explanation("") is None and C.explanation(None) is None
