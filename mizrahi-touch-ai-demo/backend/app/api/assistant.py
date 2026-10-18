"""Assistant → app actions: click-time validation of an offered action, and the outcome of an
upload that the customer started from the assistant."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import auth, i18n
from ..agent import actions, continuation
from ..i18n import continuation_en
from ..store import repo

router = APIRouter(prefix="/api/cases/{case_id}")


class Resolve(BaseModel):
    action_id: str
    turn_id: Optional[str] = None


@router.post("/actions/resolve")
def resolve_action(case_id: str, body: Resolve, request: Request):
    auth.require_customer_case(request, case_id)
    try:
        action = actions.resolve(case_id, body.action_id, body.turn_id)
    except actions.ActionRefused as exc:
        repo.audit(case_id, "customer", "assistant_action_refused", body.action_id, {"turn_id": body.turn_id, "code": exc.code})
        raise HTTPException(exc.status, exc.message_he) from None
    repo.audit(case_id, "customer", "assistant_action_opened", action.action_id, {"turn_id": body.turn_id, "type": action.type})
    return {"action": action.model_dump()}


@router.get("/documents/{document_id}/outcome")
def upload_outcome(case_id: str, document_id: str, request: Request):
    auth.require_customer_case(request, case_id)
    try:
        return i18n.localized(i18n.lang(request), continuation.outcome(case_id, document_id),
                              lambda o: continuation_en.outcome(o, case_id))
    except KeyError:
        raise HTTPException(404, "no such document in this case") from None
