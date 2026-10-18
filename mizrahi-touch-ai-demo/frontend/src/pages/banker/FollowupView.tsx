import { useState } from "react";
import { timeL, usePolling } from "../../api";
import { ACTION_HE, followupApi, PLAN_HE } from "../../followupApi";
import { locOf, useLang } from "../../i18n";
import { Chip } from "./deskUi";

const TASK_HE: Record<string, string> = { OPEN: "פתוחה", RESOLVED: "נפתרה, מסמך חדש עבר בדיקה", CANCELED: "בוטלה",
  PAUSED_BY_BANKER: "מושהית ע״י הבנקאי", PAUSED_BY_CUSTOMER: "נדחתה לבקשת הלקוח", POLICY_BLOCKED: "חסומה לפי מדיניות" };
const OUTCOME_HE: Record<string, string> = { LINK_SENT: "נשלח קישור להשלמה", CALLBACK_REQUESTED: "הלקוח ביקש שיחה חוזרת",
  REFUSED: "הלקוח סירב", HUMAN_REQUESTED: "הלקוח ביקש נציג", NO_ANSWER: "אין מענה", IDENTITY_FAILED: "זיהוי נכשל",
  COMPLETED_NO_ACTION: "הסתיימה ללא פעולה" };
const TASK_EN: Record<string, string> = { OPEN: "Open", RESOLVED: "Resolved — a new document passed the check", CANCELED: "Canceled",
  PAUSED_BY_BANKER: "Paused by the banker", PAUSED_BY_CUSTOMER: "Postponed at the customer's request", POLICY_BLOCKED: "Blocked by policy" };
const OUTCOME_EN: Record<string, string> = { LINK_SENT: "Completion link sent", CALLBACK_REQUESTED: "The customer asked for a callback",
  REFUSED: "The customer declined", HUMAN_REQUESTED: "The customer asked for a representative", NO_ANSWER: "No answer", IDENTITY_FAILED: "Identity check failed",
  COMPLETED_NO_ACTION: "Ended with no action" };
const PLAN_EN: Record<string, string> = {
  IDLE: "No active follow-up", WAITING: "Waiting for the customer", IN_APP: "Reminder in the app", SCHEDULED: "Call scheduled",
  DISPATCHING: "Dialing", IN_CALL: "On a call", AWAITING_CUSTOMER: "Link sent, awaiting upload",
  BLOCKED: "Blocked by policy", PAUSED: "Paused by the banker", CANCELED: "Canceled", ESCALATED: "Passed to the banker", COMPLETED: "Completed",
};
const ACTION_EN: Record<string, string> = {
  NO_ACTION: "No action needed", IN_APP_ONLY: "In the app only", WAIT: "Wait", SUPPRESS: "No contact", IN_APP_NUDGE: "Reminder in the app",
  SCHEDULE_CALL: "Schedule a call", DISPATCH_NOW: "Contact now", BLOCK: "Blocked", RESOLVE_AND_CANCEL: "Resolved, follow-up canceled",
  ESCALATE: "Pass to the banker", SNOOZE: "Postponed at the customer's request",
};

/** The completion follow-up of one case for the banker: what is missing, what the engine decided and why (in Hebrew,
 *  with rule ids), every simulated JEEN Talk attempt and its outcome, and the timeline. Pause, resume and call-now go
 *  through the same guards as the engine. */
