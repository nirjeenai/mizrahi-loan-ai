import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { LangSwitch, loc, locList, locOf, Orig, useLang } from "../../i18n";
import { api, AUTH_EVENT, outcomeL, timeL, usePolling, type BankerCaseRow, type Finding, type Session, type Workspace } from "../../api";
import { Chip, useOutsideClose, When } from "./deskUi";
import { FollowupView } from "./FollowupView";
import { CaseCentricV3 } from "./CaseCentricV3";
import { IntelligenceV2 } from "./IntelligenceV2";
import { ReviewWorkspace } from "./ReviewWorkspace";

type View = "intel" | "case" | "review" | "followup" | "conversation" | "technical";
/** The banker's last choice between the classic review (V1), the intelligence briefing (V2) and the case workspace (V3); V1 when never chosen. */
const UI_PREF = "mz.banker.ui";
const CASE_PREF = "mz.banker.case";

export function ConsoleTop({ active, identity }: { active: "customer" | "banker" | "system"; identity?: string }) {
  const { t } = useLang();
  return (
    <>
      <div className="console-top">
        <div className="brand"><img className="mz-logo" src="/brand/mizrahi-logo.svg" alt={t("מזרחי טפחות", "Mizrahi-Tefahot")} /><span className="brand-x" aria-hidden>×</span>
          <img className="jeen-logo-light" src="/brand/jeen-logo-light.svg" alt="Jeen" /><span className="brand-title">{t("קונסולת בנקאי אשראי · הלוואות", "Credit banker console · Loans")}</span></div>
        {identity && <span className="staff-chip" title={t("הזהות נקבעת בשרת ונרשמת בכל החלטה.", "The identity is set by the server and recorded with every decision.")}>{identity}</span>}
        <nav>
          <Link to="/customer" className={active === "customer" ? "on" : ""}>{t("אפליקציית לקוח", "Customer app")}</Link>
          <Link to="/banker" className={active === "banker" ? "on" : ""}>{t("בנקאי", "Banker")}</Link>
          <Link to="/system" className={active === "system" ? "on" : ""}>{t("מערכת ואינטגרציות", "System & integrations")}</Link>
          <Link to="/admin" data-testid="nav-admin">{t("הגדרות", "Settings")}</Link>
        </nav>
        <LangSwitch tone="dark" />
      </div>
    </>
  );
}


