"""English understanding for the conversational questionnaire, without a model.

The questionnaire's deterministic parser (onboarding_nlu, loan_sim.understand, onboarding_chat._topic) reads Hebrew.
An English message is rewritten into the Hebrew cue words that parser already knows — "80k" → "80 אלף", "net" → "נטו",
"just me" → "רק אני", "how did you calculate" → "איך חישבת" — and the same, tested parser does the rest. Numbers, ID
numbers and anything not in the table pass through unchanged, so a value is never invented: a word the table does not
know simply does not count, and the assistant asks again. The customer's own words are stored as they wrote them; only
the copy handed to the parser is rewritten.

A pending name or company-name question is not rewritten (a surname such as "Price" stays a name)."""
from __future__ import annotations

import re

NO_REWRITE = {"name", "co_name", "signatory", "company_name"}

_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
          "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}
_WORD = "|".join(sorted(list(_UNITS) + list(_SCALES), key=len, reverse=True))
# a run of number words ("one hundred and twenty thousand", "forty-eight"); "and" only between two number words
_RUN = re.compile(rf"\b(?:{_WORD})(?:(?:[\s-]+|\s+and\s+)(?:{_WORD}))*\b", re.IGNORECASE)


def _words_value(run: str) -> int | None:
    """The value of a run of English number words, composed as spoken (hundred / thousand / million multiply); None for
    a run that is not one number ("five five"), so nothing is guessed."""
    total, current, last = 0, 0, None
    for w in re.split(r"[\s-]+", run.lower()):
        if w == "and":
            continue
        if w in _UNITS:
            v = _UNITS[w]
            if last == "unit" and not (current % 100 >= 20 and current % 10 == 0 and v < 10):
                return None                              # "five five", "twenty thirty": not one number
            current += v
            last = "unit"
        else:
            scale = _SCALES[w]
            if scale == 100:
                if current == 0 or current % 100 >= 10 and current >= 100:
                    return None
                current = (current - current % 100) + (current % 100) * 100 if current >= 100 else current * 100
            else:
                if current == 0 and total == 0:
                    return None
                total += max(current, 1) * scale
                current = 0
            last = "scale"
    return total + current


