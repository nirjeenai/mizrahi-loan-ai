# Code map

Where to look, by topic. Paths are relative to `mizrahi-touch-ai-demo/`. Behavior and rationale live in
`README.md`; this file only routes you to code and lists what must change together.
Verified against the code on 2026-10-13. Update the entry in the same task when a responsibility moves.

## Request flow in one picture
```
UploadSheet.tsx → api.upload → POST /api/cases/{id}/documents            api/routes.py::upload
  → review_desk.check_request_link → engine.submit_document               (mime, 15 MB, SHA-256 dedupe per document family, file to DATA_DIR/uploads)
  → review_desk.link_upload · continuation.record_intent                  (answers a banker request · upload intent, never sent to the reviewer)
  → worker engine._run_document → registry.active() → GeminiReviewProvider._review_document
       extract (blind Gemini) → _verify (evidence.py) → _deterministic (deterministic.py) → _judge (Gemini) → _merge (verdict by code)
  → review_runs.result + audit → engine.request_case_review
  → worker engine._run_case → case_review.run → engine.reconcile_findings → readiness.compute → case_state
UI: caseContext.usePolling(GET /api/cases/{id}, /documents) → Home (DocumentCheckCard, DocumentSummary, RecentUpdates), Documents, DocumentReview+EvidenceViewer
```

