"""Fill the generated sections of Document A from the machine-readable deliverables.

Usage:  python tools/build_master_spec.py
Reads:  B_MORTGAGE_DOCUMENT_REQUIREMENTS_MATRIX.csv, C_MORTGAGE_RUBRIC_LIBRARY/{rubrics/*.json,reason_codes.json},
        E_golden/scenarios.v1.json
Writes: the blocks between <!-- GEN:NAME --> and <!-- /GEN:NAME --> in A_VISIONTRACE_MORTGAGE_FULL_SPEC_HE.md.
Re-running is idempotent; nothing outside the markers changes.
"""
from __future__ import annotations

import collections
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "A_VISIONTRACE_MORTGAGE_FULL_SPEC_HE.md"
MATRIX = ROOT / "B_MORTGAGE_DOCUMENT_REQUIREMENTS_MATRIX.csv"
RUBRICS = sorted((ROOT / "C_MORTGAGE_RUBRIC_LIBRARY" / "rubrics").glob("*.json"))
CODES = ROOT / "C_MORTGAGE_RUBRIC_LIBRARY" / "reason_codes.json"
SCENARIOS = ROOT / "E_golden" / "scenarios.v1.json"


def cell(text, limit: int | None = None) -> str:
    s = " ".join(str(text if text is not None else "").split()).replace("|", "\\|")
    if limit and len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s


def matrix_rows() -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(MATRIX.open(encoding="utf-8-sig")))
    return rows[0], rows[1:]


def gen_taxonomy() -> str:
    header, rows = matrix_rows()
    col = {h: i for i, h in enumerate(header)}
    by_family: dict[str, list[list[str]]] = collections.OrderedDict()
    for r in rows:
        by_family.setdefault(r[col["משפחה"]], []).append(r)
    out = ["| משפחה | מסמכים (קוד — שם · עדיפות · היקף VisionTrace) |", "|---|---|"]
    for fam, docs in by_family.items():
        items = "<br>".join(f"`{d[0]}` — {cell(d[col['1. שם רשמי (עברית)']], 70)} · {d[col['23. עדיפות']]} · {d[col['היקף VisionTrace']]}"
                            for d in docs)
        out.append(f"| {cell(fam)} | {items} |")
    return "\n".join(out)


def gen_matrix() -> str:
    header, rows = matrix_rows()
    col = {h: i for i, h in enumerate(header)}
    out = ["| קוד | שם | מתי נדרש | תנאי תחולה | סיווג | תוקף / עדכניות | בסיס | עדיפות | רובריקה | היקף |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| " + " | ".join([
            f"`{r[0]}`",
            cell(r[col["1. שם רשמי (עברית)"]], 60),
            cell(r[col["6. מתי נדרש"]], 110),
            cell(r[col["7. תנאי תחולה"]], 110),
            cell(r[col["9. סיווג דרישה"]], 60),
            cell(r[col["10. תוקף / עדכניות / תקופה"]], 110),
            cell(r[col["22. מדיניות מאומתת או כלל מוצע"]], 40),
            cell(r[col["23. עדיפות"]]),
            cell(r[col["רובריקה"]]),
            cell(r[col["היקף VisionTrace"]]),
        ]) + " |")
    return "\n".join(out)


def load_rubrics() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf8")) | {"_file": p.name} for p in RUBRICS]


def applies(r: dict) -> str:
    a = r.get("applies_to") or {}
    parts = []
    for key, label in (("doc_types", "סוגי מסמך"), ("requirement_codes", "דרישות"), ("employment_types", "העסקה"),
                       ("transaction_types", "עסקה")):
        v = a.get(key)
        if v:
            parts.append(f"{label}: {', '.join(map(str, v))}")
    return "; ".join(parts) or "—"


