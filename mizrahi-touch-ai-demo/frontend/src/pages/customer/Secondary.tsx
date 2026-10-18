import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ils, ilsL, localeL } from "../../api";
import { useCase } from "../../caseContext";
import { useLang } from "../../i18n";
import { IBag, ICalendar, ICheck, ICoins, IUpload } from "../../components/Icons";

/** The customer's four steps of the document check; each AI readiness state (workflow/readiness.py) sits on one of them. */
const JEEN_STEPS = ["העלאת מסמכים", "בדיקה חכמה", "עיון הבנקאית", "הכנה אושרה"];
const JEEN_STEPS_EN = ["Upload documents", "Smart check", "Banker review", "Preparation confirmed"];
const STEP_OF: Record<string, number> = { NOT_CHECKED: 0, ACTION_REQUIRED: 0, CHECKING: 1, RECHECKING: 1, ERROR: 1,
  READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS: 2, READY_FOR_HUMAN_REVIEW: 2, PREPARATION_CONFIRMED: 3 };
const dmy = (iso: string) => iso.split("-").reverse().join("/");

export function RequestDetails() {
  const { snap, openAssistant } = useCase();
  const { en, t } = useLang();
  if (!snap) return null;
  const c = snap.case;
  const money = en ? ilsL : ils;
  const firstEn = (h: string) => { const b = c.borrowers.find((x) => x.borrower_id === h); return b?.first_name_en || b?.first_name_he; };
  return (
    <>
      <div className="page-title">{t("פרטי בקשת ההלוואה", "Loan application details")}</div>
      <div className="card">
        <div className="card-row" style={{ marginBottom: 12 }}><span className="circle-icon small"><IBag size={18} /></span>
          <span className="grow"><div className="card-sub">{t("סכום הלוואה מבוקש", "Requested loan amount")}</div><div className="card-title ltr">{money(c.requested_loan_ils)}</div></span></div>
        <div className="card-row" style={{ marginBottom: 12 }}><span className="circle-icon small"><ICoins size={18} /></span>
          <span className="grow"><div className="card-sub">{t("מספר תשלומים מבוקש", "Requested number of payments")}</div><div className="card-title ltr">{c.loan?.payments}</div></span></div>
        {c.preliminary_decision && <div className="card-row"><span className="circle-icon small"><ICoins size={18} /></span>
          <span className="grow"><div className="card-sub">{(en && c.preliminary_decision.label_en) || c.preliminary_decision.label_he}</div><div className="card-title ltr">{money(c.preliminary_decision.amount_ils)}</div></span></div>}
      </div>
      <div style={{ textAlign: "center", margin: "6px 0 14px" }}>
        <button className="btn btn-ghost" onClick={() => openAssistant(t("אני רוצה לפנות לבנקאית לעדכון הבקשה", "I'd like to contact my banker to update my application"))}>{t("פניה לבנקאית לעדכון הבקשה", "Contact your banker to update the application")}</button>
      </div>
      <div className="kv"><span>{t("תאריך הגשת בקשה", "Application submitted")}</span><span className="ltr">{new Date(c.submitted_at).toLocaleString(localeL())}</span></div>
      <div className="section-label">{t("פרטי ההלוואה", "Loan details")}</div>
      <div className="kv"><span>{t("מסלול", "Product")}</span><span>{(en && c.loan?.product_en) || c.loan?.product_he}</span></div>
      <div className="kv"><span>{t("מטרת ההלוואה", "Loan purpose")}</span><span>{en ? <>{c.loan?.purpose_en || c.loan?.purpose_he}{c.loan?.note_he ? <> · {c.loan.note_en || <bdi lang="he" dir="rtl">{c.loan.note_he}</bdi>}</> : null}</>
        : <>{c.loan?.purpose_he}{c.loan?.note_he ? ` · ${c.loan.note_he}` : ""}</>}</span></div>
      {(c.accounts || []).map((a) => (
        <div key={a.account_id} className="kv"><span>{(en && a.label_en) || a.label_he}</span><span>{en
          ? `${a.bank_en || a.bank_he} · ${a.holders.map(firstEn).join(" and ")}`
          : <>{a.bank_he} · {a.holders.map((h) => c.borrowers.find((b) => b.borrower_id === h)?.first_name_he).join(" ו")}</>}</span></div>
      ))}
      {c.borrowers.map((b, i) => (
        <div key={b.borrower_id}>
          <div className="section-label">{i === 0 ? t("פרטי המבקש/ת", "Applicant details") : t("פרטי לווה נוסף", "Co-borrower details")}</div>
          <div className="kv"><span>{t("שם מלא", "Full name")}</span><span>{(en && b.name_en) || b.name_he}</span></div>
          <div className="kv"><span>{t("מספר ת.ז", "ID number")}</span><span className="ltr">******{b.national_id.slice(-3)}</span></div>
          <div className="kv"><span>{t("סטטוס תעסוקה", "Employment")}</span><span>{en
            ? <>{b.employment === "self_employed" ? "Self-employed" : "Salaried"} · {b.employer_declared_en || <bdi lang="he" dir="rtl">{b.employer_declared_he}</bdi>}</>
            : <>{b.employment === "self_employed" ? "עצמאי/ת" : "שכיר/ה"} · {b.employer_declared_he}</>}</span></div>
          <div className="kv"><span>{t("הכנסה נטו מוצהרת", "Declared net income")}</span><span className="ltr">{money(b.declared_net_monthly_ils)}</span></div>
        </div>
      ))}
    </>
  );
}