export function BankerConsole() {
  const { en, t } = useLang();
  const [params, setParams] = useSearchParams();
  const caseId = params.get("case") || "";
  const pref = localStorage.getItem(UI_PREF);
  const view = (params.get("view") as View) || (pref === "intel" || pref === "case" ? pref : "review");
  // the console works on a staff session; in demo mode it obtains the demo banker's session without a login
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const ensureSession = useCallback(async () => {
    let s: Session | null = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt) await new Promise((r) => setTimeout(r, 600 * attempt));
      s = await api.session().catch(() => null);
      if (s && !s.staff && s.demo_identity && await api.demoStaff().catch(() => null)) s = await api.session().catch(() => null);
      if (s && (s.staff || !s.demo_identity)) break;
    }
    setSession(s);
  }, []);
  useEffect(() => {
    ensureSession();
    window.addEventListener(AUTH_EVENT, ensureSession);
    return () => window.removeEventListener(AUTH_EVENT, ensureSession);
  }, [ensureSession]);
  const me = session?.staff || null;
  const staff = me?.staff_id || "";
  // nothing is polled until a staff member signs in
  const cases = usePolling<BankerCaseRow[] | null>(() => (me ? api.bankerCases() : Promise.resolve(null)), [staff], () => false);
  const ws = usePolling<Workspace | null>(() => (me && caseId ? api.bankerWorkspace(caseId) : Promise.resolve(null)), [caseId, staff],
    (w) => !!w && (w.summary.processing > 0 || ["CHECKING", "RECHECKING"].includes(w.review_state.state)));
  const patch = useCallback((next: Record<string, string | null>) => {
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(next)) { if (v === null) p.delete(k); else p.set(k, v); }
      return p;
    }, { replace: true });
  }, [setParams]);
  // no case in the URL: the remembered one if it still exists, else the top of the main list; written into the URL so
  // the open case does not change when the list reorders. Only a case someone chose is remembered, never that default.
  const list = cases.data;
  const remembered = localStorage.getItem(CASE_PREF);
  const defaulted = useRef<string | null>(null);
  useEffect(() => {
    if (caseId || !list) return;
    const keep = list.some((c) => c.case_id === remembered) ? remembered : null;
    const pick = keep || (list.find((c) => inMainList(c.case_id)) || list[0])?.case_id;
    defaulted.current = keep ? null : pick || null;
    if (pick) patch({ case: pick });
  }, [caseId, list, remembered, patch]);
  useEffect(() => { if (caseId && caseId !== defaulted.current) localStorage.setItem(CASE_PREF, caseId); }, [caseId]);
  const chooseCase = useCallback((id: string) => {
    localStorage.setItem(CASE_PREF, id);
    patch({ case: id, item: null });
  }, [patch]);
  const reload = useCallback(() => { ws.reload(); cases.reload(); }, [ws, cases]);
  const switchView = useCallback((v: View) => {
    if (v === "intel" || v === "case" || v === "review") localStorage.setItem(UI_PREF, v);
    patch({ view: v === "review" ? null : v });
  }, [patch]);
  const w = me && ws.data && ws.data.case_id === caseId ? ws.data : null;
  const readOnly = !!w && !!w.case.banker.staff_id && w.case.banker.staff_id !== staff;
  // the session carries the Hebrew name only; a case assigned to the same banker carries its English twin
  const mine = cases.data?.find((c) => c.banker.staff_id === staff)?.banker;
  const myName = me ? (mine ? locOf(mine, "name_he") : loc(me.name_he, me.name_en)) : "";
  if (!me) return (
    <div className="console desk">
      <ConsoleTop active="banker" />
      <div className="desk-loading">{session === undefined ? <span className="spinner" />
        : <span data-testid="no-session">{t("אין חיבור של צוות הבנק.", "No bank staff session.")}</span>}</div>
    </div>
  );
  return (
    <div className="console desk">
      <ConsoleTop active="banker" identity={en ? `${readOnly ? "View only · " : ""}Signed in: ${myName}`
        : `${readOnly ? "צפייה בלבד · " : ""}מחובר/ת: ${me.name_he}`} />
      <CaseBar caseId={caseId} cases={cases.data || []} ws={w} view={view} staff={staff} onOpen={cases.reload}
        onCase={chooseCase} onView={switchView} />
      {!w ? <div className="desk-loading">{ws.error ? <>{t("לא הצלחנו לטעון את התיק.", "We couldn't load the case.")} <button className="link" onClick={ws.reload}>{t("ניסיון חוזר", "Try again")}</button></> : <><span className="spinner" /> {t("טוען את התיק…", "Loading the case…")}</>}</div>
        : view === "intel" || view === "case" ? (() => {
            const openV1 = (item?: string | null) => {
              localStorage.setItem(UI_PREF, "review");
              patch({ view: null, item: item || null });
            };
            return view === "intel" ? <IntelligenceV2 caseId={caseId} ws={w} openV1={openV1} /> : <CaseCentricV3 caseId={caseId} ws={w} openV1={openV1} />;
          })()
        : view === "review" ? <ReviewWorkspace ws={w} selected={params.get("item")} onSelect={(id) => patch({ item: id })} reload={reload}
            staff={staff} readOnly={readOnly} stale={!!ws.error} openV3={() => switchView("case")} />
          : view === "followup" ? <FollowupView caseId={caseId} readOnly={readOnly} />
          : view === "conversation" ? <ConversationView caseId={caseId} ws={w} />
            : <TechnicalView caseId={caseId} onRecheck={async () => { await api.bankerRecheck(caseId).catch(() => null); reload(); }} readOnly={readOnly} />}
    </div>
  );
}

/** The six official customer profiles (UC-01…06 ↔ presenter TC-01…06); with every customer-created application
 *  (intake and onboarding ids are DEMO-LN-…) they make the main list. Every other prepared case is under
 *  "תרחישי בדיקה נוספים". Both are filters of the server's list, so each keeps its most-recent-activity order. */
