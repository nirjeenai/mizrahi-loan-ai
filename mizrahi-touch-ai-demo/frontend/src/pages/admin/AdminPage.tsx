import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import "../../admin.css";
import { AdminError, adminApi, kindL, type Json, type Kind, type Report, type Settings, type VersionRow } from "../../adminApi";
import { LangSwitch, tr, useLang } from "../../i18n";
import { Chip, Toast } from "../banker/deskUi";
import { DocumentsTab } from "./DocumentsTab";
import { FollowupTab } from "./FollowupTab";
import { DashSwitch, InsightsDashboards } from "./InsightsDashboards";
import { PromptTab } from "./PromptTab";
import { ActionBar } from "./ui";
import { VersionsTab } from "./VersionsTab";

/** The admin's working copy of one configuration kind: the open draft (if any) and unsaved edits on top of it. */
export interface Work {
  draft: VersionRow | null; config: Json; dirty: boolean; report: Report | null; reasons: string[]; stale: boolean;
  busy: string | null;
}
export type Edit = (update: (config: Json) => Json) => void;
export interface KindProps { work: Work; edit: Edit; bar: JSX.Element }

const TABS = [["insights", "ביצועים ותובנות"], ["documents", "מסמכים ותהליך"], ["followup", "מעקב והשלמה"], ["prompt", "התאמת הנחיות ותבניות"],
  ["versions", "בדיקה וגרסאות"]] as const;
const TABS_EN: Record<string, string> = { insights: "Performance & insights", documents: "Documents & process", followup: "Follow-up & completion",
  prompt: "Instructions & templates", versions: "Testing & versions" };
type Tab = typeof TABS[number][0];
const KINDS: Kind[] = ["loan_policy", "talk_prompt"];

const fresh = (s: Settings, kind: Kind): Work => {
  const draft = s.drafts[kind];
  return { draft, config: (draft || s.published[kind]).config!, dirty: false, report: null, reasons: [], stale: false, busy: null };
};

function AdminTop({ name }: { name?: string }) {
  const { t } = useLang();
  return (
    <>
      <div className="console-top">
        <div className="brand"><img className="mz-logo" src="/brand/mizrahi-logo.svg" alt={t("מזרחי טפחות", "Mizrahi Tefahot")} /><span className="brand-x" aria-hidden>×</span>
          <img className="jeen-logo-light" src="/brand/jeen-logo-light.svg" alt="Jeen" /><span className="brand-title">{t("הגדרות השלמת מסמכים · הלוואות", "Document completion settings · Loans")}</span></div>
        {name && <span className="staff-chip" title={t("חיבור צוות הבנק, אותו חיבור של קונסולת הבנקאי.", "Bank staff sign-in, the same one the banker console uses.")}>{t("מחובר/ת", "Signed in")}: {name}</span>}
        <nav>
          <Link to="/customer">{t("אפליקציית לקוח", "Customer app")}</Link>
          <Link to="/banker">{t("בנקאי", "Banker")}</Link>
          <Link to="/admin" className="on">{t("הגדרות", "Settings")}</Link>
          <Link to="/system">{t("מערכת ואינטגרציות", "System & integrations")}</Link>
        </nav>
        <LangSwitch tone="dark" />
      </div>
    </>
  );
}

