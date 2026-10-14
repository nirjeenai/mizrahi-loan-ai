"""What the Admin may save and publish: schema errors, the bank's envelope, locked fields and the prompt lint.

The schema (`policy/schema.py`) already enforces most bounds; the envelope checks here restate the bank's limits from
`followup.contract.ENVELOPE` on the raw configuration, so a looser schema can never widen them. Code decides; the
editor only proposes."""
from __future__ import annotations

from typing import Any, Optional

from ..followup.contract import ENVELOPE
from . import prompts, store

LOCKED_FIELDS = {"loan_policy": ("schema_version", "scope"), "talk_prompt": ("schema_version", "opening_locked")}
LOCKED_HE = {"schema_version": "גרסת הסכמה נקבעת בקוד", "scope": "הסביבה והמוצר נקבעים בהתקנה, לא בהגדרות",
             "opening_locked": "פתיח הגילוי (סוכנת בינה מלאכותית) נעול"}


def _int(v: Any) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def envelope_errors(config: dict) -> list[dict]:
    f = config.get("followup") if isinstance(config.get("followup"), dict) else {}
    env = (config.get("scope") or {}).get("environment", "demo") if isinstance(config.get("scope"), dict) else "demo"
    out: list[dict] = []
    grace, floor = _int(f.get("abandonment_grace_minutes")), ENVELOPE["min_grace_minutes"].get(env, 5)
    if grace is not None and grace < floor:
        out.append({"path": "followup.abandonment_grace_minutes",
                    "message": f"מעטפת הבנק: תקופת ההמתנה בסביבה זו היא לפחות {floor} דקות"})
    attempts = _int(f.get("max_attempts_per_case"))
    if attempts is not None and attempts > ENVELOPE["max_attempts_per_case"]:
        out.append({"path": "followup.max_attempts_per_case",
                    "message": f"מעטפת הבנק: לכל היותר {ENVELOPE['max_attempts_per_case']} פניות לתיק"})
    spacing = _int(f.get("min_hours_between_calls"))
    if spacing is not None and spacing < ENVELOPE["min_hours_between_calls"]:
        out.append({"path": "followup.min_hours_between_calls",
                    "message": f"מעטפת הבנק: לפחות {ENVELOPE['min_hours_between_calls']} שעות בין שיחות"})
    window = f.get("call_window") if isinstance(f.get("call_window"), dict) else {}
    lo, hi = ENVELOPE["call_window_bounds"]
    for key in ("from", "to"):
        v = window.get(key)
        if isinstance(v, str) and not (lo <= v <= hi):
            out.append({"path": f"followup.call_window.{key}", "message": f"מעטפת הבנק: שעות הפנייה בין {lo} ל־{hi}"})
    days = window.get("days") if isinstance(window.get("days"), list) else []
    banned = [d for d in days if d in ENVELOPE["no_contact_days"]]
    if banned:
        out.append({"path": "followup.call_window.days", "message": "מעטפת הבנק: אין פנייה בשבת"})
    return out


def locked_errors(kind: str, base: dict, config: dict) -> list[dict]:
    return [{"path": k, "message": LOCKED_HE[k]} for k in LOCKED_FIELDS[kind] if config.get(k) != base.get(k)]


def check(kind: str, config: dict) -> dict:
    """{errors[{path, message}], warnings[{path, code, message, span}]} for one configuration."""
    errors = store.validate(kind, config)
    covered = [e["path"] for e in errors]
    if kind == "loan_policy":
        errors += [e for e in envelope_errors(config)
                   if not any(e["path"] == p or e["path"].startswith(p + ".") for p in covered)]
        lint = prompts.lint_messages(config)
    else:
        lint = prompts.lint_prompt(config)
    # an unknown variable is already a schema error; the lint adds only what the schema can't see
    errors += [{"path": f["path"], "message": f["message_he"], "code": f["code"]} for f in lint
               if f["severity"] == "error" and f["code"] != "PROMPT_UNKNOWN_VARIABLE"]
    warnings = [{"path": f["path"], "code": f["code"], "message": f["message_he"], "span": f["span"],
                 "match": f["match"]} for f in lint if f["severity"] == "warning"]
    if kind == "loan_policy":
        env = (config.get("scope") or {}).get("environment") if isinstance(config.get("scope"), dict) else None
        if (config.get("talk") or {}).get("mode") == "live" and env == "demo":
            warnings.append({"path": "talk.mode", "code": "TALK_LIVE_IN_DEMO", "span": None, "match": "",
                             "message": "מצב live בסביבת הדגמה: ספק השיחות החי אינו מוגדר, ולכן לא תתבצע אף שיחה."})
    return {"errors": errors, "warnings": warnings, "lint": lint}


def publish_reasons(row: dict) -> list[str]:
    """Why a draft can't be published yet (empty when it can)."""
    published = store.published(row["kind"])
    reasons = [f"{e['path'] or 'תצורה'}: {e['message']}" for e in check(row["kind"], row["config"])["errors"]]
    reasons += [f"{e['path']}: {e['message']}" for e in locked_errors(row["kind"], published["config"], row["config"])]
    if row.get("based_on") and row["based_on"] != published["version_id"]:
        reasons.append(f"הטיוטה נפתחה מגרסה שאינה הפעילה (הפעילה היא {published['label']}). בטלו אותה ופתחו טיוטה חדשה.")
    if not store.diff(published["config"], row["config"]):
        reasons.append("אין שינויים לעומת הגרסה הפעילה.")
    return reasons
