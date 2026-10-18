"""Customer-side and system HTTP API of the Mortgage Case Service. Every case route checks the signed-in session
(app/auth.py): a customer reaches only their own cases; raw review data (findings, runs, audit) is bank-staff only."""
from __future__ import annotations

import csv
import io
import json
import time
import wave
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .. import auth, i18n
from ..agent import actions, agent, continuation, tools
from ..i18n import continuation_en as i18n_continuation, en as i18n_en, views as i18n_views
from ..bank.mock_bank import bank
from ..config import settings
from ..llm import gemini as g
from ..review import deterministic as det
from ..review import evidence as ev
from ..review import registry, rubrics
from ..store import repo
from ..util import sha256_bytes
from ..workflow import (demo, desk_state, engine, intake, onboarding, onboarding_chat, outcomes, profile_change, readiness,
                        review_desk)

router = APIRouter(prefix="/api")


def _case(case_id: str) -> dict:
    try:
        return bank.get_case(case_id)
    except KeyError:
        raise HTTPException(404, "no such case") from None


def _doc_view(d: dict, with_result: bool = True) -> dict:
    r = repo.latest_document_result(d["document_id"]) if with_result and d["status"] == "reviewed" else None
    run = repo.run(d["current_run_id"]) if d.get("current_run_id") else None
    return {**{k: d[k] for k in ("document_id", "case_id", "borrower_id", "requirement_code", "filename", "mime", "bytes",
                                 "pages", "text_layer_chars", "uploaded_at", "channel", "status", "stage", "error")},
            "stage_he": tools.STAGE_HE.get(d["stage"] or "", d["stage"]),
            "current_run": {k: run[k] for k in ("run_id", "status", "stage", "started_at", "finished_at", "provider")} if run else None,
            "review": r}


@router.get("/health")
def health():
    return {"ok": True, "provider": settings.review_provider, "simulation_date": settings.simulation_date,
            "data": "main" if settings.main_data else "isolated"}


@router.get("/cases")
def cases(request: Request):
    out = []
    for cid in repo.by_latest_activity(auth.require_customer(request)["cases"]):
        c = bank.get_case(cid)
        out.append({"case_id": cid, "display_number": c["display_number"], "title_he": c["title_he"],
                    "borrowers": [b["name_he"] for b in c["borrowers"]], "readiness": readiness.compute(cid)["state_he"]})
    return out


CUSTOMER_UPDATES = ("document_uploaded", "document_reviewed", "case_reviewed", "customer_statement_recorded",
                    "customer_profile_changed",
                    "banker_handoff_created", "banker_finding_decision", "banker_confirmed_preparation",
                    "document_review_failed", "banker_document_decision", "banker_requested_document",
                    "customer_request_responded", "banker_request_withdrawn", "banker_handoff_acknowledged")
# what a banker event may tell the customer; the banker's internal rationale never leaves the console
CUSTOMER_SAFE_DETAIL = ("action", "customer_message", "customer_request_id", "filename", "verdict", "period", "document_id",
                        "kind", "replaces", "reasons", "doc_type", "title_he", "statement_id")


def _customer_update(e: dict) -> dict:
    detail = e.get("detail") or {}
    if e["action"].startswith("banker_") or e["action"] == "customer_request_responded":
        detail = {k: v for k, v in detail.items() if k in CUSTOMER_SAFE_DETAIL}
        if detail.get("action") in ("ESCALATE", "ESCALATE_FINDING"):
            detail.pop("customer_message", None)
    return {**e, "actor": "banker" if e["actor"].startswith("banker") else e["actor"], "detail": detail}


def _customer_finding(f: dict) -> dict:
    return {**f, "resolution_note": None, "history": desk_state.customer_history(f["history"])}


def _customer_handoff(h: dict) -> dict:
    """A handoff as the customer may see it: never the banker's package or notes."""
    return {k: h.get(k) for k in ("package_id", "status", "created_at", "channel", "banker_decision", "decided_at")}


def _customer_readiness(state: dict) -> dict:
    confirmation = state.get("banker_confirmation")
    return {**state, "banker_confirmation": {"confirmed_at": confirmation["confirmed_at"]} if confirmation else None,
            "banker_confirmation_stale": None}


