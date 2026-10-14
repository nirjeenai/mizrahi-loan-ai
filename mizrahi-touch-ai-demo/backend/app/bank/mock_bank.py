"""MockBankAdapter — the ONLY source of bank-side case data in this demo, and it is
synthetic. Every value carries source=DEMO_BANK_ADAPTER and authoritative=false.
The real adapter (P2) implements the same methods against bank-approved APIs.

The product is a personal loan that needs documents (Mizrahi-Tefahot's "הלוואה לכל מטרה" publicly lists an ID,
3 months of current-account statements, the last 3 payslips and proof of the loan's purpose). Which documents a case
needs is NOT defined here: it comes from the published loan policy (workflow/requirements.py)."""
from __future__ import annotations

import copy
from datetime import date
from typing import Any, Optional

from ..config import settings

SOURCE = {"source": "DEMO_BANK_ADAPTER", "authoritative": False}
PRODUCT = "personal_loan.all_purpose"

# A demo assumption, not a verified bank enum: no public page lists Mizrahi's internal personal-loan stages.
STAGE_DICTIONARY = [
    {"index": 1, "code": "APPLICATION_SUBMITTED", "label_he": "הגשת בקשה", "observed": False},
    {"index": 2, "code": "DOCUMENTS_AND_CHECKS", "label_he": "השלמת מסמכים", "observed": False},
    {"index": 3, "code": "BANKER_REVIEW", "label_he": "בדיקת בנקאי", "observed": False},
    {"index": 4, "code": "SIGNING", "label_he": "חתימה על הסכם ההלוואה", "observed": False},
    {"index": 5, "code": "DISBURSEMENT", "label_he": "העמדת ההלוואה", "observed": False},
]

BANKER_CAPS = ["case.read", "case.write", "followup.override", "followup.manual_call"]
# Demo staff directory. Capabilities are checked server-side (app/auth.py); a real adapter would take them from bank SSO.
STAFF = {
    "STAFF-DANA": {"staff_id": "STAFF-DANA", "name_he": "דנה כהן", "role_he": "בנקאית אשראי", "capabilities": BANKER_CAPS},
    "STAFF-ORI": {"staff_id": "STAFF-ORI", "name_he": "אורי לוי", "role_he": "בנקאי אשראי", "capabilities": BANKER_CAPS},
    "STAFF-MAYA": {"staff_id": "STAFF-MAYA", "name_he": "מאיה רוזן", "role_he": "מנהלת מדיניות תפעול",
                   "capabilities": ["case.read", "policy.read", "policy.edit", "prompt.edit", "demo.simulate", "audit.read"]},
    "STAFF-AVI": {"staff_id": "STAFF-AVI", "name_he": "אבי שגיא", "role_he": "ממונה ציות",
                  "capabilities": ["case.read", "policy.read", "policy.publish", "prompt.publish", "audit.read",
                                   "demo.simulate"]},
}

_DANA = {"name_he": "דנה כהן", "role_he": "הבנקאית שלך", "staff_id": "STAFF-DANA"}
_CONTACT = {"consent_voice": True, "consent_message": True, "phone_ref": "TEST-LINE-01", "phone_masked": "050-•••-4471"}

# The presenter golden set (fixtures/presenter/golden_set/CASE_PROFILE.json) prints these identities; its payslips
# are reviewed only in the cases that carry them, so the Lavi cases stay untouched.
_GOLDEN_SET_BORROWERS = [
    {"borrower_id": "BRW-A", "name_he": "עידו לוי", "first_name_he": "עידו", "national_id": "DEMO-ID-001",
     "employment": "salaried", "employer_declared_he": "אביב מערכות דיגיטל בע״מ", "role": "primary",
     "declared_net_monthly_ils": 14700, "declaration_note_he": "הוצהר בטופס הבקשה"},
    {"borrower_id": "BRW-B", "name_he": "נועה לוי", "first_name_he": "נועה", "national_id": "DEMO-ID-002",
     "employment": "salaried", "employer_declared_he": "אורן פתרונות תוכנה בע״מ", "role": "co_borrower",
     "declared_net_monthly_ils": 18500, "declaration_note_he": "הוצהר בטופס הבקשה"},
]
_LAVI = [
    {"borrower_id": "BRW-A", "name_he": "עידו לביא", "first_name_he": "עידו", "national_id": "039812457",
     "employment": "salaried", "employer_declared_he": "אופק לוגיסטיקה בע״מ", "role": "primary",
     "declared_net_monthly_ils": 13500, "declaration_note_he": "שכר קבוע"},
    {"borrower_id": "BRW-B", "name_he": "נועה לביא", "first_name_he": "נועה", "national_id": "204376815",
     "employment": "salaried", "employer_declared_he": "גלי טכנולוגיות בע״מ", "role": "co_borrower",
     "declared_net_monthly_ils": 18500, "declaration_note_he": "ייתכנו רכיבים משתנים"},
]


