import type { Settings } from "../../adminApi";
import { useLang } from "../../i18n";
import type { KindProps } from "./AdminPage";
import { FieldErrors, LintList, Lock, Preview, VarText } from "./ui";

const TEMPLATE_HE: Record<string, [string, string]> = {
  in_app_correction: ["הודעת תיקון באפליקציה", "מוצגת ללקוח כשמסמך דורש תיקון"],
  link_message: ["הודעה עם קישור להעלאה", "נשלחת אחרי שיחה, עם קישור מאובטח"],
  reminder: ["תזכורת", "תזכורת עדינה כשהבקשה ממתינה"],
  completed: ["הבקשה הושלמה", "כשכל המסמכים התקבלו ונבדקו"],
};
const TEMPLATE_EN: Record<string, [string, string]> = {
  in_app_correction: ["In-app correction message", "shown to the customer when a document needs a correction"],
  link_message: ["Message with an upload link", "sent after a call, with a secure link"],
  reminder: ["Reminder", "a gentle reminder while the application is waiting"],
  completed: ["Application completed", "when every document has been received and reviewed"],
};

export function PromptTab({ prompt, policy, settings }: { prompt: KindProps; policy: KindProps; settings: Settings }) {
  const { en, t } = useLang();
  const TEMPLATES = en ? TEMPLATE_EN : TEMPLATE_HE;
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
          <h3>{t("הנחיות לסוכנת השיחה", "Instructions for the call agent")}</h3>
          <div className="adm-label"><Lock reason={t("גילוי שמדובר בסוכנת בינה מלאכותית הוא דרישת חובה", "Disclosing that the caller is an AI agent is mandatory")} /> {t("פתיח השיחה (נעול)", "Call opening (locked)")}</div>
          <div className="adm-locked-text" data-testid="opening-locked" {...(en ? { dir: "auto", lang: "he" } : {})}>{p.opening_locked}</div>
          <FieldErrors report={prompt.work.report} path="opening_locked" />
          <LintList lint={lint} path="opening_locked" />
          <div className="adm-label" style={{ marginTop: 12 }}>{t("הנחיות", "Instructions")}</div>
          <VarText value={p.instructions || ""} rows={8} maxLength={4000} variables={allowed} testId="prompt-instructions"
            onChange={(v) => prompt.edit((c) => ({ ...c, instructions: v }))} />
          <FieldErrors report={prompt.work.report} path="" />
          <FieldErrors report={prompt.work.report} path="instructions" />
          <LintList lint={lint} path="instructions" />
          <div className="tiny muted" style={{ marginTop: 6 }}>
            {t("ההנחיות קובעות איך הסוכנת מדברת, לא מתי פונים. מועד הפנייה, הערוצים והמכסות נקבעים רק בלשונית ״מעקב והשלמה״.",
              "The instructions set how the agent speaks, not when to contact. Contact timing, channels and limits are set only in the “Follow-up & completion” tab.")}
          </div>
          {en && <div className="tiny muted adm-en-hint">The agent speaks Hebrew with the customer, so the opening, the instructions and the templates are edited in Hebrew.</div>}
        </div>
        <div className="panel">
          <h3>{t("תצוגה מקדימה", "Preview")}</h3>
          <Preview text={p.opening_locked || ""} vars={settings.preview_variables} label={t("פתיח", "Opening")} />
          <Preview text={p.instructions || ""} vars={settings.preview_variables} label={t("הנחיות", "Instructions")} />
          <div className="tiny muted" style={{ margin: "8px 0" }}>
            {en ? <>Values: {Object.entries(settings.preview_variables).map(([k, v], i) => <span key={k}>{i > 0 && " · "}{k} = <bdi lang="he" dir="auto">{Array.isArray(v) ? v.join(", ") : v}</bdi></span>)}</>
              : <>{t("ערכים", "Values")}: {Object.entries(settings.preview_variables).map(([k, v]) => `${k} = ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ")}</>}
          </div>
          <button className="btn btn-ghost btn-sm" disabled title={t("שיחת בדיקה עם הסוכנת תתאפשר בשלב מאוחר יותר", "A test call with the agent will be available at a later stage")}>{t("שיחת בדיקה (בקרוב)", "Test call (coming soon)")}</button>
        </div>
      </div>

      <div className="adm-section-gap" />
      {policy.bar}
      <div className="panel">
        <h3>{t("תבניות הודעה ללקוח", "Customer message templates")}</h3>
        <div className="adm-templates">
          {Object.entries(templates).map(([name, text]) => (
            <div key={name} className="adm-template" data-testid={`template-${name}`}>
              <div className="adm-label">{TEMPLATES[name]?.[0] || name} <span className="tiny muted">· {TEMPLATES[name]?.[1]}</span></div>
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
        <h3>{t("הודעות ללקוח לפי סוג ממצא", "Customer messages by finding type")}</h3>
        <div className="small muted" style={{ marginBottom: 8 }}>{t("מחליפות את הנוסח הקבוע כשה-AI מוצא בעיה מהסוג הזה.", "They replace the standard wording when the AI finds an issue of this type.")}</div>
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
