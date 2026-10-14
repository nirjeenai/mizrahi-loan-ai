"""Versioned configuration: drafts, one published version per (kind, scope), immutable history.

Publishing is atomic (the previous version is archived in the same transaction) and a rollback publishes a NEW
version that copies an old configuration, so the history always shows what was active when. Edits carry the
revision they were based on; a stale revision is a conflict, never a silent overwrite."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from .. import db
from ..config import BACKEND_DIR
from ..util import new_id, now_iso, stable_hash
from . import schema

SCOPE = "demo:personal_loan.all_purpose"
SEED_DIR = BACKEND_DIR / "policy" / "seed"
SEED_FILES = {"loan_policy": "loan_policy.demo.json", "talk_prompt": "talk_prompt.demo.json"}


class Conflict(Exception):
    pass


class NotDraft(Exception):
    pass


class InvalidConfig(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("invalid configuration")
        self.errors = errors


def _row(r: Optional[dict]) -> Optional[dict]:
    if r:
        r["config"] = db.jload(r["config"])
        r["validation"] = db.jload(r.get("validation"))
        r["label"] = f"{r['kind']}@v{r['number']}"
    return r


def seed_config(kind: str) -> dict:
    return json.loads((SEED_DIR / SEED_FILES[kind]).read_text(encoding="utf8"))


def ensure_seeded() -> None:
    for kind in SEED_FILES:
        if db.one("SELECT 1 FROM config_versions WHERE kind=? AND scope=?", (kind, SCOPE)):
            continue
        config = schema.parse(kind, seed_config(kind)).model_dump(by_alias=True)
        now = now_iso()
        with db.tx() as c:
            if c.execute("SELECT 1 FROM config_versions WHERE kind=? AND scope=?", (kind, SCOPE)).fetchone():
                continue
            c.execute("INSERT INTO config_versions(version_id, kind, scope, number, status, config, schema_version, hash,"
                      " revision, author, created_at, updated_at, published_at, published_by, change_reason, last_editor)"
                      " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (new_id("CFG"), kind, SCOPE, 1, "PUBLISHED", db.jdump(config), config.get("schema_version"),
                       stable_hash(db.jdump(config)), 1, "system:seed", now, now, now, "system:seed",
                       "גרסת פתיחה מתוך קובץ הזרע (נתוני הדגמה)", "system:seed"))


def published(kind: str) -> dict:
    row = _row(db.one("SELECT * FROM config_versions WHERE kind=? AND scope=? AND status='PUBLISHED'", (kind, SCOPE)))
    if row is None:
        ensure_seeded()
        row = _row(db.one("SELECT * FROM config_versions WHERE kind=? AND scope=? AND status='PUBLISHED'", (kind, SCOPE)))
    return row


def get(version_id: str) -> Optional[dict]:
    return _row(db.one("SELECT * FROM config_versions WHERE version_id=?", (version_id,)))


def versions(kind: str) -> list[dict]:
    return [_row(r) for r in db.query("SELECT * FROM config_versions WHERE kind=? AND scope=? ORDER BY number DESC",
                                      (kind, SCOPE))]


def parsed(kind: str, version_id: Optional[str] = None) -> tuple[Any, dict]:
    """(validated model, row). Raises InvalidConfig when the stored configuration no longer validates."""
    row = get(version_id) if version_id else published(kind)
    if row is None:
        raise KeyError(version_id)
    try:
        return schema.parse(kind, row["config"]), row
    except ValidationError as exc:
        raise InvalidConfig(_errors(exc)) from None


def policy(version_id: Optional[str] = None) -> tuple[schema.LoanPolicy, dict]:
    return parsed("loan_policy", version_id)


def _errors(exc: ValidationError) -> list[dict]:
    return [{"path": ".".join(str(p) for p in e["loc"]), "message": e["msg"].removeprefix("Value error, ")}
            for e in exc.errors()]


def validate(kind: str, config: dict) -> list[dict]:
    try:
        schema.parse(kind, config)
        return []
    except ValidationError as exc:
        return _errors(exc)


def _next_number(c, kind: str) -> int:
    return (c.execute("SELECT MAX(number) FROM config_versions WHERE kind=? AND scope=?", (kind, SCOPE)).fetchone()[0] or 0) + 1


def create_draft(kind: str, actor: str, based_on: Optional[str] = None, config: Optional[dict] = None,
                 reason: str = "") -> dict:
    base = get(based_on) if based_on else published(kind)
    body = config if config is not None else base["config"]
    now = now_iso()
    vid = new_id("CFG")
    with db.tx() as c:
        c.execute("INSERT INTO config_versions(version_id, kind, scope, number, status, config, schema_version, hash, revision,"
                  " author, created_at, updated_at, based_on, change_reason, validation, last_editor)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (vid, kind, SCOPE, _next_number(c, kind), "DRAFT", db.jdump(body), body.get("schema_version"),
                   stable_hash(db.jdump(body)), 1, actor, now, now, base["version_id"], reason,
                   db.jdump(validate(kind, body)), actor))
    return get(vid)


def update_draft(version_id: str, config: dict, revision: int, actor: str, reason: str = "") -> dict:
    row = get(version_id)
    if row is None:
        raise KeyError(version_id)
    if row["status"] != "DRAFT":
        raise NotDraft(version_id)
    with db.tx() as c:
        cur = c.execute("UPDATE config_versions SET config=?, hash=?, revision=revision+1, updated_at=?, validation=?,"
                        " change_reason=COALESCE(NULLIF(?, ''), change_reason), last_editor=?"
                        " WHERE version_id=? AND revision=? AND status='DRAFT'",
                        (db.jdump(config), stable_hash(db.jdump(config)), now_iso(), db.jdump(validate(row["kind"], config)),
                         reason, actor, version_id, revision))
        if cur.rowcount != 1:
            raise Conflict(version_id)
    return get(version_id)


def discard_draft(version_id: str, revision: int) -> None:
    with db.tx() as c:
        cur = c.execute("UPDATE config_versions SET status='DISCARDED', updated_at=? WHERE version_id=? AND revision=?"
                        " AND status='DRAFT'", (now_iso(), version_id, revision))
        if cur.rowcount != 1:
            raise Conflict(version_id)


def publish(version_id: str, revision: int, actor: str) -> dict:
    row = get(version_id)
    if row is None:
        raise KeyError(version_id)
    if row["status"] != "DRAFT":
        raise NotDraft(version_id)
    errors = validate(row["kind"], row["config"])
    if errors:
        raise InvalidConfig(errors)
    now = now_iso()
    with db.tx() as c:
        cur = c.execute("UPDATE config_versions SET status='PUBLISHED', published_at=?, published_by=?, updated_at=?"
                        " WHERE version_id=? AND revision=? AND status='DRAFT'", (now, actor, now, version_id, revision))
        if cur.rowcount != 1:
            raise Conflict(version_id)
        c.execute("UPDATE config_versions SET status='ARCHIVED', updated_at=? WHERE kind=? AND scope=? AND status='PUBLISHED'"
                  " AND version_id<>?", (now, row["kind"], SCOPE, version_id))
    return get(version_id)


def rollback(kind: str, to_version_id: str, actor: str, reason: str) -> dict:
    target = get(to_version_id)
    if target is None or target["kind"] != kind or target["status"] not in ("ARCHIVED", "PUBLISHED"):
        raise KeyError(to_version_id)
    draft = create_draft(kind, actor, based_on=to_version_id, config=target["config"],
                         reason=f"שחזור לגרסה v{target['number']}: {reason}")
    return publish(draft["version_id"], draft["revision"], actor)


def diff(before: Any, after: Any, path: str = "") -> list[dict]:
    """A flat list of changed leaves: {path, before, after}."""
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for k in sorted(set(before) | set(after), key=str):
            out += diff(before.get(k), after.get(k), f"{path}.{k}" if path else str(k))
        return out
    if isinstance(before, list) and isinstance(after, list) and all(isinstance(x, dict) and "id" in x for x in before + after):
        b, a = {x["id"]: x for x in before}, {x["id"]: x for x in after}
        out = []
        for k in list(b) + [k for k in a if k not in b]:
            out += diff(b.get(k), a.get(k), f"{path}[{k}]")
        return out
    return [] if before == after else [{"path": path, "before": before, "after": after}]
