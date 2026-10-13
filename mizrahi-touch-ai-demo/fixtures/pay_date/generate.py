"""Synthetic payslips that print a payment date, in the golden-set layout, for the PS-10 regression tests.
The golden-set payslips print only an issue date and stay untouched; these exercise the printed-date branch.

    backend/.venv/bin/python fixtures/pay_date/generate.py
"""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "out"
BORROWER = {"ref": "IDO", "name": "עידו לוי", "id": "DEMO-ID-001", "employer": "אביב מערכות דיגיטל בע״מ", "role": "מהנדס מערכות"}
PERIOD, PERIOD_HE, GROSS, NET = "2026-09", "ספטמבר 2026", 21500, 15000
# The PRINTED slip's issue date falls inside the salary month: read as a payment date it would need review, so a
# PASS shows the two fields were kept apart.
SLIPS = [
    {"file": "ido_2026_09_PAYDATE_PRINTED.pdf", "payment_date": "09.10.2026", "issue_date": "15.09.2026",
     "expect": {"PS-10": "PASS", "verdict": "VALID"}},
    {"file": "ido_2026_09_PAYDATE_BEFORE_PERIOD.pdf", "payment_date": "25.08.2026", "issue_date": "01.10.2026",
     "expect": {"PS-10": "FAIL", "verdict": "NEEDS_REVIEW"}},
    {"file": "ido_2026_09_PAYDATE_MID_PERIOD.pdf", "payment_date": "15.09.2026", "issue_date": "01.10.2026",
     "expect": {"PS-10": "NEEDS_REVIEW", "verdict": "NEEDS_REVIEW"}},
]
CSS = """
@page{size:A4;margin:0} *{box-sizing:border-box} html,body{margin:0;padding:0;font-family:"Noto Sans Hebrew",Arial,sans-serif;color:#263448}
.sheet{position:relative;width:210mm;height:296.5mm;padding:18mm 19mm 22mm;background:white;overflow:hidden}
.top{display:flex;justify-content:space-between;border-bottom:4px solid #ff780b;padding-bottom:13px;margin-bottom:18px;gap:16px}
.issuer{color:#334157;font-weight:800;font-size:19px}.subissuer{color:#647285;font-size:11px;margin-top:2px}
.corner{text-align:left;direction:ltr;color:#68768c;font-size:10px;line-height:1.65}
.typeTitle{font-size:25px;font-weight:800;color:#334157;margin:0 0 4px}.deck{font-size:11px;color:#6b7888;margin-bottom:16px}
.ribbon{background:#fff3e7;border:1px solid #f7d1b6;padding:9px 11px;border-radius:7px;color:#a45822;font-size:10px;font-weight:700;margin:12px 0 16px}
.sectiontitle{font-size:13px;font-weight:750;color:#34465e;margin:20px 0 10px;border-bottom:1px solid #e6ebf1;padding-bottom:6px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px}.field{background:#f5f7fa;border-radius:8px;padding:10px 11px;min-height:60px}
.k{font-size:10px;color:#667489;margin-bottom:5px}.v{font-size:14px;font-weight:700;color:#263448;unicode-bidi:plaintext}
.table{width:100%;border-collapse:collapse;font-size:11px;margin-top:10px}.table th{background:#e9edf3;text-align:right;padding:9px 10px}
.table td{padding:9px 10px;border-bottom:1px solid #e8edf1}
.note{font-size:10px;color:#607185;background:#f5f7f8;border-right:3px solid #93a4b7;padding:11px 12px;margin-top:16px;line-height:1.75}
.foot{position:absolute;bottom:15mm;left:19mm;right:19mm;border-top:1px solid #e7ebf0;padding-top:9px;display:flex;justify-content:space-between;color:#8b95a3;font-size:10px}
.watermark{position:absolute;top:49%;left:11%;font-size:37px;transform:rotate(-24deg);color:rgba(240,103,34,.085);font-weight:900;white-space:nowrap}
"""


