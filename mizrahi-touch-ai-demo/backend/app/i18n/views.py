"""`*_en` siblings for the customer responses (see app/i18n/__init__.py). Each function takes a deep copy of one
response shape and adds English next to the Hebrew, from the codes and ids already in it. It never removes or changes a
`*_he` field, a number, a status or an id. Text with no English source gets no sibling."""
from __future__ import annotations

import re
from typing import Any, Optional

from ..review import case_review as CR
from ..review import deterministic as det
from ..review import reason_codes as RC
from ..store import repo
from . import criteria_en, en

_FILE_TEXT_MARK = "\x00"


def _set(o: dict, key: str, value: Optional[str]) -> None:
    """o[key_en] = value, when there is an English value and it differs in nothing but language."""
    if value:
        o[f"{key}_en"] = value


# ---------------------------------------------------------------- people, case, policy
class Ctx:
    """What English wording needs from the case: first names, full names, accounts, the purpose, the banker."""

    def __init__(self, case: Optional[dict]):
        case = case or {}
        self.case = case
        self.first = {b["borrower_id"]: en.name(b.get("first_name_he")) for b in case.get("borrowers") or []}
        self.full = {b["borrower_id"]: en.name(b.get("name_he")) for b in case.get("borrowers") or []}
        self.accounts = {a["account_id"]: a for a in case.get("accounts") or []}
        self.banker = en.name((case.get("banker") or {}).get("name_he"))
        self.purpose = (case.get("loan") or {}).get("purpose")
        self.company = en.name((case.get("company") or {}).get("name_he")) if case.get("company") else None
        self._files: Optional[dict[str, str]] = None

    def files(self) -> dict[str, str]:
        if self._files is None:
            self._files = {d["document_id"]: d["filename"] for d in repo.documents(self.case.get("case_id", ""))} \
                if self.case.get("case_id") else {}
        return self._files


def _case(c: dict, ctx: Ctx) -> None:
    _set(c, "title", en.case_title(c.get("title_he", "")) or _composed_title(c))
    loan = c.get("loan") or {}
    _set(loan, "product", en.PRODUCTS.get(loan.get("product_he", "")))
    if loan.get("purpose") in en.PURPOSES:
        _set(loan, "purpose", en.PURPOSES[loan["purpose"]][0])
    _set(loan, "note", en.LOAN_NOTES.get(loan.get("note_he") or ""))
    banker = c.get("banker") or {}
    _set(banker, "name", en.name(banker.get("name_he")))
    _set(banker, "role", en.BANKER_ROLES.get(banker.get("role_he", "")))
    if c.get("meeting"):
        _set(c["meeting"], "type", en.MEETING_TYPES.get(c["meeting"].get("type_he", "")))
    for a in c.get("accounts") or []:
        _set(a, "label", en.account_label(a.get("label_he", "")))
        _set(a, "bank", en.BANK.get(a.get("bank_he", "")))
    for b in c.get("borrowers") or []:
        _set(b, "name", en.name(b.get("name_he")))
        _set(b, "first_name", en.name(b.get("first_name_he")))
        _set(b, "declaration_note", en.DECLARATION_NOTES.get(b.get("declaration_note_he") or ""))
        _set(b, "employer_declared", en.NAMES.get(b.get("employer_declared_he") or ""))
    stage = c.get("bank_stage") or {}
    _set(stage, "label", en.BANK_STAGES.get(stage.get("code", "")))
    _set(c, "profile_label", en.PROFILE_LABELS.get(c.get("profile_label_he") or ""))
    if c.get("company"):
        co = c["company"]
        _set(co, "name", en.name(co.get("name_he")))
        _set(co, "signatory", en.name(co.get("signatory_he")))
        _set(co, "signatory_role", "CEO and authorized signatory" if co.get("signatory_role_he") == "מנכ״ל ומורשה חתימה" else None)
    if c.get("preliminary_decision"):
        _set(c["preliminary_decision"], "label", "Preliminary approval")
    p = c.get("document_profile")
    if p:
        _set(p, "entity", en.ENTITY.get(p.get("entity", "")))
        if p.get("purpose") in en.PURPOSES:
            _set(p, "purpose", en.PURPOSES[p["purpose"]][0])
        _set(p, "profile_label", en.PROFILE_LABELS.get(p.get("profile_label_he") or ""))
        _set(p, "disclaimer", en.POLICY_DISCLAIMER)
        for a in p.get("applicants") or []:
            _set(a, "name", en.name(a.get("name_he")))
            _set(a, "role", en.ROLE.get(a.get("role", "")))
            _set(a, "profile", _income_profile(a))
        for a in p.get("accounts") or []:
            _set(a, "label", en.account_label(a.get("label_he", "")))
            if a.get("other_holders_he"):
                a["other_holders_en"] = [en.OTHER_HOLDERS.get(x, x) for x in a["other_holders_he"]]
        if p.get("company"):
            co = p["company"]
            _set(co, "name", en.name(co.get("name_he")))
            _set(co, "signatory", en.name(co.get("signatory_he")))


