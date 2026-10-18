import { useState, type CSSProperties, type ReactNode } from "react";
import { IPhone } from "../../components/Icons";
import { useLang } from "../../i18n";
import { derive, mmss, pct, sum, totals, VARIANTS, type Variant } from "./insightsData";
import "./insightsV2.css";

/** Dashboard V2 of "ביצועים ותובנות": the same synthetic dataset as V1 (insightsData.ts), a different presentation. */

const SCALE = 0.6;
const GRID = [0, 0.2, 0.4, 0.6];
const n = (x: number) => <bdi className="ins2-num">{x.toLocaleString("he-IL")}</bdi>;
const p = (x: number) => <bdi className="ins2-num">{pct(x)}</bdi>;
const width = (part: number, whole: number): CSSProperties => ({ width: `${(part / whole) * 100}%` });
const height = (rate: number): CSSProperties => ({ height: `${(rate / SCALE) * 100}%` });

export function InsightsV2({ activeGrace, activeVersion }: { activeGrace?: number; activeVersion?: number }) {
  const leader = VARIANTS.reduce((a, b) => (derive(b).readyRate > derive(a).readyRate ? b : a));
  const [sel, setSel] = useState<Variant["id"]>(leader.id);
  const [showReturn, setShowReturn] = useState(false);
  const v = VARIANTS.find((x) => x.id === sel)!;
  const { en, t } = useLang();
  const tot = totals();
  const returned = sum(tot.returned), ready = sum(tot.ready);
  const others = VARIANTS.filter((x) => x.id !== leader.id);

  return (
    <div className="ins2" data-testid="tab-body-insights" data-dash="v2">
      <header className="ins2-head">
        <div>
          <div className="ins2-eyebrow">Jeen · {t("מעקב השלמת מסמכים בבקשת הלוואה", "Document completion follow-up in a loan application")}</div>
          <h1>{t("מבקשה שנעצרה בגלל מסמך, לתיק שמוכן לבנקאי", "From an application stopped by a document to a case ready for the banker")}</h1>
        </div>
      </header>

      <section className="ins2-hero" aria-label={t("המסלול של כל הבקשות שנעצרו, כל הגרסאות יחד", "The path of every stopped application, all variants together")}>
        <Stage tone="neutral" label={t("בקשות שנעצרו במסמך", "Applications stopped by a document")} value={tot.cases} share={1} testId="kpi-cases"
          note={t("מסמך חסר, שגוי או לא ברור", "A missing, wrong or unclear document")} />
        <Step rate={returned / tot.cases} text={t("חזרו", "came back")} />
        <Stage tone="return" label={t("חזרו לתהליך", "Came back to the process")} value={returned} share={returned / tot.cases} testId="kpi-returned"
          note={<Split tone="return" self={tot.returned.self} call={tot.returned.call} />} />
        <Step rate={ready / returned} text={t("מהחוזרים מוכנים", "of returners are ready")} />
        <Stage tone="ready" lead label={t("מוכנים לבדיקת בנקאי", "Ready for banker review")} value={ready} share={ready / tot.cases} testId="kpi-ready"
          note={<><span className="ins2-stage-rate">{p(ready / tot.cases)} {t("מכל הבקשות שנעצרו", "of all stopped applications")}</span><Split tone="ready" self={tot.ready.self} call={tot.ready.call} /></>} />
        <div className="ins2-friction" data-testid="kpi-unanswered">
          <span className="ins2-friction-label"><IPhone size={13} /> {t("שיחות שלא נענו", "Unanswered calls")}</span>
          <span className="ins2-friction-value">{p(tot.unanswered / tot.attempts)}</span>
          <span className="ins2-friction-note">{t(<>{n(tot.unanswered)} מתוך {n(tot.attempts)} ניסיונות שיחה</>, <>{n(tot.unanswered)} of {n(tot.attempts)} call attempts</>)}</span>
          <span className="ins2-down">{t("▼ רצוי נמוך", "▼ lower is better")}</span>
        </div>
      </section>

      <section className="ins2-main">
        <div className="ins2-card ins2-compare" data-testid="policy-compare">
          <div className="ins2-kicker">{t("השוואת מדיניות מעקב · כמה זמן לחכות לפני שיחה", "Follow-up policy comparison · how long to wait before a call")}</div>
          {en ? <h2 className="ins2-headline" data-testid="insight">
            A {n(leader.graceMinutes)}-minute wait leads: <em>{p(derive(leader).readyRate)}</em> of applications ready for the banker
          </h2> : <h2 className="ins2-headline" data-testid="insight">
            המתנה של {n(leader.graceMinutes)} דקות מובילה: <em>{p(derive(leader).readyRate)}</em> מהבקשות מוכנות לבנקאי
          </h2>}
          {en ? <p className="ins2-caveat">
            Compared with {others.map((o, i) => <span key={o.id}>{i ? " and " : ""}{p(derive(o).readyRate)} at {n(o.graceMinutes)} minutes</span>)}.
            {" "}Everything is identical except the wait time, and a controlled experiment is needed to establish whether timing is the cause.
          </p> : <p className="ins2-caveat">
            לעומת {others.map((o, i) => <span key={o.id}>{i ? " ו־" : ""}{p(derive(o).readyRate)} ב־{n(o.graceMinutes)} דקות</span>)}.
            {" "}הכול זהה מלבד זמן ההמתנה, ונדרש ניסוי מבוקר כדי לקבוע אם התזמון הוא הגורם.
          </p>}
          <div className="ins2-chart">
            <div className="ins2-grid" aria-hidden>
              {GRID.map((g) => <span key={g} style={{ bottom: `${(g / SCALE) * 100}%` }}><i>{pct(g, 0)}</i></span>)}
            </div>
            <div className="ins2-cols" role="radiogroup" aria-label={t("גרסאות מדיניות המעקב", "Follow-up policy variants")}>
              {VARIANTS.map((x) => (
                <Column key={x.id} v={x} on={x.id === sel} best={x.id === leader.id} showReturn={showReturn} onPick={() => setSel(x.id)}
                  active={activeGrace === x.graceMinutes ? activeVersion : undefined} />
              ))}
            </div>
          </div>
          <div className="ins2-chart-foot">
            <span className="ins2-key"><i className="ins2-sw ready" />{t("מוכנים לבדיקת בנקאי", "Ready for banker review")}</span>
            {showReturn && <span className="ins2-key"><i className="ins2-sw return-ghost" />{t("חזרו לתהליך", "Came back to the process")}</span>}
            <label className="ins2-toggle">
              <input type="checkbox" checked={showReturn} onChange={(e) => setShowReturn(e.target.checked)} data-testid="toggle-returned" />
              {t("הצגת שיעור החזרה לתהליך", "Show the return rate")}
            </label>
            <span className="ins2-hint">{t("בחרו עמודה כדי לראות את המסלול שלה", "Pick a column to see its path")}</span>
          </div>
        </div>

        <Journey v={v} />
      </section>
    </div>
  );
}

