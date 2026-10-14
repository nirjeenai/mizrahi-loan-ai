"""GeminiReviewProvider — the ACTIVE full review pipeline.

Document review:  A intake + classification · B multimodal extraction (PDF or image,
scans included) · evidence verification against the original file · C deterministic
checks · E LLM-as-a-Judge over a versioned rubric · verdict by rubric policy (code).
Case review lives in case_review.py (deterministic coverage + D semantic review +
the case rubric)."""
from __future__ import annotations

import copy
import json
from datetime import date
from typing import Any, Optional

from ..config import settings
from ..llm import gemini as g
from ..util import now_iso
from . import case_review
from . import deterministic as det
from . import evidence as ev
from . import family_checks
from . import prompts as P
from .contract import (CaseReviewRequest, CaseReviewResult, CriterionOutcome, DocumentReviewRequest,
                       DocumentReviewResult, EvidenceRef, ExtractedFact, ProgressFn, ProviderIdentity,
                       ReviewHandle, ReviewStatus)

REREAD_FIELDS = ("employee_name", "employee_id", "salary_period", "gross_pay", "net_pay", "employer_name",
                 "total_deductions", "payment_date", "holder_name", "holder_id", "statement_from", "statement_to",
                 "issuer_name", "total_amount", "issue_date", "expiry_date", "tax_year")


class Usage:
    def __init__(self) -> None:
        self.calls = 0
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.thought_tokens = 0

    def add(self, data: dict) -> None:
        u = g.usage_of(data)
        self.calls += 1
        self.prompt_tokens += u["prompt_tokens"] or 0
        self.output_tokens += u["output_tokens"] or 0
        self.thought_tokens += u["thought_tokens"] or 0

    def as_dict(self) -> dict:
        return {"llm_calls": self.calls, "prompt_tokens": self.prompt_tokens, "output_tokens": self.output_tokens,
                "thought_tokens": self.thought_tokens}


def _normalize(name: str, f: dict) -> Any:
    raw, norm = f.get("value"), f.get("normalized")
    if name == "salary_period":
        return det.parse_month(norm) or det.parse_month(raw)
    if name in P.MONEY_FIELDS:
        value = det.parse_amount(norm)
        return value if value is not None else det.parse_amount(raw)
    if name in P.DATE_FIELDS:
        day = det.parse_day(norm) or det.parse_day(raw)
        return day.isoformat() if day else None
    if name == "tax_year":
        found = [d for d in (det.digits(norm), det.digits(raw)) if len(d) == 4 and 1990 <= int(d) <= 2100]
        return found[0] if found else None
    return (raw or "").strip() or None