const OFFICIAL_CASES = new Set(["DEMO-MTZ-2026-101", "DEMO-MTZ-2026-102", "DEMO-MTZ-2026-103", "DEMO-MTZ-2026-104",
  "DEMO-MTZ-2026-105", "DEMO-MTZ-2026-106"]);
const inMainList = (id: string) => OFFICIAL_CASES.has(id) || id.startsWith("DEMO-LN-");

function CaseBar({ caseId, cases, ws, view, staff, onOpen, onCase, onView }: {
  caseId: string; cases: BankerCaseRow[]; ws: Workspace | null; view: View; staff: string;
  onOpen: () => void; onCase: (id: string) => void; onView: (v: View) => void;
}) {
  const { en, t } = useLang();
  const [open, setOpen] = useState(false);
  const [more, setMore] = useState(false);
  const pop = useRef<HTMLDivElement>(null);
  useOutsideClose(open, () => setOpen(false));
  useEffect(() => {
    if (open && more && !inMainList(caseId)) pop.current?.querySelector(".case-pop-row.on")?.scrollIntoView({ block: "nearest" });
  }, [open, more, caseId]);
  const current = cases.find((c) => c.case_id === caseId);
  const main = cases.filter((c) => inMainList(c.case_id));
  const extra = cases.filter((c) => !inMainList(c.case_id));
  const row = (c: BankerCaseRow) => {
    const q = c.queue || {};
    return (
      <button key={c.case_id} role="option" aria-selected={c.case_id === caseId} className={`case-pop-row${c.case_id === caseId ? " on" : ""}`}
        data-case={c.case_id} onClick={() => { onCase(c.case_id); setOpen(false); }}>
        <span className="bold"><span className="ltr">{c.display_number}</span> · {locOf(c, "title_he")}</span>
        <span className="small muted">{locList(c, "borrowers").join(", ")}{c.banker.staff_id && c.banker.staff_id !== staff
          ? (en ? ` · assigned to ${locOf(c.banker, "name_he")}` : ` · משויך ל${c.banker.name_he}`) : ""}</span>
        <span className="row" style={{ gap: 4, flexWrap: "wrap", marginTop: 4 }}>
          {(q.decide || 0) + (q.judgment || 0) + (q.escalated || 0) > 0 && <Chip tone="navy">{(q.decide || 0) + (q.judgment || 0) + (q.escalated || 0)} {t("להחלטתך", "for your decision")}</Chip>}
          {(q.missing || 0) > 0 && <Chip tone="warn">{q.missing} {t("חסרים", "missing")}</Chip>}
          {(q.correction || 0) > 0 && <Chip tone="warn">{q.correction} {t("בתיקון", "in correction")}</Chip>}
          <Chip>{locOf(c, "readiness_he")}</Chip>
        </span>
      </button>
    );
  };
  return (
    <div className="case-bar">
      <div className="case-switch" data-popover>
        <button className="case-switch-btn" onClick={() => { if (!open) { onOpen(); setMore(!inMainList(caseId)); } setOpen(!open); }}
          aria-expanded={open} aria-haspopup="listbox" data-testid="case-switch">
          <span className="case-no ltr">{ws?.case.display_number || current?.display_number || caseId}</span>
          <span className="case-names" title={ws ? locOf(ws.case, "title_he") : undefined}>{ws?.document_profile?.company ? `${locOf(ws.document_profile.company, "name_he")} · ` : ""}
            {en ? (ws ? ws.case.borrowers.map((b) => locOf(b, "name_he")) : current ? locList(current, "borrowers") : []).join(" & ")
              : ws ? ws.case.borrowers.map((b) => b.name_he).join(" ו") : current?.borrowers.join(" ו")}</span>
          {ws?.document_profile?.profile_label_he && <span className="case-profile" data-testid="banker-profile-label">{locOf(ws.document_profile, "profile_label_he")}</span>}
          {ws?.document_profile?.banker_assisted && <span className="case-profile assisted" data-testid="banker-assisted">{t("ליווי בנקאי · מסלול עסקי מוגבל", "Banker-assisted · limited business track")}</span>}
          <span aria-hidden>▾</span>
        </button>
        {open && (
          <div className="case-pop" role="listbox" aria-label={t("תיקים בתור", "Cases in the queue")} ref={pop}>
            <div className="case-pop-head">{t("תיקים בתור", "Cases in the queue")}</div>
            <div data-testid="case-main">{main.map(row)}</div>
            {extra.length > 0 && (
              <>
                <button className="case-pop-more" aria-expanded={more} onClick={() => setMore(!more)} data-testid="case-more-toggle">
                  <span>{t("תרחישי בדיקה נוספים", "More test scenarios")}</span>
                  <span className="small muted">{extra.length} {t("תיקים", "cases")} <span aria-hidden>{more ? "▴" : "▾"}</span></span>
                </button>
                {more && <div data-testid="case-more">{extra.map(row)}</div>}
              </>
            )}
          </div>
        )}
      </div>
      <div className="ui-switch" role="group" aria-label={t("גרסת התצוגה", "View version")} data-testid="banker-ui-switch">
        <button className={view === "review" ? "on" : ""} onClick={() => onView("review")} data-testid="ui-v1" title={t("סקירת המסמכים הקיימת", "The existing document review")}>{t("V1 · סקירה", "V1 · Review")}</button>
        <button className={view === "intel" ? "on v2" : "v2"} onClick={() => onView("intel")} data-testid="ui-v2" title={t("Banker Intelligence V2, תמונת מצב, ניתוח פיננסי וסימולציה", "Banker Intelligence V2: case briefing, financial analysis and simulation")}>{t("V2 · תמונת מצב Jeen", "V2 · Jeen briefing")}</button>
        <button className={view === "case" ? "on v3" : "v3"} onClick={() => onView("case")} data-testid="ui-v3" title={t("Banker Case-Centric V3, התיק המוכן, מלמעלה למטה", "Banker Case-Centric V3: the prepared case, top to bottom")}>{t("V3 · תיק מוכן", "V3 · Prepared case")}</button>
      </div>
      <nav className="view-tabs" aria-label={t("תצוגות", "Views")}>
        {(en ? [["review", "Document review"], ["followup", "Completion follow-up"], ["conversation", "Customer conversation"], ["technical", "Log & technical details"]] as [View, string][]
          : [["review", "סקירת מסמכים"], ["followup", "מעקב השלמה"], ["conversation", "שיחה עם הלקוח"], ["technical", "יומן ופרטים טכניים"]] as [View, string][]).map(([k, label]) => (
          <button key={k} className={view === k ? "on" : ""} onClick={() => onView(k)} aria-current={view === k ? "page" : undefined}>{label}</button>
        ))}
      </nav>
    </div>
  );
}

