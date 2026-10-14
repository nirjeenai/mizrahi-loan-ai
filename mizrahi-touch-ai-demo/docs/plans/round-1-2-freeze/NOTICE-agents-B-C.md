# Notice for Agents B and C (paste into each agent's chat; Agent A did not touch your worktrees)

Rounds 1–2 are frozen and committed on `main` (gate G2). `main` now records `parallel/r12-snapshot` as merged with
`-s ours`, so the snapshot is the merge base for G3/G4. Do **not** merge `main` into your branch; keep working from
`parallel/base` as before. Nothing of yours was touched.

The baseline is newer than the 10:00 snapshot you branched from: 74 paths changed afterwards. None of them are in your
scopes, and no frozen contract changed. To keep the merge from reverting them:

1. Edit only your own paths. `check_scope.py` must print OK. Your copies of Agent A's files are 10:00 versions; an edit
   there can undo a later fix at merge time.
2. Don't call `repo.document_by_sha`. It is now `repo.documents_by_sha(case_id, sha)` and returns a list.
3. Upload dedupe now works per case and **document family**. The same file uploaded for another kind of document is a new
   document. Don't rely on "same file anywhere in the case → `created: false`".
4. Upload action labels: first uploads read "העלאת …". "העלאה מחדש: …" means a document was sent back.
5. The latest payslip rubric is `payslip.il.salaried@1.3.0` (wording only). Don't assert `1.2.0` in new tests.
6. `db.py` gained `DROPPED_INDEXES` and `migrate(conn)`, and the `ADDED_COLUMNS` loop moved into `migrate()`. Your
   `ADDED_COLUMNS` line stays exactly as agreed. If git reports a conflict there, keep both sides.
7. Agent C: `App.tsx` gained an `Apply` import and route and new presenter-pane text. Your one import line and one
   `/admin` route are unaffected.
8. The gate suite is `e2e/test_loan_journey.py` (REPLAY, 34 checks). `e2e/test_featured_demo.py` is LEGACY and fails by
   design.

Details and the post-merge guard are `docs/plans/round-1-2-freeze/FREEZE.md` and `check_r12_baseline.py` on `main`.
Read them without touching your tree:
`git show main:mizrahi-touch-ai-demo/docs/plans/round-1-2-freeze/FREEZE.md`.
