import { useState, type CSSProperties, type ReactNode } from "react";
import { IBulb, IChevron, IPhone } from "../../components/Icons";
import { derive, mmss, pct, problems, sum, totals, VARIANTS, type Lane, type Variant } from "./insightsData";

if (import.meta.env.DEV && problems().length) console.error("insightsData does not reconcile:", problems());

const n = (x: number) => <bdi className="ins-num">{x.toLocaleString("he-IL")}</bdi>;
const p = (x: number, digits = 1) => <bdi className="ins-num">{pct(x, digits)}</bdi>;
const w = (part: number, whole: number): CSSProperties => ({ width: `${(part / whole) * 100}%` });

/** Observation for one variant, worded as what the illustration shows, never as a cause. */
function observe(v: Variant): ReactNode {
  const d = derive(v);
  if (v.id === "A") return <>{n(d.contacted)} מתוך {n(v.cases)} התיקים הגיעו לשיחה, ו־{p(d.unanswered / v.calls.attempts)} מהשיחות לא נענו.</>;
  if (v.id === "B") return <>{n(v.returned.self)} לקוחות חזרו בעצמם לפני שנדרשה פנייה, ו־{p(v.calls.answered / v.calls.attempts)} מהשיחות נענו.</>;
  return <>{n(v.returned.self)} לקוחות חזרו בעצמם, אבל השיחות החזירו רק {n(v.returned.call)} מתוך {n(d.contacted)} הלקוחות שקיבלו פנייה.</>;
}

