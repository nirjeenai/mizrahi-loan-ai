"""Banker console API — human decisions with gates and audit. Every route needs a signed-in staff session
(app/auth.py); writes need the case's assigned banker. Staff identity comes only from the session, never from a
header the browser chooses."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import auth
from ..bank.mock_bank import bank
from ..store import repo
from ..workflow import engine, readiness, review_desk
from ..workflow.review_desk import DeskError
from . import banker_chat, banker_intelligence
from .banker_package import build_package, build_workspace, case_queue_counts

router = APIRouter(prefix="/api/banker")


def _case(case_id: str) -> dict:
    try:
        return bank.get_case(case_id)
    except KeyError:
        raise HTTPException(404, "no such case") from None


def _reader(request: Request, case_id: str) -> dict:
    s = auth.require_staff(request)
    _case(case_id)
    return s


def _staff(request: Request, case_id: str) -> dict:
    return auth.require_assigned_staff(request, case_id)


def _desk(call):
    try:
        return call()
    except DeskError as exc:
        raise HTTPException(exc.status, exc.message_he) from None


@router.get("/cases")
def cases(request: Request):
    auth.require_staff(request)
    out = []
    for cid in bank.case_ids():
        c = bank.get_case(cid)
        st = readiness.compute(cid)
        out.append({"case_id": cid, "display_number": c["display_number"], "title_he": c["title_he"],
                    "borrowers": [b["name_he"] for b in c["borrowers"]], "readiness": st["state"],
                    "readiness_he": st["state_he_banker"], "counts": st["counts"], "queue": case_queue_counts(cid),
                    "banker": c["banker"], "handoffs": len(review_desk.open_handoffs(cid))})
    return out


@router.get("/cases/{case_id}/package")
def package(case_id: str, request: Request):
    _reader(request, case_id)
    return {**build_package(case_id), "handoffs": repo.handoffs(case_id), "conversation": repo.turns(case_id),
            "runs": repo.runs(case_id), "audit": repo.audit_events(case_id, 200),
            "decisions": [review_desk.public_decision(d) for d in repo.decisions(case_id)],
            "customer_requests": repo.customer_requests(case_id)}


@router.get("/cases/{case_id}/workspace")
def workspace(case_id: str, request: Request):
    _reader(request, case_id)
    return build_workspace(case_id)


@router.get("/cases/{case_id}/intelligence")
def intelligence(case_id: str, request: Request):
    """Banker Intelligence V2: the case briefing, financial context and scenarios. Read-only; writes nothing."""
    _reader(request, case_id)
    return banker_intelligence.build(case_id)


class ChatTurn(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(..., max_length=4000)


class ChatDraft(BaseModel):
    kind: str = Field(..., max_length=60)
    text: str = Field(..., max_length=6000)


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=24)
    draft: Optional[ChatDraft] = None


@router.post("/cases/{case_id}/chat")
def chat(case_id: str, body: ChatMessage, request: Request):
    """Banker V3 "שאל את JEEN": answers about this case and may propose a checked revision of the draft the banker sent.
    Writes nothing to the case; the browser applies a returned revision to its own editor."""
    _reader(request, case_id)
    try:
        return banker_chat.respond(case_id, body.message, [t.model_dump() for t in body.history],
                                   body.draft.model_dump() if body.draft else None)
    except banker_chat.ChatUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("/cases/{case_id}/conversation")
def conversation(case_id: str, request: Request):
    """The customer's conversation as the banker reads it. Read-only: unlike the customer route it posts nothing."""
    _reader(request, case_id)
    return [{**t, "actions": (t["provenance"] or {}).get("actions") or []} for t in repo.turns(case_id)]


class DocumentDecision(BaseModel):
    action: Literal["accept", "request_correction", "escalate"]
    rationale: str = Field("", max_length=2000)
    customer_message: str = Field("", max_length=2000)
    requested_period: Optional[str] = None
    acknowledged_finding_ids: list[str] = []
    request_id: Optional[str] = Field(None, max_length=80)


DOCUMENT_ACTION = {"accept": "ACCEPT_DOCUMENT", "request_correction": "REQUEST_CORRECTION", "escalate": "ESCALATE"}


