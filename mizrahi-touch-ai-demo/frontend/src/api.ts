import { useCallback, useEffect, useRef, useState } from "react";

export const CASE_ID_DEFAULT = "DEMO-MTZ-2026-001";

export type Verdict = "VALID" | "INVALID" | "NEEDS_REVIEW";
export type Outcome = "PASS" | "FAIL" | "NEEDS_REVIEW" | "NOT_APPLICABLE";

export interface EvidenceRef {
  evidence_id: string; document_id: string; field: string; page: number; quote?: string | null;
  bbox?: number[] | null; coord_space: string; page_size?: number[] | null; witness: string; witness_detail?: string | null;
}
export interface Fact { field: string; label_he: string; value_raw?: string | null; value_normalized?: unknown; confidence?: number | null; evidence?: EvidenceRef | null }
export interface Criterion {
  criterion_id: string; title_he: string; method: string; outcome: Outcome; severity: string; reason_code?: string | null;
  explanation_he: string; evidence_ids: string[]; decided_by: string; escalation?: string | null;
}
export interface DocReview {
  run_id: string; document_id: string; identity: { provider: string; mode: string; models: Record<string, string>; prompt_version: string };
  rubric_id: string; rubric_version: string; started_at: string; finished_at: string; doc_type: string; doc_type_he: string;
  is_scanned: boolean; pages: number; legibility: string; matched_borrower_id?: string | null; period?: string | null;
  file_name_period?: string | null; facts: Fact[]; criteria: Criterion[]; verdict: Verdict; verdict_reason_codes: string[];
  summary_he: string; limitations_he: string[]; uncertainty_he: string[]; security_flags: string[]; demo_marked?: boolean;
  usage: Record<string, number>;
}
export interface DocView {
  document_id: string; case_id: string; borrower_id?: string | null; requirement_code?: string | null; filename: string; mime: string;
  bytes: number; pages: number; text_layer_chars: number; uploaded_at: string; channel?: string; status: string; stage?: string | null;
  stage_he?: string; error?: string | null; current_run?: { run_id: string; status: string; stage: string; started_at: string; finished_at?: string; provider: string } | null;
  review?: DocReview | null;
}
export interface Finding {
  finding_id: string; key: string; code: string; severity: string; review_state: "CUSTOMER_ACTION_REQUIRED" | "NEEDS_BANKER_REVIEW" | "INFO";
  status: "open" | "resolved" | "dismissed" | "superseded"; borrower_id?: string | null; document_id?: string | null; period?: string | null;
  title_he: string; message_he: string; detail: Record<string, any>; evidence: EvidenceRef[]; created_at: string; updated_at: string;
  resolution?: string | null; resolution_note?: string | null; history: { at: string; event: string; run_id?: string; note?: string; changes?: any }[];
}
/** Document families of the loan policy (backend/policy/seed/loan_policy.demo.json) */
export type Family = "payslip" | "id_document" | "bank_statement" | "purpose_proof" | "tax_form";
export interface Requirement {
  code: string; title_he: string; family: Family | string; family_he?: string; hint_he?: string; requirement_id?: string;
  borrower_id?: string | null; account_id?: string | null; holders?: string[]; evaluated_by_ai: boolean; bank_status: string;
  policy_version?: string; ai_state: string; ai_state_he: string; requested_months?: string[]; covered?: string[]; pending_review?: string[]; missing?: string[]; duplicates?: Record<string, number>;
  open_customer_actions?: number; open_banker_items?: number; open_customer_requests?: number;
  required?: number; verified_months?: string[]; in_review_months?: string[]; documents?: number; customer_status?: CustomerStatus;
  units_required?: number; units_verified?: number; document_ids?: string[];
  /** ai_review: a rubric checks the upload · human_review: no rubric — the upload is stored for the banker, never "valid by AI" */
  intake?: "ai_review" | "human_review"; owner_type?: "applicant" | "account" | "case" | "company"; owner_he?: string;
  why_he?: string; alternatives_he?: string[];
}
export const FAMILY_HE: Record<string, string> = { payslip: "תלוש שכר", id_document: "תעודת זהות", bank_statement: "דף עו״ש",
  purpose_proof: "אסמכתה למטרה", tax_form: "שומת מס / אישור רו״ח", business_registration: "אישור רישום עוסק",
  pnl_statement: "דוח רווח והפסד", company_registry: "נסח חברה", signatory_authority: "מורשי חתימה",
  financial_statements: "דוחות כספיים", business_bank_statement: "דפי עו״ש עסקי" };
