import { useMemo, useState } from "react";
import { ils } from "../../api";
import { useCase } from "../../caseContext";
import { IBag, ICalendar, ICoins, IHouse } from "../../components/Icons";

const READINESS_FLOW: [string, string][] = [["NOT_CHECKED", "טרם נבדק"], ["CHECKING", "בבדיקה"], ["ACTION_REQUIRED", "נדרשת השלמה"],
  ["RECHECKING", "בדיקה חוזרת"], ["READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS", "לבנקאית — עם ממצאים"], ["READY_FOR_HUMAN_REVIEW", "מוכן לבנקאית"],
  ["PREPARATION_CONFIRMED", "הבנקאית אישרה הכנה"]];

export function RequestDetails() {
  const { snap, openAssistant } = useCase();
  if (!snap) return null;
  const c = snap.case;
  return (
    <>
      <div className="page-title">פרטי הבקשה שלנו</div>
      <div className="card">
        <div className="card-row" style={{ marginBottom: 12 }}><span className="circle-icon small"><IBag size={18} /></span>
          <span className="grow"><div className="card-sub">סכום משכנתה מבוקש</div><div className="card-title ltr">{ils(c.requested_loan_ils)}</div></span></div>
        <div className="card-row" style={{ marginBottom: 12 }}><span className="circle-icon small"><IHouse size={18} /></span>
          <span className="grow"><div className="card-sub">מחיר הנכס</div><div className="card-title ltr">{ils(c.property.price_ils)}</div></span></div>
        {c.preliminary_decision && <div className="card-row"><span className="circle-icon small"><ICoins size={18} /></span>
          <span className="grow"><div className="card-sub">{c.preliminary_decision.label_he}</div><div className="card-title ltr">{ils(c.preliminary_decision.amount_ils)}</div></span></div>}
      </div>
      <div style={{ textAlign: "center", margin: "6px 0 14px" }}>
        <button className="btn btn-ghost" onClick={() => openAssistant("אני רוצה לפנות לבנקאית לעדכון הבקשה")}>פניה לבנקאית לעדכון הבקשה</button>
      </div>
      <div className="kv"><span>תאריך הגשת בקשה</span><span className="ltr">{new Date(c.submitted_at).toLocaleString("he-IL")}</span></div>
      <div className="section-label">פרטי נכס</div>
      <div className="kv"><span>מטרת משכנתה</span><span>{c.property.purpose_he}</span></div>
      <div className="kv"><span>יישוב</span><span>{c.property.city_he}</span></div>
      {c.borrowers.map((b, i) => (
        <div key={b.borrower_id}>
          <div className="section-label">{i === 0 ? "פרטי לווה ראשי" : "פרטי לווה נוסף"}</div>
          <div className="kv"><span>שם מלא</span><span>{b.name_he}</span></div>
          <div className="kv"><span>מספר ת.ז</span><span className="ltr">******{b.national_id.slice(-3)}</span></div>
          <div className="kv"><span>סטטוס תעסוקה</span><span>שכיר/ה · {b.employer_declared_he}</span></div>
          <div className="kv"><span>הכנסה נטו מוצהרת</span><span className="ltr">{ils(b.declared_net_monthly_ils)}</span></div>
        </div>
      ))}
      <div className="tiny muted" style={{ marginTop: 12 }}>נתוני הבקשה הם נתונים סינתטיים להדגמה.</div>
    </>
  );
}

