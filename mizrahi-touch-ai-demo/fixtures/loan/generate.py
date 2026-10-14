"""Generate the synthetic personal-loan documents (ID card, current-account statements, proof of purpose).

Rendered from HTML with the system Chrome (Playwright, channel="chrome") so the PDFs carry a real text layer; the
unreadable variant is rasterised and degraded like fixtures/generate.py does. Every document prints "מסמך דמו" and a
synthetic-corpus footer, and every identity is the synthetic golden-set identity (DEMO-ID-001), never a real number.
Payslips are not generated here: the loan cases reuse the golden-set payslips (fixtures/presenter/golden_set).

Usage:  backend/.venv/bin/python fixtures/loan/generate.py
"""
from __future__ import annotations

import hashlib
import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "presenter" / "loan_set"           # served by the presenter pane; never inside golden_set
PERSON = {"first": "עידו", "last": "לוי", "full": "עידו לוי", "id": "DEMO-ID-001", "birth": "14.03.1988",
          "address": "רחוב הדמו 12, רמת גן"}
FOOTER = "מסמך דמו · Synthetic Test Corpus · JEEN × מזרחי־טפחות — אינו מסמך אמיתי"
STYLE = """
@page { size: A4; margin: 14mm; }
body { font-family: Arial, "Arial Hebrew", sans-serif; color: #1f2937; font-size: 10.5pt; margin: 0; }
.wm { position: fixed; top: 40%; left: 10%; font-size: 64pt; color: rgba(200,30,30,.08); transform: rotate(-24deg); }
h1 { font-size: 16pt; color: #1d4f7a; margin: 0 0 4px; } h2 { font-size: 11pt; margin: 14px 0 6px; color: #1d4f7a; }
table { width: 100%; border-collapse: collapse; } td, th { border-bottom: 1px solid #e5e7eb; padding: 4px 6px; text-align: right; }
th { background: #f3f4f6; font-weight: 700; } .n { text-align: left; direction: ltr; unicode-bidi: embed; }
.kv td:first-child { width: 34%; color: #4b5563; } .footer { margin-top: 18px; font-size: 8pt; color: #6b7280; }
.card { border: 2px solid #1d4f7a; border-radius: 12px; padding: 16px; width: 150mm; }
.photo { float: left; width: 30mm; height: 38mm; background: #e5e7eb; border: 1px solid #9ca3af; text-align: center;
         line-height: 38mm; color: #6b7280; font-size: 9pt; }
"""


def page(body: str) -> str:
    return (f'<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><style>{STYLE}</style></head><body>'
            f'<div class="wm">מסמך דמו</div>{body}<div class="footer">{FOOTER}</div></body></html>')


def id_card(expiry: str, issued: str) -> str:
    return page(f"""
<div class="card"><div class="photo">תמונה</div>
<h1>מדינת ישראל · תעודת זהות</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו — אינו תעודה רשמית</div>
<table class="kv" style="margin-top:10px;width:105mm">
<tr><td>שם משפחה</td><td>{PERSON['last']}</td></tr><tr><td>שם פרטי</td><td>{PERSON['first']}</td></tr>
<tr><td>שם מלא</td><td>{PERSON['full']}</td></tr>
<tr><td>מספר זהות</td><td class="n">{PERSON['id']}</td></tr><tr><td>תאריך לידה</td><td class="n">{PERSON['birth']}</td></tr>
<tr><td>תאריך הנפקה</td><td class="n">{issued}</td></tr><tr><td>תוקף עד</td><td class="n">{expiry}</td></tr>
</table></div>""")


def _salary_lines(start: date, end: date) -> list[tuple[date, str, float]]:
    rng = random.Random(start.toordinal())
    lines: list[tuple[date, str, float]] = []
    d = start
    while d <= end:
        if d.day == 9:
            lines.append((d, "משכורת — אביב מערכות דיגיטל בע״מ", {7: 14400.0, 8: 14700.0, 9: 15000.0}.get(d.month, 14500.0)))
        if d.day == 2:
            lines.append((d, "הוראת קבע — ועד בית", -250.0))
        if d.day == 10:
            lines.append((d, "חיוב כרטיס אשראי", -round(rng.uniform(3200, 5200), 2)))
        if d.day == 15:
            lines.append((d, "העברה — שכר דירה", -6200.0))
        if d.day in (5, 20):
            lines.append((d, "סופרמרקט דמו", -round(rng.uniform(300, 900), 2)))
        d += timedelta(days=1)
    return lines


