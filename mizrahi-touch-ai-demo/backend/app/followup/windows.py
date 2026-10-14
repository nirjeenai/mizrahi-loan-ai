"""Call windows and holidays, evaluated in the window's time zone (Asia/Jerusalem). Pure functions over aware datetimes:
no clock reads and no database, so the evaluator and `clock.py` share them.

The bank's envelope always applies on top of the configured window: hours are clipped to its bounds and its
no-contact days (Saturday) are removed, whatever the configuration says. DST is handled by `zoneinfo`."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from .contract import ENVELOPE

TZ = "Asia/Jerusalem"
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")      # datetime.weekday() order
HORIZON_DAYS = 60


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required")
    return dt


def _hm(text: str) -> time:
    h, m = text.split(":")
    return time(int(h), int(m))


def _window(call_window: Any, envelope: dict) -> tuple[ZoneInfo, set[str], time, time]:
    """(zone, allowed days, from, to) after the envelope. Accepts the schema's CallWindow or its JSON dict."""
    if isinstance(call_window, dict):
        tz, days, start, end = call_window.get("timezone", TZ), call_window["days"], call_window["from"], call_window["to"]
    else:
        tz, days, start, end = call_window.timezone, call_window.days, call_window.from_, call_window.to
    lo, hi = envelope["call_window_bounds"]
    return (ZoneInfo(tz), {d for d in days if d not in envelope["no_contact_days"]},
            _hm(max(start, lo)), _hm(min(end, hi)))


def closed_reason(dt: datetime, call_window: Any, holidays: Iterable[str] = (),
                  envelope: dict = ENVELOPE) -> Optional[str]:
    """None inside the window, otherwise "holiday" or "window" (hours, weekday or Shabbat)."""
    zone, days, start, end = _window(call_window, envelope)
    local = _aware(dt).astimezone(zone)
    if local.date().isoformat() in set(holidays):
        return "holiday"
    if DAYS[local.weekday()] not in days or not (start <= local.time() < end):
        return "window"
    return None


def in_window(dt: datetime, call_window: Any, holidays: Iterable[str] = (), envelope: dict = ENVELOPE) -> bool:
    return closed_reason(dt, call_window, holidays, envelope) is None


def next_window_start(dt: datetime, call_window: Any, holidays: Iterable[str] = (),
                      envelope: dict = ENVELOPE) -> Optional[datetime]:
    """`dt` itself (in UTC) when it is inside the window, else the next opening; None if nothing opens within
    HORIZON_DAYS (a window with no allowed day)."""
    if in_window(dt, call_window, holidays, envelope):
        return dt.astimezone(timezone.utc)
    zone, days, start, end = _window(call_window, envelope)
    if start >= end:
        return None
    blocked, local = set(holidays), dt.astimezone(zone)
    for i in range(HORIZON_DAYS + 1):
        day = local.date() + timedelta(days=i)
        if day.isoformat() in blocked or DAYS[day.weekday()] not in days:
            continue
        opening = datetime.combine(day, start, tzinfo=zone)
        if opening >= local:
            return opening.astimezone(timezone.utc)
    return None


def local_date(dt: datetime, tz: str = TZ) -> date:
    return _aware(dt).astimezone(ZoneInfo(tz)).date()


def next_local_midnight(dt: datetime, tz: str = TZ) -> datetime:
    zone = ZoneInfo(tz)
    return datetime.combine(local_date(dt, tz) + timedelta(days=1), time(0), tzinfo=zone).astimezone(timezone.utc)


def format_local(dt: datetime, tz: str = TZ) -> str:
    """"13.10 14:30" in Israel time, for Hebrew explanations."""
    return _aware(dt).astimezone(ZoneInfo(tz)).strftime("%d.%m %H:%M")
