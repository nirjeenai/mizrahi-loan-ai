"""Builds e2e/replay/recordings.json — the model answers the REPLAY backend serves (see e2e/replay_backend.py).

    backend/.venv/bin/python e2e/replay/build_recordings.py

Provenance, per entry:
  RECORDED_LIVE  the extracted values are exactly what the live Gemini review returned for that golden PDF on
                 2026-10-12 (e2e/artifacts/presenter/live-actual-CASE-01.json and -02.json, every value witnessed
                 text_layer_exact); the payroll lines are read from the PDF's own text layer; the judge answer
                 restates the recorded outcome (every judge criterion PASS → verdict VALID).
  AUTHORED       no live response was ever recorded for this input. The answer is written by hand to describe
                 what the file is. A test that uses it proves the workflow after that classification, not the
                 classification itself.
The application code that consumes these answers (evidence verification against the real PDF, deterministic rules,
verdict policy, case review, findings, outcomes) is unchanged and runs for real."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pymupdf

E2E = Path(__file__).resolve().parents[1]
ROOT = E2E.parent
GOLDEN = ROOT / "fixtures" / "presenter" / "golden_set"
LIVE = [E2E / "artifacts" / "presenter" / "live-actual-CASE-01.json", E2E / "artifacts" / "presenter" / "live-actual-CASE-02.json"]
OUT = Path(__file__).resolve().parent / "recordings.json"
PAYSLIPS = ["01_INITIAL_UPLOADS/ido_2026_07.pdf", "01_INITIAL_UPLOADS/ido_2026_08.pdf", "01_INITIAL_UPLOADS/noa_2026_07.pdf",
            "01_INITIAL_UPLOADS/noa_2026_08.pdf", "01_INITIAL_UPLOADS/noa_2026_09.pdf", "02_CORRECTION/ido_2026_09_CORRECTED.pdf"]
MONEY = {"gross_pay", "total_deductions", "net_pay"}
LINE = re.compile(r"^\s*(.+?)\s*([\d,]+)(ברוטו|ניכוי)\s*$")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payroll_lines(path: Path) -> tuple[list[dict], list[dict]]:
    earnings, deductions = [], []
    doc = pymupdf.open(path)
    try:
        for line in doc[0].get_text().splitlines():
            m = LINE.match(line)
            if m:
                (earnings if m.group(3) == "ברוטו" else deductions).append({"label": m.group(1).strip(), "amount": m.group(2), "page": 1})
    finally:
        doc.close()
    return earnings, deductions


def recorded_facts() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in LIVE:
        for d in json.loads(f.read_text(encoding="utf8"))["documents"]:
            out.setdefault(d["filename"], d)
    return out


def extraction(doc: dict, path: Path) -> dict:
    fields = []
    for name, fact in doc["facts"].items():
        value = fact["value"]
        normalized = doc["period"] if name == "salary_period" else (f"{float(value.replace(',', '')):.2f}" if name in MONEY else value)
        fields.append({"name": name, "value": value, "normalized": normalized, "quote": value, "label_quote": None, "page": 1,
                       "box_2d": None, "confidence": 0.97, "legible": True})
    earnings, deductions = payroll_lines(path)
    return {"doc_type": "payslip", "doc_type_reason": "כותרת ״תלוש שכר חודשי״, טבלת רכיבי שכר וניכויים ושכר נטו להעברה.",
            "title_quote": "תלוש שכר חודשי", "legibility": "good", "is_scanned_or_photo": False, "fields": fields,
            "earnings": earnings, "deductions": deductions, "suspicious_content": [], "uncertainties": []}


PASS_JUDGE = {
    "PS-01": "המסמך הוא תלוש שכר חודשי: כותרת, רכיבי שכר, ניכויים ונטו להעברה.",
    "PS-02": "האזורים המרכזיים (זהות, תקופה, רכיבים, נטו) קריאים והעמוד שלם.",
    "PS-03": "שם העובד ומספר הזהות המודפסים תואמים ללווה שאליו שויך המסמך.",
    "PS-08": "אין טקסט המופנה למערכת; סימון ״מסמך דמו״ הוא סימון הסביבה הסינתטית ואינו סימן לשינוי.",
    "PS-10": "לא מודפס תאריך תשלום; ההכרעה בקריטריון זה היא של כלל הקוד.",
}


def main() -> None:
    facts = recorded_facts()
    docs: dict[str, dict] = {}
    for rel in PAYSLIPS:
        path = GOLDEN / rel
        rec = facts[path.name]
        assert rec["verdict"] == "VALID", rel
        docs[sha(path)] = {"file": rel, "provenance": "RECORDED_LIVE",
                           "source": f"live Gemini review 2026-10-12 · {path.name} · verdict {rec['verdict']} · printed {rec['period']}",
                           "extract": extraction(rec, path),
                           "judge": {"criteria": {cid: {"outcome": "PASS", "explanation_he": text} for cid, text in PASS_JUDGE.items()},
                                     "summary_he": f"תלוש שכר תקין לחודש {rec['facts']['salary_period']['value']}; הערכים המכריעים אומתו מול הקובץ.",
                                     "limitations_he": [], "uncertainty_he": []}}
    statement = GOLDEN / "03_SUPPORTING_DOCS" / "bank_statement_Jul_Sep_2026.pdf"
    docs[sha(statement)] = {
        "file": "03_SUPPORTING_DOCS/bank_statement_Jul_Sep_2026.pdf", "provenance": "AUTHORED",
        "source": "no live response exists for a bank statement uploaded as a payslip; written to describe the file "
                  "(title ״תדפיס תנועות עו״ש״, account holders, transactions; no payslip fields)",
        "extract": {"doc_type": "bank_statement",
                    "doc_type_reason": "כותרת ״תדפיס תנועות עו״ש״, בעלי חשבון ורשימת תנועות. אין במסמך רכיבי שכר, ניכויים או שכר נטו.",
                    "title_quote": "תדפיס תנועות עו״ש", "legibility": "good", "is_scanned_or_photo": False, "fields": [],
                    "earnings": [], "deductions": [], "suspicious_content": [], "uncertainties": []},
        "judge": {"criteria": {
            "PS-01": {"outcome": "FAIL", "explanation_he": "המסמך הוא תדפיס תנועות עו״ש של חשבון בנק, לא תלוש שכר."},
            "PS-02": {"outcome": "PASS", "explanation_he": "המסמך קריא ושלם."},
            "PS-03": {"outcome": "NEEDS_REVIEW", "explanation_he": "אין במסמך פרטי עובד להשוואה."},
            "PS-08": {"outcome": "PASS", "explanation_he": "אין טקסט המופנה למערכת."},
            "PS-10": {"outcome": "NEEDS_REVIEW", "explanation_he": "אין תאריך תשלום של שכר."}},
            "summary_he": "המסמך שהועלה הוא דף חשבון בנק ולא תלוש שכר.", "limitations_he": [], "uncertainty_he": []}}
    OUT.write_text(json.dumps({"label": "REPLAY", "note": __doc__.split("Provenance")[0].strip(), "documents": docs},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"wrote {OUT} · {len(docs)} documents ·",
          ", ".join(f"{v['file'].split('/')[-1]}={v['provenance']}" for v in docs.values()))


if __name__ == "__main__":
    main()