def _customer_requests(case_id: str) -> list[dict]:
    docs = {d["document_id"]: d["filename"] for d in repo.documents(case_id)}
    replies = {s["statement_id"]: s["text"] for s in repo.statements(case_id)}
    return [{"customer_request_id": r["customer_request_id"], "kind": r["kind"], "borrower_id": r["borrower_id"],
             "requirement_code": r["requirement_code"], "period": r["period"], "document_id": r["document_id"],
             "document_filename": docs.get(r["document_id"] or ""), "title_he": r["title_he"], "message_he": r["message_he"],
             "status": r["status"], "created_at": r["created_at"], "created_by_name": r["created_by_name"],
             "responded_document_id": r["responded_document_id"],
             "responded_filename": docs.get(r["responded_document_id"] or ""), "responded_at": r["responded_at"],
             "responded_text": replies.get(r.get("responded_statement_id") or ""), "can_reply": r["kind"] in ("explanation", "additional_document")}
            for r in repo.customer_requests(case_id) if r["status"] in ("OPEN", "RESPONDED")]


def _customer_document_status(case_id: str) -> dict:
    out = {}
    for did, s in desk_state.document_statuses(case_id).items():
        if s["status"] in desk_state.CUSTOMER_STATUS_HE:
            out[did] = {"status": s["status"], "status_he": desk_state.CUSTOMER_STATUS_HE[s["status"]],
                        "replaced_by": s["replaced_by"]}
        elif s["replaces"]:
            out[did] = {"status": "REPLACEMENT", "status_he": "מסמך חלופי שהעליתם", "replaces": s["replaces"]}
    return out


def _outcomes(case_id: str, state: dict) -> dict:
    docs = repo.documents(case_id)
    reviews = {d["document_id"]: repo.latest_document_result(d["document_id"]) for d in docs if d["status"] == "reviewed"}
    open_f = repo.findings(case_id, status="open")
    return outcomes.for_case(docs, reviews, desk_state.document_statuses(case_id, docs, open_f), open_f, state["requirements"])


@router.get("/cases/{case_id}")
def case_snapshot(case_id: str, request: Request):
    auth.require_customer_case(request, case_id)
    case = _case(case_id)
    latest = repo.latest_case_result(case_id)
    state = readiness.compute(case_id)
    return i18n.localized(i18n.lang(request), {"case": case, "stage_dictionary": bank.stage_dictionary(), "readiness": _customer_readiness(state),
            "available_actions": [a.model_dump() for a in actions.available(case_id, state)],
            "findings": [_customer_finding(f) for f in repo.findings(case_id)], "statements": repo.statements(case_id),
            "case_review": {k: latest.get(k) for k in ("run_id", "finished_at", "coverage", "income", "semantic", "criteria",
                                                       "limitations_he", "rubric_id", "rubric_version")} if latest else None,
            "handoffs": [_customer_handoff(h) for h in repo.handoffs(case_id)],
            "customer_requests": _customer_requests(case_id),
            "document_status": _customer_document_status(case_id),
            "outcomes": _outcomes(case_id, state),
            "updates": [_customer_update(e) for e in repo.audit_events(case_id, 80) if e["action"] in CUSTOMER_UPDATES][:25],
            "provider": registry.active().identity().model_dump()}, i18n_views.snapshot)


@router.get("/cases/{case_id}/documents")
def case_documents(case_id: str, request: Request):
    auth.require_customer_case(request, case_id)
    return i18n.localized(i18n.lang(request), [_doc_view(d) for d in repo.documents(case_id)], i18n_views.documents)


