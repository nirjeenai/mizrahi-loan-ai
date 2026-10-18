import { useState, type ReactNode, type UIEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, type SessionCase } from "../api";
import { useCase } from "../caseContext";
import { LANG_SWITCH, useLang, type Lang } from "../i18n";
import { usePresence } from "../presence";
import { AssistantSheet } from "./AssistantSheet";
import { IBulb, ICalendar, IChevronDown, IDocs, IHome, IMenu, ISpark, IStages } from "./Icons";
import { UploadSheet } from "./UploadSheet";

const TABS = [
  { to: "/customer", label: "ראשי", en: "Home", icon: <IHome /> },
  { to: "/customer/documents", label: "מסמכים", en: "Documents", icon: <IDocs /> },
  { to: "/customer/meetings", label: "פגישות", en: "Meetings", icon: <ICalendar /> },
  { to: "/customer/stages", label: "שלבים", en: "Stages", icon: <IStages /> },
  { to: "/customer/tools", label: "כלים", en: "Tools", icon: <IBulb /> },
];

/** The language chip in the header's brand corner: it names the other language in that language's own script. */
function LangChip() {
  const { lang, setLang } = useLang();
  const next: Lang = lang === "en" ? "he" : "en";
  return (
    <button type="button" className="lang-chip" onClick={() => setLang(next)} lang={next} data-testid="lang-switch" data-lang={lang}
      aria-label={next === "en" ? "Switch to English" : "מעבר לעברית"} title={next === "en" ? "English" : "עברית"}>
      {next === "en" ? "EN" : "עב"}
    </button>
  );
}

export function TouchShell({ children, onPresenter }: { children: ReactNode; onPresenter?: () => void }) {
  const { snap, caseId, setCaseId, openAssistant, assistant, upload, assistantOrigin, auth } = useCase();
  const { lang, en, t } = useLang();
  const loc = useLocation();
  const nav = useNavigate();
  const [menu, setMenu] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  usePresence(caseId, auth.status === "signed-in" && !!snap && snap.case.case_id === caseId);
  const onScroll = (e: UIEvent<HTMLElement>) => setScrolled(e.currentTarget.scrollTop > 24);
  // the questionnaire is a new customer's own JEEN chat: no case is open yet, and the case assistant stays out of the way
  const applying = loc.pathname.startsWith("/customer/apply");
  const active = (to: string) => (to === "/customer" ? loc.pathname === "/customer" || loc.pathname === "/customer/" : loc.pathname.startsWith(to));
  return (
    <div className="phone" {...(en ? { dir: "ltr", lang: "en", "data-lang": lang } : {})}>
      <div className="phone-screen">
        <div className="phone-notch" />
        <div className="statusbar"><span>9:41</span><span>●●● ▮</span></div>
        <header className={`touch-header${LANG_SWITCH ? " with-lang" : ""}`}>
          <button className="icon-btn" aria-label={t("תפריט", "Menu")} onClick={() => setMenu(true)}><IMenu /></button>
          <button className="case-pill" onClick={() => setMenu(true)} aria-label={t("בחירת תיק", "Choose an application")}>
            <IChevronDown /><span>{applying ? t("בקשת הלוואה חדשה", "New loan application") : snap
              ? `${snap.case.display_number} ${en ? snap.case.title_en || snap.case.title_he : snap.case.title_he}` : t("טוען…", "Loading…")}</span>
          </button>
          {LANG_SWITCH ? (
            <span className="brand-corner"><LangChip /><img className="mark" src="/brand/mizrahi-mark.svg" alt={t("מזרחי טפחות", "Mizrahi-Tefahot")} /></span>
          ) : <img className="mark" src="/brand/mizrahi-mark.svg" alt="מזרחי טפחות" style={{ justifySelf: "end" }} />}
        </header>
        {auth.status === "signed-out" ? (
          <main className="screen">
            <div className="notice" role="status" style={{ marginTop: 16 }} data-testid="no-session">
              {t(<>אין חיבור לתיק. הכניסה נעשית דרך מערכת הזיהוי של הבנק.</>,
                <>No application is connected. Sign-in goes through the bank&apos;s identity service.</>)}</div>
          </main>
        ) : (<>
        <main className="screen" onScroll={onScroll}>{children}</main>
        {!assistant.open && !applying && (
          <button className={`fab${assistantOrigin ? " return" : ""}${scrolled && !assistantOrigin ? " mini" : ""}`} onClick={() => openAssistant()} data-testid="fab"
            aria-label={assistantOrigin ? t("חזרה לשיחה עם העוזר", "Back to the conversation with the assistant") : t("שאלו את העוזר", "Ask the assistant")}>
            <span className="spark"><ISpark size={14} /></span><span className="fab-label">{assistantOrigin ? t("חזרה לשיחה", "Back to chat") : t("עוזר", "Assistant")}</span>
          </button>
        )}
        <nav className="bottom-nav">
          {TABS.map((tab) => (
            <button key={tab.to} className={active(tab.to) ? "on" : ""} onClick={() => nav(tab.to)} aria-current={active(tab.to) ? "page" : undefined}>
              {tab.icon}<span>{en ? tab.en : tab.label}</span>
            </button>
          ))}
        </nav>
        {menu && <Drawer caseId={caseId} onPick={(id) => { setCaseId(id); setMenu(false); nav("/customer"); }} onClose={() => setMenu(false)}
          onPresenter={onPresenter} />}
        {assistant.open && <AssistantSheet />}
        {upload.open && <UploadSheet key={upload.nonce} />}
        </>)}
      </div>
    </div>
  );
}

