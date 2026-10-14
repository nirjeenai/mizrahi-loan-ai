"""Process-wide switches in `system_flags`. A closed set of keys, each with a fixed type and default; every change is
an event, so the kill switch and the demo clock always show who moved them and when."""
from __future__ import annotations

from typing import Any

from . import db, events
from .util import now_iso

KILL_SWITCH = "followup.kill_switch"              # bool: True stops every automatic customer contact
DEMO_CLOCK_OFFSET = "demo.clock_offset_seconds"   # int: added to the wall clock by clock.now(), demo environment only

DEFAULTS: dict[str, Any] = {KILL_SWITCH: False, DEMO_CLOCK_OFFSET: 0}
_EVENT = {KILL_SWITCH: "settings.kill_switch_changed.v1", DEMO_CLOCK_OFFSET: "demo.clock_changed.v1"}


def get(key: str) -> Any:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = db.one("SELECT value FROM system_flags WHERE key=?", (key,))
    return DEFAULTS[key] if row is None else db.jload(row["value"], DEFAULTS[key])


def row(key: str) -> dict:
    """The value with who set it and when (None for both while the default applies)."""
    if key not in DEFAULTS:
        raise KeyError(key)
    r = db.one("SELECT * FROM system_flags WHERE key=?", (key,))
    return {"key": key, "value": get(key), "updated_at": (r or {}).get("updated_at"), "updated_by": (r or {}).get("updated_by")}


def put(key: str, value: Any, actor: str, reason: str = "") -> dict:
    if key not in DEFAULTS:
        raise KeyError(key)
    if type(value) is not type(DEFAULTS[key]):
        raise TypeError(f"{key} takes {type(DEFAULTS[key]).__name__}")
    with db.tx() as c:
        prev = c.execute("SELECT value FROM system_flags WHERE key=?", (key,)).fetchone()
        before = db.jload(prev["value"], DEFAULTS[key]) if prev else DEFAULTS[key]
        c.execute("INSERT INTO system_flags(key, value, updated_at, updated_by) VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE"
                  " SET value=excluded.value, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                  (key, db.jdump(value), now_iso(), actor))
        events.emit(_EVENT[key], None, actor, {"key": key, "before": before, "after": value, "reason": reason}, conn=c)
    return row(key)