export function FollowupView({ caseId, readOnly }: { caseId: string; readOnly: boolean }) {
  const view = usePolling(() => followupApi.banker(caseId), [caseId], () => true);
  const tl = usePolling(() => followupApi.timeline(caseId, 80), [caseId], () => true);
  const [note, setNote] = useState<string | null>(null);
  const { en, t: tx } = useLang();
  const v = view.data;
  if (!v) return <div className="desk-loading"><span className="spinner" /> {tx("טוען…", "Loading…")}</div>;
  const d = v.decision;
  const paused = v.overrides.some((o) => o.active && (o.type === "pause" || o.type === "cancel"));
  const act = async (run: () => Promise<unknown>, done: string) => {
    setNote(null);
    try { await run(); setNote(done); } catch (e) { setNote((e as Error).message); }
    view.reload(); tl.reload();
  };
  return (
    <div className="desk-page" data-testid="followup-view">
      <div className="panel">
        <div className="row between wrap">
          <h3 style={{ margin: 0 }}>{tx("מעקב השלמה", "Completion follow-up")}</h3>
          <span className="row wrap" style={{ gap: 6 }}>
            <Chip tone="navy"><span data-testid="fu-plan-state" data-state={v.plan.state}>{(en ? PLAN_EN : PLAN_HE)[v.plan.state] || v.plan.state}</span></Chip>
            <Chip>{v.case_status}</Chip>
            {v.kill_switch && <Chip tone="bad">{tx("מתג חירום פעיל", "Kill switch active")}</Chip>}
            <span className="tiny muted ltr">{v.plan.policy_version}</span>
          </span>
        </div>
        {d && (
          <div className="fu-decision" data-testid="fu-decision" data-action={d.action}>
            <b>{(en ? ACTION_EN : ACTION_HE)[d.action] || d.action}</b> · {locOf(d, "explanation_he")}
            {d.next_eligible_at && <span className="small muted"> · {tx("פנייה אפשרית מ־", "Contact possible from ")}<span className="ltr">{timeL(d.next_eligible_at)}</span></span>}
            <div className="fu-rules">{d.rule_ids.map((id) => <span key={id} className={`chip ${d.blocked_by.includes(id) ? "bad" : ""}`}><span className="ltr">{id}</span></span>)}</div>
          </div>
        )}
        {!readOnly && (
          <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
            {paused ? <button className="btn btn-ghost btn-sm" data-testid="fu-resume" onClick={() => act(() => followupApi.override(caseId, "resume", "חידוש המעקב מהקונסולה"), tx("המעקב חודש.", "The follow-up was resumed."))}>{tx("חידוש המעקב", "Resume the follow-up")}</button>
              : <button className="btn btn-ghost btn-sm" data-testid="fu-pause" onClick={() => act(() => followupApi.override(caseId, "pause", "השהיה ידנית מהקונסולה"), tx("המעקב הושהה, אין פניות עד לחידוש.", "The follow-up is paused; no contact until it's resumed."))}>{tx("השהיית המעקב", "Pause the follow-up")}</button>}
            <button className="btn btn-ghost btn-sm" data-testid="fu-call-now" onClick={() => act(() => followupApi.callNow(caseId, "שיחה יזומה מהקונסולה"), tx("השיחה יצאה.", "The call went out."))}>{tx("שיחה עכשיו", "Call now")}</button>
          </div>
        )}
        {note && <div className="small" role="status" style={{ marginTop: 6 }} data-testid="fu-note">{note}</div>}
      </div>
      <div className="grid2">
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>{tx("מה חסר, דרישות השלמה", "What's missing — completion requirements")} ({v.tasks.length})</h3>
          <table className="t" data-testid="fu-tasks"><thead><tr><th>{tx("דרישה", "Requirement")}</th><th>{tx("סיבה", "Reason")}</th><th>{tx("מצב", "Status")}</th><th>{tx("נפתחה", "Opened")}</th><th>{tx("נסגרה", "Closed")}</th></tr></thead>
            <tbody>{v.tasks.map((t) => (
              <tr key={t.task_id} data-status={t.status}><td className="tiny">{locOf(t, "title_he")}<div className="muted ltr">{t.requirement_code}</div></td>
                <td className="tiny ltr">{t.reason_code}</td><td className="tiny">{(en ? TASK_EN : TASK_HE)[t.status] || t.status}</td>
                <td className="tiny ltr">{timeL(t.created_at)}</td><td className="tiny ltr">{t.resolved_at ? timeL(t.resolved_at) : "-"}</td></tr>))}</tbody></table>
          <h3 style={{ marginTop: 14 }}>{tx("פניות", "Contacts")} ({v.attempts.length})</h3>
          {v.attempts.length === 0 ? <div className="small muted">{tx("לא נוצרה פנייה.", "No contact was made.")}</div> : (
            <table className="t" data-testid="fu-attempts"><thead><tr><th>{tx("זמן", "Time")}</th><th>{tx("ערוץ", "Channel")}</th><th>{tx("ספק", "Provider")}</th><th>{tx("מצב", "Status")}</th><th>{tx("תוצאה", "Outcome")}</th></tr></thead>
              <tbody>{v.attempts.map((a) => (
                <tr key={a.attempt_id}><td className="tiny ltr">{timeL(a.created_at)}</td><td className="tiny">{a.channel === "voice" ? tx("שיחה", "Call") : tx("הודעה", "Message")}</td>
                  <td className="tiny ltr">{a.provider}</td><td className="tiny ltr">{a.status}</td>
                  <td className="tiny" data-testid="fu-attempt-outcome">{a.outcome ? (en ? OUTCOME_EN : OUTCOME_HE)[a.outcome] || a.outcome : "-"}{a.link_id ? tx(" · קישור מאובטח", " · secure link") : ""}</td></tr>))}</tbody></table>
          )}
        </div>
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>{tx("ציר הזמן", "Timeline")}</h3>
          <div data-testid="fu-timeline">
            {(tl.data || []).length === 0 && <div className="small muted">{tx("אין עדיין אירועים.", "No events yet.")}</div>}
            {[...(tl.data || [])].reverse().map((e, i) => (
              <div key={`${e.at}-${i}`} className="fu-event" data-type={e.type}>
                <span className="tiny muted ltr">{timeL(e.at)}</span> <span className="small">{locOf(e, "summary_he")}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
