# Frozen shared contracts — parallel Rounds 3 and 4

Frozen on 2026-10-14 at base `parallel/base` (snapshot `parallel/r12-snapshot` + this contract commit). These are the
names and shapes that Agent A (Rounds 1–2), Agent B (Round 3 follow-up engine) and Agent C (Round 4 Admin) all rely
on. `backend/tests/test_parallel_contracts.py` checks every item marked **[tested]**.

Change rules:
- **Additive only.** You may add a rule id, event type, field with a default, or route. You may not rename, remove or
  re-type anything listed here.
- A breaking change needs the user's approval and a line in §11 (change log) on the owner's branch.
- Where `04-target-architecture-contracts.md` and the code disagree, **the code and this file win**.

## 0. Demo-first scope (v2, 2026-10-14, user decision) — read this first
Mizrahi #2 is a working sales demo, not a production banking platform. Build for today's demo and keep tomorrow's
integration path: a real follow-up engine, a mock JEEN Talk behind the `OutboundProvider` boundary, and an Admin
area that edits, tests and saves configuration that the engine really reads.

- **Not built** (and not to be added):
  - new login, roles, persona switching or permission screens;
  - two-person / distinct-approver publishing;
  - a separate audit view or audit API;
  - `If-Match` / `ETag` / 428 handling;
  - the HTTP webhook route with HMAC, timestamps and a secret;
  - the `talk_reconcile` job;
  - identity-verification or onboarding screens;
  - new tables.
- **Existing security stays as it is**: signed sessions (`auth.py`), case-bound customer sessions, the banker's
  assignment rule for writes, and the customer projection.
- **No real call** happens unless `talk.mode = live` *and* a configured JEEN Talk adapter exists. Today the live
  adapter is a stub that reports "not configured", so the evaluator blocks (`OP-PROVIDER-UNHEALTHY`).
- Sections below are edited in place where v2 changes them; each change is logged in §11.

## 1. Database (`backend/app/db.py`, owner: Agent A) [tested]
- The 14 Round 3/4 tables already exist, with the columns asserted in `test_parallel_contracts.TABLES`:
  `config_versions`, `case_profile`, `demo_applications`, `completion_tasks`, `contact_plans`, `contact_attempts`,
  `policy_decisions`, `customer_presence`, `contact_preferences`, `provider_events`, `case_events`, `case_overrides`,
  `upload_links`, `simulation_runs`, `system_flags`. Also `jobs`, for the job kinds in §8.
- Differences from doc 04:
  - `completion_tasks` has `issue_key`, not `issue_version`.
  - `contact_attempts` adds `request` and `actor`.
  - `upload_links` adds `demo_token`. This is the clear token, written **only** in the demo environment so that
    `GET /api/demo/cases/{id}/sent-links` can show it. Outside demo it must be NULL.
  - `customer_presence` adds `visible` and `started_at`.
- B and C do not edit `db.py`. If a column is truly needed on one of the 14 tables, add it as a **new line** in
  `db.ADDED_COLUMNS` (TEXT columns only) and log it in §11. New tables need the user's approval.
- One transaction per state change. `db.tx()` does not nest, so pass `conn=` to `events.emit` inside a transaction.
- Booleans are stored as `0`/`1`, timestamps as UTC ISO-8601 strings, and JSON via `db.jdump`/`db.jload`.

## 2. Policy configuration (`backend/app/policy/schema.py`, frozen; `store.py`, owner: Agent C, additions only) [tested]
- `LoanPolicy` sections: `schema_version, scope, product, document_requirements, validation, customer_messages,
  followup, talk, templates`.
  - `Followup` and `Talk` have exactly the fields in the test.
  - `talk` is flat: `mode, enabled, link_ttl_minutes, reconcile_after_minutes, max_provider_errors`. Doc 04's
    `retry.backoff_minutes` is not in the schema. Agent B uses the code constant `[5, 30]` in `comms/`.
- `TalkPrompt`: `schema_version, locale, opening_locked, instructions, allowed_variables`.
- `PROMPT_VARIABLES = (first_name, missing_documents, secure_upload_link, next_step)`.
- Template variables use the `{{name}}` form.
- Seed files are `backend/policy/seed/loan_policy.demo.json` and `talk_prompt.demo.json`, with scope
  `demo:personal_loan.all_purpose`.
- The store API is `published, get, versions, parsed, policy, validate, create_draft, update_draft, discard_draft,
  publish, rollback, diff`, with the exceptions `Conflict, NotDraft, InvalidConfig`.
  - A version row carries `label` (`"loan_policy@v3"`) and `revision`, which is the ETag.
  - Rollback publishes a NEW version.
