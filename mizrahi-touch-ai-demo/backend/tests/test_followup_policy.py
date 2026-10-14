"""The follow-up evaluator (CONTRACTS §5): every scenario fixture in backend/policy/scenarios through `evaluate` and
`contract.matches` (03 §5 S01–S18, S20–S28, S33–S37 → P01–P29, W04–W06), plus property checks that hold for any
input: hard guards always win, an invalid configuration fails closed, the bank's envelope clamps a permissive
configuration, and every decision explains itself in Hebrew."""
import ast
import itertools
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.followup import contract, policy as followup_policy
from app.followup.contract import FollowupContext
from app.followup.policy import evaluate
from app.policy import schema, store

SEED = store.seed_config("loan_policy")
SCENARIOS = contract.load_scenarios()
CONTACT = {"SCHEDULE_CALL", "DISPATCH_NOW"}
HEBREW = re.compile(r"[\u0590-\u05FF]")
NOW = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)          # Tuesday 11:00 in Israel


def policy_for(overrides: dict):
    try:
        return schema.parse("loan_policy", contract.merge_overrides(SEED, overrides))
    except ValidationError:
        return None


SEED_POLICY = policy_for({})


def ctx(**kw) -> FollowupContext:
    base = {"case_id": "DEMO-MTZ-2026-009", "policy_version": "loan_policy@v1", "consent_voice": True,
            "open_tasks": [{"task_id": "TSK-1", "requirement_code": "PAYSLIPS:BRW-A",
                            "reason_code": "REQUIRED_PERIOD_MISSING"}],
            "presence": "ENDED", "last_activity_at": NOW - timedelta(minutes=30), "plan_state": "WAITING"}
    return FollowupContext.model_validate({**base, **kw})


# ---------------------------------------------------------------- fixtures
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_scenario(scenario):
    decision = evaluate(scenario.context, policy_for(scenario.policy_overrides), scenario.now)
    assert contract.matches(scenario.expect, decision), (scenario.expect, decision)
    assert decision.policy_version == scenario.context.policy_version
    assert HEBREW.search(decision.explanation_he)


def test_fixtures_cover_the_catalogue():
    roots = {s.id[:3] for s in SCENARIOS}
    wanted = {f"S{i:02d}" for i in [*range(1, 19), *range(20, 29), *range(33, 38)]}
    assert wanted <= roots, wanted - roots
    assert all(s.mandatory == (s.id[:3] <= "S18") for s in SCENARIOS)
    refs = " ".join(s.ref for s in SCENARIOS)
    assert all(f"P{i:02d}" in refs for i in range(1, 30))
    assert all(f"W0{i}" in refs for i in (4, 5, 6))
    for s in SCENARIOS:                                 # the simulator's input must stay schema-valid JSON
        assert contract.Scenario.model_validate(s.model_dump(mode="json")) == s


# What a fixture may pin: the timing and limit values its expectation depends on. Never a safety switch (talk mode,
# Talk on/off, auto follow-up, channel order): those always come from the draft under test.
PINNABLE = {f"followup.{k}" for k in ("abandonment_grace_minutes", "in_app_idle_nudge_minutes",
                                      "unknown_presence_extra_minutes", "statement_extends_grace_minutes",
                                      "min_hours_between_calls", "max_attempts_per_case", "max_attempts_per_case_per_day",
                                      "max_attempts_per_customer_per_day", "call_window", "holidays")} | {
    "talk.reconcile_after_minutes"}


def _paths(d: dict, prefix: str = "") -> set[str]:
    out = set()
    for k, v in d.items():
        path = f"{prefix}{k}"
        out |= {path} if not isinstance(v, dict) or path in PINNABLE else _paths(v, path + ".")
    return out


def test_fixtures_pin_only_timing_values():
    for s in SCENARIOS:
        assert _paths(s.policy_overrides) <= PINNABLE, (s.id, _paths(s.policy_overrides) - PINNABLE)


def test_hard_guard_fixtures_run_against_the_draft_as_is():
    """A hard-guard fixture with no time in its expectation pins nothing: it runs on the draft exactly as edited."""
    for s in SCENARIOS:
        hard = [r for r in s.expect.blocked_by_include if contract.RULES[r][0] == "HARD_GUARD" and r != "CFG-INVALID"]
        if hard and s.expect.next_eligible_at is None:
            assert s.policy_overrides == {}, s.id


