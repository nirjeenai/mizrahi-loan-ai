"""The document-review contract — the ONE boundary between the Mortgage Case Service
and any review engine (Gemini now, VisionTrace later).

A provider owns the whole review lifecycle of a document and of a case's evidence
set: intake and classification, extraction, evidence verification, rubric-based
judgement, a document-level verdict, cross-document consistency and re-review.
The case service owns bank-case state, the required-document inventory,
orchestration, audit and readiness aggregation. Bank staff own acceptance.

A verdict here is a DOCUMENT REVIEW verdict — never a credit decision.
"""
from __future__ import annotations

from typing import Any, Callable, Literal, Optional, Protocol

from pydantic import BaseModel, Field

Verdict = Literal["VALID", "INVALID", "NEEDS_REVIEW"]
Outcome = Literal["PASS", "FAIL", "NEEDS_REVIEW", "NOT_APPLICABLE"]
Witness = Literal["text_layer_exact", "vision_reread_confirmed", "vision_unverified", "not_found", "unavailable"]
ReviewState = Literal["CUSTOMER_ACTION_REQUIRED", "NEEDS_BANKER_REVIEW", "INFO"]


class EvidenceRef(BaseModel):
    evidence_id: str
    document_id: str
    field: str
    page: int
    quote: Optional[str] = None
    bbox: Optional[list[float]] = None                    # [x0, y0, x1, y1]
    coord_space: Literal["pdf_points", "page_norm_1000"] = "pdf_points"
    page_size: Optional[list[float]] = None               # [width, height] in the bbox space
    witness: Witness = "unavailable"
    witness_detail: Optional[str] = None


class ExtractedFact(BaseModel):
    field: str
    label_he: str
    value_raw: Optional[str] = None
    value_normalized: Optional[Any] = None
    confidence: Optional[float] = None
    evidence: Optional[EvidenceRef] = None

    @property
    def verified(self) -> bool:
        return bool(self.evidence and self.evidence.witness in ("text_layer_exact", "vision_reread_confirmed"))


class CriterionOutcome(BaseModel):
    criterion_id: str
    title_he: str
    method: Literal["deterministic", "judge", "hybrid"]
    outcome: Outcome
    severity: str
    reason_code: Optional[str] = None
    explanation_he: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    decided_by: Literal["code", "judge", "code+judge"] = "code"
    escalation: Optional[str] = None


class ProviderIdentity(BaseModel):
    provider: str
    mode: Literal["LIVE", "STUB"]
    models: dict[str, str] = Field(default_factory=dict)
    prompt_version: str


class DocumentReviewRequest(BaseModel):
    case_id: str
    document_id: str
    filename: str
    mime: str
    storage_path: str
    assigned_borrower_id: Optional[str] = None
    requirement_code: Optional[str] = None
    case_context: dict[str, Any]                          # borrowers, requested months, simulation date
    rubric: dict[str, Any]
    run_id: str


class DocumentReviewResult(BaseModel):
    run_id: str
    document_id: str
    identity: ProviderIdentity
    rubric_id: str
    rubric_version: str
    started_at: str
    finished_at: str
    doc_type: str
    doc_type_he: str
    is_scanned: bool
    pages: int
    legibility: str
    matched_borrower_id: Optional[str] = None
    period: Optional[str] = None
    file_name_period: Optional[str] = None
    facts: list[ExtractedFact]
    criteria: list[CriterionOutcome]
    verdict: Verdict
    verdict_reason_codes: list[str]
    summary_he: str
    limitations_he: list[str]
    uncertainty_he: list[str]
    security_flags: list[str]
    demo_marked: bool = False
    payroll_lines: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class CaseReviewRequest(BaseModel):
    case_id: str
    run_id: str
    case_context: dict[str, Any]
    documents: list[dict[str, Any]]                       # current document review results + document metadata
    statements: list[dict[str, Any]]                      # customer explanations — never evidence
    rubric: dict[str, Any]


class DesiredFinding(BaseModel):
    key: str                                              # stable identity: CODE:subject[:period]
    code: str
    severity: str
    review_state: ReviewState
    borrower_id: Optional[str] = None
    document_id: Optional[str] = None
    period: Optional[str] = None
    title_he: str
    message_he: str
    detail: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class CaseReviewResult(BaseModel):
    run_id: str
    case_id: str
    identity: ProviderIdentity
    rubric_id: str
    rubric_version: str
    started_at: str
    finished_at: str
    coverage: dict[str, Any]
    income: dict[str, Any]
    semantic: list[dict[str, Any]]
    criteria: list[CriterionOutcome]
    findings: list[DesiredFinding]
    limitations_he: list[str]
    usage: dict[str, Any] = Field(default_factory=dict)


ProgressFn = Callable[[str], None]


class ReviewHandle(BaseModel):
    provider: str
    run_id: str
    external_ref: Optional[str] = None                    # e.g. a VisionTrace intake id / review reference


class ReviewStatus(BaseModel):
    state: Literal["queued", "running", "succeeded", "failed"]
    stage: Optional[str] = None
    detail: Optional[str] = None


class ReviewProvider(Protocol):
    """Full review lifecycle. Synchronous providers finish inside start_*; asynchronous
    ones (VisionTrace intakes) return a handle the workflow polls with get_status."""

    name: str

    def identity(self) -> ProviderIdentity: ...

    def readiness(self) -> dict[str, Any]: ...

    def start_document_review(self, req: DocumentReviewRequest, progress: ProgressFn) -> ReviewHandle: ...

    def get_status(self, handle: ReviewHandle) -> ReviewStatus: ...

    def get_document_result(self, handle: ReviewHandle) -> DocumentReviewResult: ...

    def review_case(self, req: CaseReviewRequest, progress: ProgressFn) -> CaseReviewResult: ...


class ProviderNotEnabled(RuntimeError):
    pass
