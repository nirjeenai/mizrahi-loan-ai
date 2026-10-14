# Frozen shared contracts — parallel Rounds 3 and 4

Frozen on 2026-10-14 at base `parallel/base` (snapshot `parallel/r12-snapshot` + this contract commit). These are the
names and shapes that Agent A (Rounds 1–2), Agent B (Round 3 follow-up engine) and Agent C (Round 4 Admin) all rely
on. `backend/tests/test_parallel_contracts.py` checks every item marked **[tested]**.

Change rules:
- **Additive only.** You may add a rule id, event type, field with a default, or route. You may not rename, remove or
  re-type anything listed here.
- A breaking change needs the user's approval and a line in §11 (change log) on the owner's branch.
- Where `04-target-architecture-contracts.md` and the code disagree, **the code and this file win**.

**Demo-first scope (user decision, 2026-10-14 10:45).** Mizrahi #2 is a working sales demo, not a production banking
platform. Build for today's demo and keep tomorrow's integration path (the `OutboundProvider` boundary, versioned
configuration, the pure evaluator). Where this file and docs 04/05/06 describe a production control, the simplified
rule here wins. What was cut is listed in §12; nothing in §12 is built in Rounds 3–4.
- No new login, identity, role or approval flows. Routes use the session checks `auth.py` already has (§4).
- No new tables or columns beyond the 14 that already exist. Columns a simplified feature no longer needs stay NULL.
- No production webhook security before the live JEEN Talk connection exists (§8).
- No real customer call is possible until a live provider is implemented and configured (§10).

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
  - A version row carries `label` (`"loan_policy@v3"`) and `revision`, which an edit sends back (stale → 409).
  - Rollback publishes a NEW version.
- A case pins its policy version on first use (`workflow/requirements.pin`). Publishing never changes an open
  case's requirements. Agent B's evaluator reads **follow-up** settings from the **currently published** policy
  (doc 03 S27: a publish re-evaluates pending plans under the new rules, with no catch-up blast).
- Settings with no schema field are code constants. The bank envelope is `followup.contract.ENVELOPE`.
  (`require_distinct_approver` is deferred: one demo admin edits and publishes, §12.)

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

## 4. Access — the existing sessions only
No new login screens, roles, persona switchers or permission flows. Every Round 3–4 route uses a check `auth.py`
already has; the demo obtains its sessions without a login (`DEMO_IDENTITY=1`), as the customer app and the banker
console do today.

| Routes | Check |
|---|---|
| Customer follow-up routes (§8) | `auth.require_customer_case` |
| Banker reads (follow-up view, timeline) | `auth.require_staff` |
| Banker writes on a case (override, manual call) | `auth.require_assigned_staff` (the existing rule) |
| Admin Settings, every route (§7) | `auth.require_staff`: the demo staff session the console already uses; one admin edits, tests and publishes |
| Demo controls (§8) | `settings.demo_identity` on (else 404), plus a staff session or the case's customer session (the presenter pane drives them from the customer app) |
| Talk webhook (§8) | no session; a shared secret, and only once one is configured |

`capabilities.py` and the capability lists in `mock_bank.STAFF` stay as they are (the contract test covers them).
Round 3–4 routes don't depend on them, and nothing is added to them.

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
- **Publish gate (`loan_policy`):** the schema is valid, the envelope holds, and `mandatory_passed` is true. The
  same admin who edited may publish.

## 7. Admin API (`backend/app/api/admin.py`, owner: Agent C; prefix `/api/admin/loan-completion`)
Every route needs a staff session (`auth.require_staff`, §4). The flow is edit → test → save and publish → history
→ rollback, by one admin, with no approval step.

