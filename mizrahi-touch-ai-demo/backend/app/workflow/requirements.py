"""Case completeness: the requirement instances a case must satisfy, computed from the loan policy version pinned to
the case — never from UI components or code constants.

A case pins the policy version that was published when it was first evaluated (`case_profile`). Publishing a new
policy changes only cases pinned afterwards, or a case whose banker explicitly re-pins it (audited); requirements
never change silently under an open case."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from .. import db
from ..bank.mock_bank import SOURCE, bank
from ..config import settings
from ..policy import schema, store
from ..review import rubrics
from ..util import now_iso

FAMILY_CODE = {"payslip": "PAYSLIPS", "id_document": "ID_CARD", "bank_statement": "BANK_STATEMENTS",
               "purpose_proof": "PURPOSE_PROOF", "tax_form": "TAX_ASSESSMENT"}
FAMILY_HE = {"payslip": "תלוש שכר", "id_document": "תעודת זהות", "bank_statement": "דף עו״ש",
             "purpose_proof": "אסמכתה למטרה", "tax_form": "שומת מס / אישור רו״ח"}


def pin(case_id: str) -> str:
    """The loan-policy version pinned to the case (pinning the published one on first use)."""
    row = db.one("SELECT requirement_set_version FROM case_profile WHERE case_id=?", (case_id,))
    if row and row["requirement_set_version"]:
        return row["requirement_set_version"]
    version = store.published("loan_policy")["version_id"]
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO case_profile(case_id, requirement_set_version, pinned_at) VALUES (?,?,?)",
                  (case_id, version, now_iso()))
    return db.one("SELECT requirement_set_version FROM case_profile WHERE case_id=?", (case_id,))["requirement_set_version"]


def repin(case_id: str) -> tuple[Optional[str], str]:
    """Re-pin a case to the currently published policy (a banker's explicit action). Returns (old, new)."""
    old = (db.one("SELECT requirement_set_version FROM case_profile WHERE case_id=?", (case_id,)) or {}).get("requirement_set_version")
    new = store.published("loan_policy")["version_id"]
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO case_profile(case_id, requirement_set_version, pinned_at) VALUES (?,?,?)",
                  (case_id, new, now_iso()))
    return old, new


def case_policy(case_id: str) -> tuple[schema.LoanPolicy, dict]:
    return store.policy(pin(case_id))


def _matches(cond: Optional[schema.Condition], case: dict, applicant: Optional[dict]) -> bool:
    if cond is None:
        return True
    if cond.employment is not None:
        if applicant is None or applicant.get("employment") not in cond.employment:
            return False
    if cond.purposes is not None and (case.get("loan") or {}).get("purpose") not in cond.purposes:
        return False
    return True


def evaluated_by_ai(family: str) -> bool:
    return rubrics.has_family(family)


def payslip_months(case_id: str) -> int:
    try:
        pol, _ = case_policy(case_id)
    except (store.InvalidConfig, KeyError):
        return rubrics.for_case()["policy"]["requested_months"]
    rule = next((r for r in pol.document_requirements if r.family == "payslip"), None)
    return (rule.rules.months if rule and rule.rules.months else rubrics.for_case()["policy"]["requested_months"])


def for_case(case_id: str) -> list[dict[str, Any]]:
    case = bank.get_case(case_id)
    pol, row = case_policy(case_id)
    label = row["label"]
    out: list[dict[str, Any]] = []
    for rule in pol.document_requirements:
        title = rule.label_he.replace("{months}", str(rule.rules.months or 3))
        base = {"requirement_id": rule.id, "family": rule.family, "family_he": FAMILY_HE[rule.family],
                "required": rule.required, "rules": rule.rules.model_dump(exclude_none=True), "hint_he": rule.hint_he,
                "evaluated_by_ai": evaluated_by_ai(rule.family), "bank_status": "awaiting_documents",
                "policy_version": label, "family_code": FAMILY_CODE.get(rule.family, rule.id), **SOURCE}
        if rule.per == "applicant":
            for b in case["borrowers"]:
                if not _matches(rule.condition, case, b):
                    continue
                out.append({**base, "code": f"{rule.id}:{b['borrower_id']}", "borrower_id": b["borrower_id"],
                            "account_id": None, "holders": [b["borrower_id"]], "title_he": f"{title} — {b['first_name_he']}"})
        elif rule.per == "account":
            if not _matches(rule.condition, case, None):
                continue
            names = {b["borrower_id"]: b["first_name_he"] for b in case["borrowers"]}
            for a in case.get("accounts", []):
                holders = [h for h in a["holders"] if h in names]
                out.append({**base, "code": f"{rule.id}:{a['account_id']}", "borrower_id": holders[0] if holders else None,
                            "account_id": a["account_id"], "holders": holders,
                            "title_he": f"{title} — {a['label_he']} ({' ו'.join(names[h] for h in holders)})"})
        else:
            if not _matches(rule.condition, case, None):
                continue
            purpose = pol.product.purposes.get((case.get("loan") or {}).get("purpose") or "")
            out.append({**base, "code": rule.id, "borrower_id": None, "account_id": None,
                        "holders": [b["borrower_id"] for b in case["borrowers"]],
                        "title_he": title + (f" — {purpose.label_he}" if purpose else ""),
                        "hint_he": (purpose.proof_he if purpose else "") or rule.hint_he})
    return out


def family_of(requirement_code: Optional[str], case_id: Optional[str] = None) -> str:
    """The document family an upload was intended for (PAYSLIPS:BRW-A → payslip). Unknown → payslip (legacy)."""
    if case_id and requirement_code:
        req = requirement(case_id, requirement_code)
        if req:
            return req["family"]
    head = (requirement_code or "").split(":", 1)[0]
    for family, code in FAMILY_CODE.items():
        if head == code:
            return family
    return "payslip"


def requirement(case_id: str, code: str) -> Optional[dict]:
    return next((r for r in for_case(case_id) if r["code"] == code), None)


def simulation_today() -> date:
    return date.fromisoformat(settings.simulation_date)
