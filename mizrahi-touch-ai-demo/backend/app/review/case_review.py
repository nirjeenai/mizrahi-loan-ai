"""Case-level review of the income-document set — deterministic coverage and identity
checks, Stage D semantic cross-document review (Gemini) and the case rubric.

Arithmetic and month logic are code. Gemini only judges meaning (are these figures
comparable, is a difference grounded) and never sees a customer explanation as proof."""
from __future__ import annotations

import json
from datetime import date, timedelta
from statistics import mean
from typing import Any

from ..config import settings
from ..llm import gemini as g
from ..util import now_iso, stable_hash
from . import deterministic as det
from . import prompts as P
from . import reason_codes as RC
from . import rubrics as R
from .contract import CaseReviewRequest, CaseReviewResult, CriterionOutcome, DesiredFinding, EvidenceRef, ProgressFn, ProviderIdentity

_SEMANTIC_CACHE: dict[str, dict] = {}

STATE_BY_ESCALATION = {"customer": "CUSTOMER_ACTION_REQUIRED", "banker": "NEEDS_BANKER_REVIEW"}
DOC_FINDING_TEXT = {
    "UNEXPECTED_DOCUMENT_TYPE": ("המסמך אינו תלוש שכר", "המסמך {file} אינו תלוש שכר. יש להעלות תלוש שכר במקומו."),
    "DOCUMENT_UNREADABLE": ("המסמך אינו קריא", "לא ניתן לקרוא את {file}. יש להעלות עותק ברור יותר (PDF מקורי או צילום חד)."),
    "PERIOD_UNCLEAR": ("תקופת השכר לא ברורה", "בתלוש {file} לא ניתן לזהות תקופת שכר חד־משמעית."),
    "MANDATORY_FIELD_MISSING": ("חסר שדה חובה בתלוש", "בתלוש {file} חסר שדה חובה: {detail}"),
    "INTERNAL_ARITHMETIC_MISMATCH": ("אי־התאמה חשבונית בתלוש", "בתלוש {file} הסכומים אינם מתיישבים: {detail}"),
    "UNTRUSTED_INSTRUCTION_IN_DOCUMENT": ("טקסט חשוד במסמך", "בתלוש {file} נמצא טקסט המופנה למערכת או לבודק. הטקסט לא בוצע; המסמך הועבר לבדיקת בנקאי."),
    "EVIDENCE_UNVERIFIED": ("ראיה לא אומתה מול הקובץ", "בתלוש {file} חלק מהערכים המכריעים לא אומתו מול הקובץ המקורי: {detail}"),
    "PAY_DATE_INCONSISTENT": ("תאריך תשלום חריג", "בתלוש {file} תאריך התשלום אינו מתיישב עם תקופת השכר: {detail}"),
}
# the same criteria when the review could not decide: a person looks first, the customer is not told the file is wrong
DOC_FINDING_UNCERTAIN_TEXT = {
    "UNEXPECTED_DOCUMENT_TYPE": ("לא ברור אם המסמך הוא תלוש שכר",
                                 "בדיקת ה-AI לא הצליחה לקבוע אם {file} הוא תלוש שכר. המסמך הועבר לבדיקת בנקאי."),
    "DOCUMENT_UNREADABLE": ("לא ברור אם המסמך קריא במלואו",
                            "בדיקת ה-AI לא הצליחה לקבוע אם {file} קריא ושלם. המסמך הועבר לבדיקת בנקאי."),
}
UNCERTAIN_FALLBACK = "{detail} — לא הוכרע בבדיקת ה-AI, הועבר לבדיקת בנקאי."


def _first(borrower: dict) -> str:
    return borrower["name_he"].split()[0]


def _evidence(doc: dict, field: str) -> list[EvidenceRef]:
    for f in doc["review"]["facts"]:
        if f["field"] == field and f.get("evidence"):
            return [EvidenceRef(**f["evidence"])]
    return []


def _fact(doc: dict, field: str) -> dict | None:
    return next((f for f in doc["review"]["facts"] if f["field"] == field), None)


