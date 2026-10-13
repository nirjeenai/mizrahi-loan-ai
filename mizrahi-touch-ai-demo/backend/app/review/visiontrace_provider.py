"""VisionTraceReviewProvider — the FUTURE full review engine behind the same contract.

Not active. It becomes selectable (REVIEW_PROVIDER=visiontrace) only after a real
mortgage review has run end to end through VisionTrace and its findings were verified.
Listing workflows over MCP is NOT document-review integration.

Integration plan, from VisionTrace main 5a1ca7d (11.10.2026):
  start      — a review starts when a person submits files: MCP `visiontrace_open_intake`
               (scope intake:write; today its workflow enum is fire / protected_spaces only)
               returns a 30-minute upload link; the upload is relayed with explicit consent.
  status     — MCP `visiontrace_intake_status` (intake:read) → state + review reference.
  result     — MCP read tools are voice-shaped summaries without boxes, so the full result
               needs the review envelope (REST with service access, or an evidence-bearing
               MCP tool to be added): screening.cases[].checks[] + documents[].facts.
  mapping    — map_envelope() below translates that envelope into DocumentReviewResult.
"""
from __future__ import annotations

from typing import Any

import httpx

from ..config import settings
from .contract import (CaseReviewRequest, CaseReviewResult, CriterionOutcome, DocumentReviewRequest,
                       DocumentReviewResult, EvidenceRef, ExtractedFact, ProgressFn, ProviderIdentity,
                       ProviderNotEnabled, ReviewHandle, ReviewStatus)

USER_AGENT = "mizrahi-touch-jeen-demo/0.1 (mcp client)"      # Cloudflare rejects library-default agents
STATUS_MAP = {"pass": "PASS", "review": "FAIL", "insufficient": "NEEDS_REVIEW", "not_applicable": "NOT_APPLICABLE"}


class VisionTraceReviewProvider:
    name = "visiontrace"

    def identity(self) -> ProviderIdentity:
        return ProviderIdentity(provider=self.name, mode="STUB", prompt_version="visiontrace-mortgage/unreleased",
                                models={"engine": "VisionTrace mortgage workflow (not yet available)"})

    def readiness(self) -> dict[str, Any]:
        missing = []
        if not settings.visiontrace_mcp_url:
            missing.append("VISIONTRACE_MCP_URL")
        if not settings.visiontrace_mcp_key:
            missing.append("VISIONTRACE_MCP_KEY")
        missing.append("VisionTrace mortgage review workflow (in development)")
        missing.append("evidence-bearing review result access (REST service access or new MCP tool)")
        return {"provider": self.name, "state": "BLOCKED", "missing": missing}

    def probe_mcp(self) -> dict[str, Any]:
        """Read-only connectivity check: initialize + tools/list. Never opens an intake."""
        if not (settings.visiontrace_mcp_url and settings.visiontrace_mcp_key):
            return {"state": "BLOCKED", "detail": "no VisionTrace MCP key configured"}
        headers = {"Authorization": f"Bearer {settings.visiontrace_mcp_key}", "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18",
                   "User-Agent": USER_AGENT}
        try:
            init = httpx.post(settings.visiontrace_mcp_url, headers=headers, timeout=20, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "mizrahi-touch-demo", "version": "0.1"}}})
            if init.status_code != 200:
                return {"state": "BLOCKED", "detail": f"initialize → HTTP {init.status_code}: {init.text[:160]}"}
            tools = httpx.post(settings.visiontrace_mcp_url, headers=headers, timeout=20,
                               json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            names = [t["name"] for t in tools.json().get("result", {}).get("tools", [])]
            return {"state": "CONNECTED_READ_ONLY", "tools": names,
                    "detail": "MCP reachable. This is not a document-review integration."}
        except httpx.HTTPError as exc:
            return {"state": "BLOCKED", "detail": f"{type(exc).__name__}: {exc}"}

    def start_document_review(self, req: DocumentReviewRequest, progress: ProgressFn) -> ReviewHandle:
        raise ProviderNotEnabled("VisionTrace mortgage review workflow is not available yet")

    def get_status(self, handle: ReviewHandle) -> ReviewStatus:
        raise ProviderNotEnabled("VisionTrace provider is not enabled")

    def get_document_result(self, handle: ReviewHandle) -> DocumentReviewResult:
        raise ProviderNotEnabled("VisionTrace provider is not enabled")

    def review_case(self, req: CaseReviewRequest, progress: ProgressFn) -> CaseReviewResult:
        raise ProviderNotEnabled("VisionTrace provider is not enabled")

    # ------------------------------------------------------------------ mapping (untested until a real review exists)
    @staticmethod
    def map_envelope(envelope: dict, *, document_id: str, run_id: str, rubric: dict, started_at: str,
                     finished_at: str) -> DocumentReviewResult:
        """VisionTrace review envelope → the shared contract. Ledger check status maps to criterion
        outcome (pass→PASS, review→FAIL, insufficient→NEEDS_REVIEW); facts keep VisionTrace's own
        exact evidence boxes (field_sources) and are text-layer witnessed by its grounding gate."""
        doc = (envelope.get("documents") or [{}])[0]
        facts = []
        for f in doc.get("facts") or []:
            src = (doc.get("field_sources") or {}).get(f["concept"], {})
            ref = EvidenceRef(evidence_id=f"{document_id}:{f['concept']}", document_id=document_id, field=f["concept"],
                              page=int(src.get("page", 1)), quote=f.get("quote"), bbox=src.get("bbox"),
                              coord_space="pdf_points", witness="text_layer_exact" if src else "unavailable")
            facts.append(ExtractedFact(field=f["concept"], label_he=f["concept"], value_raw=f.get("value"),
                                       value_normalized=f.get("typed"), evidence=ref))
        checks = [c for case in (envelope.get("screening") or {}).get("cases", []) for c in case.get("checks", [])]
        criteria = [CriterionOutcome(criterion_id=c["id"], title_he=c.get("label", c["id"]), method="hybrid",
                                     outcome=STATUS_MAP.get(c.get("status"), "NEEDS_REVIEW"), severity="major",
                                     reason_code=c.get("id"), explanation_he=c.get("summary_he") or c.get("detail") or "",
                                     decided_by="code+judge") for c in checks]
        verdict_raw = (envelope.get("verdict") or {}).get("severity")
        verdict = "VALID" if verdict_raw == "ok" else "NEEDS_REVIEW"
        return DocumentReviewResult(
            run_id=run_id, document_id=document_id, identity=VisionTraceReviewProvider().identity(),
            rubric_id=rubric["rubric_id"], rubric_version=rubric["version"], started_at=started_at,
            finished_at=finished_at, doc_type=doc.get("doc_type", "other"), doc_type_he=doc.get("doc_type_he", ""),
            is_scanned=not doc.get("has_text", True), pages=1, legibility="unknown", facts=facts, criteria=criteria,
            verdict=verdict, verdict_reason_codes=[c.reason_code for c in criteria if c.outcome != "PASS" and c.reason_code],
            summary_he=(envelope.get("verdict") or {}).get("headline_he", ""), limitations_he=[], uncertainty_he=[],
            security_flags=[])
