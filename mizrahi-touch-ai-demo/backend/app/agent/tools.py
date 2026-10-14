"""The case tools — ONE registry used by the Gemini agent (chat and voice) and by the MCP
server (JEEN Talk / JEEN agents). Every tool is bound to the caller's case by the server;
a model never chooses which case it reads. Writes require explicit customer confirmation
and are idempotent per request id."""
from __future__ import annotations

from typing import Any, Callable, Optional

from ..bank.mock_bank import bank
from ..review import deterministic as det
from ..store import repo
from ..util import mask_ids, new_id, now_iso, stable_hash
from ..workflow import desk_state, engine, readiness, review_desk
from . import actions

APP_CHANNELS = ("text", "voice")
NOTICE = "בדיקת מסמכים אוטומטית בלבד — לא החלטת אשראי ולא קבלת מסמך על ידי הבנק. הבנקאי מחליט."
MODE = {"bank": "DEMO", "review_provider": "gemini (LIVE)", "data": "synthetic"}
VERDICT_HE = {"VALID": "נמצא תקין בבדיקה האוטומטית", "INVALID": "לא תקין — נדרש תיקון", "NEEDS_REVIEW": "דורש בדיקה"}
STAGE_HE = {"queued": "ממתין לבדיקה", "intake": "קליטה", "extract": "קריאה וחילוץ", "verify_evidence": "אימות ראיות",
            "deterministic_checks": "בדיקות כללים", "judge": "שיפוט לפי רובריקה", "done": "הבדיקה הושלמה",
            "retrying": "ניסיון חוזר", "failed": "הבדיקה נכשלה", "human_review": "התקבל · ממתין לבדיקת הבנקאי"}


class ToolError(ValueError):
    pass


def _borrowers(case_id: str) -> dict[str, dict]:
    return {b["borrower_id"]: b for b in bank.get_case(case_id)["borrowers"]}


def _doc_summary(case_id: str, d: dict) -> dict:
    r = repo.latest_document_result(d["document_id"]) if d["status"] == "reviewed" else None
    b = _borrowers(case_id).get(d["borrower_id"] or "", {})
    net = next((f for f in (r or {}).get("facts", []) if f["field"] == "net_pay"), None)
    return {"document_id": d["document_id"], "filename": d["filename"], "uploaded_for": b.get("first_name_he"),
            "status_he": STAGE_HE.get(d["stage"] or d["status"], d["status"]),
            "verdict": (r or {}).get("verdict"), "verdict_he": VERDICT_HE.get((r or {}).get("verdict"), "בבדיקה"),
            "doc_type_he": (r or {}).get("doc_type_he"),
            "printed_period": det.month_label_he(r["period"]) if r and r.get("period") else None,
            "file_name_claims": det.month_label_he(r["file_name_period"]) if r and r.get("file_name_period") else None,
            "net_pay_ils": net.get("value_normalized") if net else None}


def _finding_view(f: dict) -> dict:
    return {"finding_id": f["finding_id"], "code": f["code"], "title_he": f["title_he"], "message_he": mask_ids(f["message_he"]),
            "review_state": f["review_state"], "status": f["status"], "period": f["period"],
            "document_id": f["document_id"], "evidence_count": len(f["evidence"])}


def _app_actions(case_id: str, ctx: dict, keep: Callable[[actions.AppAction], bool] = lambda a: True) -> dict:
    """Actions the in-app assistant may offer as buttons. Phone and MCP callers have no screen to put them on."""
    if ctx.get("channel") not in APP_CHANNELS:
        return {}
    return {"app_actions": [actions.compact(a) for a in actions.available(case_id) if keep(a)]}


