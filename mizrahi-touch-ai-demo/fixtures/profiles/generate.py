"""Generate the synthetic document packs of the six use cases (TC-01…06) and of the new-customer journey.

Every identity is the one of its prepared case (backend/app/bank/mock_bank.py::_USE_CASES), never another applicant's
renamed file: names, identity numbers, employers, businesses, accounts and the company number match the case, and the
amounts match the declarations (payslip nets ≈ declared net; statements carry the matching salary credits). Rendered
from HTML with the system Chrome so every PDF has a real text layer; every page prints "מסמך דמו" and the synthetic
footer. Payslips use the payslip template of fixtures/generate.py; IDs, statements and quotes the templates of
fixtures/loan/generate.py. Deliberately invalid files are named *_OUTDATED / *_COPY and say why in the manifest.

Dates are relative to the demo's simulation date (2026-10-12). Document-age limits are demo-policy assumptions.

Usage:  backend/.venv/bin/python fixtures/profiles/generate.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
FIX = ROOT.parent
OUT = FIX / "presenter" / "profile_set"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LOAN = _load("loan_generate", FIX / "loan" / "generate.py")
PAY = _load("payslip_generate", FIX / "generate.py")
page = LOAN.page

# ---------------------------------------------------------------- people (as in mock_bank._USE_CASES)
P = {
    "michal": {"full": "מיכל ברק", "first": "מיכל", "last": "ברק", "id": "311204572", "birth": "02.11.1986",
               "address": "רחוב הנרקיס 8, כפר סבא", "account": "20-614-338120"},
    "yoav": {"full": "יואב כרמי", "first": "יואב", "last": "כרמי", "id": "DEMO-ID-102", "birth": "17.06.1990",
             "address": "רחוב התבור 21, חיפה", "account": "20-512-104477", "business": "כרמי צילום"},
    "shiran": {"full": "שירן אזולאי", "first": "שירן", "last": "אזולאי", "id": "DEMO-ID-103", "birth": "09.01.1985",
               "address": "שדרות הים 4, אשדוד", "account": "20-433-778015", "business": "אזולאי עיצוב פנים"},
    "alon": {"full": "אלון פרידמן", "first": "אלון", "last": "פרידמן", "id": "DEMO-ID-104", "birth": "28.04.1983",
             "address": "רחוב ויצמן 40, רחובות", "account": "20-701-559310", "business": "פרידמן הדרכות"},
    "roy": {"full": "רועי שטרן", "first": "רועי", "last": "שטרן", "id": "DEMO-ID-105", "birth": "12.12.1987",
            "address": "רחוב הגפן 3, הוד השרון"},
    "maya": {"full": "מאיה שטרן", "first": "מאיה", "last": "שטרן", "id": "DEMO-ID-115", "birth": "30.03.1989",
             "address": "רחוב הגפן 3, הוד השרון", "business": "סטודיו מאיה שטרן — אדריכלות"},
    "gilad": {"full": "גלעד ששון", "first": "גלעד", "last": "ששון", "id": "DEMO-ID-106", "birth": "05.08.1979",
              "address": "רחוב המלאכה 12, פתח תקווה"},
    "neta": {"full": "נטע אלון", "first": "נטע", "last": "אלון", "id": "DEMO-ID-201", "birth": "21.02.1992",
             "address": "רחוב הדקל 15, מודיעין", "account": "20-388-246190"},
}
COMPANY = {"name": "ש.ג. מערכות מיזוג בע״מ", "number": "DEMO-CO-516001060", "account": "20-900-610600",
           "address": "רחוב המלאכה 12, פתח תקווה", "signatory": "גלעד ששון", "partner": "שרון גולן"}
EMPLOYERS = {
    "michal": {"employer": "שחף הנדסה בע״מ", "employer_id": "515338204", "employee_no": "E-4471", "department": "תכנון מבנים",
               "nets": {7: 21000.0, 8: 21300.0, 9: 20850.0}},
    "alon": {"employer": "נתיב תוכנה בע״מ", "employer_id": "516447201", "employee_no": "E-1290", "department": "פיתוח תוכנה",
             "nets": {7: 13900.0, 8: 14100.0, 9: 13850.0}},
    "roy": {"employer": "מרכז רפואי השרון", "employer_id": "580112233", "employee_no": "E-7720", "department": "מעבדות",
            "nets": {7: 15600.0, 8: 15750.0, 9: 15450.0}},
    "neta": {"employer": "גל־אור תקשורת בע״מ", "employer_id": "514902336", "employee_no": "E-3318", "department": "שירות לקוחות",
             "nets": {7: 12000.0, 8: 12150.0, 9: 11900.0}},
}
CPA = {"name": "רו״ח דורית לנדאו", "firm": "לנדאו ושות׳ — רואי חשבון", "license": "רישיון מס׳ DEMO-CPA-30418"}


def _p(key: str) -> dict:
    """A person in the shape the loan templates expect."""
    p = P[key]
    return {"first": p["first"], "last": p["last"], "full": p["full"], "id": p["id"], "birth": p["birth"], "address": p["address"]}


# ---------------------------------------------------------------- documents
def id_card(key: str, expiry: str = "14.07.2032", issued: str = "14.07.2022", copy: bool = False) -> str:
    LOAN.PERSON = _p(key)
    html = LOAN.id_card(expiry, issued)
    if copy:
        html = html.replace('<div class="card">', '<div class="card" style="border-style:dashed;transform:rotate(-1.2deg)">'
                            '<div style="color:#b91c1c;font-weight:700;font-size:9pt">צילום נוסף של התעודה — הועלה לבקשה</div>')
    return html


def payslip(key: str, month: int) -> str:
    e, p = EMPLOYERS[key], P[key]
    net = e["nets"][month]
    tax = round(net * 0.19, 0)
    bl, health, pension = round(net * 0.055, 0), round(net * 0.034, 0), round(net * 0.06, 0)
    travel = 650.0
    base = net + tax + bl + health + pension - travel
    slip = {"period": f"2026-{month:02d}", "pay_date": f"09.{month + 1:02d}.2026", "issued": f"06.{month + 1:02d}.2026",
            "doc_no": f"SAL-{key}-2026-{month:02d}", "earnings": [["שכר בסיס", base], ["החזר נסיעות", travel]],
            "deductions": [["מס הכנסה", tax], ["ביטוח לאומי", bl], ["מס בריאות", health], ["פנסיה — חלק עובד", pension]]}
    borrower = {"name": p["full"], "national_id": p["id"], **{k: e[k] for k in ("employer", "employer_id", "employee_no", "department")}}
    return PAY.payslip_html(slip, borrower, variant="digital")


def _lines(start: date, end: date, credits: list[tuple[int, str, float]], seed: int, rent: float = 5200.0) -> list:
    rng = random.Random(seed)
    out, d = [], start
    while d <= end:
        for day, label, amount in credits:
            if d.day == day:
                amount = amount(d) if callable(amount) else amount
                if amount:
                    out.append((d, label, amount))
        if d.day == 2:
            out.append((d, "הוראת קבע — ארנונה", -410.0))
        if d.day == 10:
            out.append((d, "חיוב כרטיס אשראי", -round(rng.uniform(3600, 6400), 2)))
        if d.day == 15 and rent:
            out.append((d, "העברה — שכר דירה / משכנתא", -rent))
        if d.day in (6, 21):
            out.append((d, "סופרמרקט דמו", -round(rng.uniform(380, 980), 2)))
        d += timedelta(days=1)
    return out


def _small_lines(start: date, end: date, credits: list[tuple[int, str, float]], seed: int) -> list:
    """A secondary household account: a pension credit and a family transfer, utilities and small purchases."""
    rng = random.Random(seed)
    out, d = [], start
    while d <= end:
        for day, label, amount in credits:
            if d.day == day:
                out.append((d, label, amount))
        if d.day == 3:
            out.append((d, "חברת החשמל — הוראת קבע", -round(rng.uniform(310, 470), 2)))
        if d.day == 12:
            out.append((d, "בית מרקחת דמו", -round(rng.uniform(120, 260), 2)))
        if d.day in (8, 23):
            out.append((d, "סופרמרקט דמו", -round(rng.uniform(420, 760), 2)))
        if d.day == 20:
            out.append((d, "קופת חולים — השתתפות עצמית", -95.0))
        d += timedelta(days=1)
    return out


def statement(holder: str, holder_id: str | None, account: str, lines: list, start: date, end: date,
              bank_he: str = "מזרחי־טפחות", opening: float = 9850.40, title: str = "דף תנועות בחשבון עו״ש") -> str:
    balance, rows = opening, []
    for d, label, amount in lines:
        balance = round(balance + amount, 2)
        rows.append(f"<tr><td class='n'>{d:%d.%m.%Y}</td><td>{label}</td>"
                    f"<td class='n'>{'' if amount < 0 else f'{amount:,.2f}'}</td><td class='n'>{'' if amount > 0 else f'{-amount:,.2f}'}</td>"
                    f"<td class='n'>{balance:,.2f}</td></tr>")
    ident = f"<tr><td>מספר זהות</td><td class='n'>{holder_id}</td></tr>" if holder_id else ""
    return page(f"""