function Split({ tone, self, call }: { tone: "return" | "ready"; self: number; call: number }) {
  const { t } = useLang();
  return (
    <span className="ins2-split">
      <span><i className={`ins2-sw ${tone}`} />{n(self)} {t("בלי פנייה", "with no contact")}</span>
      <span><i className={`ins2-sw ${tone} call`} /><IPhone size={11} />{n(call)} {t("אחרי שיחה", "after a call")}</span>
    </span>
  );
}

function Stage({ tone, label, value, share, note, lead, testId }: {
  tone: "neutral" | "return" | "ready"; label: string; value: number; share: number; note: ReactNode; lead?: boolean; testId: string;
}) {
  return (
    <div className={`ins2-stage ${tone}${lead ? " lead" : ""}`} data-testid={testId}>
      <span className="ins2-stage-label">{label}</span>
      <span className="ins2-stage-value">{n(value)}</span>
      <span className="ins2-meter" aria-hidden><span style={{ width: `${share * 100}%` }} /></span>
      <span className="ins2-stage-note">{note}</span>
    </div>
  );
}

function Step({ rate, text }: { rate: number; text: string }) {
  return (
    <div className="ins2-step" aria-label={`${pct(rate)} ${text}`}>
      <span className="ins2-step-rate">{p(rate)}</span>
      <span className="ins2-step-text">{text}</span>
      <span className="ins2-step-arrow" aria-hidden />
    </div>
  );
}

function Column({ v, on, best, active, showReturn, onPick }: {
  v: Variant; on: boolean; best: boolean; active?: number; showReturn: boolean; onPick: () => void;
}) {
  const { t } = useLang();
  const d = derive(v);
  return (
    <button type="button" role="radio" aria-checked={on} className={`ins2-col${on ? " on" : ""}${best ? " best" : ""}`} onClick={onPick}
      data-testid={`variant-${v.id}`}
      aria-label={t(`${v.graceMinutes} דקות המתנה: ${d.ready} מתוך ${v.cases} מוכנים לבנקאי (${pct(d.readyRate)}), ${d.returned} חזרו (${pct(d.returnRate)})`,
        `${v.graceMinutes}-minute wait: ${d.ready} of ${v.cases} ready for the banker (${pct(d.readyRate)}), ${d.returned} came back (${pct(d.returnRate)})`)}>
      <span className="ins2-plot">
        {showReturn && (
          <span className="ins2-bar return-ghost" style={height(d.returnRate)} data-testid={`returned-${v.id}`}>
            <span className="ins2-bar-tag">{t("חזרו", "Came back")} {p(d.returnRate)}</span>
          </span>
        )}
        <span className={`ins2-bar ready${showReturn ? " narrow" : ""}`} style={height(d.readyRate)}>
          <span className="ins2-bar-value">
            {best && <span className="ins2-best">{t("הגבוה בהמחשה", "Highest in the illustration")}</span>}
            {p(d.readyRate)}
          </span>
        </span>
      </span>
      <span className="ins2-col-label">
        <span className="ins2-col-grace"><bdi className="ins2-num">{v.graceMinutes}</bdi> {t("דק׳ המתנה", "min wait")}</span>
        <span className="ins2-col-of">{t(<>{n(d.ready)} מתוך {n(v.cases)} מוכנים</>, <>{n(d.ready)} of {n(v.cases)} ready</>)}</span>
        {active !== undefined && <span className="ins2-active" title={t("זמן ההמתנה בגרסה הפעילה של מדיניות המעקב", "The wait time in the active version of the follow-up policy")}>{t("כמו המדיניות הפעילה", "Same as the active policy")} · v{active}</span>}
      </span>
    </button>
  );
}

