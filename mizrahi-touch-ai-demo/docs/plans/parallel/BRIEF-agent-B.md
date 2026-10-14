# Agent B — Round 3 follow-up engine (backend)

You are Agent B on Mizrahi #2 (the loan completion demo). Two other agents work in parallel; you own only the files
listed below.

- **Your worktree:** `/Users/nakash/Desktop/mizrahi2-agentB`
- **Your branch:** `agent-b/round3-followup`
- **Base:** `parallel/base`

## Before anything
1. Open the worktree as your workspace. In every shell, run `. /Users/nakash/Desktop/mizrahi2-agentB/AGENT_ENV.sh`.
2. Read these, in order:
   - `mizrahi-touch-ai-demo/docs/plans/parallel/README.md` (ownership, gates)
   - `docs/plans/parallel/CONTRACTS.md` (frozen; you implement §4, §5, §8, §9 and §10)
   - `docs/plans/03-prd-gap-analysis.md` §5 (scenarios S01–S42)
   - `docs/plans/04-target-architecture-contracts.md` §4–§7, §10–§11
   - `CLAUDE.md` (boundaries that must hold)
3. Check the baseline: `cd mizrahi-touch-ai-demo/backend && .venv/bin/python -m pytest -q tests --ignore=tests/test_recorded_reviews.py`.
   You should see **121 passed** (8 of them are `test_parallel_contracts.py`). `test_recorded_reviews.py` fails only
   because its recordings are excluded from the snapshot. Ignore it.

## Goal
Deliver the follow-up loop as a backend, driven entirely by the server and testable with a fixed clock:
self-service in the app → grace period → simulated call → secure link → corrected upload → ready for the banker.

## Build this, in this order
1. **`backend/app/clock.py`:**
   - `now()` returns aware UTC plus the demo offset (`flags.DEMO_CLOCK_OFFSET`, demo environment only); `now_iso()`.
   - Asia/Jerusalem helpers: `in_window(dt, call_window, holidays)`, `next_window_start(dt, …)`.
   - Use `zoneinfo`. Cover Shabbat, the config's holidays, and the DST change on 2026-10-25.
2. **`backend/app/followup/policy.py`:** `evaluate(ctx, policy, now) -> Decision`, exactly as in CONTRACTS §5.
   - Pure: no imports of `db`, `clock` or `flags`.
   - Precedence: hard guards, then operational, then config, then preferences.
   - Every Decision carries Hebrew `explanation_he`, `rule_ids` and `blocked_by`.
   - Respect `ENVELOPE` even when a policy is more permissive.
3. **`backend/policy/scenarios/*.json`:** one fixture per decision scenario in 03 §5: S01–S18, S20–S28, S33–S37.
   Mark the PRD §8.9 scenarios (S01–S18) `"mandatory": true`. **Then gate G1:**
   - make `test_followup_policy.py` (every fixture through `evaluate` + `contract.matches`) and the contract tests
     green;
   - commit with a message starting `G1:`;
   - run `git branch -f parallel/g1-evaluator HEAD`;
   - tell the user G1 is reached. Agent C is waiting on it.

   After G1, the `evaluate` signature and the fixture format are final. Fixes are new commits, then move the ref
   forward again.
4. **`followup/tasks.py`:**
   - Derive completion tasks from open `CUSTOMER_ACTION_REQUIRED` findings and readiness requirements.
   - One open task per `(case, requirement_code, reason_code)`; a banker request and an AI task on the same
     requirement merge into one (S29).
   - A task resolves only when a new document for its requirement passed review.
   - Unverified (UNDETERMINED) issues route to human review, never to contact.
5. **`followup/presence.py`:**
   - Per-session rows; `seq` ordering; TTL from the policy.
   - Aggregate across tabs and devices: ACTIVE beats IDLE beats UNKNOWN beats ENDED.
   - Picker and upload flags. Upload and evaluation in flight are derived from `jobs` and `documents`.
6. **`backend/app/comms/`:**
   - `contract.py` (CONTRACTS §10 dataclasses + `OutboundProvider` protocol)
   - `mock_talk.py` (never dials; scripted steps produce signed events)
   - `jeen_talk.py` stub (not configured)
   - `registry.py`
   - `webhook.py`: HMAC v1 signature, ±300 s timestamp, dedupe on `provider_events.event_id`, forward-only ranks,
     orphan → 202 + `integration.reconciliation_required.v1`
7. **`followup/links.py`:**
   - A 32-byte token; only the SHA-256 is stored; scoped to case + tasks; expiry from `talk.link_ttl_minutes`;
     single use.
   - `demo_token` is written only in the demo environment.
   - Redeem returns `ok|resolved|expired|used|invalid` and issues a case-bound customer session (`auth.issue` +
     `auth._set`; a public helper comes at G5).
8. **`followup/orchestrator.py`:**
   - `context(case_id, now)` builds `FollowupContext` from the database.
   - `tick(now)` / `run_due(now)` / `on_event(case_id, trigger, now)`.
   - A single contact plan per case, with consolidation.
   - The **atomic pre-dispatch gate**: re-read state and re-evaluate inside one `db.tx()`, and create the attempt
     with its idempotency key in the same transaction.
   - Write a `policy_decisions` row per evaluation and `case_events` per transition (`events.emit(..., conn=c)`).
   - Kill switch: the next evaluation and the gate both block; queued plans are cancelled.
   - The derived case status (`FOLLOWUP_IN_PROGRESS` / `AWAITING_CUSTOMER`).
9. **`backend/app/api/followup.py`:** every route in CONTRACTS §8 (customer, banker, webhook, demo), with
   permissions from §4.
   - The customer projection contains no rule ids, attempts, policy versions or banker text.
   - The demo routes return a "סימולציה" label.