def income_comparable(review: dict, policy: dict) -> bool:
    """Whether a payslip's net pay may enter the declared-income comparison. With the policy's list of income-relevant
    criteria, a criterion that does not bear on the compared amounts (the payment-date check, say) cannot exclude it."""
    required = policy.get("income_comparison_requires_pass")
    if not required:
        return review["verdict"] == "VALID"
    outcomes = {c["criterion_id"]: c["outcome"] for c in review["criteria"]}
    return review["verdict"] != "INVALID" and all(outcomes.get(cid) == "PASS" for cid in required)


def _rubric_of(review: dict) -> dict:
    return R.all_rubrics().get(f"{review['rubric_id']}@{review['rubric_version']}") or {}


def _document_findings(d: dict, family: str) -> list[DesiredFinding]:
    """A non-payslip document's failed or undecided checks. One root cause per document, as for payslips: a doubt
    about the type or the legibility explains every downstream gap."""
    r = d["review"]
    rubric = _rubric_of(r)
    by_id = {c["criterion_id"]: c for c in r["criteria"]}
    type_id, legible_id = rubric.get("type_criterion"), rubric.get("legibility_criterion")
    type_outcome = by_id.get(type_id, {}).get("outcome")
    # a legible document of another type (a payslip in the ID card) is "not an ID card", even when the judge also found
    # the ID fields "illegible"; a file that could not be read at all is reported as unreadable
    if type_outcome == "FAIL" and r.get("doc_type") not in ("unreadable", None) and r.get("legibility") != "unreadable":
        reported = [by_id[type_id]]
    elif by_id.get(legible_id, {}).get("outcome") in ("FAIL", "NEEDS_REVIEW"):
        reported = [by_id[legible_id]]
    elif type_outcome in ("FAIL", "NEEDS_REVIEW"):
        reported = [by_id[type_id]]
    else:
        reported = r["criteria"]
    out = []
    for c in reported:
        if c["outcome"] not in ("FAIL", "NEEDS_REVIEW") or not c.get("reason_code"):
            continue
        code = c["reason_code"]
        state = STATE_BY_ESCALATION.get(c.get("escalation") or "banker", "NEEDS_BANKER_REVIEW")
        uncertain = state == "CUSTOMER_ACTION_REQUIRED" and c["outcome"] != "FAIL"
        if uncertain:
            state = "NEEDS_BANKER_REVIEW"                # an undecided check goes to a person, never back to the customer
        title, message = RC.document_text(code, family, d["filename"], c["explanation_he"], uncertain, c["title_he"])
        out.append(DesiredFinding(
            key=f"{code}:{d['document_id']}", code=code, severity=c["severity"], review_state=state,
            borrower_id=d["borrower_id"], document_id=d["document_id"], period=None, title_he=title, message_he=message,
            detail={"criterion_id": c["criterion_id"], "document_verdict": r["verdict"], "run_id": r["run_id"],
                    "requirement_code": d.get("requirement_code"), "family": family},
            evidence=[e for fid in c.get("evidence_ids", []) for e in _evidence(d, fid.split(":", 1)[1])]))
    return out