class GeminiReviewProvider:
    name = "gemini"

    def __init__(self) -> None:
        self._results: dict[str, DocumentReviewResult] = {}

    # ------------------------------------------------------------------ identity
    def identity(self) -> ProviderIdentity:
        return ProviderIdentity(provider=self.name, mode="LIVE", prompt_version=P.PROMPT_VERSION,
                                models={"extract": settings.model_extract, "evidence_reread": settings.model_extract,
                                        "judge": settings.model_judge, "semantic": settings.model_judge})

    def readiness(self) -> dict[str, Any]:
        return {"provider": self.name, "configured": bool(settings.gemini_api_key),
                "state": "LIVE" if settings.gemini_api_key else "BLOCKED", "models": self.identity().models}

    # ------------------------------------------------------------------ lifecycle
    def start_document_review(self, req: DocumentReviewRequest, progress: ProgressFn) -> ReviewHandle:
        self._results[req.run_id] = self._review_document(req, progress)
        return ReviewHandle(provider=self.name, run_id=req.run_id)

    def get_status(self, handle: ReviewHandle) -> ReviewStatus:
        return ReviewStatus(state="succeeded" if handle.run_id in self._results else "failed")

    def get_document_result(self, handle: ReviewHandle) -> DocumentReviewResult:
        return self._results.pop(handle.run_id)

    def review_case(self, req: CaseReviewRequest, progress: ProgressFn) -> CaseReviewResult:
        return case_review.run(self.identity(), req, progress)

    # ------------------------------------------------------------------ document review
    def _review_document(self, req: DocumentReviewRequest, progress: ProgressFn) -> DocumentReviewResult:
        started = now_iso()
        usage = Usage()
        rubric = req.rubric
        spec = {c["id"]: c for c in rubric["criteria"]}
        progress("intake")
        info = ev.inspect(req.storage_path, req.mime)
        scanned = info["is_image"] or info["text_layer_chars"] < 40
        raw = ev.file_bytes(req.storage_path)
        model_mime = req.mime if req.mime in ev.IMAGE_MIMES else "application/pdf"

        # ---- Stage A + B: classification and multimodal extraction (blind to the assigned borrower)
        progress("extract")
        data = g.generate(settings.model_extract,
                          [{"role": "user", "parts": [g.text_part(P.EXTRACTION_USER), g.inline_part(raw, model_mime)]}],
                          purpose="extract", run_id=req.run_id, system=P.EXTRACTION_SYSTEM,
                          schema=P.EXTRACTION_SCHEMA, thinking="low")
        usage.add(data)
        ext = g.response_json(data)
        fields: dict[str, dict] = {}
        for f in ext.get("fields") or []:
            name = f.get("name")
            if name in P.FIELDS and f.get("value") not in (None, ""):
                if name not in fields or (f.get("confidence") or 0) > (fields[name].get("confidence") or 0):
                    fields[name] = f

        # ---- evidence verification against the original file
        progress("verify_evidence")
        facts = self._verify(req, info, scanned, fields, usage)

        # ---- Stage C: deterministic checks
        progress("deterministic_checks")
        checks = self._deterministic(req, info, scanned, ext, facts)

        # ---- Stage E: LLM-as-a-Judge over the versioned rubric
        progress("judge")
        judged = self._judge(req, raw, model_mime, ext, facts, checks, usage)

        criteria = self._merge(rubric, spec, ext, facts, checks, judged)
        invalid = any(c.outcome == "FAIL" and spec[c.criterion_id].get("on_fail") == "INVALID" for c in criteria)
        needs = any(c.outcome in ("FAIL", "NEEDS_REVIEW") for c in criteria)
        verdict = "INVALID" if invalid else "NEEDS_REVIEW" if needs else "VALID"
        reasons = sorted({c.reason_code for c in criteria if c.outcome in ("FAIL", "NEEDS_REVIEW") and c.reason_code})

        limitations = list(judged.get("limitations_he") or [])
        if scanned:
            limitations.insert(0, "המסמך סרוק ואין בו שכבת טקסט — כל ערך מכריע אומת בקריאה חוזרת עצמאית של אזור הערך בתמונה.")
        limitations.append("תוצאת בדיקת מסמך בלבד — אינה קבלת המסמך על ידי הבנק ואינה החלטת אשראי.")
        doc_type = ext.get("doc_type") or "other"
        if ext.get("legibility") == "unreadable":
            doc_type = "unreadable"
        return DocumentReviewResult(
            run_id=req.run_id, document_id=req.document_id, identity=self.identity(),
            rubric_id=rubric["rubric_id"], rubric_version=rubric["version"], started_at=started, finished_at=now_iso(),
            doc_type=doc_type, doc_type_he=P.DOC_TYPES_HE.get(doc_type, "מסמך"), is_scanned=scanned, pages=info["pages"],
            legibility=ext.get("legibility") or "unknown", matched_borrower_id=checks["matched_borrower_id"],
            period=checks["period"], file_name_period=checks["file_period"], facts=list(facts.values()),
            criteria=criteria, verdict=verdict, verdict_reason_codes=reasons,
            summary_he=(judged.get("summary_he") or "").strip(), limitations_he=limitations,
            uncertainty_he=list(judged.get("uncertainty_he") or []) + list(ext.get("uncertainties") or []),
            security_flags=checks["injection_hits"], demo_marked=bool(checks["demo_marked"]),
            payroll_lines={"earnings": ext.get("earnings") or [], "deductions": ext.get("deductions") or []},
            usage=usage.as_dict())

    def _verify(self, req: DocumentReviewRequest, info: dict, scanned: bool, fields: dict[str, dict],
                usage: Usage) -> dict[str, ExtractedFact]:
        facts: dict[str, ExtractedFact] = {}
        reread: list[tuple[str, int, list[int]]] = []
        for name, f in fields.items():
            page = min(max(1, int(f.get("page") or 1)), info["pages"])
            size = info["page_sizes"][page - 1]
            ref = EvidenceRef(evidence_id=f"{req.document_id}:{name}", document_id=req.document_id, field=name,
                              page=page, quote=f.get("quote") or f.get("value"))
            box = f.get("box_2d") if isinstance(f.get("box_2d"), list) and len(f.get("box_2d") or []) == 4 else None
            if not scanned:
                loc = ev.text_layer_locate(req.storage_path, page, f.get("value"), f.get("quote"))
                if loc:
                    ref.bbox, ref.page_size = loc["bbox"], loc["page_size"]
                    ref.witness = "text_layer_exact"
                    ref.witness_detail = f"מודפס בשכבת הטקסט של ה־PDF ({loc['occurrences']} מופעים בעמוד)"
                else:
                    ref.witness = "not_found"
                    ref.witness_detail = "שכבת הטקסט של ה־PDF אינה מדפיסה ערך זה — הערך לא אומת"
            else:
                if box:
                    ref.bbox, ref.page_size = ev.norm_box_to_page(box, size), size
                    if name in REREAD_FIELDS:
                        reread.append((name, page, box))
                ref.witness = "vision_unverified"
                ref.witness_detail = "עמוד סרוק — טרם אומת בקריאה חוזרת"
            facts[name] = ExtractedFact(field=name, label_he=P.FIELD_LABELS_HE[name], value_raw=f.get("value"),
                                        value_normalized=_normalize(name, f), confidence=f.get("confidence"),
                                        evidence=ref)
        if scanned and reread:
            crops = []
            for name, page, box in reread:
                png = ev.crop_for_reread(req.document_id, req.storage_path, req.mime, page, box)
                if png:
                    crops.append((name, png))
            if crops:
                parts = [g.text_part(P.REREAD_PROMPT)]
                for i, (_, png) in enumerate(crops):
                    parts += [g.text_part(f"crop {i}:"), g.inline_part(png, "image/png")]
                data = g.generate(settings.model_extract, [{"role": "user", "parts": parts}], purpose="evidence_reread",
                                  run_id=req.run_id, schema=P.REREAD_SCHEMA, thinking="low")
                usage.add(data)
                reads = {c.get("index"): c for c in (g.response_json(data).get("crops") or [])}
                for i, (name, _) in enumerate(crops):
                    r = reads.get(i) or {}
                    ref = facts[name].evidence
                    if r.get("legible") and ev.values_agree(name, facts[name].value_raw, r.get("text")):
                        ref.witness = "vision_reread_confirmed"
                        ref.witness_detail = f"אומת בקריאה חוזרת עצמאית של אזור הערך: “{r.get('text')}”"
                    else:
                        ref.witness = "vision_unverified"
                        ref.witness_detail = f"הקריאה החוזרת לא אישרה את הערך (נקרא: “{r.get('text')}”)"
        return facts

    def _deterministic(self, req: DocumentReviewRequest, info: dict, scanned: bool, ext: dict,
                       facts: dict[str, ExtractedFact]) -> dict[str, Any]:
        rubric = req.rubric
        spec = {c["id"]: c for c in rubric["criteria"]}
        borrowers = {b["borrower_id"]: b for b in req.case_context["borrowers"]}
        assigned = borrowers.get(req.assigned_borrower_id or "")
        val = lambda n: facts[n].value_raw if n in facts else None
        norm = lambda n: facts[n].value_normalized if n in facts else None
        family = rubric.get("family", "payslip")
        if family != "payslip":
            return self._family_deterministic(family, req, scanned, ext, facts, borrowers, assigned, val, norm)
        # A payslip may print the identity number under an employee-identifier label ("מזהה עובד"), which the extractor
        # reads as employee_number. Only an exact, verified match with a case identity makes it the identity number.
        number = facts.get("employee_number")
        if "employee_id" not in facts and number and number.verified and any(
                str(number.value_raw or "").strip() == b["national_id"] for b in borrowers.values()):
            facts["employee_id"] = number.model_copy(update={
                "field": "employee_id", "label_he": "מספר זהות (מודפס כ״מזהה עובד״)",
                "evidence": number.evidence.model_copy(update={"evidence_id": f"{req.document_id}:employee_id",
                                                               "field": "employee_id"})})

        matched = None
        for b in borrowers.values():
            idr = det.id_relation(val("employee_id"), b["national_id"])
            nr = det.name_relation(val("employee_name"), b["name_he"])
            if idr == "same" or (idr == "unknown" and nr in ("same", "variant")):
                matched = b["borrower_id"]
                break
        id_rel = det.id_relation(val("employee_id"), assigned["national_id"]) if assigned else "unknown"
        name_rel = det.name_relation(val("employee_name"), assigned["name_he"]) if assigned else "unknown"

        period = norm("salary_period")
        tolerance = float(spec["PS-06"].get("tolerance_ils", 2.0))
        arith = det.arithmetic(norm("gross_pay"), norm("total_deductions"), norm("net_pay"), tolerance)
        earnings = [det.parse_amount(line.get("amount")) for line in ext.get("earnings") or []
                    if not det.is_total_label(line.get("label"))]
        if earnings and all(e is not None for e in earnings) and norm("gross_pay") is not None:
            total = round(sum(earnings), 2)
            if abs(total - norm("gross_pay")) > tolerance:
                arith = {"state": "fail", "detail": f"סכום שורות התשלומים {total:,.2f} שונה מהברוטו המודפס {norm('gross_pay'):,.2f}"}

        text_layer = self._text_layer(req, scanned)
        hits = det.injection_hits(text_layer)
        hits += [s.get("quote", "") for s in ext.get("suspicious_content") or [] if s.get("kind") == "instruction_to_ai"]
        decisive = rubric.get("decisive_fields", [])
        unverified = [n for n in decisive if n in facts and not facts[n].verified]
        legible_unreadable = ext.get("legibility") == "unreadable" or ext.get("doc_type") == "unreadable"

        demo = det.demo_marked(text_layer) or any(det.demo_marked(s.get("quote")) for s in ext.get("suspicious_content") or [])
        out: dict[str, Any] = {"scanned": scanned, "demo_marked": demo or scanned and "דמו" in (ext.get("doc_type_reason") or ""),
                               "matched_borrower_id": matched, "id_rel": id_rel, "name_rel": name_rel, "period": period,
                               "file_period": det.named_month(req.filename), "arith": arith, "injection_hits": hits,
                               "unverified": unverified, "unreadable": legible_unreadable, "outcomes": {}}
        o = out["outcomes"]
        o["PS-04"] = ("PASS", f"תקופת השכר: {det.month_label_he(period)}") if period else \
            ("FAIL", "תקופת השכר אינה מודפסת או אינה ניתנת לפענוח חד־משמעי")
        missing_money = [P.FIELD_LABELS_HE[n] for n in ("gross_pay", "net_pay") if norm(n) is None]
        o["PS-05"] = ("FAIL", "חסר במסמך: " + ", ".join(missing_money)) if missing_money else \
            ("PASS", f"ברוטו {norm('gross_pay'):,.2f} ₪ · נטו {norm('net_pay'):,.2f} ₪")
        o["PS-06"] = {"pass": "PASS", "fail": "FAIL", "unknown": "NEEDS_REVIEW"}[arith["state"]], arith["detail"]
        o["PS-07"] = ("PASS", f"מעסיק: {val('employer_name')}") if val("employer_name") else ("FAIL", "שם המעסיק אינו מזוהה")
        present_decisive = [n for n in decisive if n in facts]
        if not present_decisive:
            o["PS-09"] = ("FAIL", "לא חולצו שדות מכריעים שניתן לאמת")
        elif unverified:
            o["PS-09"] = ("FAIL", "לא אומתו מול הקובץ: " + ", ".join(P.FIELD_LABELS_HE[n] for n in unverified))
        else:
            o["PS-09"] = ("PASS", "כל השדות המכריעים אומתו מול הקובץ המקורי")
        if not assigned:
            o["PS-03"] = ("NEEDS_REVIEW", "המסמך לא שויך ללווה")
        elif id_rel == "different":
            other = borrowers.get(matched or "")
            o["PS-03"] = ("FAIL", f"מספר הזהות במסמך אינו של {assigned['name_he']}" +
                          (f" — המסמך מזוהה עם {other['name_he']}" if other and other is not assigned else ""))
        elif name_rel == "different" and id_rel != "same":
            o["PS-03"] = ("FAIL", f"שם העובד במסמך ({val('employee_name')}) אינו {assigned['name_he']}")
        elif id_rel == "same" and name_rel in ("same", "variant"):
            o["PS-03"] = ("PASS", f"שם ומספר זהות תואמים ל{assigned['name_he']}")
        else:
            o["PS-03"] = ("JUDGE", f"השוואת זהות לא חד־משמעית (שם: {name_rel}, ת״ז: {id_rel})")
        o["PS-08"] = ("FAIL", "נמצא במסמך טקסט המופנה למערכת או לבודק: " + hits[0][:140]) if hits else ("JUDGE", "")
        paid = facts.get("payment_date")
        o["PS-10"] = det.pay_date_check(period, val("payment_date"),
                                        date.fromisoformat(paid.value_normalized) if paid and paid.value_normalized else None,
                                        bool(paid and paid.verified), int(spec.get("PS-10", {}).get("payday_day_of_next_month", 9)))
        return out

    @staticmethod
    def _text_layer(req: DocumentReviewRequest, scanned: bool) -> str:
        if scanned:
            return ""
        import pymupdf
        doc = pymupdf.open(req.storage_path)
        try:
            return "\n".join(p.get_text() for p in doc)
        finally:
            doc.close()

    def _family_deterministic(self, family: str, req: DocumentReviewRequest, scanned: bool, ext: dict,
                              facts: dict[str, ExtractedFact], borrowers: dict, assigned: Optional[dict],
                              val: Any, norm: Any) -> dict[str, Any]:
        rubric = req.rubric
        text_layer = self._text_layer(req, scanned)
        hits = det.injection_hits(text_layer)
        hits += [s.get("quote", "") for s in ext.get("suspicious_content") or [] if s.get("kind") == "instruction_to_ai"]
        decisive = rubric.get("decisive_fields", [])
        unverified = [n for n in decisive if n in facts and not facts[n].verified]
        requirement = next((r for r in req.case_context.get("requirements") or []
                            if r.get("code") == req.requirement_code), {})
        matched = family_checks.match_holder(val("holder_name"), val("holder_id"), borrowers)
        outcomes = family_checks.outcomes(
            family, rubric, val=val, norm=norm, as_of=date.fromisoformat(req.case_context["simulation_date"]),
            borrowers=borrowers, assigned=assigned, matched=matched, hits=hits, unverified=unverified,
            present_decisive=[n for n in decisive if n in facts], rules=requirement.get("rules") or {},
            allowed_holders=requirement.get("holders") if family == "bank_statement" else None, labels=P.FIELD_LABELS_HE)
        demo = det.demo_marked(text_layer) or any(det.demo_marked(s.get("quote")) for s in ext.get("suspicious_content") or [])
        return {"scanned": scanned, "demo_marked": demo, "matched_borrower_id": matched, "id_rel": None, "name_rel": None,
                "period": None, "file_period": None, "arith": None, "injection_hits": hits, "unverified": unverified,
                "unreadable": ext.get("legibility") == "unreadable" or ext.get("doc_type") == "unreadable",
                "outcomes": outcomes}

    def _judge(self, req: DocumentReviewRequest, raw: bytes, model_mime: str, ext: dict,
               facts: dict[str, ExtractedFact], checks: dict, usage: Usage) -> dict:
        rubric = req.rubric
        assigned = next((b for b in req.case_context["borrowers"] if b["borrower_id"] == req.assigned_borrower_id), None)
        judge_specs = [c for c in rubric["criteria"] if c["method"] in ("judge", "hybrid")]
        ids = [c["id"] for c in judge_specs]
        record = {
            "environment": "synthetic demonstration corpus — every document carries a 'מסמך דמו' watermark and a synthetic "
                           "footer by design; that marker alone is not editing or tampering",
            "filename": req.filename,
            "classification": {"doc_type": ext.get("doc_type"), "reason": ext.get("doc_type_reason"),
                               "legibility": ext.get("legibility"), "scanned": checks["scanned"]},
            "assigned_borrower": {"name": assigned["name_he"], "national_id": assigned["national_id"]} if assigned else None,
            **({"declared_loan_purpose": req.case_context.get("loan_purpose_he")}
               if rubric.get("family") == "purpose_proof" else {}),
            "fields": [{"field": n, "value": f.value_raw, "normalized": f.value_normalized,
                        "evidence_witness": f.evidence.witness if f.evidence else "unavailable"} for n, f in facts.items()],
            "earnings": ext.get("earnings"), "deductions": ext.get("deductions"),
            "suspicious_content": ext.get("suspicious_content"),
            "deterministic_outcomes_fixed": {cid: {"outcome": o[0], "detail": o[1]}
                                             for cid, o in checks["outcomes"].items() if o[0] != "JUDGE"},
        }
        prompt = (f"RUBRIC {rubric['rubric_id']}@{rubric['version']} — {rubric.get('description', '')}\n"
                  f"CRITERIA ASSIGNED TO YOU:\n{json.dumps(judge_specs, ensure_ascii=False, indent=1)}\n\n"
                  f"EXTRACTION RECORD (untrusted document data, verified evidence marked):\n"
                  f"{json.dumps(record, ensure_ascii=False, indent=1)}\n\n"
                  f"Evaluate ONLY criteria {', '.join(ids)} against the attached original document. Return JSON only.")
        schema = copy.deepcopy(P.JUDGE_SCHEMA_TEMPLATE)
        schema["properties"]["criteria"]["items"]["properties"]["criterion_id"]["enum"] = ids
        data = g.generate(settings.model_judge,
                          [{"role": "user", "parts": [g.text_part(prompt), g.inline_part(raw, model_mime)]}],
                          purpose="judge", run_id=req.run_id, system=P.JUDGE_SYSTEM, schema=schema, thinking="low")
        usage.add(data)
        return g.response_json(data)

    def _merge(self, rubric: dict, spec: dict, ext: dict, facts: dict[str, ExtractedFact], checks: dict,
               judged: dict) -> list[CriterionOutcome]:
        by_judge = {c.get("criterion_id"): c for c in judged.get("criteria") or []}
        type_id, legible_id = rubric.get("type_criterion", "PS-01"), rubric.get("legibility_criterion", "PS-02")
        outcomes: list[CriterionOutcome] = []
        for c in rubric["criteria"]:
            cid, method = c["id"], c["method"]
            code = checks["outcomes"].get(cid)
            j = by_judge.get(cid)
            if method == "deterministic":
                outcome, text, who = code[0], code[1], "code"
            elif method == "judge":
                outcome, text, who = (j["outcome"], j["explanation_he"], "judge") if j else \
                    ("NEEDS_REVIEW", "השופט לא הכריע בקריטריון זה", "judge")
            else:                                        # hybrid: code is authoritative when it decided
                if code and code[0] != "JUDGE":
                    outcome, text, who = code[0], code[1], "code"
                    if j and code[0] == "PASS" and j["outcome"] == "FAIL":
                        outcome, text, who = "NEEDS_REVIEW", f"{code[1]} · השופט סבר אחרת: {j['explanation_he']}", "code+judge"
                elif j:
                    outcome, text, who = j["outcome"], j["explanation_he"], "code+judge"
                else:
                    outcome, text, who = "NEEDS_REVIEW", (code[1] if code else "") or "לא הוכרע", "code"
            if cid == legible_id and checks["unreadable"]:
                outcome, text, who = "FAIL", "המסמך אינו קריא — לא ניתן לזהות את השדות המכריעים", "code+judge"
            if cid == type_id and checks["unreadable"] and outcome == "FAIL":
                outcome, text, who = "NEEDS_REVIEW", "לא ניתן לקבוע את סוג המסמך כי אינו קריא", "code+judge"
            needed = [n for n in c.get("required_fields", []) if n in rubric.get("decisive_fields", [])]
            unverified = [n for n in needed if n not in facts or not facts[n].verified]
            reason = c.get("reason_code")
            if outcome == "PASS" and unverified:
                outcome = "NEEDS_REVIEW"
                # the doubt is about the evidence, not the criterion's own failure (e.g. not a borrower mismatch)
                reason = "EVIDENCE_UNVERIFIED"
                text = f"{text} · הראיה לא אומתה מול הקובץ המקורי: " + ", ".join(P.FIELD_LABELS_HE[n] for n in unverified)
            evidence_ids = [facts[n].evidence.evidence_id for n in c.get("required_fields", [])
                            if n in facts and facts[n].evidence and facts[n].verified]
            if j:
                evidence_ids += [facts[n].evidence.evidence_id for n in j.get("cited_fields") or []
                                 if n in facts and facts[n].evidence and facts[n].verified
                                 and facts[n].evidence.evidence_id not in evidence_ids]
            outcomes.append(CriterionOutcome(criterion_id=cid, title_he=c["title_he"], method=method, outcome=outcome,
                                             severity=c["severity"], reason_code=reason,
                                             explanation_he=text, evidence_ids=evidence_ids, decided_by=who,
                                             escalation=c.get("escalation")))
        return outcomes