/** The structured profile the document policy composed the checklist from (workflow/requirements.profile). */
export interface DocumentProfile {
  entity: "individual" | "company"; entity_he: string; purpose?: string; purpose_he?: string; banker_assisted: boolean;
  use_case?: string | null; profile_label_he?: string | null; disclaimer_he: string;
  company?: { name_he: string; company_number: string; signatory_he: string; signatory_role_he: string } | null;
  applicants: { borrower_id: string; name_he: string; role?: string; role_he: string; income_sources: string[];
    business_registration?: string | null; profile_he: string }[];
  accounts: { account_id: string; label_he: string; holders: string[]; other_holders_he: string[] }[];
}
export interface OnboardingOption { value: string | number; label_he: string }
export interface OnboardingQuestion { question_id: string; kind: "choice" | "multi" | "name" | "text" | "number"; prompt_he: string; options: OnboardingOption[] }
export interface OnboardingDraft {
  draft_id: string; status: "draft" | "confirmed"; case_id: string | null; note_he: string;
  asked: { question_id: string; prompt_he: string; kind: string; answer: unknown; answer_he: string }[];
  next: OnboardingQuestion | null;
  summary: null | { profile: DocumentProfile; policy_version: string; title_he: string; loan: LoanDetails;
    requirements: Pick<Requirement, "code" | "title_he" | "family" | "family_he" | "owner_he" | "owner_type" | "why_he" | "alternatives_he" | "intake" | "required">[] };
}
/** The customer's next step, computed by the backend (readiness.customer_status) with explicit precedence. */
export type CustomerStatus = "NO_PAYSLIPS_REQUIRED" | "AWAITING_UPLOAD" | "ERROR" | "PROCESSING" | "REVALIDATING"
  | "CORRECTION_REQUIRED" | "MISSING_DOCUMENTS" | "PREPARATION_CONFIRMED" | "BANKER_REVIEW" | "CHECKS_COMPLETE";
