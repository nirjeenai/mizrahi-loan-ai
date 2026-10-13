"""The banker's review desk — the human decisions on documents, missing documents and findings.

Every operation is a persisted, validated state transition with actor, time, previous and new
status, rationale and evidence references, written in one transaction with its audit event.
None of them touches the bank stage, and accepting a document is a documentary decision only:
it is not a credit decision and not an approval of the mortgage.

Customer requests are in-app requests stored in the case. Nothing here sends an SMS, an e-mail
or a push notification."""
from __future__ import annotations

import functools
import threading
from typing import Any, Callable, Optional, TypeVar

from ..bank.mock_bank import bank
from ..review import deterministic as det
from ..store import repo
from ..util import new_id, now_iso
from . import desk_state, engine, readiness

MAX_MESSAGE = 600
MAX_RATIONALE = 1000
COVERAGE_CODES = ("REQUIRED_PERIOD_MISSING", "DUPLICATE_PERIOD")
TRANSITIONS = {
    "ACCEPT_DOCUMENT": ({"AWAITING_DECISION", "ESCALATED"}, "ACCEPTED"),
    "REQUEST_CORRECTION": ({"AWAITING_DECISION", "AWAITING_CUSTOMER_FIX", "ESCALATED", "FAILED"}, "CORRECTION_REQUESTED"),
    "ESCALATE": ({"AWAITING_DECISION", "AWAITING_CUSTOMER_FIX"}, "ESCALATED"),
}
ACTION_HE = {
    "ACCEPT_DOCUMENT": "קבלת המסמך", "REQUEST_CORRECTION": "החזרה לתיקון", "ESCALATE": "העברה לבירור",
    "REQUEST_MISSING_DOCUMENT": "בקשת השלמת מסמך", "ACCEPT_EXPLANATION": "קבלת ההסבר (פעולה קודמת)",
    "RESOLVE_FINDING": "סגירת הבירור לאחר בדיקה", "DISMISS_FINDING": "דיווח על טעות בזיהוי ה-AI",
    "ESCALATE_FINDING": "העברה להמשך בירור", "REQUEST_EXPLANATION": "בקשת הסבר / אסמכתה",
    "REQUEST_DOCUMENT": "בקשת מסמך נוסף", "WITHDRAW_REQUEST": "ביטול בקשה ללקוח", "NOTE": "הערה פנימית",
    "CONFIRM_PREPARATION": "אישור הכנת מסמכי השכר", "ACKNOWLEDGE_HANDOFF": "קבלת פניית הלקוח לטיפול",
}
REASON_HE = {
    "verified_with_documents": "אומת מול מסמכים בתיק", "explanation_supported": "הסבר הלקוח נתמך באסמכתה",
    "professional_judgment": "החלטה מקצועית במסגרת המדיניות", "misread_document": "הנתון נקרא שגוי מהמסמך",
    "rule_not_applicable": "הכלל אינו חל על המקרה", "duplicate_finding": "כפילות של ממצא אחר", "other": "סיבה אחרת",
}


class DeskError(Exception):
    def __init__(self, status: int, message_he: str):
        super().__init__(message_he)
        self.status, self.message_he = status, message_he


_lock = threading.RLock()
F = TypeVar("F", bound=Callable[..., Any])