@router.post("/cases/{case_id}/documents", status_code=202)
async def upload(case_id: str, request: Request, file: UploadFile = File(...), borrower_id: Optional[str] = Form(None),
                 requirement_code: Optional[str] = Form(None), channel: str = Form("customer_app"),
                 expected_period: Optional[str] = Form(None), action_id: Optional[str] = Form(None),
                 origin_turn_id: Optional[str] = Form(None), customer_request_id: Optional[str] = Form(None),
                 replaces_document_id: Optional[str] = Form(None)):
    auth.require_customer_case(request, case_id)
    data = await file.read()
    mime = (file.content_type or "").lower()
    if mime in ("", "application/octet-stream") and (file.filename or "").lower().endswith(".pdf"):
        mime = "application/pdf"
    try:
        review_desk.check_request_link(case_id, borrower_id, customer_request_id)
        review_desk.check_replacement(case_id, borrower_id, replaces_document_id, customer_request_id)
        doc, created = engine.submit_document(case_id, file.filename or "document", mime, data, borrower_id,
                                              requirement_code, "customer", channel)
    except engine.UploadRejected as exc:
        raise HTTPException(422, str(exc)) from None
    except review_desk.DeskError as exc:
        raise HTTPException(exc.status, exc.message_he) from None
    answered = review_desk.link_upload(case_id, doc, created, customer_request_id, expected_period)
    note = None
    if not created:
        note = "הקובץ הזה כבר הועלה לתיק, לא נבדק פעם נוספת."
        if borrower_id and doc.get("borrower_id") and doc["borrower_id"] != borrower_id:
            owner = next((b["first_name_he"] for b in bank.get_case(case_id)["borrowers"] if b["borrower_id"] == doc["borrower_id"]), "")
            note = f"אותו קובץ כבר הועלה עבור {owner}. אם זה מסמך של לווה אחר, יש להעלות את המסמך הנכון."
    replaces = replaces_document_id if created else None
    intent = continuation.record_intent(case_id, doc, created, expected_period, action_id, origin_turn_id, replaces)
    if replaces:
        repo.audit(case_id, "customer", "customer_replaced_document", doc["document_id"],
                   {"document_id": doc["document_id"], "replaces": replaces, "filename": doc["filename"]})
    out = {"document": _doc_view(doc), "created": created, "note": note, "intent": intent,
           "answered_request": answered["customer_request_id"] if answered else None, "replaces": replaces}
    if note and i18n.lang(request):
        out["note_en"] = (i18n_en.DUPLICATE_UPLOAD if note.startswith("הקובץ הזה") else
                          i18n_en.DUPLICATE_OTHER_BORROWER.format(owner=i18n_en.name(owner)))
    return i18n.localized(i18n.lang(request), out, lambda o: i18n_views.doc_view(o["document"]))


class ProfileChange(BaseModel):
    borrowers: dict[str, dict]


@router.post("/cases/{case_id}/profile")
def change_profile(case_id: str, body: ProfileChange, request: Request):
    """The customer corrects their income profile after confirming the application; the checklist is recomposed by
    the same policy engine (workflow/profile_change.py). Documents and review history are kept."""
    auth.require_customer_case(request, case_id)
    try:
        out = profile_change.change(case_id, body.borrowers, "customer")
    except profile_change.ProfileError as exc:
        raise HTTPException(exc.status, exc.message_he) from None
    return i18n.localized(i18n.lang(request), {k: v for k, v in out.items() if k != "requirements"} | {
        "requirements": [{k: r[k] for k in ("code", "title_he", "owner_he", "intake")} for r in out["requirements"]]},
        i18n_views.profile_change)


class Reply(BaseModel):
    text: str


@router.post("/cases/{case_id}/customer-requests/{customer_request_id}/reply")
def reply_to_request(case_id: str, customer_request_id: str, body: Reply, request: Request):
    """The customer's written answer to a banker's explanation request — recorded as unverified context."""
    auth.require_customer_case(request, case_id)
    try:
        review_desk.reply_to_request(case_id, customer_request_id, body.text)
    except review_desk.DeskError as exc:
        raise HTTPException(exc.status, exc.message_he) from None
    return {"ok": True, "customer_request": next(q for q in _customer_requests(case_id) if q["customer_request_id"] == customer_request_id)}


def _document(request: Request, document_id: str) -> dict:
    """A document the signed-in customer (its case) or a bank staff member may read; 404 before revealing anything."""
    d = repo.document(document_id)
    if not d:
        if not (auth.staff(request) or auth.customer(request)):
            raise auth.unauthorized(auth.NEED_CUSTOMER, "staff", "customer")
        raise HTTPException(404, "no such document")
    auth.require_reader(request, d["case_id"])
    return d


@router.get("/documents/{document_id}")
def document_detail(document_id: str, request: Request):
    d = _document(request, document_id)
    return i18n.localized(i18n.lang(request), {**_doc_view(d), "runs": repo.runs(d["case_id"], document_id),
            "findings": [_customer_finding(f) for f in repo.findings(d["case_id"]) if f["document_id"] == document_id
                         or any(e.get("document_id") == document_id for e in f["evidence"])],
            "banker_status": _customer_document_status(d["case_id"]).get(document_id),
            "outcome": _outcomes(d["case_id"], readiness.compute(d["case_id"]))["documents"].get(document_id)},
                          i18n_views.document)


@router.get("/documents/{document_id}/file")
def document_file(document_id: str, request: Request):
    d = _document(request, document_id)
    return FileResponse(d["storage_path"], media_type=d["mime"], filename=d["filename"], headers={"Cache-Control": "private, no-store"})