<h1>{bank_he} · {title}</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו סינתטי — אינו דף חשבון אמיתי</div>
<table class="kv" style="margin-top:10px">
<tr><td>שם בעל החשבון</td><td>{holder}</td></tr>{ident}
<tr><td>בנק / סניף / חשבון</td><td class="n">{account}</td></tr>
<tr><td>תקופה מתאריך</td><td class="n">{start:%d.%m.%Y}</td></tr><tr><td>עד תאריך</td><td class="n">{end:%d.%m.%Y}</td></tr>
</table>
<h2>תנועות</h2><table><tr><th>תאריך</th><th>תיאור</th><th>זכות</th><th>חובה</th><th>יתרה</th></tr>{''.join(rows)}</table>
<table class="kv" style="margin-top:8px"><tr><td>יתרת סגירה</td><td class="n">{balance:,.2f}</td></tr></table>""")


Q3 = (date(2026, 7, 1), date(2026, 9, 30))


def salary(key: str):
    e = EMPLOYERS[key]
    return (9, f"משכורת — {e['employer']}", lambda d: e["nets"].get(d.month - 1, e["nets"][7]))


def quote(supplier: str, supplier_id: str, customer: str, kind: str, subject: str, items: list[tuple[str, float]],
          issued: str, number: str, validity: str = "ההצעה בתוקף ל־30 יום ממועד הנפקתה.") -> str:
    total = sum(v for _, v in items)
    base = round(total / 1.18, 2)
    rows = "".join(f"<tr><td>{label}</td><td class='n'>{v:,.2f}</td></tr>" for label, v in items)
    return page(f"""
