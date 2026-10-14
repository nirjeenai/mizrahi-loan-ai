import { Fragment, useEffect, useState } from "react";
import { actorHe, adminApi, KIND_HE, STATUS_HE, type AuditEvent, type DiffEntry, type Kind, type ScenarioResult, type Settings, type SimulationRun, type VersionRow } from "../../adminApi";
import { timeHe } from "../../api";
import { Chip } from "../banker/deskUi";
import type { Work } from "./AdminPage";
import { DiffTable } from "./ui";

const KINDS: Kind[] = ["loan_policy", "talk_prompt"];
const STATUS_TONE: Record<string, string> = { PUBLISHED: "ok", DRAFT: "info", ARCHIVED: "neutral", DISCARDED: "neutral" };
const EVENT_HE: Record<string, string> = {
  "settings.draft_saved.v1": "טיוטה נשמרה", "settings.draft_discarded.v1": "טיוטה בוטלה", "settings.policy_published.v1": "מדיניות הופעלה",
  "settings.prompt_published.v1": "הנחיות הופעלו", "settings.rollback_applied.v1": "שחזור גרסה", "settings.kill_switch_changed.v1": "מתג חירום",
  "policy.simulation_completed.v1": "הרצת סימולציה",
};

export function VersionsTab({ settings, work, refresh, bars, onRollback }: {
  settings: Settings; work: Record<Kind, Work>; refresh: number; bars: Record<Kind, JSX.Element>;
  onRollback: (kind: Kind, to: string, reason: string) => Promise<void>;
}) {
  const [log, setLog] = useState<{ events: AuditEvent[]; versions: Record<Kind, VersionRow[]> } | null>(null);
  useEffect(() => { adminApi.audit(80).then(setLog).catch(() => setLog(null)); }, [refresh]);
  return (
    <div className="adm-tab" data-testid="tab-body-versions">
      {settings.simulator_available ? <Simulator settings={settings} work={work.loan_policy} /> : (
        <div className="panel" data-testid="simulator">
          <h3>סימולציית מדיניות</h3>
          <div className="adm-waiting">
            <Chip>ממתין למנוע המדיניות</Chip>
            <span className="small muted">כאן תרוץ הטיוטה על תרחישי הבדיקה של מנוע המעקב, עם פעולה צפויה מול פעולה בפועל לכל תרחיש.</span>
            <button className="btn btn-ghost btn-sm" disabled>הרצת סימולציה</button>
          </div>
        </div>
      )}
      {KINDS.map((k) => (
        <div key={k}>
          {bars[k]}
          <div className="panel" data-testid={`pending-${k}`}>
            <h3>שינויים בטיוטה לעומת הגרסה הפעילה · {KIND_HE[k]}</h3>
            <DiffTable diff={work[k].report?.diff || []} testId={`pending-diff-${k}`} />
          </div>
        </div>
      ))}
      <div className="grid2">
        {KINDS.map((k) => <History key={k} kind={k} rows={log?.versions[k] || []} settings={settings} onRollback={onRollback} />)}
      </div>
      <div className="panel" data-testid="audit">
        <h3>יומן שינויים בהגדרות</h3>
        <table className="t">
          <thead><tr><th>זמן</th><th>מי</th><th>פעולה</th><th>גרסה</th><th>פרטים</th></tr></thead>
          <tbody>{(log?.events || []).map((e) => (
            <tr key={e.event_id}>
              <td className="ltr tiny">{timeHe(e.occurred_at)}</td>
              <td className="tiny">{actorHe(e.actor, settings.caller)}</td>
              <td className="tiny">{EVENT_HE[e.type] || e.type}{e.payload.action === "created" ? " (חדשה)" : ""}</td>
              <td className="ltr tiny">{e.payload.label || (e.payload.key ? (e.payload.after ? "ON" : "OFF") : "")}</td>
              <td className="tiny muted">{details(e)}</td>
            </tr>
          ))}</tbody>
        </table>
        {log && !log.events.length && <div className="small muted">אין עדיין שינויים.</div>}
      </div>
    </div>
  );
}

const ACTION_HE: Record<string, string> = {
  NO_ACTION: "אין פעולה", IN_APP_ONLY: "תיקון באפליקציה בלבד", IN_APP_NUDGE: "תזכורת באפליקציה", SUPPRESS: "השהיה (פעילות בתהליך)",
  WAIT: "המתנה", SCHEDULE_CALL: "תזמון שיחה", DISPATCH_NOW: "שיחה עכשיו", BLOCK: "חסימה", SNOOZE: "דחייה לבקשת הלקוח",
  ESCALATE: "העברה לבנקאי", RESOLVE_AND_CANCEL: "הושלם, ביטול פניות",
};

