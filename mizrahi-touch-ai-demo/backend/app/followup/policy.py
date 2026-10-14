"""The follow-up policy evaluator (CONTRACTS §5): `evaluate(ctx, policy, now) -> Decision`.

Pure: no database, clock, flags or randomness. Every fact arrives in the FollowupContext and every setting in the
published LoanPolicy, so the orchestrator, the pre-dispatch gate and the Admin simulator get the same answer for the
same input. Code decides; the Talk prompt never takes part.

Precedence, where the first blocking tier wins:
1. hard guards: case-level (kill switch, closed, nothing open, banker requested or paused, human review), then the
   customer helping themselves (upload or review in flight, an active or idle session), then the contact channel
   (consent, opt-out, unverified contact, no live dialling in the demo);
2. operational uncertainty (a call still in progress or of unknown status, provider down, presence unknown);
3. the published configuration (switches, attempt cap, grace, daily caps, spacing, call window and holidays);
4. customer preferences (snooze, requested callback, preferred channel).
The bank's ENVELOPE is applied on top of the configuration, even when a configuration is more permissive.

A customer-requested callback (PREF-CALLBACK) replaces the grace period, the configured spacing and the per-case daily
cap; the call window, the envelope's spacing, the attempt cap, the per-customer cap and every hard guard still apply.
A manual call (`ctx.manual`) skips the grace period and the auto-follow-up switch, and turns every deferral into a
BLOCK: the banker asked for a call now, so "later" is a refusal with its reason."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..policy.schema import LoanPolicy
from . import windows
from .contract import ATTEMPT_RANK, ENVELOPE, RULES, Decision, FollowupContext

IN_PROGRESS = tuple(s for s, rank in ATTEMPT_RANK.items() if rank < 9 and s != "UNKNOWN")
QUIET_PLAN_STATES = ("IDLE", "COMPLETED", "CANCELED")          # nothing to cancel when the last task resolves
PROVIDER_RETRY_MINUTES = 5                                      # first step of the comms back-off [5, 30]

HEADLINE = {
    "NO_ACTION": "אין פעולה נדרשת",
    "IN_APP_ONLY": "תיקון עצמי בפורטל — אין פנייה יזומה",
    "IN_APP_NUDGE": "תזכורת בפורטל — אין שיחה",
    "SUPPRESS": "אין פנייה כעת",
    "WAIT": "ממתינים לפני פנייה",
    "SCHEDULE_CALL": "שיחה מתוכננת",
    "DISPATCH_NOW": "השיחה יוצאת כעת",
    "BLOCK": "פנייה חסומה",
    "SNOOZE": "הפנייה נדחתה לבקשת הלקוח",
    "ESCALATE": "הועבר לטיפול הבנקאי",
    "RESOLVE_AND_CANCEL": "כל הדרישות הושלמו — פניות מתוכננות בוטלו",
}


def _decision(ctx: FollowupContext, action: str, blocked: tuple[str, ...] = (), shaped: tuple[str, ...] = (), *,
              next_at: Optional[datetime] = None, channel: Optional[str] = None, tasks: tuple[str, ...] = (),
              note: str = "") -> Decision:
    rule_ids = tuple(dict.fromkeys(blocked + shaped))
    reasons = [RULES[r][1] for r in dict.fromkeys(blocked)] or ["כל תנאי המדיניות מתקיימים"]
    text = HEADLINE[action] + ": " + "; ".join(reasons)
    if note:
        text += f" ({note})"
    if next_at is not None:
        text += f" · מועד אפשרי: {windows.format_local(next_at)}"
    return Decision(action=action, policy_version=ctx.policy_version, explanation_he=text,
                    blocked_by=tuple(dict.fromkeys(blocked)), rule_ids=rule_ids, next_eligible_at=next_at,
                    channel=channel, task_ids=tasks)


def _channel_guards(ctx: FollowupContext, channel: str) -> tuple[str, ...]:
    consent, opt_out = ((ctx.consent_voice, ctx.opt_out_voice) if channel == "voice"
                        else (ctx.consent_message, ctx.opt_out_message))
    out = []
    if opt_out:
        out.append("HG-OPT-OUT")
    if not consent:
        out.append("HG-NO-CONSENT")
    if not ctx.contact_verified:
        out.append("HG-CONTACT-UNVERIFIED")
    return tuple(out)


def evaluate(ctx: FollowupContext, policy: Optional[LoanPolicy], now: datetime) -> Decision:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    all_tasks = tuple(t.task_id for t in ctx.open_tasks)
    if policy is None:
        return _decision(ctx, "BLOCK", ("CFG-INVALID",), tasks=all_tasks)
    f, talk = policy.followup, policy.talk

    # ---- 1. hard guards: the case
    if ctx.kill_switch:
        return _decision(ctx, "BLOCK", ("HG-KILL-SWITCH",), tasks=all_tasks)
    if not ctx.case_open:
        return _decision(ctx, "BLOCK", ("HG-CASE-CLOSED",), tasks=all_tasks)
    if not ctx.open_tasks:
        action = "NO_ACTION" if ctx.plan_state in QUIET_PLAN_STATES else "RESOLVE_AND_CANCEL"
        return _decision(ctx, action, ("HG-NO-OPEN-TASK",))
    if ctx.human_requested:
        return _decision(ctx, "ESCALATE", ("HG-HUMAN-REQUESTED",), tasks=all_tasks)
    if ctx.banker_paused:
        return _decision(ctx, "BLOCK", ("HG-BANKER-PAUSE",), tasks=all_tasks)
    verified = tuple(t.task_id for t in ctx.open_tasks if t.verified)
    if ctx.human_review or not verified:
        return _decision(ctx, "BLOCK", ("HG-HUMAN-REVIEW",), tasks=all_tasks)
    shaped: tuple[str, ...] = ()
    if len(verified) < len(all_tasks):
        shaped += ("HG-HUMAN-REVIEW",)               # the unverified ones wait for the banker; the rest go on
    if len(verified) >= 2:
        shaped += ("CFG-CONSOLIDATE",)
    tasks = verified

    def block(*rules: str, note: str = "") -> Decision:
        return _decision(ctx, "BLOCK", rules, shaped, tasks=tasks, note=note)

    # ---- 1. hard guards: the customer is helping themselves
    if ctx.upload_in_flight or ctx.evaluation_in_flight:
        return _decision(ctx, "SUPPRESS", ("HG-IN-FLIGHT",), shaped, tasks=tasks)
    grace = timedelta(minutes=max(f.abandonment_grace_minutes, ENVELOPE["min_grace_minutes"][ctx.environment]))
    if ctx.presence == "ACTIVE":
        if ctx.manual:
            return block("HG-ACTIVE-SESSION")
        if ctx.on_task_screen:
            return _decision(ctx, "IN_APP_ONLY", ("HG-ACTIVE-SESSION",), ("CFG-IN-APP-FIRST",) + shaped,
                             channel="in_app", tasks=tasks)
        if ctx.live_sessions >= 2:
            return _decision(ctx, "SUPPRESS", ("HG-ACTIVE-SESSION",), shaped, tasks=tasks, note="פעיל במכשיר אחר")
        return _decision(ctx, "WAIT", ("HG-ACTIVE-SESSION",), shaped, tasks=tasks, note="הלקוח עדיין בפורטל")
    if ctx.presence == "IDLE":
        idle_since = ctx.last_activity_at or ctx.last_seen_at or now
        if ctx.manual:
            return block("HG-ACTIVE-SESSION")
        nudge = timedelta(minutes=f.in_app_idle_nudge_minutes)
        if now < idle_since + min(nudge, grace):
            return _decision(ctx, "WAIT", ("HG-ACTIVE-SESSION",), ("CFG-IDLE-NUDGE",) + shaped,
                             next_at=idle_since + min(nudge, grace), tasks=tasks, note="הלקוח פתח את הפורטל ואינו פעיל")
        if now < idle_since + grace:
            return _decision(ctx, "IN_APP_NUDGE", ("HG-ACTIVE-SESSION",), ("CFG-IDLE-NUDGE",) + shaped,
                             next_at=idle_since + grace, channel="in_app", tasks=tasks)
        # idle for the whole grace period: treated as having left

    # ---- 1. hard guards: may this customer be contacted outside the app at all?
    channels = [c for c in f.channel_order if c != "in_app"]
    allowed = [c for c in channels if not _channel_guards(ctx, c)]
    if channels and not allowed:
        return block(*sum((_channel_guards(ctx, c) for c in channels), ()))
    if talk.mode == "live" and ctx.environment == "demo":
        return block("HG-LIVE-DIAL-DEMO")

    # ---- 2. operational uncertainty
    def defer(action: str, rules: tuple[str, ...], until: Optional[datetime], extra: tuple[str, ...] = ()) -> Decision:
        if ctx.manual:
            return block(*rules)
        return _decision(ctx, action, rules, extra + shaped, next_at=until, tasks=tasks)

    if any(a.status in IN_PROGRESS for a in ctx.attempts):
        return defer("SUPPRESS", ("OP-CALL-IN-PROGRESS",), None)
    if any(a.status == "UNKNOWN" for a in ctx.attempts):
        return defer("WAIT", ("OP-ATTEMPT-UNKNOWN",), now + timedelta(minutes=talk.reconcile_after_minutes))
    if not ctx.provider_healthy:
        return defer("WAIT", ("OP-PROVIDER-UNHEALTHY",), now + timedelta(minutes=PROVIDER_RETRY_MINUTES))
    callback = ctx.callback_at is not None
    seen = [t for t in (ctx.last_activity_at, ctx.last_seen_at) if t is not None]
    if ctx.presence == "UNKNOWN" and seen and not ctx.manual and not callback:
        until = max(seen) + grace + timedelta(minutes=f.unknown_presence_extra_minutes)
        if now < until:
            return defer("WAIT", ("OP-PRESENCE-UNKNOWN",), until, ("CFG-GRACE",))

    # ---- 3. published configuration
    if not f.auto_followup_enabled and not ctx.manual:
        return block("CFG-AUTO-OFF")
    if talk.mode == "off" or not talk.enabled or not channels:
        return block("CFG-TALK-OFF")
    counted = [a for a in ctx.attempts if a.status != "CANCELED"]
    if len(counted) >= min(f.max_attempts_per_case, ENVELOPE["max_attempts_per_case"]):
        if ctx.manual:
            return block("CFG-MAX-ATTEMPTS")
        return _decision(ctx, "ESCALATE", ("CFG-MAX-ATTEMPTS",), shaped, tasks=tasks)

    deferrals: list[tuple[str, datetime]] = []
    if not ctx.manual and not callback:
        reference = ctx.last_activity_at or ctx.last_seen_at
        if reference is not None:
            shaped += ("CFG-GRACE",)
            deferrals.append(("CFG-GRACE", reference + grace))
        if ctx.customer_statement_at is not None:
            deferrals.append(("CFG-STATEMENT-GRACE",
                              ctx.customer_statement_at + timedelta(minutes=f.statement_extends_grace_minutes)))
    next_day = windows.next_window_start(windows.next_local_midnight(now), f.call_window, f.holidays)
    if ctx.customer_attempts_today >= f.max_attempts_per_customer_per_day and next_day:
        deferrals.append(("CFG-DAILY-CUSTOMER", next_day))
    today = windows.local_date(now)
    if not callback and sum(windows.local_date(a.created_at) == today for a in counted) >= f.max_attempts_per_case_per_day \
            and next_day:
        deferrals.append(("CFG-DAILY-CASE", next_day))
    if counted:
        hours = ENVELOPE["min_hours_between_calls"] if callback else max(f.min_hours_between_calls,
                                                                          ENVELOPE["min_hours_between_calls"])
        deferrals.append(("CFG-SPACING", max(a.created_at for a in counted) + timedelta(hours=hours)))
    pending = [(rule, until) for rule, until in deferrals if until > now]
    target = max([until for _, until in pending], default=now)
    callback_ahead = callback and ctx.callback_at > now and not ctx.manual
    if callback:
        shaped += ("PREF-CALLBACK",)
    if callback_ahead:                                # the requested time is the target; only later limits block
        target = max(target, ctx.callback_at)
        pending = [(rule, until) for rule, until in pending if until > ctx.callback_at]
    opening = windows.next_window_start(target, f.call_window, f.holidays)
    closed = windows.closed_reason(now, f.call_window, f.holidays)
    window_rule = {"holiday": "CFG-HOLIDAY", "window": "CFG-CALL-WINDOW"}.get(closed or "", "")
    if opening is None:                               # no allowed day at all: a configuration the envelope emptied
        return block("CFG-CALL-WINDOW")
    if pending or window_rule or callback_ahead:
        blocked = tuple(rule for rule, _ in pending) + ((window_rule,) if window_rule else ())
        if ctx.manual:
            return block(*blocked)
        return _decision(ctx, "WAIT" if pending else "SCHEDULE_CALL", blocked, ("CFG-CALL-WINDOW",) + shaped,
                         next_at=opening, channel=None if pending else allowed[0], tasks=tasks,
                         note="שיחה חוזרת במועד שהלקוח ביקש" if callback_ahead and not pending else "")
    shaped += ("CFG-CALL-WINDOW",)

    # ---- 4. customer preferences
    if ctx.snooze_until is not None and ctx.snooze_until > now:
        until = windows.next_window_start(ctx.snooze_until, f.call_window, f.holidays)
        if ctx.manual:
            return block("PREF-SNOOZE")
        return _decision(ctx, "SNOOZE", ("PREF-SNOOZE",), shaped, next_at=until, tasks=tasks)
    channel = allowed[0]
    if ctx.preferred_channel == "in_app" and not ctx.manual:
        return _decision(ctx, "IN_APP_NUDGE", ("PREF-CHANNEL",), shaped, channel="in_app", tasks=tasks)
    if ctx.preferred_channel in allowed and ctx.preferred_channel != channel:
        channel, shaped = ctx.preferred_channel, shaped + ("PREF-CHANNEL",)

    action = "DISPATCH_NOW" if ctx.manual or ctx.plan_state == "SCHEDULED" else "SCHEDULE_CALL"
    return _decision(ctx, action, (), shaped, next_at=now, channel=channel, tasks=tasks)
