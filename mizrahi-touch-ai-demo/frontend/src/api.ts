import type { Afford as SimAfford, Issue as SimIssue, Params as SimParams, Product as SimProduct, Rate as SimRate, Result as SimResult, Target as SimTarget } from "./loanCalc";
import { useCallback, useEffect, useRef, useState } from "react";
import { currentLang, LANG_SWITCH } from "./i18n";

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
export interface OnboardingQuestion { question_id: string; kind: "choice" | "multi" | "name" | "text" | "number" | "simulator"; prompt_he: string; options: OnboardingOption[] }
export interface OnboardingDraft {
  draft_id: string; status: "draft" | "confirmed"; case_id: string | null; note_he: string;
  asked: { question_id: string; prompt_he: string; kind: string; answer: unknown; answer_he: string }[];
  next: OnboardingQuestion | null;
  summary: null | { profile: DocumentProfile; policy_version: string; title_he: string; loan: LoanDetails;
    requirements: Pick<Requirement, "code" | "title_he" | "family" | "family_he" | "owner_he" | "owner_type" | "why_he" | "alternatives_he" | "intake" | "required">[] };
}
/** Conversational questionnaire (V2): the same draft as OnboardingDraft, with a transcript, stages and a DEMO indication. */
export interface ChatIndication {
  max_amount_ils: number; requested_amount_ils: number; within: boolean; requested_monthly_ils: number; payments: number;
  declared_net_ils: number; co_borrower_pending: boolean;
  /** the formula's assumptions, on messages saved since they were added */
  ratio?: number; annual_rate?: number; business_income?: boolean;
}
export interface ChatReply { label_he: string; value: unknown }
/** A quick reply under a message: answers a question (question_id + value) or sends a text. */
export interface ChatAction { label_he: string; question_id?: string; value?: unknown; text?: string;
  /** a suggested scenario change (amount / term) for the loan simulator */
  simulation?: Partial<SimParams> }
/** One message's record of the loan simulator card it carried; only the latest one is live. */
export interface SimSnapshot { status: "pending" | "confirmed"; product_he: string; amount: number; term: number;
  monthly_payment: number | null; rev: number; live: boolean }
export interface SimEval { result: (Omit<SimResult, "rows"> & { yearly: { year: number; from_month: string; to_month: string; paid: number;
    interest: number; principal: number; balance: number }[] }) | null;
  issues: SimIssue[]; affordability: SimAfford | null; comparison: { term: number; monthly_payment: number; total_interest: number; chosen: boolean }[];
  target: SimTarget | null; rate: SimRate }
/** The loan simulator inside the conversation: candidate products (rules + sources), the draft and confirmed scenarios,
 *  the server's evaluation of each and the customer-declared context. Amount and term are questionnaire answers. */
