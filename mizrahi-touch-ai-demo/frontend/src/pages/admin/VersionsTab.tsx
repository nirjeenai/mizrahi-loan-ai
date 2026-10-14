import { Fragment, useEffect, useState } from "react";
import { actorHe, adminApi, KIND_HE, STATUS_HE, type AuditEvent, type DiffEntry, type Kind, type Settings, type VersionRow } from "../../adminApi";
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
      <div className="panel" data-testid="simulator">
        <h3>סימולציית מדיניות</h3>
        {settings.simulator_available ? <div className="small">הסימולטור זמין.</div> : (
          <div className="adm-waiting">
            <Chip>ממתין למנוע המדיניות</Chip>
            <span className="small muted">כאן תרוץ הטיוטה על תרחישי הבדיקה של מנוע המעקב (פעיל בפורטל, עזב, מחוץ לשעות, אין הסכמה ועוד),
              עם פעולה צפויה מול פעולה בפועל לכל תרחיש. אין הרצה ואין תוצאות עד שהמנוע יחובר.</span>
            <button className="btn btn-ghost btn-sm" disabled>הרצת סימולציה</button>
          </div>
        )}
      </div>
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
