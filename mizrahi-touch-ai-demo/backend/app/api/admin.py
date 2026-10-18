"""Admin Settings API (CONTRACTS §7): one demo admin edits, tests and publishes the loan-completion configuration.

Every route needs a staff session (the demo staff session the banker console already uses). A draft never changes
behavior; publishing makes it the version the engine reads, and a rollback publishes a new version. Concurrency is
the store's revision: the client sends the revision it edited, and a stale one is a 409."""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import auth, events, flags, i18n
from ..config import settings
from ..followup.contract import ENVELOPE, LOCKED_RULES, RULES
from ..i18n import en as EN
from ..policy import prompts, schema, simulator, store, validate

router = APIRouter(prefix="/api/admin/loan-completion")

Kind = Literal["loan_policy", "talk_prompt"]
KINDS: tuple[str, ...] = ("loan_policy", "talk_prompt")
ENVIRONMENT_HE = {"demo": "סביבת הדגמה · נתונים סינתטיים", "staging": "סביבת בדיקות", "prod": "סביבת ייצור"}
_ROW_FIELDS = ("version_id", "kind", "number", "label", "status", "revision", "author", "last_editor", "created_at",
               "updated_at", "published_at", "published_by", "based_on", "change_reason", "hash")


class NewDraft(BaseModel):
    kind: Kind
    based_on: Optional[str] = None
    reason: str = Field("", max_length=300)


class SaveDraft(BaseModel):
    config: dict[str, Any]
    revision: int
    reason: str = Field("", max_length=300)


class Revision(BaseModel):
    revision: int


class Check(BaseModel):
    kind: Kind
    config: dict[str, Any]


class Rollback(BaseModel):
    kind: Kind
    to_version_id: str
    reason: str = Field("", max_length=300)


class Simulate(BaseModel):
    version_id: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    scenario_ids: Optional[list[str]] = None


class Pause(BaseModel):
    paused: bool
    reason: str = Field("", max_length=300)


def _admin(request: Request) -> tuple[dict, str]:
    person = auth.require_staff(request)
    return person, f"admin:{person['staff_id']}"


def _project(row: Optional[dict], with_config: bool = True) -> Optional[dict]:
    if row is None:
        return None
    out = {k: row.get(k) for k in _ROW_FIELDS}
    if with_config:
        out["config"] = row["config"]
    return out


def _refusal(request: Request, status: int, detail: dict) -> HTTPException:
    """A structured refusal; when the app sent its language, its message and reasons also carry English siblings."""
    return HTTPException(status, i18n.staff(request, detail))


# the parts of a validation report that are the service's own wording; the configuration, its diff and its rendered
# preview are the admin's editable content and stay exactly as written
_REPORT_TEXT = ("errors", "warnings", "lint", "reasons")


def _en(request: Request, body: dict) -> dict:
    if not i18n.lang(request):
        return body
    return {**body, **i18n.staff(request, {k: body[k] for k in _REPORT_TEXT if k in body})}


def _canonical_en() -> dict:
    """Read-only English renderings of the policy's canonical Hebrew texts, shown beside the editable Hebrew values."""
    return {"requirements": {rid: {"label": label, "hint": hint, "why": why, "alternatives": alts}
                             for rid, (label, hint, why, alts) in EN.REQUIREMENTS.items()},
            "purposes": {pid: {"label": label, "proof": proof} for pid, (label, proof) in EN.PURPOSES.items()}}


def _draft(version_id: str, request: Request) -> dict:
    row = store.get(version_id)
    if row is None or row["kind"] not in KINDS:
        raise HTTPException(404, "הטיוטה לא נמצאה")
    if row["status"] != "DRAFT":
        raise _refusal(request, 409, {"message": "הגרסה הזו כבר אינה טיוטה", "status": row["status"]})
    return row


def _stale(row: dict, request: Request) -> HTTPException:
    current = store.get(row["version_id"]) or row
    return _refusal(request, 409, {"message": "הטיוטה נשמרה בינתיים ממקום אחר. טענו אותה מחדש לפני שמירה.",
                                   "revision": current.get("revision"), "status": current.get("status")})


def _environment() -> str:
    return (store.published("loan_policy")["config"].get("scope") or {}).get("environment", "demo")


def _report(kind: str, config: dict) -> dict:
    published = store.published(kind)
    result = validate.check(kind, config)
    return {**result, "diff": store.diff(published["config"], config), "preview": prompts.preview(kind, config),
            "against": published["label"]}


