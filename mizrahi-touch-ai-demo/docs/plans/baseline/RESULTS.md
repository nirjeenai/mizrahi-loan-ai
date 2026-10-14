# Round 0 baseline (2026-10-13, unchanged mortgage app in Mizrahi #2)

- Backend tests: `pytest -q tests` → **100 passed**.
- Frontend typecheck: `tsc --noEmit -p .` → clean.
- Executive demo browser suite, **REPLAY** stack (backend :8798, frontend :5846, DATA_DIR
  `e2e/artifacts/featured/data-baseline`): **25/25 checks passed**, 20 extract/judge answers from recordings,
  no Gemini call.
- Screenshots in this folder: `customer-*.png`, `banker-*.png`, `system.png` (from `e2e/baseline_screens.py`,
  case 008 after the suite) and `01…11-*.png` (from `e2e/test_featured_demo.py`).