<h1>{supplier} · {kind}</h1><div style="color:#6b7280;font-size:9pt">ח.פ. {supplier_id} (דמו) · מסמך דמו סינתטי</div>
<table class="kv" style="margin-top:10px">
<tr><td>סוג המסמך</td><td>{kind}</td></tr><tr><td>מספר הצעה</td><td class="n">{number}</td></tr>
<tr><td>תאריך</td><td class="n">{issued}</td></tr><tr><td>לכבוד</td><td>{customer}</td></tr>
<tr><td>תיאור</td><td>{subject}</td></tr>
</table>
<h2>פירוט</h2><table><tr><th>פריט</th><th>סכום כולל מע״מ</th></tr>{rows}
<tr><td>מתוכו מע״מ</td><td class="n">{total - base:,.2f}</td></tr>
<tr><td><b>סה״כ לתשלום</b></td><td class="n"><b>{total:,.2f}</b></td></tr></table>
<p>{validity}</p>""")


def car_quote(key: str, model: str, total: float, number: str) -> str:
    return quote("אוטו־דמו יבואנים בע״מ", "51-000000-0", P[key]["full"], "הצעת מחיר לרכב", model,
                 [("מחיר הרכב כולל מע״מ", total)], "01.10.2026", number)


def vat_cert(key: str, exempt: bool, opened: str) -> str:
    p = P[key]
    kind = "עוסק פטור" if exempt else "עוסק מורשה"
    title = "אישור עוסק פטור" if exempt else "תעודת עוסק מורשה"
    note = ("העוסק רשום כעוסק פטור ואינו מגיש דוחות מע״מ תקופתיים; מגיש הצהרת מחזור שנתית." if exempt else
            "העוסק רשום כעוסק מורשה ומגיש דוחות מע״מ תקופתיים.")
    return page(f"""
<h1>רשות המסים בישראל · מע״מ · {title}</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו — אינו אישור רשמי של רשות המסים</div>
<table class="kv" style="margin-top:12px">
<tr><td>שם העוסק</td><td>{p['full']}</td></tr>
<tr><td>מספר זהות</td><td class="n">{p['id']}</td></tr>
<tr><td>שם העסק</td><td>{p['business']}</td></tr>
<tr><td>מספר עוסק</td><td class="n">{p['id']}</td></tr>
<tr><td>סוג הרישום</td><td>{kind}</td></tr>
<tr><td>תאריך פתיחת התיק</td><td class="n">{opened}</td></tr>
<tr><td>כתובת העסק</td><td>{p['address']}</td></tr>
<tr><td>תאריך הפקת האישור</td><td class="n">18.09.2026</td></tr>
</table>
<p>{note}</p><p style="font-size:9pt;color:#4b5563">משרד מע״מ (דמו) · האישור הופק ממערכת דמו לצורך ההדגמה בלבד.</p>""")


def cpa_letter(key: str, year: int, annual: float, issued: str) -> str:
    p = P[key]
    return page(f"""
