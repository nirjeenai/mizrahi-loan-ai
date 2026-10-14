"""The follow-up clock (CONTRACTS §8): the demo offset (demo environment only, audited) and the Asia/Jerusalem call
window with Shabbat, configured holidays, the bank's envelope and the 2026-10-25 DST change."""
from datetime import datetime, timedelta, timezone

import pytest

from app import clock, db, events, flags
from app.followup import windows

UTC = timezone.utc
WINDOW = {"timezone": "Asia/Jerusalem", "days": ["SUN", "MON", "TUE", "WED", "THU"], "from": "09:00", "to": "18:00"}


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    yield
    flags.put(flags.DEMO_CLOCK_OFFSET, 0, "test")


def il(y, mo, d, h, mi=0):
    """An Israel wall-clock time as aware UTC."""
    from zoneinfo import ZoneInfo
    return datetime(y, mo, d, h, mi, tzinfo=ZoneInfo("Asia/Jerusalem")).astimezone(UTC)


def test_offset_is_applied_and_audited():
    wall = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
    assert clock.now(wall) == wall and clock.now().tzinfo is not None
    state = clock.advance(90, "demo:test", "קדימה")
    assert state["offset_seconds"] == 5400 and state["simulated"]
    assert clock.now(wall) == wall + timedelta(minutes=90)
    assert events.recent(None, ("demo.clock_changed.v1",))[0]["payload"]["after"] == 5400
    target = clock.now() + timedelta(hours=2)
    clock.set_to(target, "demo:test")
    assert abs((clock.now() - target).total_seconds()) < 5
    clock.set_to(clock.now() - timedelta(hours=5), "demo:test")          # never backwards
    assert clock.offset_seconds() >= 5400 + 7200 - 5
    assert clock.to_wall(clock.now(wall)) == wall
    assert clock.reset("demo:test")["offset_seconds"] == 0
    assert datetime.fromisoformat(clock.now_iso()).tzinfo is not None


def test_offset_is_ignored_outside_demo(monkeypatch):
    flags.put(flags.DEMO_CLOCK_OFFSET, 3600, "test")
    wall = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
    assert clock.now(wall) == wall + timedelta(hours=1)
    monkeypatch.setenv("APP_ENV", "prod")
    assert clock.environment() == "prod" and clock.now(wall) == wall
    with pytest.raises(PermissionError):
        clock.advance(10, "test")


def test_call_window_hours_and_days():
    assert clock.in_window(il(2026, 10, 13, 11), WINDOW)                  # Tuesday 11:00
    assert not clock.in_window(il(2026, 10, 13, 8, 59), WINDOW)
    assert clock.in_window(il(2026, 10, 13, 17, 59), WINDOW)
    assert not clock.in_window(il(2026, 10, 13, 18, 0), WINDOW)           # the end is exclusive
    assert not clock.in_window(il(2026, 10, 16, 11), WINDOW)              # Friday is not configured
    assert clock.closed_reason(il(2026, 10, 17, 11), WINDOW) == "window"  # Shabbat
    assert clock.next_window_start(il(2026, 10, 13, 11), WINDOW) == il(2026, 10, 13, 11)
    assert clock.next_window_start(il(2026, 10, 13, 7), WINDOW) == il(2026, 10, 13, 9)
    assert clock.next_window_start(il(2026, 10, 15, 19), WINDOW) == il(2026, 10, 18, 9)   # Thu night → Sunday


def test_holidays():
    holidays = ["2026-10-14"]
    assert clock.closed_reason(il(2026, 10, 14, 11), WINDOW, holidays) == "holiday"
    assert clock.next_window_start(il(2026, 10, 13, 19), WINDOW, holidays) == il(2026, 10, 15, 9)


def test_envelope_clips_a_wider_window_and_removes_shabbat():
    wide = {**WINDOW, "days": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"], "from": "06:00", "to": "23:00"}
    assert not clock.in_window(il(2026, 10, 13, 7, 30), wide)
    assert clock.in_window(il(2026, 10, 13, 19, 59), wide)
    assert not clock.in_window(il(2026, 10, 13, 20, 0), wide)
    assert not clock.in_window(il(2026, 10, 17, 12), wide)
    assert clock.next_window_start(il(2026, 10, 17, 12), wide) == il(2026, 10, 18, 8)


def test_dst_change_on_2026_10_25():
    before, after = clock.next_window_start(il(2026, 10, 21, 19), WINDOW), clock.next_window_start(il(2026, 10, 23, 19), WINDOW)
    assert before == datetime(2026, 10, 22, 6, 0, tzinfo=UTC)             # 09:00 IDT (UTC+3)
    assert after == datetime(2026, 10, 25, 7, 0, tzinfo=UTC)              # 09:00 IST (UTC+2), the first day of winter time
    assert windows.format_local(after) == "25.10 09:00"
    assert clock.in_window(datetime(2026, 10, 25, 15, 30, tzinfo=UTC), WINDOW)       # 17:30 IST
    assert not clock.in_window(datetime(2026, 10, 25, 16, 0, tzinfo=UTC), WINDOW)    # 18:00 IST


def test_local_days_and_naive_input():
    assert windows.local_date(datetime(2026, 10, 13, 22, 30, tzinfo=UTC)).isoformat() == "2026-10-14"   # 01:30 IL
    assert windows.next_local_midnight(il(2026, 10, 13, 11)) == il(2026, 10, 14, 0)
    with pytest.raises(ValueError):
        clock.in_window(datetime(2026, 10, 13, 11), WINDOW)
