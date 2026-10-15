"""The follow-up clock: aware UTC wall time plus the audited demo offset (`flags.DEMO_CLOCK_OFFSET`).

The offset is honoured only in the demo environment, and only follow-up code reads this clock: review months still
come from `settings.SIMULATION_DATE`, and existing code keeps `util.now_iso()`. Call windows and holidays are
evaluated in Asia/Jerusalem (`followup/windows.py`, re-exported here)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import flags
from .followup.windows import closed_reason, format_local, in_window, local_date, next_window_start  # noqa: F401


def environment() -> str:
    """"demo" unless APP_ENV says otherwise; the follow-up engine's environment, echoed into every FollowupContext."""
    env = os.environ.get("APP_ENV", "demo").lower()
    return env if env in ("demo", "staging", "prod") else "demo"


def offset_seconds() -> int:
    return flags.get(flags.DEMO_CLOCK_OFFSET) if environment() == "demo" else 0


def wall() -> datetime:
    return datetime.now(timezone.utc)


def now(wall_time: Optional[datetime] = None) -> datetime:
    return (wall_time or wall()) + timedelta(seconds=offset_seconds())


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def advance(minutes: int, actor: str, reason: str = "") -> dict:
    """Move the demo clock forward (demo environment only)."""
    if environment() != "demo":
        raise PermissionError("the demo clock exists only in the demo environment")
    flags.put(flags.DEMO_CLOCK_OFFSET, offset_seconds() + int(minutes) * 60, actor, reason or f"+{minutes} דקות")
    return state()


def set_to(target: datetime, actor: str, reason: str = "") -> dict:
    """Jump the demo clock forward to `target` (never backwards: follow-up history must stay ordered)."""
    if environment() != "demo":
        raise PermissionError("the demo clock exists only in the demo environment")
    delta = int((target - now()).total_seconds())
    if delta > 0:
        flags.put(flags.DEMO_CLOCK_OFFSET, offset_seconds() + delta, actor, reason or "קפיצה לחלון הפנייה הבא")
    return state()


def reset(actor: str) -> dict:
    flags.put(flags.DEMO_CLOCK_OFFSET, 0, actor, "איפוס השעון")
    return state()


def state() -> dict:
    return {"now": now_iso(), "offset_seconds": offset_seconds(), "simulated": offset_seconds() != 0}


def to_wall(target: datetime) -> datetime:
    """A clock-time target as wall-clock UTC (what a scheduler comparing with the real clock needs)."""
    return target - timedelta(seconds=offset_seconds())