function Drawer({ caseId, onPick, onClose, onPresenter }: {
  caseId: string; onPick: (id: string) => void; onClose: () => void; onPresenter?: () => void;
}) {
  const [cases, setCases] = useState<SessionCase[] | null>(null);
  if (cases === null) api.demoCases().then(setCases).catch(() => setCases([]));
  const { reload } = useCase();
  const { lang, en, t, setLang } = useLang();
  // "התיקים שלי": the applications of the customer being demonstrated; every other demo and QA case stays reachable below
  const current = (cases || []).find((c) => c.case_id === caseId);
  const persona = current?.persona_id;
  const mine = (cases || []).filter((c) => (persona ? c.persona_id === persona : c.case_id === caseId));
  const others = (cases || []).filter((c) => !mine.includes(c));
  const who = en ? current?.company_en || current?.company_he || (current?.applicants_en || current?.applicants_he)?.join(" and ")
    : current?.company_he || current?.applicants_he?.join(" ו");
  const row = (c: SessionCase) => (
    <button key={c.case_id} onClick={() => onPick(c.case_id)} data-testid="drawer-case" data-case={c.case_id}
      style={{ color: c.case_id === caseId ? "var(--mz-orange)" : undefined }}>
      {c.display_number} · {en ? c.title_en || c.title_he : c.title_he}
    </button>
  );
  return (
    <div className="drawer" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="small muted">{t("התיקים שלי", "My applications")}{who ? ` · ${who}` : ""}</div>
        <div className="drawer-mine" data-testid="drawer-my-cases">{mine.map(row)}</div>
        {others.length > 0 && (
          <details className="drawer-others" data-testid="drawer-other-cases">
            {en ? <summary className="small muted">Other customers&apos; applications ({others.length})</summary>
              : <summary className="small muted">תיקים של לקוחות אחרים ({others.length})</summary>}
            {others.map(row)}
          </details>
        )}
        <Link to="/customer/apply" onClick={onClose} data-testid="drawer-apply" style={{ color: "var(--mz-orange)", fontWeight: 700 }}>
          {t("+ בקשת הלוואה חדשה", "+ New loan application")}</Link>
        <div className="small muted" style={{ marginTop: 14 }}>{t("עוד", "More")}</div>
        {onPresenter && <button onClick={() => { onClose(); onPresenter(); }} data-testid="drawer-presenter">{t("תרחישים וקבצים להורדה", "Demo scenarios and files (Hebrew)")}</button>}
        <Link to="/banker" onClick={onClose}>{t("תצוגת בנקאי, חבילת ראיות", "Banker view, evidence package (Hebrew)")}</Link>
        <Link to="/system" onClick={onClose}>{t("מטריצת אינטגרציות, MCP ורובריקות", "Integrations, MCP and rubrics (Hebrew)")}</Link>
        <button onClick={async () => { if (confirm(t("לאפס את התיק הזה ולמחוק מסמכים, ממצאים ושיחה?", "Reset this application and delete its documents, findings and conversation?"))) { await api.reset(caseId); reload(); onClose(); } }}>
          {t("איפוס התיק", "Reset the application")}
        </button>
        {LANG_SWITCH && (
          <div className="drawer-lang" role="radiogroup" aria-label={t("שפה", "Language")} data-testid="drawer-lang">
            <span className="small muted">{t("שפה", "Language")}</span>
            <span className="drawer-lang-seg">
              {(["he", "en"] as Lang[]).map((l) => (
                <button key={l} type="button" role="radio" aria-checked={lang === l} lang={l} className={lang === l ? "on" : ""}
                  onClick={() => setLang(l)} data-testid={`drawer-lang-${l}`}>{l === "he" ? "עברית" : "English"}</button>
              ))}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