export interface Readiness {
  scope: string; state: string; state_he: string; requirements: Requirement[];
  customer_status?: CustomerStatus; case_review_failed?: boolean; case_status?: string;
  progress?: { done: number; total: number; missing_units: number; human_review_total?: number; human_review_received?: number };
  payslips?: { required: number; verified: number; requested_months: string[] };
  counts: { documents: number; reviewed: number; processing: number; failed: number; customer_actions: number; banker_items: number; payslip_requirements_ready: number; payslip_requirements_total: number;
    customer_requests?: number; documents_accepted?: number };
  pending_jobs: { kind: string; document_id?: string }[]; not_evaluated: string[]; banker_confirmation?: { confirmed_at: string } | null;
  /** requirements a profile change made inactive: their documents stay in the history, outside the evaluated set */
  inactive_requirements?: { code: string; family: string; family_he: string; document_ids: string[]; state_he: string }[];
}
export interface Borrower { borrower_id: string; name_he: string; first_name_he: string; national_id: string; employment: string; declared_net_monthly_ils: number; declaration_note_he: string; employer_declared_he: string; role?: string }
export interface LoanDetails { product: string; product_he: string; purpose: string; purpose_he: string; requested_amount_ils: number; payments: number; note_he?: string }
export interface BankCase {
  case_id: string; display_number: string; title_he: string; requested_loan_ils: number; submitted_at: string;
  preliminary_decision?: { label_he: string; issued_on: string; valid_until: string; amount_ils: number } | null;
  loan: LoanDetails; accounts?: { account_id: string; label_he: string; bank_he: string; holders: string[] }[];
  contact?: { consent_voice: boolean; consent_message: boolean; phone_masked?: string };
  banker: { name_he: string; role_he: string; staff_id?: string };
  meeting?: { date: string; from: string; to: string; type_he: string } | null; borrowers: Borrower[];
  persona_id?: string | null; use_case?: string | null; applicant_type?: "individual" | "company"; banker_assisted?: boolean;
  profile_changed_at?: string | null;
  document_profile?: DocumentProfile;
  bank_stage: { index: number; of: number; label_he: string; source: string; authoritative: boolean; label_observed_in_screenshot: boolean };
}
export interface AuditEvent { event_id: number; at: string; actor: string; action: string; target?: string; detail?: any }
/** app_action.v1 — derived and validated by the Loan Case Service; the model only picks among them by id. */
interface ActionBase { contract: "app_action.v1"; action_id: string; case_id: string; label_he: string; detail_he?: string | null; priority: number }
export type DocumentType = "PAYSLIP" | "ID_CARD" | "BANK_STATEMENT" | "PURPOSE_PROOF" | "TAX_FORM";
export type AppAction = ActionBase & (
  | { type: "NAVIGATE_TO_DOCUMENT_UPLOAD"; params: { borrower_id: string | null; requirement_code: string; document_type: DocumentType; period: string | null; missing_periods: string[]; finding_ids: string[] } }
  | { type: "VIEW_DOCUMENT_REVIEW"; params: { document_id: string; finding_ids: string[] } }
  | { type: "CONTACT_BANKER"; params: { message_he: string; finding_ids: string[] } }
  | { type: "VIEW_MISSING_DOCUMENTS" | "VIEW_REVIEW_STATUS" | "VIEW_CASE_DETAILS"; params: Record<string, never> }
);
export interface UploadOutcome {
  document_id: string; filename: string; borrower_id?: string | null; status: string; expected_period?: string | null;
  phase: "reviewing_document" | "rechecking_case" | "complete"; message_he: string; verdict?: Verdict | null; printed_period?: string | null;
  findings: { finding_id: string; code: string; review_state: string; title_he: string; message_he: string; document_id?: string | null }[];
  actions: AppAction[];
}
export class ActionRefusal extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
/** A banker's in-app request to the customer, as the customer app may show it (no internal rationale). */
export interface CustomerRequest {
  customer_request_id: string; kind: "correction" | "missing_document" | "additional_document" | "explanation"; borrower_id?: string | null;
  requirement_code?: string | null; period?: string | null; document_id?: string | null; document_filename?: string | null;
  title_he: string; message_he: string; status: "OPEN" | "RESPONDED"; created_at: string; created_by_name?: string | null;
  responded_document_id?: string | null; responded_filename?: string | null; responded_at?: string | null;
  responded_text?: string | null; can_reply?: boolean;
}
export interface Snapshot {
  case: BankCase; stage_dictionary: { stages: { index: number; label_he: string; observed: boolean }[]; note_he: string };
  readiness: Readiness; available_actions?: AppAction[];
  findings: Finding[]; statements: { statement_id: string; finding_id?: string; text: string; channel: string; created_at: string }[];
  case_review?: { run_id: string; finished_at: string; coverage: any; income: Record<string, any>; semantic: any[]; criteria: Criterion[]; limitations_he: string[]; rubric_id: string; rubric_version: string } | null;
  handoffs: any[]; updates: AuditEvent[]; provider: { provider: string; mode: string; models: Record<string, string>; prompt_version: string };
  customer_requests?: CustomerRequest[];
  document_status?: Record<string, { status: string; status_he: string; replaced_by?: string | null; replaces?: string | null }>;
  /** PASS / REVIEW / BLOCKER, derived by the service on every read (workflow/outcomes.py) — never stored, never a credit decision */
  outcomes?: { documents: Record<string, RoutedOutcome>; borrowers: Record<string, RoutedOutcome>; requirements?: Record<string, RoutedOutcome> };
}
export type RouteKey = "PASS" | "ACCEPTED" | "REVIEW" | "BLOCKER" | "IN_PROGRESS" | "NOT_COMPLETED" | "REPLACED" | "INCOMPLETE"
  | "AWAITING_UPLOAD" | "CONFIRMED" | "HUMAN_REVIEW_PENDING";
export interface RoutedOutcome { outcome: RouteKey; label_he: string; by?: "ai" | "banker" }
export interface Turn { turn_id: string; channel: string; role: "user" | "assistant"; text: string; provenance?: any; tool_calls?: { name: string; args: any; ok: boolean }[] | null; actions?: AppAction[]; created_at: string }

