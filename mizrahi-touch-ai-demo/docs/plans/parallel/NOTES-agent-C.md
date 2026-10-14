# Agent C notes — Round 4 Admin Settings

Status 2026-10-14: Round 4 is built and tested on `agent-c/round4-admin`, including the G1 work (merged
`parallel/g1-evaluator` = `4adf7fa` with the user's go-ahead): `policy/simulator.py`, `POST /policy/simulate`, the
mandatory-scenario publish check, and the simulator panel.

## Request to Agent B (approved by the user): pin config-dependent values in mandatory fixtures
The publish gate runs every fixture against the draft (CONTRACTS §6). Several mandatory fixtures assume the seed
values without stating them, so ordinary edits fail them and can't be published:

| Edit | Mandatory fixtures that fail |
|---|---|
| grace 20 → 30 (or → 5) | S04, S05, S16 |
| idle nudge 5 → 10 | S04 |
| unknown-presence extra 10 → 20 | S16 |
| call window from 09:00 → 10:00 | S11, S11-dst, S11-holiday, S11-shabbat |
| (non-mandatory) max attempts 2 → 3 | S21 |

The fix is in the fixtures only: put each value an expectation depends on into its `policy_overrides`. For example,
S05 gets `{"followup": {"abandonment_grace_minutes": 20}}`. Then:
- the scenario still runs against the draft for everything it doesn't pin;
- hard-guard scenarios still catch any draft that would contact a customer it mustn't;
- normal edits publish.

`e2e/test_admin_ui.py` handles both states. Until the pinning lands, it checks that the gate refuses the grace edit
and then publishes a change no fixture depends on (`min_hours_between_calls`). After the pinning, it publishes the
grace edit directly.

## What exists
| Area | Where | Notes |
|---|---|---|
| Admin API | `backend/app/api/admin.py` | Every CONTRACTS §7 route. All routes use `auth.require_staff`. `/prompts/test` returns 501. |
| Simulator | `backend/app/policy/simulator.py` | `run` (pure), `simulate` (one `simulation_runs` row + one event), `mismatch_he` (which part of an expectation failed), following Agent B's recipe (`merge_overrides`, `evaluate`, `matches`). |
| Validation | `backend/app/policy/validate.py` | `check(kind, config)`: schema errors plus envelope checks restated from `followup.contract.ENVELOPE`, deduplicated against schema paths. Also `locked_errors` (`scope`, `schema_version`, `opening_locked`) and `publish_reasons(row)`, the gate. |
| Prompt checks | `backend/app/policy/prompts.py` | `lint`, `lint_prompt`, `lint_messages`, `render`, `preview`, `PREVIEW_VARIABLES` (synthetic). |
| Store additions | `backend/app/policy/store.py` | Settings events emitted inside each write transaction; `open_draft(kind)`; `discard_draft(..., *, actor=)`; `rollback` now runs in one transaction. Existing signatures and results are unchanged. |
| Events | `backend/app/events.py` | `settings.draft_discarded.v1` appended to `SETTINGS_EVENTS`. |
| UI | `frontend/src/pages/admin/*`, `adminApi.ts`, `admin.css` | `/admin`, four tabs. |
| Route | `frontend/src/App.tsx` | One import and one `<Route path="/admin">` line. |
| Tests | `backend/tests/test_admin_settings.py` (31), `test_admin_simulator.py` (7), `e2e/test_admin_ui.py` (20 checks) | The settings suite uses four config-independent fixtures (S01, S02, S12, S25). The simulator suite builds its own gate scenarios, so neither depends on fixture values. |

## Behavior (for the README section at G5)
- **`/admin`** ("הגדרות") uses the same demo staff session as `/banker`. There are no personas and no approval step.
- **Tabs:**
  - **מסמכים ותהליך:** turn requirements on or off from the seed catalog, edit labels, hints, the mandatory flag and per-family rules, loan purposes, and the low-confidence threshold.
  - **מעקב והשלמה:** the follow-up and Talk form with the envelope bounds; locked rules shown read-only with a lock; the kill switch.
  - **התאמת הנחיות ותבניות:** the call prompt (locked AI-disclosure opening), variable chips, live lint and preview, and the message templates and per-finding customer messages.
  - **בדיקה וגרסאות:**
    - the simulator: runs the working copy, saved or not; a scenario table with pass/fail, expected vs actual action, rule ids (blocking ones in red), the evaluator's Hebrew explanation, and the gap for each failure;
    - pending changes against the published version;
    - version history with diff and rollback;
    - the settings audit list.
- **Flow:** edits stay local until "שמירת טיוטה" (a DRAFT, inactive). "שמירה והפעלה" saves, checks the gate and publishes. "ביטול השינויים" discards.
  - The live check (`POST /validate`, ~350 ms after typing) shows errors, warnings, the diff and the preview without storing anything.
- **Concurrency:** one open draft per kind. The client sends the revision it edited; a stale one gets 409, and the UI offers to reload.
- **Publish gate** (`validate.publish_reasons`), checked in this order:
  1. schema and envelope errors;
  2. a locked field changed;
  3. the draft's base is no longer the published version (for example after a rollback);
  4. no change against the published version;
  5. for `loan_policy`: a recorded simulation run in which every mandatory scenario passes. The run id is returned on success (`simulation_run_id`) and on refusal (`run_id`).
  - `POST /drafts/{id}/validate` runs the scenarios purely (nothing stored) and reports `scenarios{total, failed, mandatory_failed}`.
- **Engine effect:** publishing moves the version `store.policy()` returns, so the follow-up engine reads it at once (S27). Document requirements reach new cases only, because open cases stay pinned (`requirements.pin`).
- **Rollback** publishes a new version that copies the old config (A13) and emits `settings.rollback_applied.v1`.
- **The lint warns and never changes policy (S38).** It flags urgency ("התקשרו מיד"), approval or rate promises, threats, and requests for ID numbers, passwords or document content. A negation in the same clause cancels a match ("אל תבטיחי…").
  - Errors: an unknown variable, a missing AI disclosure, or an instruction to hide that it is AI.
  - Templates: a `link_message` without `{{secure_upload_link}}` gets a warning.

## CODEMAP lines (for G5)
- `backend/app/api/admin.py`: Admin Settings API (drafts, validate, publish, versions, rollback, kill switch, audit).
- `backend/app/policy/validate.py`: envelope, locked fields, publish gate. `policy/prompts.py`: prompt and template lint, render, preview.
- `backend/app/policy/simulator.py`: scenario runs for the Admin. Changes together with `followup/contract.py` (Scenario, matches, merge_overrides) and `backend/policy/scenarios/`.
- `frontend/src/pages/admin/`: `AdminPage` (shell, working copies, save/publish/discard), `DocumentsTab`, `FollowupTab`, `PromptTab`, `VersionsTab`, `ui.tsx`. `adminApi.ts` is the API client.
- Changes together: `schema.py` field bounds ↔ the `NumberField` min/max in `FollowupTab` / `DocumentsTab` (the server stays authoritative).

## Additive items beyond the contract text (to log in CONTRACTS §11 at G4; not edited now, per the user)
- `POST /api/admin/loan-completion/validate` `{kind, config}`: the validate report for an unsaved configuration. Stateless.
- Extra `GET /settings` fields: `locked_fields`, `rule_labels`, `prompt_variables`, `preview_variables`, `requirement_catalog`, `caller`.
- `POST /policy/simulate` also takes `scenario_ids`. The publish response adds `simulation_run_id`.
- The validate report adds `lint`, `preview`, `against`; the draft variant also adds `publishable`, `reasons`, `revision`.
- `settings.draft_discarded.v1` in `SETTINGS_EVENTS`.

## For G5 (other owners)
- Agent A: an "הגדרות" link to `/admin` in `ConsoleTop` (banker console). The admin page draws its own top bar with that link, because `ConsoleTop` is Agent A's file.
- Agent C: `POST /prompts/test` through the agent loop is still deferred.
