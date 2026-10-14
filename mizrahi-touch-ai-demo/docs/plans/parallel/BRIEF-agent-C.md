# Agent C — Round 4 Admin Settings, Customize Prompt, versioning

You are Agent C on Mizrahi #2 (the loan completion demo). Two other agents work in parallel; you own only the files
listed below.

- **Your worktree:** `/Users/nakash/Desktop/mizrahi2-agentC`
- **Your branch:** `agent-c/round4-admin`
- **Base:** `parallel/base` (it includes the demo-first scope update of 2026-10-14)

## Before anything
1. Open the worktree as your workspace. In every shell, run `. /Users/nakash/Desktop/mizrahi2-agentC/AGENT_ENV.sh`.
2. Read these, in order:
   - `mizrahi-touch-ai-demo/docs/plans/parallel/README.md` (ownership, gates)
   - `docs/plans/parallel/CONTRACTS.md`: frozen. Read the demo-first note at the top and §12 (deferred) first;
     you implement the §2 store additions, §6 and §7.
   - `docs/plans/04-target-architecture-contracts.md` §3 (configuration shape; its roles in §8–§9 are superseded)
   - `docs/plans/03-prd-gap-analysis.md` (A1–A13, S38–S40)
   - `CLAUDE.md`
3. Check the baseline:
   - `cd mizrahi-touch-ai-demo/backend && .venv/bin/python -m pytest -q tests --ignore=tests/test_recorded_reviews.py`
     should give **121 passed**.
   - `cd ../frontend && ./node_modules/.bin/tsc --noEmit -p .` should be clean.
   - `test_recorded_reviews.py` fails only because its recordings are excluded from the snapshot. Ignore it.

## Goal
The demo admin changes loan-completion behavior without touching code, in one simple flow: edit, then test
(validate + simulate), then save and publish, with version history and rollback. No approval step and no second
person.

This is a sales demo. Make it polished and persistent (real versions in `config_versions`, not frontend state), and
build nothing for production governance. It lives in a "הגדרות" (Settings) area at `/admin`, inside the existing
console shell (`console-top`, `console-ribbon`, `desk-page` styles; Hebrew RTL). It has four tabs:
1. **מסמכים ותהליך** (documents and process): the `document_requirements`, `product.purposes` and `validation`
   editor.
2. **מעקב והשלמה** (follow-up): a structured `followup` + `talk` form (FR-25). The locked hard guards
   (`followup.contract.LOCKED_RULES` + `RULES` labels) and the `ENVELOPE` are shown read-only with a lock and the
   reason. The kill switch lives here.
3. **התאמת הנחיות ותבניות** (Customize Prompt and templates):
   - `talk_prompt` editing: `opening_locked` (AI disclosure) is read-only; `instructions` uses `{{variables}}` from
     `PROMPT_VARIABLES` only.
   - Lint: "התקשרו מיד", approval or credit promises ("ההלוואה אושרה"), threats, asking for ID numbers or document
     contents, unknown variables, a missing disclosure.
   - `templates` and `customer_messages` with the same variable checker.
   - A preview rendered with synthetic variables.
4. **בדיקה וגרסאות** (test and versions): the simulator run (after G1), validation and diff against the published
   version, "שמירה והפעלה" (save and publish), the version list with rollback, and the audit list.

Always show an environment banner ("סביבת הדגמה · נתונים סינתטיים") and the publish state of each kind.

## Build this, in this order (all of it independent of Agent B until step 5)
1. **`backend/app/policy/validate.py`:** schema errors (from `store.validate`), plus envelope checks the schema can't
   express: grace ≥5 minutes outside demo (`ENVELOPE`), `max_attempts_per_case ≤ 3`, call window inside
   08:00–20:00, no Saturday (S39). No approver rules.
2. **`backend/app/policy/prompts.py`:** `lint(prompt) -> [warnings{code, message_he, span}]` (S38: a warning, never a
   policy change), `render(text, variables)`, synthetic preview variables.
3. **`backend/app/policy/store.py` additions only:**
   - Events through `events.emit`: `settings.draft_saved.v1`, `settings.policy_published.v1`,
     `settings.prompt_published.v1`, `settings.rollback_applied.v1`.
   - Don't change existing signatures or behavior: Agent A's tests and `requirements.pin` depend on them.