@router.get("/documents/{document_id}/pages/{page}.png")
def document_page(document_id: str, page: int, request: Request, dpi: int = 110):
    d = _document(request, document_id)
    if page < 1 or page > (d["pages"] or 1):
        raise HTTPException(404, "no such page")
    png = ev.render_page(document_id, d["storage_path"], d["mime"], page, dpi=max(60, min(dpi, 200)))
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/documents/{document_id}/retry")
def retry(document_id: str, request: Request):
    """Re-run a review that failed. Only failed documents, only by the case's customer or its banker."""
    d = _document(request, document_id)
    role, who = auth.require_case_actor(request, d["case_id"])
    if d["status"] != "failed":
        raise HTTPException(409, "אפשר לבקש בדיקה חוזרת רק למסמך שהבדיקה שלו נכשלה.")
    engine.retry_document(document_id, "customer" if role == "customer" else f"banker:{who['staff_id']}")
    return {"queued": True}


@router.post("/cases/{case_id}/revalidate")
def revalidate(case_id: str, request: Request):
    """Re-run the set-level review — the same request the assistant's request_revalidation tool makes."""
    auth.require_customer_case(request, case_id)
    return {"queued": engine.request_case_review(case_id, "customer requested a re-check", "customer")}


@router.get("/cases/{case_id}/findings")
def findings(case_id: str, request: Request, status: Optional[str] = None):
    """Raw findings, including banker resolution notes — bank staff only (the customer gets them projected)."""
    auth.require_staff(request)
    _case(case_id)
    return repo.findings(case_id, status)


@router.get("/cases/{case_id}/runs")
def runs(case_id: str, request: Request):
    auth.require_staff(request)
    _case(case_id)
    return repo.runs(case_id)


@router.get("/runs/{run_id}")
def run_detail(run_id: str, request: Request):
    auth.require_staff(request)
    r = repo.run(run_id)
    if not r:
        raise HTTPException(404, "no such run")
    return r


@router.get("/cases/{case_id}/audit")
def audit(case_id: str, request: Request, limit: int = 200):
    """The full audit log with banker reasons and notes — bank staff only."""
    auth.require_staff(request)
    _case(case_id)
    return repo.audit_events(case_id, min(limit, 500))


@router.get("/cases/{case_id}/conversation")
def conversation(case_id: str, request: Request):
    auth.require_customer_case(request, case_id)
    lang = i18n.lang(request)
    continuation.sync_conversation(case_id, lang)
    turns = [{**t, "actions": (t["provenance"] or {}).get("actions") or []} for t in repo.turns(case_id)]
    if lang is None:                                   # the English a turn may carry is the customer app's alone
        return [{**t, "provenance": {k: v for k, v in t["provenance"].items() if k not in ("text_en", "lang")}}
                if t.get("provenance") and ("text_en" in t["provenance"] or "lang" in t["provenance"]) else t for t in turns]
    return i18n.localized(lang, turns, lambda ts: i18n_continuation.conversation_en(case_id, ts))


class Message(BaseModel):
    text: str
    channel: str = "text"
    provenance: Optional[dict] = None


@router.post("/cases/{case_id}/agent/messages")
def agent_message(case_id: str, msg: Message, request: Request):
    auth.require_customer_case(request, case_id)
    if msg.channel not in ("text", "voice"):
        raise HTTPException(422, "channel must be text or voice")
    try:
        return agent.respond(case_id, msg.text, msg.channel, msg.provenance, lang=i18n.lang(request))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/voice/transcribe")
async def transcribe(request: Request, audio: UploadFile = File(...)):
    """Server-side Hebrew speech-to-text fallback (Gemini audio understanding) for browsers
    without Hebrew speech recognition. The transcript is returned for the user to confirm."""
    auth.require_customer(request)
    data = await audio.read()
    if not data or len(data) > 8 * 1024 * 1024:
        raise HTTPException(422, "audio is empty or too large")
    mime = (audio.content_type or "audio/webm").split(";")[0]
    mime = {"audio/x-wav": "audio/wav", "audio/wave": "audio/wav"}.get(mime, mime)
    if mime == "audio/wav":
        try:
            with wave.open(io.BytesIO(data)) as w:
                too_short = w.getnframes() < w.getframerate() * 0.3
        except (wave.Error, EOFError):
            raise HTTPException(422, "audio is not a readable WAV recording") from None
        if too_short:
            raise HTTPException(422, "recording is too short")
    started = time.monotonic()
    try:
        instruction = ("Transcribe this Hebrew speech verbatim in Hebrew. Return only the transcript text, no commentary. "
                       "If nothing intelligible is said, return an empty string.")
        if i18n.lang(request) == "en":                  # the customer app in English: the customer speaks English
            instruction = ("Transcribe this English speech verbatim in English. Return only the transcript text, no "
                           "commentary. If nothing intelligible is said, return an empty string.")
        resp = g.generate(settings.model_agent, [{"role": "user", "parts": [
            g.text_part(instruction), g.inline_part(data, mime)]}],
            purpose="voice_transcribe", thinking="low", timeout=40)
    except g.GeminiError:
        raise HTTPException(502, "transcription failed") from None
    return {"text": g.response_text(resp).strip(), "engine": f"gemini:{settings.model_agent}",
            "latency_ms": int((time.monotonic() - started) * 1000)}


