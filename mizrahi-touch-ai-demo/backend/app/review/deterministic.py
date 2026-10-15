"""Deterministic review utilities — pure functions, no model, no I/O.

Arithmetic, month logic, identity comparison and injection scanning are decided
here, never by a language model. Month semantics follow VisionTrace's
unemployment-claim module (coverage, the month a file NAME claims vs the month a
document PRINTS)."""
from __future__ import annotations

import calendar
import re
import unicodedata
from collections import Counter
from datetime import date, timedelta
from typing import Iterable, Optional

HEBREW_MONTHS = {"ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4, "מאי": 5, "יוני": 6, "יולי": 7,
                 "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12}
HEBREW_MONTH_NAMES = {v: k for k, v in HEBREW_MONTHS.items() if k != "מרס"}

_ISO = re.compile(r"^\s*(\d{4})\s*[-/.]\s*(\d{1,2})\s*$")
_MY = re.compile(r"^\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\s*$")
_DAY = re.compile(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})")
_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_NAMED_NUMERIC = re.compile(r"(?<!\d)(\d{4})[\s._\-](\d{1,2})(?!\d)|(?<!\d)(\d{1,2})[\s._\-](\d{4})(?!\d)")


def _month(year: int, month: int) -> Optional[str]:
    return f"{year:04d}-{month:02d}" if 1 <= month <= 12 and 1990 <= year <= 2100 else None


def parse_month(text: Optional[str]) -> Optional[str]:
    """A salary period as printed (08/2026 · 2026-08 · אוגוסט 2026) → YYYY-MM, or None (never a guess)."""
    value = unicodedata.normalize("NFKC", str(text or "")).strip()
    if not value:
        return None
    if m := _ISO.match(value):
        return _month(int(m.group(1)), int(m.group(2)))
    if m := _MY.match(value):
        return _month(int(m.group(2)), int(m.group(1)))
    for name, number in HEBREW_MONTHS.items():
        if m := re.search(rf"{name}\s+(\d{{4}})", value):
            return _month(int(m.group(1)), number)
    return None


def named_month(filename: Optional[str]) -> Optional[str]:
    """The month a file NAME claims (ido_payslip_2026-09.pdf → 2026-09). Display and a finding only."""
    name = str(filename or "")
    for word, number in HEBREW_MONTHS.items():
        if m := re.search(rf"{word}[\s._\-]*(\d{{4}})", name):
            return _month(int(m.group(1)), number)
    if m := _NAMED_NUMERIC.search(name):
        if m.group(1):
            return _month(int(m.group(1)), int(m.group(2)))
        return _month(int(m.group(4)), int(m.group(3)))
    return None


def parse_amount(text: Optional[str]) -> Optional[float]:
    """A printed amount (₪ 13,500.00 · 13500) → 13500.0, or None."""
    if text is None:
        return None
    s = unicodedata.normalize("NFKC", str(text))
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_day(text: Optional[str]) -> Optional[date]:
    m = _DAY.search(str(text or ""))
    try:
        if m:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = _ISO_DAY.search(str(text or ""))
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except ValueError:
        return None


def shift(month: str, by: int) -> str:
    year, number = (int(p) for p in month.split("-"))
    index = year * 12 + (number - 1) + by
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def requested_months(as_of: date, count: int, payday_day: int) -> list[str]:
    """The `count` latest salary months a borrower can already hold on `as_of`: salary for month M
    is paid by day `payday_day` of M+1, so before that day the latest available month is M-1."""
    latest = shift(f"{as_of.year:04d}-{as_of.month:02d}", -1 if as_of.day >= payday_day else -2)
    return [shift(latest, -i) for i in reversed(range(count))]


def coverage(supplied: Iterable[str], requested: Iterable[str]) -> dict:
    counts = Counter(supplied)
    wanted = list(requested)
    return {"requested": wanted, "distinct": sorted(counts),
            "duplicates": {m: n for m, n in sorted(counts.items()) if n > 1},
            "missing": [m for m in wanted if m not in counts],
            "extra": [m for m in sorted(counts) if m not in wanted]}