function ConversationView({ caseId, ws }: { caseId: string; ws: Workspace }) {
  const conv = usePolling(() => api.bankerConversation(caseId), [caseId], () => false);
  const { t: tx } = useLang();
  return (
    <div className="desk-page">
      <div className="panel">
        <h3>{tx("השיחה עם הלקוחות, מקור אחד לצ׳אט ולקול", "The conversation with the customers — one source for chat and voice")}</h3>
        {ws.unattached_statements.length > 0 && (
          <div className="notice" style={{ marginBottom: 10 }}>
            <b>{tx("הסברי לקוח שלא שויכו לממצא (לא מאומתים):", "Customer explanations not linked to a finding (unverified):")}</b>
            {ws.unattached_statements.map((s) => <div key={s.statement_id} className="small">• <Orig text={s.text} /> <When at={s.created_at} /></div>)}
          </div>
        )}
        {(conv.data || []).length === 0 && <div className="small muted">{tx("אין עדיין שיחה.", "No conversation yet.")}</div>}
        {(conv.data || []).map((t) => (
          <div key={t.turn_id} className="conv-turn">
            <div className="row small"><Chip tone={t.role === "user" ? "neutral" : "jeen"}>{t.role === "user" ? tx("לקוח", "Customer") : tx("עוזר", "Assistant")}</Chip>
              <Chip>{t.channel === "voice" ? tx("קול", "Voice") : t.channel === "app" ? tx("עדכון מהמערכת", "System update") : tx("צ׳אט", "Chat")}</Chip><When at={t.created_at} /></div>
            <div className="small" style={{ marginTop: 4, whiteSpace: "pre-wrap" }}><Orig text={t.text} /></div>
            {t.tool_calls?.length ? <div className="tiny muted ltr" style={{ marginTop: 2 }}>{t.tool_calls.map((c) => c.name).join(" · ")}</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

const ACTOR_HE = (a: string) => a.startsWith("banker") ? `בנקאי ${a.split(":")[1] || ""}` : a.startsWith("provider") ? "ספק בדיקה" : a;
const ACTOR_EN = (a: string) => a.startsWith("banker") ? `Banker ${a.split(":")[1] || ""}` : a.startsWith("provider") ? "Review provider" : a;

function TechnicalView({ caseId, onRecheck, readOnly }: { caseId: string; onRecheck: () => void; readOnly: boolean }) {
  const pkg = usePolling(() => api.bankerPackage(caseId), [caseId], () => false);
  const { en, t } = useLang();
  const p = pkg.data;
  if (!p) return <div className="desk-loading"><span className="spinner" /> {t("טוען…", "Loading…")}</div>;
  const all: Finding[] = [...p.findings_open_banker, ...p.findings_open_customer, ...p.findings_info, ...p.findings_closed];
  const disclaimers: [string, string][] = p.disclaimers_he.map((d: string, i: number) => [d, loc(d, p.disclaimers_en?.[i])]);
  return (
    <div className="desk-page">
      <div className="notice navy row between" style={{ marginBottom: 12 }}>
        <span>{t("מידע טכני ויומן ביקורת לשימוש מורשים: הרצות, רובריקות, מודלים, כל הממצאים כולל סגורים, והחלטות אנושיות. אינו נדרש לבדיקת מסמך שגרתית.",
          "Technical information and audit log for authorized users: runs, rubrics, models, every finding including closed ones, and human decisions. Not needed for a routine document review.")}</span>
        <button className="btn btn-ghost btn-sm" onClick={onRecheck} disabled={readOnly} title={t("הרצה חוזרת של בדיקת סט המסמכים", "Re-run the check of the document set")}>{t("הרצה חוזרת של בדיקת הסט", "Re-run the set check")}</button>
      </div>
      <div className="grid2">
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>{t("החלטות אנושיות", "Human decisions")} ({p.decisions.length})</h3>
          <table className="t"><thead><tr><th>{t("זמן", "Time")}</th><th>{t("בנקאי", "Banker")}</th><th>{t("פעולה", "Action")}</th><th>{t("יעד", "Target")}</th><th>{t("מצב", "Status")}</th><th>{t("נימוק פנימי", "Internal rationale")}</th></tr></thead>
            <tbody>{[...p.decisions].reverse().map((d: any) => (
              <tr key={d.decision_id}><td className="ltr tiny">{timeL(d.created_at)}</td><td className="tiny">{loc(d.actor_name, d.actor_name_en)}</td><td className="tiny">{locOf(d, "action_he")}</td>
                <td className="ltr tiny">{d.document_id || d.finding_id || `${d.borrower_id || ""} ${d.period || ""}`}</td>
                <td className="tiny">{d.previous_status} → {d.new_status}</td><td className="tiny"><Orig text={d.rationale} /></td></tr>))}</tbody></table>
          <h3 style={{ marginTop: 16 }}>{t("בקשות ללקוח", "Requests to the customer")} ({p.customer_requests.length})</h3>
          <table className="t"><thead><tr><th>{t("נוצרה", "Created")}</th><th>{t("סוג", "Type")}</th><th>{t("כותרת", "Title")}</th><th>{t("מצב", "Status")}</th><th>{t("מסמך שהתקבל", "Document received")}</th></tr></thead>
            <tbody>{p.customer_requests.map((r: any) => (
              <tr key={r.customer_request_id}><td className="ltr tiny">{timeL(r.created_at)}</td><td className="tiny">{r.kind}</td><td className="tiny">{locOf(r, "title_he")}</td>
                <td className="tiny">{r.status}</td><td className="ltr tiny">{r.responded_document_id || "-"}</td></tr>))}</tbody></table>
        </div>
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>{t("כל הממצאים, כולל סגורים", "Every finding, including closed ones")} ({all.length})</h3>
          {all.map((f) => (
            <div key={f.finding_id} className={`finding ${f.review_state}`}>
              <div className="row between"><div className="finding-title">{locOf(f, "title_he")}</div><span className="tiny muted ltr">{f.code} · {f.status}{f.resolution ? ` · ${f.resolution}` : ""}</span></div>
              <div className="finding-msg">{locOf(f, "message_he")}</div>
              <details style={{ marginTop: 4 }}><summary className="tiny muted" style={{ cursor: "pointer" }}>{t("היסטוריה", "History")} ({f.history.length})</summary>
                {f.history.map((h: any, i: number) => <div key={i} className="tiny muted">{timeL(h.at)} · {h.event}{h.actor ? ` · ${h.actor}` : ""}{h.note ? <> · <Orig text={h.note} /></> : ""}{h.run_id ? ` · ${h.run_id}` : ""}</div>)}
              </details>
            </div>
          ))}
        </div>
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>{t("היסטוריית הרצות", "Run history")} ({p.runs.length})</h3>
          <table className="t"><thead><tr><th>{t("הרצה", "Run")}</th><th>{t("היקף", "Scope")}</th><th>{t("ספק", "Provider")}</th><th>{t("רובריקה", "Rubric")}</th><th>{t("מצב", "Status")}</th><th>{t("התחלה", "Started")}</th></tr></thead>
            <tbody>{p.runs.map((r: any) => (<tr key={r.run_id}><td className="ltr tiny">{r.run_id}</td><td>{r.scope}</td><td className="ltr tiny">{r.provider}</td>
              <td className="ltr tiny">{r.rubric_id}@{r.rubric_version}</td><td>{r.status}{r.error ? <div className="tiny" style={{ color: "var(--bad)" }}>{r.error}</div> : null}</td>
              <td className="ltr tiny">{timeL(r.started_at)}</td></tr>))}</tbody></table>
          <h3 style={{ marginTop: 16 }}>{t("קריטריונים ברמת התיק", "Case-level criteria")}</h3>
          {p.case_criteria.map((c: any) => (
            <div className="crit" key={c.criterion_id}><span className={`badge ${c.outcome}`}>{outcomeL(c.outcome)}</span>
              <div><div className="bold small">{locOf(c, "title_he")} <span className="crit-id">{c.criterion_id} · {c.decided_by}</span></div><div className="small muted">{c.explanation_en && en ? c.explanation_en : <Orig text={c.explanation_he} />}</div></div></div>
          ))}
          <div className="small" style={{ marginTop: 10 }}>{disclaimers.filter(([d]) => !d.includes("סינתט")).map(([d, shown]) => <div key={d}>• {shown}</div>)}
            <div className="muted" style={{ marginTop: 6 }}>{t("לא נכלל בבדיקה:", "Not included in the check:")} {locList(p, "not_evaluated").join(" · ")}</div></div>
        </div>
        <div className="panel" style={{ overflowX: "auto" }}>
          <h3>{t("יומן ביקורת", "Audit log")}</h3>
          <table className="t"><thead><tr><th>{t("זמן", "Time")}</th><th>{t("גורם", "Actor")}</th><th>{t("פעולה", "Action")}</th><th>{t("יעד", "Target")}</th></tr></thead>
            <tbody>{p.audit.map((e: any) => (<tr key={e.event_id}><td className="ltr tiny">{timeL(e.at)}</td><td className="tiny">{en ? ACTOR_EN(e.actor) : ACTOR_HE(e.actor)}</td>
              <td className="tiny ltr">{e.action}</td><td className="ltr tiny">{e.target}</td></tr>))}</tbody></table>
        </div>
      </div>
    </div>
  );
}