- A case pins its policy version on first use (`workflow/requirements.pin`). Publishing never changes an open
  case's requirements. Agent B's evaluator reads **follow-up** settings from the **currently published** policy
  (doc 03 S27: a publish re-evaluates pending plans under the new rules, with no catch-up blast).
- Settings with no schema field are code constants. The bank envelope is `followup.contract.ENVELOPE`.
- No approval step (v2): the admin who edits a draft may publish it. There is no `require_distinct_approver`.

## 3. Requirements and readiness (owner: Agent A, read-only for B and C) [tested]
- `requirements.for_case(case_id)` returns a list of instances with at least `code` (`PAYSLIPS:BRW-A`,
  `BANK_STATEMENTS:ACC-1`, `PURPOSE_PROOF`), `requirement_id, family, required, borrower_id, account_id, title_he,
  policy_version`.
- `readiness.compute(case_id)` returns `state, case_status, requirements[], pending_jobs, counts`. Each requirement
  carries `code, family, ai_state, open_customer_actions, accepted_document_ids`.
  - `ai_state` is one of `required_missing, needs_customer_action, needs_banker_review, checking, extracted,
    preparation_confirmed` (plus `uploaded_unreadable` and `not_evaluated_in_demo`).
  - `CASE_STATUS_HE` already includes `FOLLOWUP_IN_PROGRESS` and `AWAITING_CUSTOMER`. Agent B refines
    `NEEDS_COMPLETION` into those inside `followup/orchestrator.py`, without editing `readiness.py`.
- Findings (`findings` table): `code`, `review_state` (`CUSTOMER_ACTION_REQUIRED` / `NEEDS_BANKER_REVIEW`),
  `status`, `document_id`, `borrower_id`, `period`, `detail` (JSON; `detail.requirement_code` when the finding is
  about a missing requirement).
  - Reason codes and customer wording come from `review/reason_codes.py`, through `CUSTOMER_SHORT` and
    `document_text`.
  - A task's `reason_code` is a finding `code`.
- Demo cases:
  - `DEMO-MTZ-2026-009` is the follow-up journey case: consent given, voice line `TEST-LINE-01`.
  - `DEMO-MTZ-2026-010` has consent withheld, so every contact is blocked.
  - `case["contact"]` = `{consent_voice, consent_message, phone_ref, phone_masked}`. `contact_preferences` is
    seeded from it on first use.

## 4. Sessions and permissions (v2: the existing mechanism only, no new RBAC) [tested]
No new login, roles, persona switcher or permission UI. Routes use the session checks `auth.py` already has:
- Customer routes use `auth.require_customer_case`.
- Staff reads, every `/admin` route and the demo routes use `auth.require_staff`: any signed staff session.
  - In demo mode, `/banker`, `/system` and `/admin` all obtain the demo banker's session through
    `POST /api/session/demo/staff {}`, exactly as `/banker` does today. The demo banker is also the demo admin.
