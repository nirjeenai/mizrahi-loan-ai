import { useState } from "react";
import { actorHe, setPath, type Json, type Settings } from "../../adminApi";
import { Chip, When } from "../banker/deskUi";
import type { KindProps } from "./AdminPage";
import { FieldErrors, Lock, NumberField, Toggle } from "./ui";

const DAYS: [string, string][] = [["SUN", "א׳"], ["MON", "ב׳"], ["TUE", "ג׳"], ["WED", "ד׳"], ["THU", "ה׳"], ["FRI", "ו׳"], ["SAT", "שבת"]];
const AFTER_APP: [string, string[]][] = [["שיחה קולית", ["voice"]], ["הודעה", ["message"]], ["שיחה, ואז הודעה", ["voice", "message"]],
  ["הודעה, ואז שיחה", ["message", "voice"]], ["ללא ערוץ נוסף", []]];
const MODE_HE: Record<string, string> = { simulation: "סימולציה", off: "כבוי", live: "חי (ספק JEEN Talk)" };

export function FollowupTab({ work, edit, bar, settings, onKillSwitch }: KindProps & {
  settings: Settings; onKillSwitch: (paused: boolean, reason: string) => Promise<void>;
}) {
  const f: Json = work.config.followup || {};
  const talk: Json = work.config.talk || {};
  const report = work.report;
  const env = settings.environment.name;
  const set = (path: string) => (v: unknown) => edit((c) => setPath(c, path, v));
  const num = (key: string, label: string, min: number, max: number, unit: string, hint?: string) => (
    <NumberField label={label} value={f[key]} min={min} max={max} unit={unit} hint={hint} path={`followup.${key}`} report={report}
      onChange={set(`followup.${key}`)} testId={`f-${key}`} />
  );
  const days: string[] = f.call_window?.days || [];
  const after = JSON.stringify((f.channel_order || []).slice(1));
  return (
    <div className="adm-tab" data-testid="tab-body-followup">
      {bar}
      <div className="adm-grid">
        <div>
          <div className="panel">
            <h3>הפעלה</h3>
            <Toggle label="מעקב יזום אחרי מסמכים חסרים" checked={!!f.auto_followup_enabled} onChange={set("followup.auto_followup_enabled")}
              hint="כבוי: הלקוח רואה את המשימות באפליקציה, אבל אין תזכורות ושיחות יזומות" testId="f-auto" />
            <Toggle label="ערוץ שיחה (JEEN Talk)" checked={!!talk.enabled} onChange={set("talk.enabled")} testId="t-enabled" />
            <label className="adm-field"><span className="adm-label">מצב ספק השיחות</span>
              <select value={talk.mode} onChange={(e) => set("talk.mode")(e.target.value)} data-testid="t-mode">
                {Object.entries(MODE_HE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <span className="tiny muted">במצב חי, שיחה תתבצע רק כשספק JEEN Talk אמיתי מחובר ומוגדר. כרגע הוא אינו מוגדר.</span>
              <FieldErrors report={report} path="talk.mode" />
            </label>
          </div>
          <div className="panel">
            <h3>נוכחות, המתנה ותזכורות</h3>
            <div className="adm-fields">
              {num("abandonment_grace_minutes", "המתנה אחרי שהלקוח עזב", settings.envelope.min_grace_minutes[env] ?? 5, 1440, "דקות",
                `מינימום הבנק בסביבה זו: ${settings.envelope.min_grace_minutes[env] ?? 5} דק׳`)}
              {num("in_app_idle_nudge_minutes", "תזכורת באפליקציה אחרי חוסר פעילות", 1, 120, "דקות")}
              {num("unknown_presence_extra_minutes", "המתנה נוספת כשהנוכחות לא ודאית", 0, 240, "דקות")}
              {num("statement_extends_grace_minutes", "הארכה כשהלקוח אומר שכבר שלח", 0, 240, "דקות")}
              {num("presence_ttl_seconds", "זמן עד שסשן נחשב לא פעיל", 20, 600, "שניות")}
            </div>
          </div>
          <div className="panel">
            <h3>מכסות ומרווחים</h3>
            <div className="adm-fields">
              {num("max_attempts_per_case", "פניות לתיק, סה״כ", 1, settings.envelope.max_attempts_per_case, "פניות", "מעטפת הבנק")}
              {num("max_attempts_per_case_per_day", "פניות לתיק ביום", 1, 3, "פניות")}
              {num("max_attempts_per_customer_per_day", "פניות ללקוח ביום (כל התיקים)", 1, 5, "פניות")}
              {num("min_hours_between_calls", "מרווח מינימלי בין שיחות", settings.envelope.min_hours_between_calls, 168, "שעות", "מעטפת הבנק")}
            </div>
            <div className="adm-locked-row"><Lock reason="כשמוצו הפניות, הדרישה עוברת לבנקאי" />
              <span className="small">כשמוצו הפניות: <b>העברה לבנקאי</b> (נעול)</span></div>
          </div>
        </div>
        <div>
          <div className="panel">
            <h3>חלון הפנייה <span className="tiny muted">(שעון ישראל)</span></h3>
            <div className="row wrap" style={{ gap: 6 }}>
              {DAYS.map(([d, he]) => d === "SAT" ? (
                <span key={d} className="adm-day locked" title="אין פנייה בשבת (מעטפת הבנק)"><Lock reason="אין פנייה בשבת" /> {he}</span>
              ) : (
                <label key={d} className={`adm-day${days.includes(d) ? " on" : ""}`}>
                  <input type="checkbox" checked={days.includes(d)} data-testid={`day-${d}`}
                    onChange={(e) => set("followup.call_window.days")(e.target.checked ? DAYS.map(([x]) => x).filter((x) => x === d || days.includes(x)) : days.filter((x) => x !== d))} />
                  {he}
                </label>
              ))}
            </div>
            <div className="row" style={{ marginTop: 10, gap: 12 }}>
              <label className="adm-field"><span className="adm-label">משעה</span>
                <input type="time" value={f.call_window?.from || ""} onChange={(e) => set("followup.call_window.from")(e.target.value)} data-testid="w-from" /></label>
              <label className="adm-field"><span className="adm-label">עד שעה</span>
                <input type="time" value={f.call_window?.to || ""} onChange={(e) => set("followup.call_window.to")(e.target.value)} data-testid="w-to" /></label>
            </div>
            <div className="tiny muted">מעטפת הבנק: {settings.envelope.call_window_bounds[0]}–{settings.envelope.call_window_bounds[1]}, ללא שבת.</div>
            <FieldErrors report={report} path="followup.call_window" />
            <Holidays value={f.holidays || []} onChange={set("followup.holidays")} />
            <FieldErrors report={report} path="followup.holidays" />
          </div>
          <div className="panel">
            <h3>סדר הערוצים</h3>
            <div className="adm-locked-row"><Lock reason="תיקון עצמי באפליקציה תמיד קודם לכל פנייה" />
              <span className="small">ראשון תמיד: <b>תיקון עצמי באפליקציה</b> (נעול)</span></div>
            <label className="adm-field"><span className="adm-label">אחר כך</span>
              <select value={after} onChange={(e) => set("followup.channel_order")(["in_app", ...JSON.parse(e.target.value)])} data-testid="f-channels">
                {AFTER_APP.map(([label, rest]) => <option key={label} value={JSON.stringify(rest)}>{label}</option>)}
              </select></label>
            <FieldErrors report={report} path="followup.channel_order" />
            <h3 style={{ marginTop: 14 }}>שיחות וקישורים</h3>
            <div className="adm-fields">
              <NumberField label="תוקף קישור להעלאה" value={talk.link_ttl_minutes} min={15} max={10080} unit="דקות" path="talk.link_ttl_minutes"
                report={report} onChange={set("talk.link_ttl_minutes")} />
              <NumberField label="שגיאות ספק עד עצירה" value={talk.max_provider_errors} min={0} max={5} unit="שגיאות" path="talk.max_provider_errors"
                report={report} onChange={set("talk.max_provider_errors")} />
              <NumberField label="בירור שיחה בסטטוס לא ידוע אחרי" value={talk.reconcile_after_minutes} min={1} max={120} unit="דקות"
                path="talk.reconcile_after_minutes" report={report} onChange={set("talk.reconcile_after_minutes")} />
            </div>
          </div>
          <KillSwitch settings={settings} onChange={onKillSwitch} />
          <div className="panel" data-testid="locked-rules">
            <h3><Lock reason="כללי הגנה בקוד" /> כללי הגנה קבועים</h3>
            <div className="small muted" style={{ marginBottom: 6 }}>כללים אלה קבועים בקוד ואינם ניתנים לשינוי בהגדרות או בהנחיות. הם גוברים על כל כלל אחר.</div>
            <ul className="adm-rules">{settings.locked_rules.map((r) => (
              <li key={r.id}><span className="ltr tiny muted">{r.id}</span> {r.label_he}</li>
            ))}</ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function Holidays({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const [day, setDay] = useState("");
  return (
    <div style={{ marginTop: 12 }}>
      <div className="adm-label">ימי חג ללא פניות</div>
      <div className="row wrap" style={{ gap: 4, margin: "6px 0" }}>
        {value.map((d) => (
          <span key={d} className="chip">{new Date(d + "T12:00:00").toLocaleDateString("he-IL")}
            <button className="adm-x" aria-label={`הסרת ${d}`} onClick={() => onChange(value.filter((x) => x !== d))}>×</button></span>
        ))}
        {!value.length && <span className="tiny muted">אין</span>}
      </div>
      <span className="row"><input type="date" value={day} onChange={(e) => setDay(e.target.value)} aria-label="תאריך חג" />
        <button className="btn btn-ghost btn-sm" disabled={!day || value.includes(day)}
          onClick={() => { onChange([...value, day].sort()); setDay(""); }}>הוספה</button></span>
    </div>
  );
}

function KillSwitch({ settings, onChange }: { settings: Settings; onChange: (paused: boolean, reason: string) => Promise<void> }) {
  const ks = settings.kill_switch;
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className={`panel adm-kill${ks.value ? " on" : ""}`} data-testid="kill-switch">
      <h3>מתג חירום</h3>
      <div className="row between wrap">
        <span className="small">{ks.value
          ? <><Chip tone="bad">פעיל</Chip> אין אף פנייה יזומה ללקוחות. העלאת מסמכים ובדיקתם ממשיכות כרגיל.</>
          : <><Chip tone="ok">כבוי</Chip> המעקב פועל לפי המדיניות הפעילה.</>}</span>
        {ks.updated_at && <When at={ks.updated_at} by={actorHe(ks.updated_by, settings.caller)} />}
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <input className="adm-cell grow" placeholder="סיבה (לא חובה)" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} />
        <button className={`btn btn-sm ${ks.value ? "btn-dark" : "btn-orange"}`} disabled={busy} data-testid="kill-toggle"
          onClick={async () => { setBusy(true); await onChange(!ks.value, reason); setReason(""); setBusy(false); }}>
          {ks.value ? "החזרת המעקב לפעולה" : "עצירת כל הפניות היזומות"}</button>
      </div>
      <div className="tiny muted" style={{ marginTop: 6 }}>המתג פועל מיד, בלי טיוטה והפעלה, ונרשם ביומן.</div>
    </div>
  );
}
