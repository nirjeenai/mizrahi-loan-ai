"""After-upload continuation — what happened to an uploaded document and what is still open,
composed from persisted review results and the refreshed case state, never by the model.
An upload that started from an assistant action gets one follow-up message in the same
conversation, posted only after the document review and the re-check of the whole set."""
from __future__ import annotations

import threading
from typing import Optional

from ..bank.mock_bank import bank
from ..review import deterministic as det
from ..store import repo
from ..util import mask_ids, now_iso
from ..workflow import engine, readiness
from . import actions

_lock = threading.Lock()
MAX_DOCS_IN_MESSAGE = 3


def record_intent(case_id: str, doc: dict, created: bool, expected_period: Optional[str], action_id: Optional[str],
                  origin_turn_id: Optional[str], replaces_document_id: Optional[str] = None) -> Optional[dict]:
    """What the customer meant to upload. Never passed to the review provider: the review stays blind."""
    period = expected_period if expected_period in readiness.policy_months(case_id) else None
    turn = repo.turn(origin_turn_id) if origin_turn_id else None
    origin = turn if turn and turn["case_id"] == case_id and turn["role"] == "assistant" else None
    replaces = replaces_document_id if created else None
    if not period and not origin and not replaces:
        return None
    known = action_id is not None and (action_id in (actions.offered_in(origin) if origin else set())
                                       or any(a.action_id == action_id for a in actions.available(case_id)))
    row = {"document_id": doc["document_id"], "case_id": case_id, "requirement_code": doc["requirement_code"],
           "expected_period": period, "action_id": action_id if known else None,
           "origin_turn_id": origin["turn_id"] if origin else None, "created_new": int(created), "created_at": now_iso(),
           "replaces_document_id": replaces}
    repo.save_upload_intent(row)
    return row


def outcome(case_id: str, document_id: str) -> dict:
    doc = repo.document(document_id)
    if not doc or doc["case_id"] != case_id:
        raise KeyError(document_id)
    intent = repo.upload_intent(document_id) or {}
    base = {"document_id": document_id, "filename": doc["filename"], "borrower_id": doc["borrower_id"],
            "status": doc["status"], "expected_period": intent.get("expected_period"), "findings": [], "actions": []}
    if doc["status"] in ("queued", "processing"):
        return {**base, "phase": "reviewing_document", "message_he": "הקובץ התקבל. בדיקת המסמך רצה כעת."}
    if engine.pending_jobs(case_id):
        return {**base, "phase": "rechecking_case",
                "message_he": ("המסמך נבדק. " if doc["status"] == "reviewed" else "") + "מעדכנים את תמונת המסמכים בתיק…"}
    message, next_actions, related = compose(case_id, [doc], {document_id: intent})
    review = repo.latest_document_result(document_id) if doc["status"] == "reviewed" else None
    return {**base, "phase": "complete", "verdict": (review or {}).get("verdict"), "printed_period": (review or {}).get("period"),
            "message_he": message, "findings": related, "actions": [a.model_dump() for a in next_actions]}


def compose(case_id: str, docs: list[dict], intents: dict[str, dict]) -> tuple[str, list[actions.AppAction], list[dict]]:
    names = {b["borrower_id"]: b["first_name_he"] for b in bank.get_case(case_id)["borrowers"]}
    open_f = repo.findings(case_id, status="open")
    parts, related = [], []
    for d in docs[:MAX_DOCS_IN_MESSAGE]:
        found = _findings_for(d["document_id"], open_f)
        related += [f for f in found if f not in related]
        review = repo.latest_document_result(d["document_id"]) if d["status"] == "reviewed" else None
        parts.append(_document_sentence(d, review, intents.get(d["document_id"]) or {}, found, names))
    if len(docs) > MAX_DOCS_IN_MESSAGE:
        parts.append(f"ועוד {len(docs) - MAX_DOCS_IN_MESSAGE} מסמכים נבדקו.")
    parts.append(_remaining_sentence(readiness.compute(case_id), names, open_f))
    return mask_ids(" ".join(parts)), _next_actions(case_id, docs, related), [_brief(f) for f in related]


def _findings_for(document_id: str, open_f: list[dict]) -> list[dict]:
    found = [f for f in open_f if f.get("document_id") == document_id
             or document_id in ((f.get("detail") or {}).get("documents") or [])]
    return sorted(found, key=lambda f: (f.get("document_id") != document_id, actions.FINDING_RANK.get(f["review_state"], 3)))


