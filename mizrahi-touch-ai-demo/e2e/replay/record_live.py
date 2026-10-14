"""Records LIVE Gemini answers for the personal-loan fixtures into e2e/replay/recordings.json (RECORDED_LIVE).

Runs the real GeminiReviewProvider (extract → evidence → deterministic → judge → merge) on each file against the rubric
of the requirement it is uploaded for, in a throw-away DATA_DIR, and stores the raw extract and judge answers by the
file's SHA-256 (judge answers per rubric, so the same file can be replayed in a wrong slot). Includes every AI-reviewed
file of the six use-case packs and the new-customer pack (presenter manifest `useCases` / `newCustomer`), each in the
slot its scenario uploads it to. Real, paid Gemini calls: about two per file. Run only with the user's go-ahead:

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
RESULTS = Path(__file__).resolve().parent / "live_results"
LOAN = ROOT / "fixtures" / "presenter" / "loan_set"
GOLDEN = ROOT / "fixtures" / "presenter" / "golden_set"
LAVI = ROOT / "fixtures" / "out" / "main"
CASE = "DEMO-MTZ-2026-009"
# the Lavi payslips print עידו לביא · 039812457: they are reviewed against the two-applicant Lavi case they belong to
CASE_OF = {LAVI / "ido_payslip_2026-07.pdf": "DEMO-MTZ-2026-003", LAVI / "ido_payslip_2026-08.pdf": "DEMO-MTZ-2026-003"}
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
    (LAVI / "ido_payslip_2026-07.pdf", "payslip", "PAYSLIPS:BRW-A"),
    (LAVI / "ido_payslip_2026-08.pdf", "payslip", "PAYSLIPS:BRW-A"),
]


PROFILES = ROOT / "fixtures" / "presenter" / "profile_set"
NEW_CUSTOMER_CASE = "DEMO-LN-REC-NETA"


def profile_plan() -> list[tuple[Path, str, str]]:
    """Every AI-reviewed file of the use-case packs, in the slot its scenario uploads it to (file, case, requirement)."""
    manifest = json.loads((ROOT / "fixtures" / "presenter" / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
    docs = {d["id"]: d for d in manifest["documents"]}
    out, seen = [], set()
    for case, steps in [(u["caseId"], u["steps"]) for u in manifest["useCases"]] + [(NEW_CUSTOMER_CASE, manifest["newCustomer"]["steps"])]:
        for st in steps:
            d = docs.get(st["file"])
            if not d or d.get("intake") != "ai_review" or st["file"] in seen or st.get("role", "").startswith("banker"):
                continue
            seen.add(st["file"])
            out.append((PROFILES / Path(d["downloadPath"]).name, case, st["uploadAs"]))
    return out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT / "fixtures"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-record entries that already have a LIVE answer")
    ap.add_argument("--only", nargs="*", help="record only these file names (a staged pilot)")
    ap.add_argument("--max-calls", type=int, default=0, help="hard cap on HTTP requests to Gemini, retries included")
    a = ap.parse_args()
    data = json.loads(OUT.read_text(encoding="utf8"))
    docs = data["documents"]

    def pending(path: Path, family: str) -> bool:
        rec = docs.get(sha(path)) or {}
        from_rubric = (rec.get("judge_by_rubric") or {})
        return a.force or family_rubric(family) not in from_rubric

    plan = [(path, family, code, CASE_OF.get(path, CASE)) for path, family, code in PLAN]
    for path, case, code in profile_plan():
        plan.append((path, FAMILY_OF_CODE[code.split(":")[0]], code, case))
    todo = [p for p in plan if pending(p[0], p[1]) and (not a.only or p[0].name in a.only)]
    print(f"{len(todo)} of {len(plan)} file × rubric combinations to record (about {2 * len(todo)} Gemini calls)")
    for path, family, code, case in todo:
        print(" ·", rel(path), "→", family, "·", code, "·", case)
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
    from app.bank import mock_bank
    neta = mock_bank._case(NEW_CUSTOMER_CASE, "438800201", "הלוואה לכל מטרה · רכישת רכב",
                           [mock_bank._person("BRW-A", "נטע", "אלון", "DEMO-ID-201", "primary", ["salaried"], 12000)],
                           mock_bank._loan("car", "רכישת רכב", 80000, 60), mock_bank._accounts(["BRW-A"]),
                           customer_started=True, persona_id="PRS-REC-NETA", applicant_type="individual")
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO demo_applications(case_id, created_at, application) VALUES (?,?,?)",
                  (NEW_CUSTOMER_CASE, "2026-10-12T09:00:00+03:00", db.jdump(neta)))
    captured: dict[str, dict] = {}
    raw: dict[str, dict] = {}
    real = g.generate
    sent = {"n": 0}
    real_post = g.httpx.post

    def counted_post(url, *args, **kw):
        if "generativelanguage.googleapis.com" in str(url):
            if a.max_calls and sent["n"] >= a.max_calls:
                raise SystemExit(f"stopped: the {a.max_calls}-request cap for this run is reached")
            sent["n"] += 1
        return real_post(url, *args, **kw)

    g.httpx.post = counted_post

    def capture(model, contents, *, purpose, run_id=None, **kw):
        out = real(model, contents, purpose=purpose, run_id=run_id, **kw)
        if purpose in ("extract", "judge"):
            captured[purpose] = g.response_json(out)
            raw[purpose] = out                              # the unmodified API response, kept next to the result
        return out

    g.generate = capture
    provider = GeminiReviewProvider()
    for path, family, code, case in todo:
        captured.clear()
        raw.clear()
        ctx = bank.case_context(case)
        rubric = rubrics.for_family(family)
        target = next((r for r in ctx["requirements"] if r["code"] == code), {})
        assigned = target.get("borrower_id") or "BRW-A"
        req = DocumentReviewRequest(case_id=case, document_id=f"REC-{sha(path)[:8]}", filename=path.name,
                                    mime="application/pdf", storage_path=str(path), assigned_borrower_id=assigned,
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
            f"live Gemini review {date.today().isoformat()} · {path.name} · case {case} · rubric {rubric['rubric_id']}@{rubric['version']}"
            f" · verdict {result.verdict} · doc_type {result.doc_type}")
        print(f"recorded {path.name} × {rubric['rubric_id']}: {result.doc_type} {result.verdict} {result.verdict_reason_codes}")
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
        # the complete live review as the app stored it (facts, evidence coordinates and witnesses, criteria, verdict)
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / f"{path.stem}.{rubric['rubric_id']}.json").write_text(
            json.dumps({"case_id": case, "requirement_code": code, "sha256": key, "result": result.model_dump(mode="json")},
                       ensure_ascii=False, indent=1) + "\n", encoding="utf8")
        (RESULTS / "raw").mkdir(exist_ok=True)
        (RESULTS / "raw" / f"{path.stem}.{rubric['rubric_id']}.json").write_text(
            json.dumps({"sha256": key, "file": rel(path), "case_id": case, "requirement_code": code, "responses": raw},
                       ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print("ledger:", g.ledger_summary(), "· HTTP requests to Gemini this run:", sent["n"])


def family_rubric(family: str) -> str:
    return {"payslip": "payslip.il.salaried", "id_document": "id_document.il", "bank_statement": "bank_statement.il",
            "purpose_proof": "purpose_proof.il", "tax_form": "tax_form.il",
            "business_registration": "business_registration.il", "pnl_statement": "pnl_statement.il"}[family]


FAMILY_OF_CODE = {"ID_CARD": "id_document", "PAYSLIPS": "payslip", "BANK_STATEMENTS": "bank_statement",
                  "PURPOSE_PROOF": "purpose_proof", "TAX_ASSESSMENT": "tax_form", "VAT_EXEMPT_CERT": "business_registration",
                  "VAT_DEALER_CERT": "business_registration", "PNL_STATEMENT": "pnl_statement"}


if __name__ == "__main__":
    main()