def _serialized(fn: F) -> F:
    """State check and write happen under one lock, so two concurrent submissions cannot both pass the check."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with _lock:
            return fn(*args, **kwargs)
    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------- shared helpers
def _clean(text: Optional[str], limit: int) -> str:
    return (text or "").strip()[:limit]


def _first(case: dict, borrower_id: Optional[str]) -> str:
    return next((b["first_name_he"] for b in case["borrowers"] if b["borrower_id"] == borrower_id), "")


def month_word(period: Optional[str]) -> str:
    return det.month_label_he(period).split()[0] if period else ""


def _claimed_period(doc: dict, review: Optional[dict]) -> Optional[str]:
    """The month the customer meant: what they picked when uploading, otherwise what the file name says."""
    intent = repo.upload_intent(doc["document_id"]) or {}
    return intent.get("expected_period") or (review or {}).get("file_name_period")


def _evidence_refs(findings: list[dict], review: Optional[dict] = None, fields: tuple[str, ...] = ()) -> list[dict]:
    refs = [{k: e.get(k) for k in ("evidence_id", "document_id", "field", "page", "witness")} for f in findings for e in f["evidence"]]
    for fact in (review or {}).get("facts", []):
        if fact["field"] in fields and fact.get("evidence"):
            refs.append({k: fact["evidence"].get(k) for k in ("evidence_id", "document_id", "field", "page", "witness")})
    seen, out = set(), []
    for r in refs:
        if r["evidence_id"] not in seen:
            seen.add(r["evidence_id"])
            out.append(r)
    return out


def _replay(request_id: Optional[str], case_id: str) -> Optional[dict]:
    """The same submission again (a double click, a retry after a timeout) returns the recorded decision."""
    if not request_id:
        return None
    prior = repo.decision_by_request(request_id)
    if prior and prior["case_id"] != case_id:
        raise DeskError(409, "מזהה הבקשה כבר שימש בתיק אחר.")
    return prior


def _result(decision: dict, case_id: str, duplicate: bool = False) -> dict:
    request = repo.customer_request(decision["customer_request_id"]) if decision.get("customer_request_id") else None
    return {"ok": True, "duplicate": duplicate, "decision": public_decision(decision), "customer_request": request,
            "readiness": readiness.compute(case_id)}


def public_decision(d: dict) -> dict:
    staff = {"actor_id": d["actor_id"], "actor_name": d["actor_name"]}
    return {**{k: d[k] for k in ("decision_id", "case_id", "target_kind", "document_id", "finding_id", "borrower_id", "period",
                                 "action", "previous_status", "new_status", "rationale", "customer_message",
                                 "customer_request_id", "finding_ids", "evidence_refs", "created_at")},
            **staff, "action_he": ACTION_HE.get(d["action"], d["action"]), "reason_code": d.get("reason_code"),
            "reason_he": REASON_HE.get(d.get("reason_code") or "")}


def _record(case_id: str, staff: dict, *, target_kind: str, action: str, previous: Optional[str], new: Optional[str],
            rationale: str = "", customer_message: str = "", document_id: Optional[str] = None,
            finding_id: Optional[str] = None, borrower_id: Optional[str] = None, period: Optional[str] = None,
            finding_ids: Optional[list[str]] = None, evidence: Optional[list[dict]] = None, request_id: Optional[str] = None,
            customer_request: Optional[dict] = None, finding_rows: Optional[list[dict]] = None,
            audit_action: str = "banker_decision", audit_extra: Optional[dict] = None, reason_code: Optional[str] = None,
            closes_requests: Optional[list[str]] = None, handoff_row: Optional[dict] = None,
            handoff_decision: Optional[tuple[str, str, str]] = None) -> dict:
    now = now_iso()
    decision = {"decision_id": new_id("DEC"), "case_id": case_id, "target_kind": target_kind, "document_id": document_id,
                "finding_id": finding_id, "borrower_id": borrower_id, "period": period, "action": action,
                "previous_status": previous, "new_status": new, "rationale": rationale or None,
                "customer_message": customer_message or None, "customer_request_id": None,
                "finding_ids": finding_ids or [], "evidence_refs": evidence or [], "actor_id": staff["staff_id"],
                "actor_name": staff["name_he"], "created_at": now, "request_id": request_id or new_id("REQ"),
                "reason_code": reason_code, "closes_requests": closes_requests or []}
    request_row = None
    if customer_request:
        request_row = {"customer_request_id": new_id("CR"), "case_id": case_id, "status": "OPEN", "created_at": now,
                       "updated_at": now, "created_by": staff["staff_id"], "created_by_name": staff["name_he"],
                       "decision_id": decision["decision_id"], "document_id": None, "finding_id": None, "period": None,
                       "requirement_code": None, "borrower_id": None, **customer_request}
        decision["customer_request_id"] = request_row["customer_request_id"]
    for f in finding_rows or []:
        f["history"] = f["history"] + [{"at": now, "event": f"banker_{action.lower()}", "actor": staff["staff_id"],
                                        "decision_id": decision["decision_id"], "note": rationale[:300] if rationale else None,
                                        "reason": reason_code}]
        f.update({"updated_at": now, "resolved_at": now if f["status"] != "open" else f.get("resolved_at")})
        if f["status"] == "superseded":
            f["superseded_by"] = decision["decision_id"]
    audit_row = {"case_id": case_id, "actor": f"banker:{staff['staff_id']}", "action": audit_action,
                 "target": document_id or finding_id or borrower_id or case_id,
                 "detail": {"decision_id": decision["decision_id"], "action": action, "previous_status": previous, "new_status": new,
                            "rationale": rationale or None, "customer_message": customer_message or None, "reason_code": reason_code,
                            "customer_request_id": decision["customer_request_id"], "finding_ids": finding_ids or [],
                            "closed_requests": closes_requests or [], "actor_name": staff["name_he"], **(audit_extra or {})}}
    repo.insert_decision(decision, request_row, finding_rows, audit_row, handoff_row, handoff_decision)
    return repo.decision_by_request(decision["request_id"])


# ---------------------------------------------------------------- customer message drafts (deterministic, editable)
def draft_correction(case: dict, doc: dict, review: Optional[dict], open_findings: list[dict]) -> dict[str, Any]:
    """A short Hebrew message for the customer, built from verified review facts. The banker edits it before sending."""
    first = _first(case, doc["borrower_id"])
    printed = (review or {}).get("period")
    claimed = _claimed_period(doc, review)
    period = claimed or printed
    hello = f"שלום {first}, " if first else ""
    label = f"תלוש {month_word(printed)}" if printed else f"הקובץ {doc['filename']}"
    codes = {f["code"] for f in open_findings if f["document_id"] == doc["document_id"]}
    if review is None:
        explanation = f"עיבוד הקובץ {doc['filename']} לא הושלם."
        message = f"{hello}לא הצלחנו לעבד את הקובץ {doc['filename']}. נא להעלות אותו שוב, רצוי כקובץ PDF מקורי מהמעסיק."
    elif claimed and printed and claimed != printed:
        explanation = f"הקובץ שהועלה עבור {month_word(claimed)} מכיל בפועל תלוש של חודש {month_word(printed)}."
        message = (f"{hello}המסמך שהעלית עבור {month_word(claimed)} מציג את חודש {month_word(printed)}. "
                   f"כדי להמשיך בבדיקת מסמכי ההכנסה, נא להעלות את תלוש {det.month_label_he(claimed)}.")
    elif "BORROWER_MISMATCH" in codes:
        explanation = f"המסמך {doc['filename']} אינו על שם הלווה שעבורו הועלה."
        message = (f"{hello}המסמך שהועלה עבורך ({doc['filename']}) אינו על שמך. "
                   f"נא להעלות את תלוש השכר שלך{' ל' + det.month_label_he(period) if period else ''}.")
    elif "UNEXPECTED_DOCUMENT_TYPE" in codes:
        explanation = f"הקובץ {doc['filename']} אינו תלוש שכר."
        message = f"{hello}הקובץ {doc['filename']} אינו תלוש שכר. נא להעלות תלוש שכר{' ל' + det.month_label_he(period) if period else ''}."
    elif "DOCUMENT_UNREADABLE" in codes:
        explanation = f"לא ניתן לקרוא את {label}."
        message = f"{hello}לא הצלחנו לקרוא את {label}. נא להעלות עותק ברור — עדיף קובץ PDF מקורי מהמעסיק או מאתר השכר."
    elif "PERIOD_UNCLEAR" in codes:
        explanation = "בתלוש לא מודפס חודש שכר חד־משמעי."
        message = f"{hello}בתלוש שהעלית לא מופיע חודש שכר ברור. נא להעלות תלוש שבו מודפס חודש השכר."
    else:
        failing = [c for c in (review or {}).get("criteria", []) if c["outcome"] in ("FAIL", "NEEDS_REVIEW")]
        explanation = failing[0]["explanation_he"] if failing else "נמצאו בתלוש פרטים שדורשים מסמך נוסף."
        message = (f"{hello}ב{label} שהעלית חלק מהפרטים אינם ברורים לנו. "
                   "נא להעלות עותק מקורי של התלוש מהמעסיק או מאתר השכר.")
    item = f"תלוש שכר ל{det.month_label_he(period)} — {first}" if period else f"תלוש שכר מתוקן — {first}"
    return {"explanation_he": explanation, "message_he": message, "requested_period": period, "requested_item_he": item}


def draft_missing(case: dict, borrower_id: str, period: str, related: list[dict]) -> dict[str, Any]:
    first = _first(case, borrower_id)
    hello = f"שלום {first}, " if first else ""
    mislabeled = next((r for r in related if r.get("claimed_period") == period and r.get("printed_period") != period), None)
    if mislabeled:
        message = (f"{hello}המסמך שהעלית עבור {month_word(period)} מציג את חודש {month_word(mislabeled['printed_period'])}, "
                   f"ולכן תלוש {det.month_label_he(period)} עדיין חסר. נא להעלות אותו כדי להמשיך בבדיקת מסמכי ההכנסה.")
    else:
        message = f"{hello}כדי להשלים את בדיקת מסמכי ההכנסה חסר תלוש השכר של {det.month_label_he(period)}. נא להעלות אותו באפליקציה."
    return {"message_he": message, "requested_period": period, "requested_item_he": f"תלוש שכר ל{det.month_label_he(period)} — {first}"}


def draft_missing_months(case: dict, borrower_id: str, months: list[str]) -> dict[str, Any]:
    first = _first(case, borrower_id)
    hello = f"שלום {first}, " if first else ""
    if len(months) == 1:
        message = f"{hello}כדי להשלים את בדיקת ההכנסה חסר תלוש השכר של {det.month_label_he(months[0])}. נא להעלות אותו באפליקציה."
    else:
        words = [month_word(m) for m in months]
        listed = (", ".join(words[:-1]) + " ו" + words[-1]) + (f" {months[0][:4]}" if len({m[:4] for m in months}) == 1 else "")
        message = f"{hello}כדי להשלים את בדיקת ההכנסה חסרים תלושי השכר של {listed}. נא להעלות אותם באפליקציה."
    return {"message_he": message, "months": months, "requested_item_he": f"תלושי שכר חסרים — {first}"}


def draft_explanation(case: dict, finding: dict, income: Optional[dict]) -> dict[str, Any]:
    first = _first(case, finding["borrower_id"])
    hello = f"שלום {first}, " if first else ""
    needed = [x for x in ((finding.get("detail") or {}).get("semantic") or {}).get("evidence_needed_he") or [] if x]
    if income and income.get("declared_net_monthly_ils") and income.get("average_documented_net_ils") is not None:
        documented = income.get("documented_label_he") or "בתלושים"
        message = (f"{hello}ההכנסה החודשית נטו שהצהרת ({income['declared_net_monthly_ils']:,.0f} ₪) שונה מהנטו {documented} "
                   f"({income['average_documented_net_ils']:,.0f} ₪). נבקש הסבר קצר, ואם אפשר גם אסמכתה — "
                   f"{needed[0].rstrip('.') if needed else 'למשל אישור מעסיק על רכיבי שכר משתנים'}.")
    else:
        message = f"{hello}בבדיקת המסמכים עלתה שאלה: {finding['title_he']}. נבקש הסבר קצר, ואם אפשר גם מסמך תומך."
    return {"message_he": message, "requested_item_he": f"הסבר או אסמכתה — {first}"}


def draft_additional(case: dict, finding: dict) -> dict[str, Any]:
    first = _first(case, finding["borrower_id"])
    hello = f"שלום {first}, " if first else ""
    needed = [x for x in ((finding.get("detail") or {}).get("semantic") or {}).get("evidence_needed_he") or [] if x]
    ask = needed[0].rstrip(".") if needed else "מסמך שמסביר את ההפרש בין ההכנסה שהוצהרה לבין התלושים"
    return {"message_he": f"{hello}כדי להשלים את בדיקת ההכנסה נבקש להעלות: {ask}.", "requested_period": None,
            "requested_item_he": f"מסמך משלים לבדיקת ההכנסה — {first}"}


# ---------------------------------------------------------------- document decisions
@_serialized
def decide_document(case_id: str, document_id: str, staff: dict, action: str, rationale: str = "",
                    customer_message: str = "", requested_period: Optional[str] = None,
                    acknowledged_finding_ids: Optional[list[str]] = None, request_id: Optional[str] = None) -> dict:
    case = bank.get_case(case_id)
    if action not in TRANSITIONS:
        raise DeskError(422, "פעולה לא מוכרת.")
    doc = repo.document(document_id)
    if not doc or doc["case_id"] != case_id:
        raise DeskError(404, "המסמך אינו שייך לתיק.")
    prior = _replay(request_id, case_id)
    if prior:
        if prior["document_id"] != document_id or prior["action"] != action:
            raise DeskError(409, "מזהה הבקשה כבר שימש לפעולה אחרת.")
        return _result(prior, case_id, duplicate=True)
    rationale, customer_message = _clean(rationale, MAX_RATIONALE), _clean(customer_message, MAX_MESSAGE)
    open_f = repo.findings(case_id, status="open")
    status = desk_state.document_statuses(case_id, open_findings=open_f)[document_id]
    allowed, new = TRANSITIONS[action]
    if status["status"] not in allowed:
        if action == "ACCEPT_DOCUMENT" and status["status"] == "AWAITING_CUSTOMER_FIX":
            raise DeskError(409, "בבדיקת ה-AI נמצא ממצא שמחייב תיקון מצד הלקוח. אם הממצא שגוי — סמנו אותו כשגוי, ורק אז קבלו את המסמך.")
        raise DeskError(409, f"לא ניתן לבצע ״{ACTION_HE[action]}״ במסמך במצב ״{status['status_he']}״.")
    review = repo.latest_document_result(document_id) if doc["status"] == "reviewed" else None
    mine = [f for f in open_f if f["document_id"] == document_id]
    banker_findings = [f for f in mine if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    finding_rows: list[dict] = []
    customer_request = None
    if action == "ACCEPT_DOCUMENT":
        expected = sorted(f["finding_id"] for f in banker_findings)
        if sorted(acknowledged_finding_ids or []) != expected:
            raise DeskError(409, "רשימת הממצאים במסמך השתנתה מאז שנפתח. רעננו את המסך ובדקו שוב לפני הקבלה.")
        if (banker_findings or (review or {}).get("verdict") != "VALID") and not rationale:
            raise DeskError(422, "יש לנמק קבלה של מסמך שבדיקת ה-AI לא מצאה תקין או שיש בו ממצאים פתוחים.")
        finding_rows = [{**f, "status": "resolved", "resolution": "accepted_by_banker",
                         "resolution_note": rationale or None} for f in banker_findings]
    elif action == "REQUEST_CORRECTION":
        if not customer_message:
            raise DeskError(422, "יש לכתוב ללקוח מה לתקן או להעלות.")
        period = requested_period or None
        if period and period not in readiness.policy_months():
            raise DeskError(422, "החודש המבוקש אינו אחד מחודשי השכר הנדרשים.")
        if period and any(r["borrower_id"] == doc["borrower_id"] and r["period"] == period
                          for r in repo.customer_requests(case_id, status="OPEN")):
            raise DeskError(409, f"כבר נשלחה ללקוח בקשה פתוחה לתלוש {det.month_label_he(period)}.")
        first = _first(case, doc["borrower_id"])
        customer_request = {"kind": "correction", "borrower_id": doc["borrower_id"], "document_id": document_id,
                            "requirement_code": doc["requirement_code"], "period": period, "message_he": customer_message,
                            "title_he": (f"נדרש תלוש {det.month_label_he(period)} — {first}" if period
                                         else f"נדרש תלוש מתוקן במקום {doc['filename']} — {first}")}
        finding_rows = [{**f, "status": "superseded", "resolution": "correction_requested_by_banker",
                         "resolution_note": rationale or None} for f in banker_findings]
    elif action == "ESCALATE":
        if not rationale:
            raise DeskError(422, "יש לציין מה דורש בירור.")
    decision = _record(case_id, staff, target_kind="document", action=action, previous=status["status"], new=new,
                       rationale=rationale, customer_message=customer_message if action == "REQUEST_CORRECTION" else "",
                       document_id=document_id, borrower_id=doc["borrower_id"],
                       period=(customer_request or {}).get("period") or (review or {}).get("period"),
                       finding_ids=[f["finding_id"] for f in banker_findings],
                       evidence=_evidence_refs(mine, review, ("salary_period", "net_pay")), request_id=request_id,
                       customer_request=customer_request, finding_rows=finding_rows, audit_action="banker_document_decision",
                       audit_extra={"filename": doc["filename"]})
    return _result(decision, case_id)


# ---------------------------------------------------------------- missing documents
@_serialized
def request_missing(case_id: str, staff: dict, borrower_id: str, period: str, customer_message: str,
                    rationale: str = "", request_id: Optional[str] = None) -> dict:
    case = bank.get_case(case_id)
    if borrower_id not in {b["borrower_id"] for b in case["borrowers"]}:
        raise DeskError(404, "הלווה אינו שייך לתיק.")
    prior = _replay(request_id, case_id)
    if prior:
        if prior["action"] != "REQUEST_MISSING_DOCUMENT" or prior["borrower_id"] != borrower_id or prior["period"] != period:
            raise DeskError(409, "מזהה הבקשה כבר שימש לפעולה אחרת.")
        return _result(prior, case_id, duplicate=True)
    customer_message, rationale = _clean(customer_message, MAX_MESSAGE), _clean(rationale, MAX_RATIONALE)
    if not customer_message:
        raise DeskError(422, "יש לכתוב ללקוח מה להעלות.")
    if engine.pending_jobs(case_id):
        raise DeskError(409, "ה-AI עדיין בודק מסמכים בתיק, וייתכן שהחודש כבר הועלה. המתינו לסיום הבדיקה ורק אז בקשו את המסמך.")
    req = next((r for r in readiness.compute(case_id)["requirements"] if r["evaluated_by_ai"] and r["borrower_id"] == borrower_id), None)
    missing = (req or {}).get("missing") or []
    if period not in missing:
        raise DeskError(409, f"{det.month_label_he(period) if period else 'החודש'} אינו חסר כרגע אצל {_first(case, borrower_id)}.")
    if any(r["borrower_id"] == borrower_id and r["period"] == period for r in repo.customer_requests(case_id, status="OPEN")):
        raise DeskError(409, f"כבר נשלחה ללקוח בקשה פתוחה לתלוש {det.month_label_he(period)}.")
    finding = next((f for f in repo.findings(case_id, status="open")
                    if f["code"] == "REQUIRED_PERIOD_MISSING" and f["borrower_id"] == borrower_id and f["period"] == period), None)
    first = _first(case, borrower_id)
    decision = _record(case_id, staff, target_kind="missing_period", action="REQUEST_MISSING_DOCUMENT", previous="MISSING",
                       new="REQUESTED", rationale=rationale, customer_message=customer_message, borrower_id=borrower_id,
                       period=period, finding_id=(finding or {}).get("finding_id"), request_id=request_id,
                       customer_request={"kind": "missing_document", "borrower_id": borrower_id, "period": period,
                                         "requirement_code": (req or {}).get("code"), "message_he": customer_message,
                                         "finding_id": (finding or {}).get("finding_id"),
                                         "title_he": f"נדרש תלוש {det.month_label_he(period)} — {first}"},
                       audit_action="banker_requested_document")
    return _result(decision, case_id)


# ---------------------------------------------------------------- findings
FINDING_ACTIONS = {"resolve": "RESOLVE_FINDING", "dismiss": "DISMISS_FINDING", "escalate": "ESCALATE_FINDING",
                   "request_explanation": "REQUEST_EXPLANATION", "request_document": "REQUEST_DOCUMENT",
                   "accept_explanation": "RESOLVE_FINDING"}
RESOLUTION_REASONS = ("verified_with_documents", "explanation_supported", "professional_judgment")
DISMISS_REASONS = ("misread_document", "rule_not_applicable", "duplicate_finding", "other")
MIN_OVERRIDE_RATIONALE = 15


def finding_basis(f: dict) -> dict[str, Any]:
    """How complete the evidence behind a finding is. Only the declared-income comparison can rest on part of the months."""
    detail = f.get("detail") or {}
    compared = detail.get("months_compared") or (detail.get("stats") or {}).get("months_compared") or []
    required = detail.get("months_required") or readiness.policy_months()
    partial = f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE" and bool(compared) and len(compared) < len(required)
    return {"partial": partial, "months_compared": compared, "months_required": required,
            "months_missing": [m for m in required if m not in compared] if partial else []}


def finding_escalated(finding: dict, decisions: list[dict]) -> bool:
    mine = [d for d in decisions if d["finding_id"] == finding["finding_id"] and d["action"] != "NOTE"]
    return finding["status"] == "open" and bool(mine) and mine[-1]["action"] == "ESCALATE_FINDING"


def _supporting_documents(case_id: str, finding: dict, ids: list[str]) -> list[dict]:
    docs = []
    for did in dict.fromkeys(ids or []):
        doc = repo.document(did)
        if not doc or doc["case_id"] != case_id or doc["status"] != "reviewed":
            raise DeskError(422, "אחד המסמכים שסומנו אינו מסמך שנבדק בתיק הזה.")
        if finding["borrower_id"] and doc["borrower_id"] != finding["borrower_id"]:
            raise DeskError(422, "אחד המסמכים שסומנו שייך ללווה אחר.")
        docs.append(doc)
    return docs


@_serialized
def decide_finding(case_id: str, finding_id: str, staff: dict, action: str, rationale: str = "",
                   customer_message: str = "", request_id: Optional[str] = None, reason_code: Optional[str] = None,
                   evidence_document_ids: Optional[list[str]] = None, acknowledge_partial: bool = False) -> dict:
    """A banker ruling on an AI finding. Resolving says the issue was checked and settled; dismissing says the AI was
    wrong; escalating keeps it open for further review; a request asks the customer for a document or an explanation.
    None of them is a decision on a document, and a customer statement alone never settles a finding."""
    case = bank.get_case(case_id)
    if action not in FINDING_ACTIONS:
        raise DeskError(422, "פעולה לא מוכרת.")
    f = repo.finding(finding_id)
    if not f or f["case_id"] != case_id:
        raise DeskError(404, "הממצא אינו שייך לתיק.")
    code = FINDING_ACTIONS[action]
    if action == "accept_explanation":                   # the former single action, kept for API callers
        action, reason_code = "resolve", reason_code or "professional_judgment"
    prior = _replay(request_id, case_id)
    if prior:
        if prior["finding_id"] != finding_id or prior["action"] != code:
            raise DeskError(409, "מזהה הבקשה כבר שימש לפעולה אחרת.")
        return _result(prior, case_id, duplicate=True)
    if f["status"] != "open":
        raise DeskError(409, "הממצא כבר טופל.")
    rationale, customer_message = _clean(rationale, MAX_RATIONALE), _clean(customer_message, MAX_MESSAGE)
    if f["review_state"] == "INFO":
        raise DeskError(409, "ממצא לידיעה אינו דורש החלטה.")
    if f["code"] in COVERAGE_CODES:
        raise DeskError(409, "חודש חסר או כפול הוא עובדת כיסוי ולא ממצא שאפשר לסגור. לבקשת המסמך השתמשו ב״בקשת השלמת מסמך״.")
    if action != "dismiss" and f["review_state"] != "NEEDS_BANKER_REVIEW":
        raise DeskError(409, "פעולה זו זמינה רק לממצאים שממתינים לשיקול דעת הבנקאי.")
    if action in ("request_document", "request_explanation") and f["document_id"]:
        raise DeskError(409, "לממצא במסמך מסוים — החזירו את המסמך לתיקון מתוך המסמך עצמו.")
    linked = [r["customer_request_id"] for r in repo.customer_requests(case_id, status="OPEN") if r["finding_id"] == finding_id]
    statements = [x for x in repo.statements(case_id) if x["finding_id"] == finding_id]
    evidence = _evidence_refs([f])
    finding_rows, customer_request, closes, extra = [], None, [], {"code": f["code"]}
    if action == "resolve":
        if reason_code not in RESOLUTION_REASONS:
            raise DeskError(422, "יש לבחור על מה מבוססת סגירת הבירור.")
        if not rationale:
            raise DeskError(422, "יש לנמק את סגירת הבירור.")
        docs = _supporting_documents(case_id, f, evidence_document_ids or [])
        if reason_code in ("verified_with_documents", "explanation_supported") and not docs:
            raise DeskError(422, "יש לסמן את המסמכים שמאמתים את הסגירה.")
        if reason_code == "explanation_supported" and not statements:
            raise DeskError(409, "לא נמסר הסבר מהלקוח בממצא הזה. בחרו בסיס אחר לסגירה או בקשו הסבר.")
        if reason_code == "professional_judgment" and len(rationale) < MIN_OVERRIDE_RATIONALE:
            raise DeskError(422, "החלטה מקצועית בלי אסמכתה מחייבת נימוק מפורט.")
        basis = finding_basis(f)
        if basis["partial"] and not acknowledge_partial:
            raise DeskError(409, f"ההשוואה מבוססת על {len(basis['months_compared'])} מתוך {len(basis['months_required'])} החודשים "
                                 "הנדרשים. כדי להכריע עכשיו יש לאשר במפורש הכרעה על בסיס חלקי.")
        for doc in docs:
            evidence += _evidence_refs([], repo.latest_document_result(doc["document_id"]), ("net_pay", "salary_period"))
        finding_rows = [{**f, "status": "resolved", "resolution": "resolved_by_banker", "resolution_note": rationale}]
        closes, new = linked, "resolved"
        extra.update({"evidence_document_ids": [d["document_id"] for d in docs], "partial_basis": basis["partial"],
                      "customer_statements": len(statements)})
    elif action == "dismiss":
        reason_code = reason_code if reason_code in DISMISS_REASONS else "other"
        if len(rationale) < MIN_OVERRIDE_RATIONALE:
            raise DeskError(422, "דיווח על טעות של ה-AI מחייב נימוק מפורט.")
        finding_rows = [{**f, "status": "dismissed", "resolution": "dismissed_by_banker", "resolution_note": rationale}]
        closes, new = linked, "dismissed"
    elif action == "escalate":
        if not rationale:
            raise DeskError(422, "יש לציין מה דורש המשך בירור.")
        if finding_escalated(f, repo.decisions(case_id)):
            raise DeskError(409, "הממצא כבר הועבר להמשך בירור.")
        finding_rows, new = [{**f}], "open"
    else:
        if not customer_message:
            raise DeskError(422, "יש לכתוב ללקוח מה נדרש.")
        if linked:
            raise DeskError(409, "כבר נשלחה ללקוח בקשה פתוחה בנושא זה.")
        first = _first(case, f["borrower_id"])
        explain = action == "request_explanation"
        customer_request = {"kind": "explanation" if explain else "additional_document", "borrower_id": f["borrower_id"],
                            "finding_id": finding_id, "message_he": customer_message,
                            "requirement_code": f"PAYSLIPS:{f['borrower_id']}" if f["borrower_id"] else None,
                            "title_he": f"נדרש הסבר או אסמכתה — {first}" if explain else f"נדרש מסמך משלים — {first}"}
        finding_rows, new = [{**f}], "open"
    decision = _record(case_id, staff, target_kind="finding", action=code, previous=f["status"], new=new, rationale=rationale,
                       customer_message=customer_message if customer_request else "", finding_id=finding_id,
                       document_id=f["document_id"], borrower_id=f["borrower_id"], period=f["period"],
                       finding_ids=[finding_id], evidence=evidence, request_id=request_id, reason_code=reason_code,
                       customer_request=customer_request, finding_rows=finding_rows, closes_requests=closes,
                       audit_action="banker_finding_decision", audit_extra=extra)
    return _result(decision, case_id)


@_serialized
def withdraw_request(case_id: str, staff: dict, customer_request_id: str, rationale: str,
                     request_id: Optional[str] = None) -> dict:
    """The banker closes an open customer request that is no longer needed. A request is never closed by the AI."""
    prior = _replay(request_id, case_id)
    if prior:
        return _result(prior, case_id, duplicate=True)
    r = repo.customer_request(customer_request_id)
    if not r or r["case_id"] != case_id:
        raise DeskError(404, "הבקשה אינה שייכת לתיק.")
    if r["status"] != "OPEN":
        raise DeskError(409, "הבקשה כבר נענתה או נסגרה.")
    rationale = _clean(rationale, MAX_RATIONALE)
    if not rationale:
        raise DeskError(422, "יש לנמק את ביטול הבקשה.")
    reopen = []
    if r["kind"] == "correction" and r.get("decision_id"):
        origin = next((d for d in repo.decisions(case_id) if d["decision_id"] == r["decision_id"]), None)
        for fid in (origin or {}).get("finding_ids") or []:
            f = repo.finding(fid)
            if f and f["status"] == "superseded" and f.get("resolution") == "correction_requested_by_banker":
                reopen.append({**f, "status": "open", "resolution": None, "resolution_note": None, "resolved_at": None,
                               "superseded_by": None})
    decision = _record(case_id, staff, target_kind="customer_request", action="WITHDRAW_REQUEST", previous="OPEN", new="CLOSED",
                       rationale=rationale, finding_id=r["finding_id"], document_id=r["document_id"], borrower_id=r["borrower_id"],
                       period=r["period"], request_id=request_id, closes_requests=[customer_request_id], finding_rows=reopen,
                       finding_ids=[f["finding_id"] for f in reopen], audit_action="banker_request_withdrawn",
                       audit_extra={"customer_request_id": customer_request_id, "title_he": r["title_he"], "kind": r["kind"]})
    return _result(decision, case_id)


# ---------------------------------------------------------------- notes and the case-level step
@_serialized
def add_note(case_id: str, staff: dict, text: str, document_id: Optional[str] = None, finding_id: Optional[str] = None,
             request_id: Optional[str] = None) -> dict:
    prior = _replay(request_id, case_id)
    if prior:
        return _result(prior, case_id, duplicate=True)
    text = _clean(text, MAX_RATIONALE)
    if not text:
        raise DeskError(422, "ההערה ריקה.")
    status = None
    if document_id:
        doc = repo.document(document_id)
        if not doc or doc["case_id"] != case_id:
            raise DeskError(404, "המסמך אינו שייך לתיק.")
        status = desk_state.document_statuses(case_id)[document_id]["status"]
    if finding_id:
        f = repo.finding(finding_id)
        if not f or f["case_id"] != case_id:
            raise DeskError(404, "הממצא אינו שייך לתיק.")
        status = f["status"]
    decision = _record(case_id, staff, target_kind="document" if document_id else "finding" if finding_id else "case",
                       action="NOTE", previous=status, new=status, rationale=text, document_id=document_id,
                       finding_id=finding_id, request_id=request_id, audit_action="banker_note")
    return _result(decision, case_id)


def open_handoffs(case_id: str) -> list[dict]:
    """Customer requests to be passed to the banker (assistant or MCP) that no banker has taken yet."""
    return [h for h in repo.handoffs(case_id) if h["status"] == "IN_BANKER_QUEUE_DEMO" and not h.get("banker_decision")]


@_serialized
def confirm_preparation(case_id: str, staff: dict, note: str = "", request_id: Optional[str] = None) -> dict:
    """The banker confirms the payslip documents are prepared for her handling. Refused while the customer has open
    items or the AI is still working. Never a credit decision; the bank stage does not move. The confirmation lapses
    when a document is uploaded after it or the banker asks the customer for something (readiness.confirmation)."""
    from ..api.banker_package import build_package    # banker_package imports this module
    prior = _replay(request_id, case_id)
    if prior:
        if prior["action"] != "CONFIRM_PREPARATION":
            raise DeskError(409, "מזהה הבקשה כבר שימש לפעולה אחרת.")
        return {**_result(prior, case_id, duplicate=True),
                "package_id": (repo.handoff_by_request(f"confirm:{request_id}") or {}).get("package_id")}
    state = readiness.compute(case_id)
    if state["counts"]["customer_actions"] or state["counts"]["customer_requests"]:
        raise DeskError(409, "יש פריטים פתוחים לטיפול הלקוח — לא ניתן לאשר הכנה")
    if state["state"] in ("CHECKING", "RECHECKING", "NOT_CHECKED", "ERROR"):
        raise DeskError(409, f"לא ניתן לאשר במצב {state['state_he_banker']}")
    current = state.get("banker_confirmation")
    if current:
        return {"ok": True, "duplicate": True, "package_id": current.get("package_id"), "readiness": state}
    note = _clean(note, 500)
    pkg = build_package(case_id)
    now = now_iso()
    handoff = {"package_id": new_id("PKG"), "case_id": case_id, "status": "DECIDED", "created_at": now,
               "created_by": f"banker:{staff['staff_id']}", "channel": "banker_console", "note": note, "package": pkg,
               "request_id": f"confirm:{request_id or new_id('C')}", "banker_decision": "confirmed_preparation",
               "decided_at": now, "decided_note": note}
    decision = _record(case_id, staff, target_kind="case", action="CONFIRM_PREPARATION", previous=state["state"],
                       new="PREPARATION_CONFIRMED", rationale=note, request_id=request_id, audit_action="banker_confirmed_preparation",
                       audit_extra={"package_id": handoff["package_id"], "open_banker_items": state["counts"]["banker_items"],
                                    "case_run_id": pkg.get("case_run_id")}, handoff_row=handoff)
    return {**_result(decision, case_id), "package_id": handoff["package_id"]}


@_serialized
def acknowledge_handoff(case_id: str, staff: dict, package_id: str, note: str = "", request_id: Optional[str] = None) -> dict:
    """The banker takes a customer's 'pass me to my banker' request into handling. The note stays internal."""
    prior = _replay(request_id, case_id)
    if prior:
        if prior["action"] != "ACKNOWLEDGE_HANDOFF":
            raise DeskError(409, "מזהה הבקשה כבר שימש לפעולה אחרת.")
        return _result(prior, case_id, duplicate=True)
    h = next((x for x in repo.handoffs(case_id) if x["package_id"] == package_id), None)
    if not h:
        raise DeskError(404, "הפנייה אינה שייכת לתיק.")
    if h["status"] != "IN_BANKER_QUEUE_DEMO" or h.get("banker_decision"):
        raise DeskError(409, "הפנייה כבר טופלה.")
    decision = _record(case_id, staff, target_kind="handoff", action="ACKNOWLEDGE_HANDOFF", previous="IN_BANKER_QUEUE_DEMO",
                       new="ACKNOWLEDGED", rationale=_clean(note, MAX_RATIONALE), request_id=request_id,
                       audit_action="banker_handoff_acknowledged",
                       audit_extra={"package_id": package_id}, handoff_decision=(package_id, "acknowledged", _clean(note, MAX_RATIONALE)))
    return _result(decision, case_id)


