import { useRef, useState, type ReactNode } from "react";
import { actorHe, KIND_HE, renderPreview, type DiffEntry, type Kind, type LintFinding, type Report, type Settings } from "../../adminApi";
import { Chip } from "../banker/deskUi";
import type { Work } from "./AdminPage";

export const VAR_HE: Record<string, string> = {
  first_name: "שם פרטי", missing_documents: "המסמכים החסרים", secure_upload_link: "קישור מאובטח להעלאה", next_step: "הצעד הבא",
};

export function Lock({ reason }: { reason: string }) {
  return <span className="adm-lock" title={reason} aria-label={`נעול: ${reason}`}>🔒</span>;
}

/** Errors the service reported for one path (or anything under it). */
export function errorsAt(report: Report | null, path: string): string[] {
  return (report?.errors || []).filter((e) => e.path === path || e.path.startsWith(path + ".")).map((e) => e.message);
}

export function FieldErrors({ report, path }: { report: Report | null; path: string }) {
  const errs = errorsAt(report, path);
  return errs.length ? <div className="adm-err" role="alert">{errs.map((m) => <div key={m}>{m}</div>)}</div> : null;
}

export function NumberField({ label, value, onChange, min, max, step = 1, unit, hint, path, report, testId }: {
  label: string; value: unknown; onChange: (v: number | "") => void; min: number; max: number; step?: number; unit?: string;
  hint?: ReactNode; path: string; report: Report | null; testId?: string;
}) {
  const bad = errorsAt(report, path).length > 0;
  return (
    <label className={`adm-field${bad ? " bad" : ""}`}>
      <span className="adm-label">{label}</span>
      <span className="adm-input-row">
        <input type="number" min={min} max={max} step={step} value={value === undefined || value === null ? "" : String(value)}
          data-testid={testId} data-path={path}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />
        {unit && <span className="small muted">{unit}</span>}
      </span>
      <span className="tiny muted">טווח {min}–{max}{hint ? <> · {hint}</> : null}</span>
      <FieldErrors report={report} path={path} />
    </label>
  );
}