# ---------------------------------------------------------------- tool handlers
def get_case_overview(case_id: str, args: dict, ctx: dict) -> dict:
    case = bank.get_case(case_id)
    state = readiness.compute(case_id)
    reqs = [{"code": r["code"], "title_he": r["title_he"], "document_type_he": r.get("family_he"),
             "ai_state_he": r["ai_state_he"],
             "missing_months": [det.month_label_he(m) for m in r.get("missing", [])],
             "duplicate_months": [det.month_label_he(m) for m in r.get("duplicates", {})]}
            for r in state["requirements"] if r["evaluated_by_ai"]]
    stage = case["bank_stage"]
    requests = repo.customer_requests(case_id, status="OPEN")
    progress = state.get("progress") or {}
    spoken = (f"שלב הבקשה במערכת הבנק: {stage['label_he']}. מצב בדיקת מסמכי הבקשה: {state['state_he']} "
              f"({progress.get('done', 0)} מתוך {progress.get('total', 0)} דרישות הושלמו). "
              f"פריטים לטיפולכם: {state['counts']['customer_actions'] + len(requests)}, "
              f"פריטים לבדיקת הבנקאי: {state['counts']['banker_items']}."
              + (f" הבנקאית ביקשה: {requests[0]['title_he']}." if requests else ""))
    return {"spoken_he": spoken,
            "bank_stage": {"label_he": stage["label_he"], "step": f"{stage['index']}/{stage['of']}",
                           "source": stage["source"], "authoritative": False},
            "preliminary_decision": case.get("preliminary_decision"),
            "ai_document_readiness": {"state": state["state"], "state_he": state["state_he"]},
            "borrowers": [{"borrower_id": b["borrower_id"], "first_name_he": b["first_name_he"]} for b in case["borrowers"]],
            "loan": {k: (case.get("loan") or {}).get(k) for k in ("product_he", "purpose_he", "requested_amount_ils", "payments")},
            "document_requirements": reqs, "counts": state["counts"],
            "banker_requests": [_request_view(q) for q in requests],
            "not_evaluated_in_demo": state["not_evaluated"], "banker": case["banker"],
            "notice": NOTICE, "mode": MODE, **_app_actions(case_id, ctx)}


def list_documents(case_id: str, args: dict, ctx: dict) -> dict:
    docs = [d for d in repo.documents(case_id) if not args.get("borrower_id") or d["borrower_id"] == args["borrower_id"]]
    return {"documents": [_doc_summary(case_id, d) for d in docs], "notice": NOTICE}


def get_document_review(case_id: str, args: dict, ctx: dict) -> dict:
    doc = repo.document(args.get("document_id", ""))
    if not doc or doc["case_id"] != case_id:
        raise ToolError("אין מסמך כזה בתיק")
    r = repo.latest_document_result(doc["document_id"])
    if not r:
        return {"document": _doc_summary(case_id, doc), "review": None, "spoken_he": "המסמך עדיין בבדיקה."}
    facts = [{"field": f["label_he"], "value": mask_ids(str(f["value_raw"] or "")),
              "verified_against_file": (f.get("evidence") or {}).get("witness") in ("text_layer_exact", "vision_reread_confirmed")}
             for f in r["facts"] if f["field"] in ("employee_name", "employee_id", "employer_name", "salary_period",
                                                    "gross_pay", "net_pay", "payment_date")]
    open_f = [_finding_view(f) for f in repo.findings(case_id, status="open") if f["document_id"] == doc["document_id"]]
    related = _app_actions(case_id, ctx, lambda a: a.params.get("document_id") == doc["document_id"]
                           or a.params.get("borrower_id") == doc["borrower_id"])
    return {"document": _doc_summary(case_id, doc), **related,
            "review": {"verdict": r["verdict"], "verdict_he": VERDICT_HE[r["verdict"]], "summary_he": r["summary_he"],
                       "criteria": [{"id": c["criterion_id"], "title_he": c["title_he"], "outcome": c["outcome"],
                                     "explanation_he": mask_ids(c["explanation_he"])} for c in r["criteria"]],
                       "facts": facts, "limitations_he": r["limitations_he"][:3],
                       "rubric": f"{r['rubric_id']}@{r['rubric_version']}", "provider": r["identity"]["provider"],
                       "model": r["identity"]["models"].get("judge"), "run_id": r["run_id"], "finished_at": r["finished_at"]},
            "open_findings": open_f, "notice": NOTICE}


