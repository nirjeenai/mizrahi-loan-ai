import { useState } from "react";
import type { Json, Settings } from "../../adminApi";
import { tr, useLang } from "../../i18n";
import { Chip } from "../banker/deskUi";
import type { KindProps } from "./AdminPage";
import { FieldErrors, Lock, NumberField, Toggle } from "./ui";

const FAMILY_HE: Record<string, string> = {
  id_document: "תעודת זהות", payslip: "תלושי שכר", bank_statement: "דפי עו״ש", purpose_proof: "אסמכתה למטרה", tax_form: "שומת מס / אישור רו״ח",
  business_registration: "אישור רישום עוסק", pnl_statement: "דוח רווח והפסד", company_registry: "נסח חברה",
  signatory_authority: "מורשי חתימה", financial_statements: "דוחות כספיים", business_bank_statement: "דפי עו״ש עסקי",
};
const PER_HE: Record<string, string> = { applicant: "לכל לווה", account: "לכל חשבון", case: "פעם אחת לתיק" };
const EMPLOYMENT_HE: Record<string, string> = { salaried: "שכירים", self_employed: "עצמאים", allowance: "מקבלי קצבה" };
const REGISTRATION_HE: Record<string, string> = { vat_exempt: "עוסק פטור", vat_registered: "עוסק מורשה" };
const ENTITY_HE: Record<string, string> = { individual: "הלוואה פרטית", company: "חברה בע״מ" };
const FAMILY_EN: Record<string, string> = {
  id_document: "ID card", payslip: "Payslips", bank_statement: "Bank statements", purpose_proof: "Proof of purpose", tax_form: "Tax assessment / CPA letter",
  business_registration: "Business registration certificate", pnl_statement: "Profit and loss statement", company_registry: "Company registry extract",
  signatory_authority: "Authorized signatories", financial_statements: "Financial statements", business_bank_statement: "Business bank statements",
};
const PER_EN: Record<string, string> = { applicant: "Per borrower", account: "Per account", case: "Once per case" };
const EMPLOYMENT_EN: Record<string, string> = { salaried: "salaried", self_employed: "self-employed", allowance: "allowance recipients" };
const REGISTRATION_EN: Record<string, string> = { vat_exempt: "Exempt dealer", vat_registered: "Licensed dealer" };
const ENTITY_EN: Record<string, string> = { individual: "Personal loan", company: "Limited company" };
// by the Hebrew label of RULE_FIELDS
const RULE_EN: Record<string, string> = {
  "בדיקת תוקף התעודה": "Check the ID card's expiry", "מספר חודשים נדרש": "Number of months required",
  "רצף ימים נדרש": "Continuous coverage required", "גיל מרבי של הדף האחרון": "Maximum age of the latest statement",
  "חשבון משותף מכסה את כל בעליו": "A joint account covers all its holders", "גיל מרבי של האסמכתה": "Maximum age of the proof",
  "שנת מס אחרונה לפחות לפני": "Latest tax year, at least",
};
const UNIT_EN: Record<string, string> = { "חודשים": "months", "ימים": "days", "שנים": "years back" };
/** a label from one of the maps above in the platform's language */
const L = (he: Record<string, string>, en: Record<string, string>, key: string) => tr(he[key], en[key]) || key;
// families with a review rubric (backend/rubrics); in the limited company path only the signatory's ID is AI-reviewed
const AI_FAMILIES = ["id_document", "payslip", "bank_statement", "purpose_proof", "tax_form", "business_registration", "pnl_statement"];
// the rule fields each document family uses, with the schema's bounds
const RULE_FIELDS: Record<string, { key: string; label: string; min?: number; max?: number; unit?: string; bool?: boolean }[]> = {
  id_document: [{ key: "check_expiry", label: "בדיקת תוקף התעודה", bool: true }],
  payslip: [{ key: "months", label: "מספר חודשים נדרש", min: 1, max: 6, unit: "חודשים" }],
  bank_statement: [{ key: "coverage_days", label: "רצף ימים נדרש", min: 30, max: 180, unit: "ימים" },
    { key: "max_age_days", label: "גיל מרבי של הדף האחרון", min: 7, max: 365, unit: "ימים" },
    { key: "joint_satisfies_all", label: "חשבון משותף מכסה את כל בעליו", bool: true }],
  purpose_proof: [{ key: "max_age_days", label: "גיל מרבי של האסמכתה", min: 7, max: 365, unit: "ימים" }],
  tax_form: [{ key: "min_tax_year_offset", label: "שנת מס אחרונה לפחות לפני", min: 1, max: 3, unit: "שנים" }],
};

