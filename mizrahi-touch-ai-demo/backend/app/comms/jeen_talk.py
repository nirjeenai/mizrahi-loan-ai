"""The live JEEN Talk slot — a stub. It reports "not configured" and refuses every call, so `talk.mode = live` yields
OP-PROVIDER-UNHEALTHY (and HG-LIVE-DIAL-DEMO in the demo environment): no real customer can be dialled until this
class is implemented against JEEN Talk's API and configured. The receiver's signature check is added at the same
time (CONTRACTS §12)."""
from __future__ import annotations

from .contract import (CallRequest, CallState, CancelResult, Capabilities, Health, MessageRequest, ProviderAck,
                       ProviderNotConfigured)


class JeenTalkProvider:
    name = "jeen-talk"
    simulated = False

    def capabilities(self) -> Capabilities:
        return Capabilities(cancel_call=False, get_call=False, send_message=False, hebrew_voice=True, sandbox=False)

    def health(self) -> Health:
        return Health(ok=False, detail="JEEN Talk לא הוגדר — אין חיבור חי")

    def create_call(self, req: CallRequest) -> ProviderAck:
        raise ProviderNotConfigured("JEEN Talk is not configured")

    def cancel_call(self, provider_call_id: str) -> CancelResult:
        raise ProviderNotConfigured("JEEN Talk is not configured")

    def get_call(self, provider_call_id: str) -> CallState:
        raise ProviderNotConfigured("JEEN Talk is not configured")

    def send_message(self, req: MessageRequest) -> ProviderAck:
        raise ProviderNotConfigured("JEEN Talk is not configured")