def _request_view(q: dict) -> dict:
    """A banker's in-app request as the customer may hear it — the customer-facing message only."""
    return {"customer_request_id": q["customer_request_id"], "kind": q["kind"], "title_he": q["title_he"],
            "message_he": mask_ids(q["message_he"]), "period": q["period"], "borrower_id": q["borrower_id"],
            "finding_id": q["finding_id"], "requested_by": q["created_by_name"], "status": q["status"],
            "how_to_answer": "תשובה בכתב (תתועד כהסבר לא מאומת) או העלאת מסמך" if q["kind"] in ("explanation", "additional_document")
            else "העלאת המסמך המבוקש"}


def list_open_items(case_id: str, args: dict, ctx: dict) -> dict:
    audience = args.get("audience", "customer")
    wanted = {"customer": ("CUSTOMER_ACTION_REQUIRED",), "banker": ("NEEDS_BANKER_REVIEW",),
              "all": ("CUSTOMER_ACTION_REQUIRED", "NEEDS_BANKER_REVIEW", "INFO")}[audience]
    items = [_finding_view(f) for f in repo.findings(case_id, status="open") if f["review_state"] in wanted]
    requests = [_request_view(q) for q in repo.customer_requests(case_id, status="OPEN")] if audience != "banker" else []
    if audience == "customer":
        spoken = ("אין כרגע פריטים שמחכים לכם." if not items and not requests else
                  " ".join([f"הבנקאית ביקשה: {q['title_he']}." for q in requests[:2]] + [i["title_he"] + "." for i in items[:3]]))
    else:
        spoken = f"{len(items)} פריטים ממתינים לבדיקת הבנקאי."
    return {"spoken_he": spoken, "audience": audience, "items": items, "banker_requests": requests, "notice": NOTICE,
            **_app_actions(case_id, ctx, lambda a: a.type != "VIEW_CASE_DETAILS")}


def get_upload_guidance(case_id: str, args: dict, ctx: dict) -> dict:
    borrowers = _borrowers(case_id)
    bid = args.get("borrower_id")
    if bid and bid not in borrowers:
        raise ToolError("הלווה אינו שייך לתיק")
    state = readiness.compute(case_id)
    targets = [r for r in state["requirements"] if r["evaluated_by_ai"] and (not bid or r["borrower_id"] in (None, bid))
               and r["ai_state"] not in ("extracted", "preparation_confirmed")]
    steps = ["פתחו את לשונית ״מסמכים״ באפליקציה.", "בכרטיס הדרישה המתאימה (תעודת זהות, תלוש שכר, דף עו״ש או אסמכתה) לחצו ״להעלאה״.",
             "עדיף PDF מקורי; אם מצלמים — צילום חד, ישר ומלא של כל העמוד.",
             "ודאו שבמסמך מודפסים השם ומספר הזהות, והתקופה הנכונה (חודש התלוש או תקופת דף החשבון).",
             "אחרי ההעלאה הבדיקה רצה מחדש על כל סט המסמכים."]
    need = [{"borrower": borrowers[r["borrower_id"]]["first_name_he"] if r.get("borrower_id") in borrowers else None,
             "requirement_code": r["code"], "title_he": r["title_he"], "hint_he": r.get("hint_he"),
             "missing_months": [det.month_label_he(m) for m in r.get("missing", [])]} for r in targets]
    uploads = _app_actions(case_id, ctx, lambda a: a.type in ("NAVIGATE_TO_DOCUMENT_UPLOAD", "VIEW_MISSING_DOCUMENTS")
                           and (not bid or a.params.get("borrower_id") in (None, bid)))
    return {"spoken_he": "אפשר להעלות דרך לשונית מסמכים, בכפתור להעלאה. עדיף קובץ PDF מקורי.", "steps_he": steps,
            "needed": need, "accepted_formats": ["PDF", "PNG", "JPEG"], "max_size_mb": 15, "app_route": "/customer/documents",
            **uploads}


