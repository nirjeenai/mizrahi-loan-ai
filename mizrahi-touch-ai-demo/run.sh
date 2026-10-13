#!/usr/bin/env bash
# Mizrahi Tefahot Touch × JEEN — concept demo on synthetic data.
#   ./run.sh setup   install backend + frontend, build the app, generate fixtures, create backend/.env
#   ./run.sh start   serve API + MCP + built app on http://127.0.0.1:8790 (default)
#   ./run.sh dev     Vite dev server on :5190 (proxies /api and /mcp) + backend on :8790
#   ./run.sh test    unit tests, browser end-to-end journey (real Gemini), MCP SDK checks, presenter pane checks — backend must be running
#   ./run.sh reset   clear the demo case and the QA case back to "not checked"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8790}"
PY="$ROOT/backend/.venv/bin/python"

setup() {
  [ -x "$PY" ] || "${PYTHON:-python3}" -m venv "$ROOT/backend/.venv"
  "$PY" -m pip install -q -r "$ROOT/backend/requirements-dev.txt"
  (cd "$ROOT/frontend" && npm install --silent && npm run build)
  [ -f "$ROOT/fixtures/out/manifest.json" ] || "$PY" "$ROOT/fixtures/generate.py"
  if [ ! -f "$ROOT/backend/.env" ]; then
    "$PY" - "$ROOT/backend/.env.example" "$ROOT/backend/.env" <<'EOF'
import secrets, sys
text = open(sys.argv[1], encoding="utf8").read()
for name in ("MCP_DEMO_KEY", "MCP_DEMO_KEY_2"):
    text = text.replace(f"\n{name}=\n", f"\n{name}=mcs_{secrets.token_urlsafe(24)}\n", 1)
open(sys.argv[2], "w", encoding="utf8").write(text)
EOF
    chmod 600 "$ROOT/backend/.env"
    echo "Created backend/.env — set GEMINI_API_KEY there before ./run.sh start"
  fi
}

start() {
  cd "$ROOT/backend" && exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
}

dev() {
  trap 'trap - EXIT; kill 0' EXIT INT TERM
  (cd "$ROOT/frontend" && npm run dev) &
  cd "$ROOT/backend" && ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --reload
}

run_tests() {
  (cd "$ROOT/backend" && ./.venv/bin/python -m pytest -q tests)
  "$PY" "$ROOT/e2e/test_journey.py"
  "$PY" "$ROOT/e2e/test_mcp_sdk.py"
  "$PY" "$ROOT/e2e/test_presenter.py"
}

reset() {
  # the service has no anonymous access: take the demo banker's session (demo mode), then reset her cases
  local jar; jar="$(mktemp)"
  curl -fsS -c "$jar" -H 'Content-Type: application/json' -d '{}' -X POST "http://127.0.0.1:$PORT/api/session/demo/staff" >/dev/null
  for c in DEMO-MTZ-2026-001 DEMO-MTZ-2026-003; do
    curl -fsS -b "$jar" -X POST "http://127.0.0.1:$PORT/api/cases/$c/reset" >/dev/null
  done
  rm -f "$jar"
  echo "demo cases reset"
}

case "${1:-start}" in
  setup) setup ;;
  start) start ;;
  dev) dev ;;
  test) run_tests ;;
  reset) reset ;;
  *) echo "usage: $0 [setup|start|dev|test|reset]"; exit 2 ;;
esac
