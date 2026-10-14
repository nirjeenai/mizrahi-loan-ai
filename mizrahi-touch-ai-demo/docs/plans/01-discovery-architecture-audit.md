# 01 — Discovery & Existing Architecture Audit (Mizrahi #2)

Verified against the code on 2026-10-13. Paths are relative to `mizrahi-touch-ai-demo/`.
Companion documents: [02 research](02-loan-process-research.md) · [03 PRD gaps](03-prd-gap-analysis.md) ·
[04 architecture](04-target-architecture-contracts.md) · [05 rounds](05-implementation-rounds.md) · [06 roadmap](06-roadmap-traceability.md).

## 1. Baseline (run in this session)

| Check | Command | Result |
|---|---|---|
| Backend tests | `cd backend && .venv/bin/python -m pytest -q tests` | **100 passed** (temp DATA_DIR, Gemini disabled) |
| Frontend typecheck | `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` | **clean** |
| Executive demo browser suite | REPLAY stack (see 05, Round 0) | recorded in `docs/plans/baseline/` |

## 2. What the application is today

One FastAPI process serves the API, an MCP server (`/mcp`) and the built React app:
`/customer` (Hebrew RTL, mobile-first phone frame with a presenter pane on desktop), `/banker` (three-pane review
desk) and `/system` (integration matrix). SQLite (WAL) with 13 tables, three in-process job workers, Gemini as the
only live review provider. Data is synthetic; the bank adapter is a mock (`authoritative=false`).

### 2.1 Document review pipeline (the core asset)
`UploadSheet` → `POST /api/cases/{id}/documents` (`api/routes.py`) → `engine.submit_document` (MIME, 15 MB,
SHA-256 dedupe) → job `review_document` → `GeminiReviewProvider._review_document`:
extract (blind classification + fields) → `_verify` (`review/evidence.py`: text-layer exact match or crop re-read)
→ `_deterministic` (`review/deterministic.py`: months, arithmetic, names/IDs, injection, pay date) → `_judge`
(LLM-as-judge per rubric criterion) → `_merge` (code precedence; verdict decided in code) → job `review_case`
(`review/case_review.py`: coverage, duplicates, identity, declared vs document income) →
`engine.reconcile_findings` → `workflow/readiness.compute` → `case_state`.

Hard-wired to payslips: `review/rubrics.py::for_document()` ignores the requirement and always returns
`payslip.il.salaried`; `prompts.FIELDS` is the payslip field list; readiness scope is `income_documents.payslips`;
`agent/actions.py` allows only `document_type: "PAYSLIP"`.

### 2.2 Persistence (`backend/app/db.py`)
`documents`, `review_runs`, `findings`, `statements`, `turns`, `audit`, `jobs`, `llm_calls`, `case_state`,
`handoffs`, `upload_intents`, `banker_decisions`, `customer_requests`. `tx()` = `BEGIN IMMEDIATE` under a process
lock. No migration framework: `ADDED_COLUMNS` for new columns on existing tables.

### 2.3 Jobs (`workflow/engine.py`)
`jobs(kind, idempotency_key UNIQUE, status, attempts, not_before, payload)`; kinds `review_document`,
`review_case`; 3 workers poll every ~0.6 s; 3 attempts with exponential backoff via `not_before`; startup
recovery. **`not_before` is a ready-made primitive for delayed follow-up jobs.**

### 2.4 Auth (`backend/app/auth.py`)
HMAC-signed session tokens in cookies `mz_customer` / `mz_staff` or Bearer. Roles: `customer` (bound to ≤8 case
ids) and `staff` (looked up in `bank.staff()`). Gates: `require_customer_case`, `require_staff`,
`require_assigned_staff`, `require_reader`, `require_case_actor`. **No capability/admin model.**

### 2.5 Agent and MCP
`agent/agent.py` Gemini function calling over one tool registry `agent/tools.py` (11 tools; MCP exposes 10 —
`offer_app_actions` is app-only). `agent/actions.py` `app_action.v1` buttons; `agent/continuation.py` writes one
follow-up turn after an assistant-initiated upload completes. `mcp/server.py` binds a bearer key to one case.

### 2.6 Frontend (`frontend/src`)
Routes in `App.tsx`; `caseContext.tsx` polls `GET /api/cases/{id}` + documents (`usePolling` 1.2 s busy / 4 s idle);
`api.ts` hand-written types for every endpoint. Single stylesheet `styles.css` with `--mz-*` tokens, RTL at
document level, `.ltr` helper, breakpoints 900/520/380 (hub) and 1360/1100 (desk).

## 3. Preservation audit — screens, components, workflows

Classification: **KEEP** (works, relevant) · **ADAPT** (keep implementation, change content/rules) · **EXTEND**
(keep behavior, add loan features) · **REPLACE** (justified).