export interface Simulation {
  status: "pending" | "confirmed"; editing: boolean; rev: number; product_id: string; candidates: SimProduct[];
  amount_field: "amount" | "business_amount"; purpose: string | null;
  draft: SimParams; draft_eval: SimEval; confirmed: SimParams | null; confirmed_eval: SimEval | null;
  context: { net_income: number | null; net_parts: { who: string; net_ils: number }[]; co_borrower_pending: boolean;
    obligations: number | null; target_monthly: number | null; source: "CUSTOMER_DECLARED" };
  start_month: string; config_version: string; checked_on: string;
}
export interface ChatMessage {
  id: number; role: "assistant" | "user"; kind: "text" | "question" | "insight" | "withdrawn" | "summary"; text_he: string;
  question_id?: string; indication?: ChatIndication & { key: string }; insight?: "new" | "updated" | "withdrawn";
  simulator?: SimSnapshot;
  stale?: boolean; actions?: ChatAction[]; engine?: "llm" | "rules"; understood_by?: "llm" | "rules";
}
export interface ChatStage { id: string; label_he: string; state: "done" | "current" | "upcoming"; total: number; answered: number }
export interface ChatDraft {
  draft_id: string; status: "draft" | "confirmed"; case_id: string | null; first_name_he: string | null; note_he: string;
  messages: ChatMessage[]; stages: ChatStage[]; indication: ChatIndication | null; suggestions: string[]; actions: ChatAction[];
  loan: { type?: "personal" | "business" | null; form?: "vat_exempt" | "vat_registered" | "company" | null };
  engine: "llm" | "rules";
  simulation: Simulation | null;
  pending: null | { question_id: string; kind: OnboardingQuestion["kind"]; prompt_he: string; replies: ChatReply[];
    placeholder_he: string; editing: boolean; current_he: string | null };
  summary: null | (NonNullable<OnboardingDraft["summary"]> & {
    lines: { label_he: string; value_he: string; question_id: string }[]; intro_he: string });
}
export type ChatTurn = ({ text: string } | { question_id: string; value: unknown; label_he?: string }
  | { question_id?: string; action: "edit" | "cancel_edit" }
  | { action: "simulate_confirm" | "simulate_apply"; simulation: Partial<SimParams> & { product?: string }; label_he?: string })
  & { turn_id?: string };
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
  case_id: string; display_number: string; title_he: string; title_en?: string; requested_loan_ils: number; submitted_at: string;
  preliminary_decision?: { label_he: string; label_en?: string; issued_on: string; valid_until: string; amount_ils: number } | null;
  loan: LoanDetails; accounts?: { account_id: string; label_he: string; label_en?: string; bank_he: string; bank_en?: string; holders: string[] }[];
  contact?: { consent_voice: boolean; consent_message: boolean; phone_masked?: string };
  banker: { name_he: string; name_en?: string; role_he: string; role_en?: string; staff_id?: string };
  meeting?: { date: string; from: string; to: string; type_he: string; type_en?: string } | null; borrowers: Borrower[];
  persona_id?: string | null; use_case?: string | null; applicant_type?: "individual" | "company"; banker_assisted?: boolean;
  profile_changed_at?: string | null;
  document_profile?: DocumentProfile;
  bank_stage: { index: number; of: number; label_he: string; label_en?: string; source: string; authoritative: boolean; label_observed_in_screenshot: boolean };
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
/** Fired on a 401 the app could not recover from; the session cookie is HttpOnly, so this is the only signal. */
export const AUTH_EVENT = "mz-auth-required";