function Journey({ v }: { v: Variant }) {
  const { t } = useLang();
  const d = derive(v);
  const rows = [
    { label: t("נעצרו במסמך", "Stopped by a document"), tone: "neutral", total: v.cases, lane: null, rate: null },
    { label: t("חזרו לתהליך", "Came back to the process"), tone: "return", total: d.returned, lane: v.returned, rate: d.returnRate },
    { label: t("השלימו את המסמכים", "Completed the documents"), tone: "return", total: d.uploaded, lane: v.uploaded, rate: null },
    { label: t("מוכנים לבדיקת בנקאי", "Ready for banker review"), tone: "ready", total: d.ready, lane: v.ready, rate: d.readyRate },
  ];
  return (
    <div className="ins2-card ins2-journey" data-testid="journey" aria-live="polite">
      <div className="ins2-kicker">{t("המסלול בגרסה הנבחרת", "The path in the selected variant")}</div>
      <h2 className="ins2-journey-title"><bdi className="ins2-num">{v.graceMinutes}</bdi> {t("דק׳ המתנה", "min wait")} <small>· {n(v.cases)} {t("בקשות שנעצרו", "stopped applications")}</small></h2>
      <ol className="ins2-funnel">
        {rows.map((r, i) => (
          <li key={r.label} className={r.tone} data-testid={`step-${i + 1}`}>
            <span className="ins2-funnel-label">{r.label}</span>
            <span className="ins2-funnel-track">
              {r.lane ? <>
                <span className={`ins2-fill ${r.tone}`} style={width(r.lane.self, v.cases)} title={`${t("בלי פנייה", "With no contact")}: ${r.lane.self}`} />
                <span className={`ins2-fill ${r.tone} call`} style={width(r.lane.call, v.cases)} title={`${t("אחרי שיחה", "After a call")}: ${r.lane.call}`} />
              </> : <span className={`ins2-fill ${r.tone}`} style={width(r.total, v.cases)} />}
            </span>
            <span className="ins2-funnel-value">{n(r.total)}{r.rate !== null && <small>{p(r.rate)}</small>}</span>
          </li>
        ))}
      </ol>
      <div className="ins2-paths" data-testid="self-share">
        <div className="ins2-path">
          <span className="ins2-path-head"><i className="ins2-sw ready" />{t("בלי שום פנייה", "With no contact at all")}</span>
          <span className="ins2-path-value">{n(v.ready.self)}</span>
          <span className="ins2-path-note">{t(<>מוכנים לבנקאי · {n(v.returned.self)} חזרו בזמן ההמתנה</>, <>ready for the banker · {n(v.returned.self)} came back during the wait</>)}</span>
        </div>
        <div className="ins2-path">
          <span className="ins2-path-head"><i className="ins2-sw ready call" /><IPhone size={12} />{t("אחרי שיחה", "After a call")}</span>
          <span className="ins2-path-value">{n(v.ready.call)}</span>
          <span className="ins2-path-note">{t(<>מוכנים לבנקאי · מתוך {n(d.contacted)} שקיבלו פנייה</>, <>ready for the banker · of {n(d.contacted)} who were contacted</>)}</span>
        </div>
      </div>
      <dl className="ins2-contact" aria-label={t("אירועי שיחה בגרסה זו", "Call events in this variant")}>
        <div><dt>{t("פניות שנחסכו", "Contacts saved")}</dt><dd>{n(v.returned.self)}</dd></div>
        <div className="bad"><dt>{t("שיחות שלא נענו", "Unanswered calls")} <span className="ins2-down">▼</span></dt><dd>{p(d.unanswered / v.calls.attempts)}</dd></div>
        <div><dt>{t("ניסיונות שיחה", "Call attempts")}</dt><dd>{n(v.calls.attempts)}</dd></div>
        <div><dt>{t("משך שיחה ממוצע", "Average call length")}</dt><dd><bdi className="ins2-num">{mmss(v.calls.avgSeconds)}</bdi></dd></div>
      </dl>
      <p className="ins2-question"><b>{t("שאלה לבדיקה:", "Question to test:")}</b> {t(v.question, v.questionEn)}</p>
    </div>
  );
}
