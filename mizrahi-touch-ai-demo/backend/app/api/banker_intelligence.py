"""Banker Intelligence V2 — one case's briefing: the conclusion first, then what supports it.

Read-only and derived on every request from what already exists: the review workspace (build_workspace — document
state, findings, income comparison, drafts), the case in the bank adapter (application, declarations), the synthetic
bank financial context (bank/financial_context.py) and deterministic arithmetic (workflow/finance.py). It writes
nothing, changes no state and calls no model.

Facts → deterministic calculations → named demo assumptions → a rule-based recommendation → Hebrew wording.
Two tracks never merge: the documentation recommendation (is the file complete, what happens next) and the
illustrative financial assessment (scenarios, ratios, what would still need verification). Neither is a credit
decision. Every number carries a `source_id` into `sources`, which says where it came from: a document field (with
its evidence), the customer's declaration, the synthetic bank context, a calculation (formula and inputs), a demo
assumption, or "missing"."""
from __future__ import annotations

from typing import Any, Optional

from ..bank import financial_context
from ..bank.mock_bank import bank
from ..review import deterministic as det
from ..store import repo
from ..util import now_iso
from ..workflow import finance, requirements
from .banker_package import VERIFIED, _month_list_he, build_workspace

VERSION = "banker_intelligence.v1"
DISCLAIMER_HE = ("תמונת מצב לתמיכה בהחלטת הבנקאי. אינה החלטת אשראי, אינה הצעה מחייבת ואינה קובעת זכאות, סכום או ריבית — "
                 "ההחלטה בידי הבנק. נתוני ההקשר הבנקאי וההנחות אינם מאומתים מול מערכות הבנק.")
WITNESS_HE = {"text_layer_exact": "אומת מול שכבת הטקסט של הקובץ", "vision_reread_confirmed": "אומת בקריאה חוזרת של הסריקה"}


def _ils(n: Optional[float]) -> str:
    return "—" if n is None else f"₪{n:,.0f}"


def _pct(n: Optional[float]) -> str:
    return "—" if n is None else f"{n:.1f}%"


def _join_he(items: list[str]) -> str:
    items = [x for x in items if x]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " ו" + items[-1] if items else ""


