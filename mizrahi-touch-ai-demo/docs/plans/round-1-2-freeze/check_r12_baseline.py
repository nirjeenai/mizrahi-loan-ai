"""Guard for the frozen Rounds 1–2 baseline: fails if a merge (Agents B/C, gates G3–G5) dropped one of the fixes made
after the 10:00 snapshot. Read-only; run from the repository root or from mizrahi-touch-ai-demo/.

    python3 mizrahi-touch-ai-demo/docs/plans/round-1-2-freeze/check_r12_baseline.py              # markers
    python3 mizrahi-touch-ai-demo/docs/plans/round-1-2-freeze/check_r12_baseline.py --manifest   # + tree == frozen tree

Markers are what each fix needs to exist, not whole files: later rounds may change these files around them. The
manifest check is only for gate G2 (the user's commit of Agent A's tree must equal the frozen tree); after G3 it is
expected to differ."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

# (file, text that must be present, text that must be absent) — F-numbers refer to round-1-2-final-audit.md §5
MARKERS = [
    ("F1", "backend/app/workflow/engine.py", ['repo.documents_by_sha(case_id, sha)', 'family_of(d["requirement_code"], case_id) == family'], ["document_by_sha("]),
    ("F1", "backend/app/store/repo.py", ["def documents_by_sha("], ["def document_by_sha("]),
    ("F1", "backend/app/db.py", ["ux_documents_case_sha_req ON documents(case_id, sha256, COALESCE(requirement_code, ''))",
                                 'DROPPED_INDEXES = ["ux_documents_case_sha"]', "def migrate(conn", "migrate(conn)"],
     ["ux_documents_case_sha ON documents(case_id, sha256);"]),
    ("F2", "backend/app/agent/actions.py", ['"העלאה מחדש:" if any(f.get("document_id") for f in fixes) else "העלאת"'], []),
    ("F2", "frontend/src/pages/customer/Documents.tsx", ["const firstUpload =", '{firstUpload ? "להעלאה" : "העלאה מחדש"}'], []),
    ("F3", "frontend/src/api.ts", ["export function customerVerdict("], ["DOCUMENT_TYPE_FAMILY"]),
    ("F3", "frontend/src/pages/customer/Documents.tsx", ["customerVerdict(d.review.verdict"], []),
    ("F3", "frontend/src/pages/customer/DocumentReview.tsx", ["customerVerdict(r.verdict"], []),
    ("F3", "frontend/src/components/UploadSheet.tsx", ["customerVerdict(doc.review.verdict"], []),
    ("F4", "frontend/src/pages/customer/DocumentReview.tsx",
     ["{ requirementCode: doc.requirement_code || undefined, replacesDocumentId: aiBlocker ? doc.document_id : undefined }"], []),
    ("F5", "frontend/src/App.tsx", ["תרחישי הלוואה, קבצים משלימים", '<Route path="apply" element={<Apply />} />'], ["Golden Set"]),
    ("F6", "backend/app/mcp/server.py", ["Personal-loan document case service", "A valid case MCP key is required."], ["Mortgage Case MCP key"]),
    ("F6", "backend/app/api/routes.py", ['"Loan Case Service (state, workflow', '"Loan Case MCP server"'], ['"Mortgage Case Service (state']),
    ("F7", "backend/app/workflow/review_desk.py", ["COVERAGE_CODES = engine.COVERAGE_CODES"], []),
    ("F8", "e2e/test_ai_card.py", ["LEGACY (", "python -m uvicorn app.main:app --port 8793"], ["./.venv/bin/uvicorn"]),
    ("F8", "e2e/test_banker_review.py", ["LEGACY (", "python -m uvicorn"], ["./.venv/bin/uvicorn"]),
    ("F8", "e2e/test_finding_resolution.py", ["LEGACY (", "python -m uvicorn"], ["./.venv/bin/uvicorn"]),
    ("F8", "e2e/test_featured_demo.py", ["LEGACY (mortgage era): superseded by e2e/test_loan_journey.py"], []),
    ("R13", "backend/tests/test_pay_date.py", ['assert latest["version"] == "1.3.0"'], []),
    ("tests", "backend/tests/test_loan_review.py", ["def test_a_file_put_under_the_wrong_requirement_can_still_be_filed_under_the_right_one",
                                                    "def test_an_older_database_loses_the_one_file_per_case_index",
                                                    "def test_a_document_never_uploaded_or_a_period_gap_is_a_first_upload_not_a_re_upload"], []),
    ("tests", "e2e/test_loan_journey.py", ["re-filing:", "first-upload wording:", "document page: 'העלאת מסמך חלופי'",
                                           "stale quote:", "def mobile(", "presenter: split screen kept"], []),
]


def rubric_check() -> list[str]:
    d = APP / "backend" / "rubrics"
    try:
        new = json.loads((d / "payslip.il.salaried.v1.3.0.json").read_text(encoding="utf8"))
        old = json.loads((d / "payslip.il.salaried.v1.2.0.json").read_text(encoding="utf8"))
    except FileNotFoundError as exc:
        return [f"R13 rubric file missing: {exc.filename}"]
    strip = lambda r: {k: v for k, v in r.items() if k not in ("version", "description", "changelog")}
    errors = []
    if new.get("version") != "1.3.0" or "mortgage" in new.get("description", ""):
        errors.append("R13 payslip.il.salaried v1.3.0: wrong version or mortgage wording back in the description")
    if strip(new) != strip(old):
        errors.append("R13 payslip.il.salaried v1.3.0 differs from v1.2.0 beyond version/description/changelog")
    return errors


def tree_files() -> dict[str, str]:
    import subprocess
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "--", "."], cwd=APP, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    skip = str(HERE.relative_to(APP)) + "/"
    return {f: hashlib.sha256((APP / f).read_bytes()).hexdigest() for f in sorted(out) if not f.startswith(skip) and (APP / f).is_file()}


def main() -> int:
    errors = []
    for tag, rel, present, absent in MARKERS:
        path = APP / rel
        if not path.exists():
            errors.append(f"{tag} {rel}: file missing")
            continue
        text = path.read_text(encoding="utf8")
        errors += [f"{tag} {rel}: missing  {m!r}" for m in present if m not in text]
        errors += [f"{tag} {rel}: reverted  {m!r} is back" for m in absent if m in text]
    errors += rubric_check()
    if "--manifest" in sys.argv:
        frozen = json.loads((HERE / "manifest.json").read_text(encoding="utf8"))["files"]
        now = tree_files()
        changed = sorted(f for f in frozen.keys() | now.keys() if frozen.get(f) != now.get(f))
        errors += [f"manifest: {f} {'missing' if f not in now else 'new' if f not in frozen else 'differs'}" for f in changed]
    if errors:
        print("ROUNDS 1–2 BASELINE BROKEN:\n  " + "\n  ".join(errors))
        return 1
    print(f"OK — {len(MARKERS)} fix markers and the payslip rubric v1.3.0 are intact"
          + (" · tree equals the frozen manifest" if "--manifest" in sys.argv else ""))
    return 0


if __name__ == "__main__":
    if "--write-manifest" in sys.argv:
        (HERE / "manifest.json").write_text(json.dumps({"frozen_at": "2026-10-14", "files": tree_files()}, indent=1) + "\n",
                                            encoding="utf8")
        print("manifest written")
        sys.exit(0)
    sys.exit(main())
