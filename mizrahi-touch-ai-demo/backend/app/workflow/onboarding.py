"""The new-customer questionnaire (JEEN chat on /customer/apply): a short, deterministic Hebrew interview that captures
the structured profile the document policy composes from, then creates the case on the customer's confirmation.

No model is involved: the questions, their order and conditions are code, and the requirements shown in the summary
come from the published loan policy (`requirements.preview`) — the same composition the prepared cases use. A draft is
not a case: nothing here reaches the bank adapter, the follow-up engine or the reviewer until it is confirmed, and a
confirmed draft always answers with the one case it created."""
from __future__ import annotations

import re
import secrets
import threading
from typing import Any, Callable

from .. import db
from ..bank import mock_bank
from ..policy import store
from ..util import now_iso
from . import requirements

MAX_DRAFTS = 500
ID_PROMPT = "מה מספר תעודת הזהות שלך? (9 ספרות; בהדגמה מתקבל גם מזהה סינתטי בצורה DEMO-ID-201)"
ID_QUESTIONS = ("national_id", "co_national_id", "signatory_id")
_DEMO_ID = re.compile(r"^DEMO-ID-\d{3}$")
MAX_CASES = 200
_NAME = re.compile(r"^[^<>{}\\]{2,30}$")
_confirm_lock = threading.Lock()


class OnboardingError(ValueError):
    def __init__(self, message_he: str, status: int = 422):
        super().__init__(message_he)
        self.message_he, self.status = message_he, status


def _purposes(entity: str) -> list[dict]:
    pol, _ = store.policy()
    return [{"value": k, "label_he": p.label_he} for k, p in pol.product.purposes.items() if p.entity == entity]


INCOME = [{"value": "salaried", "label_he": "שכיר/ה"}, {"value": "self_employed", "label_he": "עצמאי/ת"}]
REGISTRATION = [{"value": "vat_exempt", "label_he": "עוסק פטור"}, {"value": "vat_registered", "label_he": "עוסק מורשה"}]
YES_NO = [{"value": "yes", "label_he": "כן, יש לווה נוסף"}, {"value": "no", "label_he": "לא, רק אני"}]
NET = [{"value": v, "label_he": f"כ־{v:,} ₪"} for v in (8000, 12000, 16000, 22000)]
AMOUNTS = [{"value": v, "label_he": f"{v:,} ₪"} for v in (50000, 80000, 120000, 180000)]
BUSINESS_AMOUNTS = [{"value": v, "label_he": f"{v:,} ₪"} for v in (150000, 300000, 500000)]
PAYMENTS = [{"value": v, "label_he": f"{v} תשלומים"} for v in (36, 48, 60, 84)]


def _individual(a: dict) -> bool:
    return a.get("entity") == "individual"


def _co(a: dict) -> bool:
    return _individual(a) and a.get("co_borrower") == "yes"