export function Stages() {
  const { snap } = useCase();
  const nav = useNavigate();
  const { en, t } = useLang();
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
      <div className="page-title">{t("שלבים", "Stages")}</div>
      <p className="page-sub">{t("כאן רואים איפה הבקשה עומדת בבנק, ואיפה עומדת בדיקת המסמכים החכמה של JEEN.", "See where your application stands at the bank, and where JEEN's smart document check stands.")}</p>
      <section className="card st-card" aria-labelledby="st-bank">
        <h2 className="st-title" id="st-bank">{t("שלב הבקשה בבנק", "Your application's stage at the bank")}</h2>
        <ol className="st-list">
          {stages.map((s) => {
            const state = s.index < idx ? "done" : s.index === idx ? "now" : "next";
            return (
              <li key={s.index} className={`st-item ${state}`} aria-current={state === "now" ? "step" : undefined}>
                <span className="st-dot" aria-hidden>{state === "done" ? <ICheck size={13} /> : s.index}</span>
                <div className="st-text">
                  <div className="st-label">{(en && s.label_en) || s.label_he}{state === "now" && <span className="st-here">{t("כאן אתם", "You are here")}</span>}</div>
                  {state === "now" && pd && (
                    <div className="st-detail">{en ? <>{pd.label_en || pd.label_he} for <b className="ltr">{ilsL(pd.amount_ils)}</b><br />valid until <span className="ltr">{dmy(pd.valid_until)}</span></>
                      : <>{pd.label_he} על <b className="ltr">{ils(pd.amount_ils)}</b><br />בתוקף עד <span className="ltr">{dmy(pd.valid_until)}</span></>}</div>
                  )}
                  {state === "now" && next && <div className="st-next">{t("השלב הבא: ", "Next stage: ")}{(en && next.label_en) || next.label_he}</div>}
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="card st-card" aria-labelledby="st-jeen">
        <h2 className="st-title with-brand" id="st-jeen">{t("בדיקת המסמכים החכמה", "The smart document check")}<img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt={t("של JEEN", "by JEEN")} /></h2>
        {noPayslips ? <div className="st-foot">{t("אין מסמכים לבדיקה בתיק זה. מסמכי התיק מטופלים ישירות מול הבנק.", "There are no documents to check in this application. Its documents are handled directly with the bank.")}</div> : (<>
          {required > 0 && (<>
            <div className="st-progress">{en ? <><b>{verified} of {required}</b> document requirements complete</> : <><b>{verified} מתוך {required}</b> דרישות מסמכים הושלמו</>}</div>
            <span className="dx-meter" aria-hidden><span style={{ width: `${Math.round((verified / required) * 100)}%` }} /></span>
          </>)}
          <ol className="st-steps">
            {JEEN_STEPS.map((label, i) => {
              const done = i < step || (i === step && step === JEEN_STEPS.length - 1);
              return (
                <li key={label} className={`stage-item${done ? " done" : ""}${i === step ? " now" : ""}`} aria-current={i === step ? "step" : undefined}>
                  <span className="st-step-dot" aria-hidden>{done ? <ICheck size={11} /> : i + 1}</span>{en ? JEEN_STEPS_EN[i] : label}
                </li>
              );
            })}
          </ol>
          <div className={`st-status${r.state === "ERROR" || r.state === "ACTION_REQUIRED" ? " warn" : ""}`} data-testid="stages-ai-status">
            <span className="grow">{(en && r.state_en) || r.state_he}</span>
            {canUpload && <button className="btn btn-dark st-cta" onClick={() => nav("/customer/documents?focus=payslips")}><IUpload size={16} />{t("להעלאה", "Upload")}</button>}
          </div>
          <div className="st-foot">{t("הבדיקה מכינה את מסמכי הבקשה לבנקאי ואינה משנה את שלב הבקשה. ההחלטה על ההלוואה נתונה לבנק.", "The check prepares your application's documents for the banker and doesn't change the application's stage. The decision on the loan rests with the bank.")}</div>
        </>)}
      </section>
    </>
  );
}

export function Meetings() {
  const { snap, openAssistant } = useCase();
  const { en, t } = useLang();
  if (!snap) return null;
  const m = snap.case.meeting;
  return (
    <>
      <div className="page-title">{t("פגישות", "Meetings")}</div>
      {m ? (
        <div className="card card-row">
          <span className="circle-icon"><ICalendar /></span>
          <span className="grow"><div className="card-title">{(en && m.type_en) || m.type_he}</div>
            <div className="card-sub ltr">{m.date.split("-").reverse().join("/")} · {m.from}–{m.to}</div>
            <div className="tiny muted">{en ? <>With {snap.case.banker.name_en || snap.case.banker.name_he}</> : <>עם {snap.case.banker.name_he}</>}</div></span>
        </div>
      ) : <div className="card small muted">{t("אין פגישות מתוכננות.", "No meetings scheduled.")}</div>}
      <button className="btn btn-dark" onClick={() => openAssistant(t("אני רוצה לתאם פגישה עם הבנקאית", "I'd like to schedule a meeting with my banker"))}>{t("בקשה לתיאום פגישה", "Request a meeting")}</button>
      <div className="tiny muted" style={{ marginTop: 8 }}>{t("הבקשה עוברת לבנקאית דרך עוזר המסמכים; התיאום עצמו נעשה על ידי הבנק.", "Your request goes to your banker through the document assistant; the bank arranges the meeting itself.")}</div>
    </>
  );
}

export function Tools() {
  const [amount, setAmount] = useState(100000);
  const [payments, setPayments] = useState(60);
  const [rate, setRate] = useState(7);
  const { en, t } = useLang();
  const monthly = useMemo(() => {
    const n = payments, i = rate / 100 / 12;
    return i === 0 ? amount / n : (amount * i) / (1 - Math.pow(1 + i, -n));
  }, [amount, payments, rate]);
  return (
    <>
      <div className="page-title">{t("כלים", "Tools")}</div>
      <div className="card">
        <div className="card-title">{t("מחשבון החזר חודשי, להמחשה בלבד", "Monthly repayment calculator, for illustration only")}</div>
        <div className="tiny muted" style={{ marginBottom: 10 }}>{t("מחשבון כללי (לוח שפיצר). הריבית מוזנת על ידכם, זו אינה הצעת ריבית, אינה הצעת אשראי ואינה החלטה של הבנק.",
          "A general calculator (Spitzer amortization). You enter the interest rate yourself — it is not a rate offer, not a credit offer and not a decision by the bank.")}</div>
        {[["סכום הלוואה (₪)", amount, setAmount, 5000, 250000, 1000, "Loan amount (₪)"], ["מספר תשלומים", payments, setPayments, 2, 120, 1, "Number of payments"],
          ["ריבית שנתית (%)", rate, setRate, 0, 15, 0.1, "Annual interest rate (%)"]].map(([label, value, set, min, max, step, labelEn]) => (
          <label key={label as string} className="stack" style={{ gap: 4, marginBottom: 10 }}>
            <span className="small bold">{(en ? labelEn : label) as string}: <span className="ltr">{Number(value).toLocaleString(localeL())}</span></span>
            <input type="range" min={min as number} max={max as number} step={step as number} value={value as number}
              onChange={(e) => (set as (n: number) => void)(Number(e.target.value))} />
          </label>
        ))}
        <div className="statbox" style={{ textAlign: "center" }}><span>{t("החזר חודשי משוער", "Estimated monthly repayment")}</span><b className="ltr">{en ? ilsL(Math.round(monthly)) : ils(Math.round(monthly))}</b></div>
      </div>
      <a className="card card-row" style={{ textDecoration: "none" }} href="https://www.mizrahi-tefahot.co.il/loans/privateloanslib/all-purpose-loan/" target="_blank" rel="noreferrer">
        <span className="grow"><div className="card-title">{t("הלוואה לכל מטרה, באתר מזרחי־טפחות", "All-purpose loan, on the Mizrahi-Tefahot website (Hebrew)")}</div>
          <div className="card-sub">{t("המקור הציבורי לרשימת המסמכים: ת״ז, 3 תלושים, דפי עו״ש ל־3 חודשים ואסמכתה למטרה", "The public source of the document list: ID card, 3 payslips, 3 months of bank statements and proof of purpose")}</div></span>
      </a>
    </>
  );
}
