"""Build the rubric index and the reason-code catalog FROM the rubric files (single source of truth).

Usage:  python tools/build_catalog.py      (needs: jsonschema)
Writes: ../index.json, ../reason_codes.json — fails if any rubric violates rubric.schema.json,
if a criterion id repeats across the library, or if a reason code is used with conflicting
review states.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "rubric.schema.json").read_text(encoding="utf8"))

# Codes emitted by the platform outside any rubric criterion (intake, lifecycle, provider failures).
PLATFORM_CODES = {
    "FILE_TYPE_NOT_ALLOWED": ("קובץ מסוג שאינו נתמך", "blocking", "CUSTOMER_ACTION_REQUIRED", "intake"),
    "FILE_ENCRYPTED": ("הקובץ מוגן בסיסמה", "blocking", "CUSTOMER_ACTION_REQUIRED", "intake"),
    "FILE_TOO_LARGE": ("הקובץ גדול מהמותר", "blocking", "CUSTOMER_ACTION_REQUIRED", "intake"),
    "FILE_MALWARE_SUSPECTED": ("הקובץ נחסם בבדיקת אבטחה", "blocking", "BANKER_REVIEW_REQUIRED", "intake"),
    "PAGE_LIMIT_EXCEEDED": ("לא כל עמודי הקובץ נקראו", "major", "BANKER_REVIEW_REQUIRED", "intake"),
    "PARTIALLY_READABLE": ("חלק מהעמודים אינם קריאים", "major", "CUSTOMER_ACTION_REQUIRED", "intake"),
    "LANGUAGE_UNSUPPORTED": ("שפת המסמך אינה נתמכת", "major", "BANKER_REVIEW_REQUIRED", "intake"),
    "UNSUPPORTED_DOCUMENT_TYPE": ("סוג מסמך שאינו בקטלוג הבדיקה", "info", "BANKER_REVIEW_REQUIRED", "classification"),
    "AMBIGUOUS_CLASSIFICATION": ("לא ניתן לקבוע את סוג המסמך", "major", "BANKER_REVIEW_REQUIRED", "classification"),
    "FILENAME_TYPE_MISMATCH": ("שם הקובץ מרמז על סוג אחר", "info", "INFO", "classification"),
    "NAME_VARIANT": ("וריאציית שם מוכרת", "info", "INFO", "identity"),
    "ID_POSSIBLE_MISREAD": ("מספר זהות שאינו עובר ספרת ביקורת ושונה בספרה אחת — חשד לשגיאת קריאה", "major", "BANKER_REVIEW_REQUIRED", "identity"),
    "PERIOD_CONFLICT": ("שני חודשים שונים מודפסים במסמך", "major", "BANKER_REVIEW_REQUIRED", "period"),
    "PERIOD_IN_FUTURE": ("תקופה עתידית ביחס לתאריך הבדיקה", "major", "BANKER_REVIEW_REQUIRED", "period"),
    "WAGE_PAID_AFTER_LEGAL_DEADLINE": ("השכר שולם אחרי ה־9 בחודש העוקב", "info", "INFO", "period"),
    "CORRECTED_PAYSLIP": ("תלוש מתוקן / הפרשים", "info", "INFO", "period"),
    "PARTIAL_PROPERTY_INSURANCE": ("ביטוח נכס חלקי (מותר; הבנק אינו ממליץ)", "info", "INFO", "insurance"),
    "DIGITAL_ORIGINAL_REQUIRED": ("נדרש עותק דיגיטלי חתום של המסמך", "major", "BANKER_REVIEW_REQUIRED", "authenticity"),
    "DIGITAL_SIGNATURE_VALID": ("חתימה אלקטרונית אומתה", "info", "INFO", "authenticity"),
    "ORIGINAL_REQUIRED": ("הבנק דורש את המסמך המקורי בסניף", "info", "INFO", "completion"),
    "BORROWER_NOT_BUYER": ("לווה שאינו קונה בחוזה", "info", "INFO", "cross_document"),
    "CUSTOMER_STATEMENT_PARTIALLY_SUPPORTED": ("הסבר הלקוח נתמך חלקית במסמכים", "major", "BANKER_REVIEW_REQUIRED", "semantic"),
    "REISSUED_COPY": ("עותק שהופק מחדש", "info", "INFO", "period"),
    "ISSUE_DATE_BEFORE_PERIOD": ("תאריך הפקה לפני תחילת התקופה", "minor", "BANKER_REVIEW_REQUIRED", "period"),
    "EMPLOYER_CHANGED_WITHIN_WINDOW": ("מעסיק שונה בתוך החלון", "minor", "BANKER_REVIEW_REQUIRED", "identity"),
    "LIABILITY_DOCUMENT_MISSING": ("התחייבות מוצהרת ללא ראיה", "major", "CUSTOMER_ACTION_REQUIRED", "financial"),
    "PLEDGOR_NOT_OWNER": ("משעבד שאינו בעלים רשום", "major", "BANKER_REVIEW_REQUIRED", "property"),
    "INSURANCE_BRANCH_DETAILS_MISSING": ("בסעיף השעבוד חסרים מספר הסניף או כתובתו, או שהם שונים", "major", "CUSTOMER_ACTION_REQUIRED", "insurance"),
    "INSURED_PROPERTY_MISMATCH": ("הנכס המבוטח אינו הנכס המשועבד", "blocking", "CUSTOMER_ACTION_REQUIRED", "insurance"),
    "REPEATED_UNREADABLE": ("אותו מסמך לא קריא פעמיים ברציפות", "major", "BANKER_REVIEW_REQUIRED", "lifecycle"),
    "PROVIDER_FAILURE": ("הבדיקה לא הושלמה בשל תקלה", "major", "BANKER_REVIEW_REQUIRED", "lifecycle"),
    "POLICY_PARAMETER_PENDING": ("נדרש ערך מדיניות בנק להכרעה", "info", "BANKER_REVIEW_REQUIRED", "lifecycle"),
    "JUDGE_NO_OUTCOME": ("השופט לא החזיר תוצאה לקריטריון", "major", "BANKER_REVIEW_REQUIRED", "semantic"),
    "DEMO_DOCUMENT_IN_PRODUCTION": ("מסמך דמו בסביבת ייצור", "major", "BANKER_REVIEW_REQUIRED", "intake"),
}


def main() -> None:
    v = jsonschema.Draft202012Validator(SCHEMA)
    index, seen_ids = [], {}
    codes: dict[str, dict] = {}
    for path in sorted((ROOT / "rubrics").glob("*.json")):
        r = json.loads(path.read_text(encoding="utf8"))
        errors = list(v.iter_errors(r))
        if errors:
            print(f"✗ {path.name}: {errors[0].message}")
            sys.exit(1)
        index.append({"rubric_id": r["rubric_id"], "version": r["version"], "ref": f"{r['rubric_id']}@{r['version']}",
                      "priority": r["priority"], "scope": r["scope"], "document_category": r["document_category"],
                      "name_he": r["name_he"], "name_en": r["name_en"], "file": f"rubrics/{path.name}",
                      "criteria": [c["id"] for c in r["criteria"]],
                      "methods": dict(collections.Counter(c["method"] for c in r["criteria"])),
                      "source_refs": r["source_refs"]})
        for c in r["criteria"]:
            if c["id"] in seen_ids:
                print(f"✗ duplicate criterion id {c['id']} in {path.name} and {seen_ids[c['id']]}")
                sys.exit(1)
            seen_ids[c["id"]] = path.name
            code = c.get("reason_code")
            if not code:
                continue
            f = c.get("finding") or {}
            entry = codes.setdefault(code, {"code": code, "title_he": None, "category": c["dimension"],
                                            "default_severity": c["severity"], "review_states": set(),
                                            "customer_message_he": None, "internal_message_he": None,
                                            "key_templates": set(), "used_by": [], "requirement_basis": set()})
            entry["used_by"].append(f"{r['rubric_id']}@{r['version']}#{c['id']}")
            entry["requirement_basis"].add(c.get("requirement_basis", "PROPOSED_VALIDATION"))
            if f:
                entry["review_states"].add(f.get("review_state"))
                entry["key_templates"].add(f.get("key_template"))
                entry["customer_message_he"] = entry["customer_message_he"] or f.get("customer_message_he")
                entry["internal_message_he"] = entry["internal_message_he"] or f.get("internal_message_he")
            entry["title_he"] = entry["title_he"] or c["title_he"]
    for code, (title, sev, state, cat) in PLATFORM_CODES.items():
        if code in codes:
            codes[code]["review_states"].add(state)
            continue
        codes[code] = {"code": code, "title_he": title, "category": cat, "default_severity": sev,
                       "review_states": {state}, "customer_message_he": None, "internal_message_he": None,
                       "key_templates": {f"{code}:{{subject}}"}, "used_by": ["platform"], "requirement_basis": {"PROPOSED_VALIDATION"}}
    out = []
    for code in sorted(codes):
        e = codes[code]
        e["review_states"] = sorted(s for s in e["review_states"] if s)
        if len(e["review_states"]) > 1:
            print(f"✗ reason code {code} has conflicting review states {e['review_states']} ({', '.join(e['used_by'])})")
            sys.exit(1)
        e["key_templates"] = sorted(k for k in e["key_templates"] if k)
        e["requirement_basis"] = sorted(e["requirement_basis"])
        out.append(e)
    (ROOT / "index.json").write_text(json.dumps({"library": "mortgage-rubrics", "version": "1.0.0-draft",
                                                 "generated": "2026-10-12", "rubrics": index}, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf8")
    (ROOT / "reason_codes.json").write_text(json.dumps({"catalog": "mortgage-reason-codes", "version": "1.0.0-draft",
                                                        "generated": "2026-10-12", "codes": out}, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf8")
    write_readme_index(index)
    print(f"✓ {len(index)} rubrics, {len(seen_ids)} criteria, {len(out)} reason codes")


def write_readme_index(index: list[dict]) -> None:
    readme = ROOT / "README.md"
    begin, end = "<!-- BEGIN:INDEX -->", "<!-- END:INDEX -->"
    text = readme.read_text(encoding="utf8")
    if begin not in text or end not in text:
        return
    rows = ["| קובץ | rubric_id@version | עדיפות | היקף | שם | קריטריונים | שיטות |", "|---|---|---|---|---|---|---|"]
    for r in index:
        methods = " · ".join(f"{k} {v}" for k, v in sorted(r["methods"].items()))
        rows.append(f"| `{r['file'].split('/')[-1].split('_')[0]}` | `{r['ref']}` | {r['priority']} | {r['scope']} | {r['name_he']} | "
                    f"{len(r['criteria'])}: {', '.join(r['criteria'])} | {methods} |")
    head, rest = text.split(begin, 1)
    tail = rest.split(end, 1)[1]
    readme.write_text(f"{head}{begin}\n" + "\n".join(rows) + f"\n{end}{tail}", encoding="utf8")


if __name__ == "__main__":
    main()
