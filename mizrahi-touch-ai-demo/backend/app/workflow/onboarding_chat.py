"""Conversational questionnaire (V2, /customer/apply/v2): the same onboarding draft as V1, asked as a conversation.

One canonical state. Every value — a quick reply, a fact read from free text by Gemini or by the deterministic parser —
is recorded through `onboarding.answer`, so V1's validation, conditional questions, corrections and the idempotent
`onboarding.confirm` own the workflow. Next to the answers the draft stores what a conversation needs
(`onboarding_drafts.conversation`): the transcript, the loan category, facts held until they apply, the question being
edited and the last indication shown.

A turn is understand → apply → compose, and always ends in exactly ONE assistant message:
  understand  `onboarding_llm.interpret` (when switched on) or `onboarding_nlu.understand` — proposals only;
  apply       loan category first, then each proposal through `onboarding.answer`; a value that contradicts an
              earlier answer without a correction is not applied but asked about; one that does not apply yet is held;
  compose     `onboarding_llm.reply` from the validated outcome, or the deterministic composer.
The financing indication is `indication.compute` — a labelled DEMO illustration; the model only words it.

Loan category vs legal entity: "הלוואה פרטית" is the individual path (any income mix). "הלוואה עסקית" asks how the
business is registered: עוסק פטור / עוסק מורשה run on the individual path as the business owner, with business income
and the VAT registration recorded; חברה בע״מ is the limited, banker-assisted company path. The category is stored on
the case at confirmation (`annotate_case`)."""
from __future__ import annotations

import logging
import re
import threading
from typing import Any, Callable, Optional

from .. import db
from ..config import settings
from ..policy import store
from ..review import deterministic as det
from ..review import rubrics
from ..util import now_iso
from .. import i18n
from ..i18n import chat_en as EN
from . import indication, loan_sim, onboarding, onboarding_llm as llm, onboarding_nlu as nlu, onboarding_nlu_en as nlu_en
from .onboarding import BY_ID, OnboardingError

log = logging.getLogger("onboarding_chat")
# what a message gains when the customer app sent its language; removed again from a view without it
LANG_KEYS = ("text_en", "lang")

LOAN_FIELDS = ("loan_type", "business_form")
STAGES: list[tuple[str, str, list[str]]] = [
    ("intro", "היכרות", ["loan_type", "business_form", "entity", "name", "national_id", "company_name", "signatory",
                         "signatory_id"]),
    ("loan", "פרטי ההלוואה", ["purpose", "company_purpose", "amount", "business_amount", "payments"]),
    ("profile", "התאמה אישית", ["income", "registration", "net", "co_borrower", "co_name", "co_national_id",
                                "co_income", "co_registration", "co_net", "accounts"]),
    ("summary", "סיכום ואישור", []),
]
ORDER = [q for _, _, qs in STAGES for q in qs]
assert sorted(q for q in ORDER if q not in LOAN_FIELDS) == sorted(BY_ID), "every question belongs to one V2 stage"
QUESTION_INDEX = {q[0]: i for i, q in enumerate(onboarding.QUESTIONS)}
MAX_MESSAGES = 240
MAX_TEXT = 500
_lock = threading.Lock()

LOAN_TYPE_REPLIES = [{"label_he": "הלוואה פרטית", "value": "personal"}, {"label_he": "הלוואה עסקית", "value": "business"}]
FORM_REPLIES = [{"label_he": "עוסק פטור", "value": "vat_exempt"}, {"label_he": "עוסק מורשה", "value": "vat_registered"},
                {"label_he": "חברה בע״מ", "value": "company"}]
INCOME_REPLIES = [{"label_he": "משכורת (שכיר/ה)", "value": ["salaried"]},
                  {"label_he": "עסק (עצמאי/ת)", "value": ["self_employed"]},
                  {"label_he": "גם משכורת וגם עסק", "value": ["salaried", "self_employed"]}]
FORM_HE = {"vat_exempt": "עוסק פטור", "vat_registered": "עוסק מורשה", "company": "חברה בע״מ"}
FIELD_HE = {"loan_type": "סוג ההלוואה", "business_form": "סוג העסק", "entity": "סוג הבקשה", "name": "השם",
            "national_id": "מספר הזהות", "purpose": "מטרת ההלוואה", "amount": "הסכום", "payments": "מספר התשלומים",
            "income": "מקור ההכנסה", "registration": "סוג העוסק", "net": "ההכנסה החודשית",
            "co_borrower": "הלווה הנוסף", "co_name": "שם הלווה הנוסף", "co_national_id": "מספר הזהות של הלווה הנוסף",
            "co_income": "מקור ההכנסה של הלווה הנוסף", "co_registration": "סוג העוסק של הלווה הנוסף",
            "co_net": "ההכנסה של הלווה הנוסף", "accounts": "החשבונות", "company_name": "שם החברה",
            "signatory": "מורשה החתימה", "signatory_id": "מספר הזהות של מורשה החתימה",
            "company_purpose": "מטרת המימון", "business_amount": "סכום המימון"}
CHANGE_WORDS = [("סכום", ("amount", "business_amount")), ("תשלומים", ("payments",)), ("תקופה", ("payments",)),
                ("סוג ההלוואה", ("loan_type",)), ("פרטית", ("loan_type",)), ("עסקית", ("loan_type",)),
                ("מקור", ("income",)), ("שכיר", ("income",)), ("עצמאי", ("income",)), ("עוסק", ("registration",)),
                ("מע\"מ", ("registration",)), ("הכנסה", ("net",)), ("משכורת", ("net",)), ("נטו", ("net",)),
                ("מטרה", ("purpose", "company_purpose")), ("מטרת", ("purpose", "company_purpose")),
                ("תעודת זהות", ("national_id",)), ("ת\"ז", ("national_id",)), ("שם", ("name",)),
                ("לווה", ("co_borrower",)), ("חשבון", ("accounts",))]
BANK_WORDS = ("הלוואה", "בנק", "מסמך", "ריבית", "תשלום", "החזר", "הכנסה", "משכורת", "תלוש", "עסק", "לווה", "סכום",
              "אישור", "מימון", "בקשה", "חשבון", "שומה", "עוסק", "מע\"מ", "נטו", "ברוטו", "אינדיקציה", "לחשב", "חישוב")


# ---------------------------------------------------------------- state
def _new_conv() -> dict:
    return {"messages": [], "focus": None, "shown": None, "explained": None, "asked": None, "seq": 0,
            "summary_for": None, "loan": {}, "held": {}, "turns": [], "llm_calls": 0, "sim": {}}


def _load(draft_id: str, lang: Optional[str] = None) -> tuple[dict, dict, dict]:
    row = onboarding._row(draft_id)
    a = onboarding._clean_answers(row["answers"])
    conv = db.jload(row.get("conversation"))
    if not conv:
        conv = _new_conv()
        first = _pending(conv, a)
        _say(conv, f"{OPENING}\nנתחיל, {_prompt(first, conv, a)}" if first == "loan_type" else _prompt(first, conv, a),
             question_id=first, **_said(lang, lambda: EN.opening(conv, a, first)))
        conv["asked"] = first
        _save(draft_id, conv)
    for k, v in _new_conv().items():
        conv.setdefault(k, v)
    return row, a, conv


def _save(draft_id: str, conv: dict) -> None:
    conv["messages"] = conv["messages"][-MAX_MESSAGES:]
    conv["turns"] = conv["turns"][-30:]
    with db.tx() as c:
        c.execute("UPDATE onboarding_drafts SET conversation=? WHERE draft_id=?", (db.jdump(conv), draft_id))


def _say(conv: dict, text: str, role: str = "assistant", kind: str = "text", **extra) -> None:
    conv["seq"] += 1
    conv["messages"].append({"id": conv["seq"], "role": role, "kind": kind, "text_he": text, "at": now_iso(),
                             **{k: v for k, v in extra.items() if v not in (None, [], "")}})


def _said(lang: Optional[str], make: Optional[Callable[[], str]] = None) -> dict:
    """What a message records of the language when the customer app sent it: the session's language and, where the
    message has an English source (the assistant's reply, a quick reply's label), its English. Without the header,
    nothing — the message is exactly what it was before English existed."""
    if not lang:
        return {}
    out: dict[str, Any] = {"lang": lang}
    if make is not None:
        try:
            out["text_en"] = make()
        except Exception:                          # English must never cost the customer the Hebrew turn
            log.exception("English wording failed; the message keeps its Hebrew only")
    return out


def _english(t: dict, key: str, make: Callable[[], str]) -> None:
    """The English twin of one Hebrew sentence of this turn (i18n/chat_en), recorded only when the customer app sent its
    language. A failure drops this turn's English, never its Hebrew."""
    rec = t.get("_en")
    if rec is None:
        return
    try:
        text = make()
    except Exception:
        log.exception("English wording failed; the turn keeps its Hebrew only")
        t["_en"] = None
        return
    if isinstance(rec[key], list):
        rec[key].append(text)
    else:
        rec[key] = text


def _en_text(make: Callable[[], str]) -> str:
    try:
        return make()
    except Exception:
        log.exception("English wording failed")
        return ""


def _parser_text(text: Any, pending: Optional[str], lang: Optional[str]) -> str:
    """The copy of a typed message the deterministic parser reads: the message itself, or for an English session its
    English rewritten into the parser's Hebrew cue words (onboarding_nlu_en). The message is stored as typed."""
    clean = " ".join(str(text).split())[:MAX_TEXT]
    return nlu_en.to_parser(clean, pending) if lang == "en" else clean


def _loan(conv: dict, a: dict) -> dict:
    """The loan category; drafts started before V2 had one are read from their entity."""
    loan = dict(conv.get("loan") or {})
    if not loan.get("type") and a.get("entity"):
        loan = {"type": "business", "form": "company"} if a["entity"] == "company" else {"type": "personal", "form": None}
    return loan


def _v2(conv: dict, a: dict) -> dict:
    loan = _loan(conv, a)
    out = dict(a)
    if loan.get("type"):
        out["loan_type"] = loan["type"]
    if loan.get("form"):
        out["business_form"] = loan["form"]
    return out


def _applicable(conv: dict, a: dict) -> list[str]:
    loan = _loan(conv, a)
    base = {q[0] for q in onboarding._applicable(a)} - {"entity"}
    out = ["loan_type"] + (["business_form"] if loan.get("type") == "business" else [])
    return out + [q for q in ORDER if q in base]


def _pending(conv: dict, a: dict) -> Optional[str]:
    v = _v2(conv, a)
    applicable = _applicable(conv, a)
    focus = conv.get("focus")
    if focus and focus in applicable:
        return focus
    return next((q for q in applicable if q not in v), None)


