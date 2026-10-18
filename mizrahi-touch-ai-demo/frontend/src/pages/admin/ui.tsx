import { useRef, useState, type ReactNode } from "react";
import { actorHe, kindL, renderPreview, type DiffEntry, type Kind, type LintFinding, type Report, type Settings } from "../../adminApi";
import { tr, useLang } from "../../i18n";
import { Chip } from "../banker/deskUi";
import type { Work } from "./AdminPage";

export const VAR_HE: Record<string, string> = {
  first_name: "שם פרטי", missing_documents: "המסמכים החסרים", secure_upload_link: "קישור מאובטח להעלאה", next_step: "הצעד הבא",
};
export const VAR_EN: Record<string, string> = {
  first_name: "First name", missing_documents: "Missing documents", secure_upload_link: "Secure upload link", next_step: "Next step",
};
const varL = (v: string) => tr(VAR_HE[v], VAR_EN[v]);

export function Lock({ reason }: { reason: string }) {
  return <span className="adm-lock" title={reason} aria-label={`${tr("נעול", "Locked")}: ${reason}`}>🔒</span>;
}

/** Errors the service reported for one path (or anything under it). */
export function errorsAt(report: Report | null, path: string): string[] {
  return (report?.errors || []).filter((e) => e.path === path || e.path.startsWith(path + ".")).map((e) => tr(e.message, e.message_en || e.message));
}

export function FieldErrors({ report, path }: { report: Report | null; path: string }) {
  useLang();
  const errs = errorsAt(report, path);
  return errs.length ? <div className="adm-err" role="alert">{errs.map((m) => <div key={m}>{m}</div>)}</div> : null;
}

export function NumberField({ label, value, onChange, min, max, step = 1, unit, hint, path, report, testId }: {
  label: string; value: unknown; onChange: (v: number | "") => void; min: number; max: number; step?: number; unit?: string;
  hint?: ReactNode; path: string; report: Report | null; testId?: string;
}) {
  const { t } = useLang();
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
      <span className="tiny muted">{t("טווח", "Range")} {min}–{max}{hint ? <> · {hint}</> : null}</span>
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
  const { en, t } = useLang();
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
      <textarea ref={ref} rows={rows} value={value} maxLength={maxLength} onChange={(e) => onChange(e.target.value)} data-testid={testId}
        {...(en ? { dir: "auto", lang: "he" } : {})} />
      <div className="row wrap" style={{ gap: 4 }}>
        <span className="tiny muted">{t("הוספת משתנה:", "Insert a variable:")}</span>
        {variables.map((v) => (
          <button key={v} type="button" className="adm-var" onClick={() => insert(v)} title={varL(v)}>
            <span className="ltr">{`{{${v}}}`}</span> {varL(v)}</button>
        ))}
      </div>
    </div>
  );
}

/** Lint findings for one path, with the matched words highlighted. */
export function LintList({ lint, path }: { lint: LintFinding[]; path: string }) {
  const { t } = useLang();
  const items = lint.filter((f) => f.path === path);
  if (!items.length) return null;
  return (
    <ul className="adm-lint" data-testid={`lint-${path}`}>
      {items.map((f, i) => (
        <li key={i} className={f.severity}>
          <Chip tone={f.severity === "error" ? "bad" : "warn"}>{f.severity === "error" ? t("שגיאה", "Error") : t("אזהרה", "Warning")}</Chip>
          {f.match && <mark>{f.match}</mark>} {t(f.message_he, f.message_en || f.message_he)}
        </li>
      ))}
    </ul>
  );
}

export function Preview({ text, vars, label }: { text: string; vars: Settings["preview_variables"]; label?: string }) {
  const { en, t } = useLang();
  return (
    <div className="adm-preview">
      <div className="tiny muted">{label ?? t("תצוגה מקדימה", "Preview")}</div>
      <div className="adm-preview-text" {...(en ? { dir: "auto", lang: "he" } : {})}>{renderPreview(text, vars)}</div>
    </div>
  );
}

const show = (v: unknown) => v === undefined ? "-" : typeof v === "string" ? v : JSON.stringify(v);

