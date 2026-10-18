import { useState, type CSSProperties, type ReactNode } from "react";
import { IBulb, IChevron, IPhone } from "../../components/Icons";
import { tr, useLang } from "../../i18n";
import { derive, mmss, pct, problems, sum, totals, VARIANTS, type Lane, type Variant } from "./insightsData";

if (import.meta.env.DEV && problems().length) console.error("insightsData does not reconcile:", problems());

const n = (x: number) => <bdi className="ins-num">{x.toLocaleString("he-IL")}</bdi>;
const p = (x: number, digits = 1) => <bdi className="ins-num">{pct(x, digits)}</bdi>;
const w = (part: number, whole: number): CSSProperties => ({ width: `${(part / whole) * 100}%` });

/** Observation for one variant, worded as what the illustration shows, never as a cause. */
function observe(v: Variant): ReactNode {
  const d = derive(v);
  if (tr(false, true)) {
    if (v.id === "A") return <>{n(d.contacted)} of the {n(v.cases)} cases reached a call, and {p(d.unanswered / v.calls.attempts)} of the calls went unanswered.</>;
    if (v.id === "B") return <>{n(v.returned.self)} customers came back on their own before a contact was needed, and {p(v.calls.answered / v.calls.attempts)} of the calls were answered.</>;
    return <>{n(v.returned.self)} customers came back on their own, but the calls brought back only {n(v.returned.call)} of the {n(d.contacted)} customers who were contacted.</>;
  }
  if (v.id === "A") return <>{n(d.contacted)} מתוך {n(v.cases)} התיקים הגיעו לשיחה, ו־{p(d.unanswered / v.calls.attempts)} מהשיחות לא נענו.</>;
  if (v.id === "B") return <>{n(v.returned.self)} לקוחות חזרו בעצמם לפני שנדרשה פנייה, ו־{p(v.calls.answered / v.calls.attempts)} מהשיחות נענו.</>;
  return <>{n(v.returned.self)} לקוחות חזרו בעצמם, אבל השיחות החזירו רק {n(v.returned.call)} מתוך {n(d.contacted)} הלקוחות שקיבלו פנייה.</>;
}