| Route | Notes |
|---|---|
| `GET /settings` | published rows for both kinds, the open draft per kind (if any), `kill_switch` (`flags.row`), `locked_rules` + labels, `envelope`, environment |
| `POST /drafts` `{kind, based_on?, reason?}` | returns the open draft for that kind if one exists, otherwise a new one (one working draft per kind) |
| `PUT /drafts/{id}` `{config, revision, reason?}` | 409 on a stale `revision` (the store's `Conflict`), 404/409 when not a draft |
| `POST /drafts/{id}/validate` | `{errors[{path,message}], warnings[], diff[]}`; warnings include the prompt lint |
| `POST /drafts/{id}/discard` `{revision}` | |
| `POST /drafts/{id}/publish` `{revision}` | the gate in §6; 422 with reasons when it fails |
| `GET /versions?kind=` · `GET /versions/{id}/diff?against=` | |
| `POST /rollback` `{kind, to_version_id, reason}` | publishes a new version (store behavior) |
| `POST /policy/simulate` `{version_id? , config?}` | returns `SimulationRun` (gate G1) |
| `POST /followups/pause` `{paused, reason}` | the kill switch: `flags.put(KILL_SWITCH, …)` |
| `GET /audit?kind=&limit=` | version history + settings events, from the existing tables |
| `POST /prompts/test` | 501 "deferred"; optional at G5 |

Events: `settings.draft_saved.v1`, `settings.policy_published.v1`, `settings.prompt_published.v1`,
`settings.rollback_applied.v1`, `policy.simulation_completed.v1`. The kill switch emits its event through `flags.put`.
The natural-language proposal route (`interpret-proposal`) is deferred (§12).

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
  - A link works until it expires or its tasks are resolved. It is not single-use, so a presenter can open it twice.
    The `used` state and `upload_links.used_at` are reserved (§12).
  - The token is 32 random bytes, and only its SHA-256 is stored. `demo_token` (the clear token) is written in the
    demo environment only, for `sent-links`.
  - `ok` and `resolved` set a customer session bound to that case only (`auth.issue` + `auth._set`).
  - `target` is `/customer/documents?req=<code>`.

Banker routes (access per §4):
- `GET /api/banker/cases/{id}/followup` → `{plan{state, plan_version, next_eligible_at,
  policy_version, updated_at}, decision (Decision), tasks[], attempts[{attempt_id, channel, provider, simulated,
  status, outcome, created_at, updated_at, prompt_version, link_id}], preferences, overrides[], kill_switch,
  talk_mode, simulated}`.
- `GET /api/banker/cases/{id}/timeline` → `[{at, type, actor, summary_he, payload}]`, from `case_events`.
- `POST /api/banker/cases/{id}/followup-override` `{type: pause|resume|cancel, reason (≥3)}`.
- `POST /api/banker/cases/{id}/followups` `{reason}` (a manual call through the same guards) → 201 attempt, or 409
  `{detail, blocked_by[]}`.

Talk events and webhook (demo-grade until the live connection; the real scheme comes from JEEN Talk's spec):
- **The main path is in-process.** `comms.webhook.apply(event: dict, provider: str) -> result` does every functional
  check: dedupe on `provider_events.event_id`, forward-only ranks, a final status is never overwritten, and an unknown
  `client_reference` is stored as an orphan with `integration.reconciliation_required.v1`. The mock provider calls
  `apply` directly. The event body is `{event_id, event_type: "call.status_changed", client_reference,
  provider_call_id, sequence, status, outcome?, occurred_at, data: {link_sent?, callback_at?}}`.
- **HTTP receiver** `POST /api/webhooks/jeen-talk`: a thin wrapper around `apply`.
  - 404 when `TALK_WEBHOOK_SECRET` is not set, which is the default in the demo.
  - When it is set, the header `X-Talk-Secret` must equal it (constant-time compare), else 401.
  - Responses: 200 `applied|duplicate|ignored`, 202 `orphan`, 400 for a malformed body.
  - The HMAC signature, timestamp window and secret file are deferred to the live integration (§12).

Demo routes (`/api/demo`; access per §4; each call writes one `repo.audit` row and returns a "סימולציה" label):
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

Scheduling: no new job kinds; one tick.
- `orchestrator.tick(now)` runs all due follow-up work in one pass:
  - evaluates plans whose `next_eligible_at` has passed;
  - advances due mock-call script steps, whose state lives on the attempt row (`request`, `history`);
  - reconciles `UNKNOWN` attempts older than `talk.reconcile_after_minutes` through `provider.get_call`.
- `orchestrator.on_event(case_id, trigger, now)` re-evaluates one case right away (presence change, upload, review
  finished, override).
- Before G5, tests (with a fixed `now`) and `POST /api/demo/tick` drive both. At G5 the existing worker loop calls
  `tick(clock.now())` every few seconds, and the upload and review paths call `on_event`. `engine._claim` is
  unchanged.

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
- `MockTalkProvider` (`simulated=True`) never dials. Its scripted steps (dialing → connected → outcome) are advanced
  by `tick` and produce the same event bodies a live provider would, passed to `webhook.apply`. A demo control
  (`talk-outcome`) picks the outcome.
- `JeenTalkProvider` is a stub: `health()` returns not configured, and every call raises `ProviderNotConfigured`.
- `comms.registry.active(policy)` maps `talk.mode`:
  - `simulation` → mock
  - `off` → None
  - `live` → the stub, whose unhealthy status makes the evaluator return `OP-PROVIDER-UNHEALTHY`. In the demo
    environment `HG-LIVE-DIAL-DEMO` blocks as well.
  - So no real call can start until a live provider is implemented, configured and explicitly enabled.
- Every attempt records `provider` and `simulated`.
- Connecting live Talk later means implementing `JeenTalkProvider` and the receiver's real signature check. The
  workflow, the evaluator, the gate and the tables stay as they are.

## 11. Change log
| Date | Owner | Change | Approved by |
|---|---|---|---|
| 2026-10-14 | setup | initial freeze | user (parallel workflow) |
| 2026-10-14 | Agent B (for the user) | demo-first scope: §4 existing sessions only; §6 no distinct approver; §7 no capabilities, If-Match/ETag or NL proposal; §8 reusable links, in-process Talk events + shared-secret receiver, override types pause/resume/cancel, one tick instead of job kinds; §10 mock via `webhook.apply`; §12 added | user ("demo-first scope simplification") |
| 2026-10-14 | Agent B, logged at G3 | additive, §5: `FollowupContext.live_sessions` (≥2 live sessions while ACTIVE = another device) and `FollowupContext.manual` (banker call-now); rule `OP-CALL-IN-PROGRESS`; `contract.merge_overrides(config, overrides)` (dicts merge, lists/scalars replace; pins apply only on top of a draft valid by itself). §1: `db.ADDED_COLUMNS["customer_presence"] = ["screen"]` (`"<screen>:<requirement_code>"`). Fixtures: the 18 timing-dependent scenarios pin the values their expectations depend on; hard-guard fixtures pin nothing (`38de807`) | user (Agent C's request; G3 go-ahead) |
| 2026-10-14 | Agent C, logged at G4 | additive, §7: `POST /api/admin/loan-completion/validate` `{kind, config}` (stateless report); extra `GET /settings` fields `locked_fields, rule_labels, prompt_variables, preview_variables, requirement_catalog, caller`; `POST /policy/simulate` takes `scenario_ids`; publish response adds `simulation_run_id`; validate report adds `lint, preview, against` (+ draft: `publishable, reasons, revision`). §9: `settings.draft_discarded.v1` in `SETTINGS_EVENTS` | user (Round 4) |
| 2026-10-14 | integration (G4) | additive, §6/§7: `POST /policy/as-configured` `{config? , version_id?, scenario_ids?}` → `{scenario_id: {pinned, decision}}` for the scenarios that pin timing values: the decision the configuration's own values produce. Display only (the simulator panel shows it as "בהגדרות הטיוטה"); `/policy/simulate` and the publish gate are unchanged and still a valid `SimulationRun` | user (G4: "simulator using actual policy values") |
| 2026-10-14 | Agent A, logged at G3 | §1, post-G2: documents dedupe per (case, sha256, requirement) — index `ux_documents_case_sha_req`, `DROPPED_INDEXES` + `db.migrate(conn)` (the `ADDED_COLUMNS` loop moved there); `repo.documents_by_sha` (list) replaces `document_by_sha` | user (Rounds 1–2 audit) |

## 12. Deferred (not built in Rounds 3–4; the integration path stays open)
| Deferred | Today instead | When it comes back |
|---|---|---|
| Editor/approver roles, the distinct-approver rule, persona switcher, capability checks on new routes | one demo admin on the existing staff session | bank SSO and roles |
| A separate staff session per console (`/admin` vs `/banker`) | the shared `mzl_staff` demo session | with SSO |
| `demo.simulate` capability for the presenter | demo routes open to the case's customer session or any staff session, in demo mode only | never in prod (demo routes are 404 outside demo) |
| `If-Match` / `ETag` / 428 | `revision` in the body; 409 when stale | if a real multi-editor admin is needed |
| NL policy proposal (FR-27, P1, `interpret-proposal`, `proposal.py`) | the structured editor | after the demo |
| `POST /prompts/test` through the agent loop | prompt lint + rendered preview | optional at G5 |
| HMAC v1 signature, ±300 s timestamp window, per-DATA_DIR secret file | in-process `apply`; the HTTP receiver is off unless `TALK_WEBHOOK_SECRET` is set | live JEEN Talk, per JEEN's actual spec |
| Single-use links (`used`, `used_at`) | reusable until expiry or resolution | production links (with OTP) |
| `TALK_LIVE_ALLOWLIST`, live-mode start-up refusal | `live` maps to a not-configured stub (`OP-PROVIDER-UNHEALTHY` + `HG-LIVE-DIAL-DEMO`) | live JEEN Talk |
| Job kinds `followup_evaluate`, `talk_mock_script`, `talk_reconcile` | `orchestrator.tick` + `on_event` | if load ever needs it |
| Override types `human_review`, `reschedule` | `pause`, `resume`, `cancel` | after the demo |
| Identity-verification screens | the `requires_identity_verification` flag in `CallRequest` only (Talk-side) | live JEEN Talk |
| Staging/prod behavior beyond the schema's environment checks | the demo environment | production |