# (id, kind, prompt, options, applies). Kinds: choice · multi · name · text · number (with suggested chips).
QUESTIONS: list[tuple[str, str, str, Callable[[], list[dict]] | list[dict], Callable[[dict], bool]]] = [
    ("entity", "choice", "שלום! אני העוזר של טפחות טאצ׳. נתחיל בקצרה: עבור מי הבקשה?",
     [{"value": "individual", "label_he": "הלוואה פרטית — עבורי (או עבורי ועבור לווה נוסף)"},
      {"value": "company", "label_he": "מימון לחברה בע״מ שאני מורשה החתימה בה"}], lambda a: True),
    ("name", "name", "איך קוראים לך?", [], _individual),
    ("national_id", "text", ID_PROMPT, [], _individual),
    ("purpose", "choice", "מה מטרת ההלוואה?", lambda: _purposes("individual"), _individual),
    ("income", "multi", "מאיפה ההכנסה שלך? אפשר לבחור יותר מאחת.", INCOME, _individual),
    ("registration", "choice", "איך העסק רשום במע״מ?", REGISTRATION,
     lambda a: _individual(a) and "self_employed" in (a.get("income") or [])),
    ("net", "number", "מה ההכנסה החודשית נטו שלך, בערך? (הצהרה בלבד — אינה מאומתת)", NET, _individual),
    ("co_borrower", "choice", "האם יש לווה נוסף בבקשה — מישהו שיחתום איתך על ההלוואה?", YES_NO, _individual),
    ("co_name", "name", "איך קוראים ללווה הנוסף?", [], _co),
    ("co_national_id", "text", "ומה מספר תעודת הזהות של הלווה הנוסף?", [], _co),
    ("co_income", "multi", "מאיפה ההכנסה של הלווה הנוסף?", INCOME, _co),
    ("co_registration", "choice", "איך העסק של הלווה הנוסף רשום במע״מ?", REGISTRATION,
     lambda a: _co(a) and "self_employed" in (a.get("co_income") or [])),
    ("co_net", "number", "מה ההכנסה החודשית נטו של הלווה הנוסף, בערך?", NET, _co),
    ("accounts", "choice", "האם יש לכם חשבון עו״ש משותף?",
     [{"value": "joint", "label_he": "כן, חשבון משותף לשנינו"}, {"value": "separate", "label_he": "לא, לכל אחד חשבון משלו"}], _co),
    ("company_name", "text", "מה שם החברה?", [], lambda a: a.get("entity") == "company"),
    ("signatory", "name", "מי מורשה החתימה שמגיש את הפנייה?", [], lambda a: a.get("entity") == "company"),
    ("signatory_id", "text", "מה מספר תעודת הזהות של מורשה החתימה?", [], lambda a: a.get("entity") == "company"),
    ("company_purpose", "choice", "למה החברה צריכה את המימון?", lambda: _purposes("company"),
     lambda a: a.get("entity") == "company"),
    ("amount", "number", "איזה סכום מבקשים?", AMOUNTS, _individual),
    ("business_amount", "number", "איזה סכום מימון מבקשים?", BUSINESS_AMOUNTS, lambda a: a.get("entity") == "company"),
    ("payments", "choice", "בכמה תשלומים?", PAYMENTS, lambda a: "entity" in a),
]
BY_ID = {q[0]: q for q in QUESTIONS}
NUMBER_BOUNDS = {"net": (0, 200000), "co_net": (0, 200000), "amount": (5000, 250000), "business_amount": (20000, 3000000)}


def _options(q: tuple) -> list[dict]:
    return q[3]() if callable(q[3]) else q[3]


def _applicable(answers: dict) -> list[tuple]:
    return [q for q in QUESTIONS if q[4](answers)]


def _clean_answers(answers: dict) -> dict:
    """Only the answers of questions that still apply (a correction can make a later branch irrelevant). A condition
    reads only earlier questions, so one pass in question order is enough."""
    out: dict = {}
    for q in QUESTIONS:
        if q[0] in answers and q[4](out):
            out[q[0]] = answers[q[0]]
    return out


def _validate(qid: str, value: Any) -> Any:
    q = BY_ID.get(qid)
    if not q:
        raise OnboardingError("שאלה לא מוכרת")
    kind = q[1]
    allowed = [o["value"] for o in _options(q)]
    if kind == "choice":
        if value not in allowed:
            raise OnboardingError("נא לבחור אחת מהאפשרויות")
        return value
    if kind == "multi":
        vals = [v for v in allowed if v in (value or [])]
        if not vals or len(vals) != len(set(value or [])):
            raise OnboardingError("נא לבחור לפחות מקור הכנסה אחד")
        return vals
    if kind == "number":
        lo, hi = NUMBER_BOUNDS[qid]
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise OnboardingError("נא להזין מספר") from None
        if not lo <= n <= hi:
            raise OnboardingError(f"הסכום צריך להיות בין {lo:,} ל־{hi:,} ₪")
        return n
    if kind == "name":
        first, last = (" ".join(str((value or {}).get(k, "")).split()) for k in ("first", "last"))
        if not (_NAME.match(first) and _NAME.match(last)):
            raise OnboardingError("נא להזין שם פרטי ושם משפחה (2–30 תווים)")
        return {"first": first, "last": last}
    text = " ".join(str(value or "").split())
    if qid in ID_QUESTIONS:
        from ..review import deterministic as det
        text = text.replace(" ", "").upper() if text.upper().startswith("DEMO") else text.replace("-", "").replace(" ", "")
        if not (_DEMO_ID.match(text) or (text.isdigit() and len(text) == 9 and det.israeli_id_check(text) == "valid")):
            raise OnboardingError("מספר הזהות אינו תקין (9 ספרות עם ספרת ביקורת, או מזהה הדגמה DEMO-ID-XXX)")
        return text
    if not 2 <= len(text) <= 60 or any(ch in text for ch in "<>{}\\"):
        raise OnboardingError("נא להזין 2–60 תווים")
    return text


