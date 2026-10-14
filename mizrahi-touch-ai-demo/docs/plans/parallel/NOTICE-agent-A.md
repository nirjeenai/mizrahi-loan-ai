# Notice for Agent A (paste into Agent A's chat; no action needed beyond following it)

Two more agents are now working in parallel on separate git worktrees, branched from a snapshot of your tree taken at
10:00. Your working tree, index and `main` were not touched, and nothing will be merged into `main` until you finish
Rounds 1–2 and the user commits your work.

- **Agent B** (`/Users/nakash/Desktop/mizrahi2-agentB`, ports 8796/5857) builds the Round 3 follow-up engine backend.
- **Agent C** (`/Users/nakash/Desktop/mizrahi2-agentC`, ports 8797/5858) builds Round 4 Admin Settings.

Please keep to the following until integration.

1. **Don't create files at these paths.** They would collide with B's or C's new files:
   - `backend/app/{clock,capabilities,flags,events}.py`
   - `backend/app/followup/`, `backend/app/comms/`
   - `backend/app/policy/{validate,simulator,prompts,proposal}.py`
   - `backend/policy/scenarios/`
   - `backend/tests/test_followup_*`, `test_talk_*`, `test_upload_links.py`, `test_clock.py`, `test_admin_*`,
     `test_parallel_contracts.py`
   - `frontend/src/pages/admin/`, `frontend/src/adminApi.ts`, `frontend/src/admin.css`
   - `e2e/test_admin_ui.py`
2. **Don't edit** `backend/app/api/followup.py` (B's), `backend/app/api/admin.py` (C's) or `backend/app/policy/store.py`
   (handed to C, additions only).
3. **These are frozen contracts B and C depend on.** If you must change one, tell the user first:
   - The 14 Round 3/4 tables in `db.py` (names and columns).
   - `policy/schema.py`: section and field names, `PROMPT_VARIABLES`.
   - The `store.py` public functions.
   - `requirements.for_case` keys: `code, requirement_id, family, required, borrower_id, account_id, title_he,
     policy_version`.
   - `readiness.compute` keys `state, case_status, requirements, pending_jobs, counts` and per-requirement
     `code, family, ai_state, open_customer_actions, accepted_document_ids`.
   - The `ai_state` values, and `CASE_STATUS_HE` including `FOLLOWUP_IN_PROGRESS` / `AWAITING_CUSTOMER`.
   - The staff ids and capabilities in `mock_bank.STAFF`, and `case["contact"]` fields.
   - Cases 009 (follow-up journey) and 010 (no consent).
   - `auth.issue`, `auth._set`, `auth.require_*`.
4. **Ports:** don't use 8796, 8797, 5857 or 5858. Yours stay 8791/5192 (+ 8798/5846/8801 for isolated stacks).
5. **After Rounds 1–2 (gate G5),** you will own the Round 3 frontend against B's API: the presence hook in
   `caseContext.tsx`, the customer snooze / contact-preference / handoff controls, the banker Talk card, timeline and
   overrides, and the presenter simulation controls. (Scope v2: the demo routes and `/admin` need only the demo
   staff session `api.demoStaff()` already obtains. There is no capability or persona work for you.)

   The full contract is in `docs/plans/parallel/CONTRACTS.md` on branch `parallel/base`. Read it with
   `git show parallel/base:mizrahi-touch-ai-demo/docs/plans/parallel/CONTRACTS.md`, which doesn't change your tree.