4. **`backend/app/api/admin.py`:** every route in CONTRACTS §7, each behind `auth.require_staff`.
   - The `revision` goes in the request body; the store's `Conflict` becomes 409. No If-Match or ETag.
   - The kill switch goes through `flags.put(flags.KILL_SWITCH, …)`.
   - Audit is `events.recent(None, SETTINGS_EVENTS)` plus version history.
   - `/prompts/test` → 501 "deferred".
5. **After gate G1 only.** Wait until the user tells you G1 is reached, or until `git branch --list
   parallel/g1-evaluator` shows the ref. Then `git merge --no-ff parallel/g1-evaluator` and build:
   - `backend/app/policy/simulator.py::simulate`, exactly as CONTRACTS §6 (only `simulation_runs` + one event). Use
     `contract.load_scenarios()` and `contract.matches`; if G1 ships a deep-merge helper in `contract.py`, use it.
   - `POST /policy/simulate`
   - the mandatory-scenario publish gate for `loan_policy`
   - the simulator panel in tab 4: a scenario table with pass/fail, expected vs actual action, rule ids and Hebrew
     explanation

   Until then, show the panel as "ממתין למנוע המדיניות" (waiting for the policy engine), with no fake results. Do
   not write an evaluator or scenario fixtures yourself; those are Agent B's.
6. **Frontend (can run in parallel with steps 1–4):**
   - `frontend/src/pages/admin/*` (AdminPage + one component per tab), `frontend/src/adminApi.ts` (your own fetch
     helper modelled on `api.ts::http`, credentials `same-origin`), `frontend/src/admin.css` (imported by the admin
     page; reuse existing class names read-only).
   - Add exactly one import and one `<Route path="/admin" element={<AdminPage />} />` line to `frontend/src/App.tsx`.
   - Session: the same demo staff session the banker console gets (`POST /api/session/demo/staff` with the default
     staff id, when `GET /api/session` has none). No persona switcher, no login screen.

**Not built (deferred, CONTRACTS §12):**
- the distinct-approver rule, `classify()` and sensitive paths;
- editor/approver personas;
- If-Match, ETag and 428;
- the NL policy proposal (`proposal.py`, `interpret-proposal`);
- the agent-loop prompt test.

## Allowed files (relative to `mizrahi-touch-ai-demo/`)
- `backend/app/api/admin.py` (already mounted in `main.py`)
- `backend/app/policy/validate.py`, `prompts.py`, `simulator.py` (after G1); `store.py` additions only
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

## Tests you must add (06-roadmap-traceability.md, AC 16–19, 21, 25; AC 20 is deferred)
**`test_admin_settings.py`:**
- Access with the existing checks: no session → 401 on every route; a customer-only session → 401; the demo staff
  session → 200.
- A draft is inactive: the published version, `requirements.for_case` and the pinned cases are unchanged until
  publish (AC 17).
- A stale `revision` → 409, so of two edits from the same base, one wins (AC 21).
- Validation paths and envelope rejections (S39).
- Publish is atomic, leaving one PUBLISHED per kind; rollback creates a new version; audit lists each step with its
  actor (AC 25).
- Prompt lint (S38) and preview; the locked opening can't be edited; unknown variable → error (AC 19).
- The kill switch toggles, and `GET /settings` shows it.
- **After G1:**
  - the simulator runs every fixture;
  - `side_effects` is false: row counts of every table other than `simulation_runs`/`case_events` are unchanged
    (S40);
  - a draft that breaks a mandatory scenario can't be published (AC 18).

**Frontend:** `tsc` clean, `npm run build` OK. `e2e/test_admin_ui.py` covers:
- edit the grace period in tab 2 and save;
- the diff shows in tab 4;
- run the simulator (after G1);
- publish, and see the version list update;
- roll back;
- toggle the kill switch;
- screenshots go to `e2e/artifacts/agent-c/`.

## Definition of done
- [ ] Every CONTRACTS §7 route is implemented (`/prompts/test` returns 501 "deferred"); the four tabs work in the
      browser on your stack.
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