export function InsightsTab({ activeGrace, activeVersion }: { activeGrace?: number; activeVersion?: number }) {
  const leader = VARIANTS.reduce((a, b) => (derive(b).readyRate > derive(a).readyRate ? b : a));
  const [sel, setSel] = useState<Variant["id"]>(leader.id);
  const v = VARIANTS.find((x) => x.id === sel)!;
  const t = totals();
  const returned = sum(t.returned), ready = sum(t.ready);
  const others = VARIANTS.filter((x) => x.id !== leader.id);

  return (
    <div className="ins" data-testid="tab-body-insights">
      <header className="ins-head">
        <div>
          <div className="ins-eyebrow">JEEN · מעקב השלמת מסמכים בבקשת הלוואה</div>
          <h1>מבקשה שנעצרה בגלל מסמך, לתיק שמוכן לבנקאי</h1>
          <p>כמה לקוחות חוזרים אחרי שנעצרו, כמה משלימים את המסמכים, ואיזו מדיניות מעקב נראית מבטיחה.</p>
        </div>
      </header>

      <section className="ins-kpis" aria-label="מדדים מרכזיים, כל הגרסאות יחד">
        <Kpi tone="neutral" label="בקשות שנעצרו במסמך" value={n(t.cases)} testId="kpi-cases"
          sub="מסמך חסר, שגוי או לא ברור" />
        <Conversion rate={returned / t.cases} label="חזרו" />
        <Kpi tone="return" label="חזרו לתהליך" value={n(returned)} testId="kpi-returned"
          sub={<>{p(returned / t.cases)} מהבקשות שנעצרו</>} lane={t.returned} />
        <Conversion rate={ready / returned} label="מהחוזרים מוכנים" />
        <Kpi tone="ready" lead label="מוכנים לבדיקת בנקאי" value={n(ready)} testId="kpi-ready" better="up"
          sub={<>{p(ready / t.cases)} מהבקשות שנעצרו</>} lane={t.ready} />
        <div className="ins-kpi-gap" aria-hidden />
        <Kpi tone="bad" label="שיחות שלא נענו" value={p(t.unanswered / t.attempts)} testId="kpi-unanswered" better="down"
          sub={<>{n(t.unanswered)} מתוך {n(t.attempts)} ניסיונות שיחה</>} />
      </section>

      <section className="ins-main">
        <div className="panel ins-compare" data-testid="policy-compare">
          <div className="ins-panel-head">
            <div>
              <h2>השוואת מדיניות מעקב: כמה זמן לחכות לפני שיחה</h2>
              <div className="ins-panel-sub">
                {n(VARIANTS[0].cases)} בקשות לכל גרסה, והכול זהה מלבד זמן ההמתנה. בחרו גרסה כדי לראות את המסלול שלה.</div>
            </div>
          </div>
          <Legend />
          <div className="ins-rows" role="radiogroup" aria-label="גרסאות מדיניות המעקב">
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
              <p className="ins-insight-text">
                <span className="ins-insight-label">תובנה</span>
                המתנה של {n(leader.graceMinutes)} דקות לפני שיחה מציגה את שיעור ההשלמה הגבוה ביותר:
                {" "}<b className="ins-ready-text">{p(derive(leader).readyRate)}</b> מהבקשות מוכנות לבנקאי, לעומת
                {" "}{others.map((o, i) => <span key={o.id}>{i ? " ו־" : ""}{p(derive(o).readyRate)} ב־{n(o.graceMinutes)} דקות</span>)}.
                {" "}נדרש ניסוי מבוקר כדי לקבוע אם התזמון הוא הגורם.
              </p>
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
  return (
    <div className={`ins-kpi ${tone}${lead ? " lead" : ""}`} data-testid={testId}>
      <div className="ins-kpi-label"><i className={`ins-sw ${tone}`} aria-hidden />{label}
        {better && <span className={`ins-better ${better}`}>{better === "up" ? "▲ רצוי גבוה" : "▼ רצוי נמוך"}</span>}</div>
      <div className="ins-kpi-value">{value}</div>
      <div className="ins-kpi-sub">{sub}</div>
      {lane && (
        <div className="ins-kpi-lane">
          <span><i className={`ins-sw ${tone}`} aria-hidden />{n(lane.self)} בלי פנייה</span>
          <span><i className={`ins-sw ${tone} call`} aria-hidden /><IPhone size={11} />{n(lane.call)} אחרי שיחה</span>
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
  return (
    <ul className="ins-legend" aria-label="מקרא">
      <li><i className="ins-sw ready" />מוכן לבדיקת בנקאי</li>
      <li><i className="ins-sw pending" />חזרו, עדיין בטיפול</li>
      <li><i className="ins-sw lost" />לא חזרו</li>
      <li><i className="ins-sw bracket" />חזרו לתהליך</li>
      <li><i className="ins-sw plain call" /><IPhone size={11} />פסים: אחרי שיחה</li>
    </ul>
  );
}

function VariantRow({ v, on, active, onPick }: { v: Variant; on: boolean; active?: number; onPick: () => void }) {
  const d = derive(v);
  const seg = (cls: string, count: number, title: string) => count > 0 && (
    <span className={`ins-seg ${cls}`} style={w(count, v.cases)} title={`${title}: ${count} מתוך ${v.cases}`}>
      {count / v.cases >= 0.07 ? count : ""}</span>
  );
  return (
    <button type="button" role="radio" aria-checked={on} className={`ins-row${on ? " on" : ""}`} onClick={onPick} data-testid={`variant-${v.id}`}
      aria-label={`${v.name}, המתנה ${v.graceMinutes} דקות: ${d.ready} מתוך ${v.cases} מוכנים לבנקאי (${pct(d.readyRate)}), ${d.returned} חזרו`}>
      <span className="ins-row-label">
        <span className="ins-row-name">{v.name}{active !== undefined && <span className="ins-active" title="זמן ההמתנה בגרסה הפעילה של מדיניות המעקב">כמו הפעילה (v{active})</span>}</span>
        <span className="ins-row-grace"><bdi className="ins-num">{v.graceMinutes}</bdi> דק׳ המתנה</span>
      </span>
      <span className="ins-bar-wrap">
        <span className="ins-bracket" style={w(d.returned, v.cases)}><span>חזרו {d.returned}</span></span>
        <span className="ins-bar">
          {seg("ready", v.ready.self, "מוכנים לבנקאי, בלי פנייה")}
          {seg("ready call", v.ready.call, "מוכנים לבנקאי, אחרי שיחה")}
          {seg("pending", d.inProgress, "חזרו, עדיין בטיפול")}
          {seg("lost", d.notReturned, "לא חזרו")}
        </span>
      </span>
      <span className="ins-row-result">
        <span className="ins-row-rate">{p(d.readyRate)}</span>
        <span className="ins-row-of">{n(d.ready)} מתוך {n(v.cases)} מוכנים</span>
      </span>
    </button>
  );
}

function Journey({ v }: { v: Variant }) {
  const d = derive(v);
  const contacted: Lane = { self: v.returned.self, call: d.contacted };
  const steps: { label: string; tone: string; lane: Lane | null; total: number; split?: [string, string]; drop?: [number, string, string] }[] = [
    { label: "נעצרו במסמך", tone: "neutral", lane: null, total: v.cases },
    { label: "הזדמנות למעקב", tone: "neutral", lane: contacted, total: v.cases, split: ["חזרו לפני שנדרשה פנייה", "הגיעו לשיחה"] },
    { label: "חזרו לתהליך", tone: "return", lane: v.returned, total: d.returned, drop: [d.notReturned, "לא חזרו", "bad"] },
    { label: "השלימו את המסמכים", tone: "return", lane: v.uploaded, total: d.uploaded, drop: [d.returned - d.uploaded, "עדיין חסר מסמך", "warn"] },
    { label: "מוכנים לבדיקת בנקאי", tone: "ready", lane: v.ready, total: d.ready, drop: [d.uploaded - d.ready, "נדרש תיקון במסמך", "warn"] },
  ];
  return (
    <div className="panel ins-journey" data-testid="journey" aria-live="polite">
      <div className="ins-panel-head">
        <div>
          <h2>המסלול ב{v.name} · <bdi className="ins-num">{v.graceMinutes}</bdi> דק׳ המתנה</h2>
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
                <span className={`ins-seg ${s.tone}`} style={w(s.lane.self, v.cases)} title={s.split ? s.split[0] : "בלי פנייה"} />
                <span className={`ins-seg ${s.tone} call`} style={w(s.lane.call, v.cases)} title={s.split ? s.split[1] : "אחרי שיחה"} />
              </> : <span className={`ins-seg ${s.tone}`} style={w(s.total, v.cases)} />}
            </div>
            {s.split && <div className="ins-step-split"><span><i className="ins-sw neutral" />{s.split[0]}</span><span><i className="ins-sw neutral call" /><IPhone size={11} />{s.split[1]}</span></div>}
          </li>
        ))}
      </ol>
      <div className="ins-self" data-testid="self-share">
        <b>{n(v.ready.self)} מתוך {n(d.ready)}</b> התיקים המוכנים הושלמו בלי שום פנייה; {n(v.ready.call)} אחרי שיחה.
      </div>
      <div className="ins-calls" aria-label="אירועי שיחה בגרסה זו">
        <div className="ins-calls-title"><IPhone size={13} /> אירועי שיחה</div>
        <dl>
          <div><dt>ניסיונות שיחה</dt><dd>{n(v.calls.attempts)}</dd><span>ל־{n(d.contacted)} תיקים</span></div>
          <div className="bad"><dt>לא נענו</dt><dd>{p(d.unanswered / v.calls.attempts)}</dd><span>▼ רצוי נמוך</span></div>
          <div><dt>פניות שנחסכו</dt><dd>{n(v.returned.self)}</dd><span>חזרו לפני שיחה</span></div>
          <div><dt>משך שיחה ממוצע</dt><dd><bdi className="ins-num">{mmss(v.calls.avgSeconds)}</bdi></dd><span>שיחות שנענו</span></div>
        </dl>
      </div>
      <div className="ins-question"><b>שאלה לבדיקה:</b> {v.question}</div>
    </div>
  );
}
