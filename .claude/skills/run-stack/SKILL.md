---
name: run-stack
description: Start, smoke-test and stop the Mizrahi Touch demo app — the user's main instance on :8791 or an isolated backend+frontend pair with its own DATA_DIR — and run the browser E2E suites (mizrahi-touch-ai-demo/e2e/*.py) against it. Use to run or launch the app, verify a UI or workflow change in the real app, run an E2E suite, or debug an E2E failure.
---

# Run the stack and E2E suites

All paths are relative to `mizrahi-touch-ai-demo/`.

## Ground rules
- The server on :8791 holds the user's demo data. Never stop or reset it, and never point a suite that resets or
  uploads at it, unless the user asks. Verify on an isolated stack instead.
- Suites marked "Gemini" make real, paid calls. Name the suite and the rough call count and get the user's OK first
  (`.claude/settings.json` asks before any `e2e/test_*.py`).
- Run servers with `run_in_background`, note their PIDs, and stop exactly what you started.
- Report results only from the suite's own output or results file. Say which checks you did not run.

## 1. Main instance (:8791)
- Up? `curl -s http://127.0.0.1:8791/api/health`
- Start (only if it isn't running and the user wants it): `./run.sh start` in the background.
- Read-only endpoints: `/api/health`, `/api/cases`, `/api/cases/{id}`, `/api/cases/{id}/documents`, `/api/system/rubrics`,
  `/api/system/llm`, `/api/fixtures`, `/api/presenter/scenarios`, `/api/banker/cases/{id}/workspace`.
  Not read-only: any POST, `GET /api/cases/{id}/conversation` (writes turns), `GET /api/system/integrations` and the
  `/system` page (network probe to VisionTrace when `VISIONTRACE_MCP_KEY` is set).
- Every `/api` route except health, fixtures, presenter files and `/api/session/*` needs a session (`backend/app/auth.py`);
  without one it returns 401. Demo mode (`DEMO_IDENTITY=1`, default) hands sessions out without a login. curl:
  `curl -s -c /tmp/j -H 'Content-Type: application/json' -d '{"case_id":"DEMO-MTZ-2026-001"}' :PORT/api/session/demo/customer`
  (or `-d '{}' …/api/session/demo/staff`), then `curl -s -b /tmp/j …`. Python suites: `import demo_auth; demo_auth.install(BASE)`
  (`e2e/demo_auth.py`). The browser apps obtain their own sessions.

## 2. Isolated stack (default for verification)
Pick free ports (`lsof -nP -iTCP:<port> -sTCP:LISTEN` prints nothing): backend 8792–8799, frontend 5841–5860.
Reserved, never use for a throw-away stack: 8790 / 5190 (Mizrahi #1, mortgage) and 8791 / 5192 (this app's main instance).
```bash
# backend — from backend/, in the background. A fresh DATA_DIR starts with every case empty.
DATA_DIR=../e2e/artifacts/<suite>/data-<tag> ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port <BPORT>
# (python -m, never .venv/bin/uvicorn: the copied venv's console scripts point at Mizrahi #1's interpreter)
# no-cost variant for smoke tests: prefix  GEMINI_API_KEY= GEMINI_MAX_CALLS_PER_HOUR=0
# (environment variables win over backend/.env, which the isolated backend otherwise reads for its keys)

# frontend — from mizrahi-touch-ai-demo/, in the background. Builds into its own folder; never touches frontend/dist.
node e2e/serve_frontend.mjs e2e/artifacts/<suite>/web-<tag> <FPORT> http://127.0.0.1:<BPORT>
```
- Ready when `curl -s http://127.0.0.1:<BPORT>/api/health` returns `"ok":true` and
  `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<FPORT>/customer` returns 200.
- Without the frontend step the backend serves the last `frontend/dist` build itself at `http://127.0.0.1:<BPORT>/customer`.
- Smoke test without cost: `/api/health`, `/api/session/demo/cases` (8 cases), `/customer` and `/banker` return 200.
- REPLAY stack (zero Gemini calls; only the Gemini transport is replaced by `e2e/replay/recordings.json`):
  `.venv/bin/python ../e2e/replay_backend.py --port <BPORT> --data ../e2e/artifacts/featured/data-replay` from backend/,
  then the frontend step above. Every model answer is logged to `<DATA_DIR>/replay-transport.jsonl`; report results as REPLAY.

## 3. Suites (run from mizrahi-touch-ai-demo/: `backend/.venv/bin/python e2e/<suite>`)
| Suite | Target env var (default) | Gemini | Resets / writes | Time |
|---|---|---|---|---|
| `test_presenter.py` | `PRESENTER_BASE` (:8791) | no | resets case 005 via the pane | ~25 s |
| `test_featured_demo.py` | `FEATURED_E2E_BASE` (:5846) + `FEATURED_DATA` | no (REPLAY backend) | resets 006–008 via "התחל דמו חדש", uploads | ~40 s |
| `test_presenter.py --live` | `PRESENTER_BASE` (:8791) | yes | resets 004 and 005, uploads | ~2 min |
| `test_journey.py` | `E2E_BASE` (:8791) | ~37 calls | resets 001 and 003, uploads | ~4 min (voice step needs macOS `say`/`afconvert`) |
| `test_mcp_sdk.py` | `E2E_BASE` (:8791) | no | audit rows only; run after the journey; reads MCP keys from `backend/.env` | <1 min |
| `test_chat_actions.py` | `E2E_BASE` (:8791) | ~26 calls | resets 001 and 003, uploads | ~3 min |
| `test_banker_review.py` | `BANKER_E2E_BASE` (:5853) | yes | resets 001 | ~80 s |
| `test_finding_resolution.py` | `FINDING_E2E_BASE` (:5855) | yes | resets 001 and 004 | ~75 s |
| `test_ai_card.py after` | `CARD_QA_BASE` (:5841) + `CARD_QA_ERROR_BASE` (:5842, backend with `GEMINI_MAX_CALLS_PER_HOUR=0`) | yes | resets every case it uses | see docstring |
| `screens.py`, `banker_screens.py`, `banker_visual.py` | fixed :8791 / `BANKER_SHOTS_BASE` / `BANKER_VISUAL_BASE` | no | none (screenshots) | short |

Each suite's docstring has its exact command; follow it when it differs from this table.
`./run.sh test` runs pytest, `test_journey`, `test_mcp_sdk` and `test_presenter` against :8791 — it resets 001, 003 and 005.

## 4. Evidence and debugging
- Results and screenshots land in `e2e/artifacts/` (gitignored): `e2e-results.json` (journey), `mcp-sdk-results.json`,
  `actions-results.json`, `presenter/presenter-results.json`, `banker/e2e/results.json`, `finding/results.json`,
  `ai-card/after/results.json`.
- A failing check: open its screenshot; find the run via `GET /api/cases/{id}/runs` and read `GET /api/runs/{run_id}`
  (verdict, criteria, evidence); Gemini calls and errors are in `GET /api/system/llm`; the backend log is the uvicorn output.
- Reproduce on a fresh DATA_DIR before changing code. Differences from golden expectations are reported, not asserted away.

## 5. Stop
Stop the background processes you started (by PID). Leave `e2e/artifacts/` in place unless the user asks to clean it.
