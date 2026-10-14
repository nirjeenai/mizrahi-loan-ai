"""Deterministic outcomes for the non-payslip document families (ID card, bank statement, proof of purpose, tax form,
VAT registration confirmation, a sole proprietor's P&L).

Pure functions over extracted, evidence-checked facts. Code decides identity, check digits, dates and recency; a
criterion it cannot decide is returned as JUDGE for the hybrid judge. Thresholds come from the loan policy the case
is pinned to (passed in `rules`), never from constants here."""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Optional

from . import deterministic as det


def match_holder(printed_name: Optional[str], printed_id: Optional[str], borrowers: dict[str, dict]) -> Optional[str]:
    for b in borrowers.values():
        idr = det.id_relation(printed_id, b["national_id"])
        nr = det.holder_relation(printed_name, b["name_he"])
        if idr == "same" or (idr == "unknown" and nr in ("same", "variant")):
            return b["borrower_id"]
    return None


def _holder(cid: str, assigned: Optional[dict], borrowers: dict, name: Optional[str], pid: Optional[str],
            matched: Optional[str], allowed: Optional[list[str]] = None) -> tuple[str, str]:
    """The printed holder against the applicant the document was uploaded for (or any holder of the account)."""
    if not assigned:
        return "NEEDS_REVIEW", "המסמך לא שויך למבקש/ת"
    candidates = [borrowers[b] for b in (allowed or [assigned["borrower_id"]]) if b in borrowers] or [assigned]
    for person in candidates:
        idr = det.id_relation(pid, person["national_id"])
        nr = det.holder_relation(name, person["name_he"])
        if idr == "same" and nr in ("same", "variant", "unknown"):
            return "PASS", f"השם ומספר הזהות תואמים ל{person['name_he']}"
        if idr == "unknown" and nr in ("same", "variant"):
            return "PASS", f"השם במסמך ({name}) תואם ל{person['name_he']}"
    if pid and all(det.id_relation(pid, p["national_id"]) == "different" for p in candidates):
        other = borrowers.get(matched or "")
        return "FAIL", (f"מספר הזהות במסמך אינו של {assigned['name_he']}"
                        + (f" — המסמך מזוהה עם {other['name_he']}" if other and other["borrower_id"] != assigned["borrower_id"] else ""))
    if name and all(det.holder_relation(name, p["name_he"]) == "different" for p in candidates):
        return "FAIL", f"השם במסמך ({name}) אינו {assigned['name_he']}"
    return "JUDGE", f"השוואת זהות לא חד־משמעית (שם: {name or 'לא מודפס'})"