export function Toggle({ label, checked, onChange, hint, disabled, testId }: {
  label: ReactNode; checked: boolean; onChange: (v: boolean) => void; hint?: ReactNode; disabled?: boolean; testId?: string;
}) {
  return (
    <label className={`adm-toggle${disabled ? " disabled" : ""}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} data-testid={testId} />
      <span><span className="bold small">{label}</span>{hint && <span className="tiny muted adm-block">{hint}</span>}</span>
    </label>
  );
}

/** A text area with variable chips that insert `{{name}}` at the cursor. */
export function VarText({ value, onChange, variables, rows = 3, testId, maxLength }: {
  value: string; onChange: (v: string) => void; variables: string[]; rows?: number; testId?: string; maxLength?: number;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const insert = (name: string) => {
    const el = ref.current;
    const token = `{{${name}}}`;
    const at = el ? el.selectionStart : value.length;
    const end = el ? el.selectionEnd : value.length;
    onChange(value.slice(0, at) + token + value.slice(end));
    requestAnimationFrame(() => { if (el) { el.focus(); el.selectionStart = el.selectionEnd = at + token.length; } });
  };
  return (
    <div className="adm-vartext">
      <textarea ref={ref} rows={rows} value={value} maxLength={maxLength} onChange={(e) => onChange(e.target.value)} data-testid={testId} />
      <div className="row wrap" style={{ gap: 4 }}>
        <span className="tiny muted">הוספת משתנה:</span>
        {variables.map((v) => (
          <button key={v} type="button" className="adm-var" onClick={() => insert(v)} title={VAR_HE[v]}>
            <span className="ltr">{`{{${v}}}`}</span> {VAR_HE[v]}</button>
        ))}
      </div>
    </div>
  );
}

/** Lint findings for one path, with the matched words highlighted. */
export function LintList({ lint, path }: { lint: LintFinding[]; path: string }) {
  const items = lint.filter((f) => f.path === path);
  if (!items.length) return null;
  return (
    <ul className="adm-lint" data-testid={`lint-${path}`}>
      {items.map((f, i) => (
        <li key={i} className={f.severity}>
          <Chip tone={f.severity === "error" ? "bad" : "warn"}>{f.severity === "error" ? "שגיאה" : "אזהרה"}</Chip>
          {f.match && <mark>{f.match}</mark>} {f.message_he}
        </li>
      ))}
    </ul>
  );
}

export function Preview({ text, vars, label = "תצוגה מקדימה" }: { text: string; vars: Settings["preview_variables"]; label?: string }) {
  return (
    <div className="adm-preview">
      <div className="tiny muted">{label} · ערכי הדגמה</div>
      <div className="adm-preview-text">{renderPreview(text, vars)}</div>
    </div>
  );
}

const show = (v: unknown) => v === undefined ? "—" : typeof v === "string" ? v : JSON.stringify(v);

export function DiffTable({ diff, testId }: { diff: DiffEntry[]; testId?: string }) {
  if (!diff.length) return <div className="small muted">אין שינויים.</div>;
  return (
    <table className="t adm-diff" data-testid={testId}>
      <thead><tr><th>שדה</th><th>לפני</th><th>אחרי</th></tr></thead>
      <tbody>{diff.map((d) => (
        <tr key={d.path}><td className="ltr tiny">{d.path}</td>
          <td className="adm-before">{show(d.before)}</td><td className="adm-after">{show(d.after)}</td></tr>
      ))}</tbody>
    </table>
  );
}

/** Save · publish · discard for one kind, with the live check summary and the pending changes. */
export function ActionBar({ kind, work, settings, onSave, onPublish, onDiscard, onReload }: {
  kind: Kind; work: Work; settings: Settings; onSave: () => void; onPublish: () => void; onDiscard: () => void; onReload: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const published = settings.published[kind];
  const r = work.report;
  const changes = r?.diff.length || 0;
  const errors = r?.errors.length || 0;
  const warnings = r?.warnings.length || 0;
  const busy = !!work.busy;
  const state = work.dirty ? <Chip tone="warn">שינויים שלא נשמרו</Chip>
    : work.draft ? <Chip tone="info" testId={`draft-chip-${kind}`}>טיוטה v{work.draft.number} נשמרה · לא פעילה</Chip>
      : <Chip tone="ok">תואם לגרסה הפעילה</Chip>;
  return (
    <div className="adm-actions" data-testid={`actions-${kind}`}>
      <div className="adm-actions-row">
        <div className="adm-actions-state">
          <span className="bold">{KIND_HE[kind]}</span>
          <span className="small muted">פעילה: <span className="ltr">v{published.number}</span> · {actorHe(published.published_by, settings.caller)}</span>
          {state}
          {r && (errors ? <Chip tone="bad">{errors} שגיאות</Chip> : <Chip tone="ok">תקין</Chip>)}
          {r && warnings > 0 && <Chip tone="warn">{warnings} אזהרות</Chip>}
          {changes > 0 && <button className="link small" onClick={() => setShowDiff(!showDiff)} data-testid={`diff-toggle-${kind}`}>
            {showDiff ? "הסתרת השינויים" : `מה ישתנה (${changes})`}</button>}
        </div>
        <div className="adm-actions-btns">
          {busy && <span className="spinner" />}
          <button className="btn btn-ghost btn-sm" disabled={busy || !work.dirty} onClick={onSave} data-testid={`save-${kind}`}>שמירת טיוטה</button>
          <button className="btn btn-dark btn-sm" disabled={busy || !changes || errors > 0} onClick={() => setConfirm(true)}
            data-testid={`publish-${kind}`}>שמירה והפעלה</button>
          <button className="btn btn-soft btn-sm" disabled={busy || (!work.dirty && !work.draft)} onClick={onDiscard}
            data-testid={`discard-${kind}`}>ביטול השינויים</button>
        </div>
      </div>
      {confirm && (
        <div className="adm-confirm" data-testid={`confirm-${kind}`}>
          <span className="small">
            להפעיל {changes} שינויים ב{KIND_HE[kind]}? מנגנון המעקב יפעל לפיהם מיד.
            {kind === "loan_policy" ? " דרישות המסמכים חלות על תיקים חדשים; תיק פתוח נשאר על הגרסה שננעלה לו." : ""}
          </span>
          <span className="row">
            <button className="btn btn-dark btn-sm" onClick={() => { setConfirm(false); onPublish(); }} data-testid={`confirm-publish-${kind}`}>הפעלה</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setConfirm(false)}>חזרה</button>
          </span>
        </div>
      )}
      {work.reasons.length > 0 && (
        <div className="adm-err adm-reasons" role="alert" data-testid={`reasons-${kind}`}>
          {work.reasons.map((m) => <div key={m}>• {m}</div>)}
          {work.stale && <button className="link small" onClick={onReload}>טעינת הטיוטה העדכנית</button>}
        </div>
      )}
      {showDiff && r && <div style={{ marginTop: 8 }}><DiffTable diff={r.diff} /></div>}
    </div>
  );
}