export function DocumentsTab({ work, edit, bar, settings }: KindProps & { settings: Settings }) {
  const { en, t } = useLang();
  const config = work.config;
  const report = work.report;
  const reqs: Json[] = config.document_requirements || [];
  const catalog = settings.requirement_catalog;
  const ids = [...catalog.map((r) => r.id), ...reqs.map((r) => r.id).filter((id) => !catalog.some((c) => c.id === id))];
  const setReqs = (next: Json[]) => edit((c) => ({ ...c, document_requirements: next }));
  const updateReq = (id: string, update: (r: Json) => Json) => setReqs(reqs.map((r) => (r.id === id ? update(r) : r)));
  const include = (id: string, on: boolean) => {
    if (!on) return setReqs(reqs.filter((r) => r.id !== id));
    const source = catalog.find((r) => r.id === id)!;
    const order = (x: string) => ids.indexOf(x);
    setReqs([...reqs, structuredClone(source)].sort((a, b) => order(a.id) - order(b.id)));
  };
  return (
    <div className="adm-tab" data-testid="tab-body-documents">
      {bar}
      {en ? <div className="notice navy small" style={{ marginBottom: 12 }}>
        These requirements set what the customer is asked to upload and what the AI checks. An open case is locked to the requirements version
        that was active when it opened, so a change applies to new cases (or to a case the banker explicitly updated). The requirement texts are
        the canonical Hebrew the customer sees; the customer app's English versions are shown beside them for reference.
      </div> : <div className="notice navy small" style={{ marginBottom: 12 }}>
        הדרישות כאן קובעות מה הלקוח מתבקש להעלות ומה ה-AI בודק. תיק פתוח ננעל על גרסת הדרישות שהייתה פעילה כשנפתח, כך ששינוי חל על תיקים חדשים
        (או על תיק שהבנקאי עדכן במפורש).
      </div>}
      <div className="panel">
        <h3>{t("מסמכים נדרשים", "Required documents")}</h3>
        <FieldErrors report={report} path="document_requirements" />
        <div className="adm-reqs">
          {ids.map((id) => {
            const r = reqs.find((x) => x.id === id);
            const source = r || catalog.find((x) => x.id === id)!;
            const path = `document_requirements.${r ? reqs.indexOf(r) : -1}`;
            const canon = settings.canonical_en?.requirements[id];
            return (
              <div key={id} className={`adm-req${r ? "" : " off"}`} data-testid={`req-${id}`}>
                <div className="adm-req-head">
                  <Toggle label={<>{L(FAMILY_HE, FAMILY_EN, source.family)} <span className="tiny muted ltr">{id}</span></>}
                    checked={!!r} onChange={(on) => include(id, on)} testId={`req-include-${id}`} />
                  <span className="row" style={{ gap: 4 }}>
                    <Chip>{L(PER_HE, PER_EN, source.per)}</Chip>
                    {source.condition?.employment && <Chip tone="info">{t("רק ל", "Only for ")}{source.condition.employment.map((e: string) => L(EMPLOYMENT_HE, EMPLOYMENT_EN, e)).join(" / ")}</Chip>}
                    {source.condition?.registration && <Chip tone="info">{source.condition.registration.map((e: string) => L(REGISTRATION_HE, REGISTRATION_EN, e)).join(" / ")}</Chip>}
                    {source.condition?.entity && <Chip tone="info">{source.condition.entity.map((e: string) => L(ENTITY_HE, ENTITY_EN, e)).join(" / ")}</Chip>}
                    {!AI_FAMILIES.includes(source.family) && <Chip>{t("בדיקת בנקאי · ללא AI", "Banker review · no AI")}</Chip>}
                    {r && <Chip tone={r.required ? "navy" : "neutral"}>{r.required ? t("חובה", "Mandatory") : t("רשות", "Optional")}</Chip>}
                  </span>
                </div>
                {r && (
                  <div className="adm-req-body">
                    <label className="adm-field wide"><span className="adm-label">{t("שם הדרישה ללקוח", "Requirement name shown to the customer (Hebrew)")}</span>
                      <input value={r.label_he} maxLength={80} {...(en ? { dir: "auto", lang: "he" } : {})} onChange={(e) => updateReq(id, (x) => ({ ...x, label_he: e.target.value }))} />
                      {r.label_he.includes("{months}") && <span className="tiny muted">{"{months}"} {t("יוחלף במספר החודשים", "is replaced with the number of months")}</span>}
                      {en && canon && <span className="tiny muted adm-en-hint" data-testid={`req-en-${id}`}>Customer app (English): {canon.label}</span>}
                    </label>
                    <label className="adm-field wide"><span className="adm-label">{t("הסבר קצר", "Short explanation (Hebrew)")}</span>
                      <input value={r.hint_he || ""} maxLength={300} {...(en ? { dir: "auto", lang: "he" } : {})} onChange={(e) => updateReq(id, (x) => ({ ...x, hint_he: e.target.value }))} />
                      {en && canon?.hint && <span className="tiny muted adm-en-hint">Customer app (English): {canon.hint}</span>}
                    </label>
                    <label className="adm-field wide"><span className="adm-label">{t("למה המסמך נדרש", "Why the document is needed (Hebrew)")}</span>
                      <input value={r.why_he || ""} maxLength={300} {...(en ? { dir: "auto", lang: "he" } : {})} onChange={(e) => updateReq(id, (x) => ({ ...x, why_he: e.target.value }))}
                        data-testid={`req-why-${id}`} />
                      {en && canon?.why && <span className="tiny muted adm-en-hint">Customer app (English): {canon.why}</span>}
                    </label>
                    <label className="adm-field wide"><span className="adm-label">{t("מסמכים חלופיים מקובלים (מופרדים ב־״;״)", "Accepted alternative documents (Hebrew, separated by “;”)")}</span>
                      <input value={(r.alternatives_he || []).join("; ")} maxLength={700} {...(en ? { dir: "auto", lang: "he" } : {})}
                        onChange={(e) => updateReq(id, (x) => ({ ...x, alternatives_he: e.target.value ? e.target.value.split(";").map((s) => s.trimStart()) : [] }))}
                        data-testid={`req-alternatives-${id}`} />
                      {en && !!canon?.alternatives.length && <span className="tiny muted adm-en-hint">Customer app (English): {canon.alternatives.join("; ")}</span>}
                    </label>
                    <Toggle label={t("מסמך חובה", "Mandatory document")} checked={!!r.required} onChange={(v) => updateReq(id, (x) => ({ ...x, required: v }))}
                      hint={t("מסמך רשות מוצג ללקוח אך אינו מעכב את השלמת הבקשה", "An optional document is shown to the customer but doesn't hold up completing the application")} />
                    {(RULE_FIELDS[r.family] || []).map((f) => f.bool ? (
                      <Toggle key={f.key} label={t(f.label, RULE_EN[f.label] || f.label)} checked={!!r.rules?.[f.key]}
                        onChange={(v) => updateReq(id, (x) => ({ ...x, rules: { ...x.rules, [f.key]: v } }))} />
                    ) : (
                      <NumberField key={f.key} label={t(f.label, RULE_EN[f.label] || f.label)} value={r.rules?.[f.key]} min={f.min!} max={f.max!}
                        unit={f.unit && t(f.unit, UNIT_EN[f.unit] || f.unit)}
                        path={`${path}.rules.${f.key}`} report={report} testId={`rule-${id}-${f.key}`}
                        onChange={(v) => updateReq(id, (x) => ({ ...x, rules: { ...x.rules, [f.key]: v } }))} />
                    ))}
                    <FieldErrors report={report} path={path} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="grid2">
        <Purposes config={config} edit={edit} report={report} canon={settings.canonical_en?.purposes} />
        <div className="panel">
          <h3>{t("בדיקת המסמכים", "Document review")}</h3>
          <NumberField label={t("סף ביטחון נמוך", "Low-confidence threshold")} value={config.validation?.low_confidence_threshold} min={0.3} max={0.95} step={0.05}
            path="validation.low_confidence_threshold" report={report}
            hint={t("מתחת לסף, הממצא אינו נחשב מאומת ועובר לבדיקה אנושית", "Below the threshold, a finding isn't considered verified and goes to human review")}
            onChange={(v) => edit((c) => ({ ...c, validation: { ...c.validation, low_confidence_threshold: v } }))} />
          <div className="adm-locked-row"><Lock reason={t("ממצא לא ודאי תמיד מועבר לבנקאי ולא לפנייה ללקוח", "An uncertain finding always goes to the banker, never to a customer contact")} />
            {t(<span className="small">ממצא לא ודאי: <b>העברה לבדיקה אנושית</b> (נעול)</span>,
              <span className="small">Uncertain finding: <b>handed to human review</b> (locked)</span>)}</div>
        </div>
      </div>
    </div>
  );
}

function Purposes({ config, edit, report, canon }: {
  config: Json; edit: KindProps["edit"]; report: KindProps["work"]["report"]; canon?: NonNullable<Settings["canonical_en"]>["purposes"];
}) {
  const { en, t } = useLang();
  const purposes: Record<string, Json> = config.product?.purposes || {};
  const [key, setKey] = useState("");
  const setPurposes = (next: Record<string, Json>) => edit((c) => ({ ...c, product: { ...c.product, purposes: next } }));
  const valid = /^[a-z][a-z_]{1,30}$/.test(key) && !purposes[key];
  return (
    <div className="panel">
      <h3>{t("מטרות ההלוואה והאסמכתה לכל מטרה", "Loan purposes and the proof for each")}</h3>
      <FieldErrors report={report} path="product" />
      <table className="t">
        <thead><tr><th>{t("מזהה", "ID")}</th><th>{t("שם המטרה", "Purpose name (Hebrew)")}</th><th>{t("אסמכתה נדרשת", "Required proof (Hebrew)")}</th><th /></tr></thead>
        <tbody>{Object.entries(purposes).map(([k, p]) => (
          <tr key={k}>
            <td className="ltr tiny">{k}</td>
            <td><input className="adm-cell" value={p.label_he} maxLength={60} {...(en ? { dir: "auto", lang: "he" } : {})}
              onChange={(e) => setPurposes({ ...purposes, [k]: { ...p, label_he: e.target.value } })} />
              {en && canon?.[k] && <div className="tiny muted adm-en-hint">{canon[k].label}</div>}</td>
            <td><input className="adm-cell" value={p.proof_he} maxLength={120} {...(en ? { dir: "auto", lang: "he" } : {})}
              onChange={(e) => setPurposes({ ...purposes, [k]: { ...p, proof_he: e.target.value } })} />
              {en && canon?.[k] && <div className="tiny muted adm-en-hint">{canon[k].proof}</div>}</td>
            <td><button className="link small" disabled={Object.keys(purposes).length <= 1}
              onClick={() => { const { [k]: _, ...rest } = purposes; setPurposes(rest); }}>{t("הסרה", "Remove")}</button></td>
          </tr>
        ))}</tbody>
      </table>
      <div className="row" style={{ marginTop: 8 }}>
        <input className="adm-cell ltr" placeholder="new_purpose" value={key} onChange={(e) => setKey(e.target.value.trim())} aria-label={t("מזהה מטרה חדשה", "New purpose ID")} />
        <button className="btn btn-ghost btn-sm" disabled={!valid}
          onClick={() => { setPurposes({ ...purposes, [key]: { label_he: "מטרה חדשה", proof_he: "אסמכתה למטרה" } }); setKey(""); }}>{t("הוספת מטרה", "Add purpose")}</button>
      </div>
    </div>
  );
}
