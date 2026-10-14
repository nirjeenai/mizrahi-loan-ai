import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ils, type ApplicationOptions } from "../../api";
import { useCase } from "../../caseContext";

/** A new personal-loan application (demo intake). What is asked here only decides which documents are required;
 *  it is not an eligibility check and nothing is priced. */
export function Apply() {
  const { openCase } = useCase();
  const nav = useNavigate();
  const [opts, setOpts] = useState<ApplicationOptions | null>(null);
  const [form, setForm] = useState({ first_name_he: "", last_name_he: "", purpose: "car", requested_amount_ils: 80000,
    payments: 60, employment: "salaried" as "salaried" | "self_employed", employer_he: "", declared_net_monthly_ils: 12000 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.applicationOptions().then(setOpts).catch(() => setError("פתיחת בקשה חדשה אינה זמינה בסביבה זו.")); }, []);
  const set = (k: keyof typeof form, v: string | number) => setForm({ ...form, [k]: v });
  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.createApplication(form);
      openCase(r.case_id);
      nav("/customer/documents");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const valid = form.first_name_he.trim().length > 1 && form.last_name_he.trim().length > 1;
  return (
    <>
      <div className="page-title">בקשת הלוואה חדשה</div>
      <p className="page-sub">{opts?.product_he || "הלוואה לכל מטרה"} · כמה פרטים, ואחריהם נציג בדיוק אילו מסמכים נדרשים.</p>
      <div className="card stack" data-testid="apply-form">
        <div className="row" style={{ gap: 8 }}>
          <label className="stack grow" style={{ gap: 4 }}><span className="small bold">שם פרטי</span>
            <input className="input" value={form.first_name_he} onChange={(e) => set("first_name_he", e.target.value)} data-testid="apply-first" /></label>
          <label className="stack grow" style={{ gap: 4 }}><span className="small bold">שם משפחה</span>
            <input className="input" value={form.last_name_he} onChange={(e) => set("last_name_he", e.target.value)} data-testid="apply-last" /></label>
        </div>
        <div className="small bold">מטרת ההלוואה</div>
        <div className="choice wrap" role="radiogroup" aria-label="מטרת ההלוואה">
          {(opts?.purposes || []).map((p) => (
            <label key={p.id} className={form.purpose === p.id ? "on" : ""}>
              <input type="radio" name="purpose" checked={form.purpose === p.id} onChange={() => set("purpose", p.id)} data-purpose={p.id} />
              <span>{p.label_he}</span>
            </label>
          ))}
        </div>
        <label className="stack" style={{ gap: 4 }}>
          <span className="small bold">סכום מבוקש: <span className="ltr">{ils(form.requested_amount_ils)}</span></span>
          <input type="range" min={opts?.amount.min ?? 5000} max={opts?.amount.max ?? 250000} step={1000} value={form.requested_amount_ils}
            onChange={(e) => set("requested_amount_ils", Number(e.target.value))} />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="small bold">מספר תשלומים: <span className="ltr">{form.payments}</span></span>
          <input type="range" min={opts?.payments.min ?? 2} max={opts?.payments.max ?? 120} step={1} value={form.payments}
            onChange={(e) => set("payments", Number(e.target.value))} />
        </label>
        <div className="small bold">תעסוקה</div>
        <div className="choice">
          {([["salaried", "שכיר/ה"], ["self_employed", "עצמאי/ת"]] as const).map(([k, l]) => (
            <label key={k} className={form.employment === k ? "on" : ""}>
              <input type="radio" name="employment" checked={form.employment === k} onChange={() => set("employment", k)} data-employment={k} />
              <span>{l}</span>
            </label>
          ))}
        </div>
        <label className="stack" style={{ gap: 4 }}><span className="small bold">{form.employment === "salaried" ? "מעסיק" : "שם העסק"} (רשות)</span>
          <input className="input" value={form.employer_he} onChange={(e) => set("employer_he", e.target.value)} /></label>
        <label className="stack" style={{ gap: 4 }}><span className="small bold">הכנסה חודשית נטו מוצהרת (₪)</span>
          <input className="input ltr" type="number" min={0} value={form.declared_net_monthly_ils}
            onChange={(e) => set("declared_net_monthly_ils", Number(e.target.value))} /></label>
        <div className="tiny muted" style={{ lineHeight: 1.6 }}>{opts?.note_he} ההכנסה המוצהרת נשמרת כהצהרה שלכם ואינה הכנסה מאומתת.</div>
        {error && <div className="notice" role="alert">{error}</div>}
        <button className="btn btn-orange" disabled={!valid || busy || !opts} onClick={submit} data-testid="apply-submit">
          {busy && <span className="spinner" />}פתיחת הבקשה והצגת המסמכים הנדרשים</button>
      </div>
      <div className="tiny muted" style={{ marginTop: 10 }}>בקשת הדגמה עם נתונים סינתטיים — אינה מגיעה לבנק.</div>
    </>
  );
}