def record_customer_statement(case_id: str, args: dict, ctx: dict) -> dict:
    if args.get("customer_confirmed") is not True:
        raise ToolError("נדרש אישור מפורש של הלקוח לפני תיעוד ההסבר")
    finding = repo.finding(args.get("finding_id", "")) if args.get("finding_id") else None
    if args.get("finding_id") and (not finding or finding["case_id"] != case_id):
        raise ToolError("אין ממצא כזה בתיק")
    text = (args.get("statement") or "").strip()
    if not text:
        raise ToolError("ההסבר ריק")
    request_id = args.get("request_id") or f"{ctx.get('turn_id', '')}:{stable_hash(text)}"
    st = repo.add_statement(case_id, finding["finding_id"] if finding else None, text[:1000], ctx.get("channel", "text"),
                            ctx.get("actor", "customer"), request_id)
    repo.audit(case_id, ctx.get("actor", "customer"), "customer_statement_recorded", st["statement_id"],
               {"finding_id": st["finding_id"], "channel": st["channel"]})
    answered = review_desk.link_statement(case_id, st)
    engine.request_case_review(case_id, "customer statement recorded", ctx.get("actor", "customer"))
    return {"statement_id": st["statement_id"], "attached_to": st["finding_id"],
            "answers_banker_request": answered["customer_request_id"] if answered else None,
            "spoken_he": "תיעדתי את ההסבר וצירפתי אותו לממצא. הוא מועבר לבנקאי ואינו סוגר את הממצא.",
            "effect": "attached_for_banker_review_only", "notice": NOTICE}


def request_banker_handoff(case_id: str, args: dict, ctx: dict) -> dict:
    if args.get("customer_confirmed") is not True:
        raise ToolError("נדרש אישור מפורש של הלקוח לפני העברה לבנקאי")
    request_id = args.get("request_id") or f"{ctx.get('turn_id', '')}:handoff"
    existing = repo.handoff_by_request(request_id)
    if existing:
        return {"package_id": existing["package_id"], "status": existing["status"], "spoken_he": "הבקשה כבר הועברה."}
    banker = bank.get_case(case_id)["banker"]["name_he"]
    queued = next((h for h in repo.handoffs(case_id)
                   if h["status"] == "IN_BANKER_QUEUE_DEMO" and not h.get("banker_decision")), None)
    if queued:
        return {"package_id": queued["package_id"], "status": queued["status"], "already_in_queue": True,
                "spoken_he": f"התיק כבר נמצא בתור של {banker} ולא נפתחה פנייה כפולה. היא תחזור אליכם.", "notice": NOTICE}
    from ..api.banker_package import build_package
    package = build_package(case_id)
    row = {"package_id": new_id("PKG"), "case_id": case_id, "status": "IN_BANKER_QUEUE_DEMO", "created_at": now_iso(),
           "created_by": ctx.get("actor", "customer"), "channel": ctx.get("channel", "text"),
           "note": (args.get("note") or "")[:500], "package": package, "request_id": request_id}
    repo.insert_handoff(row)
    repo.audit(case_id, ctx.get("actor", "customer"), "banker_handoff_created", row["package_id"],
               {"note": row["note"], "open_banker_items": len(package["findings_open_banker"])})
    return {"package_id": row["package_id"], "status": row["status"],
            "spoken_he": f"העברתי את התיק עם הממצאים והראיות ל{banker}. היא תחזור אליכם; זו אינה החלטה על ההלוואה.",
            "note": "נשמר בתור הבנקאי של ההדגמה — לא נשלח למערכות הבנק.", "notice": NOTICE}


def request_revalidation(case_id: str, args: dict, ctx: dict) -> dict:
    created = engine.request_case_review(case_id, f"requested via {ctx.get('channel', 'tool')}: {args.get('reason', '')}"[:200],
                                         ctx.get("actor", "customer"))
    return {"queued": created, "spoken_he": "הפעלתי בדיקה חוזרת של סט המסמכים." if created else "בדיקה חוזרת כבר ממתינה בתור."}


def get_review_history(case_id: str, args: dict, ctx: dict) -> dict:
    runs = repo.runs(case_id, args.get("document_id"))
    return {"runs": [{"run_id": r["run_id"], "scope": r["scope"], "document_id": r["document_id"], "status": r["status"],
                      "provider": r["provider"], "rubric": f"{r['rubric_id']}@{r['rubric_version']}",
                      "started_at": r["started_at"], "finished_at": r["finished_at"]} for r in runs[:20]]}


