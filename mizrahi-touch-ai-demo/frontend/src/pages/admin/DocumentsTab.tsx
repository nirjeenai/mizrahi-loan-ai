import { useState } from "react";
import type { Json, Settings } from "../../adminApi";
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
// families without a review rubric (backend/rubrics): uploads are stored for the banker
const AI_FAMILIES = ["id_document", "payslip", "bank_statement", "purpose_proof", "tax_form"];
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
      <div className="notice navy small" style={{ marginBottom: 12 }}>
        הדרישות כאן קובעות מה הלקוח מתבקש להעלות ומה ה-AI בודק. תיק פתוח ננעל על גרסת הדרישות שהייתה פעילה כשנפתח, כך ששינוי חל על תיקים חדשים
        (או על תיק שהבנקאי עדכן במפורש).
      </div>
      <div className="panel">
        <h3>מסמכים נדרשים</h3>
        <FieldErrors report={report} path="document_requirements" />
        <div className="adm-reqs">
          {ids.map((id) => {
            const r = reqs.find((x) => x.id === id);
            const source = r || catalog.find((x) => x.id === id)!;
            const path = `document_requirements.${r ? reqs.indexOf(r) : -1}`;
            return (
              <div key={id} className={`adm-req${r ? "" : " off"}`} data-testid={`req-${id}`}>
                <div className="adm-req-head">
                  <Toggle label={<>{FAMILY_HE[source.family] || source.family} <span className="tiny muted ltr">{id}</span></>}
                    checked={!!r} onChange={(on) => include(id, on)} testId={`req-include-${id}`} />
                  <span className="row" style={{ gap: 4 }}>
                    <Chip>{PER_HE[source.per]}</Chip>
                    {source.condition?.employment && <Chip tone="info">רק ל{source.condition.employment.map((e: string) => EMPLOYMENT_HE[e] || e).join(" / ")}</Chip>}
                    {source.condition?.registration && <Chip tone="info">{source.condition.registration.map((e: string) => REGISTRATION_HE[e] || e).join(" / ")}</Chip>}
                    {source.condition?.entity && <Chip tone="info">{source.condition.entity.map((e: string) => ENTITY_HE[e] || e).join(" / ")}</Chip>}
                    {!AI_FAMILIES.includes(source.family) && <Chip>בדיקת בנקאי · ללא AI</Chip>}
                    {r && <Chip tone={r.required ? "navy" : "neutral"}>{r.required ? "חובה" : "רשות"}</Chip>}
                  </span>
                </div>
                {r && (
                  <div className="adm-req-body">
                    <label className="adm-field wide"><span className="adm-label">שם הדרישה ללקוח</span>
                      <input value={r.label_he} maxLength={80} onChange={(e) => updateReq(id, (x) => ({ ...x, label_he: e.target.value }))} />
                      {r.label_he.includes("{months}") && <span className="tiny muted">{"{months}"} יוחלף במספר החודשים</span>}
                    </label>
                    <label className="adm-field wide"><span className="adm-label">הסבר קצר</span>
                      <input value={r.hint_he || ""} maxLength={300} onChange={(e) => updateReq(id, (x) => ({ ...x, hint_he: e.target.value }))} />
                    </label>
                    <label className="adm-field wide"><span className="adm-label">למה המסמך נדרש</span>
                      <input value={r.why_he || ""} maxLength={300} onChange={(e) => updateReq(id, (x) => ({ ...x, why_he: e.target.value }))}
                        data-testid={`req-why-${id}`} />
                    </label>
                    <label className="adm-field wide"><span className="adm-label">מסמכים חלופיים מקובלים (מופרדים ב־״;״)</span>
                      <input value={(r.alternatives_he || []).join("; ")} maxLength={700}
                        onChange={(e) => updateReq(id, (x) => ({ ...x, alternatives_he: e.target.value ? e.target.value.split(";").map((s) => s.trimStart()) : [] }))}
                        data-testid={`req-alternatives-${id}`} />
                    </label>
                    <Toggle label="מסמך חובה" checked={!!r.required} onChange={(v) => updateReq(id, (x) => ({ ...x, required: v }))}
                      hint="מסמך רשות מוצג ללקוח אך אינו מעכב את השלמת הבקשה" />
                    {(RULE_FIELDS[r.family] || []).map((f) => f.bool ? (
                      <Toggle key={f.key} label={f.label} checked={!!r.rules?.[f.key]}
                        onChange={(v) => updateReq(id, (x) => ({ ...x, rules: { ...x.rules, [f.key]: v } }))} />
                    ) : (
                      <NumberField key={f.key} label={f.label} value={r.rules?.[f.key]} min={f.min!} max={f.max!} unit={f.unit}
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
        <Purposes config={config} edit={edit} report={report} />
        <div className="panel">
          <h3>בדיקת המסמכים</h3>
          <NumberField label="סף ביטחון נמוך" value={config.validation?.low_confidence_threshold} min={0.3} max={0.95} step={0.05}
            path="validation.low_confidence_threshold" report={report}
            hint="מתחת לסף, הממצא אינו נחשב מאומת ועובר לבדיקה אנושית"
            onChange={(v) => edit((c) => ({ ...c, validation: { ...c.validation, low_confidence_threshold: v } }))} />
          <div className="adm-locked-row"><Lock reason="ממצא לא ודאי תמיד מועבר לבנקאי ולא לפנייה ללקוח" />
            <span className="small">ממצא לא ודאי: <b>העברה לבדיקה אנושית</b> (נעול)</span></div>
        </div>
      </div>
    </div>
  );
}

function Purposes({ config, edit, report }: { config: Json; edit: KindProps["edit"]; report: KindProps["work"]["report"] }) {
  const purposes: Record<string, Json> = config.product?.purposes || {};
  const [key, setKey] = useState("");
  const setPurposes = (next: Record<string, Json>) => edit((c) => ({ ...c, product: { ...c.product, purposes: next } }));
  const valid = /^[a-z][a-z_]{1,30}$/.test(key) && !purposes[key];
  return (
    <div className="panel">
      <h3>מטרות ההלוואה והאסמכתה לכל מטרה</h3>
      <FieldErrors report={report} path="product" />
      <table className="t">
        <thead><tr><th>מזהה</th><th>שם המטרה</th><th>אסמכתה נדרשת</th><th /></tr></thead>
        <tbody>{Object.entries(purposes).map(([k, p]) => (
          <tr key={k}>
            <td className="ltr tiny">{k}</td>
            <td><input className="adm-cell" value={p.label_he} maxLength={60}
              onChange={(e) => setPurposes({ ...purposes, [k]: { ...p, label_he: e.target.value } })} /></td>
            <td><input className="adm-cell" value={p.proof_he} maxLength={120}
              onChange={(e) => setPurposes({ ...purposes, [k]: { ...p, proof_he: e.target.value } })} /></td>
            <td><button className="link small" disabled={Object.keys(purposes).length <= 1}
              onClick={() => { const { [k]: _, ...rest } = purposes; setPurposes(rest); }}>הסרה</button></td>
          </tr>
        ))}</tbody>
      </table>
      <div className="row" style={{ marginTop: 8 }}>
        <input className="adm-cell ltr" placeholder="new_purpose" value={key} onChange={(e) => setKey(e.target.value.trim())} aria-label="מזהה מטרה חדשה" />
        <button className="btn btn-ghost btn-sm" disabled={!valid}
          onClick={() => { setPurposes({ ...purposes, [key]: { label_he: "מטרה חדשה", proof_he: "אסמכתה למטרה" } }); setKey(""); }}>הוספת מטרה</button>
      </div>
    </div>
  );
}