def month_label_he(month: str) -> str:
    year, number = month.split("-")
    return f"{HEBREW_MONTH_NAMES[int(number)]} {year}"


def pay_date_check(period: Optional[str], printed: Optional[str], paid: Optional[date], verified: bool,
                   payday_day: int) -> tuple[str, str]:
    """PS-10 decided by code. The Wage Protection Law addendum does not list a payment date among the mandatory
    payslip details, so an absent one stays unknown (NOT_APPLICABLE), never a defect; the issue date is a different
    field and never stands in for it. A printed date that cannot be parsed or verified is left to the judge."""
    if not str(printed or "").strip():
        return ("NOT_APPLICABLE", "תאריך תשלום אינו מודפס בתלוש, מועד התשלום נשאר לא ידוע. "
                                  "תאריך ההפקה הוא שדה אחר ואינו משמש כתאריך תשלום.")
    if not paid or not period:
        return "JUDGE", f"תאריך התשלום המודפס ({printed}) אינו ניתן לפענוח חד־משמעי"
    if not verified:
        return "JUDGE", f"תאריך התשלום ({printed}) לא אומת מול הקובץ המקורי"
    year, month = (int(p) for p in period.split("-"))
    first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    following = shift(period, 1)
    deadline = date(int(following[:4]), int(following[5:]), payday_day)
    shown, label = paid.strftime("%d.%m.%Y"), month_label_he(period)
    if paid < first:
        return "FAIL", f"תאריך התשלום {shown} קודם לתחילת תקופת השכר ({label})"
    if paid < last - timedelta(days=3):
        return "NEEDS_REVIEW", f"תאריך התשלום {shown} בתוך תקופת השכר ({label}) ולפני סופה, מקדמה או תקופה שגויה"
    if paid <= deadline:
        return "PASS", f"תאריך התשלום {shown}, בסוף {label} או עד ה־{payday_day} בחודש העוקב"
    return "PASS", f"תאריך התשלום {shown}, אחרי ה־{payday_day} בחודש העוקב (הערת מידע, לא פגם במסמך)"


_FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})


def name_key(text: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))          # niqqud
    s = re.sub(r"[\u05f3\u05f4'\"`׳״\-.,]", " ", s).translate(_FINALS)
    return " ".join(s.split()).strip()


def name_relation(a: Optional[str], b: Optional[str]) -> str:
    """same · variant (word order / an added or missing word / one-letter slip) · different · unknown."""
    ka, kb = name_key(a), name_key(b)
    if not ka or not kb:
        return "unknown"
    if ka == kb:
        return "same"
    wa, wb = set(ka.split()), set(kb.split())
    if wa == wb or (wa <= wb or wb <= wa) and len(wa & wb) >= 1 and len(wa ^ wb) <= 1:
        return "variant"
    if len(wa & wb) >= 1 and _one_slip(ka, kb):
        return "variant"
    return "different"


