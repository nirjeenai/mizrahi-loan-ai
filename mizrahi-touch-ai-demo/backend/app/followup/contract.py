"""The follow-up evaluator contract, frozen for parallel work (docs/plans/parallel/CONTRACTS.md §5–6).

`followup/policy.py` implements `evaluate(ctx, policy, now) -> Decision`, a pure function over these types. The
orchestrator builds a FollowupContext from the database; the Admin simulator builds one from a scenario fixture in
`backend/policy/scenarios/`. Both read the same models, so a fixture and a live evaluation cannot drift apart.

Rule ids, actions and states may be appended to; a published id is never renamed, reused or removed."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional, Protocol, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from ..config import BACKEND_DIR
from ..policy.schema import LoanPolicy

Action = Literal["NO_ACTION", "IN_APP_ONLY", "IN_APP_NUDGE", "SUPPRESS", "WAIT", "SCHEDULE_CALL", "DISPATCH_NOW",
                 "BLOCK", "SNOOZE", "ESCALATE", "RESOLVE_AND_CANCEL"]
ACTIONS: tuple[str, ...] = get_args(Action)
Presence = Literal["ACTIVE", "IDLE", "ENDED", "UNKNOWN", "NONE"]        # aggregated over every tab and device
Tier = Literal["HARD_GUARD", "OPERATIONAL", "CONFIG", "PREFERENCE"]    # precedence order: the first blocking tier wins

TASK_STATUSES = ("OPEN", "IN_APP_PROMPTED", "FOLLOWUP_SCHEDULED", "CONTACT_ATTEMPTED", "AWAITING_CUSTOMER",
                 "RECHECKING", "RESOLVED", "ESCALATED", "CANCELED", "PAUSED_BY_CUSTOMER", "PAUSED_BY_BANKER",
                 "POLICY_BLOCKED")
PLAN_STATES = ("IDLE", "IN_APP", "WAITING", "SCHEDULED", "DISPATCHING", "IN_CALL", "AWAITING_CUSTOMER", "BLOCKED",
               "PAUSED", "ESCALATED", "COMPLETED", "CANCELED")
# contact attempts only move forward: a callback with a lower rank is ignored, a final status is never overwritten
ATTEMPT_RANK = {"QUEUED": 0, "DISPATCHING": 1, "DIALING": 2, "CONNECTED": 3, "UNKNOWN": 4, "CANCEL_REQUESTED": 5,
                "CANCEL_FAILED": 6, "COMPLETED": 9, "NO_ANSWER": 9, "FAILED": 9, "CANCELED": 9}
FINAL_ATTEMPT_STATUSES = tuple(s for s, rank in ATTEMPT_RANK.items() if rank == 9)
CALL_OUTCOMES = ("LINK_SENT", "CALLBACK_REQUESTED", "REFUSED", "HUMAN_REQUESTED", "NO_ANSWER", "IDENTITY_FAILED",
                 "COMPLETED_NO_ACTION")

RULES: dict[str, tuple[Tier, str]] = {
    # hard guards: code constants, shown read-only in Admin, never overridable by configuration or prompt
    "HG-KILL-SWITCH": ("HARD_GUARD", "האוטומציה הושבתה במתג החירום"),
    "CFG-INVALID": ("HARD_GUARD", "תצורת המדיניות אינה תקינה — אין פניות יזומות"),
    "HG-CASE-CLOSED": ("HARD_GUARD", "התיק סגור או בוטל"),
    "HG-NO-CONSENT": ("HARD_GUARD", "אין הרשאת קשר לערוץ"),
    "HG-OPT-OUT": ("HARD_GUARD", "הלקוח ביקש שלא ליצור איתו קשר בערוץ זה"),
    "HG-CONTACT-UNVERIFIED": ("HARD_GUARD", "פרטי הקשר לא אומתו"),
    "HG-HUMAN-REVIEW": ("HARD_GUARD", "הדרישה בבדיקה אנושית — אין פנייה אוטומטית"),
    "HG-HUMAN-REQUESTED": ("HARD_GUARD", "הלקוח ביקש נציג אנושי"),
    "HG-BANKER-PAUSE": ("HARD_GUARD", "הבנקאי השהה את הטיפול היזום"),
    "HG-NO-OPEN-TASK": ("HARD_GUARD", "אין דרישת השלמה פתוחה ומאומתת"),
    "HG-ACTIVE-SESSION": ("HARD_GUARD", "הלקוח פעיל בפורטל"),
    "HG-IN-FLIGHT": ("HARD_GUARD", "העלאה או בדיקת מסמך בתהליך"),
    "HG-LIVE-DIAL-DEMO": ("HARD_GUARD", "סביבת הדגמה אינה מחייגת ללקוחות"),
    # operational uncertainty
    "OP-PRESENCE-UNKNOWN": ("OPERATIONAL", "נוכחות הלקוח אינה ודאית — המתנה נוספת"),
    "OP-PROVIDER-UNHEALTHY": ("OPERATIONAL", "ספק השיחות אינו זמין"),
    "OP-ATTEMPT-UNKNOWN": ("OPERATIONAL", "סטטוס שיחה קודמת אינו ידוע — מבררים לפני פנייה נוספת"),
    "OP-CALL-IN-PROGRESS": ("OPERATIONAL", "פנייה קודמת עדיין בתהליך — אין פנייה נוספת"),
    # published configuration
    "CFG-AUTO-OFF": ("CONFIG", "הטיפול היזום כבוי בהגדרות"),
    "CFG-TALK-OFF": ("CONFIG", "ערוץ השיחה כבוי בהגדרות"),
    "CFG-IN-APP-FIRST": ("CONFIG", "תיקון עצמי בפורטל קודם לכל פנייה"),
    "CFG-IDLE-NUDGE": ("CONFIG", "תזכורת בפורטל לאחר חוסר פעילות"),
    "CFG-GRACE": ("CONFIG", "תקופת המתנה לאחר שהלקוח עזב"),
    "CFG-STATEMENT-GRACE": ("CONFIG", "הלקוח מסר שכבר שלח — הארכת ההמתנה"),
    "CFG-CALL-WINDOW": ("CONFIG", "מחוץ לשעות הפנייה"),
    "CFG-HOLIDAY": ("CONFIG", "יום חג — אין פניות"),
    "CFG-MAX-ATTEMPTS": ("CONFIG", "מוצתה מכסת הפניות לתיק"),
    "CFG-DAILY-CASE": ("CONFIG", "מוצתה המכסה היומית לתיק"),
    "CFG-DAILY-CUSTOMER": ("CONFIG", "מוצתה המכסה היומית ללקוח"),
    "CFG-SPACING": ("CONFIG", "טרם עבר המרווח המינימלי בין שיחות"),
    "CFG-CONSOLIDATE": ("CONFIG", "כל הדרישות הפתוחות מטופלות בפנייה אחת"),
    # customer preferences
    "PREF-SNOOZE": ("PREFERENCE", "הלקוח ביקש לדחות את הפנייה"),
    "PREF-CHANNEL": ("PREFERENCE", "ערוץ מועדף על הלקוח"),
    "PREF-CALLBACK": ("PREFERENCE", "הלקוח ביקש שיחה חוזרת במועד מסוים"),
}
LOCKED_RULES: tuple[str, ...] = tuple(r for r, (tier, _) in RULES.items() if tier == "HARD_GUARD")
# the bank's envelope: limits no published configuration can exceed (policy/schema.py enforces those it can express)
ENVELOPE: dict[str, Any] = {
    "call_window_bounds": ("08:00", "20:00"), "no_contact_days": ("SAT",), "max_attempts_per_case": 3,
    "min_hours_between_calls": 4, "min_grace_minutes": {"demo": 1, "staging": 5, "prod": 5},
}


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenTask(_Frozen):
    task_id: str
    requirement_code: str
    reason_code: str
    status: str = "OPEN"
    verified: bool = True          # False: the issue rests on an UNDETERMINED or low-confidence review → human review


class AttemptSummary(_Frozen):
    attempt_id: str
    channel: Literal["voice", "message"]
    status: str
    created_at: AwareDatetime
    outcome: Optional[str] = None


class FollowupContext(_Frozen):
    """Every fact the evaluator may use. Defaults are the fail-closed reading (no consent, nobody present)."""
    case_id: str
    policy_version: str                          # e.g. "loan_policy@v3", echoed in the Decision
    environment: Literal["demo", "staging", "prod"] = "demo"
    case_open: bool = True
    kill_switch: bool = False
    open_tasks: tuple[OpenTask, ...] = ()
    human_review: bool = False
    human_requested: bool = False
    banker_paused: bool = False
    presence: Presence = "NONE"
    on_task_screen: bool = False                 # an ACTIVE session is on the screen that fixes an open task
    last_activity_at: Optional[AwareDatetime] = None
    last_seen_at: Optional[AwareDatetime] = None
    upload_in_flight: bool = False               # file picker open or an upload request running
    evaluation_in_flight: bool = False           # a review job for the case is queued or running
    consent_voice: bool = False
    consent_message: bool = False
    opt_out_voice: bool = False
    opt_out_message: bool = False
    contact_verified: bool = True
    snooze_until: Optional[AwareDatetime] = None
    preferred_channel: Optional[Literal["in_app", "message", "voice"]] = None
    callback_at: Optional[AwareDatetime] = None
    customer_statement_at: Optional[AwareDatetime] = None
    attempts: tuple[AttemptSummary, ...] = ()
    customer_attempts_today: int = Field(0, ge=0)   # across every case of the same customer
    provider_healthy: bool = True
    plan_state: str = "IDLE"
    live_sessions: int = Field(0, ge=0)          # sessions not ENDED or expired; ≥2 with ACTIVE means another device
    manual: bool = False                         # a banker's call-now request: no grace, and every deferral blocks


class Decision(_Frozen):
    action: Action
    policy_version: str
    explanation_he: str = Field(..., min_length=2)
    blocked_by: tuple[str, ...] = ()             # the rules that stopped a contact (a subset of rule_ids)
    rule_ids: tuple[str, ...] = ()               # every rule that shaped the decision
    next_eligible_at: Optional[AwareDatetime] = None
    channel: Optional[Literal["in_app", "message", "voice"]] = None
    task_ids: tuple[str, ...] = ()               # the open tasks this decision covers (one plan per case)

    @model_validator(mode="after")
    def _known_rules(self) -> "Decision":
        unknown = [r for r in self.rule_ids + self.blocked_by if r not in RULES]
        if unknown:
            raise ValueError(f"unknown rule ids: {unknown}")
        if not set(self.blocked_by) <= set(self.rule_ids):
            raise ValueError("blocked_by must be a subset of rule_ids")
        return self


class Evaluator(Protocol):
    """`policy=None` means the configuration under evaluation did not validate: the answer is BLOCK / CFG-INVALID."""
    def __call__(self, ctx: FollowupContext, policy: Optional[LoanPolicy], now: datetime) -> Decision: ...


# ---------------------------------------------------------------- simulator input / output
SCENARIO_DIR = BACKEND_DIR / "policy" / "scenarios"


class Expectation(_Frozen):
    action: Action
    rule_ids_include: tuple[str, ...] = ()
    blocked_by_include: tuple[str, ...] = ()
    next_eligible_at: Optional[AwareDatetime] = None


class Scenario(_Frozen):
    id: str = Field(..., pattern=r"^[A-Z]{1,2}\d{2}[A-Za-z0-9_-]*$")   # S06, P01, W04 … (03-prd-gap-analysis.md §5)
    title_he: str
    mandatory: bool = True                       # a mandatory scenario must pass before a draft can be published
    ref: str = ""                                # where the scenario comes from, e.g. "PRD §8.9 #6" or "03 §5 S06"
    now: AwareDatetime
    context: FollowupContext
    policy_overrides: dict[str, Any] = {}        # deep-merged into the configuration under test
    expect: Expectation


class ScenarioResult(_Frozen):
    scenario_id: str
    title_he: str
    mandatory: bool
    passed: bool
    expected: Expectation
    actual: Optional[Decision] = None
    error: Optional[str] = None


class SimulationRun(_Frozen):
    run_id: str
    version_id: Optional[str]                    # the draft or version simulated; None for an unsaved configuration
    config_hash: str
    actor: str
    created_at: AwareDatetime
    side_effects: Literal[False] = False
    passed: bool                                 # every scenario passed
    mandatory_passed: bool                       # every mandatory scenario passed (the publish gate)
    results: tuple[ScenarioResult, ...]


def matches(expect: Expectation, decision: Decision) -> bool:
    """The one comparison both the simulator and the scenario tests use."""
    return (decision.action == expect.action and set(expect.rule_ids_include) <= set(decision.rule_ids)
            and set(expect.blocked_by_include) <= set(decision.blocked_by)
            and (expect.next_eligible_at is None or decision.next_eligible_at == expect.next_eligible_at))


def merge_overrides(config: dict, overrides: dict) -> dict:
    """A scenario's `policy_overrides` over a configuration: dicts merge key by key, anything else (lists included)
    replaces. Neither input is modified."""
    out = dict(config)
    for key, value in overrides.items():
        out[key] = merge_overrides(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def load_scenarios(directory: Path = SCENARIO_DIR) -> list[Scenario]:
    """Every `*.json` file holds one scenario or a list of them; ids are unique across files."""
    out: list[Scenario] = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf8"))
        out += [Scenario.model_validate(s) for s in (data if isinstance(data, list) else [data])]
    ids = [s.id for s in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate scenario id")
    return out