# ---------------------------------------------------------------- customer uploads answering a request
def check_request_link(case_id: str, borrower_id: Optional[str], customer_request_id: Optional[str]) -> None:
    """Refuse an upload that names someone else's request before the file is stored."""
    if not customer_request_id:
        return
    target = repo.customer_request(customer_request_id)
    if not target or target["case_id"] != case_id:
        raise DeskError(404, "הבקשה אינה שייכת לתיק.")
    if target["borrower_id"] and target["borrower_id"] != borrower_id:
        raise DeskError(422, "המסמך הועלה עבור לווה אחר מזה שהבקשה מתייחסת אליו.")


def check_replacement(case_id: str, borrower_id: Optional[str], replaces_document_id: Optional[str],
                      customer_request_id: Optional[str] = None) -> None:
    """A customer may replace, on their own, only a document the AI review sent back to them (an open customer finding
    on it) — of the same borrower, not yet replaced, decided or asked about by the banker. Checked before storing."""
    if not replaces_document_id:
        return
    old = repo.document(replaces_document_id)
    if not old or old["case_id"] != case_id:
        raise DeskError(404, "המסמך שאותו מחליפים אינו שייך לתיק.")
    if old["borrower_id"] != borrower_id:
        raise DeskError(422, "המסמך החלופי חייב להיות של אותו לווה.")
    if customer_request_id or any(r["document_id"] == replaces_document_id for r in repo.customer_requests(case_id, status="OPEN")):
        raise DeskError(409, "על המסמך הזה יש בקשה פתוחה מהבנקאי — יש להעלות דרך הבקשה.")
    status = desk_state.document_statuses(case_id)[replaces_document_id]["status"]
    if status != "AWAITING_CUSTOMER_FIX":
        raise DeskError(409, "המסמך הזה אינו ממתין להחלפה." if status != "REPLACED" else "המסמך הזה כבר הוחלף.")