def outcomes(family: str, rubric: dict, *, val: Callable[[str], Any], norm: Callable[[str], Any], as_of: date,
             borrowers: dict[str, dict], assigned: Optional[dict], matched: Optional[str], hits: list[str],
             unverified: list[str], present_decisive: list[str], rules: dict, allowed_holders: Optional[list[str]],
             labels: dict[str, str]) -> dict[str, tuple[str, str]]:
    ids = {c["id"] for c in rubric["criteria"]}
    o: dict[str, tuple[str, str]] = {}

    def put(cid: str, value: tuple[str, str]) -> None:
        if cid in ids:
            o[cid] = value

    def evidence(cid: str) -> None:
        if not present_decisive:
            put(cid, ("FAIL", "לא חולצו שדות מכריעים שניתן לאמת"))
        elif unverified:
            put(cid, ("FAIL", "לא אומתו מול הקובץ: " + ", ".join(labels.get(n, n) for n in unverified)))
        else:
            put(cid, ("PASS", "כל השדות המכריעים אומתו מול הקובץ המקורי"))

    def injection(cid: str) -> None:
        put(cid, ("FAIL", "נמצא במסמך טקסט המופנה למערכת או לבודק: " + hits[0][:140]) if hits else ("JUDGE", ""))

    holder_name, holder_id = val("holder_name"), val("holder_id")
    if family == "id_document":
        put("ID-03", _holder("ID-03", assigned, borrowers, holder_name, holder_id, matched))
        check = det.israeli_id_check(holder_id)
        put("ID-04", {"valid": ("PASS", f"מספר הזהות {holder_id} עומד בבדיקת ספרת הביקורת"),
                      "synthetic": ("PASS", f"מזהה סינתטי של סביבת ההדגמה ({holder_id}) — בדיקת ספרת ביקורת אינה רלוונטית"),
                      "invalid": ("FAIL", f"מספר הזהות {holder_id} אינו עומד בבדיקת ספרת הביקורת"),
                      "unknown": ("NEEDS_REVIEW", "מספר הזהות אינו מודפס או אינו קריא")}[check])
        expiry = norm("expiry_date")
        if not rules.get("check_expiry", True):
            put("ID-05", ("NOT_APPLICABLE", "בדיקת תוקף כבויה במדיניות"))
        elif not expiry:
            put("ID-05", ("NOT_APPLICABLE", "תאריך תוקף אינו מודפס"))
        else:
            d = date.fromisoformat(expiry)
            put("ID-05", ("PASS", f"בתוקף עד {det.day_he(d)}") if d >= as_of else
                ("FAIL", f"תוקף התעודה פג ב־{det.day_he(d)}"))
        injection("ID-06")
        evidence("ID-07")
    elif family == "bank_statement":
        put("BS-03", _holder("BS-03", assigned, borrowers, holder_name, holder_id, matched, allowed_holders))
        start, end = norm("statement_from"), norm("statement_to")
        if start and end and start <= end:
            put("BS-04", ("PASS", f"תקופת הדף: {det.day_he(date.fromisoformat(start))}–{det.day_he(date.fromisoformat(end))}"))
            # one statement must fall inside the window; whether the SET is recent enough is a case-level coverage fact
            age = (as_of - date.fromisoformat(end)).days
            limit = int(rules.get("max_age_days", 30)) + int(rules.get("coverage_days", 90))
            put("BS-05", ("PASS", f"הדף מסתיים {age} ימים לפני תאריך הבדיקה — בתוך התקופה הנדרשת") if age <= limit else
                ("FAIL", f"הדף מסתיים ב־{det.day_he(date.fromisoformat(end))}, {age} ימים לפני תאריך הבדיקה — "
                         "מחוץ לתקופה הנדרשת. נדרש דף עדכני."))
        else:
            put("BS-04", ("FAIL", "תקופת הדף אינה מודפסת או אינה ניתנת לפענוח"))
            put("BS-05", ("NEEDS_REVIEW", "לא ניתן לקבוע את עדכניות הדף בלי תקופה מודפסת"))
        injection("BS-06")
        evidence("BS-07")
    elif family == "purpose_proof":
        missing = [labels[n] for n in ("issuer_name", "total_amount") if not norm(n) and not val(n)]
        put("PP-03", ("FAIL", "חסר במסמך: " + ", ".join(missing)) if missing else
            ("PASS", f"ספק: {val('issuer_name')} · סכום: {val('total_amount')}"))
        issued = norm("issue_date")
        limit = int(rules.get("max_age_days", 90))
        if issued:
            age = (as_of - date.fromisoformat(issued)).days
            put("PP-04", ("PASS", f"הופק לפני {age} ימים (עד {limit})") if 0 <= age <= limit else
                ("FAIL", f"המסמך הופק ב־{det.day_he(date.fromisoformat(issued))} — מעבר ל־{limit} הימים שהמדיניות מאפשרת"))
        else:
            put("PP-04", ("FAIL", "תאריך המסמך אינו מודפס"))
        injection("PP-06")
        evidence("PP-07")
    elif family == "tax_form":
        put("TX-03", _holder("TX-03", assigned, borrowers, holder_name, holder_id, matched))
        year = norm("tax_year")
        offset = int(rules.get("min_tax_year_offset", 1))
        if year:
            put("TX-04", ("PASS", f"שנת מס {year}") if int(year) >= as_of.year - offset - 1 else
                ("FAIL", f"שנת המס {year} ישנה — נדרשת שומה של {as_of.year - offset} או מאוחרת"))
        else:
            put("TX-04", ("FAIL", "שנת המס אינה מודפסת"))
        injection("TX-05")
        evidence("TX-06")
    elif family == "business_registration":
        put("BR-03", _holder("BR-03", assigned, borrowers, holder_name, holder_id, matched))
        wanted = rules.get("registration")
        printed = " ".join(str(val("registration_type") or "").split())
        kind = "vat_exempt" if "פטור" in printed else "vat_registered" if "מורשה" in printed else None
        if not printed:
            put("BR-04", ("FAIL", "סוג הרישום (עוסק פטור / מורשה) אינו מודפס"))
        elif not wanted or kind == wanted:
            put("BR-04", ("PASS", f"רישום: {printed}"))
        else:
            put("BR-04", ("FAIL", f"במסמך מודפס ״{printed}״, אבל הדרישה היא ל{REGISTRATION_HE.get(wanted, wanted)}"))
        dealer = val("dealer_number")
        if not dealer:
            put("BR-05", ("NEEDS_REVIEW", "מספר העוסק אינו מודפס"))
        elif not assigned:
            put("BR-05", ("NEEDS_REVIEW", "המסמך לא שויך למבקש/ת"))
        else:
            rel = det.id_relation(dealer, assigned["national_id"])
            put("BR-05", ("PASS", f"מספר העוסק {dealer} זהה למספר הזהות של {assigned['name_he']}") if rel == "same" else
                ("FAIL", f"מספר העוסק {dealer} אינו מספר הזהות של {assigned['name_he']}") if rel == "different" else
                ("NEEDS_REVIEW", f"לא ניתן להשוות את מספר העוסק {dealer}"))
        injection("BR-06")
        evidence("BR-07")
    elif family == "pnl_statement":
        put("PL-03", _holder("PL-03", assigned, borrowers, holder_name, holder_id, matched))
        end = norm("period_to")
        limit = int(rules.get("max_age_days", 120))
        if end:
            d = date.fromisoformat(end)
            age = (as_of - d).days
            start = norm("period_from")
            span = f"{det.day_he(date.fromisoformat(start))}–{det.day_he(d)}" if start else f"עד {det.day_he(d)}"
            put("PL-04", ("PASS", f"תקופת הדוח {span} — הסתיימה לפני {age} ימים (עד {limit})") if 0 <= age <= limit else
                ("FAIL", f"תקופת הדוח הסתיימה ב־{det.day_he(d)}, {age} ימים לפני תאריך הבדיקה — מעבר ל־{limit} הימים "
                         "שמדיניות ההדגמה מאפשרת. נדרש דוח עדכני."))
        else:
            put("PL-04", ("FAIL", "תקופת הדוח אינה מודפסת"))
        issuer = val("issuer_name")
        put("PL-05", ("PASS", f"הדוח נערך בידי {issuer}") if issuer else ("NEEDS_REVIEW", "לא מודפס מי ערך או חתם על הדוח"))
        injection("PL-06")
        evidence("PL-07")
    return o


REGISTRATION_HE = {"vat_exempt": "עוסק פטור", "vat_registered": "עוסק מורשה"}