def explain_finding(case_id: str, args: dict, ctx: dict) -> dict:
    f = repo.finding(args.get("finding_id", ""))
    if not f or f["case_id"] != case_id:
        raise ToolError("אין ממצא כזה בתיק")
    st = [s["text"] for s in repo.statements(case_id) if s["finding_id"] == f["finding_id"]]
    related = _app_actions(case_id, ctx, lambda a: f["finding_id"] in a.params.get("finding_ids", []))
    return {"finding": _finding_view(f), "history": desk_state.customer_history(f["history"])[-5:], **related,
            "evidence": [{"document_id": e["document_id"], "field": e["field"], "page": e["page"], "quote": mask_ids(e.get("quote") or ""),
                          "verified_against_file": e["witness"] in ("text_layer_exact", "vision_reread_confirmed")}
                         for e in f["evidence"][:6]],
            "customer_statements_unverified": st, "notice": NOTICE}


def get_followup_context(case_id: str, args: dict, ctx: dict) -> dict:
    """The follow-up state the customer may see (no rule ids, attempts or banker text) and the open completion tasks."""
    from ..followup import orchestrator, tasks
    view = orchestrator.customer_view(case_id)
    return {**view, "open_tasks": [{"requirement_code": t["requirement_code"], "reason_code": t["reason_code"],
                                    "title_he": t["title_he"], "customer_text_he": t["customer_text_he"]}
                                   for t in tasks.open_for(case_id)],
            "notice": "מעקב השלמה מדומה (JEEN Talk בסימולציה): אין שיחה אמיתית. ההחלטות נקבעות בקוד, לא במודל."}


def offer_app_actions(case_id: str, args: dict, ctx: dict) -> dict:
    chosen, rejected = actions.choose(actions.available(case_id), list(args.get("action_ids") or [])[:8])
    if not chosen:
        ids = ", ".join(a.action_id for a in actions.available(case_id))
        raise ToolError(f"אף אחד מהמזהים אינו פעולה זמינה בתיק. מזהים זמינים: {ids}")
    return {"offered": [a.model_dump() for a in chosen], "rejected_ids": rejected,
            "note": "הכפתורים יוצגו ללקוח מתחת לתשובה. הם אינם מנווטים בלי לחיצה של הלקוח."}