def _answer_he(qid: str, value: Any) -> str:
    q = BY_ID[qid]
    if q[1] == "name":
        return f"{value['first']} {value['last']}"
    labels = {o["value"]: o["label_he"] for o in _options(q)}
    if q[1] == "multi":
        return " + ".join(labels.get(v, v) for v in value)
    if q[1] == "number":
        return labels.get(value) or (f"{value:,} ₪" if qid != "payments" else str(value))
    return labels.get(value, str(value))


def build_case(answers: dict, case_id: str, display_number: str, persona_id: str) -> dict:
    """The synthetic bank-side case for a completed questionnaire (also used, unsaved, for the summary preview)."""
    a = _clean_answers(answers)
    pol, _ = store.policy()
    if a["entity"] == "company":
        purpose = pol.product.purposes[a["company_purpose"]]
        sig = a["signatory"]
        borrower = mock_bank._person("BRW-A", sig["first"], sig["last"], a["signatory_id"], "authorized_signatory", [], 0)
        return mock_bank._case(
            case_id, display_number, f"{purpose.label_he} — {a['company_name']}", [borrower],
            mock_bank._loan(a["company_purpose"], purpose.label_he, a["business_amount"], a["payments"], business=True),
            [{"account_id": "ACC-1", "label_he": "חשבון עסקי של החברה", "bank_he": "מזרחי־טפחות", "holders": ["COMPANY"]}],
            submitted_at=now_iso(), customer_started=True, persona_id=persona_id, applicant_type="company",
            banker_assisted=True, profile_label_he="חברה בע״מ",
            company={"name_he": a["company_name"], "company_number": f"DEMO-CO-{display_number}",
                     "signatory_he": f"{sig['first']} {sig['last']}", "signatory_role_he": "מורשה חתימה"})
    purpose = pol.product.purposes[a["purpose"]]

    def person(bid: str, prefix: str, role: str) -> dict:
        name = a[f"{prefix}name"]
        return mock_bank._person(bid, name["first"], name["last"], a[f"{prefix}national_id"], role,
                                 a[f"{prefix}income"], a[f"{prefix}net"], registration=a.get(f"{prefix}registration"))

    borrowers = [person("BRW-A", "", "primary")]
    accounts = mock_bank._accounts(["BRW-A"])
    if a.get("co_borrower") == "yes":
        borrowers.append(person("BRW-B", "co_", "co_borrower"))
        accounts = (mock_bank._accounts(["BRW-A", "BRW-B"]) if a["accounts"] == "joint"
                    else mock_bank._accounts(["BRW-A"], ["BRW-B"]))
        if a["accounts"] == "joint":
            accounts[0]["label_he"] = "חשבון עו״ש משותף"
    label = " ו".join(requirements.applicant_profile_he(b) for b in borrowers)
    return mock_bank._case(case_id, display_number, f"{pol.product.label_he} · {purpose.label_he}", borrowers,
                           mock_bank._loan(a["purpose"], purpose.label_he, a["amount"], a["payments"]), accounts,
                           submitted_at=now_iso(), customer_started=True, persona_id=persona_id,
                           applicant_type="individual", profile_label_he=label)


def _row(draft_id: str) -> dict:
    row = db.one("SELECT * FROM onboarding_drafts WHERE draft_id=?", (draft_id,))
    if not row:
        raise OnboardingError("הטיוטה לא נמצאה — אפשר להתחיל בקשה חדשה", 404)
    return {**row, "answers": db.jload(row["answers"]) or {}}


def view(draft_id: str) -> dict[str, Any]:
    row = _row(draft_id)
    answers = _clean_answers(row["answers"])
    applicable = _applicable(answers)
    pending = next((q for q in applicable if q[0] not in answers), None)
    out: dict[str, Any] = {
        "draft_id": draft_id, "status": row["status"], "case_id": row["case_id"], "updated_at": row["updated_at"],
        "asked": [{"question_id": q[0], "prompt_he": q[2], "kind": q[1], "answer": answers[q[0]],
                   "answer_he": _answer_he(q[0], answers[q[0]])} for q in applicable if q[0] in answers],
        "next": {"question_id": pending[0], "kind": pending[1], "prompt_he": pending[2], "options": _options(pending)}
        if pending else None,
        "summary": None,
        "note_he": "השאלות קובעות רק אילו מסמכים נדרשים. הן אינן בדיקת זכאות ואינן הצעת אשראי.",
    }
    if pending is None and answers:
        case = build_case(answers, "PREVIEW", "000000000", "PREVIEW")
        reqs, label = requirements.preview(case)
        out["summary"] = {"profile": requirements.profile(case), "policy_version": label,
                          "title_he": case["title_he"], "loan": case["loan"],
                          "requirements": [{k: r.get(k) for k in ("code", "title_he", "family", "family_he", "owner_he",
                                                                   "owner_type", "why_he", "alternatives_he", "intake",
                                                                   "required")} for r in reqs]}
    return out


