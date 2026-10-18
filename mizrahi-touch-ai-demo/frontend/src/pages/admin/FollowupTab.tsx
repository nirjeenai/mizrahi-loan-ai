import { useState } from "react";
import { actorHe, setPath, type Json, type Settings } from "../../adminApi";
import { localeL } from "../../api";
import { Loc, useLang } from "../../i18n";
import { Chip, When } from "../banker/deskUi";
import type { KindProps } from "./AdminPage";
import { FieldErrors, Lock, NumberField, Toggle } from "./ui";

const DAYS: [string, string][] = [["SUN", "א׳"], ["MON", "ב׳"], ["TUE", "ג׳"], ["WED", "ד׳"], ["THU", "ה׳"], ["FRI", "ו׳"], ["SAT", "שבת"]];
const DAY_EN: Record<string, string> = { SUN: "Sun", MON: "Mon", TUE: "Tue", WED: "Wed", THU: "Thu", FRI: "Fri", SAT: "Sat" };
const AFTER_APP: [string, string[]][] = [["שיחה קולית", ["voice"]], ["הודעה", ["message"]], ["שיחה, ואז הודעה", ["voice", "message"]],
  ["הודעה, ואז שיחה", ["message", "voice"]], ["ללא ערוץ נוסף", []]];
const AFTER_APP_EN: Record<string, string> = { "שיחה קולית": "Voice call", "הודעה": "Message", "שיחה, ואז הודעה": "Call, then message",
  "הודעה, ואז שיחה": "Message, then call", "ללא ערוץ נוסף": "No further channel" };
const MODE_HE: Record<string, string> = { simulation: "סימולציה", off: "כבוי", live: "חי (ספק Jeen Talk)" };
const MODE_EN: Record<string, string> = { simulation: "Simulation", off: "Off", live: "Live (Jeen Talk provider)" };

