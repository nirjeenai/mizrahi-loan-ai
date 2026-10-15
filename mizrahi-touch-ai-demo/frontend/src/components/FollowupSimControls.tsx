import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { timeHe } from "../api";
import { useCase } from "../caseContext";
import { ACTION_HE, followupApi, PLAN_HE, type FollowupDecision, type SentLink } from "../followupApi";

/** Presenter controls for the follow-up demo on the case open on the right: the customer leaves, the demo clock moves,
 *  the engine runs, the simulated JEEN Talk call ends with an outcome, and the secure link it sent can be opened. All
 *  of it is simulation: no real call, and the decisions are the engine's own (shown with their reason). */
export function FollowupSimControls() {
  const { caseId, reload } = useCase();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [line, setLine] = useState<string | null>(null);
  const [links, setLinks] = useState<SentLink[]>([]);
  const say = (d: FollowupDecision | undefined, prefix: string) =>
    setLine(d ? `${prefix} ${ACTION_HE[d.action] || d.action} · ${d.explanation_he}${d.next_eligible_at ? ` · פנייה אפשרית מ־${timeHe(d.next_eligible_at)}` : ""}` : prefix);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try { await fn(); } catch (e) { setLine((e as Error).message); } finally { setBusy(false); reload(); }
  };
  const state = async () => {
    const v = await followupApi.banker(caseId);
    say(v.decision || undefined, `מצב: ${PLAN_HE[v.plan.state] || v.plan.state} ·`);
    setLinks((await followupApi.demo.sentLinks(caseId)).links);
  };
  return (
    <details className="all-scn fu-sim" data-testid="followup-sim">
      <summary><span className="all-scn-title">סימולציית מעקב השלמה</span>
        <span className="small muted">על התיק שפתוח מימין</span></summary>
      <div className="fu-sim-body">
        <div className="row wrap" style={{ gap: 6 }}>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-customer-left"
            onClick={() => run(async () => { const r = await followupApi.demo.customerLeft(caseId); say(r.decision, "הלקוח עזב ·"); })}>הלקוח עזב</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-clock-20"
            onClick={() => run(async () => { const r = await followupApi.demo.clock({ advance_minutes: 20 }); await followupApi.demo.tick(); setLine(`השעון: ${timeHe(r.now)}`); await state(); })}>+20 דק׳ והרצה</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-next-window"
            onClick={() => run(async () => { await followupApi.demo.clock({ to_next_window: true }); await followupApi.demo.tick(); await state(); })}>לחלון השיחות הבא</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-tick"
            onClick={() => run(async () => { await followupApi.demo.tick(); await state(); })}>הרצת המנוע</button>
        </div>
        <div className="row wrap" style={{ gap: 6, marginTop: 6 }}>
          <span className="tiny muted">תוצאת השיחה:</span>
          {([["LINK_SENT", "נשלח קישור"], ["NO_ANSWER", "אין מענה"], ["CALLBACK_REQUESTED", "לחזור אליי"]] as const).map(([o, he]) => (
            <button key={o} className="btn btn-ghost btn-sm" disabled={busy} data-testid={`sim-outcome-${o}`}
              onClick={() => run(async () => { const r = await followupApi.demo.talkOutcome(caseId, o); setLine(`השיחה הסתיימה: ${he} · ${PLAN_HE[r.plan_state] || r.plan_state}`); setLinks((await followupApi.demo.sentLinks(caseId)).links); })}>{he}</button>
          ))}
          <button className="link small" disabled={busy} onClick={() => run(state)} data-testid="sim-refresh">מצב נוכחי</button>
        </div>
        {line && <div className="small fu-sim-line" role="status" data-testid="sim-line">{line}</div>}
        {links.filter((l) => l.url && l.state === "ok").map((l) => (
          <button key={l.link_id} className="btn btn-dark btn-sm" style={{ marginTop: 6 }} data-testid="sim-open-link"
            onClick={() => nav(`/customer/link#t=${l.token}`)}>פתיחת הקישור המאובטח שנשלח ללקוח</button>
        ))}
        <button className="link tiny" style={{ marginTop: 6 }} disabled={busy} data-testid="sim-clock-reset"
          onClick={() => run(async () => { await followupApi.demo.clock({ reset: true }); setLine("השעון אופס."); })}>איפוס השעון</button>
      </div>
    </details>
  );
}
