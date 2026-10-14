# Agent C — Round 4 Admin Settings, Customize Prompt, versioning

You are Agent C on Mizrahi #2 (the loan completion demo). Two other agents work in parallel; you own only the files
listed below.

- **Your worktree:** `/Users/nakash/Desktop/mizrahi2-agentC`
- **Your branch:** `agent-c/round4-admin`
- **Base:** `parallel/base`, plus `parallel/scope-v2` (the demo-first revision, already on your branch)

> **Scope v2 (demo-first, 2026-10-14).** This is a working sales demo. Read CONTRACTS §0 first.
> - **Build:** one demo admin who edits, tests (validation, lint, preview, simulator) and publishes configuration
>   that the engine really reads, with versions and rollback.
> - **Not built:** personas or capability checks; a distinct approver; `If-Match`/`ETag`/428; an audit route or
>   view; new tables.
> - Use the existing staff session (`auth.require_staff`).

## Before anything
1. Open the worktree as your workspace. In every shell, run `. /Users/nakash/Desktop/mizrahi2-agentC/AGENT_ENV.sh`.
2. Read these, in order:
   - `mizrahi-touch-ai-demo/docs/plans/parallel/README.md` (ownership, gates)
   - `docs/plans/parallel/CONTRACTS.md` (frozen; §0 first, then you implement §2 store additions, §6 and §7)
   - `docs/plans/04-target-architecture-contracts.md` §3, §8
   - `docs/plans/03-prd-gap-analysis.md` (A10, A13, S26, S38–S40)
   - `CLAUDE.md`
3. Check the baseline:
   - `cd mizrahi-touch-ai-demo/backend && .venv/bin/python -m pytest -q tests --ignore=tests/test_recorded_reviews.py`
     should give **121 passed**.
   - `cd ../frontend && ./node_modules/.bin/tsc --noEmit -p .` should be clean.
   - `test_recorded_reviews.py` fails only because its recordings are excluded from the snapshot. Ignore it.

## Goal
The demo admin changes loan-completion behavior without touching code: open a draft, edit, validate, see the diff,
simulate (after G1), publish, and roll back. Publishing changes what the engine reads; nothing is a frontend illusion.
This all lives in a "הגדרות" (Settings) area at `/admin`, inside the existing console shell (`console-top`,
`console-ribbon`, `desk-page` styles; Hebrew RTL), with five tabs:
1. **מסמכים ותהליך** (documents and process): the `document_requirements`, `product.purposes` and `validation`
   editor.
2. **מעקב והשלמה** (follow-up): a structured `followup` + `talk` form (FR-25). The locked hard guards
   (`followup.contract.LOCKED_RULES` + `RULES` labels) and the `ENVELOPE` are shown read-only with a lock and the
   reason. The kill switch lives here.
3. **התאמת הנחיות** (Customize Prompt):
   - `talk_prompt` editing: `opening_locked` (AI disclosure) is read-only; `instructions` uses `{{variables}}` from
     `PROMPT_VARIABLES` only.
   - A light lint (a few patterns, warnings only): "התקשרו מיד", approval or credit promises ("ההלוואה אושרה"),
     threats, asking for ID numbers or document contents. Unknown variables and a missing disclosure are errors.
   - Preview rendered with synthetic variables.
   - A "test conversation" button that stays disabled until G5.
4. **תבניות הודעה** (message templates): `templates` and `customer_messages`, with a variable checker and preview.
5. **סימולציה וגרסאות** (simulator and versions): the version list (who, when, why) with diff and rollback, and the
   simulator run (built after G1).

Always show an environment banner ("סביבת הדגמה · נתונים סינתטיים") and the publish state of each kind. Each tab
has the same simple action bar: save draft · validate · publish · discard.

## Build this, in this order (all of it independent of Agent B until step 6)
1. **`backend/app/policy/validate.py`:**
   - Schema errors (from `store.validate`) plus envelope checks the schema can't express: grace ≥ the
     environment's minimum (`ENVELOPE`), `max_attempts_per_case ≤ 3`, `min_hours_between_calls ≥ 4`, call window
     inside 08:00–20:00, no Saturday (S39).
   - Locked fields: `scope`, `schema_version`, and the prompt's `opening_locked` can't change.
   - `check(kind, config) -> {errors, warnings}` and `publish_reasons(row) -> [str]` (the §6 gate).
