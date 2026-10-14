"""The outbound-contact boundary (CONTRACTS §10). `OutboundProvider` is the only path to a customer contact; nothing
outside `comms/` knows whether a call is simulated or live, except that every attempt records `provider` and
`simulated`. Connecting live JEEN Talk means implementing this protocol in `jeen_talk.py`; the workflow stays."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional, Protocol

ALLOWED_ACTIONS = ("send_link", "mark_no_answer", "request_human", "schedule_callback")
CONTEXT_TOOL = "get_followup_context"
RETRY_BACKOFF_MINUTES = (5, 30)              # code constant: the policy schema has no retry section (CONTRACTS §2)


class ProviderNotConfigured(Exception):
    pass


@dataclass(frozen=True)
class Capabilities:
    cancel_call: bool
    get_call: bool
    send_message: bool
    hebrew_voice: bool
    sandbox: bool


@dataclass(frozen=True)
class Health:
    ok: bool
    detail: str


@dataclass(frozen=True)
class CallRequest:
    idempotency_key: str                     # case:{case}:plan:{plan_version}:tasks:{hash}
    client_reference: str                    # the attempt id
    case_ref: str                            # opaque
    contact_ref: str                         # opaque; the demo uses the allowlisted TEST-LINE-01
    prompt_version: str
    variables: dict                          # first_name, missing_documents[], secure_upload_link, next_step
    expires_at: str
    locale: str = "he-IL"
    allowed_actions: tuple[str, ...] = ALLOWED_ACTIONS
    requires_identity_verification: bool = True
    context_tool: str = CONTEXT_TOOL
    callback_url: Optional[str] = None

    def redacted(self) -> dict:
        """What is stored on the attempt: the upload link's token never lands in the database in clear."""
        out = asdict(self)
        out["variables"] = {**self.variables, "secure_upload_link": "[secure-link]"}
        return out


@dataclass(frozen=True)
class MessageRequest:
    idempotency_key: str
    client_reference: str
    case_ref: str
    contact_ref: str
    text: str
    locale: str = "he-IL"


@dataclass(frozen=True)
class ProviderAck:
    provider_call_id: str
    status: str
    accepted_at: str


@dataclass(frozen=True)
class CancelResult:
    status: Literal["CANCELED", "TOO_LATE_TO_CANCEL", "NOT_FOUND"]


@dataclass(frozen=True)
class CallState:
    status: str
    sequence: int
    updated_at: str
    outcome: Optional[str] = None
    data: dict = field(default_factory=dict)


class OutboundProvider(Protocol):
    name: str
    simulated: bool

    def capabilities(self) -> Capabilities: ...
    def health(self) -> Health: ...
    def create_call(self, req: CallRequest) -> ProviderAck: ...        # idempotent on req.idempotency_key
    def cancel_call(self, provider_call_id: str) -> CancelResult: ...
    def get_call(self, provider_call_id: str) -> CallState: ...
    def send_message(self, req: MessageRequest) -> ProviderAck: ...