def _requirement_coverage(ctx: dict, documents: list[dict], as_of: date, findings: list[DesiredFinding],
                          criteria: list[CriterionOutcome]) -> dict[str, Any]:
    """Non-payslip requirements: is there a document for each, and do the statements of an account cover the window."""
    out: dict[str, Any] = {}
    names = {b["borrower_id"]: b["name_he"].split()[0] for b in ctx["borrowers"]}
    for q in ctx.get("requirements") or []:
        if q["family"] == "payslip" or not q.get("required", True):
            continue
        code = q["code"]
        mine = [d for d in documents if d.get("requirement_code") == code]
        reviewed = [d for d in mine if d.get("review")]
        entry: dict[str, Any] = {"documents": [d["document_id"] for d in mine], "gaps": []}
        if not mine:
            findings.append(DesiredFinding(
                key=f"{RC.REQUIRED_DOCUMENT_MISSING}:{code}", code=RC.REQUIRED_DOCUMENT_MISSING, severity="blocking",
                review_state="CUSTOMER_ACTION_REQUIRED", borrower_id=q.get("borrower_id"),
                title_he=f"חסר: {q['title_he']}", message_he=f"כדי להשלים את בקשת ההלוואה חסר: {q['title_he']}.",
                detail={"requirement_code": code, "family": q["family"]}))
        if q["family"] == "bank_statement" and reviewed:
            ranges = []
            for d in reviewed:
                facts = {f["field"]: f for f in d["review"]["facts"]}
                start = (facts.get("statement_from") or {}).get("value_normalized")
                end = (facts.get("statement_to") or {}).get("value_normalized")
                types_ok = d["review"]["doc_type"] == "bank_statement" and d["review"]["verdict"] != "INVALID"
                if start and end and types_ok:
                    ranges.append((date.fromisoformat(start), date.fromisoformat(end)))
            days = int((q.get("rules") or {}).get("coverage_days", 90))
            max_age = int((q.get("rules") or {}).get("max_age_days", 30))
            if ranges:
                # the window ends at the latest statement, or at the oldest acceptable end date when that is later
                latest = max(max(b for _, b in ranges), as_of - timedelta(days=max_age))
                lo, hi = det.window(latest, days)
                gaps = det.coverage_gaps(ranges, lo, hi)
                entry.update({"window": [lo.isoformat(), hi.isoformat()],
                              "covered": [[a.isoformat(), b.isoformat()] for a, b in sorted(ranges)],
                              "gaps": [[a.isoformat(), b.isoformat()] for a, b in gaps]})
                if gaps:
                    listed = ", ".join(f"{det.day_he(a)}–{det.day_he(b)}" for a, b in gaps)
                    holders = " ו".join(names.get(h, h) for h in q.get("holders") or [])
                    findings.append(DesiredFinding(
                        key=f"{RC.STATEMENT_PERIOD_GAP}:{code}", code=RC.STATEMENT_PERIOD_GAP, severity="blocking",
                        review_state="CUSTOMER_ACTION_REQUIRED", borrower_id=q.get("borrower_id"),
                        title_he=f"חסרה תקופה בדפי העו״ש — {holders}",
                        message_he=(f"דפי העו״ש שהועלו לחשבון אינם מכסים את {days} הימים האחרונים. חסרה התקופה: {listed}. "
                                    "נא להעלות דף תנועות שמכסה אותה."),
                        detail={"requirement_code": code, "family": q["family"], "gaps": entry["gaps"], "window": entry["window"]}))
        satisfied = bool(mine) and not entry["gaps"]
        criteria.append(CriterionOutcome(criterion_id=f"RQ:{code}", title_he=q["title_he"], method="deterministic",
                                         outcome="PASS" if satisfied else "FAIL", severity="blocking",
                                         reason_code=RC.STATEMENT_PERIOD_GAP if entry["gaps"] else RC.REQUIRED_DOCUMENT_MISSING,
                                         explanation_he=("הועלה מסמך" if satisfied else
                                                         "חסרה תקופה" if entry["gaps"] else "טרם הועלה מסמך")))
        out[code] = entry
    return out


