"""Readiness aggregation — deterministic, owned by the Mortgage Case Service.

AI document readiness is a separate state machine from the bank's stage. The AI moves
only its own state; PREPARATION_CONFIRMED is reached only through a banker action.
`customer_status` is the customer's next step, derived from the same persisted facts."""
from __future__ import annotations

from datetime import date
from typing import Any

from .. import db
from ..bank.mock_bank import bank
from ..config import settings
from ..review import deterministic as det
from ..review import rubrics
from ..store import repo
from ..util import now_iso
from . import desk_state

STATE_HE = {
    "NOT_CHECKED": "טרם נבדק",
    "CHECKING": "בבדיקה",
    "RECHECKING": "בבדיקה חוזרת",
    "ACTION_REQUIRED": "נדרשת השלמה מצדכם",
    "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS": "מוכן לבדיקת הבנקאי — עם ממצאים פתוחים",
    "READY_FOR_HUMAN_REVIEW": "מוכן לבדיקת הבנקאי",
    "PREPARATION_CONFIRMED": "הבנקאי אישר את הכנת מסמכי השכר",
    "ERROR": "תקלה בבדיקה — נדרש טיפול",
}
# the same states as the banker reads them; STATE_HE above speaks to the customer
STATE_HE_BANKER = {
    "NOT_CHECKED": "טרם הועלו מסמכים",
    "CHECKING": "AI בודק מסמכים",
    "RECHECKING": "AI בודק מחדש",
    "ACTION_REQUIRED": "ממתין להשלמות מהלקוח",
    "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS": "ממתין לבדיקתך · יש ממצאים פתוחים",
    "READY_FOR_HUMAN_REVIEW": "ממתין לבדיקתך",
    "PREPARATION_CONFIRMED": "הכנת מסמכי השכר אושרה",
    "ERROR": "תקלה בעיבוד — נדרש טיפול",
}
REQ_STATE_HE = {
    "required_missing": "טרם הועלה", "needs_customer_action": "נדרשת השלמה", "needs_banker_review": "לבדיקת הבנקאי",
    "checking": "בבדיקה", "uploaded_unreadable": "לא קריא", "extracted": "נבדק — תקין", "not_evaluated_in_demo": "לא נבדק בהדגמה",
    "preparation_confirmed": "אושר על ידי הבנקאי (הדגמה)",
}


def customer_status(*, required: int, documents: int, failed: int, review_failed: bool, busy: bool,
                    reviewed_before: bool, correction: int, missing: int, confirmed: bool, banker: int,
                    verified: int) -> str:
    """The customer's next step when several conditions hold at once, for the case or one borrower.

    Nothing required, then nothing uploaded, a review that stopped, work in progress (earlier
    results may be stale), a document to fix (it often explains a missing month), months still
    missing, the banker's confirmation, open banker items or payslips not yet verified. Complete
    needs every required month verified; an empty findings list alone never qualifies."""
    if not required:
        return "NO_PAYSLIPS_REQUIRED"
    if not documents:
        return "AWAITING_UPLOAD"
    if failed or review_failed:
        return "ERROR"
    if busy:
        return "REVALIDATING" if reviewed_before else "PROCESSING"
    if correction:
        return "CORRECTION_REQUIRED"
    if missing:
        return "MISSING_DOCUMENTS"
    if confirmed:
        return "PREPARATION_CONFIRMED"
    if banker or verified < required:
        return "BANKER_REVIEW"
    return "CHECKS_COMPLETE"


def policy_months() -> list[str]:
    """The salary months the case rubric requires as of the simulation date — known before any review."""
    policy = rubrics.for_case()["policy"]
    return det.requested_months(date.fromisoformat(settings.simulation_date), policy["requested_months"],
                                policy["payday_day_of_next_month"])


REOPENING = ("REQUEST_CORRECTION", "REQUEST_MISSING_DOCUMENT", "REQUEST_EXPLANATION", "REQUEST_DOCUMENT")