@router.get("/settings")
def get_settings(request: Request):
    person, _ = _admin(request)
    env = _environment()
    out = {
        "environment": {"name": env, "label_he": ENVIRONMENT_HE.get(env, env), "demo_identity": settings.demo_identity,
                        "synthetic": env == "demo"},
        "published": {k: _project(store.published(k)) for k in KINDS},
        "drafts": {k: _project(store.open_draft(k)) for k in KINDS},
        "kill_switch": flags.row(flags.KILL_SWITCH),
        "locked_rules": [{"id": r, "label_he": RULES[r][1]} for r in LOCKED_RULES],
        "rule_labels": {r: {"tier": tier, "label_he": label} for r, (tier, label) in RULES.items()},
        "envelope": ENVELOPE,
        "locked_fields": {k: [{"path": p, "reason_he": validate.LOCKED_HE[p]} for p in v]
                          for k, v in validate.LOCKED_FIELDS.items()},
        "prompt_variables": list(schema.PROMPT_VARIABLES),
        "preview_variables": prompts.PREVIEW_VARIABLES,
        "requirement_catalog": store.seed_config("loan_policy")["document_requirements"],
        "simulator_available": True,
        "caller": {k: person.get(k) for k in ("staff_id", "name_he", "role_he")},
    }
    if i18n.lang(request):              # never the configurations or the requirement catalog the editor copies from
        out.update(i18n.staff(request, {k: out[k] for k in ("environment", "locked_rules", "rule_labels", "locked_fields",
                                                            "caller")}))
        out["canonical_en"] = _canonical_en()
    return out


@router.post("/drafts")
def open_draft(body: NewDraft, request: Request):
    """The open draft of a kind, or a new one from the published version (or `based_on`)."""
    _, actor = _admin(request)
    existing = store.open_draft(body.kind)
    if existing:
        return _project(existing)
    if body.based_on:
        base = store.get(body.based_on)
        if base is None or base["kind"] != body.kind:
            raise HTTPException(404, "גרסת הבסיס לא נמצאה")
    return _project(store.create_draft(body.kind, actor, based_on=body.based_on, reason=body.reason))


@router.put("/drafts/{version_id}")
def save_draft(version_id: str, body: SaveDraft, request: Request):
    _, actor = _admin(request)
    row = _draft(version_id, request)
    locked = validate.locked_errors(row["kind"], store.published(row["kind"])["config"], body.config)
    if locked:
        raise _refusal(request, 422, {"message": "שדה נעול אינו ניתן לשינוי", "errors": locked})
    try:
        return _project(store.update_draft(version_id, body.config, body.revision, actor, body.reason))
    except store.Conflict:
        raise _stale(row, request) from None
    except store.NotDraft:
        raise _refusal(request, 409, {"message": "הגרסה הזו כבר אינה טיוטה"}) from None


@router.post("/drafts/{version_id}/validate")
def validate_draft(version_id: str, request: Request):
    _admin(request)
    row = store.get(version_id)
    if row is None or row["kind"] not in KINDS:
        raise HTTPException(404, "הגרסה לא נמצאה")
    results = simulator.run(row["config"]) if row["kind"] == "loan_policy" else []     # pure: nothing is stored
    reasons = validate.publish_reasons(row, results) if row["status"] == "DRAFT" else []
    return _en(request, {**_report(row["kind"], row["config"]), "publishable": row["status"] == "DRAFT" and not reasons,
                         "reasons": reasons, "revision": row["revision"],
                         "scenarios": {"total": len(results), "failed": [r.scenario_id for r in results if not r.passed],
                                       "mandatory_failed": [r.scenario_id for r in simulator.mandatory_failures(results)]}})


@router.post("/validate")
def validate_config(body: Check, request: Request):
    """The same report for an unsaved configuration (live lint and preview while typing). Nothing is stored."""
    _admin(request)
    return _en(request, _report(body.kind, body.config))


@router.post("/drafts/{version_id}/discard")
def discard_draft(version_id: str, body: Revision, request: Request):
    _, actor = _admin(request)
    row = _draft(version_id, request)
    try:
        store.discard_draft(version_id, body.revision, actor=actor)
    except store.Conflict:
        raise _stale(row, request) from None
    return {"discarded": version_id}


