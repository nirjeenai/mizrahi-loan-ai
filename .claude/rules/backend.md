---
paths:
  - "mizrahi-touch-ai-demo/backend/**"
---

# Backend rules (FastAPI · SQLite · Gemini)

Locations and couplings: `mizrahi-touch-ai-demo/docs/CODEMAP.md`. Behavior: README "Architecture".

## Patterns to follow
- Every module starts with a docstring stating its responsibility; keep `from __future__ import annotations`.
- Case data goes through `app/store/repo.py`. Raw SQL elsewhere exists only for the job queue (`workflow/engine.py`),
  readiness reads and the LLM ledger (`llm/gemini.py`). Don't add more.
- A state change and its audit event are written together: `with db.tx():` … `repo.audit(...)`.
- Banker writes: `@_serialized` + a `request_id` replay check (see `workflow/review_desk.py`); invalid transitions
  raise `DeskError` with a Hebrew message and an HTTP status.
- Schema: add tables to `db.SCHEMA`; a new column on an existing table also goes into `db.ADDED_COLUMNS`.
- Gemini only through `llm/gemini.generate` (budget, retries, ledger), with a JSON response schema. Its output is
  input to code: code merges it with precedence and computes the verdict, state and permissions.
- Changing `review/prompts.py` (prompt text or schema) means bumping `PROMPT_VERSION`.
- Every route checks the session (`app/auth.py`): customer routes `require_customer_case` (or `require_reader` for document
  files and pages), banker reads `require_staff`, banker writes `require_assigned_staff`. Raw findings/audit/runs are
  staff-only. Never take identity from a request header.
- Anything a banker writes that reaches customer endpoints is projected (`CUSTOMER_SAFE_DETAIL`, `_customer_finding`
  in `api/routes.py`). Internal rationale never leaves the banker API.
- Agent/MCP tools live once in `agent/tools.py`. Write tools require `customer_confirmed=true` and are idempotent.
  Adding a tool changes the MCP catalog (`e2e/test_mcp_sdk.py` asserts 10 tools).
- User-facing strings are Hebrew. Customer messages are deterministic templates (`review_desk.draft_*`).

## Changing a rubric (`backend/rubrics/`)
1. Never edit a released version. Copy it to `<rubric_id>.v<next semver>.json` and add a `changelog` entry;
   `review/rubrics.py::latest` picks the highest version automatically. Older versions stay for history.
2. A `deterministic` criterion needs code in `review/deterministic.py` and/or `GeminiReviewProvider._deterministic`;
   `judge`/`hybrid` criteria flow through `_judge` and `_merge` (code precedence for hybrid).
3. A new document-level `reason_code` needs Hebrew text in `review/case_review.py::DOC_FINDING_TEXT`.
4. Add or update tests (`tests/test_pay_date.py` shows criterion-level testing without Gemini).
5. If outcomes on the golden set may change: update `fixtures/presenter/presenter_scenarios_manifest.json`
   expectations only with user approval, and run `e2e/test_presenter.py --live` on an isolated stack (paid: ask first).
6. Update README "Rubrics".

## Tests
- `tests/conftest.py` sets a temp `DATA_DIR` and disables Gemini before any app import. Unit tests must never call Gemini:
  seed reviews through `repo` as `tests/test_review_desk.py` does, and use `TestClient(app)` for routes.
- Run: `cd mizrahi-touch-ai-demo/backend && .venv/bin/python -m pytest -q tests`.