# longest phrases first; each maps to the Hebrew cue the parser keys on (word boundaries, case-insensitive)
PHRASES: list[tuple[str, str]] = [
    # greetings and flow
    (r"let'?s continue|let'?s go on|go on|continue", "נמשיך"), (r"thank you|thanks", "תודה"),
    (r"good morning", "בוקר טוב"), (r"good evening", "ערב טוב"), (r"hello|hi|hey", "שלום"),
    (r"ok(?:ay)?|sure|fine", "בסדר"),
    # the simulator: confirm, defer, targets, existing debt, the vehicle's price
    (r"(?:yes,?\s*)?i confirm|confirm(?:ed)?|that works(?: for me)?|looks good|this is my scenario", "מאשר"),
    (r"no deferral|don'?t defer|without (?:a )?deferral", "בלי דחייה"),
    (r"(?:defer|postpone|delay) the first payment(?: by)?", "לדחות את התשלום הראשון ב"),
    (r"i don'?t want to (?:pay|go) (?:more than|over|above)", "אני לא רוצה לעבור החזר של"),
    (r"(?:i want to |i'?d like to )?pay up to|pay no more than|at most", "לשלם עד"),
    (r"i have no (?:other )?(?:loans|debts|obligations)|no (?:other )?loans|no obligations", "אין לי הלוואות"),
    (r"i (?:already )?have an? (?:existing )?(?:loan|mortgage) (?:of|repayment of)", "יש לי הלוואה קיימת של"),
    (r"i (?:already )?pay", "אני משלם"), (r"the car costs|car costs|the car'?s price is|car price", "הרכב עולה"),
    (r"costs", "עולה"), (r"price", "מחיר"),
    (r"per month|a month|monthly|each month|every month", "בחודש"),
    # loan type, products and business form
    (r"personal loan|private loan|for myself|for me", "הלוואה פרטית"),
    (r"business loan|a loan for my business|for my business", "הלוואה עסקית"),
    (r"instant loan|quick loan|fast loan", "הלוואה ברגע"), (r"all[- ]purpose loan|all[- ]purpose", "הלוואה לכל מטרה"),
    (r"celebrations? loan|happy events? loan", "הלוואה לשמחות"), (r"electric (?:car|vehicle)", "רכב חשמלי"),
    (r"car loan", "הלוואה לרכב"), (r"solar(?: panels?| system)?", "סולארי"),
    (r"exempt dealer|osek patur|vat[- ]exempt", "עוסק פטור"),
    (r"licensed dealer|authorized dealer|osek murshe|vat[- ]registered", "עוסק מורשה"),
    (r"limited company|private company|my company|a company|ltd\.?", "חברה בע\"מ"),
    (r"authori[sz]ed signatory", "מורשה חתימה"),
    # purposes
    (r"buying a car|buy(?:ing)? a car|a car|the car|car|vehicle", "רכב"),
    (r"renovation|renovating|renovate|remodel(?:ing)?", "שיפוץ"),
    (r"wedding|bar mitzvah|bat mitzvah|family celebration|celebration|family event", "חתונה"),
    (r"vacation|holiday|trip", "חופשה"), (r"equipment", "ציוד"), (r"working capital", "הון חוזר"),
    (r"something else|another purpose|other purpose|other", "מטרה אחרת"),
    # income
    (r"both (?:a )?salary and (?:a )?business|(?:a )?salary and (?:a )?business", "גם משכורת וגם עסק"),
    (r"self[- ]employed|freelancer|freelance|my own business|own business", "עצמאי"),
    (r"salaried|employee|employed|on payroll", "שכיר"),
    (r"salary|wage", "משכורת"), (r"i earn|i make|earning|earn", "אני מרוויח"), (r"income", "הכנסה"),
    (r"net", "נטו"), (r"gross", "ברוטו"), (r"business", "עסק"),
    (r"pension|allowance|rental income|rent", "קצבה"),
    # co-borrower and accounts
    (r"just me|only me|only myself|by myself|alone|on my own|no co-?borrower", "רק אני"),
    (r"(?:my )?(?:wife|husband|spouse|partner)", "בן זוג"), (r"co-?borrower|another borrower", "לווה נוסף"),
    (r"joint account|shared account", "חשבון משותף"), (r"separate accounts?|each (?:has|have) (?:their|our) own", "נפרד"),
    # corrections and intent
    (r"actually|in fact", "בעצם"), (r"instead of", "במקום"), (r"i made a mistake|my mistake", "טעיתי"),
    (r"change|update|edit", "לשנות"), (r"i (?:only|just) (?:want|need)", "אני רוצה רק"),
    (r"i want|i'?d like|i need|we need|i would like", "אני רוצה"),
    (r"only|just", "רק"), (r"loan", "הלוואה"), (r"amount", "סכום"),
    (r"payments|installments", "תשלומים"), (r"payment|installment", "תשלום"), (r"months", "חודשים"), (r"month", "חודש"),
    (r"years", "שנים"), (r"year", "שנה"),
    # questions (topics)
    (r"how did you (?:calculate|get|work out|figure)|how was (?:this|it) calculated|what are the assumptions", "איך חישבת"),
    (r"what'?s the repayment|what is the repayment|how much will i pay|monthly repayment|relative to my income"
     r"|compared to my income", "מה ההחזר ביחס להכנסה"),
    (r"will (?:the bank|you) approve|guarantee|promise|am i eligible|eligible|chances", "מבטיח שהבנק יאשר"),
    (r"interest(?: rate)?", "ריבית"), (r"which documents|what documents|documents", "אילו מסמכים"),
    (r"payslips?|pay slips?", "תלוש"), (r"what'?s left|how many (?:more )?questions|how long", "מה נשאר"),
    (r"talk to (?:a|my) banker|banker|a human|representative|person", "בנקאי"),
    (r"privacy|my data|who sees", "פרטיות"), (r"weather|forecast|rain", "מזג האוויר"),
    (r"why do you need (?:this|that|it)|why", "למה"), (r"how", "איך"), (r"what", "מה"), (r"which", "איזה"),
    (r"can i|could i|is it possible", "אפשר"), (r"when", "מתי"), (r"calculate|compute", "לחשב"),
    (r"no", "לא"), (r"yes|yeah|yep|correct|right", "כן"), (r"i have|we have", "יש לי"), (r"i'?m|i am", "אני"),
    (r"my name is|i'?m called|call me", "קוראים לי"),
]
_COMPILED = [(re.compile(rf"(?<![\w-]){p}(?![\w-])", re.IGNORECASE), he) for p, he in PHRASES]


def _numbers(text: str) -> str:
    """'80k' / '80 thousand' / '1.5m' / 'five years' / '12,000' → figures the Hebrew parser reads (an English comma
    between digits is a thousands separator)."""
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*k\b", lambda m: f"{m.group(1)} אלף", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*thousand\b", lambda m: f"{m.group(1)} אלף", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*(?:m|million)\b", lambda m: f"{int(float(m.group(1)) * 1_000_000)}", text, flags=re.IGNORECASE)
    text = re.sub(r"[₪$]\s*(\d)", r"\1", text)
    text = re.sub(r"(\d)\s*(?:nis|ils|shekels?)\b", r"\1", text, flags=re.IGNORECASE)
    def value(m: re.Match) -> str:
        v = _words_value(m.group(0))
        return m.group(0) if v is None else str(v)       # not one number: left as words, so the parser doesn't read it
    return _RUN.sub(value, text)


def to_parser(text: str, pending: str | None) -> str:
    """The copy of an English message the Hebrew parser reads. Hebrew text is returned unchanged."""
    if not re.search(r"[A-Za-z]", text) or re.search(r"[֐-׿]", text):
        return text
    if pending in NO_REWRITE:
        return re.sub(r"(?i)^\s*(?:my name is|i'?m called|call me|i'?m|i am|it'?s)\s+", "", text)
    out = _numbers(text)
    if pending in ("income", "co_income"):           # "both" answers the income question only (not "both of us")
        out = re.sub(r"(?i)(?<![\w-])both(?![\w-])", "גם משכורת וגם עסק", out)
    for rx, he in _COMPILED:
        out = rx.sub(he, out)
    return out
