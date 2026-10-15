"""Conversational questionnaire (V2, /customer/apply/v2): the same onboarding draft as V1, asked as a conversation.

One canonical state: every value — a quick reply or a value read from free text — is recorded through
`onboarding.answer`, so validation, conditional questions, corrections and the idempotent `onboarding.confirm` are
V1's. This layer only adds what a conversation needs, stored next to the answers (`onboarding_drafts.conversation`):
the transcript, the question being edited, and which preliminary indication was last shown.

Everything is deterministic: understanding is `onboarding_nlu` (keywords and patterns, no model), answers to the
customer's questions are composed from the published loan policy, and the financing indication is
`indication.compute` — a labelled DEMO illustration, never an eligibility result."""
from __future__ import annotations

import threading
from typing import Any

from .. import db
from ..config import settings
from ..policy import store
from ..review import deterministic as det
from ..review import rubrics
from ..util import now_iso
from . import indication, onboarding, onboarding_nlu as nlu
from .onboarding import BY_ID, OnboardingError

STAGES: list[tuple[str, str, list[str]]] = [
    ("intro", "היכרות", ["entity", "name", "national_id", "company_name", "signatory", "signatory_id"]),
    ("loan", "פרטי ההלוואה", ["purpose", "company_purpose", "amount", "business_amount", "payments"]),
    ("profile", "התאמה אישית", ["income", "registration", "net", "co_borrower", "co_name", "co_national_id",
                                "co_income", "co_registration", "co_net", "accounts"]),
    ("summary", "סיכום ואישור", []),
]
ORDER = [q for _, _, qs in STAGES for q in qs]
assert sorted(ORDER) == sorted(BY_ID), "every questionnaire question belongs to one V2 stage"
QUESTION_INDEX = {q[0]: i for i, q in enumerate(onboarding.QUESTIONS)}
MAX_MESSAGES = 240
MAX_TEXT = 500
_lock = threading.Lock()

INCOME_REPLIES = [{"label_he": "משכורת (שכיר/ה)", "value": ["salaried"]},
                  {"label_he": "עסק (עצמאי/ת)", "value": ["self_employed"]},
                  {"label_he": "גם משכורת וגם עסק", "value": ["salaried", "self_employed"]}]
ENTITY_REPLIES = [{"label_he": "הלוואה פרטית — בשבילי", "value": "individual"},
                  {"label_he": "מימון לחברה בע״מ", "value": "company"}]
FIELD_HE = {"entity": "סוג הבקשה", "name": "השם", "national_id": "מספר הזהות", "purpose": "מטרת ההלוואה",
            "amount": "הסכום", "payments": "מספר התשלומים", "income": "מקור ההכנסה", "registration": "סוג העוסק",
            "net": "ההכנסה החודשית", "co_borrower": "הלווה הנוסף", "co_name": "שם הלווה הנוסף",
            "co_national_id": "מספר הזהות של הלווה הנוסף", "co_income": "מקור ההכנסה של הלווה הנוסף",
            "co_registration": "סוג העוסק של הלווה הנוסף", "co_net": "ההכנסה של הלווה הנוסף",
            "accounts": "החשבונות", "company_name": "שם החברה", "signatory": "מורשה החתימה",
            "signatory_id": "מספר הזהות של מורשה החתימה", "company_purpose": "מטרת המימון",
            "business_amount": "סכום המימון"}
CHANGE_WORDS = [("סכום", ("amount", "business_amount")), ("תשלומים", ("payments",)), ("תקופה", ("payments",)),
                ("מקור", ("income",)), ("שכיר", ("income",)), ("עצמאי", ("income",)), ("עוסק", ("registration",)),
                ("מע\"מ", ("registration",)), ("הכנסה", ("net",)), ("משכורת", ("net",)), ("נטו", ("net",)),
                ("מטרה", ("purpose", "company_purpose")), ("מטרת", ("purpose", "company_purpose")),
                ("תעודת זהות", ("national_id",)), ("ת\"ז", ("national_id",)), ("שם", ("name",)),
                ("לווה", ("co_borrower",)), ("חשבון", ("accounts",))]


# ---------------------------------------------------------------- state
def _load(draft_id: str) -> tuple[dict, dict, dict]:
    row = onboarding._row(draft_id)
    a = onboarding._clean_answers(row["answers"])
    conv = db.jload(row.get("conversation"))
    if not conv:
        conv = {"messages": [], "focus": None, "shown": None, "explained": None, "asked": None, "seq": 0,
                "summary_for": None}
        _say(conv, "text", _opening(a))
        first = _pending(a, None)
        _ask(conv, a, first, "נתחיל: " if first == "entity" else "")
        _save(draft_id, conv)
    return row, a, conv


def _save(draft_id: str, conv: dict) -> None:
    conv["messages"] = conv["messages"][-MAX_MESSAGES:]
    with db.tx() as c:
        c.execute("UPDATE onboarding_drafts SET conversation=? WHERE draft_id=?", (db.jdump(conv), draft_id))


def _say(conv: dict, kind: str, text: str, role: str = "assistant", **extra) -> None:
    conv["seq"] += 1
    conv["messages"].append({"id": conv["seq"], "role": role, "kind": kind, "text_he": text, "at": now_iso(), **extra})


def _pending(a: dict, focus: str | None) -> str | None:
    applicable = {q[0] for q in onboarding._applicable(a)}
    if focus and focus in applicable:
        return focus
    return next((q for q in ORDER if q in applicable and q not in a), None)


def _ask(conv: dict, a: dict, qid: str | None, lead: str = "") -> None:
    if qid is None:
        return
    _say(conv, "question", lead + _prompt(qid, a), question_id=qid)
    conv["asked"] = qid


# ---------------------------------------------------------------- wording
def _first(a: dict, key: str = "name") -> str:
    return ((a.get(key) or {}).get("first") or "").strip()


def _ils(n: int) -> str:
    return f"{int(n):,} ₪"


