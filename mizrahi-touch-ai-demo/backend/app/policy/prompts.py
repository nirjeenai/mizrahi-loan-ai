"""Talk prompt and message-template checks for the Admin: a light lint, `{{variable}}` rendering and synthetic preview
values.

The lint only warns (doc 03 S38): a prompt that says "call now" changes nothing, because when to contact a customer
is decided by the follow-up policy in code, never by prompt text. Two findings are errors because they break a locked
rule: an unknown variable, and an opening without the AI disclosure."""
from __future__ import annotations

import re
from typing import Any, Optional

from .schema import PROMPT_VARIABLES

VARIABLE = re.compile(r"{{\s*(\w+)\s*}}")
# synthetic values only; never a real customer's data
PREVIEW_VARIABLES: dict[str, Any] = {
    "first_name": "עידו",
    "missing_documents": ["תלוש שכר לספטמבר 2026", "דף עו״ש של החשבון המשותף לספטמבר 2026"],
    "secure_upload_link": "https://demo.invalid/u/DEMO-LINK",
    "next_step": "אחרי ההעלאה נבדוק את המסמך ונעדכן אותך באפליקציה",
}
DISCLOSURE = re.compile(r"בינה מלאכותית|סוכנת? דיגיטלי|\bAI\b|בוט")
# "אל תבטיחי אישור" is an instruction, not a promise: a negation earlier in the same clause cancels a match
_NEGATION = re.compile(r"(^|\s)ו?(אל|לא|אסור|אין|בלי|ללא|אף פעם)(\s|$)")
_CLAUSE_END = re.compile(r"[.,;:!?\n]")

# (code, severity, pattern, message, negatable)
_RULES: list[tuple[str, str, re.Pattern, str, bool]] = [
    ("PROMPT_URGENCY", "warning",
     re.compile(r"התקשר(ו|י)?\s+(מיד|מייד|עכשיו)|באופן מיידי|בדחיפות|\bדחוף\b|בלי לחכות|ללא המתנה"),
     "הנחיה לפנייה מיידית אינה משנה דבר: מתי פונים ללקוח נקבע רק בכללי המעקב.", True),
    ("PROMPT_PROMISE", "warning",
     re.compile(r"(ההלוואה|הבקשה|האשראי)\s+(אושרה|אושר|מאושרת|מאושר|תאושר)|מובטחת|מובטח|מבטיחים|אני מבטיחה|אני מבטיח"
                r"|אישור\s+(ודאי|בטוח)|ריבית\s+(של|מובטחת|מיוחדת|נמוכה)"),
     "הבטחת אישור, ריבית או תנאים אסורה: הסוכנת אינה מחליטה על אשראי.", True),
    ("PROMPT_THREAT", "warning",
     re.compile(r"תבוטל|נבטל|יבוטל|תיסגר|ייסגר|נסגור|קנס|השלכות|הליכים משפטיים|תביעה"),
     "ניסוח מאיים אינו מתאים לפנייה ללקוח.", True),
    ("PROMPT_SENSITIVE_DATA", "warning",
     re.compile(r"מספר\s+(ה)?(תעודת\s+)?(ה)?זהות|ת\.ז|תעודת\s+הזהות\s+שלך|מספר\s+(ה)?(חשבון|כרטיס)|סיסמ|קוד\s+(ה)?אימות"
                r"|הקרא(י|ו)?\s+(לי\s+)?(את\s+)?(ה)?(מסמך|תלוש)|סכום\s+(ה)?(משכורת|שכר)|פרטי\s+(ה)?(תלוש|מסמך)"),
     "אין לבקש בשיחה מספרי זהות, סיסמאות או את תוכן המסמכים.", True),
    ("PROMPT_DISCLOSURE_DENIAL", "error",
     re.compile(r"אל\s+ת(גיד|גידי|ספר|ספרי|ציין|צייני)\s+ש(את|אתה|זו|זה|מדובר)|העמיד(י|ו)?\s+פנים|התחז(י|ה|ו)"),
     "אסור להסתיר שמדובר בסוכנת בינה מלאכותית.", False),
]


def _negated(text: str, start: int) -> bool:
    window = text[max(0, start - 30):start]
    window = _CLAUSE_END.split(window)[-1]
    return bool(_NEGATION.search(window))


def lint(text: str, *, path: str = "") -> list[dict]:
    """Findings for one text: {code, severity, message_he, path, span[start, end], match}."""
    out: list[dict] = []
    for code, severity, pattern, message, negatable in _RULES:
        for m in pattern.finditer(text or ""):
            if negatable and _negated(text, m.start()):
                continue
            out.append({"code": code, "severity": severity, "message_he": message, "path": path,
                        "span": [m.start(), m.end()], "match": m.group(0)})
    for m in VARIABLE.finditer(text or ""):
        if m.group(1) not in PROMPT_VARIABLES:
            out.append({"code": "PROMPT_UNKNOWN_VARIABLE", "severity": "error", "path": path, "span": [m.start(), m.end()],
                        "match": m.group(0),
                        "message_he": f"משתנה לא מוכר: {m.group(1)}. מותר: {', '.join(PROMPT_VARIABLES)}"})
    return sorted(out, key=lambda f: f["span"][0])


def lint_prompt(config: dict) -> list[dict]:
    opening = str(config.get("opening_locked") or "")
    out = []
    if not DISCLOSURE.search(opening):
        out.append({"code": "PROMPT_DISCLOSURE_MISSING", "severity": "error", "path": "opening_locked", "span": None,
                    "match": "", "message_he": "הפתיח חייב לומר ללקוח שמדברת סוכנת בינה מלאכותית."})
    return out + lint(str(config.get("instructions") or ""), path="instructions")


def lint_messages(config: dict) -> list[dict]:
    """The customer-facing texts of a loan policy: templates and customer_messages."""
    out = []
    for section in ("templates", "customer_messages"):
        for name, text in (config.get(section) or {}).items():
            out += lint(str(text), path=f"{section}.{name}")
    link = str((config.get("templates") or {}).get("link_message") or "")
    if link and "secure_upload_link" not in VARIABLE.findall(link):
        out.append({"code": "TEMPLATE_LINK_MISSING", "severity": "warning", "path": "templates.link_message", "span": None,
                    "match": "", "message_he": "הודעת הקישור אינה כוללת את {{secure_upload_link}}."})
    return out


def render(text: str, variables: Optional[dict[str, Any]] = None) -> str:
    """Replace known `{{name}}` variables; an unknown one is left as written so the preview shows it."""
    values = PREVIEW_VARIABLES if variables is None else variables

    def one(m: re.Match) -> str:
        v = values.get(m.group(1))
        if v is None:
            return m.group(0)
        return ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)
    return VARIABLE.sub(one, text or "")


def preview(kind: str, config: dict) -> dict:
    if kind == "talk_prompt":
        return {"opening": render(str(config.get("opening_locked") or "")),
                "instructions": render(str(config.get("instructions") or ""))}
    return {section: {name: render(str(text)) for name, text in (config.get(section) or {}).items()}
            for section in ("templates", "customer_messages")}