BUSINESS_PRODUCT = "business_financing.inquiry"


def _loan(purpose: str, purpose_he: str, amount: int, payments: int, note_he: str = "", business: bool = False) -> dict:
    return {"product": BUSINESS_PRODUCT if business else PRODUCT,
            "product_he": "מימון עסקי — פנייה ראשונית" if business else "הלוואה לכל מטרה", "purpose": purpose,
            "purpose_he": purpose_he, "requested_amount_ils": amount, "payments": payments, "note_he": note_he}


def _accounts(*holders: list[str], start: int = 1) -> list[dict]:
    return [{"account_id": f"ACC-{start + i}", "label_he": f"חשבון עו״ש {start + i}", "bank_he": "מזרחי־טפחות",
             "holders": h} for i, h in enumerate(holders)]


def _case(case_id: str, number: str, title_he: str, borrowers: list[dict], loan: dict, accounts: list[dict],
          **extra: Any) -> dict:
    return {"case_id": case_id, "display_number": number, "title_he": title_he, "stage_index": 2,
            "preliminary_decision": None, "requested_loan_ils": loan["requested_amount_ils"], "loan": loan,
            "submitted_at": extra.pop("submitted_at", "2026-10-05T10:00:00+03:00"), "banker": dict(_DANA),
            "meeting": extra.pop("meeting", None), "borrowers": borrowers, "accounts": accounts,
            "contact": {**_CONTACT, **extra.pop("contact", {})}, **extra}


_GOLDEN_CAR = _loan("car", "רכישת רכב", 120000, 60, "רכב משפחתי חדש")
_CASES: dict[str, dict[str, Any]] = {
    "DEMO-MTZ-2026-001": _case(
        "DEMO-MTZ-2026-001", "438838921", "הלוואה לרכישת רכב", copy.deepcopy(_LAVI),
        _loan("car", "רכישת רכב", 95000, 48, "רכב משפחתי"), _accounts(["BRW-A", "BRW-B"]),
        submitted_at="2026-09-28T10:32:00+03:00",
        meeting={"date": "2026-10-20", "from": "10:00", "to": "10:30", "type_he": "שיחת וידאו עם הבנקאית"}),
    "DEMO-MTZ-2026-003": _case(
        "DEMO-MTZ-2026-003", "438838999", "תיק בדיקות QA — מסמכים בעייתיים", copy.deepcopy(_LAVI),
        _loan("car", "רכישת רכב", 95000, 48), _accounts(["BRW-A", "BRW-B"]), submitted_at="2026-09-28T10:32:00+03:00"),
    "DEMO-MTZ-2026-002": {
        **_case("DEMO-MTZ-2026-002", "438840117", "הלוואה לשיפוץ",
                [{"borrower_id": "BRW-C", "name_he": "מיכל ברק", "first_name_he": "מיכל", "national_id": "311204578",
                  "employment": "salaried", "employer_declared_he": "שחף הנדסה בע״מ", "role": "primary",
                  "declared_net_monthly_ils": 21000, "declaration_note_he": "שכר קבוע"}],
                _loan("renovation", "שיפוץ", 80000, 60), _accounts(["BRW-C"]), submitted_at="2026-10-01T09:10:00+03:00"),
        "stage_index": 1, "banker": {"name_he": "אורי לוי", "role_he": "הבנקאי שלך", "staff_id": "STAFF-ORI"}},
    # The presenter's test-scenario cases: one applicant (the golden identity), so each scenario's result is its own.
    "DEMO-MTZ-2026-004": _case("DEMO-MTZ-2026-004", "438839004", "תרחישי בדיקה — הלוואה לרכב",
                               [copy.deepcopy(_GOLDEN_SET_BORROWERS[0])], _GOLDEN_CAR, _accounts(["BRW-A"])),
    "DEMO-MTZ-2026-005": _case("DEMO-MTZ-2026-005", "438839005", "תרחישי בדיקה — תיק QA מבודד",
                               [copy.deepcopy(_GOLDEN_SET_BORROWERS[0])], _GOLDEN_CAR, _accounts(["BRW-A"])),
    # Executive demo: one applicant per case, so each featured scenario has its own case-wide status. The presenter
    # manifest maps scenarios to these cases; nothing here says what a review of them should conclude.
    "DEMO-MTZ-2026-006": _case("DEMO-MTZ-2026-006", "438839006", "הלוואה לרכב · הדגמה א׳",
                               [copy.deepcopy(_GOLDEN_SET_BORROWERS[0])], _GOLDEN_CAR, _accounts(["BRW-A"]),
                               executive_demo=True),
    "DEMO-MTZ-2026-007": _case("DEMO-MTZ-2026-007", "438839007", "הלוואה לרכב · הדגמה ב׳",
                               [{**copy.deepcopy(_GOLDEN_SET_BORROWERS[1]), "role": "primary"}], _GOLDEN_CAR,
                               _accounts(["BRW-B"]), executive_demo=True),
    "DEMO-MTZ-2026-008": _case("DEMO-MTZ-2026-008", "438839008", "הלוואה לרכב · הדגמה ג׳",
                               [copy.deepcopy(_GOLDEN_SET_BORROWERS[0])], _GOLDEN_CAR, _accounts(["BRW-A"]),
                               executive_demo=True),
    # The loan-completion journey: a full package, a wrong-month payslip, follow-up and a simulated JEEN Talk call.
    "DEMO-MTZ-2026-009": _case("DEMO-MTZ-2026-009", "438839009", "השלמת מסמכים · הדגמה ד׳",
                               [copy.deepcopy(_GOLDEN_SET_BORROWERS[0])], _GOLDEN_CAR, _accounts(["BRW-A"]),
                               executive_demo=True),
    # Contact permission withheld: the policy must block every automatic contact and explain why.
    "DEMO-MTZ-2026-010": _case("DEMO-MTZ-2026-010", "438839010", "ללא הרשאת קשר · הדגמה ה׳",
                               [copy.deepcopy(_GOLDEN_SET_BORROWERS[0])], _GOLDEN_CAR, _accounts(["BRW-A"]),
                               executive_demo=True, contact={"consent_voice": False, "consent_message": False}),
    # A complete, valid package whose payslips do not support the declared income: the banker's judgment (human review).
    "DEMO-MTZ-2026-011": _case("DEMO-MTZ-2026-011", "438839011", "פער הכנסה · הדגמה ו׳",
                               [{**copy.deepcopy(_GOLDEN_SET_BORROWERS[0]), "declared_net_monthly_ils": 16500,
                                 "declaration_note_he": "הוצהר בטופס הבקשה — כולל בונוס צפוי"}],
                               _GOLDEN_CAR, _accounts(["BRW-A"]), executive_demo=True),
}

