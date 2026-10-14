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
             "purpose_proof": "אסמכתה למטרה", "tax_form": "שומת מס / אישור רו״ח",
             "business_registration": "אישור רישום עוסק", "pnl_statement": "דוח רווח והפסד",
             "company_registry": "נסח חברה", "signatory_authority": "מורשי חתימה",
             "financial_statements": "דוחות כספיים", "business_bank_statement": "דפי עו״ש עסקי"}
ENTITY_HE = {"individual": "הלוואה פרטית", "company": "מימון לחברה בע״מ"}
COMPANY_AI_FAMILIES = ("id_document",)
INCOME_HE = {"salaried": "שכיר/ה", "self_employed": "עצמאי/ת", "allowance": "מקבל/ת קצבה"}
REGISTRATION_HE = {"vat_exempt": "עוסק פטור", "vat_registered": "עוסק מורשה"}
ROLE_HE = {"primary": "לווה ראשי", "co_borrower": "לווה נוסף", "authorized_signatory": "מורשה חתימה"}
POLICY_DISCLAIMER_HE = ("מדיניות מסמכים להדגמה, המבוססת על פרקטיקה בנקאית ומיסויית ציבורית — אינה רשימת הדרישות "
                        "המאושרת של מזרחי־טפחות.")


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


def income_sources(applicant: dict) -> list[str]:
    """An applicant's income sources: the explicit list, or the single legacy `employment` value."""
    if applicant.get("income_sources") is not None:
        return list(applicant["income_sources"])
    return [applicant["employment"]] if applicant.get("employment") in INCOME_HE else []


def entity_of(case: dict) -> str:
    return case.get("applicant_type") or "individual"


def _matches(cond: Optional[schema.Condition], case: dict, applicant: Optional[dict]) -> bool:
    if cond is None:
        return True
    if cond.entity is not None and entity_of(case) not in cond.entity:
        return False
    if cond.employment is not None:
        if applicant is None or not set(income_sources(applicant)) & set(cond.employment):
            return False
    if cond.registration is not None:
        if applicant is None or applicant.get("business_registration") not in cond.registration:
            return False
    if cond.purposes is not None and (case.get("loan") or {}).get("purpose") not in cond.purposes:
        return False
    return True


def applicant_profile_he(applicant: dict) -> str:
    """'שכיר/ה · עצמאי/ת (עוסק פטור)' — the income profile the policy composes from."""
    parts = []
    for src in income_sources(applicant):
        reg = REGISTRATION_HE.get(applicant.get("business_registration") or "") if src == "self_employed" else None
        parts.append(f"{INCOME_HE[src]} ({reg})" if reg else INCOME_HE[src])
    return " · ".join(parts) or ROLE_HE.get(applicant.get("role") or "", "")


def profile(case: dict) -> dict[str, Any]:
    """The structured document profile of a case: the inputs the policy composition reads, in display form."""
    company = case.get("company")
    return {"entity": entity_of(case), "entity_he": ENTITY_HE[entity_of(case)],
            "purpose": (case.get("loan") or {}).get("purpose"), "purpose_he": (case.get("loan") or {}).get("purpose_he"),
            "company": company, "banker_assisted": bool(case.get("banker_assisted")),
            "use_case": case.get("use_case"), "profile_label_he": case.get("profile_label_he"),
            "applicants": [{"borrower_id": b["borrower_id"], "name_he": b["name_he"], "role": b.get("role"),
                            "role_he": ROLE_HE.get(b.get("role") or "", ""), "income_sources": income_sources(b),
                            "business_registration": b.get("business_registration"),
                            "profile_he": applicant_profile_he(b)} for b in case["borrowers"]],
            "accounts": [{"account_id": a["account_id"], "label_he": a["label_he"], "holders": a["holders"],
                          "other_holders_he": a.get("other_holders_he") or []} for a in case.get("accounts", [])],
            "disclaimer_he": POLICY_DISCLAIMER_HE}


def evaluated_by_ai(family: str) -> bool:
    return rubrics.has_family(family)


def payslip_months(case_id: str) -> int:
    try:
        pol, _ = case_policy(case_id)
    except (store.InvalidConfig, KeyError):
        return rubrics.for_case()["policy"]["requested_months"]
    rule = next((r for r in pol.document_requirements if r.family == "payslip"), None)
    return (rule.rules.months if rule and rule.rules.months else rubrics.for_case()["policy"]["requested_months"])


