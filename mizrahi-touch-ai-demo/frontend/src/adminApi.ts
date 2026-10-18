/** The Admin Settings API (`/api/admin/loan-completion`, CONTRACTS §7). Every call rides the staff session cookie. */
import { request } from "./api";
import { currentLang, loc } from "./i18n";

export type Kind = "loan_policy" | "talk_prompt";
export type Json = Record<string, any>;

export interface VersionRow {
  version_id: string; kind: Kind; number: number; label: string; status: "DRAFT" | "PUBLISHED" | "ARCHIVED" | "DISCARDED";
  revision: number; author: string | null; last_editor: string | null; created_at: string; updated_at: string;
  published_at: string | null; published_by: string | null; based_on: string | null; change_reason: string | null;
  change_reason_en?: string; hash: string | null; config?: Json;
}
export interface DiffEntry { path: string; before: unknown; after: unknown }
export interface Problem { path: string; message: string; message_en?: string; code?: string; span?: [number, number] | null; match?: string }
export interface LintFinding { code: string; severity: "warning" | "error"; message_he: string; message_en?: string; path: string; span: [number, number] | null; match: string }
export interface Report {
  errors: Problem[]; warnings: Problem[]; lint: LintFinding[]; diff: DiffEntry[]; preview: Json; against: string;
  publishable?: boolean; reasons?: string[]; reasons_en?: (string | null)[]; revision?: number;
}
/** read-only English renderings of the policy's canonical Hebrew texts (sent only with a language header) */
export interface CanonicalEn {
  requirements: Record<string, { label: string; hint: string; why: string; alternatives: string[] }>;
  purposes: Record<string, { label: string; proof: string }>;
}
export interface FlagRow { key: string; value: boolean; updated_at: string | null; updated_by: string | null }
export interface Settings {
  environment: { name: string; label_he: string; label_en?: string; demo_identity: boolean; synthetic: boolean };
  published: Record<Kind, VersionRow>;
  drafts: Record<Kind, VersionRow | null>;
  kill_switch: FlagRow;
  locked_rules: { id: string; label_he: string; label_en?: string }[];
  rule_labels: Record<string, { tier: string; label_he: string; label_en?: string }>;
  envelope: { call_window_bounds: [string, string]; no_contact_days: string[]; max_attempts_per_case: number;
    min_hours_between_calls: number; min_grace_minutes: Record<string, number> };
  locked_fields: Record<Kind, { path: string; reason_he: string; reason_en?: string }[]>;
  prompt_variables: string[];
  preview_variables: Record<string, string | string[]>;
  requirement_catalog: Json[];
  simulator_available: boolean;
  caller: { staff_id: string; name_he: string; name_en?: string; role_he: string; role_en?: string };
  canonical_en?: CanonicalEn;
}
export interface Decision {
  action: string; policy_version: string; explanation_he: string; explanation_en?: string; blocked_by: string[]; rule_ids: string[];
  next_eligible_at: string | null; channel: string | null; task_ids: string[];
}
export interface ScenarioResult {
  scenario_id: string; title_he: string; title_en?: string; mandatory: boolean; passed: boolean;
  expected: { action: string; rule_ids_include: string[]; blocked_by_include: string[]; next_eligible_at: string | null };
  actual: Decision | null; error: string | null;
}
export interface SimulationRun {
  run_id: string; version_id: string | null; config_hash: string; actor: string; created_at: string; side_effects: false;
  passed: boolean; mandatory_passed: boolean; results: ScenarioResult[];
}
/** Scenarios that pin timing values for the regression check: the decision with the configuration's own values. */
export type AsConfigured = Record<string, { pinned: string[]; decision: Decision }>;
export interface AuditEvent { event_id: string; type: string; occurred_at: string; actor: string; payload: Json }

/** A refused request, with the service's structured detail (reasons, errors, the current revision). */
export class AdminError extends Error {
  status: number;
  detail: any;
  constructor(status: number, message: string, detail: any) { super(message); this.status = status; this.detail = detail; }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await request(path, init);
  if (!res.ok) {
    let detail: any = null;
    let detailEn: string | null = null;
    try { const body = await res.json(); detail = body.detail; detailEn = body.detail_en ?? null; } catch { /* not json */ }
    const message = currentLang() === "en"
      ? (typeof detail === "string" ? detailEn || detail : detail?.message_en || detail?.message || `Error ${res.status}`)
      : typeof detail === "string" ? detail : detail?.message || `שגיאה ${res.status}`;
    throw new AdminError(res.status, message, detail);
  }
  return res.json() as Promise<T>;
}

const send = (method: string, body: unknown): RequestInit =>
  ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const BASE = "/api/admin/loan-completion";

