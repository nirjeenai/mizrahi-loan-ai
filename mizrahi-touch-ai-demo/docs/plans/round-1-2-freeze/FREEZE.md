# Rounds 1–2 — frozen baseline (2026-10-14)

**Status: FROZEN and committed on `main` at gate G2.** Approved by the user after the final audit
(`docs/plans/round-1-2-final-audit.md`). G2 consists of two local commits on `main`:
1. the frozen tree;
2. `git merge -s ours parallel/r12-snapshot`, which records the 10:00 snapshot as superseded.

Agents B and C can read this folder without changing their trees:
`git show main:mizrahi-touch-ai-demo/docs/plans/round-1-2-freeze/FREEZE.md`.

## What is frozen
Agent A's working tree in `/Users/nakash/Desktop/מזרחי copy` as of this note. `manifest.json` (next to this file) has the
SHA-256 of every tracked and untracked, non-ignored file under `mizrahi-touch-ai-demo/` except this folder.
`python3 mizrahi-touch-ai-demo/docs/plans/round-1-2-freeze/check_r12_baseline.py --manifest` proves a tree equals it.

It is newer than the 10:00 snapshot (`parallel/r12-snapshot`) that Agents B and C branched from. It differs in 74 paths:
the rest of the Rounds 1–2 frontend, the intake, the audit fixes F1–F8, and payslip rubric v1.3.0. The recordings
(`e2e/replay/recordings.json`) were excluded from the snapshot and are part of this baseline.

Verified on this tree (2026-10-14):

| Check | Result |
|---|---|
| Backend tests | 130 passed |
| Frontend typecheck | OK |
| Production build | OK |
| Loan journey, REPLAY (:8798/:5846) | 34/34; 22 recorded answers, payslips reviewed under `payslip.il.salaried@1.3.0` |
| MCP SDK suite, REPLAY | 9/9 |
| Mizrahi #2 main | restarted on :8791 with this code; the old index migrated; :5192 works against it |
| Mizrahi #1 | untouched: same process since 2026-10-13 14:17; no file changed |

## Fixes later merges must not undo
`check_r12_baseline.py` (no flags) checks a marker for each fix. It must print `OK` after every merge (G3, G4) and after
each G5 wiring step.

| Id | Fix | Files |
|---|---|---|
| F1 | file dedupe per case **and document family**; index `ux_documents_case_sha_req`; `db.migrate()` drops the old index | `workflow/engine.py`, `store/repo.py` (`documents_by_sha`), `db.py` |
| F2 | "העלאה מחדש" only for a document sent back, never for a missing document or a period gap | `agent/actions.py`, `pages/customer/Documents.tsx` |
| F3 | the customer file badge follows the routed outcome (`customerVerdict`) | `api.ts`, `Documents.tsx`, `DocumentReview.tsx`, `UploadSheet.tsx` |
| F4 | the document page's replace button keeps the document's requirement | `DocumentReview.tsx` |
| F5–F7 | loan wording (presenter pane, MCP instructions, `/system`), one `COVERAGE_CODES` | `App.tsx`, `mcp/server.py`, `api/routes.py`, `review_desk.py`, `api.ts` |
| F8 | legacy suites marked LEGACY; never start #1's interpreter or bind :8791 | `e2e/test_*.py` |
| R13 | `payslip.il.salaried` v1.3.0: wording only, criteria identical to v1.2.0 | `backend/rubrics/payslip.il.salaried.v1.3.0.json`, `tests/test_pay_date.py` |

## Integration rules (additions to `docs/plans/parallel/README.md` on `parallel/base`)
1. **G2.**
   - Before the user commits, `check_r12_baseline.py --manifest` prints OK. If anything changed after the freeze, run
     the checks above again and write a new manifest (`--write-manifest`).
   - Then commit, then `git merge -s ours --no-edit parallel/r12-snapshot`, as planned. This makes the snapshot the
     merge base, so the 74 later changes count as main's own and B/C cannot revert them unless they edit the same lines.
2. **The "REPLAY featured suite" in G2–G4 is `e2e/test_loan_journey.py` (34 checks).**
   - `e2e/test_featured_demo.py` is LEGACY. It fails 2/6 by design, because it still asserts the mortgage scenarios.
   - A red run of it is not a regression. Never "fix" it by restoring mortgage behaviour or reverting loan files.
3. **Before each merge:**
   - `check_scope.py B|C` prints OK. Any A-owned file edited in a B/C branch is a diff against 10:00 and can silently
     revert later fixes.
   - Read-only check on 2026-10-14 (B at `24facc7`, C at `3790cb9`, `parallel/base` at `1d6297a`): all three change
     only the 12 contract and docs files, and none of the 74 post-snapshot paths, so nothing overlaps.
4. **The two shared files, if they conflict:**
   - `db.py`: keep Agent A's documents index, `DROPPED_INDEXES` and `migrate()`. Add the agent's `ADDED_COLUMNS` entry
     inside the dict. Since 10:00 the `ADDED_COLUMNS` loop lives in `migrate()`, not in `connect()`.
   - `App.tsx`: keep the presenter-pane text and the `Apply` import and route. Add Agent C's import line and `/admin`
     route.
5. **G5 wiring is done on `main`'s current files.** Never copy a whole file from a B/C worktree: those copies are 10:00
   versions of Agent A's files (`engine.py`, `agent/tools.py`, `e2e/test_mcp_sdk.py`, …).
6. **After each merge, run:**
   - `check_r12_baseline.py`
   - the backend tests (130 + the merged agent's tests)
   - typecheck and build
   - `e2e/test_loan_journey.py` on an isolated REPLAY stack

## Behaviour that changed after the 10:00 snapshot (relevant to B and C)
- `repo.document_by_sha(case, sha)` is now `repo.documents_by_sha(case, sha)`, which returns a list.
- A duplicate is the same file for the same **document family**. The same file sent for another family is a new document.
- Upload action labels: "העלאת …" for a first upload, "העלאה מחדש: …" only when a document was sent back.
- The latest payslip rubric is `payslip.il.salaried@1.3.0`. Assert criteria, not the version string.
- `db.migrate(conn)` exists. New columns still go in `ADDED_COLUMNS`; dropped indexes go in `DROPPED_INDEXES`.

None of the frozen contracts in `CONTRACTS.md` changed. `auth.py` only gained the alias `set_session = _set`. The
readiness, requirements and mock-bank files are identical to the snapshot.