export function Stages() {
  const { snap } = useCase();
  if (!snap) return null;
  const idx = snap.case.bank_stage.index;
  const ai = snap.readiness.state;
  return (
    <>
      <div className="page-title">שלבים</div>
      <p className="page-sub">שני מסלולים נפרדים: שלב הבקשה במערכת הבנק, ומצב הבדיקה החכמה של המסמכים. ה־AI מעדכן רק את המסלול השני.</p>
      <div className="card">
        <div className="card-title">שלב הבקשה בבנק</div>
        <div className="timeline" style={{ marginTop: 10 }}>
          {snap.stage_dictionary.stages.map((s) => (
            <div className="tl-item" key={s.index} style={{ opacity: s.index > idx ? 0.45 : 1 }}>
              <div className="tl-title">{s.index}. {s.label_he} {s.index === idx && <span className="badge warn">כאן אתם</span>}</div>
              {!s.observed && <div className="tiny muted">תווית הדגמה</div>}
            </div>
          ))}
        </div>
        <div className="tiny muted">{snap.stage_dictionary.note_he}</div>
      </div>
      <div className="card">
        <div className="row between"><div className="card-title">הבדיקה החכמה של מסמכי השכר</div><span className="mode LIVE">AI</span></div>
        <div className="stage-list">
          {READINESS_FLOW.map(([k, label]) => (
            <div key={k} className={`stage-item ${k === ai ? "now" : ""}`}><span className="dot" />{label}</div>
          ))}
        </div>
      </div>
    </>
  );
}

export function Meetings() {
  const { snap, openAssistant } = useCase();
  if (!snap) return null;
  const m = snap.case.meeting;
  return (
    <>
      <div className="page-title">פגישות</div>
      {m ? (
        <div className="card card-row">
          <span className="circle-icon"><ICalendar /></span>
          <span className="grow"><div className="card-title">{m.type_he}</div>
            <div className="card-sub ltr">{m.date.split("-").reverse().join("/")} · {m.from}–{m.to}</div>
            <div className="tiny muted">עם {snap.case.banker.name_he}</div></span>
        </div>
      ) : <div className="card small muted">אין פגישות מתוכננות.</div>}
      <button className="btn btn-dark" onClick={() => openAssistant("אני רוצה לתאם פגישה עם הבנקאית")}>בקשה לתיאום פגישה</button>
      <div className="tiny muted" style={{ marginTop: 8 }}>הבקשה עוברת לבנקאית דרך עוזר המסמכים; התיאום עצמו נעשה על ידי הבנק.</div>
    </>
  );
}

export function Tools() {
  const [amount, setAmount] = useState(1400000);
  const [years, setYears] = useState(25);
  const [rate, setRate] = useState(4.5);
  const monthly = useMemo(() => {
    const n = years * 12, i = rate / 100 / 12;
    return i === 0 ? amount / n : (amount * i) / (1 - Math.pow(1 + i, -n));
  }, [amount, years, rate]);
  return (
    <>
      <div className="page-title">כלים</div>
      <div className="card">
        <div className="card-title">מחשבון החזר חודשי</div>
        <div className="tiny muted" style={{ marginBottom: 10 }}>מחשבון כללי (לוח שפיצר). הריבית מוזנת על ידכם — זו אינה הצעת ריבית של הבנק.</div>
        {[["סכום הלוואה (₪)", amount, setAmount, 100000, 5000000, 10000], ["תקופה (שנים)", years, setYears, 4, 30, 1], ["ריבית שנתית (%)", rate, setRate, 0, 10, 0.05]].map(([label, value, set, min, max, step]) => (
          <label key={label as string} className="stack" style={{ gap: 4, marginBottom: 10 }}>
            <span className="small bold">{label as string}: <span className="ltr">{Number(value).toLocaleString("he-IL")}</span></span>
            <input type="range" min={min as number} max={max as number} step={step as number} value={value as number}
              onChange={(e) => (set as (n: number) => void)(Number(e.target.value))} />
          </label>
        ))}
        <div className="statbox" style={{ textAlign: "center" }}><span>החזר חודשי משוער</span><b className="ltr">{ils(Math.round(monthly))}</b></div>
      </div>
      <a className="card card-row" style={{ textDecoration: "none" }} href="https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/second-hand/" target="_blank" rel="noreferrer">
        <span className="grow"><div className="card-title">המדריך הרשמי לרכישת דירה יד שנייה</div><div className="card-sub">באתר מזרחי־טפחות — המקור לרשימת המסמכים</div></span>
      </a>
    </>
  );
}