<h1>{CPA['firm']}</h1><div style="color:#6b7280;font-size:9pt">{CPA['license']} · מסמך דמו סינתטי</div>
<p style="margin-top:14px">לכבוד: מזרחי־טפחות (הדגמה)<br>תאריך: <span class="n">{issued}</span></p>
<h2>אישור רואה חשבון על הכנסות מעסק</h2>
<table class="kv">
<tr><td>שם הנישום</td><td>{p['full']}</td></tr><tr><td>מספר זהות</td><td class="n">{p['id']}</td></tr>
<tr><td>שם העסק</td><td>{p['business']}</td></tr><tr><td>שנת המס</td><td class="n">{year}</td></tr>
<tr><td>הכנסה חייבת מעסק</td><td class="n">{annual:,.2f}</td></tr>
<tr><td>ממוצע חודשי</td><td class="n">{annual / 12:,.2f}</td></tr>
</table>
<p>הריני לאשר כי על פי ספרי העסק והדוח השנתי שהוגש למס הכנסה לשנת המס {year}, הכנסתו החייבת של הנישום מהעסק היא
כמפורט לעיל. האישור ניתן לבקשת הנישום לצורך הגשה לבנק.</p>
<p>בכבוד רב,<br><b>{CPA['name']}</b>, רואת חשבון · {CPA['license']}</p>""")


def tax_assessment(key: str, year: int, annual: float, issued: str) -> str:
    p = P[key]
    tax = round(annual * 0.21, 2)
    return page(f"""
<h1>רשות המסים בישראל · מס הכנסה · הודעת שומה</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו — אינה שומה רשמית</div>
<table class="kv" style="margin-top:12px">
<tr><td>שם הנישום</td><td>{p['full']}</td></tr><tr><td>מספר זהות</td><td class="n">{p['id']}</td></tr>
<tr><td>שם העסק</td><td>{p['business']}</td></tr><tr><td>שנת המס</td><td class="n">{year}</td></tr>
<tr><td>תאריך הפקה</td><td class="n">{issued}</td></tr><tr><td>פקיד שומה</td><td>פקיד שומה דמו</td></tr>
</table>
<h2>סיכום השומה</h2><table><tr><th>רכיב</th><th>סכום</th></tr>
<tr><td>הכנסה חייבת מעסק</td><td class="n">{annual:,.2f}</td></tr><tr><td>מס מחושב</td><td class="n">{tax:,.2f}</td></tr>
<tr><td>מקדמות ששולמו</td><td class="n">{tax - 1240:,.2f}</td></tr><tr><td>יתרה לתשלום</td><td class="n">1,240.00</td></tr></table>
<p>השומה נקבעה על פי הדוח השנתי (טופס 1301) שהגיש הנישום.</p>""")


def pnl(owner: str, owner_id: str | None, business: str, start: str, end: str, issued: str, revenue: float, expenses: float,
        preparer: str = CPA["name"], title: str = "דוח רווח והפסד", entity_line: str = "") -> str:
    rows = [("הכנסות ממכירות ושירותים", revenue), ("עלות המכירות / חומרים", -round(expenses * 0.45, 2)),
            ("הוצאות שכירות ותפעול", -round(expenses * 0.3, 2)), ("הוצאות רכב ונסיעות", -round(expenses * 0.15, 2)),
            ("הוצאות כלליות והנהלה", -round(expenses * 0.1, 2))]
    table = "".join(f"<tr><td>{label}</td><td class='n'>{v:,.2f}</td></tr>" for label, v in rows)
    ident = f"<tr><td>מספר זהות</td><td class='n'>{owner_id}</td></tr>" if owner_id else ""
    return page(f"""
<h1>{title} · {business}</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו סינתטי · לא מבוקר אלא אם צוין אחרת</div>
<table class="kv" style="margin-top:10px">
<tr><td>בעל העסק</td><td>{owner}</td></tr>{ident}{entity_line}
<tr><td>תקופת הדוח מתאריך</td><td class="n">{start}</td></tr><tr><td>עד תאריך</td><td class="n">{end}</td></tr>
<tr><td>תאריך הפקה</td><td class="n">{issued}</td></tr><tr><td>נערך בידי</td><td>{preparer}</td></tr>
</table>
<h2>פירוט</h2><table><tr><th>סעיף</th><th>סכום בש״ח</th></tr>{table}
<tr><td><b>רווח לתקופה</b></td><td class="n"><b>{revenue - expenses:,.2f}</b></td></tr></table>
<p style="font-size:9pt">חתימה: {preparer} · {CPA['license']}</p>""")


def vat_report(key: str, start: str, end: str, sales: float, inputs: float) -> str:
    p = P[key]
    return page(f"""
