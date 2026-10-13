"""MockBankAdapter — the ONLY source of bank-side case data in this demo, and it is
synthetic. Every value carries source=DEMO_BANK_ADAPTER and authoritative=false.
The real adapter (P2) implements the same methods against bank-approved APIs."""
from __future__ import annotations

import copy
from datetime import date
from typing import Any, Optional

from ..config import settings

SOURCE = {"source": "DEMO_BANK_ADAPTER", "authoritative": False}

# Observed in a user-provided Tefahot Touch screenshot: a 5-step ring showing "2/5 קיבלנו החלטה".
# Only that label is observed; the other four are demo assumptions, not a verified bank enum.
STAGE_DICTIONARY = [
    {"index": 1, "code": "APPLICATION_SUBMITTED", "label_he": "הגשנו בקשה", "observed": False},
    {"index": 2, "code": "DECISION_RECEIVED", "label_he": "קיבלנו החלטה", "observed": True},
    {"index": 3, "code": "DOCUMENTS_AND_CHECKS", "label_he": "השלמת מסמכים ובדיקות", "observed": False},
    {"index": 4, "code": "SIGNING", "label_he": "חתימה על מסמכי ההלוואה", "observed": False},
    {"index": 5, "code": "DISBURSEMENT", "label_he": "העמדת ההלוואה", "observed": False},
]

# Demo staff directory. The banker console works on a staff session issued by app/auth.py (in demo mode, without a
# login); the service then checks the case assignment. A real adapter would take identity from bank SSO.
STAFF = {
    "STAFF-DANA": {"staff_id": "STAFF-DANA", "name_he": "דנה כהן", "role_he": "מומחית משכנתאות"},
    "STAFF-ORI": {"staff_id": "STAFF-ORI", "name_he": "אורי לוי", "role_he": "מומחה משכנתאות"},
}

# The presenter golden set (fixtures/presenter/golden_set/CASE_PROFILE.json) prints these identities; its PDFs
# are reviewed only in the two cases that carry them, so the Lavi cases above stay untouched.
_GOLDEN_SET_BORROWERS = [
    {"borrower_id": "BRW-A", "name_he": "עידו לוי", "first_name_he": "עידו", "national_id": "DEMO-ID-001",
     "employment": "salaried", "employer_declared_he": "אביב מערכות דיגיטל בע״מ",
     "declared_net_monthly_ils": 14700, "declaration_note_he": "הוצהר בטופס הבקשה"},
    {"borrower_id": "BRW-B", "name_he": "נועה לוי", "first_name_he": "נועה", "national_id": "DEMO-ID-002",
     "employment": "salaried", "employer_declared_he": "אורן פתרונות תוכנה בע״מ",
     "declared_net_monthly_ils": 18500, "declaration_note_he": "הוצהר בטופס הבקשה"},
]

_GOLDEN_SET_CASE = {
    "stage_index": 2,
    "preliminary_decision": {"label_he": "אישור עקרוני", "issued_on": "2026-10-05", "valid_until": "2027-01-03",
                             "amount_ils": 1500000},
    "requested_loan_ils": 1500000,
    "property": {"purpose_he": "רכישת דירה יד שנייה", "city_he": "רמת גן", "price_ils": 2400000},
    "submitted_at": "2026-10-02T10:00:00+03:00",
    "banker": {"name_he": "דנה כהן", "role_he": "מומחית המשכנתאות שלך", "staff_id": "STAFF-DANA"},
    "meeting": None,
    "borrowers": _GOLDEN_SET_BORROWERS,
}