/** A request the service refused because nobody is signed in (401) or the signed-in user may not see it (403). */
export class AccessError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
/** Fired on every 401 so the app can show its sign-in screen; the session cookie is HttpOnly, so this is the only signal. */
export const AUTH_EVENT = "mz-auth-required";

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin", ...init });
  if (!res.ok) {
    let detail = `${res.status}`;
    try { const body = await res.json(); detail = body.detail || JSON.stringify(body); } catch { /* not json */ }
    if (res.status === 401) window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: { path } }));
    if (res.status === 401 || res.status === 403) throw new AccessError(res.status, detail);
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export interface SessionCase {
  case_id: string; display_number: string; title_he: string;
  /** the demonstrated customer ("התיקים שלי" lists one persona's cases); QA cases have none */
  persona_id?: string | null; qa?: boolean; use_case?: string | null; applicants_he?: string[]; company_he?: string | null;
}
export interface ApplicationOptions {
  product_he: string; policy_version: string; purposes: { id: string; label_he: string; proof_he: string }[];
  amount: { min: number; max: number }; payments: { min: number; max: number }; note_he: string;
}
/** The server sessions this browser holds (HttpOnly cookies). In demo mode they are obtained without a login. */
export interface Session {
  customer: { cases: SessionCase[]; expires_at: number } | null;
  staff: { staff_id: string; name_he: string; role_he: string; exp: number } | null;
  demo_identity: boolean;
}