def statement(start: date, end: date, holder: str = PERSON["full"], account: str = "12-345-678901") -> str:
    balance = 8420.55
    rows = []
    for d, label, amount in _salary_lines(start, end):
        balance = round(balance + amount, 2)
        rows.append(f"<tr><td class='n'>{d:%d.%m.%Y}</td><td>{label}</td>"
                    f"<td class='n'>{'' if amount < 0 else f'{amount:,.2f}'}</td><td class='n'>{'' if amount > 0 else f'{-amount:,.2f}'}</td>"
                    f"<td class='n'>{balance:,.2f}</td></tr>")
    return page(f"""
<h1>מזרחי־טפחות · דף תנועות בחשבון עו״ש</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו סינתטי — אינו דף חשבון אמיתי</div>
<table class="kv" style="margin-top:10px">
<tr><td>שם בעל החשבון</td><td>{holder}</td></tr><tr><td>מספר זהות</td><td class="n">{PERSON['id']}</td></tr>
<tr><td>בנק / סניף / חשבון</td><td class="n">{account}</td></tr>
<tr><td>תקופה מתאריך</td><td class="n">{start:%d.%m.%Y}</td></tr><tr><td>עד תאריך</td><td class="n">{end:%d.%m.%Y}</td></tr>
</table>
<h2>תנועות</h2><table><tr><th>תאריך</th><th>תיאור</th><th>זכות</th><th>חובה</th><th>יתרה</th></tr>{''.join(rows)}</table>
<table class="kv" style="margin-top:8px"><tr><td>יתרת סגירה</td><td class="n">{balance:,.2f}</td></tr></table>""")


def car_quote(issued: str, total: float) -> str:
    base = round(total / 1.18, 2)
    return page(f"""
<h1>אוטו־דמו יבואנים בע״מ · הצעת מחיר</h1><div style="color:#6b7280;font-size:9pt">ח.פ. 51-000000-0 (דמו) · מסמך דמו סינתטי</div>
<table class="kv" style="margin-top:10px">
<tr><td>סוג המסמך</td><td>הצעת מחיר לרכב חדש</td></tr><tr><td>מספר הצעה</td><td class="n">Q-2026-4471</td></tr>
<tr><td>תאריך</td><td class="n">{issued}</td></tr><tr><td>לכבוד</td><td>{PERSON['full']}</td></tr>
<tr><td>הרכב</td><td>רכב משפחתי חדש, דגם דמו 1.5 טורבו, שנת ייצור 2026</td></tr>
</table>
<h2>פירוט</h2><table><tr><th>פריט</th><th>סכום</th></tr>
<tr><td>מחיר הרכב לפני מע״מ</td><td class="n">{base:,.2f}</td></tr><tr><td>מע״מ</td><td class="n">{total - base:,.2f}</td></tr>
<tr><td><b>סה״כ לתשלום</b></td><td class="n"><b>{total:,.2f}</b></td></tr></table>
<p>ההצעה בתוקף ל־30 יום ממועד הנפקתה.</p>""")


FILES = {
    "id_card_ido.pdf": ("id_document", lambda: id_card("20.05.2031", "20.05.2021"), "valid"),
    "id_card_ido_EXPIRED.pdf": ("id_document", lambda: id_card("01.03.2025", "01.03.2015"), "expired"),
    "statement_ido_2026-07_09.pdf": ("bank_statement", lambda: statement(date(2026, 7, 1), date(2026, 9, 30)), "valid"),
    "statement_ido_2026-07.pdf": ("bank_statement", lambda: statement(date(2026, 7, 1), date(2026, 7, 31)), "partial"),
    "statement_ido_2026-08.pdf": ("bank_statement", lambda: statement(date(2026, 8, 1), date(2026, 8, 31)), "partial"),
    "statement_ido_2026-09.pdf": ("bank_statement", lambda: statement(date(2026, 9, 1), date(2026, 9, 30)), "partial"),
    "statement_ido_STALE_2026-04_06.pdf": ("bank_statement", lambda: statement(date(2026, 4, 1), date(2026, 6, 30)), "stale"),
    "car_quote_ido.pdf": ("purpose_proof", lambda: car_quote("01.10.2026", 118000.0), "valid"),
    "car_quote_ido_OLD.pdf": ("purpose_proof", lambda: car_quote("15.03.2026", 112000.0), "stale"),
}


def raster(pdf: bytes, dpi: int, blur: float, seed: int) -> bytes:
    src = pymupdf.open(stream=pdf, filetype="pdf")
    out = pymupdf.open()
    rng = random.Random(seed)
    for p in src:
        pix = p.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).rotate(rng.uniform(-2, 2), expand=True,
                                                                                   fillcolor="white")
        img = img.filter(ImageFilter.GaussianBlur(blur))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=20)
        page_ = out.new_page(width=p.rect.width, height=p.rect.height)
        page_.insert_image(page_.rect, stream=buf.getvalue())
    data = out.tobytes()
    src.close()
    out.close()
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page_ = browser.new_page()
        for name, (family, html, variant) in FILES.items():
            page_.set_content(html(), wait_until="load")
            pdf = page_.pdf(format="A4", print_background=True)
            (OUT / name).write_bytes(pdf)
            manifest.append({"file": name, "family": family, "variant": variant, "sha256": hashlib.sha256(pdf).hexdigest()})
        browser.close()
    unreadable = raster((OUT / "id_card_ido.pdf").read_bytes(), dpi=22, blur=1.8, seed=7)
    (OUT / "id_card_ido_UNREADABLE.pdf").write_bytes(unreadable)
    manifest.append({"file": "id_card_ido_UNREADABLE.pdf", "family": "id_document", "variant": "unreadable",
                     "sha256": hashlib.sha256(unreadable).hexdigest()})
    (OUT / "manifest.json").write_text(json.dumps({"files": manifest}, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"{len(manifest)} files → {OUT}")


if __name__ == "__main__":
    main()