@router.post("/cases/{case_id}/reset")
def reset(case_id: str, request: Request):
    """Demo control: wipe one case. Off with DEMO_RESET=0; only the case's customer or its assigned banker."""
    if not settings.demo_reset:
        raise HTTPException(403, "איפוס תיקים כבוי בסביבה זו.")
    role, who = auth.require_case_actor(request, case_id)
    repo.reset_case(case_id)
    repo.audit(case_id, "customer" if role == "customer" else f"banker:{who['staff_id']}", "case_reset", case_id, {})
    return {"reset": True}


@router.get("/stage-dictionary")
def stage_dictionary(request: Request):
    return i18n.localized(i18n.lang(request), bank.stage_dictionary(), i18n_views.stage_dictionary)


# ---------------------------------------------------------------- customer-started applications (demo intake)
@router.get("/demo/applications/options")
def application_options(request: Request):
    if not settings.demo_identity:
        raise HTTPException(404, "demo intake is switched off")
    return i18n.localized(i18n.lang(request), intake.options(), i18n_views.application_options)


@router.post("/demo/applications", status_code=201)
def create_application(body: intake.Application, request: Request, response: Response):
    """A new synthetic loan application; the browser's customer session is extended to it (demo identity only)."""
    if not settings.demo_identity:
        raise HTTPException(404, "demo intake is switched off")
    try:
        case_id = intake.create(body)
    except intake.IntakeRefused as exc:
        raise HTTPException(422, str(exc)) from None
    held = (auth.customer(request) or {}).get("cases", [])
    token = auth.issue("customer", list(dict.fromkeys([case_id] + held))[:auth.MAX_CASES])
    auth.set_session(response, "customer", token)
    repo.audit(case_id, "customer", "loan_application_started", case_id,
               {"purpose": body.purpose, "employment": body.employment, "payments": body.payments})
    return {"case_id": case_id, "requirements": [r["title_he"] for r in bank.requirements(case_id)]}


# ---------------------------------------------------------------- new-customer questionnaire (JEEN chat, demo intake)
class OnboardingAnswer(BaseModel):
    question_id: str
    value: object = None


def _onboarding(fn, *args):
    if not settings.demo_identity:
        raise HTTPException(404, "demo intake is switched off")
    try:
        return fn(*args)
    except onboarding.OnboardingError as exc:
        raise HTTPException(exc.status, exc.message_he) from None


@router.post("/demo/onboarding", status_code=201)
def onboarding_start():
    """A new questionnaire draft. It is not a case: no requirement, follow-up or review exists until it is confirmed."""
    return _onboarding(onboarding.start)


@router.get("/demo/onboarding/{draft_id}")
def onboarding_get(draft_id: str):
    return _onboarding(onboarding.view, draft_id)


@router.post("/demo/onboarding/{draft_id}/answers")
def onboarding_answer(draft_id: str, body: OnboardingAnswer):
    return _onboarding(onboarding.answer, draft_id, body.question_id, body.value)


class OnboardingTurn(BaseModel):
    text: Optional[str] = Field(None, max_length=onboarding_chat.MAX_TEXT)
    question_id: Optional[str] = None
    value: object = None
    label_he: Optional[str] = Field(None, max_length=120)
    label_en: Optional[str] = Field(None, max_length=120)
    action: Optional[Literal["edit", "cancel_edit", "simulate_confirm", "simulate_apply"]] = None
    turn_id: Optional[str] = Field(None, max_length=64)
    simulation: Optional[dict] = None


class SimulationDraft(BaseModel):
    draft: dict


@router.post("/demo/onboarding/v2", status_code=201)
def onboarding_v2_start(request: Request):
    """A new questionnaire draft, asked as a conversation (V2). Same draft table and confirmation as V1."""
    return _onboarding(onboarding_chat.start, i18n.lang(request))


@router.get("/demo/onboarding/{draft_id}/v2")
def onboarding_v2_get(draft_id: str, request: Request):
    return _onboarding(onboarding_chat.view, draft_id, i18n.lang(request))