# ---------------------------------------------------------------- registry
TOOLS: dict[str, dict[str, Any]] = {
    "get_case_overview": {"handler": get_case_overview, "write": False,
                          "description": "Current state of the customer's personal-loan application: the bank stage (demo data, not "
                                         "authoritative), the AI document-readiness state, every document requirement (ID, payslips with "
                                         "missing or duplicate months, bank statements, proof of purpose) and counts. "
                                         "Call this before answering any question about the case.",
                          "parameters": {"type": "object", "properties": {}}},
    "list_documents": {"handler": list_documents, "write": False,
                       "description": "Uploaded documents with their review status, document-review verdict, printed salary month "
                                      "and the month the file name claims.",
                       "parameters": {"type": "object", "properties": {"borrower_id": {"type": "string", "description": "Optional, e.g. BRW-A"}}}},
    "get_document_review": {"handler": get_document_review, "write": False,
                            "description": "The full review of one document: verdict, rubric criteria with outcomes and explanations, "
                                           "extracted facts and whether each was verified against the file, open findings.",
                            "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}}, "required": ["document_id"]}},
    "list_open_items": {"handler": list_open_items, "write": False,
                        "description": "Open findings: audience 'customer' for what the customer must do, 'banker' for items awaiting "
                                       "the banker, 'all' for everything including informational notes.",
                        "parameters": {"type": "object", "properties": {"audience": {"type": "string", "enum": ["customer", "banker", "all"]}}}},
    "get_upload_guidance": {"handler": get_upload_guidance, "write": False,
                            "description": "Exactly what to upload, for whom and how, with the months still missing.",
                            "parameters": {"type": "object", "properties": {"borrower_id": {"type": "string"}}}},
    "explain_finding": {"handler": explain_finding, "write": False,
                        "description": "One finding with its evidence (document, page, quote, verification) and history.",
                        "parameters": {"type": "object", "properties": {"finding_id": {"type": "string"}}, "required": ["finding_id"]}},
    "get_review_history": {"handler": get_review_history, "write": False,
                           "description": "Review run history (provider, rubric version, timestamps) for the case or one document.",
                           "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}}}},
    "get_followup_context": {"handler": get_followup_context, "write": False,
                             "description": "The completion follow-up for this case as the customer may see it: whether the bank is "
                                            "waiting for the customer, a reminder in the app, a scheduled simulated JEEN Talk call or "
                                            "nothing; the open completion tasks; snooze and contact preferences. Read-only.",
                             "parameters": {"type": "object", "properties": {}}},
    "record_customer_statement": {"handler": record_customer_statement, "write": True,
                                  "description": "Attach the customer's own explanation to a finding for the banker. Only after the "
                                                 "customer explicitly agreed it should be recorded. It never resolves a finding.",
                                  "parameters": {"type": "object", "properties": {
                                      "finding_id": {"type": "string"}, "statement": {"type": "string"},
                                      "customer_confirmed": {"type": "boolean", "description": "true only if the customer explicitly agreed"}},
                                      "required": ["statement", "customer_confirmed"]}},
    "request_banker_handoff": {"handler": request_banker_handoff, "write": True,
                               "description": "Send the case with its findings and evidence to the human banker. Only after the "
                                              "customer explicitly asked for it or agreed.",
                               "parameters": {"type": "object", "properties": {
                                   "note": {"type": "string"},
                                   "customer_confirmed": {"type": "boolean", "description": "true only if the customer explicitly agreed"}},
                                   "required": ["customer_confirmed"]}},
    "request_revalidation": {"handler": request_revalidation, "write": True,
                             "description": "Queue a fresh review of the whole document set (idempotent).",
                             "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}}},
    "offer_app_actions": {"handler": offer_app_actions, "write": False, "channels": APP_CHANNELS,
                          "description": "Show the customer tappable buttons under your reply that open the right place in the Tefahot "
                                         "app: an upload for a requirement (ID, payslip, bank statement, proof of purpose) with the person, document type "
                                         "and month preselected, "
                                         "the list of missing documents, a document's review with its evidence, and similar. Pass only "
                                         "action_id values from app_actions returned by the other tools in this turn; the server rejects "
                                         "anything else. Offer the 1-3 actions that match your answer. The app never navigates by itself: "
                                         "the customer taps the button.",
                          "parameters": {"type": "object", "properties": {
                              "action_ids": {"type": "array", "items": {"type": "string"},
                                             "description": "action_id values taken from app_actions"}},
                              "required": ["action_ids"]}},
}


def on_channel(name: str, channel: str) -> bool:
    spec = TOOLS.get(name)
    return bool(spec) and channel in spec.get("channels", (channel,))


def call(name: str, case_id: str, args: Optional[dict], ctx: dict) -> dict:
    spec = TOOLS.get(name)
    if not spec:
        raise ToolError(f"unknown tool {name}")
    if not on_channel(name, ctx.get("channel", "")):
        raise ToolError(f"{name} is not available on this channel")
    handler: Callable = spec["handler"]
    result = handler(case_id, args or {}, ctx)
    repo.audit(case_id, ctx.get("actor", "agent"), "tool_call", name,
               {"channel": ctx.get("channel"), "args": {k: v for k, v in (args or {}).items() if k != "statement"},
                "write": spec["write"]}, trace_id=ctx.get("trace_id", ""))
    return result


def gemini_declarations() -> list[dict]:
    def conv(schema: dict) -> dict:
        out = {"type": schema["type"].upper()}
        if "description" in schema:
            out["description"] = schema["description"]
        if "enum" in schema:
            out["enum"] = schema["enum"]
        if "items" in schema:
            out["items"] = conv(schema["items"])
        if schema["type"] == "object":
            out["properties"] = {k: conv(v) for k, v in schema.get("properties", {}).items()}
            if schema.get("required"):
                out["required"] = schema["required"]
        return out
    decls = []
    for name, spec in TOOLS.items():
        d = {"name": name, "description": spec["description"]}
        if spec["parameters"].get("properties"):
            d["parameters"] = conv(spec["parameters"])
        decls.append(d)
    return decls