export const api = {
  session: () => http<Session>(`/api/session`),
  /** demo mode: the case selector's list (number and title only) and the sessions the app obtains without a login */
  demoCases: () => http<SessionCase[]>(`/api/session/demo/cases`),
  demoCustomer: (caseId: string) => http<{ cases: SessionCase[] }>(`/api/session/demo/customer`, json({ case_id: caseId })),
  demoStaff: () => http<{ staff: { staff_id: string; name_he: string } }>(`/api/session/demo/staff`, json({})),
  snapshot: (caseId: string) => http<Snapshot>(`/api/cases/${caseId}`),
  documents: (caseId: string) => http<DocView[]>(`/api/cases/${caseId}/documents`),
  document: (docId: string) => http<DocView & { runs: any[]; findings: Finding[]; banker_status?: { status: string; status_he: string } | null;
    outcome?: RoutedOutcome | null }>(`/api/documents/${docId}`),
  conversation: (caseId: string) => http<Turn[]>(`/api/cases/${caseId}/conversation`),
  cases: () => http<{ case_id: string; display_number: string; title_he: string; borrowers: string[]; readiness: string }[]>(`/api/cases`),
  upload: (caseId: string, file: File, borrowerId: string | null | undefined,
    intent: { requirementCode?: string; expectedPeriod?: string | null; actionId?: string; originTurnId?: string; customerRequestId?: string;
      replacesDocumentId?: string } = {}) => {
    const body = new FormData();
    body.append("file", file);
    if (borrowerId) body.append("borrower_id", borrowerId);
    if (intent.requirementCode) body.append("requirement_code", intent.requirementCode);
    if (intent.expectedPeriod) body.append("expected_period", intent.expectedPeriod);
    if (intent.actionId) body.append("action_id", intent.actionId);
    if (intent.originTurnId) body.append("origin_turn_id", intent.originTurnId);
    if (intent.customerRequestId) body.append("customer_request_id", intent.customerRequestId);
    if (intent.replacesDocumentId) body.append("replaces_document_id", intent.replacesDocumentId);
    return http<{ document: DocView; created: boolean; note?: string; answered_request?: string | null; replaces?: string | null }>(
      `/api/cases/${caseId}/documents`, { method: "POST", body });
  },
  resolveAction: async (caseId: string, actionId: string, turnId?: string): Promise<AppAction> => {
    const res = await fetch(`/api/cases/${caseId}/actions/resolve`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action_id: actionId, turn_id: turnId }) });
    const body = await res.json().catch(() => ({}));
    if (res.ok && body.action) return body.action as AppAction;
    if (res.status === 401) window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: { path: "actions/resolve" } }));
    if ([403, 404, 409].includes(res.status) && typeof body.detail === "string") throw new ActionRefusal(res.status, body.detail);
    throw new Error(`resolve failed (${res.status})`);
  },
  uploadOutcome: (caseId: string, docId: string) => http<UploadOutcome>(`/api/cases/${caseId}/documents/${docId}/outcome`),
  retry: (docId: string) => http(`/api/documents/${docId}/retry`, { method: "POST" }),
  revalidate: (caseId: string) => http<{ queued: boolean }>(`/api/cases/${caseId}/revalidate`, { method: "POST" }),
  send: (caseId: string, text: string, channel: "text" | "voice", provenance?: any) =>
    http<{ reply: string; turn_id: string; tool_calls: { name: string; ok: boolean }[]; guard: any; fallback: boolean }>(
      `/api/cases/${caseId}/agent/messages`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, channel, provenance }) }),
  transcribe: (audio: Blob) => {
    const body = new FormData();
    body.append("audio", audio, audio.type.includes("wav") ? "speech.wav" : "speech.webm");
    return http<{ text: string; engine: string; latency_ms: number }>(`/api/voice/transcribe`, { method: "POST", body });
  },
  reset: (caseId: string) => http(`/api/cases/${caseId}/reset`, { method: "POST" }),
  /** presenter: wipe the executive demo cases 006–008 only; 409 while a review is still running in one of them */
  demoReset: () => http<{ reset: string[]; deleted: Record<string, number> }>(`/api/presenter/demo-reset`, { method: "POST" }),
  integrations: () => http<any>(`/api/system/integrations`),
  rubrics: () => http<any[]>(`/api/system/rubrics`),
  mcpSelftest: () => http<any>(`/api/system/mcp-selftest`, { method: "POST" }),
  bankerCases: () => http<BankerCaseRow[]>(`/api/banker/cases`),
  bankerPackage: (caseId: string) => http<any>(`/api/banker/cases/${caseId}/package`),
  bankerWorkspace: (caseId: string) => http<Workspace>(`/api/banker/cases/${caseId}/workspace`),
  bankerConversation: (caseId: string) => http<Turn[]>(`/api/banker/cases/${caseId}/conversation`),
  decideDocument: (caseId: string, docId: string, body: {
    action: "accept" | "request_correction" | "escalate"; rationale?: string; customer_message?: string; requested_period?: string | null;
    acknowledged_finding_ids?: string[]; request_id: string }) =>
    http<DeskResult>(`/api/banker/cases/${caseId}/documents/${docId}/decision`, json(body)),
  requestMissing: (caseId: string, body: { borrower_id: string; period: string; customer_message: string; rationale?: string; request_id: string }) =>
    http<DeskResult>(`/api/banker/cases/${caseId}/missing-requests`, json(body)),
  applicationOptions: () => http<ApplicationOptions>(`/api/demo/applications/options`),
  createApplication: (body: Record<string, string | number>) =>
    http<{ case_id: string; requirements: string[] }>(`/api/demo/applications`, json(body)),
  changeProfile: (caseId: string, borrowers: Record<string, { income_sources: string[]; business_registration?: string | null }>) =>
    http<{ changed: boolean; added: string[]; removed: string[]; tasks_canceled: string[]; calls_canceled: number }>(
      `/api/cases/${caseId}/profile`, json({ borrowers })),
  onboardingStart: () => http<OnboardingDraft>(`/api/demo/onboarding`, { method: "POST" }),
  onboarding: (draftId: string) => http<OnboardingDraft>(`/api/demo/onboarding/${encodeURIComponent(draftId)}`),
  onboardingAnswer: (draftId: string, questionId: string, value: unknown) =>
    http<OnboardingDraft>(`/api/demo/onboarding/${encodeURIComponent(draftId)}/answers`, json({ question_id: questionId, value })),
  onboardingConfirm: (draftId: string) =>
    http<{ case_id: string; created: boolean }>(`/api/demo/onboarding/${encodeURIComponent(draftId)}/confirm`, { method: "POST" }),
  requestRequirement: (caseId: string, code: string, body: { customer_message: string; rationale?: string; request_id: string }) =>
    http<DeskResult>(`/api/banker/cases/${caseId}/requirements/${encodeURIComponent(code)}/request`, json(body)),
  decide: (caseId: string, findingId: string, body: {
    action: FindingAction; rationale?: string; customer_message?: string; request_id: string; reason_code?: string;
    evidence_document_ids?: string[]; acknowledge_partial?: boolean }) =>
    http<DeskResult>(`/api/banker/cases/${caseId}/findings/${findingId}/decision`, json(body)),
  withdrawRequest: (caseId: string, requestId: string, body: { rationale: string; request_id: string }) =>
    http<DeskResult>(`/api/banker/cases/${caseId}/customer-requests/${requestId}/withdraw`, json(body)),
  acknowledgeHandoff: (caseId: string, packageId: string, body: { note?: string; request_id: string }) =>
    http<DeskResult>(`/api/banker/cases/${caseId}/handoffs/${packageId}/acknowledge`, json(body)),
  replyToRequest: (caseId: string, requestId: string, text: string) =>
    http<{ ok: boolean; customer_request: CustomerRequest }>(`/api/cases/${caseId}/customer-requests/${requestId}/reply`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) }),
  addNote: (caseId: string, body: { text: string; document_id?: string; finding_id?: string; request_id: string }) =>
    http<DeskResult>(`/api/banker/cases/${caseId}/notes`, json(body)),
  confirmPreparation: (caseId: string, body: { note: string; request_id: string }) =>
    http<{ ok: boolean; package_id: string; duplicate: boolean }>(`/api/banker/cases/${caseId}/confirm-preparation`, json(body)),
  bankerRecheck: (caseId: string) => http(`/api/banker/cases/${caseId}/recheck`, { method: "POST" }),
};

