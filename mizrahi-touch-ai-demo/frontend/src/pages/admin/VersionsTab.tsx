import { Fragment, useEffect, useState } from "react";
import { actorHe, adminApi, kindL, statusL, type AsConfigured, type AuditEvent, type DiffEntry, type Kind, type ScenarioResult, type Settings, type SimulationRun, type VersionRow } from "../../adminApi";
import { localeL, timeL as timeHe } from "../../api";
import { Loc, loc, tr, useLang } from "../../i18n";
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
const EVENT_EN: Record<string, string> = {
  "settings.draft_saved.v1": "Draft saved", "settings.draft_discarded.v1": "Draft discarded", "settings.policy_published.v1": "Policy published",
  "settings.prompt_published.v1": "Instructions published", "settings.rollback_applied.v1": "Version rollback", "settings.kill_switch_changed.v1": "Emergency switch",
  "policy.simulation_completed.v1": "Simulation run",
};

export function VersionsTab({ settings, work, refresh, bars, onRollback }: {
  settings: Settings; work: Record<Kind, Work>; refresh: number; bars: Record<Kind, JSX.Element>;
  onRollback: (kind: Kind, to: string, reason: string) => Promise<void>;
}) {
  const { t } = useLang();
  const [log, setLog] = useState<{ events: AuditEvent[]; versions: Record<Kind, VersionRow[]> } | null>(null);
  useEffect(() => { adminApi.audit(80).then(setLog).catch(() => setLog(null)); }, [refresh]);
  return (
    <div className="adm-tab" data-testid="tab-body-versions">
      {settings.simulator_available ? <Simulator settings={settings} work={work.loan_policy} /> : (
        <div className="panel" data-testid="simulator">
          <h3>{t("סימולציית מדיניות", "Policy simulation")}</h3>
          <div className="adm-waiting">
            <Chip>{t("ממתין למנוע המדיניות", "Waiting for the policy engine")}</Chip>
            <span className="small muted">{t("כאן תרוץ הטיוטה על תרחישי הבדיקה של מנוע המעקב, עם פעולה צפויה מול פעולה בפועל לכל תרחיש.", "Here the draft runs through the follow-up engine's test scenarios, with the expected action against the actual action for each scenario.")}</span>
            <button className="btn btn-ghost btn-sm" disabled>{t("הרצת סימולציה", "Run simulation")}</button>
          </div>
        </div>
      )}
      {KINDS.map((k) => (
        <div key={k}>
          {bars[k]}
          <div className="panel" data-testid={`pending-${k}`}>
            <h3>{t("שינויים בטיוטה לעומת הגרסה הפעילה", "Draft changes compared with the active version")} · {kindL(k)}</h3>
            <DiffTable diff={work[k].report?.diff || []} testId={`pending-diff-${k}`} />
          </div>
        </div>
      ))}
      <div className="grid2">
        {KINDS.map((k) => <History key={k} kind={k} rows={log?.versions[k] || []} settings={settings} onRollback={onRollback} />)}
      </div>
      <div className="panel" data-testid="audit">
        <h3>{t("יומן שינויים בהגדרות", "Settings change log")}</h3>
        <table className="t">
          <thead><tr><th>{t("זמן", "Time")}</th><th>{t("מי", "Who")}</th><th>{t("פעולה", "Action")}</th><th>{t("גרסה", "Version")}</th><th>{t("פרטים", "Details")}</th></tr></thead>
          <tbody>{(log?.events || []).map((e) => (
            <tr key={e.event_id}>
              <td className="ltr tiny">{timeHe(e.occurred_at)}</td>
              <td className="tiny">{actorHe(e.actor, settings.caller)}</td>
              <td className="tiny">{t(EVENT_HE[e.type], EVENT_EN[e.type]) || e.type}{e.payload.action === "created" ? t(" (חדשה)", " (new)") : ""}</td>
              <td className="ltr tiny">{e.payload.label || (e.payload.key ? (e.payload.after ? "ON" : "OFF") : "")}</td>
              <td className="tiny muted">{details(e)}</td>
            </tr>
          ))}</tbody>
        </table>
        {log && !log.events.length && <div className="small muted">{t("אין עדיין שינויים.", "No changes yet.")}</div>}
      </div>
    </div>
  );
}

