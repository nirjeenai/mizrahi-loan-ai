# Agent B notes — Round 3 follow-up engine

## G1 (evaluator + fixtures) — `parallel/g1-evaluator`
- `followup/policy.py::evaluate(ctx, policy, now)`: pure. It imports only `followup/windows.py` (calendar math) and
  the contract. The tier order and its two documented exceptions are in the module docstring:
  - a customer callback replaces grace, the configured spacing and the per-case daily cap;
  - a manual call skips grace and turns every deferral into a BLOCK.
- `followup/windows.py`: Asia/Jerusalem windows, holidays and DST, with the envelope applied on top. `clock.py`
  re-exports it.
- `backend/policy/scenarios/*.json`: 39 fixtures, one per decision scenario in 03 §5 (S01–S18, S20–S28, S33–S37)
  plus variants (`S06-gate`, `S10-no-redial`, `S11-shabbat`, `S11-holiday`, `S11-dst`, `S12-unverified`,
  `S24-allowed`). The 24 fixtures under S01–S18 are `mandatory`. Expectations were written by hand from 03 §5.
  `now` is Tuesday 2026-10-13 11:00 Israel time unless stated.
- **Fixture pinning (Agent C's request):** the 18 timing-dependent fixtures pin the values their expectations depend
  on (grace, nudge, unknown-presence extra, statement extension, spacing, caps, call window, holidays, reconcile
  delay). Hard-guard fixtures pin nothing and run on the draft as edited. `merge_overrides` applies pins only on top
  of a draft that is valid by itself, so pins never repair an invalid draft (it stays CFG-INVALID). Tests:
  `test_fixtures_pin_only_timing_values`, `test_ordinary_edits_keep_every_scenario_green`,
  `test_fixture_overrides_cannot_bypass_hard_guards`, `test_pins_never_repair_an_invalid_draft`.
- Simulator recipe (what `test_followup_policy.py` does):
  `schema.parse("loan_policy", contract.merge_overrides(config, s.policy_overrides))`, where a `ValidationError`
  means `policy=None`, then `evaluate(s.context, policy, s.now)`, then `contract.matches(s.expect, d)`.

## Contract additions to log in CONTRACTS §11 at merge (additive; the user asked to stop editing shared docs)
- `followup/contract.py`:
  - `FollowupContext.live_sessions: int = 0`: ACTIVE with ≥2 live sessions means "another device" (S17 SUPPRESS vs
    S03 WAIT).
  - `FollowupContext.manual: bool = False`: a banker's call-now (S24).
  - Rule `OP-CALL-IN-PROGRESS` (OPERATIONAL).
  - `merge_overrides(config, overrides)`: dicts merge; lists and scalars replace. Agent C's simulator should use it.
- `db.ADDED_COLUMNS`: `"customer_presence": ["screen"]` (TEXT, `"<screen>:<requirement_code>"`). It lets the
  evaluator tell "on the screen that fixes the task" (S01) from "elsewhere in the app" (S03).

## Round 3 backend — what exists
| Module | Responsibility |
|---|---|
| `clock.py` | `now()` = wall + demo offset (demo only), `advance/set_to/reset/state`, `environment()` (`APP_ENV`, default demo) |
| `followup/tasks.py` | one open task per (case, requirement, reason) from open customer-action findings + banker requests (merged, banker wording); `verified` = no banker item / failed review on the requirement; RESOLVED only by a new passing document, else CANCELED |
| `followup/presence.py` | per-session rows, seq ordering, TTL → UNKNOWN, idle after 60 s / hidden tab, picker 3 min, upload until completed, review-in-flight from `jobs`/`documents` |
| `followup/links.py` | 32-byte token, SHA-256 stored, `demo_token` in demo only, TTL from `talk.link_ttl_minutes`, reusable until expiry/resolution |
| `followup/orchestrator.py` | `context`, `on_event`, `tick`, the pre-dispatch gate (one `db.tx()`: re-read, re-evaluate, attempt + idempotency key + link), `_send` after commit (kill switch re-checked), Talk outcomes, kill-switch cancellation, manual call, overrides, derived case status, customer/banker/timeline views |
| `comms/contract.py` · `mock_talk.py` · `jeen_talk.py` · `registry.py` · `webhook.py` | provider boundary; mock script DIALING→CONNECTED→outcome via `webhook.apply`; live stub (not configured); `talk.mode` → provider; receiver (dedupe, forward-only ranks, finals kept, orphans) |
| `api/followup.py` | every CONTRACTS §8 route with the existing session checks |

Behavior choices worth knowing:
- **No presence on record:** grace counts from the oldest open task's creation, so a customer who never opened the
  app is not called the moment a review finishes.
- **Plan states:**
  - WAIT, SUPPRESS and SNOOZE → WAITING.
  - IN_APP_* → IN_APP.
  - BLOCK → PAUSED (banker), CANCELED (kill switch, opt-out, no consent or case closed while a contact was pending)
    or BLOCKED.
  - AWAITING_CUSTOMER persists through waits after a completed contact.
- **The tick** re-evaluates plans that are due, plus IN_APP, BLOCKED and PAUSED plans every pass (presence can
  expire without any event). It also picks up plans the kill switch cancelled, once the switch is off.
- **Decision rows:** `policy_decisions` gets a row for every non-tick evaluation, and for a tick evaluation only
  when the decision changed (otherwise every tick would write one).
- **A provider failure** ends the attempt as FAILED (it counts toward caps). Documents are never touched (AC 13).
- **`override: cancel`** = a pause that also cancels a call already under way. `resume` revokes pause, cancel and
  human_requested.
- **The link URL** is `${PUBLIC_BASE_URL}/customer/link#t=<token>`. The landing page is Agent A's at G5: it should
  `POST /api/links/redeem` and navigate to `target`.

## G5 wiring (on `main`, after G3)
1. `workflow/engine.py`:
   - in the worker loop, call `followup.orchestrator.tick(clock.now())` every ~5 s, in one worker only and after
     document jobs (no new job kinds; `_claim` unchanged);
   - after a document review and after a case review: `orchestrator.on_event(case_id, "review_finished")`;
   - after an upload is accepted: `orchestrator.on_event(case_id, "document_uploaded")`.
2. `agent/tools.py`: `get_followup_context(case_id)` returns `orchestrator.customer_view` + open tasks. Read-only;
   the MCP tool count goes 10 → 11 in `e2e/test_mcp_sdk.py`.
3. `/system` integration row: "JEEN Talk — SIMULATION (mock-talk); live slot not configured".
4. Agent A's frontend:
   - the presence hook (session_started/heartbeat 30 s/user_activity throttled/file_picker_opened/upload_*/
     session_ended via `sendBeacon`, `seq` per tab);
   - `/customer/link` landing; snooze, preference and "talk to a banker" controls;
   - the banker Talk card from `GET /api/banker/cases/{id}/followup` and the timeline;
   - presenter buttons: customer-left, clock +N / next window, tick, talk-outcome, sent-links.
5. Optional: move `APP_ENV` and `PUBLIC_BASE_URL` into `config.Settings`.

## README / CODEMAP text (draft)
- **README › Follow-up engine (Round 3):**
  - "When a customer leaves a correction unfinished, the server decides — in code, with rule ids and a Hebrew
    reason — whether to wait, nudge in the app, schedule a call or block. The customer is never called while active
    in the app or while an upload or review is running. Calls go through `OutboundProvider`: in this demo a
    simulated JEEN Talk (`mock-talk`) that never dials, posts the same status events a live provider would, and
    sends a secure upload link. A corrected upload that passes review resolves the task and cancels further contact.
    The demo clock (`POST /api/demo/clock`, demo only, audited) makes grace periods and call windows demonstrable."
  - Known limitations: no live Talk; the receiver uses a shared secret only; links are reusable within their TTL.
- **CODEMAP rows:**
  - "Follow-up engine | `followup/{policy,windows,tasks,presence,links,orchestrator}.py`, `clock.py` | scenarios
    `backend/policy/scenarios/`; tables `completion_tasks, contact_plans, contact_attempts, policy_decisions,
    customer_presence, contact_preferences, case_overrides, upload_links`"
  - "Outbound contact | `comms/{contract,mock_talk,jeen_talk,registry,webhook}.py` | `provider_events`; route
    `api/followup.py`"

## Open questions
- `APP_ENV` and `PUBLIC_BASE_URL` are read from the environment by follow-up code and are not in `config.py`.
- `docs/plans/07-jeen-talk-handoff.md` (optional) was not written. The handoff points are in `comms/contract.py`
  and `jeen_talk.py`.