// ---------------------------------------------------------------- banker review workspace
export interface BankerCaseRow {
  case_id: string; display_number: string; title_he: string; borrowers: string[]; readiness: string; readiness_he: string;
  counts: Readiness["counts"]; queue: Record<string, number>;
  banker: { name_he: string; staff_id?: string };
}
export interface Decision {
  decision_id: string; target_kind: string; document_id?: string | null; finding_id?: string | null; borrower_id?: string | null;
  period?: string | null; action: string; action_he: string; previous_status?: string | null; new_status?: string | null;
  rationale?: string | null; customer_message?: string | null; customer_request_id?: string | null; finding_ids: string[];
  evidence_refs: { evidence_id: string; document_id: string; field: string; page: number; witness: string }[];
  actor_id: string; actor_name: string; created_at: string; reason_code?: string | null; reason_he?: string | null;
}
export type FindingAction = "resolve" | "dismiss" | "escalate" | "request_explanation" | "request_document";
export interface DeskRequest extends Omit<CustomerRequest, "document_filename" | "responded_filename"> { status_he: string; decision_id?: string }
export interface DeskFinding {
  finding_id: string; key: string; code: string; severity: string; review_state: Finding["review_state"]; review_state_he: string;
  status: Finding["status"]; status_he: string; borrower_id?: string | null; document_id?: string | null; period?: string | null;
  title_he: string; message_he: string; resolution?: string | null; resolution_note?: string | null;
  evidence: (EvidenceRef & { label_he: string; verified: boolean })[]; can_dismiss: boolean; can_decide: boolean; not_reproduced: boolean;
  statements: { text: string; channel: string; created_at: string }[]; history: (Finding["history"][number] & { actor?: string })[];
}
export interface IncomeBlock {
  declared_net_monthly_ils?: number | null; average_documented_net_ils?: number | null; difference_ils?: number | null;
  difference_pct?: number | null; months_compared: string[]; months_compared_he: string; months_required: number; tolerance_pct: number;
  outcome?: string | null; decided_by?: string | null; summary_he: string; tone: string; finding_id?: string | null; basis_he: string;
  model_assessment?: string | null; model_explanation_he?: string | null; criterion_id?: string | null;
  basis?: "none" | "preliminary" | "complete"; months_missing?: string[]; months_missing_he?: string; documented_label_he?: string;
}
export interface Draft { message_he: string; requested_period?: string | null; requested_item_he: string; explanation_he?: string }
interface ItemBase { id: string; group: string; attention: boolean; borrower_id?: string | null; borrower_he?: string | null; title_he: string;
  history: Decision[]; draft: Draft; requests: DeskRequest[] }