@router.post("/cases/{case_id}/documents/{document_id}/decision")
def decide_document(case_id: str, document_id: str, body: DocumentDecision, request: Request):
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.decide_document(
        case_id, document_id, staff, DOCUMENT_ACTION[body.action], body.rationale, body.customer_message,
        body.requested_period, body.acknowledged_finding_ids, body.request_id))


class MissingRequest(BaseModel):
    borrower_id: str
    period: str
    customer_message: str = Field("", max_length=2000)
    rationale: str = Field("", max_length=2000)
    request_id: Optional[str] = Field(None, max_length=80)


@router.post("/cases/{case_id}/missing-requests")
def request_missing(case_id: str, body: MissingRequest, request: Request):
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.request_missing(case_id, staff, body.borrower_id, body.period, body.customer_message,
                                                     body.rationale, body.request_id))


class RequirementRequest(BaseModel):
    customer_message: str = Field("", max_length=2000)
    rationale: str = Field("", max_length=2000)
    request_id: Optional[str] = Field(None, max_length=80)


@router.post("/cases/{case_id}/requirements/{requirement_code}/request")
def request_requirement(case_id: str, requirement_code: str, body: RequirementRequest, request: Request):
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.request_requirement(case_id, staff, requirement_code, body.customer_message,
                                                         body.rationale, body.request_id))


class FindingDecision(BaseModel):
    action: Literal["resolve", "dismiss", "escalate", "request_explanation", "request_document", "accept_explanation"]
    rationale: str = Field("", max_length=2000)
    note: str = Field("", max_length=2000)
    customer_message: str = Field("", max_length=2000)
    reason_code: Optional[str] = Field(None, max_length=40)
    evidence_document_ids: list[str] = []
    acknowledge_partial: bool = False
    request_id: Optional[str] = Field(None, max_length=80)


@router.post("/cases/{case_id}/findings/{finding_id}/decision")
def decide_finding(case_id: str, finding_id: str, body: FindingDecision, request: Request):
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.decide_finding(
        case_id, finding_id, staff, body.action, body.rationale or body.note, body.customer_message, body.request_id,
        body.reason_code, body.evidence_document_ids, body.acknowledge_partial))


class Withdraw(BaseModel):
    rationale: str = Field("", max_length=2000)
    request_id: Optional[str] = Field(None, max_length=80)


@router.post("/cases/{case_id}/customer-requests/{customer_request_id}/withdraw")
def withdraw_request(case_id: str, customer_request_id: str, body: Withdraw, request: Request):
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.withdraw_request(case_id, staff, customer_request_id, body.rationale, body.request_id))


class Note(BaseModel):
    text: str = Field(..., max_length=2000)
    document_id: Optional[str] = None
    finding_id: Optional[str] = None
    request_id: Optional[str] = Field(None, max_length=80)


@router.post("/cases/{case_id}/notes")
def add_note(case_id: str, body: Note, request: Request):
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.add_note(case_id, staff, body.text, body.document_id, body.finding_id, body.request_id))


class Acknowledge(BaseModel):
    note: str = Field("", max_length=2000)
    request_id: Optional[str] = Field(None, max_length=80)


@router.post("/cases/{case_id}/handoffs/{package_id}/acknowledge")
def acknowledge_handoff(case_id: str, package_id: str, body: Acknowledge, request: Request):
    """The banker takes the customer's 'transfer to my banker' request into handling. The note stays internal."""
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.acknowledge_handoff(case_id, staff, package_id, body.note, body.request_id))


class Confirm(BaseModel):
    note: str = Field("", max_length=500)
    request_id: Optional[str] = Field(None, max_length=80)


@router.post("/cases/{case_id}/confirm-preparation")
def confirm_preparation(case_id: str, body: Confirm, request: Request):
    """The case-level human step: the banker confirms the INCOME documents are prepared for her own
    handling. Refused while customer actions or banker requests are open. Never a credit decision;
    bank status untouched. The confirmation lapses when the document set changes or the banker reopens the case."""
    staff = _staff(request, case_id)
    return _desk(lambda: review_desk.confirm_preparation(case_id, staff, body.note, body.request_id))


@router.post("/cases/{case_id}/recheck")
def recheck(case_id: str, request: Request):
    staff = _staff(request, case_id)
    return {"queued": engine.request_case_review(case_id, "banker requested re-review", f"banker:{staff['staff_id']}")}