@_serialized
def link_upload(case_id: str, doc: dict, created: bool, customer_request_id: Optional[str],
                expected_period: Optional[str]) -> Optional[dict]:
    """An upload answers a banker request when it names the request, when exactly one of the borrower's open requests
    is for the month the customer picked, or when it is the borrower's only open request and the months don't
    disagree. A re-upload of a file already in the case answers nothing."""
    if not created:
        return None
    open_requests = [r for r in repo.customer_requests(case_id, status="OPEN") if r["borrower_id"] == doc["borrower_id"]]
    same_month = [r for r in open_requests if expected_period and r["period"] == expected_period]
    if customer_request_id:
        target = repo.customer_request(customer_request_id)
        if not target or target["status"] != "OPEN":
            return None
    elif len(same_month) == 1:
        target = same_month[0]
    elif len(open_requests) == 1 and (not open_requests[0]["period"] or not expected_period
                                      or open_requests[0]["period"] == expected_period):
        target = open_requests[0]
    else:
        return None
    if not repo.respond_customer_request(target["customer_request_id"], doc["document_id"]):
        return None
    repo.audit(case_id, "customer", "customer_request_responded", target["customer_request_id"],
               {"document_id": doc["document_id"], "kind": target["kind"], "replaces": target["document_id"],
                "period": target["period"]})
    return repo.customer_request(target["customer_request_id"])


