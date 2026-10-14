# Parallel workflow — Rounds 3 and 4 alongside Rounds 1–2

Set up 2026-10-14. Three agents work at the same time, each with strict file ownership. This folder only exists on
the parallel branches; Agent A's tree (`main`, uncommitted) never received it.

| Agent | Scope | Tree | Branch | Ports (backend / frontend) |
|---|---|---|---|---|
| A | Rounds 1–2 frontend and app adaptation | `/Users/nakash/Desktop/מזרחי copy` | `main` (uncommitted work) | 8791 / 5192; isolated stacks 8798, 8801 / 5846 |
| B | Round 3 follow-up engine backend | `/Users/nakash/Desktop/mizrahi2-agentB` | `agent-b/round3-followup` | 8796 / 5857 |
| C | Round 4 Admin Settings | `/Users/nakash/Desktop/mizrahi2-agentC` | `agent-c/round4-admin` | 8797 / 5858 |

- Mizrahi #1 (`/Users/nakash/Desktop/מזרחי`, ports 8790 / 5190) is off-limits to everyone: no reads, no writes, no
  network calls.
- Shared refs:
  - `parallel/r12-snapshot` is Agent A's work at 10:00, verified blob-for-blob.
  - `parallel/base` is the snapshot, plus the frozen contracts, plus the demo-first scope update (a docs-only
    commit). Both agent branches contain it.
  - `parallel/g1-evaluator` is set by Agent B at gate G1.

## Demo-first scope (user decision, 2026-10-14 10:45)
Mizrahi #2 is a sales demo. Rounds 3–4 build the working follow-up engine, the mock Talk recovery loop and a simple
Admin Settings flow, and nothing for future production governance.
- Access uses the existing sessions only.
- One admin edits, tests and publishes.
- Talk events are applied in-process, and the HTTP receiver is off until a secret is configured.
- Links are reusable until they expire.
- There is one scheduler `tick`.

The details are at the top of `CONTRACTS.md` and in its §12 (deferred).

## Snapshot
- Built with a private index (`.git/parallel-snapshot.index`, since deleted) after 60 s without writes in Agent A's
  tree. Agent A's `.git/index` and working tree were not touched.
- All 116 changed paths were checked identical to the working tree at the moment of the snapshot.
- **Excluded:**
  - `e2e/replay/recordings.json` (a generated recording; kept at its HEAD version).
  - Everything gitignored: `backend/.env`, `backend/data/`, `.venv`, `node_modules`, `frontend/dist`,
    `e2e/artifacts`, `__pycache__`, `.claude/settings.local.json`.
- A secret scan of the whole tree (Google keys, private keys, `*_KEY=`/`SESSION_SECRET=` with values) found
  nothing. `backend/.env.example` holds placeholders only.
- **Known baseline in the worktrees:** the snapshot alone gives 113 passed and 10 failed. All 10 failures are in
  `test_recorded_reviews.py`, because they need the excluded recordings. They pass in Agent A's tree, which was
  checked. With the contract tests, `pytest -q tests --ignore=tests/test_recorded_reviews.py` gives **121 passed**.
  Agents ignore that file; it is not theirs to fix.

## Runtime isolation (per worktree)
- `backend/.venv` is a fresh venv from `/opt/homebrew/opt/python@3.12` with `requirements-dev.txt`. Its scripts
  point into the worktree. Always run `.venv/bin/python -m …`. Never use Agent A's venv: it was copied from
  Mizrahi #1, and its `pip` and `pytest` scripts start #1's interpreter.
- Agent C's `frontend/node_modules` is an APFS clone (copy-on-write) of Agent A's. Installing or removing packages
  is not allowed without the user's approval.
- No `backend/.env` exists in the worktrees, so the Gemini key is absent and no paid call is possible. Keep it that
  way: never create a `.env` with keys.
- `AGENT_ENV.sh` at each worktree root (untracked, excluded through `.git/info/exclude`) sets the ports, `DATA_DIR`,
  `MZ_API`, and empty Gemini and VisionTrace keys. Source it in every shell: `. /Users/nakash/Desktop/mizrahi2-agentX/AGENT_ENV.sh`.
- `DATA_DIR` lives under the worktree's `e2e/artifacts/agent-x/` (gitignored). Tests use their own temp
  directory (`tests/conftest.py`).

## Ownership
Paths are relative to `mizrahi-touch-ai-demo/`. `python3 docs/plans/parallel/check_scope.py B|C` lists any changed
file outside the agent's scope. It must print `OK` before a merge.

