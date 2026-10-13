"""Banker-side document status, derived from the append-only decision log and the customer requests.

It sits next to the AI verdict and never changes it: an AI verdict is a document-review result, a banker
status is a human documentary decision, and neither is a credit decision or a bank stage."""
from __future__ import annotations

from typing import Any, Optional

from ..store import repo

DOCUMENT_ACTIONS = ("ACCEPT_DOCUMENT", "REQUEST_CORRECTION", "ESCALATE")
STATUS_HE = {
    "PROCESSING": "בעיבוד AI",
    "FAILED": "עיבוד AI נכשל",
    "AWAITING_DECISION": "ממתין להחלטתך",
    "AWAITING_CUSTOMER_FIX": "תיקון נדרש מהלקוח (זוהה ב-AI)",
    "ACCEPTED": "התקבל על ידי הבנקאי",
    "CORRECTION_REQUESTED": "הוחזר לתיקון · ממתין ללקוח",
    "ESCALATED": "בבירור",
    "REPLACED": "הוחלף במסמך חדש",
}
# what the customer may see about a banker status; internal states stay internal
CUSTOMER_STATUS_HE = {
    "ACCEPTED": "התקבל על ידי הבנקאית לבדיקת המסמכים",
    "CORRECTION_REQUESTED": "הבנקאית ביקשה מסמך מתוקן",
    "REPLACED": "הוחלף במסמך שהעליתם",
}


def replacements(requests: list[dict], case_id: Optional[str] = None) -> dict[str, dict]:
    """old document id → the correction request a replacement answered. With `case_id`, also the uploads the customer
    made to replace a document the AI review sent back (kind `customer_replacement`, no request behind them)."""
    out = {r["document_id"]: r for r in requests
           if r["kind"] == "correction" and r["document_id"] and r.get("responded_document_id")}
    if case_id:
        for i in repo.replacement_intents(case_id):
            out.setdefault(i["replaces_document_id"], {"kind": "customer_replacement", "document_id": i["replaces_document_id"],
                                                       "responded_document_id": i["document_id"], "customer_request_id": None})
    return out


def document_statuses(case_id: str, docs: Optional[list[dict]] = None, open_findings: Optional[list[dict]] = None,
                      decisions: Optional[list[dict]] = None, requests: Optional[list[dict]] = None) -> dict[str, dict[str, Any]]:
    docs = repo.documents(case_id) if docs is None else docs
    open_findings = repo.findings(case_id, status="open") if open_findings is None else open_findings
    decisions = repo.decisions(case_id) if decisions is None else decisions
    requests = repo.customer_requests(case_id) if requests is None else requests
    replaced = replacements(requests, case_id)
    answering = {r["responded_document_id"]: r for r in replaced.values()}
    withdrawn = {r["customer_request_id"] for r in requests if r["status"] == "CLOSED" and r.get("closed_reason") == "WITHDRAW_REQUEST"}
    latest: dict[str, dict] = {}
    for d in decisions:
        # a correction the banker withdrew no longer decides the document: it returns to its previous state
        if d["target_kind"] == "document" and d["action"] in DOCUMENT_ACTIONS and d.get("customer_request_id") not in withdrawn:
            latest[d["document_id"]] = d
    out = {}
    for doc in docs:
        did = doc["document_id"]
        customer_fix = any(f["document_id"] == did and f["review_state"] == "CUSTOMER_ACTION_REQUIRED" for f in open_findings)
        if did in replaced:
            status = "REPLACED"
        elif did in latest:
            status = latest[did]["new_status"]
        elif doc["status"] in ("queued", "processing"):
            status = "PROCESSING"
        elif doc["status"] == "failed":
            status = "FAILED"
        elif customer_fix:
            status = "AWAITING_CUSTOMER_FIX"
        else:
            status = "AWAITING_DECISION"
        open_request = next((r for r in requests if r["document_id"] == did and r["status"] == "OPEN"), None)
        out[did] = {"status": status, "status_he": STATUS_HE[status], "decision": latest.get(did),
                    "replaced_by": (replaced.get(did) or {}).get("responded_document_id"),
                    "replaces": (answering.get(did) or {}).get("document_id"),
                    "replacement_kind": (replaced.get(did) or answering.get(did) or {}).get("kind"),
                    "answers_request": (answering.get(did) or {}).get("customer_request_id"),
                    "open_request": open_request, "customer_fix": customer_fix}
    return out


def customer_history(history: list[dict]) -> list[dict]:
    """A finding's history as the customer, the assistant and MCP may see it: banker events without notes or staff ids."""
    return [{k: v for k, v in h.items() if k not in ("note", "actor", "decision_id")} if str(h.get("event", "")).startswith("banker_")
            else h for h in history]


def counts_toward_coverage(verdict: Optional[str], banker_status: Optional[str]) -> bool:
    """A required month is verified by an AI-VALID payslip or one the banker accepted, unless the banker rejected it."""
    if banker_status in ("CORRECTION_REQUESTED", "REPLACED"):
        return False
    return verdict == "VALID" or banker_status == "ACCEPTED"