class Sources:
    """Where each number came from. Ids are stable per request so the UI can open any of them."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(self, sid: str, kind: str, **kw: Any) -> str:
        self.items[sid] = {"id": sid, "kind": kind, **kw}
        return sid


def _datum(value: Any, source_id: Optional[str], unit: str = "ils") -> dict:
    return {"value": value, "unit": unit, "source_id": source_id}


def build(case_id: str) -> dict[str, Any]:
    case = bank.get_case(case_id)
    ws = build_workspace(case_id)
    latest_case = repo.latest_case_result(case_id) or {}
    src = Sources()
    docs = [i for i in ws["items"] if i["kind"] == "document" and i["banker"]["status"] != "REPLACED"]
    docs_by_id = {i["document_id"]: i for i in ws["items"] if i["kind"] == "document"}
    profile = case.get("document_profile") or {}
    company = profile.get("entity") == "company"
    loan = case.get("loan") or {}
    names = {b["borrower_id"]: b for b in case["borrowers"]}

    def doc_fact(document_id: str, field: str) -> Optional[str]:
        item = docs_by_id.get(document_id)
        fact = next((f for f in (item or {}).get("ai", {}).get("facts", []) if f["field"] == field), None)
        if not item or not fact:
            return None
        ev = fact.get("evidence") or {}
        accepted = item["banker"]["status"] == "ACCEPTED"
        return src.add(f"doc:{document_id}:{field}", "document", label_he=f"{fact['label_he']} · {item['doc_type_he']}"
                       + (f" {item['period_he']}" if item.get("period_he") else ""),
                       value_raw=fact.get("value_raw"), value=fact.get("value_normalized"), document_id=document_id,
                       field=field, filename=item["filename"], doc_type_he=item["doc_type_he"], period_he=item.get("period_he"),
                       verified=fact.get("verified", False), witness=ev.get("witness"),
                       witness_he=WITNESS_HE.get(ev.get("witness") or "", "לא אומת מול הקובץ"),
                       page=ev.get("page"), has_location=bool(ev.get("bbox")), ai_verdict_he=item["ai"]["verdict_he"],
                       banker_status=item["banker"]["status"], banker_status_he=item["banker"]["status_he"],
                       banker_reviewed=accepted, v1_item=item["id"])

    # ------------------------------------------------------------ application
    sid_amount = src.add("app:amount", "declared", label_he="סכום ההלוואה המבוקש", value=loan.get("requested_amount_ils"),
                         origin_he="בקשת ההלוואה — נתוני התיק")
    sid_term = src.add("app:term", "declared", label_he="מספר תשלומים מבוקש", value=loan.get("payments"),
                       origin_he="בקשת ההלוואה — נתוני התיק")
    purpose_doc = next((d for d in docs if d.get("family") == "purpose_proof"), None)
    sid_price = doc_fact(purpose_doc["document_id"], "total_amount") if purpose_doc else None
    price = src.items[sid_price]["value"] if sid_price else None
    sid_subject = doc_fact(purpose_doc["document_id"], "subject") if purpose_doc else None

    borrowers_out = []
    for b in case["borrowers"]:
        sources_b = requirements.income_sources(b)
        payslip = sorted((d for d in docs if d.get("family") == "payslip" and d.get("borrower_id") == b["borrower_id"]),
                         key=lambda d: d.get("period") or "")
        employer_sid = doc_fact(payslip[-1]["document_id"], "employer_name") if payslip else None
        borrowers_out.append({"borrower_id": b["borrower_id"], "name_he": b["name_he"], "first_name_he": b["first_name_he"],
                              "role": b.get("role"), "role_he": {"primary": "לווה ראשי", "co_borrower": "לווה נוסף",
                                                                  "authorized_signatory": "מורשה חתימה"}.get(b.get("role") or "", ""),
                              "profile_he": next((a["profile_he"] for a in profile.get("applicants", [])
                                                  if a["borrower_id"] == b["borrower_id"]), None),
                              "employer_declared_he": b.get("employer_declared_he"), "employer_document_source_id": employer_sid,
                              "income_sources": sources_b})

    # ------------------------------------------------------------ income per borrower
    income_rows, discrepancies = [], []
    finding_items = [i for i in ws["items"] if i["kind"] == "case_finding"]
    for b in case["borrowers"]:
        bid = b["borrower_id"]
        declared = b.get("declared_net_monthly_ils") or 0
        sid_decl = src.add(f"declared:{bid}", "declared", label_he=f"הכנסה נטו מוצהרת — {b['first_name_he']}", value=declared,
                           origin_he="טופס הבקשה (CUSTOMER_DECLARED) — לא מאומת", note_he=b.get("declaration_note_he")) \
            if declared else None
        inc = (latest_case.get("income") or {}).get(bid) or {}
        row = next((r for r in ws["borrowers"] if r["borrower_id"] == bid), None)
        block = (row or {}).get("income") or {}
        months = []
        for period in inc.get("months_compared") or []:
            m = (inc.get("months") or {}).get(period) or {}
            sid = doc_fact(m["document_id"], "net_pay") if m.get("document_id") else None
            months.append({"period": period, "period_he": det.month_label_he(period), "net_ils": m.get("net"),
                           "verified": m.get("net_witness") in VERIFIED, "source_id": sid})
        avg = inc.get("average_documented_net_ils")
        basis = block.get("basis") or "none"
        sid_avg = None
        if avg is not None and months:
            sid_avg = src.add(f"calc:avg_net:{bid}", "calculated", label_he=f"ממוצע נטו בתלושים — {b['first_name_he']}", value=avg,
                              unit="ils", formula_he=f"סכום הנטו בתלושים ÷ {len(months)} חודשים",
                              inputs=[{"label_he": f"נטו {m['period_he']}", "value": m["net_ils"], "unit": "ils",
                                       "source_id": m["source_id"]} for m in months],
                              note_he="תלושים שעברו את בדיקות ההכנסה בלבד, בחודשים הנדרשים (בדיקת IS-04 בקוד).")
        finding = next((i for i in finding_items if i["finding"]["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"
                        and i["borrower_id"] == bid), None)
        unresolved = bool(finding and finding["finding"]["status"] == "open")
        all_verified = bool(months) and all(m["verified"] for m in months)
        if avg is not None and basis == "complete" and all_verified:
            chosen, quality = (min(avg, declared) if unresolved and declared else avg), "verified"
        elif avg is not None and basis == "preliminary":
            chosen, quality = (min(avg, declared) if unresolved and declared else avg), "partial"
        elif declared:
            chosen, quality = declared, "declared"
        else:
            chosen, quality = None, "missing"
        if quality == "declared" or (unresolved and declared and avg is not None and declared < avg):
            chosen_sid = sid_decl
        else:
            chosen_sid = sid_avg
        values = [m["net_ils"] for m in months if m["net_ils"] is not None]
        variability = round((max(values) - min(values)) / avg * 100, 1) if len(values) > 1 and avg else None
        if finding:
            d_ils, d_pct = (finding.get("income") or {}).get("difference_ils"), (finding.get("income") or {}).get("difference_pct")
            discrepancies.append({
                "borrower_id": bid, "first_name_he": b["first_name_he"], "kind": "income",
                "title_he": "פער בין ההכנסה המוצהרת להכנסה בתלושים", "open": unresolved,
                "declared": _datum(declared, sid_decl), "documented": _datum(avg, sid_avg),
                "difference_ils": d_ils, "difference_pct": d_pct, "tolerance_pct": (finding.get("income") or {}).get("tolerance_pct"),
                "status_he": finding["finding"]["status_he"], "v1_item": finding["id"],
                "explanation_he": (f"{b['first_name_he']} הצהיר/ה על {_ils(declared)} נטו בחודש; ממוצע הנטו בתלושים {_ils(avg)} "
                                   f"(פער {_ils(abs(d_ils or 0))}, {abs(d_pct or 0):.1f}%). פער כזה יכול לנבוע משינוי שכר, רכיבים "
                                   "משתנים או הגדרה שונה של ההכנסה — אינו מעיד בהכרח על אי-התאמה מכוונת."),
                "action_he": ("לבקש הסבר ואסמכתה (למשל אישור מעסיק על רכיבים משתנים) או להכריע בבירור בסקירת המסמכים. "
                              "עד אז הניתוח הפיננסי מבוסס על הנתון הנמוך מבין השניים ומסומן כזמני.") if unresolved else
                             "הבירור נסגר על ידי הבנקאי בסקירת המסמכים; הניתוח מבוסס על ההכנסה שאומתה בתלושים."})
        income_rows.append({"borrower_id": bid, "first_name_he": b["first_name_he"], "name_he": b["name_he"],
                            "declared": _datum(declared or None, sid_decl), "documented_avg": _datum(avg, sid_avg),
                            "months": months, "months_required": len(block.get("months_compared") or []) + len(block.get("months_missing") or [])
                            if block else 0, "basis": basis, "quality": quality, "variability_pct": variability,
                            "chosen": _datum(chosen, chosen_sid), "unresolved_discrepancy": unresolved,
                            "business_income": "self_employed" in requirements.income_sources(b)})

    counted = [r for r in income_rows if r["chosen"]["value"] is not None]
    income_total = round(sum(r["chosen"]["value"] for r in counted), 2) if counted else None
    business = any(r["business_income"] for r in counted)
    sid_income = None
    if income_total is not None:
        sid_income = src.add("calc:income", "calculated", label_he="הכנסה חודשית נטו לחישוב", value=income_total, unit="ils",
                             formula_he=" + ".join(f"נטו {r['first_name_he']}" for r in counted) if len(counted) > 1
                             else f"הכנסת {counted[0]['first_name_he']} לחישוב",
                             inputs=[{"label_he": f"{r['first_name_he']} · " + {"verified": "ממוצע מאומת בתלושים",
                                                                                  "partial": "ממוצע חלקי בתלושים",
                                                                                  "declared": "מוצהר בלבד — לא מאומת"}[r["quality"]]
                                      + (" · הנמוך מבין מוצהר ומתועד עד לבירור" if r["unresolved_discrepancy"] else ""),
                                      "value": r["chosen"]["value"], "unit": "ils", "source_id": r["chosen"]["source_id"]}
                                     for r in counted],
                             note_he="כשאין פער פתוח — ההכנסה שאומתה בתלושים. כשיש פער פתוח — הנתון הנמוך מבין ההצהרה לממוצע "
                                     "בתלושים, כדי שהניתוח לא יעדיף את המספר שמציג את הבקשה טוב יותר.")

    # ------------------------------------------------------------ synthetic bank context
    contexts = [c for c in (financial_context.for_borrower(b) for b in case["borrowers"]) if c]
    context_missing = [b["first_name_he"] for b in case["borrowers"]
                       if not any(c["borrower_id"] == b["borrower_id"] for c in contexts) and not company]
    loans, lines, events = [], [], []
    for c in contexts:
        who = names[c["borrower_id"]]["first_name_he"]
        for ln in c.get("loans", []):
            base = f"bank:{c['fixture_id']}:{ln['id']}"
            meta = dict(fixture_id=c["fixture_id"], observed_at=c["observed_at"], source_he="הקשר בנקאי (לא מאומת)",
                        note_he=c["note_he"])
            loans.append({**ln, "owner_he": who,
                          "monthly": _datum(ln["monthly_payment_ils"], src.add(f"{base}:monthly", "synthetic_bank",
                                            label_he=f"החזר חודשי — {ln['type_he']} ({ln['id']})", value=ln["monthly_payment_ils"], **meta)),
                          "outstanding": _datum(ln["outstanding_ils"], src.add(f"{base}:outstanding", "synthetic_bank",
                                                label_he=f"יתרת קרן — {ln['type_he']} ({ln['id']})", value=ln["outstanding_ils"], **meta))})
        for cl in c.get("credit_lines", []):
            sid = src.add(f"bank:{c['fixture_id']}:{cl['id']}", "synthetic_bank", label_he=f"{cl['type_he']} ({cl['id']})",
                          value=cl["utilized_ils"], fixture_id=c["fixture_id"], observed_at=c["observed_at"],
                          source_he="הקשר בנקאי (לא מאומת)", note_he=c["note_he"],
                          detail_he=f"מסגרת {_ils(cl['limit_ils'])} · מנוצל {_ils(cl['utilized_ils'])}")
            lines.append({**cl, "owner_he": who, "source_id": sid})
        ev = c.get("events") or {}
        sid_ev = src.add(f"bank:{c['fixture_id']}:events", "synthetic_bank", label_he=f"אירועי חשבון ב־12 חודשים — {who}",
                         value=ev.get("returned_checks_12m", 0), fixture_id=c["fixture_id"], observed_at=c["observed_at"],
                         source_he="הקשר בנקאי (לא מאומת)", note_he=c["note_he"],
                         detail_he=" · ".join(ev.get("detail_he") or []) or "לא נרשמו שיקים חוזרים, פיגורים או הגבלות.")
        events.append({"owner_he": who, "returned_checks_12m": ev.get("returned_checks_12m", 0), "arrears_12m": ev.get("arrears_12m", 0),
                       "restrictions_he": ev.get("restrictions_he") or [], "detail_he": ev.get("detail_he") or [], "source_id": sid_ev})
    spending = [{"owner_he": names[c["borrower_id"]]["first_name_he"], **c["card_spending"],
                 "source_id": src.add(f"bank:{c['fixture_id']}:card_spending", "synthetic_bank",
                                      label_he=f"חיובי כרטיס אשראי חודשיים — {names[c['borrower_id']]['first_name_he']}",
                                      value=c["card_spending"]["avg_monthly_ils"], fixture_id=c["fixture_id"],
                                      observed_at=c["observed_at"], source_he="הקשר בנקאי (לא מאומת)",
                                      note_he=c["card_spending"]["note_he"])}
                for c in contexts if c.get("card_spending")]

    existing = round(sum(x["monthly_payment_ils"] for x in loans), 2) if contexts else None
    sid_existing = None
    if existing is not None:
        sid_existing = src.add("calc:existing_debt", "calculated", label_he="החזר חודשי על הלוואות קיימות", value=existing,
                               formula_he="סכום ההחזרים החודשיים של ההלוואות הקיימות" if loans else "אין הלוואות קיימות בהקשר הבנקאי",
                               inputs=[{"label_he": f"{x['type_he']} · {x['owner_he']}", "value": x["monthly_payment_ils"], "unit": "ils",
                                        "source_id": x["monthly"]["source_id"]} for x in loans],
                               note_he="חיובי כרטיס אשראי (הוצאה שוטפת) ומסגרות אשראי שאינן מנוצלות אינם החזר חוב ואינם נספרים כאן.")
    exposure = None
    if contexts:
        outstanding = round(sum(x["outstanding_ils"] for x in loans), 2)
        limits = round(sum(x["limit_ils"] for x in lines), 2)
        used = round(sum(x["utilized_ils"] for x in lines), 2)
        inputs_appr = [{"label_he": f"יתרת {x['type_he']}", "value": x["outstanding_ils"], "unit": "ils", "source_id": x["outstanding"]["source_id"]}
                       for x in loans] + [{"label_he": f"מסגרת — {x['type_he']}", "value": x["limit_ils"], "unit": "ils",
                                           "source_id": x["source_id"]} for x in lines]
        inputs_used = [{"label_he": f"יתרת {x['type_he']}", "value": x["outstanding_ils"], "unit": "ils", "source_id": x["outstanding"]["source_id"]}
                       for x in loans] + [{"label_he": f"ניצול — {x['type_he']}", "value": x["utilized_ils"], "unit": "ils",
                                           "source_id": x["source_id"]} for x in lines]
        exposure = {
            "loans_outstanding": _datum(outstanding, None),
            "approved": _datum(round(outstanding + limits, 2), src.add("calc:exposure_approved", "calculated",
                               label_he="אובליגו מאושר", value=round(outstanding + limits, 2),
                               formula_he="יתרות הלוואות + מסגרות אשראי מאושרות", inputs=inputs_appr,
                               note_he="חשיפת אשראי — אינה החזר חודשי ואינה נכנסת ליחס ההחזר.")),
            "utilized": _datum(round(outstanding + used, 2), src.add("calc:exposure_utilized", "calculated",
                               label_he="אובליגו מנוצל", value=round(outstanding + used, 2),
                               formula_he="יתרות הלוואות + ניצול מסגרות בפועל", inputs=inputs_used,
                               note_he="חשיפת אשראי בפועל ביום התצפית — אינה החזר חודשי.")),
            "credit_limits_ils": limits, "credit_utilized_ils": used}

    # ------------------------------------------------------------ calculations on the application
    amount, term, rate = loan.get("requested_amount_ils"), loan.get("payments"), finance.DEMO_ANNUAL_RATE_PCT
    threshold = finance.threshold_pct(business)
    sid_rate = src.add("assume:rate", "assumption", label_he="ריבית שנתית להמחשה", value=rate, unit="pct",
                       note_he="ריבית קבועה אחת לכל החלופות — הנחה לצורך החישוב. אינה ריבית של מזרחי־טפחות, אינה מבוססת פריים "
                               "ואינה הצעה. זהה להנחה בהערכה הראשונית שבשאלון הלקוח.")
    sid_threshold = src.add("assume:dsr", "assumption", label_he="סף יחס החזר להמחשה", value=threshold, unit="pct",
                            note_he=("החזרים חודשיים כוללים עד " + _pct(threshold) + " מההכנסה נטו"
                                     + (" (הכנסה מעסק — הנחה שמרנית יותר)" if business else " (הכנסה ממשכורת)")
                                     + ". הנחה לצורך ההסבר בלבד — אינה מדיניות אשראי של מזרחי־טפחות ואינה קובעת זכאות."))
    app = finance.schedule(amount, term, rate) if amount and term else None
    calc: dict[str, Any] = {}
    if app:
        sid_pay = src.add("calc:proposed_payment", "calculated", label_he="החזר חודשי משוער להלוואה המבוקשת",
                          value=app["monthly_payment_ils"], formula_he="P·r ÷ (1 − (1 + r)^−n), r = ריבית שנתית ÷ 12",
                          inputs=[{"label_he": "קרן (P)", "value": amount, "unit": "ils", "source_id": sid_amount},
                                  {"label_he": "תשלומים (n)", "value": term, "unit": "months", "source_id": sid_term},
                                  {"label_he": "ריבית שנתית", "value": rate, "unit": "pct", "source_id": sid_rate}],
                          note_he="הלוואה בריבית קבועה בלוח שפיצר. מעוגל לאגורות.")
        calc["proposed_payment"] = _datum(app["monthly_payment_ils"], sid_pay)
        calc["total_interest"] = _datum(app["total_interest_ils"], src.add("calc:total_interest", "calculated",
                                        label_he="עלות המימון (ריבית) בחלופה המבוקשת", value=app["total_interest_ils"],
                                        formula_he="החזר חודשי × מספר התשלומים − הקרן",
                                        inputs=[{"label_he": "החזר חודשי", "value": app["monthly_payment_ils"], "unit": "ils", "source_id": sid_pay},
                                                {"label_he": "תשלומים", "value": term, "unit": "months", "source_id": sid_term},
                                                {"label_he": "קרן", "value": amount, "unit": "ils", "source_id": sid_amount}],
                                        note_he="מחושב מההחזר הלא מעוגל — התשלום האחרון סופג את עיגול האגורות, כמו בלוח סילוקין."))
        calc["total_payments"] = _datum(app["total_payments_ils"], src.add("calc:total_payments", "calculated",
                                        label_he="סך התשלומים בחלופה המבוקשת", value=app["total_payments_ils"],
                                        formula_he="קרן + עלות המימון",
                                        inputs=[{"label_he": "קרן", "value": amount, "unit": "ils", "source_id": sid_amount},
                                                {"label_he": "עלות המימון", "value": app["total_interest_ils"], "unit": "ils",
                                                 "source_id": "calc:total_interest"}]))
    existing_dsr = finance.ratio_pct(existing, income_total)
    if existing_dsr is not None:
        calc["existing_dsr"] = _datum(existing_dsr, src.add("calc:existing_dsr", "calculated", label_he="יחס החזר קיים",
                                      value=existing_dsr, unit="pct", formula_he="החזר חודשי על הלוואות קיימות ÷ הכנסה נטו × 100",
                                      inputs=[{"label_he": "החזרים קיימים", "value": existing, "unit": "ils", "source_id": sid_existing},
                                              {"label_he": "הכנסה נטו", "value": income_total, "unit": "ils", "source_id": sid_income}]), "pct")
    combined = None
    if app and income_total:
        combined_ils = round(app["monthly_payment_ils"] + (existing or 0), 2)
        combined = finance.ratio_pct(combined_ils, income_total)
        inputs = [{"label_he": "החזר משוער להלוואה המבוקשת", "value": app["monthly_payment_ils"], "unit": "ils", "source_id": "calc:proposed_payment"}]
        if existing is not None:
            inputs.append({"label_he": "החזרים קיימים", "value": existing, "unit": "ils", "source_id": sid_existing})
        inputs.append({"label_he": "הכנסה נטו", "value": income_total, "unit": "ils", "source_id": sid_income})
        calc["combined_dsr"] = _datum(combined, src.add("calc:combined_dsr", "calculated", label_he="יחס החזר משולב",
                                      value=combined, unit="pct", formula_he="(החזר משוער + החזרים קיימים) ÷ הכנסה נטו × 100",
                                      inputs=inputs, note_he=None if existing is not None else
                                      "אין נתוני התחייבויות קיימות לתיק — היחס כולל רק את ההלוואה המבוקשת ולכן חלקי."), "pct")
        remaining = round(income_total - combined_ils, 2)
        calc["remaining_after_debt"] = _datum(remaining, src.add("calc:remaining", "calculated",
                                              label_he="הכנסה שנותרת אחרי החזרי חוב", value=remaining,
                                              formula_he="הכנסה נטו − (החזר משוער + החזרים קיימים)",
                                              inputs=inputs[::-1],
                                              note_he="מדד תיאורי בלבד — אינו הכנסה פנויה: הוצאות מחיה, דיור וחובות שאינם בהקשר הבנקאי אינם כלולים."))
    if amount and price:
        ltv = finance.ratio_pct(amount, price)
        calc["ltv"] = _datum(ltv, src.add("calc:ltv", "calculated", label_he="שיעור מימון מסכום האסמכתה", value=ltv, unit="pct",
                             formula_he="סכום ההלוואה ÷ הסכום בהצעת המחיר × 100",
                             inputs=[{"label_he": "סכום מבוקש", "value": amount, "unit": "ils", "source_id": sid_amount},
                                     {"label_he": "סכום בהצעת המחיר", "value": price, "unit": "ils", "source_id": sid_price}]), "pct")
    scenarios = finance.scenarios(amount, term, rate, income_total, existing, price) if amount and term else []
    if amount and price and amount > price:
        discrepancies.append({
            "borrower_id": None, "first_name_he": None, "kind": "purpose_amount", "open": True,
            "title_he": "הסכום המבוקש גבוה מהסכום בהצעת המחיר",
            "declared": _datum(amount, sid_amount), "documented": _datum(price, sid_price),
            "difference_ils": round(amount - price, 2), "difference_pct": finance.ratio_pct(amount - price, price),
            "tolerance_pct": None, "status_he": "לבדיקתך", "v1_item": purpose_doc["id"],
            "explanation_he": (f"בבקשה {_ils(amount)}, ובהצעת המחיר שהועלתה {_ils(price)} — מימון של {_pct(calc['ltv']['value'])} "
                               "מהסכום באסמכתה. ייתכן שהבקשה כוללת עלויות נלוות או שהצעת המחיר עודכנה."),
            "action_he": "לברר עם הלקוח את ההפרש או להתאים את סכום ההלוואה לסכום באסמכתה."})

    # ------------------------------------------------------------ documentation track
    state, case_status = ws["review_state"]["state"], ws.get("case_status")
    missing = [{"title_he": i["title_he"], "item_he": i["draft"].get("requested_item_he") or i["title_he"],
                "status_he": i["status_he"], "v1_item": i["id"], "requested": bool(i.get("open_request"))}
               for i in ws["items"] if i["kind"] == "missing"]
    corrections = [{"title_he": i["title_he"], "item_he": i["draft"].get("requested_item_he") or i["title_he"],
                    "reason_he": (i["ai"]["attention_he"] or [""])[0], "v1_item": i["id"]}
                   for i in docs if i["group"] == "correction"]
    awaiting = [i for i in docs if i["banker"]["status"] == "AWAITING_DECISION"]
    accepted = [i for i in docs if i["banker"]["status"] == "ACCEPTED"]
    judgment = [i for i in finding_items if i["finding"]["status"] == "open" and i["group"] in ("judgment", "escalated")]
    open_income = [d for d in discrepancies if d["open"] and d["kind"] == "income"]
    if state in ("CHECKING", "RECHECKING"):
        rec_state = "PROCESSING"
    elif state == "NOT_CHECKED":
        rec_state = "NO_DOCUMENTS"
    elif state == "ERROR":
        rec_state = "ERROR"
    elif state == "ACTION_REQUIRED" or missing or corrections:
        rec_state = "DOCUMENTS_INCOMPLETE"
    elif state == "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS" or judgment:
        rec_state = "CLARIFICATION_REQUIRED"
    elif state == "PREPARATION_CONFIRMED":
        rec_state = "PREPARATION_CONFIRMED"
    else:
        rec_state = "READY_FOR_CREDIT_REVIEW"
    docs_ready = rec_state in ("READY_FOR_CREDIT_REVIEW", "PREPARATION_CONFIRMED")

    # ------------------------------------------------------------ financial availability
    reasons = []
    if company:
        availability = "unavailable"
        reasons.append("תיק מימון עסקי: יחס החזר אישי אינו רלוונטי; נדרש ניתוח דוחות החברה על ידי הבנקאי.")
    elif not app:
        availability = "unavailable"
        reasons.append("חסרים סכום או מספר תשלומים בבקשה.")
    elif income_total is None:
        availability = "unavailable"
        reasons.append("אין הכנסה מוצהרת או מתועדת לחישוב.")
    else:
        if open_income:
            reasons.append("פער ההכנסה טרם נבדק — הניתוח מבוסס על הנתון הנמוך מבין ההצהרה לתלושים.")
        for r in income_rows:
            if r["quality"] == "declared" and r["chosen"]["value"] is not None:
                reasons.append(f"ההכנסה של {r['first_name_he']} מוצהרת בלבד — טרם אומתה במסמכים.")
            elif r["quality"] == "partial":
                reasons.append(f"ההכנסה של {r['first_name_he']} מבוססת על חלק מהחודשים הנדרשים.")
        if context_missing:
            reasons.append(f"אין נתוני הקשר בנקאי (התחייבויות ומסגרות) עבור {_join_he(context_missing)} — היחס המשולב כולל רק את ההלוואה המבוקשת.")
        availability = "provisional" if open_income else "partial" if reasons else "full"

    # The declared-income alternative, so the banker sees what the choice of income changes.
    alt = None
    if open_income and app:
        decl_total = sum((r["declared"]["value"] or 0) for r in income_rows) or None
        alt_dsr = finance.ratio_pct(app["monthly_payment_ils"] + (existing or 0), decl_total)
        alt = {"basis_he": "על בסיס ההכנסה המוצהרת", "income_ils": decl_total, "combined_dsr_pct": alt_dsr}

    suggested, max_amount = None, None
    base_sc = next((s for s in scenarios if s["key"] == "requested"), None)
    if income_total and term and availability != "unavailable":
        budget = income_total * threshold / 100 - (existing or 0)
        max_amount = finance.max_principal(budget, term, rate)
    if availability == "full" and docs_ready and base_sc and base_sc["combined_dsr_pct"] is not None:
        within = [s for s in scenarios if s["combined_dsr_pct"] <= threshold]
        if base_sc in within:
            pick, why = base_sc, f"החלופה שהתבקשה ({term} תשלומים) נשארת בתוך ההנחה ליחס ההחזר ({_pct(threshold)})."
        elif within:
            pick = min(within, key=lambda s: s["term_months"])
            why = (f"בתקופה שהתבקשה יחס ההחזר המשולב ({_pct(base_sc['combined_dsr_pct'])}) מעל ההנחה; "
                   f"בפריסה ל־{pick['term_months']} תשלומים הוא יורד ל־{_pct(pick['combined_dsr_pct'])}.")
        else:
            pick, why = None, (f"בכל החלופות יחס ההחזר המשולב מעל ההנחה ({_pct(threshold)}). "
                               + (f"להמחשה: בסכום של עד {_ils(max_amount)} ל־{term} תשלומים היחס נשאר בתוך ההנחה." if max_amount else ""))
        suggested = {"key": pick["key"] if pick else None, "term_months": pick["term_months"] if pick else None,
                     "why_he": why, "label_he": "חלופה להמחשה לבחינת הבנקאי — לא החלטת אשראי"}

    # ------------------------------------------------------------ recommendation wording
    first_names = _join_he([b["first_name_he"] for b in case["borrowers"]])
    purpose = loan.get("purpose_he") or "ההלוואה"
    months_by: dict[str, list[str]] = {}
    for i in ws["items"]:
        if i["kind"] == "missing" and i.get("period"):
            months_by.setdefault(i.get("borrower_he") or "", []).append(i["period"])
    missing_he = _join_he([f"תלושי שכר של {_month_list_he(sorted(ms))}" + (f" ({who})" if who and len(case["borrowers"]) > 1 else "")
                           if len(ms) > 1 else f"תלוש שכר של {_month_list_he(ms)}" for who, ms in months_by.items()]
                          + [i["title_he"] for i in ws["items"] if i["kind"] == "missing" and not i.get("period")]
                          + [c["item_he"] for c in corrections][:2])
    if rec_state == "READY_FOR_CREDIT_REVIEW":
        headline = ("התיק הושלם מבחינת מסמכים. על בסיס הנתונים שנאספו ניתן להתקדם לבחינת בקשת האשראי. "
                    + (f"נבחנו {len(scenarios)} חלופות מימון לצורך סימולציה. " if availability != "unavailable" else
                       "ניתוח החזר אישי אינו רלוונטי לתיק זה. ")
                    + "קביעת זכאות, סכום ותנאים מחייבת אימות נוסף והחלטת הבנק.")
        tone, doc_status = "ok", "המסמכים הושלמו"
        next_action = {"kind": "accept_documents" if awaiting else "credit_review", "label_he": "מעבר לטיפול בתיק",
                       "detail_he": (("מסמך אחד ממתין" if len(awaiting) == 1 else f"{len(awaiting)} מסמכים ממתינים")
                                     + " לקבלה שלך בסקירת המסמכים") if awaiting else "סקירת המסמכים והפעולות בתיק",
                       "v1_item": awaiting[0]["id"] if awaiting else None}
    elif rec_state == "PREPARATION_CONFIRMED":
        headline = ("הכנת מסמכי הבקשה אושרה על ידך. הנתונים מוכנים לבחינת האשראי על ידי הבנק; החלופות שלהלן להמחשה בלבד, "
                    "וקביעת זכאות, סכום ותנאים נעשית על ידי הבנק.")
        tone, doc_status = "ok", "הכנת התיק אושרה"
        next_action = {"kind": "credit_review", "label_he": "מעבר לטיפול בתיק", "detail_he": "סקירת המסמכים והפעולות בתיק",
                       "v1_item": None}
    elif rec_state == "CLARIFICATION_REQUIRED":
        if open_income:
            d = open_income[0]
            headline = (f"זוהה פער בין ההכנסה שהוצהרה ({_ils(d['declared']['value'])}) לבין הנתונים שחולצו מהתלושים "
                        f"({_ils(d['documented']['value'])}). מומלץ לאמת את הנתונים לפני שימוש בהם בניתוח ההחזר.")
        else:
            headline = (f"{len(judgment)} ממצאים ממתינים לשיקול דעתך לפני המשך הטיפול. מומלץ לבחון אותם לפני שימוש בנתונים "
                        "בניתוח ההחזר.")
        tone, doc_status = "warn", "נדרש בירור בנקאי"
        target = (open_income[0]["v1_item"] if open_income else judgment[0]["id"] if judgment else None)
        next_action = {"kind": "clarify", "label_he": "בירור הפער בסקירת המסמכים" if open_income else "בחינת הממצאים הפתוחים",
                       "v1_item": target}
    elif rec_state == "DOCUMENTS_INCOMPLETE":
        headline = ("נדרשת השלמת מסמכים לפני שניתן לגבש תמונה פיננסית מספקת."
                    + (f" חסר: {missing_he}." if missing_he else ""))
        tone, doc_status = "warn", "נדרשת השלמת מסמכים"
        first_missing = next((m for m in missing if not m["requested"]), None) or (missing[0] if missing else None)
        target = first_missing["v1_item"] if first_missing else corrections[0]["v1_item"] if corrections else None
        next_action = {"kind": "request_documents", "label_he": "בקשת ההשלמות מהלקוח", "v1_item": target}
    elif rec_state == "PROCESSING":
        headline, tone, doc_status = "JEEN עדיין בודק את המסמכים שהועלו. תמונת המצב תתעדכן אוטומטית בסיום הבדיקה.", "neutral", "בבדיקה"
        next_action = {"kind": "wait", "label_he": "ממתינים לסיום בדיקת המסמכים", "v1_item": None}
    elif rec_state == "NO_DOCUMENTS":
        headline = "טרם הועלו מסמכים לבקשה. אין עדיין בסיס מתועד לתמונה פיננסית — הנתונים שלהלן מוצהרים בלבד."
        tone, doc_status = "neutral", "ממתין למסמכים"
        next_action = {"kind": "request_documents", "label_he": "בקשת המסמכים מהלקוח", "v1_item": missing[0]["v1_item"] if missing else None}
    else:
        headline, tone, doc_status = "בדיקת המסמכים נתקלה בתקלה. אפשר להריץ שוב את הבדיקה מתוך היומן הטכני.", "bad", "תקלה בבדיקה"
        next_action = {"kind": "technical", "label_he": "מעבר לטיפול בתיק", "v1_item": None}

    if availability == "full":
        fin_text = ("בהתאם לנתונים הזמינים, אפשר לבחון מספר חלופות מימון. בחלופה לתקופה ארוכה יותר ההחזר החודשי נמוך יותר, "
                    "אך עלות המימון הכוללת גבוהה יותר.")
        if not docs_ready:
            fin_text += " לא מוצגת חלופה מומלצת עד להשלמת מסלול המסמכים."
        fin_status = "ניתוח מלא על בסיס נתונים מאומתים והקשר בנקאי"
    elif availability == "provisional":
        fin_text = (f"הניתוח הפיננסי זמני. על בסיס ההכנסה שאומתה בתלושים יחס ההחזר המשולב בחלופה שהתבקשה הוא {_pct(combined)}"
                    + (f"; על בסיס ההצהרה — {_pct(alt['combined_dsr_pct'])}" if alt else "")
                    + ". אין להסתמך על החלופות עד לבירור הפער.")
        fin_status = "ניתוח זמני — פער פתוח"
    elif availability == "partial":
        fin_text = "הניתוח חלקי: " + " ".join(reasons)
        fin_status = "ניתוח חלקי"
    else:
        fin_text, fin_status = " ".join(reasons), "ניתוח פיננסי לא זמין"

    considerations: list[dict] = []
    for r in income_rows:
        if r["quality"] == "verified" and r["documented_avg"]["value"] is not None:
            months_he = _join_he([m["period_he"].split()[0] for m in r["months"]]) + (f" {r['months'][0]['period'][:4]}" if r["months"] else "")
            gap = next((d for d in discrepancies if d["borrower_id"] == r["borrower_id"]), None)
            line = (f"הכנסה נטו של {r['first_name_he']} אומתה ב־{len(r['months'])} תלושים ({months_he}): ממוצע {_ils(r['documented_avg']['value'])}"
                    + (f"; פער פתוח מול ההצהרה ({_ils(r['declared']['value'])})." if gap and gap["open"] else
                       f"; תואם להצהרה ({_ils(r['declared']['value'])})." if r["declared"]["value"] else "."))
            considerations.append({"text_he": line, "tone": "warn" if gap and gap["open"] else "ok",
                                   "source_ids": [m["source_id"] for m in r["months"] if m["source_id"]] + [r["documented_avg"]["source_id"]]})
        elif r["quality"] == "declared" and r["declared"]["value"]:
            considerations.append({"text_he": f"ההכנסה של {r['first_name_he']} ({_ils(r['declared']['value'])}) מוצהרת בלבד — טרם אומתה במסמכים.",
                                   "tone": "warn", "source_ids": [r["declared"]["source_id"]]})
    if existing is not None:
        considerations.append({"text_he": (f"התחייבויות קיימות (הקשר בנקאי, לא מאומת): {len(loans)} הלוואות, החזר חודשי {_ils(existing)}"
                                           if len(loans) != 1 else f"התחייבויות קיימות (הקשר בנקאי, לא מאומת): הלוואה אחת, החזר חודשי {_ils(existing)}")
                                          + (f" — {_pct(existing_dsr)} מההכנסה." if existing_dsr is not None else "."),
                               "tone": "info", "source_ids": [sid_existing] + ([calc["existing_dsr"]["source_id"]] if "existing_dsr" in calc else [])})
    if app and combined is not None:
        over = combined > threshold
        considerations.append({"text_he": (f"ההלוואה המבוקשת ({_ils(amount)} · {term} תשלומים) מוסיפה כ־{_ils(app['monthly_payment_ils'])} לחודש; "
                                           f"יחס ההחזר המשולב {_pct(combined)} — {'מעל' if over else 'בתוך'} ההנחה ({_pct(threshold)})."
                                           + ("" if existing is not None else " היחס אינו כולל התחייבויות קיימות (אין נתונים).")),
                               "tone": "warn" if over or availability != "full" else "ok",
                               "source_ids": ["calc:proposed_payment", "calc:combined_dsr", sid_threshold]})
    if "ltv" in calc:
        considerations.append({"text_he": f"המימון מהווה {_pct(calc['ltv']['value'])} מהסכום בהצעת המחיר ({_ils(price)}).",
                               "tone": "warn" if calc["ltv"]["value"] > 100 else "info", "source_ids": [sid_price, "calc:ltv"]})
    if exposure:
        considerations.append({"text_he": (f"אובליגו מנוצל {_ils(exposure['utilized']['value'])} מתוך {_ils(exposure['approved']['value'])} מאושר"
                                           + (f"; חיובי כרטיס שוטפים ({_ils(spending[0]['avg_monthly_ils'])} בממוצע) אינם נספרים כהחזר חוב."
                                              if spending else ".")),
                               "tone": "info", "source_ids": [exposure["utilized"]["source_id"]] + [s["source_id"] for s in spending]})
    for e in events:
        if e["returned_checks_12m"] or e["arrears_12m"] or e["restrictions_he"]:
            considerations.append({"text_he": f"אירוע חשבון בהקשר הבנקאי ({e['owner_he']}): {' '.join(e['detail_he'])} יש לאמת במערכות הבנק; אינו קובע זכאות.",
                                   "tone": "warn", "source_ids": [e["source_id"]]})

    verify = []
    if awaiting:
        verify.append({"text_he": ("מסמך אחד נבדק ב-AI וממתין" if len(awaiting) == 1 else f"{len(awaiting)} מסמכים נבדקו ב-AI וממתינים")
                       + " לקבלה פורמלית שלך בסקירת המסמכים.", "v1_item": awaiting[0]["id"]})
    for d in open_income:
        verify.append({"text_he": f"לאמת את ההכנסה של {d['first_name_he']} מול ההצהרה (פער {abs(d['difference_pct'] or 0):.1f}%).", "v1_item": d["v1_item"]})
    for d in discrepancies:
        if d["kind"] == "purpose_amount":
            verify.append({"text_he": f"לברר את ההפרש בין הסכום המבוקש לסכום בהצעת המחיר ({_ils(d['difference_ils'])}).", "v1_item": d["v1_item"]})
    if contexts:
        verify.append({"text_he": "ההתחייבויות, המסגרות ואירועי החשבון מקורם בהקשר הבנקאי ולא אומתו — יש לאמת מול מערכות הבנק."})
    verify.append({"text_he": "תנועות דפי העו״ש לא נותחו; לא בוצעה הצלבה בין ההתחייבויות לבין החיובים בחשבון."})
    verify.append({"text_he": "לא נבדקו נתוני אשראי חיצוניים (אין חיבור למאגר נתוני אשראי)."})
    verify.append({"text_he": f"הריבית בסימולציה ({_pct(rate)}) והסף ליחס ההחזר הם הנחות לצורך החישוב; הריבית, הסכום והתנאים ייקבעו על ידי הבנק."})

    # ------------------------------------------------------------ risks & missing information
    risks = []
    for i in finding_items:
        if i["finding"]["status"] != "open" or any(d["v1_item"] == i["id"] for d in discrepancies):
            continue
        cited = [doc_fact(e["document_id"], e["field"]) for e in i["finding"]["evidence"]]
        risks.append({"kind": "finding", "title_he": i["finding"]["title_he"], "text_he": i["finding"]["message_he"],
                      "tone": "warn", "who_he": i["finding"]["review_state_he"], "v1_item": i["id"],
                      "source_ids": [s for s in cited if s]})
    for c in corrections:
        risks.append({"kind": "correction", "title_he": c["title_he"], "text_he": c["reason_he"], "tone": "warn",
                      "who_he": "דורש פעולה מהלקוח", "v1_item": c["v1_item"], "source_ids": []})
    for m in missing:
        risks.append({"kind": "missing", "title_he": m["title_he"], "text_he": m["status_he"], "tone": "miss",
                      "who_he": "חסר בתיק", "v1_item": m["v1_item"], "source_ids": []})
    unknowns = [{"label_he": "תנועות בדפי העו״ש", "text_he": "JEEN אימת את פרטי הדף (בעלים, תקופה, יתרת סגירה) אך לא חילץ תנועות."},
                {"label_he": "הוצאות מחיה ודיור", "text_he": "אינן כלולות בחישוב; ההכנסה שנותרת היא מדד תיאורי בלבד."},
                {"label_he": "נתוני אשראי חיצוניים", "text_he": "אין חיבור — לא נבדקו."}]
    if context_missing:
        unknowns.insert(0, {"label_he": "התחייבויות קיימות", "text_he": f"אין נתוני הקשר בנקאי עבור {_join_he(context_missing)}."})

    # ------------------------------------------------------------ draft responses (never sent from here)
    banker = case["banker"]["name_he"]
    hello = f"שלום {first_names},"
    sign = f"\n\nבברכה,\n{banker}\nמזרחי־טפחות"
    ref = lambda i: {"document_id": i["document_id"], "label_he": i["doc_type_he"] + (f" — {i['period_he']}" if i.get("period_he") else "")}
    drafts = []
    if missing or corrections:
        lines_he = [f"• {m['item_he']}" for m in missing] + [f"• {c['item_he']}" for c in corrections]
        drafts.append({"kind": "missing_documents", "title_he": "בקשת השלמת מסמכים",
                       "message_he": (f"{hello}\nכדי להמשיך בטיפול בבקשת ההלוואה ל{purpose} נבקש להשלים באפליקציה:\n" + "\n".join(lines_he)
                                      + "\nלאחר ההעלאה המסמכים ייבדקו ונעדכן אותך בהמשך הטיפול." + sign),
                       "attachments": [ref(i) for i in docs if i["group"] == "correction"]})
    for d in open_income:
        item = next(i for i in finding_items if i["id"] == d["v1_item"])
        body = item["drafts"]["explanation"]["message_he"]
        body = body.split(", ", 1)[1] if body.startswith("שלום ") and ", " in body else body
        drafts.append({"kind": "financial_clarification", "title_he": "בקשת הבהרה על ההכנסה",
                       "message_he": f"שלום {d['first_name_he']},\n{body}\nההבהרה תסייע לנו להשלים את בדיקת הבקשה." + sign,
                       "attachments": [ref(docs_by_id[m["source_id"].split(":")[1]]) for r in income_rows if r["borrower_id"] == d["borrower_id"]
                                       for m in r["months"] if m["source_id"]]})
    if docs_ready:
        drafts.append({"kind": "complete_documentation", "title_he": "אישור קבלת מסמכים",
                       "message_he": (f"{hello}\nקיבלנו את כל המסמכים הנדרשים לבקשת ההלוואה ל{purpose} "
                                      f"({_ils(amount)}, {term} תשלומים). הבקשה עוברת כעת לבדיקת הבנק, ונעדכן אותך כשתהיה התקדמות. "
                                      "ייתכן שנבקש פרטים נוספים במהלך הבדיקה.\nהודעה זו אינה אישור הלוואה ואינה התחייבות לתנאים." + sign),
                       "attachments": [ref(i) for i in docs]})
        if availability == "full" and scenarios:
            drafts.append({"kind": "conditional_financing", "title_he": "שיחת המשך — חלופות להמחשה",
                           "message_he": (f"{hello}\nלקראת שיחת ההמשך ריכזנו כמה חלופות פריסה להמחשה בלבד, בהנחת ריבית שנתית קבועה של "
                                          f"{_pct(rate)}:\n" + "\n".join(
                                              f"• {s['term_months']} תשלומים — כ־{_ils(s['monthly_payment_ils'])} לחודש "
                                              f"(סך התשלומים כ־{_ils(s['total_payments_ils'])})" for s in scenarios)
                                          + "\nהסכומים אינם הצעה מחייבת. הסכום, הריבית והתנאים ייקבעו על ידי הבנק לאחר השלמת הבדיקה "
                                            "ובכפוף לאישורו." + sign),
                           "attachments": [ref(purpose_doc)] if purpose_doc else []})
    recommended = {"DOCUMENTS_INCOMPLETE": "missing_documents", "NO_DOCUMENTS": "missing_documents",
                   "CLARIFICATION_REQUIRED": "financial_clarification" if open_income else None,
                   "READY_FOR_CREDIT_REVIEW": "complete_documentation", "PREPARATION_CONFIRMED": "complete_documentation"}.get(rec_state)
    if not any(d["kind"] == recommended for d in drafts):
        recommended = drafts[0]["kind"] if drafts else None

    return {
        "version": VERSION, "case_id": case_id, "generated_at": now_iso(), "disclaimer_he": DISCLAIMER_HE,
        "case": {"display_number": case["display_number"], "title_he": case["title_he"], "banker": case["banker"],
                 "bank_stage": case["bank_stage"], "submitted_at": case.get("submitted_at")},
        "applicant": {"entity": profile.get("entity", "individual"), "entity_he": profile.get("entity_he"),
                      "profile_label_he": profile.get("profile_label_he") or case.get("profile_label_he"),
                      "company": profile.get("company"), "borrowers": borrowers_out,
                      "co_borrowers": [b["name_he"] for b in case["borrowers"] if b.get("role") == "co_borrower"]},
        "loan": {"product_he": loan.get("product_he"), "purpose_he": loan.get("purpose_he"), "note_he": loan.get("note_he"),
                 "amount": _datum(amount, sid_amount), "term": _datum(term, sid_term, "months"),
                 "asset": {"price": _datum(price, sid_price), "subject_source_id": sid_subject,
                           "label_he": "מחיר לפי הצעת המחיר" if loan.get("purpose") == "car" else "סכום לפי האסמכתה"} if purpose_doc else None},
        "documents": {"state": state, "state_he": ws["review_state"]["label_he"], "case_status": case_status,
                      "progress": ws.get("progress"), "total": len(docs), "accepted": len(accepted), "awaiting_decision": len(awaiting),
                      "missing": missing, "corrections": corrections, "open_findings": len(judgment),
                      "requirements": [{"title_he": r["title_he"], "family_he": r.get("family_he"), "satisfied": r["satisfied"],
                                        "state_he": r["ai_state_he"], "inactive": bool(r.get("inactive"))}
                                       for r in ws.get("requirement_matrix") or [] if not r.get("inactive")]},
        "income": {"borrowers": income_rows, "total": _datum(income_total, sid_income), "business_income": business},
        "bank_context": {"available": bool(contexts), "missing_for": context_missing, "source": financial_context.source(),
                         "observed_at": contexts[0]["observed_at"] if contexts else None,
                         "fixture_ids": [c["fixture_id"] for c in contexts],
                         "accounts": [{**c["account"], "owner_he": names[c["borrower_id"]]["first_name_he"]} for c in contexts],
                         "loans": loans, "credit_lines": lines, "card_spending": spending, "events": events, "exposure": exposure},
        "analysis": {"availability": availability, "status_he": fin_status, "reasons_he": reasons,
                     "existing_debt": _datum(existing, sid_existing), "income": _datum(income_total, sid_income), **calc,
                     "declared_alternative": alt, "illustrative_max_principal": max_amount},
        "simulation": {"inputs": {"principal": amount, "term_months": term, "annual_rate_pct": rate},
                       "income_ils": income_total, "existing_debt_ils": existing, "asset_price_ils": price,
                       "threshold_pct": threshold, "threshold_source_id": sid_threshold, "rate_source_id": sid_rate,
                       "income_source_id": sid_income, "existing_source_id": sid_existing, "asset_source_id": sid_price,
                       "bounds": {"term_min": finance.DEMO_TERM_MIN, "term_max": finance.DEMO_TERM_MAX, "step": finance.SCENARIO_STEP_MONTHS,
                                  "principal_max": max(int(price or 0), int((amount or 0) * 2), 50000)},
                       "scenarios": scenarios, "suggested": suggested, "enabled": bool(scenarios)},
        "recommendation": {"state": rec_state, "tone": tone, "headline_he": headline, "next_action": next_action,
                           "documentation": {"status_he": doc_status, "case_status": case_status},
                           "financial": {"availability": availability, "status_he": fin_status, "text_he": fin_text,
                                         "suggested": suggested},
                           "considerations": considerations, "verify": verify},
        "discrepancies": discrepancies, "risks": risks, "unknowns": unknowns,
        "drafts": drafts, "recommended_draft": recommended, "sources": src.items,
    }
