"""Keeps the automated suites off the user's own data. A suite that uploads, resets, decides or creates cases calls
require_isolated(BASE) first: the backend behind BASE says in /api/health whether it runs on the default DATA_DIR
(backend/data, the user's :8791), and the suite stops if it does — also when BASE is an isolated frontend
(e2e/serve_frontend.mjs) that proxies to that backend. Mizrahi #1 (:8790) is refused by its port.

    import isolation
    isolation.require_isolated(BASE)

E2E_ALLOW_MAIN=1 lifts the check, for a run the user asked for on their own data."""
from __future__ import annotations

import os
import sys

import httpx

FOREIGN = (":8790",)
MAIN_PORTS = (":8791", ":5192")


def require_isolated(base: str) -> None:
    if not base:
        return
    if any(p in base for p in FOREIGN):
        sys.exit(f"refusing to run against {base}: that is Mizrahi #1")
    if os.environ.get("E2E_ALLOW_MAIN") == "1":
        return
    try:
        health = httpx.get(f"{base.rstrip('/')}/api/health", timeout=10).json()
    except Exception:                     # not up yet or not this app: the suite's own first request reports it
        return
    data = health.get("data") if isinstance(health, dict) else None
    if data == "main" or (data is None and any(p in base for p in MAIN_PORTS)):
        sys.exit(f"refusing to run against {base}: its backend serves the main data (backend/data). Start an isolated "
                 "stack (DATA_DIR=… on another port, see .claude/skills/run-stack) or set E2E_ALLOW_MAIN=1.")