@router.post("/drafts/{version_id}/publish")
def publish_draft(version_id: str, body: Revision, request: Request):
    _, actor = _admin(request)
    row = _draft(version_id, request)
    if row["revision"] != body.revision:
        raise _stale(row, request)
    reasons = validate.publish_reasons(row)
    if reasons:
        raise _refusal(request, 422, {"message": "לא ניתן להפעיל את הטיוטה", "reasons": reasons})
    run_id = None
    if row["kind"] == "loan_policy":                     # the recorded simulation run that cleared (or stopped) this publish
        sim = simulator.simulate(row["config"], version_id, actor)
        run_id = sim.run_id
        failed = validate.scenario_reasons(list(sim.results))
        if failed:
            raise _refusal(request, 422, {"message": "תרחישי חובה נכשלו בסימולציה", "reasons": failed, "run_id": run_id})
    previous = store.published(row["kind"])
    try:
        published = store.publish(version_id, body.revision, actor)
    except store.Conflict:
        raise _stale(row, request) from None
    except store.InvalidConfig as exc:
        raise _refusal(request, 422, {"message": "לא ניתן להפעיל את הטיוטה",
                                      "reasons": [f"{e['path']}: {e['message']}" for e in exc.errors]}) from None
    return {"published": _project(published), "previous": _project(previous, with_config=False), "simulation_run_id": run_id}


@router.post("/policy/simulate")
def simulate(body: Simulate, request: Request):
    """Run a loan-policy configuration (unsaved, a version, or the published one) through every scenario fixture."""
    _, actor = _admin(request)
    config, version_id = body.config, body.version_id
    if config is None:
        row = store.get(version_id) if version_id else store.published("loan_policy")
        if row is None or row["kind"] != "loan_policy":
            raise HTTPException(404, "הגרסה לא נמצאה")
        config, version_id = row["config"], row["version_id"]
    return i18n.staff(request, simulator.simulate(config, version_id, actor, body.scenario_ids).model_dump(mode="json"))


@router.post("/policy/as-configured")
def as_configured(body: Simulate, request: Request):
    """Stateless companion to /policy/simulate: for the scenarios that pin timing values, the decision the
    configuration's own values produce. Nothing is stored; the publish gate is unaffected."""
    _admin(request)
    config = body.config
    if config is None:
        row = store.get(body.version_id) if body.version_id else store.published("loan_policy")
        if row is None or row["kind"] != "loan_policy":
            raise HTTPException(404, "הגרסה לא נמצאה")
        config = row["config"]
    return i18n.staff(request, simulator.as_configured(config, body.scenario_ids))


@router.get("/versions")
def list_versions(kind: Kind, request: Request):
    _admin(request)
    return i18n.staff(request, [_project(r, with_config=False) for r in store.versions(kind)])


@router.get("/versions/{version_id}/diff")
def version_diff(version_id: str, request: Request, against: Optional[str] = None):
    _admin(request)
    row = store.get(version_id)
    if row is None or row["kind"] not in KINDS:
        raise HTTPException(404, "הגרסה לא נמצאה")
    other = store.get(against) if against else (store.get(row["based_on"]) if row.get("based_on") else None)
    if against and (other is None or other["kind"] != row["kind"]):
        raise HTTPException(404, "גרסת ההשוואה לא נמצאה")
    return {"version": _project(row, with_config=False), "against": _project(other, with_config=False),
            "diff": store.diff(other["config"] if other else {}, row["config"])}


@router.post("/rollback")
def rollback(body: Rollback, request: Request):
    _, actor = _admin(request)
    target = store.get(body.to_version_id)
    if target is None or target["kind"] != body.kind:
        raise HTTPException(404, "הגרסה לא נמצאה")
    if target["status"] == "PUBLISHED":
        raise _refusal(request, 409, {"message": "זו כבר הגרסה הפעילה"})
    if target["status"] != "ARCHIVED":
        raise _refusal(request, 409, {"message": "אפשר לשחזר רק גרסה שהייתה פעילה בעבר"})
    try:
        row = store.rollback(body.kind, body.to_version_id, actor, body.reason)
    except store.InvalidConfig as exc:
        raise _refusal(request, 422, {"message": "הגרסה הישנה אינה תקינה עוד",
                                      "reasons": [f"{e['path']}: {e['message']}" for e in exc.errors]}) from None
    return _project(row)


@router.post("/followups/pause")
def kill_switch(body: Pause, request: Request):
    _, actor = _admin(request)
    return flags.put(flags.KILL_SWITCH, body.paused, actor, body.reason)


@router.get("/audit")
def audit(request: Request, kind: Optional[Kind] = None, limit: int = 100):
    _admin(request)
    rows = events.recent(None, events.SETTINGS_EVENTS, max(1, min(limit, 500)))
    if kind:
        rows = [e for e in rows if e["payload"].get("kind") == kind]
    kinds = (kind,) if kind else KINDS
    return i18n.staff(request, {"events": rows,
                                "versions": {k: [_project(r, with_config=False) for r in store.versions(k)] for k in kinds}})


@router.post("/prompts/test")
def prompt_test(request: Request):
    _admin(request)
    raise HTTPException(501, "שיחת בדיקה עם הסוכנת תתאפשר בשלב מאוחר יותר (deferred)")