def run(identity: ProviderIdentity, req: CaseReviewRequest, progress: ProgressFn) -> CaseReviewResult:
    started = now_iso()
    rubric = req.rubric
    policy = rubric["policy"]
    ctx = req.case_context
    as_of = date.fromisoformat(ctx["simulation_date"])
    requested = det.requested_months(as_of, ctx.get("payslip_months") or policy["requested_months"],
                                     policy["payday_day_of_next_month"])
    borrowers = {b["borrower_id"]: b for b in ctx["borrowers"]}
    family_by_code = {q["code"]: q["family"] for q in ctx.get("requirements") or []}

    def family(d: dict) -> str:
        return family_by_code.get(d.get("requirement_code") or "", "payslip")

    reviewed = [d for d in req.documents if d.get("review")]
    findings: list[DesiredFinding] = []
    criteria: list[CriterionOutcome] = []
    coverage: dict[str, Any] = {}
    income: dict[str, Any] = {}

    progress("case_coverage")
    for d in reviewed:                                    # document-level outcomes become findings
        r = d["review"]
        if family(d) != "payslip":
            findings += _document_findings(d, family(d))
            continue
        if r.get("file_name_period") and r.get("period") and r["file_name_period"] != r["period"]:
            findings.append(DesiredFinding(
                key=f"FILE_NAME_PERIOD_MISMATCH:{d['document_id']}", code="FILE_NAME_PERIOD_MISMATCH", severity="info",
                review_state="INFO", borrower_id=d["borrower_id"], document_id=d["document_id"], period=r["period"],
                title_he="שם הקובץ אינו תואם את החודש המודפס",
                message_he=f"שם הקובץ {d['filename']} מציין את {det.month_label_he(r['file_name_period'])}, "
                           f"אך במסמך עצמו מודפס {det.month_label_he(r['period'])}. הבדיקה מסתמכת על החודש המודפס.",
                detail={"file_name_claims": r["file_name_period"], "document_prints": r["period"]},
                evidence=_evidence(d, "salary_period")))
        by_id = {c["criterion_id"]: c for c in r["criteria"]}
        # one root cause per document: an unreadable page or a non-payslip — or the doubt about either — explains every
        # downstream gap (no period, no net pay), so only that question is reported
        if by_id.get("PS-02", {}).get("outcome") in ("FAIL", "NEEDS_REVIEW"):
            reported = [by_id["PS-02"]]
        elif by_id.get("PS-01", {}).get("outcome") in ("FAIL", "NEEDS_REVIEW"):
            reported = [by_id["PS-01"]]
        else:
            reported = r["criteria"]
        for c in reported:
            if c["outcome"] not in ("FAIL", "NEEDS_REVIEW") or c["criterion_id"] == "PS-03" or not c.get("reason_code"):
                continue
            code = c["reason_code"]
            review_state = STATE_BY_ESCALATION.get(c.get("escalation") or "banker", "NEEDS_BANKER_REVIEW")
            if review_state == "CUSTOMER_ACTION_REQUIRED" and c["outcome"] != "FAIL":
                # only a failed check is sent back to the customer; an undecided one goes to the banker
                review_state = "NEEDS_BANKER_REVIEW"
                title, template = DOC_FINDING_UNCERTAIN_TEXT.get(code, (c["title_he"], UNCERTAIN_FALLBACK))
            else:
                title, template = DOC_FINDING_TEXT.get(code, (c["title_he"], "{detail}"))
            findings.append(DesiredFinding(
                key=f"{code}:{d['document_id']}", code=code, severity=c["severity"],
                review_state=review_state,
                borrower_id=d["borrower_id"], document_id=d["document_id"], period=r.get("period"), title_he=title,
                message_he=template.format(file=d["filename"], detail=c["explanation_he"]),
                detail={"criterion_id": c["criterion_id"], "document_verdict": r["verdict"], "run_id": r["run_id"]},
                evidence=[e for fid in c.get("evidence_ids", []) for e in _evidence(d, fid.split(":", 1)[1])]))

    requirement_coverage = _requirement_coverage(ctx, req.documents, as_of, findings, criteria)
    # payslip months are asked only of a borrower the policy gives a payslip requirement (not a self-employed applicant
    # or a company signatory); a context without a requirements list keeps the payslip-only behaviour
    listed = ctx.get("requirements")
    with_payslips = {q.get("borrower_id") for q in listed or [] if q["family"] == "payslip"}
    for bid, b in borrowers.items():
        if listed is not None and bid not in with_payslips:
            income[bid] = {"declared_net_monthly_ils": b.get("declared_net_monthly_ils"),
                           "declaration_note_he": b.get("declaration_note_he"),
                           "declared_provenance": b.get("declared_income_provenance"), "months": {}}
            continue
        assigned = [d for d in reviewed if d["borrower_id"] == bid and family(d) == "payslip"]
        counting, mismatched = [], []
        for d in assigned:
            r = d["review"]
            crit = {c["criterion_id"]: c for c in r["criteria"]}
            if r["doc_type"] != "payslip":
                continue
            if crit.get("PS-03", {}).get("outcome") == "FAIL":
                mismatched.append(d)
                continue
            if r.get("period"):
                counting.append(d)
        cov = det.coverage([d["review"]["period"] for d in counting], requested)
        coverage[bid] = {**cov, "documents": [{"document_id": d["document_id"], "filename": d["filename"],
                                               "period": d["review"]["period"], "verdict": d["review"]["verdict"],
                                               "file_name_period": d["review"].get("file_name_period")} for d in counting]}
        for m in cov["missing"]:
            findings.append(DesiredFinding(
                key=f"REQUIRED_PERIOD_MISSING:{bid}:{m}", code="REQUIRED_PERIOD_MISSING", severity="blocking",
                review_state="CUSTOMER_ACTION_REQUIRED", borrower_id=bid, period=m,
                title_he=f"חסר תלוש שכר ל{det.month_label_he(m)} — {_first(b)}",
                message_he=f"כדי להשלים את מסמכי השכר של {_first(b)} חסר תלוש שכר לחודש {det.month_label_he(m)}. "
                           f"החודשים הנדרשים: {', '.join(det.month_label_he(x) for x in requested)}.",
                detail={"requested": requested, "covered": cov["distinct"]}))
        for m, n in cov["duplicates"].items():
            dups = [d for d in counting if d["review"]["period"] == m]
            names = ", ".join(d["filename"] for d in dups)
            claimed = [f"{d['filename']} (שם הקובץ: {det.month_label_he(d['review']['file_name_period'])})"
                       for d in dups if d["review"].get("file_name_period") and d["review"]["file_name_period"] != m]
            action = bool(cov["missing"])
            findings.append(DesiredFinding(
                key=f"DUPLICATE_PERIOD:{bid}:{m}", code="DUPLICATE_PERIOD", severity="minor" if not action else "major",
                review_state="CUSTOMER_ACTION_REQUIRED" if action else "INFO", borrower_id=bid, period=m,
                title_he=f"התקבלו {n} תלושים ל{det.month_label_he(m)} — {_first(b)}",
                message_he=(f"התקבלו {n} מסמכים שמודפס בהם {det.month_label_he(m)}: {names}."
                            + (f" {'; '.join(claimed)}." if claimed else "")
                            + (" החודש החסר עדיין נדרש." if action else " כל החודשים הנדרשים כוסו — אין צורך בפעולה.")),
                detail={"documents": [d["document_id"] for d in dups], "copies": n},
                evidence=[e for d in dups for e in _evidence(d, "salary_period")]))
        for d in mismatched:
            r = d["review"]
            other = borrowers.get(r.get("matched_borrower_id") or "")
            ps03 = next(c for c in r["criteria"] if c["criterion_id"] == "PS-03")
            findings.append(DesiredFinding(
                key=f"BORROWER_MISMATCH:{d['document_id']}", code="BORROWER_MISMATCH", severity="blocking",
                review_state="CUSTOMER_ACTION_REQUIRED", borrower_id=bid, document_id=d["document_id"],
                period=r.get("period"), title_he=f"המסמך אינו של {_first(b)}",
                message_he=f"המסמך {d['filename']} הועלה עבור {_first(b)}, אך {ps03['explanation_he']}. "
                           + (f"נראה שזהו מסמך של {_first(other)} — יש לשייך אותו מחדש או להעלות את המסמך הנכון." if other
                              else "יש להעלות את התלוש הנכון."),
                detail={"assigned": bid, "document_identifies": r.get("matched_borrower_id")},
                evidence=_evidence(d, "employee_id") + _evidence(d, "employee_name")))
        criteria.append(CriterionOutcome(criterion_id=f"IS-01:{bid}", title_he=f"כיסוי החודשים הנדרשים — {_first(b)}",
                                         method="deterministic", outcome="PASS" if not cov["missing"] else "FAIL",
                                         severity="blocking", reason_code="REQUIRED_PERIOD_MISSING",
                                         explanation_he=("כל החודשים מכוסים" if not cov["missing"] else
                                                         "חסרים: " + ", ".join(det.month_label_he(m) for m in cov["missing"]))))
        criteria.append(CriterionOutcome(criterion_id=f"IS-02:{bid}", title_he=f"כפילות חודשים — {_first(b)}",
                                         method="deterministic",
                                         outcome="FAIL" if cov["duplicates"] and cov["missing"] else "PASS",
                                         severity="minor", reason_code="DUPLICATE_PERIOD",
                                         explanation_he=("אין כפילות" if not cov["duplicates"] else
                                                         "כפילות ב: " + ", ".join(det.month_label_he(m) for m in cov["duplicates"]))))
        criteria.append(CriterionOutcome(criterion_id=f"IS-03:{bid}", title_he=f"שיוך מסמכים ללווה — {_first(b)}",
                                         method="deterministic", outcome="FAIL" if mismatched else "PASS",
                                         severity="blocking", reason_code="BORROWER_MISMATCH",
                                         explanation_he=f"{len(mismatched)} מסמכים שויכו בטעות" if mismatched else "כל המסמכים שויכו נכון"))
        invalid = [d for d in counting if d["review"]["verdict"] != "VALID"]
        criteria.append(CriterionOutcome(criterion_id=f"IS-06:{bid}", title_he=f"תקינות מסמכי השכר — {_first(b)}",
                                         method="deterministic", outcome="PASS" if not invalid else "NEEDS_REVIEW",
                                         severity="major", reason_code="DOCUMENT_NOT_VALID",
                                         explanation_he=("כל התלושים נמצאו תקינים" if not invalid else
                                                         f"{len(invalid)} תלושים דורשים בדיקה")))
        nets: dict[str, dict] = {}
        for d in sorted((x for x in counting if income_comparable(x["review"], policy)), key=lambda x: x["uploaded_at"]):
            m = d["review"]["period"]
            net, gross = _fact(d, "net_pay"), _fact(d, "gross_pay")
            if m in requested and m not in nets and net and net.get("value_normalized") is not None:
                nets[m] = {"document_id": d["document_id"], "net": net["value_normalized"],
                           "gross": gross["value_normalized"] if gross else None,
                           "net_witness": (net.get("evidence") or {}).get("witness"),
                           "document_verdict": d["review"]["verdict"],
                           "earnings": [l.get("label") for l in d["review"].get("payroll_lines", {}).get("earnings", [])]}
        declared = b.get("declared_net_monthly_ils")
        stats: dict[str, Any] = {"declared_net_monthly_ils": declared, "declaration_note_he": b.get("declaration_note_he"),
                                 "declared_provenance": b.get("declared_income_provenance"), "months": nets}
        if nets and declared:
            avg = round(mean(v["net"] for v in nets.values()), 2)
            stats.update({"average_documented_net_ils": avg, "difference_ils": round(avg - declared, 2),
                          "difference_pct": round((avg - declared) / declared * 100, 2),
                          "months_compared": sorted(nets)})
        income[bid] = stats

    progress("semantic_review")
    semantic = _semantic(req, borrowers, income)
    sem_by = {s["borrower_id"]: s for s in semantic.get("borrowers", [])}
    tol = float(policy["income_variance_tolerance_pct"])
    for bid, b in borrowers.items():
        stats, s = income[bid], sem_by.get(bid)
        if "difference_pct" in stats and "self_employed" in (b.get("income_sources") or []):
            # the declaration covers salary and business income; payslips show the salary part only
            criteria.append(CriterionOutcome(criterion_id=f"IS-04:{bid}", title_he=f"הכנסה מוצהרת מול תלושים — {_first(b)}",
                                             method="judge", outcome="NOT_APPLICABLE", severity="major",
                                             reason_code="DECLARED_VS_DOCUMENT_INCOME_VARIANCE",
                                             explanation_he=(f"הכנסה משולבת: ההצהרה ({stats['declared_net_monthly_ils']:,.0f} ₪) כוללת גם "
                                                             f"הכנסה מעסק, והתלושים ({stats['average_documented_net_ils']:,.0f} ₪ בממוצע) "
                                                             "מראים רק את השכר — אין השוואה אוטומטית; ההכנסה מהעסק מתועדת "
                                                             "בשומה או באישור הרו״ח לשיקול הבנקאי."),
                                             decided_by="code"))
            continue
        if "difference_pct" not in stats:
            no_payslips = listed is not None and bid not in with_payslips
            criteria.append(CriterionOutcome(criterion_id=f"IS-04:{bid}", title_he=f"הכנסה מוצהרת מול תלושים — {_first(b)}",
                                             method="judge", outcome="NOT_APPLICABLE", severity="major",
                                             reason_code="DECLARED_VS_DOCUMENT_INCOME_VARIANCE",
                                             explanation_he=("לא נדרשים תלושי שכר מלווה זה — ההכנסה מתועדת במסמכים אחרים "
                                                             "לשיקול הבנקאי" if no_payslips else "אין עדיין תלושים מאומתים להשוואה"),
                                             decided_by="code"))
            continue
        # the numeric band is code's decision; the model only judges whether the figures are comparable
        within = abs(stats["difference_pct"]) <= tol
        assessment = (s or {}).get("income_assessment", "INSUFFICIENT_EVIDENCE")
        comparable = bool((s or {}).get("definitions_equivalent", False))
        if within and comparable:
            outcome, who = "PASS", "code"
        elif within:
            outcome, who = "NEEDS_REVIEW", "code+judge"
        else:
            outcome, who = ("FAIL" if assessment == "INCONSISTENT" else "NEEDS_REVIEW"), "code+judge"
        compared = stats["months_compared"]
        partial = len(compared) < len(requested)
        missing_months = [m for m in requested if m not in compared]
        basis = (f"בתלוש {det.month_label_he(compared[0])}" if len(compared) == 1 else
                 f"ממוצע {len(compared)} תלושים")
        explanation = (f"מוצהר {stats['declared_net_monthly_ils']:,.0f} ₪ נטו · {basis} {stats['average_documented_net_ils']:,.0f} ₪ "
                       f"({stats['difference_pct']:+.1f}%)" + (f" · השוואה ראשונית, {len(compared)} מתוך {len(requested)} חודשים" if partial else "")
                       + ". " + ((s or {}).get("explanation_he") or ""))
        criteria.append(CriterionOutcome(criterion_id=f"IS-04:{bid}", title_he=f"הכנסה מוצהרת מול תלושים — {_first(b)}",
                                         method="judge", outcome=outcome, severity="major",
                                         reason_code="DECLARED_VS_DOCUMENT_INCOME_VARIANCE", explanation_he=explanation,
                                         decided_by=who, escalation="banker",
                                         evidence_ids=[f"{v['document_id']}:net_pay" for v in stats["months"].values()]))
        if outcome != "PASS":
            ev = [EvidenceRef(**f["evidence"]) for d in reviewed for f in d["review"]["facts"]
                  if f["field"] == "net_pay" and f.get("evidence")
                  and d["document_id"] in {v["document_id"] for v in stats["months"].values()}]
            findings.append(DesiredFinding(
                key=f"DECLARED_VS_DOCUMENT_INCOME_VARIANCE:{bid}", code="DECLARED_VS_DOCUMENT_INCOME_VARIANCE",
                severity="major", review_state="NEEDS_BANKER_REVIEW", borrower_id=bid,
                title_he=f"פער בין ההכנסה המוצהרת לתלושים — {_first(b)}",
                message_he=(f"בבקשה הוצהרה הכנסה נטו של {stats['declared_net_monthly_ils']:,.0f} ₪ לחודש. "
                            + (f"השוואה ראשונית על בסיס {len(compared)} מתוך {len(requested)} החודשים הנדרשים: "
                               f"{basis} הנטו הוא {stats['average_documented_net_ils']:,.0f} ₪ ({stats['difference_pct']:+.1f}%). "
                               f"חסרים עדיין: {', '.join(det.month_label_he(m) for m in missing_months)}. " if partial else
                               f"בתלושים שנבדקו ממוצע הנטו הוא {stats['average_documented_net_ils']:,.0f} ₪ "
                               f"({stats['difference_pct']:+.1f}%), על בסיס כל {len(requested)} החודשים הנדרשים. ")
                            + "הפער הועבר לבדיקת הבנקאי; הסבר הלקוח, אם נמסר, מצורף אך אינו מהווה ראיה."),
                detail={"stats": stats, "assessment": assessment, "semantic": s or {},
                        "basis": "preliminary" if partial else "complete", "months_compared": compared,
                        "months_required": requested, "months_missing": missing_months}, evidence=ev))
        if s and s.get("identity_assessment") == "INCONSISTENT":
            findings.append(DesiredFinding(
                key=f"IDENTITY_INCONSISTENT:{bid}", code="IDENTITY_INCONSISTENT", severity="major",
                review_state="NEEDS_BANKER_REVIEW", borrower_id=bid, title_he=f"אי־עקביות בזהות — {_first(b)}",
                message_he=s.get("identity_explanation_he") or "נמצאה אי־עקביות בפרטי הזהות בין המסמכים.",
                detail={"semantic": s}))
    return CaseReviewResult(run_id=req.run_id, case_id=req.case_id, identity=identity, rubric_id=rubric["rubric_id"],
                            rubric_version=rubric["version"], started_at=started, finished_at=now_iso(),
                            coverage={"requested": requested, "by_borrower": coverage, "by_requirement": requirement_coverage},
                            income=income, semantic=semantic.get("borrowers", []), criteria=criteria, findings=findings,
                            limitations_he=list(semantic.get("limitations_he") or []) + [
                                "הדרישות נגזרות ממדיניות המסמכים שהוצמדה לתיק (נתוני הדגמה) — אינן רשימה מאומתת של הבנק.",
                                "החודשים והתקופות הנדרשים מחושבים לפי תאריך הסימולציה ומדיניות ניתנת להגדרה."],
                            usage={"semantic_cached": semantic.get("_cached", False),
                                   "semantic_source_run": semantic.get("_source_run")})