2. **`backend/app/policy/prompts.py`:** `lint(text) -> [{code, severity, message_he, span}]` (S38: a warning, never
   a policy change), `render(text, variables)`, synthetic preview variables.
3. **`backend/app/policy/store.py` additions only:**
   - Events through `events.emit` (`settings.draft_saved.v1`, `settings.policy_published.v1`,
     `settings.prompt_published.v1`, `settings.rollback_applied.v1`).
   - `open_draft(kind)`, the one open draft of a kind.
   - Don't change existing signatures or behavior: Agent A's tests and `requirements.pin` depend on them.
4. **`backend/app/api/admin.py`:** every route in CONTRACTS §7, each with `auth.require_staff`.
   - The body carries `revision`; a stale one is a 409.
   - Kill switch through `flags.put(flags.KILL_SWITCH, …)`.
5. **`backend/app/policy/proposal.py`** (lowest priority; build it last): a natural-language proposal, turned into a
   JSON patch over **allowed keys only**.
   - Use the existing `app/llm/gemini.py` client through an injectable function, so tests stub it.
   - Gemini is disabled in your environment, so the route returns 503 "unavailable".
   - Never save or publish: the admin applies the patch to a draft explicitly (AC 20).
6. **After gate G1 only.** Wait until the user tells you G1 is reached, or until `git branch --list
   parallel/g1-evaluator` shows the ref. Then `git merge --no-ff parallel/g1-evaluator` and build:
   - `backend/app/policy/simulator.py::simulate` exactly as CONTRACTS §6 (only `simulation_runs` + one event)
   - `POST /policy/simulate`
   - the mandatory-scenario publish gate for `loan_policy`
   - the simulator panel in tab 5: a scenario table with pass/fail, expected vs actual action, rule ids and Hebrew
     explanation

   Until then, show the panel as "ממתין למנוע המדיניות" (waiting for the policy engine), with no fake results. Do
   not write an evaluator or scenario fixtures yourself; those are Agent B's.
7. **Frontend (can run in parallel with steps 1–5):**
   - `frontend/src/pages/admin/*` (AdminPage + one component per tab), `frontend/src/adminApi.ts` (your own fetch
     helper modelled on `api.ts::http`, credentials `same-origin`), `frontend/src/admin.css` (imported by the admin
     page; reuse existing class names read-only).
   - Add exactly one import and one `<Route path="/admin" element={<AdminPage />} />` line to `frontend/src/App.tsx`.
   - Session: like `/banker`, obtain the demo staff session with `POST /api/session/demo/staff {}` when there is
     none. No persona switcher.

## Allowed files (relative to `mizrahi-touch-ai-demo/`)
- `backend/app/api/admin.py` (already mounted in `main.py`)
- `backend/app/policy/validate.py`, `prompts.py`, `proposal.py`, `simulator.py` (after G1); `store.py` additions only
- `backend/app/events.py`: append to `SETTINGS_EVENTS` only
- New tests: `backend/tests/test_admin_settings.py` (and other `test_admin_*.py`)
- `frontend/src/pages/admin/**`, `frontend/src/adminApi.ts`, `frontend/src/admin.css`, the two lines in
  `frontend/src/App.tsx`
- New `e2e/test_admin_ui.py` (Playwright via `backend/.venv/bin/python`, against your own stack on 8797)
- `docs/plans/parallel/NOTES-agent-C.md`: README and CODEMAP text for G5, open questions, contract change requests
- Additive only: `backend/tests/test_parallel_contracts.py`, `CONTRACTS.md` §11, one new line in `db.ADDED_COLUMNS`
  (log it in §11)