export function InsightsTab({ activeGrace, activeVersion }: { activeGrace?: number; activeVersion?: number }) {
  const { en, t } = useLang();
  const leader = VARIANTS.reduce((a, b) => (derive(b).readyRate > derive(a).readyRate ? b : a));
  const [sel, setSel] = useState<Variant["id"]>(leader.id);
  const v = VARIANTS.find((x) => x.id === sel)!;
  const tot = totals();
  const returned = sum(tot.returned), ready = sum(tot.ready);
  const others = VARIANTS.filter((x) => x.id !== leader.id);

  return (
    <div className="ins" data-testid="tab-body-insights">
      <header className="ins-head">
        <div>
          <div className="ins-eyebrow">Jeen · {t("מעקב השלמת מסמכים בבקשת הלוואה", "Document completion follow-up in a loan application")}</div>
          <h1>{t("מבקשה שנעצרה בגלל מסמך, לתיק שמוכן לבנקאי", "From an application stopped by a document to a case ready for the banker")}</h1>
          <p>{t("כמה לקוחות חוזרים אחרי שנעצרו, כמה משלימים את המסמכים, ואיזו מדיניות מעקב נראית מבטיחה.", "How many customers come back after being stopped, how many complete their documents, and which follow-up policy looks promising.")}</p>
        </div>
      </header>

      <section className="ins-kpis" aria-label={t("מדדים מרכזיים, כל הגרסאות יחד", "Key metrics, all variants together")}>
        <Kpi tone="neutral" label={t("בקשות שנעצרו במסמך", "Applications stopped by a document")} value={n(tot.cases)} testId="kpi-cases"
          sub={t("מסמך חסר, שגוי או לא ברור", "A missing, wrong or unclear document")} />
        <Conversion rate={returned / tot.cases} label={t("חזרו", "came back")} />
        <Kpi tone="return" label={t("חזרו לתהליך", "Came back to the process")} value={n(returned)} testId="kpi-returned"
          sub={en ? <>{p(returned / tot.cases)} of the stopped applications</> : <>{p(returned / tot.cases)} מהבקשות שנעצרו</>} lane={tot.returned} />
        <Conversion rate={ready / returned} label={t("מהחוזרים מוכנים", "of returners are ready")} />
        <Kpi tone="ready" lead label={t("מוכנים לבדיקת בנקאי", "Ready for banker review")} value={n(ready)} testId="kpi-ready" better="up"
          sub={en ? <>{p(ready / tot.cases)} of the stopped applications</> : <>{p(ready / tot.cases)} מהבקשות שנעצרו</>} lane={tot.ready} />
        <div className="ins-kpi-gap" aria-hidden />
        <Kpi tone="bad" label={t("שיחות שלא נענו", "Unanswered calls")} value={p(tot.unanswered / tot.attempts)} testId="kpi-unanswered" better="down"
          sub={en ? <>{n(tot.unanswered)} of {n(tot.attempts)} call attempts</> : <>{n(tot.unanswered)} מתוך {n(tot.attempts)} ניסיונות שיחה</>} />
      </section>

      <section className="ins-main">
        <div className="panel ins-compare" data-testid="policy-compare">
          <div className="ins-panel-head">
            <div>
              <h2>{t("השוואת מדיניות מעקב: כמה זמן לחכות לפני שיחה", "Follow-up policy comparison: how long to wait before a call")}</h2>
              {en ? <div className="ins-panel-sub">
                {n(VARIANTS[0].cases)} applications per variant, with everything identical except the wait time. Pick a variant to see its path.</div>
                : <div className="ins-panel-sub">
                {n(VARIANTS[0].cases)} בקשות לכל גרסה, והכול זהה מלבד זמן ההמתנה. בחרו גרסה כדי לראות את המסלול שלה.</div>}
            </div>
          </div>
          <Legend />
          <div className="ins-rows" role="radiogroup" aria-label={t("גרסאות מדיניות המעקב", "Follow-up policy variants")}>
            {VARIANTS.map((x) => (
              <VariantRow key={x.id} v={x} on={x.id === sel} onPick={() => setSel(x.id)}
                active={activeGrace === x.graceMinutes ? activeVersion : undefined} />
            ))}
            <div className="ins-axis" aria-hidden>
              <span />
              <span className="ins-axis-scale">{[0, 25, 50, 75, 100].map((k) => <i key={k} style={{ insetInlineStart: `${k}%` }}>{k}%</i>)}</span>
              <span />
            </div>
          </div>
          <div className="ins-insight" data-testid="insight">
            <IBulb size={22} />
            <div>
              {en ? <p className="ins-insight-text">
                <span className="ins-insight-label">Insight</span>
                Waiting {n(leader.graceMinutes)} minutes before a call shows the highest completion rate:
                {" "}<b className="ins-ready-text">{p(derive(leader).readyRate)}</b> of applications ready for the banker, compared with
                {" "}{others.map((o, i) => <span key={o.id}>{i ? " and " : ""}{p(derive(o).readyRate)} at {n(o.graceMinutes)} minutes</span>)}.
                {" "}A controlled experiment is needed to establish whether timing is the cause.
              </p> : <p className="ins-insight-text">
                <span className="ins-insight-label">תובנה</span>
                המתנה של {n(leader.graceMinutes)} דקות לפני שיחה מציגה את שיעור ההשלמה הגבוה ביותר:
                {" "}<b className="ins-ready-text">{p(derive(leader).readyRate)}</b> מהבקשות מוכנות לבנקאי, לעומת
                {" "}{others.map((o, i) => <span key={o.id}>{i ? " ו־" : ""}{p(derive(o).readyRate)} ב־{n(o.graceMinutes)} דקות</span>)}.
                {" "}נדרש ניסוי מבוקר כדי לקבוע אם התזמון הוא הגורם.
              </p>}
            </div>
          </div>
        </div>

        <Journey v={v} />
      </section>
    </div>
  );
}

function Kpi({ tone, label, value, sub, lane, better, lead, testId }: {
  tone: "neutral" | "return" | "ready" | "bad"; label: string; value: ReactNode; sub: ReactNode; lane?: Lane;
  better?: "up" | "down"; lead?: boolean; testId: string;
}) {
  const { t } = useLang();
  return (
    <div className={`ins-kpi ${tone}${lead ? " lead" : ""}`} data-testid={testId}>
      <div className="ins-kpi-label"><i className={`ins-sw ${tone}`} aria-hidden />{label}
        {better && <span className={`ins-better ${better}`}>{better === "up" ? t("▲ רצוי גבוה", "▲ higher is better") : t("▼ רצוי נמוך", "▼ lower is better")}</span>}</div>
      <div className="ins-kpi-value">{value}</div>
      <div className="ins-kpi-sub">{sub}</div>
      {lane && (
        <div className="ins-kpi-lane">
          <span><i className={`ins-sw ${tone}`} aria-hidden />{n(lane.self)} {t("בלי פנייה", "with no contact")}</span>
          <span><i className={`ins-sw ${tone} call`} aria-hidden /><IPhone size={11} />{n(lane.call)} {t("אחרי שיחה", "after a call")}</span>
        </div>
      )}
    </div>
  );
}