_CASES: dict[str, dict[str, Any]] = {
    "DEMO-MTZ-2026-001": {
        "case_id": "DEMO-MTZ-2026-001",
        "display_number": "438838921",
        "title_he": "קניית דירה יד שנייה",
        "stage_index": 2,
        "preliminary_decision": {"label_he": "אישור עקרוני", "issued_on": "2026-09-21", "valid_until": "2026-12-20",
                                 "amount_ils": 1400000},
        "requested_loan_ils": 1400000,
        "property": {"purpose_he": "רכישת דירה יד שנייה", "city_he": "חיפה", "price_ils": 2000000},
        "submitted_at": "2026-09-14T10:32:00+03:00",
        "banker": {"name_he": "דנה כהן", "role_he": "מומחית המשכנתאות שלך", "staff_id": "STAFF-DANA"},
        "meeting": {"date": "2026-10-20", "from": "10:00", "to": "11:00", "type_he": "פגישת חתימה בסניף חיפה"},
        "borrowers": [
            {"borrower_id": "BRW-A", "name_he": "עידו לביא", "first_name_he": "עידו", "national_id": "039812457",
             "employment": "salaried", "employer_declared_he": "אופק לוגיסטיקה בע״מ",
             "declared_net_monthly_ils": 13500, "declaration_note_he": "שכר קבוע"},
            {"borrower_id": "BRW-B", "name_he": "נועה לביא", "first_name_he": "נועה", "national_id": "204376815",
             "employment": "salaried", "employer_declared_he": "גלי טכנולוגיות בע״מ",
             "declared_net_monthly_ils": 18500, "declaration_note_he": "ייתכנו רכיבים משתנים"},
        ],
    },
    "DEMO-MTZ-2026-003": {
        "case_id": "DEMO-MTZ-2026-003",
        "display_number": "438838999",
        "title_he": "תיק בדיקות QA — מסמכים בעייתיים",
        "stage_index": 2,
        "preliminary_decision": {"label_he": "אישור עקרוני", "issued_on": "2026-09-21", "valid_until": "2026-12-20",
                                 "amount_ils": 1400000},
        "requested_loan_ils": 1400000,
        "property": {"purpose_he": "רכישת דירה יד שנייה", "city_he": "חיפה", "price_ils": 2000000},
        "submitted_at": "2026-09-14T10:32:00+03:00",
        "banker": {"name_he": "דנה כהן", "role_he": "מומחית המשכנתאות שלך", "staff_id": "STAFF-DANA"},
        "meeting": None,
        "borrowers": [
            {"borrower_id": "BRW-A", "name_he": "עידו לביא", "first_name_he": "עידו", "national_id": "039812457",
             "employment": "salaried", "employer_declared_he": "אופק לוגיסטיקה בע״מ",
             "declared_net_monthly_ils": 13500, "declaration_note_he": "שכר קבוע"},
            {"borrower_id": "BRW-B", "name_he": "נועה לביא", "first_name_he": "נועה", "national_id": "204376815",
             "employment": "salaried", "employer_declared_he": "גלי טכנולוגיות בע״מ",
             "declared_net_monthly_ils": 18500, "declaration_note_he": "ייתכנו רכיבים משתנים"},
        ],
    },
    "DEMO-MTZ-2026-002": {
        "case_id": "DEMO-MTZ-2026-002",
        "display_number": "438840117",
        "title_he": "מחזור משכנתא",
        "stage_index": 1,
        "preliminary_decision": None,
        "requested_loan_ils": 600000,
        "property": {"purpose_he": "מחזור משכנתא", "city_he": "רמת גן", "price_ils": 1650000},
        "submitted_at": "2026-10-01T09:10:00+03:00",
        "banker": {"name_he": "אורי לוי", "role_he": "מומחה המשכנתאות שלך", "staff_id": "STAFF-ORI"},
        "meeting": None,
        "borrowers": [
            {"borrower_id": "BRW-C", "name_he": "מיכל ברק", "first_name_he": "מיכל", "national_id": "311204578",
             "employment": "salaried", "employer_declared_he": "שחף הנדסה בע״מ",
             "declared_net_monthly_ils": 21000, "declaration_note_he": "שכר קבוע"},
        ],
    },
    "DEMO-MTZ-2026-004": {
        "case_id": "DEMO-MTZ-2026-004",
        "display_number": "438839004",
        "title_he": "תרחישי בדיקה — דירה יד שנייה",
        **_GOLDEN_SET_CASE,
    },
    "DEMO-MTZ-2026-005": {
        "case_id": "DEMO-MTZ-2026-005",
        "display_number": "438839005",
        "title_he": "תרחישי בדיקה — תיק QA מבודד",
        **_GOLDEN_SET_CASE,
    },
    # Executive demo: one borrower per case, so each featured scenario has its own case-wide status. The presenter
    # manifest maps scenarios to these cases; nothing here says what a review of them should conclude.
    "DEMO-MTZ-2026-006": {
        "case_id": "DEMO-MTZ-2026-006",
        "display_number": "438839006",
        "title_he": "דירה יד שנייה · הדגמה א׳",
        "executive_demo": True,
        **{**_GOLDEN_SET_CASE, "borrowers": [_GOLDEN_SET_BORROWERS[0]]},
    },
    "DEMO-MTZ-2026-007": {
        "case_id": "DEMO-MTZ-2026-007",
        "display_number": "438839007",
        "title_he": "דירה יד שנייה · הדגמה ב׳",
        "executive_demo": True,
        **{**_GOLDEN_SET_CASE, "borrowers": [_GOLDEN_SET_BORROWERS[1]]},
    },
    "DEMO-MTZ-2026-008": {
        "case_id": "DEMO-MTZ-2026-008",
        "display_number": "438839008",
        "title_he": "דירה יד שנייה · הדגמה ג׳",
        "executive_demo": True,
        **{**_GOLDEN_SET_CASE, "borrowers": [_GOLDEN_SET_BORROWERS[0]]},
    },
}

