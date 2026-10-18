import { useEffect, useState } from "react";
import { useCase } from "../caseContext";
import { followupApi, type CustomerFollowup } from "../followupApi";
import { localeL } from "../api";
import { useLang } from "../i18n";
import { IClock } from "./Icons";

const QUIET = "אפשר להשלים את המסמכים כאן באפליקציה";

/** The completion follow-up as the customer sees it — only when there is something to say: an in-app reminder, a
 *  scheduled (simulated) call, a link that was sent, or a snooze. Two light controls: remind later, no phone calls. */
export function FollowupNotice() {
  const { caseId, snap } = useCase();
  const [view, setView] = useState<CustomerFollowup | null>(null);
  const [busy, setBusy] = useState(false);
  const { en, t } = useLang();
  useEffect(() => { followupApi.customer(caseId).then(setView).catch(() => setView(null)); }, [caseId, snap]);
  if (!view || (!view.nudge && view.state_he === QUIET && !view.snooze_until) || !view.open_items.length) return null;
  const act = async (run: () => Promise<CustomerFollowup>) => {
    setBusy(true);
    try { setView(await run()); } finally { setBusy(false); }
  };
  const until = view.snooze_until ? new Date(view.snooze_until).toLocaleTimeString(localeL(), { hour: "2-digit", minute: "2-digit" }) : null;
  const line = en ? (view.nudge && view.nudge_text_he ? view.nudge_text_en || view.nudge_text_he : view.state_en || view.state_he)
    : view.nudge && view.nudge_text_he ? view.nudge_text_he : view.state_he;
  return (
    <section className="card fu-note" data-testid="followup-notice" aria-live="polite">
      <div className="fu-head"><span className="fu-ic" aria-hidden><IClock size={16} /></span>
        <span className="grow"><b data-testid="followup-state">{line}</b></span></div>
      {until && <div className="small muted" data-testid="followup-snoozed">{en ? <>We won&apos;t contact you until {until}.</> : <>לא ניצור קשר עד {until}.</>}</div>}
      <div className="fu-actions">
        {!until && <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act(() => followupApi.snooze(caseId, 60))}
          data-testid="followup-snooze">{t("להזכיר בעוד שעה", "Remind me in an hour")}</button>}
        {view.contact.voice_allowed && <button className="btn btn-ghost btn-sm" disabled={busy}
          onClick={() => act(() => followupApi.preferences(caseId, { opt_out_voice: true }))} data-testid="followup-no-calls">{t("בלי שיחות טלפון", "No phone calls")}</button>}
      </div>
    </section>
  );
}
