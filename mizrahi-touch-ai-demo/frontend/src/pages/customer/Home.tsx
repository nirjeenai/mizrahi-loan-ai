import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ils, ilsL, localeL } from "../../api";
import { useCase } from "../../caseContext";
import { useLang } from "../../i18n";
import { DocumentCheckCard } from "../../components/DocumentCheckCard";
import { DocumentSummary } from "../../components/DocumentSummary";
import { FollowupNotice } from "../../components/FollowupNotice";
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

/** "Ido", "Ido and Noa", "Ido, Noa and Dana" */
const joinEn = (items: string[]) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);
const m0 = (m: { type_he: string; type_en?: string } | null | undefined, en: boolean) => (m ? (en ? m.type_en || m.type_he : m.type_he) : "");

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
  const { en, t } = useLang();
  if (!snap) return (
    <div className="page-sub" style={{ marginTop: 40, textAlign: "center" }} role="status">
      {en ? (error ? <>We couldn&apos;t load your application. <button className="link" onClick={reload}>Try again</button></> : <><span className="spinner" /> Loading your application…</>)
        : error ? <>לא הצלחנו לטעון את התיק. <button className="link" onClick={reload}>ניסיון חוזר</button></> : <><span className="spinner" /> טוען את התיק…</>}
    </div>
  );
  const c = snap.case;
  const stage = c.bank_stage;
  const names = en ? joinEn(c.borrowers.map((b) => b.first_name_en || b.first_name_he)) : c.borrowers.map((b) => b.first_name_he).join(" ו");
  const bankerName = en ? c.banker.name_en || c.banker.name_he : c.banker.name_he;
  const bankerRole = en ? c.banker.role_en || c.banker.role_he : c.banker.role_he;
  const meetingType = m0(c.meeting, en);
  const m = c.meeting;
  const date = m ? m.date.split("-").reverse().join("/") : "";
  return (
    <>
      <div className="greeting">
        <HomeArt />
        {en ? <h1>Hello {names}</h1> : <h1>שלום {names}</h1>}
        <p>{t("מה קורה בבקשת ההלוואה שלכם", "Here's where your loan application stands")}</p>
      </div>

      {stale && (
        <div className="home-stale" role="status" data-testid="card-stale">
          {en ? <span>We couldn&apos;t refresh your application{updatedAt ? <> since <span className="ltr">{updatedAt.toLocaleTimeString(localeL(), { hour: "2-digit", minute: "2-digit" })}</span></> : null}. The information may be out of date.</span>
            : <span>לא הצלחנו לרענן את התיק{updatedAt ? <> מאז <span className="ltr">{updatedAt.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" })}</span></> : null}. ייתכן שהמידע אינו עדכני.</span>}
          <button className="link" onClick={reload}>{t("ניסיון חוזר", "Try again")}</button>
        </div>
      )}

      {/* the bank's stage (MockBankAdapter, not authoritative) — never the AI readiness, which has its own cards below */}
      <button className="card stage-card pressable" onClick={() => nav("/customer/stages")} data-testid="stage-card">
        <span className="grow">
          {en ? <span className="stage-of">Stage <span className="ltr">{stage.index}</span> of <span className="ltr">{stage.of}</span> · in the bank&apos;s system</span>
            : <span className="stage-of">שלב <span className="ltr">{stage.index}</span> מתוך <span className="ltr">{stage.of}</span> · במערכת הבנק</span>}
          <span className="stage-label">{en ? stage.label_en || stage.label_he : stage.label_he}</span>
          <span className="card-sub">{en
            ? (c.preliminary_decision ? `${c.preliminary_decision.label_en || c.preliminary_decision.label_he} · not a final approval`
              : `${c.loan?.product_en || c.loan?.product_he || "Loan"} · ${c.loan?.purpose_en || c.loan?.purpose_he || ""}`)
            : c.preliminary_decision ? `${c.preliminary_decision.label_he} · אינו אישור סופי`
            : `${c.loan?.product_he || "הלוואה"} · ${c.loan?.purpose_he || ""}`}</span>
        </span>
        <StageRing step={stage.index} of={stage.of} label={en ? stage.label_en || stage.label_he : stage.label_he} compact />
        <span className="chev"><IChevron /></span>
      </button>

      <DocumentCheckCard />
      <FollowupNotice />

      <section className="card banker-box" aria-label={`${bankerRole}: ${bankerName}`} data-testid="banker-card">
        <div className="banker-top">
          <BankerAvatar key={c.banker.staff_id || c.banker.name_he} banker={c.banker} />
          <span className="grow"><div className="card-title">{bankerName}</div><div className="card-sub">{bankerRole}</div></span>
          <button className="banker-write" onClick={() => openAssistant(t(`אני רוצה לפנות ל${c.banker.name_he}`, `I'd like to contact ${bankerName}`))}><IChat size={16} />{t("כתיבת פנייה", "Write a message")}</button>
        </div>
        <button className="meet-row pressable" onClick={() => nav("/customer/meetings")} data-testid="banker-meeting"
          aria-label={m ? t(`פגישה קרובה: ${m.type_he}, ${date} ${m.from}–${m.to}`, `Upcoming meeting: ${meetingType}, ${date} ${m.from}–${m.to}`)
            : t("אין פגישה מתוכננת, לבקשת תיאום", "No meeting scheduled — request one")} title={m ? meetingType : undefined}>
          <span className="meet-ic" aria-hidden><ICalendar size={18} /></span>
          {m ? <span className="grow meet-when"><span className="meet-label">{t("פגישה קרובה · ", "Upcoming meeting · ")}</span><span className="ltr">{date}</span> · <span className="ltr">{m.from}–{m.to}</span></span>
            : <span className="grow meet-what">{t("אין פגישה מתוכננת · לבקשת תיאום", "No meeting scheduled · request one")}</span>}
          <span className="chev" aria-hidden><IChevron size={14} /></span>
        </button>
      </section>

      <DocumentSummary />

      <RecentUpdates />

      <button className="card card-row pressable" style={{ width: "100%", border: "none", textAlign: en ? "left" : "right" }} onClick={() => nav("/customer/request")}>
        <span className="circle-icon"><IBag /></span>
        <span className="grow"><div className="card-title">{t("פרטי בקשת ההלוואה", "Loan application details")}</div>
          <div className="card-sub"><span className="ltr">{en ? ilsL(c.requested_loan_ils) : ils(c.requested_loan_ils)}</span>{c.loan ? t(` · ${c.loan.payments} תשלומים`, ` · ${c.loan.payments} payments`) : ""}</div></span>
        <span className="chev"><IChevron /></span>
      </button>
    </>
  );
}
