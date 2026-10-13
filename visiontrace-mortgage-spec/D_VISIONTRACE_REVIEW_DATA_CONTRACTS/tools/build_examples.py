"""Build and validate the D-package example payloads from ONE consistent synthetic scenario.

Scenario = the canonical demo (E_MORTGAGE_GOLDEN_TEST_PLAN.md, scenario GS-01): Ido and Noa Lavi,
salaried, second-hand apartment in Haifa, after preliminary approval, simulation date 2026-10-12.
File hashes, page sizes and every bounding box below were measured on the demo's synthetic fixtures
(mizrahi-touch-ai-demo/fixtures/out, PyMuPDF word geometry). The scanned file's boxes are
illustrative OCR geometry (no OCR provider has been chosen yet).

Usage:  python tools/build_examples.py            (needs: jsonschema)
Writes: ../examples/*.json — and fails loudly if any payload violates schemas/mortgage-review.v1.schema.json.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCHEMA = json.loads((ROOT / "schemas" / "mortgage-review.v1.schema.json").read_text(encoding="utf8"))
OUT = ROOT / "examples"

TENANT, CASE = "mizrahi-tefahot-demo", "DEMO-MTZ-2026-001"
RC, RC_REF = "rc_7k2m9q4x1d", "C-7K2M-9Q4X"
RUN1, RUN1_REF = "a3f91c2e7b", "R-A3F91"
RUN2, RUN2_REF = "b7d204e9c1", "R-B7D20"
AS_OF = "2026-10-12"
W, H = 595.92, 842.88          # born-digital fixture page (points)
WS, HS = 595.28, 841.89        # scanned fixture page (points)
RUBRICS = ["mortgage.document.intake_quality@1.0.0", "mortgage.payslip.classification_identity@1.0.0",
           "mortgage.payslip.period@1.0.0", "mortgage.payslip.financials@1.0.0",
           "mortgage.income.payslip_coverage@1.0.0", "mortgage.payslip.duplicates@1.0.0",
           "mortgage.income.declared_vs_documented@1.0.0", "mortgage.identity.consistency@1.0.0"]
DISCLAIMER = ("מוכנות תיעודית בלבד בהיקף שנבדק (מסמכי שכר). אין זו קבלת מסמך על ידי הבנק, אין זו החלטת אשראי, "
              "ואין זו בדיקת אותנטיות. שמאות, ביטוחים, מסמכי מוכר ובטוחות, דפי חשבון ויתרות הלוואות לא נבדקו בהרצה זו.")


def norm(box, w=W, h=H):
    x0, y0, x1, y1 = box
    return [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)]


# ---------------------------------------------------------------- the synthetic world (fixtures)
PARTIES = {
    "BRW-A": {"name": "עידו לביא", "id": "039812457", "employer": "אופק לוגיסטיקה בע״מ", "declared_net": 13500,
              "note": "שכר קבוע"},
    "BRW-B": {"name": "נועה לביא", "id": "204376815", "employer": "גלי טכנולוגיות בע״מ", "declared_net": 18500,
              "note": "ייתכנו רכיבים משתנים"},
}
# layout of a born-digital payslip (y offset 0) and of the reissued copy (shifted 19.5 pt by its stamp)
LAYOUT = {
    "employee_name": {"BRW-A": [506.88, 132.99, 547.26, 144.73], "BRW-B": [505.02, 132.99, 547.25, 144.73]},
    "employee_id": [367.57, 132.99, 420.11, 144.73],
    "employer_name": {"BRW-A": [402.91, 40.86, 556.26, 59.85], "BRW-B": [415.95, 40.86, 556.25, 59.85]},
    "salary_period": [509.30, 161.49, 547.24, 173.23],
    "payment_date": [367.57, 161.49, 420.11, 173.23],
    "gross_pay": [475.92, 338.48, 533.74, 353.00],
    "total_deductions": [308.66, 338.48, 359.25, 353.00],
    "net_pay": [126.93, 338.48, 184.75, 353.00],
    "document_number": [40.25, 55.31, 104.50, 64.80],
    "issue_date": [40.25, 64.31, 82.78, 73.80],
}
SHIFTED = {"employee_name", "employee_id", "salary_period", "payment_date", "gross_pay", "total_deductions", "net_pay"}
OCCURRENCES = {"gross_pay": 2, "total_deductions": 2}
LABELS = {"employee_name": "שם העובד/ת", "employee_id": "מספר זהות", "employer_name": "שם המעסיק",
          "salary_period": "תקופת שכר", "payment_date": "תאריך תשלום", "gross_pay": "שכר ברוטו",
          "total_deductions": "סה״כ ניכויים", "net_pay": "נטו לתשלום", "document_number": "מספר מסמך",
          "issue_date": "תאריך הפקה"}
QUOTE_LABEL = {"gross_pay": "שכר ברוטו", "total_deductions": "סה״כ ניכויים", "net_pay": "נטו לתשלום"}
TYPES = {"employee_name": "person_name", "employee_id": "national_id", "employer_name": "organization_name",
         "salary_period": "month", "payment_date": "date", "gross_pay": "money", "total_deductions": "money",
         "net_pay": "money", "document_number": "text", "issue_date": "date"}
NORMALIZER = {"person_name": "person_name@1", "national_id": "national_id@1", "organization_name": "text@1",
              "month": "month@1", "date": "date_il@1", "money": "money_ils@1", "text": "text@1"}

DOCS = {
    # doc_id: party, filename, sha256, printed period, pay date, issue date, doc no, gross, deductions, net, variant
    "DOC-A1": dict(party="BRW-A", filename="ido_payslip_2026-07.pdf", sha="7bd0fa9084a98299b70b8292de1897971d7d48f6d61fadc418d2642035bd8082",
                   period="2026-07", pay="09.08.2026", issued="06.08.2026", no="SAL-ido-2026-07", gross=17000, ded=3800, net=13200,
                   bytes=156316, chars=754, variant="digital", named="2026-07",
                   earnings=[("שכר בסיס", 15500), ("שעות נוספות", 900), ("החזר נסיעות", 600)],
                   deductions=[("מס הכנסה", 1950), ("ביטוח לאומי", 760), ("מס בריאות", 470), ("פנסיה — חלק עובד", 620)]),
    "DOC-A2": dict(party="BRW-A", filename="ido_payslip_2026-08.pdf", sha="a1827f86abe7d7f1abf0175e2e258a25972ac118091184f55a46661e9d6861da",
                   period="2026-08", pay="09.09.2026", issued="06.09.2026", no="SAL-ido-2026-08", gross=17500, ded=4000, net=13500,
                   bytes=157866, chars=758, variant="digital", named="2026-08",
                   earnings=[("שכר בסיס", 15500), ("שעות נוספות", 1400), ("החזר נסיעות", 600)],
                   deductions=[("מס הכנסה", 2080), ("ביטוח לאומי", 790), ("מס בריאות", 490), ("פנסיה — חלק עובד", 640)]),
    "DOC-A3": dict(party="BRW-A", filename="ido_payslip_2026-09.pdf", sha="376ac993be17b3287f7b136506516095952d5d599bdc133ae4665af029223b7f",
                   period="2026-08", pay="09.09.2026", issued="15.09.2026", no="SAL-ido-2026-08", gross=17500, ded=4000, net=13500,
                   bytes=169585, chars=775, variant="reissued", named="2026-09",
                   earnings=[("שכר בסיס", 15500), ("שעות נוספות", 1400), ("החזר נסיעות", 600)],
                   deductions=[("מס הכנסה", 2080), ("ביטוח לאומי", 790), ("מס בריאות", 490), ("פנסיה — חלק עובד", 640)]),
    "DOC-A3v2": dict(party="BRW-A", filename="ido_payslip_2026-09_corrected.pdf", sha="64a07c9f4f7e92f96a17d6e1e9ea40152f9779bf32afd2c6f7214dadad6d4b11",
                     period="2026-09", pay="09.10.2026", issued="06.10.2026", no="SAL-ido-2026-09", gross=17300, ded=3900, net=13400,
                     bytes=157591, chars=758, variant="digital", named="2026-09",
                     earnings=[("שכר בסיס", 15500), ("שעות נוספות", 1200), ("החזר נסיעות", 600)],
                     deductions=[("מס הכנסה", 2010), ("ביטוח לאומי", 780), ("מס בריאות", 480), ("פנסיה — חלק עובד", 630)]),
    "DOC-B1": dict(party="BRW-B", filename="noa_payslip_2026-07_scan.pdf", sha="d2d8510c5d2696864e77a44ce0074adef6299d0e7b0a55e93db2501fadc1267b",
                   period="2026-07", pay="09.08.2026", issued="05.08.2026", no="SAL-noa-2026-07", gross=22600, ded=5700, net=16900,
                   bytes=67554, chars=0, variant="scan", named="2026-07",
                   earnings=[("שכר בסיס", 21500), ("החזר נסיעות", 600), ("אחזקת טלפון", 500)],
                   deductions=[("מס הכנסה", 3420), ("ביטוח לאומי", 1090), ("מס בריאות", 610), ("פנסיה — חלק עובד", 580)]),
    "DOC-B2": dict(party="BRW-B", filename="noa_payslip_2026-08.pdf", sha="8ce41cdbd75c3818553d9e11f5351f7352f5a6bd40689b196ca702b7cd69c32a",
                   period="2026-08", pay="09.09.2026", issued="05.09.2026", no="SAL-noa-2026-08", gross=22600, ded=5700, net=16900,
                   bytes=158928, chars=755, variant="digital", named="2026-08",
                   earnings=[("שכר בסיס", 21500), ("החזר נסיעות", 600), ("אחזקת טלפון", 500)],
                   deductions=[("מס הכנסה", 3420), ("ביטוח לאומי", 1090), ("מס בריאות", 610), ("פנסיה — חלק עובד", 580)]),
    "DOC-B3": dict(party="BRW-B", filename="noa_payslip_2026-09.pdf", sha="1fc425b83048b23980eaf105c55e75d769fe21fc133f181c44e7aff1bb6640cf",
                   period="2026-09", pay="09.10.2026", issued="05.10.2026", no="SAL-noa-2026-09", gross=22600, ded=5700, net=16900,
                   bytes=158627, chars=755, variant="digital", named="2026-09",
                   earnings=[("שכר בסיס", 21500), ("החזר נסיעות", 600), ("אחזקת טלפון", 500)],
                   deductions=[("מס הכנסה", 3420), ("ביטוח לאומי", 1090), ("מס בריאות", 610), ("פנסיה — חלק עובד", 580)]),
}
MONTH_HE = {"2026-07": "יולי 2026", "2026-08": "אוגוסט 2026", "2026-09": "ספטמבר 2026"}


def money(v):
    return {"amount": float(v), "currency": "ILS"}


def fmt(v):
    return f"{v:,.2f}"


def doc_key(doc_id):
    return doc_id.replace("v2", "")


def version_of(doc_id):
    return 2 if doc_id.endswith("v2") else 1


def raw_value(d, field):
    p = PARTIES[d["party"]]
    return {"employee_name": p["name"], "employee_id": p["id"], "employer_name": p["employer"],
            "salary_period": f"{d['period'][5:]}/{d['period'][:4]}", "payment_date": d["pay"],
            "gross_pay": fmt(d["gross"]), "total_deductions": fmt(d["ded"]), "net_pay": fmt(d["net"]),
            "document_number": d["no"], "issue_date": d["issued"]}[field]


def normalized_value(d, field):
    p = PARTIES[d["party"]]
    if field in ("gross_pay", "total_deductions", "net_pay"):
        return money({"gross_pay": d["gross"], "total_deductions": d["ded"], "net_pay": d["net"]}[field])
    if field == "salary_period":
        return d["period"]
    if field in ("payment_date", "issue_date"):
        dd, mm, yy = d["pay" if field == "payment_date" else "issued"].split(".")
        return f"{yy}-{mm}-{dd}"
    if field == "employee_id":
        return p["id"]
    return raw_value(d, field)


def box_for(d, field):
    base = LAYOUT[field]
    if isinstance(base, dict):
        base = base[d["party"]]
    base = list(base)
    if d["variant"] == "reissued" and field in SHIFTED:
        base = [base[0], base[1] + 19.5, base[2], base[3] + 19.5]
    return base


def evidence(doc_id, d, field, run):
    ver, key = version_of(doc_id), doc_key(doc_id)
    eid = f"ev_{run}_{key}_v{ver}_{field}"
    box = box_for(d, field)
    raw = raw_value(d, field)
    quote = f"{QUOTE_LABEL[field]} {raw} ₪" if field in QUOTE_LABEL else raw
    item = {"evidence_id": eid, "document_id": key, "document_version": ver, "sha256": d["sha"], "page": 1,
            "quote": quote, "rotation": 0, "created_by_run": run, "occurrences_on_page": OCCURRENCES.get(field, 1)}
    if d["variant"] == "scan":
        # illustrative OCR token geometry on the image-only page (no OCR provider chosen yet)
        x0, y0, x1, y1 = box
        item.update(bbox=norm([x0 - 0.9, y0 + 2.6, x1 - 0.9, y1 + 2.6], WS, HS), bbox_pdf_points=None,
                    page_size_points=[WS, HS], precision="exact", witness="ocr_token_match",
                    witness_detail="ערך זה הודפס בעמוד סרוק; אומת מול מילות ה־OCR שבתוך התיבה (אין שכבת טקסט)")
    else:
        detail = (f"מודפס בשכבת הטקסט של ה־PDF ({item['occurrences_on_page']} מופעים בעמוד; העוגן הוא המופע שבצמוד לתווית שצוטטה)"
                  if item["occurrences_on_page"] > 1 else "מודפס בשכבת הטקסט של ה־PDF")
        item.update(bbox=norm(box), bbox_pdf_points=[round(v, 2) for v in box], page_size_points=[W, H],
                    precision="exact", witness="text_layer_exact", witness_detail=detail)
    item["snippet_url"] = (f"https://visiontrace.example.invalid/api/v1/evidence/{eid}/snippet"
                           f"?exp=1760259000&sig=EXAMPLE")
    item["snippet_expires_at"] = "2026-10-12T09:30:00Z"
    return item


FIELDS = ["employee_name", "employee_id", "employer_name", "salary_period", "payment_date",
          "gross_pay", "total_deductions", "net_pay", "document_number", "issue_date"]


def facts_and_evidence(doc_id, d, run):
    facts, evs = [], []
    for f in FIELDS:
        ev = evidence(doc_id, d, f, run)
        evs.append(ev)
        method = "ocr_llm" if d["variant"] == "scan" else "text_layer_llm"
        facts.append({"fact_id": f"fact_{run}_{doc_key(doc_id)}_v{version_of(doc_id)}_{f}", "field": f,
                      "label_he": LABELS[f], "value_type": TYPES[f], "status": "present", "raw": raw_value(d, f),
                      "normalized": normalized_value(d, f), "normalizer": NORMALIZER[TYPES[f]],
                      "evidence_ids": [ev["evidence_id"]],
                      "extraction": {"method": method, "model": "gemini-3.8-flash",
                                     "prompt_version": "vt-mortgage-read/1.0.0"},
                      "self_reported_confidence": 0.98 if d["variant"] != "scan" else 0.93, "verified": True})
    return facts, evs


def line_items(doc_id, d, run):
    rows = []
    cat = {"שכר בסיס": "base_salary", "שעות נוספות": "overtime", "החזר נסיעות": "travel_reimbursement",
           "אחזקת טלפון": "phone_allowance", "מס הכנסה": "income_tax", "ביטוח לאומי": "national_insurance",
           "מס בריאות": "health_tax", "פנסיה — חלק עובד": "pension_employee"}
    for i, (label, amount) in enumerate(d["earnings"]):
        rows.append({"table": "earnings", "label_raw": label, "category": cat[label], "amount": money(amount),
                     "date": None, "evidence_id": f"ev_{run}_{doc_key(doc_id)}_v{version_of(doc_id)}_earn{i}"})
    for i, (label, amount) in enumerate(d["deductions"]):
        rows.append({"table": "deductions", "label_raw": label, "category": cat[label], "amount": money(amount),
                     "date": None, "evidence_id": f"ev_{run}_{doc_key(doc_id)}_v{version_of(doc_id)}_ded{i}"})
    return rows


def crit(cid, rubric, title, method, outcome, severity, reason, rationale, evs, *, decided="code", dimension,
         computation=None, params=None, escalation="none", judge=None):
    out = {"criterion_id": cid, "rubric": rubric, "title_he": title, "dimension": dimension, "method": method,
           "outcome": outcome, "severity": severity, "reason_code": reason, "rationale_internal_he": rationale,
           "computation": computation, "evidence_ids": evs, "decided_by": decided, "escalation": escalation}
    if params:
        out["policy_parameters"] = params
    if judge:
        out["judge"] = judge
    return out


JUDGE = {"model": "gemini-3.8-flash", "prompt_version": "vt-mortgage-judge/1.0.0", "samples": 1, "agreement": 1.0,
         "raw_outcome": "PASS", "downgraded_reason": None}


def document_review(doc_id, run, *, claimed_period):
    d = DOCS[doc_id]
    key, ver = doc_key(doc_id), version_of(doc_id)
    facts, evs = facts_and_evidence(doc_id, d, run)
    ev = {f["field"]: f["evidence_ids"][0] for f in facts}
    p = PARTIES[d["party"]]
    scan = d["variant"] == "scan"
    reissued = d["variant"] == "reissued"
    name_mismatch = d["named"] != d["period"]
    R = "mortgage.payslip"
    criteria = [
        crit("GEN-INT-01", "mortgage.document.intake_quality@1.0.0", "הקובץ נפתח ונקרא", "deterministic", "PASS",
             "blocking", None, "PDF תקין, לא מוצפן, עמוד אחד" + (" — סרוק, נקרא ב־OCR" if scan else " עם שכבת טקסט מלאה"),
             [], dimension="readability"),
        crit("GEN-SEC-01", "mortgage.document.intake_quality@1.0.0", "אין במסמך הוראות המופנות למערכת", "hybrid",
             "PASS", "major", None, "לא נמצא טקסט המופנה למערכת או לבודק (סורק דטרמיניסטי + סיווג תוכן חשוד)", [],
             decided="code+judge", dimension="security", escalation="banker", judge=JUDGE),
        crit("PSL-CLS-01", f"{R}.classification_identity@1.0.0", "המסמך הוא תלוש שכר", "hybrid", "PASS", "blocking", None,
             "כותרת 'תלוש שכר לחודש …', טבלאות תשלומים וניכויים, 'נטו לתשלום'", [ev["net_pay"]], decided="code+judge",
             dimension="classification", escalation="customer", judge=JUDGE),
        crit("PSL-CLS-02", f"{R}.classification_identity@1.0.0", "סוג המסמך תואם לדרישה שאליה הועלה", "deterministic",
             "PASS", "blocking", None, f"הועלה ל־INC.PAYSLIP:{d['party']} וזוהה כתלוש שכר", [],
             dimension="classification", escalation="customer"),
        crit("PSL-IDN-01", f"{R}.classification_identity@1.0.0", "מספר הזהות המודפס הוא של הלווה המשויך", "deterministic",
             "PASS", "blocking", None, f"מספר הזהות במסמך זהה למספר של {p['name'].split()[0]} בתיק",
             [ev["employee_id"]], dimension="identity_binding", escalation="customer"),
        crit("PSL-IDN-02", f"{R}.classification_identity@1.0.0", "שם העובד תואם ללווה", "hybrid", "PASS", "major", None,
             "שם זהה (השוואה מנורמלת)", [ev["employee_name"]], dimension="identity_binding", escalation="customer"),
        crit("PSL-PER-01", f"{R}.period@1.0.0", "תקופת השכר מודפסת וחד־משמעית", "deterministic", "PASS", "major", None,
             f"תקופת שכר מודפסת: {raw_value(d, 'salary_period')} → {d['period']}", [ev["salary_period"]],
             dimension="period_relevance", escalation="customer"),
        crit("PSL-PER-02", f"{R}.period@1.0.0", "החודש ששם הקובץ מציין תואם לחודש המודפס", "deterministic",
             "FAIL" if name_mismatch else "PASS", "info", "FILE_NAME_PERIOD_MISMATCH" if name_mismatch else None,
             (f"שם הקובץ מציין {MONTH_HE[d['named']]}, במסמך מודפס {MONTH_HE[d['period']]}. הבדיקה סופרת את החודש המודפס."
              if name_mismatch else "שם הקובץ והחודש המודפס תואמים"),
             [ev["salary_period"]], dimension="period_relevance"),
        crit("PSL-PER-03", f"{R}.period@1.0.0", "תאריך התשלום מתיישב עם תקופת השכר", "hybrid", "PASS", "minor", None,
             f"שולם {d['pay']} — אחרי סוף תקופת השכר ובחודש העוקב", [ev["payment_date"], ev["salary_period"]],
             decided="code", dimension="internal_consistency", escalation="banker"),
        crit("PSL-FIN-01", f"{R}.financials@1.0.0", "שכר ברוטו ונטו לתשלום מודפסים", "deterministic", "PASS", "major",
             None, f"ברוטו {fmt(d['gross'])} ₪ · נטו {fmt(d['net'])} ₪", [ev["gross_pay"], ev["net_pay"]],
             dimension="completeness", escalation="customer"),
        crit("PSL-FIN-02", f"{R}.financials@1.0.0", "ברוטו פחות ניכויים שווה לנטו (בסובלנות)", "deterministic", "PASS",
             "major", None, "החשבון מתיישב", [ev["gross_pay"], ev["total_deductions"], ev["net_pay"]],
             computation=f"{fmt(d['gross'])} − {fmt(d['ded'])} = {fmt(d['gross'] - d['ded'])} (מודפס {fmt(d['net'])})",
             params=[{"name": "arithmetic_tolerance_ils", "value": 2.0, "status": "ENGINEERING_DEFAULT"}],
             dimension="internal_consistency", escalation="banker"),
        crit("PSL-FIN-03", f"{R}.financials@1.0.0", "סכום שורות התשלומים שווה לברוטו", "deterministic", "PASS", "minor",
             None, "שורות התשלומים מסתכמות לברוטו", [ev["gross_pay"]],
             computation=" + ".join(fmt(a) for _, a in d["earnings"]) + f" = {fmt(sum(a for _, a in d['earnings']))}",
             dimension="internal_consistency", escalation="banker"),
        crit("PSL-FIN-05", f"{R}.financials@1.0.0", "הערכים המכריעים אומתו מול הקובץ המקורי", "deterministic", "PASS",
             "major", None, "שם, ת״ז, תקופה, ברוטו ונטו — " + ("עוגנו למילות OCR" if scan else "עוגנו בשכבת הטקסט"),
             [ev[f] for f in ("employee_name", "employee_id", "salary_period", "gross_pay", "net_pay")],
             dimension="evidence_sufficiency", escalation="banker"),
        crit("PSL-FIN-06", f"{R}.financials@1.0.0", "סיווג רכיבי השכר (קבוע / משתנה / החזר הוצאות)", "judge",
             "PASS", "info", None,
             ("רכיבים: " + ", ".join(l for l, _ in d["earnings"]) + ". " +
              ("שעות נוספות — רכיב משתנה; החזר נסיעות — החזר הוצאות." if d["party"] == "BRW-A"
               else "אין רכיב משתנה מודפס; החזר נסיעות ואחזקת טלפון — החזרי הוצאות/הטבות.")),
             [], decided="judge", dimension="semantic", judge=JUDGE),
    ]
    limitations = ["תוצאת בדיקת מסמך בלבד — אינה קבלת המסמך על ידי הבנק ואינה החלטת אשראי.",
                   "האותנטיות של המסמך לא נבדקה (אין חתימה דיגיטלית לאימות)."]
    if scan:
        limitations.insert(0, "המסמך סרוק ואין בו שכבת טקסט; הערכים המכריעים אומתו מול מילות OCR בתוך תיבת הראיה.")
    signals = ["תלוש שכר לחודש", "נטו לתשלום", "סה״כ ניכויים"]
    if reissued:
        signals.append("העתק — הופק מחדש")
        limitations.append("המסמך מסומן 'העתק — הופק מחדש' ונושא מספר מסמך זהה לתלוש אוגוסט שהוגש (DOC-A2).")
    return {
        "document_id": key, "document_version": ver, "sha256": d["sha"], "filename": d["filename"],
        "intake": {"mime_declared": "application/pdf", "mime_sniffed": "application/pdf", "bytes": d["bytes"], "pages": 1,
                   "pages_read": 1, "encrypted": False, "text_layer": "none" if scan else "full",
                   "text_layer_chars": d["chars"], "page_rotations": [0], "duplicate_of": None, "malware_scan": "clean",
                   "demo_marked": True, "digital_signature": "none", "pdf_metadata_signals": []},
        "classification": {"doc_type": "payslip", "doc_type_he": "תלוש שכר", "method": "hybrid", "signals": signals,
                           "claimed_requirement_code": f"INC.PAYSLIP:{d['party']}",
                           "claimed_by_filename": f"payslip {claimed_period}", "matches_claim": "match", "bundle": False,
                           "bundle_parts": []},
        "party_binding": {"assigned_party_id": d["party"], "matched_party_id": d["party"], "relation": "match",
                          "id_relation": "same", "name_relation": "same",
                          "evidence_ids": [ev["employee_id"], ev["employee_name"]]},
        "period": {"kind": "month", "month": d["period"], "evidence_ids": [ev["salary_period"]]},
        "facts": facts, "evidence": evs, "line_items": line_items(doc_id, d, run), "criteria": criteria,
        "dimensions": {"readability": "READABLE", "classification": "MATCHES_REQUIREMENT", "completeness": "COMPLETE",
                       "internal_consistency": "CONSISTENT", "identity_binding": "MATCH", "period_relevance": "IN_SCOPE",
                       "evidence_sufficiency": "SUFFICIENT", "authenticity": "NOT_ASSESSED",
                       "bank_acceptance": "NOT_DETERMINED_BY_PROVIDER"},
        "verdict": "VALID",
        "verdict_reason_codes": ["FILE_NAME_PERIOD_MISMATCH"] if name_mismatch else [],
        "summary_internal_he": (f"תלוש שכר של {p['name']} ל{MONTH_HE[d['period']]}: ברוטו {fmt(d['gross'])} ₪, "
                                f"ניכויים {fmt(d['ded'])} ₪, נטו {fmt(d['net'])} ₪. כל הקריטריונים המכריעים עברו עם ראיה מאומתת."
                                + (" שם הקובץ מציין ספטמבר אך המסמך הוא אוגוסט (העתק שהופק מחדש)." if name_mismatch else "")),
        "limitations_he": limitations, "security_flags": [],
    }


# ---------------------------------------------------------------- shared case pieces
def parties():
    out = []
    for pid, p in PARTIES.items():
        out.append({"party_id": pid, "role": "borrower" if pid == "BRW-A" else "co_borrower",
                    "display_name_he": p["name"], "national_id": p["id"], "employment_type": "salaried",
                    "employers_declared": [p["employer"]],
                    "declared_income": {"net_monthly": money(p["declared_net"]), "basis": "net_regular",
                                        "note_he": p["note"], "source": "mock_bank_adapter"}})
    return out


def requirements():
    reqs = [{"requirement_code": f"INC.PAYSLIP:{pid}", "party_id": pid, "doc_types": ["payslip"],
             "required_periods": ["2026-07", "2026-08", "2026-09"], "min_count": 3, "source": "mock_bank_adapter",
             "evaluate": True, "bank_status": "awaiting_documents"} for pid in PARTIES]
    for code, types in (("FIN.BANK_STATEMENT", ["bank_statement"]), ("FIN.LOAN_BALANCE_REPORT", ["loan_balance_report"]),
                        ("PRP.APPRAISAL", ["appraisal_report"]), ("INS.LIFE", ["life_insurance_policy"]),
                        ("INS.PROPERTY", ["property_insurance_policy"]), ("SEL.UNDERTAKING", ["seller_undertaking"])):
        reqs.append({"requirement_code": code, "party_id": None, "doc_types": types, "required_periods": [],
                     "source": "mock_bank_adapter", "evaluate": False, "bank_status": "awaiting_documents"})
    return reqs


UPLOAD_TIMES = {"DOC-A1": "2026-10-12T07:58:11Z", "DOC-A2": "2026-10-12T07:58:40Z", "DOC-A3": "2026-10-12T07:59:02Z",
                "DOC-B1": "2026-10-12T08:03:15Z", "DOC-B2": "2026-10-12T08:03:31Z", "DOC-B3": "2026-10-12T08:03:48Z",
                "DOC-A3v2": "2026-10-12T08:41:22Z"}


def doc_ref(doc_id):
    d = DOCS[doc_id]
    ref = {"document_id": doc_key(doc_id), "version": version_of(doc_id), "replaces": None, "sha256": d["sha"],
           "filename": d["filename"], "mime": "application/pdf", "bytes": d["bytes"], "uploaded_at": UPLOAD_TIMES[doc_id],
           "submitted_to_bank_at": UPLOAD_TIMES[doc_id], "uploaded_by": f"customer:{d['party']}", "channel": "demo_upload",
           "claimed_requirement_code": f"INC.PAYSLIP:{d['party']}", "assigned_party_id": d["party"],
           "download": {"url": f"https://mcs.example.invalid/api/v1/files/{doc_key(doc_id)}/{version_of(doc_id)}?exp=1760257200&sig=EXAMPLE",
                        "expires_at": "2026-10-12T09:00:00Z"}}
    if doc_id == "DOC-A3v2":
        ref["replaces"] = {"document_id": "DOC-A3", "version": 1}
    return ref


def context():
    return {"as_of": AS_OF, "product": "purchase",
            "transaction": {"type": "second_hand_purchase", "property_city_he": "חיפה", "declared_price": money(2000000),
                            "requested_loan": money(1400000), "dwelling_status": "single",
                            "preliminary_approval": {"issued_on": "2026-09-21", "valid_until": "2026-12-20",
                                                     "source": "mock_bank_adapter"}},
            "parties": parties(),
            "bank_stage": {"code": "DECISION_RECEIVED", "label_he": "קיבלנו החלטה", "authoritative": False,
                           "source": "MOCK_BANK_ADAPTER"}}


def provenance(run, started_docs):
    canonical = json.dumps({"docs": started_docs, "as_of": AS_OF, "policy": "pol-demo-3"}, sort_keys=True)
    return {"provider": "visiontrace", "provider_version": "visiontrace@5a1ca7d+mortgage-documents(TO-BUILD)",
            "mode": "LIVE", "workflow": "mortgage-documents", "workflow_version": "1.0.0", "rubrics": RUBRICS,
            "rule_set_version": "mortgage-documents-rules/1", "policy_store_version": "pol-demo-3",
            "models": {"read": "gemini-3.8-flash", "ocr": "unselected (OTD-03 — Azure Read / Document AI / Tesseract heb)", "judge": "gemini-3.8-flash",
                       "semantic": "gemini-3.8-flash"},
            "prompt_versions": {"read": "vt-mortgage-read/1.0.0", "judge": "vt-mortgage-judge/1.0.0",
                                "semantic": "vt-mortgage-semantic/1.0.0"},
            "input_hash": hashlib.sha256(canonical.encode()).hexdigest(),
            "generated_at": "2026-10-12T08:11:31Z" if run == RUN1 else "2026-10-12T08:42:58Z",
            "trace_id": f"trc-{run}"}


PAYSLIP_PARAMS = [
    {"name": "requested_payslip_count", "value": 3, "status": "CONFIRMED_PUBLIC_SOURCE", "source_ref": "MZ-05"},
    {"name": "payday_day_of_next_month", "value": 9, "status": "CONFIRMED_PUBLIC_SOURCE", "source_ref": "SEC-02"},
    {"name": "window_anchor", "value": "as_of", "status": "PENDING_BANK_POLICY"},
]
TOLERANCE = {"name": "income_variance_tolerance_pct", "value": 5.0, "status": "ENGINEERING_DEFAULT"}


def ev_id(run, doc_id, field):
    return f"ev_{run}_{doc_key(doc_id)}_v{version_of(doc_id)}_{field}"


def set_review(pid, run, docs_by_period, missing, dups, named_disagree):
    supplied = []
    for period, ids in docs_by_period.items():
        item = {"period": period, "document_ids": [doc_key(i) for i in ids], "counted_document_id": doc_key(ids[0])}
        if named_disagree.get(period):
            item["named_period_disagrees"] = [doc_key(i) for i in named_disagree[period]]
        supplied.append(item)
    return {"requirement_code": f"INC.PAYSLIP:{pid}", "party_id": pid, "rubric": "mortgage.income.payslip_coverage@1.0.0",
            "required_periods": ["2026-07", "2026-08", "2026-09"], "supplied": supplied, "missing": missing,
            "duplicates": {k: [doc_key(i) for i in v] for k, v in dups.items()}, "extra": [],
            "status": "INCOMPLETE" if missing else "COMPLETE", "policy_parameters": PAYSLIP_PARAMS,
            "evidence_ids": [ev_id(run, i, "salary_period") for ids in docs_by_period.values() for i in ids]}


def income_comparison(pid, run, doc_ids):
    p = PARTIES[pid]
    nets = [DOCS[i]["net"] for i in doc_ids]
    avg = round(sum(nets) / len(nets), 2)
    pct = round((avg - p["declared_net"]) / p["declared_net"] * 100, 2)
    inconsistent = abs(pct) > TOLERANCE["value"]
    readings = [{"source": "mcs:declared", "value": p["declared_net"], "normalized": money(p["declared_net"]),
                 "counted": True, "note_he": "הצהרה בבקשה (נטו חודשי) — אינה ראיה"}]
    readings += [{"source": doc_key(i), "value": fmt(DOCS[i]["net"]), "normalized": money(DOCS[i]["net"]),
                  "evidence_id": ev_id(run, i, "net_pay"), "counted": True, "note_he": f"נטו לתשלום — {MONTH_HE[DOCS[i]['period']]}"}
                 for i in doc_ids]
    return {"comparison_id": f"XD-INC-DEC:{pid}", "rule_id": "INC-DEC-02", "kind": "aggregate",
            "method_he": "ממוצע 'נטו לתשלום' בתלושים המאומתים (חודש מודפס, מסמך אחד לחודש) מול הנטו החודשי שהוצהר; השוואת נטו לנטו בלבד.",
            "items": [{"concept": "net_monthly_income", "label_he": "הכנסה נטו חודשית", "readings": readings,
                       "outcome": "conflict" if inconsistent else "agree",
                       "explanation_he": (f"ממוצע מתועד {fmt(avg)} ₪ מול מוצהר {fmt(p['declared_net'])} ₪ — "
                                          f"פער {fmt(avg - p['declared_net'])} ₪ ({pct:+.2f}%); סובלנות {TOLERANCE['value']}% (ברירת מחדל הנדסית, ממתינה למדיניות הבנק).")}],
            "tolerance": TOLERANCE, "outcome": "INCONSISTENT" if inconsistent else "CONSISTENT"}, avg, pct


def employer_comparison(pid, run, doc_ids):
    p = PARTIES[pid]
    readings = [{"source": "mcs:declared", "value": p["employer"], "counted": True, "note_he": "מעסיק מוצהר"}]
    readings += [{"source": doc_key(i), "value": p["employer"], "evidence_id": ev_id(run, i, "employer_name"), "counted": True}
                 for i in doc_ids]
    return {"comparison_id": f"XD-EMP:{pid}", "rule_id": "IDN-CON-04", "kind": "values",
            "method_he": "שם המעסיק בכל תלוש מול המעסיק המוצהר (השוואת טקסט מנורמלת; בע״מ/בע\"מ שקולים).",
            "items": [{"concept": "employer_name", "label_he": "שם המעסיק", "readings": readings, "outcome": "agree",
                       "explanation_he": "זהה בכל המסמכים"}], "tolerance": None, "outcome": "CONSISTENT"}


def finding(fid, key, code, severity, state, status, title, internal, customer, run_created, run_updated, *,
            party=None, req=None, docs=(), period=None, items=(), evidence_ids=(), criteria=(), detail=None,
            resolved_run=None, resolution=None, history=None, statements=None):
    return {"finding_id": fid, "key": key, "code": code, "severity": severity, "review_state": state, "status": status,
            "party_id": party, "requirement_code": req, "document_ids": list(docs), "period": period, "title_he": title,
            "message_customer_he": customer, "message_internal_he": internal, "requested_items": list(items),
            "detail": detail or {}, "evidence_ids": list(evidence_ids), "criterion_refs": list(criteria),
            "customer_statements": statements or [], "created_run_id": run_created, "updated_run_id": run_updated,
            "resolved_run_id": resolved_run, "resolution": resolution, "history": history or []}


NOA_STATEMENT = {"statement_id": "stm_noa_0001", "party_id": "BRW-B",
                 "finding_key": "DECLARED_VS_DOCUMENT_INCOME_VARIANCE:BRW-B",
                 "text": "חלק מההכנסה שלי הוא תשלום משתנה — בונוס רבעוני שלא מופיע בתלושים האלה.",
                 "channel": "chat", "transcript_provenance": "typed", "created_at": "2026-10-12T08:20:07Z",
                 "evidentiary_status": "UNVERIFIED_CLAIM", "assessment_he": None}


def findings_run1():
    return [
        finding("fnd_9q2w4e6r1t", "REQUIRED_PERIOD_MISSING:BRW-A:2026-09", "REQUIRED_PERIOD_MISSING", "blocking",
                "CUSTOMER_ACTION_REQUIRED", "OPEN", "חסר תלוש שכר לספטמבר 2026 — עידו",
                "INC.PAYSLIP:BRW-A — נדרשים יולי, אוגוסט, ספטמבר 2026 (3 תלושים אחרונים לפי מדיניות פומבית S05; ספטמבר שולם עד 09.10.2026). כוסו: יולי (DOC-A1), אוגוסט (DOC-A2, DOC-A3). ספטמבר לא כוסה.",
                "כדי להשלים את מסמכי השכר של עידו חסר תלוש השכר של ספטמבר 2026. אפשר להעלות אותו באזור המסמכים.",
                RUN1, RUN1, party="BRW-A", req="INC.PAYSLIP:BRW-A", period="2026-09", items=["payslip:BRW-A:2026-09"],
                criteria=["INC-COV-01"], detail={"required": ["2026-07", "2026-08", "2026-09"], "covered": ["2026-07", "2026-08"]},
                history=[{"at": "2026-10-12T08:11:31Z", "run_id": RUN1, "change": "opened", "actor": "system"}]),
        finding("fnd_3e5r7t9y2u", "DUPLICATE_PERIOD:BRW-A:2026-08", "DUPLICATE_PERIOD", "major",
                "CUSTOMER_ACTION_REQUIRED", "OPEN", "התקבלו שני תלושים לאוגוסט 2026 — עידו",
                "DOC-A2 ו־DOC-A3 מדפיסים תקופת שכר 08/2026, מספר מסמך זהה SAL-ido-2026-08 וסכומים זהים (ברוטו 17,500.00, נטו 13,500.00). DOC-A3 מסומן 'העתק — הופק מחדש' (תאריך הפקה 15.09.2026) ושמו מציין ספטמבר. סיווג: עותק שהופק מחדש של אותו תלוש — לא תוכן סותר. נספר פעם אחת.",
                "התקבלו שני מסמכים של תלוש אוגוסט 2026 (אחד מהם בשם קובץ של ספטמבר). התלוש של ספטמבר עדיין חסר.",
                RUN1, RUN1, party="BRW-A", req="INC.PAYSLIP:BRW-A", docs=["DOC-A2", "DOC-A3"], period="2026-08",
                evidence_ids=[ev_id(RUN1, "DOC-A2", "salary_period"), ev_id(RUN1, "DOC-A3", "salary_period"),
                              ev_id(RUN1, "DOC-A2", "document_number"), ev_id(RUN1, "DOC-A3", "document_number")],
                criteria=["PSL-DUP-02", "PSL-DUP-03"],
                detail={"duplicate_kind": "reissued_copy_same_content", "same_document_number": True, "same_amounts": True,
                        "copies": 2},
                history=[{"at": "2026-10-12T08:11:31Z", "run_id": RUN1, "change": "opened", "actor": "system"}]),
        finding("fnd_5t7y9u1i3o", "FILE_NAME_PERIOD_MISMATCH:DOC-A3", "FILE_NAME_PERIOD_MISMATCH", "info", "INFO", "OPEN",
                "שם הקובץ אינו תואם את החודש המודפס",
                "ido_payslip_2026-09.pdf — שם הקובץ מציין 2026-09; המסמך מדפיס 08/2026. הבדיקה מסתמכת על החודש המודפס.",
                "שם הקובץ ido_payslip_2026-09.pdf מציין את ספטמבר 2026, אך במסמך עצמו מודפס אוגוסט 2026.",
                RUN1, RUN1, party="BRW-A", docs=["DOC-A3"], period="2026-08",
                evidence_ids=[ev_id(RUN1, "DOC-A3", "salary_period")], criteria=["PSL-PER-02"],
                detail={"file_name_claims": "2026-09", "document_prints": "2026-08"},
                history=[{"at": "2026-10-12T08:11:31Z", "run_id": RUN1, "change": "opened", "actor": "system"}]),
        finding("fnd_7u9i1o3p5a", "DECLARED_VS_DOCUMENT_INCOME_VARIANCE:BRW-B", "DECLARED_VS_DOCUMENT_INCOME_VARIANCE",
                "major", "BANKER_REVIEW_REQUIRED", "OPEN", "פער בין ההכנסה המוצהרת לתלושים — נועה",
                "מוצהר נטו 18,500.00 ₪; ממוצע נטו בתלושים המאומתים (יולי–ספטמבר 2026) 16,900.00 ₪ — פער −1,600.00 ₪ (−8.65%). שלושת התלושים זהים ברכיביהם (שכר בסיס 21,500, החזר נסיעות 600, אחזקת טלפון 500); אין רכיב משתנה מודפס. הסובלנות (5%) היא ברירת מחדל הנדסית הממתינה למדיניות הבנק. הממצא אינו קובע דבר על זכאות לאשראי.",
                "נמצא הבדל בין ההכנסה שהוצהרה בבקשה לבין תלושי השכר שהועלו. הנושא הועבר לבדיקה של מומחה המשכנתאות שלך.",
                RUN1, RUN1, party="BRW-B", docs=["DOC-B1", "DOC-B2", "DOC-B3"],
                evidence_ids=[ev_id(RUN1, i, "net_pay") for i in ("DOC-B1", "DOC-B2", "DOC-B3")],
                criteria=["INC-DEC-02", "INC-DEC-03"],
                detail={"declared_net": 18500, "documented_avg_net": 16900.0, "difference_ils": -1600.0,
                        "difference_pct": -8.65, "months": ["2026-07", "2026-08", "2026-09"],
                        "tolerance": TOLERANCE, "semantic_assessment": "INCONSISTENT"},
                history=[{"at": "2026-10-12T08:11:31Z", "run_id": RUN1, "change": "opened", "actor": "system"}]),
    ]


def case_criteria(run, ido_docs, pct_a, pct_b):
    R = "mortgage.income.declared_vs_documented@1.0.0"
    return [
        crit("INC-DEC-01", R, "ההשוואה היא נטו מול נטו לאותם חודשים", "deterministic", "PASS", "major", None,
             "ההצהרה היא נטו חודשי קבוע (basis=net_regular); נלקח 'נטו לתשלום' מכל תלוש", [], dimension="cross_document_consistency"),
        crit("INC-DEC-02", R, "פער מוצהר מול מתועד בגבולות הסובלנות — עידו", "deterministic", "PASS", "major", None,
             f"פער {pct_a:+.2f}% — בתוך {TOLERANCE['value']}%", [ev_id(run, i, "net_pay") for i in ido_docs],
             params=[TOLERANCE], dimension="cross_document_consistency", escalation="banker"),
        crit("INC-DEC-02", R, "פער מוצהר מול מתועד בגבולות הסובלנות — נועה", "deterministic", "NEEDS_REVIEW", "major",
             "DECLARED_VS_DOCUMENT_INCOME_VARIANCE",
             f"פער {pct_b:+.2f}% — מעבר ל־{TOLERANCE['value']}%. סובלנות ממתינה למדיניות בנק ולכן התוצאה NEEDS_REVIEW ולא FAIL.",
             [ev_id(run, i, "net_pay") for i in ("DOC-B1", "DOC-B2", "DOC-B3")], params=[TOLERANCE],
             dimension="cross_document_consistency", escalation="banker"),
        crit("INC-DEC-03", R, "הערכה סמנטית של הפער — נועה", "judge", "NEEDS_REVIEW", "major",
             "DECLARED_VS_DOCUMENT_INCOME_VARIANCE",
             "הגדרות ההכנסה שוות ערך (נטו); אין בתלושים רכיב משתנה; הפער מבוסס בראיות. השערות לבדיקת אדם בלבד: הצהרה שכללה רכיב שאינו מופיע בתלושים האחרונים, או טעות בהצהרה.",
             [ev_id(run, i, "net_pay") for i in ("DOC-B1", "DOC-B2", "DOC-B3")], decided="judge",
             dimension="semantic", escalation="banker",
             judge={**JUDGE, "raw_outcome": "NEEDS_REVIEW"}),
    ]


def run1_result():
    docs = [document_review(i, RUN1, claimed_period=DOCS[i]["named"]) for i in ("DOC-A1", "DOC-A2", "DOC-A3", "DOC-B1", "DOC-B2", "DOC-B3")]
    cmp_a, _, pct_a = income_comparison("BRW-A", RUN1, ["DOC-A1", "DOC-A2"])
    cmp_b, _, pct_b = income_comparison("BRW-B", RUN1, ["DOC-B1", "DOC-B2", "DOC-B3"])
    return {
        "schema_version": "mortgage-review/1", "tenant_id": TENANT, "case_ref": CASE, "review_case_id": RC,
        "review_case_reference": RC_REF, "review_run_id": RUN1, "review_run_reference": RUN1_REF, "parent_run_id": None,
        "trigger": "initial", "state": "succeeded", "started_at": "2026-10-12T08:10:02Z", "finished_at": "2026-10-12T08:11:31Z",
        "provenance": provenance(RUN1, sorted(DOCS[i]["sha"] for i in ("DOC-A1", "DOC-A2", "DOC-A3", "DOC-B1", "DOC-B2", "DOC-B3"))),
        "documents": docs, "superseded_documents": [],
        "set_reviews": [
            set_review("BRW-A", RUN1, {"2026-07": ["DOC-A1"], "2026-08": ["DOC-A2", "DOC-A3"]}, ["2026-09"],
                       {"2026-08": ["DOC-A2", "DOC-A3"]}, {"2026-08": ["DOC-A3"]}),
            set_review("BRW-B", RUN1, {"2026-07": ["DOC-B1"], "2026-08": ["DOC-B2"], "2026-09": ["DOC-B3"]}, [], {}, {}),
        ],
        "cross_document": [cmp_a, cmp_b, employer_comparison("BRW-A", RUN1, ["DOC-A1", "DOC-A2", "DOC-A3"]),
                           employer_comparison("BRW-B", RUN1, ["DOC-B1", "DOC-B2", "DOC-B3"])],
        "case_criteria": case_criteria(RUN1, ["DOC-A1", "DOC-A2"], pct_a, pct_b),
        "findings": findings_run1(),
        "findings_diff": {"opened": [f["key"] for f in findings_run1()], "resolved": [], "changed": [], "unchanged": [],
                          "reopened": []},
        "readiness": {"scope": ["INC.PAYSLIP:BRW-A", "INC.PAYSLIP:BRW-B"], "status": "ACTION_REQUIRED",
                      "by_requirement": [
                          {"requirement_code": "INC.PAYSLIP:BRW-A", "status": "INCOMPLETE",
                           "open_finding_keys": ["REQUIRED_PERIOD_MISSING:BRW-A:2026-09", "DUPLICATE_PERIOD:BRW-A:2026-08"]},
                          {"requirement_code": "INC.PAYSLIP:BRW-B", "status": "COMPLETE",
                           "open_finding_keys": ["DECLARED_VS_DOCUMENT_INCOME_VARIANCE:BRW-B"]}],
                      "open_counts": {"customer": 2, "banker": 1, "info": 1},
                      "not_evaluated": ["FIN.BANK_STATEMENT", "FIN.LOAN_BALANCE_REPORT", "PRP.APPRAISAL", "INS.LIFE",
                                        "INS.PROPERTY", "SEL.UNDERTAKING"],
                      "disclaimer_he": DISCLAIMER},
        "limitations_he": ["נבדקו מסמכי שכר בלבד.",
                           "החודשים הנדרשים חושבו מתאריך הסימולציה 2026-10-12 ומיום התשלום החוקי — עד ה־9 בחודש העוקב (חוק הגנת השכר; SEC-02).",
                           "סובלנות הפער בהכנסה (5%) היא ברירת מחדל הנדסית — ממתינה למדיניות הבנק."],
        "usage": {"llm_calls": 13, "prompt_tokens": 41800, "output_tokens": 6900, "ocr_pages": 1, "estimate_usd": None,
                  "basis": "list_price_estimate", "duration_ms": 89000},
    }


def run2_result():
    ids = ("DOC-A1", "DOC-A2", "DOC-A3v2", "DOC-B1", "DOC-B2", "DOC-B3")
    docs = [document_review(i, RUN2, claimed_period=DOCS[i]["named"]) for i in ids]
    cmp_a, _, pct_a = income_comparison("BRW-A", RUN2, ["DOC-A1", "DOC-A2", "DOC-A3v2"])
    cmp_b, _, pct_b = income_comparison("BRW-B", RUN2, ["DOC-B1", "DOC-B2", "DOC-B3"])
    f1 = findings_run1()
    for f in f1:
        f["updated_run_id"] = RUN2
    missing, dup, fname, variance = f1
    missing.update(status="RESOLVED", resolved_run_id=RUN2,
                   resolution={"basis": "NEW_EVIDENCE", "note_he": "התקבל תלוש ספטמבר 2026 (DOC-A3 גרסה 2) — חודש מודפס 09/2026, אומת.", "actor": "system"})
    missing["history"].append({"at": "2026-10-12T08:42:58Z", "run_id": RUN2, "change": "resolved", "actor": "system",
                               "note_he": "החודש החסר כוסה בבדיקה מחדש של כל סט המסמכים"})
    dup.update(status="RESOLVED", resolved_run_id=RUN2,
               resolution={"basis": "DOCUMENT_WITHDRAWN", "note_he": "העותק הכפול (DOC-A3 גרסה 1) הוחלף בגרסה חדשה; הגרסה הקודמת נשמרת לתיעוד בלבד.", "actor": "system"})
    dup["history"].append({"at": "2026-10-12T08:42:58Z", "run_id": RUN2, "change": "resolved", "actor": "system"})
    fname.update(status="RESOLVED", resolved_run_id=RUN2,
                 resolution={"basis": "DOCUMENT_WITHDRAWN", "note_he": "גרסה 2 של DOC-A3: שם הקובץ והחודש המודפס תואמים (09/2026).", "actor": "system"})
    fname["history"].append({"at": "2026-10-12T08:42:58Z", "run_id": RUN2, "change": "resolved", "actor": "system"})
    statement = dict(NOA_STATEMENT, assessment_he=("שלושת התלושים שהוגשו (יולי–ספטמבר 2026) מדפיסים אותם רכיבים ואין בהם רכיב בונוס או "
                                                    "תשלום משתנה. ההסבר אינו נתמך במסמכים שהוגשו ואינו סותר אותם — נדרשת בדיקת בנקאי."))
    variance["customer_statements"] = [statement]
    variance["evidence_ids"] = [ev_id(RUN2, i, "net_pay") for i in ("DOC-B1", "DOC-B2", "DOC-B3")]
    variance["history"] += [
        {"at": "2026-10-12T08:20:07Z", "run_id": None, "change": "statement_attached", "actor": "customer:BRW-B",
         "note_he": "הסבר הלקוחה צורף כטענה לא מאומתת"},
        {"at": "2026-10-12T08:42:58Z", "run_id": RUN2, "change": "evidence_updated", "actor": "system",
         "note_he": "נבדק מחדש; הפער נותר (−8.65%); ההסבר אינו נתמך בראיות שהוגשו"}]
    findings = [missing, dup, fname, variance]
    return {
        "schema_version": "mortgage-review/1", "tenant_id": TENANT, "case_ref": CASE, "review_case_id": RC,
        "review_case_reference": RC_REF, "review_run_id": RUN2, "review_run_reference": RUN2_REF, "parent_run_id": RUN1,
        "trigger": "replacement", "state": "succeeded", "started_at": "2026-10-12T08:41:40Z", "finished_at": "2026-10-12T08:42:58Z",
        "provenance": provenance(RUN2, sorted(DOCS[i]["sha"] for i in ids)),
        "documents": docs,
        "superseded_documents": [{"document_id": "DOC-A3", "version": 1, "superseded_by_version": 2, "retained": True}],
        "set_reviews": [
            set_review("BRW-A", RUN2, {"2026-07": ["DOC-A1"], "2026-08": ["DOC-A2"], "2026-09": ["DOC-A3v2"]}, [], {}, {}),
            set_review("BRW-B", RUN2, {"2026-07": ["DOC-B1"], "2026-08": ["DOC-B2"], "2026-09": ["DOC-B3"]}, [], {}, {}),
        ],
        "cross_document": [cmp_a, cmp_b, employer_comparison("BRW-A", RUN2, ["DOC-A1", "DOC-A2", "DOC-A3v2"]),
                           employer_comparison("BRW-B", RUN2, ["DOC-B1", "DOC-B2", "DOC-B3"])],
        "case_criteria": case_criteria(RUN2, ["DOC-A1", "DOC-A2", "DOC-A3v2"], pct_a, pct_b) + [
            crit("INC-DEC-04", "mortgage.income.declared_vs_documented@1.0.0", "הסבר הלקוח נבחן מול הראיות (אינו סוגר ממצא)",
                 "judge", "NEEDS_REVIEW", "major", "CUSTOMER_STATEMENT_UNSUPPORTED",
                 "ההסבר 'בונוס רבעוני' אינו מופיע באף תלוש שהוגש; הוא אינו ראיה ולכן הממצא נשאר פתוח לבדיקת בנקאי.",
                 [ev_id(RUN2, i, "net_pay") for i in ("DOC-B1", "DOC-B2", "DOC-B3")], decided="judge",
                 dimension="semantic", escalation="banker", judge={**JUDGE, "raw_outcome": "NEEDS_REVIEW"})],
        "findings": findings,
        "findings_diff": {"opened": [], "resolved": [missing["key"], dup["key"], fname["key"]], "changed": [variance["key"]],
                          "unchanged": [], "reopened": []},
        "readiness": {"scope": ["INC.PAYSLIP:BRW-A", "INC.PAYSLIP:BRW-B"], "status": "HUMAN_REVIEW_REQUIRED",
                      "by_requirement": [
                          {"requirement_code": "INC.PAYSLIP:BRW-A", "status": "COMPLETE", "open_finding_keys": []},
                          {"requirement_code": "INC.PAYSLIP:BRW-B", "status": "COMPLETE",
                           "open_finding_keys": ["DECLARED_VS_DOCUMENT_INCOME_VARIANCE:BRW-B"]}],
                      "open_counts": {"customer": 0, "banker": 1, "info": 0},
                      "not_evaluated": ["FIN.BANK_STATEMENT", "FIN.LOAN_BALANCE_REPORT", "PRP.APPRAISAL", "INS.LIFE",
                                        "INS.PROPERTY", "SEL.UNDERTAKING"],
                      "disclaimer_he": DISCLAIMER},
        "limitations_he": ["נבדקו מסמכי שכר בלבד.", "הבדיקה החוזרת רצה על כל סט המסמכים הנוכחי, לא רק על הקובץ החדש.",
                           "סובלנות הפער בהכנסה (5%) היא ברירת מחדל הנדסית — ממתינה למדיניות הבנק."],
        "usage": {"llm_calls": 12, "prompt_tokens": 39900, "output_tokens": 6400, "ocr_pages": 1, "estimate_usd": None,
                  "basis": "list_price_estimate", "duration_ms": 78000},
    }


def start_request():
    return {"schema_version": "mortgage-review/1", "tenant_id": TENANT, "case_ref": CASE, "review_case_id": None,
            "workflow": "mortgage-documents", "workflow_version": None, "trigger": "initial", "parent_run_id": None,
            "case_context": context(), "requirements": requirements(),
            "documents": [doc_ref(i) for i in ("DOC-A1", "DOC-A2", "DOC-A3", "DOC-B1", "DOC-B2", "DOC-B3")],
            "customer_statements": [], "policy_overrides": [],
            "callback": {"webhook_connection": "conn_mcs_events", "events": ["review.completed", "review.failed", "finding.opened", "finding.resolved"]},
            "idempotency_key": "mcs-DEMO-MTZ-2026-001-r1-7f3a", "consent_ref": "consent-demo-0001", "trace_id": "trc-a3f91c2e7b",
            "requested_by": "service:mortgage-case-service"}


def supplement_submission():
    return {"schema_version": "mortgage-review/1", "review_case_id": RC, "supplement_id": "sup_k3j5h7g9f1",
            "mode": "replace", "documents": [doc_ref("DOC-A3v2")], "customer_statements": [NOA_STATEMENT],
            "idempotency_key": "mcs-DEMO-MTZ-2026-001-sup1-a9c2", "trace_id": "trc-b7d204e9c1"}


def supplement_request():
    return {"supplement_id": "sup_k3j5h7g9f1", "review_case_id": RC, "requested_items": ["payslip:BRW-A:2026-09"],
            "finding_keys": ["REQUIRED_PERIOD_MISSING:BRW-A:2026-09", "DUPLICATE_PERIOD:BRW-A:2026-08"],
            "channel": "touch_upload",
            "message_customer_he": "כדי להשלים את מסמכי השכר של עידו חסר תלוש השכר של ספטמבר 2026. אפשר להעלות אותו באזור המסמכים; אם הקובץ ido_payslip_2026-09.pdf הועלה בטעות, אפשר להחליף אותו.",
            "state": "issued", "expires_at": "2026-10-26T08:16:00Z", "created_at": "2026-10-12T08:16:00Z"}


def history():
    r1, r2 = run1_result(), run2_result()
    return {"review_case_id": RC, "items": [
        {"review_run_id": RUN1, "review_run_reference": RUN1_REF, "parent_run_id": None, "trigger": "initial",
         "state": "succeeded", "started_at": r1["started_at"], "finished_at": r1["finished_at"],
         "documents": ["DOC-A1@1", "DOC-A2@1", "DOC-A3@1", "DOC-B1@1", "DOC-B2@1", "DOC-B3@1"],
         "readiness_status": "ACTION_REQUIRED", "findings_diff": r1["findings_diff"], "provenance": r1["provenance"],
         "is_current": False},
        {"review_run_id": RUN2, "review_run_reference": RUN2_REF, "parent_run_id": RUN1, "trigger": "replacement",
         "state": "succeeded", "started_at": r2["started_at"], "finished_at": r2["finished_at"],
         "documents": ["DOC-A1@1", "DOC-A2@1", "DOC-A3@2", "DOC-B1@1", "DOC-B2@1", "DOC-B3@1"],
         "readiness_status": "HUMAN_REVIEW_REQUIRED", "findings_diff": r2["findings_diff"], "provenance": r2["provenance"],
         "is_current": True}]}


def events():
    base = {"tenant_id": TENANT, "case_ref": CASE, "review_case_id": RC}
    return [
        {**base, "event_id": "evt_0001aa11bb", "type": "review.queued", "occurred_at": "2026-10-12T08:10:00Z", "review_run_id": RUN1,
         "actor": "service:mortgage-case-service", "payload": {"trigger": "initial", "documents": 6}, "trace_id": "trc-a3f91c2e7b"},
        {**base, "event_id": "evt_0002aa11bb", "type": "review.completed", "occurred_at": "2026-10-12T08:11:31Z", "review_run_id": RUN1,
         "actor": "system", "payload": {"readiness": "ACTION_REQUIRED", "open_counts": {"customer": 2, "banker": 1, "info": 1},
                                        "verdicts": {"VALID": 6}, "decision": "human decision required"}, "trace_id": "trc-a3f91c2e7b"},
        {**base, "event_id": "evt_0003aa11bb", "type": "finding.opened", "occurred_at": "2026-10-12T08:11:31Z", "review_run_id": RUN1,
         "actor": "system", "payload": {"key": "REQUIRED_PERIOD_MISSING:BRW-A:2026-09", "severity": "blocking",
                                        "review_state": "CUSTOMER_ACTION_REQUIRED"}},
        {**base, "event_id": "evt_0004aa11bb", "type": "supplement.requested", "occurred_at": "2026-10-12T08:16:00Z", "review_run_id": RUN1,
         "actor": "service:mortgage-case-service", "payload": {"supplement_id": "sup_k3j5h7g9f1", "requested_items": ["payslip:BRW-A:2026-09"]}},
        {**base, "event_id": "evt_0005aa11bb", "type": "supplement.received", "occurred_at": "2026-10-12T08:41:30Z", "review_run_id": None,
         "actor": "customer:BRW-A", "payload": {"supplement_id": "sup_k3j5h7g9f1", "mode": "replace", "documents": 1}},
        {**base, "event_id": "evt_0006aa11bb", "type": "review.completed", "occurred_at": "2026-10-12T08:42:58Z", "review_run_id": RUN2,
         "actor": "system", "payload": {"readiness": "HUMAN_REVIEW_REQUIRED", "open_counts": {"customer": 0, "banker": 1, "info": 0},
                                        "resolved": 3, "decision": "human decision required"}},
        {**base, "event_id": "evt_0007aa11bb", "type": "finding.resolved", "occurred_at": "2026-10-12T08:42:58Z", "review_run_id": RUN2,
         "actor": "system", "payload": {"key": "REQUIRED_PERIOD_MISSING:BRW-A:2026-09", "basis": "NEW_EVIDENCE"}},
        {**base, "event_id": "evt_0008aa11bb", "type": "package.generated", "occurred_at": "2026-10-12T08:43:10Z", "review_run_id": RUN2,
         "actor": "system", "payload": {"package_id": "pkg_2026_10_12_001"}},
    ]


def package():
    r2 = run2_result()
    open_f = [f for f in r2["findings"] if f["status"] == "OPEN"]
    resolved = [f for f in r2["findings"] if f["status"] == "RESOLVED"]
    key_values = []
    for i in ("DOC-A1", "DOC-A2", "DOC-A3v2", "DOC-B1", "DOC-B2", "DOC-B3"):
        d = DOCS[i]
        for f in ("gross_pay", "net_pay"):
            key_values.append({"party_id": d["party"], "field": f, "label_he": LABELS[f], "period": d["period"],
                               "value": d["gross"] if f == "gross_pay" else d["net"], "evidence_id": ev_id(RUN2, i, f),
                               "witness": "ocr_token_match" if d["variant"] == "scan" else "text_layer_exact"})
    inventory = [{"document_id": doc_key(i), "version": version_of(i), "filename": DOCS[i]["filename"], "doc_type": "payslip",
                  "party_id": DOCS[i]["party"], "period": DOCS[i]["period"], "verdict": "VALID", "superseded": False,
                  "viewer_url": f"https://visiontrace.example.invalid/#/mortgage?run={RUN2}&doc={doc_key(i)}"} for i in
                 ("DOC-A1", "DOC-A2", "DOC-A3v2", "DOC-B1", "DOC-B2", "DOC-B3")]
    inventory.append({"document_id": "DOC-A3", "version": 1, "filename": "ido_payslip_2026-09.pdf", "doc_type": "payslip",
                      "party_id": "BRW-A", "period": "2026-08", "verdict": "VALID", "superseded": True, "viewer_url": None})
    return {"package_id": "pkg_2026_10_12_001", "schema_version": "mortgage-review/1", "case_ref": CASE, "review_case_id": RC,
            "review_run_id": RUN2, "generated_at": "2026-10-12T08:43:10Z",
            "case_summary": {"headline_he": "מסמכי השכר של שני הלווים הושלמו; ממצא אחד פתוח לבדיקת בנקאי (פער הכנסה — נועה).",
                             "transaction_he": "רכישת דירה יד שנייה, חיפה; מחיר מוצהר 2,000,000 ₪; הלוואה מבוקשת 1,400,000 ₪; אחרי אישור עקרוני (נתוני mock).",
                             "parties_he": ["עידו לביא — לווה, שכיר", "נועה לביא — לווה, שכירה"],
                             "readiness": r2["readiness"], "bank_stage_he": "קיבלנו החלטה (mock, לא סמכותי)"},
            "document_inventory": inventory, "coverage": r2["set_reviews"], "key_values": key_values,
            "comparisons": r2["cross_document"], "open_findings": open_f, "resolved_findings": resolved,
            "customer_statements": [dict(NOA_STATEMENT, assessment_he=open_f[0]["customer_statements"][0]["assessment_he"])],
            "outstanding_questions_he": ["האם ההכנסה המוצהרת של נועה כוללת רכיב משתנה שאינו מופיע בשלושת התלושים האחרונים? (החלטת בנקאי לגבי ראיה נוספת)",
                                         "מהי סובלנות הפער המקובלת בבנק בין הכנסה מוצהרת למתועדת? (מדיניות בנק)"],
            "suggested_next_actions": [
                {"action_he": "לבחון את פער ההכנסה של נועה ולהחליט אם לעדכן את ההכנסה בבקשה או לבקש ראיה נוספת לפי נוהלי הבנק",
                 "owner": "banker", "finding_keys": ["DECLARED_VS_DOCUMENT_INCOME_VARIANCE:BRW-B"], "non_binding": True},
                {"action_he": "להמשיך באיסוף דפי חשבון ודוח ריכוז יתרות — לא נבדקו בהרצה זו", "owner": "banker",
                 "finding_keys": [], "non_binding": True}],
            "not_evaluated_he": ["דפי תנועות עו״ש (3 חודשים, כל החשבונות)", "דוח ריכוז יתרות הלוואות", "שמאות (מועברת ישירות מהשמאי לבנק)",
                                 "ביטוח חיים וביטוח נכס", "מסמכי מוכר ובטוחות"],
            "limitations_he": r2["limitations_he"],
            "disclaimer_he": DISCLAIMER, "audit_trail": events(), "provenance": r2["provenance"]}


def decision():
    return {"decision_id": "dec_0001", "review_case_id": RC, "review_run_id": RUN2, "action": "waive_finding",
            "finding_keys": ["DECLARED_VS_DOCUMENT_INCOME_VARIANCE:BRW-B"],
            "note_he": "הבנקאית תעדכן את ההכנסה בבקשה לפי ממוצע התלושים (16,900 ₪ נטו). אין צורך בפעולת מסמכים נוספת מהלקוחה.",
            "actor": {"id": "banker:dana.cohen", "role": "banker"}, "request_id": "dec-req-0001-4c1d",
            "acknowledge_document_review_only": True, "created_at": "2026-10-12T09:30:12Z"}


def escalation():
    return {"escalation_id": "esc_0001", "review_case_id": RC, "review_run_id": RUN2, "reason": "open_banker_findings",
            "finding_keys": ["DECLARED_VS_DOCUMENT_INCOME_VARIANCE:BRW-B"],
            "note_he": "מסמכי השכר הושלמו; נותר פער הכנסה פתוח. הלקוחה מסרה הסבר שאינו נתמך במסמכים שהוגשו.",
            "state": "open", "created_at": "2026-10-12T08:43:12Z", "created_by": "service:mortgage-case-service"}


def status_running():
    return {"review_case_id": RC, "review_case_reference": RC_REF, "review_run_id": RUN1, "review_run_reference": RUN1_REF,
            "state": "running", "stage": "extract",
            "progress": {"documents_total": 6, "documents_read": 3, "pages_total": 6, "pages_read": 3},
            "queued_at": "2026-10-12T08:10:00Z", "started_at": "2026-10-12T08:10:02Z", "error": None,
            "result_url": None}


def error_stale():
    return {"code": "stale_review", "message": "The decision names review a3f91c2e7b, but the case's current review is b7d204e9c1. Reload the case and decide on the review you see.",
            "retryable": False, "retry_after_seconds": None, "trace_id": "trc-dec-0002", "details": {"current_review_id": RUN2}}


def facts_response():
    r1 = run1_result()
    doc = next(d for d in r1["documents"] if d["document_id"] == "DOC-A3")
    return {"review_run_id": RUN1, "document_id": "DOC-A3", "document_version": 1, "facts": doc["facts"], "evidence": doc["evidence"]}


# ---------------------------------------------------------------- validation + write
def validator(defname):
    schema = {"$schema": SCHEMA["$schema"], "$ref": f"#/$defs/{defname}", "$defs": SCHEMA["$defs"]}
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def list_validator(defname):
    schema = {"$schema": SCHEMA["$schema"], "type": "array", "items": {"$ref": f"#/$defs/{defname}"}, "$defs": SCHEMA["$defs"]}
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def check(name, payload, v):
    errors = sorted(v.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        for e in errors[:10]:
            print(f"✗ {name}: {list(e.path)} — {e.message[:300]}")
        raise SystemExit(1)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    items = [
        ("01_start_review_request.initial.json", start_request(), validator("StartReviewRequest")),
        ("02_review_status.running.json", status_running(), validator("ReviewStatus")),
        ("03_review_result.run1_initial.json", run1_result(), validator("ReviewResult")),
        ("04_document_facts.DOC-A3_v1.json", facts_response(), None),
        ("05_evidence_item.DOC-A3_salary_period.json", run1_result()["documents"][2]["evidence"][3], validator("EvidenceItem")),
        ("06_supplement_request.json", supplement_request(), validator("SupplementRequest")),
        ("07_customer_statement.json", NOA_STATEMENT, validator("CustomerStatement")),
        ("08_supplement_submission.replace_DOC-A3.json", supplement_submission(), validator("SupplementSubmission")),
        ("09_review_result.run2_after_replacement.json", run2_result(), validator("ReviewResult")),
        ("10_review_history.json", history(), None),
        ("11_escalation.json", escalation(), validator("Escalation")),
        ("12_banker_review_package.json", package(), validator("BankerReviewPackage")),
        ("13_banker_decision.waive.json", decision(), validator("BankerDecision")),
        ("14_lifecycle_events.json", events(), list_validator("LifecycleEvent")),
        ("15_error.stale_review.json", error_stale(), validator("ErrorEnvelope")),
    ]
    fv, ev = list_validator("ExtractedFact"), list_validator("EvidenceItem")
    hv = list_validator("ReviewHistoryEntry")
    for name, payload, v in items:
        if name.startswith("04_"):
            check(name + ":facts", payload["facts"], fv)
            check(name + ":evidence", payload["evidence"], ev)
        elif name.startswith("10_"):
            check(name, payload["items"], hv)
        else:
            check(name, payload, v)
        (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        print(f"✓ {name}")
    print(f"all {len(items)} examples valid against mortgage-review.v1.schema.json")


if __name__ == "__main__":
    main()
