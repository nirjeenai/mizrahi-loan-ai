"""The banker's evidence package and review workspace — built from persisted state only."""
from __future__ import annotations

from typing import Any, Optional

from ..bank.mock_bank import bank
from ..review import deterministic as det
from ..review import prompts as P
from ..review import rubrics
from ..store import repo
from ..util import now_iso
from ..workflow import desk_state, outcomes, readiness, review_desk
from ..workflow.engine import BANKER_RULINGS, COVERAGE_CODES

DISCLAIMERS_HE = ["אינו החלטת אשראי ואינו קבלת מסמכים על ידי הבנק.",
                  "״מוכן לבדיקת בנקאי״ פירושו שדרישות המסמכים התקיימו — לא זכאות, לא ריבית ולא אישור הלוואה.",
                  "נתונים סינתטיים להדגמה בלבד."]


def build_package(case_id: str) -> dict[str, Any]:
    case = bank.get_case(case_id)
    state = readiness.compute(case_id)
    findings = repo.findings(case_id)
    latest_case = repo.latest_case_result(case_id) or {}
    borrowers = {b["borrower_id"]: b for b in case["borrowers"]}
    docs = []
    for d in repo.documents(case_id):
        r = repo.latest_document_result(d["document_id"]) if d["status"] == "reviewed" else None
        docs.append({"document_id": d["document_id"], "filename": d["filename"],
                     "uploaded_for": borrowers.get(d["borrower_id"] or "", {}).get("name_he"), "status": d["status"],
                     "uploaded_at": d["uploaded_at"], "sha256": d["sha256"],
                     "verdict": (r or {}).get("verdict"), "doc_type_he": (r or {}).get("doc_type_he"),
                     "period": (r or {}).get("period"),
                     "period_he": det.month_label_he(r["period"]) if r and r.get("period") else None,
                     "file_name_period": (r or {}).get("file_name_period"), "is_scanned": (r or {}).get("is_scanned"),
                     "rubric": f"{r['rubric_id']}@{r['rubric_version']}" if r else None,
                     "run_id": (r or {}).get("run_id"), "provider": ((r or {}).get("identity") or {}).get("provider"),
                     "models": ((r or {}).get("identity") or {}).get("models"),
                     "criteria": (r or {}).get("criteria", []), "facts": (r or {}).get("facts", []),
                     "summary_he": (r or {}).get("summary_he"), "limitations_he": (r or {}).get("limitations_he", []),
                     "security_flags": (r or {}).get("security_flags", [])})
    open_f = [f for f in findings if f["status"] == "open"]
    evidence_index = [{"finding_id": f["finding_id"], **e} for f in open_f for e in f["evidence"]]
    return {
        "case_id": case_id, "generated_at": now_iso(), "status": "DRAFT_FOR_BANKER_REVIEW",
        "bank_stage": case["bank_stage"], "preliminary_decision": case.get("preliminary_decision"),
        "scope_he": "מסמכי בקשת ההלוואה — לפי מדיניות המסמכים שהוצמדה לתיק",
        "borrowers": [{"borrower_id": b["borrower_id"], "name_he": b["name_he"],
                       "declared_net_monthly_ils": b["declared_net_monthly_ils"], "declaration_note_he": b["declaration_note_he"],
                       "declared_income_provenance": b["declared_income_provenance"]}
                      for b in case["borrowers"]],
        "ai_readiness": {"state": state["state"], "state_he": state["state_he"], "state_he_banker": state["state_he_banker"],
                         "counts": state["counts"]},
        "requirements": [r for r in state["requirements"] if r["evaluated_by_ai"]],
        "policy_version": next((r.get("policy_version") for r in state["requirements"]), None),
        "documents": docs,
        "findings_open_customer": [f for f in open_f if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"],
        "findings_open_banker": [f for f in open_f if f["review_state"] == "NEEDS_BANKER_REVIEW"],
        "findings_info": [f for f in open_f if f["review_state"] == "INFO"],
        "findings_closed": [f for f in findings if f["status"] != "open"],
        "customer_statements": repo.statements(case_id),
        "income": latest_case.get("income", {}), "semantic": latest_case.get("semantic", []),
        "case_criteria": latest_case.get("criteria", []), "coverage": latest_case.get("coverage", {}),
        "case_run_id": latest_case.get("run_id"), "evidence_index": evidence_index,
        "not_evaluated": state["not_evaluated"],
        "disclaimers_he": DISCLAIMERS_HE,
        "human_actions": ["accept_document", "request_correction", "escalate", "request_missing_document",
                          "accept_explanation", "request_document", "dismiss_finding", "note", "confirm_preparation"],
    }


# ---------------------------------------------------------------- review workspace
GROUPS = [
    ("decide", "ממתינים להחלטתך", "מסמכים שנבדקו ב-AI וממתינים לקבלה, להחזרה לתיקון או לבירור"),
    ("judgment", "פערים לשיקול דעתך", "ממצאים ברמת התיק שה-AI לא סוגר בעצמו"),
    ("escalated", "בבירור", "מסמכים שהעברת לבירור נוסף"),
    ("correction", "תיקון אצל הלקוח", "מסמכים שהוחזרו לתיקון או שבדיקת ה-AI מצאה בהם בעיה שהלקוח צריך לתקן"),
    ("missing", "מסמכים חסרים", "חודשים נדרשים שהלקוח טרם העלה — אינם מסמכים שממתינים לאישור"),
    ("processing", "בעיבוד", "מסמכים שה-AI עדיין קורא, או שעיבודם נכשל"),
    ("done", "טופלו", "מסמכים שקיבלת או שהוחלפו, וממצאים שהכרעת בהם"),
]
GROUP_BY_STATUS = {"AWAITING_DECISION": "decide", "ESCALATED": "escalated", "AWAITING_CUSTOMER_FIX": "correction",
                   "CORRECTION_REQUESTED": "correction", "PROCESSING": "processing", "FAILED": "processing",
                   "ACCEPTED": "done", "REPLACED": "done"}
ALLOWED = {"AWAITING_DECISION": ["accept", "request_correction", "escalate"],
           "AWAITING_CUSTOMER_FIX": ["request_correction", "escalate"],
           "ESCALATED": ["accept", "request_correction"], "FAILED": ["request_correction"]}
VERDICT_HE = {"VALID": "תקין", "NEEDS_REVIEW": "דורש בדיקה", "INVALID": "לא תקין"}
VERDICT_TONE = {"VALID": "ok", "NEEDS_REVIEW": "warn", "INVALID": "bad"}
REVIEW_STATE_HE = {"CUSTOMER_ACTION_REQUIRED": "דורש פעולה מהלקוח", "NEEDS_BANKER_REVIEW": "לשיקול דעתך", "INFO": "לידיעה"}
RESOLUTION_HE = {"resolved_by_new_evidence": "נסגר — ראיה חדשה", "accepted_by_banker": "נסגר — התקבל על ידי הבנקאי",
                 "resolved_by_banker": "הבירור נסגר על ידי הבנקאי לאחר בדיקה",
                 "dismissed_by_banker": "סומן כשגוי על ידי הבנקאי", "correction_requested_by_banker": "נסגר — המסמך הוחזר לתיקון",
                 "replaced_by_customer_upload": "נסגר — הוחלף במסמך חדש"}
REQUEST_STATUS_HE = {"OPEN": "ממתין ללקוח", "RESPONDED": "הלקוח העלה מסמך"}
MAIN_FACTS = ["employee_name", "employee_id", "employer_name", "salary_period", "payment_date", "gross_pay", "total_deductions", "net_pay"]
VERIFIED = ("text_layer_exact", "vision_reread_confirmed")


def _month_list_he(months: list[str]) -> str:
    if not months:
        return ""
    if len({m[:4] for m in months}) == 1:
        words = [review_desk.month_word(m) for m in months]
        return (", ".join(words[:-1]) + " ו" + words[-1] if len(words) > 1 else words[0]) + f" {months[0][:4]}"
    return ", ".join(det.month_label_he(m) for m in months)


def _finding_view(f: dict, labels: dict[str, str], statements: list[dict]) -> dict:
    status_he = "פתוח" if f["status"] == "open" else RESOLUTION_HE.get(f.get("resolution") or "", f["status"])
    return {**{k: f[k] for k in ("finding_id", "key", "code", "severity", "review_state", "status", "borrower_id", "document_id",
                                 "period", "title_he", "message_he", "resolution", "resolution_note", "created_at", "updated_at")},
            "review_state_he": REVIEW_STATE_HE.get(f["review_state"], f["review_state"]), "status_he": status_he,
            "evidence": [{**e, "label_he": labels.get(f"{e['document_id']}:{e['field']}", e["field"]),
                          "verified": e.get("witness") in VERIFIED} for e in f["evidence"]],
            "can_dismiss": f["status"] == "open" and f["review_state"] != "INFO" and f["code"] not in COVERAGE_CODES,
            "can_decide": f["status"] == "open" and f["review_state"] == "NEEDS_BANKER_REVIEW" and f["code"] not in COVERAGE_CODES,
            "not_reproduced": bool((f.get("detail") or {}).get("not_reproduced_by")),
            "statements": [{"text": s["text"], "channel": s["channel"], "created_at": s["created_at"]}
                           for s in statements if s["finding_id"] == f["finding_id"]],
            "history": f["history"]}


def _request_view(r: dict) -> dict:
    status_he = ("הלקוח השיב בכתב" if r["status"] == "RESPONDED" and r.get("responded_statement_id") else
                 "נסגרה" if r["status"] == "CLOSED" else REQUEST_STATUS_HE.get(r["status"], r["status"]))
    return {**r, "status_he": status_he}


def _doc_item(case: dict, d: dict, review: Optional[dict], st: dict, findings: list[dict], labels: dict[str, str],
              statements: list[dict], decisions: list[dict], requests: list[dict], docs_by_id: dict[str, dict]) -> dict:
    did = d["document_id"]
    first = review_desk._first(case, d["borrower_id"])
    claimed = review_desk._claimed_period(d, review)
    printed = (review or {}).get("period")
    open_f = [f for f in findings if f["status"] == "open"]
    related = [f for f in findings if f["document_id"] == did or did in ((f.get("detail") or {}).get("documents") or [])]
    mine_open = [f for f in open_f if f["document_id"] == did]
    banker_open = [f for f in mine_open if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    customer_open = [f for f in mine_open if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
    criteria = (review or {}).get("criteria", [])
    status = st["status"]
    draft = review_desk.draft_correction(case, d, review, open_f)
    attention: list[str] = []
    if status == "PROCESSING":
        attention.append("ה-AI עדיין קורא ובודק את המסמך. התוצאה תופיע כאן אוטומטית.")
    elif status == "FAILED":
        attention.append("עיבוד ה-AI לא הושלם בגלל תקלה טכנית. אפשר לבקש מהלקוח להעלות את הקובץ שוב.")
    else:
        if claimed and printed and claimed != printed:
            attention.append(draft["explanation_he"])
        for f in customer_open + banker_open:
            if f["code"] != "FILE_NAME_PERIOD_MISMATCH":
                attention.append(f"{f['title_he']}: {f['message_he']}")
        if not attention:
            uncertain = [c for c in criteria if c["outcome"] in ("FAIL", "NEEDS_REVIEW")]
            if uncertain:
                attention += [f"{c['title_he']}: {c['explanation_he']}" for c in uncertain[:3]]
            elif review:
                verified = sum(1 for f in review["facts"] if (f.get("evidence") or {}).get("witness") in VERIFIED)
                passed = sum(c["outcome"] == "PASS" for c in criteria)
                applicable = sum(c["outcome"] != "NOT_APPLICABLE" for c in criteria)
                attention.append(f"בדיקת ה-AI לא מצאה בעיה: {passed} מתוך {applicable} קריטריונים עברו, ו-{verified} ערכים מכריעים "
                                 "אומתו מול הקובץ. נדרשת החלטה שלך כדי לסמן את המסמך כנבדק.")
    family = (rubrics.all_rubrics().get(f"{review['rubric_id']}@{review['rubric_version']}") or {}).get("family", "payslip") \
        if review else "payslip"
    main = MAIN_FACTS if family == "payslip" else P.FAMILY_FIELDS.get(family, MAIN_FACTS)
    facts = sorted((f for f in (review or {}).get("facts", []) if f["field"] in main), key=lambda f: main.index(f["field"]))
    replaced_by = docs_by_id.get(st["replaced_by"] or "")
    replaces = docs_by_id.get(st["replaces"] or "")
    allowed = list(ALLOWED.get(status, []))
    blocked = None
    if status == "AWAITING_CUSTOMER_FIX":
        blocked = "בבדיקת ה-AI נמצא ממצא שמחייב תיקון מצד הלקוח. אם הממצא שגוי — סמנו אותו כשגוי, ואז אפשר לקבל את המסמך."
    identity = (review or {}).get("identity") or {}
    return {
        "id": f"doc:{did}", "kind": "document", "group": GROUP_BY_STATUS[status],
        "attention": bool(banker_open or customer_open or (review and review["verdict"] != "VALID") or status == "FAILED"
                          or (claimed and printed and claimed != printed)),
        "document_id": did, "filename": d["filename"], "mime": d["mime"], "pages": d["pages"] or 1,
        "requirement_code": d["requirement_code"], "family": family,
        "borrower_id": d["borrower_id"], "borrower_he": first,
        "doc_type_he": (review or {}).get("doc_type_he") or "מסמך", "period": printed,
        "period_he": det.month_label_he(printed) if printed else None, "claimed_period": claimed,
        "claimed_period_he": det.month_label_he(claimed) if claimed else None,
        "uploaded_at": d["uploaded_at"], "is_scanned": bool((review or {}).get("is_scanned")),
        "title_he": f"{(review or {}).get('doc_type_he') or 'מסמך'} · {first}" + (f" · {det.month_label_he(printed)}" if printed else ""),
        "ai": {"status": d["status"], "stage": d["stage"], "verdict": (review or {}).get("verdict"),
               "verdict_he": VERDICT_HE.get((review or {}).get("verdict") or "", "בעיבוד" if status == "PROCESSING" else "—"),
               "tone": VERDICT_TONE.get((review or {}).get("verdict") or "", "neutral"),
               "attention_he": attention, "summary_he": (review or {}).get("summary_he") or "",
               "facts": [{**f, "verified": (f.get("evidence") or {}).get("witness") in VERIFIED} for f in facts],
               "criteria_failed": [c for c in criteria if c["outcome"] == "FAIL"],
               "criteria_uncertain": [c for c in criteria if c["outcome"] == "NEEDS_REVIEW"],
               "criteria_passed": [c for c in criteria if c["outcome"] == "PASS"],
               "criteria_na": [c for c in criteria if c["outcome"] == "NOT_APPLICABLE"],
               "limitations_he": (review or {}).get("limitations_he", []), "uncertainty_he": (review or {}).get("uncertainty_he", []),
               "security_flags": (review or {}).get("security_flags", []),
               "technical": {"rubric": f"{review['rubric_id']}@{review['rubric_version']}" if review else None,
                             "run_id": (review or {}).get("run_id"), "provider": identity.get("provider"),
                             "models": identity.get("models"), "prompt_version": identity.get("prompt_version"),
                             "finished_at": (review or {}).get("finished_at"),
                             "verdict_reason_codes": (review or {}).get("verdict_reason_codes", []),
                             "sha256": d["sha256"], "error": d.get("error")}},
        "banker": {"status": status, "status_he": st["status_he"],
                   "decision": review_desk.public_decision(st["decision"]) if st["decision"] else None,
                   "allowed_actions": allowed, "blocked_accept_he": blocked,
                   "acknowledge_finding_ids": [f["finding_id"] for f in banker_open],
                   "accept_requires_rationale": bool(banker_open) or (review or {}).get("verdict") != "VALID"},
        "findings": [_finding_view(f, labels, statements) for f in related],
        "requests": [_request_view(r) for r in requests if r["document_id"] == did or r.get("responded_document_id") == did],
        "replaces": {"document_id": replaces["document_id"], "filename": replaces["filename"],
                     "by": "customer" if st.get("replacement_kind") == "customer_replacement" else "banker_request"} if replaces else None,
        "replaced_by": {"document_id": replaced_by["document_id"], "filename": replaced_by["filename"],
                        "status": replaced_by["status"],
                        "by": "customer" if st.get("replacement_kind") == "customer_replacement" else "banker_request"} if replaced_by else None,
        "outcome": outcomes.document_outcome(d, review, status, open_f),
        "history": [review_desk.public_decision(x) for x in decisions if x["document_id"] == did][::-1],
        "draft": draft,
    }


def _income_block(bid: str, latest_case: dict, required: list[str], open_f: list[dict], tolerance: float) -> dict:
    inc = (latest_case.get("income") or {}).get(bid) or {}
    crit = next((c for c in latest_case.get("criteria", []) if c["criterion_id"] == f"IS-04:{bid}"), None)
    sem = next((s for s in latest_case.get("semantic", []) if s.get("borrower_id") == bid), None) or {}
    months = inc.get("months_compared") or []
    missing = [m for m in required if m not in months]
    finding = next((f for f in open_f if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE" and f["borrower_id"] == bid), None)
    outcome = (crit or {}).get("outcome")
    pct, diff = inc.get("difference_pct"), inc.get("difference_ils")
    basis = "none" if pct is None else "preliminary" if missing else "complete"
    documented_he = (f"בתלוש {det.month_label_he(months[0])}" if len(months) == 1 else
                     f"בממוצע {len(months)} התלושים" if months else "")
    if outcome is None or outcome == "NOT_APPLICABLE" or pct is None:
        summary = "אין עדיין תלושים מתאימים להשוואה מול ההכנסה המוצהרת."
        tone = "neutral"
    else:
        gap = (f"{documented_he} הנטו זהה להכנסה המוצהרת" if not diff else
               f"{documented_he} הנטו {'נמוך' if diff < 0 else 'גבוה'} ב־{abs(diff):,.0f} ₪ ({abs(pct):.1f}%) מההכנסה המוצהרת")
        over = abs(pct) > tolerance
        if basis == "preliminary":
            summary = (f"השוואה ראשונית על בסיס {len(months)} מתוך {len(required)} חודשים: {gap}. "
                       + (f"בחודשים הזמינים הפער מעל סף הסבולת של {tolerance:g}%. " if over
                          else f"בחודשים הזמינים הפער בתוך סף הסבולת של {tolerance:g}%. ")
                       + f"ההשוואה המלאה תתאפשר אחרי {_month_list_he(missing)}.")
            tone = "warn" if outcome != "PASS" else "neutral"
        elif outcome == "PASS":
            summary, tone = f"{gap} — בתוך סף הסבולת של {tolerance:g}%. לידיעה בלבד; לא נפתח ממצא.", "ok"
        else:
            summary = gap + (f" — בתוך סף {tolerance:g}%, אך ההגדרות אינן ניתנות להשוואה ודורשות שיקול דעת." if not over
                             else f" — מעל סף הסבולת של {tolerance:g}%. הועבר לשיקול דעתך.")
            tone = "warn"
    return {"declared_net_monthly_ils": inc.get("declared_net_monthly_ils"), "average_documented_net_ils": inc.get("average_documented_net_ils"),
            "difference_ils": diff, "difference_pct": pct, "months_compared": months, "months_compared_he": _month_list_he(months),
            "months_required": len(required), "months_missing": missing, "months_missing_he": _month_list_he(missing),
            "basis": basis, "documented_label_he": documented_he or "בתלושים",
            "tolerance_pct": tolerance, "outcome": outcome, "decided_by": (crit or {}).get("decided_by"),
            "summary_he": summary, "tone": tone, "finding_id": (finding or {}).get("finding_id"),
            "basis_he": "נטו שהלקוח הצהיר מול הנטו בתלושים שעברו את בדיקות ההכנסה, בחודשים הנדרשים בלבד; הסף נבדק בקוד",
            "model_assessment": sem.get("income_assessment"), "model_explanation_he": sem.get("explanation_he"),
            "criterion_id": (crit or {}).get("criterion_id")}


def _case_finding_item(case: dict, f: dict, state: dict, requests: list[dict], decisions: list[dict], statements: list[dict],
                       labels: dict, latest_case: dict, required: list[str], open_f: list[dict], tolerance: float,
                       evidence_docs: list[dict], docs: list[dict], reviews: dict, statuses: dict, group: str) -> dict:
    """A case-level finding with what the banker needs to decide it: how complete the evidence is, what the customer
    said, the next step, the documents that could support a resolution, and what a resolution would change."""
    fid, bid = f["finding_id"], f["borrower_id"]
    names = {b["borrower_id"]: b for b in case["borrowers"]}
    first = (names.get(bid or "") or {}).get("first_name_he") or ""
    is_open = f["status"] == "open"
    escalated = review_desk.finding_escalated(f, decisions)
    if is_open and escalated:
        group = "escalated"
    basis = review_desk.finding_basis(f)
    income = _income_block(bid, latest_case, required, open_f, tolerance) if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE" and bid else None
    req = next((r for r in state["requirements"] if r["evaluated_by_ai"] and r["family"] == "payslip"
                and r["borrower_id"] == bid), None)
    missing = list((req or {}).get("missing") or [])
    asked_months = {q["period"] for q in requests if q["status"] == "OPEN" and q["borrower_id"] == bid and q["period"]}
    to_request = [m for m in missing if m not in asked_months]
    linked = [q for q in requests if q["finding_id"] == fid]
    open_request = next((q for q in linked if q["status"] == "OPEN"), None)
    said = [x for x in statements if x["finding_id"] == fid]
    allowed: list[str] = []
    if is_open and f["review_state"] == "NEEDS_BANKER_REVIEW":
        allowed = (["request_missing"] if to_request else []) + ([] if open_request else ["request_explanation"]) \
            + ["resolve", "dismiss"] + ([] if escalated else ["escalate"])
    if not is_open:
        rec = None
    elif escalated:
        last = next(d for d in reversed(decisions) if d["finding_id"] == fid and d["action"] == "ESCALATE_FINDING")
        rec = {"action": "resolve", "title_he": "בהמשך בירור", "body_he": f"הועבר להמשך בירור: {last['rationale']}"}
    elif basis["partial"] and to_request:
        rec = {"action": "request_missing", "title_he": "קודם להשלים את המסמכים",
               "body_he": f"ההשוואה מבוססת על {len(basis['months_compared'])} מתוך {len(basis['months_required'])} החודשים הנדרשים. "
                          f"לפני הכרעה מומלץ לבקש את {_month_list_he(to_request)}."}
    elif basis["partial"]:
        rec = {"action": None, "title_he": "ממתינים למסמכים מהלקוח",
               "body_he": f"נשלחה בקשה ל{_month_list_he([m for m in basis['months_missing'] if m in asked_months]) or 'חודשים החסרים'}. "
                          "ההשוואה תתעדכן אוטומטית אחרי ההעלאה והבדיקה."}
    elif open_request:
        rec = {"action": None, "title_he": "ממתינים לתשובת הלקוח", "body_he": f"נשלחה בקשה: {open_request['title_he']}."}
    elif not said:
        rec = {"action": "request_explanation", "title_he": "אין הסבר מהלקוח",
               "body_he": "אפשר לבקש הסבר ואסמכתה, או לסגור את הבירור על סמך המסמכים שבתיק עם נימוק."}
    else:
        rec = {"action": "resolve", "title_he": "הלקוח מסר הסבר — לא מאומת",
               "body_he": "הסבר לבדו אינו מספיק לסגירה. בדקו אם מסמך בתיק תומך בו, בקשו אסמכתה, או הכריעו בהחלטה מקצועית מנומקת."}
    options = []
    for d in docs:
        r = reviews.get(d["document_id"])
        if d["borrower_id"] != bid or d["status"] != "reviewed" or statuses.get(d["document_id"], {}).get("status") == "REPLACED":
            continue
        net = next((x for x in (r or {}).get("facts", []) if x["field"] == "net_pay"), None)
        options.append({"document_id": d["document_id"], "filename": d["filename"],
                        "period_he": det.month_label_he(r["period"]) if r and r.get("period") else None,
                        "net": (net or {}).get("value_raw"), "verdict_he": VERDICT_HE.get((r or {}).get("verdict") or "", "—")})
    open_requests = [q for q in requests if q["status"] == "OPEN"]
    other_requests = [q for q in open_requests if q["finding_id"] != fid]
    banker_now = state["counts"]["banker_items"]
    after_state = ("ACTION_REQUIRED" if state["counts"]["customer_actions"] or other_requests else
                   "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS" if banker_now - 1 > 0 else "READY_FOR_HUMAN_REVIEW")
    if state["state"] in ("CHECKING", "RECHECKING", "ERROR", "PREPARATION_CONFIRMED"):
        after_state = state["state"]
    state_line = (f"מצב בדיקת מסמכי הבקשה לא ישתנה ({state['state_he_banker']})." if after_state == state["state"] else
                  f"מצב בדיקת מסמכי הבקשה: {state['state_he_banker']} ← {readiness.STATE_HE_BANKER[after_state]}.")
    closes = [f"הבקשה הפתוחה ללקוח („{q['title_he']}”) תיסגר ותרד מהאפליקציה." for q in linked if q["status"] == "OPEN"]
    impact = {
        "resolve": ["הממצא ייסגר ויירשם כהכרעה שלך, עם הבסיס, המסמכים התומכים והנימוק.",
                    f"פריטים לשיקול דעתך בתיק: {banker_now} ← {max(banker_now - 1, 0)}.", state_line, *closes,
                    "תוצאות בדיקת ה-AI ותוקף המסמכים לא משתנים. שלב הבקשה בבנק לא משתנה.",
                    "אם הנתונים ישתנו בהמשך (למשל יתקבלו תלושים נוספים), ייפתח ממצא חדש עם קישור להכרעה הזו."],
        "dismiss": ["הממצא יסומן כטעות בזיהוי של ה-AI ויתועד ביומן לבקרת איכות.",
                    f"פריטים לשיקול דעתך בתיק: {banker_now} ← {max(banker_now - 1, 0)}.", state_line, *closes,
                    "הממצא לא ייפתח מחדש, אלא אם הנתונים שעליהם נשען ישתנו."],
        "customer_he": "ללקוח תוצג בעדכונים שורה ניטרלית שהנושא נבדק ונסגר, בלי הנימוק הפנימי. לא נוצרת הודעה או בקשה חדשה ללקוח.",
    }
    reopened = next((h for h in f["history"] if h.get("after_banker_ruling")), None)
    return {
        "id": f"finding:{fid}", "kind": "case_finding", "group": group, "attention": is_open and not escalated,
        "borrower_id": bid, "borrower_he": first, "title_he": f["title_he"], "finding": _finding_view(f, labels, statements),
        "evidence_documents": evidence_docs, "income": income, "basis": basis, "escalated": escalated,
        "missing_months": missing, "missing_months_he": _month_list_he(missing), "months_to_request": to_request,
        "months_to_request_he": _month_list_he(to_request), "recommendation": rec, "evidence_options": options,
        "has_customer_statement": bool(said), "impact": impact,
        "reopened_after": {"finding_id": reopened["after_banker_ruling"], "resolution": reopened.get("prior_resolution"),
                           "note_he": reopened.get("note")} if reopened else None,
        "open_request": _request_view(open_request) if open_request else None,
        "requests": [_request_view(q) for q in linked],
        "allowed_actions": allowed,
        "history": [review_desk.public_decision(x) for x in decisions if x["finding_id"] == fid][::-1],
        "draft": review_desk.draft_additional(case, f),
        "drafts": {"missing": review_desk.draft_missing_months(case, bid, to_request) if bid and to_request else None,
                   "explanation": review_desk.draft_explanation(case, f, income)},
    }


def case_queue_counts(case_id: str) -> dict[str, int]:
    ws = build_workspace(case_id, light=True)
    return {g["key"]: len(g["items"]) for g in ws["groups"]}


def build_workspace(case_id: str, light: bool = False) -> dict[str, Any]:
    case = bank.get_case(case_id)
    state = readiness.compute(case_id)
    docs = repo.documents(case_id)
    findings = repo.findings(case_id)
    open_f = [f for f in findings if f["status"] == "open"]
    decisions = repo.decisions(case_id)
    requests = repo.customer_requests(case_id)
    statuses = desk_state.document_statuses(case_id, docs, open_f, decisions, requests)
    latest_case = repo.latest_case_result(case_id) or {}
    statements = repo.statements(case_id)
    reviews = {d["document_id"]: repo.latest_document_result(d["document_id"]) if d["status"] == "reviewed" else None for d in docs}
    docs_by_id = {d["document_id"]: d for d in docs}
    labels = {f"{did}:{f['field']}": f["label_he"] for did, r in reviews.items() for f in (r or {}).get("facts", [])}
    tolerance = float(rubrics.for_case()["policy"]["income_variance_tolerance_pct"])
    required = (state.get("payslips") or {}).get("requested_months") or []
    names = {b["borrower_id"]: b for b in case["borrowers"]}
    items: list[dict] = []

    for d in docs:
        items.append(_doc_item(case, d, reviews[d["document_id"]], statuses[d["document_id"]], findings, labels, statements,
                               decisions, requests, docs_by_id))

    claimed_by_borrower: dict[str, list[dict]] = {}
    for it in items:
        if it["kind"] == "document" and it["claimed_period"]:
            claimed_by_borrower.setdefault(it["borrower_id"] or "", []).append(
                {"document_id": it["document_id"], "filename": it["filename"], "claimed_period": it["claimed_period"],
                 "printed_period": it["period"]})
    for r in state["requirements"]:
        if not r["evaluated_by_ai"] or r["family"] != "payslip":
            continue
        bid = r["borrower_id"]
        for period in r.get("missing") or []:
            finding = next((f for f in open_f if f["code"] == "REQUIRED_PERIOD_MISSING" and f["borrower_id"] == bid
                            and f["period"] == period), None)
            mine = [q for q in requests if q["borrower_id"] == bid and q["period"] == period]
            open_request = next((q for q in mine if q["status"] == "OPEN"), None)
            related = [x for x in claimed_by_borrower.get(bid, []) if x["claimed_period"] == period and x["printed_period"] != period]
            duplicate = next((f for f in open_f if f["code"] == "DUPLICATE_PERIOD" and f["borrower_id"] == bid), None)
            items.append({
                "id": f"missing:{bid}:{period}", "kind": "missing", "group": "missing", "attention": open_request is None,
                "borrower_id": bid, "borrower_he": names[bid]["first_name_he"], "period": period,
                "period_he": det.month_label_he(period),
                "title_he": f"תלוש {det.month_label_he(period)} · {names[bid]['first_name_he']}",
                "status_he": "נשלחה בקשה ללקוח" if open_request else "לא הועלה",
                "explanation_he": (finding or {}).get("message_he")
                or f"לא התקבל תלוש שכר שמודפס בו {det.month_label_he(period)}.",
                "related_documents": [{**x, "note_he": f"הועלה עבור {review_desk.month_word(period)}, אך מודפס בו "
                                                       f"{det.month_label_he(x['printed_period']) if x['printed_period'] else 'חודש אחר'}"}
                                      for x in related],
                "duplicate_note_he": (duplicate or {}).get("message_he"),
                "finding": _finding_view(finding, labels, statements) if finding else None,
                "open_request": _request_view(open_request) if open_request else None,
                "requests": [_request_view(q) for q in mine],
                # while the AI is still reviewing, the month may already be on its way: no request until it settles
                "allowed_actions": [] if open_request or state["state"] in ("CHECKING", "RECHECKING") else ["request_missing"],
                "history": [review_desk.public_decision(x) for x in decisions
                            if x["target_kind"] == "missing_period" and x["borrower_id"] == bid and x["period"] == period][::-1],
                "draft": review_desk.draft_missing(case, bid, period, related),
            })

    for r in state["requirements"]:
        if not r["evaluated_by_ai"] or r["family"] == "payslip":
            continue
        code = r["code"]
        about = [f for f in open_f if f["code"] in COVERAGE_CODES and (f.get("detail") or {}).get("requirement_code") == code]
        mine = [q for q in requests if q["requirement_code"] == code and q["kind"] == "missing_document"]
        open_request = next((q for q in mine if q["status"] == "OPEN"), None)
        if r["ai_state"] != "required_missing" and not about and not open_request:
            continue
        finding = about[0] if about else None
        who = names.get(r.get("borrower_id") or "", {}).get("first_name_he", "")
        items.append({
            "id": f"missing:{code}", "kind": "missing", "group": "missing", "attention": open_request is None,
            "borrower_id": r.get("borrower_id"), "borrower_he": who, "period": None, "period_he": None,
            "requirement_code": code, "family": r["family"], "family_he": r.get("family_he"),
            "title_he": r["title_he"], "status_he": "נשלחה בקשה ללקוח" if open_request else "לא הועלה" if not finding or
            finding["code"] == "REQUIRED_DOCUMENT_MISSING" else "חסרה תקופה",
            "explanation_he": (finding or {}).get("message_he") or f"טרם הועלה: {r['title_he']}.",
            "related_documents": [], "duplicate_note_he": None,
            "finding": _finding_view(finding, labels, statements) if finding else None,
            "open_request": _request_view(open_request) if open_request else None,
            "requests": [_request_view(q) for q in mine],
            "allowed_actions": [] if open_request or state["state"] in ("CHECKING", "RECHECKING") else ["request_requirement"],
            "history": [review_desk.public_decision(x) for x in decisions
                        if x["target_kind"] == "missing_requirement" and (x.get("customer_request_id") in
                                                                          {q["customer_request_id"] for q in mine})][::-1],
            "draft": review_desk.draft_requirement(case, r, finding),
        })

    for f in findings:
        if f["document_id"] or f["code"] in COVERAGE_CODES or f["review_state"] == "INFO":
            continue
        if f["status"] == "open":
            group = "judgment" if f["review_state"] == "NEEDS_BANKER_REVIEW" else "correction"
        elif f.get("resolution") in BANKER_RULINGS:
            group = "done"
        else:
            continue
        evidence_docs = []
        for e in f["evidence"]:
            doc, r = docs_by_id.get(e["document_id"]), reviews.get(e["document_id"])
            if doc and not any(x["document_id"] == e["document_id"] for x in evidence_docs):
                fact = next((x for x in (r or {}).get("facts", []) if x["field"] == e["field"]), None)
                evidence_docs.append({"document_id": e["document_id"], "filename": doc["filename"], "field": e["field"],
                                      "label_he": labels.get(f"{e['document_id']}:{e['field']}", e["field"]),
                                      "value": (fact or {}).get("value_raw"), "period_he": det.month_label_he(r["period"])
                                      if r and r.get("period") else None, "verified": e.get("witness") in VERIFIED})
        items.append(_case_finding_item(case, f, state, requests, decisions, statements, labels, latest_case, required, open_f,
                                        tolerance, evidence_docs, docs, reviews, statuses, group))

    def order(it: dict) -> tuple:
        return (not it["attention"], it.get("borrower_id") or "", it.get("period") or "", it["id"])

    groups = [{"key": key, "title_he": title, "hint_he": hint,
               "items": [it["id"] for it in sorted((x for x in items if x["group"] == key), key=order)]}
              for key, title, hint in GROUPS]
    if light:
        return {"groups": groups}

    coverage = (latest_case.get("coverage") or {}).get("by_borrower") or {}
    borrower_rows = []
    for r in state["requirements"]:
        if not r["evaluated_by_ai"] or r["family"] != "payslip":
            continue
        bid = r["borrower_id"]
        cov_docs = (coverage.get(bid) or {}).get("documents") or []
        months = []
        for m in (r.get("requested_months") or required):
            month_docs = [x["document_id"] for x in cov_docs if x["period"] == m]
            accepted = any(statuses.get(x, {}).get("status") == "ACCEPTED" for x in month_docs)
            if m in (r.get("missing") or []):
                asked = any(q["borrower_id"] == bid and q["period"] == m and q["status"] == "OPEN" for q in requests)
                st, st_he = ("requested", "חסר · נשלחה בקשה") if asked else ("missing", "חסר")
            elif m in (r.get("verified_months") or []):
                st, st_he = ("accepted", "התקבל על ידך") if accepted else ("verified", "תקין ב-AI")
            elif month_docs:
                st, st_he = "in_review", "ממתין להחלטה"
            else:
                st, st_he = "unknown", "טרם נבדק"
            months.append({"period": m, "label_he": det.month_label_he(m), "state": st, "state_he": st_he,
                           "documents": month_docs, "copies": (r.get("duplicates") or {}).get(m, 0)})
        borrower_rows.append({"borrower_id": bid, "name_he": names[bid]["name_he"], "first_name_he": names[bid]["first_name_he"],
                              "months": months, "verified": len(r.get("verified_months") or []), "required": r.get("required"),
                              "income": _income_block(bid, latest_case, required, open_f, tolerance)})

    group_count = {g["key"]: len(g["items"]) for g in groups}
    open_requests = [q for q in requests if q["status"] == "OPEN"]
    accepted_months = sum(1 for row in borrower_rows for m in row["months"] if m["state"] == "accepted")
    missing_total = sum(len(r.get("missing") or []) for r in state["requirements"] if r["evaluated_by_ai"])
    missing_requirements = [r for r in state["requirements"] if r["evaluated_by_ai"] and r["family"] != "payslip"
                            and r["ai_state"] == "required_missing"]
    confirmation = state.get("banker_confirmation")
    handoffs = review_desk.open_handoffs(case_id)
    reasons = []
    if state["state"] in ("CHECKING", "RECHECKING"):
        reasons.append("ה-AI עדיין בודק מסמכים")
    if state["state"] in ("NOT_CHECKED",):
        reasons.append("טרם הועלו מסמכים")
    if state["state"] == "ERROR":
        reasons.append("יש תקלה בעיבוד")
    if missing_total:
        reasons.append(f"{'חסר תלוש אחד' if missing_total == 1 else f'חסרים {missing_total} תלושים'}")
    if missing_requirements:
        reasons.append("חסר: " + ", ".join(r["family_he"] for r in missing_requirements))
    other_customer = sum(1 for f in open_f if f["review_state"] == "CUSTOMER_ACTION_REQUIRED" and f["code"] not in COVERAGE_CODES)
    if other_customer:
        reasons.append("פריט אחד לתיקון אצל הלקוח" if other_customer == 1 else f"{other_customer} פריטים לתיקון אצל הלקוח")
    if open_requests:
        reasons.append("בקשה פתוחה ללקוח" if len(open_requests) == 1 else f"{len(open_requests)} בקשות פתוחות ללקוח")
    if confirmation and state["state"] == "PREPARATION_CONFIRMED":
        reasons = ["ההכנה כבר אושרה"]
    history = [{"at": x["created_at"], "kind": "decision", **review_desk.public_decision(x)} for x in decisions]
    history += [{"at": q["responded_at"], "kind": "customer_response", "customer_request_id": q["customer_request_id"],
                 "document_id": q["responded_document_id"], "title_he": q["title_he"],
                 "filename": (docs_by_id.get(q["responded_document_id"] or "") or {}).get("filename")}
                for q in requests if q.get("responded_at")]
    history.sort(key=lambda h: h["at"] or "", reverse=True)
    return {
        "case_id": case_id, "generated_at": now_iso(),
        "case": {"case_id": case_id, "display_number": case["display_number"], "title_he": case["title_he"],
                 "banker": case["banker"], "preliminary_decision": case.get("preliminary_decision"),
                 "requested_loan_ils": case.get("requested_loan_ils"),
                 "borrowers": [{k: b[k] for k in ("borrower_id", "name_he", "first_name_he", "declared_net_monthly_ils",
                                                  "declaration_note_he", "declared_income_provenance")} for b in case["borrowers"]]},
        "bank_stage": case["bank_stage"],
        "review_state": {"state": state["state"], "label_he": state["state_he_banker"]},
        "preparation": confirmation,
        "preparation_stale": state.get("banker_confirmation_stale"),
        "handoffs": [{"package_id": h["package_id"], "created_at": h["created_at"], "channel": h["channel"],
                      "note": h.get("note"), "created_by": h["created_by"]} for h in handoffs],
        "can_confirm": {"allowed": not reasons, "reason_he": " · ".join(reasons) if reasons else None,
                        "open_banker_items": state["counts"]["banker_items"]},
        "summary": {"payslips_required": (state.get("payslips") or {}).get("required", 0),
                    "payslips_verified": (state.get("payslips") or {}).get("verified", 0),
                    "payslips_accepted": accepted_months, "missing": missing_total, "open_requests": len(open_requests),
                    "documents": len(docs), "processing": state["counts"]["processing"], "groups": group_count},
        "borrowers": borrower_rows,
        "requirement_matrix": [{"code": r["code"], "title_he": r["title_he"], "family": r["family"],
                                "family_he": r.get("family_he"), "ai_state": r["ai_state"], "ai_state_he": r["ai_state_he"],
                                "borrower_he": names.get(r.get("borrower_id") or "", {}).get("first_name_he"),
                                "satisfied": r["ai_state"] in ("extracted", "preparation_confirmed"),
                                "units": f"{r.get('units_verified', 0)}/{r.get('units_required', 0)}",
                                "policy_version": r.get("policy_version")}
                               for r in state["requirements"] if r["evaluated_by_ai"]],
        "progress": state.get("progress"), "case_status": state.get("case_status"),
        "groups": groups,
        "items": items,
        "info_findings": [_finding_view(f, labels, statements) for f in open_f if f["review_state"] == "INFO"],
        "unattached_statements": [s for s in statements if not s["finding_id"]],
        "customer_requests": [_request_view(q) for q in requests],
        "history": history,
        "not_evaluated": state["not_evaluated"],
        "disclaimers_he": DISCLAIMERS_HE,
    }