def compose(case: dict, pol: schema.LoanPolicy, label: str) -> list[dict[str, Any]]:
    """The requirement instances of a case under one policy version — deterministic, from the case's profile only.

    One instance per applicant / account / case as the rule says, so a requirement shared by several people (an ID per
    person, one statement per account, one purpose proof) is never listed twice. An account holder who is not a
    borrower gets nothing. Every instance names its owner, why it is asked for and the documents accepted instead."""
    out: list[dict[str, Any]] = []
    company = (case.get("company") or {}).get("name_he")
    for rule in pol.document_requirements:
        title = rule.label_he.replace("{months}", str(rule.rules.months or 3))
        # the limited business path: company documents are the banker's to review; only the signatory's ID has a rubric
        ai = evaluated_by_ai(rule.family) and (entity_of(case) != "company" or rule.family in COMPANY_AI_FAMILIES)
        rules = rule.rules.model_dump(exclude_none=True)
        if rule.family == "business_registration" and rule.condition and rule.condition.registration:
            rules["registration"] = rule.condition.registration[0]
        base = {"requirement_id": rule.id, "family": rule.family, "family_he": FAMILY_HE[rule.family],
                "required": rule.required, "rules": rules, "hint_he": rule.hint_he,
                "why_he": rule.why_he, "alternatives_he": list(rule.alternatives_he),
                "evaluated_by_ai": ai, "intake": "ai_review" if ai else "human_review", "bank_status": "awaiting_documents",
                "policy_version": label, "family_code": FAMILY_CODE.get(rule.family, rule.id), **SOURCE}
        if rule.per == "applicant":
            for b in case["borrowers"]:
                if not _matches(rule.condition, case, b):
                    continue
                out.append({**base, "code": f"{rule.id}:{b['borrower_id']}", "borrower_id": b["borrower_id"],
                            "account_id": None, "holders": [b["borrower_id"]], "title_he": f"{title} — {b['first_name_he']}",
                            "owner_type": "applicant", "owner_he": b["name_he"]})
        elif rule.per == "account":
            if not _matches(rule.condition, case, None):
                continue
            names = {b["borrower_id"]: b["first_name_he"] for b in case["borrowers"]}
            full = {b["borrower_id"]: b["name_he"] for b in case["borrowers"]}
            for a in case.get("accounts", []):
                holders = [h for h in a["holders"] if h in names]
                who = " ו".join(names[h] for h in holders)
                out.append({**base, "code": f"{rule.id}:{a['account_id']}", "borrower_id": holders[0] if holders else None,
                            "account_id": a["account_id"], "holders": holders,
                            "title_he": f"{title} — {a['label_he']}" + (f" ({who})" if who else ""),
                            "owner_type": "account",
                            "owner_he": " ו".join(full[h] for h in holders) or company or a["label_he"]})
        else:
            if not _matches(rule.condition, case, None):
                continue
            purpose = pol.product.purposes.get((case.get("loan") or {}).get("purpose") or "")
            purpose_proof = rule.family == "purpose_proof"
            out.append({**base, "code": rule.id, "borrower_id": None, "account_id": None,
                        "holders": [b["borrower_id"] for b in case["borrowers"]],
                        "title_he": title + (f" — {purpose.label_he}" if purpose and purpose_proof else ""),
                        "hint_he": ((purpose.proof_he if purpose and purpose_proof else "") or rule.hint_he),
                        "owner_type": "company" if company else "case",
                        "owner_he": company or " ו".join(b["name_he"] for b in case["borrowers"])})
    return out


def for_case(case_id: str) -> list[dict[str, Any]]:
    pol, row = case_policy(case_id)
    return compose(bank.get_case(case_id), pol, row["label"])


def preview(case: dict) -> tuple[list[dict[str, Any]], str]:
    """The requirements a not-yet-created case would get under the published policy (the onboarding summary)."""
    pol, row = store.policy()
    return compose(case, pol, row["label"]), row["label"]


def family_of(requirement_code: Optional[str], case_id: Optional[str] = None) -> str:
    """The document family an upload was intended for (PAYSLIPS:BRW-A → payslip). Unknown → payslip (legacy)."""
    if case_id and requirement_code:
        req = requirement(case_id, requirement_code)
        if req:
            return req["family"]
    head = (requirement_code or "").split(":", 1)[0]
    if case_id and head:
        # a requirement that a profile change made inactive keeps its family: the pinned policy still defines it
        try:
            rule = next((r for r in case_policy(case_id)[0].document_requirements if r.id == head), None)
        except (store.InvalidConfig, KeyError):
            rule = None
        if rule:
            return rule.family
    for family, code in FAMILY_CODE.items():
        if head == code:
            return family
    return "payslip"


def inactive_codes(case_id: str, docs: list[dict]) -> set[str]:
    """Requirement codes that documents were filed under but the case's current profile no longer requires."""
    active = {r["code"] for r in for_case(case_id)}
    return {d["requirement_code"] for d in docs if d.get("requirement_code") and d["requirement_code"] not in active}


def requirement(case_id: str, code: str) -> Optional[dict]:
    return next((r for r in for_case(case_id) if r["code"] == code), None)


def simulation_today() -> date:
    return date.fromisoformat(settings.simulation_date)
