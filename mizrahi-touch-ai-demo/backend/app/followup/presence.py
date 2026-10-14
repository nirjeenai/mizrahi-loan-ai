"""Customer presence: one row per browser tab or device (`customer_presence`), aggregated across all of them.

The client reports only UI facts (CONTRACTS §8); whether a document is being reviewed comes from `jobs` and `documents`
on the server. A lower or repeated `seq` for a session is ignored, so a late or replayed heartbeat never revives a
session. Aggregate: ACTIVE beats IDLE beats UNKNOWN beats ENDED; NONE when the customer never opened the app.
- ACTIVE: a fresh heartbeat, a visible tab and activity within IDLE_AFTER.
- IDLE: a fresh heartbeat but no recent activity (or a hidden tab).
- UNKNOWN: the heartbeat expired (presence TTL) without a session_ended: network loss, a closed laptop (S16).
- ENDED: the client said session_ended."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from .. import clock, db

EVENTS = ("session_started", "heartbeat", "user_activity", "file_picker_opened", "upload_started", "upload_completed",
          "session_resumed", "session_ended")
SCREENS = ("home", "documents", "document", "other")
ACTIVITY = {"session_started", "user_activity", "file_picker_opened", "upload_started", "upload_completed",
            "session_resumed"}
TASK_SCREENS = ("documents", "document")
IDLE_AFTER = timedelta(seconds=60)
PICKER_HOLD = timedelta(minutes=3)            # a file picker counts as an upload in flight this long
UPLOAD_HOLD = timedelta(minutes=10)           # an upload request in flight, until upload_completed
FORGET_AFTER = timedelta(hours=24)            # older session rows no longer count
RANK = {"ACTIVE": 3, "IDLE": 2, "UNKNOWN": 1, "ENDED": 0}


def _t(v: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(v) if v else None


def record(case_id: str, session_id: str, event: str, seq: int, visible: bool, screen: Optional[str] = None,
           requirement_code: Optional[str] = None, now: Optional[datetime] = None) -> bool:
    """Store one client event. False when it was ignored (an old or repeated seq)."""
    if event not in EVENTS:
        raise ValueError(event)
    now = now or clock.now()
    at = now.isoformat(timespec="seconds")
    with db.tx() as c:
        row = c.execute("SELECT * FROM customer_presence WHERE case_id=? AND session_id=?", (case_id, session_id)).fetchone()
        r = dict(row) if row else {"state": "ACTIVE", "started_at": at, "seq": -1, "last_activity_at": None,
                                   "last_upload_action_at": None, "picker_open_until": None, "ended_at": None,
                                   "screen": None}
        if seq <= r["seq"]:
            return False
        if r["state"] == "ENDED" and event not in ("session_started", "session_resumed"):
            return False
        r.update(seq=seq, visible=1 if visible else 0, last_seen_at=at)
        if screen:
            r["screen"] = f"{screen}:{requirement_code or ''}"
        if event in ACTIVITY:
            r["last_activity_at"] = at
        if event in ("session_started", "session_resumed"):
            r.update(state="ACTIVE", ended_at=None)
        if event == "file_picker_opened":
            r["picker_open_until"] = (now + PICKER_HOLD).isoformat(timespec="seconds")
        if event == "upload_started":
            r.update(last_upload_action_at=at, picker_open_until=(now + UPLOAD_HOLD).isoformat(timespec="seconds"))
        if event == "upload_completed":
            r.update(last_upload_action_at=at, picker_open_until=None)
        if event == "session_ended":
            r.update(state="ENDED", ended_at=at, picker_open_until=None)
        c.execute("INSERT OR REPLACE INTO customer_presence(case_id, session_id, state, last_seen_at, last_activity_at,"
                  " last_upload_action_at, picker_open_until, ended_at, seq, visible, started_at, screen)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (case_id, session_id, r["state"], r["last_seen_at"], r["last_activity_at"], r["last_upload_action_at"],
                   r["picker_open_until"], r["ended_at"], r["seq"], r["visible"], r["started_at"], r["screen"]))
    return True


def end_all(case_id: str, now: Optional[datetime] = None) -> int:
    """Every session of the case ends now (the demo's "customer left" control)."""
    at = (now or clock.now()).isoformat(timespec="seconds")
    with db.tx() as c:
        cur = c.execute("UPDATE customer_presence SET state='ENDED', ended_at=?, last_seen_at=?, picker_open_until=NULL"
                        " WHERE case_id=? AND state<>'ENDED'", (at, at, case_id))
        return cur.rowcount


def session_state(r: dict, now: datetime, ttl: timedelta) -> str:
    if r["state"] == "ENDED":
        return "ENDED"
    seen = _t(r["last_seen_at"])
    if seen is None or now - seen > ttl:
        return "UNKNOWN"
    activity = _t(r["last_activity_at"])
    if not r.get("visible") or activity is None or now - activity > IDLE_AFTER:
        return "IDLE"
    return "ACTIVE"


def evaluation_in_flight(case_id: str) -> bool:
    jobs = db.one("SELECT 1 FROM jobs WHERE case_id=? AND kind IN ('review_document','review_case')"
                  " AND status IN ('queued','running') LIMIT 1", (case_id,))
    docs = db.one("SELECT 1 FROM documents WHERE case_id=? AND status IN ('queued','processing') LIMIT 1", (case_id,))
    return bool(jobs or docs)


def snapshot(case_id: str, now: datetime, ttl_seconds: int, task_requirements: tuple[str, ...] = ()) -> dict[str, Any]:
    """The aggregate the evaluator reads (FollowupContext fields) plus a per-session list for the banker."""
    ttl = timedelta(seconds=ttl_seconds)
    rows = [r for r in db.query("SELECT * FROM customer_presence WHERE case_id=?", (case_id,))
            if (_t(r["last_seen_at"]) or now) > now - FORGET_AFTER]
    sessions = [{**r, "derived": session_state(r, now, ttl)} for r in rows]
    best = max((s["derived"] for s in sessions), key=RANK.__getitem__, default=None)
    live = [s for s in sessions if s["derived"] in ("ACTIVE", "IDLE")]

    def on_task(s: dict) -> bool:
        screen, _, code = (s.get("screen") or "").partition(":")
        return screen in TASK_SCREENS and (not code or code in task_requirements)

    stamps = lambda key: [t for t in (_t(s[key]) for s in sessions) if t]   # noqa: E731
    return {
        "presence": best or "NONE",
        "on_task_screen": any(s["derived"] == "ACTIVE" and on_task(s) for s in sessions),
        "last_activity_at": max(stamps("last_activity_at"), default=None),
        "last_seen_at": max(stamps("last_seen_at"), default=None),
        "upload_in_flight": any((_t(s["picker_open_until"]) or now) > now for s in live),
        "evaluation_in_flight": evaluation_in_flight(case_id),
        "live_sessions": len(live),
        "sessions": [{"session_id": s["session_id"], "state": s["derived"], "screen": (s.get("screen") or "").split(":")[0],
                      "last_seen_at": s["last_seen_at"]} for s in sessions],
    }
