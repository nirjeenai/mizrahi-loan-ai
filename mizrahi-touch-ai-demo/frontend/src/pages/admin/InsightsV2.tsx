import { useState, type CSSProperties, type ReactNode } from "react";
import { IInfo, IPhone } from "../../components/Icons";
import { derive, HELD_EQUAL, mmss, PERIOD_HE, pct, sum, totals, VARIANTS, type Variant } from "./insightsData";
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
  const t = totals();
  const returned = sum(t.returned), ready = sum(t.ready);
  const others = VARIANTS.filter((x) => x.id !== leader.id);

  return (
    <div className="ins2" data-testid="tab-body-insights" data-dash="v2">
      <header className="ins2-head">
        <div>
          <div className="ins2-eyebrow">JEEN · מעקב השלמת מסמכים בבקשת הלוואה</div>
          <h1>מבקשה שנעצרה בגלל מסמך, לתיק שמוכן לבנקאי</h1>
        </div>
        <div className="ins2-synth" role="note" data-testid="synthetic-banner">
          <IInfo size={16} />
          <span><b>נתוני המחשה סינתטיים — אינם נתוני לקוחות אמיתיים</b>
            <small>{PERIOD_HE} · שיחות JEEN Talk מדומות, ללא חיוג</small></span>
        </div>
      </header>

      <section className="ins2-hero" aria-label="המסלול של כל הבקשות שנעצרו, כל הגרסאות יחד">
        <Stage tone="neutral" label="בקשות שנעצרו במסמך" value={t.cases} share={1} testId="kpi-cases"
          note="מסמך חסר, שגוי או לא ברור" />
        <Step rate={returned / t.cases} text="חזרו" />
        <Stage tone="return" label="חזרו לתהליך" value={returned} share={returned / t.cases} testId="kpi-returned"
          note={<Split tone="return" self={t.returned.self} call={t.returned.call} />} />
        <Step rate={ready / returned} text="מהחוזרים מוכנים" />
        <Stage tone="ready" lead label="מוכנים לבדיקת בנקאי" value={ready} share={ready / t.cases} testId="kpi-ready"
          note={<><span className="ins2-stage-rate">{p(ready / t.cases)} מכל הבקשות שנעצרו</span><Split tone="ready" self={t.ready.self} call={t.ready.call} /></>} />
        <div className="ins2-friction" data-testid="kpi-unanswered">
          <span className="ins2-friction-label"><IPhone size={13} /> שיחות שלא נענו</span>
          <span className="ins2-friction-value">{p(t.unanswered / t.attempts)}</span>
          <span className="ins2-friction-note">{n(t.unanswered)} מתוך {n(t.attempts)} ניסיונות שיחה מדומים</span>
          <span className="ins2-down">▼ רצוי נמוך</span>
        </div>
      </section>

      <section className="ins2-main">
        <div className="ins2-card ins2-compare" data-testid="policy-compare">
          <div className="ins2-kicker">השוואת מדיניות מעקב · כמה זמן לחכות לפני שיחה</div>
          <h2 className="ins2-headline" data-testid="insight">
            בהמחשה, המתנה של {n(leader.graceMinutes)} דקות מובילה: <em>{p(derive(leader).readyRate)}</em> מהבקשות מוכנות לבנקאי
          </h2>
          <p className="ins2-caveat">
            לעומת {others.map((o, i) => <span key={o.id}>{i ? " ו־" : ""}{p(derive(o).readyRate)} ב־{n(o.graceMinutes)} דקות</span>)}.
            {" "}הכול זהה מלבד זמן ההמתנה, ונדרש ניסוי מבוקר כדי לקבוע אם התזמון הוא הגורם.
          </p>
          <div className="ins2-chart">
            <div className="ins2-grid" aria-hidden>
              {GRID.map((g) => <span key={g} style={{ bottom: `${(g / SCALE) * 100}%` }}><i>{pct(g, 0)}</i></span>)}
            </div>
            <div className="ins2-cols" role="radiogroup" aria-label="גרסאות מדיניות המעקב">
              {VARIANTS.map((x) => (
                <Column key={x.id} v={x} on={x.id === sel} best={x.id === leader.id} showReturn={showReturn} onPick={() => setSel(x.id)}
                  active={activeGrace === x.graceMinutes ? activeVersion : undefined} />
              ))}
            </div>
          </div>
          <div className="ins2-chart-foot">
            <span className="ins2-key"><i className="ins2-sw ready" />מוכנים לבדיקת בנקאי</span>
            {showReturn && <span className="ins2-key"><i className="ins2-sw return-ghost" />חזרו לתהליך</span>}
            <label className="ins2-toggle">
              <input type="checkbox" checked={showReturn} onChange={(e) => setShowReturn(e.target.checked)} data-testid="toggle-returned" />
              הצגת שיעור החזרה לתהליך
            </label>
            <span className="ins2-hint">בחרו עמודה כדי לראות את המסלול שלה</span>
          </div>
        </div>

        <Journey v={v} />
      </section>

      <footer className="ins2-foot">
        כל המספרים בעמוד סינתטיים ונבנו להמחשה; אין בהם מדידה של לקוחות, של שיחות או של המערכת. תנאים זהים בכל הגרסאות: {HELD_EQUAL.join(" · ")}.
        סימולציית המדיניות בלשונית "בדיקה וגרסאות" מחשבת החלטות תפעוליות בלבד ואינה חוזה התנהגות לקוחות.
        "מוכן לבדיקת בנקאי" פירושו חבילת מסמכים שלמה שעברה בדיקת מסמכים; ההחלטה בידי הבנקאי, ואין בכך אישור הלוואה.
      </footer>
    </div>
  );
}

