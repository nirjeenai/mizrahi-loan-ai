"""Customer presence (CONTRACTS §8, 03 §5 S02, S16, S17): per-session rows, seq ordering, the TTL, aggregation across
tabs and devices (ACTIVE > IDLE > UNKNOWN > ENDED), picker and upload flags, and review-in-flight from the server."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import db
from app.followup import presence
from app.util import new_id, now_iso
from tests.test_followup_flow import JOURNEY, clean  # noqa: F401  (fixture)

T0 = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)


def snap(at: datetime, reqs=("PAYSLIPS:BRW-A",)) -> dict:
    return presence.snapshot(JOURNEY, at, 90, reqs)


def test_nobody_then_active_on_the_task_screen():
    assert snap(T0)["presence"] == "NONE"
    presence.record(JOURNEY, "tab-1", "session_started", 1, True, "document", "PAYSLIPS:BRW-A", T0)
    s = snap(T0 + timedelta(seconds=5))
    assert (s["presence"], s["on_task_screen"], s["live_sessions"]) == ("ACTIVE", True, 1)
    assert not snap(T0, reqs=("PURPOSE_PROOF",))["on_task_screen"]          # another requirement's screen


def test_a_lower_or_repeated_seq_is_ignored():
    assert presence.record(JOURNEY, "tab-1", "session_started", 5, True, now=T0)
    assert not presence.record(JOURNEY, "tab-1", "session_ended", 4, True, now=T0 + timedelta(seconds=1))
    assert not presence.record(JOURNEY, "tab-1", "session_ended", 5, True, now=T0 + timedelta(seconds=1))
    assert snap(T0 + timedelta(seconds=2))["presence"] == "ACTIVE"
    assert presence.record(JOURNEY, "tab-1", "session_ended", 6, True, now=T0 + timedelta(seconds=3))
    assert snap(T0 + timedelta(seconds=4))["presence"] == "ENDED"
    assert not presence.record(JOURNEY, "tab-1", "heartbeat", 7, True, now=T0 + timedelta(seconds=5))   # stays ended
    assert presence.record(JOURNEY, "tab-1", "session_resumed", 8, True, now=T0 + timedelta(seconds=6))
    assert snap(T0 + timedelta(seconds=7))["presence"] == "ACTIVE"


def test_idle_hidden_and_expired_sessions():
    presence.record(JOURNEY, "tab-1", "session_started", 1, True, now=T0)
    presence.record(JOURNEY, "tab-1", "heartbeat", 2, True, now=T0 + timedelta(seconds=70))
    assert snap(T0 + timedelta(seconds=75))["presence"] == "IDLE"           # no activity for a minute
    presence.record(JOURNEY, "tab-1", "user_activity", 3, False, now=T0 + timedelta(seconds=80))
    assert snap(T0 + timedelta(seconds=81))["presence"] == "IDLE"           # a hidden tab
    assert snap(T0 + timedelta(seconds=80 + 91))["presence"] == "UNKNOWN"   # S16: heartbeat expired, no session_ended


def test_any_active_device_wins():
    presence.record(JOURNEY, "phone", "session_started", 1, True, now=T0)
    presence.record(JOURNEY, "phone", "session_ended", 2, True, now=T0 + timedelta(seconds=10))
    presence.record(JOURNEY, "laptop", "session_started", 1, True, now=T0 + timedelta(seconds=20))
    s = snap(T0 + timedelta(seconds=25))
    assert s["presence"] == "ACTIVE" and s["live_sessions"] == 1           # S17
    presence.record(JOURNEY, "tablet", "session_started", 1, True, now=T0 + timedelta(seconds=26))
    assert snap(T0 + timedelta(seconds=27))["live_sessions"] == 2
    assert presence.end_all(JOURNEY, T0 + timedelta(seconds=30)) == 2
    assert snap(T0 + timedelta(seconds=31))["presence"] == "ENDED"


def test_picker_and_upload_flags():
    presence.record(JOURNEY, "tab-1", "session_started", 1, True, now=T0)
    presence.record(JOURNEY, "tab-1", "file_picker_opened", 2, True, now=T0 + timedelta(seconds=5))
    assert snap(T0 + timedelta(seconds=10))["upload_in_flight"]             # S02
    assert not snap(T0 + timedelta(minutes=4))["upload_in_flight"]          # an abandoned picker stops counting
    presence.record(JOURNEY, "tab-1", "upload_started", 3, True, now=T0 + timedelta(minutes=4))
    assert snap(T0 + timedelta(minutes=5))["upload_in_flight"]
    presence.record(JOURNEY, "tab-1", "upload_completed", 4, True, now=T0 + timedelta(minutes=5))
    assert not snap(T0 + timedelta(minutes=5, seconds=1))["upload_in_flight"]


def test_review_in_flight_comes_from_the_server():
    assert not presence.evaluation_in_flight(JOURNEY)
    with db.tx() as c:
        c.execute("INSERT INTO jobs(job_id, kind, case_id, status, created_at, updated_at, not_before) VALUES (?,?,?,?,?,?,?)",
                  (new_id("JOB"), "review_document", JOURNEY, "queued", now_iso(), now_iso(), now_iso()))
    assert presence.evaluation_in_flight(JOURNEY) and snap(T0)["evaluation_in_flight"]