def field(label: str, value: str) -> str:
    return f'<div class="field"><div class="k">{escape(label)}</div><div class="v">{escape(value)}</div></div>'


def payslip_html(slip: dict) -> str:
    b, deduct = BORROWER, GROSS - NET
    rows = [("שכר יסוד", GROSS - 1500, "ברוטו"), ("תוספת / שעות נוספות", 1500, "ברוטו"),
            ("מס הכנסה", round(deduct * .6), "ניכוי"), ("ביטוח לאומי ובריאות", deduct - round(deduct * .6), "ניכוי")]
    table = "".join(f'<tr><td>{escape(a)}</td><td><span dir="ltr">{v:,}</span></td><td>{t}</td></tr>' for a, v, t in rows)
    ref = f"SYN-{b['ref']}-09-{slip['payment_date'].replace('.', '')}"
    return f"""<html lang="he" dir="rtl"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<section class="sheet" dir="rtl"><div class="watermark">מסמך דמו · לא לשימוש</div>
<div class="top"><div><div class="issuer">{escape(b['employer'])}</div><div class="subissuer">מסמך סינתטי לצורכי בדיקות QA בלבד</div></div>
<div class="corner">TEST DATA / NOT VALID<br/>REF: {escape(slip['file'])}<br/>12 OCT 2026</div></div>
<h1 class="typeTitle">תלוש שכר חודשי</h1><div class="deck">ריכוז רכיבי שכר, נתוני עובד ותקופת שכר</div>
<div class="ribbon">⚠ נתוני דוגמה בלבד · אינו אישור בנקאי, תלוש שכר אמיתי, מסמך זכויות או מסמך משפטי תקף.</div>
<div class="grid">{field('שם העובד', b['name'])}{field('מזהה עובד (דמו)', b['id'])}{field('מעסיק', b['employer'])}{field('תפקיד', b['role'])}
{field('חודש שכר', PERIOD_HE)}{field('תאריך תשלום', slip['payment_date'])}{field('תאריך הפקה', slip['issue_date'])}{field('מספר אסמכתת שכר', ref)}</div>
<div class="sectiontitle">רכיבי שכר וניכויים</div><table class="table"><thead><tr><th>רכיב</th><th>סכום (₪)</th><th>סוג</th></tr></thead><tbody>{table}</tbody></table>
<div class="sectiontitle">סיכום שכר לחודש</div><div class="grid">{field('שכר ברוטו (₪)', f'{GROSS:,}')}{field('ניכויים (₪)', f'{deduct:,}')}{field('שכר נטו להעברה (₪)', f'{NET:,}')}</div>
<div class="note">שכר נטו מחושב לצורכי בדיקה: ברוטו פחות הניכויים המוצגים. המסמך משמש לבדיקת תקופה, זהות, תאריך תשלום והצלבת סכומים בלבד. אינו מוכיח אותנטיות.</div>
<div class="foot"><span>JEEN × Mortgage Intelligence · PAY-DATE REGRESSION FIXTURE</span><span>עמוד 1 מתוך 1 · {escape(slip['file'])}</span></div>
</section></body></html>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 794, "height": 1123})
        for slip in SLIPS:
            page.set_content(payslip_html(slip), wait_until="load")
            page.evaluate("document.fonts.ready")
            pdf = page.pdf(format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                           prefer_css_page_size=True)
            (OUT / slip["file"]).write_bytes(pdf)
            manifest.append({**slip, "sha256": hashlib.sha256(pdf).hexdigest(), "bytes": len(pdf), "borrower": BORROWER["ref"],
                             "period": PERIOD, "gross": GROSS, "net": NET, "synthetic": True})
        browser.close()
    (OUT / "manifest.json").write_text(json.dumps({"purpose": "PS-10 printed payment date (golden-set payslips print none)",
                                                   "files": manifest}, ensure_ascii=False, indent=2), encoding="utf8")
    for m in manifest:
        print(f"{m['file']:<40} payment {m['payment_date']} issue {m['issue_date']} → PS-10 {m['expect']['PS-10']}")


if __name__ == "__main__":
    main()