# "התיקים שלי" lists the cases of the persona being demonstrated. QA cases belong to no persona; the Lavi (לביא) and
# Levy (לוי) families are different people with different national ids and never share a persona.
for _cid, _persona in {"DEMO-MTZ-2026-001": "PRS-LAVI", "DEMO-MTZ-2026-002": "PRS-BARAK",
                       "DEMO-MTZ-2026-006": "PRS-IDO-LEVY", "DEMO-MTZ-2026-008": "PRS-IDO-LEVY",
                       "DEMO-MTZ-2026-009": "PRS-IDO-LEVY", "DEMO-MTZ-2026-010": "PRS-IDO-LEVY",
                       "DEMO-MTZ-2026-011": "PRS-IDO-LEVY", "DEMO-MTZ-2026-007": "PRS-NOA-LEVY"}.items():
    _CASES[_cid]["persona_id"] = _persona
for _cid in ("DEMO-MTZ-2026-003", "DEMO-MTZ-2026-004", "DEMO-MTZ-2026-005"):
    _CASES[_cid]["qa"] = True


def _person(bid: str, first: str, last: str, national_id: str, role: str, sources: list[str], declared: int,
            employer_he: str = "", registration: Optional[str] = None, business_he: str = "") -> dict:
    """A synthetic applicant with an explicit income profile (what the document policy composes from)."""
    employment = "self_employed" if sources == ["self_employed"] else "salaried" if sources else "none"
    return {"borrower_id": bid, "name_he": f"{first} {last}", "first_name_he": first, "national_id": national_id,
            "employment": employment, "income_sources": sources, "business_registration": registration,
            "employer_declared_he": " · ".join(x for x in (employer_he, business_he) if x), "business_name_he": business_he or None,
            "role": role, "declared_net_monthly_ils": declared, "declaration_note_he": "הוצהר בטופס הבקשה"}