| Feature | Files | Works today | Class | What changes | Regression guard |
|---|---|---|---|---|---|
| Phone shell, bottom nav, case drawer | `components/TouchShell.tsx` | yes | KEEP/ADAPT | labels only | screenshot + featured suite |
| Customer home | `pages/customer/Home.tsx` | yes | ADAPT | loan copy, amount, stage, banker role | screenshot, featured suite |
| Documents list + deep links (`?upload=&period=&focus=&request=&replace=`) | `pages/customer/Documents.tsx` | yes | EXTEND | requirement groups by family | featured suite, chat-action deep links |
| Document review + **Evidence Viewer** | `pages/customer/DocumentReview.tsx`, `components/EvidenceViewer.tsx` | yes | KEEP (+ per-family fields) | `MAIN` fields per family | REPLAY evidence boxes assertion |
| Upload sheet with live outcome | `components/UploadSheet.tsx`, `api/assistant.py` outcome | yes | EXTEND | doc type from requirement; presence events | featured suite upload steps |
| Home action card | `components/DocumentCheckCard.tsx` ↔ `readiness.customer_status` | yes | ADAPT/EXTEND | loan copy; follow-up controls | test_readiness, screenshot |
| Summary + recent updates | `DocumentSummary.tsx`, `RecentUpdates.tsx` | yes | ADAPT/EXTEND | family counts; follow-up events | screenshot |
| **Chat-to-action** (assistant, voice, `app_action.v1`) | `AssistantSheet.tsx`, `AssistantActions.tsx`, `agent/*` | yes | KEEP flow / ADAPT types | `document_type` union; loan system prompt | test_actions, test_guard |
| Request details, stages, meetings, tools | `pages/customer/Secondary.tsx` | yes | ADAPT | loan details/stages; illustrative calculator | screenshot |
| **Left-side presenter / test-case pane** | `App.tsx::HubSide`, `FeaturedScenarios.tsx`, `ScenarioPresenter.tsx`, `GET /api/presenter/*`, `workflow/demo.py` | yes | KEEP mechanism / ADAPT manifest / EXTEND controls | loan scenarios, server-side simulation controls | test_featured_demo (backend + e2e) |
| **Banker desk** queue · evidence · decision | `pages/banker/BankerConsole.tsx`, `ReviewWorkspace.tsx`, `DecisionPanel.tsx`, `api/banker.py`, `api/banker_package.py`, `workflow/review_desk.py` | yes | EXTEND | requirement matrix, Talk card, timeline, overrides | test_review_desk, banker screenshots |
| Banker conversation / technical views | `BankerConsole.tsx` `?view=` | yes | KEEP | — | screenshot |
| System page | `pages/system/SystemPage.tsx`, `routes.py::/system/*` | yes | EXTEND | Talk readiness, policy version, kill switch | screenshot |
| Browser voice | `voice.ts` | yes | KEEP | — | — |
| MCP server | `mcp/server.py` | yes | KEEP/EXTEND | `get_followup_context` tool | test_integration_closure, test_mcp_sdk |
| Mock bank case data | `bank/mock_bank.py` | yes | **REPLACE** content | mortgage → personal loan (ids kept) | all case tests updated |
| Rubric dispatch | `review/rubrics.py::for_document` | payslip only | **REPLACE** function body | dispatch by detected type | new tests |
| Readiness | `workflow/readiness.py` | payslip scope | EXTEND | requirement instances | test_readiness + new |

Decision recorded with the user (2026-10-13): **replace** mortgage content inside #2; Mizrahi #1 remains the
mortgage demo. Case ids `DEMO-MTZ-2026-00x` are kept ("MTZ" = Mizrahi-Tefahot, not mortgage) to keep tests,
presenter mapping and `localStorage` stable.

## 4. Reuse matrix (major PRD capabilities)

