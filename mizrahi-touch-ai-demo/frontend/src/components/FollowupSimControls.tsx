import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { timeL } from "../api";
import { useCase } from "../caseContext";
import { actionL, followupApi, planL, type FollowupDecision, type SentLink } from "../followupApi";
import { Loc, tr, useLang } from "../i18n";

/** Presenter controls for the follow-up demo on the case open on the right: the customer leaves, the demo clock moves,
 *  the engine runs, the simulated JEEN Talk call ends with an outcome, and the secure link it sent can be opened. All
 *  of it is simulation: no real call, and the decisions are the engine's own (shown with their reason). */
export function FollowupSimControls() {
  const { caseId, reload } = useCase();
  const { t } = useLang();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [line, setLine] = useState<ReactNode>(null);
  const [links, setLinks] = useState<SentLink[]>([]);
  const say = (d: FollowupDecision | undefined, prefix: string) =>
    setLine(d ? <>{`${prefix} ${actionL(d.action)} · `}<Loc he={d.explanation_he} en={d.explanation_en} />
      {d.next_eligible_at ? tr(` · פנייה אפשרית מ־${timeL(d.next_eligible_at)}`, ` · contact possible from ${timeL(d.next_eligible_at)}`) : ""}</> : prefix);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try { await fn(); } catch (e) { setLine((e as Error).message); } finally { setBusy(false); reload(); }
  };
  const state = async () => {
    const v = await followupApi.banker(caseId);
    say(v.decision || undefined, tr(`מצב: ${planL(v.plan.state)} ·`, `State: ${planL(v.plan.state)} ·`));
    setLinks((await followupApi.demo.sentLinks(caseId)).links);
  };
  const outcomes = [["LINK_SENT", "נשלח קישור", "Link sent"], ["NO_ANSWER", "אין מענה", "No answer"],
    ["CALLBACK_REQUESTED", "לחזור אליי", "Call me back"]] as const;
  return (
    <details className="all-scn fu-sim" data-testid="followup-sim">
      <summary><span className="all-scn-title">{t("מעקב השלמה · הפעלה ידנית", "Completion follow-up · manual control")}</span>
        <span className="small muted">{t("על התיק שפתוח מימין", "On the case open on the right")}</span></summary>
      <div className="fu-sim-body">
        <div className="row wrap" style={{ gap: 6 }}>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-customer-left"
            onClick={() => run(async () => { const r = await followupApi.demo.customerLeft(caseId); say(r.decision, tr("הלקוח עזב ·", "The customer left ·")); })}>{t("הלקוח עזב", "The customer left")}</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-clock-20"
            onClick={() => run(async () => { const r = await followupApi.demo.clock({ advance_minutes: 20 }); await followupApi.demo.tick(); setLine(tr(`השעון: ${timeL(r.now)}`, `Clock: ${timeL(r.now)}`)); await state(); })}>{t("+20 דק׳ והרצה", "+20 min and run")}</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-next-window"
            onClick={() => run(async () => { await followupApi.demo.clock({ to_next_window: true }); await followupApi.demo.tick(); await state(); })}>{t("לחלון השיחות הבא", "To the next call window")}</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} data-testid="sim-tick"
            onClick={() => run(async () => { await followupApi.demo.tick(); await state(); })}>{t("הרצת המנוע", "Run the engine")}</button>
        </div>
        <div className="row wrap" style={{ gap: 6, marginTop: 6 }}>
          <span className="tiny muted">{t("תוצאת השיחה:", "Call outcome:")}</span>
          {outcomes.map(([o, he, en]) => (
            <button key={o} className="btn btn-ghost btn-sm" disabled={busy} data-testid={`sim-outcome-${o}`}
              onClick={() => run(async () => { const r = await followupApi.demo.talkOutcome(caseId, o); setLine(tr(`השיחה הסתיימה: ${he} · ${planL(r.plan_state)}`, `The call ended: ${en} · ${planL(r.plan_state)}`)); setLinks((await followupApi.demo.sentLinks(caseId)).links); })}>{t(he, en)}</button>
          ))}
          <button className="link small" disabled={busy} onClick={() => run(state)} data-testid="sim-refresh">{t("מצב נוכחי", "Current state")}</button>
        </div>
        {line && <div className="small fu-sim-line" role="status" data-testid="sim-line">{line}</div>}
        {links.filter((l) => l.url && l.state === "ok").map((l) => (
          <button key={l.link_id} className="btn btn-dark btn-sm" style={{ marginTop: 6 }} data-testid="sim-open-link"
            onClick={() => nav(`/customer/link#t=${l.token}`)}>{t("פתיחת הקישור המאובטח שנשלח ללקוח", "Open the secure link sent to the customer")}</button>
        ))}
        <button className="link tiny" style={{ marginTop: 6 }} disabled={busy} data-testid="sim-clock-reset"
          onClick={() => run(async () => { await followupApi.demo.clock({ reset: true }); setLine(tr("השעון אופס.", "The clock was reset.")); })}>{t("איפוס השעון", "Reset the clock")}</button>
      </div>
    </details>
  );
}