# ---------------------------------------------------------------- written answers to a request
@_serialized
def reply_to_request(case_id: str, customer_request_id: str, text: str, channel: str = "app") -> dict:
    """The customer answers an explanation request in writing. The answer is attached to the finding as unverified
    context; the finding stays open for the banker."""
    r = repo.customer_request(customer_request_id)
    if not r or r["case_id"] != case_id:
        raise DeskError(404, "הבקשה אינה שייכת לתיק.")
    if r["kind"] not in ("explanation", "additional_document"):
        raise DeskError(409, "לבקשה זו יש להעלות מסמך.")
    if r["status"] != "OPEN":
        raise DeskError(409, "כבר השבתם לבקשה הזו.")
    text = _clean(text, MAX_RATIONALE)
    if not text:
        raise DeskError(422, "התשובה ריקה.")
    st = repo.add_statement(case_id, r["finding_id"], text, channel, "customer", f"reply:{customer_request_id}")
    repo.respond_customer_request(customer_request_id, statement_id=st["statement_id"])
    repo.audit(case_id, "customer", "customer_statement_recorded", st["statement_id"], {"finding_id": r["finding_id"], "channel": channel})
    repo.audit(case_id, "customer", "customer_request_responded", customer_request_id,
               {"kind": r["kind"], "statement_id": st["statement_id"], "finding_id": r["finding_id"]})
    engine.request_case_review(case_id, "customer answered a banker request", "customer")
    return repo.customer_request(customer_request_id)


@_serialized
def link_statement(case_id: str, statement: dict) -> Optional[dict]:
    """A statement recorded by the assistant (chat, voice, MCP) answers the open explanation request on the same finding."""
    if not statement.get("finding_id"):
        return None
    target = next((r for r in repo.customer_requests(case_id, status="OPEN")
                   if r["finding_id"] == statement["finding_id"] and r["kind"] == "explanation"), None)
    if not target or not repo.respond_customer_request(target["customer_request_id"], statement_id=statement["statement_id"]):
        return None
    repo.audit(case_id, statement.get("actor") or "customer", "customer_request_responded", target["customer_request_id"],
               {"kind": target["kind"], "statement_id": statement["statement_id"], "finding_id": statement["finding_id"],
                "channel": statement.get("channel")})
    return repo.customer_request(target["customer_request_id"])
