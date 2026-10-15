import type { Settings } from "../../adminApi";
import type { KindProps } from "./AdminPage";
import { FieldErrors, LintList, Lock, Preview, VarText } from "./ui";

const TEMPLATE_HE: Record<string, [string, string]> = {
  in_app_correction: ["הודעת תיקון באפליקציה", "מוצגת ללקוח כשמסמך דורש תיקון"],
  link_message: ["הודעה עם קישור להעלאה", "נשלחת אחרי שיחה, עם קישור מאובטח"],
  reminder: ["תזכורת", "תזכורת עדינה כשהבקשה ממתינה"],
  completed: ["הבקשה הושלמה", "כשכל המסמכים התקבלו ונבדקו"],
};

export function PromptTab({ prompt, policy, settings }: { prompt: KindProps; policy: KindProps; settings: Settings }) {
  const p = prompt.work.config;
  const vars = settings.prompt_variables;
  const allowed: string[] = p.allowed_variables || vars;
  const lint = prompt.work.report?.lint || [];
  const templates: Record<string, string> = policy.work.config.templates || {};
  const messages: Record<string, string> = policy.work.config.customer_messages || {};
  const policyLint = policy.work.report?.lint || [];
  return (
    <div className="adm-tab" data-testid="tab-body-prompt">
      {prompt.bar}
      <div className="adm-grid">
        <div className="panel">
          <h3>הנחיות לסוכנת השיחה</h3>
          <div className="adm-label"><Lock reason="גילוי שמדובר בסוכנת בינה מלאכותית הוא דרישת חובה" /> פתיח השיחה (נעול)</div>
          <div className="adm-locked-text" data-testid="opening-locked">{p.opening_locked}</div>
          <FieldErrors report={prompt.work.report} path="opening_locked" />
          <LintList lint={lint} path="opening_locked" />
          <div className="adm-label" style={{ marginTop: 12 }}>הנחיות</div>
          <VarText value={p.instructions || ""} rows={8} maxLength={4000} variables={allowed} testId="prompt-instructions"
            onChange={(v) => prompt.edit((c) => ({ ...c, instructions: v }))} />
          <FieldErrors report={prompt.work.report} path="" />
          <FieldErrors report={prompt.work.report} path="instructions" />
          <LintList lint={lint} path="instructions" />
          <div className="tiny muted" style={{ marginTop: 6 }}>
            ההנחיות קובעות איך הסוכנת מדברת, לא מתי פונים. מועד הפנייה, הערוצים והמכסות נקבעים רק בלשונית ״מעקב והשלמה״.
          </div>
        </div>
        <div className="panel">
          <h3>תצוגה מקדימה</h3>
          <Preview text={p.opening_locked || ""} vars={settings.preview_variables} label="פתיח" />
          <Preview text={p.instructions || ""} vars={settings.preview_variables} label="הנחיות" />
          <div className="tiny muted" style={{ margin: "8px 0" }}>
            ערכים: {Object.entries(settings.preview_variables).map(([k, v]) => `${k} = ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ")}
          </div>
          <button className="btn btn-ghost btn-sm" disabled title="שיחת בדיקה עם הסוכנת תתאפשר בשלב מאוחר יותר">שיחת בדיקה (בקרוב)</button>
        </div>
      </div>

      <div className="adm-section-gap" />
      {policy.bar}
      <div className="panel">
        <h3>תבניות הודעה ללקוח</h3>
        <div className="adm-templates">
          {Object.entries(templates).map(([name, text]) => (
            <div key={name} className="adm-template" data-testid={`template-${name}`}>
              <div className="adm-label">{TEMPLATE_HE[name]?.[0] || name} <span className="tiny muted">· {TEMPLATE_HE[name]?.[1]}</span></div>
              <VarText value={text} maxLength={600} variables={vars} onChange={(v) => policy.edit((c) => ({ ...c, templates: { ...c.templates, [name]: v } }))} />
              <FieldErrors report={policy.work.report} path={`templates.${name}`} />
              <LintList lint={policyLint} path={`templates.${name}`} />
              <Preview text={text} vars={settings.preview_variables} />
            </div>
          ))}
        </div>
        <FieldErrors report={policy.work.report} path="" />
      </div>
      <div className="panel">
        <h3>הודעות ללקוח לפי סוג ממצא</h3>
        <div className="small muted" style={{ marginBottom: 8 }}>מחליפות את הנוסח הקבוע כשה-AI מוצא בעיה מהסוג הזה.</div>
        {Object.entries(messages).map(([code, text]) => (
          <div key={code} className="adm-template">
            <div className="adm-label ltr">{code}</div>
            <VarText value={text} rows={2} variables={vars} onChange={(v) => policy.edit((c) => ({ ...c, customer_messages: { ...c.customer_messages, [code]: v } }))} />
            <LintList lint={policyLint} path={`customer_messages.${code}`} />
          </div>
        ))}
      </div>
    </div>
  );
}
