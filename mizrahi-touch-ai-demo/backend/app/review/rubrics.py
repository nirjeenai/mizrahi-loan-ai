"""Versioned rubrics on disk: rubrics/<rubric_id>.v<version>.json. Loaded and checked
once; a rubric is data — changing one never changes code."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..config import settings

ALLOWED_METHODS = {"deterministic", "judge", "hybrid"}


def _check(rubric: dict[str, Any], name: str) -> dict[str, Any]:
    for key in ("rubric_id", "version", "scope", "criteria"):
        if key not in rubric:
            raise ValueError(f"rubric {name}: missing {key}")
    seen = set()
    for c in rubric["criteria"]:
        if c["id"] in seen:
            raise ValueError(f"rubric {name}: duplicate criterion {c['id']}")
        seen.add(c["id"])
        if c["method"] not in ALLOWED_METHODS:
            raise ValueError(f"rubric {name}: bad method {c['method']}")
    return rubric


@lru_cache(maxsize=None)
def all_rubrics() -> dict[str, dict[str, Any]]:
    out = {}
    for path in sorted(settings.rubrics_dir.glob("*.json")):
        rubric = _check(json.loads(path.read_text(encoding="utf8")), path.name)
        out[f"{rubric['rubric_id']}@{rubric['version']}"] = rubric
    return out


def latest(rubric_id: str) -> dict[str, Any]:
    versions = [r for r in all_rubrics().values() if r["rubric_id"] == rubric_id]
    if not versions:
        raise KeyError(rubric_id)
    return sorted(versions, key=lambda r: tuple(int(x) for x in r["version"].split(".")))[-1]


def for_document(requirement_code: str | None) -> dict[str, Any]:
    return latest("payslip.il.salaried")


def for_case() -> dict[str, Any]:
    return latest("income-set.salaried")
