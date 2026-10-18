"""English of the upload outcome (agent/continuation.py): the same inputs, the same branches, the same facts, worded in
English. continuation.compose stays the Hebrew source; this module is called next to it and never instead of it."""
from __future__ import annotations

from typing import Optional

from ..bank.mock_bank import bank
from ..store import repo
from ..util import mask_ids
from ..workflow import readiness
from . import en, views

MAX_DOCS_IN_MESSAGE = 3          # continuation.MAX_DOCS_IN_MESSAGE
PHASE = {"reviewing_document": "File received. The document check is running now.",
         "rechecking_case": "Updating the picture of your application's documents…",
         "rechecking_case_reviewed": "The document was checked. Updating the picture of your application's documents…"}


def compose(case_id: str, docs: list[dict], intents: dict[str, dict]) -> str:
    case = bank.get_case(case_id)
    ctx = views.Ctx(case)
    open_f = repo.findings(case_id, status="open")
    for f in open_f:
        views.finding(f, ctx)
    from ..agent.continuation import _findings_for                     # the same selection as the Hebrew
    parts = []
    for d in docs[:MAX_DOCS_IN_MESSAGE]:
        found = _findings_for(d["document_id"], open_f)
        review = repo.latest_document_result(d["document_id"]) if d["status"] == "reviewed" else None
        parts.append(_document_sentence(d, review, intents.get(d["document_id"]) or {}, found, ctx))
    if len(docs) > MAX_DOCS_IN_MESSAGE:
        parts.append(f"{len(docs) - MAX_DOCS_IN_MESSAGE} more documents were checked.")
    parts.append(_remaining_sentence(readiness.compute(case_id), ctx, open_f))
    return mask_ids(" ".join(parts))


def _document_sentence(d: dict, review: Optional[dict], intent: dict, found: list[dict], ctx: views.Ctx) -> str:
    lead = "" if intent.get("created_new", 1) else f"The file {d['filename']} was already uploaded before and wasn't checked again. "
    if d["status"] == "failed":
        return lead + f"The check of {d['filename']} didn't finish because of a technical problem."
    if not review:
        return lead + f"{d['filename']} is still being checked."
    name = ctx.first.get(d["borrower_id"] or "", "")
    payslip = review.get("doc_type") == "payslip"
    someone_else = review.get("matched_borrower_id") not in (None, d["borrower_id"])
    from ..workflow import requirements
    family = requirements.family_of(d.get("requirement_code"), d.get("case_id"))
    if payslip and name and not someone_else:
        subject = f"{name}'s payslip"
    elif family != "payslip" and review.get("doc_type") == family:
        noun = en.FAMILY_NOUN.get(family, "document")
        subject = f"{name}'s {noun}" if name else f"The {noun}"
    else:
        subject = f"The document uploaded for {name}" if name else f"The document {d['filename']}"
    printed, chosen = review.get("period"), intent.get("expected_period")
    claimed = chosen or review.get("file_name_period")
    if payslip and printed and claimed and claimed != printed:
        why = "as you chose" if chosen else "as the file name says"
        return lead + f"{subject} was received and checked: it is printed {en.month(printed)}, not {en.month(claimed)} {why}."
    if payslip and printed:
        subject += f" for {en.month(printed)}"
    customer = [f for f in found if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
    banker = [f for f in found if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    if customer:
        what = customer[0].get("message_en") or customer[0].get("title_en")
        return lead + f"{subject} was received and checked, and needs a correction" + (f": {what}" if what else ".")
    if banker:
        what = banker[0].get("title_en")
        return lead + f"{subject} was received and checked, and was passed to the banker for review" + (f": {what}." if what else ".")
    if review.get("verdict") == "VALID":
        return lead + f"{subject} was received and checked — it's valid."
    if review.get("verdict") == "NEEDS_REVIEW":
        return lead + f"{subject} was received and checked, and needs a further review."
    return lead + f"{subject} was received and checked, and is not valid."


def _remaining_sentence(state: dict, ctx: views.Ctx, open_f: list[dict]) -> str:
    gaps = [(ctx.first.get(r["borrower_id"], ""), r["missing"]) for r in state["requirements"]
            if r["evaluated_by_ai"] and r.get("family", "payslip") == "payslip" and r.get("missing")]
    others = []
    for r in state["requirements"]:
        if r["evaluated_by_ai"] and r.get("family", "payslip") != "payslip" and r.get("ai_state") == "required_missing":
            q = dict(r)
            views.requirement(q, ctx)
            others.append(q.get("title_en") or r["title_he"])
    if sum(len(months) for _, months in gaps) == 1 and not others:
        name, months = gaps[0]
        return f"Still to upload: {name}'s payslip for {en.month(months[0])}."
    if gaps or others:
        return "Still to upload: " + "; ".join([f"{name}'s payslip{'s' if len(months) > 1 else ''} for {en.months(months)}"
                                                for name, months in gaps] + others) + "."
    customer = [f for f in open_f if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
    if customer:
        return (f"One item is left for you: {customer[0].get('title_en') or customer[0]['title_he']}." if len(customer) == 1
                else f"{len(customer)} items are left for you.")
    banker = [f for f in open_f if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    if banker:
        return "All required documents were received. " + ("One item is waiting for the banker's review." if len(banker) == 1
                                                          else f"{len(banker)} items are waiting for the banker's review.")
    return "All required documents were received and checked."


def outcome(o: dict, case_id: str) -> None:
    """GET /api/cases/{case}/documents/{doc}/outcome: message_en, and English for its findings and actions."""
    phase = o.get("phase")
    if phase == "reviewing_document":
        o["message_en"] = PHASE["reviewing_document"]
    elif phase == "rechecking_case":
        o["message_en"] = PHASE["rechecking_case_reviewed" if o.get("status") == "reviewed" else "rechecking_case"]
    elif phase == "complete":
        doc = repo.document(o["document_id"])
        intent = repo.upload_intent(o["document_id"]) or {}
        o["message_en"] = compose(case_id, [doc], {o["document_id"]: intent})
    case = bank.get_case(case_id)
    ctx = views.Ctx(case)
    full = {f["finding_id"]: f for f in repo.findings(case_id)}
    for brief in o.get("findings") or []:
        f = dict(full.get(brief.get("finding_id"), brief))
        views.finding(f, ctx)
        for k in ("title_en", "message_en", "message_detail_he"):
            if f.get(k):
                brief[k] = mask_ids(f[k])
    with_en = {}
    for f in full.values():
        views.finding(f, ctx)
        with_en[f["finding_id"]] = f
    state = readiness.compute(case_id)
    reqs = {}
    for q in state["requirements"]:
        q = dict(q)
        views.requirement(q, ctx)
        reqs[q["code"]] = q
    for a in o.get("actions") or []:
        views.action(a, ctx, with_en, reqs)


def actions_en(case_id: str, items: list[dict]) -> None:
    """English labels for actions stored on a conversation turn (they are re-derived ids, the same parameters)."""
    if not items:
        return
    case = bank.get_case(case_id)
    ctx = views.Ctx(case)
    full = {}
    for f in repo.findings(case_id):
        views.finding(f, ctx)
        full[f["finding_id"]] = f
    reqs = {}
    for q in readiness.compute(case_id)["requirements"]:
        q = dict(q)
        views.requirement(q, ctx)
        reqs[q["code"]] = q
    for a in items:
        views.action(a, ctx, full, reqs)