<h1>רשות המסים · מע״מ · דוח תקופתי (דו־חודשי)</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו — אינו דוח רשמי</div>
<table class="kv" style="margin-top:10px">
<tr><td>שם העוסק</td><td>{p['full']}</td></tr><tr><td>מספר עוסק</td><td class="n">{p['id']}</td></tr>
<tr><td>שם העסק</td><td>{p['business']}</td></tr>
<tr><td>תקופת הדיווח מתאריך</td><td class="n">{start}</td></tr><tr><td>עד תאריך</td><td class="n">{end}</td></tr>
<tr><td>הוגש באמצעות מייצג</td><td>{CPA['name']}</td></tr><tr><td>תאריך הגשה</td><td class="n">14.09.2026</td></tr>
</table>
<h2>סיכום הדיווח</h2><table><tr><th>רכיב</th><th>סכום</th></tr>
<tr><td>עסקאות חייבות (לפני מע״מ)</td><td class="n">{sales:,.2f}</td></tr><tr><td>מע״מ עסקאות</td><td class="n">{sales * 0.18:,.2f}</td></tr>
<tr><td>מע״מ תשומות</td><td class="n">{inputs:,.2f}</td></tr><tr><td>מע״מ לתשלום</td><td class="n">{sales * 0.18 - inputs:,.2f}</td></tr></table>""")


def company_extract(issued: str) -> str:
    return page(f"""
<h1>רשם החברות · נסח חברה</h1><div style="color:#6b7280;font-size:9pt">מסמך דמו — אינו נסח רשמי של רשות התאגידים</div>
<table class="kv" style="margin-top:10px">
<tr><td>שם החברה</td><td>{COMPANY['name']}</td></tr><tr><td>מספר חברה</td><td class="n">{COMPANY['number']}</td></tr>
<tr><td>סוג תאגיד</td><td>חברה פרטית מוגבלת במניות</td></tr><tr><td>סטטוס</td><td>פעילה</td></tr>
<tr><td>תאריך התאגדות</td><td class="n">11.03.2014</td></tr><tr><td>כתובת רשומה</td><td>{COMPANY['address']}</td></tr>
<tr><td>תאריך הפקת הנסח</td><td class="n">{issued}</td></tr>
</table>
<h2>בעלי מניות</h2><table><tr><th>שם</th><th>מזהה</th><th>אחזקה</th></tr>
<tr><td>{COMPANY['signatory']}</td><td class="n">DEMO-ID-106</td><td class="n">60%</td></tr>
<tr><td>{COMPANY['partner']}</td><td class="n">DEMO-ID-126</td><td class="n">40%</td></tr></table>
<h2>דירקטורים</h2><table><tr><th>שם</th><th>מזהה</th><th>מיום</th></tr>
<tr><td>{COMPANY['signatory']}</td><td class="n">DEMO-ID-106</td><td class="n">11.03.2014</td></tr>
<tr><td>{COMPANY['partner']}</td><td class="n">DEMO-ID-126</td><td class="n">01.01.2019</td></tr></table>
<p>שעבודים רשומים: אין · דוח שנתי אחרון הוגש: 2025</p>""")


def signatory_protocol() -> str:
    return page(f"""
<h1>{COMPANY['name']} · פרוטוקול ישיבת דירקטוריון</h1><div style="color:#6b7280;font-size:9pt">ח.פ. {COMPANY['number']} · מסמך דמו סינתטי</div>
<table class="kv" style="margin-top:10px">
<tr><td>תאריך הישיבה</td><td class="n">15.09.2026</td></tr><tr><td>נוכחים</td><td>{COMPANY['signatory']}, {COMPANY['partner']}</td></tr>
</table>
<h2>החלטה: זכויות חתימה</h2>
<p>הוחלט כי מורשה החתימה של החברה הוא <b>{COMPANY['signatory']}</b>, מספר זהות <span class="n">DEMO-ID-106</span>,
מנכ״ל החברה. חתימתו לבדה, בצירוף חותמת החברה, מחייבת את החברה בכל עניין, לרבות פתיחת חשבונות, קבלת אשראי ומימון
ציוד מתאגידים בנקאיים.</p>
<p>אישור עו״ד: אני מאשר/ת כי ההחלטה התקבלה כדין בהתאם לתקנון החברה. <b>עו״ד אבנר מילר (דמו)</b> · מ.ר. DEMO-LAW-5521</p>
<p>חתימות: {COMPANY['signatory']} · {COMPANY['partner']}</p>""")


def audited_fs() -> str:
    return page(f"""
