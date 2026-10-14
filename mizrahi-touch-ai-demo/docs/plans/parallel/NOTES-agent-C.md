# Agent C notes — Round 4 Admin Settings

Status 2026-10-14: everything that doesn't depend on gate G1 is built and tested on `agent-c/round4-admin`. The
simulator, `POST /policy/simulate`, the mandatory-scenario publish check and the simulator panel are waiting for G1;
until then the panel says "ממתין למנוע המדיניות" and shows no results.

## What exists
| Area | Where | Notes |
|---|---|---|
| Admin API | `backend/app/api/admin.py` | Every CONTRACTS §7 route except `/policy/simulate` (G1). All routes use `auth.require_staff`. `/prompts/test` returns 501. |
| Validation | `backend/app/policy/validate.py` | `check(kind, config)`: schema errors plus envelope checks restated from `followup.contract.ENVELOPE`, deduplicated against schema paths. Also `locked_errors` (`scope`, `schema_version`, `opening_locked`) and `publish_reasons(row)`, the gate. |
| Prompt checks | `backend/app/policy/prompts.py` | `lint`, `lint_prompt`, `lint_messages`, `render`, `preview`, `PREVIEW_VARIABLES` (synthetic). |
| Store additions | `backend/app/policy/store.py` | Settings events emitted inside each write transaction; `open_draft(kind)`; `discard_draft(..., *, actor=)`; `rollback` now runs in one transaction. Existing signatures and results are unchanged. |
| Events | `backend/app/events.py` | `settings.draft_discarded.v1` appended to `SETTINGS_EVENTS`. |
| UI | `frontend/src/pages/admin/*`, `adminApi.ts`, `admin.css` | `/admin`, four tabs. |
| Route | `frontend/src/App.tsx` | One import and one `<Route path="/admin">` line. |
| Tests | `backend/tests/test_admin_settings.py` (30), `e2e/test_admin_ui.py` (19 checks) | |

## Behavior (for the README section at G5)
- **`/admin`** ("הגדרות") uses the same demo staff session as `/banker`. There are no personas and no approval step.
- **Tabs:**
  - **מסמכים ותהליך:** turn requirements on or off from the seed catalog, edit labels, hints, the mandatory flag and per-family rules, loan purposes, and the low-confidence threshold.
  - **מעקב והשלמה:** the follow-up and Talk form with the envelope bounds; locked rules shown read-only with a lock; the kill switch.
  - **התאמת הנחיות ותבניות:** the call prompt (locked AI-disclosure opening), variable chips, live lint and preview, and the message templates and per-finding customer messages.
  - **בדיקה וגרסאות:** the simulator placeholder, pending changes against the published version, version history with diff and rollback, and the settings audit list.
- **Flow:** edits stay local until "שמירת טיוטה" (a DRAFT, inactive). "שמירה והפעלה" saves, checks the gate and publishes. "ביטול השינויים" discards.
  - The live check (`POST /validate`, ~350 ms after typing) shows errors, warnings, the diff and the preview without storing anything.
- **Concurrency:** one open draft per kind. The client sends the revision it edited; a stale one gets 409, and the UI offers to reload.
- **Publish gate** (`validate.publish_reasons`), checked in this order:
  1. schema and envelope errors;
  2. a locked field changed;
  3. the draft's base is no longer the published version (for example after a rollback);
  4. no change against the published version;
  5. after G1: mandatory scenarios.
- **Engine effect:** publishing moves the version `store.policy()` returns, so the follow-up engine reads it at once (S27). Document requirements reach new cases only, because open cases stay pinned (`requirements.pin`).
- **Rollback** publishes a new version that copies the old config (A13) and emits `settings.rollback_applied.v1`.
- **The lint warns and never changes policy (S38).** It flags urgency ("התקשרו מיד"), approval or rate promises, threats, and requests for ID numbers, passwords or document content. A negation in the same clause cancels a match ("אל תבטיחי…").
  - Errors: an unknown variable, a missing AI disclosure, or an instruction to hide that it is AI.
  - Templates: a `link_message` without `{{secure_upload_link}}` gets a warning.

## CODEMAP lines (for G5)
- `backend/app/api/admin.py`: Admin Settings API (drafts, validate, publish, versions, rollback, kill switch, audit).
- `backend/app/policy/validate.py`: envelope, locked fields, publish gate. `policy/prompts.py`: prompt and template lint, render, preview.
- `frontend/src/pages/admin/`: `AdminPage` (shell, working copies, save/publish/discard), `DocumentsTab`, `FollowupTab`, `PromptTab`, `VersionsTab`, `ui.tsx`. `adminApi.ts` is the API client.
- Changes together: `schema.py` field bounds ↔ the `NumberField` min/max in `FollowupTab` / `DocumentsTab` (the server stays authoritative).

## Additive items beyond the contract text (to log in CONTRACTS §11 at G4; not edited now, per the user)
- `POST /api/admin/loan-completion/validate` `{kind, config}`: the validate report for an unsaved configuration. Stateless.
- Extra `GET /settings` fields: `locked_fields`, `prompt_variables`, `preview_variables`, `requirement_catalog`, `caller`.
- The validate report adds `lint`, `preview`, `against`; the draft variant also adds `publishable`, `reasons`, `revision`.
- `settings.draft_discarded.v1` in `SETTINGS_EVENTS`.

## For gate G1 (next step)
- `policy/simulator.py::simulate` per CONTRACTS §6, `POST /policy/simulate`, the `mandatory_passed` check in `publish_reasons` for `loan_policy`, and the scenario table in `VersionsTab`.
- `simulator_available` in `/settings` becomes true automatically once `policy/simulator.py` exists.

## For G5 (other owners)
- Agent A: an "הגדרות" link to `/admin` in `ConsoleTop` (banker console). The admin page draws its own top bar with that link, because `ConsoleTop` is Agent A's file.
- Agent C: `POST /prompts/test` through the agent loop is still deferred.
