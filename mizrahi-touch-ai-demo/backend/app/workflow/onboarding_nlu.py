"""Deterministic Hebrew understanding for the conversational questionnaire (V2). No model is called.

`understand(text, answers, pending)` turns one customer message into candidate answers for the questionnaire's own
question ids, the questions the customer asked, and what it could not settle. Candidates are only proposals: every
one is validated by `onboarding.answer`, exactly like a quick reply. What this parser does not recognise is reported
as not understood — it never guesses a value to keep the conversation moving.

Coverage is keyword and pattern based: digits ("80,000", "16 אלף", "80K"), common Hebrew number words up to
millions, ranges (the lower bound is kept), income sources with simple negation, VAT registration, purposes,
co-borrower phrases, names after "קוראים לי" / "שמי" (or as the answer to a name question) and ID numbers."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

HEB = "\u05d0-\u05ea"
_PREFIX = "והבלמשכ"
_TOKEN = re.compile(rf"\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?|[A-Za-z{HEB}][A-Za-z{HEB}\"']*|[?!.,;:\n]")
_PUNCT = set("?!.,;:\n")
_ID = re.compile(r"\bDEMO[\s-]*ID[\s-]*(\d{3})\b|(?<!\d)(\d{9})(?!\d)|(?<!\d)(\d{2,3}[-\s]\d{3}[-\s]\d{3,4})(?!\d)",
                 re.IGNORECASE)

UNITS = {"אחד": 1, "אחת": 1, "שניים": 2, "שתיים": 2, "שני": 2, "שתי": 2, "שלוש": 3, "שלושה": 3, "ארבע": 4,
         "ארבעה": 4, "חמש": 5, "חמישה": 5, "שש": 6, "שישה": 6, "שבע": 7, "שבעה": 7, "שמונה": 8, "תשע": 9,
         "תשעה": 9, "עשר": 10, "עשרה": 10}
TENS = {"עשרים": 20, "שלושים": 30, "ארבעים": 40, "חמישים": 50, "שישים": 60, "שבעים": 70, "שמונים": 80, "תשעים": 90}
CONSTRUCT = {"שלושת": 3, "ארבעת": 4, "חמשת": 5, "ששת": 6, "שבעת": 7, "שמונת": 8, "תשעת": 9, "עשרת": 10}
THOUSAND = {"אלף", "אלפים", "א'", "K", "k"}

NET_KW = {"מרוויח", "מרוויחה", "מרויח", "מרויחה", "מרוויחים", "משתכר", "משתכרת", "משכורת", "שכר", "נטו", "הכנסה",
          "הכנסות", "מכניס", "מכניסה", "מכניסים", "נכנס", "נכנסים", "חודש", "חודשי", "חודשית", "מקבל", "מקבלת"}
GROSS_KW = {"ברוטו"}
AMOUNT_KW = {"הלוואה", "הלוואת", "ללוות", "לווות", "מימון", "לממן", "סכום", "צריך", "צריכה", "צריכים", "רוצה",
             "רוצים", "מבקש", "מבקשת", "מבקשים", "לקנות", "לרכוש", "קונה", "עולה", "עולים", "רכב", "מכונית", "אוטו",
             "שיפוץ", "חתונה", "מחיר", "אירוע"}
CO_KW = {"בעלי", "אשתי", "זוגי", "זוגתי", "הזוג", "שותפה", "הלווה", "הנוסף", "הוא", "היא", "שלו", "שלה"}
SAL_KW = {"שכיר", "שכירה", "שכירים", "משכורת", "תלוש", "תלושי", "תלושים", "מועסק", "מועסקת"}
WORKER_KW = {"עובד", "עובדת"}
SELF_KW = {"עצמאי", "עצמאית", "עצמאים", "עסק", "עסקים", "פרילנס", "פרילנסר", "פרילנסרית"}
NEG_KW = {"לא", "אינני", "איני", "אינו", "אינה", "בלי", "ללא"}
PAST_KW = {"הייתי", "בעבר", "פעם", "הייתה", "היה"}
CORRECTION = re.compile(r"בעצם|במקום|טעיתי|לשנות|לתקן|לעדכן|כבר לא|(?:^|\s)רק(?=\s)|(?:^|\s)לא\s+\S+\s*,?\s*(?:אלא|אני)")
SIDE_JOBS = re.compile(r"מהצד|עבודות צד|עבודות נוספות|ג'וב|פה ושם|השלמות הכנסה|עבודות מזדמנות")
UNSURE = re.compile(r"לא (?:ממש |כל כך )?(?:יודע|יודעת|בטוח|בטוחה)|איך להגדיר|לא ברור לי")
BUSINESS_LOAN = re.compile(r"(?:^|\s)(?:ו?ה?הלוואה\s+)?עסקית|(?:^|\s)(?:ל|בשביל ה|עבור ה|מימון ל)עסק(?: שלי)?(?=$|[\s,.!?])"
                           r"|(?:^|\s)עסקי(?=$|[\s,.!?])")
PERSONAL_LOAN = re.compile(r"(?:^|\s)(?:ו?ה?הלוואה\s+)?(?:פרטית|אישית)|(?:^|\s)(?:פרטי|לעצמי|בשבילי|עבורי)(?=$|[\s,.!?])")
COMPANY = re.compile(r"חברה\s*בע\"?מ|בע\"מ|חברה בעמ|החברה שלי|(?:^|\s)לחברה(?=$|[\s,.!?])|מורש[הת] חתימה")
OTHER_INCOME_KW = {"פנסיה", "קצבה", "קצבת", "פנסיונר", "פנסיונרית", "גמלה", "שכירות", "השקעות", "דמי"}
PURPOSE_KW = {"car": {"רכב", "מכונית", "אוטו", "רכבים", "מכוניות"},
              "renovation": {"שיפוץ", "לשפץ", "שיפוצים", "משפץ", "משפצים", "משפצת"},
              "celebration": {"חתונה", "אירוע", "מצווה", "ברית", "חגיגה"},
              "other": {"לימודים", "חופשה", "טיול", "תואר", "קורס"}}
COMPANY_PURPOSE_KW = {"business_equipment": {"ציוד", "מכונות", "מכשור"},
                      "working_capital": {"חוזר", "תזרים", "מלאי", "שוטף", "שוטפת"}}
COMPANY_PHRASES = ("לחברה", "החברה שלי", "בע\"מ", "מורשה חתימה", "מורשת חתימה", "עבור החברה", "בשביל החברה",
                   "מימון לחברה", "חברה בעמ")
PERSONAL_PHRASES = ("פרטית", "פרטי", "עבורי", "בשבילי", "לעצמי", "בשבילנו", "עבורנו")
CO_YES_PHRASES = ("לווה נוסף", "עוד לווה", "בן זוג", "בת זוג", "בן הזוג", "בת הזוג", "בן זוגי", "בת זוגי", "אשתי",
                  "בעלי", "יחד עם", "ביחד עם", "זוגתי")
CO_NO_PHRASES = ("רק אני", "לבד", "לבדי", "בלי לווה", "אין לווה", "רק על שמי", "אני בלבד")
YES = {"כן", "בטח", "נכון", "בהחלט", "כמובן", "יש"}
NO = {"לא", "אין", "שלילי"}
INTERROGATIVE = {"למה", "מה", "איך", "כמה", "אפשר", "האם", "מתי", "מי", "איפה", "מדוע", "בשביל", "איזה", "אילו",
                 "אם", "ומה", "ולמה", "ואיך", "וכמה", "ואפשר"}
NAME_LEADS = ("קוראים לי", "שמי", "השם שלי הוא", "השם שלי", "קוראים לו", "קוראים לה", "השם שלו", "השם שלה")
STOP = (NET_KW | AMOUNT_KW | SAL_KW | SELF_KW | WORKER_KW | NEG_KW | YES | INTERROGATIVE | CO_KW | GROSS_KW
        | {"אני", "גם", "רק", "יש", "לי", "של", "עם", "על", "את", "זה", "בעצם", "שלום", "היי", "הי", "תודה", "מעוניין",
           "מעוניינת", "מחפש", "מחפשת", "בערך", "פטור", "מורשה", "עוסק", "עוסקת", "בן", "בת", "רוצה", "צריך"})
CO_QUESTIONS = ("co_name", "co_national_id", "co_income", "co_registration", "co_net")


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = t.replace("\u05be", " ").replace("–", " ").replace("—", " ")
    t = re.sub(r"[\u0591-\u05c7]", "", t)
    for a, b in (("״", '"'), ("”", '"'), ("“", '"'), ("׳", "'"), ("’", "'"), ("₪", " ₪ ")):
        t = t.replace(a, b)
    return " ".join(t.split())


def stems(tok: str) -> set[str]:
    out = {tok}
    for n in (1, 2):
        if len(tok) - n >= 2 and all(c in _PREFIX for c in tok[:n]):
            out.add(tok[n:])
    return out


def _is(tok: str, words: set[str]) -> bool:
    return bool(stems(tok) & words)


def _has_phrase(text: str, phrases) -> bool:
    return any(re.search(rf"(?:^|[\s,.;:!?])[{_PREFIX}]{{0,2}}{re.escape(p)}(?=$|[\s,.;:!?])", text) for p in phrases)


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def _num(tok: str) -> float | None:
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", tok):
        return float(tok.replace(",", ""))
    return None


def _word_value(tok: str) -> tuple[str, int] | None:
    for s in sorted(stems(tok), key=len, reverse=True):
        if s in UNITS:
            return "unit", UNITS[s]
        if s in TENS:
            return "unit", TENS[s]
        if s in CONSTRUCT:
            return "construct", CONSTRUCT[s]
        if s == "מאה":
            return "unit", 100
        if s == "מאתיים":
            return "unit", 200
        if s == "מאות":
            return "hundreds", 0
        if s == "אלפיים":
            return "thousands2", 0
        if s in ("אלף", "אלפים"):
            return "thousand", 0
        if s == "מיליון":
            return "million", 0
        if s == "חצי":
            return "half", 0
    return None


def numbers(toks: list[str]) -> list[dict]:
    """Every number in the message: {value, start, end, raw_small, range_high} (end is exclusive, after a multiplier)."""
    out: list[dict] = []
    i = 0
    while i < len(toks):
        v = _num(toks[i])
        if v is not None:
            start, j, mult = i, i + 1, 1
            if j < len(toks) and (toks[j] in THOUSAND or _is(toks[j], {"אלף", "אלפים"})):
                mult, j = 1000, j + 1
            elif j < len(toks) and _is(toks[j], {"מיליון"}):
                mult, j = 1_000_000, j + 1
            out.append({"value": int(round(v * mult)), "start": start, "end": j, "multiplied": mult > 1})
            i = j
            continue
        w = _word_value(toks[i])
        if w and w[0] != "thousand" and not (w[0] == "half" and not (i + 1 < len(toks) and _is(toks[i + 1], {"מיליון"}))):
            start, total, cur, j, half = i, 0, 0, i, False
            while j < len(toks):
                w = _word_value(toks[j])
                if not w:
                    break
                kind, val = w
                if kind in ("unit", "construct"):
                    cur += val
                elif kind == "hundreds":
                    cur = (cur or 1) * 100
                elif kind == "thousands2":
                    total += 2000
                elif kind == "thousand":
                    total, cur = total + (cur or 1) * 1000, 0
                elif kind == "half":
                    half = True
                elif kind == "million":
                    total, cur = total + int((0.5 if half else (cur or 1)) * 1_000_000), 0
                j += 1
            value = total + cur
            if value:
                out.append({"value": value, "start": start, "end": j,
                            "multiplied": any(_word_value(t) and _word_value(t)[0] in ("thousand", "thousands2", "million")
                                              for t in toks[start:j])})
            i = max(j, i + 1)
            continue
        i += 1
    # "בין 10 ל־12 אלף" / "10-12 אלף": one range, the lower bound kept; a multiplier on the upper bound applies to both
    merged: list[dict] = []
    for n in out:
        prev = merged[-1] if merged else None
        if prev and n["start"] - prev["end"] <= 1 and (n["start"] == prev["end"] or _is(toks[prev["end"]], {"עד"})
                                                        or toks[prev["end"]] in ("ל", "-")):
            low = prev["value"] * (1000 if n["multiplied"] and not prev["multiplied"] else 1)
            merged[-1] = {"value": min(low, n["value"]), "start": prev["start"], "end": n["end"],
                          "multiplied": n["multiplied"], "range_high": max(low, n["value"])}
            continue
        merged.append(n)
    return merged


def _window(toks: list[str], start: int, end: int) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    before, after = [], []
    k = start - 1
    while k >= 0 and start - k <= 6 and toks[k] not in _PUNCT:
        before.append((start - k, toks[k]))
        k -= 1
    k = end
    while k < len(toks) and k - end < 3 and toks[k] not in _PUNCT:
        after.append((k - end + 1, toks[k]))
        k += 1
    return before, after


def _classify(toks: list[str], n: dict) -> str:
    nxt = toks[n["end"]] if n["end"] < len(toks) else ""
    if any(_is(toks[k], {"במקום"}) for k in range(max(0, n["start"] - 2), n["start"])):
        return "replaced"                                       # "120 אלף במקום 80": 80 is the old value
    if _is(nxt, {"תשלומים", "תשלום"}):
        return "payments"
    if _is(nxt, {"חודשים"}) and 6 <= n["value"] <= 120:
        return "payments"
    if _is(nxt, {"שנים", "שנה"}) and 1 <= n["value"] <= 10:
        return "years"
    before, after = _window(toks, n["start"], n["end"])
    best: dict[str, float] = {}
    for dist, tok in before:
        for cat, kw in (("gross", GROSS_KW), ("net", NET_KW), ("amount", AMOUNT_KW)):
            if _is(tok, kw):
                best[cat] = min(best.get(cat, 99), dist)
    for dist, tok in after:
        for cat, kw in (("gross", GROSS_KW), ("net", NET_KW), ("amount", AMOUNT_KW)):
            if _is(tok, kw):
                best[cat] = min(best.get(cat, 99), dist + 0.5)
    if "gross" in best and best["gross"] <= min(best.values()) + 1:
        return "gross"
    if not best:
        return "bare"
    return min(best, key=lambda c: best[c])


def _co_context(toks: list[str], n: dict) -> bool:
    before, _ = _window(toks, n["start"], n["end"])
    return any(_is(t, CO_KW) for _, t in before)


def _income(toks: list[str], text: str) -> tuple[set[str], set[str], bool]:
    """(positive sources, negated sources, unsupported source mentioned)."""
    pos, neg = set(), set()
    has_self = any(_is(t, SELF_KW) for t in toks) or bool(re.search(r"עוסק(ת)?\s+(פטור|מורשה)(?!\s+חתימה)", text))
    for i, t in enumerate(toks):
        src = None
        if _is(t, SAL_KW) or (_is(t, WORKER_KW) and not has_self):
            src = "salaried"
        elif _is(t, SELF_KW) or (_is(t, {"עוסק", "עוסקת"}) and i + 1 < len(toks) and _is(toks[i + 1], {"פטור", "מורשה"})):
            src = "self_employed"
        if not src:
            continue
        prev = [toks[k] for k in range(max(0, i - 2), i)]
        negated = any(p in NEG_KW or _is(p, {"אין"}) for p in prev[-1:]) or (len(prev) == 2 and prev[0] == "אין" and prev[1] == "לי")
        # "בעבר הייתי שכיר" describes a past job, not a current income source
        past = any(_is(toks[k], PAST_KW) for k in range(max(0, i - 3), i) if toks[k] not in _PUNCT)
        (neg if negated or past else pos).add(src)
    if re.search(r"(?:^|\s)(?:גם\s+וגם|שניהם|שתיהן|משניהם|שני\s+הסוגים)(?=$|[\s,.!?])", text):
        pos |= {"salaried", "self_employed"}
    other = any(_is(t, OTHER_INCOME_KW) for t in toks)
    return pos - neg, neg, other


def _registration(text: str) -> str | None:
    exempt = re.search(r"פטור", text)
    registered = re.search(r"מורשה(?!\s+חתימה)|מורשית", text)
    if exempt and not registered:
        return "vat_exempt"
    if registered and not exempt:
        return "vat_registered"
    return None


def _name(text: str, toks: list[str], expected: bool) -> tuple[dict | None, bool]:
    """(name, partial). With a name question pending a bare "מיכל ברק" is the answer; otherwise only after a lead."""
    lead = next((p for p in NAME_LEADS if p in text), None)
    if lead:
        rest = text.split(lead, 1)[1]
    elif expected:
        rest = re.sub(r"^(אני|זה|זאת)\s+", "", text)
    else:
        m = re.match(rf"^(?:היי|הי|שלום)?[\s,]*אני\s+([{HEB}]{{2,}})\s+([{HEB}]{{2,}})(?=$|[\s,.!]+(?:ו|$))", text)
        if not m or m.group(1) in STOP or m.group(2) in STOP:
            return None, False
        return {"first": m.group(1), "last": m.group(2)}, False
    words = re.findall(rf"[{HEB}A-Za-z'\"-]+", re.split(r"[,.!?;]| ו(?=[{HEB}])", rest.strip())[0])
    words = [w for w in words if w not in ("הוא", "היא")]
    # names are matched exactly against the stop list: stripping a "prefix" would read ברק as רק
    if lead is None and (len(words) > 3 or any(w in STOP for w in words)):
        return None, False
    if len(words) >= 2 and not any(w in STOP for w in words[:2]) and words[0] != words[1]:
        return {"first": words[0], "last": " ".join(words[1:3])}, False
    if len(words) == 1 and words[0] not in STOP:
        return None, True
    return None, False


def _clauses(text: str) -> list[tuple[str, bool]]:
    """[(clause, is_question)] — a question ends with "?" or starts with an interrogative."""
    out = []
    for m in re.finditer(r"[^?.!\n,;]+[?.!\n,;]*", text):
        c = m.group(0).strip()
        if not c.strip("?.!,; "):
            continue
        first = (tokens(c) or [""])[0]
        out.append((c, c.endswith("?") or first in INTERROGATIVE))
    return out


def is_question(text: str) -> bool:
    return any(q for _, q in _clauses(normalize(text)))


def understand(text: str, answers: dict, pending: str | None, as_statement: bool = False) -> dict[str, Any]:
    """Candidate answers and open points of one message. `answers` are the draft's cleaned answers. Values are read
    from statements only ("למה צריך לדעת אם אני עוסק פטור?" records nothing) unless `as_statement` — a change request
    such as "אפשר לשנות את הסכום ל־100 אלף?" carries its new value inside the question."""
    norm = normalize(text)
    clauses = _clauses(norm)
    statement = " , ".join(c.rstrip("?") for c, q in clauses if as_statement or not q)
    questions = [c for c, q in clauses if q]
    values: dict[str, Any] = {}
    notes: list[dict] = []
    if not statement:
        return {"values": values, "notes": notes, "questions": questions, "statement": "", "text": norm,
                "corrections": set()}
    co_target = pending in CO_QUESTIONS or (answers.get("co_borrower") == "yes" and _has_phrase(statement, CO_YES_PHRASES)
                                            and pending not in ("income", "net", "registration"))
    p = "co_" if co_target else ""

    # identity numbers first, then blank them so their digits are not read as amounts
    id_text = statement
    for m in _ID.finditer(statement):
        raw = f"DEMO-ID-{m.group(1)}" if m.group(1) else re.sub(r"[-\s]", "", m.group(2) or m.group(3))
        target = pending if pending in ("national_id", "co_national_id", "signatory_id") else (
            "national_id" if "national_id" not in answers and answers.get("entity") != "company" else None)
        if target:
            values[target] = raw
        id_text = id_text.replace(m.group(0), " ")
    toks = tokens(id_text)

    # loan type and business form — only when the customer names them: a car or a salary does not decide either
    company = bool(COMPANY.search(statement)) or (pending == "business_form" and _has_phrase(statement, ("חברה",)))
    personal = bool(PERSONAL_LOAN.search(statement))
    business = bool(BUSINESS_LOAN.search(statement)) or company
    if personal and not business:
        values["loan_type"] = "personal"
    elif business and not personal:
        values["loan_type"] = "business"
    if (values.get("loan_type") or answers.get("loan_type")) == "business":
        form = "company" if company else _registration(statement) if (pending == "business_form" or "עוסק" in statement) else None
        if form:
            values["business_form"] = form
    entity = "company" if (values.get("business_form") or answers.get("business_form")) == "company" else answers.get("entity")

    # purpose
    if entity == "company" or company:
        for k, kw in COMPANY_PURPOSE_KW.items():
            if any(_is(t, kw) for t in toks):
                values["company_purpose"] = k
                break
    else:
        hits = [k for k, kw in PURPOSE_KW.items() if any(_is(t, kw) for t in toks)]
        if pending == "purpose" and not hits and re.search(r"(?:^|\s)(?:אחר|אחרת|משהו אחר)(?=$|[\s,.!?])", statement):
            hits = ["other"]
        if len(hits) == 1:
            values["purpose"] = hits[0]
        elif len(hits) > 1:
            notes.append({"kind": "ambiguous_purpose"})

    # income sources and VAT registration
    pos, neg, other = _income(toks, statement)
    reg = _registration(statement) if entity != "company" else None
    if reg:
        pos.add("self_employed")
    target = f"{p}income"
    existing = list(answers.get(target) or [])
    side, unsure = bool(SIDE_JOBS.search(statement)), bool(UNSURE.search(statement))
    if (side or unsure) and "self_employed" not in pos and (pos or side or pending == target):
        # side jobs of unknown form, or "I don't know how to define myself": ask, record nothing about income
        notes.append({"kind": "income_side_jobs" if "salaried" in pos else "income_help", "field": target})
        pos, neg, reg = set(), set(), None
    if pos or neg:
        additive = bool(re.search(r"(?:^|\s)גם(?=\s)", statement)) and pending != target
        replace = not additive and (pending == target or bool(re.search(r"בעצם|טעיתי|(?:^|\s)רק(?=\s)|כבר לא", statement)))
        new = set(pos) if (replace and pos) else (set(existing) | pos) - neg
        ordered = [s for s in ("salaried", "self_employed") if s in new]
        if ordered and ordered != existing:
            values[target] = ordered
        elif not ordered and neg:
            notes.append({"kind": "no_income_left"})
    elif other:
        notes.append({"kind": "unsupported_income"})
    if reg:
        values[f"{p}registration"] = reg

    # co-borrower and accounts
    if entity != "company":
        short = len(toks) <= 4
        if pending == "co_borrower" and short and any(t in YES for t in toks) and not any(t in NO for t in toks):
            values["co_borrower"] = "yes"
        elif pending == "co_borrower" and short and toks and toks[0] in NO:
            values["co_borrower"] = "no"
        elif _has_phrase(statement, CO_NO_PHRASES):
            values["co_borrower"] = "no"
        elif _has_phrase(statement, CO_YES_PHRASES) and not re.search(r"(?:בלי|ללא|אין)\s+(?:לווה|בן|בת)", statement):
            if answers.get("co_borrower") != "yes":
                values["co_borrower"] = "yes"
        if pending == "accounts" or (answers.get("co_borrower") == "yes" or values.get("co_borrower") == "yes"):
            if re.search(r"נפרד|לכל אחד", statement):
                values["accounts"] = "separate"
            elif re.search(r"משותף", statement) and not re.search(r"(?:לא|אין)\s+(?:\S+\s+)?משותף", statement):
                values["accounts"] = "joint"
            elif pending == "accounts" and short and toks and toks[0] in YES:
                values["accounts"] = "joint"
            elif pending == "accounts" and short and toks and toks[0] in NO:
                values["accounts"] = "separate"

    # numbers
    by: dict[str, list[dict]] = {}
    for n in numbers(toks):
        cat = _classify(toks, n)
        if cat == "years":
            by.setdefault("payments", []).append({**n, "value": n["value"] * 12, "from_years": n["value"]})
            continue
        if cat == "replaced":
            continue
        if cat == "gross":
            notes.append({"kind": "gross", "value": n["value"]})
            continue
        if cat == "net":
            key = "co_net" if (co_target or _co_context(toks, n)) else "net"
        elif cat == "amount":
            key = "business_amount" if entity == "company" else "amount"
        elif cat == "payments":
            key = "payments"
        else:
            key = pending if pending in ("net", "co_net", "amount", "business_amount", "payments") else None
        if key is None:
            notes.append({"kind": "unplaced_number", "value": n["value"]})
            continue
        by.setdefault(key, []).append(n)
    for key, items in by.items():
        vals = {i["value"] for i in items}
        if len(vals) > 1:
            notes.append({"kind": "conflicting_numbers", "field": key, "values": sorted(vals)})
            continue
        n = items[0]
        v = n["value"]
        if key in ("amount", "net", "co_net") and not n.get("multiplied") and v <= (250 if key == "amount" else 200):
            v *= 1000
            notes.append({"kind": "assumed_thousands", "field": key, "value": v})
        if n.get("range_high"):
            notes.append({"kind": "range_low", "field": key, "value": v, "high": n["range_high"]})
        values[key] = v
    if pending == "payments" and "payments" not in values and "שנתיים" in statement:
        values["payments"] = 24

    # names (after numbers, so "מיכל ברק, 16 אלף נטו" keeps both)
    name_q = pending if pending in ("name", "co_name", "signatory") else None
    if name_q or "name" not in answers:
        name, partial = _name(statement.split(" , ")[0] if name_q else statement, toks, bool(name_q))
        if name:
            values[name_q or "name"] = name
        elif partial and name_q:
            notes.append({"kind": "partial_name"})

    # free-text questions (company name)
    if pending == "company_name" and not values:
        values["company_name"] = re.sub(r"^(?:שם החברה(?: הוא)?|קוראים לה|החברה נקראת)\s*", "", statement.strip(" ,"))
    corrections = set(values) if CORRECTION.search(statement) else set()
    if f"{p}income" in values and re.search(r"(?:^|\s)גם(?=\s)", statement):
        corrections.add(f"{p}income")                           # "יש לי גם עסק" adds a source on purpose
    return {"values": values, "notes": notes, "questions": questions, "statement": statement, "text": norm,
            "corrections": corrections}