export function FollowupTab({ work, edit, bar, settings, onKillSwitch }: KindProps & {
  settings: Settings; onKillSwitch: (paused: boolean, reason: string) => Promise<void>;
}) {
  const { t } = useLang();
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
            <h3>{t("הפעלה", "Activation")}</h3>
            <Toggle label={t("מעקב יזום אחרי מסמכים חסרים", "Proactive follow-up on missing documents")} checked={!!f.auto_followup_enabled} onChange={set("followup.auto_followup_enabled")}
              hint={t("כבוי: הלקוח רואה את המשימות באפליקציה, אבל אין תזכורות ושיחות יזומות", "Off: the customer sees the tasks in the app, but there are no proactive reminders or calls")} testId="f-auto" />
            <Toggle label={t("ערוץ שיחה (Jeen Talk)", "Call channel (Jeen Talk)")} checked={!!talk.enabled} onChange={set("talk.enabled")} testId="t-enabled" />
            <label className="adm-field"><span className="adm-label">{t("מצב ספק השיחות", "Call provider mode")}</span>
              <select value={talk.mode} onChange={(e) => set("talk.mode")(e.target.value)} data-testid="t-mode">
                {Object.entries(MODE_HE).map(([k, v]) => <option key={k} value={k}>{t(v, MODE_EN[k])}</option>)}
              </select>
              <span className="tiny muted">{t("במצב חי, שיחה תתבצע רק כשספק Jeen Talk מחובר ומוגדר. כרגע הוא אינו מוגדר.", "In live mode, a call is made only when the Jeen Talk provider is connected and configured. It isn't configured right now.")}</span>
              <FieldErrors report={report} path="talk.mode" />
            </label>
          </div>
          <div className="panel">
            <h3>{t("נוכחות, המתנה ותזכורות", "Presence, waiting and reminders")}</h3>
            <div className="adm-fields">
              {num("abandonment_grace_minutes", t("המתנה אחרי שהלקוח עזב", "Wait after the customer leaves"), settings.envelope.min_grace_minutes[env] ?? 5, 1440, t("דקות", "minutes"),
                t(`מינימום הבנק בסביבה זו: ${settings.envelope.min_grace_minutes[env] ?? 5} דק׳`, `Bank minimum in this environment: ${settings.envelope.min_grace_minutes[env] ?? 5} min`))}
              {num("in_app_idle_nudge_minutes", t("תזכורת באפליקציה אחרי חוסר פעילות", "In-app reminder after inactivity"), 1, 120, t("דקות", "minutes"))}
              {num("unknown_presence_extra_minutes", t("המתנה נוספת כשהנוכחות לא ודאית", "Extra wait when presence is uncertain"), 0, 240, t("דקות", "minutes"))}
              {num("statement_extends_grace_minutes", t("הארכה כשהלקוח אומר שכבר שלח", "Extension when the customer says they already sent it"), 0, 240, t("דקות", "minutes"))}
              {num("presence_ttl_seconds", t("זמן עד שסשן נחשב לא פעיל", "Time until a session counts as inactive"), 20, 600, t("שניות", "seconds"))}
            </div>
          </div>
          <div className="panel">
            <h3>{t("מכסות ומרווחים", "Limits and intervals")}</h3>
            <div className="adm-fields">
              {num("max_attempts_per_case", t("פניות לתיק, סה״כ", "Contacts per case, total"), 1, settings.envelope.max_attempts_per_case, t("פניות", "contacts"), t("מעטפת הבנק", "bank envelope"))}
              {num("max_attempts_per_case_per_day", t("פניות לתיק ביום", "Contacts per case per day"), 1, 3, t("פניות", "contacts"))}
              {num("max_attempts_per_customer_per_day", t("פניות ללקוח ביום (כל התיקים)", "Contacts per customer per day (all cases)"), 1, 5, t("פניות", "contacts"))}
              {num("min_hours_between_calls", t("מרווח מינימלי בין שיחות", "Minimum interval between calls"), settings.envelope.min_hours_between_calls, 168, t("שעות", "hours"), t("מעטפת הבנק", "bank envelope"))}
            </div>
            <div className="adm-locked-row"><Lock reason={t("כשמוצו הפניות, הדרישה עוברת לבנקאי", "Once the contacts are used up, the requirement goes to the banker")} />
              {t(<span className="small">כשמוצו הפניות: <b>העברה לבנקאי</b> (נעול)</span>,
                <span className="small">When the contacts are used up: <b>hand over to the banker</b> (locked)</span>)}</div>
          </div>
        </div>
        <div>
          <div className="panel">
            <h3>{t("חלון הפנייה", "Contact window")} <span className="tiny muted">{t("(שעון ישראל)", "(Israel time)")}</span></h3>
            <div className="row wrap" style={{ gap: 6 }}>
              {DAYS.map(([d, he]) => d === "SAT" ? (
                <span key={d} className="adm-day locked" title={t("אין פנייה בשבת (מעטפת הבנק)", "No contact on Saturday (bank envelope)")}><Lock reason={t("אין פנייה בשבת", "No contact on Saturday")} /> {t(he, DAY_EN[d])}</span>
              ) : (
                <label key={d} className={`adm-day${days.includes(d) ? " on" : ""}`}>
                  <input type="checkbox" checked={days.includes(d)} data-testid={`day-${d}`}
                    onChange={(e) => set("followup.call_window.days")(e.target.checked ? DAYS.map(([x]) => x).filter((x) => x === d || days.includes(x)) : days.filter((x) => x !== d))} />
                  {t(he, DAY_EN[d])}
                </label>
              ))}
            </div>
            <div className="row" style={{ marginTop: 10, gap: 12 }}>
              <label className="adm-field"><span className="adm-label">{t("משעה", "From")}</span>
                <input type="time" value={f.call_window?.from || ""} onChange={(e) => set("followup.call_window.from")(e.target.value)} data-testid="w-from" /></label>
              <label className="adm-field"><span className="adm-label">{t("עד שעה", "Until")}</span>
                <input type="time" value={f.call_window?.to || ""} onChange={(e) => set("followup.call_window.to")(e.target.value)} data-testid="w-to" /></label>
            </div>
            <div className="tiny muted">{t("מעטפת הבנק", "Bank envelope")}: {settings.envelope.call_window_bounds[0]}–{settings.envelope.call_window_bounds[1]}{t(", ללא שבת.", ", no Saturdays.")}</div>
            <FieldErrors report={report} path="followup.call_window" />
            <Holidays value={f.holidays || []} onChange={set("followup.holidays")} />
            <FieldErrors report={report} path="followup.holidays" />
          </div>
          <div className="panel">
            <h3>{t("סדר הערוצים", "Channel order")}</h3>
            <div className="adm-locked-row"><Lock reason={t("תיקון עצמי באפליקציה תמיד קודם לכל פנייה", "In-app self-correction always comes before any contact")} />
              {t(<span className="small">ראשון תמיד: <b>תיקון עצמי באפליקציה</b> (נעול)</span>,
                <span className="small">Always first: <b>in-app self-correction</b> (locked)</span>)}</div>
            <label className="adm-field"><span className="adm-label">{t("אחר כך", "Then")}</span>
              <select value={after} onChange={(e) => set("followup.channel_order")(["in_app", ...JSON.parse(e.target.value)])} data-testid="f-channels">
                {AFTER_APP.map(([label, rest]) => <option key={label} value={JSON.stringify(rest)}>{t(label, AFTER_APP_EN[label])}</option>)}
              </select></label>
            <FieldErrors report={report} path="followup.channel_order" />
            <h3 style={{ marginTop: 14 }}>{t("שיחות וקישורים", "Calls and links")}</h3>
            <div className="adm-fields">
              <NumberField label={t("תוקף קישור להעלאה", "Upload link validity")} value={talk.link_ttl_minutes} min={15} max={10080} unit={t("דקות", "minutes")} path="talk.link_ttl_minutes"
                report={report} onChange={set("talk.link_ttl_minutes")} />
              <NumberField label={t("שגיאות ספק עד עצירה", "Provider errors before stopping")} value={talk.max_provider_errors} min={0} max={5} unit={t("שגיאות", "errors")} path="talk.max_provider_errors"
                report={report} onChange={set("talk.max_provider_errors")} />
              <NumberField label={t("בירור שיחה בסטטוס לא ידוע אחרי", "Check a call with unknown status after")} value={talk.reconcile_after_minutes} min={1} max={120} unit={t("דקות", "minutes")}
                path="talk.reconcile_after_minutes" report={report} onChange={set("talk.reconcile_after_minutes")} />
            </div>
          </div>
          <KillSwitch settings={settings} onChange={onKillSwitch} />
          <div className="panel" data-testid="locked-rules">
            <h3><Lock reason={t("כללי הגנה בקוד", "Safeguards in code")} /> {t("כללי הגנה קבועים", "Fixed safeguards")}</h3>
            <div className="small muted" style={{ marginBottom: 6 }}>{t("כללים אלה קבועים בקוד ואינם ניתנים לשינוי בהגדרות או בהנחיות. הם גוברים על כל כלל אחר.", "These rules are fixed in code and can't be changed in the settings or the instructions. They override every other rule.")}</div>
            <ul className="adm-rules">{settings.locked_rules.map((r) => (
              <li key={r.id}><span className="ltr tiny muted">{r.id}</span> <Loc he={r.label_he} en={r.label_en} /></li>
            ))}</ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function Holidays({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const { t } = useLang();
  const [day, setDay] = useState("");
  return (
    <div style={{ marginTop: 12 }}>
      <div className="adm-label">{t("ימי חג ללא פניות", "Holidays with no contact")}</div>
      <div className="row wrap" style={{ gap: 4, margin: "6px 0" }}>
        {value.map((d) => (
          <span key={d} className="chip">{new Date(d + "T12:00:00").toLocaleDateString(localeL())}
            <button className="adm-x" aria-label={t(`הסרת ${d}`, `Remove ${d}`)} onClick={() => onChange(value.filter((x) => x !== d))}>×</button></span>
        ))}
        {!value.length && <span className="tiny muted">{t("אין", "None")}</span>}
      </div>
      <span className="row"><input type="date" value={day} onChange={(e) => setDay(e.target.value)} aria-label={t("תאריך חג", "Holiday date")} />
        <button className="btn btn-ghost btn-sm" disabled={!day || value.includes(day)}
          onClick={() => { onChange([...value, day].sort()); setDay(""); }}>{t("הוספה", "Add")}</button></span>
    </div>
  );
}

function KillSwitch({ settings, onChange }: { settings: Settings; onChange: (paused: boolean, reason: string) => Promise<void> }) {
  const { t } = useLang();
  const ks = settings.kill_switch;
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className={`panel adm-kill${ks.value ? " on" : ""}`} data-testid="kill-switch">
      <h3>{t("מתג חירום", "Emergency switch")}</h3>
      <div className="row between wrap">
        <span className="small">{ks.value
          ? <><Chip tone="bad">{t("פעיל", "On")}</Chip> {t("אין אף פנייה יזומה ללקוחות. העלאת מסמכים ובדיקתם ממשיכות כרגיל.", "No proactive contact with customers at all. Document uploads and reviews continue as usual.")}</>
          : <><Chip tone="ok">{t("כבוי", "Off")}</Chip> {t("המעקב פועל לפי המדיניות הפעילה.", "Follow-up runs according to the active policy.")}</>}</span>
        {ks.updated_at && <When at={ks.updated_at} by={actorHe(ks.updated_by, settings.caller)} />}
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <input className="adm-cell grow" placeholder={t("סיבה (לא חובה)", "Reason (optional)")} value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} />
        <button className={`btn btn-sm ${ks.value ? "btn-dark" : "btn-orange"}`} disabled={busy} data-testid="kill-toggle"
          onClick={async () => { setBusy(true); await onChange(!ks.value, reason); setReason(""); setBusy(false); }}>
          {ks.value ? t("החזרת המעקב לפעולה", "Resume follow-up") : t("עצירת כל הפניות היזומות", "Stop all proactive contact")}</button>
      </div>
      <div className="tiny muted" style={{ marginTop: 6 }}>{t("המתג פועל מיד, בלי טיוטה והפעלה, ונרשם ביומן.", "The switch takes effect immediately, without a draft or publishing, and is recorded in the log.")}</div>
    </div>
  );
}