export interface DocItem extends ItemBase {
  kind: "document"; document_id: string; filename: string; mime: string; pages: number; doc_type_he: string; period?: string | null;
  requirement_code?: string | null; family?: string;
  period_he?: string | null; claimed_period?: string | null; claimed_period_he?: string | null; uploaded_at: string; is_scanned: boolean;
  ai: { status: string; stage?: string | null; verdict?: Verdict | null; verdict_he: string; tone: string; attention_he: string[]; summary_he: string;
    facts: (Fact & { verified: boolean })[]; criteria_failed: Criterion[]; criteria_uncertain: Criterion[]; criteria_passed: Criterion[];
    criteria_na: Criterion[]; limitations_he: string[]; uncertainty_he: string[]; security_flags: string[];
    technical: Record<string, any> };
  banker: { status: string; status_he: string; decision?: Decision | null; allowed_actions: ("accept" | "request_correction" | "escalate")[];
    blocked_accept_he?: string | null; acknowledge_finding_ids: string[]; accept_requires_rationale: boolean };
  findings: DeskFinding[]; replaces?: { document_id: string; filename: string; by?: "customer" | "banker_request" } | null;
  replaced_by?: { document_id: string; filename: string; status: string; by?: "customer" | "banker_request" } | null;
  outcome?: RoutedOutcome;
}
/** A missing payslip month (period set) or a missing non-payslip requirement (requirement_code set, period null). */
export interface MissingItem extends ItemBase {
  kind: "missing"; period: string | null; period_he: string | null; status_he: string; explanation_he: string;
  requirement_code?: string; family?: string; family_he?: string;
  related_documents: { document_id: string; filename: string; claimed_period: string; printed_period?: string | null; note_he: string }[];
  duplicate_note_he?: string | null; finding?: DeskFinding | null; open_request?: DeskRequest | null;
  allowed_actions: ("request_missing" | "request_requirement")[];
}
export interface RequirementRow {
  code: string; title_he: string; family: string; family_he?: string; ai_state: string; ai_state_he: string;
  borrower_he?: string | null; satisfied: boolean; units: string; policy_version?: string;
}
export interface CaseFindingItem extends ItemBase {
  kind: "case_finding"; finding: DeskFinding; income?: IncomeBlock | null; open_request?: DeskRequest | null;
  evidence_documents: { document_id: string; filename: string; field: string; label_he: string; value?: string | null; period_he?: string | null; verified: boolean }[];
  allowed_actions: ("request_missing" | "request_explanation" | "resolve" | "dismiss" | "escalate")[];
  basis: { partial: boolean; months_compared: string[]; months_required: string[]; months_missing: string[] };
  escalated: boolean; missing_months: string[]; missing_months_he: string; months_to_request: string[]; months_to_request_he: string;
  recommendation?: { action: string | null; title_he: string; body_he: string } | null;
  evidence_options: { document_id: string; filename: string; period_he?: string | null; net?: string | null; verdict_he: string }[];
  has_customer_statement: boolean; impact: { resolve: string[]; dismiss: string[]; customer_he: string };
  reopened_after?: { finding_id: string; resolution?: string | null; note_he?: string | null } | null;
  drafts: { missing?: { message_he: string; months: string[]; requested_item_he: string } | null; explanation: Draft };
}
export type QueueItem = DocItem | MissingItem | CaseFindingItem;
export interface Workspace {
  case_id: string; generated_at: string;
  case: { case_id: string; display_number: string; title_he: string; banker: { name_he: string; role_he: string; staff_id?: string };
    preliminary_decision?: BankCase["preliminary_decision"]; requested_loan_ils?: number;
    borrowers: { borrower_id: string; name_he: string; first_name_he: string; declared_net_monthly_ils: number; declaration_note_he: string }[] };
  bank_stage: BankCase["bank_stage"]; review_state: { state: string; label_he: string };
  preparation?: { confirmed_at: string; note?: string } | null;
  preparation_stale?: { confirmed_at: string; reason_he: string } | null;
  handoffs?: { package_id: string; created_at: string; channel: string; note?: string | null; created_by: string }[];
  can_confirm: { allowed: boolean; reason_he?: string | null; open_banker_items: number };
  summary: { payslips_required: number; payslips_verified: number; payslips_accepted: number; missing: number; open_requests: number;
    documents: number; processing: number; groups: Record<string, number> };
  borrowers: { borrower_id: string; name_he: string; first_name_he: string; verified: number; required: number; income: IncomeBlock;
    months: { period: string; label_he: string; state: string; state_he: string; documents: string[]; copies: number }[] }[];
  requirement_matrix?: RequirementRow[]; progress?: Readiness["progress"]; case_status?: string;
  groups: { key: string; title_he: string; hint_he: string; items: string[] }[];
  items: QueueItem[]; info_findings: DeskFinding[]; unattached_statements: { statement_id: string; text: string; channel: string; created_at: string }[];
  customer_requests: DeskRequest[]; history: (Partial<Decision> & { at: string; kind: string; title_he?: string; filename?: string; document_id?: string })[];
  not_evaluated: string[]; disclaimers_he: string[];
  document_profile?: DocumentProfile;
}
export interface DeskResult { ok: boolean; duplicate: boolean; decision: Decision; customer_request?: DeskRequest | null }

