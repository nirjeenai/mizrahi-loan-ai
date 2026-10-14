import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import "../../admin.css";
import { AdminError, adminApi, KIND_HE, type Json, type Kind, type Report, type Settings, type VersionRow } from "../../adminApi";
import { Chip, Toast } from "../banker/deskUi";
import { DocumentsTab } from "./DocumentsTab";
import { FollowupTab } from "./FollowupTab";
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

const TABS = [["documents", "מסמכים ותהליך"], ["followup", "מעקב והשלמה"], ["prompt", "התאמת הנחיות ותבניות"],
  ["versions", "בדיקה וגרסאות"]] as const;
type Tab = typeof TABS[number][0];
const KINDS: Kind[] = ["loan_policy", "talk_prompt"];

const fresh = (s: Settings, kind: Kind): Work => {
  const draft = s.drafts[kind];
  return { draft, config: (draft || s.published[kind]).config!, dirty: false, report: null, reasons: [], stale: false, busy: null };
};

function AdminTop({ name }: { name?: string }) {
  return (
    <>
      <div className="console-top">
        <div className="brand"><img className="mz-logo" src="/brand/mizrahi-logo.svg" alt="מזרחי טפחות" /><span className="brand-x" aria-hidden>×</span>
          <img className="jeen-logo-light" src="/brand/jeen-logo-light.png" alt="Jeen" /><span className="brand-title">הגדרות השלמת מסמכים · הלוואות</span></div>
        {name && <span className="staff-chip" title="חיבור הדגמה של צוות הבנק, אותו חיבור של קונסולת הבנקאי.">מחובר/ת: {name} (הדגמה)</span>}
        <nav>
          <Link to="/customer">אפליקציית לקוח</Link>
          <Link to="/banker">בנקאי</Link>
          <Link to="/admin" className="on">הגדרות</Link>
          <Link to="/system">מערכת ואינטגרציות</Link>
        </nav>
      </div>
      <div className="console-ribbon">הדגמת קונספט של JEEN · נתונים סינתטיים · אינה מערכת של מזרחי־טפחות · אין החלטת אשראי אוטומטית</div>
    </>
  );
}

export function AdminPage() {
  const [params, setParams] = useSearchParams();
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
      let s = await adminApi.session().catch(() => null);
      if (s && !s.staff && s.demo_identity && await adminApi.demoStaff().catch(() => null)) s = await adminApi.session().catch(() => null);
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
    const reasons: string[] = err.detail?.reasons || err.detail?.errors?.map((x: any) => `${x.path}: ${x.message}`) || [err.message];
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
      setToast({ text: `הטיוטה של ${KIND_HE[kind]} נשמרה (v${saved.number}). היא אינה פעילה עד ההפעלה.`, tone: "ok" });
      setRefresh((n) => n + 1);
      return saved;
    } catch (e) { fail(kind, e, "השמירה נכשלה"); return null; }
  }, [patch, fail]);

  const publish = useCallback(async (kind: Kind) => {
    const w = workRef.current![kind];
    const d = w.dirty || !w.draft ? await save(kind) : w.draft;
    if (!d) return;
    patch(kind, { busy: "publish", reasons: [] });
    try {
      const res = await adminApi.publish(d.version_id, d.revision);
      setToast({ text: `${KIND_HE[kind]} v${res.published.number} הופעלה (במקום v${res.previous.number}).`, tone: "ok" });
      await reload([kind]);
    } catch (e) { fail(kind, e, "ההפעלה נכשלה"); }
  }, [save, patch, fail, reload]);

  const discard = useCallback(async (kind: Kind) => {
    const w = workRef.current![kind];
    patch(kind, { busy: "discard", reasons: [] });
    try {
      if (w.draft) await adminApi.discard(w.draft.version_id, w.draft.revision);
      setToast({ text: w.draft ? `הטיוטה של ${KIND_HE[kind]} בוטלה.` : "השינויים שלא נשמרו בוטלו.", tone: "ok" });
      await reload([kind]);
    } catch (e) { fail(kind, e, "הביטול נכשל"); }
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
        {session === "none" ? <span data-testid="no-session">אין חיבור של צוות הבנק. בסביבה זו לא מונפק חיבור הדגמה אוטומטי.</span>
          : loadError ? <>לא הצלחנו לטעון את ההגדרות: {loadError} <button className="link" onClick={() => reload()}>ניסיון חוזר</button></>
            : <><span className="spinner" /> טוען הגדרות…</>}
      </div>
    </div>
  );

  const ks = settings.kill_switch;
  return (
    <div className="console desk admin" data-testid="admin-page">
      <AdminTop name={settings.caller.name_he} />
      <div className="adm-env" data-testid="env-banner">
        <span className="bold">{settings.environment.label_he}</span>
        <span>שיחות JEEN Talk במצב {settings.published.loan_policy.config?.talk?.mode === "simulation" ? "סימולציה — אין חיוג אמיתי" : settings.published.loan_policy.config?.talk?.mode}</span>
        {ks.value && <Chip tone="bad" testId="kill-chip">מתג חירום פעיל: אין פניות יזומות</Chip>}
      </div>
      <div className="case-bar adm-bar">
        <div className="adm-title">
          <h2>הגדרות</h2>
          {KINDS.map((k) => (
            <span key={k} className="small muted" data-testid={`published-${k}`}>{KIND_HE[k]}: <span className="ltr bold">v{settings.published[k].number}</span>
              {settings.drafts[k] ? ` · טיוטה v${settings.drafts[k]!.number}` : ""}</span>
          ))}
        </div>
        <nav className="view-tabs" aria-label="לשוניות הגדרות">
          {TABS.map(([k, label]) => (
            <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} data-testid={`tab-${k}`}
              onClick={() => setParams((p) => { const n = new URLSearchParams(p); n.set("tab", k); return n; }, { replace: true })}>{label}</button>
          ))}
        </nav>
      </div>
      <main className="desk-page adm-page">
        {tab === "documents" && <DocumentsTab {...props("loan_policy")} settings={settings} />}
        {tab === "followup" && <FollowupTab {...props("loan_policy")} settings={settings} onKillSwitch={async (paused, reason) => {
          try {
            await adminApi.pause(paused, reason);
            setToast({ text: paused ? "מתג החירום הופעל: לא תתבצע אף פנייה יזומה." : "מתג החירום כובה: המעקב חוזר לפעול לפי המדיניות.", tone: "ok" });
            await reload();
          } catch (e) { setToast({ text: (e as Error).message, tone: "bad" }); }
        }} />}
        {tab === "prompt" && <PromptTab prompt={props("talk_prompt")} policy={props("loan_policy")} settings={settings} />}
        {tab === "versions" && <VersionsTab settings={settings} work={work} refresh={refresh} bars={{ loan_policy: props("loan_policy").bar, talk_prompt: props("talk_prompt").bar }}
          onRollback={async (kind, to, reason) => {
            try {
              const row = await adminApi.rollback(kind, to, reason);
              setToast({ text: `שוחזר: ${KIND_HE[kind]} v${row.number} פעילה (העתק של גרסה קודמת).`, tone: "ok" });
              await reload([kind]);
            } catch (e) { setToast({ text: `השחזור נכשל: ${(e as Error).message}`, tone: "bad" }); }
          }} />}
      </main>
      <Toast message={toast} onClose={() => setToast(null)} />
    </div>
  );
}