## Backend (`backend/app/`)
| Topic | Start here | Then |
|---|---|---|
| Loan policy (versioned config) | `policy/schema.py` (LoanPolicy, TalkPrompt, bank envelope bounds) · `policy/store.py` (seed, drafts, ETag revision, atomic publish, rollback-as-new-version, diff) | seed files `backend/policy/seed/*.json`; table `config_versions` |
| Loan requirements | `workflow/requirements.py` (`pin`/`repin` → `case_profile`, `compose(case, policy)` — the one composition engine; `for_case`, `preview`, `profile`, `income_sources`, `family_of`, `payslip_months`) | `bank.requirements()` and `bank.case_context()` delegate here; conditions in `policy/schema.Condition` (employment · registration · entity · purposes); seed upgrade `policy/store.upgrade_from_seed` (lifespan) |
| Document profiles (Round 1) | prepared cases `bank/mock_bank.py::_USE_CASES` (101–106, `persona_id`, `use_case`, `applicant_type`, `banker_assisted`) | onboarding questionnaire `workflow/onboarding.py` ↔ `/api/demo/onboarding*` (`api/routes.py`), table `onboarding_drafts`; families without a rubric → `engine.submit_document` stores them (`status='stored'`), `readiness._human_requirement`, outcome `HUMAN_REVIEW_PENDING` |
| Non-payslip families | `review/family_checks.py` (ID, statement, proof of purpose, tax form) | rubrics `backend/rubrics/{id_document,bank_statement,purpose_proof,tax_form}.il.v1.0.0.json`; dispatch `rubrics.for_family`; reason texts `review/reason_codes.py` |
| Case coverage per family | `case_review._document_findings`, `_requirement_coverage` | coverage codes also in `engine.COVERAGE_CODES` / `review_desk.COVERAGE_CODES` |
| Follow-up engine (Round 3) | `followup/{policy,windows,tasks,presence,links,orchestrator}.py`, `clock.py`, `flags.py` | scenarios `backend/policy/scenarios/`; tables `completion_tasks, contact_plans, contact_attempts, policy_decisions, customer_presence, contact_preferences, case_overrides, upload_links`; routes `api/followup.py`; wired at G5 in `workflow/engine.py` (`followup_event`, `_tick_followups`) |
| Outbound contact | `comms/{contract,mock_talk,jeen_talk,registry,webhook}.py` | `provider_events`; contract `docs/plans/07-jeen-talk-handoff.md`; live plan `docs/plans/08-jeen-talk-live-integration.md` |
| Admin Settings (Round 4) | `api/admin.py` (drafts, validate, publish, simulate, `as-configured`, versions, rollback, kill switch, audit) | `policy/validate.py` (envelope, locked fields, publish gate), `policy/simulator.py` (changes together with `followup/contract.py` and the scenario fixtures), `policy/prompts.py` (lint, preview) |
| Demo intake | `workflow/intake.py` ↔ `GET/POST /api/demo/applications` (`api/routes.py`) | stored in `demo_applications`, read by `MockBankAdapter._applications` |
| App wiring | `main.py` (routers, SPA fallback, lifespan starts workers) | `config.py` (reads `backend/.env`, `DATA_DIR`, `SIMULATION_DATE`, MCP key→case map, `SESSION_*`, `DEMO_IDENTITY`, `DEMO_RESET`) |
| Sessions and access | `auth.py` (signed sessions, `require_customer_case` / `require_reader` / `require_staff` / `require_assigned_staff`, `/api/session` + demo-session routes) | every route in `api/*.py` calls one of these; demo identity on/off: `DEMO_IDENTITY` |
| Persistence | `store/repo.py` (all case data access) | `db.py` (13-table schema, `tx()`, `ADDED_COLUMNS`); job queue SQL in `workflow/engine.py`; LLM ledger in `llm/gemini.py` |
| Customer + system API | `api/routes.py` | customer projection: `CUSTOMER_SAFE_DETAIL`, `_customer_update`, `_customer_finding`; presenter + fixtures endpoints; `/system/*` |
| Assistant API | `api/assistant.py` | `POST /actions/resolve`, `GET /documents/{id}/outcome` |
| Banker API | `api/banker.py` (staff-session gate via `auth.py`, request models; conversation read; handoff acknowledge; confirm) | decisions → `workflow/review_desk.py`; queue/workspace (incl. open handoffs, lapsed confirmation) → `api/banker_package.py::build_workspace`; confirmation validity → `workflow/readiness.py::confirmation` |
| Banker transitions | `workflow/review_desk.py` (`TRANSITIONS`, `decide_document`, `decide_finding`, `request_missing`, `draft_*` templates, `@_serialized`) | derived banker status: `workflow/desk_state.py` |
| Durable jobs + findings | `workflow/engine.py` (`submit_document`, `_run_document`, `_run_case`, `reconcile_findings`, 3 workers, 3 attempts) | |
| Readiness | `workflow/readiness.py` (`compute` → AI state; `customer_status` → home card) | required months: `policy_months()` from case rubric + simulation date |
| PASS / REVIEW / BLOCKER | `workflow/outcomes.py` (`document_outcome`, `set_outcome`, `for_case`; derived on read, never stored) | exposed as `outcomes` in `GET /api/cases/{id}`, `outcome` in `GET /api/documents/{id}` and on banker workspace document items |
| Customer replacement | `review_desk.check_replacement` (validation before storing) · `upload_intents.replaces_document_id` · `desk_state.replacements(requests, case_id)` | `engine.reconcile_findings` supersedes only non-banker findings of a customer-replaced document |
| Executive demo reset | `workflow/demo.py::reset_executive_cases` ↔ `POST /api/presenter/demo-reset` (cases flagged `executive_demo`) | worker guards in `engine._run_document` / `_run_case` drop results for a reset case |
| Provider boundary | `review/contract.py` (Pydantic models, `ReviewProvider`) | `review/registry.py` (`REVIEW_PROVIDER`; `hybrid` raises) |
| Document review | `review/gemini_provider.py` | `review/prompts.py` (`PROMPT_VERSION`, response schemas), `review/evidence.py` (text-layer boxes, crops, witnesses), `review/deterministic.py` (months, amounts, names/IDs, injection, pay date) |
| Case review | `review/case_review.py::run` (coverage, duplicates, IS-04 income, `_semantic`) | `income_comparable()` decides which payslips feed IS-04; a customer-escalation criterion becomes a customer action only on FAIL (`DOC_FINDING_UNCERTAIN_TEXT` otherwise) |
| Rubrics | `backend/rubrics/<id>.v<semver>.json` | loader/validation: `review/rubrics.py` (`latest`, `for_document`, `for_case`) |
| Gemini client | `llm/gemini.py::generate` (hourly budget, retries on 429/5xx, ledger) | the only place that calls the Gemini API |
| Agent | `agent/agent.py` (loop, `guard_reply`, no-model fallback) | `agent/tools.py` (one tool registry for agent + MCP), `agent/actions.py` (`app_action.v1`), `agent/continuation.py` (upload outcome, follow-up turn) |
| MCP server | `mcp/server.py` (bearer key → one case, `additionalProperties: false`, 3,800-char results) | tools come from `agent/tools.py` |
| Bank (demo) | `bank/mock_bank.py` (cases 001–008, staff, stage dictionary, `authoritative=False`; 006–008 `executive_demo`) | `executive_demo_case_ids()` is the reset allow-list |
| VisionTrace | `review/visiontrace_provider.py` (stub + read-only probe + untested `map_envelope`) | BLOCKED; see README "VisionTrace" |