type Role = "customer" | "staff";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
/** The session a screen uses when a 401 accepts either: the banker console, admin and system pages work as staff. */
const pageRole = (): Role => (/^\/(banker|admin|system)/.test(window.location.pathname) ? "staff" : "customer");
const caseOf = (path: string) => {
  const m = path.match(/^\/api\/cases\/([^/?#]+)/);
  return m ? decodeURIComponent(m[1]) : localStorage.getItem("mz.case") || CASE_ID_DEFAULT;
};
const renewing = new Map<string, Promise<boolean>>();
/** Demo mode: obtain the session a 401 named (the customer one for the request's case). Concurrent 401s share one
 *  renewal; false when the service issues no demo sessions or cannot be reached. */
function renew(role: Role, path: string): Promise<boolean> {
  const caseId = role === "customer" ? caseOf(path) : "";
  const key = `${role}:${caseId}`;
  let p = renewing.get(key);
  if (!p) {
    p = fetch(role === "staff" ? "/api/session/demo/staff" : "/api/session/demo/customer", {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(role === "staff" ? {} : { case_id: caseId }),
    }).then((r) => r.ok, () => false).finally(() => renewing.delete(key));
    renewing.set(key, p);
  }
  return p;
}
const TRANSIENT = new Set([502, 503, 504]);
/** The customer endpoints whose wording follows the customer app's language (backend: app/i18n.py reads X-MZ-Lang on
 *  these routes only). Sent from /customer pages only — the presenter pane, banker, admin and system stay Hebrew — and
 *  merged into the request's own headers. Without the switch (VITE_LANG_SWITCH=0) no request changes. */
const LOCALIZED = /^\/api\/(cases\/|documents\/|demo\/onboarding|session\/demo\/cases|links\/|voice\/)/;
function withLang(path: string, init?: RequestInit): RequestInit | undefined {
  if (!LANG_SWITCH || !window.location.pathname.startsWith("/customer") || !LOCALIZED.test(path)) return init;
  const headers = new Headers(init?.headers);
  headers.set("X-MZ-Lang", currentLang());
  return { ...init, headers };
}

/** fetch for the app's API. A read is retried twice on a network error or 502/503/504 (a backend restarting); a 401
 *  renews the session it names once and repeats the request once — the server refused it before doing anything, so
 *  repeating a write is safe. Anything else, and a second 401, goes back to the caller unchanged. */
export async function request(path: string, given?: RequestInit): Promise<Response> {
  const init = withLang(path, given);
  const read = !init?.method || ["GET", "HEAD"].includes(init.method.toUpperCase());
  let res!: Response;
  for (let attempt = 0; ; attempt++) {
    try {
      res = await fetch(path, { credentials: "same-origin", ...init });
      if (!(read && TRANSIENT.has(res.status) && attempt < 2)) break;
    } catch (e) {
      if (!read || attempt >= 2) throw e;
    }
    await sleep(attempt ? 1200 : 400);
  }
  if (res.status === 401 && !path.startsWith("/api/session")) {
    const roles = (res.headers.get("X-Auth-Required") || "").split(",").map((r) => r.trim()).filter(Boolean) as Role[];
    const role = roles.includes(pageRole()) ? pageRole() : roles[0];
    if (role && await renew(role, path)) res = await fetch(path, { credentials: "same-origin", ...init });
  }
  return res;
}

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await request(path, init);
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
  case_id: string; display_number: string; title_he: string; title_en?: string;
  /** the demonstrated customer ("התיקים שלי" lists one persona's cases); QA cases have none */
  persona_id?: string | null; qa?: boolean; use_case?: string | null; applicants_he?: string[]; applicants_en?: string[];
  company_he?: string | null; company_en?: string | null;
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
    const res = await request(`/api/cases/${caseId}/actions/resolve`, {
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
  bankerIntelligence: (caseId: string) => http<Intelligence>(`/api/banker/cases/${caseId}/intelligence`),
  bankerChat: (caseId: string, body: { message: string; history: { role: "user" | "model"; text: string }[]; draft: { kind: string; text: string } | null },
    signal?: AbortSignal) => http<CaseChatReply>(`/api/banker/cases/${caseId}/chat`, { ...json(body), signal }),
  bankerDemoLetter: (caseId: string, body: { acknowledge_open_issues: boolean; use_ai: boolean }, signal?: AbortSignal) =>
    http<DemoLetter>(`/api/banker/cases/${caseId}/demo-approval-letter`, { ...json(body), signal }),
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
  chatStart: () => http<ChatDraft>(`/api/demo/onboarding/v2`, { method: "POST" }),
  chat: (draftId: string) => http<ChatDraft>(`/api/demo/onboarding/${encodeURIComponent(draftId)}/v2`),
  chatTurn: (draftId: string, turn: ChatTurn) =>
    http<ChatDraft>(`/api/demo/onboarding/${encodeURIComponent(draftId)}/v2/turn`, json(turn)),
  chatSimulation: (draftId: string, draft: Partial<SimParams> & { product?: string; obligations?: number | null }) =>
    http<{ simulation: Simulation }>(`/api/demo/onboarding/${encodeURIComponent(draftId)}/v2/simulation`, json({ draft })),
  chatConfirm: (draftId: string) =>
    http<{ case_id: string; created: boolean }>(`/api/demo/onboarding/${encodeURIComponent(draftId)}/v2/confirm`, { method: "POST" }),
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
  /** the case's latest audited activity; rows arrive newest first */
  last_activity_at: string | null;
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

// ---------------------------------------------------------------- banker intelligence V2 (api/banker_intelligence.py)
export interface Datum { value: number | null; unit: "ils" | "pct" | "months"; source_id: string | null }
/** `origin` marks an input that has no stored source: a value the banker set in the simulator, or one computed alongside. */
export interface SourceInput { label_he: string; value: number | null; unit: string; source_id: string | null; origin?: "sim" | "calc" }
export interface IntelSource {
  id: string; kind: "document" | "declared" | "synthetic_bank" | "calculated" | "assumption" | "missing";
  label_he: string; value?: number | string | null; unit?: string; note_he?: string | null;
  // document
  value_raw?: string | null; document_id?: string; field?: string; filename?: string; doc_type_he?: string; period_he?: string | null;
  verified?: boolean; witness?: string | null; witness_he?: string; page?: number | null; has_location?: boolean; ai_verdict_he?: string;
  banker_status?: string; banker_status_he?: string; banker_reviewed?: boolean; v1_item?: string;
  // declared · synthetic
  origin_he?: string; fixture_id?: string; observed_at?: string; source_he?: string; detail_he?: string;
  // calculated
  formula_he?: string; inputs?: SourceInput[];
}
export interface IntelScenario {
  key: "short" | "requested" | "long"; term_months: number; principal_ils: number; annual_rate_pct: number; monthly_payment_ils: number;
  total_payments_ils: number; total_interest_ils: number; combined_debt_service_ils: number; combined_dsr_pct: number | null;
  combined_includes_existing: boolean; ltv_pct: number | null; remaining_after_debt_ils: number | null;
}
export interface IntelDiscrepancy {
  borrower_id: string | null; first_name_he: string | null; kind: "income" | "purpose_amount"; title_he: string; open: boolean;
  declared: Datum; documented: Datum; difference_ils: number | null; difference_pct: number | null; tolerance_pct: number | null;
  status_he: string; v1_item: string; explanation_he: string; action_he: string;
}
export interface IntelDraft { kind: string; title_he: string; message_he: string; attachments: { document_id: string; label_he: string }[] }
/** Banker V3 "שאל את JEEN" (api/banker_chat.py). `edit` is a revision of the draft that was sent, already checked in code. */
export interface CaseChatReply {
  intent: "question" | "draft_edit" | "question_and_edit" | "clarification" | "declined";
  answer_he: string; source_ids: string[]; sources: Record<string, { label_he: string; kind: IntelSource["kind"] }>;
  edit: { kind: string; text: string; summary_he: string } | null; rejected_issues_he: string[]; repaired: boolean; model: string;
}
/** Banker V3 third reply (api/banker_demo_letter.py): an approval letter for a SIMULATED decision; the case is unchanged.
 *  `source` "ai" = prose written by Gemini around code-built terms; "base" = the fixed base wording, no model. */
export interface DemoLetter {
  kind: "demo_approval"; title_he: string; text: string; source: "ai" | "base"; model: string | null; case_ready: boolean;
  open_issues_he: string[]; check_issues_he: string[];
  scenario: { label_he: string; principal_ils: number; term_months: number; annual_rate_pct: number; monthly_payment_ils: number;
    total_payments_ils: number; total_interest_ils: number };
}
export interface Intelligence {
  version: string; case_id: string; generated_at: string; disclaimer_he: string;
  case: { display_number: string; title_he: string; banker: { name_he: string; role_he: string; staff_id?: string }; bank_stage: BankCase["bank_stage"]; submitted_at?: string };
  applicant: { entity: string; entity_he?: string; profile_label_he?: string | null; company?: DocumentProfile["company"];
    borrowers: { borrower_id: string; name_he: string; first_name_he: string; role?: string; role_he: string; profile_he?: string | null;
      employer_declared_he?: string; employer_document_source_id?: string | null; income_sources: string[] }[]; co_borrowers: string[] };
  loan: { product_he?: string; purpose_he?: string; note_he?: string; amount: Datum; term: Datum;
    asset: { price: Datum; subject_source_id?: string | null; label_he: string } | null };
  documents: { state: string; state_he: string; case_status?: string; progress?: { done: number; total: number; missing_units: number } | null;
    total: number; accepted: number; awaiting_decision: number; open_findings: number;
    missing: { title_he: string; item_he: string; status_he: string; v1_item: string; requested: boolean }[];
    corrections: { title_he: string; item_he: string; reason_he: string; v1_item: string }[];
    requirements: { title_he: string; family_he?: string; satisfied: boolean; state_he: string }[] };
  income: { borrowers: { borrower_id: string; first_name_he: string; name_he: string; declared: Datum; documented_avg: Datum;
    months: { period: string; period_he: string; net_ils: number | null; verified: boolean; source_id: string | null }[];
    months_required: number; basis: string; quality: "verified" | "partial" | "declared" | "missing"; variability_pct: number | null;
    chosen: Datum; unresolved_discrepancy: boolean; business_income: boolean }[]; total: Datum; business_income: boolean };
  bank_context: { available: boolean; missing_for: string[]; source: { source: string; note_he: string }; observed_at: string | null; fixture_ids: string[];
    accounts: { type_he: string; number: string; opened: string; holders_he: string; owner_he: string }[];
    loans: { id: string; type_he: string; lender_he: string; original_ils: number; start: string; term_months: number; annual_rate_pct: number;
      remaining_payments: number; end: string; owner_he: string; monthly: Datum; outstanding: Datum }[];
    credit_lines: { id: string; kind: string; type_he: string; limit_ils: number; utilized_ils: number; owner_he: string; source_id: string }[];
    card_spending: { owner_he: string; avg_monthly_ils: number; months: string[]; note_he: string; source_id: string }[];
    events: { owner_he: string; returned_checks_12m: number; arrears_12m: number; restrictions_he: string[]; detail_he: string[]; source_id: string }[];
    exposure: { approved: Datum; utilized: Datum; loans_outstanding: Datum; credit_limits_ils: number; credit_utilized_ils: number } | null };
  analysis: { availability: "full" | "partial" | "provisional" | "unavailable"; status_he: string; reasons_he: string[];
    existing_debt: Datum; income: Datum; proposed_payment?: Datum; total_payments?: Datum; total_interest?: Datum; existing_dsr?: Datum;
    combined_dsr?: Datum; remaining_after_debt?: Datum; ltv?: Datum;
    declared_alternative: { basis_he: string; income_ils: number | null; combined_dsr_pct: number | null } | null; illustrative_max_principal: number | null };
  simulation: { inputs: { principal: number; term_months: number; annual_rate_pct: number }; income_ils: number | null; existing_debt_ils: number | null;
    asset_price_ils: number | null; threshold_pct: number; threshold_source_id: string; rate_source_id: string; income_source_id: string | null;
    existing_source_id: string | null; asset_source_id: string | null;
    bounds: { term_min: number; term_max: number; step: number; principal_max: number };
    scenarios: IntelScenario[]; suggested: { key: string | null; term_months: number | null; why_he: string; label_he: string } | null; enabled: boolean };
  recommendation: { state: string; tone: string; headline_he: string; next_action: { kind: string; label_he: string; detail_he?: string; v1_item: string | null };
    documentation: { status_he: string; case_status?: string };
    financial: { availability: string; status_he: string; text_he: string; suggested: Intelligence["simulation"]["suggested"] };
    considerations: { text_he: string; tone: string; source_ids: string[] }[]; verify: { text_he: string; v1_item?: string }[] };
  discrepancies: IntelDiscrepancy[];
  risks: { kind: string; title_he: string; text_he: string; tone: string; who_he: string; v1_item: string; source_ids: string[] }[];
  unknowns: { label_he: string; text_he: string }[];
  drafts: IntelDraft[]; recommended_draft: string | null; sources: Record<string, IntelSource>;
}

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
  n === null || n === undefined ? "-" : `₪${Number(n).toLocaleString("he-IL", { maximumFractionDigits: 2 })}`;

const MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
export const monthHe = (ym?: string | null) => {
  if (!ym) return "-";
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
};
export const timeHe = (iso?: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", year: "2-digit" })} | ${d.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" })}`;
};
export const VERDICT_HE: Record<string, string> = { VALID: "נמצא תקין", INVALID: "לא תקין, נדרש תיקון", NEEDS_REVIEW: "דורש בדיקה" };
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