const at = (iso: string | null) => iso ? new Date(iso).toLocaleString("he-IL", { timeZone: "Asia/Jerusalem", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "ללא מועד";

/** Which part of the expectation the decision missed (the parts contract.matches compares). */
function mismatchHe(r: ScenarioResult): string {
  if (!r.actual) return `שגיאה בהרצה: ${r.error}`;
  const e = r.expected, d = r.actual, parts: string[] = [];
  if (d.action !== e.action) parts.push(`פעולה צפויה ${ACTION_HE[e.action] || e.action}`);
  const missing = e.rule_ids_include.filter((x) => !d.rule_ids.includes(x));
  if (missing.length) parts.push(`חסרים כללים: ${missing.join(", ")}`);
  const unblocked = e.blocked_by_include.filter((x) => !d.blocked_by.includes(x));
  if (unblocked.length) parts.push(`לא נחסם לפי: ${unblocked.join(", ")}`);
  if (e.next_eligible_at && (!d.next_eligible_at || new Date(d.next_eligible_at).getTime() !== new Date(e.next_eligible_at).getTime()))
    parts.push(`מועד הפנייה הבא: צפוי ${at(e.next_eligible_at)}, בפועל ${at(d.next_eligible_at)}`);
  return parts.join(" · ");
}

/** The draft (as edited, saved or not) through every scenario fixture of the follow-up engine. */
function Simulator({ settings, work }: { settings: Settings; work: Work }) {
  const [run, setRun] = useState<SimulationRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedOnly, setFailedOnly] = useState(false);
  const go = async () => {
    setBusy(true); setError(null);
    try { setRun(await adminApi.simulate(work.config, !work.dirty && work.draft ? work.draft.version_id : null)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const results = (run?.results || []).filter((r) => !failedOnly || !r.passed);
  const failed = run ? run.results.filter((r) => !r.passed) : [];
  const label = (id: string) => settings.rule_labels[id]?.label_he || id;
  const subject = work.dirty ? "העריכה הנוכחית (לא נשמרה)" : work.draft ? `טיוטה v${work.draft.number}` : `הגרסה הפעילה v${settings.published.loan_policy.number}`;
  return (
    <div className="panel" data-testid="simulator">
      <div className="row between wrap">
        <h3 style={{ margin: 0 }}>סימולציית מדיניות · {subject}</h3>
        <span className="row">
          {run && <label className="small row" style={{ gap: 4 }}><input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} />רק כשלים</label>}
          <button className="btn btn-dark btn-sm" onClick={go} disabled={busy} data-testid="simulate">{busy && <span className="spinner" />}הרצת סימולציה</button>
        </span>
      </div>
      <div className="small muted" style={{ margin: "6px 0 10px" }}>
        מנוע המעקב מקבל את מדיניות המעקב וההשלמה שבטיוטה ומחליט בכל תרחיש בדיקה (לקוח פעיל, עזב, מחוץ לשעות, אין הסכמה ועוד) מה לעשות.
        ההרצה אינה נוגעת בתיקים ואינה יוצרת פניות; היא נרשמת ביומן. תרחישי חובה שנכשלים חוסמים את ההפעלה.
      </div>
      {error && <div className="adm-err" role="alert">{error}</div>}
      {run && (
        <>
          <div className="row wrap" style={{ marginBottom: 8 }} data-testid="sim-summary">
            <Chip tone={run.mandatory_passed ? "ok" : "bad"}>{run.mandatory_passed ? "כל תרחישי החובה עברו" : "תרחישי חובה נכשלו: אי אפשר להפעיל"}</Chip>
            <Chip>{run.results.length - failed.length}/{run.results.length} עברו</Chip>
            <Chip tone="info">ללא תופעות לוואי</Chip>
            <span className="tiny muted ltr">{run.run_id} · {timeHe(run.created_at)}</span>
          </div>
          <table className="t adm-sim" data-testid="sim-table">
            <thead><tr><th>תרחיש</th><th>תוצאה</th><th>צפוי</th><th>בפועל</th><th>כללים והסבר</th></tr></thead>
            <tbody>{results.map((r) => (
              <tr key={r.scenario_id} className={r.passed ? "" : "adm-sim-fail"} data-testid={`sim-${r.scenario_id}`}>
                <td><span className="ltr bold tiny">{r.scenario_id}</span> {r.mandatory && <Chip tone="navy">חובה</Chip>}<div className="tiny">{r.title_he}</div></td>
                <td><Chip tone={r.passed ? "ok" : r.mandatory ? "bad" : "warn"}>{r.passed ? "עבר" : "נכשל"}</Chip></td>
                <td className="tiny">{ACTION_HE[r.expected.action] || r.expected.action}<div className="muted"><span className="ltr">{r.expected.action}</span></div></td>
                <td className="tiny">{r.actual ? <>{ACTION_HE[r.actual.action] || r.actual.action}<div className="muted"><span className="ltr">{r.actual.action}</span></div></> : null}
                  {!r.passed && <div className="adm-err" data-testid={`sim-gap-${r.scenario_id}`}>{mismatchHe(r)}</div>}</td>
                <td className="tiny">
                  {r.actual && <>
                    <div>{r.actual.explanation_he}</div>
                    <div className="adm-rule-ids">{r.actual.rule_ids.map((id) => (
                      <span key={id} className={`chip ${r.actual!.blocked_by.includes(id) ? "bad" : ""}`} title={label(id)}><span className="ltr">{id}</span></span>
                    ))}</div>
                  </>}
                </td>
              </tr>
            ))}</tbody>
          </table>
        </>
      )}
    </div>
  );
}

function details(e: AuditEvent): string {
  const p = e.payload;
  const parts: string[] = [];
  if (p.restored_label) parts.push(`העתק של ${p.restored_label}`);
  if (p.previous_label) parts.push(`במקום ${p.previous_label}`);
  if (Array.isArray(p.paths) && p.paths.length) parts.push(`${p.paths.length} שדות: ${p.paths.slice(0, 3).join(", ")}${p.paths.length > 3 ? "…" : ""}`);
  if (p.reason) parts.push(p.reason);
  return parts.join(" · ");
}

function History({ kind, rows, settings, onRollback }: {
  kind: Kind; rows: VersionRow[]; settings: Settings; onRollback: (kind: Kind, to: string, reason: string) => Promise<void>;
}) {
  const [open, setOpen] = useState<{ id: string; diff: DiffEntry[]; against: string } | null>(null);
  const [rollback, setRollback] = useState<{ id: string; reason: string } | null>(null);
  const shown = rows.filter((r) => r.status !== "DISCARDED");
  const compare = async (r: VersionRow) => {
    if (open?.id === r.version_id) return setOpen(null);
    const prev = shown.find((x) => x.number < r.number && x.status !== "DRAFT");
    const res = await adminApi.diff(r.version_id, prev?.version_id).catch(() => null);
    if (res) setOpen({ id: r.version_id, diff: res.diff, against: res.against?.label || "—" });
  };
  return (
    <div className="panel" data-testid={`history-${kind}`}>
      <h3>היסטוריית גרסאות · {KIND_HE[kind]}</h3>
      <table className="t">
        <thead><tr><th>גרסה</th><th>מצב</th><th>נוצרה</th><th>הופעלה</th><th /></tr></thead>
        <tbody>{shown.map((r) => (
          <Fragment key={r.version_id}>
            <tr data-testid={`version-${kind}-${r.number}`}>
              <td className="ltr bold">v{r.number}</td>
              <td><Chip tone={STATUS_TONE[r.status]}>{STATUS_HE[r.status]}</Chip></td>
              <td className="tiny">{actorHe(r.author, settings.caller)}<div className="muted"><span className="ltr">{timeHe(r.created_at)}</span></div></td>
              <td className="tiny">{r.published_at ? <>{actorHe(r.published_by, settings.caller)}<div className="muted"><span className="ltr">{timeHe(r.published_at)}</span></div></> : "—"}</td>
              <td className="tiny adm-row-actions">
                <button className="link small" onClick={() => compare(r)}>{open?.id === r.version_id ? "סגירה" : "השוואה"}</button>
                {r.status === "ARCHIVED" && <button className="link small" data-testid={`rollback-${kind}-${r.number}`}
                  onClick={() => setRollback({ id: r.version_id, reason: "" })}>שחזור</button>}
              </td>
            </tr>
            {r.change_reason && <tr key={`${r.version_id}-why`} className="adm-why"><td /><td colSpan={4} className="tiny muted">{r.change_reason}</td></tr>}
            {rollback?.id === r.version_id && (
              <tr key={`${r.version_id}-rb`}><td colSpan={5}>
                <div className="adm-confirm" data-testid={`rollback-confirm-${kind}`}>
                  <span className="small">לשחזר את v{r.number}? תיווצר גרסה חדשה עם אותה תצורה, וההיסטוריה נשמרת.</span>
                  <input className="adm-cell grow" placeholder="סיבה (לא חובה)" value={rollback.reason} maxLength={300}
                    onChange={(e) => setRollback({ ...rollback, reason: e.target.value })} />
                  <button className="btn btn-dark btn-sm" data-testid={`rollback-go-${kind}`}
                    onClick={async () => { const reason = rollback.reason; setRollback(null); await onRollback(kind, r.version_id, reason); }}>שחזור</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setRollback(null)}>חזרה</button>
                </div>
              </td></tr>
            )}
            {open?.id === r.version_id && (
              <tr key={`${r.version_id}-diff`}><td colSpan={5}>
                <div className="tiny muted">לעומת {open.against}</div><DiffTable diff={open.diff} />
              </td></tr>
            )}
          </Fragment>
        ))}</tbody>
      </table>
    </div>
  );
}
