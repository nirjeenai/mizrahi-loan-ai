import { useState } from "react";
import { timeHe, usePolling } from "../../api";
import { ACTION_HE, followupApi, PLAN_HE } from "../../followupApi";
import { Chip } from "./deskUi";

const TASK_HE: Record<string, string> = { OPEN: "פתוחה", RESOLVED: "נפתרה — מסמך חדש עבר בדיקה", CANCELED: "בוטלה",
  PAUSED_BY_BANKER: "מושהית ע״י הבנקאי", PAUSED_BY_CUSTOMER: "נדחתה לבקשת הלקוח", POLICY_BLOCKED: "חסומה לפי מדיניות" };
const OUTCOME_HE: Record<string, string> = { LINK_SENT: "נשלח קישור להשלמה", CALLBACK_REQUESTED: "הלקוח ביקש שיחה חוזרת",
  REFUSED: "הלקוח סירב", HUMAN_REQUESTED: "הלקוח ביקש נציג", NO_ANSWER: "אין מענה", IDENTITY_FAILED: "זיהוי נכשל",
  COMPLETED_NO_ACTION: "הסתיימה ללא פעולה" };

/** The completion follow-up of one case for the banker: what is missing, what the engine decided and why (in Hebrew,
 *  with rule ids), every simulated JEEN Talk attempt and its outcome, and the timeline. Pause, resume and call-now go
 *  through the same guards as the engine. */
export function FollowupView({ caseId, readOnly }: { caseId: string; readOnly: boolean }) {
  const view = usePolling(() => followupApi.banker(caseId), [caseId], () => true);
  const tl = usePolling(() => followupApi.timeline(caseId, 80), [caseId], () => true);
  const [note, setNote] = useState<string | null>(null);
  const v = view.data;
  if (!v) return <div className="desk-loading"><span className="spinner" /> טוען…</div>;
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
          <h3 style={{ margin: 0 }}>מעקב השלמה</h3>
          <span className="row wrap" style={{ gap: 6 }}>
            <Chip tone="navy"><span data-testid="fu-plan-state" data-state={v.plan.state}>{PLAN_HE[v.plan.state] || v.plan.state}</span></Chip>
            <Chip>{v.case_status}</Chip>
            {v.simulated && <Chip tone="info">JEEN Talk מדומה — ללא חיוג</Chip>}
            {v.kill_switch && <Chip tone="bad">מתג חירום פעיל</Chip>}
            <span className="tiny muted ltr">{v.plan.policy_version}</span>
          </span>
        </div>
        {d && (
          <div className="fu-decision" data-testid="fu-decision" data-action={d.action}>
            <b>{ACTION_HE[d.action] || d.action}</b> · {d.explanation_he}
            {d.next_eligible_at && <span className="small muted"> · פנייה אפשרית מ־<span className="ltr">{timeHe(d.next_eligible_at)}</span></span>}
            <div className="fu-rules">{d.rule_ids.map((id) => <span key={id} className={`chip ${d.blocked_by.includes(id) ? "bad" : ""}`}><span className="ltr">{id}</span></span>)}</div>
          </div>
        )}
        {!readOnly && (
          <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
            {paused ? <button className="btn btn-ghost btn-sm" data-testid="fu-resume" onClick={() => act(() => followupApi.override(caseId, "resume", "חידוש המעקב מהקונסולה"), "המעקב חודש.")}>חידוש המעקב</button>
              : <button className="btn btn-ghost btn-sm" data-testid="fu-pause" onClick={() => act(() => followupApi.override(caseId, "pause", "השהיה ידנית מהקונסולה"), "המעקב הושהה — אין פניות עד לחידוש.")}>השהיית המעקב</button>}
            <button className="btn btn-ghost btn-sm" data-testid="fu-call-now" onClick={() => act(() => followupApi.callNow(caseId, "שיחה יזומה מהקונסולה"), "השיחה המדומה יצאה.")}>שיחה עכשיו (מדומה)</button>
          </div>
        )}
        {note && <div className="small" role="status" style={{ marginTop: 6 }} data-testid="fu-note">{note}</div>}
      </div>
      <div className="grid2">
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>מה חסר — דרישות השלמה ({v.tasks.length})</h3>
          <table className="t" data-testid="fu-tasks"><thead><tr><th>דרישה</th><th>סיבה</th><th>מצב</th><th>נפתחה</th><th>נסגרה</th></tr></thead>
            <tbody>{v.tasks.map((t) => (
              <tr key={t.task_id} data-status={t.status}><td className="tiny">{t.title_he}<div className="muted ltr">{t.requirement_code}</div></td>
                <td className="tiny ltr">{t.reason_code}</td><td className="tiny">{TASK_HE[t.status] || t.status}</td>
                <td className="tiny ltr">{timeHe(t.created_at)}</td><td className="tiny ltr">{t.resolved_at ? timeHe(t.resolved_at) : "—"}</td></tr>))}</tbody></table>
          <h3 style={{ marginTop: 14 }}>פניות ({v.attempts.length})</h3>
          {v.attempts.length === 0 ? <div className="small muted">לא נוצרה פנייה.</div> : (
            <table className="t" data-testid="fu-attempts"><thead><tr><th>זמן</th><th>ערוץ</th><th>ספק</th><th>מצב</th><th>תוצאה</th></tr></thead>
              <tbody>{v.attempts.map((a) => (
                <tr key={a.attempt_id}><td className="tiny ltr">{timeHe(a.created_at)}</td><td className="tiny">{a.channel === "voice" ? "שיחה" : "הודעה"}</td>
                  <td className="tiny ltr">{a.provider}{a.simulated ? " · סימולציה" : ""}</td><td className="tiny ltr">{a.status}</td>
                  <td className="tiny" data-testid="fu-attempt-outcome">{a.outcome ? OUTCOME_HE[a.outcome] || a.outcome : "—"}{a.link_id ? " · קישור מאובטח" : ""}</td></tr>))}</tbody></table>
          )}
        </div>
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>ציר הזמן</h3>
          <div data-testid="fu-timeline">
            {(tl.data || []).length === 0 && <div className="small muted">אין עדיין אירועים.</div>}
            {[...(tl.data || [])].reverse().map((e, i) => (
              <div key={`${e.at}-${i}`} className="fu-event" data-type={e.type}>
                <span className="tiny muted ltr">{timeHe(e.at)}</span> <span className="small">{e.summary_he}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
