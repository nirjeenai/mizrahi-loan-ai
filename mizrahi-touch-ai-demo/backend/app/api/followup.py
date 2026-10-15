"""Follow-up, presence, links, the Talk receiver and the demo controls (CONTRACTS §8).

Access uses the session checks `auth.py` already has (CONTRACTS §4): customer routes need the customer session of
that case, banker reads any staff session, banker writes the case's assigned banker. The customer projection holds
no rule ids, attempts, policy versions or banker text. Demo routes exist only with DEMO_IDENTITY=1, accept a staff
session or the case's customer session (the presenter drives them from the customer app), are audited and say
"סימולציה" in every response."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, Field, model_validator

from .. import auth, clock, events
from ..comms import webhook
from ..config import settings
from ..followup import links, orchestrator, presence, tasks
from ..followup.contract import CALL_OUTCOMES
from ..store import repo

router = APIRouter(prefix="/api")
SIM = {"label_he": "סימולציה", "simulated": True}


# ---------------------------------------------------------------- customer
class PresenceEvent(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    event: Literal[presence.EVENTS]  # type: ignore[valid-type]
    seq: int = Field(..., ge=0)
    visible: bool = True
    screen: Optional[Literal[presence.SCREENS]] = None  # type: ignore[valid-type]
    requirement_code: Optional[str] = Field(None, max_length=60)


class Snooze(BaseModel):
    minutes: Optional[int] = Field(None, ge=15, le=1440)
    until: Optional[AwareDatetime] = None

    @model_validator(mode="after")
    def _one(self) -> "Snooze":
        if (self.minutes is None) == (self.until is None):
            raise ValueError("minutes or until, exactly one")
        return self


class Preferences(BaseModel):
    opt_out_voice: Optional[bool] = None
    opt_out_message: Optional[bool] = None
    preferred_channel: Optional[Literal["in_app", "message", "voice"]] = None


class Redeem(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


def _aggregate(case_id: str) -> tuple:
    pol, _ = orchestrator.published_policy()
    ttl = pol.followup.presence_ttl_seconds if pol else 90
    reqs = tuple(t["requirement_code"] for t in tasks.open_for(case_id))
    s = presence.snapshot(case_id, clock.now(), ttl, reqs)
    return (s["presence"], s["on_task_screen"], s["upload_in_flight"]), ttl


@router.post("/cases/{case_id}/presence")
def post_presence(case_id: str, body: PresenceEvent, request: Request):
    auth.require_customer_case(request, case_id)
    before, ttl = _aggregate(case_id)
    presence.record(case_id, body.session_id, body.event, body.seq, body.visible, body.screen, body.requirement_code)
    after, _ = _aggregate(case_id)
    if after != before:
        events.emit("customer.presence_changed.v1", case_id, "customer",
                    {"from": before[0], "to": after[0], "on_task_screen": after[1], "upload_in_flight": after[2]},
                    occurred_at=clock.now_iso())
        orchestrator.on_event(case_id, f"presence:{body.event}")
    return {"state": after[0], "ttl_seconds": ttl}


@router.get("/cases/{case_id}/followup")
def get_followup(case_id: str, request: Request):
    auth.require_customer_case(request, case_id)
    return orchestrator.customer_view(case_id)


@router.post("/cases/{case_id}/followup-snooze")
def snooze(case_id: str, body: Snooze, request: Request):
    auth.require_customer_case(request, case_id)
    now = clock.now()
    until = now + timedelta(minutes=body.minutes) if body.minutes else body.until
    if until <= now or until > now + timedelta(minutes=1440):
        raise HTTPException(422, "אפשר לדחות עד 24 שעות קדימה.")
    orchestrator.set_preferences(case_id, "customer", snooze_until=until.isoformat(timespec="seconds"))
    repo.audit(case_id, "customer", "customer_followup_snoozed", case_id, {"until": until.isoformat(timespec="seconds")})
    orchestrator.on_event(case_id, "customer_snooze")
    return orchestrator.customer_view(case_id)


@router.post("/cases/{case_id}/contact-preferences")
def contact_preferences(case_id: str, body: Preferences, request: Request):
    auth.require_customer_case(request, case_id)
    changes = body.model_dump(exclude_none=True)
    if changes:
        orchestrator.set_preferences(case_id, "customer", **changes)
        repo.audit(case_id, "customer", "customer_contact_preferences_changed", case_id, changes)
        orchestrator.on_event(case_id, "customer_preferences")
    return orchestrator.customer_view(case_id)


@router.post("/links/redeem")
def redeem(body: Redeem, response: Response):
    result = links.redeem(body.token)
    if result["state"] not in ("ok", "resolved"):
        return {"state": result["state"]}
    token = auth.issue("customer", [result["case_id"]])
    auth._set(response, "customer", token)
    repo.audit(result["case_id"], "customer", "followup_link_redeemed", result["case_id"], {"state": result["state"]})
    return result


# ---------------------------------------------------------------- banker
class Override(BaseModel):
    type: Literal["pause", "resume", "cancel"]
    reason: str = Field(..., min_length=3, max_length=300)


class ManualCall(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


@router.get("/banker/cases/{case_id}/followup")
def banker_followup(case_id: str, request: Request):
    auth.require_staff(request)
    auth._known_case(case_id)
    return orchestrator.banker_view(case_id)


@router.get("/banker/cases/{case_id}/timeline")
def banker_timeline(case_id: str, request: Request, limit: int = 200):
    auth.require_staff(request)
    auth._known_case(case_id)
    return orchestrator.timeline(case_id, max(1, min(limit, 500)))


@router.post("/banker/cases/{case_id}/followup-override")
def banker_override(case_id: str, body: Override, request: Request):
    staff = auth.require_assigned_staff(request, case_id)
    orchestrator.banker_override(case_id, body.type, body.reason, staff["staff_id"])
    repo.audit(case_id, f"banker:{staff['staff_id']}", f"followup_{body.type}", case_id, {"reason": body.reason})
    return orchestrator.banker_view(case_id)


@router.post("/banker/cases/{case_id}/followups", status_code=201)
def banker_manual_call(case_id: str, body: ManualCall, request: Request):
    staff = auth.require_assigned_staff(request, case_id)
    attempt, decision = orchestrator.manual_call(case_id, staff["staff_id"], body.reason)
    repo.audit(case_id, f"banker:{staff['staff_id']}", "followup_manual_call", case_id,
               {"reason": body.reason, "action": decision.action, "blocked_by": list(decision.blocked_by)})
    if attempt is None:
        return JSONResponse(status_code=409, content={"detail": decision.explanation_he,
                                                      "blocked_by": list(decision.blocked_by)})
    keep = ("attempt_id", "channel", "provider", "simulated", "status", "outcome", "created_at", "link_id")
    return {k: attempt[k] for k in keep}


# ---------------------------------------------------------------- Talk receiver (off until a secret is configured)
@router.post("/webhooks/jeen-talk")
async def talk_webhook(request: Request):
    if not webhook.secret():
        raise HTTPException(404, "not configured")
    if not webhook.secret_ok(request.headers.get("x-talk-secret")):
        raise HTTPException(401, "bad secret")
    try:
        body = await request.json()
        result = orchestrator.handle_talk_event(body, "jeen-talk")
    except (ValueError, webhook.Malformed) as exc:
        raise HTTPException(400, f"malformed event: {exc}") from None
    return JSONResponse(status_code=202 if result == "orphan" else 200, content={"result": result})


# ---------------------------------------------------------------- demo controls
class Clock(BaseModel):
    advance_minutes: Optional[int] = Field(None, ge=1, le=10080)
    to_next_window: bool = False
    reset: bool = False


class TalkOutcome(BaseModel):
    outcome: Literal[CALL_OUTCOMES]  # type: ignore[valid-type]
    callback_at: Optional[AwareDatetime] = None


def _demo(request: Request, case_id: Optional[str] = None) -> str:
    if not settings.demo_identity or clock.environment() != "demo":
        raise HTTPException(404, "demo controls are switched off")
    staff = auth.staff(request)
    if staff:
        if case_id:
            auth._known_case(case_id)
        return f"demo:{staff['staff_id']}"
    if case_id:
        auth.require_customer_case(request, case_id)
    else:
        auth.require_customer(request)
    return "demo:customer"


@router.post("/demo/clock")
def demo_clock(body: Clock, request: Request):
    actor = _demo(request)
    if body.reset:
        state = clock.reset(actor)
    elif body.to_next_window:
        pol, _ = orchestrator.published_policy()
        target = clock.next_window_start(clock.now(), pol.followup.call_window, pol.followup.holidays) if pol else None
        state = clock.set_to(target, actor) if target else clock.state()
    elif body.advance_minutes:
        state = clock.advance(body.advance_minutes, actor)
    else:
        state = clock.state()
    repo.audit(None, actor, "demo_clock", "", state)
    return {**SIM, **state}


@router.post("/demo/cases/{case_id}/customer-left")
def demo_customer_left(case_id: str, request: Request):
    actor = _demo(request, case_id)
    ended = presence.end_all(case_id)
    result = orchestrator.on_event(case_id, "demo:customer_left", actor=actor)
    repo.audit(case_id, actor, "demo_customer_left", case_id, {"ended_sessions": ended})
    return {**SIM, "ended_sessions": ended, "state": result["state"],
            "decision": result["decision"].model_dump(mode="json")}


@router.post("/demo/cases/{case_id}/talk-outcome")
def demo_talk_outcome(case_id: str, body: TalkOutcome, request: Request):
    actor = _demo(request, case_id)
    attempt = orchestrator.set_talk_outcome(case_id, body.outcome, body.callback_at)
    if attempt is None:
        raise HTTPException(409, "אין שיחה מדומה פעילה בתיק")
    repo.audit(case_id, actor, "demo_talk_outcome", attempt["attempt_id"], {"outcome": body.outcome})
    return {**SIM, "attempt_id": attempt["attempt_id"], "status": attempt["status"], "outcome": attempt["outcome"],
            "plan_state": (orchestrator.plan(case_id) or {}).get("state")}


@router.get("/demo/cases/{case_id}/sent-links")
def demo_sent_links(case_id: str, request: Request):
    _demo(request, case_id)
    return {**SIM, "links": links.sent(case_id)}


@router.post("/demo/tick")
def demo_tick(request: Request):
    actor = _demo(request)
    out = orchestrator.tick()
    repo.audit(None, actor, "demo_tick", "", {"evaluated": len(out["evaluated"]), "steps": out["steps"]})
    return {**SIM, **out}
