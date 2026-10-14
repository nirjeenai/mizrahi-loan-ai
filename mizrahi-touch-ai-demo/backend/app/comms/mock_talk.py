"""MockTalkProvider: a JEEN Talk stand-in that never dials anyone.

A call is a script the follow-up tick advances: DIALING, then CONNECTED, then a final status with an outcome. Each step
is the same event body a live provider would post (04 §6) and goes through the same receiver
(`orchestrator.handle_talk_event` → `webhook.apply`), so the receiving code path is real. The script's state lives on
the attempt row (`request.mock`); the demo's talk-outcome control picks the outcome (LINK_SENT by default)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from .contract import CallRequest, CallState, CancelResult, Capabilities, Health, MessageRequest, ProviderAck

# (status of the step, seconds after the previous step)
SCRIPT = (("DIALING", 0), ("CONNECTED", 20), ("FINAL", 40))
FINAL_STATUS = {"NO_ANSWER": "NO_ANSWER", "IDENTITY_FAILED": "COMPLETED"}   # every other outcome completes the call


def call_id(idempotency_key: str) -> str:
    return "MOCK-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:12].upper()


class MockTalkProvider:
    name = "mock-talk"
    simulated = True

    def capabilities(self) -> Capabilities:
        return Capabilities(cancel_call=True, get_call=True, send_message=True, hebrew_voice=True, sandbox=True)

    def health(self) -> Health:
        return Health(ok=True, detail="סימולציה — אין חיוג אמיתי")

    def create_call(self, req: CallRequest) -> ProviderAck:
        return ProviderAck(provider_call_id=call_id(req.idempotency_key), status="QUEUED", accepted_at=req.expires_at)

    def cancel_call(self, provider_call_id: str) -> CancelResult:
        return CancelResult("CANCELED")      # the orchestrator answers TOO_LATE_TO_CANCEL once the script connected

    def get_call(self, provider_call_id: str) -> CallState:
        return CallState(status="UNKNOWN", sequence=0, updated_at="")

    def send_message(self, req: MessageRequest) -> ProviderAck:
        return ProviderAck(provider_call_id=call_id(req.idempotency_key), status="SENT", accepted_at="")


def first_step(now: datetime) -> dict:
    return {"step": 0, "next_at": now.isoformat(timespec="seconds"), "outcome": "LINK_SENT", "callback_at": None}


def step_event(attempt: dict, mock: dict, now: datetime) -> tuple[dict, dict]:
    """The event of the script's current step and the script state after it."""
    step = mock["step"]
    status, _ = SCRIPT[step]
    data: dict = {}
    outcome: Optional[str] = None
    if status == "FINAL":
        outcome = mock.get("outcome") or "LINK_SENT"
        status = FINAL_STATUS.get(outcome, "COMPLETED")
        data = {"link_sent": outcome == "LINK_SENT", "identity_verified": outcome != "IDENTITY_FAILED"}
        if outcome == "CALLBACK_REQUESTED" and mock.get("callback_at"):
            data["callback_at"] = mock["callback_at"]
    event = {"event_id": f"{attempt['provider_call_id']}:{step}", "event_type": "call.status_changed",
             "client_reference": attempt["attempt_id"], "provider_call_id": attempt["provider_call_id"],
             "sequence": step + 1, "status": status, "outcome": outcome,
             "occurred_at": now.isoformat(timespec="seconds"), "data": data}
    following = step + 1
    nxt = dict(mock, step=following, next_at=None)
    if following < len(SCRIPT):
        nxt["next_at"] = (now + timedelta(seconds=SCRIPT[following][1])).isoformat(timespec="seconds")
    return event, nxt