function Conversion({ rate, label }: { rate: number; label: string }) {
  return (
    <div className="ins-link" aria-label={`${pct(rate)} ${label}`}>
      <span className="ins-link-rate">{p(rate)}</span>
      <span className="ins-link-label">{label}</span>
      <IChevron size={16} />
    </div>
  );
}

function Legend() {
  const { t } = useLang();
  return (
    <ul className="ins-legend" aria-label={t("מקרא", "Legend")}>
      <li><i className="ins-sw ready" />{t("מוכן לבדיקת בנקאי", "Ready for banker review")}</li>
      <li><i className="ins-sw pending" />{t("חזרו, עדיין בטיפול", "Came back, still in progress")}</li>
      <li><i className="ins-sw lost" />{t("לא חזרו", "Didn't come back")}</li>
      <li><i className="ins-sw bracket" />{t("חזרו לתהליך", "Came back to the process")}</li>
      <li><i className="ins-sw plain call" /><IPhone size={11} />{t("פסים: אחרי שיחה", "Stripes: after a call")}</li>
    </ul>
  );
}

function VariantRow({ v, on, active, onPick }: { v: Variant; on: boolean; active?: number; onPick: () => void }) {
  const { t } = useLang();
  const d = derive(v);
  const seg = (cls: string, count: number, title: string) => count > 0 && (
    <span className={`ins-seg ${cls}`} style={w(count, v.cases)} title={t(`${title}: ${count} מתוך ${v.cases}`, `${title}: ${count} of ${v.cases}`)}>
      {count / v.cases >= 0.07 ? count : ""}</span>
  );
  const name = t(v.name, v.nameEn);
  return (
    <button type="button" role="radio" aria-checked={on} className={`ins-row${on ? " on" : ""}`} onClick={onPick} data-testid={`variant-${v.id}`}
      aria-label={t(`${v.name}, המתנה ${v.graceMinutes} דקות: ${d.ready} מתוך ${v.cases} מוכנים לבנקאי (${pct(d.readyRate)}), ${d.returned} חזרו`,
        `${v.nameEn}, ${v.graceMinutes}-minute wait: ${d.ready} of ${v.cases} ready for the banker (${pct(d.readyRate)}), ${d.returned} came back`)}>
      <span className="ins-row-label">
        <span className="ins-row-name">{name}{active !== undefined && <span className="ins-active" title={t("זמן ההמתנה בגרסה הפעילה של מדיניות המעקב", "The wait time in the active version of the follow-up policy")}>{t("כמו הפעילה", "Same as active")} (v{active})</span>}</span>
        <span className="ins-row-grace"><bdi className="ins-num">{v.graceMinutes}</bdi> {t("דק׳ המתנה", "min wait")}</span>
      </span>
      <span className="ins-bar-wrap">
        <span className="ins-bracket" style={w(d.returned, v.cases)}><span>{t("חזרו", "Came back")} {d.returned}</span></span>
        <span className="ins-bar">
          {seg("ready", v.ready.self, t("מוכנים לבנקאי, בלי פנייה", "Ready for the banker, with no contact"))}
          {seg("ready call", v.ready.call, t("מוכנים לבנקאי, אחרי שיחה", "Ready for the banker, after a call"))}
          {seg("pending", d.inProgress, t("חזרו, עדיין בטיפול", "Came back, still in progress"))}
          {seg("lost", d.notReturned, t("לא חזרו", "Didn't come back"))}
        </span>
      </span>
      <span className="ins-row-result">
        <span className="ins-row-rate">{p(d.readyRate)}</span>
        <span className="ins-row-of">{t(<>{n(d.ready)} מתוך {n(v.cases)} מוכנים</>, <>{n(d.ready)} of {n(v.cases)} ready</>)}</span>
      </span>
    </button>
  );
}