- **Agent B owns:**
  - `backend/app/clock.py`
  - `backend/app/followup/**`, where `contract.py` is additive only
  - `backend/app/comms/**`
  - `backend/app/api/followup.py`
  - `backend/app/capabilities.py`, `flags.py`, and `events.py` (`DOCUMENT_EVENTS`/`FOLLOWUP_EVENTS` only)
  - `backend/policy/scenarios/**`
  - `backend/tests/test_followup_*.py`, `test_talk_*.py`, `test_upload_links.py`, `test_clock.py`
  - `docs/plans/parallel/NOTES-agent-B.md`, `docs/plans/07-jeen-talk-handoff.md`
- **Agent C owns:**
  - `backend/app/api/admin.py`
  - `backend/app/policy/{validate,simulator,prompts,proposal}.py`, plus `store.py` additions only
  - `events.py` (`SETTINGS_EVENTS` only)
  - `backend/tests/test_admin_*.py`
  - `frontend/src/pages/admin/**`, `frontend/src/adminApi.ts`, `frontend/src/admin.css`
  - `frontend/src/App.tsx`: one import line and one `<Route path="/admin">` line
  - `e2e/test_admin_ui.py`
  - `docs/plans/parallel/NOTES-agent-C.md`
- **Shared, additive only:**
  - `backend/tests/test_parallel_contracts.py`
  - `docs/plans/parallel/CONTRACTS.md` §11 (change log)
  - one new line each in `db.ADDED_COLUMNS` (logged)
- **Agent A keeps everything else:** all other frontend files, `review/*`, `workflow/*`, `bank/*`, `agent/*`,
  `mcp/*`, `auth.py`, `db.py`, `main.py`, `config.py`, `util.py`, `api/{routes,banker,banker_package,assistant}.py`,
  `policy/schema.py`, `policy/seed/*`, `rubrics/*`, `fixtures/*`, `e2e/*` (except C's one new file), the existing
  tests, `conftest.py`, `loan_helpers.py`, README, CODEMAP, `CLAUDE.md`, `run.sh`, `vite.config.ts` and
  `package.json`.

## Git rules for B and C
- Commit small and often, on your own branch only.
- Never `push`, `rebase`, `commit --amend` on a commit another branch has merged, `reset --hard`, `stash`,
  `checkout`/`switch` to another branch, or `worktree` commands.
- Never `git merge` anything except the gate refs named below. Never touch `main` or Agent A's tree.

## Gates
- **G0 — base frozen (done).** `parallel/base` = snapshot + contracts; `test_parallel_contracts.py` passes (8 tests).
  The demo-first scope update was then added as a docs-only commit. `parallel/base` was moved forward to it, and both
  agent branches were fast-forwarded before either had any work of its own.
- **G1 — evaluator final (B → C).** When G1 is done, Agent C runs `git merge --no-ff parallel/g1-evaluator` and
  only then builds the simulator, the publish gate's scenario check, `POST /policy/simulate` and the simulator tab.
  Agent B must have:
  - `followup/policy.py::evaluate` implemented
  - scenario fixtures for every decision scenario in 03 §5 (S01–S18, S20–S28, S33–S37), each with `mandatory`
  - `test_followup_policy.py` and the contract tests green
  - a commit whose message starts with `G1:`, then `git branch -f parallel/g1-evaluator HEAD`, and a report to the
    user

  Later evaluator fixes move the ref **forward only**, and Agent C merges again.
- **G2 — Agent A done.** Rounds 1–2 are green: backend tests, typecheck, build, and the REPLAY featured suite. The
  user commits Agent A's tree on `main`, then records the snapshot as superseded:
  `git merge -s ours --no-edit parallel/r12-snapshot`. That makes the snapshot the merge base, so files Agent A
  changed after 10:00 don't conflict.
- **G3 — merge B.** `git merge --no-ff agent-b/round3-followup` on `main`. Then run backend tests, contract tests,
  typecheck, build, and the REPLAY featured suite on an isolated stack.
- **G4 — merge C.** `git merge --no-ff agent-c/round4-admin`, then the same checks plus an `/admin` browser check.
  Agent C's branch contains Agent B's G1 commits; merging B first keeps C's diff to C's own files.
- **G5 — cross-boundary wiring on `main`, one owner at a time:**
  - B: `orchestrator.tick(clock.now())` every few seconds in the existing worker loop (no new job kinds);
    `on_event` after reviews and uploads; `get_followup_context` in `agent/tools.py` (MCP tool count 10 → 11 in
    `e2e/test_mcp_sdk.py`); `/system` row.
  - A: presence hook in `caseContext.tsx`; customer snooze / preference / handoff controls; banker Talk card,
    timeline and overrides; presenter simulation controls (the demo routes already accept the customer session, so
    no new permission is needed); an "הגדרות" link to `/admin` in the console.
  - C (optional): `POST /prompts/test` through the agent loop.
  - README and CODEMAP sections from each agent's NOTES file.
- **G6 — Round 5.**

No merge happens before G2, and every merge needs the user's go-ahead.