export function AdminPage() {
  const [params, setParams] = useSearchParams();
  const { t } = useLang();
  const tab = (TABS.find(([k]) => k === params.get("tab"))?.[0] || "documents") as Tab;
  const [session, setSession] = useState<"loading" | "ok" | "none">("loading");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [work, setWork] = useState<Record<Kind, Work> | null>(null);
  const [toast, setToast] = useState<{ text: string; tone: "ok" | "bad" } | null>(null);
  const [refresh, setRefresh] = useState(0);
  const workRef = useRef(work);
  workRef.current = work;

  useEffect(() => {
    (async () => {
      let s: Awaited<ReturnType<typeof adminApi.session>> | null = null;
      for (let attempt = 0; attempt < 3; attempt++) {
        if (attempt) await new Promise((r) => setTimeout(r, 600 * attempt));
        s = await adminApi.session().catch(() => null);
        if (s && !s.staff && s.demo_identity && await adminApi.demoStaff().catch(() => null)) s = await adminApi.session().catch(() => null);
        if (s && (s.staff || !s.demo_identity)) break;
      }
      setSession(s?.staff ? "ok" : "none");
    })();
  }, []);

  /** Reload settings; keep unsaved edits of a kind unless `reset` names it. */
  const reload = useCallback(async (reset: Kind[] = []) => {
    try {
      const s = await adminApi.settings();
      setSettings(s);
      setLoadError(null);
      setWork((prev) => {
        const next = {} as Record<Kind, Work>;
        for (const k of KINDS) {
          const p = prev?.[k];
          next[k] = !p || reset.includes(k) || !p.dirty ? { ...fresh(s, k), report: p && !reset.includes(k) ? p.report : null } : { ...p, draft: s.drafts[k] };
        }
        return next;
      });
      setRefresh((n) => n + 1);
    } catch (e) { setLoadError((e as Error).message); }
  }, []);
  useEffect(() => { if (session === "ok") reload(); }, [session, reload]);

  const patch = useCallback((kind: Kind, p: Partial<Work>) => setWork((prev) => prev && { ...prev, [kind]: { ...prev[kind], ...p } }), []);

  // the live check: errors, lint, preview and the diff against the published version, for the unsaved working copy
  const configs = work ? KINDS.map((k) => work[k].config) : [];
  useEffect(() => {
    if (!work) return;
    const timers = KINDS.map((k) => window.setTimeout(() => {
      const config = workRef.current?.[k].config;
      if (!config) return;
      adminApi.check(k, config).then((report) => {
        if (workRef.current?.[k].config === config) patch(k, { report });
      }).catch(() => null);
    }, 350));
    return () => timers.forEach(window.clearTimeout);
  }, configs); // eslint-disable-line react-hooks/exhaustive-deps

  const fail = useCallback((kind: Kind, e: unknown, what: string) => {
    const err = e as AdminError;
    const d = err.detail;
    const reasons: string[] = tr(
      d?.reasons || d?.errors?.map((x: any) => `${x.path}: ${x.message}`) || [err.message],
      d?.reasons?.map((r: string, i: number) => d.reasons_en?.[i] || r)
        || d?.errors?.map((x: any) => `${x.path}: ${x.message_en || x.message}`) || [err.message]);
    patch(kind, { busy: null, reasons, stale: err.status === 409 });
    setToast({ text: `${what}: ${err.message}`, tone: "bad" });
  }, [patch]);

  const save = useCallback(async (kind: Kind): Promise<VersionRow | null> => {
    const w = workRef.current![kind];
    patch(kind, { busy: "save", reasons: [] });
    try {
      const d = w.draft || await adminApi.openDraft(kind, "עריכה במסך ההגדרות");
      const saved = await adminApi.saveDraft(d.version_id, w.config, d.revision);
      patch(kind, { draft: saved, config: saved.config!, dirty: false, busy: null, stale: false });
      setToast({ text: tr(`הטיוטה של ${kindL(kind)} נשמרה (v${saved.number}). היא אינה פעילה עד ההפעלה.`,
        `${kindL(kind)} draft saved (v${saved.number}). It isn't active until it's published.`), tone: "ok" });
      setRefresh((n) => n + 1);
      return saved;
    } catch (e) { fail(kind, e, tr("השמירה נכשלה", "Saving failed")); return null; }
  }, [patch, fail]);

  const publish = useCallback(async (kind: Kind) => {
    const w = workRef.current![kind];
    const d = w.dirty || !w.draft ? await save(kind) : w.draft;
    if (!d) return;
    patch(kind, { busy: "publish", reasons: [] });
    try {
      const res = await adminApi.publish(d.version_id, d.revision);
      setToast({ text: tr(`${kindL(kind)} v${res.published.number} הופעלה (במקום v${res.previous.number}).`,
        `${kindL(kind)} v${res.published.number} is now active (replacing v${res.previous.number}).`), tone: "ok" });
      await reload([kind]);
    } catch (e) { fail(kind, e, tr("ההפעלה נכשלה", "Publishing failed")); }
  }, [save, patch, fail, reload]);

  const discard = useCallback(async (kind: Kind) => {
    const w = workRef.current![kind];
    patch(kind, { busy: "discard", reasons: [] });
    try {
      if (w.draft) await adminApi.discard(w.draft.version_id, w.draft.revision);
      setToast({ text: w.draft ? tr(`הטיוטה של ${kindL(kind)} בוטלה.`, `${kindL(kind)} draft discarded.`)
        : tr("השינויים שלא נשמרו בוטלו.", "Unsaved changes discarded."), tone: "ok" });
      await reload([kind]);
    } catch (e) { fail(kind, e, tr("הביטול נכשל", "Discarding failed")); }
  }, [patch, fail, reload]);

  const props = (kind: Kind): KindProps => ({
    work: work![kind],
    edit: (update) => setWork((prev) => prev && { ...prev, [kind]: { ...prev[kind], config: update(prev[kind].config), dirty: true } }),
    bar: <ActionBar kind={kind} work={work![kind]} settings={settings!} onSave={() => save(kind)} onPublish={() => publish(kind)}
      onDiscard={() => discard(kind)} onReload={() => reload([kind])} />,
  });

  if (session !== "ok" || !settings || !work) return (
    <div className="console desk">
      <AdminTop />
      <div className="desk-loading">
        {session === "none" ? <span data-testid="no-session">{t("אין חיבור של צוות הבנק.", "No bank staff session.")}</span>
          : loadError ? <>{t("לא הצלחנו לטעון את ההגדרות", "We couldn't load the settings")}: {loadError} <button className="link" onClick={() => reload()}>{t("ניסיון חוזר", "Try again")}</button></>
            : <><span className="spinner" /> {t("טוען הגדרות…", "Loading settings…")}</>}
      </div>
    </div>
  );

  const ks = settings.kill_switch;
  return (
    <div className="console desk admin" data-testid="admin-page">
      <AdminTop name={t(settings.caller.name_he, settings.caller.name_en || settings.caller.name_he)} />
      {ks.value && (
        <div className="adm-env" data-testid="env-banner">
          <Chip tone="bad" testId="kill-chip">{t("מתג חירום פעיל: אין פניות יזומות", "Emergency switch on: no proactive contact")}</Chip>
        </div>
      )}
      <div className="case-bar adm-bar">
        <div className="adm-title">
          <h2>{t("הגדרות", "Settings")}</h2>
          {KINDS.map((k) => (
            <span key={k} className="small muted" data-testid={`published-${k}`}>{kindL(k)}: <span className="ltr bold">v{settings.published[k].number}</span>
              {settings.drafts[k] ? ` · ${t("טיוטה", "draft")} v${settings.drafts[k]!.number}` : ""}</span>
          ))}
        </div>
        {tab === "insights" && <DashSwitch />}
        <nav className="view-tabs" aria-label={t("לשוניות הגדרות", "Settings tabs")}>
          {TABS.map(([k, label]) => (
            <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} data-testid={`tab-${k}`}
              onClick={() => setParams((p) => { const n = new URLSearchParams(p); n.set("tab", k); return n; }, { replace: true })}>{t(label, TABS_EN[k])}</button>
          ))}
        </nav>
      </div>
      <main className="desk-page adm-page">
        {tab === "insights" && <InsightsDashboards activeGrace={settings.published.loan_policy.config?.followup?.abandonment_grace_minutes}
          activeVersion={settings.published.loan_policy.number} />}
        {tab === "documents" && <DocumentsTab {...props("loan_policy")} settings={settings} />}
        {tab === "followup" && <FollowupTab {...props("loan_policy")} settings={settings} onKillSwitch={async (paused, reason) => {
          try {
            await adminApi.pause(paused, reason);
            setToast({ text: paused ? t("מתג החירום הופעל: לא תתבצע אף פנייה יזומה.", "Emergency switch turned on: no proactive contact will be made.")
              : t("מתג החירום כובה: המעקב חוזר לפעול לפי המדיניות.", "Emergency switch turned off: follow-up resumes according to the policy."), tone: "ok" });
            await reload();
          } catch (e) { setToast({ text: (e as Error).message, tone: "bad" }); }
        }} />}
        {tab === "prompt" && <PromptTab prompt={props("talk_prompt")} policy={props("loan_policy")} settings={settings} />}
        {tab === "versions" && <VersionsTab settings={settings} work={work} refresh={refresh} bars={{ loan_policy: props("loan_policy").bar, talk_prompt: props("talk_prompt").bar }}
          onRollback={async (kind, to, reason) => {
            try {
              const row = await adminApi.rollback(kind, to, reason);
              setToast({ text: t(`שוחזר: ${kindL(kind)} v${row.number} פעילה (העתק של גרסה קודמת).`,
                `Restored: ${kindL(kind)} v${row.number} is active (a copy of an earlier version).`), tone: "ok" });
              await reload([kind]);
            } catch (e) { setToast({ text: `${t("השחזור נכשל", "Rollback failed")}: ${(e as Error).message}`, tone: "bad" }); }
          }} />}
      </main>
      <Toast message={toast} onClose={() => setToast(null)} />
    </div>
  );
}