def confirmation(case_id: str, docs: list[dict]) -> tuple[dict | None, dict | None]:
    """The banker's latest preparation confirmation and whether it still holds. It lapses when a document was uploaded
    after it (the confirmed package lists the documents it covered) or when the banker asked the customer for something
    after it; the banker then confirms again. Returns (valid confirmation, stale confirmation)."""
    handoff = next((h for h in repo.handoffs(case_id) if h.get("banker_decision") == "confirmed_preparation"), None)
    if not handoff:
        return None, None
    decisions = repo.decisions(case_id)
    last = max((i for i, d in enumerate(decisions) if d["action"] == "CONFIRM_PREPARATION"), default=None)
    covered = {d["document_id"] for d in (handoff.get("package") or {}).get("documents") or []}
    new_docs = [d for d in docs if d["document_id"] not in covered]
    reopened = [d for d in decisions[last + 1:] if d["action"] in REOPENING] if last is not None else []
    view = {"confirmed_at": handoff["decided_at"], "note": handoff.get("decided_note"), "package_id": handoff["package_id"]}
    if not new_docs and not reopened:
        return view, None
    return None, {**view, "reason_he": "הועלה מסמך חדש אחרי האישור" if new_docs else "נשלחה בקשה ללקוח אחרי האישור"}