def _one_slip(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= 1


def digits(text: Optional[str]) -> str:
    return "".join(ch for ch in str(text or "") if ch.isdigit())


def id_relation(printed: Optional[str], expected: Optional[str]) -> str:
    p, e = digits(printed), digits(expected)
    if not p or not e:
        return "unknown"
    return "same" if p.lstrip("0") == e.lstrip("0") else "different"


_SYNTHETIC_ID = re.compile(r"^\s*DEMO-ID-\d{3}\s*$")


def israeli_id_check(printed: Optional[str]) -> str:
    """valid · invalid · synthetic (a demo identifier) · unknown. The Israeli check digit: digits weighted 1,2,1,2…,
    two-digit products reduced by 9, the sum divisible by 10."""
    if printed and _SYNTHETIC_ID.match(str(printed)):
        return "synthetic"
    d = digits(printed)
    if not d or len(d) > 9:
        return "unknown" if not d else "invalid"
    total = 0
    for i, ch in enumerate(d.zfill(9)):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n - 9 if n > 9 else n
    return "valid" if total % 10 == 0 else "invalid"


def window(as_of: date, days: int) -> tuple[date, date]:
    """The trailing window of `days` days that ends on `as_of`."""
    return as_of - timedelta(days=days - 1), as_of


def coverage_gaps(ranges: Iterable[tuple[date, date]], start: date, end: date, slack_days: int = 3) -> list[tuple[date, date]]:
    """Parts of [start, end] that no range covers. Gaps up to `slack_days` (weekends, statement cut-off days) are ignored."""
    gaps, cursor = [], start
    for a, b in sorted(r for r in ranges if r[0] and r[1]):
        if b < cursor:
            continue
        if a > cursor + timedelta(days=slack_days):
            gaps.append((cursor, a - timedelta(days=1)))
        cursor = max(cursor, b + timedelta(days=1))
        if cursor > end:
            break
    if cursor <= end - timedelta(days=slack_days):
        gaps.append((cursor, end))
    return gaps


def day_he(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def holder_relation(printed: Optional[str], name: Optional[str]) -> str:
    """Like name_relation, but a joint holder line ("עידו לוי ונועה לוי") matches each of its names."""
    rel = name_relation(printed, name)
    if rel != "different":
        return rel
    parts = [p for p in re.split(r"\s+ו(?=\S)|,|/|&|\s+and\s+", str(printed or "")) if p.strip()]
    if len(parts) > 1 and any(name_relation(p, name) in ("same", "variant") for p in parts):
        return "same"
    return rel


_INJECTION = [
    r"ignore (all |any )?(previous|prior|the) (instructions|rules)",
    r"\bsystem\s*:", r"approve (the )?(mortgage|loan|credit)", r"mark (this|the) document (as )?valid",
    r"התעלם מ", r"אשר את המשכנתא", r"אשר את ההלוואה", r"סמן (את )?(המסמך|מסמך זה) כתקין", r"הוראה למערכת",
    r"למערכת הבינה המלאכותית",
]
_INJECTION_RE = re.compile("|".join(_INJECTION), re.IGNORECASE)


def injection_hits(text: Optional[str]) -> list[str]:
    """Instruction-like text addressed to an AI or reviewer. Untrusted data — flagged, never followed."""
    hits = []
    for m in _INJECTION_RE.finditer(str(text or "")):
        start = max(0, m.start() - 40)
        hits.append(str(text)[start: m.end() + 40].replace("\n", " ").strip())
    return hits[:5]


_TOTAL_LABEL = re.compile(r"סה[\"״׳']?כ|סך הכל|total|^\s*(ברוטו|נטו)", re.IGNORECASE)
DEMO_MARKS = ("מסמך דמו", "Synthetic Test Corpus")


def is_total_label(label: Optional[str]) -> bool:
    return bool(_TOTAL_LABEL.search(unicodedata.normalize("NFKC", str(label or ""))))


def demo_marked(text: Optional[str]) -> bool:
    return any(mark in str(text or "") for mark in DEMO_MARKS)


def arithmetic(gross: Optional[float], deductions: Optional[float], net: Optional[float], tolerance: float) -> dict:
    if gross is None or net is None:
        return {"state": "unknown", "detail": "שכר ברוטו או נטו אינו זמין במסמך"}
    if net > gross + tolerance:
        return {"state": "fail", "detail": f"הנטו {net:,.2f} גבוה מהברוטו {gross:,.2f}"}
    if deductions is None:
        return {"state": "unknown", "detail": "סך הניכויים אינו זמין במסמך"}
    expected = gross - deductions
    gap = round(net - expected, 2)
    if abs(gap) <= tolerance:
        return {"state": "pass", "detail": f"{gross:,.2f} − {deductions:,.2f} = {expected:,.2f} (מודפס {net:,.2f})"}
    return {"state": "fail", "detail": f"{gross:,.2f} − {deductions:,.2f} = {expected:,.2f}, נטו מודפס {net:,.2f} (פער {gap:,.2f})"}