# ---------------------------------------------------------------- wording
OPENING = ("היי, אני העוזר הדיגיטלי של מזרחי־טפחות. אני כאן כדי לעזור לך להכין בקשת הלוואה. "
           "אפשר לבחור תשובה או פשוט לכתוב לי במילים שלך.")


def _first(a: dict, key: str = "name") -> str:
    return ((a.get(key) or {}).get("first") or "").strip()


def _ils(n: int) -> str:
    return f"{int(n):,} ₪"


def _and(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    last = items[-1]
    return f"{', '.join(items[:-1])} ו{'־' if not last[:1].isalpha() or last[:1].isascii() else ''}{last}"


def _purpose_he(key: Optional[str]) -> str:
    pol, _ = store.policy()
    p = pol.product.purposes.get(key or "")
    return p.label_he if p else ""


def _income_he(sources: Optional[list[str]], reg: Optional[str] = None) -> str:
    s = sources or []
    biz = f"עסק ({FORM_HE[reg]})" if reg in ("vat_exempt", "vat_registered") else "עסק"
    if s == ["salaried"]:
        return "משכורת"
    if s == ["self_employed"]:
        return biz
    return f"משכורת + {biz}" if s else ""


def _sole(conv: dict, a: dict) -> bool:
    loan = _loan(conv, a)
    return loan.get("type") == "business" and loan.get("form") in ("vat_exempt", "vat_registered")


def _sim_question(qid: Optional[str], conv: dict, a: dict) -> bool:
    """Amount and term are asked together, as the loan simulator card, once the purpose is known."""
    return qid in loan_sim.SIM_FIELDS and loan_sim.applies(conv, a)


def _prompt(qid: str, conv: dict, a: dict) -> str:
    if _sim_question(qid, conv, a):
        return loan_sim.intro(conv, a) if not loan_sim._sim(conv)["shown"] else loan_sim.reprompt()
    first, co = _first(a), _first(a, "co_name") or "הלווה הנוסף"
    sources = a.get("income") or []
    purpose = a.get("purpose")
    prompts = {
        "loan_type": "איזו הלוואה מעניינת אותך?",
        "business_form": "איך העסק רשום, עוסק פטור, עוסק מורשה או חברה בע״מ?",
        "name": "איך קוראים לך? (שם פרטי ושם משפחה)",
        "national_id": "מה מספר תעודת הזהות שלך?",
        "purpose": "למה העסק צריך את המימון?" if _sole(conv, a) else f"{first + ', ' if first else ''}למה מיועדת ההלוואה?",
        "amount": {"car": "איזה סכום צריך למימון הרכב?", "renovation": "איזה סכום צריך לשיפוץ?",
                   "celebration": "איזה סכום צריך לאירוע?"}.get(purpose or "", "איזה סכום תרצו לבקש?"),
        "payments": "על פני כמה תשלומים נוח לפרוס את ההחזר?",
        "income": "איך מגיעה ההכנסה שלך היום, ממשכורת, מעסק או משניהם?",
        "registration": "העסק שלך רשום כעוסק פטור או כעוסק מורשה?",
        "net": ("כמה נכנס לך בחודש בערך, נטו, מהמשכורת ומהעסק יחד?" if len(sources) > 1 else
                "כמה נשאר לך מהעסק בחודש, בערך, נטו?" if sources == ["self_employed"] else
                "מה המשכורת החודשית שלך נטו, בערך?") + " (הצהרה בלבד, המסמכים יאמתו אותה בהמשך)",
        "co_borrower": "מישהו נוסף חותם איתך על ההלוואה, למשל בן או בת זוג?",
        "co_name": "איך קוראים ללווה הנוסף? (שם פרטי ושם משפחה)",
        "co_national_id": f"ומה מספר תעודת הזהות של {co}?",
        "co_income": f"איך מגיעה ההכנסה של {co}, ממשכורת, מעסק או משניהם?",
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


SHORT = {"loan_type": "מדובר בהלוואה פרטית או עסקית?", "name": "איך קוראים לך?",
         "national_id": "מה מספר תעודת הזהות שלך?", "amount": "איזה סכום צריך?", "payments": "בכמה תשלומים?",
         "income": "איך מגיעה ההכנסה שלך, ממשכורת, מעסק או משניהם?", "net": "כמה נכנס לך נטו בחודש, בערך?",
         "co_borrower": "יש לווה נוסף, או שהבקשה רק על שמך?"}


def _short(qid: str, conv: dict, a: dict) -> str:
    if _sim_question(qid, conv, a):
        return loan_sim.reprompt()
    return SHORT.get(qid) or _prompt(qid, conv, a).split(" (")[0]


def _replies(qid: str, conv: dict, a: dict) -> list[dict]:
    if qid == "loan_type":
        return LOAN_TYPE_REPLIES
    if qid == "business_form":
        return FORM_REPLIES
    if qid in ("income", "co_income"):
        return INCOME_REPLIES
    q = BY_ID[qid]
    if q[1] in ("name", "text"):
        return []
    opts = [{"label_he": o["label_he"], "value": o["value"]} for o in onboarding._options(q)]
    if qid == "purpose" and _sole(conv, a):
        opts = [o for o in opts if o["value"] != "celebration"]
    return opts


def _placeholder(qid: Optional[str]) -> str:
    return {"name": "שם פרטי ושם משפחה", "co_name": "שם פרטי ושם משפחה", "signatory": "שם פרטי ושם משפחה",
            "national_id": "מספר תעודת זהות", "co_national_id": "מספר תעודת זהות",
            "signatory_id": "מספר תעודת זהות", "company_name": "שם החברה"}.get(qid or "", "אפשר לכתוב כאן במילים שלך…")


def _value_he(qid: str, v: Any, a: dict, short: bool = False) -> str:
    if qid == "loan_type":
        return "הלוואה פרטית" if v == "personal" else "הלוואה עסקית"
    if qid == "business_form":
        return FORM_HE.get(v, "")
    if qid in ("income", "co_income"):
        reg = a.get("registration" if qid == "income" else "co_registration")
        if short:
            return _income_he(v, reg)
        biz = f"מעסק ({FORM_HE[reg]})" if reg in ("vat_exempt", "vat_registered") else "מעסק"
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
    if qid in ("purpose", "company_purpose"):
        return _purpose_he(v)
    return onboarding._answer_he(qid, v)


def _ack(changes: list[tuple[str, Any, Any]], a: dict, conv: dict, skip_new: frozenset = frozenset()) -> str:
    """A short, contextual acknowledgement of what this turn recorded (the deterministic composer). `skip_new`: new
    facts the next line already speaks about (the simulator's introduction names the purpose)."""
    new = [(q, v) for q, old, v in changes if old is None and v is not None and q not in skip_new]
    upd = [(q, old, v) for q, old, v in changes if old is not None and v is not None]
    parts: list[str] = []
    ids = {q for q, _ in new}
    loan = _loan(conv, a)
    if "loan_type" in ids or "business_form" in ids:
        if loan.get("type") == "personal":
            parts.append("הלוואה פרטית, בשמחה.")
        elif loan.get("form") == "company":
            parts.append("הלוואה עסקית לחברה בע״מ. זה מסלול מוגבל בליווי בנקאי/ת, ואאסוף כאן רק את מה שצריך כדי להתחיל.")
        elif loan.get("form"):
            parts.append(f"הלוואה עסקית כ{FORM_HE[loan['form']]}, הבקשה תיפתח על שמך כבעל/ת העסק, עם מסמכי העסק שלך.")
        else:
            parts.append("הלוואה עסקית, הבנתי.")
    if "name" in ids:
        parts.append(f"נעים להכיר, {_first(a)}.")
    if "co_name" in ids:
        parts.append(f"נעים להכיר גם את {_first(a, 'co_name')}.")
    skip = {"name", "co_name", "entity", "national_id", "co_national_id", "signatory_id", "registration",
            "co_registration", "loan_type", "business_form"}
    if _sole(conv, a):
        skip |= {"income"}
    listed = sorted([(q, v) for q, v in new if q not in skip], key=lambda x: ORDER.index(x[0]))
    if any(q == "purpose" and v == "car" for q, v in listed) and len(listed) <= 2:
        extra = [_value_he(q, v, a) for q, v in listed if q != "purpose"]
        parts.append("הבנתי, נבדוק יחד מימון לרכב" + (f", {_and(extra)}." if extra else "."))
    elif len(listed) >= 2:
        parts.append(_ack_many(dict(listed), a))
    elif len(listed) == 1:
        parts.append(_ack_one(*listed[0], a))
    income_changed = any(q.endswith("income") for q, _ in listed) or any(q.endswith("income") for q, _, _ in upd)
    if any(q in ("registration", "co_registration") for q, _ in new) and not income_changed and "business_form" not in ids:
        reg = next(v for q, v in new if q in ("registration", "co_registration"))
        parts.append(f"{FORM_HE[reg]}, רשמתי.")
    if any(q in ("national_id", "co_national_id", "signatory_id") for q, _ in new) and not parts:
        parts.append("תודה, רשמתי.")
    for q, old, v in upd:
        if q in ("income", "co_income"):
            reg_q = "registration" if q == "income" else "co_registration"
            more = " אשאל עוד שאלה קצרה כדי להתאים את המסמכים." if "self_employed" in v and reg_q not in a else ""
            if len(v) > 1:
                parts.append(_ack_one(q, v, a))
            else:
                parts.append(f"עדכנתי: {_value_he(q, v, a)} בלבד, במקום {_value_he(q, old, a, short=True)}.{more}")
        elif q not in ("entity", "registration") or not income_changed:
            parts.append(f"עדכנתי את {FIELD_HE[q]}: {_value_he(q, v, a, short=True)} במקום {_value_he(q, old, a, short=True)}.")
    return " ".join(parts)


def _ack_many(f: dict, a: dict) -> str:
    """Several facts from one message as one sentence: the loan, then the income — not a list of fields."""
    to = {"car": " לרכב", "renovation": " לשיפוץ", "celebration": " לאירוע"}.get(f.get("purpose") or "", "")
    loan = (f"מימון של {_ils(f['amount'])}{to}" if "amount" in f else
            f"מימון{to}" if to else _purpose_he(f["purpose"]) if "purpose" in f else "")
    if "payments" in f:
        loan = (loan + " " if loan else "") + f"ב־{f['payments']} תשלומים"
    income = ""
    sources = f.get("income")
    if sources:
        income = ("הכנסה ממשכורת" if sources == ["salaried"] else "הכנסה מעסק" if sources == ["self_employed"]
                  else "שתי הכנסות, ממשכורת ומהעסק")
    if "net" in f:
        income = (income + " של" if income and len(sources or []) < 2 else income + ", יחד" if income else "הכנסה של") \
            + f" כ־{_ils(f['net'])} נטו בחודש"
    rest = [_value_he(q, v, a) for q, v in f.items() if q not in ("purpose", "amount", "payments", "income", "net")]
    bits = [b for b in [loan, income] + rest if b]
    out = f"הבנתי, {_and(bits)}."
    if sources and len(sources) > 1:
        out += " אקח את שתי ההכנסות בחשבון כשנבנה את הבקשה."
    return out


def _ack_one(q: str, v: Any, a: dict) -> str:
    co = _first(a, "co_name") or "הלווה הנוסף"
    if q in ("income", "co_income"):
        reg_q = "registration" if q == "income" else "co_registration"
        reg = {"vat_exempt": ", כעוסק פטור", "vat_registered": ", כעוסק מורשה"}.get(a.get(reg_q) or "", "")
        who = "יש לך" if q == "income" else f"ל{co} יש"
        more = " אשאל עוד שאלה קצרה כדי להתאים את המסמכים." if "self_employed" in v and reg_q not in a else ""
        if len(v) > 1:
            return f"הבנתי, {who} שתי הכנסות, ממשכורת ומהעסק{reg}. אקח את שתיהן בחשבון.{more}"
        return "הבנתי, הכנסה ממשכורת." if v == ["salaried"] else f"הבנתי, הכנסה מעסק{reg}.{more}"
    if q in ("purpose", "company_purpose"):
        return f"{_purpose_he(v)}, רשמתי."
    if q == "amount":
        return f"{_ils(v)}{' למימון הרכב' if a.get('purpose') == 'car' else ''}, רשמתי."
    if q == "business_amount":
        return f"{_ils(v)}, רשמתי."
    if q == "payments":
        return f"{v} תשלומים{f', כלומר {v // 12} שנים' if v % 12 == 0 else ''}."
    if q == "net":
        return f"תודה, רשמתי כ־{_ils(v)} נטו בחודש."
    if q == "co_net":
        return f"תודה, רשמתי כ־{_ils(v)} נטו בחודש ל{co}."
    if q == "co_borrower":
        return "בסדר, נוסיף לווה נוסף לבקשה." if v == "yes" else "בסדר, הבקשה רק על שמך."
    if q == "accounts":
        return "חשבון משותף, רשמתי." if v == "joint" else "חשבונות נפרדים, רשמתי."
    if q == "company_name":
        return f"{v}, רשמתי."
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
    return count, _and([f"{det.HEBREW_MONTH_NAMES[int(m[5:])]} {m[:4]}" for m in months])


def _why(qid: str, conv: dict, a: dict) -> str:
    reg = [r for r in store.policy()[0].document_requirements if r.condition and r.condition.registration]
    exempt = [r.label_he for r in reg if "vat_exempt" in r.condition.registration]
    registered = [r.label_he for r in reg if "vat_registered" in r.condition.registration]
    pay, tax, ident, stmt, proof = (_rule(x) for x in ("PAYSLIPS", "TAX_ASSESSMENT", "ID_CARD", "BANK_STATEMENTS",
                                                       "PURPOSE_PROOF"))
    purpose = store.policy()[0].product.purposes.get(a.get("purpose") or "car")
    why = {
        "loan_type": "כי להלוואה פרטית ולהלוואה עסקית יש מסלול אחר ומסמכים אחרים.",
        "business_form": ("כי לכל סוג רישום יש מסמכים אחרים: לעוסק פטור או מורשה הבקשה נפתחת על שמך עם מסמכי העסק, "
                          "ולחברה בע״מ יש מסלול נפרד בליווי בנקאי/ת."),
        "name": "כדי לפנות אליך בשמך ולשייך כל מסמך ללווה הנכון.",
        "national_id": f"מספר הזהות משמש ל{ident.why_he}." if ident else "",
        "purpose": (f"לכל מטרה מבקשים אסמכתה אחרת, {proof.why_he}. למשל, ל{purpose.label_he}: {purpose.proof_he}."
                    if proof and purpose else ""),
        "amount": "הסכום הוא חלק מהבקשה, והוא גם מאפשר לי לתת לך אינדיקציה ראשונית להמחשה. הוא לא משנה את רשימת המסמכים.",
        "payments": "מספר התשלומים קובע את גובה ההחזר החודשי, ולכן גם את האינדיקציה הראשונית.",
        "income": (f"כי מקור ההכנסה משפיע על המסמכים שנצטרך: ממשכורת, {_label('PAYSLIPS')}; מעסק, "
                   f"{_label('TAX_ASSESSMENT')} ואישור על רישום העסק. מי שיש לו את שניהם מתבקש את שני הסוגים."
                   if pay and tax else ""),
        "registration": (f"סוג הרישום במע״מ קובע אילו מסמכים יבקשו על העסק: לעוסק פטור, {_and(exempt)}; "
                         f"לעוסק מורשה, {_and(registered)}. בשני המקרים מבקשים גם {_label('TAX_ASSESSMENT')}."),
        "net": "ההכנסה המוצהרת נשמרת כהצהרה בלבד, והבנקאי/ת משווה אותה למסמכים. היא גם מאפשרת לי לתת אינדיקציה ראשונית.",
        "co_borrower": "לכל לווה נוסף נדרשים מסמכים משלו, תעודת זהות ומסמכי הכנסה, ולכן חשוב לדעת את זה כבר עכשיו.",
        "accounts": f"דפי העו״ש נבדקים לכל חשבון. {stmt.why_he}." if stmt else "",
        "company_name": "המסלול לחברות מטופל בליווי בנקאי/ת, והשם מופיע על כל מסמכי החברה.",
        "signatory": "רק מורשה חתימה יכול להגיש בקשה בשם החברה.",
        "signatory_id": f"מספר הזהות משמש ל{ident.why_he}." if ident else "",
        "company_purpose": "מטרת המימון היא חלק מהבקשה, והבנקאי/ת בודק/ת אותה.",
        "business_amount": "הסכום הוא חלק מהבקשה; במסלול לחברות אין אינדיקציה אוטומטית.",
    }
    for k in ("co_national_id", "co_income", "co_registration", "co_net"):
        why[k] = why[k[3:]]
    why["co_name"] = why["co_borrower"]
    return why.get(qid) or "השאלה הזו קובעת אילו מסמכים יידרשו לבקשה."


def _why_registration(a: dict, conv: dict) -> str:
    reg = a.get("registration") or (_loan(conv, a).get("form") if _sole(conv, a) else None)
    if reg in ("vat_exempt", "vat_registered"):
        rules = [r for r in store.policy()[0].document_requirements
                 if r.condition and r.condition.registration and reg in r.condition.registration]
        if rules:
            return (f"כי יש לך הכנסה מעסק כ{FORM_HE[reg]}, ולכן המדיניות מבקשת {_and([r.label_he for r in rules])}: "
                    f"{rules[0].why_he}.")
    return _why("registration", conv, a)


def _provisional_documents(a: dict) -> Optional[list[str]]:
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


def _explain(ind: dict, a: dict) -> str:
    if not ind["available"]:
        if ind["reason"] == "company":
            return "במסלול לחברות אין אינדיקציה אוטומטית, הבקשה נבדקת בליווי בנקאי/ת."
        if ind["reason"] == "no_income":
            return "בלי הכנסה חודשית מוצהרת אין לי בסיס לאינדיקציה, ולכן אני לא מציג מספר."
        return f"עוד אין לי אינדיקציה, חסרים לי {_and(ind['missing_he'])}. כשיהיו לי, אחשב ואסביר בדיוק איך."
    parts = [f"{_ils(p['net_ils'])} שלך" if p["who"] == "primary" else
             f"{_ils(p['net_ils'])} של {_first(a, 'co_name') or 'הלווה הנוסף'}" for p in ind["net_parts"]]
    income = f"{_ils(ind['declared_net_ils'])} ({' + '.join(parts)})" if len(parts) > 1 else _ils(ind["declared_net_ils"])
    ratio = int(round(ind["ratio"] * 100))
    lines = [
        "כך חישבתי (הנחות חישוב כלליות, לא כללי חיתום של הבנק):",
        f"• ההכנסה החודשית נטו שמסרת: {income}, הצהרה, עוד לא מאומתת.",
        f"• עד {ratio}% ממנה להחזר חודשי ← עד כ־{_ils(ind['max_monthly_ils'])} בחודש."
        + (f" ({ratio}% ולא {int(indication.DEMO_RATIO_SALARIED * 100)}%, כי חלק מההכנסה מעסק.)" if ind["business_income"] else ""),
        f"• ריבית המחשה של {ind['annual_rate'] * 100:g}% לשנה ו־{ind['payments']} תשלומים: על {_ils(ind['requested_amount_ils'])} "
        f"ההחזר המשוער הוא כ־{_ils(ind['requested_monthly_ils'])} בחודש.",
        f"• התקרה התיאורטית בנוסחה הזו היא כ־{_ils(ind['max_amount_ils'])}"
        + (f" (מוגבלת ל־{_ils(ind['cap_ils'])}, התקרה של מסלול הבקשה)" if ind["capped"] else "")
        + ", זו לא מסגרת אשראי מאושרת.",
    ]
    if ind["co_borrower_pending"]:
        lines.append("• ההכנסה של הלווה הנוסף עוד לא נכללה.")
    lines.append("לא השתמשתי בנתוני אשראי, בחשבונות בנק או בהתחייבויות, אין לי גישה אליהם, והם לא נבדקו.")
    return "\n".join(lines)


def _topic(q: str) -> str:
    t = q
    if any(p in t for p in ("איך הגעת", "איך חישבת", "איך חושב", "מה החישוב", "איך זה מחושב", "על סמך מה",
                            "מאיפה הסכום", "מאיפה המספר", "למה הסכום", "איך הגעתם", "מה ההנחות")):
        return "explain_indication"
    if any(p in t for p in ("כמה אשלם", "כמה אצטרך לשלם", "כמה ההחזר", "מה ההחזר", "כמה יוצא בחודש", "כמה זה בחודש",
                            "מה התשלום החודשי", "כמה התשלום החודשי", "סך הכול אשלם", "סך הכל אשלם", "כמה אחזיר",
                            "ביחס להכנסה", "על התקציב", "מה הסימולציה", "כמה ריבית אשלם", "כמה ריבית אני משלם")):
        return "scenario"
    if any(p in t for p in ("מבטיח", "הבטחה", "יאשר", "תאשר", "מאושר", "אישרו", "יאושר", "זכאי", "זכאית", "כמה אפשר לקבל",
                            "כמה אוכל לקבל", "כמה אני יכול", "כמה אני יכולה", "מה המקסימום", "מה הסיכוי", "יסרבו")):
        return "approval"
    if "ריבית" in t:
        return "interest"
    if any(p in t for p in ("לחשב", "חישוב", "תחשב", "תחשבי", "לבדוק כמה")):
        return "calculate"
    if "תלוש" in t and any(p in t for p in ("אין לי", "חסר", "לא קיבלתי", "אין תלוש", "מה קורה אם", "מה אם")):
        return "missing_payslip"
    if "תלוש" in t:
        return "why_payslips"
    if any(p in t for p in ("פטור", "מורשה", "מע\"מ", "מעמ", "רשום", "רישום", "עוסק")) and "חתימה" not in t:
        return "why_registration"
    if any(p in t for p in ("לשנות", "לתקן", "לעדכן", "לערוך", "טעיתי")):
        return "change"
    if any(p in t for p in ("להוסיף", "עוד לווה", "לווה נוסף", "ערב", "בן זוג", "בת זוג", "אשתי", "בעלי")):
        return "add_coborrower"
    if any(p in t for p in ("אילו מסמכים", "איזה מסמכים", "מה צריך להביא", "מה צריך להעלות", "מסמכים")):
        return "documents"
    if any(p in t for p in ("מה חסר", "מה נשאר", "כמה נשאר", "כמה עוד", "כמה זמן", "כמה שאלות", "להתקדם")):
        return "remaining"
    if any(p in t for p in ("נציג", "בנקאי", "בנקאית", "בן אדם", "לדבר עם")):
        return "banker"
    if any(p in t for p in ("פרטיות", "המידע שלי", "מאובטח", "הנתונים שלי", "מי רואה")):
        return "privacy"
    if any(p in t for p in ("למה", "בשביל מה", "מה זה משנה", "מדוע", "למה זה חשוב", "למה אתה צריך")):
        return "why_pending"
    return "other_banking" if any(w in t for w in BANK_WORDS) else "off_topic"


def _answer(topic: str, q: str, a: dict, conv: dict, pending: Optional[str]) -> tuple[str, list[dict]]:
    """(deterministic, policy-grounded answer, quick-reply actions) for one customer question."""
    ind = _indication(a)
    if topic == "explain_indication":
        conv["explained"] = ind.get("key")
        return _explain(ind, a), []
    if topic == "scenario":
        conv["sim_touch"] = True
        return loan_sim.scenario_answer(conv, a, pending), []
    if topic == "approval":
        return ("אני לא יכול להבטיח אישור, אבל אפשר לבדוק את הבקשה ולהכין אותה להמשך בחינה, את ההחלטה מקבל הבנק "
                "אחרי בדיקת הבקשה והמסמכים."), []
    if topic == "interest":
        return ("את הריבית בפועל קובע הבנק רק אחרי בדיקת הבקשה, ואין לי נתון כזה. בסימולציה ובאינדיקציה הראשונית אני "
                f"משתמש בריבית המחשה של {indication.DEMO_ANNUAL_RATE * 100:g}% בלבד."), []
    if topic == "calculate":
        if ind["available"]:
            return "האינדיקציה הראשונית כבר מוצגת בשיחה, ואפשר לשאול אותי איך חישבתי אותה.", []
        if ind["reason"] == "company":
            return "במסלול לחברות אין אינדיקציה אוטומטית, הבקשה נבדקת בליווי בנקאי/ת.", []
        return f"אחשב אינדיקציה ראשונית ברגע שיהיו לי {_and(ind.get('missing_he') or ['עוד כמה פרטים'])}.", []
    if topic == "missing_payslip":
        count, months = _payslip_months_he()
        return (f"המדיניות מבקשת {count} תלושים אחרונים: {months}. אם חסר תלוש, אפשר בכל זאת לפתוח "
                "את הבקשה ולהעלות את מה שיש; חודש חסר יסומן, והבנקאי/ת יוכלו לבקש אותו או הסבר. הסבר בכתב לא מחליף "
                "את התלוש, ואין לי אפשרות לאשר כאן חלופה."), []
    if topic == "why_payslips":
        r = _rule("PAYSLIPS")
        count, months = _payslip_months_he()
        return (f"תלושי השכר מאמתים את ההכנסה ממשכורת. המדיניות מבקשת {count} תלושים אחרונים: "
                f"{months}. {r.why_he if r else ''}."), []
    if topic == "why_registration":
        return _why_registration(a, conv), []
    if topic == "change":
        target = _change_target(q, conv, a)
        if target and target in _v2(conv, a):
            conv["focus"] = target
            return f"בטח. כרגע רשום: {_value_he(target, _v2(conv, a)[target], a)}.", []
        if target:
            return "עוד לא הגענו לזה, אשאל על זה בהמשך.", []
        return "מה תרצו לשנות? אפשר ללחוץ \"שינוי\" ליד כל פרט בסיכום, או לכתוב לי, למשל \"לשנות את הסכום ל־90 אלף\".", []
    if topic == "add_coborrower":
        if a.get("entity") == "company":
            return "בבקשה של חברה אין לווה נוסף, את הבקשה מגיש/ה מורשה החתימה.", []
        if a.get("co_borrower") == "yes":
            return f"כבר הוספנו את {_first(a, 'co_name') or 'הלווה הנוסף'}. בבקשה הזו אפשר לצרף לווה נוסף אחד.", []
        act = [{"label_he": "להוסיף לווה נוסף", "question_id": "co_borrower", "value": "yes"}] if a.get("entity") else []
        return ("אפשר, לבקשה אפשר לצרף לווה נוסף אחד, למשל בן או בת זוג. אז יידרשו גם המסמכים שלו או שלה"
                + (", ואשאל על זה בשלב ההתאמה האישית." if a.get("co_borrower") != "no" else ".")), act
    if topic == "documents":
        docs = _provisional_documents(a)
        if docs:
            return f"לפי מה שסיפרת עד עכשיו, יידרשו {len(docs)} מסמכים: {_and(docs)}. את הרשימה הסופית אציג בסיכום.", []
        return "רשימת המסמכים תלויה בסוג ההלוואה ובמקור ההכנסה, כשאדע אותם אציג בדיוק מה יידרש.", []
    if topic == "remaining":
        left = [x for x in _applicable(conv, _assume(a)) if x not in _v2(conv, a)]
        if not left:
            return "סיימנו את השאלות, נשאר לעבור על הסיכום ולאשר, ואז נעבור למסמכים.", []
        stages = [label for _, label, qs in STAGES if any(x in qs for x in left)]
        return f"נשארו עוד {len(left)} שאלות קצרות ({_and(stages)}), ואחריהן סיכום לאישור.", []
    if topic == "banker":
        return "אני עוזר דיגיטלי, לא בנקאי. אחרי שהבקשה תיפתח היא תגיע לבנקאי/ת שמטפל/ת בה, וההחלטות מתקבלות שם.", []
    if topic == "privacy":
        return ("הפרטים שמסרת משמשים להכנת הבקשה בלבד: התשובות קובעות אילו מסמכים יידרשו, ואחרי פתיחת הבקשה "
                "הם מגיעים לבנקאי/ת שמטפל/ת בה."), []
    if topic == "why_pending" and pending:
        return _why(pending, conv, a), []
    if topic == "smalltalk":
        return "", []
    if topic == "off_topic":
        weather = any(w in q for w in ("מזג אוויר", "מזג האוויר", "תחזית", "גשם"))
        return ("אני מתמקד כרגע בבקשת ההלוואה שלך, אז לא אוכל לתת " + ("תחזית מזג אוויר." if weather else "תשובה על זה.")), []
    return "על זה אין לי מידע מאומת, ואני לא רוצה לנחש.", []


def _change_target(q: str, conv: dict, a: dict) -> Optional[str]:
    applicable = set(_applicable(conv, a))
    for word, qids in CHANGE_WORDS:
        if word in q:
            return next((x for x in qids if x in applicable), None)
    return None


NOTE_TEXT = {
    "range_low": lambda n: f"רשמתי {_ils(n['value'])}, הערך הנמוך בטווח שכתבת, כדי לא להגזים בהערכה.",
    "conflicting_numbers": lambda n: f"ראיתי כמה מספרים ל{FIELD_HE.get(n['field'], 'אותו פרט')}, איזה מהם נכון?",
    "unplaced_number": lambda n: f"לא בטוח למה התכוונת ב־{n['value']:,}, זה הסכום, ההכנסה או משהו אחר?",
    "ambiguous_purpose": lambda n: "הזכרת יותר ממטרה אחת, מה המטרה העיקרית של ההלוואה?",
    "unsupported_income": lambda n: ("בשאלון הזה אפשר לציין הכנסה ממשכורת או מעסק. הכנסה מסוג אחר (למשל קצבה או שכירות) "
                                     "השאלון עוד לא יודע לקלוט."),
    "partial_name": lambda n: "אשמח גם לשם המשפחה.",
    "no_income_left": lambda n: "אם אין הכנסה ממשכורת ולא מעסק, השאלון הזה עוד לא תומך בסוג ההכנסה הזה.",
}
CLARIFYING_NOTES = {"conflicting_numbers", "unplaced_number", "ambiguous_purpose", "partial_name"}


def _gross_text(pending: Optional[str]) -> str:
    return ("כדי לחשב אינדיקציה ראשונית אצטרך לדעת כמה נכנס לך נטו, ולא ברוטו."
            + (" כמה זה בערך?" if pending in ("net", "co_net") else " נגיע לזה בהמשך."))


def _unclear(field: str, kind: str, conv: dict, a: dict) -> tuple[str, list[dict]]:
    if field in ("income", "co_income"):
        acts = [{"label_he": "יש לי גם עסק עצמאי", "question_id": field, "value": ["salaried", "self_employed"]},
                {"label_he": "הכול כשכיר", "question_id": field, "value": ["salaried"]}]
        if kind == "income_side_jobs":
            return ("הבנתי שיש לך לפעמים הכנסה כשכיר וגם עבודות נוספות. העבודות מהצד הן במסגרת עסק עצמאי, "
                    "או שגם שם מדובר בהעסקה כשכיר?"), acts + [{"label_he": "אני לא בטוח/ה", "text": "אני לא בטוח איך להגדיר את העבודות מהצד"}]
        return ("זה בסדר, זה לא תמיד ברור. אם על העבודות מוציאים חשבונית או קבלה, זו הכנסה מעסק עצמאי. "
                "אם מקבלים עליהן תלוש, זו הכנסה כשכיר. מה מתאים לך?"), acts + [
            {"label_he": "רק עסק עצמאי", "question_id": field, "value": ["self_employed"]}]
    return {"amount": "כמה בערך תרצו לבקש? גם סכום משוער מספיק.",
            "business_amount": "כמה בערך מבקשים? גם סכום משוער מספיק.",
            "net": "כמה בערך נכנס לך נטו בחודש? גם מספר משוער מספיק.",
            "co_net": "כמה בערך נכנס ללווה הנוסף נטו בחודש?",
            "payments": "בכמה תשלומים תרצו לפרוס? למשל 36, 48 או 60.",
            "loan_type": "מדובר בהלוואה פרטית או עסקית?",
            "purpose": "למה מיועדת ההלוואה, למשל רכב, שיפוץ או מטרה אחרת?",
            "name": "אשמח לשם המלא, שם פרטי ושם משפחה."}.get(field, f"אפשר לפרט קצת לגבי {FIELD_HE.get(field, 'זה')}?"), []


ERROR_LEAD = {"net": "לא רשמתי את ההכנסה: ", "co_net": "לא רשמתי את ההכנסה: "}


def _error_text(qid: str, msg: str, value: Any = None) -> str:
    if qid == "payments":
        lo, hi = onboarding.PAYMENT_BOUNDS
        return f"אפשר לבחור בין {lo} ל־{hi} תשלומים. מה מתאים לך?"
    if qid in ("amount", "business_amount") and isinstance(value, int):
        lo, hi = onboarding.NUMBER_BOUNDS[qid]
        limit = f"של עד {_ils(hi)}" if value > hi else f"של {_ils(lo)} לפחות"
        return f"במסלול הבקשה הזה אפשר כרגע להזין סכום {limit}. אם מתאים לך, נמשיך עם סכום בטווח הנתמך."
    if msg == "השאלה אינה רלוונטית לתשובות הקודמות":
        return f"לא רשמתי את {FIELD_HE.get(qid, 'הפרט')}, הוא לא מתאים לסוג הבקשה הנוכחי."
    return ERROR_LEAD.get(qid, "") + msg + "."


def _not_understood(pending: Optional[str]) -> str:
    if pending is None:
        return "לא בטוח שהבנתי. אפשר לבקש לשנות פרט, למשל \"לשנות את הסכום\", או לאשר את הסיכום למטה."
    kind = "choice" if pending in LOAN_FIELDS else BY_ID[pending][1]
    hint = {"choice": "אפשר לבחור אחת מהאפשרויות או לכתוב במילים שלך.",
            "multi": "אפשר לבחור אחת מהאפשרויות או לכתוב, למשל \"אני שכירה\".",
            "number": "אפשר לבחור מהאפשרויות או לכתוב מספר, למשל \"80 אלף\".",
            "name": "אשמח לשם פרטי ושם משפחה, למשל: מיכל ברק.",
            "text": "אפשר לכתוב את התשובה כאן למטה."}[kind]
    return f"לא בטוח שהבנתי. {hint}"


# ---------------------------------------------------------------- indication and progress
def _indication(a: dict) -> dict:
    return indication.compute(a, onboarding.NUMBER_BOUNDS["amount"][1])


def _assume(a: dict) -> dict:
    """For display only: before the first answer the stages show the individual path, the common case."""
    return a if "entity" in a else {**a, "entity": "individual"}


def _stages(conv: dict, a: dict, pending: Optional[str], status: str) -> list[dict]:
    v = _v2(conv, a)
    applicable = set(_applicable(conv, _assume(a)))
    out = []
    for sid, label, qids in STAGES:
        qs = [q for q in qids if q in applicable]
        if sid != "summary" and not qs:
            continue
        answered = [q for q in qs if q in v]
        if sid == "summary":
            state = "done" if status == "confirmed" else "current" if pending is None else "upcoming"
        elif pending in qs:
            state = "current"
        else:
            state = "done" if len(answered) == len(qs) else "upcoming"
        out.append({"id": sid, "label_he": label, "state": state, "total": len(qs), "answered": len(answered)})
    return out


def _indication_event(conv: dict, a: dict) -> tuple[Optional[str], Optional[dict], str]:
    """(event, snapshot, sentence): a new or updated indication, or the withdrawal of an outdated one."""
    ind = _indication(a)
    shown = conv.get("shown")
    if ind["available"]:
        if shown and shown.get("key") == ind["key"]:
            return None, None, ""
        snap = {k: ind[k] for k in ("key", "max_amount_ils", "requested_amount_ils", "within", "requested_monthly_ils",
                                    "payments", "declared_net_ils", "co_borrower_pending", "ratio", "annual_rate",
                                    "business_income")}
        conv["shown"] = {"key": ind["key"]}
        updated = bool(shown and shown.get("key"))
        req = _ils(ind["requested_amount_ils"])
        co = " (לפי ההכנסה שלך בלבד, עד שאדע את ההכנסה של הלווה הנוסף)" if ind["co_borrower_pending"] else ""
        if ind["within"]:
            core = f"הבקשה שלך ל־{req} נראית אפשרית להמשך בדיקה ראשונית{co}"
        else:
            core = f"הסכום שביקשת ({req}) גבוה ממה שההערכה הראשונית מראה כאפשרי{co}; אפשר להמשיך כך, והבנק יבדוק"
        if updated:
            return "updated", snap, f"עדכנתי את האינדיקציה לפי השינוי: {core}."
        return "new", snap, (f"אגב, לפי ההכנסה שמסרת ובהתאם להנחות חישוב כלליות, {core}. זו עדיין לא בדיקת זכאות "
                             "או אישור מהבנק.")
    if shown and shown.get("key"):
        conv["shown"] = {"key": None}
        why = ("במסלול לחברות אין אינדיקציה אוטומטית." if ind["reason"] == "company" else
               f"אחזור אליה כשיהיו לי {_and(ind['missing_he'])}." if ind["reason"] == "missing" else "")
        return "withdrawn", None, f"האינדיקציה הקודמת כבר לא מתאימה לפרטים, אז הסרתי אותה. {why}".strip()
    return None, None, ""


def _summary_lines(conv: dict, a: dict) -> list[dict]:
    loan = _loan(conv, a)
    kind = "הלוואה פרטית" if loan.get("type") == "personal" else f"הלוואה עסקית · {FORM_HE.get(loan.get('form'), '')}"
    if a.get("entity") == "company":
        rows = [("סוג ההלוואה", kind, "loan_type"), ("החברה", a["company_name"], "company_name"),
                ("מורשה החתימה", onboarding._answer_he("signatory", a["signatory"]), "signatory"),
                ("מטרה", _purpose_he(a["company_purpose"]), "company_purpose"),
                ("סכום", _ils(a["business_amount"]), "business_amount"), ("תשלומים", f"{a['payments']} תשלומים", "payments")]
    else:
        rows = [("סוג ההלוואה", kind, "loan_type"), ("שם", onboarding._answer_he("name", a["name"]), "name"),
                ("תעודת זהות", a["national_id"], "national_id"),
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
            rows.append(("לווה נוסף", "אין, הבקשה רק על שמך", "co_borrower"))
    out = [{"label_he": l, "value_he": v, "question_id": q} for l, v, q in rows]
    sim = loan_sim.summary_line(conv, a)
    if sim:
        at = next(i for i, r in enumerate(out) if r["question_id"] == "payments") + 1
        out.insert(at, sim)
    return out


# ---------------------------------------------------------------- understanding
def _understand_rules(text: str, conv: dict, a: dict, pending: Optional[str]) -> dict:
    v = _v2(conv, a)
    u = nlu.understand(text, v, pending)
    topics = [(_topic(q), q) for q in u["questions"]]
    values, corrections = dict(u["values"]), set(u["corrections"])
    if not topics and not values and re.search(r"(?:^|\s)(?:לשנות|לתקן|לעדכן|לערוך)(?=\s)", nlu.normalize(text)):
        topics.append(("change", text))                    # "לשנות את מקור ההכנסה" without a question mark
    if any(t == "change" for t, _ in topics):
        target = _change_target(text, conv, a)
        u2 = nlu.understand(text, v, target or pending, as_statement=True)
        for k, val in u2["values"].items():
            if k not in values:
                values[k] = val
                corrections.add(k)
    unclear = [{"field": n["field"], "kind": n["kind"]} for n in u["notes"] if n["kind"].startswith("income_")]
    notes = [n for n in u["notes"] if not n["kind"].startswith("income_")]
    return {"values": values, "corrections": corrections, "unclear": unclear, "topics": topics, "notes": notes,
            "engine": "rules"}


def _understand_llm(text: str, conv: dict, a: dict, pending: Optional[str], draft_id: str,
                    det_text: Optional[str] = None, sim_numbers: frozenset = frozenset()) -> Optional[dict]:
    """`det_text` is the message without the numbers the simulator claimed (a target payment, existing repayments, a
    vehicle price); the model still reads the whole message, but a figure it proposes that IS one of those numbers is
    not an amount, a term or an income."""
    v = _v2(conv, a)
    context = {
        "pending_question": {"field": pending, "prompt_he": _prompt(pending, conv, a) if pending else None,
                             "options": [{"value": r["value"], "label_he": r["label_he"]} for r in
                                         (_replies(pending, conv, a) if pending else [])]},
        "known_answers": {k: _value_he(k, val, a, short=True) for k, val in v.items()
                          if k not in ("national_id", "co_national_id", "signatory_id", "entity")},
        "remaining_questions": [{"field": q, "prompt_he": _prompt(q, conv, a)}
                                for q in _applicable(conv, a) if q not in v][:6],
        "first_name": _first(a) or None,
        "recent_conversation": [{"role": m["role"], "text": llm.mask(m["text_he"])[:300]} for m in conv["messages"][-6:]],
        "customer_message": llm.mask(text),
    }
    out = llm.interpret(context, conv, draft_id)
    if out is None:
        return None
    values, notes = dict(out["values"]), []
    claimed = {k for k in ("amount", "business_amount", "payments", "net", "co_net") if values.get(k) in sim_numbers}
    for k in claimed:
        values.pop(k)
    # deterministic guards around the model: ID numbers by pattern only, never a net figure from a gross one
    det_u = nlu.understand(det_text if det_text is not None else text, v, pending)
    for k in ("national_id", "co_national_id", "signatory_id"):
        if k in det_u["values"]:
            values[k] = det_u["values"][k]
    norm = nlu.normalize(text)
    gross = ("ברוטו" in norm and "נטו" not in norm) or out["gross"]
    if gross:
        for k in ("net", "co_net"):
            values.pop(k, None)
        notes.append({"kind": "gross"})
    unclear_fields = {u["field"] for u in out["unclear"]}
    # a number the model hesitated on (or skipped) but the parser read plainly — "בערך 80 אלף" — is used as read;
    # approximation is not doubt, but a hedge is: "אולי 60 תשלומים" stays a question when the model marked it unclear
    hedged = bool(re.search(r"אולי|לא בטוח|לא יודע|מתלבט|יכול להיות|תלוי", norm))
    for k in ("amount", "business_amount", "payments", "net", "co_net"):
        if k in det_u["values"] and k not in values and not (gross and k in ("net", "co_net")) \
                and not (hedged and k in unclear_fields):
            values[k] = det_u["values"][k]
            unclear_fields.discard(k)
            if k in det_u["corrections"]:
                out["corrections"].add(k)
    unclear = []
    for u in out["unclear"]:
        f = u["field"]
        if f not in unclear_fields or f in values or (gross and f in ("net", "co_net")):
            continue
        if f.endswith("income"):
            unclear.append({"field": f, "kind": "income_side_jobs" if "salaried" in (det_u["values"].get(f) or []) or
                            nlu.SIDE_JOBS.search(norm) else "income_help"})
        elif f == pending:
            unclear.append({"field": f, "kind": "unclear"})
    topics = [(t, norm) for t in out["topics"]]
    return {"values": values, "corrections": out["corrections"], "unclear": unclear, "topics": topics, "notes": notes,
            "engine": "llm", "candidate": out["reply_he"], "next_field": out["next_field"],
            "proposed": {k: x for k, x in out["values"].items() if k not in claimed}}


# ---------------------------------------------------------------- apply
def _set_loan(draft_id: str, conv: dict, a: dict, loan_type: Optional[str], form: Optional[str]) -> None:
    loan = _loan(conv, a)
    t = loan_type or loan.get("type")
    f = None if t == "personal" else (form or (loan.get("form") if t == loan.get("type") else None))
    conv["loan"] = {"type": t, "form": f}
    if t == "personal":
        onboarding.answer(draft_id, "entity", "individual")
    elif t == "business" and f == "company":
        onboarding.answer(draft_id, "entity", "company")
    elif t == "business" and f in ("vat_exempt", "vat_registered"):
        onboarding.answer(draft_id, "entity", "individual")
        cur = onboarding._clean_answers(onboarding._row(draft_id)["answers"]).get("income") or []
        if "self_employed" not in cur:
            onboarding.answer(draft_id, "income", [s for s in ("salaried", "self_employed") if s in cur + ["self_employed"]])
        onboarding.answer(draft_id, "registration", f)
    elif t == "business" and a.get("entity"):
        onboarding.answer(draft_id, "entity", None)


def _apply(draft_id: str, conv: dict, a: dict, u: dict, pending: Optional[str]) -> dict:
    """Record what is valid, hold what does not apply yet, and report what was refused or contradicts an answer."""
    out: dict[str, Any] = {"rejected": [], "conflicts": [], "held": [], "actions": [], "rejected_en": []}
    values = dict(u["values"])
    focus = conv.get("focus")
    before = _v2(conv, a)

    def fresh() -> dict:
        return onboarding._clean_answers(onboarding._row(draft_id)["answers"])

    def conflict(field: str, value: Any) -> bool:
        """A different value for a field the customer had answered BEFORE this turn, without a correction and not the
        question being asked. Values set earlier in this same turn (e.g. business income from "עוסק פטור") are not
        earlier answers, so "יש לי עוסק פטור ואני גם שכיר" keeps both sources."""
        old = before.get(field)
        if old is None or old == value or field in u["corrections"] or field in (pending, focus):
            return False
        if field in loan_sim.SIM_FIELDS and u.get("sim_change"):
            return False                                  # "אני רוצה לפרוס ל־60 תשלומים" changes the scenario
        # the parser already merged income sources with the earlier answer ("גם", negation, past jobs)
        return not (u["engine"] == "rules" and field in ("income", "co_income"))

    lt, form = values.pop("loan_type", None), values.pop("business_form", None)
    if lt == "personal":
        form = None
    if lt or form:
        if lt and conflict("loan_type", lt):
            out["conflicts"].append(("loan_type", before.get("loan_type"), lt))
        else:
            _set_loan(draft_id, conv, fresh(), lt, form)
    a = fresh()
    if a.get("entity") == "company" and "amount" in conv["held"]:
        conv["held"]["business_amount"] = conv["held"].pop("amount")
    sole = _sole(conv, a)
    for qid in sorted(values, key=lambda k: QUESTION_INDEX[k]):
        value = values[qid]
        if qid == "income" and sole and "self_employed" not in (value or []):
            out["rejected"].append((qid, "בהלוואה עסקית לעוסק צריכה להיות הכנסה מהעסק. אם אין לך עסק, אפשר לעבור "
                                         "להלוואה פרטית."))
            out["rejected_en"].append(EN.SOLE_INCOME)
            out["actions"].append({"label_he": "לעבור להלוואה פרטית", "question_id": "loan_type", "value": "personal"})
            continue
        if conflict(qid, value):
            out["conflicts"].append((qid, before.get(qid), value))
            continue
        try:
            if not BY_ID[qid][4](a):
                onboarding._validate(qid, value)
                conv["held"][qid] = value
                out["held"].append(qid)
                continue
            rule = loan_sim.check_answer(conv, a, qid, onboarding._validate(qid, value))
            if rule:
                out["rejected"].append((qid, rule[0]))
                out["rejected_en"].append(_en_text(lambda: EN.rule_message(conv, a, qid, onboarding._validate(qid, value))))
                out["actions"] += rule[1]
                continue
            onboarding.answer(draft_id, qid, value)
        except OnboardingError as exc:
            out["rejected"].append((qid, _error_text(qid, exc.message_he, value)))
            out["rejected_en"].append(_en_text(lambda: EN.error(qid, exc.message_he, value)))
            continue
        a = fresh()
        if focus == qid:
            conv["focus"] = focus = None
    for qid, value in list(conv["held"].items()):
        a = fresh()
        if qid in a or not BY_ID[qid][4](a):
            if qid in a:
                conv["held"].pop(qid)
            continue
        conv["held"].pop(qid)
        try:
            rule = loan_sim.check_answer(conv, a, qid, onboarding._validate(qid, value))
            if rule:
                out["rejected"].append((qid, rule[0]))
                out["rejected_en"].append(_en_text(lambda: EN.rule_message(conv, a, qid, onboarding._validate(qid, value))))
                out["actions"] += rule[1]
                continue
            onboarding.answer(draft_id, qid, value)
        except OnboardingError as exc:
            out["rejected"].append((qid, _error_text(qid, exc.message_he, value)))
            out["rejected_en"].append(_en_text(lambda: EN.error(qid, exc.message_he, value)))
    if focus in LOAN_FIELDS and (lt or form):
        conv["focus"] = None
    a = fresh()
    after = _v2(conv, a)
    out["a"] = a
    out["changes"] = [(k, before.get(k), after.get(k)) for k in ORDER if k != "entity" and before.get(k) != after.get(k)
                      and after.get(k) is not None]
    return out


# ---------------------------------------------------------------- compose
def _question_line(t: dict, conv: dict, a: dict) -> str:
    nxt = t["next"]
    if nxt is None or t["clarifying"]:
        return ""
    if nxt != conv.get("asked") or t["changes"] or t.get("edit"):
        return _prompt(nxt, conv, a)
    # vary the way back to the question so consecutive interruptions don't all start with "אז"
    lead = ("בינתיים, " if t["gross"] else "נמשיך? " if t.get("off_topic") else
            ("", "אז ", "ולגבי הבקשה, ")[conv["seq"] % 3] if t["interrupted"] else "")
    return lead + _short(nxt, conv, a)


def _compose_rules(t: dict, conv: dict, a: dict) -> str:
    parts = [p for p in [t["ack"]] + t["issues"] + t["answers"] + [t.get("sim_text", ""), t["ind_text"]] if p]
    if t["summary_text"]:
        parts.append(t["summary_text"])
    q = _question_line(t, conv, a)
    if q:
        parts.append(q)
    if not parts:
        parts.append(_not_understood(t["next"]))
    return " ".join(parts)


def _facts(t: dict, conv: dict, a: dict, customer: str) -> dict:
    return {
        "customer_message": llm.mask(customer),
        "first_name": _first(a) or None,
        "recorded": [{"field": FIELD_HE[k], "value": _value_he(k, new, a, short=True),
                      "previous": _value_he(k, old, a, short=True) if old is not None else None}
                     for k, old, new in t["changes"] if k not in ("national_id", "co_national_id", "signatory_id")]
        + [{"field": FIELD_HE[k], "value": "נקלט"} for k, _, _ in t["changes"] if k in ("national_id", "co_national_id", "signatory_id")],
        "kept_for_later": [FIELD_HE[k] for k in t["held"]],
        "issues_and_clarifications": t["issues"],
        "answers": t["answers"],
        "indication": {"sentence_he": t["ind_text"]} if t["ind_text"] else None,
        "waiting_for_clarification": t["clarifying"],
        "next_question": ({"prompt_he": _prompt(t["next"], conv, a), "already_asked": t["next"] == conv.get("asked")}
                          if t["next"] and not t["clarifying"] else None),
        "summary_ready": t["next"] is None,
        "recent_conversation": [{"role": m["role"], "text": llm.mask(m["text_he"])[:240]} for m in conv["messages"][-4:]],
    }


ID_FIELDS = {"national_id", "co_national_id", "signatory_id"}


def _candidate_ok(u: dict, t: dict, conv: dict, a: dict, facts: dict) -> bool:
    """The interpretation's own reply may be used only on an ordinary turn whose outcome is exactly what it assumed:
    every fact it proposed was recorded as proposed and nothing else was added, nothing was refused, held, contradicted
    or left unclear, no question or disclosure is needed (policy answer, indication, summary), the next question is the
    one it asked, and every number in it is grounded. Anything else gets the second call or the deterministic reply."""
    cand = u.get("candidate")
    if not cand or u.get("engine") != "llm" or llm.claims_approval(cand):
        return False
    # a new or updated indication travels in its deterministic card (amount, verdict, disclaimer), so the text need
    # not carry it; a withdrawal must be said in words
    if (t["issues"] or t["answers"] or t["held"] or t["clarifying"] or t["actions"] or t["ind_event"] == "withdrawn"
            or t["summary_text"] or any(topic != "smalltalk" for topic, _ in u["topics"])):
        return False
    if set(u["values"]) - ID_FIELDS != set(u.get("proposed") or {}):
        return False
    v = _v2(conv, a)
    if any(v.get(k) != val for k, val in u["values"].items()):
        return False
    return (t["next"] or "summary") == u.get("next_field") and llm.grounded(cand, facts)


def _llm_reply_ok(reply: str, t: dict) -> bool:
    """The indication's framing must survive the model's wording: the requested amount and a non-approval phrase."""
    if not t["ind_text"] or t["ind_event"] == "withdrawn":
        return True
    amount = f"{t['ind_snap']['requested_amount_ils']:,}"
    if t["ind_event"] == "updated":
        return amount in reply                  # the card carries the disclaimer, as in the deterministic update
    return amount in reply and any(p in reply for p in ("לא בדיקת זכאות", "לא אישור", "אינה אישור", "אינו אישור",
                                                       "עדיין לא", "לא הצעה"))


# ---------------------------------------------------------------- API
def view(draft_id: str, lang: Optional[str] = None) -> dict[str, Any]:
    """`lang`: the customer app's language (X-MZ-Lang). With it the view gains `*_en` siblings (i18n/chat_en); without it
    the view is exactly the Hebrew one, the transcript's English included."""
    row, a, conv = _load(draft_id, lang)
    base = onboarding.view(draft_id)
    focus = conv.get("focus")
    pending = _pending(conv, a) if row["status"] == "draft" else None
    ind = _indication(a)
    current_key = ind.get("key") if ind["available"] else None
    messages = []
    live_sim = next((m["id"] for m in reversed(conv["messages"]) if m.get("simulator")), None)
    for m in conv["messages"]:
        snap = m.get("indication")
        extra = {"simulator": {**m["simulator"], "live": m["id"] == live_sim}} if m.get("simulator") else {}
        messages.append({**m, **extra, "stale": bool(snap) and snap.get("key") != current_key})
        if lang is None:
            for k in LANG_KEYS:
                messages[-1].pop(k, None)
    last_actions = next((m.get("actions") for m in reversed(messages) if m["role"] == "assistant"), None)
    simulation = loan_sim.view(conv, a, pending) if row["status"] == "draft" else None
    suggestions: list[str] = []
    if simulation and simulation["status"] == "confirmed" and simulation["context"]["net_income"]:
        suggestions.append("מה ההחזר ביחס להכנסה שלי?")
    if pending:
        suggestions.append("למה צריך את זה?")
    v = _v2(conv, a)
    first = _first(a) or _first(a, "signatory")
    out: dict[str, Any] = {
        "draft_id": draft_id, "status": row["status"], "case_id": row["case_id"], "updated_at": row["updated_at"],
        "first_name_he": first or None, "messages": messages, "engine": "llm" if llm.enabled() else "rules",
        "simulation": simulation,
        "pending": {"question_id": pending, "kind": "simulator" if _sim_question(pending, conv, a)
                    else "choice" if pending in LOAN_FIELDS else BY_ID[pending][1],
                    "prompt_he": _prompt(pending, conv, a), "replies": _replies(pending, conv, a),
                    "placeholder_he": _placeholder(pending), "editing": bool(focus and focus == pending),
                    "current_he": _value_he(pending, v[pending], a) if pending in v else None} if pending else None,
        "actions": last_actions or [],
        "stages": _stages(conv, a, pending, row["status"]),
        "loan": _loan(conv, a),
        "indication": ({k: ind[k] for k in ("max_amount_ils", "requested_amount_ils", "within", "requested_monthly_ils",
                                            "payments", "declared_net_ils", "co_borrower_pending")}
                       if ind["available"] else None),
        "suggestions": suggestions,
        "summary": None,
        "note_he": "השאלות קובעות רק אילו מסמכים נדרשים. הן אינן בדיקת זכאות ואינן הצעת אשראי.",
    }
    if pending is None and base["summary"]:
        out["summary"] = {**base["summary"], "lines": _summary_lines(conv, a),
                          "intro_he": f"{first + ', ' if first else ''}זה מה שהבנתי. אפשר לשנות כל פרט לפני שפותחים את הבקשה."}
    return i18n.localized(lang, out, lambda o: EN.view(o, conv, a))


def start(lang: Optional[str] = None) -> dict[str, Any]:
    return view(onboarding.start()["draft_id"], lang)


def _sim_action(draft_id: str, conv: dict, a: dict, t: dict, kind: str, simulation: Optional[dict],
                pending: Optional[str]) -> dict:
    """The card's confirmation (or a suggested change from a quick action): product rules, then amount and payments
    through the questionnaire. A suggested change to a scenario that is still a draft only moves the draft."""
    if not loan_sim.applies(conv, a):
        raise OnboardingError("עוד אין סימולציה לאשר")
    t["sim_touch"] = True
    current = {**loan_sim.draft_params(conv, a), "product": loan_sim.product(conv, a)["id"]}
    if kind == "simulate_apply" and loan_sim.status(conv, a, pending) == "pending":
        loan_sim.save_draft(conv, a, {**current, **loan_sim.clean(simulation)})
        loan_sim._sim(conv)["rev"] += 1
        prm = loan_sim.draft_params(conv, a)
        t["sim_text"] = (f"עדכנתי בסימולציה: {_ils(prm['amount'])} ב־{prm['term']} תשלומים. "
                         + loan_sim.monthly_sentence(conv, a, prm) + " אם זה מתאים, אפשר לאשר.")
        _english(t, "sim", lambda: EN.sim_apply_pending(conv, a, prm))
        return a
    base = ({**(loan_sim.confirmed_params(conv, a) or current), "product": current["product"]}
            if kind == "simulate_apply" else current)
    before = _v2(conv, a)
    found, prm = loan_sim.confirm(draft_id, conv, a, {**base, **loan_sim.clean(simulation)})
    a = onboarding._clean_answers(onboarding._row(draft_id)["answers"])
    if found:
        msg, acts = loan_sim.issues_text(found)
        t["issues"].append(msg)
        _english(t, "issues", lambda: EN.issues_text(found, loan_sim.product(conv, a)))
        t["actions"] += acts
        return a
    if conv.get("focus") in loan_sim.SIM_FIELDS:
        conv["focus"] = None
    after = _v2(conv, a)
    t["changes"] = [(k, before.get(k), after.get(k)) for k in ORDER if k != "entity" and before.get(k) != after.get(k)
                    and after.get(k) is not None]
    t["sim_text"] = loan_sim.confirmed_text(conv, a, prm)
    _english(t, "sim", lambda: EN.confirmed_text(conv, a, prm))
    return a


def turn(draft_id: str, text: Optional[str] = None, question_id: Optional[str] = None, value: Any = None,
         label_he: Optional[str] = None, action: Optional[str] = None, turn_id: Optional[str] = None,
         simulation: Optional[dict] = None, label_en: Optional[str] = None, lang: Optional[str] = None) -> dict[str, Any]:
    """One customer turn → exactly one assistant message. A repeated `turn_id` (a double submit) changes nothing.
    `action`: edit · cancel_edit · simulate_confirm (the card's scenario in `simulation`) · simulate_apply (a suggested
    change in `simulation`).
    `lang` (the customer app's X-MZ-Lang): the turn is composed in Hebrew exactly as without it, and the same outcome is
    also worded in English (i18n/chat_en) and stored beside it. In an English session typed English is read through
    onboarding_nlu_en, and the reply is the deterministic one (the model may still interpret the message).
    `label_en`: the English label of the quick reply the customer tapped, shown back in the English app only."""
    with _lock:
        row, a, conv = _load(draft_id, lang)
        if row["status"] != "draft":
            raise OnboardingError("הבקשה כבר נפתחה, אי אפשר לשנות את התשובות", 409)
        if turn_id and turn_id in conv["turns"]:
            return view(draft_id, lang)
        pending = _pending(conv, a)
        calls_at_start = conv.get("llm_calls", 0)
        u: dict[str, Any] = {}
        t: dict[str, Any] = {"changes": [], "held": [], "issues": [], "answers": [], "actions": [], "clarifying": False,
                             "interrupted": False, "gross": False, "edit": False, "ack": "", "ind_text": "",
                             "ind_event": None, "ind_snap": None, "summary_text": "", "sim_text": "",
                             "sim_touch": False}
        t["_en"] = {"ack": "", "issues": [], "answers": [], "sim": ""} if lang else None
        conv.pop("sim_touch", None)
        engine, customer = "rules", ""
        use_llm_reply = False
        su: dict[str, Any] = {}
        if action is None and question_id is None and text:
            su = loan_sim.understand(_parser_text(text, pending, lang), conv, a, pending)
            if su.get("confirm"):
                action = "simulate_confirm"

        if action in ("edit", "cancel_edit"):
            if action == "edit":
                if question_id == "simulation" and loan_sim.applies(conv, a):
                    conv["focus"] = loan_sim.amount_field(conv, a)
                    customer = "שינוי הסימולציה"
                    t["answers"].append("בטח, אפשר לשנות את התרחיש בסימולציה ולאשר מחדש.")
                    _english(t, "answers", lambda: EN.edit_answer("simulation", conv, a))
                    t["edit"] = True
                    _say(conv, customer, role="user", **_said(lang, lambda: EN.user_edit("simulation")))
                elif question_id not in BY_ID and question_id not in LOAN_FIELDS or question_id not in _v2(conv, a):
                    raise OnboardingError("אי אפשר לערוך את הפרט הזה")
                else:
                    conv["focus"] = question_id
                    customer = f"שינוי {FIELD_HE[question_id]}"
                    t["answers"].append(f"בטח. כרגע רשום: {_value_he(question_id, _v2(conv, a)[question_id], a)}.")
                    _english(t, "answers", lambda: EN.edit_answer(question_id, conv, a))
                    t["edit"] = True
                    _say(conv, customer, role="user", **_said(lang, lambda: EN.user_edit(question_id)))
            else:
                conv["focus"] = None
                customer = "ביטול השינוי"
                t["answers"].append("בסדר, השארתי את מה שהיה.")
                _english(t, "answers", lambda: "Fine, I left it as it was.")
                _say(conv, customer, role="user", **_said(lang, lambda: "Cancel the change"))
        elif action in ("simulate_confirm", "simulate_apply"):
            typed = bool(text and su.get("confirm"))
            if text and su.get("confirm"):
                customer = " ".join(str(text).split())[:MAX_TEXT]
            else:
                prm = {**loan_sim.draft_params(conv, a), **loan_sim.clean(simulation)} if loan_sim.applies(conv, a) else {}
                customer = (label_he or "")[:80] or (
                    f"זה התרחיש שלי: {_ils(prm['amount'])} ב־{prm['term']} תשלומים" if prm else "אישור הסימולציה")
            _say(conv, customer, role="user", **_said(lang, None if typed else
                                                       lambda: (label_en or "")[:80] or EN.user_scenario(prm)))
            a = _sim_action(draft_id, conv, a, t, action, simulation, pending)
            if t["changes"]:
                t["ind_event"], t["ind_snap"], t["ind_text"] = _indication_event(conv, a)
        else:
            if question_id is not None:
                if question_id not in BY_ID and question_id not in LOAN_FIELDS:
                    raise OnboardingError("שאלה לא מוכרת")
                customer = (label_he or "")[:80] or _value_he(question_id, value, a)
                said = _said(lang, lambda: (label_en or "")[:80] or EN.value(question_id, value, a))
                u = {"values": {question_id: value}, "corrections": {question_id}, "unclear": [], "topics": [],
                     "notes": [], "engine": "rules"}
                use_llm_reply = True
            else:
                customer = " ".join(str(text or "").split())[:MAX_TEXT]
                if not customer:
                    raise OnboardingError("ההודעה ריקה")
                # the customer's own words are stored as written; a suggestion or an action that sends text has its label
                said = _said(lang, (lambda: label_en[:80]) if label_en else None)
                masked = su.get("masked", customer)
                u = (_understand_llm(customer, conv, a, pending, draft_id, masked, frozenset(su.get("numbers") or ()))
                     or _understand_rules(masked, conv, a, pending))
                engine = u["engine"]
                use_llm_reply = engine == "llm"
                u["sim_change"] = bool(su.get("change_intent"))
                if su.get("product") and "loan_type" not in _v2(conv, a) and "loan_type" not in u["values"]:
                    u["values"]["loan_type"] = "personal"   # "הלוואה ברגע" names a personal-loan product
            _say(conv, customer, role="user", **said)
            sim_before = loan_sim.applies(conv, a)
            sim_notes = loan_sim.apply_text(conv, a, su) if su else []
            res = _apply(draft_id, conv, a, u, pending)
            a = res["a"]
            if su and not sim_before and loan_sim.applies(conv, a):
                sim_notes = list(dict.fromkeys([n for n in sim_notes if n != "product"] + loan_sim.apply_text(conv, a, su)))
            t["changes"], t["held"], t["actions"] = res["changes"], res["held"], res["actions"]
            moved = loan_sim.sync_answers(conv, a, t["changes"])
            nxt = _pending(conv, a)
            if sim_notes and loan_sim.status(conv, a, nxt) == "confirmed":
                conf = loan_sim.confirmed_params(conv, a)
                if conf and loan_sim.lp.issues(loan_sim.product(conv, a), conf["amount"], conf["term"], conf.get("asset_price")):
                    conv["focus"] = loan_sim.amount_field(conv, a)      # the changed scenario needs a re-confirmation
                    nxt = _pending(conv, a)
            intro_next = _sim_question(nxt, conv, a) and not loan_sim._sim(conv)["shown"]
            t["ack"] = _ack(t["changes"], a, conv, frozenset({"purpose", "company_purpose"}) if intro_next else frozenset())
            _english(t, "ack", lambda: EN.ack(t["changes"], a, conv, frozenset({"purpose", "company_purpose"})
                                              if intro_next else frozenset()))
            sim_text, sim_acts = loan_sim.notes_text(conv, a, sim_notes, nxt)
            if moved and loan_sim.status(conv, a, nxt) == "confirmed" and not sim_notes:
                sim_text = loan_sim.monthly_sentence(conv, a)
            _english(t, "sim", lambda: EN.monthly_sentence(conv, a) if moved and loan_sim.status(conv, a, nxt) == "confirmed"
                     and not sim_notes else EN.notes_text(conv, a, sim_notes, nxt))
            t["sim_text"], t["sim_touch"] = sim_text, bool(sim_notes or moved)
            t["actions"] += sim_acts
            if t["held"]:
                t["ack"] = (t["ack"] + " " if t["ack"] else "") + (
                    f"הבנתי, {_and([_value_he(k, conv['held'][k], a) for k in t['held']])}. אשמור את זה להמשך.")
            for qid, msg in res["rejected"]:
                t["issues"].append(msg)
                t["clarifying"] = t["clarifying"] or qid == pending
                t["sim_touch"] = t["sim_touch"] or (qid in loan_sim.SIM_FIELDS and loan_sim.applies(conv, a))
            for english in res["rejected_en"]:
                _english(t, "issues", lambda: english)
            for qid, old, new in res["conflicts"]:
                t["issues"].append(f"רק לוודא, קודם רשמתי {_value_he(qid, old, a, short=True)}, ועכשיו הבנתי "
                                   f"{_value_he(qid, new, a, short=True)}. מה נכון?")
                t["actions"] += [{"label_he": _value_he(qid, new, a, short=True), "question_id": qid, "value": new},
                                 {"label_he": _value_he(qid, old, a, short=True), "question_id": qid, "value": old}]
                t["clarifying"] = True
                _english(t, "issues", lambda: EN.conflict(qid, old, new, a))
            for un in u["unclear"]:
                msg, acts = _unclear(un["field"], un.get("kind", ""), conv, a)
                t["issues"].append(msg)
                _english(t, "issues", lambda: EN.unclear(un["field"], un.get("kind", ""), conv, a))
                t["actions"] += acts
                t["clarifying"] = True
            for n in u["notes"]:
                if n["kind"] == "gross":
                    t["gross"] = True
                    t["issues"].append(_gross_text(_pending(conv, a)))
                    _english(t, "issues", lambda: EN.gross(_pending(conv, a)))
                elif n["kind"] in NOTE_TEXT:
                    t["issues"].append(NOTE_TEXT[n["kind"]](n))
                    _english(t, "issues", lambda: EN.NOTES[n["kind"]](n))
                    t["clarifying"] = t["clarifying"] or n["kind"] in CLARIFYING_NOTES
            for topic, q in u["topics"]:
                if topic == "calculate" and t["gross"]:
                    continue                       # the gross explanation already answers "can you compute from it?"
                if topic == "other_banking" and (t["changes"] or t["issues"] or t["sim_text"] or len(u["topics"]) > 1):
                    continue                       # no "no verified information" next to a real answer
                if topic == "change" and t["changes"]:
                    continue
                t["off_topic"] = t.get("off_topic") or topic == "off_topic"
                asked_now = _pending(conv, a)
                reply, acts = _answer(topic, q, a, conv, _pending(conv, a))
                if reply:
                    t["answers"].append(reply)
                    _english(t, "answers", lambda: EN.answer(topic, q, a, conv, asked_now))
                t["actions"] += acts
            t["interrupted"] = bool(t["issues"] or t["answers"] or t["sim_text"])
            if t["changes"]:
                t["ind_event"], t["ind_snap"], t["ind_text"] = _indication_event(conv, a)
            if not (t["changes"] or t["held"] or t["issues"] or t["answers"] or t["sim_text"] or t["sim_touch"]):
                greet = nlu.normalize(_parser_text(text, pending, lang) if lang == "en" and text else customer).strip("!.,? ")
                if greet in ("שלום", "היי", "הי", "בוקר טוב", "ערב טוב", "אהלן"):
                    t["answers"].append("שלום!")
                    _english(t, "answers", lambda: "Hello!")
                elif greet.startswith("תודה"):
                    t["answers"].append("בשמחה.")
                    _english(t, "answers", lambda: "You're welcome.")
                elif greet not in ("נמשיך", "כן נמשיך", "בוא נמשיך", "בואו נמשיך", "המשך", "יאללה", "אוקיי", "בסדר", "כן"):
                    t["answers"].append(_not_understood(pending))
                    _english(t, "answers", lambda: EN.not_understood(pending))
                    t["clarifying"] = True
                t["interrupted"] = True
        t["next"] = _pending(conv, a)
        if t["next"] is None:
            sig = db.jdump(_v2(conv, a))
            if conv.get("summary_for") != sig:
                t["summary_text"] = ("עדכנתי, הסיכום למטה מעודכן." if conv.get("summary_for") else
                                     "סיימנו! ריכזתי למטה את כל הפרטים ואת המסמכים שיידרשו, אפשר לעבור עליהם, "
                                     "לשנות ולאשר. פתיחת הבקשה אינה אישור הלוואה.")
                conv["summary_for"] = sig

        reply_text, reply_engine = None, "rules"
        # a turn that carries scenario figures is worded by the deterministic composer: the numbers come from the engine
        # an English session gets the deterministic English reply (the model words Hebrew only)
        if use_llm_reply and not t["edit"] and not t["sim_text"] and lang != "en":
            facts = _facts(t, conv, a, customer)
            if _candidate_ok(u, t, conv, a, facts):
                reply_text, reply_engine = u["candidate"], "llm"     # one call: the interpretation's own reply
            else:
                candidate = llm.reply(facts, conv, draft_id)
                if candidate and _llm_reply_ok(candidate, t):
                    reply_text, reply_engine = candidate, "llm"
        if reply_text is None:
            reply_text = _compose_rules(t, conv, a)
        reply_lang = _said(lang, (lambda: EN.compose(t, conv, a)) if t["_en"] is not None else None)
        asked = t["next"] if (t["next"] and not t["clarifying"]) else None
        # the card travels with the reply while it is the open question, and whenever this turn changed the scenario
        attach = _sim_question(t["next"], conv, a) or t["sim_touch"] or conv.pop("sim_touch", False)
        sim_snap = loan_sim.snapshot(conv, a, t["next"]) if attach else None
        if sim_snap:
            loan_sim._sim(conv)["shown"] += 1
        _say(conv, reply_text, question_id=asked, indication=t["ind_snap"], insight=t["ind_event"],
             actions=t["actions"][:4], engine=reply_engine, understood_by=engine,
             llm_calls=str(conv.get("llm_calls", 0) - calls_at_start), simulator=sim_snap, **reply_lang)
        if asked:
            conv["asked"] = asked
        elif t["next"] is None:
            conv["asked"] = None
        if turn_id:
            conv["turns"].append(turn_id)
        _save(draft_id, conv)
    return view(draft_id, lang)


def save_simulation(draft_id: str, draft: dict, lang: Optional[str] = None) -> dict[str, Any]:
    """The card's unconfirmed scenario while the customer explores it: no message, no answer, no model call. Returns
    the server's own evaluation of it (the card computes the same figures locally for instant feedback)."""
    with _lock:
        row, a, conv = _load(draft_id, lang)
        if row["status"] != "draft":
            raise OnboardingError("הבקשה כבר נפתחה, אי אפשר לשנות את התשובות", 409)
        if not loan_sim.applies(conv, a):
            raise OnboardingError("עוד אין סימולציה לשמור", 409)
        loan_sim.save_draft(conv, a, draft)
        _save(draft_id, conv)
        return i18n.localized(lang, {"simulation": loan_sim.view(conv, a, _pending(conv, a))}, EN.simulation)


def annotate_case(draft_id: str, case_id: str) -> None:
    """Store the loan category the customer chose on the created case (the questionnaire knows only the entity)."""
    row = onboarding._row(draft_id)
    conv = db.jload(row.get("conversation")) or {}
    loan = _loan(conv, onboarding._clean_answers(row["answers"]))
    app_row = db.one("SELECT application FROM demo_applications WHERE case_id=?", (case_id,))
    if not app_row or not loan.get("type"):
        return
    application = db.jload(app_row["application"])
    application["loan_category"] = loan["type"]
    application["business_form"] = loan.get("form")
    sim = loan_sim.for_case(conv, onboarding._clean_answers(row["answers"]))
    if sim:
        application.setdefault("loan", {})["simulation"] = sim
    with db.tx() as c:
        c.execute("UPDATE demo_applications SET application=? WHERE case_id=?", (db.jdump(application), case_id))
