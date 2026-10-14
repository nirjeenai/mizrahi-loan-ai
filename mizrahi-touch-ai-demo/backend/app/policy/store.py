"""Versioned configuration: drafts, one published version per (kind, scope), immutable history.

Publishing is atomic (the previous version is archived in the same transaction) and a rollback publishes a NEW
version that copies an old configuration, so the history always shows what was active when. Edits carry the
revision they were based on; a stale revision is a conflict, never a silent overwrite."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from .. import db, events
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


UPGRADE_REASON = "הרחבת מדיניות המסמכים מקובץ הזרע: פרופילי מסמכים (עצמאים, לווים משותפים, חברה)"


def upgrade_from_seed() -> Optional[dict]:
    """Publish a new loan-policy version when the published one lacks requirements or purposes the seed defines.

    Additive only: requirements and purposes that no version ever had are appended (one the Admin removed stays removed),
    an existing requirement gains only the seed's entity condition and its reason/alternative texts when it has none.
    Nothing the Admin set is overwritten, and cases pinned to the previous version keep it. Returns the new version, or
    None when nothing was missing."""
    current = published("loan_policy")
    seed = schema.parse("loan_policy", seed_config("loan_policy")).model_dump(by_alias=True)
    config = json.loads(json.dumps(current["config"]))
    history = versions("loan_policy")
    ever_ids = {r["id"] for v in history for r in v["config"].get("document_requirements", [])}
    ever_purposes = {k for v in history for k in (v["config"].get("product") or {}).get("purposes", {})}
    have = {r["id"]: r for r in config["document_requirements"]}
    changed = False
    for s in seed["document_requirements"]:
        r = have.get(s["id"])
        if r is None:
            if s["id"] not in ever_ids:
                config["document_requirements"].append(s)
                changed = True
            continue
        entity = (s.get("condition") or {}).get("entity")
        if entity and not (r.get("condition") or {}).get("entity"):
            r["condition"] = {**(r.get("condition") or {}), "entity": entity}
            changed = True
        for key in ("why_he", "alternatives_he"):
            if s.get(key) and not r.get(key):
                r[key] = s[key]
                changed = True
    for key, purpose in seed["product"]["purposes"].items():
        if key not in config["product"]["purposes"] and key not in ever_purposes:
            config["product"]["purposes"][key] = purpose
            changed = True
    if not changed or validate("loan_policy", config):
        return None
    draft = create_draft("loan_policy", "system:seed", config=config, reason=UPGRADE_REASON)
    return publish(draft["version_id"], draft["revision"], "system:seed")


def published(kind: str) -> dict:
    row = _row(db.one("SELECT * FROM config_versions WHERE kind=? AND scope=? AND status='PUBLISHED'", (kind, SCOPE)))
    if row is None:
        ensure_seeded()
        row = _row(db.one("SELECT * FROM config_versions WHERE kind=? AND scope=? AND status='PUBLISHED'", (kind, SCOPE)))
    return row


def get(version_id: str) -> Optional[dict]:
    return _row(db.one("SELECT * FROM config_versions WHERE version_id=?", (version_id,)))


def open_draft(kind: str) -> Optional[dict]:
    """The newest open draft of a kind (the Admin works on one draft per kind)."""
    return _row(db.one("SELECT * FROM config_versions WHERE kind=? AND scope=? AND status='DRAFT' ORDER BY number DESC"
                       " LIMIT 1", (kind, SCOPE)))


def _emit(c, event_type: str, kind: str, version_id: str, number: int, actor: str, **payload: Any) -> None:
    """A settings event inside the caller's transaction. Payloads name versions and changed paths, never values."""
    events.emit(event_type, None, actor, {"kind": kind, "version_id": version_id, "label": f"{kind}@v{number}", **payload},
                conn=c)


