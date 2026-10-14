"""Which outbound provider the published policy selects: `talk.mode` simulation → the mock, off → none, live → the
JEEN Talk slot (a not-configured stub today)."""
from __future__ import annotations

from typing import Optional

from ..policy.schema import LoanPolicy
from .contract import OutboundProvider
from .jeen_talk import JeenTalkProvider
from .mock_talk import MockTalkProvider

_MOCK, _LIVE = MockTalkProvider(), JeenTalkProvider()


def active(policy: Optional[LoanPolicy]) -> Optional[OutboundProvider]:
    mode = policy.talk.mode if policy else "off"
    return {"simulation": _MOCK, "live": _LIVE}.get(mode)


def by_name(name: str) -> Optional[OutboundProvider]:
    return {_MOCK.name: _MOCK, _LIVE.name: _LIVE}.get(name)