@router.post("/demo/onboarding/{draft_id}/v2/turn")
def onboarding_v2_turn(draft_id: str, body: OnboardingTurn, request: Request):
    """One customer turn → one assistant message: a quick reply, free text (Gemini by default, else the
    deterministic parser; the questionnaire validates either way) or an edit action. A repeated turn_id is a no-op."""
    return _onboarding(onboarding_chat.turn, draft_id, body.text, body.question_id, body.value, body.label_he, body.action,
                       body.turn_id, body.simulation, body.label_en, i18n.lang(request))


@router.post("/demo/onboarding/{draft_id}/v2/simulation")
def onboarding_v2_simulation(draft_id: str, body: SimulationDraft, request: Request):
    """Save the loan simulator's unconfirmed scenario (slider moves): no message, no answer, no model call."""
    return _onboarding(onboarding_chat.save_simulation, draft_id, body.draft, i18n.lang(request))


@router.post("/demo/onboarding/{draft_id}/v2/confirm")
def onboarding_v2_confirm(draft_id: str, request: Request, response: Response):
    """V1's confirmation (one case, session extended), then the chosen loan category is stored on the case."""
    out = onboarding_confirm(draft_id, request, response)
    _onboarding(onboarding_chat.annotate_case, draft_id, out["case_id"])
    return out


@router.post("/demo/onboarding/{draft_id}/confirm")
def onboarding_confirm(draft_id: str, request: Request, response: Response):
    """Create the case from the confirmed profile (once — repeating returns the same case) and extend the session to it."""
    case_id, created = _onboarding(onboarding.confirm, draft_id)
    held = (auth.customer(request) or {}).get("cases", [])
    token = auth.issue("customer", list(dict.fromkeys([case_id] + held))[:auth.MAX_CASES])
    auth.set_session(response, "customer", token)
    if created:
        repo.audit(case_id, "customer", "loan_application_started", case_id, onboarding.audit_detail(draft_id))
    return {"case_id": case_id, "created": created,
            "requirements": [{k: r[k] for k in ("code", "title_he", "owner_he", "intake")} for r in bank.requirements(case_id)]}


FIXTURES = settings.frontend_dist.parent.parent / "fixtures" / "out"
FIXTURE_NOTES = {"digital_reissued": "שם הקובץ: ספטמבר · התוכן: אוגוסט", "scan": "סריקה ללא שכבת טקסט", "unreadable": "סריקה לא קריאה",
                 "injection": "מכיל הוראה למערכת", "contradictory": "סכומים סותרים"}


@router.get("/fixtures")
def fixtures():
    manifest = FIXTURES / "manifest.json"
    if not manifest.exists():
        return []
    import json as _json
    files = _json.loads(manifest.read_text(encoding="utf8"))["files"]
    return [{"file": f["file"], "scene": f["scene"], "variant": f["variant"], "upload_as": f["upload_as"],
             "note": FIXTURE_NOTES.get(f["variant"], "")} for f in files]


@router.get("/fixtures/file")
def fixture_file(path: str):
    target = (FIXTURES / path).resolve()
    if FIXTURES.resolve() not in target.parents or target.suffix != ".pdf" or not target.exists():
        raise HTTPException(404, "no such fixture")
    return FileResponse(target, media_type="application/pdf", filename=target.name)


# Presenter golden set: expected outputs are static ground truth shown next to the live app, never fed into it.
PRESENTER = FIXTURES.parent / "presenter"
PRESENTER_MANIFEST = PRESENTER / "presenter_scenarios_manifest.json"
PRESENTER_NEGATIVE = "golden_set/05_EXPECTED/negative_test_expectations.json"
PRESENTER_RUBRICS = "golden_set/06_RUBRICS"


def _presenter_path(relative: str) -> Optional[Path]:
    # manifest paths are relative to fixtures/presenter; the Lavi payslips it lists live next to it in fixtures/out
    target = (PRESENTER / relative).resolve()
    return target if FIXTURES.parent.resolve() in target.parents and target.is_file() else None


def _presenter_json(relative: str) -> Optional[dict]:
    target = _presenter_path(relative)
    return json.loads(target.read_text(encoding="utf8")) if target and target.suffix == ".json" else None