function Journey({ v }: { v: Variant }) {
  const { en, t } = useLang();
  const d = derive(v);
  const contacted: Lane = { self: v.returned.self, call: d.contacted };
  const steps: { label: string; tone: string; lane: Lane | null; total: number; split?: [string, string]; drop?: [number, string, string] }[] = [
    { label: t("נעצרו במסמך", "Stopped by a document"), tone: "neutral", lane: null, total: v.cases },
    { label: t("הזדמנות למעקב", "Follow-up opportunity"), tone: "neutral", lane: contacted, total: v.cases,
      split: [t("חזרו לפני שנדרשה פנייה", "Came back before a contact was needed"), t("הגיעו לשיחה", "Reached a call")] },
    { label: t("חזרו לתהליך", "Came back to the process"), tone: "return", lane: v.returned, total: d.returned, drop: [d.notReturned, t("לא חזרו", "didn't come back"), "bad"] },
    { label: t("השלימו את המסמכים", "Completed the documents"), tone: "return", lane: v.uploaded, total: d.uploaded, drop: [d.returned - d.uploaded, t("עדיין חסר מסמך", "still missing a document"), "warn"] },
    { label: t("מוכנים לבדיקת בנקאי", "Ready for banker review"), tone: "ready", lane: v.ready, total: d.ready, drop: [d.uploaded - d.ready, t("נדרש תיקון במסמך", "a document needs a correction"), "warn"] },
  ];
  return (
    <div className="panel ins-journey" data-testid="journey" aria-live="polite">
      <div className="ins-panel-head">
        <div>
          {en ? <h2>The path in {v.nameEn} · <bdi className="ins-num">{v.graceMinutes}</bdi> min wait</h2>
            : <h2>המסלול ב{v.name} · <bdi className="ins-num">{v.graceMinutes}</bdi> דק׳ המתנה</h2>}
          <div className="ins-panel-sub" data-testid="journey-observation">{observe(v)}</div>
        </div>
      </div>
      <ol className="ins-steps">
        {steps.map((s, i) => (
          <li key={s.label} className={`ins-step ${s.tone}`} data-testid={`step-${i + 1}`}>
            <div className="ins-step-head">
              <span className="ins-step-label">{s.label}</span>
              <span className="ins-step-value">{s.split ? <>{n(s.lane!.self)} + {n(s.lane!.call)}</> : n(s.total)}</span>
              {s.drop && s.drop[0] > 0 && <span className={`ins-drop ${s.drop[2]}`}><span className="ltr ins-num">−{s.drop[0]}</span> {s.drop[1]}</span>}
            </div>
            <div className="ins-step-bar">
              {s.lane ? <>
                <span className={`ins-seg ${s.tone}`} style={w(s.lane.self, v.cases)} title={s.split ? s.split[0] : t("בלי פנייה", "With no contact")} />
                <span className={`ins-seg ${s.tone} call`} style={w(s.lane.call, v.cases)} title={s.split ? s.split[1] : t("אחרי שיחה", "After a call")} />
              </> : <span className={`ins-seg ${s.tone}`} style={w(s.total, v.cases)} />}
            </div>
            {s.split && <div className="ins-step-split"><span><i className="ins-sw neutral" />{s.split[0]}</span><span><i className="ins-sw neutral call" /><IPhone size={11} />{s.split[1]}</span></div>}
          </li>
        ))}
      </ol>
      {en ? <div className="ins-self" data-testid="self-share">
        <b>{n(v.ready.self)} of {n(d.ready)}</b> ready cases were completed with no contact at all; {n(v.ready.call)} after a call.
      </div> : <div className="ins-self" data-testid="self-share">
        <b>{n(v.ready.self)} מתוך {n(d.ready)}</b> התיקים המוכנים הושלמו בלי שום פנייה; {n(v.ready.call)} אחרי שיחה.
      </div>}
      <div className="ins-calls" aria-label={t("אירועי שיחה בגרסה זו", "Call events in this variant")}>
        <div className="ins-calls-title"><IPhone size={13} /> {t("אירועי שיחה", "Call events")}</div>
        <dl>
          <div><dt>{t("ניסיונות שיחה", "Call attempts")}</dt><dd>{n(v.calls.attempts)}</dd><span>{t(<>ל־{n(d.contacted)} תיקים</>, <>for {n(d.contacted)} cases</>)}</span></div>
          <div className="bad"><dt>{t("לא נענו", "Unanswered")}</dt><dd>{p(d.unanswered / v.calls.attempts)}</dd><span>{t("▼ רצוי נמוך", "▼ lower is better")}</span></div>
          <div><dt>{t("פניות שנחסכו", "Contacts saved")}</dt><dd>{n(v.returned.self)}</dd><span>{t("חזרו לפני שיחה", "came back before a call")}</span></div>
          <div><dt>{t("משך שיחה ממוצע", "Average call length")}</dt><dd><bdi className="ins-num">{mmss(v.calls.avgSeconds)}</bdi></dd><span>{t("שיחות שנענו", "answered calls")}</span></div>
        </dl>
      </div>
      <div className="ins-question"><b>{t("שאלה לבדיקה:", "Question to test:")}</b> {t(v.question, v.questionEn)}</div>
    </div>
  );
}