# The six primary demo use cases (UC-01…UC-06 ↔ presenter TC-01…TC-06 in fixtures/presenter). Each is one synthetic
# persona; which documents it needs is NOT written here — the published loan policy composes it from this profile.
_BARAK = copy.deepcopy(_CASES["DEMO-MTZ-2026-002"]["borrowers"][0])
_USE_CASES: dict[str, dict[str, Any]] = {
    "DEMO-MTZ-2026-101": _case(
        "DEMO-MTZ-2026-101", "438839101", "הלוואה לרכישת רכב", [{**_BARAK, "income_sources": ["salaried"]}],
        _loan("car", "רכישת רכב", 90000, 60, "רכב משפחתי חדש"), _accounts(["BRW-C"]),
        submitted_at="2026-10-08T09:20:00+03:00", use_case="UC-01", persona_id="PRS-BARAK", profile_label_he="שכירה"),
    "DEMO-MTZ-2026-102": _case(
        "DEMO-MTZ-2026-102", "438839102", "הלוואה לרכישת רכב",
        [_person("BRW-A", "יואב", "כרמי", "DEMO-ID-102", "primary", ["self_employed"], 11200,
                 registration="vat_exempt", business_he="כרמי צילום")],
        _loan("car", "רכישת רכב", 60000, 48, "רכב לעבודה"), _accounts(["BRW-A"]),
        submitted_at="2026-10-08T11:05:00+03:00", use_case="UC-02", persona_id="PRS-KARMI", profile_label_he="עוסק פטור"),
    "DEMO-MTZ-2026-103": _case(
        "DEMO-MTZ-2026-103", "438839103", "הלוואה לרכישת רכב",
        [_person("BRW-A", "שירן", "אזולאי", "DEMO-ID-103", "primary", ["self_employed"], 19800,
                 registration="vat_registered", business_he="אזולאי עיצוב פנים")],
        _loan("car", "רכישת רכב", 140000, 60, "רכב לעסק ולמשפחה"), _accounts(["BRW-A"]),
        submitted_at="2026-10-09T10:40:00+03:00", use_case="UC-03", persona_id="PRS-AZULAY", profile_label_he="עוסקת מורשית"),
    "DEMO-MTZ-2026-104": _case(
        "DEMO-MTZ-2026-104", "438839104", "הלוואה לרכישת רכב",
        [_person("BRW-A", "אלון", "פרידמן", "DEMO-ID-104", "primary", ["salaried", "self_employed"], 17400,
                 employer_he="נתיב תוכנה בע״מ", registration="vat_exempt", business_he="פרידמן הדרכות")],
        _loan("car", "רכישת רכב", 110000, 60), _accounts(["BRW-A"]),
        submitted_at="2026-10-09T15:15:00+03:00", use_case="UC-04", persona_id="PRS-FRIEDMAN",
        profile_label_he="שכיר וגם עצמאי"),
    "DEMO-MTZ-2026-105": _case(
        "DEMO-MTZ-2026-105", "438839105", "הלוואה לשיפוץ — בקשה משותפת",
        [_person("BRW-A", "רועי", "שטרן", "DEMO-ID-105", "primary", ["salaried"], 15600, employer_he="מרכז רפואי השרון"),
         _person("BRW-B", "מאיה", "שטרן", "DEMO-ID-115", "co_borrower", ["self_employed"], 13900,
                 registration="vat_registered", business_he="סטודיו מאיה שטרן — אדריכלות")],
        _loan("renovation", "שיפוץ", 150000, 84, "שיפוץ הדירה"),
        _accounts(["BRW-A", "BRW-B"], ["BRW-A", "HLD-RACHEL"]),
        submitted_at="2026-10-10T09:00:00+03:00", use_case="UC-05", persona_id="PRS-STERN", profile_label_he="שני לווים"),
    "DEMO-MTZ-2026-106": {
        **_case("DEMO-MTZ-2026-106", "438839106", "מימון ציוד — ש.ג. מערכות מיזוג בע״מ",
                [_person("BRW-A", "גלעד", "ששון", "DEMO-ID-106", "authorized_signatory", [], 0)],
                _loan("business_equipment", "מימון ציוד לעסק", 300000, 60, "מערכות מיזוג לפרויקט חדש", business=True),
                [{"account_id": "ACC-1", "label_he": "חשבון עסקי של החברה", "bank_he": "מזרחי־טפחות", "holders": ["COMPANY"]}],
                submitted_at="2026-10-11T08:30:00+03:00", use_case="UC-06", persona_id="PRS-SG-HVAC",
                profile_label_he="חברה בע״מ", applicant_type="company", banker_assisted=True,
                company={"name_he": "ש.ג. מערכות מיזוג בע״מ", "company_number": "DEMO-CO-516001060",
                         "signatory_he": "גלעד ששון", "signatory_role_he": "מנכ״ל ומורשה חתימה"}),
        "banker": {"name_he": "דנה כהן", "role_he": "הבנקאית המלווה", "staff_id": "STAFF-DANA"}},
}
_USE_CASES["DEMO-MTZ-2026-105"]["accounts"][1].update(
    {"label_he": "חשבון עו״ש של רועי ואמו", "other_holders_he": ["רחל שטרן — בעלת חשבון, אינה לווה בבקשה"]})