def _paths(before: Any, after: Any) -> list[str]:
    return [d["path"] for d in diff(before, after)][:40]


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
        number = _next_number(c, kind)
        c.execute("INSERT INTO config_versions(version_id, kind, scope, number, status, config, schema_version, hash, revision,"
                  " author, created_at, updated_at, based_on, change_reason, validation, last_editor)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (vid, kind, SCOPE, number, "DRAFT", db.jdump(body), body.get("schema_version"),
                   stable_hash(db.jdump(body)), 1, actor, now, now, base["version_id"], reason,
                   db.jdump(validate(kind, body)), actor))
        _emit(c, "settings.draft_saved.v1", kind, vid, number, actor, action="created", revision=1,
              based_on=base["version_id"], paths=_paths(base["config"], body), reason=reason)
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
        _emit(c, "settings.draft_saved.v1", row["kind"], version_id, row["number"], actor, action="updated",
              revision=revision + 1, paths=_paths(row["config"], config), reason=reason)
    return get(version_id)


def discard_draft(version_id: str, revision: int, *, actor: str = "system") -> None:
    with db.tx() as c:
        cur = c.execute("UPDATE config_versions SET status='DISCARDED', updated_at=? WHERE version_id=? AND revision=?"
                        " AND status='DRAFT'", (now_iso(), version_id, revision))
        if cur.rowcount != 1:
            raise Conflict(version_id)
        r = c.execute("SELECT kind, number FROM config_versions WHERE version_id=?", (version_id,)).fetchone()
        _emit(c, "settings.draft_discarded.v1", r["kind"], version_id, r["number"], actor)


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
        prev = c.execute("SELECT version_id, number, config FROM config_versions WHERE kind=? AND scope=? AND status='PUBLISHED'",
                         (row["kind"], SCOPE)).fetchone()
        cur = c.execute("UPDATE config_versions SET status='PUBLISHED', published_at=?, published_by=?, updated_at=?"
                        " WHERE version_id=? AND revision=? AND status='DRAFT'", (now, actor, now, version_id, revision))
        if cur.rowcount != 1:
            raise Conflict(version_id)
        c.execute("UPDATE config_versions SET status='ARCHIVED', updated_at=? WHERE kind=? AND scope=? AND status='PUBLISHED'"
                  " AND version_id<>?", (now, row["kind"], SCOPE, version_id))
        _emit(c, "settings.prompt_published.v1" if row["kind"] == "talk_prompt" else "settings.policy_published.v1",
              row["kind"], version_id, row["number"], actor, previous_version_id=prev["version_id"] if prev else None,
              previous_label=f"{row['kind']}@v{prev['number']}" if prev else None,
              paths=_paths(db.jload(prev["config"]) if prev else {}, row["config"]), reason=row.get("change_reason") or "")
    return get(version_id)


def rollback(kind: str, to_version_id: str, actor: str, reason: str) -> dict:
    """Publish a NEW version that copies an earlier configuration, in one transaction."""
    target = get(to_version_id)
    if target is None or target["kind"] != kind or target["status"] not in ("ARCHIVED", "PUBLISHED"):
        raise KeyError(to_version_id)
    errors = validate(kind, target["config"])
    if errors:
        raise InvalidConfig(errors)
    body, now, vid = target["config"], now_iso(), new_id("CFG")
    with db.tx() as c:
        prev = c.execute("SELECT version_id, number FROM config_versions WHERE kind=? AND scope=? AND status='PUBLISHED'",
                         (kind, SCOPE)).fetchone()
        number = _next_number(c, kind)
        c.execute("UPDATE config_versions SET status='ARCHIVED', updated_at=? WHERE kind=? AND scope=? AND status='PUBLISHED'",
                  (now, kind, SCOPE))
        c.execute("INSERT INTO config_versions(version_id, kind, scope, number, status, config, schema_version, hash, revision,"
                  " author, created_at, updated_at, published_at, published_by, based_on, change_reason, validation, last_editor)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (vid, kind, SCOPE, number, "PUBLISHED", db.jdump(body), body.get("schema_version"),
                   stable_hash(db.jdump(body)), 1, actor, now, now, now, actor, to_version_id,
                   f"שחזור לגרסה v{target['number']}: {reason}", db.jdump([]), actor))
        _emit(c, "settings.rollback_applied.v1", kind, vid, number, actor, restored_version_id=to_version_id,
              restored_label=target["label"], previous_version_id=prev["version_id"] if prev else None,
              previous_label=f"{kind}@v{prev['number']}" if prev else None, reason=reason)
    return get(vid)


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