const ACTION_HE: Record<string, string> = {
  NO_ACTION: "אין פעולה", IN_APP_ONLY: "תיקון באפליקציה בלבד", IN_APP_NUDGE: "תזכורת באפליקציה", SUPPRESS: "השהיה (פעילות בתהליך)",
  WAIT: "המתנה", SCHEDULE_CALL: "תזמון שיחה", DISPATCH_NOW: "שיחה עכשיו", BLOCK: "חסימה", SNOOZE: "דחייה לבקשת הלקוח",
  ESCALATE: "העברה לבנקאי", RESOLVE_AND_CANCEL: "הושלם, ביטול פניות",
};
const ACTION_EN: Record<string, string> = {
  NO_ACTION: "No action", IN_APP_ONLY: "In-app correction only", IN_APP_NUDGE: "In-app reminder", SUPPRESS: "Hold (activity in progress)",
  WAIT: "Wait", SCHEDULE_CALL: "Schedule a call", DISPATCH_NOW: "Call now", BLOCK: "Block", SNOOZE: "Postpone at the customer's request",
  ESCALATE: "Hand over to the banker", RESOLVE_AND_CANCEL: "Completed, contacts canceled",
};
const actionL = (a: string) => tr(ACTION_HE[a], ACTION_EN[a]) || a;