@router.get("/presenter/scenarios")
def presenter_scenarios():
    manifest = _presenter_json(PRESENTER_MANIFEST.name)
    if manifest is None:
        raise HTTPException(404, "presenter manifest not installed")
    listing = _presenter_path("golden_set/MANIFEST.csv")
    rows = {r["path"]: r for r in csv.DictReader(listing.open(encoding="utf-8-sig"))} if listing else {}
    files = {}
    for d in manifest["documents"]:
        target = _presenter_path(d["downloadPath"])
        data = target.read_bytes() if target else b""
        row = rows.get(d["id"], {})
        files[d["id"]] = {"available": bool(data), "bytes": len(data), "sha256_matches_manifest": sha256_bytes(data) == d["sha256"],
                          "pages": int(row["pages"]) if row.get("pages") else None, "input_mode": row.get("input_mode")}
    refs = sorted({s["expectedJson"] for s in manifest["scenarios"] if s.get("expectedJson")})
    # the engine's own rubrics (latest version per family) — what the app on the right actually checks against
    engine = [rubrics.latest(rid) for rid in rubrics.FAMILY_RUBRIC.values() if any(
        r["rubric_id"] == rid for r in rubrics.all_rubrics().values())]
    return {"manifest": manifest, "files": files, "expected": {ref: _presenter_json(ref) for ref in refs},
            "negative_tests": (_presenter_json(PRESENTER_NEGATIVE) or {}).get("tests", []),
            "rubrics": [{**r, "document_type": r.get("family", "payslip")} for r in engine]}


@router.get("/presenter/file")
def presenter_file(doc_id: str = Query(alias="id")):
    manifest = _presenter_json(PRESENTER_MANIFEST.name) or {"documents": []}
    doc = next((d for d in manifest["documents"] if d["id"] == doc_id), None)
    target = _presenter_path(doc["downloadPath"]) if doc else None
    if not target or target.suffix != ".pdf":
        raise HTTPException(404, "no such presenter document")
    data = target.read_bytes()
    if sha256_bytes(data) != doc["sha256"]:
        raise HTTPException(409, "presenter document does not match its manifest checksum")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{target.name}"', "Cache-Control": "no-store"})


@router.post("/presenter/demo-reset")
def presenter_demo_reset(request: Request):
    """Presenter control "התחל דמו חדש": wipes the executive demo cases (006–011) and nothing else. Off with
    DEMO_RESET=0; needs any signed-in session (the presenter is signed in to the app on the right)."""
    if not settings.demo_reset:
        raise HTTPException(403, "איפוס תיקים כבוי בסביבה זו.")
    s, c = auth.staff(request), auth.customer(request)
    if not (s or c):
        raise auth.unauthorized(auth.NEED_CUSTOMER, "staff", "customer")
    try:
        return demo.reset_executive_cases(f"banker:{s['staff_id']}" if s else "presenter")
    except demo.DemoBusy:
        raise HTTPException(409, "בדיקת מסמך עדיין רצה באחד מתיקי הדמו, האיפוס יתבצע מיד כשתסתיים.") from None