def _composed_title(c: dict) -> Optional[str]:
    """A customer-created application: '<product> · <purpose>' (or '<purpose> — <company>'), as onboarding.build_case."""
    loan = c.get("loan") or {}
    purpose = en.PURPOSES.get(loan.get("purpose") or "", (None,))[0]
    if not purpose:
        return None
    if c.get("company"):
        return f"{purpose} — {en.name(c['company'].get('name_he'))}"
    product = en.PRODUCTS.get(loan.get("product_he") or "", "All-purpose loan")
    return f"{product} · {purpose}"


def _income_profile(a: dict) -> Optional[str]:
    """requirements.income_profile: 'Salaried · Self-employed (Exempt dealer)'."""
    parts = []
    for s in a.get("income_sources") or []:
        label = en.INCOME.get(s)
        if s == "self_employed" and a.get("business_registration") in en.REGISTRATION:
            label += f" ({en.REGISTRATION[a['business_registration']]})"
        parts.append(label)
    return " · ".join(p for p in parts if p) or None


def requirement(q: dict, ctx: Ctx) -> None:
    rid = q.get("requirement_id") or (q.get("code") or "").split(":")[0]
    entry = en.REQUIREMENTS.get(rid)
    _set(q, "family", en.FAMILY.get(q.get("family", "")))
    _set(q, "ai_state", en.AI_STATE.get(q.get("ai_state", "")))
    if q.get("state_he"):
        _set(q, "state", en.INACTIVE_STATE if q.get("state_he") == "לא נדרש עוד, פרופיל ההכנסה עודכן" else None)
    if not entry:
        return
    label, hint, why, alternatives = entry
    title = label.replace("{months}", str((q.get("rules") or {}).get("months") or 3))
    owner_type = q.get("owner_type")
    if owner_type == "applicant" and q.get("borrower_id"):
        _set(q, "title", f"{title} — {ctx.first.get(q['borrower_id'], '')}")
        _set(q, "owner", ctx.full.get(q["borrower_id"]))
    elif owner_type == "account":
        account = ctx.accounts.get(q.get("account_id") or "") or {}
        who = en.join([ctx.first.get(h, "") for h in q.get("holders") or []])
        _set(q, "title", f"{title} — {en.account_label(account.get('label_he', ''))}" + (f" ({who})" if who else ""))
        _set(q, "owner", en.join([ctx.full.get(h, "") for h in q.get("holders") or []]) or ctx.company)
    else:
        purpose = en.PURPOSES.get(ctx.purpose or "")
        proof = q.get("family") == "purpose_proof" and purpose
        _set(q, "title", title + (f" — {purpose[0]}" if proof else ""))
        _set(q, "owner", ctx.company or en.join(list(ctx.full.values())))
        if proof:
            hint = purpose[1]
    _set(q, "hint", hint)
    _set(q, "why", why)
    if q.get("alternatives_he"):
        q["alternatives_en"] = alternatives if len(alternatives) == len(q["alternatives_he"]) else list(q["alternatives_he"])