function Split({ tone, self, call }: { tone: "return" | "ready"; self: number; call: number }) {
  return (
    <span className="ins2-split">
      <span><i className={`ins2-sw ${tone}`} />{n(self)} בלי פנייה</span>
      <span><i className={`ins2-sw ${tone} call`} /><IPhone size={11} />{n(call)} אחרי שיחה</span>
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
  const d = derive(v);
  return (
    <button type="button" role="radio" aria-checked={on} className={`ins2-col${on ? " on" : ""}${best ? " best" : ""}`} onClick={onPick}
      data-testid={`variant-${v.id}`}
      aria-label={`${v.graceMinutes} דקות המתנה: ${d.ready} מתוך ${v.cases} מוכנים לבנקאי (${pct(d.readyRate)}), ${d.returned} חזרו (${pct(d.returnRate)})`}>
      <span className="ins2-plot">
        {showReturn && (
          <span className="ins2-bar return-ghost" style={height(d.returnRate)} data-testid={`returned-${v.id}`}>
            <span className="ins2-bar-tag">חזרו {p(d.returnRate)}</span>
          </span>
        )}
        <span className={`ins2-bar ready${showReturn ? " narrow" : ""}`} style={height(d.readyRate)}>
          <span className="ins2-bar-value">
            {best && <span className="ins2-best">הגבוה בהמחשה</span>}
            {p(d.readyRate)}
          </span>
        </span>
      </span>
      <span className="ins2-col-label">
        <span className="ins2-col-grace"><bdi className="ins2-num">{v.graceMinutes}</bdi> דק׳ המתנה</span>
        <span className="ins2-col-of">{n(d.ready)} מתוך {n(v.cases)} מוכנים</span>
        {active !== undefined && <span className="ins2-active" title="זמן ההמתנה בגרסה הפעילה של מדיניות המעקב">כמו המדיניות הפעילה · v{active}</span>}
      </span>
    </button>
  );
}

function Journey({ v }: { v: Variant }) {
  const d = derive(v);
  const rows = [
    { label: "נעצרו במסמך", tone: "neutral", total: v.cases, lane: null, rate: null },
    { label: "חזרו לתהליך", tone: "return", total: d.returned, lane: v.returned, rate: d.returnRate },
    { label: "השלימו את המסמכים", tone: "return", total: d.uploaded, lane: v.uploaded, rate: null },
    { label: "מוכנים לבדיקת בנקאי", tone: "ready", total: d.ready, lane: v.ready, rate: d.readyRate },
  ];
  return (
    <div className="ins2-card ins2-journey" data-testid="journey" aria-live="polite">
      <div className="ins2-kicker">המסלול בגרסה הנבחרת</div>
      <h2 className="ins2-journey-title"><bdi className="ins2-num">{v.graceMinutes}</bdi> דק׳ המתנה <small>· {n(v.cases)} בקשות שנעצרו</small></h2>
      <ol className="ins2-funnel">
        {rows.map((r, i) => (
          <li key={r.label} className={r.tone} data-testid={`step-${i + 1}`}>
            <span className="ins2-funnel-label">{r.label}</span>
            <span className="ins2-funnel-track">
              {r.lane ? <>
                <span className={`ins2-fill ${r.tone}`} style={width(r.lane.self, v.cases)} title={`בלי פנייה: ${r.lane.self}`} />
                <span className={`ins2-fill ${r.tone} call`} style={width(r.lane.call, v.cases)} title={`אחרי שיחה מדומה: ${r.lane.call}`} />
              </> : <span className={`ins2-fill ${r.tone}`} style={width(r.total, v.cases)} />}
            </span>
            <span className="ins2-funnel-value">{n(r.total)}{r.rate !== null && <small>{p(r.rate)}</small>}</span>
          </li>
        ))}
      </ol>
      <div className="ins2-paths" data-testid="self-share">
        <div className="ins2-path">
          <span className="ins2-path-head"><i className="ins2-sw ready" />בלי שום פנייה</span>
          <span className="ins2-path-value">{n(v.ready.self)}</span>
          <span className="ins2-path-note">מוכנים לבנקאי · {n(v.returned.self)} חזרו בזמן ההמתנה</span>
        </div>
        <div className="ins2-path">
          <span className="ins2-path-head"><i className="ins2-sw ready call" /><IPhone size={12} />אחרי שיחה מדומה</span>
          <span className="ins2-path-value">{n(v.ready.call)}</span>
          <span className="ins2-path-note">מוכנים לבנקאי · מתוך {n(d.contacted)} שקיבלו פנייה</span>
        </div>
      </div>
      <dl className="ins2-contact" aria-label="אירועי שיחה מדומים בגרסה זו">
        <div><dt>פניות שנחסכו</dt><dd>{n(v.returned.self)}</dd></div>
        <div className="bad"><dt>שיחות שלא נענו <span className="ins2-down">▼</span></dt><dd>{p(d.unanswered / v.calls.attempts)}</dd></div>
        <div><dt>ניסיונות שיחה</dt><dd>{n(v.calls.attempts)}</dd></div>
        <div><dt>משך שיחה ממוצע</dt><dd><bdi className="ins2-num">{mmss(v.calls.avgSeconds)}</bdi></dd></div>
      </dl>
      <p className="ins2-question"><b>שאלה לבדיקה:</b> {v.question}</p>
    </div>
  );
}