@router.post("/system/mcp-selftest")
def mcp_selftest(request: Request):
    """A real MCP round trip over HTTP against this server's own /mcp, compared with the app state. Reads case data,
    so bank staff only."""
    auth.require_staff(request)
    import httpx as _httpx
    keys = {case: key for key, case in settings.mcp_keys.items()}
    base = str(request.base_url).rstrip("/") + "/mcp"
    case_id = "DEMO-MTZ-2026-001"

    def rpc(key: str, msg: dict) -> tuple[int, dict]:
        r = _httpx.post(base, json=msg, timeout=30, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                                              "Accept": "application/json, text/event-stream",
                                                              "MCP-Protocol-Version": "2025-06-18"})
        return r.status_code, (r.json() if r.content else {})

    exchange = []
    _, init = rpc(keys[case_id], {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "selftest", "version": "1"}}})
    exchange.append({"method": "initialize", "result": init.get("result", {}).get("serverInfo")})
    rpc(keys[case_id], {"jsonrpc": "2.0", "method": "notifications/initialized"})
    _, listed = rpc(keys[case_id], {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_ = [t["name"] for t in listed.get("result", {}).get("tools", [])]
    exchange.append({"method": "tools/list", "tools": tools_})
    _, called = rpc(keys[case_id], {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                    "params": {"name": "get_case_overview", "arguments": {}}})
    overview = called.get("result", {}).get("structuredContent", {})
    exchange.append({"method": "tools/call get_case_overview", "spoken_he": overview.get("spoken_he"),
                     "ai_document_readiness": overview.get("ai_document_readiness"), "counts": overview.get("counts")})
    app_state = readiness.compute(case_id)
    consistent = (overview.get("ai_document_readiness", {}).get("state") == app_state["state"]
                  and overview.get("counts", {}).get("customer_actions") == app_state["counts"]["customer_actions"])
    cross_ok = True
    if "DEMO-MTZ-2026-002" in keys:
        _, other = rpc(keys["DEMO-MTZ-2026-002"], {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                                    "params": {"name": "list_documents", "arguments": {}}})
        other_docs = {d["document_id"] for d in other.get("result", {}).get("structuredContent", {}).get("documents", [])}
        mine = {d["document_id"] for d in repo.documents(case_id)}
        cross_ok = not (other_docs & mine)
        exchange.append({"method": "tools/call list_documents (key bound to DEMO-MTZ-2026-002)", "documents_visible": len(other_docs),
                         "overlap_with_001": len(other_docs & mine)})
    status, denied = rpc("mcs_invalid_key_for_test", {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {}})
    exchange.append({"method": "tools/list with an invalid key", "http_status": status, "error": denied.get("error", {}).get("message")})
    return {"protocol": init.get("result", {}).get("protocolVersion"), "tools": tools_, "consistent": consistent,
            "cross_case_denied": cross_ok and status == 401, "app_state": app_state["state"], "exchange": exchange}


@router.get("/system/rubrics")
def system_rubrics():
    return list(rubrics.all_rubrics().values())


@router.get("/system/llm")
def system_llm():
    return g.ledger_summary()


def _followup_rows() -> list[dict]:
    from .. import db, flags
    from ..comms import registry as talk
    from ..followup import orchestrator
    pol, version = orchestrator.published_policy()
    provider = talk.active(pol)
    attempts = db.one("SELECT COUNT(*) n, SUM(simulated) s FROM contact_attempts") or {}
    return [
        {"component": "Follow-up engine (completion tasks, presence, policy, scheduler)", "state": "LOCAL",
         "detail": f"tick every {engine.TICK_SECONDS:g} s in review-worker-0 · policy {version} · kill switch "
                   f"{'ON' if flags.get(flags.KILL_SWITCH) else 'off'}"},
        {"component": "JEEN Talk (outbound follow-up calls)", "state": "DEMO",
         "detail": f"SIMULATION — {getattr(provider, 'name', 'none')} never dials; live slot not configured · talk.mode="
                   f"{pol.talk.mode if pol else 'off'} · {attempts.get('n') or 0} attempts ({attempts.get('s') or 0} simulated)"},
    ]


@router.get("/system/integrations")
def integrations():
    gem = registry.gemini().readiness()
    vt = registry.visiontrace()
    probe = vt.probe_mcp()
    ledger = g.ledger_summary()
    last = ledger.get("last") or {}
    stages_by_model: dict[str, list[str]] = {}
    for stage, model in gem["models"].items():
        stages_by_model.setdefault(model, []).append(stage)
    return {"matrix": [
        {"component": "Gemini document review (classification, OCR/extraction, judge, semantic review)",
         "state": "LIVE" if gem["configured"] else "BLOCKED",
         "detail": " · ".join(f"{model} ({', '.join(stages)})" for model, stages in stages_by_model.items())},
        {"component": "Gemini conversational agent (function calling)", "state": "LIVE" if gem["configured"] else "BLOCKED",
         "detail": f"{settings.model_agent} · last Gemini call: "
                   + ("none yet" if not last else "ok" if str(last.get("ok")) == "1" else "failed")},
        {"component": "Deterministic validation, evidence verification, rubric policy", "state": "LOCAL",
         "detail": "PyMuPDF text layer · crop re-read for scans · versioned rubrics on disk"},
        {"component": "Loan Case Service (state, workflow, findings lifecycle, audit)", "state": "LOCAL",
         "detail": f"SQLite at {settings.db_path.name} · durable jobs with retry"},
        {"component": "Loan Case MCP server", "state": "LOCAL",
         "detail": "POST /mcp · Streamable HTTP · case-bound bearer keys"},
        {"component": "Voice — browser speech (STT/TTS) on the same agent", "state": "LOCAL",
         "detail": "Web Speech he-IL when available; Gemini transcription fallback; system Hebrew voice for answers"},
        *_followup_rows(),
        {"component": "VisionTrace review provider", "state": "BLOCKED", "detail": "; ".join(vt.readiness()["missing"])},
        {"component": "VisionTrace MCP (read-only probe)", "state": probe["state"], "detail": probe["detail"]},
        {"component": "Bank systems (case stage, requirements, acceptance)", "state": "DEMO",
         "detail": "synthetic bank adapter · not authoritative"},
        {"component": "Identity & authorization", "state": "DEMO",
         "detail": "server-checked signed sessions on every route; demo sessions issued without a login (DEMO_IDENTITY); "
                   "banker writes need the case's assigned banker; MCP keys bound to one case"},
    ], "llm": ledger, "provider": settings.review_provider}
