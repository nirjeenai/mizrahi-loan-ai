import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ils } from "../../api";
import { useCase } from "../../caseContext";
import { DocumentCheckCard } from "../../components/DocumentCheckCard";
import { DocumentSummary } from "../../components/DocumentSummary";
import { IBag, ICalendar, IChat, IChevron } from "../../components/Icons";
import { RecentUpdates } from "../../components/RecentUpdates";
import { StageRing } from "../../components/StageRing";

/** Decorative: soft houses and a sun beside the greeting (Touch home art direction). No meaning, hidden from screen readers. */
function HomeArt() {
  return (
    <svg className="home-art" viewBox="0 0 170 92" aria-hidden focusable="false">
      <defs>
        <linearGradient id="homeSun" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor="#ffd2ad" /><stop offset="1" stopColor="#ffa25c" /></linearGradient>
      </defs>
      <circle cx="118" cy="30" r="22" fill="url(#homeSun)" opacity="0.85" />
      <path d="M8 92V58l26-20 26 20v34z" fill="#e4e8ee" />
      <path d="M52 92V48l34-26 34 26v44z" fill="#eef0f4" />
      <path d="M48 50 86 20l38 30" fill="none" stroke="#dde1e8" strokeWidth="4" strokeLinejoin="round" />
      <rect x="72" y="56" width="11" height="11" rx="1.5" fill="#dfe3ea" /><rect x="89" y="56" width="11" height="11" rx="1.5" fill="#dfe3ea" />
      <rect x="80" y="74" width="12" height="18" rx="1.5" fill="#dde1e8" />
      <rect x="22" y="66" width="9" height="9" rx="1.5" fill="#d6dbe3" />
      <path d="M118 92c0-9 7-15 15-15 3-7 10-10 17-7 5 1 9 6 9 11 6 1 10 5 10 11z" fill="#e9ecf1" />
    </svg>
  );
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("");

/** Synthetic demo portraits of the fictional bankers; anyone else (or a portrait that fails to load) gets initials. */
const PORTRAITS: Record<string, string> = { "STAFF-DANA": "/people/dana-cohen.jpg" };

function BankerAvatar({ banker }: { banker: { name_he: string; staff_id?: string } }) {
  const [failed, setFailed] = useState(false);
  const src = banker.staff_id ? PORTRAITS[banker.staff_id] : undefined;
  if (src && !failed) return <span className="avatar photo" aria-hidden><img src={src} alt="" onError={() => setFailed(true)} /></span>;
  return <span className="avatar initials" aria-hidden>{initials(banker.name_he)}</span>;
}

export function Home() {
  const { snap, error, stale, updatedAt, reload, openAssistant } = useCase();
  const nav = useNavigate();
  if (!snap) return (
    <div className="page-sub" style={{ marginTop: 40, textAlign: "center" }} role="status">
      {error ? <>לא הצלחנו לטעון את התיק. <button className="link" onClick={reload}>ניסיון חוזר</button></> : <><span className="spinner" /> טוען את התיק…</>}
    </div>
  );
  const c = snap.case;
  const stage = c.bank_stage;
  const names = c.borrowers.map((b) => b.first_name_he).join(" ו");
  const m = c.meeting;
  const date = m ? m.date.split("-").reverse().join("/") : "";
  return (
    <>
      <div className="greeting">
        <HomeArt />
        <h1>שלום {names}</h1>
        <p>מה קורה בבקשת ההלוואה שלכם</p>
      </div>

      {stale && (
        <div className="home-stale" role="status" data-testid="card-stale">
          <span>לא הצלחנו לרענן את התיק{updatedAt ? <> מאז <span className="ltr">{updatedAt.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" })}</span></> : null}. ייתכן שהמידע אינו עדכני.</span>
          <button className="link" onClick={reload}>ניסיון חוזר</button>
        </div>
      )}

      {/* the bank's stage (MockBankAdapter, not authoritative) — never the AI readiness, which has its own cards below */}
      <button className="card stage-card pressable" onClick={() => nav("/customer/stages")} data-testid="stage-card">
        <span className="grow">
          <span className="stage-of">שלב <span className="ltr">{stage.index}</span> מתוך <span className="ltr">{stage.of}</span> · במערכת הבנק</span>
          <span className="stage-label">{stage.label_he}</span>
          <span className="card-sub">{c.preliminary_decision ? `${c.preliminary_decision.label_he} · אינו אישור סופי`
            : `${c.loan?.product_he || "הלוואה"} · ${c.loan?.purpose_he || ""}`}</span>
        </span>
        <StageRing step={stage.index} of={stage.of} label={stage.label_he} compact />
        <span className="chev"><IChevron /></span>
      </button>

      <DocumentCheckCard />

      <section className="card banker-box" aria-label={`${c.banker.role_he}: ${c.banker.name_he}`} data-testid="banker-card">
        <div className="banker-top">
          <BankerAvatar key={c.banker.staff_id || c.banker.name_he} banker={c.banker} />
          <span className="grow"><div className="card-title">{c.banker.name_he}</div><div className="card-sub">{c.banker.role_he}</div></span>
          <button className="banker-write" onClick={() => openAssistant(`אני רוצה לפנות ל${c.banker.name_he}`)}><IChat size={16} />כתיבת פנייה</button>
        </div>
        <button className="meet-row pressable" onClick={() => nav("/customer/meetings")} data-testid="banker-meeting"
          aria-label={m ? `פגישה קרובה: ${m.type_he}, ${date} ${m.from}–${m.to}` : "אין פגישה מתוכננת — לבקשת תיאום"} title={m?.type_he}>
          <span className="meet-ic" aria-hidden><ICalendar size={18} /></span>
          {m ? <span className="grow meet-when"><span className="meet-label">פגישה קרובה · </span><span className="ltr">{date}</span> · <span className="ltr">{m.from}–{m.to}</span></span>
            : <span className="grow meet-what">אין פגישה מתוכננת · לבקשת תיאום</span>}
          <span className="chev" aria-hidden><IChevron size={14} /></span>
        </button>
      </section>

      <DocumentSummary />

      <RecentUpdates />

      <button className="card card-row pressable" style={{ width: "100%", border: "none", textAlign: "right" }} onClick={() => nav("/customer/request")}>
        <span className="circle-icon"><IBag /></span>
        <span className="grow"><div className="card-title">פרטי בקשת ההלוואה</div>
          <div className="card-sub"><span className="ltr">{ils(c.requested_loan_ils)}</span>{c.loan ? ` · ${c.loan.payments} תשלומים` : ""}</div></span>
        <span className="chev"><IChevron /></span>
      </button>
    </>
  );
}
