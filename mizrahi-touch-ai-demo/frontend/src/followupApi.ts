import { http } from "./api";

/* The follow-up engine's API (CONTRACTS §8): the customer's view, the banker's card and timeline, and the demo controls
   the presenter drives. Every call goes to the same origin; demo routes answer only in demo mode and say "סימולציה". */
export interface CustomerFollowup {
  state_he: string; nudge: boolean; nudge_text_he: string | null; snooze_until: string | null; simulated: boolean;
  open_items: { requirement_code: string; title_he: string; customer_text_he: string | null }[];
  contact: { voice_allowed: boolean; message_allowed: boolean; preferred_channel: string | null };
}
export interface FollowupDecision {
  action: string; explanation_he: string; blocked_by: string[]; rule_ids: string[]; next_eligible_at: string | null;
  channel: string | null; policy_version: string;
}
export interface BankerFollowup {
  plan: { state: string; plan_version: number; next_eligible_at: string | null; policy_version: string | null; updated_at: string | null };
  decision: FollowupDecision | null; case_status: string; kill_switch: boolean; talk_mode: string; simulated: boolean;
  tasks: { task_id: string; requirement_code: string; reason_code: string; status: string; title_he: string; created_at: string;
    resolved_at: string | null; document_id: string | null }[];
  attempts: { attempt_id: string; channel: string; provider: string; simulated: boolean; status: string; outcome: string | null;
    created_at: string; link_id: string | null }[];
  overrides: { type: string; reason: string; actor: string; created_at: string; revoked_at: string | null; active: boolean }[];
}
export interface TimelineEntry { at: string; type: string; actor: string; summary_he: string; payload: Record<string, unknown> }
export interface SentLink { link_id: string; requirement_code: string | null; created_at: string; state: string; url: string | null; token: string | null }

const post = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const c = (id: string) => encodeURIComponent(id);

export const followupApi = {
  customer: (caseId: string) => http<CustomerFollowup>(`/api/cases/${c(caseId)}/followup`),
  snooze: (caseId: string, minutes: number) => http<CustomerFollowup>(`/api/cases/${c(caseId)}/followup-snooze`, post({ minutes })),
  preferences: (caseId: string, prefs: { opt_out_voice?: boolean; preferred_channel?: string }) =>
    http<CustomerFollowup>(`/api/cases/${c(caseId)}/contact-preferences`, post(prefs)),
  redeem: (token: string) => http<{ state: string; case_id?: string; target?: string }>(`/api/links/redeem`, post({ token })),
  banker: (caseId: string) => http<BankerFollowup>(`/api/banker/cases/${c(caseId)}/followup`),
  timeline: (caseId: string, limit = 60) => http<TimelineEntry[]>(`/api/banker/cases/${c(caseId)}/timeline?limit=${limit}`),
  override: (caseId: string, type: "pause" | "resume" | "cancel", reason: string) =>
    http<BankerFollowup>(`/api/banker/cases/${c(caseId)}/followup-override`, post({ type, reason })),
  callNow: (caseId: string, reason: string) => http<Record<string, unknown>>(`/api/banker/cases/${c(caseId)}/followups`, post({ reason })),
  demo: {
    clock: (body: { advance_minutes?: number; to_next_window?: boolean; reset?: boolean }) =>
      http<{ now: string; offset_seconds?: number }>(`/api/demo/clock`, post(body)),
    customerLeft: (caseId: string) => http<{ state: string; decision: FollowupDecision }>(`/api/demo/cases/${c(caseId)}/customer-left`, post({})),
    tick: () => http<{ evaluated: string[]; steps: number }>(`/api/demo/tick`, post({})),
    talkOutcome: (caseId: string, outcome: string) =>
      http<{ status: string; outcome: string; plan_state: string }>(`/api/demo/cases/${c(caseId)}/talk-outcome`, post({ outcome })),
    sentLinks: (caseId: string) => http<{ links: SentLink[] }>(`/api/demo/cases/${c(caseId)}/sent-links`),
  },
};

export const PLAN_HE: Record<string, string> = {
  IDLE: "אין מעקב פעיל", WAITING: "ממתינים ללקוח", IN_APP: "תזכורת באפליקציה", SCHEDULED: "שיחה מתוזמנת",
  DISPATCHING: "מחייגים", IN_CALL: "בשיחה", AWAITING_CUSTOMER: "נשלח קישור, ממתינים להעלאה",
  BLOCKED: "חסום לפי מדיניות", PAUSED: "מושהה ע״י הבנקאי", CANCELED: "בוטל", ESCALATED: "הועבר לבנקאי", COMPLETED: "הושלם",
};
export const ACTION_HE: Record<string, string> = {
  NO_ACTION: "אין צורך בפעולה", IN_APP_ONLY: "באפליקציה בלבד", WAIT: "המתנה", SUPPRESS: "בלי פנייה", IN_APP_NUDGE: "תזכורת באפליקציה",
  SCHEDULE_CALL: "תזמון שיחה", DISPATCH_NOW: "פנייה עכשיו", BLOCK: "חסום", RESOLVE_AND_CANCEL: "נפתר, המעקב בוטל",
  ESCALATE: "העברה לבנקאי", SNOOZE: "נדחה לבקשת הלקוח",
};