## Forbidden
- Every other file. In particular:
  - `policy/schema.py`: frozen. A needed schema change goes to `NOTES-agent-C.md` as a request.
  - `policy/seed/*`, `capabilities.py`, `flags.py`, `followup/**`, `comms/**`, `api/followup.py`, `clock.py`
    (Agent B's).
  - `frontend/src/api.ts`, `styles.css`, `components/*`, `pages/{customer,banker,system}/*`, `caseContext.tsx`
    (Agent A's).
  - `workflow/*`, `review/*`, `agent/*`, `mcp/*`, `auth.py`, `db.py` (except the line above), `main.py`,
    `config.py`, `bank/*`, `fixtures/*`, `rubrics/*`, existing tests, `conftest.py`, other `e2e/*`, README,
    CODEMAP, `CLAUDE.md`, `run.sh`, `package.json`, `vite.config.ts`.
- Agent A's tree `/Users/nakash/Desktop/מזרחי copy`, Mizrahi #1 `/Users/nakash/Desktop/מזרחי` (files, venv,
  ports 8790/5190), and ports 8791/5192/8798/5846/8801/8796/5857.
- Any live Gemini call, creating `backend/.env`, `pip`/`npm` installs, `git push/rebase/reset --hard/stash/checkout`,
  merging anything except `parallel/g1-evaluator`, and touching `main`.
- Deferred in v2 (don't build): capability checks, personas, distinct approver, `If-Match`/`ETag`, `/audit`.

## Tests you must add (06-roadmap-traceability.md, AC 16–22, 25)
**`test_admin_settings.py`:**
- Sessions: no session → 401; a customer session → 401; a staff session works.
- A draft is inactive: the published version, `requirements.for_case` and the pinned cases are unchanged until
  publish (AC 17).
- One open draft per kind; a stale `revision` → 409, and two saves from the same revision → one wins (AC 21).
- Validation paths; envelope rejections (S39); locked fields can't change.
- Publish is atomic, leaving one PUBLISHED per kind; the engine reads the new values after publish; rollback creates
  a new version; the version list shows who did each step (AC 25).
- Prompt lint (S38) and preview; the locked opening can't be edited; unknown variable → error (AC 19).
- Kill switch toggles and is reported in `/settings`.
- NL proposal with a stubbed LLM: the patch only touches allowed keys, a disallowed key is dropped and reported,
  and nothing is saved or published (AC 20).
- **After G1:**
  - the simulator runs every fixture;
  - `side_effects` is false: row counts of every table other than `simulation_runs`/`case_events` are unchanged
    (S40);
  - a draft that breaks a mandatory scenario can't be published (AC 18).

**Frontend:** `tsc` clean, `npm run build` OK. `e2e/test_admin_ui.py` covers:
- the admin edits the grace period in tab 2 and saves a draft;
- the diff shows;
- publish;
- the version list updates;
- rollback;
- the kill switch toggles;
- screenshots go to `e2e/artifacts/agent-c/`.

## Definition of done
- [ ] Every CONTRACTS §7 route is implemented (`/prompts/test` returns 501 "deferred to G5"); the five tabs work in
      the browser on your stack.
- [ ] `pytest -q tests --ignore=tests/test_recorded_reviews.py` passes in full (121 baseline + yours); `tsc` is
      clean; `npm run build` succeeds (it writes your own `frontend/dist`).
- [ ] G1 work done after merging `parallel/g1-evaluator`. If G1 hasn't happened by the time everything else is
      done, report that and stop; don't stub an evaluator.
- [ ] `python3 docs/plans/parallel/check_scope.py C` prints `OK`. Review the printed `App.tsx` diff: it should be
      two lines.
- [ ] No Gemini call was made.
- [ ] `NOTES-agent-C.md` is written.
- [ ] Everything is committed on `agent-c/round4-admin`; nothing pushed or merged into `main`.
- [ ] Report the commands you ran, their output, and screenshots. Label anything not run as not verified.

## Runtime
- Backend: `cd mizrahi-touch-ai-demo/backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port $BPORT --reload`.
  It serves your `frontend/dist` at `http://127.0.0.1:8797/admin` after `npm run build`.
- Vite dev: `cd mizrahi-touch-ai-demo/frontend && ./node_modules/.bin/vite --port $FPORT --strictPort`. `MZ_API` is
  set by `AGENT_ENV.sh`. Don't use `npm run dev`; it is pinned to Agent A's 5192.
- Stop: `lsof -tiTCP:$BPORT -sTCP:LISTEN | xargs kill` (same for `$FPORT`).