def _and(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    last = items[-1]
    return f"{', '.join(items[:-1])} ו{'־' if not last[:1].isalpha() or last[:1].isascii() else ''}{last}"


def _purpose_he(key: str | None) -> str:
    pol, _ = store.policy()
    p = pol.product.purposes.get(key or "")
    return p.label_he if p else ""


def _income_he(sources: list[str] | None, reg: str | None = None) -> str:
    s = sources or []
    reg_he = {"vat_exempt": "עוסק פטור", "vat_registered": "עוסק מורשה"}.get(reg or "")
    biz = f"עסק ({reg_he})" if reg_he else "עסק"
    if s == ["salaried"]:
        return "משכורת"
    if s == ["self_employed"]:
        return biz
    if s:
        return f"משכורת + {biz}"
    return ""


def _opening(a: dict) -> str:
    return ("היי, אני העוזר הדיגיטלי של טפחות טאצ׳ ואלווה אותך בפתיחת בקשה להלוואה. זה לוקח כמה דקות, "
            "ואפשר לעצור ולחזור בכל שלב.\n"
            "אפשר לענות בלחיצה על אחת האפשרויות, או פשוט לכתוב לי במילים שלך — למשל: "
            "\"אני שכירה ורוצה 80 אלף לרכב\".")


def _prompt(qid: str, a: dict) -> str:
    first, co = _first(a), _first(a, "co_name") or "הלווה הנוסף"
    sources = a.get("income") or []
    purpose = a.get("purpose")
    prompts = {
        "entity": "הבקשה היא בשבילך, או עבור חברה בע״מ?",
        "name": "איך קוראים לך? (שם פרטי ושם משפחה)",
        "national_id": f"{first + ', ' if first else ''}מה מספר תעודת הזהות שלך? 9 ספרות — בהדגמה אפשר גם מזהה סינתטי, "
                       "למשל DEMO-ID-201.",
        "purpose": f"{first + ', ' if first else ''}למה מיועדת ההלוואה?",
        "amount": {"car": "איזה סכום צריך למימון הרכב?", "renovation": "איזה סכום צריך לשיפוץ?",
                   "celebration": "איזה סכום צריך לאירוע?"}.get(purpose or "", "איזה סכום תרצו לבקש?"),
        "payments": "על פני כמה תשלומים נוח לפרוס את ההחזר?",
        "income": "איך מגיעה ההכנסה שלך היום — ממשכורת, מעסק, או משניהם?",
        "registration": "העסק שלך רשום כעוסק פטור או כעוסק מורשה?",
        "net": ("כמה נכנס לך בחודש בערך, נטו — מהמשכורת ומהעסק יחד?" if len(sources) > 1 else
                "כמה נשאר לך מהעסק בחודש, בערך, נטו?" if sources == ["self_employed"] else
                "מה המשכורת החודשית שלך נטו, בערך?") + " (זו הצהרה בלבד — המסמכים יאמתו אותה בהמשך)",
        "co_borrower": "מישהו נוסף חותם איתך על ההלוואה — למשל בן או בת זוג?",
        "co_name": "איך קוראים ללווה הנוסף? (שם פרטי ושם משפחה)",
        "co_national_id": f"ומה מספר תעודת הזהות של {co}?",
        "co_income": f"איך מגיעה ההכנסה של {co} — ממשכורת, מעסק, או משניהם?",
        "co_registration": f"העסק של {co} רשום כעוסק פטור או כעוסק מורשה?",
        "co_net": f"וכמה נכנס ל{co} בחודש, בערך, נטו? (הצהרה בלבד)",
        "accounts": f"יש לך ול{co} חשבון עו״ש משותף, או שלכל אחד חשבון משלו?",
        "company_name": "מה שם החברה?",
        "signatory": "מי מורשה החתימה שמגיש את הבקשה? (שם פרטי ושם משפחה)",
        "signatory_id": "מה מספר תעודת הזהות של מורשה החתימה?",
        "company_purpose": f"למה {a.get('company_name') or 'החברה'} צריכה את המימון?",
        "business_amount": "איזה סכום מימון מבקשים?",
    }
    return prompts[qid]


def _replies(qid: str, a: dict) -> list[dict]:
    if qid in ("income", "co_income"):
        return INCOME_REPLIES
    if qid == "entity":
        return ENTITY_REPLIES
    q = BY_ID[qid]
    if q[1] in ("name", "text"):
        return []
    return [{"label_he": o["label_he"], "value": o["value"]} for o in onboarding._options(q)]


def _placeholder(qid: str | None) -> str:
    return {"name": "שם פרטי ושם משפחה", "co_name": "שם פרטי ושם משפחה", "signatory": "שם פרטי ושם משפחה",
            "national_id": "מספר תעודת זהות", "co_national_id": "מספר תעודת זהות",
            "signatory_id": "מספר תעודת זהות", "company_name": "שם החברה"}.get(qid or "", "אפשר לכתוב כאן במילים שלך…")


def _value_he(qid: str, v: Any, a: dict, short: bool = False) -> str:
    if qid in ("income", "co_income"):
        reg = a.get("registration" if qid == "income" else "co_registration")
        if short:
            return _income_he(v, reg)
        reg_he = {"vat_exempt": "עוסק פטור", "vat_registered": "עוסק מורשה"}.get(reg or "")
        biz = f"מעסק ({reg_he})" if reg_he else "מעסק"
        return ("הכנסה ממשכורת" if v == ["salaried"] else f"הכנסה {biz}" if v == ["self_employed"]
                else f"הכנסה ממשכורת ו{biz}")
    if qid in ("net", "co_net"):
        return f"כ־{_ils(v)} נטו בחודש"
    if qid in ("amount", "business_amount"):
        return _ils(v)
    if qid == "payments":
        return f"{v} תשלומים"
    if qid == "entity":
        return "הלוואה פרטית" if v == "individual" else "מימון לחברה"
    if qid == "co_borrower":
        return "עם לווה נוסף" if v == "yes" else "בלי לווה נוסף"
    return onboarding._answer_he(qid, v)


def _ack(changes: list[tuple[str, Any, Any]], a: dict) -> str:
    """A short, contextual acknowledgement of what this turn recorded."""
    new = [(q, v) for q, old, v in changes if old is None]
    upd = [(q, old, v) for q, old, v in changes if old is not None]
    parts: list[str] = []
    ids = {q for q, _ in new}
    if "name" in ids:
        parts.append(f"נעים להכיר, {_first(a)}.")
    if "co_name" in ids:
        parts.append(f"נעים להכיר גם את {_first(a, 'co_name')}.")
    listed = sorted([(q, v) for q, v in new if q not in ("name", "co_name", "entity", "national_id", "co_national_id",
                                                            "signatory_id", "registration", "co_registration")],
                    key=lambda x: ORDER.index(x[0]))
    if new and any(q == "purpose" and v == "car" for q, v in new) and len(listed) <= 2:
        extra = [_value_he(q, v, a) for q, v in listed if q != "purpose"]
        parts.append("הבנתי, נבדוק אפשרויות למימון הרכב" + (f" — {_and(extra)}." if extra else "."))
    elif len(listed) >= 2:
        labels = [(_purpose_he(v) if q == "purpose" else _value_he(q, v, a)) for q, v in listed]
        parts.append(f"הבנתי: {_and(labels)}.")
    elif len(listed) == 1:
        parts.append(_ack_one(*listed[0], a))
    if any(q in ("income", "co_income") and len(v) > 1 for q, v in new) and len(listed) >= 2:
        parts.append("יש לך הכנסה גם ממשכורת וגם מעסק, אז נתאים את המסמכים לשניהם.")
    income_changed = any(q.endswith("income") for q, _ in listed) or any(q.endswith("income") for q, _, _ in upd)
    if any(q in ("registration", "co_registration") for q, _ in new) and not income_changed:
        reg = next(v for q, v in new if q in ("registration", "co_registration"))
        parts.append("עוסק פטור — רשמתי." if reg == "vat_exempt" else "עוסק מורשה — רשמתי.")
    if any(q in ("national_id", "co_national_id", "signatory_id") for q, _ in new) and not parts:
        parts.append("תודה, רשמתי.")
    if "entity" in ids and not parts:
        parts.append("בשמחה, נפתח בקשה להלוואה פרטית." if a.get("entity") == "individual" else
                     "הבנתי — מימון לחברה. זה מסלול מוגבל בליווי בנקאי/ת, ואאסוף כאן רק את מה שצריך כדי להתחיל.")
    for q, old, v in upd:
        if q in ("income", "co_income"):
            parts.append(f"{_ack_one(q, v, a)} עדכנתי את מקור ההכנסה (קודם: {_value_he(q, old, a, short=True)}), "
                         "ואת רשימת המסמכים בהתאם.")
            continue
        parts.append(f"עדכנתי את {FIELD_HE[q]}: {_value_he(q, v, a, short=True)}, במקום {_value_he(q, old, a, short=True)}.")
    return " ".join(parts)


def _ack_one(q: str, v: Any, a: dict) -> str:
    co = _first(a, "co_name") or "הלווה הנוסף"
    if q in ("income", "co_income"):
        reg_q = "registration" if q == "income" else "co_registration"
        reg = {"vat_exempt": " — כעוסק פטור", "vat_registered": " — כעוסק מורשה"}.get(a.get(reg_q) or "", "")
        who = "יש לך" if q == "income" else f"ל{co} יש"
        more = " אשאל עוד שאלה קצרה כדי להתאים את המסמכים." if "self_employed" in v and reg_q not in a else ""
        if len(v) > 1:
            return f"הבנתי, {who} הכנסה גם ממשכורת וגם מעסק{reg}.{more}"
        return "הבנתי, הכנסה ממשכורת." if v == ["salaried"] else f"הבנתי, הכנסה מעסק{reg}.{more}"
    if q in ("purpose", "company_purpose"):
        return f"{_purpose_he(v)} — רשמתי."
    if q == "amount":
        return f"{_ils(v)}{' למימון הרכב' if a.get('purpose') == 'car' else ''} — רשמתי."
    if q == "business_amount":
        return f"{_ils(v)} — רשמתי."
    if q == "payments":
        return f"{v} תשלומים{f', כלומר {v // 12} שנים' if v % 12 == 0 else ''}."
    if q == "net":
        return f"תודה. רשמתי כ־{_ils(v)} נטו בחודש — כהצהרה, המסמכים יאמתו אותה בהמשך."
    if q == "co_net":
        return f"תודה, רשמתי כ־{_ils(v)} נטו בחודש ל{co}."
    if q == "co_borrower":
        return "בסדר, נוסיף לווה נוסף לבקשה." if v == "yes" else "בסדר, הבקשה רק על שמך."
    if q == "accounts":
        return "חשבון משותף — רשמתי." if v == "joint" else "חשבונות נפרדים — רשמתי."
    if q == "company_name":
        return f"{v} — רשמתי."
    return "תודה, רשמתי."


# ---------------------------------------------------------------- policy-grounded answers
def _rule(rid: str):
    pol, _ = store.policy()
    return next((r for r in pol.document_requirements if r.id == rid), None)


def _label(rid: str) -> str:
    r = _rule(rid)
    return r.label_he.replace("{months}", str(r.rules.months or 3)) if r else ""


def _payslip_months_he() -> tuple[int, str]:
    r = _rule("PAYSLIPS")
    count = (r.rules.months if r and r.rules.months else 3)
    payday = rubrics.for_case()["policy"]["payday_day_of_next_month"]
    from datetime import date
    months = det.requested_months(date.fromisoformat(settings.simulation_date), count, payday)
    names = [f"{det.HEBREW_MONTH_NAMES[int(m[5:])]} {m[:4]}" for m in months]
    return count, _and(names)


def _why(qid: str, a: dict) -> str:
    reg = [r for r in store.policy()[0].document_requirements if r.condition and r.condition.registration]
    exempt = [r.label_he for r in reg if "vat_exempt" in r.condition.registration]
    registered = [r.label_he for r in reg if "vat_registered" in r.condition.registration]
    pay, tax, ident, stmt, proof = (_rule(x) for x in ("PAYSLIPS", "TAX_ASSESSMENT", "ID_CARD", "BANK_STATEMENTS",
                                                       "PURPOSE_PROOF"))
    purpose = store.policy()[0].product.purposes.get(a.get("purpose") or "car")
    why = {
        "entity": "יש מסלול להלוואה פרטית ומסלול מוגבל לחברות בע״מ, ולכל אחד מהם רשימת מסמכים אחרת.",
        "name": "כדי לפנות אליך בשמך ולשייך כל מסמך ללווה הנכון.",
        "national_id": f"מספר הזהות משמש ל{ident.why_he}." if ident else "",
        "purpose": (f"לכל מטרה מבקשים אסמכתה אחרת — {proof.why_he}. למשל, ל{purpose.label_he}: {purpose.proof_he}."
                    if proof and purpose else ""),
        "amount": "הסכום הוא חלק מהבקשה עצמה, והוא גם מאפשר לי לתת לך אינדיקציה ראשונית להמחשה. "
                  "הוא לא משנה את רשימת המסמכים.",
        "payments": "מספר התשלומים קובע את גובה ההחזר החודשי, ולכן גם את האינדיקציה הראשונית שאוכל להציג.",
        "income": (f"מקור ההכנסה קובע אילו מסמכים יאמתו אותה: ממשכורת — {_label('PAYSLIPS')}; "
                   f"מעסק — {_label('TAX_ASSESSMENT')} ואישור על רישום העסק. מי שיש לו את שניהם מתבקש את שני הסוגים."
                   if pay and tax else ""),
        "registration": (f"סוג הרישום במע״מ קובע אילו מסמכים יבקשו על העסק: לעוסק פטור — {_and(exempt)}; "
                         f"לעוסק מורשה — {_and(registered)}. בשני המקרים מבקשים גם {_label('TAX_ASSESSMENT')}, "
                         "כדי לאמת את ההכנסה מהעסק."),
        "net": "ההכנסה שמצהירים עליה נשמרת כהצהרה בלבד, והבנקאי/ת משווה אותה למסמכים. "
               "היא גם מאפשרת לי לתת לך אינדיקציה ראשונית להמחשה.",
        "co_borrower": "לכל לווה נוסף נדרשים מסמכים משלו — תעודת זהות ומסמכי הכנסה — ולכן חשוב לדעת את זה כבר עכשיו.",
        "accounts": f"דפי העו״ש נבדקים לכל חשבון. {stmt.why_he}." if stmt else "",
        "company_name": "המסלול לחברות מטופל בליווי בנקאי/ת, והשם מופיע על כל מסמכי החברה.",
        "signatory": "רק מורשה חתימה יכול להגיש בקשה בשם החברה.",
        "signatory_id": f"מספר הזהות משמש ל{ident.why_he}." if ident else "",
        "company_purpose": "מטרת המימון היא חלק מהבקשה, והבנקאי/ת בודק/ת אותה.",
        "business_amount": "הסכום הוא חלק מהבקשה; במסלול לחברות אין אינדיקציה אוטומטית.",
    }
    for k in ("co_name", "co_national_id", "co_income", "co_registration", "co_net"):
        why[k] = why[k[3:] if k[3:] in why else "co_borrower"] if k != "co_name" else why["co_borrower"]
    return why.get(qid) or "השאלה הזו קובעת אילו מסמכים יידרשו לבקשה."


def _provisional_documents(a: dict) -> list[str] | None:
    """The checklist the published policy composes for what is known so far, or None while it still depends on
    an unanswered branch question (entity, income source or VAT registration)."""
    if a.get("entity") == "individual":
        need = ["income"] + (["registration"] if "self_employed" in (a.get("income") or []) else [])
        if a.get("co_borrower") == "yes":
            need += ["co_income"] + (["co_registration"] if "self_employed" in (a.get("co_income") or []) else [])
        if any(k not in a for k in need):
            return None
        fill = {"name": {"first": "הלקוח", "last": "הלקוח"}, "national_id": "DEMO-ID-000", "purpose": "other",
                "net": 0, "co_borrower": "no", "amount": 5000, "payments": 36,
                "co_name": {"first": "הלווה", "last": "הנוסף"}, "co_national_id": "DEMO-ID-001", "co_net": 0,
                "accounts": "joint"}
    elif a.get("entity") == "company":
        fill = {"company_name": a.get("company_name") or "החברה", "signatory": {"first": "מורשה", "last": "החתימה"},
                "signatory_id": "DEMO-ID-000", "company_purpose": "working_capital", "business_amount": 20000,
                "payments": 36}
    else:
        return None
    case = onboarding.build_case({**fill, **a}, "PREVIEW", "000000000", "PREVIEW")
    from . import requirements
    reqs, _ = requirements.preview(case)
    labels = [_label(r["requirement_id"]) + (" (לכל לווה)" if r["owner_type"] == "applicant" and a.get("co_borrower") == "yes"
                                             and r["requirement_id"] == "ID_CARD" else "") for r in reqs]
    return list(dict.fromkeys(labels))


def _indication_text(ind: dict, update: bool) -> str:
    within = (f"הסכום שביקשת ({_ils(ind['requested_amount_ils'])}) בתוך הטווח — החזר משוער של כ־"
              f"{_ils(ind['requested_monthly_ils'])} בחודש." if ind["within"] else
              f"הסכום שביקשת ({_ils(ind['requested_amount_ils'])}) גבוה מהאינדיקציה. אפשר להמשיך כך — "
              "הבנק יבדוק את הבקשה כפי שתוגש.")
    co = (" האינדיקציה מבוססת רק על ההכנסה שלך; כשאדע את ההכנסה של הלווה הנוסף, אעדכן אותה."
          if ind["co_borrower_pending"] else "")
    if update:
        return (f"עדכנתי את האינדיקציה הראשונית לפי השינוי: עכשיו מדובר במימון של עד כ־{_ils(ind['max_amount_ils'])} "
                f"ב־{ind['payments']} תשלומים. {within}{co}\nעדיין המחשה בלבד — לא הצעה ולא אישור מהבנק.")
    return ("אגב, יש לי כבר אינדיקציה ראשונית בשבילך. "
            f"לפי מה שסיפרת לי ובהתאם להנחות הדמו, ייתכן שאפשר לבחון מימון של עד כ־{_ils(ind['max_amount_ils'])} "
            f"ב־{ind['payments']} תשלומים. {within}{co}\n"
            "זו עדיין לא הצעה ולא אישור מהבנק — נצטרך להשלים את הפרטים והמסמכים כדי לדעת מה באמת אפשר להציע. נמשיך?")


def _explain(ind: dict, a: dict) -> str:
    if not ind["available"]:
        if ind["reason"] == "company":
            return "במסלול לחברות אין אינדיקציה אוטומטית — הבקשה נבדקת בליווי בנקאי/ת."
        if ind["reason"] == "no_income":
            return "בלי הכנסה חודשית מוצהרת אין לי בסיס לאינדיקציה, ולכן אני לא מציג מספר."
        return (f"עוד אין לי אינדיקציה — חסרים לי {_and(ind['missing_he'])}. "
                "כשיהיו לי, אחשב אותה לפי הנחות דמו גלויות ואסביר בדיוק איך.")
    parts = [f"{_ils(p['net_ils'])} שלך" if p["who"] == "primary" else
             f"{_ils(p['net_ils'])} של {_first(a, 'co_name') or 'הלווה הנוסף'}" for p in ind["net_parts"]]
    income = (f"{_ils(ind['declared_net_ils'])} ({' + '.join(parts)})" if len(parts) > 1 else _ils(ind["declared_net_ils"]))
    ratio = int(round(ind["ratio"] * 100))
    lines = [
        "כך הגעתי לסכום (הדגמה בלבד):",
        f"• ההכנסה החודשית נטו שהצהרת: {income} — הצהרה, עוד לא מאומתת.",
        f"• הנחת דמו: עד {ratio}% מההכנסה מופנים להחזר החודשי ← עד כ־{_ils(ind['max_monthly_ils'])} בחודש."
        + (f" ({ratio}% ולא {int(indication.DEMO_RATIO_SALARIED * 100)}%, כי חלק מההכנסה מעסק — הנחה שמרנית יותר.)"
           if ind["business_income"] else ""),
        f"• הנחת דמו: ריבית שנתית של {ind['annual_rate'] * 100:g}% ו־{ind['payments']} תשלומים ← החזר כזה מתאים "
        f"להלוואה של עד כ־{_ils(ind['max_amount_ils'])}"
        + (f" (הוגבל לתקרת הבקשה בדמו, {_ils(ind['cap_ils'])})." if ind["capped"] else ", מעוגל כלפי מטה."),
    ]
    if ind["co_borrower_pending"]:
        lines.append("• ההכנסה של הלווה הנוסף עוד לא נכללה, כי עוד לא סיפרת עליה.")
    lines.append("לא השתמשתי בנתוני אשראי, בחשבונות בנק או בהתחייבויות קיימות — אין לי גישה אליהם, והם לא נבדקו. "
                 "בדיקה אמיתית של הבנק תתבסס על נתונים מלאים ומאומתים.")
    return "\n".join(lines)


def _intent(q: str) -> str | None:
    t = q
    if any(p in t for p in ("איך הגעת", "איך חישבת", "איך חושב", "מה החישוב", "איך זה מחושב", "על סמך מה",
                            "מאיפה הסכום", "מאיפה המספר", "למה הסכום", "איך הגעתם", "מה ההנחות", "איך זה חושב")):
        return "explain_indication"
    if any(p in t for p in ("מאושר", "יאשרו", "תאשר", "אישרו", "זכאי", "זכאית", "כמה אפשר לקבל", "כמה אוכל לקבל",
                            "כמה אני יכול", "כמה אני יכולה", "כמה אפשר לקחת", "מה המקסימום", "מה הסיכוי")):
        return "approval"
    if "תלוש" in t and any(p in t for p in ("אין לי", "חסר", "לא קיבלתי", "אין תלוש", "מה קורה אם", "מה אם")):
        return "missing_payslip"
    if "תלוש" in t:
        return "why_payslips"
    if any(p in t for p in ("פטור", "מורשה", "מע\"מ", "מעמ", "רשום", "רישום")) and "חתימה" not in t:
        return "why_registration"
    if any(p in t for p in ("לשנות", "לתקן", "לעדכן", "לערוך", "טעיתי", "לשנות את")):
        return "change"
    if any(p in t for p in ("להוסיף", "עוד לווה", "לווה נוסף", "ערב", "בן זוג", "בת זוג")):
        return "add_coborrower"
    if any(p in t for p in ("אילו מסמכים", "איזה מסמכים", "מה צריך להביא", "מה צריך להעלות", "מסמכים")):
        return "documents"
    if any(p in t for p in ("מה חסר", "מה נשאר", "כמה נשאר", "כמה עוד", "כמה זמן", "כמה שאלות", "להתקדם")):
        return "whats_missing"
    if any(p in t for p in ("נציג", "בנקאי", "בנקאית", "בן אדם", "לדבר עם")):
        return "human"
    if any(p in t for p in ("פרטיות", "המידע שלי", "מאובטח", "הנתונים שלי", "מי רואה")):
        return "privacy"
    if any(p in t for p in ("למה", "בשביל מה", "מה זה משנה", "למה צריך", "מה זה", "מדוע", "למה זה חשוב")):
        return "why_pending"
    return None


def _change_target(q: str, a: dict) -> str | None:
    applicable = {x[0] for x in onboarding._applicable(a)}
    for word, qids in CHANGE_WORDS:
        if word in q:
            return next((x for x in qids if x in applicable), None)
    return None


def _answer_intent(intent: str, q: str, a: dict, conv: dict, pending: str | None) -> tuple[str, list[dict]]:
    """(reply, actions). Actions are quick replies that answer a question of the questionnaire."""
    ind = _indication(a)
    if intent == "explain_indication":
        conv["explained"] = ind.get("key")
        return _explain(ind, a), []
    if intent == "approval":
        base = "אני לא יכול לאשר הלוואה ולא לקבוע זכאות — את זה עושה הבנק, אחרי בדיקה של הפרטים והמסמכים."
        if ind["available"]:
            return base + (f" מה שיש לי כרגע הוא אינדיקציה ראשונית להמחשה בלבד: עד כ־{_ils(ind['max_amount_ils'])} "
                           f"ב־{ind['payments']} תשלומים, לפי הנחות הדמו."), []
        if ind["reason"] == "missing":
            return base + f" כשיהיו לי {_and(ind['missing_he'])}, אוכל לתת אינדיקציה ראשונית להמחשה.", []
        return base, []
    if intent == "missing_payslip":
        count, months = _payslip_months_he()
        return (f"המדיניות מבקשת {count} תלושים אחרונים — לפי תאריך ההדגמה: {months}. אם חסר תלוש, אפשר בכל זאת לפתוח "
                "את הבקשה ולהעלות את מה שיש. חודש שלא הועלה יסומן כחסר, והבנקאי/ת יוכלו לבקש אותו או לבקש הסבר. "
                "הסבר בכתב נשמר כמידע נוסף — הוא לא מחליף את התלוש, ואין לי אפשרות לאשר כאן חלופה."), []
    if intent == "why_payslips":
        r = _rule("PAYSLIPS")
        count, months = _payslip_months_he()
        return (f"תלושי השכר מאמתים את ההכנסה ממשכורת. מדיניות הדמו מבקשת {count} תלושים אחרונים — לפי תאריך "
                f"ההדגמה: {months}. {r.why_he if r else ''}."), []
    if intent == "why_registration":
        return _why("registration", a), []
    if intent == "change":
        target = _change_target(q, a)
        if target and target in a:
            conv["focus"] = target
            return f"בטח. כרגע רשום: {_value_he(target, a[target], a)}.", []
        if target:
            return "עוד לא הגענו לזה — אשאל על זה בהמשך.", []
        return ("מה תרצו לשנות? אפשר ללחוץ על \"שינוי\" ליד כל פרט בסיכום, או לכתוב לי — למשל "
                "\"לשנות את הסכום ל־90 אלף\"."), []
    if intent == "add_coborrower":
        if a.get("entity") == "company":
            return "בבקשה עבור חברה אין לווה נוסף — את הבקשה מגיש/ה מורשה החתימה.", []
        if a.get("co_borrower") == "yes":
            return (f"כבר הוספנו את {_first(a, 'co_name') or 'הלווה הנוסף'}. בבקשה הזו אפשר לצרף לווה נוסף אחד."), []
        act = [{"label_he": "להוסיף לווה נוסף", "question_id": "co_borrower", "value": "yes"}]
        if a.get("co_borrower") == "no":
            return "כרגע הבקשה רק על שמך, אבל אפשר לצרף לווה נוסף אחד. להוסיף?", act
        return ("כן — אפשר לצרף לווה נוסף אחד, ואז יידרשו גם המסמכים שלו. אשאל על זה בשלב ההתאמה האישית, "
                "או שאפשר להוסיף כבר עכשיו."), act
    if intent == "documents":
        docs = _provisional_documents(a)
        if docs:
            return (f"לפי מה שסיפרת עד עכשיו, מדיניות הדמו תבקש {len(docs)} מסמכים: {_and(docs)}. "
                    "את הרשימה הסופית אציג בסיכום, לפני שהבקשה נפתחת."), []
        return ("רשימת המסמכים תלויה בסוג הבקשה ובמקור ההכנסה — כשאדע אותם, אוכל להציג בדיוק מה יידרש. "
                "בכל מקרה מבקשים תעודת זהות לכל לווה."), []
    if intent == "whats_missing":
        applicable = {x[0] for x in onboarding._applicable(_assume(a))}
        left = [x for x in ORDER if x in applicable and x not in a]
        if not left:
            return "סיימנו את השאלות — נשאר רק לעבור על הסיכום ולאשר. אחרי זה נעבור יחד למסמכים.", []
        stages = [label for sid, label, qs in STAGES if any(x in qs for x in left)]
        return (f"נשארו עוד {len(left)} שאלות קצרות ({_and(stages)}), ואחריהן סיכום לאישור. "
                "אחרי שהבקשה תיפתח נעבור למסמכים."), []
    if intent == "human":
        return ("אני עוזר דיגיטלי, לא בנקאי. אחרי שהבקשה תיפתח היא תגיע לבנקאי/ת שמטפל/ת בה — וההחלטות על הבקשה "
                "מתקבלות שם, לא אצלי."), []
    if intent == "privacy":
        return ("זו סביבת הדגמה עם נתונים סינתטיים — הבקשה לא נשלחת לבנק. התשובות משמשות כדי לקבוע אילו מסמכים "
                "יידרשו."), []
    if intent == "why_pending" and pending:
        return _why(pending, a), []
    return ("על זה אין לי מידע מאומת, ואני לא רוצה לנחש. אני יכול לעזור עם הבקשה עצמה — למשל להסביר למה אני שואל "
            "משהו, אילו מסמכים יידרשו או איך חישבתי את האינדיקציה."), []


def _note_text(n: dict, pending: str | None) -> str | None:
    k = n["kind"]
    if k == "gross":
        return "כתבת ברוטו — כאן אני צריך את הסכום נטו, כלומר מה שנכנס לחשבון בפועל. כמה זה בערך?"
    if k == "range_low":
        return f"רשמתי {_ils(n['value'])} — הערך הנמוך בטווח שכתבת, כדי לא להגזים בהערכה."
    if k == "conflicting_numbers":
        return f"ראיתי כמה מספרים ל{FIELD_HE.get(n['field'], 'אותו פרט')} ({', '.join(f'{v:,}' for v in n['values'])}) — איזה מהם נכון?"
    if k == "unplaced_number":
        return f"לא בטוח למה התכוונת ב־{n['value']:,} — זה הסכום, ההכנסה, או משהו אחר?"
    if k == "ambiguous_purpose":
        return "הזכרת יותר ממטרה אחת — מה המטרה העיקרית של ההלוואה?"
    if k == "unsupported_income":
        return ("בשאלון הזה אפשר לציין הכנסה ממשכורת או מעסק בלבד. הכנסה מסוג אחר (למשל קצבה או שכירות) "
                "השאלון עוד לא יודע לקלוט.")
    if k == "partial_name":
        return "אשמח גם לשם המשפחה."
    if k == "no_income_left":
        return "אם אין הכנסה ממשכורת ולא מעסק — השאלון הזה עוד לא תומך בסוג ההכנסה הזה."
    return None


ERROR_LEAD = {"amount": "לא רשמתי את הסכום: ", "business_amount": "לא רשמתי את הסכום: ", "net": "לא רשמתי את ההכנסה: ",
              "co_net": "לא רשמתי את ההכנסה: ", "national_id": "", "co_national_id": "", "signatory_id": ""}


def _error_text(qid: str, msg: str) -> str:
    if qid == "payments":
        return "אפשר לבחור 36, 48, 60 או 84 תשלומים. מה מתאים לך?"
    if msg == "השאלה אינה רלוונטית לתשובות הקודמות":
        return f"לא רשמתי את {FIELD_HE.get(qid, 'הפרט')} — הוא לא מתאים לסוג הבקשה הנוכחי."
    return ERROR_LEAD.get(qid, "") + msg + "."


def _not_understood(pending: str | None) -> str:
    if pending is None:
        return "לא בטוח שהבנתי. אפשר לבקש לשנות פרט — למשל \"לשנות את הסכום\" — או לאשר את הסיכום למטה."
    kind = BY_ID[pending][1]
    hint = {"choice": "אפשר לבחור אחת מהאפשרויות למטה, או לכתוב במילים שלך.",
            "multi": "אפשר לבחור אחת מהאפשרויות למטה, או לכתוב למשל \"אני שכירה\".",
            "number": "אפשר לבחור סכום מהאפשרויות או לכתוב מספר, למשל \"80 אלף\".",
            "name": "אשמח לשם פרטי ושם משפחה, למשל: מיכל ברק.",
            "text": "אפשר לכתוב את התשובה כאן למטה."}[kind]
    return f"לא בטוח שהבנתי. {hint}"


# ---------------------------------------------------------------- indication and progress
def _indication(a: dict) -> dict:
    return indication.compute(a, onboarding.NUMBER_BOUNDS["amount"][1])


def _assume(a: dict) -> dict:
    """For display only: before the first answer the stages show the individual path, the common case."""
    return a if "entity" in a else {**a, "entity": "individual"}


def _stages(a: dict, pending: str | None, status: str) -> list[dict]:
    shown = _assume(a)
    applicable = {q[0] for q in onboarding._applicable(shown)}
    out = []
    for sid, label, qids in STAGES:
        qs = [q for q in qids if q in applicable]
        if sid != "summary" and not qs:
            continue
        answered = [q for q in qs if q in a]
        if sid == "summary":
            state = "done" if status == "confirmed" else "current" if pending is None else "upcoming"
        elif pending in qs:
            state = "current"
        else:
            state = "done" if len(answered) == len(qs) else "upcoming"
        out.append({"id": sid, "label_he": label, "state": state, "total": len(qs), "answered": len(answered)})
    return out


def _indication_turn(conv: dict, a: dict) -> None:
    ind = _indication(a)
    shown = conv.get("shown")
    if ind["available"]:
        if not shown or shown.get("key") != ind["key"]:
            snap = {k: ind[k] for k in ("key", "max_amount_ils", "requested_amount_ils", "within", "requested_monthly_ils",
                                        "payments", "declared_net_ils", "co_borrower_pending")}
            _say(conv, "insight", _indication_text(ind, update=bool(shown and shown.get("key"))), indication=snap)
            conv["shown"] = {"key": ind["key"]}
    elif shown and shown.get("key"):
        why = ("במסלול לחברות אין אינדיקציה אוטומטית." if ind["reason"] == "company" else
               f"אחזור אליה כשיהיו לי {_and(ind['missing_he'])}." if ind["reason"] == "missing" else
               "בלי הכנסה חודשית מוצהרת אין לי בסיס לאינדיקציה.")
        _say(conv, "withdrawn", f"האינדיקציה שהצגתי קודם כבר לא מתאימה לפרטים העדכניים, ולכן הסרתי אותה. {why}")
        conv["shown"] = {"key": None}


def _summary_lines(a: dict) -> list[dict]:
    if a.get("entity") == "company":
        rows = [("סוג הבקשה", "מימון לחברה בע״מ", "entity"), ("החברה", a["company_name"], "company_name"),
                ("מורשה החתימה", onboarding._answer_he("signatory", a["signatory"]), "signatory"),
                ("מטרה", _purpose_he(a["company_purpose"]), "company_purpose"),
                ("סכום", _ils(a["business_amount"]), "business_amount"), ("תשלומים", f"{a['payments']} תשלומים", "payments")]
    else:
        rows = [("שם", onboarding._answer_he("name", a["name"]), "name"), ("תעודת זהות", a["national_id"], "national_id"),
                ("מטרה", _purpose_he(a["purpose"]), "purpose"), ("סכום", _ils(a["amount"]), "amount"),
                ("תשלומים", f"{a['payments']} תשלומים", "payments"),
                ("הכנסה", _income_he(a["income"], a.get("registration")), "income"),
                ("הכנסה חודשית נטו (הצהרה)", f"כ־{_ils(a['net'])}", "net")]
        if a.get("co_borrower") == "yes":
            rows += [("לווה נוסף", f"{onboarding._answer_he('co_name', a['co_name'])} · "
                                   f"{_income_he(a['co_income'], a.get('co_registration'))} · כ־{_ils(a['co_net'])} נטו",
                      "co_borrower"),
                     ("חשבון עו״ש", "משותף" if a["accounts"] == "joint" else "נפרד לכל לווה", "accounts")]
        else:
            rows.append(("לווה נוסף", "אין — הבקשה רק על שמך", "co_borrower"))
    return [{"label_he": l, "value_he": v, "question_id": q} for l, v, q in rows]


# ---------------------------------------------------------------- API
def view(draft_id: str) -> dict[str, Any]:
    row, a, conv = _load(draft_id)
    base = onboarding.view(draft_id)
    focus = conv.get("focus")
    pending = _pending(a, focus) if row["status"] == "draft" else None
    ind = _indication(a)
    current_key = ind.get("key") if ind["available"] else None
    messages = [{**m, "stale": m["kind"] == "insight" and m["indication"]["key"] != current_key} for m in conv["messages"]]
    last_actions = next((m.get("actions") for m in reversed(messages) if m["role"] == "assistant"), None)
    suggestions: list[str] = []
    if ind["available"] and conv.get("explained") != ind["key"]:
        suggestions.append("איך הגעת לסכום הזה?")
    if pending:
        suggestions.append("למה צריך את זה?")
    if pending and len(a) >= 3:
        suggestions.append("מה חסר לי כדי להתקדם?")
    first = _first(a) or _first(a, "signatory")
    out: dict[str, Any] = {
        "draft_id": draft_id, "status": row["status"], "case_id": row["case_id"], "updated_at": row["updated_at"],
        "first_name_he": first or None, "messages": messages,
        "pending": {"question_id": pending, "kind": BY_ID[pending][1], "prompt_he": _prompt(pending, a),
                    "replies": _replies(pending, a), "placeholder_he": _placeholder(pending),
                    "editing": bool(focus and focus == pending), "current_he": _value_he(pending, a[pending], a)
                    if pending in a else None} if pending else None,
        "actions": last_actions or [],
        "stages": _stages(a, pending, row["status"]),
        "indication": ({k: ind[k] for k in ("max_amount_ils", "requested_amount_ils", "within", "requested_monthly_ils",
                                            "payments", "declared_net_ils", "co_borrower_pending")}
                       if ind["available"] else None),
        "suggestions": suggestions,
        "summary": None,
        "note_he": "בקשת הדגמה עם נתונים סינתטיים — אינה מגיעה לבנק. אינדיקציה, אם מוצגת, היא המחשה בלבד.",
    }
    if pending is None and base["summary"]:
        out["summary"] = {**base["summary"], "lines": _summary_lines(a),
                          "intro_he": f"{first + ', ' if first else ''}זה מה שהבנתי. אפשר לשנות כל פרט לפני שפותחים את הבקשה."}
    return out


def start() -> dict[str, Any]:
    d = onboarding.start()
    return view(d["draft_id"])


def turn(draft_id: str, text: str | None = None, question_id: str | None = None, value: Any = None,
         label_he: str | None = None, action: str | None = None) -> dict[str, Any]:
    """One customer turn: a quick reply (question_id + value), free text, or a UI action (edit / cancel_edit)."""
    with _lock:
        row, a, conv = _load(draft_id)
        if row["status"] != "draft":
            raise OnboardingError("הבקשה כבר נפתחה — אי אפשר לשנות את התשובות", 409)
        before_pending = _pending(a, conv.get("focus"))
        interrupted = False
        changes: list[tuple[str, Any, Any]] = []
        replies: list[str] = []
        actions: list[dict] = []

        def apply(values: dict[str, Any]) -> None:
            nonlocal a
            for qid in sorted(values, key=lambda k: QUESTION_INDEX[k]):
                old = a.get(qid)
                try:
                    d = onboarding.answer(draft_id, qid, values[qid])
                except OnboardingError as exc:
                    replies.append(_error_text(qid, exc.message_he))
                    continue
                a = onboarding._clean_answers(onboarding._row(draft_id)["answers"])
                if a.get(qid) != old:
                    changes.append((qid, old, a.get(qid)))
                if conv.get("focus") == qid:
                    conv["focus"] = None
                if d["status"] != "draft":
                    break

        if action in ("edit", "cancel_edit"):
            if action == "edit":
                if question_id not in BY_ID or question_id not in a:
                    raise OnboardingError("אי אפשר לערוך את הפרט הזה")
                conv["focus"] = question_id
                _say(conv, "text", f"שינוי {FIELD_HE[question_id]}", role="user")
                replies.append(f"בטח. כרגע רשום: {_value_he(question_id, a[question_id], a)}.")
            else:
                conv["focus"] = None
                _say(conv, "text", "ביטול השינוי", role="user")
                replies.append("בסדר, השארתי את מה שהיה.")
            interrupted = True
        elif question_id is not None:
            if question_id not in BY_ID:
                raise OnboardingError("שאלה לא מוכרת")
            _say(conv, "text", (label_he or "")[:80] or onboarding._answer_he(question_id, onboarding._validate(question_id, value)),
                 role="user")
            apply({question_id: value})
        else:
            message = " ".join(str(text or "").split())[:MAX_TEXT]
            if not message:
                raise OnboardingError("ההודעה ריקה")
            _say(conv, "text", message, role="user")
            pending = before_pending
            u = nlu.understand(message, a, pending)
            intents = [(q, _intent(q)) for q in u["questions"]]
            if any(i == "change" for _, i in intents):
                u2 = nlu.understand(message, a, _change_target(message, a) or pending, as_statement=True)
                u["values"].update({k: v for k, v in u2["values"].items() if k not in u["values"]})
            apply(u["values"])
            for n in u["notes"]:
                t = _note_text(n, pending)
                if t:
                    replies.append(t)
                    interrupted = True
            for q, intent in intents:
                if intent == "change" and changes:
                    continue
                if intent is None and changes:
                    continue
                reply, acts = _answer_intent(intent or "unsupported", q, a, conv, _pending(a, conv.get("focus")))
                replies.append(reply)
                actions += acts
                interrupted = True
            if not changes and not replies:
                greet = nlu.normalize(message).strip("!.,? ")
                if greet in ("שלום", "היי", "הי", "בוקר טוב", "ערב טוב", "אהלן"):
                    replies.append("שלום! שמח לעזור.")
                elif greet.startswith("תודה"):
                    replies.append("בשמחה.")
                elif greet in ("נמשיך", "כן נמשיך", "בוא נמשיך", "בואו נמשיך", "המשך", "יאללה", "אוקיי", "בסדר", "כן"):
                    conv["asked"] = None
                else:
                    replies.append(_not_understood(pending))
                interrupted = interrupted or bool(replies)

        ack = _ack(changes, a) if changes else ""
        if ack:
            _say(conv, "text", ack)
        for r in replies:
            _say(conv, "text", r, **({"actions": actions} if actions and r == replies[-1] else {}))
        if changes:
            _indication_turn(conv, a)
        after = _pending(a, conv.get("focus"))
        if after is not None:
            if after != conv.get("asked") or changes or interrupted:
                lead = "נמשיך מהנקודה שבה היינו: " if (interrupted and not changes and after == before_pending
                                                         and not conv.get("focus")) else ""
                _ask(conv, a, after, lead)
        else:
            conv["asked"] = None
            sig = db.jdump(a)
            if conv.get("summary_for") != sig:
                again = conv.get("summary_for") is not None
                _say(conv, "summary", ("עדכנתי. הסיכום למטה מעודכן — אפשר לעבור עליו שוב ולאשר." if again else
                                       "סיימנו את השאלות. ריכזתי למטה את כל מה שסיפרת לי ואת המסמכים שיידרשו — "
                                       "אפשר לשנות כל פרט לפני האישור. פתיחת הבקשה אינה אישור הלוואה."))
                conv["summary_for"] = sig
        _save(draft_id, conv)
    return view(draft_id)
