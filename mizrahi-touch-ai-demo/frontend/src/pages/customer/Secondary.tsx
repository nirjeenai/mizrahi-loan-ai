import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ils } from "../../api";
import { useCase } from "../../caseContext";
import { IBag, ICalendar, ICheck, ICoins, IUpload } from "../../components/Icons";

/** The customer's four steps of the document check; each AI readiness state (workflow/readiness.py) sits on one of them. */
const JEEN_STEPS = ["העלאת מסמכים", "בדיקה חכמה", "עיון הבנקאית", "הכנה אושרה"];
const STEP_OF: Record<string, number> = { NOT_CHECKED: 0, ACTION_REQUIRED: 0, CHECKING: 1, RECHECKING: 1, ERROR: 1,
  READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS: 2, READY_FOR_HUMAN_REVIEW: 2, PREPARATION_CONFIRMED: 3 };
const dmy = (iso: string) => iso.split("-").reverse().join("/");

export function RequestDetails() {
  const { snap, openAssistant } = useCase();
  if (!snap) return null;
  const c = snap.case;
  return (
    <>
      <div className="page-title">פרטי בקשת ההלוואה</div>
      <div className="card">
        <div className="card-row" style={{ marginBottom: 12 }}><span className="circle-icon small"><IBag size={18} /></span>
          <span className="grow"><div className="card-sub">סכום הלוואה מבוקש</div><div className="card-title ltr">{ils(c.requested_loan_ils)}</div></span></div>
        <div className="card-row" style={{ marginBottom: 12 }}><span className="circle-icon small"><ICoins size={18} /></span>
          <span className="grow"><div className="card-sub">מספר תשלומים מבוקש</div><div className="card-title ltr">{c.loan?.payments}</div></span></div>
        {c.preliminary_decision && <div className="card-row"><span className="circle-icon small"><ICoins size={18} /></span>
          <span className="grow"><div className="card-sub">{c.preliminary_decision.label_he}</div><div className="card-title ltr">{ils(c.preliminary_decision.amount_ils)}</div></span></div>}
      </div>
      <div style={{ textAlign: "center", margin: "6px 0 14px" }}>
        <button className="btn btn-ghost" onClick={() => openAssistant("אני רוצה לפנות לבנקאית לעדכון הבקשה")}>פניה לבנקאית לעדכון הבקשה</button>
      </div>
      <div className="kv"><span>תאריך הגשת בקשה</span><span className="ltr">{new Date(c.submitted_at).toLocaleString("he-IL")}</span></div>
      <div className="section-label">פרטי ההלוואה</div>
      <div className="kv"><span>מסלול</span><span>{c.loan?.product_he}</span></div>
      <div className="kv"><span>מטרת ההלוואה</span><span>{c.loan?.purpose_he}{c.loan?.note_he ? ` · ${c.loan.note_he}` : ""}</span></div>
      {(c.accounts || []).map((a) => (
        <div key={a.account_id} className="kv"><span>{a.label_he}</span><span>{a.bank_he} · {a.holders.map((h) => c.borrowers.find((b) => b.borrower_id === h)?.first_name_he).join(" ו")}</span></div>
      ))}
      {c.borrowers.map((b, i) => (
        <div key={b.borrower_id}>
          <div className="section-label">{i === 0 ? "פרטי המבקש/ת" : "פרטי לווה נוסף"}</div>
          <div className="kv"><span>שם מלא</span><span>{b.name_he}</span></div>
          <div className="kv"><span>מספר ת.ז</span><span className="ltr">******{b.national_id.slice(-3)}</span></div>
          <div className="kv"><span>סטטוס תעסוקה</span><span>{b.employment === "self_employed" ? "עצמאי/ת" : "שכיר/ה"} · {b.employer_declared_he}</span></div>
          <div className="kv"><span>הכנסה נטו מוצהרת</span><span className="ltr">{ils(b.declared_net_monthly_ils)}</span></div>
        </div>
      ))}
    </>
  );
}

