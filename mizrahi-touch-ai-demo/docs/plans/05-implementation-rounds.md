# 05 — Phased End-to-End Implementation Plan

Every round ends with: backend tests, frontend typecheck, a build, the REPLAY featured browser suite on an isolated
stack (never :8790), and screenshots compared with `docs/plans/baseline/`. Live Gemini runs only with the user's OK.

## Round 0 — Planning artifacts and baseline
- Objective: documents 01–06; baseline screenshots and REPLAY results of the unchanged app.
- Exit gate: roadmap approved.

## Round 1 — Isolated loan foundation
- **Objective:** #2 runs isolated from #1; the product speaks "personal loan"; requirements come from a versioned config.
- **Existing assets:** whole pipeline, desk, presenter, agent; `PAYSLIPS:{borrower}` requirement code kept.
- **Tasks:** `run.sh` (PORT 8791, Vite 5192), `frontend/vite.config.ts` (`MZ_API`), e2e/test defaults → 8791,
  `auth.py` cookies `mzl_*`; `backend/app/policy/{schema,store}.py`, `config_versions`, seed
  `backend/policy/seed/personal_loan.demo.json`; `bank/mock_bank.py` loan cases (purpose, amount, payments,
  applicants, accounts, contact consent, loan stages), staff with roles; `workflow/requirements.py` (instances,
  `case_profile` pin); readiness consumes instances; loan copy in UI, agent, outcomes, desk templates, prompts.
- **Tests:** updated case tests; `test_requirements.py`; `test_policy_store.py`.
- **Acceptance:** green suite; no "משכנת" in customer/banker UI strings; #1 untouched; separate cookies.
- **Demo:** featured loan cases with the PASS/REVIEW/BLOCKER payslip stories.
- **Risks:** readiness consumers; REPLAY recordings made under the previous prompt wording.

## Round 2 — Multi-document review and application intake
- **Objective:** ID, bank statements and purpose proof reviewed by the real pipeline; new applications.
- **Tasks:** per-family field sets and extraction schema (`review/prompts.py`, `PROMPT_VERSION` bump); rubrics
  `id_document.il`, `bank_statement.il`, `purpose_proof`, `tax_form`; deterministic checks (ID check digit,
  statement coverage/gaps/age, recency); dispatch by detected type; `review/reason_codes.py`; family coverage and
  cross-family identity in requirement engine; `fixtures/loan/generate.py`; live recording (approved) → REPLAY;
  intake screen + `demo_applications`; UploadSheet type from requirement; Documents groups; per-family evidence
  fields; banker requirement matrix; `AppAction.document_type` union.
- **Acceptance:** VALID/INVALID/UNDETERMINED per family; wrong type never VALID; READY only with all mandatory instances.

## Round 3 — Completion orchestration and simulated Talk
- **Objective:** self-service → grace → simulated call → link → corrected upload → ready, fully backend-driven.
- **Tasks:** `clock.py`; `case_events`; `followup/{tasks,presence,policy,orchestrator,links}.py`; job kinds;
  pre-dispatch gate; `comms/{contract,mock_talk,jeen_talk,webhook}.py`; customer controls and tools; banker Talk
  card, timeline, overrides; presenter simulation controls; kill switch; `/system` readiness; MCP
  `get_followup_context`.
- **Tests:** `test_followup_policy.py` (scenario catalogue), `test_followup_flow.py` (integration through routes),
  `test_talk_webhook.py` (signature, dedupe, ordering, orphan), `test_upload_links.py`.

## Round 4 — Admin Settings, Customize Prompt, simulator, governance
- **Tasks:** capabilities; `api/admin.py`; `policy/{validate,simulator,prompts,proposal}.py`; `/admin` UI with five
  tabs; draft/ETag/diff/publish/rollback/audit; kill switch UI; environment banner; prompt lint + preview + test
  conversation; templates; NL proposal.
- **Tests:** `test_admin_settings.py` (RBAC, conflicts, publish gate, rollback, simulator side-effect free).

## Round 5 — Integration, scenarios, failure paths, regression, Talk readiness
- **Tasks:** loan presenter manifest scenarios; browser suite `e2e/test_loan_completion.py` (customer mobile,
  banker desktop, admin); failure injection; ops metrics panel; README + CODEMAP; Talk handoff pack
  (`docs/plans/07-jeen-talk-handoff.md`) and provider contract tests.
- **Exit:** all suites green; every PRD AC mapped to a passing test or an explicit deferral.