_USE_CASES["DEMO-MTZ-2026-105"]["accounts"][0]["label_he"] = "חשבון עו״ש משותף"
for _cid in _USE_CASES:
    _USE_CASES[_cid]["executive_demo"] = True
    _USE_CASES[_cid]["stage_index"] = 2
_CASES.update(_USE_CASES)


def _applications() -> dict[str, dict]:
    """Customer-started applications (synthetic, stored in DATA_DIR) — see workflow/intake.py."""
    from .. import db
    try:
        rows = db.query("SELECT case_id, application FROM demo_applications ORDER BY created_at")
    except Exception:                                   # the table may not exist before db.connect()
        return {}
    return {r["case_id"]: db.jload(r["application"]) for r in rows}


class MockBankAdapter:
    name = "mock-bank"

    def _all(self) -> dict[str, dict]:
        return {**_CASES, **_applications()}

    def case_ids(self) -> list[str]:
        return list(self._all())

    def executive_demo_case_ids(self) -> list[str]:
        """The only cases the presenter's "start a new demo" control may wipe."""
        return [cid for cid, c in _CASES.items() if c.get("executive_demo")]

    def get_case(self, case_id: str) -> dict[str, Any]:
        cases = _CASES if case_id in _CASES else self._all()
        if case_id not in cases:
            raise KeyError(case_id)
        case = copy.deepcopy(cases[case_id])
        stage = STAGE_DICTIONARY[case["stage_index"] - 1]
        case["bank_stage"] = {**SOURCE, "index": stage["index"], "of": len(STAGE_DICTIONARY), "code": stage["code"],
                              "label_he": stage["label_he"], "label_observed_in_screenshot": stage["observed"]}
        case["source"] = SOURCE
        for b in case["borrowers"]:
            b["declared_income_provenance"] = "CUSTOMER_DECLARED"
        from ..workflow import requirements
        case["document_profile"] = requirements.profile(case)
        return case

    def persona_of(self, case_id: str) -> Optional[str]:
        return self._all().get(case_id, {}).get("persona_id")

    def staff(self, staff_id: str) -> Optional[dict[str, Any]]:
        return copy.deepcopy(STAFF.get(staff_id))

    def staff_directory(self) -> list[dict[str, Any]]:
        return copy.deepcopy(list(STAFF.values()))

    def customer_cases(self, national_id: str) -> list[str]:
        """The cases in which this person is a borrower (a data lookup; no credential is involved)."""
        return [cid for cid, c in self._all().items() if any(b["national_id"] == national_id for b in c["borrowers"])]

    def stage_dictionary(self) -> dict[str, Any]:
        return {**SOURCE, "stages": STAGE_DICTIONARY,
                "note_he": "מילון שלבים להדגמה בלבד — אינו רשימת שלבים מאומתת של הבנק להלוואות."}

    def requirements(self, case_id: str) -> list[dict[str, Any]]:
        """Requirement instances of the case, from the loan policy version pinned to it."""
        from ..workflow import requirements
        return requirements.for_case(case_id)

    def case_context(self, case_id: str) -> dict[str, Any]:
        """What a review engine may know about the case: identities, declarations, dates."""
        from ..workflow import requirements
        case = self.get_case(case_id)
        return {"case_id": case_id, "simulation_date": settings.simulation_date,
                "payslip_months": requirements.payslip_months(case_id),
                "loan_purpose_he": (case.get("loan") or {}).get("purpose_he"),
                "requirements": [{k: r[k] for k in ("code", "family", "rules", "holders", "required", "title_he",
                                                    "account_id", "borrower_id")}
                                 for r in requirements.for_case(case_id)],
                "borrowers": [{k: b[k] for k in ("borrower_id", "name_he", "national_id", "employment",
                                                 "employer_declared_he", "declared_net_monthly_ils",
                                                 "declaration_note_he", "declared_income_provenance")} for b in case["borrowers"]],
                "accounts": [{"account_id": a["account_id"], "holders": a["holders"]} for a in case.get("accounts", [])],
                "source": SOURCE}


def simulation_today() -> date:
    return date.fromisoformat(settings.simulation_date)


bank = MockBankAdapter()