# ---------------------------------------------------------------- findings
def _detail_of(template: str, message: str, **fmt: str) -> Optional[str]:
    """The `{detail}` part of a message built from `template` (the reviewer's own words, kept as the original)."""
    if "{detail}" not in template:
        return None
    head, _, tail = template.format(detail=_FILE_TEXT_MARK, **fmt).partition(_FILE_TEXT_MARK)
    if message.startswith(head) and message.endswith(tail) and len(message) >= len(head) + len(tail):
        return message[len(head):len(message) - len(tail)] or None
    return None


def finding(f: dict, ctx: Ctx) -> None:
    """English title and message from the finding's code and structured detail. When the Hebrew message carries the
    reviewer's own explanation, that part is kept as `message_detail_he` for the app to show as the original."""
    code, d = f.get("code", ""), f.get("detail") or {}
    first = ctx.first.get(f.get("borrower_id") or "", "")
    period = f.get("period")
    title = message = None
    if code == "REQUIRED_PERIOD_MISSING" and period:
        requested = d.get("requested") or []
        title = f"Payslip for {en.month(period)} missing — {first}"
        message = (f"To complete {first}'s salary documents we still need the payslip for {en.month(period)}."
                   + (f" Months required: {', '.join(en.month(m) for m in requested)}." if requested else ""))
    elif code == "DUPLICATE_PERIOD" and period:
        n = d.get("copies") or len(d.get("documents") or [])
        files = [ctx.files().get(x, "") for x in d.get("documents") or []]
        title = f"{n} payslips received for {en.month(period)} — {first}"
        message = f"{n} documents printed with {en.month(period)} were received: {', '.join(x for x in files if x)}."
        claimed = [f"{name} (file name says {en.month(_ym(label))})"
                   for name, label in re.findall(r"(\S+) \(שם הקובץ: ([^)]+)\)", f.get("message_he") or "") if _ym(label)]
        if claimed:
            message += " " + "; ".join(claimed) + "."
        message += (" The missing month is still required." if f.get("review_state") == "CUSTOMER_ACTION_REQUIRED"
                    else " Every required month is covered; nothing to do.")
    elif code == "FILE_NAME_PERIOD_MISMATCH":
        file = ctx.files().get(f.get("document_id") or "", "")
        title = "The file name doesn't match the printed month"
        message = (f"The file name {file} says {en.month(d.get('file_name_claims'))}, but the document itself is printed "
                   f"{en.month(d.get('document_prints'))}. The check relies on the printed month.")
    elif code == RC.REQUIRED_DOCUMENT_MISSING:
        q = {"requirement_id": (d.get("requirement_code") or "").split(":")[0], "code": d.get("requirement_code"),
             "family": d.get("family"), "borrower_id": f.get("borrower_id"), **_requirement_shape(d.get("requirement_code"), ctx)}
        requirement(q, ctx)
        if q.get("title_en"):
            title = f"Missing: {q['title_en']}"
            message = f"To complete your loan application we still need: {q['title_en']}."
    elif code == RC.STATEMENT_PERIOD_GAP:
        shape = _requirement_shape(d.get("requirement_code"), ctx)
        holders = en.join([ctx.first.get(h, "") for h in shape.get("holders") or []])
        gaps = ", ".join(f"{en.day(a)}–{en.day(b)}" for a, b in d.get("gaps") or [])
        title = f"A period is missing from the bank statements — {holders}" if holders else "A period is missing from the bank statements"
        message = (f"The statements uploaded for this account don't cover the last 90 days. Missing: {gaps}. "
                   "Please upload a statement that covers it.")
    elif code == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE" and d.get("stats"):
        s = d["stats"]
        compared, required, missing = d.get("months_compared") or [], d.get("months_required") or [], d.get("months_missing") or []
        basis = f"the {en.month(compared[0])} payslip" if len(compared) == 1 else f"the average of {len(compared)} payslips"
        title = f"Gap between declared income and payslips — {first}"
        message = f"The application declares a net income of {en.ils(s['declared_net_monthly_ils'])} a month. "
        if d.get("basis") == "preliminary":
            message += (f"Preliminary comparison on {len(compared)} of the {len(required)} required months: {basis} shows "
                        f"{en.ils(s['average_documented_net_ils'])} net ({s['difference_pct']:+.1f}%). "
                        f"Still missing: {', '.join(en.month(m) for m in missing)}. ")
        else:
            message += (f"In the payslips checked the average net pay is {en.ils(s['average_documented_net_ils'])} "
                        f"({s['difference_pct']:+.1f}%), based on all {len(required)} required months. ")
        message += ("The gap was passed to the banker for review; your explanation, if you give one, is attached but is "
                    "not evidence.")
    elif code == "IDENTITY_INCONSISTENT":
        title = f"Identity details inconsistent — {first}"
    elif code == "BORROWER_MISMATCH" and f.get("title_he", "").startswith("המסמך אינו של "):
        file = ctx.files().get(f.get("document_id") or "", "")
        other = ctx.first.get(d.get("document_identifies") or "")
        title = f"This document isn't {first}'s"
        message = (f"The document {file} was uploaded for {first}, but it identifies someone else. "
                   + (f"It looks like {other}'s document: please reassign it or upload the right one." if other
                      else "Please upload the right payslip."))
    else:
        title, message = _document_finding(f, ctx)
    _set(f, "title", title)
    _set(f, "message", message)