export function DiffTable({ diff, testId }: { diff: DiffEntry[]; testId?: string }) {
  const { t } = useLang();
  if (!diff.length) return <div className="small muted">{t("אין שינויים.", "No changes.")}</div>;
  return (
    <table className="t adm-diff" data-testid={testId}>
      <thead><tr><th>{t("שדה", "Field")}</th><th>{t("לפני", "Before")}</th><th>{t("אחרי", "After")}</th></tr></thead>
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
  const { t } = useLang();
  const [confirm, setConfirm] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const published = settings.published[kind];
  const r = work.report;
  const changes = r?.diff.length || 0;
  const errors = r?.errors.length || 0;
  const warnings = r?.warnings.length || 0;
  const busy = !!work.busy;
  const state = work.dirty ? <Chip tone="warn">{t("שינויים שלא נשמרו", "Unsaved changes")}</Chip>
    : work.draft ? <Chip tone="info" testId={`draft-chip-${kind}`}>{t(<>טיוטה v{work.draft.number} נשמרה · לא פעילה</>, <>Draft v{work.draft.number} saved · not active</>)}</Chip>
      : <Chip tone="ok">{t("תואם לגרסה הפעילה", "Matches the active version")}</Chip>;
  return (
    <div className="adm-actions" data-testid={`actions-${kind}`}>
      <div className="adm-actions-row">
        <div className="adm-actions-state">
          <span className="bold">{kindL(kind)}</span>
          <span className="small muted">{t("פעילה", "Active")}: <span className="ltr">v{published.number}</span> · {actorHe(published.published_by, settings.caller)}</span>
          {state}
          {r && (errors ? <Chip tone="bad">{t(<>{errors} שגיאות</>, <>{errors} {errors === 1 ? "error" : "errors"}</>)}</Chip> : <Chip tone="ok">{t("תקין", "Valid")}</Chip>)}
          {r && warnings > 0 && <Chip tone="warn">{t(<>{warnings} אזהרות</>, <>{warnings} {warnings === 1 ? "warning" : "warnings"}</>)}</Chip>}
          {changes > 0 && <button className="link small" onClick={() => setShowDiff(!showDiff)} data-testid={`diff-toggle-${kind}`}>
            {showDiff ? t("הסתרת השינויים", "Hide changes") : t(`מה ישתנה (${changes})`, `What will change (${changes})`)}</button>}
        </div>
        <div className="adm-actions-btns">
          {busy && <span className="spinner" />}
          <button className="btn btn-ghost btn-sm" disabled={busy || !work.dirty} onClick={onSave} data-testid={`save-${kind}`}>{t("שמירת טיוטה", "Save draft")}</button>
          <button className="btn btn-dark btn-sm" disabled={busy || !changes || errors > 0} onClick={() => setConfirm(true)}
            data-testid={`publish-${kind}`}>{t("שמירה והפעלה", "Save and publish")}</button>
          <button className="btn btn-soft btn-sm" disabled={busy || (!work.dirty && !work.draft)} onClick={onDiscard}
            data-testid={`discard-${kind}`}>{t("ביטול השינויים", "Discard changes")}</button>
        </div>
      </div>
      {confirm && (
        <div className="adm-confirm" data-testid={`confirm-${kind}`}>
          {t(<span className="small">
            להפעיל {changes} שינויים ב{kindL(kind)}? מנגנון המעקב יפעל לפיהם מיד.
            {kind === "loan_policy" ? " דרישות המסמכים חלות על תיקים חדשים; תיק פתוח נשאר על הגרסה שננעלה לו." : ""}
          </span>, <span className="small">
            Publish {changes} {changes === 1 ? "change" : "changes"} to the {kindL(kind).toLowerCase()}? The follow-up engine applies {changes === 1 ? "it" : "them"} immediately.
            {kind === "loan_policy" ? " Document requirements apply to new cases; an open case stays on the version it was locked to." : ""}
          </span>)}
          <span className="row">
            <button className="btn btn-dark btn-sm" onClick={() => { setConfirm(false); onPublish(); }} data-testid={`confirm-publish-${kind}`}>{t("הפעלה", "Publish")}</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setConfirm(false)}>{t("חזרה", "Back")}</button>
          </span>
        </div>
      )}
      {work.reasons.length > 0 && (
        <div className="adm-err adm-reasons" role="alert" data-testid={`reasons-${kind}`}>
          {work.reasons.map((m) => <div key={m}>• {m}</div>)}
          {work.stale && <button className="link small" onClick={onReload}>{t("טעינת הטיוטה העדכנית", "Load the latest draft")}</button>}
        </div>
      )}
      {showDiff && r && <div style={{ marginTop: 8 }}><DiffTable diff={r.diff} /></div>}
    </div>
  );
}