def compute(case_id: str, ignore_job_id: str | None = None) -> dict[str, Any]:
    docs = repo.documents(case_id)
    open_f = repo.findings(case_id, status="open")
    pending = db.query("SELECT kind, document_id FROM jobs WHERE case_id=? AND status IN ('queued','running') AND job_id<>?",
                       (case_id, ignore_job_id or ""))
    latest_case = repo.latest_case_result(case_id)
    last_case_run = db.one("SELECT status FROM review_runs WHERE case_id=? AND scope='case' ORDER BY started_at DESC, rowid DESC"
                           " LIMIT 1", (case_id,))
    busy = bool(pending) or any(d["status"] in ("queued", "processing") for d in docs)
    case_job_pending = any(j["kind"] == "review_case" for j in pending)
    # documents with nothing in flight and no successful set review behind them: that review failed
    case_review_failed = bool(docs) and not busy and (latest_case is None or (last_case_run or {}).get("status") == "failed")
    confirmed, stale_confirmation = confirmation(case_id, docs)
    latest_case_run = (repo.case_state(case_id) or {}).get("last_case_run_id")
    coverage = (latest_case or {}).get("coverage", {}).get("by_borrower", {})
    requested_default = (latest_case or {}).get("coverage", {}).get("requested") or policy_months()
    statuses = desk_state.document_statuses(case_id, docs, open_f)
    open_requests = repo.customer_requests(case_id, status="OPEN")

    def counts(x: dict) -> bool:
        return desk_state.counts_toward_coverage(x["verdict"], statuses.get(x["document_id"], {}).get("status"))

    requirements = []
    for r in bank.requirements(case_id):
        if not r["evaluated_by_ai"]:
            requirements.append({**r, "ai_state": "not_evaluated_in_demo", "ai_state_he": REQ_STATE_HE["not_evaluated_in_demo"]})
            continue
        bid = r["borrower_id"]
        mine = [d for d in docs if d["borrower_id"] == bid]
        customer = [f for f in open_f if f["borrower_id"] == bid and f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
        banker = [f for f in open_f if f["borrower_id"] == bid and f["review_state"] == "NEEDS_BANKER_REVIEW"]
        asked = [q for q in open_requests if q["borrower_id"] == bid]
        asked_fix = [q for q in asked if q["kind"] == "correction"]
        cov = coverage.get(bid, {})
        if any(d["status"] in ("queued", "processing") for d in mine):
            state = "checking"
        elif not mine and not asked:
            state = "required_missing"
        elif customer or asked:
            state = "needs_customer_action"
        elif banker:
            state = "needs_banker_review"
        elif cov and not cov.get("missing") and all(counts(x) for x in cov.get("documents", [])
                                                    if statuses.get(x["document_id"], {}).get("status") != "REPLACED"):
            state = "extracted"
        else:
            state = "needs_customer_action"
        if confirmed and state in ("extracted", "needs_banker_review") and not customer:
            state = "preparation_confirmed"
        verified = {x["period"] for x in cov.get("documents", []) if counts(x)}
        requested = cov.get("requested") or requested_default
        # before the first set review, only a borrower with no documents is known to miss every month
        missing = cov.get("missing", []) if cov else ([] if mine else requested)
        verified_months = [m for m in requested if m in verified]
        correction = [f for f in customer if f["document_id"]]
        requirements.append({**r, "ai_state": state, "ai_state_he": REQ_STATE_HE[state],
                             "requested_months": cov.get("requested", []) if cov else ([] if mine else requested),
                             "covered": cov.get("distinct", []),
                             "pending_review": [m for m in cov.get("distinct", []) if m not in verified],
                             "missing": missing, "duplicates": cov.get("duplicates", {}),
                             "open_customer_actions": len(customer), "open_banker_items": len(banker),
                             "open_customer_requests": len(asked),
                             "required": len(requested), "verified_months": verified_months,
                             "in_review_months": [m for m in requested if m in cov.get("distinct", []) and m not in verified],
                             "documents": len(mine),
                             "customer_status": customer_status(
                                 required=len(requested), documents=len(mine),
                                 failed=sum(d["status"] == "failed" for d in mine),
                                 review_failed=case_review_failed, reviewed_before=latest_case is not None,
                                 busy=any(d["status"] in ("queued", "processing") for d in mine) or (case_job_pending and bool(mine)),
                                 correction=len(correction) + len(asked_fix),
                                 missing=len(missing) + len(customer) - len(correction) + len(asked) - len(asked_fix),
                                 confirmed=confirmed is not None, banker=len(banker), verified=len(verified_months))})
    customer_actions = [f for f in open_f if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
    banker_items = [f for f in open_f if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    failed = [d for d in docs if d["status"] == "failed"]
    if pending:
        state = "RECHECKING" if latest_case else "CHECKING"
    elif not docs:
        state = "NOT_CHECKED"
    elif failed or case_review_failed:
        state = "ERROR"
    elif customer_actions or open_requests:
        state = "ACTION_REQUIRED"
    elif banker_items:
        state = "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS"
    else:
        state = "READY_FOR_HUMAN_REVIEW"
    if confirmed and not customer_actions and not open_requests and not pending and not failed and not case_review_failed:
        state = "PREPARATION_CONFIRMED"
    payslip_reqs = [r for r in requirements if r["evaluated_by_ai"]]
    required = sum(r["required"] for r in payslip_reqs)
    verified_total = sum(len(r["verified_months"]) for r in payslip_reqs)
    correction = [f for f in customer_actions if f["document_id"]]
    asked_fix = [q for q in open_requests if q["kind"] == "correction"]
    status = customer_status(
        required=required, documents=len(docs), failed=len(failed), review_failed=case_review_failed, busy=busy,
        reviewed_before=latest_case is not None, correction=len(correction) + len(asked_fix),
        missing=sum(len(r["missing"]) for r in payslip_reqs) + len(customer_actions) - len(correction)
        + len(open_requests) - len(asked_fix),
        confirmed=confirmed is not None, banker=len(banker_items), verified=verified_total)
    return {
        "scope": "income_documents.payslips", "state": state, "state_he": STATE_HE[state], "state_he_banker": STATE_HE_BANKER[state],
        "customer_status": status, "case_review_failed": case_review_failed,
        "payslips": {"required": required, "verified": verified_total, "requested_months": requested_default},
        "requirements": requirements,
        "counts": {"documents": len(docs), "reviewed": sum(d["status"] == "reviewed" for d in docs),
                   "processing": sum(d["status"] in ("queued", "processing") for d in docs), "failed": len(failed),
                   "customer_actions": len(customer_actions), "banker_items": len(banker_items),
                   "customer_requests": len(open_requests),
                   "documents_accepted": sum(s["status"] == "ACCEPTED" for s in statuses.values()),
                   "payslip_requirements_ready": sum(r["ai_state"] in ("extracted", "preparation_confirmed") for r in payslip_reqs),
                   "payslip_requirements_total": len(payslip_reqs)},
        "pending_jobs": pending, "not_evaluated": [r["title_he"] for r in requirements if not r["evaluated_by_ai"]],
        "banker_confirmation": confirmed, "banker_confirmation_stale": stale_confirmation,
        "last_case_run_id": latest_case_run, "computed_at": now_iso(),
    }