# Requirement inventory. Payslips are evaluated by the AI layer; the rest are listed with
# their (mock) bank status and are explicitly NOT evaluated in this demo.
_OTHER_REQUIREMENTS = [
    {"code": "BANK_STATEMENTS:ALL", "title_he": "דפי תנועות עו״ש — 3 חודשים אחרונים, כל החשבונות", "family": "income"},
    {"code": "LOAN_BALANCES:ALL", "title_he": "דוח ריכוז יתרות הלוואות", "family": "liabilities"},
    {"code": "APPRAISAL", "title_he": "שמאות — מועברת ישירות מהשמאי לבנק", "family": "property"},
    {"code": "LIFE_INSURANCE", "title_he": "פוליסת ביטוח חיים משועבדת לבנק", "family": "insurance"},
    {"code": "PROPERTY_INSURANCE", "title_he": "פוליסת ביטוח נכס משועבדת לבנק", "family": "insurance"},
    {"code": "SELLER_DOCUMENTS", "title_he": "מסמכי מוכר ובטוחות (התחייבות מוכר, הערת אזהרה, אישורי מיסים)", "family": "collateral"},
]


class MockBankAdapter:
    name = "mock-bank"

    def case_ids(self) -> list[str]:
        return list(_CASES)

    def executive_demo_case_ids(self) -> list[str]:
        """The only cases the presenter's "start a new demo" control may wipe."""
        return [cid for cid, c in _CASES.items() if c.get("executive_demo")]

    def get_case(self, case_id: str) -> dict[str, Any]:
        if case_id not in _CASES:
            raise KeyError(case_id)
        case = copy.deepcopy(_CASES[case_id])
        stage = STAGE_DICTIONARY[case["stage_index"] - 1]
        case["bank_stage"] = {**SOURCE, "index": stage["index"], "of": len(STAGE_DICTIONARY), "code": stage["code"],
                              "label_he": stage["label_he"], "label_observed_in_screenshot": stage["observed"]}
        case["source"] = SOURCE
        for b in case["borrowers"]:
            b["declared_income_provenance"] = "CUSTOMER_DECLARED"
        return case

    def staff(self, staff_id: str) -> Optional[dict[str, Any]]:
        return copy.deepcopy(STAFF.get(staff_id))

    def customer_cases(self, national_id: str) -> list[str]:
        """The cases in which this person is a borrower (a data lookup; no credential is involved)."""
        return [cid for cid, c in _CASES.items() if any(b["national_id"] == national_id for b in c["borrowers"])]

    def stage_dictionary(self) -> dict[str, Any]:
        return {**SOURCE, "stages": STAGE_DICTIONARY,
                "note_he": "מילון שלבים להדגמה. רק התווית ״קיבלנו החלטה״ נצפתה בצילום מסך של טפחות טאצ׳; שאר השלבים הם הנחת דמו."}

    def requirements(self, case_id: str) -> list[dict[str, Any]]:
        case = self.get_case(case_id)
        reqs = []
        for b in case["borrowers"]:
            if b["employment"] == "salaried":
                reqs.append({"code": f"PAYSLIPS:{b['borrower_id']}", "family": "income", "borrower_id": b["borrower_id"],
                             "title_he": f"3 תלושי שכר אחרונים — {b['first_name_he']}", "evaluated_by_ai": True,
                             "bank_status": "awaiting_documents", **SOURCE})
        for r in _OTHER_REQUIREMENTS:
            reqs.append({**r, "borrower_id": None, "evaluated_by_ai": False, "bank_status": "awaiting_documents", **SOURCE})
        return reqs

    def case_context(self, case_id: str) -> dict[str, Any]:
        """What a review engine may know about the case: identities, declarations, dates."""
        case = self.get_case(case_id)
        return {"case_id": case_id, "simulation_date": settings.simulation_date,
                "borrowers": [{k: b[k] for k in ("borrower_id", "name_he", "national_id", "employment",
                                                 "employer_declared_he", "declared_net_monthly_ils",
                                                 "declaration_note_he", "declared_income_provenance")} for b in case["borrowers"]],
                "source": SOURCE}


def simulation_today() -> date:
    return date.fromisoformat(settings.simulation_date)


bank = MockBankAdapter()
