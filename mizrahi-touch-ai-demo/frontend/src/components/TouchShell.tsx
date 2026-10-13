import { useState, type ReactNode, type UIEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useCase } from "../caseContext";
import { AssistantSheet } from "./AssistantSheet";
import { IBulb, ICalendar, IChevronDown, IDocs, IHome, IMenu, ISpark, IStages } from "./Icons";
import { UploadSheet } from "./UploadSheet";

const TABS = [
  { to: "/customer", label: "ראשי", icon: <IHome /> },
  { to: "/customer/documents", label: "מסמכים", icon: <IDocs /> },
  { to: "/customer/meetings", label: "פגישות", icon: <ICalendar /> },
  { to: "/customer/stages", label: "שלבים", icon: <IStages /> },
  { to: "/customer/tools", label: "כלים", icon: <IBulb /> },
];

export function TouchShell({ children }: { children: ReactNode }) {
  const { snap, caseId, setCaseId, openAssistant, assistant, upload, assistantOrigin, auth } = useCase();
  const loc = useLocation();
  const nav = useNavigate();
  const [menu, setMenu] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const onScroll = (e: UIEvent<HTMLElement>) => setScrolled(e.currentTarget.scrollTop > 24);
  const active = (to: string) => (to === "/customer" ? loc.pathname === "/customer" || loc.pathname === "/customer/" : loc.pathname.startsWith(to));
  return (
    <div className="phone">
      <div className="phone-screen">
        <div className="phone-notch" />
        <div className="statusbar"><span>9:41</span><span>●●● ▮</span></div>
        <div className="ribbon">הדגמת קונספט של <b>JEEN</b> · נתונים סינתטיים · לא מחובר למערכות מזרחי־טפחות</div>
        <header className="touch-header">
          <button className="icon-btn" aria-label="תפריט" onClick={() => setMenu(true)}><IMenu /></button>
          <button className="case-pill" onClick={() => setMenu(true)} aria-label="בחירת תיק">
            <IChevronDown /><span>{snap ? `${snap.case.display_number} ${snap.case.title_he}` : "טוען…"}</span>
          </button>
          <img className="mark" src="/brand/mizrahi-mark.svg" alt="מזרחי טפחות" style={{ justifySelf: "end" }} />
        </header>
        {auth.status === "signed-out" ? (
          <main className="screen">
            <div className="notice" role="status" style={{ marginTop: 16 }} data-testid="no-session">
              אין חיבור לתיק. בסביבה זו לא מונפק חיבור הדגמה אוטומטי; הכניסה נעשית דרך מערכת הזיהוי של הבנק.</div>
          </main>
        ) : (<>
        <main className="screen" onScroll={onScroll}>{children}</main>
        {!assistant.open && (
          <button className={`fab${assistantOrigin ? " return" : ""}${scrolled && !assistantOrigin ? " mini" : ""}`} onClick={() => openAssistant()} data-testid="fab"
            aria-label={assistantOrigin ? "חזרה לשיחה עם העוזר" : "שאלו את העוזר"}>
            <span className="spark"><ISpark size={14} /></span><span className="fab-label">{assistantOrigin ? "חזרה לשיחה" : "עוזר"}</span>
          </button>
        )}
        <nav className="bottom-nav">
          {TABS.map((t) => (
            <button key={t.to} className={active(t.to) ? "on" : ""} onClick={() => nav(t.to)} aria-current={active(t.to) ? "page" : undefined}>
              {t.icon}<span>{t.label}</span>
            </button>
          ))}
        </nav>
        {menu && <Drawer caseId={caseId} onPick={(id) => { setCaseId(id); setMenu(false); nav("/customer"); }} onClose={() => setMenu(false)} />}
        {assistant.open && <AssistantSheet />}
        {upload.open && <UploadSheet key={upload.nonce} />}
        </>)}
      </div>
    </div>
  );
}

function Drawer({ caseId, onPick, onClose }: { caseId: string; onPick: (id: string) => void; onClose: () => void }) {
  const [cases, setCases] = useState<{ case_id: string; display_number: string; title_he: string }[] | null>(null);
  if (cases === null) api.demoCases().then(setCases).catch(() => setCases([]));
  const { reload } = useCase();
  return (
    <div className="drawer" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="small muted">התיקים שלי</div>
        {(cases || []).map((c) => (
          <button key={c.case_id} onClick={() => onPick(c.case_id)} style={{ color: c.case_id === caseId ? "var(--mz-orange)" : undefined }}>
            {c.display_number} · {c.title_he}
          </button>
        ))}
        <div className="small muted" style={{ marginTop: 14 }}>הדגמה</div>
        <Link to="/banker" onClick={onClose}>תצוגת בנקאי — חבילת ראיות</Link>
        <Link to="/system" onClick={onClose}>מטריצת אינטגרציות, MCP ורובריקות</Link>
        <button onClick={async () => { if (confirm("לאפס את התיק הזה ולמחוק מסמכים, ממצאים ושיחה?")) { await api.reset(caseId); reload(); onClose(); } }}>
          איפוס תיק ההדגמה
        </button>
        <div className="tiny muted" style={{ marginTop: "auto", lineHeight: 1.6 }}>
          הלוגו של מזרחי־טפחות נלקח מאתר הבנק הציבורי לצורך הדגמת קונספט פנימית בלבד. כל הנתונים סינתטיים.
        </div>
      </div>
    </div>
  );
}