export const adminApi = {
  session: () => http<{ staff: { staff_id: string; name_he: string } | null; demo_identity: boolean }>(`/api/session`),
  /** demo mode: the same demo staff session the banker console obtains, without a login */
  demoStaff: () => http<{ staff: { staff_id: string } }>(`/api/session/demo/staff`, send("POST", {})),
  settings: () => http<Settings>(`${BASE}/settings`),
  openDraft: (kind: Kind, reason = "") => http<VersionRow>(`${BASE}/drafts`, send("POST", { kind, reason })),
  saveDraft: (id: string, config: Json, revision: number, reason = "") =>
    http<VersionRow>(`${BASE}/drafts/${id}`, send("PUT", { config, revision, reason })),
  validateDraft: (id: string) => http<Report>(`${BASE}/drafts/${id}/validate`, send("POST", {})),
  check: (kind: Kind, config: Json) => http<Report>(`${BASE}/validate`, send("POST", { kind, config })),
  discard: (id: string, revision: number) => http<{ discarded: string }>(`${BASE}/drafts/${id}/discard`, send("POST", { revision })),
  publish: (id: string, revision: number) =>
    http<{ published: VersionRow; previous: VersionRow }>(`${BASE}/drafts/${id}/publish`, send("POST", { revision })),
  versions: (kind: Kind) => http<VersionRow[]>(`${BASE}/versions?kind=${kind}`),
  diff: (id: string, against?: string) =>
    http<{ version: VersionRow; against: VersionRow | null; diff: DiffEntry[] }>(`${BASE}/versions/${id}/diff${against ? `?against=${against}` : ""}`),
  rollback: (kind: Kind, to: string, reason: string) => http<VersionRow>(`${BASE}/rollback`, send("POST", { kind, to_version_id: to, reason })),
  simulate: (config: Json | null, versionId: string | null) =>
    http<SimulationRun>(`${BASE}/policy/simulate`, send("POST", config ? { config, version_id: versionId } : { version_id: versionId })),
  asConfigured: (config: Json | null, versionId: string | null) =>
    http<AsConfigured>(`${BASE}/policy/as-configured`, send("POST", config ? { config, version_id: versionId } : { version_id: versionId })),
  pause: (paused: boolean, reason: string) => http<FlagRow>(`${BASE}/followups/pause`, send("POST", { paused, reason })),
  audit: (limit = 60) => http<{ events: AuditEvent[]; versions: Record<Kind, VersionRow[]> }>(`${BASE}/audit?limit=${limit}`),
};

export const KIND_HE: Record<Kind, string> = { loan_policy: "מדיניות ההשלמה", talk_prompt: "הנחיות הסוכנת" };
export const STATUS_HE: Record<string, string> = { DRAFT: "טיוטה", PUBLISHED: "פעילה", ARCHIVED: "בארכיון", DISCARDED: "בוטלה" };
export const KIND_EN: Record<Kind, string> = { loan_policy: "Completion policy", talk_prompt: "Agent instructions" };
export const STATUS_EN: Record<string, string> = { DRAFT: "Draft", PUBLISHED: "Active", ARCHIVED: "Archived", DISCARDED: "Discarded" };
/** the kind's name in the platform's language */
export const kindL = (kind: Kind): string => (currentLang() === "en" ? KIND_EN : KIND_HE)[kind];
export const statusL = (status: string): string => (currentLang() === "en" ? STATUS_EN : STATUS_HE)[status];

/** "admin:STAFF-DANA" → a display name; system and test actors stay as written. */
export function actorHe(actor: string | null | undefined, me?: { staff_id: string; name_he: string; name_en?: string }): string {
  if (!actor) return "-";
  if (actor === "system:seed") return currentLang() === "en" ? "Initial version" : "גרסת פתיחה";
  const id = actor.includes(":") ? actor.split(":")[1] : actor;
  return me && id === me.staff_id ? loc(me.name_he, me.name_en) : id;
}

export function getPath(obj: any, path: string): any {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

/** An immutable update of one dotted path. */
export function setPath<T extends Json>(obj: T, path: string, value: unknown): T {
  const [head, ...rest] = path.split(".");
  const copy: any = Array.isArray(obj) ? [...obj] : { ...obj };
  copy[head] = rest.length ? setPath(copy[head] ?? {}, rest.join("."), value) : value;
  return copy;
}

export function renderPreview(text: string, vars: Record<string, string | string[]>): string {
  return (text || "").replace(/{{\s*(\w+)\s*}}/g, (m, name) => {
    const v = vars[name];
    return v == null ? m : Array.isArray(v) ? v.join(", ") : String(v);
  });
}