def start() -> dict[str, Any]:
    if (db.one("SELECT COUNT(*) AS n FROM onboarding_drafts") or {"n": 0})["n"] >= MAX_DRAFTS:
        raise OnboardingError("הגעתם למספר המרבי של טיוטות הדגמה בסביבה זו")
    draft_id = f"OBD-{secrets.token_hex(6).upper()}"
    now = now_iso()
    with db.tx() as c:
        c.execute("INSERT INTO onboarding_drafts(draft_id, created_at, updated_at, status, answers) VALUES (?,?,?,?,?)",
                  (draft_id, now, now, "draft", db.jdump({})))
    return view(draft_id)


def answer(draft_id: str, question_id: str, value: Any) -> dict[str, Any]:
    """Record, clear (value None) or correct one answer. Later answers are kept while their question is hidden, so
    correcting the income source does not erase the VAT registration; only answers whose question applies are used."""
    row = _row(draft_id)
    if row["status"] != "draft":
        raise OnboardingError("הבקשה כבר נפתחה — אי אפשר לשנות את התשובות", 409)
    if question_id not in BY_ID:
        raise OnboardingError("שאלה לא מוכרת")
    answers = dict(row["answers"])
    if value is None:
        answers.pop(question_id, None)
    else:
        if not BY_ID[question_id][4](_clean_answers(answers)):
            raise OnboardingError("השאלה אינה רלוונטית לתשובות הקודמות")
        answers[question_id] = _validate(question_id, value)
        if question_id == "co_national_id" and answers[question_id] == answers.get("national_id"):
            raise OnboardingError("ללווה הנוסף צריך להיות מספר זהות משלו")
    with db.tx() as c:
        c.execute("UPDATE onboarding_drafts SET answers=?, updated_at=? WHERE draft_id=? AND status='draft'",
                  (db.jdump(answers), now_iso(), draft_id))
    return view(draft_id)


def confirm(draft_id: str) -> tuple[str, bool]:
    """Create the case once. Repeated or concurrent confirmations return the same case (created=False)."""
    with _confirm_lock:
        row = _row(draft_id)
        if row["case_id"]:
            return row["case_id"], False
        if view(draft_id)["next"] is not None:
            raise OnboardingError("עוד לא ענינו על כל השאלות", 409)
        count = (db.one("SELECT COUNT(*) AS n FROM demo_applications") or {"n": 0})["n"]
        if count >= MAX_CASES:
            raise OnboardingError("הגעתם למספר המרבי של בקשות הדגמה בסביבה זו")
        suffix = secrets.token_hex(2).upper()
        case_id = f"DEMO-LN-{count + 1:04d}-{suffix}"
        case = build_case(row["answers"], case_id, f"4388{secrets.randbelow(90000) + 10000}", f"PRS-NEW-{suffix}")
        case["stage_index"] = 1
        case["onboarding_draft_id"] = draft_id
        now = now_iso()
        with db.tx() as c:
            c.execute("INSERT INTO demo_applications(case_id, created_at, application) VALUES (?,?,?)",
                      (case_id, now, db.jdump(case)))
            c.execute("UPDATE onboarding_drafts SET status='confirmed', case_id=?, updated_at=? WHERE draft_id=?",
                      (case_id, now, draft_id))
        return case_id, True


def audit_detail(draft_id: str) -> dict:
    a = _clean_answers(_row(draft_id)["answers"])
    return {"source": "onboarding", "draft_id": draft_id, "entity": a.get("entity"),
            "purpose": a.get("purpose") or a.get("company_purpose"), "income": a.get("income"),
            "registration": a.get("registration"), "co_borrower": a.get("co_borrower") == "yes",
            "co_income": a.get("co_income"), "accounts": a.get("accounts"), "payments": a.get("payments")}
