"""Golden files for the Hebrew baseline: a response recorded before the bilingual work must stay byte-identical.

    GOLDEN_RECORD=1 .venv/bin/python -m pytest -q tests/test_golden_hebrew_*.py   # (re)record — only on the baseline

Ids and timestamps are random per run, so they are replaced by stable placeholders before comparing; everything else
(Hebrew wording, numbers, order, structure) is compared exactly."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

GOLDEN = Path(__file__).resolve().parent / "golden"
_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+00:00|Z)?")
# database row ids (AUTOINCREMENT): their value depends on what ran before in the same test session
ROW_IDS = {"event_id"}
_ID = re.compile(r"\b([A-Z][A-Z0-9]{0,7})-[0-9A-F]{8,12}\b|\b(DEMO-LN-\d{4}|PRS-NEW)-[0-9A-F]{4}\b")


def normalize(value: Any, literals: tuple[str, ...] = ()) -> Any:
    """Stable placeholders for ids and timestamps; ids keep their prefix and their order of first appearance.
    `literals`: other random values of the run (a created case's display number), replaced wherever they appear."""
    seen: dict[str, str] = {}

    def sub_id(m: re.Match) -> str:
        prefix = m.group(1) or re.sub(r"-\d{4}$", "", m.group(2))
        return seen.setdefault(m.group(0), f"{prefix}-<{len(seen) + 1}>")

    def walk(v: Any) -> Any:
        if isinstance(v, dict):
            return {walk(k): (seen.setdefault(f"#{k}:{x}", f"<{k}-{len(seen) + 1}>") if k in ROW_IDS else walk(x))
                    for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, str):
            for i, lit in enumerate(literals):
                v = v.replace(lit, f"<RANDOM-{i + 1}>")
            return _ID.sub(sub_id, _TS.sub("<TS>", v))
        return v
    return walk(value)


def check(name: str, actual: Any, literals: tuple[str, ...] = ()) -> None:
    """Compare `actual` (normalized) with tests/golden/<name>.json, or record it when GOLDEN_RECORD=1."""
    path = GOLDEN / f"{name}.json"
    got = json.dumps(normalize(actual, literals), ensure_ascii=False, indent=1, sort_keys=False)
    if os.environ.get("GOLDEN_RECORD") == "1":
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(got + "\n", encoding="utf8")
        return
    assert path.exists(), f"no golden file {path.name}: record it on the baseline with GOLDEN_RECORD=1"
    want = path.read_text(encoding="utf8").rstrip("\n")
    if got != want:
        a, b = want.splitlines(), got.splitlines()
        i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        raise AssertionError(f"{name}: differs from the Hebrew baseline at line {i + 1}:\n"
                             f"  baseline: {a[i] if i < len(a) else '<end>'}\n  now:      {b[i] if i < len(b) else '<end>'}")