def _ym(label_he: str) -> Optional[str]:
    """'ספטמבר 2026' → '2026-09' (det.month_label_he reversed)."""
    m = re.match(r"(\S+) (\d{4})$", label_he.strip())
    number = det.HEBREW_MONTHS.get(m.group(1)) if m else None
    return f"{m.group(2)}-{number:02d}" if number else None


def _requirement_shape(code: Optional[str], ctx: Ctx) -> dict:
    """owner type, account and holders of a requirement code ('PAYSLIPS:BRW-A', 'BANK_STATEMENTS:ACC-1', 'PURPOSE_PROOF')."""
    if not code:
        return {}
    rid, _, owner = code.partition(":")
    if owner in ctx.accounts:
        return {"owner_type": "account", "account_id": owner, "holders": ctx.accounts[owner].get("holders") or []}
    if owner in ctx.first:
        return {"owner_type": "applicant", "borrower_id": owner}
    return {"owner_type": "case"}


def _document_finding(f: dict, ctx: Ctx) -> tuple[Optional[str], Optional[str]]:
    """A document-level finding: the Hebrew title tells which table (payslip, other family, uncertain) built it."""
    code, d = f.get("code", ""), f.get("detail") or {}
    file = ctx.files().get(f.get("document_id") or "", "")
    family = d.get("family") or ("payslip" if str(d.get("criterion_id", "")).startswith("PS-") else "")
    title_he, message_he = f.get("title_he", ""), f.get("message_he", "")
    doc_he = RC.DOC_HE.get(family, "המסמך")
    candidates = []                     # (hebrew title, hebrew template, english title, english template)
    if family == "payslip":
        for table_he, table_en in ((CR.DOC_FINDING_UNCERTAIN_TEXT, en.UNCERTAIN_FINDINGS), (CR.DOC_FINDING_TEXT, en.PAYSLIP_FINDINGS),
                                   (CR.DOC_FINDING_TEXT, en.DOC_FINDINGS)):
            if code in table_he and code in table_en:
                candidates.append((table_he[code][0], table_he[code][1], *table_en[code]))
    for table_he, table_en in ((RC.UNCERTAIN, en.UNCERTAIN_FINDINGS), (RC.DOCUMENT, en.DOC_FINDINGS)):
        if code in table_he and code in table_en:
            candidates.append((table_he[code][0].format(doc=doc_he), table_he[code][1], *table_en[code]))
    noun = "payslip" if family == "payslip" else en.FAMILY_NOUN.get(family, "document")
    for t_he, tpl_he, t_en, tpl_en in candidates:
        if t_he != title_he:
            continue
        detail = _detail_of(tpl_he, message_he, file=file, doc=doc_he)
        if detail:
            f["message_detail_he"] = detail
        return t_en.format(doc=noun), tpl_en.format(doc=noun, file=file)
    criterion = en.CRITERIA.get(str(d.get("criterion_id", "")))
    if criterion and title_he:                          # the fallback built from the criterion's own title
        detail = _detail_of(CR.UNCERTAIN_FALLBACK, message_he) or (message_he if message_he else None)
        if detail:
            f["message_detail_he"] = detail
        return criterion, (en.UNCERTAIN_FALLBACK if f.get("review_state") == "NEEDS_BANKER_REVIEW" else None)
    return None, None