export function Stages() {
  const { snap } = useCase();
  const nav = useNavigate();
  if (!snap) return null;
  const stages = snap.stage_dictionary.stages;
  const idx = snap.case.bank_stage.index;
  const next = stages.find((s) => s.index === idx + 1);
  const pd = snap.case.preliminary_decision;
  const r = snap.readiness;
  const step = STEP_OF[r.state] ?? 0;
  const required = r.progress?.total ?? r.payslips?.required ?? 0;
  const verified = r.progress?.done ?? r.payslips?.verified ?? 0;
  const noPayslips = r.customer_status === "NO_PAYSLIPS_REQUIRED";
  const canUpload = r.state === "NOT_CHECKED" || r.state === "ACTION_REQUIRED";
  return (
    <>
      <div className="page-title">שלבים</div>
      <p className="page-sub">כאן רואים איפה הבקשה עומדת בבנק, ואיפה עומדת בדיקת המסמכים החכמה של Jeen.</p>
      <section className="card st-card" aria-labelledby="st-bank">
        <h2 className="st-title" id="st-bank">שלב הבקשה בבנק</h2>
        <ol className="st-list">
          {stages.map((s) => {
            const state = s.index < idx ? "done" : s.index === idx ? "now" : "next";
            return (
              <li key={s.index} className={`st-item ${state}`} aria-current={state === "now" ? "step" : undefined}>
                <span className="st-dot" aria-hidden>{state === "done" ? <ICheck size={13} /> : s.index}</span>
                <div className="st-text">
                  <div className="st-label">{s.label_he}{state === "now" && <span className="st-here">כאן אתם</span>}</div>
                  {state === "now" && pd && (
                    <div className="st-detail">{pd.label_he} על <b className="ltr">{ils(pd.amount_ils)}</b><br />בתוקף עד <span className="ltr">{dmy(pd.valid_until)}</span></div>
                  )}
                  {state === "now" && next && <div className="st-next">השלב הבא: {next.label_he}</div>}
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="card st-card" aria-labelledby="st-jeen">
        <h2 className="st-title with-brand" id="st-jeen">בדיקת המסמכים החכמה<img className="jeen-logo-inline" src="/brand/jeen-logo.svg" alt="של Jeen" /></h2>
        {noPayslips ? <div className="st-foot">אין מסמכים לבדיקה בתיק זה. מסמכי התיק מטופלים ישירות מול הבנק.</div> : (<>
          {required > 0 && (<>
            <div className="st-progress"><b>{verified} מתוך {required}</b> דרישות מסמכים הושלמו</div>
            <span className="dx-meter" aria-hidden><span style={{ width: `${Math.round((verified / required) * 100)}%` }} /></span>
          </>)}
          <ol className="st-steps">
            {JEEN_STEPS.map((label, i) => {
              const done = i < step || (i === step && step === JEEN_STEPS.length - 1);
              return (
                <li key={label} className={`stage-item${done ? " done" : ""}${i === step ? " now" : ""}`} aria-current={i === step ? "step" : undefined}>
                  <span className="st-step-dot" aria-hidden>{done ? <ICheck size={11} /> : i + 1}</span>{label}
                </li>
              );
            })}
          </ol>
          <div className={`st-status${r.state === "ERROR" || r.state === "ACTION_REQUIRED" ? " warn" : ""}`} data-testid="stages-ai-status">
            <span className="grow">{r.state_he}</span>
            {canUpload && <button className="btn btn-dark st-cta" onClick={() => nav("/customer/documents?focus=payslips")}><IUpload size={16} />להעלאה</button>}
          </div>
          <div className="st-foot">הבדיקה מכינה את מסמכי הבקשה לבנקאי ואינה משנה את שלב הבקשה. ההחלטה על ההלוואה נתונה לבנק.</div>
        </>)}
      </section>
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
  const [amount, setAmount] = useState(100000);
  const [payments, setPayments] = useState(60);
  const [rate, setRate] = useState(7);
  const monthly = useMemo(() => {
    const n = payments, i = rate / 100 / 12;
    return i === 0 ? amount / n : (amount * i) / (1 - Math.pow(1 + i, -n));
  }, [amount, payments, rate]);
  return (
    <>
      <div className="page-title">כלים</div>
      <div className="card">
        <div className="card-title">מחשבון החזר חודשי, להמחשה בלבד</div>
        <div className="tiny muted" style={{ marginBottom: 10 }}>מחשבון כללי (לוח שפיצר). הריבית מוזנת על ידכם, זו אינה הצעת ריבית, אינה הצעת אשראי ואינה החלטה של הבנק.</div>
        {[["סכום הלוואה (₪)", amount, setAmount, 5000, 250000, 1000], ["מספר תשלומים", payments, setPayments, 2, 120, 1], ["ריבית שנתית (%)", rate, setRate, 0, 15, 0.1]].map(([label, value, set, min, max, step]) => (
          <label key={label as string} className="stack" style={{ gap: 4, marginBottom: 10 }}>
            <span className="small bold">{label as string}: <span className="ltr">{Number(value).toLocaleString("he-IL")}</span></span>
            <input type="range" min={min as number} max={max as number} step={step as number} value={value as number}
              onChange={(e) => (set as (n: number) => void)(Number(e.target.value))} />
          </label>
        ))}
        <div className="statbox" style={{ textAlign: "center" }}><span>החזר חודשי משוער</span><b className="ltr">{ils(Math.round(monthly))}</b></div>
      </div>
      <a className="card card-row" style={{ textDecoration: "none" }} href="https://www.mizrahi-tefahot.co.il/loans/privateloanslib/all-purpose-loan/" target="_blank" rel="noreferrer">
        <span className="grow"><div className="card-title">הלוואה לכל מטרה, באתר מזרחי־טפחות</div><div className="card-sub">המקור הציבורי לרשימת המסמכים: ת״ז, 3 תלושים, דפי עו״ש ל־3 חודשים ואסמכתה למטרה</div></span>
      </a>
    </>
  );
}
