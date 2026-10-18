"""English for the explanations the review CODE writes on a rubric criterion (review/gemini_provider._merge,
review/family_checks, review/deterministic). Each pattern mirrors one Hebrew template exactly; a figure, a date, an ID
or a quote is carried over unchanged, and a person's name gets its Latin spelling. An explanation that matches none of
them is the model's own wording and has no English source: the app shows it as the original."""
from __future__ import annotations

import re
from typing import Callable, Optional

from ..review import deterministic as det
from ..review import prompts as P
from . import en

_MONTHS_HE = {name: number for number, name in det.HEBREW_MONTH_NAMES.items()}
_FIELD_BY_HE = {he: f for f, he in P.FIELD_LABELS_HE.items()}


def _month(label_he: str) -> str:
    """'אוגוסט 2026' → 'August 2026' (det.month_label_he)."""
    name, _, year = label_he.rpartition(" ")
    return f"{en.MONTHS[_MONTHS_HE[name] - 1]} {year}" if name in _MONTHS_HE else label_he


def _fields(labels_he: str) -> str:
    return ", ".join((en.FIELDS.get(_FIELD_BY_HE.get(x.strip(), ""), x.strip())) for x in labels_he.split(","))


def _ils(s: str) -> str:
    return f"₪{s}"


N = r"(-?[\d,]+(?:\.\d+)?)"
D = r"(\d{2}\.\d{2}\.\d{4})"
ANY = r"(.+?)"
Rule = tuple[re.Pattern, Callable[[re.Match], str]]
_RULES: list[tuple[str, Callable[[re.Match], str]]] = [
    # payslip (gemini_provider._merge)
    (rf"תקופת השכר: {ANY}", lambda m: f"Pay period: {_month(m[1])}"),
    ("תקופת השכר אינה מודפסת או אינה ניתנת לפענוח חד־משמעי", lambda m: "The pay period isn't printed or can't be read unambiguously"),
    (rf"חסר במסמך: {ANY}", lambda m: f"Missing from the document: {_fields(m[1])}"),
    (rf"ברוטו {N} ₪ · נטו {N} ₪", lambda m: f"Gross {_ils(m[1])} · net {_ils(m[2])}"),
    (rf"{N} − {N} = {N} \(מודפס {N}\)", lambda m: f"{m[1]} − {m[2]} = {m[3]} (printed {m[4]})"),
    (rf"{N} − {N} = {N}, נטו מודפס {N} \(פער {N}\)", lambda m: f"{m[1]} − {m[2]} = {m[3]}, printed net {m[4]} (a gap of {m[5]})"),
    (rf"הנטו {N} גבוה מהברוטו {N}", lambda m: f"The net {m[1]} is higher than the gross {m[2]}"),
    ("שכר ברוטו או נטו אינו זמין במסמך", lambda m: "Gross or net pay isn't available on the document"),
    ("סך הניכויים אינו זמין במסמך", lambda m: "Total deductions aren't available on the document"),
    (rf"סכום שורות התשלומים {N} שונה מהברוטו המודפס {N}", lambda m: f"The pay lines add up to {m[1]}, not the printed gross {m[2]}"),
    (rf"מעסיק: {ANY}", lambda m: f"Employer: {m[1]}"),
    ("שם המעסיק אינו מזוהה", lambda m: "The employer's name isn't identified"),
    # evidence, injection, holder (shared)
    ("לא חולצו שדות מכריעים שניתן לאמת", lambda m: "No decisive fields that can be verified were extracted"),
    (rf"לא אומתו מול הקובץ: {ANY}", lambda m: f"Not verified against the file: {_fields(m[1])}"),
    ("כל השדות המכריעים אומתו מול הקובץ המקורי", lambda m: "All the decisive fields were verified against the original file"),
    ("המסמך לא שויך ללווה", lambda m: "The document wasn't assigned to a borrower"),
    ("המסמך לא שויך למבקש/ת", lambda m: "The document wasn't assigned to an applicant"),
    (rf"מספר הזהות במסמך אינו של {ANY}, המסמך מזוהה עם {ANY}",
     lambda m: f"The ID number on the document isn't {en.name(m[1])}'s; the document matches {en.name(m[2])}"),
    (rf"מספר הזהות במסמך אינו של {ANY}", lambda m: f"The ID number on the document isn't {en.name(m[1])}'s"),
    (rf"שם העובד במסמך \({ANY}\) אינו {ANY}", lambda m: f"The employee name on the document ({m[1]}) isn't {en.name(m[2])}"),
    (rf"ה?שם ו?מספר ה?זהות תואמים ל{ANY}", lambda m: f"The name and ID number match {en.name(m[1])}"),
    (rf"השם במסמך \({ANY}\) תואם ל{ANY}", lambda m: f"The name on the document ({m[1]}) matches {en.name(m[2])}"),
    (rf"השם במסמך \({ANY}\) אינו {ANY}", lambda m: f"The name on the document ({m[1]}) isn't {en.name(m[2])}"),
    (r"השוואת זהות לא חד־משמעית.*", lambda m: "The identity comparison isn't conclusive"),
    (rf"נמצא במסמך טקסט המופנה למערכת או לבודק: {ANY}",
     lambda m: f"The document contains text addressed to the system or the reviewer: {m[1]}"),
    # payment date (deterministic.pay_date_check)
    ("תאריך תשלום אינו מודפס בתלוש, מועד התשלום נשאר לא ידוע. תאריך ההפקה הוא שדה אחר ואינו משמש כתאריך תשלום.",
     lambda m: "No payment date is printed on the payslip, so the payment date stays unknown. The issue date is a different "
               "field and isn't used as the payment date."),
    (rf"תאריך התשלום המודפס \({ANY}\) אינו ניתן לפענוח חד־משמעי", lambda m: f"The printed payment date ({m[1]}) can't be read unambiguously"),
    (rf"תאריך התשלום \({ANY}\) לא אומת מול הקובץ המקורי", lambda m: f"The payment date ({m[1]}) wasn't verified against the original file"),
    (rf"תאריך התשלום {D} קודם לתחילת תקופת השכר \({ANY}\)",
     lambda m: f"The payment date {m[1]} is before the pay period ({_month(m[2])}) begins"),
    (rf"תאריך התשלום {D} בתוך תקופת השכר \({ANY}\) ולפני סופה, מקדמה או תקופה שגויה",
     lambda m: f"The payment date {m[1]} falls inside the pay period ({_month(m[2])}), before its end: an advance or a wrong period"),
    (rf"תאריך התשלום {D}, בסוף {ANY} או עד ה־(\d+) בחודש העוקב",
     lambda m: f"The payment date {m[1]}: at the end of {_month(m[2])} or by day {m[3]} of the following month"),
    (rf"תאריך התשלום {D}, אחרי ה־(\d+) בחודש העוקב \(הערת מידע, לא פגם במסמך\)",
     lambda m: f"The payment date {m[1]} is after day {m[2]} of the following month (for information, not a defect in the document)"),
    # ID card (family_checks)
    (rf"מספר הזהות {ANY} עומד בבדיקת ספרת הביקורת", lambda m: f"The ID number {m[1]} passes the check-digit test"),
    (rf"מזהה פנימי \({ANY}\), בדיקת ספרת ביקורת אינה חלה עליו", lambda m: f"An internal identifier ({m[1]}); the check-digit test doesn't apply to it"),
    (rf"מספר הזהות {ANY} אינו עומד בבדיקת ספרת הביקורת", lambda m: f"The ID number {m[1]} fails the check-digit test"),
    ("מספר הזהות אינו מודפס או אינו קריא", lambda m: "The ID number isn't printed or isn't legible"),
    ("בדיקת תוקף כבויה במדיניות", lambda m: "The policy has the expiry check switched off"),
    ("תאריך תוקף אינו מודפס", lambda m: "No expiry date is printed"),
    (rf"בתוקף עד {D}", lambda m: f"Valid until {m[1]}"),
    (rf"תוקף התעודה פג ב־{D}", lambda m: f"The card expired on {m[1]}"),
    # bank statement
    (rf"תקופת הדף: {D}–{D}", lambda m: f"Statement period: {m[1]}–{m[2]}"),
    (r"הדף מסתיים (\d+) ימים לפני תאריך הבדיקה, בתוך התקופה הנדרשת",
     lambda m: f"The statement ends {m[1]} days before the check date, within the required period"),
    (rf"הדף מסתיים ב־{D}, (\d+) ימים לפני תאריך הבדיקה, מחוץ לתקופה הנדרשת. נדרש דף עדכני.",
     lambda m: f"The statement ends on {m[1]}, {m[2]} days before the check date, outside the required period. An up-to-date "
               "statement is needed."),
    ("תקופת הדף אינה מודפסת או אינה ניתנת לפענוח", lambda m: "The statement period isn't printed or can't be read"),
    ("לא ניתן לקבוע את עדכניות הדף בלי תקופה מודפסת", lambda m: "Without a printed period, the statement's recency can't be determined"),
    # purpose proof
    (rf"ספק: {ANY} · סכום: {ANY}", lambda m: f"Supplier: {m[1]} · amount: {m[2]}"),
    (r"הופק לפני (\d+) ימים \(עד (\d+)\)", lambda m: f"Issued {m[1]} days ago (up to {m[2]})"),
    (rf"המסמך הופק ב־{D}, מעבר ל־(\d+) הימים שהמדיניות מאפשרת",
     lambda m: f"The document was issued on {m[1]}, beyond the {m[2]} days the policy allows"),
    ("תאריך המסמך אינו מודפס", lambda m: "The document's date isn't printed"),
    # tax assessment
    (r"שנת מס (\d{4})", lambda m: f"Tax year {m[1]}"),
    (r"שנת המס (\d{4}) ישנה, נדרשת שומה של (\d{4}) או מאוחרת",
     lambda m: f"The tax year {m[1]} is too old; an assessment for {m[2]} or later is needed"),
    ("שנת המס אינה מודפסת", lambda m: "The tax year isn't printed"),
    # business registration
    (r"סוג הרישום \(עוסק פטור / מורשה\) אינו מודפס", lambda m: "The registration type (exempt / licensed dealer) isn't printed"),
    (rf"רישום: {ANY}", lambda m: f"Registration: {m[1]}"),
    (rf"במסמך מודפס ״{ANY}״, אבל הדרישה היא ל{ANY}",
     lambda m: f"The document says “{m[1]}”, but the requirement is for {en.REGISTRATION.get(_REG.get(m[2], ''), m[2]).lower()}"),
    ("מספר העוסק אינו מודפס", lambda m: "The dealer number isn't printed"),
    (rf"מספר העוסק {ANY} זהה למספר הזהות של {ANY}", lambda m: f"The dealer number {m[1]} is {en.name(m[2])}'s ID number"),
    (rf"מספר העוסק {ANY} אינו מספר הזהות של {ANY}", lambda m: f"The dealer number {m[1]} isn't {en.name(m[2])}'s ID number"),
    (rf"לא ניתן להשוות את מספר העוסק {ANY}", lambda m: f"The dealer number {m[1]} can't be compared"),
    # profit and loss statement
    (rf"תקופת הדוח {D}–{D}, הסתיימה לפני (\d+) ימים \(עד (\d+)\)",
     lambda m: f"The report covers {m[1]}–{m[2]} and ended {m[3]} days ago (up to {m[4]})"),
    (rf"תקופת הדוח עד {D}, הסתיימה לפני (\d+) ימים \(עד (\d+)\)",
     lambda m: f"The report covers up to {m[1]} and ended {m[2]} days ago (up to {m[3]})"),
    (rf"תקופת הדוח הסתיימה ב־{D}, (\d+) ימים לפני תאריך הבדיקה, מעבר ל־(\d+) הימים שהמדיניות מאפשרת. נדרש דוח עדכני.",
     lambda m: f"The report's period ended on {m[1]}, {m[2]} days before the check date, beyond the {m[3]} days the policy "
               "allows. An up-to-date report is needed."),
    ("תקופת הדוח אינה מודפסת", lambda m: "The report's period isn't printed"),
    (rf"הדוח נערך בידי {ANY}", lambda m: f"The report was prepared by {m[1]}"),
    ("לא מודפס מי ערך או חתם על הדוח", lambda m: "It isn't printed who prepared or signed the report"),
]
_REG = {"עוסק פטור": "vat_exempt", "עוסק מורשה": "vat_registered"}
_COMPILED: list[Rule] = [(re.compile(p), f) for p, f in _RULES]


def explanation(text_he: Optional[str]) -> Optional[str]:
    """The English of an explanation the review code wrote; None for the model's own wording (shown as the original)."""
    text = (text_he or "").strip()
    if not text:
        return None
    for rx, make in _COMPILED:
        m = rx.fullmatch(text)
        if m:
            return make(m)
    return None
