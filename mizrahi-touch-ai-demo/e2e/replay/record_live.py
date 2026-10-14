"""Records LIVE Gemini answers for the personal-loan fixtures into e2e/replay/recordings.json (RECORDED_LIVE).

Runs the real GeminiReviewProvider (extract → evidence → deterministic → judge → merge) on each file against the rubric
of the requirement it is uploaded for, in a throw-away DATA_DIR, and stores the raw extract and judge answers by the
file's SHA-256 (judge answers per rubric, so the same file can be replayed in a wrong slot). Real, paid Gemini calls:
about two per file. Run only with the user's go-ahead:

    backend/.venv/bin/python e2e/replay/record_live.py            # all pending files
    backend/.venv/bin/python e2e/replay/record_live.py --dry-run  # list what would be recorded
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

E2E = Path(__file__).resolve().parents[1]
ROOT = E2E.parent
BACKEND = ROOT / "backend"
OUT = Path(__file__).resolve().parent / "recordings.json"
LOAN = ROOT / "fixtures" / "presenter" / "loan_set"
GOLDEN = ROOT / "fixtures" / "presenter" / "golden_set"
CASE = "DEMO-MTZ-2026-009"
# (file, family of the slot it is uploaded into, requirement code)
PLAN = [
    (LOAN / "id_card_ido.pdf", "id_document", "ID_CARD:BRW-A"),
    (LOAN / "id_card_ido_EXPIRED.pdf", "id_document", "ID_CARD:BRW-A"),
    (LOAN / "id_card_ido_UNREADABLE.pdf", "id_document", "ID_CARD:BRW-A"),
    (LOAN / "statement_ido_2026-07_09.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1"),
    (LOAN / "statement_ido_2026-07.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1"),
    (LOAN / "statement_ido_2026-08.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1"),
    (LOAN / "statement_ido_2026-09.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1"),
    (LOAN / "statement_ido_STALE_2026-04_06.pdf", "bank_statement", "BANK_STATEMENTS:ACC-1"),
    (LOAN / "car_quote_ido.pdf", "purpose_proof", "PURPOSE_PROOF"),
    (LOAN / "car_quote_ido_OLD.pdf", "purpose_proof", "PURPOSE_PROOF"),
    (GOLDEN / "01_INITIAL_UPLOADS" / "ido_2026_09.pdf", "payslip", "PAYSLIPS:BRW-A"),
    (GOLDEN / "01_INITIAL_UPLOADS" / "ido_2026_07.pdf", "id_document", "ID_CARD:BRW-A"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT / "fixtures"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-record entries that already have a LIVE answer")
    a = ap.parse_args()
    data = json.loads(OUT.read_text(encoding="utf8"))
    docs = data["documents"]

    def pending(path: Path, family: str) -> bool:
        rec = docs.get(sha(path)) or {}
        from_rubric = (rec.get("judge_by_rubric") or {})
        return a.force or family_rubric(family) not in from_rubric

    todo = [p for p in PLAN if pending(p[0], p[1])]
    print(f"{len(todo)} of {len(PLAN)} file × rubric combinations to record")
    for path, family, code in todo:
        print(" ·", rel(path), "→", family)
    if a.dry_run or not todo:
        return

    os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="record-live-")
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    from app import db
    from app.bank.mock_bank import bank
    from app.llm import gemini as g
    from app.policy import store
    from app.review import rubrics
    from app.review.contract import DocumentReviewRequest
    from app.review.gemini_provider import GeminiReviewProvider

    db.connect()
    store.ensure_seeded()
    captured: dict[str, dict] = {}
    real = g.generate

    def capture(model, contents, *, purpose, run_id=None, **kw):
        out = real(model, contents, purpose=purpose, run_id=run_id, **kw)
        if purpose in ("extract", "judge"):
            captured[purpose] = g.response_json(out)
        return out

    g.generate = capture
    provider = GeminiReviewProvider()
    ctx = bank.case_context(CASE)
    for path, family, code in todo:
        captured.clear()
        rubric = rubrics.for_family(family)
        req = DocumentReviewRequest(case_id=CASE, document_id=f"REC-{sha(path)[:8]}", filename=path.name,
                                    mime="application/pdf", storage_path=str(path), assigned_borrower_id="BRW-A",
                                    requirement_code=code, case_context=ctx, rubric=rubric, run_id=f"REC-{sha(path)[:8]}")
        result = provider._review_document(req, lambda stage: None)
        key = sha(path)
        entry = docs.setdefault(key, {"file": rel(path), "provenance": "RECORDED_LIVE"})
        if "extract" not in entry or a.force or entry.get("provenance") != "RECORDED_LIVE":
            entry["extract"] = captured["extract"]
        judge = captured.get("judge") or {}
        entry.setdefault("judge_by_rubric", {})[rubric["rubric_id"]] = {
            "criteria": {c["criterion_id"]: {"outcome": c["outcome"], "explanation_he": c["explanation_he"]}
                         for c in judge.get("criteria") or []},
            **{k: judge.get(k) or ([] if k != "summary_he" else "") for k in ("summary_he", "limitations_he", "uncertainty_he")}}
        entry["provenance"] = "RECORDED_LIVE" if entry.get("provenance") in (None, "RECORDED_LIVE") else entry["provenance"]
        entry.setdefault("sources", []).append(
            f"live Gemini review {date.today().isoformat()} · {path.name} · rubric {rubric['rubric_id']}@{rubric['version']}"
            f" · verdict {result.verdict} · doc_type {result.doc_type}")
        print(f"recorded {path.name} × {rubric['rubric_id']}: {result.doc_type} {result.verdict} {result.verdict_reason_codes}")
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print("ledger:", g.ledger_summary())


def family_rubric(family: str) -> str:
    return {"payslip": "payslip.il.salaried", "id_document": "id_document.il", "bank_statement": "bank_statement.il",
            "purpose_proof": "purpose_proof.il", "tax_form": "tax_form.il"}[family]


if __name__ == "__main__":
    main()