/** Poll a loader; faster while the backend reports work in progress. `failures` counts failed loads in a row and
 *  `updatedAt` is the last successful one, so a caller can tell a passing hiccup from data that is really stale.
 *  A poll and a reload() can overlap: every load is numbered, and a response older than the newest one already applied
 *  is dropped, so a slow stale response never overwrites fresher data. */
export function usePolling<T>(loader: () => Promise<T>, deps: unknown[], busy: (v: T) => boolean = () => false) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failures, setFailures] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const issued = useRef(0);
  const applied = useRef(0);
  const load = useCallback(async () => {
    const seq = ++issued.current;
    try {
      const v = await loader();
      if (seq < applied.current) return v;
      applied.current = seq;
      setData(v);
      setError(null);
      setFailures(0);
      setUpdatedAt(new Date());
      return v;
    } catch (e) {
      if (seq < applied.current) return null;
      applied.current = seq;
      setError(String((e as Error).message || e));
      setFailures((n) => n + 1);
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const v = await load();
      if (!alive) return;
      timer.current = window.setTimeout(tick, v && busy(v) ? 1200 : 4000);
    };
    tick();
    return () => { alive = false; window.clearTimeout(timer.current); };
  }, [load]);
  return { data, error, reload: load, failures, updatedAt };
}

export const ils = (n?: number | null) =>
  n === null || n === undefined ? "—" : `₪${Number(n).toLocaleString("he-IL", { maximumFractionDigits: 2 })}`;

const MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
export const monthHe = (ym?: string | null) => {
  if (!ym) return "—";
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
};
export const timeHe = (iso?: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", year: "2-digit" })} | ${d.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" })}`;
};
export const VERDICT_HE: Record<string, string> = { VALID: "נמצא תקין", INVALID: "לא תקין — נדרש תיקון", NEEDS_REVIEW: "דורש בדיקה" };
/** The customer's badge for a reviewed file: a document the AI review sends back to the customer reads as one to fix,
 *  also when the reviewer's verdict is NEEDS_REVIEW (unreadable, out of date) — the same thing its page and row say. */
export function customerVerdict(verdict: string, outcome?: RoutedOutcome): { cls: string; text: string } {
  if (verdict !== "VALID" && outcome?.outcome === "BLOCKER" && outcome.by === "ai") return { cls: "INVALID", text: VERDICT_HE.INVALID };
  return { cls: verdict, text: VERDICT_HE[verdict] };
}
export const OUTCOME_HE: Record<string, string> = { PASS: "עבר", FAIL: "נכשל", NEEDS_REVIEW: "דורש בדיקה", NOT_APPLICABLE: "לא רלוונטי" };
export const WITNESS_HE: Record<string, string> = {
  text_layer_exact: "אומת מול שכבת הטקסט של הקובץ", vision_reread_confirmed: "אומת בקריאה חוזרת של הסריקה",
  vision_unverified: "לא אומת", not_found: "לא נמצא בקובץ", unavailable: "אין ראיה",
};