<h1>{COMPANY['name']} · דוחות כספיים ליום 31 בדצמבר 2025</h1><div style="color:#6b7280;font-size:9pt">ח.פ. {COMPANY['number']} · מסמך דמו סינתטי</div>
<h2>דוח רואה החשבון המבקר לבעלי המניות</h2>
<p>ביקרנו את המאזן המצורף של החברה ליום 31 בדצמבר 2025 ואת דוחות רווח והפסד לשנה שהסתיימה באותו תאריך. לדעתנו, הדוחות
הכספיים משקפים באופן נאות, מכל הבחינות המהותיות, את מצבה הכספי של החברה. <b>{CPA['firm']}</b> · {CPA['license']} ·
תאריך חוות הדעת: <span class="n">28.04.2026</span></p>
<h2>מאזן מקוצר (ש״ח)</h2><table><tr><th>סעיף</th><th>31.12.2025</th><th>31.12.2024</th></tr>
<tr><td>נכסים שוטפים</td><td class="n">2,840,500.00</td><td class="n">2,412,300.00</td></tr>
<tr><td>רכוש קבוע, נטו</td><td class="n">1,105,200.00</td><td class="n">1,188,900.00</td></tr>
<tr><td>התחייבויות שוטפות</td><td class="n">1,620,400.00</td><td class="n">1,455,000.00</td></tr>
<tr><td>הון עצמי</td><td class="n">2,325,300.00</td><td class="n">2,146,200.00</td></tr></table>
<h2>דוח רווח והפסד מקוצר (ש״ח)</h2><table><tr><th>סעיף</th><th>2025</th><th>2024</th></tr>
<tr><td>הכנסות</td><td class="n">7,920,000.00</td><td class="n">7,105,000.00</td></tr>
<tr><td>רווח גולמי</td><td class="n">2,215,000.00</td><td class="n">1,960,000.00</td></tr>
<tr><td>רווח נקי</td><td class="n">479,100.00</td><td class="n">402,800.00</td></tr></table>""")


def business_statement() -> str:
    start, end = date(2026, 4, 1), date(2026, 9, 30)
    credits = [(5, "תקבול מלקוח — קבלן ראשי", 186000.0), (18, "תקבול מלקוח — פרויקט מגורים", 142500.0),
               (25, "תקבול מלקוח — שירות ותחזוקה", 38400.0)]
    rng, lines, d = random.Random(106), [], start
    while d <= end:
        for day, label, amount in credits:
            if d.day == day:
                lines.append((d, label, amount))
        if d.day == 9:
            lines.append((d, "משכורות עובדים", -188000.0))
        if d.day == 15:
            lines.append((d, "תשלום לספק — ציוד מיזוג", -round(rng.uniform(98000, 132000), 2)))
        if d.day == 16:
            lines.append((d, "מע״מ ומקדמות מס", -round(rng.uniform(21000, 29000), 2)))
        if d.day == 1:
            lines.append((d, "שכר דירה — מבנה תעשייה", -14500.0))
        d += timedelta(days=1)
    return statement(COMPANY["name"], None, COMPANY["account"], lines, start, end, opening=412300.0,
                     title="דף תנועות בחשבון עסקי").replace(
        "<tr><td>בנק / סניף / חשבון</td>", f"<tr><td>מספר חברה</td><td class='n'>{COMPANY['number']}</td></tr><tr><td>בנק / סניף / חשבון</td>")


def renovation_quote() -> str:
    return quote("שיפוצי הגליל בע״מ", "51-555555-5", "רועי שטרן ומאיה שטרן", "הצעת מחיר לשיפוץ דירה",
                 "שיפוץ דירה ברחוב הגפן 3, הוד השרון: מטבח, שני חדרי רחצה, ריצוף ואינסטלציה",
                 [("עבודות הריסה ופינוי", 14800.0), ("אינסטלציה וחשמל", 38500.0), ("מטבח כולל התקנה", 52000.0),
                  ("חדרי רחצה", 41200.0), ("ריצוף וצבע", 19500.0)], "28.09.2026", "R-2026-0917")


# ---------------------------------------------------------------- the packs: file → (owner, html, note)
def files() -> dict[str, tuple[str, callable]]:
    yoav_credit = [(4, "תקבול — לקוח צילום אירועים", 7200.0), (19, "תקבול — לקוח צילום מוצרים", 5300.0)]
    shiran_credit = [(3, "תקבול — לקוח עיצוב דירה", 14800.0), (17, "תקבול — לקוח פרויקט משרד", 12900.0)]
    alon_credit = [salary("alon"), (22, "תקבול — סדנת הדרכה", 4100.0)]
    roy_rachel = [(1, "העברה מרחל שטרן — השתתפות בהוצאות", 1500.0), (11, "קצבת זקנה — רחל שטרן", 3400.0)]
    joint = [salary("roy"), (12, "תקבול — סטודיו מאיה שטרן", 13200.0), (26, "תקבול — לקוח תכנון", 4800.0)]
    return {
        # TC-01 · מיכל ברק · שכירה
        "id_card_michal.pdf": lambda: id_card("michal"),
        **{f"payslip_michal_2026-{m:02d}.pdf": (lambda m=m: payslip("michal", m)) for m in (7, 8, 9)},
        "statement_michal_2026-07_09.pdf": lambda: statement(P["michal"]["full"], P["michal"]["id"], P["michal"]["account"],
                                                              _lines(*Q3, [salary("michal")], 101, 6100.0), *Q3),
        "car_quote_michal.pdf": lambda: car_quote("michal", "רכב משפחתי חדש, דגם דמו 1.6 היברידי, שנת ייצור 2026", 132000.0, "Q-2026-5102"),
        # TC-02 · יואב כרמי · עוסק פטור
        "id_card_yoav.pdf": lambda: id_card("yoav", "03.02.2033", "03.02.2023"),
        "statement_yoav_2026-07_09.pdf": lambda: statement(P["yoav"]["full"], P["yoav"]["id"], P["yoav"]["account"],
                                                            _lines(*Q3, yoav_credit, 102, 3900.0), *Q3),
        "car_quote_yoav.pdf": lambda: car_quote("yoav", "רכב מסחרי קל, דגם דמו ואן, שנת ייצור 2025 (יד שנייה)", 68000.0, "Q-2026-5207"),
        "vat_exempt_cert_yoav.pdf": lambda: vat_cert("yoav", True, "01.03.2019"),
        "cpa_income_letter_yoav_2025.pdf": lambda: cpa_letter("yoav", 2025, 134400.0, "22.09.2026"),
        # TC-03 · שירן אזולאי · עוסקת מורשית
        "id_card_shiran.pdf": lambda: id_card("shiran", "19.11.2030", "19.11.2020"),
        "statement_shiran_2026-07_09.pdf": lambda: statement(P["shiran"]["full"], P["shiran"]["id"], P["shiran"]["account"],
                                                              _lines(*Q3, shiran_credit, 103, 6800.0), *Q3),
        "car_quote_shiran.pdf": lambda: car_quote("shiran", "רכב פנאי חדש, דגם דמו קרוסאובר, שנת ייצור 2026", 152000.0, "Q-2026-5311"),
        "tax_assessment_shiran_2025.pdf": lambda: tax_assessment("shiran", 2025, 236400.0, "12.08.2026"),
        "vat_dealer_cert_shiran.pdf": lambda: vat_cert("shiran", False, "15.05.2016"),
        "pnl_shiran_2025_OUTDATED.pdf": lambda: pnl(P["shiran"]["full"], P["shiran"]["id"], P["shiran"]["business"],
                                                    "01.01.2025", "31.12.2025", "20.02.2026", 412000.0, 175600.0),
        "pnl_shiran_2026-01_09.pdf": lambda: pnl(P["shiran"]["full"], P["shiran"]["id"], P["shiran"]["business"],
                                                 "01.01.2026", "30.09.2026", "08.10.2026", 318500.0, 139200.0),
        "vat_report_shiran_2026-07_08.pdf": lambda: vat_report("shiran", "01.07.2026", "31.08.2026", 74600.0, 5180.0),
        # TC-04 · אלון פרידמן · שכיר + עוסק פטור
        "id_card_alon.pdf": lambda: id_card("alon", "08.09.2029", "08.09.2019"),
        **{f"payslip_alon_2026-{m:02d}.pdf": (lambda m=m: payslip("alon", m)) for m in (7, 8, 9)},
        "statement_alon_2026-07_09.pdf": lambda: statement(P["alon"]["full"], P["alon"]["id"], P["alon"]["account"],
                                                            _lines(*Q3, alon_credit, 104, 5600.0), *Q3),
        "car_quote_alon.pdf": lambda: car_quote("alon", "רכב משפחתי חדש, דגם דמו 1.5 טורבו, שנת ייצור 2026", 124000.0, "Q-2026-5418"),
        "vat_exempt_cert_alon.pdf": lambda: vat_cert("alon", True, "10.10.2021"),
        "cpa_income_letter_alon_2025.pdf": lambda: cpa_letter("alon", 2025, 42000.0, "24.09.2026"),
        # TC-05 · רועי ומאיה שטרן · שני לווים
        "id_card_roy.pdf": lambda: id_card("roy", "26.06.2031", "26.06.2021"),
        "id_card_maya.pdf": lambda: id_card("maya", "11.04.2034", "11.04.2024"),
        "id_card_maya_COPY.pdf": lambda: id_card("maya", "11.04.2034", "11.04.2024", copy=True),
        **{f"payslip_roy_2026-{m:02d}.pdf": (lambda m=m: payslip("roy", m)) for m in (7, 8, 9)},
        "statement_stern_joint_2026-07_09.pdf": lambda: statement("רועי שטרן ומאיה שטרן", None, "20-655-310442",
                                                                   _lines(*Q3, joint, 105, 7400.0), *Q3),
        "statement_roy_rachel_2026-07_09.pdf": lambda: statement("רועי שטרן ורחל שטרן", None, "20-655-118097",
                                                                  _small_lines(*Q3, roy_rachel, 115), *Q3, opening=8640.0),
        "renovation_quote_stern.pdf": lambda: renovation_quote(),
        "tax_assessment_maya_2025.pdf": lambda: tax_assessment("maya", 2025, 171600.0, "03.08.2026"),
        "vat_dealer_cert_maya.pdf": lambda: vat_cert("maya", False, "02.01.2018"),
        "pnl_maya_2026-01_09.pdf": lambda: pnl(P["maya"]["full"], P["maya"]["id"], P["maya"]["business"],
                                               "01.01.2026", "30.09.2026", "07.10.2026", 236800.0, 101300.0),
        # TC-06 · ש.ג. מערכות מיזוג בע״מ
        "id_card_gilad.pdf": lambda: id_card("gilad", "17.12.2030", "17.12.2020"),
        "company_extract_sg_OUTDATED.pdf": lambda: company_extract("02.06.2026"),
        "company_extract_sg.pdf": lambda: company_extract("05.10.2026"),
        "signatory_protocol_sg.pdf": lambda: signatory_protocol(),
        "audited_fs_sg_2025.pdf": lambda: audited_fs(),
        "interim_pnl_sg_2026-01_06.pdf": lambda: pnl(COMPANY["name"], None, COMPANY["name"], "01.01.2026", "30.06.2026",
                                                     "05.08.2026", 4185000.0, 3922000.0, title="דוח רווח והפסד ביניים",
                                                     entity_line=f"<tr><td>מספר חברה</td><td class='n'>{COMPANY['number']}</td></tr>"),
        "business_statements_sg_2026-04_09.pdf": lambda: business_statement(),
        # new-customer journey · נטע אלון · שכירה
        "id_card_neta.pdf": lambda: id_card("neta", "02.05.2033", "02.05.2023"),
        **{f"payslip_neta_2026-{m:02d}.pdf": (lambda m=m: payslip("neta", m)) for m in (7, 8, 9)},
        "statement_neta_2026-07_09.pdf": lambda: statement(P["neta"]["full"], P["neta"]["id"], P["neta"]["account"],
                                                            _lines(*Q3, [salary("neta")], 201, 4300.0), *Q3),
        "car_quote_neta.pdf": lambda: car_quote("neta", "רכב עירוני חדש, דגם דמו 1.2, שנת ייצור 2026", 96000.0, "Q-2026-5650"),
    }


def main() -> None:
    import sys
    only = set(sys.argv[1:])           # regenerate only these files: the others keep the checksums their recordings use
    OUT.mkdir(parents=True, exist_ok=True)
    previous = {f["file"]: f for f in json.loads((OUT / "manifest.json").read_text(encoding="utf8"))["files"]} \
        if only and (OUT / "manifest.json").exists() else {}
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        pg = browser.new_page()
        for name, html in files().items():
            if only and name not in only:
                out.append(previous[name])
                continue
            pg.set_content(html(), wait_until="load")
            pdf = pg.pdf(format="A4", print_background=True)
            (OUT / name).write_bytes(pdf)
            out.append({"file": name, "sha256": hashlib.sha256(pdf).hexdigest(), "bytes": len(pdf)})
        browser.close()
    (OUT / "manifest.json").write_text(json.dumps({"files": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"{len(out)} files → {OUT}")


if __name__ == "__main__":
    main()