def _document_sentence(d: dict, review: Optional[dict], intent: dict, found: list[dict], names: dict) -> str:
    lead = "" if intent.get("created_new", 1) else f"הקובץ {d['filename']} כבר הועלה לתיק קודם ולא נבדק שוב. "
    if d["status"] == "failed":
        return lead + f"הבדיקה של {d['filename']} לא הושלמה בגלל תקלה טכנית."
    if not review:
        return lead + f"{d['filename']} עדיין בבדיקה."
    name = names.get(d["borrower_id"] or "", "")
    payslip = review.get("doc_type") == "payslip"
    someone_else = review.get("matched_borrower_id") not in (None, d["borrower_id"])
    from ..review.reason_codes import DOC_HE
    from ..workflow import requirements
    family = requirements.family_of(d.get("requirement_code"), d.get("case_id"))
    if payslip and name and not someone_else:
        subject = f"התלוש של {name}"
    elif family != "payslip" and review.get("doc_type") == family:
        subject = DOC_HE[family] + (f" של {name}" if name else "")
    else:
        subject = f"המסמך שהועלה עבור {name}" if name else f"המסמך {d['filename']}"
    printed, chosen = review.get("period"), intent.get("expected_period")
    claimed = chosen or review.get("file_name_period")
    if payslip and printed and claimed and claimed != printed:
        why = "כפי שבחרתם" if chosen else "כפי ששם הקובץ מציין"
        return lead + f"{subject} התקבל ונבדק: מודפס בו {det.month_label_he(printed)}, ולא {det.month_label_he(claimed)} {why}."
    if payslip and printed:
        subject += f" ל{det.month_label_he(printed)}"
    customer = [f for f in found if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
    banker = [f for f in found if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    if customer:
        return lead + f"{subject} התקבל ונבדק, ונדרש תיקון: {customer[0]['message_he']}"
    if banker:
        return lead + f"{subject} התקבל ונבדק, והועבר לבדיקת הבנקאית: {banker[0]['title_he']}."
    if review.get("verdict") == "VALID":
        return lead + f"{subject} התקבל ונבדק, נמצא תקין."
    if review.get("verdict") == "NEEDS_REVIEW":
        return lead + f"{subject} התקבל ונבדק, ודורש בדיקה נוספת."
    return lead + f"{subject} התקבל ונבדק ונמצא לא תקין."


def _remaining_sentence(state: dict, names: dict, open_f: list[dict]) -> str:
    gaps = [(names.get(r["borrower_id"], ""), r["missing"]) for r in state["requirements"]
            if r["evaluated_by_ai"] and r.get("family", "payslip") == "payslip" and r.get("missing")]
    others = [r["title_he"] for r in state["requirements"] if r["evaluated_by_ai"]
              and r.get("family", "payslip") != "payslip" and r.get("ai_state") == "required_missing"]
    if sum(len(months) for _, months in gaps) == 1 and not others:
        name, months = gaps[0]
        return f"נותר להעלות את תלוש {det.month_label_he(months[0])} של {name}."
    if gaps or others:
        return "נותרו להעלות: " + "; ".join([f"תלושים של {name}, {actions.months_he(months)}" for name, months in gaps]
                                            + others) + "."
    customer = [f for f in open_f if f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
    if customer:
        return (f"נותר פריט אחד לטיפולכם: {customer[0]['title_he']}." if len(customer) == 1
                else f"נותרו {len(customer)} פריטים לטיפולכם.")
    banker = [f for f in open_f if f["review_state"] == "NEEDS_BANKER_REVIEW"]
    if banker:
        return "כל המסמכים הנדרשים התקבלו. " + ("פריט אחד ממתין לבדיקת הבנקאית." if len(banker) == 1
                                                 else f"{len(banker)} פריטים ממתינים לבדיקת הבנקאית.")
    return "כל המסמכים הנדרשים התקבלו ונבדקו."


def _next_actions(case_id: str, docs: list[dict], related: list[dict]) -> list[actions.AppAction]:
    ids = {d["document_id"] for d in docs}
    banker_related = any(f["review_state"] == "NEEDS_BANKER_REVIEW" for f in related)
    keep = [a for a in actions.available(case_id)
            if a.type == "NAVIGATE_TO_DOCUMENT_UPLOAD"
            or (a.type == "VIEW_DOCUMENT_REVIEW" and a.params["document_id"] in ids)
            or (a.type == "CONTACT_BANKER" and banker_related)]
    return keep[:3]


def _brief(f: dict) -> dict:
    return {"finding_id": f["finding_id"], "code": f["code"], "review_state": f["review_state"], "title_he": f["title_he"],
            "message_he": mask_ids(f["message_he"]), "document_id": f.get("document_id")}


def sync_conversation(case_id: str, lang: Optional[str] = None) -> Optional[dict]:
    """Posts the follow-up for finished assistant-originated uploads. Idempotent; called on conversation reads.
    `lang`: the customer app's language (X-MZ-Lang); with it the follow-up also stores its English (text_en)."""
    with _lock:
        waiting = repo.upload_intents_awaiting_followup(case_id)
        if not waiting or engine.pending_jobs(case_id):
            return None
        docs = [d for d in (repo.document(i["document_id"]) for i in waiting) if d]
        if not docs or any(d["status"] in ("queued", "processing") for d in docs):
            return None
        from .agent import guard_reply                     # agent imports this module
        text, next_actions, _ = compose(case_id, docs, {i["document_id"]: i for i in waiting})
        reply, guard = guard_reply(text)
        english = {}
        if lang and not guard["blocked"]:
            try:
                from ..i18n import continuation_en
                english = {"text_en": continuation_en.compose(case_id, docs, {i["document_id"]: i for i in waiting})}
            except Exception:                       # English must never cost the customer the Hebrew follow-up
                import logging
                logging.getLogger("continuation").exception("English follow-up failed; the Hebrew one is posted alone")
        turn = repo.add_turn(case_id, "app", "assistant", reply, {
            "source": "mortgage_case_service", "event": "upload_outcome", "document_ids": [d["document_id"] for d in docs],
            "actions": [] if guard["blocked"] else [a.model_dump() for a in next_actions], "guard": guard, **english})
        repo.set_upload_followup([i["document_id"] for i in waiting], turn["turn_id"])
        repo.audit(case_id, "case_service", "assistant_followup_posted", turn["turn_id"],
                   {"document_ids": [d["document_id"] for d in docs]})
        return turn