def _semantic(req: CaseReviewRequest, borrowers: dict, income: dict) -> dict:
    payload = []
    for bid, b in borrowers.items():
        stats = income[bid]
        if not stats.get("months"):
            continue
        statements = [s["text"] for s in req.statements if s.get("borrower_id") in (bid, None)]
        counted = {v["document_id"] for v in stats["months"].values()}
        names = sorted({f.get("value_raw") for d in req.documents if d.get("review") and d["document_id"] in counted
                        for f in d["review"]["facts"] if f["field"] == "employee_name" and f.get("value_raw")})
        payload.append({"borrower_id": bid, "name_on_bank_case": b["name_he"],
                        "declared": {"net_monthly_ils": stats["declared_net_monthly_ils"],
                                     "note": stats.get("declaration_note_he"), "provenance": stats.get("declared_provenance")},
                        "documented_by_month": stats["months"],
                        "computed": {k: stats.get(k) for k in ("average_documented_net_ils", "difference_ils",
                                                               "difference_pct", "months_compared")},
                        "names_printed_on_documents": names,
                        "customer_statements_unverified": statements})
    if not payload:
        return {"borrowers": [], "limitations_he": []}
    key = stable_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    if key in _SEMANTIC_CACHE:
        return {**_SEMANTIC_CACHE[key], "_cached": True}
    prompt = ("Assess each borrower. Input (all arithmetic already computed by code):\n"
              f"{json.dumps(payload, ensure_ascii=False, indent=1, default=str)}\nReturn JSON only.")
    data = g.generate(settings.model_judge, [{"role": "user", "parts": [g.text_part(prompt)]}], purpose="semantic_review",
                      run_id=req.run_id, system=P.SEMANTIC_SYSTEM, schema=P.SEMANTIC_SCHEMA, thinking="low")
    out = g.response_json(data)
    out["_source_run"] = req.run_id
    _SEMANTIC_CACHE[key] = out
    return out