- Banker writes on a case use `auth.require_assigned_staff` (today's rule).
- Demo routes also need `settings.demo_identity`.

`capabilities.py` and the capability lists in `bank/mock_bank.py` already exist in the base and stay as they are,
together with their contract test. No Round 3/4 route has to use them; they are kept for a later bank-SSO
integration. Live JEEN Talk callbacks will be authenticated the way JEEN Talk specifies, when that connection exists.

## 5. Evaluator (`backend/app/followup/contract.py` frozen; `followup/policy.py`, owner: Agent B) [tested]
- Signature: `evaluate(ctx: FollowupContext, policy: LoanPolicy | None, now: datetime) -> Decision`.
  - It is pure: no I/O, no clock reads, no randomness.
  - `policy=None` means the configuration did not validate; the result is `BLOCK` with `CFG-INVALID` (fail closed for
    contact only).
- `FollowupContext` is a strict, frozen Pydantic model. Every datetime must be timezone-aware. Defaults are
  fail-closed: no consent and nobody present.
- `Decision` fields: `action, policy_version, explanation_he, blocked_by ⊆ rule_ids, rule_ids, next_eligible_at,
  channel, task_ids`.
  - Every id must be a key of `RULES`.
  - `policy_version` echoes `ctx.policy_version`.
- `ACTIONS`:
  - `NO_ACTION, IN_APP_ONLY, IN_APP_NUDGE, SUPPRESS, WAIT, SCHEDULE_CALL, DISPATCH_NOW, BLOCK, SNOOZE, ESCALATE,
    RESOLVE_AND_CANCEL`.
  - Doc 03's extra decision names map onto these: WAIT_FOR_INACTIVITY / START_GRACE / CANCEL_OR_DEFER → `WAIT`;
    HOLD_UNTIL_EVALUATED → `SUPPRESS`; HUMAN_REVIEW → `BLOCK` + `HG-HUMAN-REVIEW`; CANCEL / CANCEL_ALL → `BLOCK` with
    the guard's id (the orchestrator then cancels the plan); CONSOLIDATE → one decision with every `task_ids` +
    `CFG-CONSOLIDATE`.
- Precedence, where the first blocking tier wins: `HARD_GUARD` > `OPERATIONAL` > `CONFIG` > `PREFERENCE`. The
  Talk prompt never takes part.
- `LOCKED_RULES` (every `HARD_GUARD` id) and `ENVELOPE` are what Admin shows read-only.
- State vocabularies: `TASK_STATUSES`, `PLAN_STATES`, `ATTEMPT_RANK` (forward only; rank 9 is final),
  `CALL_OUTCOMES`.

## 6. Simulator input and output (models in `contract.py`; `policy/simulator.py`, owner: Agent C, after gate G1)
- **Input:** scenario fixtures in `backend/policy/scenarios/*.json`, owned by Agent B. Each file holds one
  `Scenario` or a list of them:
  `{id, title_he, mandatory, ref, now, context: FollowupContext, policy_overrides, expect: {action,
  rule_ids_include, blocked_by_include, next_eligible_at?}}`. Load them with `contract.load_scenarios()`.
- **Run:** `simulate(config: dict, version_id: str | None, actor: str, scenario_ids: list[str] | None = None) ->
  SimulationRun`.
  - For each scenario, deep-merge `policy_overrides` into `config` and parse it with `schema.parse("loan_policy",
    …)`. An invalid result becomes `policy=None`.
  - Then call `evaluate(scenario.context, policy, scenario.now)` and compare with `contract.matches`.
  - An exception in one scenario becomes `ScenarioResult.error` with `passed=False`.
- **Output:** `SimulationRun {run_id, version_id, config_hash, actor, created_at, side_effects: false, passed,
  mandatory_passed, results[]}`.
- **Side effects:** exactly one `simulation_runs` row and one `policy.simulation_completed.v1` event. No other table
  changes. This is doc 03 S40, and the tests count rows in every table.
- **Publish gate (`loan_policy`):** the schema is valid, the envelope holds, and (once the simulator exists after G1)
  `mandatory_passed` is true. For `talk_prompt`: the schema is valid and the AI-disclosure opening is unchanged.

## 7. Admin API (`backend/app/api/admin.py`, owner: Agent C; prefix `/api/admin/loan-completion`)
Every route needs a staff session (`auth.require_staff`, §4). One admin edits, tests and publishes; there is no
approval step. Concurrency is the store's `revision`: the client sends the revision it edited, and a stale one is a
409 (no `If-Match`, `ETag` or 428).

| Route | Notes |
|---|---|
| `GET /settings` | published row per kind, the open draft per kind (or null), `kill_switch` (`flags.row`), `locked_rules` + labels, `envelope`, environment, prompt variables + synthetic preview values, `simulator_available` |
| `POST /drafts` `{kind, reason?}` | returns the open draft of that kind, creating it from the published version when there is none (one open draft per kind) |
| `PUT /drafts/{id}` `{config, revision, reason?}` | returns the row; 409 on a stale revision or when not a draft, 404 when unknown; 422 when a locked field changes (`scope`, `schema_version`, the prompt's `opening_locked`) |
| `POST /drafts/{id}/validate` | `{errors[{path,message}], warnings[], diff[], preview}`; warnings include the prompt lint |
| `POST /drafts/{id}/discard` `{revision}` | |
| `POST /drafts/{id}/publish` `{revision}` | the gate in §6; 422 with reasons when it fails |
| `GET /versions?kind=` · `GET /versions/{id}/diff?against=` | the version list (author, last editor, publisher, times, reason) is the settings history |
| `POST /rollback` `{kind, to_version_id, reason?}` | publishes a new version that copies the old configuration |
| `POST /policy/simulate` `{version_id?, config?}` | returns `SimulationRun` (gate G1) |
| `POST /policy/interpret-proposal` `{text_he, version_id}` | `{patch[{path,value}], dropped[], diff, rationale_he, applied:false}`; never saves or publishes; 503 when Gemini is unavailable. Lowest priority. |
| `POST /prompts/test` `{version_id, message}` | 501 until gate G5 |
| `POST /followups/pause` `{paused, reason?}` | the kill switch: `flags.put(KILL_SWITCH, …)` |

Events (through the existing outbox, no separate audit view): the store emits `settings.draft_saved.v1`,
`settings.policy_published.v1`, `settings.prompt_published.v1` and `settings.rollback_applied.v1`; the simulator emits
`policy.simulation_completed.v1`; `flags.put` emits the kill-switch event.

## 8. Follow-up API, clock and jobs (owner: Agent B; `backend/app/api/followup.py`)
Customer routes (the customer session for that case; no rule ids, attempts, policy versions or banker text):
- `POST /api/cases/{id}/presence` `{session_id, event, seq, visible, screen?, requirement_code?}` → `{state, ttl_seconds}`.
  - `event` is one of `session_started, heartbeat, user_activity, file_picker_opened, upload_started,
    upload_completed, session_resumed, session_ended`.
  - `screen` is one of `home, documents, document, other`.
  - A lower `seq` per session is ignored.
- `GET /api/cases/{id}/followup` → `{state_he, nudge, nudge_text_he, open_items[{requirement_code, title_he,
  customer_text_he}], snooze_until, contact{voice_allowed, message_allowed, preferred_channel}, simulated}`.
- `POST /api/cases/{id}/followup-snooze` `{minutes (15–1440) | until}` · `POST /api/cases/{id}/contact-preferences`
  `{opt_out_voice?, opt_out_message?, preferred_channel?}` → both return the GET shape.
- `POST /api/links/redeem` `{token}` → `{state: ok|resolved|expired|invalid, case_id?, target?}`.
  - `ok` and `resolved` set a customer session bound to that case only (`auth.issue` + `auth._set`, as today).
  - A link stays usable until it expires or its tasks are resolved, so a presenter can open it twice. `used_at`
    records the first use; the `used` state is reserved and not returned in v2.
  - `target` is `/customer/documents?req=<code>`.

Banker routes (staff session; writes also need the assigned banker, §4):
- `GET /api/banker/cases/{id}/followup` → `{plan{state, plan_version, next_eligible_at,
  policy_version, updated_at}, decision (Decision), tasks[], attempts[{attempt_id, channel, provider, simulated,
  status, outcome, created_at, updated_at, prompt_version, link_id}], preferences, overrides[], kill_switch,
  talk_mode, simulated}`.
- `GET /api/banker/cases/{id}/timeline` → `[{at, type, actor, summary_he, payload}]`.
- `POST /api/banker/cases/{id}/followup-override` (assigned) `{type: pause|resume|human_review|reschedule|cancel,
  reason (≥3), until?}`.
- `POST /api/banker/cases/{id}/followups` (assigned) `{reason}` → 201 attempt, or 409 `{detail, blocked_by[]}`.

Talk status events (v2: an in-process receiver; the HTTP webhook is deferred):
- `comms/webhook.py::apply_event(payload) -> "applied" | "duplicate" | "ignored" | "orphan"` is the single receiver.
  The payload is the 04 §6 body: `{event_id, event_type, client_reference, provider_call_id, sequence, status,
  outcome?, occurred_at, data{link_sent?, callback_at?, identity_verified?}}`.
  - It dedupes on `provider_events.event_id` and only moves an attempt forward (`ATTEMPT_RANK`); a final status is
    never overwritten.
  - An unknown `client_reference` is stored as an orphan and emits `integration.reconciliation_required.v1`.
- `MockTalkProvider` calls `apply_event` in-process, with no signing.
- Deferred to the live JEEN Talk connection: the route `POST /api/webhooks/jeen-talk`, signature and timestamp checks,
  and the secret. The route will wrap `apply_event` without changing it.

Demo routes (`/api/demo`; `demo_identity` + a staff session; each writes an event, and every response carries a
"סימולציה" label):
- `POST /clock` `{advance_minutes? | to_next_window? | reset?}` → `{now, offset_seconds}`.
- `POST /cases/{id}/customer-left`.
- `POST /cases/{id}/talk-outcome` `{outcome ∈ CALL_OUTCOMES, callback_at?}`.
- `GET /cases/{id}/sent-links`.
- `POST /tick`, which runs due follow-up work now.

Clock (`backend/app/clock.py`, owner: Agent B):
- `clock.now()` is aware UTC: wall time plus `flags.DEMO_CLOCK_OFFSET`, with the offset honoured only in the demo
  environment. `clock.now_iso()` is the string form.
- Call windows and holidays are evaluated in `Asia/Jerusalem`.
- `settings.SIMULATION_DATE` (review months) and `util.now_iso()` (existing code) are unchanged.

Jobs:
- Kinds: `followup_evaluate` `{trigger}` and `talk_mock_script` `{attempt_id, step}`.
  - `talk_reconcile` `{attempt_id}` is deferred to live Talk: the mock never leaves an attempt `UNKNOWN`.
  - The evaluator still honours `OP-ATTEMPT-UNKNOWN`, and its scenario fixture stays.
- `not_before` is wall-clock UTC, so a clock-time target is stored as `target - offset`.
- Wiring them into `workflow/engine.py::_claim` is Agent B's job at gate G5. Before that the orchestrator exposes
  `tick(now)` and `run_due(now)`, so tests drive it with a fixed `now`.

Flags (`backend/app/flags.py`, shared; owner: Agent B) [tested]:
- `KILL_SWITCH = "followup.kill_switch"` (bool) and `DEMO_CLOCK_OFFSET = "demo.clock_offset_seconds"` (int).
- `get/row/put` are typed, and every `put` emits its event.
- The kill switch takes effect at the next evaluation and at the pre-dispatch gate. A dispatch that is already past
  the gate is cancelled best-effort (`TOO_LATE_TO_CANCEL` is allowed).

## 9. Events (`backend/app/events.py`, shared) [tested]
- `events.emit(type, case_id, actor, payload, correlation_id=None, occurred_at=None, conn=None)` and
  `events.recent(case_id, types, limit)`.
- The types are a closed list:
  - `DOCUMENT_EVENTS` and `FOLLOWUP_EVENTS` are appended to by Agent B.
  - `SETTINGS_EVENTS` is appended to by Agent C.
  - Each agent appends on its own tuple's lines only.
- Follow-up code passes `occurred_at=clock.now_iso()`.
- The payload never holds a token, phone number, ID number, amount or document content.

## 10. Talk adapter (`backend/app/comms/`, owner: Agent B; live JEEN Talk is deferred)
- `OutboundProvider` protocol, with `name` and `simulated`:
  - `capabilities() -> Capabilities{cancel_call, get_call, send_message, hebrew_voice, sandbox}`
  - `health() -> Health{ok, detail}`
  - `create_call(CallRequest) -> ProviderAck{provider_call_id, status, accepted_at}`, idempotent on
    `idempotency_key`
  - `cancel_call(id) -> CancelResult{status: CANCELED|TOO_LATE_TO_CANCEL|NOT_FOUND}`
  - `get_call(id) -> CallState{status, outcome?, sequence, updated_at}`
  - `send_message(MessageRequest) -> ProviderAck`
- `CallRequest` fields:
  - `idempotency_key = case:{case}:plan:{plan_version}:tasks:{hash}`
  - `client_reference`, which is the attempt id
  - `case_ref` and `contact_ref` (opaque; the demo uses the allowlisted `TEST-LINE-01`)
  - `locale = he-IL`, `prompt_version`
  - `variables {first_name, missing_documents[], secure_upload_link, next_step}`
  - `allowed_actions [send_link, mark_no_answer, request_human, schedule_callback]`
  - `requires_identity_verification`
  - `context_tool = "get_followup_context"`
  - `callback_url`, `expires_at`
- `MockTalkProvider` (`simulated=True`) never dials. It schedules `talk_mock_script` steps that build the 04 §6
  payloads and pass them to `comms/webhook.py::apply_event`, the same receiver the live route will use (§8).
- `JeenTalkProvider` is a stub: `health()` returns not configured, and every call raises `ProviderNotConfigured`.
  `callback_url` stays in `CallRequest` and is None for the mock. `requires_identity_verification` is a Talk-side
  flag; there are no identity screens in the app.
- `comms.registry.active(policy)` maps `talk.mode`:
  - `simulation` → mock
  - `off` → None
  - `live` → the stub, whose unhealthy status makes the evaluator return `OP-PROVIDER-UNHEALTHY`
- Every attempt records `provider` and `simulated`.

## 11. Change log
| Date | Owner | Change | Approved by |
|---|---|---|---|
| 2026-10-14 | setup | initial freeze | user (parallel workflow) |
| 2026-10-14 | setup (via Agent C) | v2 demo-first scope: §0 added. §2 drops the distinct approver. §4 uses existing `auth` checks only. §6 gate without approver. §7: staff session, body `revision`, one open draft per kind, no `/audit`. §8: no `used` link state, in-process `apply_event`, HTTP webhook + HMAC deferred, `talk_reconcile` deferred, demo routes need a staff session. §10: mock calls `apply_event`. No breaking change to code in `parallel/base`. | user ("demo-first scope simplification") |