# ---------------------------------------------------------------- actions, outcomes, requests
def action(a: dict, ctx: Ctx, findings_by_id: dict[str, dict], requirements: dict[str, dict]) -> None:
    """app_action.v1 labels (agent/actions.derive) in English; the action, its id and parameters are unchanged."""
    p, t = a.get("params") or {}, a.get("type")
    first = ctx.first.get(p.get("borrower_id") or "", "")
    label = detail = None
    if t == "NAVIGATE_TO_DOCUMENT_UPLOAD":
        q = requirements.get(p.get("requirement_code") or "", {})
        top = next((findings_by_id[i] for i in p.get("finding_ids") or [] if i in findings_by_id), None)
        missing = p.get("missing_periods") or []
        if p.get("document_type") == "PAYSLIP":
            label_he = a.get("label_he", "")
            if len(missing) == 1:
                label, detail = f"Upload the {en.month_name(missing[0])} payslip for {first}", f"Payslip for {en.month(missing[0])} missing"
            elif missing:
                label, detail = f"Upload payslips for {first}", f"Missing: {en.months(missing)}"
            elif label_he.startswith("העלאת המסמך שביקשה הבנקאית"):
                label, detail = f"Upload the document the banker asked for — {first}", None
            else:
                label, detail = f"Upload a corrected payslip for {first}", (top or {}).get("title_en")
        else:
            again = a.get("label_he", "").startswith("העלאה מחדש:")
            noun = en.FAMILY_NOUN.get(q.get("family") or "", "document")
            # the Hebrew names the borrower only when the application has more than one (agent/actions.derive)
            whose = f"{first}'s" if first and len(ctx.first) > 1 else "your"
            label = f"Re-upload {whose} {noun}" if again else f"Upload {whose} {noun}"
            detail = (top or {}).get("title_en") or q.get("title_en")
        suffix = re.search(r" · (?:מסמך אחד בבדיקה|(\d+) מסמכים בבדיקה)$", a.get("detail_he") or "")
        if suffix and detail:
            detail += " · " + ("1 document being checked" if not suffix.group(1) else f"{suffix.group(1)} documents being checked")
    elif t == "VIEW_DOCUMENT_REVIEW":
        top = next((findings_by_id[i] for i in p.get("finding_ids") or [] if i in findings_by_id), None)
        label = "View the finding"
        file = ctx.files().get(p.get("document_id") or "", "")
        detail = f"{top['title_en']} · {file}" if top and top.get("title_en") else None
    elif t == "VIEW_REVIEW_STATUS":
        label = "View the check's status"
        d = a.get("detail_he") or ""
        m = re.match(r"(\d+) מסמכים בבדיקה", d)
        detail = ("Re-checking the document set" if d == "בודקים מחדש את סט המסמכים" else
                  "1 document being checked" if d == "מסמך אחד בבדיקה" else f"{m.group(1)} documents being checked" if m else None)
    elif t == "VIEW_MISSING_DOCUMENTS":
        label = "View all missing documents"
        d = a.get("detail_he") or ""
        m = re.match(r"חסרים (\d+) תלושים", d)
        detail = "1 payslip missing" if d == "חסר תלוש אחד" else f"{m.group(1)} payslips missing" if m else None
    elif t == "CONTACT_BANKER":
        label = f"Send the application to {ctx.banker}"
        top = next((findings_by_id[i] for i in p.get("finding_ids") or [] if i in findings_by_id), None)
        detail = (top or {}).get("title_en")
        if p.get("message_he"):
            p["message_en"] = f"I agree to send my application with its findings to {ctx.banker} for review."
    elif t == "VIEW_CASE_DETAILS":
        label = "Go to the application details"
    _set(a, "label", label)
    _set(a, "detail", detail)


