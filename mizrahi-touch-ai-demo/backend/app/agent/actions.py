"""App actions — the structured contract between the assistant and the Tefahot Touch app.

Every action is derived by the Mortgage Case Service from persisted case state: the borrower,
the requirement, the missing months and the document all come from here. The model only
chooses among the derived actions by id (offer_app_actions) and never supplies a borrower,
a requirement, a month or a route. The app re-resolves an action against the current state
before acting on it, so an action offered earlier is refused once it no longer applies."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from ..bank.mock_bank import bank
from ..review import deterministic as det
from ..store import repo
from ..workflow import readiness

CONTRACT = "app_action.v1"
MAX_OFFERED = 4
FINDING_RANK = {"CUSTOMER_ACTION_REQUIRED": 0, "NEEDS_BANKER_REVIEW": 1, "INFO": 2}

ActionType = Literal["NAVIGATE_TO_DOCUMENT_UPLOAD", "VIEW_DOCUMENT_REVIEW", "VIEW_MISSING_DOCUMENTS",
                     "VIEW_REVIEW_STATUS", "VIEW_CASE_DETAILS", "CONTACT_BANKER"]


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


DOCUMENT_TYPE = {"payslip": "PAYSLIP", "id_document": "ID_CARD", "bank_statement": "BANK_STATEMENT",
                 "purpose_proof": "PURPOSE_PROOF", "tax_form": "TAX_FORM"}


class UploadParams(_Params):
    borrower_id: Optional[str] = None             # None for a case-level requirement (proof of purpose)
    requirement_code: str
    document_type: Literal["PAYSLIP", "ID_CARD", "BANK_STATEMENT", "PURPOSE_PROOF", "TAX_FORM"]
    period: Optional[str] = None                  # only when the month is unambiguous
    missing_periods: list[str] = []
    finding_ids: list[str] = []


class DocumentParams(_Params):
    document_id: str
    finding_ids: list[str] = []


class BankerParams(_Params):
    message_he: str
    finding_ids: list[str] = []


class NoParams(_Params):
    pass


PARAMS: dict[str, type[_Params]] = {
    "NAVIGATE_TO_DOCUMENT_UPLOAD": UploadParams, "VIEW_DOCUMENT_REVIEW": DocumentParams, "CONTACT_BANKER": BankerParams,
    "VIEW_MISSING_DOCUMENTS": NoParams, "VIEW_REVIEW_STATUS": NoParams, "VIEW_CASE_DETAILS": NoParams,
}


class AppAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract: Literal["app_action.v1"] = CONTRACT
    action_id: str
    type: ActionType
    case_id: str
    label_he: str
    detail_he: Optional[str] = None
    priority: int
    params: dict[str, Any] = {}

    @model_validator(mode="after")
    def _typed_params(self) -> "AppAction":
        self.params = PARAMS[self.type](**self.params).model_dump()
        return self


class ActionRefused(Exception):
    def __init__(self, status: int, code: str, message_he: str):
        super().__init__(message_he)
        self.status, self.code, self.message_he = status, code, message_he


# ---------------------------------------------------------------- Hebrew month wording
def month_name(month: str) -> str:
    return det.month_label_he(month).split()[0]


def months_he(months: list[str]) -> str:
    """['2026-07', '2026-08', '2026-09'] → 'יולי, אוגוסט וספטמבר 2026'."""
    if len({m[:4] for m in months}) == 1:
        words, year = [month_name(m) for m in months], f" {months[0][:4]}"
    else:
        words, year = [det.month_label_he(m) for m in months], ""
    if len(words) < 2:
        return "".join(words) + year
    return ", ".join(words[:-1]) + " ו" + words[-1] + year


# ---------------------------------------------------------------- derivation
def derive(case: dict, state: dict, open_findings: list[dict], documents: list[dict], handoffs: list[dict],
           requested: list[str], requests: list[dict] = ()) -> list[AppAction]:
    """Pure: what the customer can do in the app right now, most important first. `requests` are the
    banker's open in-app requests."""
    case_id = case["case_id"]
    names = {b["borrower_id"]: b["first_name_he"] for b in case["borrowers"]}
    files = {d["document_id"]: d for d in documents}
    out: list[AppAction] = []

    def add(action_id: str, type_: str, label: str, detail: Optional[str], priority: int, **params: Any) -> None:
        out.append(AppAction(action_id=action_id, type=type_, case_id=case_id, label_he=label, detail_he=detail,
                             priority=priority, params=params))

    missing_total = 0

    def payslip_side(x: dict) -> bool:
        return (x.get("detail") or {}).get("family", "payslip") == "payslip"

    payslips = [r for r in state["requirements"] if r["evaluated_by_ai"] and r.get("family", "payslip") == "payslip"
                and r.get("borrower_id") in names]
    for i, r in enumerate(payslips):
        bid, name = r["borrower_id"], names[r["borrower_id"]]
        # coverage exists only after the first case review; before it nothing has been verified yet
        missing = list(r.get("missing") or []) if r.get("requested_months") else list(requested)
        fixes = [f for f in open_findings if f["borrower_id"] == bid and f["review_state"] == "CUSTOMER_ACTION_REQUIRED"
                 and payslip_side(f)]
        asked = [q for q in requests if q["borrower_id"] == bid and (q.get("requirement_code") or r["code"]) == r["code"]]
        if not missing and not fixes and not asked:
            continue
        missing_total += len(missing)
        if len(missing) == 1:
            label, detail, period = (f"העלאת תלוש {month_name(missing[0])} ל{name}",
                                     f"חסר תלוש {det.month_label_he(missing[0])}", missing[0])
        elif missing:
            label, detail, period = f"העלאת תלושים ל{name}", f"חסרים: {months_he(missing)}", None
        elif asked:
            label, detail, period = f"העלאת המסמך שביקשה הבנקאית ל{name}", asked[0]["title_he"], asked[0].get("period")
        else:
            label, detail, period = f"העלאת תלוש מתוקן ל{name}", fixes[0]["title_he"], fixes[0].get("period")
        checking = sum(d["status"] in ("queued", "processing") for d in documents if d["borrower_id"] == bid)
        if checking:
            detail += " · " + ("מסמך אחד בבדיקה" if checking == 1 else f"{checking} מסמכים בבדיקה")
        add(f"upload:{r['code']}", "NAVIGATE_TO_DOCUMENT_UPLOAD", label, detail, 10 + i, borrower_id=bid,
            requirement_code=r["code"], document_type="PAYSLIP", period=period, missing_periods=missing,
            finding_ids=[f["finding_id"] for f in fixes])

    others = [r for r in state["requirements"] if r["evaluated_by_ai"] and r.get("family", "payslip") != "payslip"
              and r.get("ai_state") in ("required_missing", "needs_customer_action")]
    for i, r in enumerate(others):
        code = r["code"]
        fixes = [f for f in open_findings if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"
                 and (f.get("detail") or {}).get("requirement_code") == code]
        asked = [q for q in requests if q.get("requirement_code") == code]
        who = names.get(r.get("borrower_id") or "")
        # a missing document or a gap in the period is a first upload; only a document sent back is uploaded again
        verb = "העלאה מחדש:" if any(f.get("document_id") for f in fixes) else "העלאת"
        label = f"{verb} {r.get('family_he') or 'מסמך'}" + (f" ל{who}" if who and len(names) > 1 else "")
        detail = asked[0]["title_he"] if asked else fixes[0]["title_he"] if fixes else r["title_he"]
        add(f"upload:{code}", "NAVIGATE_TO_DOCUMENT_UPLOAD", label, detail, 15 + i, borrower_id=r.get("borrower_id"),
            requirement_code=code, document_type=DOCUMENT_TYPE.get(r["family"], "PAYSLIP"), period=None, missing_periods=[],
            finding_ids=[f["finding_id"] for f in fixes])

    by_doc: dict[str, list[dict]] = {}
    for f in open_findings:
        if f.get("document_id") in files:
            by_doc.setdefault(f["document_id"], []).append(f)
    for doc_id, found in by_doc.items():
        found.sort(key=lambda f: FINDING_RANK.get(f["review_state"], 3))
        top = found[0]
        add(f"review:{doc_id}", "VIEW_DOCUMENT_REVIEW", "צפייה בממצא", f"{top['title_he']} · {files[doc_id]['filename']}",
            20 + 10 * FINDING_RANK.get(top["review_state"], 3), document_id=doc_id,
            finding_ids=[f["finding_id"] for f in found])

    processing = [d for d in documents if d["status"] in ("queued", "processing")]
    if processing or state.get("pending_jobs"):
        detail = ("בודקים מחדש את סט המסמכים" if not processing else
                  "מסמך אחד בבדיקה" if len(processing) == 1 else f"{len(processing)} מסמכים בבדיקה")
        add("documents:status", "VIEW_REVIEW_STATUS", "צפייה בסטטוס הבדיקה", detail, 35)

    if any(a.type == "NAVIGATE_TO_DOCUMENT_UPLOAD" for a in out):
        detail = None if not missing_total else "חסר תלוש אחד" if missing_total == 1 else f"חסרים {missing_total} תלושים"
        add("documents:missing", "VIEW_MISSING_DOCUMENTS", "צפייה בכל המסמכים החסרים", detail, 50)

    banker_items = [f for f in open_findings if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    queued = any(h["status"] == "IN_BANKER_QUEUE_DEMO" and not h.get("banker_decision") for h in handoffs)
    if banker_items and not queued:
        banker = case["banker"]["name_he"]
        add("banker:handoff", "CONTACT_BANKER", f"העברת התיק ל{banker}", banker_items[0]["title_he"], 60,
            message_he=f"אני מאשר/ת להעביר את התיק עם הממצאים ל{banker} לבדיקה.",
            finding_ids=[f["finding_id"] for f in banker_items])

    add("case:details", "VIEW_CASE_DETAILS", "מעבר לפרטי התיק", None, 90)
    return sorted(out, key=lambda a: a.priority)


def available(case_id: str, state: Optional[dict] = None) -> list[AppAction]:
    return derive(bank.get_case(case_id), state or readiness.compute(case_id), repo.findings(case_id, status="open"),
                  repo.documents(case_id), repo.handoffs(case_id), readiness.policy_months(case_id),
                  repo.customer_requests(case_id, status="OPEN"))


# ---------------------------------------------------------------- choosing, offering, resolving
def compact(a: AppAction) -> dict:
    return {"action_id": a.action_id, "type": a.type, "label_he": a.label_he, "detail_he": a.detail_he}


def choose(available_now: list[AppAction], action_ids: list[str]) -> tuple[list[AppAction], list[str]]:
    by_id = {a.action_id: a for a in available_now}
    wanted = list(dict.fromkeys(str(x) for x in action_ids))
    chosen = sorted((by_id[x] for x in wanted if x in by_id), key=lambda a: a.priority)
    return chosen[:MAX_OFFERED], [x for x in wanted if x not in by_id]


def merge(current: list[dict], more: list[dict]) -> list[dict]:
    by_id = {a["action_id"]: a for a in current + more}
    return sorted(by_id.values(), key=lambda a: a["priority"])[:MAX_OFFERED]


def default_offer(case_id: str) -> list[dict]:
    """Without the model (fallback reply): the customer's next steps, straight from case state."""
    picks = [a for a in available(case_id)
             if a.type in ("NAVIGATE_TO_DOCUMENT_UPLOAD", "VIEW_DOCUMENT_REVIEW", "VIEW_MISSING_DOCUMENTS")]
    return [a.model_dump() for a in picks[:3]]


def offered_in(turn: dict) -> set[str]:
    return {a["action_id"] for a in ((turn.get("provenance") or {}).get("actions") or [])}


def resolve(case_id: str, action_id: str, turn_id: Optional[str] = None) -> AppAction:
    """Click-time check: the action belongs to this case, was really offered there, and still applies."""
    if turn_id:
        turn = repo.turn(turn_id)
        if not turn:
            raise ActionRefused(404, "unknown_turn", "השיחה שממנה הגיעה הפעולה לא נמצאה.")
        if turn["case_id"] != case_id or turn["role"] != "assistant":
            raise ActionRefused(403, "foreign_case", "הפעולה שייכת לתיק אחר ולא בוצעה.")
        if action_id not in offered_in(turn):
            raise ActionRefused(404, "not_offered", "הפעולה לא הוצעה בשיחה הזו ולא בוצעה.")
    current = next((a for a in available(case_id) if a.action_id == action_id), None)
    if not current:
        raise ActionRefused(409, "stale", "הפעולה כבר אינה רלוונטית למצב התיק הנוכחי.")
    return current