| Capability | Existing implementation | Decision | Required changes | Files | Risks |
|---|---|---|---|---|---|
| Loan case + requirements from config | mock cases + hard-coded `_OTHER_REQUIREMENTS` | Adapt + Build | versioned config, requirement engine, pinned set per case | `bank/mock_bank.py`, new `policy/`, `workflow/requirements.py` | requirement code compatibility (`PAYSLIPS:BRW-A` kept) |
| Upload + version history | `submit_document`, `upload_intents.replaces_document_id`, `REPLACED` status | Reuse | doc family on intent | `workflow/engine.py`, `review_desk.check_replacement` | none |
| Classification, extraction, evidence | Gemini pipeline (blind) | Reuse + Extend | per-family field sets, rubrics, deterministic checks | `review/*` | prompt change → REPLAY re-record |
| Reason codes + evidence | rubric `reason_code`, `DOC_FINDING_TEXT` | Extend | central catalog | new `review/reason_codes.py` | keep existing codes stable |
| Missing / wrong / undetermined | verdicts VALID/INVALID/NEEDS_REVIEW; outcomes PASS/REVIEW/BLOCKER | Reuse | map to PRD statuses | `workflow/outcomes.py` | — |
| Completion tasks | findings with `CUSTOMER_ACTION_REQUIRED` + `customer_requests` | Build on top | `completion_tasks` derived from findings/requirements | new `followup/tasks.py` | double source of truth → tasks derived, never edited by AI |
| In-app correction | Documents deep links, UploadSheet, DocumentCheckCard | Reuse | follow-up controls | frontend | — |
| Presence | none | Build | API + hook | new `followup/presence.py`, `presence.ts` | beacon reliability (hint only) |
| Policy engine | none | Build | pure evaluator | new `followup/policy.py` | — |
| Scheduler | `jobs.not_before` | Reuse | new job kinds | `workflow/engine.py::_claim` | worker starvation → kinds share claim order |
| Talk adapter | `JeenTalkVoice` slot (frontend, inbound voice) | Build | server-side `OutboundProvider` | new `comms/` | must not be confused with voice slot |
| Webhook | none | Build | signed receiver | new `comms/webhook.py` | replay, ordering |
| Secure links | Documents deep links + case-bound sessions | Reuse + Build | token table | new `followup/links.py`, `auth.issue` | token leakage in logs |
| Banker visibility | workspace, audit | Extend | Talk card, timeline | `api/banker_package.py`, `ReviewWorkspace.tsx` | layout overflow |
| Escalation | `handoffs`, `NEEDS_BANKER_REVIEW`, `request_banker_handoff` tool | Reuse | wire task ESCALATED | `review_desk`, `followup/orchestrator.py` | — |
| Admin settings | none | Build | config API + UI | new `policy/*`, `pages/admin/*` | RBAC must be server-side |
| Customize prompt | agent SYSTEM prompt constant | Build | prompt registry + test conversation reusing agent loop | `agent/agent.py`, `policy/prompts.py` | prompt-injection |
| Audit | `audit` table | Reuse | new actions | `store/repo.py` | volume |
| Demo test cases | presenter manifest + reset | Reuse + Adapt | loan manifest, sim controls | `fixtures/presenter/*`, `ScenarioPresenter.tsx` | golden set must stay unmodified |

## 5. Environment and isolation audit

| Risk | Evidence | Mitigation (Round 1) |
|---|---|---|
| **:8790 / :5190 belong to Mizrahi #1** | PID 36055 listening on :8790, cwd `/Users/nakash/Desktop/מזרחי/mizrahi-touch-ai-demo/backend`; #1's Vite dev port is 5190 | #2 uses backend `PORT=8791` and Vite 5192 (5191 is taken by an unrelated project); never touch :8790 |
| Vite proxy hard-coded to :8790 | `frontend/vite.config.ts` | read `MZ_API`, default `http://127.0.0.1:8791` |
| E2E defaults point at :8790 and reset cases | `e2e/test_journey.py`, `test_chat_actions.py`, `test_presenter.py`, `test_mcp_sdk.py`, `screens.py`, `backend/tests/live_journey.py`, `run.sh test` | defaults → :8791 |
| Copied venv console scripts | `.venv/bin/uvicorn` (and 21 others) start with `#!/Users/nakash/Desktop/מזרחי/.../.venv/bin/python3.12` | `run.sh` and the skill use `.venv/bin/python -m uvicorn`; `import app` resolves to the copy |
| Stale bytecode | copied `__pycache__` showed #1's paths in tracebacks | caches deleted; regenerated from the copy's sources |
| CORS | no CORS middleware: the app is same-origin (built SPA served by the backend; Vite proxies `/api`, `/mcp`) | nothing to change |
| Shared on purpose | `GEMINI_API_KEY` (same key as #1, confirmed by the user 2026-10-14) | Gemini quota/billing shared; hourly call budget is counted per DATA_DIR |
| Port-agnostic cookies `mz_customer`/`mz_staff` | `auth.py:30`; browsers scope cookies by host, not port | rename to `mzl_customer`/`mzl_staff` |
| Copied `backend/.env` | same size/timestamp as #1; content not readable (blocked) | user to regenerate `MCP_DEMO_KEY*` in the copy; Gemini key shared → combined hourly budget is per-DB |
| DATA_DIR, venv, node_modules | separate inodes, no symlinks | none needed |
| Git | no remotes, no commits | none |
| Production resources | none: synthetic data, mock bank, no telephony | Talk live mode refuses to start without credentials and allowlist |