def gen_rules() -> str:
    out = []
    for r in load_rubrics():
        crit = [c for c in r["criteria"] if c["method"] in ("deterministic", "hybrid")]
        if not crit:
            continue
        rb = r["_file"].split("_")[0]
        out.append(f"#### {rb} · `{r['rubric_id']}@{r['version']}` — {r['name_he']} ({r['priority']}, {r['scope']})")
        out.append(f"תחולה: {cell(applies(r))}")
        out.append("")
        for c in crit:
            head = (f"- **{c['id']}** — {cell(c['title_he'])} · `{c['method']}` · {c['severity']} · "
                    f"`{c.get('reason_code') or '—'}` · on_fail `{c.get('on_fail') or '—'}`")
            out.append(head)
            out.append(f"  - קלטים: {cell('; '.join(c.get('inputs') or []))}")
            logic = c.get("deterministic_logic")
            if logic:
                out.append(f"  - לוגיקה: {cell(logic)}")
            outcomes = []
            for key, label in (("pass_when", "PASS"), ("fail_when", "FAIL"), ("needs_review_when", "NEEDS_REVIEW"),
                               ("insufficient_evidence_when", "INSUFFICIENT"), ("not_applicable_when", "N/A")):
                if c.get(key):
                    outcomes.append(f"{label}: {cell(c[key], 220)}")
            if outcomes:
                out.append(f"  - תוצאות: {' · '.join(outcomes)}")
            out.append(f"  - ראיה נדרשת: {cell(', '.join(c.get('citations_required') or []) or '—')} · "
                       f"בסיס: {c.get('requirement_basis', '—')} ({cell(', '.join(c.get('source_refs') or []) or '—')})")
        out.append("")
    return "\n".join(out).rstrip()


def gen_judge() -> str:
    out = []
    for r in load_rubrics():
        crit = [c for c in r["criteria"] if c["method"] in ("judge", "hybrid")]
        if not crit:
            continue
        rb = r["_file"].split("_")[0]
        out.append(f"#### {rb} · `{r['rubric_id']}@{r['version']}` — {r['name_he']}")
        allowed = r.get("allowed_inference_he") or []
        prohibited = r.get("prohibited_inference_he") or []
        if allowed:
            out.append(f"- **מותר להסיק:** {cell(' · '.join(allowed))}")
        if prohibited:
            out.append(f"- **אסור להסיק:** {cell(' · '.join(prohibited))}")
        for c in crit:
            ji = c.get("judge_instructions") or "—"
            out.append(f"- **{c['id']}** ({c['method']}, {c['severity']}, `{c.get('reason_code') or '—'}`) — "
                       f"{cell(c['title_he'])}. הוראות לשופט: {cell(ji)}")
        out.append("")
    return "\n".join(out).rstrip()


def gen_codes() -> str:
    data = json.loads(CODES.read_text(encoding="utf8"))
    out = ["| קוד | כותרת | חומרה | review_state | קטגוריה | שימוש |", "|---|---|---|---|---|---|"]
    for c in data["codes"]:
        used = c.get("used_by") or []
        where = "פלטפורמה" if used == ["platform"] else f"{len(used)} קריטריונים"
        out.append(f"| `{c['code']}` | {cell(c.get('title_he'), 80)} | {c.get('default_severity')} | "
                   f"{', '.join(c.get('review_states') or []) or '—'} | {c.get('category')} | {where} |")
    return "\n".join(out)


def gen_scenarios() -> str:
    data = json.loads(SCENARIOS.read_text(encoding="utf8"))
    out = ["| מזהה | תרחיש | קטגוריה | עדיפות | פרופיל קריאה | שלבים |", "|---|---|---|---|---|---|"]
    for s in data["scenarios"]:
        out.append(f"| {s['id']} | {cell(s['title_he'])} | {s['category']} | {s['priority']} | {s.get('profile', '—')} | "
                   f"{len(s.get('steps') or [])} |")
    return "\n".join(out)


def gen_example_criterion() -> str:
    for r in load_rubrics():
        for c in r["criteria"]:
            if c["id"] == "PSL-PER-01":
                return "```json\n" + json.dumps(c, ensure_ascii=False, indent=2) + "\n```"
    raise SystemExit("PSL-PER-01 not found")


BLOCKS = {
    "TAXONOMY": gen_taxonomy,
    "MATRIX": gen_matrix,
    "RULES": gen_rules,
    "JUDGE": gen_judge,
    "CODES": gen_codes,
    "SCENARIOS": gen_scenarios,
    "EXAMPLE_CRITERION": gen_example_criterion,
}


def main() -> None:
    text = SPEC.read_text(encoding="utf8")
    for name, fn in BLOCKS.items():
        pattern = re.compile(rf"(<!-- GEN:{name} -->)(.*?)(<!-- /GEN:{name} -->)", re.S)
        if not pattern.search(text):
            raise SystemExit(f"marker GEN:{name} missing in {SPEC.name}")
        body = fn()
        text = pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)
    SPEC.write_text(text, encoding="utf8")
    print(f"✓ {SPEC.name}: {len(BLOCKS)} generated blocks, {len(text):,} chars")


if __name__ == "__main__":
    main()