def outcome_view(o: dict) -> None:
    """outcomes.document_outcome / for_case views: {outcome, label_he, by?}."""
    if not isinstance(o, dict) or "outcome" not in o:
        return
    label = en.OUTCOME_INCOME_REVIEW if o.get("label_he") == "נדרש בירור בנקאי, נמצא פער בהכנסה" else en.OUTCOME.get(o["outcome"])
    _set(o, "label", label)


def customer_request(r: dict, ctx: Ctx, requirements: dict[str, dict]) -> None:
    """review_desk customer-request titles; the banker's own message stays as written."""
    first = ctx.first.get(r.get("borrower_id") or "", "")
    period, kind = r.get("period"), r.get("kind")
    who = f" — {first}" if first else ""
    if kind in ("missing_document", "correction") and period:
        title = f"Payslip for {en.month(period)} needed{who}"
    elif kind == "correction":
        file = r.get("document_filename") or ctx.files().get(r.get("document_id") or "", "")
        q = requirements.get(r.get("requirement_code") or "", {})
        noun = "payslip" if q.get("family") == "payslip" else en.FAMILY_NOUN.get(q.get("family", ""), "document")
        title = f"A corrected {noun} is needed instead of {file}{who}"
    elif kind == "missing_document":
        q = requirements.get(r.get("requirement_code") or "", {})
        title = f"Needed: {q['title_en']}" if q.get("title_en") else None
    elif kind == "explanation":
        title = f"An explanation or supporting document is needed{who}"
    elif kind == "additional_document":
        title = f"An additional document is needed{who}"
    else:
        title = None
    _set(r, "title", title)


# ---------------------------------------------------------------- responses
def snapshot(out: dict) -> None:
    """GET /api/cases/{id}."""
    ctx = Ctx(out.get("case"))
    if out.get("case"):
        _case(out["case"], ctx)
    stage_dictionary(out.get("stage_dictionary") or {})
    r = out.get("readiness") or {}
    _set(r, "state", en.READINESS.get(r.get("state", "")))
    requirements = {}
    for q in (r.get("requirements") or []) + (r.get("inactive_requirements") or []):
        requirement(q, ctx)
        if q.get("code"):
            requirements[q["code"]] = q
    for f in out.get("findings") or []:
        finding(f, ctx)
    by_id = {f["finding_id"]: f for f in out.get("findings") or []}
    for a in out.get("available_actions") or []:
        action(a, ctx, by_id, requirements)
    for cr in out.get("customer_requests") or []:
        customer_request(cr, ctx, requirements)
    for s in (out.get("document_status") or {}).values():
        _set(s, "status", en.REPLACEMENT_STATUS if s.get("status") == "REPLACEMENT" else en.DESK_STATUS.get(s.get("status", "")))
    for group in (out.get("outcomes") or {}).values():
        for o in (group or {}).values():
            outcome_view(o)


def stage_dictionary(sd: dict) -> None:
    for s in sd.get("stages") or []:
        _set(s, "label", en.BANK_STAGES.get(s.get("code", "")))
    if sd.get("note_he"):
        _set(sd, "note", en.STAGE_NOTE)


def doc_view(d: dict) -> None:
    """A document of GET /api/cases/{id}/documents or /api/documents/{id}: stage, document type, fields, criteria."""
    _set(d, "stage", en.DOC_STAGE.get(d.get("stage") or "", None))
    review = d.get("review")
    if review:
        _set(review, "doc_type", en.DOC_TYPES.get(review.get("doc_type", "")))
        for fact in review.get("facts") or []:
            label = en.FIELD_EMPLOYEE_ID_AS_PRINTED if fact.get("label_he") == "מספר זהות (מודפס כ״מזהה עובד״)" \
                else en.FIELDS.get(fact.get("field", ""))
            _set(fact, "label", label)
        for c in review.get("criteria") or []:
            _set(c, "title", en.CRITERIA.get(c.get("criterion_id", "")))
            _set(c, "explanation", criteria_en.explanation(c.get("explanation_he")))


def documents(docs: list) -> None:
    for d in docs:
        doc_view(d)


