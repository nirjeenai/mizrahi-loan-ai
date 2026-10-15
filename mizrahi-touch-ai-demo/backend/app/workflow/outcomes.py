"""PASS / REVIEW / BLOCKER — the routing of a document, and of a borrower's payslip set, in business terms.

Derived on every read by code from persisted facts: the review verdict, open findings, the banker's documentary status
and the customer's status. Never stored and never set by a model. It sits next to the document verdict, the banker
status and the readiness state machine without replacing any of them, and none of these outcomes is a credit decision:
PASS means "ready for the banker's acceptance", ACCEPTED is a documentary acceptance, never a loan approval."""
from __future__ import annotations

from typing import Any, Optional

INCOME_CODE = "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"
OUTCOME_HE = {
    "PASS": "עבר בדיקת AI, ממתין לקבלת הבנקאי",
    "ACCEPTED": "התקבל אצל הבנקאי, קבלת מסמך בלבד, לא אישור הלוואה",
    "REVIEW": "נדרש בירור בנקאי",
    "BLOCKER": "המסמך אינו מתאים לדרישה, נא להעלות מסמך חלופי",
    "IN_PROGRESS": "בבדיקה",
    "NOT_COMPLETED": "הבדיקה לא הושלמה",
    "REPLACED": "הוחלף במסמך חדש",
    "INCOMPLETE": "חסרים מסמכים",
    "AWAITING_UPLOAD": "ממתינים להעלאת מסמכים",
    "CONFIRMED": "הבנקאי אישר את הכנת מסמכי הבקשה",
    "HUMAN_REVIEW_PENDING": "התקבל, ממתין לבדיקת הבנקאי (אין בדיקת AI לסוג מסמך זה)",
}
INCOME_REVIEW_HE = "נדרש בירור בנקאי, נמצא פער בהכנסה"
# the borrower's payslip set, from readiness.customer_status (same precedence: a document to fix comes before a review)
SET_OUTCOME = {"CHECKS_COMPLETE": "PASS", "BANKER_REVIEW": "REVIEW", "CORRECTION_REQUIRED": "BLOCKER",
               "MISSING_DOCUMENTS": "INCOMPLETE", "PROCESSING": "IN_PROGRESS", "REVALIDATING": "IN_PROGRESS",
               "ERROR": "NOT_COMPLETED", "AWAITING_UPLOAD": "AWAITING_UPLOAD", "PREPARATION_CONFIRMED": "CONFIRMED"}


def _cites(f: dict, document_id: str) -> bool:
    return f["document_id"] == document_id or any(e.get("document_id") == document_id for e in f.get("evidence") or [])


def _view(outcome: str, label: Optional[str] = None, **extra: Any) -> dict:
    return {"outcome": outcome, "label_he": label or OUTCOME_HE[outcome], **extra}


def document_outcome(doc: dict, review: Optional[dict], banker_status: str, open_findings: list[dict]) -> dict:
    """One document. A human decision wins over the AI route; a failed check the customer can fix (BLOCKER) wins over
    a question for the banker (REVIEW); PASS needs a VALID verdict with nothing open on the document."""
    did = doc["document_id"]
    if banker_status == "REPLACED":
        return _view("REPLACED")
    if doc["status"] in ("queued", "processing") or banker_status == "PROCESSING":
        return _view("IN_PROGRESS")
    if banker_status == "FAILED" or doc["status"] == "failed":
        return _view("NOT_COMPLETED")
    if banker_status == "CORRECTION_REQUESTED":
        return _view("BLOCKER", by="banker")
    if banker_status == "ACCEPTED":
        return _view("ACCEPTED", by="banker")
    if banker_status == "AWAITING_CUSTOMER_FIX":
        return _view("BLOCKER", by="ai")
    if doc["status"] == "stored":
        return _view("HUMAN_REVIEW_PENDING", by="banker")
    banker = [f for f in open_findings if f["review_state"] == "NEEDS_BANKER_REVIEW" and _cites(f, did)]
    if banker_status == "ESCALATED" or banker or (review or {}).get("verdict") != "VALID":
        income = any(f["code"] == INCOME_CODE for f in banker)
        return _view("REVIEW", INCOME_REVIEW_HE if income else None, by="banker" if banker_status == "ESCALATED" else "ai")
    return _view("PASS", by="ai")


def set_outcome(customer_status: Optional[str], borrower_findings: list[dict]) -> Optional[dict]:
    outcome = SET_OUTCOME.get(customer_status or "")
    if not outcome:
        return None
    if outcome == "REVIEW" and any(f["code"] == INCOME_CODE and f["review_state"] == "NEEDS_BANKER_REVIEW" for f in borrower_findings):
        return _view("REVIEW", INCOME_REVIEW_HE)
    return _view(outcome)


def for_case(docs: list[dict], reviews: dict[str, Optional[dict]], statuses: dict[str, dict], open_findings: list[dict],
             requirements: list[dict]) -> dict:
    """{"documents": {document_id: outcome}, "borrowers": {borrower_id: outcome}} for a case snapshot."""
    documents = {d["document_id"]: document_outcome(d, reviews.get(d["document_id"]),
                                                    (statuses.get(d["document_id"]) or {}).get("status", ""), open_findings)
                 for d in docs}
    borrowers, by_requirement = {}, {}
    for r in requirements:
        if not r.get("evaluated_by_ai"):
            continue
        if r.get("family", "payslip") == "payslip" and r.get("borrower_id"):
            view = set_outcome(r.get("customer_status"), [f for f in open_findings if f["borrower_id"] == r["borrower_id"]])
            if view:
                borrowers[r["borrower_id"]] = view
        view = set_outcome(r.get("customer_status"), [])
        if view:
            by_requirement[r["code"]] = view
    return {"documents": documents, "borrowers": borrowers, "requirements": by_requirement}