const at = (iso: string | null) => iso ? new Date(iso).toLocaleString(localeL(), { timeZone: "Asia/Jerusalem", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : tr("ללא מועד", "none");

/** Which part of the expectation the decision missed (the parts contract.matches compares). */
function mismatchHe(r: ScenarioResult): string {
  if (!r.actual) return `${tr("שגיאה בהרצה", "Run error")}: ${r.error}`;
  const e = r.expected, d = r.actual, parts: string[] = [];
  if (d.action !== e.action) parts.push(`${tr("פעולה צפויה", "Expected action:")} ${actionL(e.action)}`);
  const missing = e.rule_ids_include.filter((x) => !d.rule_ids.includes(x));
  if (missing.length) parts.push(`${tr("חסרים כללים", "Missing rules")}: ${missing.join(", ")}`);
  const unblocked = e.blocked_by_include.filter((x) => !d.blocked_by.includes(x));
  if (unblocked.length) parts.push(`${tr("לא נחסם לפי", "Not blocked by")}: ${unblocked.join(", ")}`);
  if (e.next_eligible_at && (!d.next_eligible_at || new Date(d.next_eligible_at).getTime() !== new Date(e.next_eligible_at).getTime()))
    parts.push(tr(`מועד הפנייה הבא: צפוי ${at(e.next_eligible_at)}, בפועל ${at(d.next_eligible_at)}`,
      `Next contact time: expected ${at(e.next_eligible_at)}, actual ${at(d.next_eligible_at)}`));
  return parts.join(" · ");
}

/** A scenario that pins timing values is checked with those values (a deterministic regression check); this line shows
 *  what the edited configuration itself does there, whenever that differs. */
function OwnValues({ r, own }: { r: ScenarioResult; own?: AsConfigured[string] }) {
  const { t } = useLang();
  if (!own || !r.actual) return null;
  const d = own.decision;
  const same = d.action === r.actual.action && (d.next_eligible_at ? new Date(d.next_eligible_at).getTime() : null)
    === (r.actual.next_eligible_at ? new Date(r.actual.next_eligible_at).getTime() : null);
  if (same) return null;
  return (
    <div className="adm-own" data-testid={`sim-own-${r.scenario_id}`} title={`${t("ערכים מקובעים בתרחיש", "Values pinned in the scenario")}: ${own.pinned.join(", ")}`}>
      {t("בהגדרות הטיוטה", "With the draft's settings")}: {actionL(d.action)}{d.next_eligible_at ? ` · ${at(d.next_eligible_at)}` : ""}
    </div>
  );
}

/** The draft (as edited, saved or not) through every scenario fixture of the follow-up engine. */
function Simulator({ settings, work }: { settings: Settings; work: Work }) {
  const { en, t } = useLang();
  const [run, setRun] = useState<SimulationRun | null>(null);
  const [own, setOwn] = useState<AsConfigured>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedOnly, setFailedOnly] = useState(false);
  const go = async () => {
    setBusy(true); setError(null);
    const version = !work.dirty && work.draft ? work.draft.version_id : null;
    try {
      const [r, o] = await Promise.all([adminApi.simulate(work.config, version), adminApi.asConfigured(work.config, version)]);
      setRun(r); setOwn(o);
    }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const results = (run?.results || []).filter((r) => !failedOnly || !r.passed);
  const failed = run ? run.results.filter((r) => !r.passed) : [];
  const label = (id: string) => (en ? loc(settings.rule_labels[id]?.label_he, settings.rule_labels[id]?.label_en) : settings.rule_labels[id]?.label_he) || id;
  const subject = work.dirty ? t("העריכה הנוכחית (לא נשמרה)", "the current edit (not saved)") : work.draft ? `${t("טיוטה", "draft")} v${work.draft.number}`
    : `${t("הגרסה הפעילה", "the active version")} v${settings.published.loan_policy.number}`;
  return (
    <div className="panel" data-testid="simulator">
      <div className="row between wrap">
        <h3 style={{ margin: 0 }}>{t("סימולציית מדיניות", "Policy simulation")} · {subject}</h3>
        <span className="row">
          {run && <label className="small row" style={{ gap: 4 }}><input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} />{t("רק כשלים", "Failures only")}</label>}
          <button className="btn btn-dark btn-sm" onClick={go} disabled={busy} data-testid="simulate">{busy && <span className="spinner" />}{t("הרצת סימולציה", "Run simulation")}</button>
        </span>
      </div>
      {en ? <div className="small muted" style={{ margin: "6px 0 10px" }}>
        The follow-up engine takes the draft's follow-up and completion policy and decides what to do in each test scenario (customer active, left,
        outside hours, no consent and more). The run doesn't touch any case or create any contact; it's recorded in the log. Failing mandatory
        scenarios block publishing.
      </div> : <div className="small muted" style={{ margin: "6px 0 10px" }}>
        מנוע המעקב מקבל את מדיניות המעקב וההשלמה שבטיוטה ומחליט בכל תרחיש בדיקה (לקוח פעיל, עזב, מחוץ לשעות, אין הסכמה ועוד) מה לעשות.
        ההרצה אינה נוגעת בתיקים ואינה יוצרת פניות; היא נרשמת ביומן. תרחישי חובה שנכשלים חוסמים את ההפעלה.
      </div>}
      {error && <div className="adm-err" role="alert">{error}</div>}
      {run && (
        <>
          <div className="row wrap" style={{ marginBottom: 8 }} data-testid="sim-summary">
            <Chip tone={run.mandatory_passed ? "ok" : "bad"}>{run.mandatory_passed ? t("כל תרחישי החובה עברו", "All mandatory scenarios passed") : t("תרחישי חובה נכשלו: אי אפשר להפעיל", "Mandatory scenarios failed: publishing is blocked")}</Chip>
            <Chip>{run.results.length - failed.length}/{run.results.length} {t("עברו", "passed")}</Chip>
            <Chip tone="info">{t("ללא תופעות לוואי", "No side effects")}</Chip>
            <span className="tiny muted ltr">{run.run_id} · {timeHe(run.created_at)}</span>
          </div>
          <table className="t adm-sim" data-testid="sim-table">
            <thead><tr><th>{t("תרחיש", "Scenario")}</th><th>{t("תוצאה", "Result")}</th><th>{t("צפוי", "Expected")}</th><th>{t("בפועל", "Actual")}</th><th>{t("כללים והסבר", "Rules and explanation")}</th></tr></thead>
            <tbody>{results.map((r) => (
              <tr key={r.scenario_id} className={r.passed ? "" : "adm-sim-fail"} data-testid={`sim-${r.scenario_id}`}>
                <td><span className="ltr bold tiny">{r.scenario_id}</span> {r.mandatory && <Chip tone="navy">{t("חובה", "Mandatory")}</Chip>}<div className="tiny"><Loc he={r.title_he} en={r.title_en} /></div></td>
                <td><Chip tone={r.passed ? "ok" : r.mandatory ? "bad" : "warn"}>{r.passed ? t("עבר", "Passed") : t("נכשל", "Failed")}</Chip></td>
                <td className="tiny">{actionL(r.expected.action)}<div className="muted"><span className="ltr">{r.expected.action}</span></div></td>
                <td className="tiny">{r.actual ? <>{actionL(r.actual.action)}<div className="muted"><span className="ltr">{r.actual.action}</span></div></> : null}
                  {!r.passed && <div className="adm-err" data-testid={`sim-gap-${r.scenario_id}`}>{mismatchHe(r)}</div>}
                  <OwnValues r={r} own={own[r.scenario_id]} /></td>
                <td className="tiny">
                  {r.actual && <>
                    <div><Loc he={r.actual.explanation_he} en={r.actual.explanation_en} /></div>
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
  if (p.restored_label) parts.push(`${tr("העתק של", "Copy of")} ${p.restored_label}`);
  if (p.previous_label) parts.push(`${tr("במקום", "Replacing")} ${p.previous_label}`);
  if (Array.isArray(p.paths) && p.paths.length) parts.push(`${p.paths.length} ${tr("שדות", p.paths.length === 1 ? "field" : "fields")}: ${p.paths.slice(0, 3).join(", ")}${p.paths.length > 3 ? "…" : ""}`);
  if (p.reason) parts.push(loc(p.reason, p.reason_en));
  return parts.join(" · ");
}

function History({ kind, rows, settings, onRollback }: {
  kind: Kind; rows: VersionRow[]; settings: Settings; onRollback: (kind: Kind, to: string, reason: string) => Promise<void>;
}) {
  const { t } = useLang();
  const [open, setOpen] = useState<{ id: string; diff: DiffEntry[]; against: string } | null>(null);
  const [rollback, setRollback] = useState<{ id: string; reason: string } | null>(null);
  const shown = rows.filter((r) => r.status !== "DISCARDED");
  const compare = async (r: VersionRow) => {
    if (open?.id === r.version_id) return setOpen(null);
    const prev = shown.find((x) => x.number < r.number && x.status !== "DRAFT");
    const res = await adminApi.diff(r.version_id, prev?.version_id).catch(() => null);
    if (res) setOpen({ id: r.version_id, diff: res.diff, against: res.against?.label || "-" });
  };
  return (
    <div className="panel" data-testid={`history-${kind}`}>
      <h3>{t("היסטוריית גרסאות", "Version history")} · {kindL(kind)}</h3>
      <table className="t">
        <thead><tr><th>{t("גרסה", "Version")}</th><th>{t("מצב", "Status")}</th><th>{t("נוצרה", "Created")}</th><th>{t("הופעלה", "Published")}</th><th /></tr></thead>
        <tbody>{shown.map((r) => (
          <Fragment key={r.version_id}>
            <tr data-testid={`version-${kind}-${r.number}`}>
              <td className="ltr bold">v{r.number}</td>
              <td><Chip tone={STATUS_TONE[r.status]}>{statusL(r.status)}</Chip></td>
              <td className="tiny">{actorHe(r.author, settings.caller)}<div className="muted"><span className="ltr">{timeHe(r.created_at)}</span></div></td>
              <td className="tiny">{r.published_at ? <>{actorHe(r.published_by, settings.caller)}<div className="muted"><span className="ltr">{timeHe(r.published_at)}</span></div></> : "-"}</td>
              <td className="tiny adm-row-actions">
                <button className="link small" onClick={() => compare(r)}>{open?.id === r.version_id ? t("סגירה", "Close") : t("השוואה", "Compare")}</button>
                {r.status === "ARCHIVED" && <button className="link small" data-testid={`rollback-${kind}-${r.number}`}
                  onClick={() => setRollback({ id: r.version_id, reason: "" })}>{t("שחזור", "Restore")}</button>}
              </td>
            </tr>
            {r.change_reason && <tr key={`${r.version_id}-why`} className="adm-why"><td /><td colSpan={4} className="tiny muted"><Loc he={r.change_reason} en={r.change_reason_en} /></td></tr>}
            {rollback?.id === r.version_id && (
              <tr key={`${r.version_id}-rb`}><td colSpan={5}>
                <div className="adm-confirm" data-testid={`rollback-confirm-${kind}`}>
                  <span className="small">{t(`לשחזר את v${r.number}? תיווצר גרסה חדשה עם אותה תצורה, וההיסטוריה נשמרת.`,
                    `Restore v${r.number}? A new version with the same configuration is created, and the history is kept.`)}</span>
                  <input className="adm-cell grow" placeholder={t("סיבה (לא חובה)", "Reason (optional)")} value={rollback.reason} maxLength={300}
                    onChange={(e) => setRollback({ ...rollback, reason: e.target.value })} />
                  <button className="btn btn-dark btn-sm" data-testid={`rollback-go-${kind}`}
                    onClick={async () => { const reason = rollback.reason; setRollback(null); await onRollback(kind, r.version_id, reason); }}>{t("שחזור", "Restore")}</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setRollback(null)}>{t("חזרה", "Back")}</button>
                </div>
              </td></tr>
            )}
            {open?.id === r.version_id && (
              <tr key={`${r.version_id}-diff`}><td colSpan={5}>
                <div className="tiny muted">{t("לעומת", "Compared with")} {open.against}</div><DiffTable diff={open.diff} />
              </td></tr>
            )}
          </Fragment>
        ))}</tbody>
      </table>
    </div>
  );
}