def document(doc: dict) -> None:
    """GET /api/documents/{id} (customer view): the document, its findings, its outcome and the banker's status."""
    doc_view(doc)
    case = None
    try:
        from ..bank.mock_bank import bank
        case = bank.get_case(doc.get("case_id", ""))
    except Exception:
        case = None
    ctx = Ctx(case)
    for f in doc.get("findings") or []:
        finding(f, ctx)
    outcome_view(doc.get("outcome") or {})
    s = doc.get("banker_status") or {}
    if s:
        _set(s, "status", en.DESK_STATUS.get(s.get("status", "")))


def session_cases(rows: list) -> None:
    for c in rows:
        _set(c, "title", en.case_title(c.get("title_he", "")))
        if c.get("applicants_he"):
            c["applicants_en"] = [en.name(n) for n in c["applicants_he"]]
        _set(c, "company", en.name(c.get("company_he")) if c.get("company_he") else None)


def followup(view: dict, case_id: str) -> None:
    """followup.customer_view: the state line, the reminder and the open items."""
    _set(view, "state", en.FOLLOWUP_STATE.get(view.get("state_he", "")))
    from ..bank.mock_bank import bank
    from ..followup import tasks
    ctx = Ctx(bank.get_case(case_id))
    rows = {t["requirement_code"]: t for t in tasks.open_for(case_id)}
    # a task is opened from findings (its history names them): its English title is the first finding's
    by_id = {f["finding_id"]: f for f in repo.findings(case_id, status="open")}
    for item in view.get("open_items") or []:
        t = rows.get(item.get("requirement_code"), {})
        _set(item, "customer_text", en.CUSTOMER_TEXT.get(t.get("reason_code") or ""))
        history = t.get("history") or []
        ids = (history[0] if history and isinstance(history[0], dict) else {}).get("finding_ids") or []
        f = dict(next((by_id[i] for i in ids if i in by_id), {}))
        if f:
            finding(f, ctx)
        _set(item, "title", f.get("title_en") or en.CUSTOMER_TEXT.get(t.get("reason_code") or ""))
    if view.get("nudge_text_he"):
        first = next(iter(ctx.first.values()), "")
        missing = ", ".join(i.get("customer_text_en") or i.get("title_en") or "" for i in view.get("open_items") or [])
        _set(view, "nudge_text", en.REMINDER.format(first_name=first, missing_documents=missing))


def application_options(o: dict) -> None:
    _set(o, "product", en.PRODUCTS.get(o.get("product_he", "")))
    for p in o.get("purposes") or []:
        if p.get("id") in en.PURPOSES:
            _set(p, "label", en.PURPOSES[p["id"]][0])
            _set(p, "proof", en.PURPOSES[p["id"]][1])
    if o.get("note_he"):
        _set(o, "note", "The application details only determine which documents are required. They are not an "
                        "eligibility check and not a credit offer.")


def error_text(message_he: str) -> Optional[str]:
    """The English of a customer-facing error message, when it is one of the known ones."""
    return en.error(message_he)


def requirement_title(title_he: str) -> Optional[str]:
    """A requirement title as composed by requirements.compose ('<policy label> — <owner>'), in English; None when the
    label is not one of the policy's."""
    from ..policy import store
    label, _, owner = title_he.partition(" — ")
    pol = store.published("loan_policy")["config"]
    for r in pol["document_requirements"]:
        months = str((r.get("rules") or {}).get("months") or 3)
        if r["label_he"].replace("{months}", months) == label and r["id"] in en.REQUIREMENTS:
            english = en.REQUIREMENTS[r["id"]][0].replace("{months}", months)
            if not owner:
                return english
            owner_en = en.PURPOSE_LABELS.get(owner) or en.name(owner)
            m = re.match(r"(.+?)(?: \((.+)\))?$", owner)
            if m and m.group(1).startswith("חשבון"):
                owner_en = en.account_label(m.group(1)) + (f" ({en.names(m.group(2).split(' ו'))})" if m.group(2) else "")
            return f"{english} — {owner_en}"
    return None


def profile_change(out: dict) -> None:
    """POST /api/cases/{id}/profile: the requirements added and removed, in English."""
    for key in ("added", "removed"):
        if out.get(key):
            out[f"{key}_en"] = [requirement_title(t) or t for t in out[key]]