EDITS = {
    "grace 20 → 30": {"followup": {"abandonment_grace_minutes": 30}},
    "grace 20 → 5": {"followup": {"abandonment_grace_minutes": 5}},
    "idle nudge 5 → 10": {"followup": {"in_app_idle_nudge_minutes": 10}},
    "unknown presence extra 10 → 20": {"followup": {"unknown_presence_extra_minutes": 20}},
    "window from 09:00 → 10:00": {"followup": {"call_window": {"from": "10:00"}}},
    "window to 18:00 → 17:00": {"followup": {"call_window": {"to": "17:00"}}},
    "window days SUN–WED": {"followup": {"call_window": {"days": ["SUN", "MON", "TUE", "WED"]}}},
    "a new holiday": {"followup": {"holidays": ["2026-10-13", "2026-10-25"]}},
    "max attempts 2 → 3": {"followup": {"max_attempts_per_case": 3}},
    "spacing 24 → 48 h": {"followup": {"min_hours_between_calls": 48}},
    "statement extension 30 → 60": {"followup": {"statement_extends_grace_minutes": 60}},
}


@pytest.mark.parametrize("edit", EDITS, ids=list(EDITS))
def test_ordinary_edits_keep_every_scenario_green(edit):
    """The publish gate runs the fixtures against the draft: a valid timing edit must not fail any of them."""
    draft = contract.merge_overrides(SEED, EDITS[edit])
    assert schema.parse("loan_policy", draft)
    failed = []
    for s in SCENARIOS:
        try:
            policy = schema.parse("loan_policy", contract.merge_overrides(draft, s.policy_overrides))
        except ValidationError:
            policy = None
        if not contract.matches(s.expect, evaluate(s.context, policy, s.now)):
            failed.append(s.id)
    assert failed == [], (edit, failed)


SAFETY_DRAFTS = {
    "talk live": {"talk": {"mode": "live"}},
    "talk off": {"talk": {"mode": "off"}},
    "talk disabled": {"talk": {"enabled": False}},
    "auto follow-up off": {"followup": {"auto_followup_enabled": False}},
    "message channel too": {"followup": {"channel_order": ["in_app", "message", "voice"]}},
}


def test_pins_never_repair_an_invalid_draft():
    """An invalid draft fails closed in every scenario, including those whose pins would overwrite the bad value."""
    broken = contract.merge_overrides(SEED, {"followup": {"max_attempts_per_case": 99}})
    for s in SCENARIOS:
        d = evaluate(s.context, policy_for_draft(broken, s), s.now)
        assert d.action == "BLOCK" and d.blocked_by == ("CFG-INVALID",), s.id


def policy_for_draft(draft: dict, s):
    try:
        return schema.parse("loan_policy", contract.merge_overrides(draft, s.policy_overrides))
    except ValidationError:
        return None


@pytest.mark.parametrize("draft", SAFETY_DRAFTS, ids=list(SAFETY_DRAFTS))
def test_fixture_overrides_cannot_bypass_hard_guards(draft):
    """Whatever a draft and a fixture's pins say, a hard-guard scenario never yields an outbound contact."""
    base = contract.merge_overrides(SEED, SAFETY_DRAFTS[draft])
    for s in SCENARIOS:
        if not any(contract.RULES[r][0] == "HARD_GUARD" for r in s.expect.blocked_by_include):
            continue
        try:
            policy = schema.parse("loan_policy", contract.merge_overrides(base, s.policy_overrides))
        except ValidationError:
            policy = None
        d = evaluate(s.context, policy, s.now)
        assert d.action not in CONTACT, (draft, s.id, d)


def test_consolidation_covers_every_open_task():
    s = next(s for s in SCENARIOS if s.id == "S14")
    d = evaluate(s.context, SEED_POLICY, s.now)
    assert d.task_ids == ("TSK-PAY-09", "TSK-BANK-1") and d.channel == "voice"


def test_merge_overrides_is_deep_and_does_not_mutate():
    before = SEED["followup"]["call_window"]["from"]
    merged = contract.merge_overrides(SEED, {"followup": {"call_window": {"from": "12:00"}, "holidays": ["2026-10-13"]}})
    assert merged["followup"]["call_window"] == {**SEED["followup"]["call_window"], "from": "12:00"}
    assert merged["followup"]["holidays"] == ["2026-10-13"]
    assert SEED["followup"]["call_window"]["from"] == before


# ---------------------------------------------------------------- properties
HARD_GUARDS = {
    "kill switch": {"kill_switch": True},
    "case closed": {"case_open": False},
    "no consent": {"consent_voice": False, "consent_message": False},
    "opt-out": {"opt_out_voice": True},
    "unverified contact": {"contact_verified": False},
    "human review": {"human_review": True},
    "human requested": {"human_requested": True},
    "banker pause": {"banker_paused": True},
    "upload in flight": {"upload_in_flight": True},
    "evaluation in flight": {"evaluation_in_flight": True},
    "active session": {"presence": "ACTIVE", "live_sessions": 1},
    "active on the task screen": {"presence": "ACTIVE", "on_task_screen": True, "live_sessions": 1},
    "unverified issue": {"open_tasks": [{"task_id": "T", "requirement_code": "PURPOSE_PROOF",
                                         "reason_code": "UNEXPECTED_DOCUMENT_TYPE", "verified": False}]},
}


