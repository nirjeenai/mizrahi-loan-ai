"""The contracts frozen for parallel work (docs/plans/parallel/CONTRACTS.md). A failure here means a shared name or shape
changed under another workstream: fix the change or update the contract with every owner, never just this test."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import auth, capabilities, db, events, flags
from app.bank.mock_bank import bank
from app.followup import contract
from app.policy import schema, store
from app.workflow import readiness, requirements

NOW = datetime(2026, 10, 13, 10, 30, tzinfo=timezone.utc)

TABLES = {
    "config_versions": "version_id kind scope number status config schema_version hash revision author created_at "
                       "updated_at published_at published_by based_on change_reason validation last_editor",
    "case_profile": "case_id requirement_set_version pinned_at profile",
    "demo_applications": "case_id created_at application",
    "completion_tasks": "task_id case_id requirement_code reason_code status issue_key document_id title_he "
                        "customer_text_he created_at updated_at resolved_at history",
    "contact_plans": "case_id state decision next_eligible_at policy_version plan_version nudge updated_at",
    "contact_attempts": "attempt_id case_id channel provider simulated idempotency_key status outcome provider_call_id "
                        "task_ids policy_version prompt_version link_id request created_at updated_at history actor",
    "policy_decisions": "decision_id case_id action blocked_by rule_ids next_eligible_at policy_version explanation_he "
                        "trigger evaluated_at",
    "customer_presence": "case_id session_id state last_seen_at last_activity_at last_upload_action_at picker_open_until "
                         "ended_at seq visible started_at",
    "contact_preferences": "case_id consent_voice consent_message opt_out_voice opt_out_message snooze_until "
                           "preferred_channel updated_at updated_by",
    "provider_events": "event_id provider received_at attempt_id payload result",
    "case_events": "event_id type case_id occurred_at actor correlation_id payload",
    "case_overrides": "override_id case_id type reason actor created_at expires_at revoked_at detail",
    "upload_links": "link_id token_hash case_id task_ids requirement_code created_at expires_at used_at attempt_id demo_token",
    "simulation_runs": "run_id version_id created_at actor results passed",
    "system_flags": "key value updated_at updated_by",
    "jobs": "job_id kind case_id document_id idempotency_key status attempts not_before created_at updated_at error payload",
}


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


def test_tables_have_the_frozen_columns():
    for table, columns in TABLES.items():
        have = {r["name"] for r in db.query(f"PRAGMA table_info({table})")}
        assert set(columns.split()) <= have, (table, set(columns.split()) - have)


def test_policy_schema_sections_and_store_api():
    assert set(schema.LoanPolicy.model_fields) == {"schema_version", "scope", "product", "document_requirements",
                                                   "validation", "customer_messages", "followup", "talk", "templates"}
    assert {"auto_followup_enabled", "presence_ttl_seconds", "in_app_idle_nudge_minutes", "abandonment_grace_minutes",
            "unknown_presence_extra_minutes", "channel_order", "min_hours_between_calls", "max_attempts_per_case",
            "max_attempts_per_case_per_day", "max_attempts_per_customer_per_day", "call_window", "holidays",
            "on_exhausted_attempts", "statement_extends_grace_minutes"} == set(schema.Followup.model_fields)
    assert set(schema.Talk.model_fields) == {"mode", "enabled", "link_ttl_minutes", "reconcile_after_minutes",
                                             "max_provider_errors"}
    assert set(schema.Templates.model_fields) == {"in_app_correction", "link_message", "reminder", "completed"}
    assert schema.PROMPT_VARIABLES == ("first_name", "missing_documents", "secure_upload_link", "next_step")
    assert set(schema.KINDS) == {"loan_policy", "talk_prompt"}
    for name in ("published", "get", "versions", "parsed", "policy", "validate", "create_draft", "update_draft",
                 "discard_draft", "publish", "rollback", "diff", "Conflict", "NotDraft", "InvalidConfig"):
        assert hasattr(store, name), name
    pol, row = store.policy()
    assert row["label"].startswith("loan_policy@v") and pol.followup.channel_order[0] == "in_app"


def test_requirement_and_readiness_shapes():
    case_id = "DEMO-MTZ-2026-009"
    reqs = requirements.for_case(case_id)
    assert reqs and {"code", "requirement_id", "family", "required", "borrower_id", "account_id", "title_he",
                     "policy_version"} <= set(reqs[0])
    assert {"required_missing", "needs_customer_action", "needs_banker_review", "checking", "extracted",
            "preparation_confirmed"} <= set(readiness.REQ_STATE_HE)
    assert {"NEEDS_COMPLETION", "FOLLOWUP_IN_PROGRESS", "AWAITING_CUSTOMER", "READY_FOR_BANKER"} <= set(readiness.CASE_STATUS_HE)
    r = readiness.compute(case_id)
    assert {"state", "case_status", "requirements", "pending_jobs", "counts"} <= set(r)
    assert {"code", "family", "ai_state", "open_customer_actions", "accepted_document_ids"} <= set(r["requirements"][0])


def test_staff_capabilities_and_contact_fields():
    caps = {s["staff_id"]: set(s["capabilities"]) for s in bank.staff_directory()}
    assert {"case.read", "case.write", "followup.override", "followup.manual_call"} <= caps["STAFF-DANA"]
    assert {"policy.read", "policy.edit", "prompt.edit", "demo.simulate", "audit.read"} <= caps["STAFF-MAYA"]
    assert {"policy.read", "policy.publish", "prompt.publish", "audit.read"} <= caps["STAFF-AVI"]
    assert "policy.publish" not in caps["STAFF-MAYA"] and "policy.edit" not in caps["STAFF-AVI"]
    assert {"consent_voice", "consent_message", "phone_ref"} <= set(bank.get_case("DEMO-MTZ-2026-009")["contact"])
    assert bank.get_case("DEMO-MTZ-2026-010")["contact"]["consent_voice"] is False


def test_capability_checks_are_server_side():
    app = FastAPI()

    @app.get("/edit")
    def edit(request: Request):
        return capabilities.require(request, "policy.edit")

    @app.get("/either")
    def either(request: Request):
        return capabilities.require(request, "policy.edit", "policy.publish", any_of=True)

    c = TestClient(app)
    assert c.get("/edit").status_code == 401
    bearer = lambda sid: {"authorization": f"Bearer {auth.issue('staff', sid)}"}   # noqa: E731
    assert c.get("/edit", headers=bearer("STAFF-DANA")).status_code == 403
    assert c.get("/edit", headers=bearer("STAFF-MAYA")).json()["staff_id"] == "STAFF-MAYA"
    assert c.get("/either", headers=bearer("STAFF-AVI")).status_code == 200
    assert c.get("/edit", headers={"X-Staff-Id": "STAFF-MAYA"}).status_code == 401


def test_events_are_a_closed_list():
    with pytest.raises(ValueError):
        events.emit("followup.made_up.v1", "DEMO-MTZ-2026-009", "test")
    eid = events.emit("followup.deferred.v1", "DEMO-MTZ-2026-009", "test", {"why": "contract"})
    assert events.recent("DEMO-MTZ-2026-009", ("followup.deferred.v1",))[0]["event_id"] == eid
    assert all(t.endswith(".v1") for t in events.EVENT_TYPES) and len(set(events.EVENT_TYPES)) == len(events.EVENT_TYPES)


def test_flags_are_typed_and_audited():
    assert flags.get(flags.KILL_SWITCH) is False and flags.get(flags.DEMO_CLOCK_OFFSET) == 0
    with pytest.raises(TypeError):
        flags.put(flags.KILL_SWITCH, 1, "test")
    with pytest.raises(KeyError):
        flags.get("made.up")
    assert flags.put(flags.KILL_SWITCH, True, "admin:STAFF-MAYA", "test")["updated_by"] == "admin:STAFF-MAYA"
    assert flags.get(flags.KILL_SWITCH) is True
    assert events.recent(None, ("settings.kill_switch_changed.v1",))[0]["payload"]["after"] is True
    flags.put(flags.KILL_SWITCH, False, "test")


def test_evaluator_and_simulator_models():
    ctx = contract.FollowupContext.model_validate({
        "case_id": "DEMO-MTZ-2026-009", "policy_version": "loan_policy@v1", "presence": "ENDED",
        "last_activity_at": "2026-10-13T09:00:00+00:00", "consent_voice": True,
        "open_tasks": [{"task_id": "TSK-1", "requirement_code": "PAYSLIPS:BRW-A", "reason_code": "REQUIRED_PERIOD_MISSING"}],
        "attempts": [{"attempt_id": "ATT-1", "channel": "voice", "status": "NO_ANSWER", "created_at": "2026-10-12T09:00:00+00:00"}]})
    assert contract.FollowupContext.model_validate(ctx.model_dump(mode="json")) == ctx
    with pytest.raises(ValidationError):
        contract.FollowupContext.model_validate({"case_id": "X", "policy_version": "v", "made_up": 1})
    with pytest.raises(ValidationError):
        contract.FollowupContext.model_validate({"case_id": "X", "policy_version": "v", "last_seen_at": "2026-10-13T09:00:00"})
    d = contract.Decision(action="SCHEDULE_CALL", policy_version="loan_policy@v1", explanation_he="תקופת ההמתנה הסתיימה",
                          rule_ids=("CFG-GRACE",), next_eligible_at=NOW + timedelta(minutes=5), channel="voice",
                          task_ids=("TSK-1",))
    with pytest.raises(ValidationError):
        contract.Decision(action="BLOCK", policy_version="v", explanation_he="חסום", blocked_by=("HG-OPT-OUT",))
    with pytest.raises(ValidationError):
        contract.Decision(action="BLOCK", policy_version="v", explanation_he="חסום", rule_ids=("MADE-UP",))
    assert contract.matches(contract.Expectation(action="SCHEDULE_CALL", rule_ids_include=("CFG-GRACE",)), d)
    assert not contract.matches(contract.Expectation(action="WAIT"), d)
    s = contract.Scenario.model_validate({"id": "S06", "title_he": "תם זמן ההמתנה", "now": NOW.isoformat(),
                                          "context": ctx.model_dump(mode="json"), "expect": {"action": "SCHEDULE_CALL"}})
    assert s.mandatory and s.policy_overrides == {}
    assert set(contract.LOCKED_RULES) >= {"HG-KILL-SWITCH", "CFG-INVALID", "HG-OPT-OUT", "HG-ACTIVE-SESSION"}
    assert contract.ATTEMPT_RANK["COMPLETED"] > contract.ATTEMPT_RANK["CONNECTED"] > contract.ATTEMPT_RANK["QUEUED"]
    for scenario in contract.load_scenarios():
        assert scenario.expect.action in contract.ACTIONS