## Allowed files (relative to `mizrahi-touch-ai-demo/`)
- `backend/app/clock.py`
- `backend/app/followup/**`, where `contract.py` is additive only: you may add rule ids and fields with defaults,
  but not rename anything
- `backend/app/comms/**`
- `backend/app/api/followup.py` (already mounted in `main.py`)
- `backend/app/capabilities.py`, `flags.py`, `events.py` (append to `DOCUMENT_EVENTS`/`FOLLOWUP_EVENTS` only)
- `backend/policy/scenarios/**`
- New tests: `backend/tests/test_followup_policy.py`, `test_followup_flow.py`, `test_talk_webhook.py`,
  `test_upload_links.py`, `test_clock.py` (and other `test_followup_*.py`)
- `docs/plans/parallel/NOTES-agent-B.md`: what README and CODEMAP need at G5, open questions, any contract change
  request
- Optional, after everything else: `docs/plans/07-jeen-talk-handoff.md`
- Additive only:
  - `backend/tests/test_parallel_contracts.py`
  - `CONTRACTS.md` §11
  - one new line in `db.ADDED_COLUMNS` (log it in §11)

## Forbidden
- Every other file. In particular: `workflow/*` (including `engine.py`; job wiring is G5), `review/*`, `agent/*`,
  `mcp/*`, `auth.py`, `db.py` (except the line above), `main.py`, `config.py`, `util.py`, `policy/schema.py`,
  `policy/store.py`, `policy/seed/*`, `api/{routes,banker,banker_package,assistant,admin}.py`, `bank/mock_bank.py`,
  all of `frontend/`, `e2e/`, `fixtures/`, `rubrics/`, existing tests, `conftest.py`, `loan_helpers.py`, README,
  CODEMAP, `CLAUDE.md`, `run.sh`.
- Agent C's files: `api/admin.py`, `policy/{validate,simulator,prompts,proposal}.py`, `pages/admin/*`.
- Agent A's tree `/Users/nakash/Desktop/מזרחי copy`, Mizrahi #1 `/Users/nakash/Desktop/מזרחי` (files, venv,
  ports 8790/5190), and ports 8791/5192/8798/5846/8801/8797/5858.
- Any Gemini call, creating `backend/.env`, `pip`/`npm` installs, `git push/rebase/reset --hard/stash/checkout`,
  merging anything, and touching `main`.
- Real JEEN Talk: the mock provider only. `jeen_talk.py` stays a stub.

If you need something outside your files, write it in `NOTES-agent-B.md` as a G5 item and work around it with a
seam (a function argument, a fixture). Don't edit the file.

## Tests you must add (map to 06-roadmap-traceability.md)
- **`test_followup_policy.py`:** every scenario fixture, plus property checks:
  - a hard guard always wins;
  - `policy=None` gives `CFG-INVALID`;
  - envelope clamps hold;
  - `explanation_he` is never empty;
  - covers P01–P29.
- **`test_talk_webhook.py`:** valid signature; bad or missing signature → 401; stale timestamp; duplicate
  `event_id` → `duplicate`; lower rank → `ignored`; a final status is never overwritten; orphan → 202 + event
  (W01–W06).
- **`test_upload_links.py`:** the token is never stored in clear; single use; expired; resolved (L01); used and
  expired (L02); the session is bound to one case; another case is 403.
- **`test_followup_flow.py`** (through `TestClient` and `tests/loan_helpers.py`, case `DEMO-MTZ-2026-009`):
  - one task per issue (AC 6) and consolidation;
  - customer leaves → grace → tick → scheduled → gate → mock call → `LINK_SENT` → link redeem → corrected upload
    (stored review via `loan_helpers.family_review`) → task resolved, plan COMPLETED, status `READY_FOR_BANKER`
    (AC 10–11);
  - kill switch blocks; opt-out mid-plan cancels;
  - case 010 (no consent) is blocked with a reason;
  - a manual call under opt-out → 409;
  - the customer projection has no internals;
  - RBAC: no session 401, wrong capability 403, unassigned banker 403;
  - Talk failure does not block uploads (AC 13).
- **`test_clock.py`:** offset, call window, Shabbat, holiday, DST.

## Definition of done
- [ ] G1 reached and reported (ref `parallel/g1-evaluator`).
- [ ] Every CONTRACTS §8 route works; the four test files above plus `test_clock.py` pass.
- [ ] `.venv/bin/python -m pytest -q tests --ignore=tests/test_recorded_reviews.py` passes in full: the 121
      baseline tests plus yours.
- [ ] `python3 docs/plans/parallel/check_scope.py B` prints `OK`.
- [ ] No Gemini call made: `grep -c . $DATA_DIR/*.jsonl` is absent or 0; tests disable Gemini.
- [ ] Optional smoke: start `uvicorn` on :8796 with your `DATA_DIR` and exercise the demo routes with `curl`.
- [ ] `NOTES-agent-B.md` lists the G5 wiring (engine job kinds, triggers, MCP tool, `/system`, README/CODEMAP text).
- [ ] Everything is committed on `agent-b/round3-followup`; nothing pushed or merged.
- [ ] Report the commands you ran and their output. Label anything not run as not verified.

## Runtime
- Backend: `cd mizrahi-touch-ai-demo/backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port $BPORT`
  (`DATA_DIR` comes from `AGENT_ENV.sh`; run it in the background).
- Stop it: `lsof -tiTCP:$BPORT -sTCP:LISTEN | xargs kill`.
- Demo sessions for `curl`: `POST /api/session/demo/staff {"staff_id":"STAFF-DANA"}` /
  `POST /api/session/demo/customer {"case_id":"DEMO-MTZ-2026-009"}`.