@pytest.mark.parametrize("guard", HARD_GUARDS, ids=list(HARD_GUARDS))
def test_a_hard_guard_always_wins(guard):
    """Over every fixture's context (and as a banker's manual call), a hard guard means no outbound contact."""
    for s, manual in itertools.product(SCENARIOS, (False, True)):
        c = FollowupContext.model_validate({**s.context.model_dump(mode="json"), **HARD_GUARDS[guard], "manual": manual})
        d = evaluate(c, policy_for(s.policy_overrides), s.now)
        assert d.action not in CONTACT, (guard, s.id, manual, d)
        hard = [r for r in d.blocked_by if contract.RULES[r][0] == "HARD_GUARD"]
        assert hard, (guard, s.id, d)


def test_precedence_first_blocking_tier_wins():
    # hard guard over config: no consent at night is a BLOCK, not a reschedule
    night = NOW.replace(hour=19)
    d = evaluate(ctx(consent_voice=False, last_activity_at=night - timedelta(hours=1)), SEED_POLICY, night)
    assert d.action == "BLOCK" and d.blocked_by == ("HG-NO-CONSENT",)
    # the case-level guard comes first within the hard tier
    d = evaluate(ctx(kill_switch=True, opt_out_voice=True, banker_paused=True), SEED_POLICY, NOW)
    assert d.blocked_by == ("HG-KILL-SWITCH",)
    # operational over config: a call of unknown status holds even outside the window
    d = evaluate(ctx(attempts=[{"attempt_id": "A", "channel": "voice", "status": "UNKNOWN",
                                "created_at": night - timedelta(minutes=5)}]), SEED_POLICY, night)
    assert d.blocked_by == ("OP-ATTEMPT-UNKNOWN",)
    # config over preference: grace still pending while a snooze is also set
    d = evaluate(ctx(last_activity_at=NOW - timedelta(minutes=5), snooze_until=NOW + timedelta(hours=3)), SEED_POLICY, NOW)
    assert d.action == "WAIT" and d.blocked_by == ("CFG-GRACE",)


@pytest.mark.parametrize("c", [ctx(), ctx(open_tasks=[]), ctx(kill_switch=True), ctx(presence="ACTIVE")])
def test_invalid_configuration_fails_closed(c):
    d = evaluate(c, None, NOW)
    assert d.action == "BLOCK" and d.blocked_by == ("CFG-INVALID",) and d.policy_version == c.policy_version


def _permissive():
    f = SEED_POLICY.followup
    window = f.call_window.model_copy(update={"days": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"],
                                              "from_": "00:00", "to": "23:59"})
    # model_copy does not validate: this is a configuration the schema would refuse, to prove the evaluator clamps it
    return SEED_POLICY.model_copy(update={"followup": f.model_copy(update={
        "call_window": window, "max_attempts_per_case": 9, "max_attempts_per_case_per_day": 9,
        "max_attempts_per_customer_per_day": 9, "min_hours_between_calls": 1, "abandonment_grace_minutes": 0})})


def test_envelope_clamps_a_permissive_configuration():
    loose = _permissive()
    tue_night = datetime(2026, 10, 13, 18, 30, tzinfo=timezone.utc)          # 21:30 in Israel
    d = evaluate(ctx(last_activity_at=tue_night - timedelta(hours=1)), loose, tue_night)
    assert d.action == "SCHEDULE_CALL" and "CFG-CALL-WINDOW" in d.blocked_by
    assert d.next_eligible_at == datetime(2026, 10, 14, 5, 0, tzinfo=timezone.utc)   # 08:00, the envelope's opening
    saturday = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)
    d = evaluate(ctx(last_activity_at=saturday - timedelta(hours=1)), loose, saturday)
    assert d.action == "SCHEDULE_CALL" and d.next_eligible_at == datetime(2026, 10, 18, 5, 0, tzinfo=timezone.utc)
    three = [{"attempt_id": f"A{i}", "channel": "voice", "status": "NO_ANSWER",
              "created_at": NOW - timedelta(days=i + 1)} for i in range(3)]
    assert evaluate(ctx(attempts=three), loose, NOW).action == "ESCALATE"
    two_hours_ago = [{"attempt_id": "A", "channel": "voice", "status": "NO_ANSWER", "created_at": NOW - timedelta(hours=2)}]
    d = evaluate(ctx(attempts=two_hours_ago), loose, NOW)
    assert d.action == "WAIT" and d.blocked_by == ("CFG-SPACING",) and d.next_eligible_at == NOW + timedelta(hours=2)
    left = NOW - timedelta(seconds=30)
    d = evaluate(ctx(last_activity_at=left), loose, NOW)
    assert d.blocked_by == ("CFG-GRACE",) and d.next_eligible_at == left + timedelta(minutes=1)
    d = evaluate(ctx(last_activity_at=left, environment="prod"), loose, NOW)
    assert d.next_eligible_at == left + timedelta(minutes=5)