## Reason codes — where each lives
- Document-level codes: `reason_code` on each criterion in `backend/rubrics/payslip.il.salaried.v*.json`.
  Hebrew finding text per code: `review/case_review.py::DOC_FINDING_TEXT`.
- Case-level codes: emitted in `review/case_review.py` (`REQUIRED_PERIOD_MISSING`, `DUPLICATE_PERIOD`, `BORROWER_MISMATCH`,
  `DOCUMENT_NOT_VALID`, `DECLARED_VS_DOCUMENT_INCOME_VARIANCE`, plus `FILE_NAME_PERIOD_MISMATCH` and `IDENTITY_INCONSISTENT`,
  which are not in any rubric file).
- Also referenced by name in `workflow/engine.py` and `workflow/review_desk.py` (`COVERAGE_CODES`), `api/banker_package.py`,
  `frontend/src/components/ScenarioPresenter.tsx`, `fixtures/presenter/presenter_scenarios_manifest.json`, and the tests.
- There is no central reason-code catalog in this app (`visiontrace-mortgage-spec/…/reason_codes.json` is spec-only).

## Frontend (`frontend/src/`)
| Topic | Files |
|---|---|
| Routes | `App.tsx` (`/customer/*`, `/banker`, `/system`; `HubSide` = desktop side pane) |
| API client + types | `api.ts` (every endpoint, hand-written types mirroring backend JSON, `usePolling`, `ils`/`monthHe`/`timeHe`, Hebrew label maps) |
| Case state | `caseContext.tsx` (selected case in `localStorage` `mz.case`, polling, `stale` after two failed refreshes, assistant/upload sheet state) |
| Customer screens | `pages/customer/Home.tsx` (greeting, bank stage card, banker card, layout), `Documents.tsx` (requirements, banker requests, upload entry, `?request=` / `?upload=` / `?focus=` deep links), `DocumentReview.tsx` (verdict, criteria, evidence), `Secondary.tsx` (request details, stages, meetings, tools) |
| Customer components | `components/TouchShell.tsx` (phone frame, bottom nav, case-picker drawer), `DocumentCheckCard.tsx` (home action card ↔ `readiness.customer_status`, open requests, `available_actions` upload targets), `DocumentSummary.tsx` (per-borrower months, uploaded/reviewed/accepted/fulfilled counts, secondary upload), `RecentUpdates.tsx` (customer wording of audit events, display-only folding, full list), `UploadSheet.tsx` (upload + live outcome), `EvidenceViewer.tsx` (page image + boxes), `AssistantSheet.tsx` + `AssistantActions.tsx` (chat, voice, action buttons), `StageRing.tsx` (`compact` for the home stage card), `Icons.tsx` |
| Voice | `voice.ts` (`VoiceChannel`, `BrowserVoice`, `JeenTalkVoice` slot; `?voice=server`) |
| Presenter pane | `App.tsx::HubSide` + `CustomerApp` (collapsible panel: starts collapsed, toggle `presenter-toggle`, docked ≥1000px / drawer below / phone via the menu's `drawer-presenter`; `.hub*` and `.presenter-toggle` in `styles.css`; stays mounted when collapsed; toggle and backdrop excluded from presence in `presence.ts`; checked by `e2e/check_presenter_layout.py`) · `components/FeaturedScenarios.tsx` (four featured cards from manifest `featured`, `FixtureRow` — one downloadable file: label, slot, small file name, compact download — `NewDemoButton`, open cards in `mz.presenter.featured.v1`) · `components/ScenarioPresenter.tsx` (11 scenarios inside the collapsed "כל תרחישי הבדיקה", their `items`, the unreferenced files under "קבצים משלימים", marks in `mz.presenter.marks.v1`) ↔ `GET /api/presenter/scenarios`, `/api/presenter/file` (manifest-listed, SHA-checked, under `fixtures/`), `POST /api/presenter/demo-reset`. Labels, owners, periods, slots and instructions come only from the manifest (`fixtures/loan/build_manifest.py`), never from parsing file names. |
| Banker console | `pages/banker/BankerConsole.tsx` (case bar; `?view=` review · conversation · technical), `ReviewWorkspace.tsx` (queue + evidence + confirmation), `DecisionPanel.tsx` (all decision forms), `deskUi.tsx` (`newRequestId`, shared UI); the console obtains its staff session itself (`BankerConsole.tsx`) |
| System page | `pages/system/SystemPage.tsx` (integrations, MCP self-test, rubrics) |
| Styles | `styles.css` (single stylesheet, `--mz-*` tokens, `.ltr` for IDs/numbers in RTL) |
| Follow-up UI (G5) | `presence.ts` (`usePresence` in `TouchShell`, `reportPresence` from `UploadSheet`) · `followupApi.ts` · `components/FollowupNotice.tsx` (home) · `pages/customer/Link.tsx` (`/customer/link#t=`) · `pages/banker/FollowupView.tsx` (console tab "מעקב השלמה") · `components/FollowupSimControls.tsx` (presenter) · `pages/admin/*` + `adminApi.ts` + `admin.css` (`/admin`, Agent C) · tab "ביצועים ותובנות" (synthetic illustration only, no API): `insightsData.ts` (the one dataset) → `InsightsDashboards.tsx` (`DashSwitch`, `?dash=v2`) → V1 `InsightsTab.tsx` (`.ins-*` in `admin.css`) or V2 `InsightsV2.tsx` (`.ins2-*` in `insightsV2.css`) |
| Document profiles (Round 1) | `components/UseCaseScenarios.tsx` (six TC↔UC cards from manifest `useCases`, first in the presenter; the 15 earlier scenarios under `more-tests` "בדיקות נוספות" in `App.tsx::HubSide`) · `TouchShell.tsx::Drawer` ("התיקים שלי" = the open case's `persona_id`) · `Documents.tsx::ProfileCard` + `uploadable` · `pages/customer/Apply.tsx` (JEEN questionnaire) |
| Loan screens | `pages/customer/Documents.tsx::LoanDocRow` (one-document requirements, owner / why / alternatives, human-review note), `pages/customer/Apply.tsx` (onboarding chat, `/customer/apply`), `UploadSheet.tsx` (`initialRequirement`, type chips), `ReviewWorkspace.tsx::RequirementMatrix`, `EvidenceViewer.MAIN` (all families' fields) |

## Change together
- Backend response shape (routes, banker_package, readiness, tools) ↔ types and methods in `frontend/src/api.ts`.
- New customer-visible field from banker data ↔ customer projection in `api/routes.py` (never leak rationale).
- New customer-visible audit action ↔ `CUSTOMER_UPDATES` in `api/routes.py` ↔ wording in `RecentUpdates.describe` (home timeline).
- Rubric criterion or reason code ↔ `deterministic.py` / `gemini_provider.py` (`_deterministic`, `_judge`, `_merge`) ↔
  `case_review.DOC_FINDING_TEXT` ↔ tests ↔ presenter manifest expectations ↔ README "Rubrics".
- Prompt or response schema in `review/prompts.py` ↔ bump `PROMPT_VERSION`.
- New column on an existing table ↔ `db.ADDED_COLUMNS`.
- Agent tool ↔ MCP catalog (same registry) ↔ `e2e/test_mcp_sdk.py` tool-count check.
- Fixture PDFs ↔ SHA-256s in `fixtures/out/manifest.json` / presenter manifest.
- Featured scenarios (`featured` in the presenter manifest) ↔ executive demo cases in `mock_bank.py` ↔ `e2e/test_featured_demo.py` ↔ `backend/tests/test_featured_demo.py`.
- Use cases (`useCases` in `fixtures/loan/build_manifest.py`) ↔ `mock_bank._USE_CASES` ↔ the seed policy ↔ `backend/tests/test_document_profiles.py` (checklists asserted against `compose`) ↔ `e2e/check_document_profiles.py`.
- A new document family ↔ `policy/schema.Family` ↔ `requirements.FAMILY_HE` ↔ `frontend/src/api.ts::FAMILY_HE` ↔ Admin `DocumentsTab.tsx` (`FAMILY_HE`, `AI_FAMILIES`); without a rubric it is human-review intake.
- A new golden file in a featured scenario ↔ a REPLAY entry: `backend/.venv/bin/python e2e/replay/build_recordings.py`.
- Presenter scenario or fixture label ↔ `fixtures/loan/build_manifest.py` (then run it) ↔ the PDF's own text (never its file
  name) ↔ `e2e/verify_presenter_scenarios.py` (REPLAY) ↔ `e2e/check_presenter_labels.py` (browser) ↔ the manifest tests in
  `backend/tests/test_featured_demo.py`.
- Outcome rules (`workflow/outcomes.py`) ↔ labels in `DocumentReview.tsx` (`OUTCOME_TONE`), `UploadSheet.tsx`, `DocumentCheckCard.tsx`.

## Demo data and fixtures (`fixtures/`)
- `world.json` (ground truth) + `generate.py` → `out/main/` (initial set + corrected September), `out/negative/` (4 edge cases), `out/manifest.json` (served by `GET /api/fixtures`).
- `pay_date/` — PS-10 regression payslips. `presenter/presenter_scenarios_manifest.json` (generated by `loan/build_manifest.py`: 4 featured, 11 scenarios, 25 documents from `presenter/loan_set/`, `presenter/golden_set/` and `out/`) + `presenter/golden_set/` (unmodified golden set; never edit).
- Cases: 001 Lavi demo · 002 second case (MCP key 2) · 003 Lavi QA (negative files) · 004 golden profile (scenarios 01, 02, 10) · 005 golden QA (03–09) · 006–011 executive demo · 101–106 the six use cases UC-01…06 (TC-01…06); "התחל דמו חדש" wipes 006–011 and 101–106 only.
- `e2e/replay/recordings.json` (built by `e2e/replay/build_recordings.py`): REPLAY model answers by file SHA-256 — `RECORDED_LIVE` for the golden payslips, `AUTHORED` (labelled) for the bank statement.

## Tests
| Test | Covers |
|---|---|
| `backend/tests/test_deterministic.py` | `review/deterministic.py`, `review/evidence.py` |
| `backend/tests/test_pay_date.py` | PS-10 rule, IS-04 income selection (`case_review`, `gemini_provider`) |
| `backend/tests/test_readiness.py` | `readiness.customer_status`, `policy_months` |
| `backend/tests/test_actions.py` | `agent/actions.py`, `agent/continuation.py` |
| `backend/tests/test_guard.py` | `agent.guard_reply` |
| `backend/tests/test_review_desk.py` | banker desk end-to-end through real routes (`TestClient`), seeding reviews via `repo` |
| `backend/tests/test_integration_closure.py` | QA findings G-01…G-13: sessions and case isolation, staff-only data, projections, retry/reset gates, confirmation lapse, withdrawal, handoffs, missing-request guard, replaced payslip, atomic decision+audit |
| `backend/tests/test_featured_demo.py` | cases 006–008, PASS/REVIEW/BLOCKER outcomes, customer replacement, uncertainty routing, demo reset, worker guards, golden-set independence |
| `e2e/replay_backend.py` + `e2e/test_loan_journey.py` | REPLAY stack (Gemini transport only replaced; judge answers per rubric) and the loan browser suite — zero Gemini calls |
| `backend/tests/test_document_profiles.py` + `e2e/check_document_profiles.py` | six use cases ↔ manifest, profile composition, personas, human-review intake, onboarding (REPLAY browser suite) |
| `backend/tests/test_loan_review.py`, `test_recorded_reviews.py`, `test_intake.py` | loan requirements, family checks, coverage gaps, wrong type, the real provider on recorded LIVE answers, intake |
| `e2e/replay/record_live.py` | records LIVE Gemini answers for new fixtures (paid; only with the user's OK) |
| `e2e/coexistence_check.py` | #2 (:8791/:5192) next to #1 (:8790): every request stays on #2's origin |
| `e2e/*.py` | browser suites (real Chrome, mostly real Gemini) — ports, env vars and resets in `.claude/skills/run-stack/SKILL.md`; `e2e/demo_auth.py` gives their API calls sessions |
| `backend/tests/live_journey.py` | not a test: uploads scenes to a running backend (real Gemini) |