def test_live_mode_never_dials_in_the_demo():
    live = SEED_POLICY.model_copy(update={"talk": SEED_POLICY.talk.model_copy(update={"mode": "live"})})
    d = evaluate(ctx(), live, NOW)
    assert d.action == "BLOCK" and d.blocked_by == ("HG-LIVE-DIAL-DEMO",)
    off = SEED_POLICY.model_copy(update={"talk": SEED_POLICY.talk.model_copy(update={"mode": "off"})})
    assert evaluate(ctx(), off, NOW).blocked_by == ("CFG-TALK-OFF",)
    assert evaluate(ctx(provider_healthy=False), SEED_POLICY, NOW).blocked_by == ("OP-PROVIDER-UNHEALTHY",)


def test_manual_call_turns_every_deferral_into_a_block():
    night = NOW.replace(hour=19)
    assert evaluate(ctx(manual=True, last_activity_at=night - timedelta(hours=1)), SEED_POLICY, night).blocked_by == (
        "CFG-CALL-WINDOW",)
    assert evaluate(ctx(manual=True, snooze_until=NOW + timedelta(hours=1)), SEED_POLICY, NOW).blocked_by == ("PREF-SNOOZE",)
    assert evaluate(ctx(manual=True, presence="IDLE", live_sessions=1), SEED_POLICY, NOW).blocked_by == ("HG-ACTIVE-SESSION",)
    d = evaluate(ctx(manual=True, last_activity_at=NOW - timedelta(minutes=1)), SEED_POLICY, NOW)
    assert d.action == "DISPATCH_NOW" and d.channel == "voice"


def test_customer_preferences():
    assert evaluate(ctx(preferred_channel="in_app"), SEED_POLICY, NOW).action == "IN_APP_NUDGE"
    with_message = policy_for({"followup": {"channel_order": ["in_app", "voice", "message"]}})
    d = evaluate(ctx(consent_message=True, preferred_channel="message"), with_message, NOW)
    assert d.channel == "message" and "PREF-CHANNEL" in d.rule_ids
    # opted out of voice but a message is allowed: the message channel is used, not a block
    d = evaluate(ctx(opt_out_voice=True, consent_message=True), with_message, NOW)
    assert d.action == "SCHEDULE_CALL" and d.channel == "message"


def test_idle_session_is_nudged_then_treated_as_left():
    assert evaluate(ctx(presence="IDLE", last_activity_at=NOW - timedelta(minutes=2)), SEED_POLICY, NOW).action == "WAIT"
    assert evaluate(ctx(presence="IDLE", last_activity_at=NOW - timedelta(minutes=8)), SEED_POLICY, NOW).action == "IN_APP_NUDGE"
    assert evaluate(ctx(presence="IDLE", last_activity_at=NOW - timedelta(minutes=25)), SEED_POLICY, NOW).action == "SCHEDULE_CALL"


def test_every_decision_explains_itself_and_uses_known_rules():
    seen = set()
    for s, (_, guard) in itertools.product(SCENARIOS, [("none", {}), *HARD_GUARDS.items()]):
        c = FollowupContext.model_validate({**s.context.model_dump(mode="json"), **guard})
        d = evaluate(c, policy_for(s.policy_overrides), s.now)
        assert d.explanation_he.strip() and HEBREW.search(d.explanation_he)
        assert set(d.rule_ids) <= set(contract.RULES) and set(d.blocked_by) <= set(d.rule_ids)
        if d.action not in CONTACT | {"NO_ACTION", "RESOLVE_AND_CANCEL"}:
            assert d.blocked_by, (s.id, d)
        seen.add(d.action)
    assert seen >= set(contract.ACTIONS) - {"NO_ACTION"}


def test_evaluate_is_pure():
    tree = ast.parse(Path(followup_policy.__file__).read_text(encoding="utf8"))
    imported = {a.name.split(".")[-1] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names} | {(n.module or "").split(".")[-1] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not imported & {"db", "clock", "flags", "random", "time", "repo"}
    s = SCENARIOS[0]
    assert evaluate(s.context, SEED_POLICY, s.now) == evaluate(s.context, SEED_POLICY, s.now)
    with pytest.raises(ValueError):
        evaluate(s.context, SEED_POLICY, datetime(2026, 10, 13, 8, 0))
