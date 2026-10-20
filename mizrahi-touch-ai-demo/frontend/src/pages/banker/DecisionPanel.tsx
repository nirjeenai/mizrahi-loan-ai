import { useState, type ReactNode } from "react";
import { api, monthHe, monthL, type CaseFindingItem, type Decision, type DeskFinding, type DeskRequest, type DeskResult, type DocItem,
  type Draft, type MissingItem, type QueueItem, type Workspace } from "../../api";
import { Loc, loc, locList, locOf, Orig, tr, useLang } from "../../i18n";
import { BANKER_TONE, Chip, Expand, newRequestId, VERDICT_TONE, When } from "./deskUi";
import type { Focus } from "./ReviewWorkspace";

interface PanelProps {
  item: QueueItem; ws: Workspace; staff: string; readOnly: boolean; focus?: Focus | null;
  onDone: (text: string) => void; onError: (text: string) => void; onNext: () => void; hasNext: boolean; showEvidence: (f: Focus) => void;
  /** the case desk shows a missing item on its own, without an evidence pane: the panel then carries the related files */
  solo?: boolean;
}
type Submit = (requestId: string) => Promise<DeskResult>;
const STATUS_WORD: Record<string, string> = {
  AWAITING_DECISION: "ממתין להחלטה", AWAITING_CUSTOMER_FIX: "תיקון אצל הלקוח", ACCEPTED: "התקבל", CORRECTION_REQUESTED: "הוחזר לתיקון",
  ESCALATED: "בבירור", FAILED: "עיבוד נכשל", REPLACED: "הוחלף", MISSING: "חסר", REQUESTED: "נשלחה בקשה", open: "פתוח", resolved: "נסגר",
  dismissed: "סומן כשגוי", superseded: "נסגר", PREPARATION_CONFIRMED: "הכנה אושרה",
};
const STATUS_WORD_EN: Record<string, string> = {
  AWAITING_DECISION: "Awaiting decision", AWAITING_CUSTOMER_FIX: "Correction with the customer", ACCEPTED: "Accepted", CORRECTION_REQUESTED: "Returned for correction",
  ESCALATED: "Escalated", FAILED: "Processing failed", REPLACED: "Replaced", MISSING: "Missing", REQUESTED: "Request sent", open: "Open", resolved: "Closed",
  dismissed: "Marked as an error", superseded: "Closed", PREPARATION_CONFIRMED: "Preparation confirmed",
};
const NOT_SENT = "הבקשה נשמרה ומוצגת ללקוח באפליקציה. לא נשלחה הודעת SMS, דוא״ל או התראה.";
const NOT_SENT_EN = "The request was saved and is shown to the customer in the app. No SMS, email or notification was sent.";
const notSent = () => tr(NOT_SENT, NOT_SENT_EN);
/** dir="auto" for a field that holds Hebrew source text, in English only (Hebrew keeps the page's own direction) */
const autoDir = (en: boolean) => (en ? { dir: "auto" as const } : {});

export function DecisionPanel(props: PanelProps) {
  const { t } = useLang();
  const [done, setDone] = useState<string | null>(null);
  const finish = (result: DeskResult, text: string) => {
    const msg = result.duplicate ? tr("ההחלטה כבר נרשמה קודם, לא נוצרה רשומה כפולה.", "The decision was already recorded earlier; no duplicate record was created.") : text;
    setDone(msg);
    props.onDone(msg);
  };
  const ctx = { ...props, finish };
  return (
    <div className="dp">
      {done && (
        <div className="dp-success" role="status" data-testid="decision-success">
          <span>✓ {done}</span>
          {props.hasNext && <button className="btn btn-dark btn-sm" onClick={props.onNext} data-testid="next-item">{t("לפריט הבא", "Next item")}</button>}
        </div>
      )}
      {props.item.kind === "document" ? <DocumentPanel {...ctx} item={props.item} />
        : props.item.kind === "missing" ? <MissingPanel {...ctx} item={props.item} /> : <CaseFindingPanel {...ctx} item={props.item} />}
    </div>
  );
}

type Ctx<T> = Omit<PanelProps, "item"> & { item: T; finish: (r: DeskResult, text: string) => void };

// ---------------------------------------------------------------- document
type DocAction = "accept" | "request_correction" | "escalate";
const DOC_ACTIONS: { key: DocAction; label: string; labelEn: string; testId: string }[] = [
  { key: "accept", label: "קבלת המסמך", labelEn: "Accept document", testId: "action-accept" },
  { key: "request_correction", label: "החזרה לתיקון", labelEn: "Return for correction", testId: "action-correction" },
  { key: "escalate", label: "העברה לבירור", labelEn: "Escalate for review", testId: "action-escalate" },
];
const DECIDED = ["ACCEPTED", "CORRECTION_REQUESTED", "ESCALATED", "REPLACED"];

/** The one decision the panel leads with: a fix when the document is wrong for the request, otherwise acceptance.
 *  The other allowed decisions stay one click away. */
function primaryDocAction(item: DocItem): DocAction | null {
  const allowed = item.banker.allowed_actions;
  if (!allowed.length) return null;
  const needsFix = (item.claimed_period && item.period && item.claimed_period !== item.period) || item.ai.verdict === "INVALID"
    || ["AWAITING_CUSTOMER_FIX", "FAILED"].includes(item.banker.status);
  const want: DocAction = needsFix ? "request_correction" : "accept";
  return allowed.includes(want) ? want : allowed[0];
}

function DocumentPanel({ item, ws, staff, readOnly, finish, showEvidence }: Ctx<DocItem>) {
  const { en, t } = useLang();
  const [mode, setMode] = useState<DocAction | null>(null);
  const b = item.banker;
  const can = (a: DocAction) => b.allowed_actions.includes(a) && !readOnly;
  const borrower = ws.case.borrowers.find((x) => x.borrower_id === item.borrower_id);
  const payslip = (item.family || "payslip") === "payslip";
  const periods = payslip ? ws.borrowers.find((x) => x.borrower_id === item.borrower_id)?.months.map((m) => m.period) || [] : undefined;
  const run = (action: DocAction, body: Record<string, unknown>): Submit => (rid) =>
    api.decideDocument(ws.case_id, item.document_id, { action, request_id: rid, ...body });
  const primary = primaryDocAction(item);
  const tone = item.attention ? "warn" : item.ai.verdict === "VALID" ? "ok" : "neutral";
  const toggle = (a: DocAction) => setMode(mode === a ? null : a);
  const context = item.findings.length > 0 || item.ai.criteria_failed.length + item.ai.criteria_uncertain.length + item.ai.criteria_passed.length > 0
    || item.requests.length > 0;
  return (<>
    <section className="dp-sec dp-summary z-ai" data-testid="ai-summary">
      <div className="dp-head"><span className="dp-eyebrow">{t("סיכום בדיקת AI", "AI review summary")}</span><img className="jeen-logo-inline" src="/brand/jeen-logo.svg" alt="Jeen" /></div>
      <div className={`dp-callout ${tone}`} data-testid="attention">
        {item.ai.attention_he.map((t, i) => <p key={i} className={i === 0 ? "lead" : ""}>{en
          ? <Loc he={t} en={(item.ai as { attention_en?: (string | null)[] }).attention_en?.[i]} /> : t}</p>)}
      </div>
      <div className="dp-facts">
        <div className="dp-fact"><span className="dp-fact-label">{t("בדיקת AI", "AI check")}</span>
          <span className={`status-dot ${VERDICT_TONE[item.ai.verdict || ""] || "neutral"}`} data-testid="ai-verdict">{locOf(item.ai, "verdict_he")}</span></div>
        <div className="dp-fact"><span className="dp-fact-label">{t("החלטת הבנקאי", "Banker's decision")}</span>
          <span className={`status-dot ${BANKER_TONE[b.status]}`} data-testid="banker-status">{locOf(b, "status_he")}</span></div>
      </div>
      {item.ai.security_flags.length > 0 && <div className="notice small">{t("טקסט חשוד שזוהה במסמך (לא בוצע):", "Suspicious text found in the document (not acted on):")} <Orig text={item.ai.security_flags[0]} /></div>}
    </section>
    <DocumentStatus item={item} />
    {b.allowed_actions.length > 0 && (
      <section className="dp-sec dp-decide z-act" data-testid="decision-actions">
        <div className="dp-eyebrow">{t("ההחלטה שלך על המסמך", "Your decision on the document")}</div>
        {primary && (() => {
          const a = DOC_ACTIONS.find((x) => x.key === primary)!;
          return <button className={`act-primary${mode === a.key ? " on" : ""}`} disabled={!can(a.key)} onClick={() => toggle(a.key)} data-testid={a.testId}>{en ? a.labelEn : a.label}</button>;
        })()}
        <div className="act-secondary-row">
          {DOC_ACTIONS.filter((a) => a.key !== primary).map((a) => (
            <button key={a.key} className={`act-secondary${mode === a.key ? " on" : ""}`} disabled={!can(a.key)} onClick={() => toggle(a.key)}
              data-testid={a.testId}>{en ? a.labelEn : a.label}</button>
          ))}
        </div>
        {b.blocked_accept_he && <div className="tiny muted">{locOf(b, "blocked_accept_he")}</div>}
        {mode === "accept" && <AcceptForm item={item} onCancel={() => setMode(null)}
          submit={(rationale) => run("accept", { rationale, acknowledged_finding_ids: b.acknowledge_finding_ids })}
          onDone={(r) => finish(r, tr("המסמך התקבל לשלב בדיקת המסמכים. זו אינה החלטת אשראי ואינה משנה את שלב הבקשה בבנק.",
            "The document was accepted for the document review stage. This is not a credit decision and doesn't change the application's stage at the bank."))} />}
        {mode === "request_correction" && <CustomerRequestForm from={ws.case.banker.name_he} draft={item.draft} periods={periods} onCancel={() => setMode(null)}
          title={(p) => p ? `נדרש תלוש ${monthHe(p)}, ${borrower?.first_name_he || ""}`
            : `נדרש ${payslip ? "תלוש" : item.doc_type_he} מתוקן במקום ${item.filename}${borrower ? `, ${borrower.first_name_he}` : ""}`}
          submitLabel={t("שמירה והצגה ללקוח באפליקציה", "Save and show to the customer in the app")} testId="correction-form"
          submit={(message, period, rationale) => run("request_correction", { customer_message: message, requested_period: period || null, rationale })}
          onDone={(r) => finish(r, notSent())} />}
        {mode === "escalate" && <RationaleForm label={t("מה דורש בירור?", "What needs review?")} submitLabel={t("העברה לבירור", "Escalate for review")} required testId="escalate-form"
          note={t("המסמך יישאר אצלך בקבוצת ״בבירור״. הלקוח אינו מקבל בקשה.", "The document stays with you in the “Escalated” group. The customer receives no request.")}
          submit={(rationale) => run("escalate", { rationale })} onCancel={() => setMode(null)}
          onDone={(r) => finish(r, tr("המסמך הועבר לבירור.", "The document was escalated for review."))} />}
        {!mode && can("accept") && <BulkAccept item={item} ws={ws} finish={finish} />}
      </section>
    )}
    {context && <div className="dp-divider">{t("פירוט הבדיקה", "Review details")}</div>}
    <FindingsList findings={item.findings} ws={ws} readOnly={readOnly} finish={finish} showEvidence={showEvidence} />
    <Criteria item={item} />
    {/* a correction request still open can be withdrawn here; the document then returns to the banker's decision */}
    {item.requests.filter((r) => r.status === "OPEN").map((r) => (
      <OpenRequest key={r.customer_request_id} r={r} ws={ws} staff={staff} readOnly={readOnly} finish={finish} />))}
    <RequestsList requests={item.requests.filter((r) => r.status !== "OPEN")} />
    <div className="dp-footer">
      {item.history.length > 0 && <Expand label={en ? `Decision history (${item.history.length})` : `היסטוריית החלטות (${item.history.length})`} defaultOpen={DECIDED.includes(b.status)}>
        <HistoryList entries={item.history} bare /></Expand>}
      {!readOnly && <NoteForm submit={(text) => (rid) => api.addNote(ws.case_id, { text, document_id: item.document_id, request_id: rid })} finish={finish} />}
      <Expand label={t("פרטים טכניים (רובריקה, מודל, הרצה)", "Technical details (rubric, model, run)")} testId="technical-details">
        <TechList rows={[[t("רובריקה", "Rubric"), item.ai.technical.rubric], [t("מזהה הרצה", "Run ID"), item.ai.technical.run_id], [t("ספק בדיקה", "Review provider"), item.ai.technical.provider],
          [t("מודלים", "Models"), item.ai.technical.models ? Object.entries(item.ai.technical.models).map(([k, v]) => `${k}: ${v}`).join(" · ") : null],
          [t("גרסת פרומפט", "Prompt version"), item.ai.technical.prompt_version], [t("הסתיים", "Finished"), item.ai.technical.finished_at],
          [t("קודי סיבה", "Reason codes"), (item.ai.technical.verdict_reason_codes || []).join(", ") || "-"], ["SHA-256", item.ai.technical.sha256],
          [t("שגיאה", "Error"), item.ai.technical.error]]} />
        {[...item.ai.criteria_failed, ...item.ai.criteria_uncertain, ...item.ai.criteria_passed, ...item.ai.criteria_na].map((c) => (
          <div key={c.criterion_id} className="tiny ltr-row"><span className="ltr">{c.criterion_id} · {c.outcome} · {c.decided_by}{c.reason_code ? ` · ${c.reason_code}` : ""}</span> — {locOf(c, "title_he")}</div>
        ))}
        {item.ai.summary_he && <div className="tiny muted" style={{ marginTop: 6 }}>{t("סיכום המודל:", "Model summary:")} <Orig text={item.ai.summary_he} /></div>}
        {item.ai.limitations_he.map((l, i) => <div key={i} className="tiny muted">• {en ? <Loc he={l} en={(item.ai as { limitations_en?: (string | null)[] }).limitations_en?.[i]} /> : l}</div>)}
        {item.ai.uncertainty_he.map((l, i) => <div key={`u${i}`} className="tiny muted">? <Orig text={l} /></div>)}
      </Expand>
    </div>
  </>);
}

/** Documents that wait for the same decision for the same reason: all clean, or all carrying the same AI finding(s). */
function signature(d: DocItem): string | null {
  if (d.group !== "decide" || !d.banker.allowed_actions.includes("accept")) return null;
  if (d.claimed_period && d.period && d.claimed_period !== d.period) return null;
  if (d.findings.some((f) => f.status === "open" && f.review_state === "CUSTOMER_ACTION_REQUIRED")) return null;
  const codes = d.findings.filter((f) => f.status === "open" && f.review_state === "NEEDS_BANKER_REVIEW").map((f) => f.code).sort();
  if (!codes.length) return d.ai.verdict === "VALID" ? "clean" : null;
  return codes.join("+");
}

function BulkAccept({ item, ws, finish }: { item: DocItem; ws: Workspace; finish: (r: DeskResult, t: string) => void }) {
  const sig = signature(item);
  const peers = sig ? ws.items.filter((i): i is DocItem => i.kind === "document" && signature(i) === sig) : [];
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(() => new Set(peers.map((p) => p.document_id)));
  const [rationale, setRationale] = useState("");
  const [ids] = useState(() => Object.fromEntries(peers.map((p) => [p.document_id, newRequestId()])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { en, t } = useLang();
  if (peers.length < 2) return null;
  const clean = sig === "clean";
  const shared = peers[0].findings.find((f) => f.status === "open" && f.review_state === "NEEDS_BANKER_REVIEW");
  const reason = clean ? t("בדיקת ה-AI תקינה וללא ממצאים", "The AI check is valid, with no findings") : shared ? locOf(shared, "title_he") : undefined;
  const go = async () => {
    setBusy(true); setError(null);
    const chosen = peers.filter((p) => picked.has(p.document_id));
    const failed: string[] = [];
    let last: DeskResult | null = null;
    for (const p of chosen) {
      try {
        last = await api.decideDocument(ws.case_id, p.document_id, { action: "accept", rationale: rationale.trim(),
          acknowledged_finding_ids: p.banker.acknowledge_finding_ids, request_id: ids[p.document_id] });
      } catch (e) { failed.push(`${p.filename}: ${(e as Error).message}`); }
    }
    setBusy(false);
    if (failed.length) setError(failed.join(" · "));
    if (last) finish({ ...last, duplicate: false }, tr(`${chosen.length - failed.length} מסמכים התקבלו לשלב בדיקת המסמכים, כל אחד כהחלטה נפרדת ביומן.`,
      `${chosen.length - failed.length} documents were accepted for the document review stage, each as a separate decision in the log.`));
  };
  return (
    <div className="bulk" data-testid="bulk-accept">
      {!open ? <button className="link tiny subtle" onClick={() => setOpen(true)} data-testid="bulk-open" title={reason}>
        {en ? <>Bulk acceptance · {peers.length} documents in the same state</> : <>קבלה מרוכזת · {peers.length} מסמכים באותו מצב</>}</button> : (
        <div className="dp-form">
          <div className="small bold">{t("קבלה מרוכזת", "Bulk acceptance")} · {reason}</div>
          {peers.map((p) => (
            <label key={p.document_id} className="bulk-row">
              <input type="checkbox" checked={picked.has(p.document_id)} onChange={(e) => {
                const next = new Set(picked); if (e.target.checked) next.add(p.document_id); else next.delete(p.document_id); setPicked(next);
              }} />
              <span>{locOf(p, "title_he")}</span><span className="ltr tiny muted">{p.filename}</span>
            </label>
          ))}
          <label className="dp-field">{t("נימוק פנימי", "Internal rationale")} {clean ? <span className="muted">{t("(רשות)", "(optional)")}</span> : <span className="warn-text">{t("(חובה, נרשם בכל אחד מהמסמכים)", "(required; recorded on each of the documents)")}</span>}
            <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="bulk-rationale" {...autoDir(en)} /></label>
          <div className="dp-disclaimer">{t("כל מסמך נרשם כהחלטה נפרדת עם הנימוק, הזהות והשעה. זו קבלה לשלב בדיקת המסמכים בלבד, אינה אישור הלוואה ואינה משנה את שלב הבקשה בבנק.",
            "Each document is recorded as a separate decision with the rationale, the identity and the time. This is acceptance for the document review stage only — not a loan approval, and it doesn't change the application's stage at the bank.")}</div>
          {error && <div className="dp-err" role="alert">{error}</div>}
          <div className="row"><button className="btn btn-dark btn-sm" disabled={busy || !picked.size || (!clean && !rationale.trim())} onClick={go}
            data-testid="bulk-submit">{busy && <span className="spinner" />}{en ? `Accept the ${picked.size} documents` : <>קבלת {picked.size} המסמכים</>}</button>
            <button className="btn btn-soft btn-sm" onClick={() => setOpen(false)}>{t("ביטול", "Cancel")}</button></div>
        </div>
      )}
    </div>
  );
}

function DocumentStatus({ item }: { item: DocItem }) {
  const d = item.banker.decision;
  const open = item.requests.find((r) => r.status === "OPEN" && r.document_id === item.document_id);
  const { en, t } = useLang();
  const actor = d ? loc(d.actor_name, (d as { actor_name_en?: string }).actor_name_en) : undefined;
  switch (item.banker.status) {
    case "ACCEPTED":
      return <div className="dp-state ok" data-testid="document-state">{t("התקבל על ידי", "Accepted by")} {actor} <When at={d?.created_at} />
        {d?.rationale && <div className="tiny muted">{t("נימוק פנימי:", "Internal rationale:")} <Orig text={d.rationale} /></div>}
        <div className="tiny muted">{t("בשלב בדיקת המסמכים בלבד, אינו אישור הלוואה.", "For the document review stage only — not a loan approval.")}</div></div>;
    case "CORRECTION_REQUESTED":
      return <div className="dp-state warn" data-testid="document-state">{t("הוחזר לתיקון · ממתין ללקוח", "Returned for correction · awaiting the customer")} <When at={d?.created_at} by={actor} />
        {open && <blockquote className="dp-quote"><Orig text={open.message_he} /></blockquote>}</div>;
    case "ESCALATED":
      return <div className="dp-state info" data-testid="document-state">{t("בבירור", "Escalated")} <When at={d?.created_at} by={actor} />
        {d?.rationale && <div className="tiny"><Orig text={d.rationale} /></div>}</div>;
    case "REPLACED":
      return <div className="dp-state neutral" data-testid="document-state">{en ? <>The customer uploaded a replacement document: <span className="ltr">{item.replaced_by?.filename}</span>. The next decision is on the new document.</>
        : <>הלקוח העלה מסמך חלופי: <span className="ltr">{item.replaced_by?.filename}</span>. ההחלטה הבאה היא על המסמך החדש.</>}</div>;
    case "AWAITING_CUSTOMER_FIX":
      return <div className="dp-state warn" data-testid="document-state">{t("בדיקת ה-AI מצאה בעיה שהלקוח מתבקש לתקן, והלקוח רואה אותה באפליקציה. אפשר להוסיף בקשה אישית או להעביר לבירור.",
        "The AI check found an issue the customer is asked to fix, and the customer sees it in the app. You can add a personal request or escalate for review.")}</div>;
    case "PROCESSING":
      return <div className="dp-state neutral" data-testid="document-state"><span className="spinner" /> {t("ה-AI עדיין בודק את המסמך. אין מה להחליט עדיין.", "The AI is still checking the document. There's nothing to decide yet.")}</div>;
    case "FAILED":
      return <div className="dp-state bad" data-testid="document-state">{t("עיבוד ה-AI נכשל. אפשר לבקש מהלקוח להעלות את הקובץ שוב.", "AI processing failed. You can ask the customer to upload the file again.")}</div>;
    default:
      return null;
  }
}

/** a criterion's explanation: English when the code wrote it, otherwise the reviewer's own wording as the original */
function Explanation({ c }: { c: { explanation_he: string; explanation_en?: string } }) {
  const { en } = useLang();
  return en && c.explanation_en ? <>{c.explanation_en}</> : <Orig text={c.explanation_he} />;
}

/** English only: what the suggested Hebrew draft says, read-only, while the banker hasn't changed it. The customer
 *  receives the Hebrew text in the field. */
function DraftPreview({ he, en: english, current }: { he: string; en?: string | null; current: string }) {
  const { en } = useLang();
  if (!en || !english || current !== he) return null;
  return <div className="tiny muted dp-draft-en" data-testid="draft-english">English preview of the draft (not sent): {english}</div>;
}

/** a finding's message: English when the whole message has it, otherwise the Hebrew (it may carry the reviewer's wording) */
function FindingMessage({ f }: { f: { message_he: string } }) {
  const { en } = useLang();
  const english = (f as { message_en?: string }).message_en;
  return en && english ? <>{english}</> : <Orig text={f.message_he} />;
}

function Criteria({ item }: { item: DocItem }) {
  const { en, t } = useLang();
  const bad = [...item.ai.criteria_failed, ...item.ai.criteria_uncertain];
  const passed = item.ai.criteria_passed;
  if (!bad.length && !passed.length) return null;
  return (
    <section className="dp-sec">
      <div className="dp-label">{t("קריטריוני הבדיקה", "Review criteria")}</div>
      {bad.map((c) => (
        <div key={c.criterion_id} className={`crit2 ${c.outcome}`}><span className="crit2-mark" aria-hidden>{c.outcome === "FAIL" ? "✕" : "?"}</span>
          <div><div className="small bold">{locOf(c, "title_he")}</div><div className="tiny muted"><Explanation c={c} /></div></div></div>
      ))}
      {passed.length > 0 && (
        <Expand label={en ? `${passed.length} criteria passed${item.ai.criteria_na.length ? ` · ${item.ai.criteria_na.length} not applicable` : ""}`
          : `${passed.length} קריטריונים עברו${item.ai.criteria_na.length ? ` · ${item.ai.criteria_na.length} לא רלוונטיים` : ""}`}>
          {passed.map((c) => <div key={c.criterion_id} className="crit2 PASS"><span className="crit2-mark" aria-hidden>✓</span>
            <div><div className="small">{locOf(c, "title_he")}</div><div className="tiny muted"><Explanation c={c} /></div></div></div>)}
        </Expand>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- findings
function FindingsList({ findings, ws, readOnly, finish, showEvidence }: { findings: DeskFinding[]; ws: Workspace;
  readOnly: boolean; finish: (r: DeskResult, t: string) => void; showEvidence: (f: Focus) => void }) {
  const { en, t } = useLang();
  if (!findings.length) return null;
  const open = findings.filter((f) => f.status === "open" && f.review_state !== "INFO");
  const info = findings.filter((f) => f.status === "open" && f.review_state === "INFO");
  const closed = findings.filter((f) => f.status !== "open");
  return (
    <section className="dp-sec">
      <div className="dp-label">{en ? `AI findings on the document${open.length ? ` (${open.length} open)` : ""}` : <>ממצאי ה-AI במסמך{open.length ? ` (${open.length} פתוחים)` : ""}</>}</div>
      {open.map((f) => <FindingRow key={f.finding_id} f={f} ws={ws} readOnly={readOnly} finish={finish} showEvidence={showEvidence} />)}
      {!open.length && !info.length && <div className="tiny muted">{t("אין ממצאים פתוחים במסמך.", "No open findings on the document.")}</div>}
      {info.length > 0 && <Expand label={en ? `For information (${info.length})` : `לידיעה (${info.length})`}>
        {info.map((f) => <FindingRow key={f.finding_id} f={f} ws={ws} readOnly={readOnly} finish={finish} showEvidence={showEvidence} />)}</Expand>}
      {closed.length > 0 && <Expand label={en ? `${closed.length} closed findings` : `${closed.length} ממצאים סגורים`}>
        {closed.map((f) => <FindingRow key={f.finding_id} f={f} ws={ws} readOnly showEvidence={showEvidence} finish={finish} />)}</Expand>}
    </section>
  );
}

function FindingRow({ f, ws, readOnly, finish, showEvidence }: { f: DeskFinding; ws: Workspace; readOnly: boolean;
  finish: (r: DeskResult, t: string) => void; showEvidence: (f: Focus) => void }) {
  const [dismissing, setDismissing] = useState(false);
  const { en, t } = useLang();
  return (
    <div className={`dfind ${f.review_state}${f.status !== "open" ? " closed" : ""}`} data-testid="desk-finding" data-code={f.code}>
      <div className="row between"><span className="small bold">{locOf(f, "title_he")}</span>
        <Chip tone={f.status !== "open" ? "neutral" : f.review_state === "CUSTOMER_ACTION_REQUIRED" ? "warn" : f.review_state === "INFO" ? "neutral" : "navy"}>
          {f.status === "open" ? locOf(f, "review_state_he") : locOf(f, "status_he")}</Chip></div>
      <div className="small dfind-msg"><FindingMessage f={f} /></div>
      {f.statements.map((s, i) => <div key={i} className="notice small" style={{ marginTop: 6 }}>{en
        ? <>Customer's explanation ({s.channel === "voice" ? "by voice" : "in chat"}, unverified): <Orig text={s.text} /></>
        : <>הסבר הלקוח ({s.channel === "voice" ? "בקול" : "בצ׳אט"}, לא מאומת): {s.text}</>}</div>)}
      {f.not_reproduced && <div className="tiny muted">{t("הבדיקה האחרונה אינה משחזרת ממצא זה, הוא נשאר פתוח עד להכרעתך.", "The latest check doesn't reproduce this finding; it stays open until you rule on it.")}</div>}
      <div className="row wrap" style={{ marginTop: 4 }}>
        {f.evidence.map((e) => (
          <button key={e.evidence_id} className="ev-link" onClick={() => showEvidence({ documentId: e.document_id, field: e.field, page: e.page })}
            data-testid="show-evidence">{en ? `Show on the document: ${locOf(e, "label_he")} · p. ${e.page}${e.verified ? "" : " (not verified)"}`
              : <>הצג במסמך: {e.label_he} · עמ׳ {e.page}{e.verified ? "" : " (לא אומת)"}</>}</button>
        ))}
        {f.can_dismiss && !readOnly && !dismissing && <button className="link tiny subtle" onClick={() => setDismissing(true)} data-testid="dismiss-finding">{t("דיווח על טעות בזיהוי ה־AI", "Report an AI detection error")}</button>}
      </div>
      {dismissing && <DismissForm finding={f} ws={ws} onCancel={() => setDismissing(false)} finish={finish}
        impact={en ? ["The finding will be marked as an AI detection error and logged for quality control.", "This isn't a decision on the document: it stays awaiting your decision.",
          "The finding won't reopen, because the file itself doesn't change."]
          : ["הממצא יסומן כטעות בזיהוי של ה-AI ויתועד ביומן לבקרת איכות.", "זו אינה החלטה על המסמך: הוא נשאר ממתין להחלטתך.",
          "הממצא לא ייפתח מחדש, כי הקובץ עצמו לא משתנה."]}
        customer={t("הלקוח אינו רואה את הדיווח ואת הנימוק.", "The customer doesn't see the report or the rationale.")} />}
      {f.history.length > 1 && <details className="tiny muted" style={{ marginTop: 4 }}><summary>{t("היסטוריית הממצא", "Finding history")} ({f.history.length})</summary>
        {f.history.map((h, i) => <div key={i}><span className="ltr">{h.at?.slice(0, 16).replace("T", " ")}</span> · {h.event}{h.note ? <> · <Orig text={h.note} /></> : ""}</div>)}</details>}
    </div>
  );
}

// ---------------------------------------------------------------- missing document
function MissingPanel({ item, ws, staff, readOnly, finish, solo, showEvidence }: Ctx<MissingItem>) {
  const [open, setOpen] = useState(false);
  const { en, t } = useLang();
  const borrower = ws.case.borrowers.find((b) => b.borrower_id === item.borrower_id);
  return (<>
    <section className="dp-sec z-info">
      <div className="dp-eyebrow">{t("מסמך חסר", "Missing document")}</div>
      <div className="row wrap"><Chip tone={item.open_request ? "warn" : "neutral"} testId="missing-status">{locOf(item, "status_he")}</Chip>
        {item.family_he && <Chip>{locOf(item, "family_he")}</Chip>}{borrower && <Chip>{locOf(borrower, "name_he")}</Chip>}</div>
      <p className="small">{locOf(item, "explanation_he")}</p>
      {solo && item.related_documents.length > 0 && (
        <div className="missing-related" data-testid="missing-related">
          <div className="small bold">{t("ייתכן שקשור:", "Possibly related:")}</div>
          {item.related_documents.map((d) => (
            <button key={d.document_id} className="related-doc" onClick={() => showEvidence({ documentId: d.document_id })}>
              <span className="ltr">{d.filename}</span><span className="small muted">{locOf(d, "note_he")}</span>
            </button>
          ))}
        </div>
      )}
      {solo && item.duplicate_note_he && <div className="tiny muted">{locOf(item, "duplicate_note_he")}</div>}
    </section>
    {item.open_request && <OpenRequest r={item.open_request} ws={ws} staff={staff} readOnly={readOnly} finish={finish} />}
    {(item.allowed_actions.includes("request_missing") || item.allowed_actions.includes("request_requirement")) && !readOnly && (
      <section className="dp-sec dp-decide z-act" data-testid="decision-actions">
        <div className="dp-eyebrow">{t("הפעולה שלך", "Your action")}</div>
        {!open ? <button className="act-primary" onClick={() => setOpen(true)} data-testid="action-request-missing">{t("בקשת השלמת מסמך", "Request a missing document")}</button>
          : <CustomerRequestForm from={ws.case.banker.name_he} draft={item.draft} onCancel={() => setOpen(false)}
            title={() => item.period_he ? `נדרש תלוש ${item.period_he}, ${borrower?.first_name_he || ""}` : `נדרש: ${item.title_he}`}
            submitLabel={t("שמירה והצגה ללקוח באפליקציה", "Save and show to the customer in the app")} testId="missing-form"
            submit={(message, _p, rationale) => (rid) => item.period
              ? api.requestMissing(ws.case_id, { borrower_id: item.borrower_id!, period: item.period, customer_message: message, rationale, request_id: rid })
              : api.requestRequirement(ws.case_id, item.requirement_code!, { customer_message: message, rationale, request_id: rid })}
            onDone={(r) => finish(r, notSent())} />}
      </section>
    )}
    <RequestsList requests={item.requests.filter((r) => r.status !== "OPEN")} />
    {item.history.length > 0 && <div className="dp-footer"><Expand label={en ? `Decision history (${item.history.length})` : `היסטוריית החלטות (${item.history.length})`} defaultOpen>
      <HistoryList entries={item.history} bare /></Expand></div>}
  </>);
}

// ---------------------------------------------------------------- case-level finding
type FindingMode = "request_missing" | "request_explanation" | "resolve" | "dismiss" | "escalate";
const FINDING_MODES: { key: FindingMode; label: string; labelEn: string }[] = [
  { key: "request_missing", label: "בקשת השלמת מסמך", labelEn: "Request a missing document" }, { key: "request_explanation", label: "בקשת הסבר / אסמכתה", labelEn: "Request an explanation / proof" },
  { key: "resolve", label: "סגירת הבירור לאחר בדיקה", labelEn: "Close the review after checking" }, { key: "dismiss", label: "דיווח על טעות בזיהוי ה־AI", labelEn: "Report an AI detection error" },
  { key: "escalate", label: "העברה להמשך בירור", labelEn: "Escalate for further review" },
];

function CaseFindingPanel({ item, ws, staff, readOnly, finish }: Ctx<CaseFindingItem>) {
  const { en, t } = useLang();
  const [mode, setMode] = useState<FindingMode | null>(null);
  const f = item.finding;
  const rec = item.recommendation;
  const run = (action: "request_explanation" | "escalate", body: Record<string, unknown>): Submit => (rid) =>
    api.decide(ws.case_id, f.finding_id, { action, request_id: rid, ...body });
  const borrower = ws.case.borrowers.find((b) => b.borrower_id === item.borrower_id);
  const inc = item.income;
  return (<>
    <section className="dp-sec z-ai">
      <div className="dp-head"><span className="dp-eyebrow">{t("ממצא ברמת התיק", "Case-level finding")}</span><img className="jeen-logo-inline" src="/brand/jeen-logo.svg" alt="Jeen" /></div>
      <div className="row wrap">
        <Chip tone={f.status === "open" ? "navy" : "neutral"}>{f.status === "open" ? locOf(f, "review_state_he") : locOf(f, "status_he")}</Chip>
        {item.escalated && <Chip tone="info">{t("בהמשך בירור", "Under further review")}</Chip>}
        {inc && inc.basis !== "none" && <Chip tone={item.basis.partial ? "warn" : "ok"} testId="comparison-basis">
          {item.basis.partial ? (en ? `Preliminary comparison · ${item.basis.months_compared.length} of ${item.basis.months_required.length} months`
            : `השוואה ראשונית · ${item.basis.months_compared.length} מתוך ${item.basis.months_required.length} חודשים`) : t("השוואה מלאה", "Full comparison")}</Chip>}
      </div>
      {!inc && <p className="small"><FindingMessage f={f} /></p>}
      {inc && <div className={`dp-income ${inc.tone}`} data-testid="income-summary">
        <div className="small bold">{locOf(inc, "summary_he")}</div>
        <div className="tiny muted">{en ? `${locOf(inc, "basis_he")}. Checked: ${locOf(inc, "months_compared_he") || "-"}${inc.months_missing?.length ? ` · missing: ${locOf(inc, "months_missing_he")}` : ""}.`
          : <>{inc.basis_he}. נבדקו: {inc.months_compared_he || "-"}{inc.months_missing?.length ? ` · חסרים: ${inc.months_missing_he}` : ""}.</>}</div>
      </div>}
      {item.reopened_after && <div className="dp-state info" data-testid="reopened-after">{t("נפתח מחדש: הנתונים השתנו מאז ההכרעה הקודמת שלך בממצא זה. ההכרעה הקודמת נשמרה בהיסטוריה.",
        "Reopened: the data changed since your previous ruling on this finding. The previous ruling is kept in the history.")}</div>}
    </section>
    <section className="dp-sec" data-testid="customer-said">
      <div className="dp-label">{t("מה הלקוח מסר", "What the customer said")}</div>
      {f.statements.length ? f.statements.map((x, i) => <div key={i} className="notice small">{en
        ? <>Customer's explanation ({x.channel === "voice" ? "by voice" : x.channel === "app" ? "in the app" : "in chat"}, unverified, not evidence): <Orig text={x.text} /></>
        : <>הסבר הלקוח ({x.channel === "voice" ? "בקול" : x.channel === "app" ? "באפליקציה" : "בצ׳אט"}, לא מאומת, אינו ראיה): {x.text}</>} <When at={x.created_at} /></div>)
        : <div className="small muted">{t("לא נמסר הסבר מהלקוח.", "The customer gave no explanation.")}</div>}
    </section>
    {item.open_request && <OpenRequest r={item.open_request} ws={ws} staff={staff} readOnly={readOnly} finish={finish} />}
    {f.status === "open" && rec && (item.allowed_actions.length === 0 || readOnly) && (
      <section className="dp-sec"><div className="dp-next" data-testid="next-step"><b>{locOf(rec, "title_he")}</b><span><Loc he={rec.body_he} en={(rec as { body_en?: string }).body_en} /></span></div></section>
    )}
    {item.allowed_actions.length > 0 && !readOnly && (
      <section className="dp-sec dp-decide z-act" data-testid="decision-actions">
        <div className="dp-eyebrow">{t("ההחלטה שלך", "Your decision")}</div>
        {f.status === "open" && rec && <div className="dp-next" data-testid="next-step"><b>{locOf(rec, "title_he")}</b><span><Loc he={rec.body_he} en={(rec as { body_en?: string }).body_en} /></span></div>}
        {(() => {
          const lead = FINDING_MODES.find((m) => m.key === rec?.action && item.allowed_actions.includes(m.key));
          const rest = FINDING_MODES.filter((m) => m !== lead && m.key !== "dismiss" && item.allowed_actions.includes(m.key));
          return (<>
            {lead && <button className={`act-primary${mode === lead.key ? " on" : ""}`} onClick={() => setMode(mode === lead.key ? null : lead.key)}
              data-testid={`finding-action-${lead.key}`}>{en ? lead.labelEn : lead.label}</button>}
            <div className="act-secondary-row">
              {rest.map((m) => <button key={m.key} className={`act-secondary${mode === m.key ? " on" : ""}`} onClick={() => setMode(mode === m.key ? null : m.key)}
                data-testid={`finding-action-${m.key}`}>{en ? m.labelEn : m.label}</button>)}
            </div>
            {item.allowed_actions.includes("dismiss") && <button className={`link tiny subtle${mode === "dismiss" ? " on" : ""}`} style={{ alignSelf: "flex-start" }}
              onClick={() => setMode(mode === "dismiss" ? null : "dismiss")} data-testid="finding-action-dismiss">{t("דיווח על טעות בזיהוי ה־AI", "Report an AI detection error")}</button>}
          </>);
        })()}
        {mode === "request_missing" && item.drafts.missing && <MissingMonthsForm item={item} ws={ws} onCancel={() => setMode(null)} finish={finish} />}
        {mode === "request_explanation" && <CustomerRequestForm from={ws.case.banker.name_he} draft={item.drafts.explanation} onCancel={() => setMode(null)}
          title={() => `נדרש הסבר או אסמכתה, ${borrower?.first_name_he || ""}`} submitLabel={t("שמירה והצגה ללקוח באפליקציה", "Save and show to the customer in the app")} testId="request-explanation-form"
          note={t("הלקוח יוכל להשיב בכתב או לצרף מסמך. התשובה תתועד כהסבר לא מאומת, והממצא יישאר פתוח עד להחלטתך.",
            "The customer can reply in writing or attach a document. The reply is recorded as an unverified explanation, and the finding stays open until your decision.")}
          submit={(message, _p, rationale) => run("request_explanation", { customer_message: message, rationale })} onDone={(r) => finish(r, notSent())} />}
        {mode === "resolve" && <ResolveForm item={item} ws={ws} onCancel={() => setMode(null)} finish={finish} />}
        {mode === "dismiss" && <DismissForm finding={f} impact={locList(item.impact, "dismiss")} customer={locOf(item.impact, "customer_he")} ws={ws}
          onCancel={() => setMode(null)} finish={finish} />}
        {mode === "escalate" && <RationaleForm label={t("מה דורש המשך בירור?", "What needs further review?")} submitLabel={t("העברה להמשך בירור", "Escalate for further review")} required testId="escalate-finding-form"
          note={t("הממצא יישאר פתוח בקבוצת ״בבירור״. הלקוח אינו מקבל הודעה.", "The finding stays open in the “Escalated” group. The customer receives no message.")} submit={(rationale) => run("escalate", { rationale })}
          onCancel={() => setMode(null)} onDone={(r) => finish(r, tr("הממצא הועבר להמשך בירור ונשאר פתוח.", "The finding was escalated for further review and stays open."))} />}
      </section>
    )}
    <RequestsList requests={item.requests.filter((r) => r.status !== "OPEN")} />
    <div className="dp-footer">
    {item.history.length > 0 && <Expand label={en ? `Decision history (${item.history.length})` : `היסטוריית החלטות (${item.history.length})`} defaultOpen={f.status !== "open" || item.escalated}>
      <HistoryList entries={item.history} bare /></Expand>}
    {!readOnly && <NoteForm submit={(text) => (rid) => api.addNote(ws.case_id, { text, finding_id: f.finding_id, request_id: rid })} finish={finish} />}
    <Expand label={t("פרטים טכניים", "Technical details")}>
      <TechList rows={[[t("נוסח הממצא", "Finding wording"), inc ? <FindingMessage f={f} /> : null], [t("קוד", "Code"), f.code], [t("מפתח", "Key"), f.key], [t("קריטריון", "Criterion"), inc?.criterion_id], [t("הוכרע על ידי", "Decided by"), inc?.decided_by],
        [t("הערכת המודל (לא מכריעה)", "Model assessment (not decisive)"), inc?.model_assessment], [t("הסבר המודל", "Model explanation"), inc?.model_explanation_he ? <Loc he={inc.model_explanation_he} en={(inc as { model_explanation_en?: string }).model_explanation_en} /> : null]]} />
    </Expand>
    </div>
  </>);
}

function MissingMonthsForm({ item, ws, onCancel, finish }: { item: CaseFindingItem; ws: Workspace; onCancel: () => void;
  finish: (r: DeskResult, t: string) => void }) {
  const draft = item.drafts.missing!;
  const [months, setMonths] = useState<string[]>(draft.months);
  const [message, setMessage] = useState(draft.message_he);
  const [ids] = useState(() => Object.fromEntries(draft.months.map((m) => [m, newRequestId()])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { en, t } = useLang();
  const go = async () => {
    setBusy(true); setError(null);
    let last: DeskResult | null = null;
    const failed: string[] = [];
    for (const m of months) {
      try { last = await api.requestMissing(ws.case_id, { borrower_id: item.borrower_id!, period: m, customer_message: message.trim(), request_id: ids[m] }); }
      catch (e) { failed.push(`${monthL(m)}: ${(e as Error).message}`); }
    }
    setBusy(false);
    if (failed.length) setError(failed.join(" · "));
    if (last) finish(last, tr(`נשמרו ${months.length - failed.length} בקשות להשלמת תלושים, והן מוצגות ללקוח באפליקציה. לא נשלחה הודעת SMS או דוא״ל.`,
      `${months.length - failed.length} payslip requests were saved and are shown to the customer in the app. No SMS or email was sent.`));
  };
  return (
    <div className="dp-form" data-testid="request-missing-form">
      <div className="small bold">{t("אילו תלושים לבקש?", "Which payslips to request?")}</div>
      {draft.months.map((m) => (
        <label key={m} className="bulk-row"><input type="checkbox" checked={months.includes(m)}
          onChange={(e) => setMonths(e.target.checked ? [...months, m].sort() : months.filter((x) => x !== m))} /><span>{en ? `${monthL(m)} payslip` : <>תלוש {monthHe(m)}</>}</span><span /></label>
      ))}
      <label className="dp-field">{t("הודעה ללקוח", "Message to the customer")} <span className="muted">{t("טיוטה מוצעת, אפשר לערוך", "Suggested draft — you can edit it (sent in Hebrew)")}</span>
        <textarea className="note msg" value={message} maxLength={600} onChange={(e) => setMessage(e.target.value)} data-testid="customer-message" {...autoDir(en)} /></label>
      <DraftPreview he={draft.message_he} en={(draft as { message_en?: string }).message_en} current={message} />
      <div className="tiny muted">{t("לכל חודש נוצרת בקשה נפרדת עם כפתור העלאה משלה באפליקציה. לא נשלחת הודעת SMS, דוא״ל או התראה.",
        "Each month gets a separate request with its own upload button in the app. No SMS, email or notification is sent.")}</div>
      {error && <div className="dp-err" role="alert">{error}</div>}
      <div className="row"><button className="btn btn-orange btn-sm" disabled={busy || !months.length || !message.trim()} onClick={go} data-testid="send-request">
        {busy && <span className="spinner" />}{t("שמירה והצגה ללקוח באפליקציה", "Save and show to the customer in the app")}</button>
        <button className="btn btn-soft btn-sm" onClick={onCancel}>{t("ביטול", "Cancel")}</button></div>
    </div>
  );
}

const RESOLVE_REASONS: { key: string; label: string; hint: string; labelEn: string; hintEn: string; needsDocs: boolean; needsStatement?: boolean }[] = [
  { key: "verified_with_documents", label: "אומת מול מסמכים בתיק", hint: "סמנו את המסמכים שבדקתם.", labelEn: "Verified against documents in the case",
    hintEn: "Select the documents you checked.", needsDocs: true },
  { key: "explanation_supported", label: "הסבר הלקוח נתמך באסמכתה", hint: "הסבר לבדו אינו מספיק, סמנו את המסמך שתומך בו.", labelEn: "The customer's explanation is backed by proof",
    hintEn: "An explanation alone isn't enough; select the document that supports it.", needsDocs: true, needsStatement: true },
  { key: "professional_judgment", label: "החלטה מקצועית במסגרת המדיניות", hint: "ללא אסמכתה במסמכים. נדרש נימוק מפורט, והיא נרשמת כהכרעה אנושית.",
    labelEn: "A professional decision within the policy", hintEn: "No supporting documents. A detailed rationale is required, and it's recorded as a human ruling.", needsDocs: false },
];
const MIN_OVERRIDE = 15;

function ResolveForm({ item, ws, onCancel, finish }: { item: CaseFindingItem; ws: Workspace; onCancel: () => void;
  finish: (r: DeskResult, t: string) => void }) {
  const { en, t } = useLang();
  const [step, setStep] = useState<"edit" | "confirm">("edit");
  const [reason, setReason] = useState<string>(item.has_customer_statement ? "" : "verified_with_documents");
  const [docs, setDocs] = useState<string[]>([]);
  const [rationale, setRationale] = useState("");
  const [ack, setAck] = useState(false);
  const s = useSubmit((r) => finish(r, tr("הבירור נסגר ונרשם עם הבסיס, המסמכים והנימוק. ללקוח מוצגת רק שורה ניטרלית בעדכונים.",
    "The review was closed and recorded with the basis, the documents and the rationale. The customer sees only a neutral line in their updates.")));
  const optionLabel = (o: CaseFindingItem["evidence_options"][number], wrap: boolean) => en
    ? `${(o.period_he ? locOf(o, "period_he") : "") || o.filename}${o.net ? (wrap ? ` (net ${o.net})` : ` · net ${o.net}`) : ""}`
    : `${o.period_he || o.filename}${o.net ? (wrap ? ` (נטו ${o.net})` : ` · נטו ${o.net}`) : ""}`;
  const chosen = RESOLVE_REASONS.find((r) => r.key === reason);
  const partial = item.basis.partial;
  const valid = !!chosen && rationale.trim().length > 0 && (!chosen.needsDocs || docs.length > 0)
    && (reason !== "professional_judgment" || rationale.trim().length >= MIN_OVERRIDE) && (!partial || ack)
    && (!chosen.needsStatement || item.has_customer_statement);
  const submit: Submit = (rid) => api.decide(ws.case_id, item.finding.finding_id, { action: "resolve", reason_code: reason,
    evidence_document_ids: chosen?.needsDocs ? docs : [], rationale: rationale.trim(), acknowledge_partial: ack, request_id: rid });
  const picked = item.evidence_options.filter((o) => docs.includes(o.document_id));
  return (
    <div className="dp-form" data-testid="resolve-form">
      {step === "edit" ? (<>
        <div className="small bold">{t("על מה מבוססת סגירת הבירור?", "What is closing the review based on?")}</div>
        <div className="reason-list" role="radiogroup">
          {RESOLVE_REASONS.map((r) => {
            const off = !!r.needsStatement && !item.has_customer_statement;
            return (
              <label key={r.key} className={`reason${reason === r.key ? " on" : ""}${off ? " off" : ""}`}>
                <input type="radio" name="resolve-reason" checked={reason === r.key} disabled={off} onChange={() => setReason(r.key)} data-testid={`reason-${r.key}`} />
                <span><b>{en ? r.labelEn : r.label}</b><span className="tiny muted">{off ? t("לא נמסר הסבר מהלקוח בממצא הזה.", "The customer gave no explanation for this finding.") : en ? r.hintEn : r.hint}</span></span>
              </label>
            );
          })}
        </div>
        {chosen?.needsDocs && (
          <div className="stack" style={{ gap: 4 }} data-testid="evidence-options">
            <div className="small bold">{t("מסמכים תומכים", "Supporting documents")}</div>
            {item.evidence_options.map((o) => (
              <label key={o.document_id} className="bulk-row"><input type="checkbox" checked={docs.includes(o.document_id)}
                onChange={(e) => setDocs(e.target.checked ? [...docs, o.document_id] : docs.filter((x) => x !== o.document_id))} />
                <span>{optionLabel(o, false)}</span><span className="tiny muted">AI: {locOf(o, "verdict_he")}</span></label>
            ))}
            {!item.evidence_options.length && <div className="tiny muted">{t("אין בתיק מסמכים שנבדקו ללווה הזה.", "There are no checked documents for this borrower in the case.")}</div>}
          </div>
        )}
        <label className="dp-field">{t("הנימוק שלך", "Your rationale")} <span className="warn-text">{en ? `(required${reason === "professional_judgment" ? ", a detailed rationale" : ""})`
          : <>(חובה{reason === "professional_judgment" ? ", נימוק מפורט" : ""})</>}</span>
          <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="resolve-rationale" {...autoDir(en)} /></label>
        {partial && (
          <label className="partial-ack" data-testid="ack-partial">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
            {en ? <span>The comparison is based on {item.basis.months_compared.length} of the {item.basis.months_required.length} required months
              (missing: {item.income?.months_missing_he ? locOf(item.income, "months_missing_he") : locOf(item, "months_to_request_he")}). I'm ruling now on a partial basis.</span>
              : <span>ההשוואה מבוססת על {item.basis.months_compared.length} מתוך {item.basis.months_required.length} החודשים הנדרשים
              (חסרים {item.income?.months_missing_he || item.months_to_request_he}). אני מכריע/ה עכשיו על בסיס חלקי.</span>}
          </label>
        )}
        <div className="row"><button className="btn btn-dark btn-sm" disabled={!valid} onClick={() => setStep("confirm")} data-testid="resolve-review">{t("המשך לסיכום", "Continue to summary")}</button>
          <button className="btn btn-soft btn-sm" onClick={onCancel}>{t("ביטול", "Cancel")}</button></div>
      </>) : (
        <div className="confirm" data-testid="resolve-confirm">
          <div className="confirm-title">{t("אישור סגירת הבירור", "Confirm closing the review")}</div>
          <dl>
            <dt>{t("הממצא", "Finding")}</dt><dd>{locOf(item.finding, "title_he")}</dd>
            <dt>{t("בסיס הסגירה", "Basis for closing")}</dt><dd>{en ? chosen?.labelEn : chosen?.label}</dd>
            <dt>{t("מסמכים תומכים", "Supporting documents")}</dt><dd>{picked.length ? picked.map((o) => optionLabel(o, true)).join(" · ") : t("ללא, החלטה מקצועית", "None — a professional decision")}</dd>
            {item.has_customer_statement && <><dt>{t("הסבר הלקוח", "Customer's explanation")}</dt><dd>{t("מצורף כהקשר בלבד, לא מאומת", "Attached as context only, unverified")}</dd></>}
            <dt>{t("הנימוק שלך", "Your rationale")}</dt><dd>{rationale.trim()}</dd>
            {partial && <><dt>{t("בסיס הנתונים", "Data basis")}</dt><dd className="warn-text">{en ? `Partial, ${item.basis.months_compared.length} of ${item.basis.months_required.length} months`
              : <>חלקי, {item.basis.months_compared.length} מתוך {item.basis.months_required.length} חודשים</>}</dd></>}
          </dl>
          <div className="small bold">{t("מה ישתנה בתיק", "What will change in the case")}</div>
          <ul className="dp-list small">{locList(item.impact, "resolve").map((l, i) => <li key={i}>{l}</li>)}</ul>
          <div className="small bold">{t("מה הלקוח יראה", "What the customer will see")}</div>
          <div className="small">{locOf(item.impact, "customer_he")}</div>
          {s.error && <div className="dp-err" role="alert">{s.error}</div>}
          <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy} onClick={() => s.go(submit)} data-testid="resolve-submit">
            {s.busy && <span className="spinner" />}{t("אישור סגירת הבירור", "Confirm closing the review")}</button>
            <button className="btn btn-soft btn-sm" disabled={s.busy} onClick={() => setStep("edit")}>{t("חזרה לעריכה", "Back to editing")}</button></div>
        </div>
      )}
    </div>
  );
}

const DISMISS_REASONS: [string, string][] = [["misread_document", "הנתון נקרא שגוי מהמסמך"], ["rule_not_applicable", "הכלל אינו חל על המקרה"],
  ["duplicate_finding", "כפילות של ממצא אחר"], ["other", "סיבה אחרת"]];
const DISMISS_REASONS_EN: [string, string][] = [["misread_document", "The value was misread from the document"], ["rule_not_applicable", "The rule doesn't apply to this case"],
  ["duplicate_finding", "A duplicate of another finding"], ["other", "Another reason"]];

function DismissForm({ finding, impact, customer, ws, onCancel, finish }: { finding: DeskFinding; impact: string[]; customer: string;
  ws: Workspace; onCancel: () => void; finish: (r: DeskResult, t: string) => void }) {
  const { en, t } = useLang();
  const [step, setStep] = useState<"edit" | "confirm">("edit");
  const [reason, setReason] = useState("");
  const [rationale, setRationale] = useState("");
  const s = useSubmit((r) => finish(r, tr("הדיווח על טעות ה-AI נרשם, והממצא סומן כשגוי.", "The AI error report was recorded, and the finding was marked as an error.")));
  const reasons = en ? DISMISS_REASONS_EN : DISMISS_REASONS;
  const label = reasons.find(([k]) => k === reason)?.[1];
  return (
    <div className="dp-form" data-testid="dismiss-form">
      {step === "edit" ? (<>
        <label className="dp-field">{t("מה הטעות בזיהוי ה־AI?", "What is the AI detection error?")}
          <select value={reason} onChange={(e) => setReason(e.target.value)} data-testid="dismiss-reason">
            <option value="">{t("בחרו סיבה", "Choose a reason")}</option>{reasons.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></label>
        <label className="dp-field">{t("הנימוק שלך", "Your rationale")} <span className="warn-text">{t("(חובה, נימוק מפורט)", "(required, a detailed rationale)")}</span>
          <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="rationale" {...autoDir(en)} /></label>
        <div className="tiny muted">{t("דיווח על טעות של ה-AI אינו החלטה על המסמך ואינו בקשה מהלקוח.", "Reporting an AI error isn't a decision on the document and isn't a request to the customer.")}</div>
        <div className="row"><button className="btn btn-dark btn-sm" disabled={!reason || rationale.trim().length < MIN_OVERRIDE} onClick={() => setStep("confirm")}
          data-testid="dismiss-review">{t("המשך לסיכום", "Continue to summary")}</button><button className="btn btn-soft btn-sm" onClick={onCancel}>{t("ביטול", "Cancel")}</button></div>
      </>) : (
        <div className="confirm" data-testid="dismiss-confirm">
          <div className="confirm-title">{t("אישור דיווח על טעות בזיהוי ה־AI", "Confirm the AI detection error report")}</div>
          <dl><dt>{t("הממצא", "Finding")}</dt><dd>{locOf(finding, "title_he")}</dd><dt>{t("סוג הטעות", "Type of error")}</dt><dd>{label}</dd><dt>{t("הנימוק שלך", "Your rationale")}</dt><dd>{rationale.trim()}</dd></dl>
          <div className="small bold">{t("מה ישתנה בתיק", "What will change in the case")}</div>
          <ul className="dp-list small">{impact.map((l, i) => <li key={i}>{l}</li>)}</ul>
          <div className="small bold">{t("מה הלקוח יראה", "What the customer will see")}</div><div className="small">{customer}</div>
          {s.error && <div className="dp-err" role="alert">{s.error}</div>}
          <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy} data-testid="confirm-rationale"
            onClick={() => s.go((rid) => api.decide(ws.case_id, finding.finding_id, { action: "dismiss", reason_code: reason, rationale: rationale.trim(), request_id: rid }))}>
            {s.busy && <span className="spinner" />}{t("אישור הדיווח", "Confirm the report")}</button>
            <button className="btn btn-soft btn-sm" disabled={s.busy} onClick={() => setStep("edit")}>{t("חזרה לעריכה", "Back to editing")}</button></div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- forms
function useSubmit(onDone: (r: DeskResult) => void) {
  const [rid] = useState(newRequestId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const go = async (submit: Submit) => {
    setBusy(true); setError(null);
    try { onDone(await submit(rid)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return { busy, error, go };
}

function AcceptForm({ item, submit, onCancel, onDone }: { item: DocItem; submit: (rationale: string) => Submit; onCancel: () => void;
  onDone: (r: DeskResult) => void }) {
  const [rationale, setRationale] = useState("");
  const s = useSubmit(onDone);
  const { en, t } = useLang();
  const required = item.banker.accept_requires_rationale;
  const ack = item.findings.filter((f) => item.banker.acknowledge_finding_ids.includes(f.finding_id));
  return (
    <div className="dp-form" data-testid="accept-form">
      {ack.length > 0 && <div className="small"><b>{t("הממצאים הבאים ייסגרו כ״נבדק והתקבל״ עם הנימוק שלך:", "These findings will be closed as “checked and accepted” with your rationale:")}</b>
        <ul className="dp-list">{ack.map((f) => <li key={f.finding_id}>{locOf(f, "title_he")}</li>)}</ul></div>}
      <label className="dp-field">{t("נימוק פנימי", "Internal rationale")} {required ? <span className="warn-text">{en ? `(required, ${ack.length ? "there are open findings" : "the AI didn't find the document valid"})`
        : <>(חובה, {ack.length ? "יש ממצאים פתוחים" : "ה-AI לא מצא את המסמך תקין"})</>}</span> : <span className="muted">{t("(רשות)", "(optional)")}</span>}
        <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="accept-rationale" {...autoDir(en)} /></label>
      <div className="dp-disclaimer">{t("קבלת המסמך מסמנת אותו כנבדק בשלב בדיקת המסמכים בלבד. זו אינה החלטת אשראי, אינה אישור ההלוואה ואינה משנה את שלב הבקשה בבנק.",
        "Accepting the document marks it as reviewed for the document review stage only. This is not a credit decision, not a loan approval, and it doesn't change the application's stage at the bank.")}</div>
      {s.error && <div className="dp-err" role="alert">{s.error}</div>}
      <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy || (required && !rationale.trim())} onClick={() => s.go(submit(rationale.trim()))}
        data-testid="confirm-accept">{s.busy && <span className="spinner" />}{t("אישור קבלת המסמך", "Confirm accepting the document")}</button>
        <button className="btn btn-soft btn-sm" onClick={onCancel}>{t("ביטול", "Cancel")}</button></div>
    </div>
  );
}

function RationaleForm({ label, submitLabel, required, note, submit, onCancel, onDone, testId }: { label: string; submitLabel: string; required?: boolean;
  note?: string; submit: (rationale: string) => Submit; onCancel: () => void; onDone: (r: DeskResult) => void; testId: string }) {
  const [rationale, setRationale] = useState("");
  const s = useSubmit(onDone);
  const { en, t } = useLang();
  return (
    <div className="dp-form" data-testid={testId}>
      <label className="dp-field">{label}<textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="rationale" {...autoDir(en)} /></label>
      {note && <div className="tiny muted">{note}</div>}
      {s.error && <div className="dp-err" role="alert">{s.error}</div>}
      <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy || (required && !rationale.trim())} onClick={() => s.go(submit(rationale.trim()))}
        data-testid="confirm-rationale">{s.busy && <span className="spinner" />}{submitLabel}</button>
        <button className="btn btn-soft btn-sm" onClick={onCancel}>{t("ביטול", "Cancel")}</button></div>
    </div>
  );
}

function CustomerRequestForm({ draft, periods, title, from, submitLabel, note, submit, onCancel, onDone, testId }: {
  draft: Draft; periods?: string[]; title: (period: string) => string; from: string; submitLabel: string; note?: string; testId: string;
  submit: (message: string, period: string, rationale: string) => Submit; onCancel: () => void; onDone: (r: DeskResult) => void;
}) {
  const [step, setStep] = useState<"edit" | "preview">("edit");
  const [message, setMessage] = useState(draft.message_he);
  const [period, setPeriod] = useState(draft.requested_period || "");
  const [rationale, setRationale] = useState("");
  const s = useSubmit(onDone);
  const { en, t } = useLang();
  return (
    <div className="dp-form" data-testid={testId}>
      {step === "edit" ? (<>
        <label className="dp-field">{t("מה הלקוח מתבקש להעלות", "What the customer is asked to upload")}
          {periods ? (
            <select value={period} onChange={(e) => setPeriod(e.target.value)} data-testid="requested-period">
              <option value="">{t("תלוש מתוקן (ללא חודש מסוים)", "A corrected payslip (no specific month)")}</option>
              {periods.map((p) => <option key={p} value={p}>{en ? `${monthL(p)} payslip` : <>תלוש {monthHe(p)}</>}</option>)}
            </select>
          ) : <span className="dp-static">{locOf(draft, "requested_item_he")}</span>}
        </label>
        <label className="dp-field">{t("הודעה ללקוח", "Message to the customer")} <span className="muted">{t("טיוטה מוצעת מתוך נתוני הבדיקה, אפשר לערוך", "A draft suggested from the review data — you can edit it (sent in Hebrew)")}</span>
          <textarea className="note msg" value={message} maxLength={600} onChange={(e) => setMessage(e.target.value)} data-testid="customer-message" {...autoDir(en)} />
          <span className="tiny muted ltr" style={{ alignSelf: "flex-end" }}>{message.length}/600</span></label>
        <DraftPreview he={draft.message_he} en={(draft as { message_en?: string }).message_en} current={message} />
        <label className="dp-field">{t("נימוק פנימי", "Internal rationale")} <span className="muted">{t("(לא מוצג ללקוח, רשות)", "(not shown to the customer, optional)")}</span>
          <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="internal-rationale" {...autoDir(en)} /></label>
        {note && <div className="tiny muted">{note}</div>}
        <div className="row"><button className="btn btn-dark btn-sm" disabled={!message.trim()} onClick={() => setStep("preview")} data-testid="preview-request">{t("המשך לתצוגה מקדימה", "Continue to preview")}</button>
          <button className="btn btn-soft btn-sm" onClick={onCancel}>{t("ביטול", "Cancel")}</button></div>
      </>) : (<>
        <div className="req-preview" data-testid="request-preview">
          <div className="tiny muted">{t("כך תופיע הבקשה באפליקציית הלקוח", "How the request will appear in the customer's app (in Hebrew)")}</div>
          <div className="req-preview-card" {...(en ? { dir: "rtl", lang: "he" } : {})}>
            <div className="req-preview-from">בקשה מ{from}</div>
            <div className="bold">{title(period)}</div>
            <p className="small">{message.trim()}</p>
            <span className="req-preview-btn">להעלאת המסמך</span>
          </div>
        </div>
        <div className="tiny muted">{t("הבקשה תישמר בתיק ותוצג ללקוח באפליקציה. לא נשלחת הודעת SMS, דוא״ל או התראה.", "The request will be saved in the case and shown to the customer in the app. No SMS, email or notification is sent.")}</div>
        {s.error && <div className="dp-err" role="alert">{s.error}</div>}
        <div className="row"><button className="btn btn-orange btn-sm" disabled={s.busy} onClick={() => s.go(submit(message.trim(), period, rationale.trim()))}
          data-testid="send-request">{s.busy && <span className="spinner" />}{submitLabel}</button>
          <button className="btn btn-soft btn-sm" onClick={() => setStep("edit")} disabled={s.busy}>{t("חזרה לעריכה", "Back to editing")}</button></div>
      </>)}
    </div>
  );
}

function NoteForm({ submit, finish }: { submit: (text: string) => Submit; finish: (r: DeskResult, t: string) => void }) {
  const [text, setText] = useState("");
  const [key, setKey] = useState(0);
  const { en, t } = useLang();
  const s = useSubmit((r) => { finish(r, tr("ההערה הפנימית נשמרה.", "The internal note was saved.")); setText(""); setKey(key + 1); });
  return (
    <Expand label={t("הערה פנימית", "Internal note")} key={key}>
      <textarea className="note" value={text} onChange={(e) => setText(e.target.value)} placeholder={t("נראית רק לצוות הבנק", "Visible to bank staff only")} data-testid="note-text" {...autoDir(en)} />
      {s.error && <div className="dp-err" role="alert">{s.error}</div>}
      <button className="btn btn-ghost btn-sm" style={{ marginTop: 6 }} disabled={s.busy || !text.trim()} onClick={() => s.go(submit(text.trim()))}>{t("שמירת הערה", "Save note")}</button>
    </Expand>
  );
}

// ---------------------------------------------------------------- read-only blocks
function OpenRequest({ r, ws, staff, readOnly, finish }: { r: DeskRequest; ws?: Workspace; staff?: string; readOnly?: boolean;
  finish?: (res: DeskResult, t: string) => void }) {
  const [withdrawing, setWithdrawing] = useState(false);
  const { t } = useLang();
  return (
    <section className="dp-sec">
      <div className="dp-state warn" data-testid="open-request">{t("בקשה פתוחה ללקוח:", "Open request to the customer:")} {locOf(r, "title_he")} <When at={r.created_at} by={r.created_by_name ? locOf(r, "created_by_name") : r.created_by_name} />
        <blockquote className="dp-quote"><Orig text={r.message_he} /></blockquote>
        {ws && staff && finish && !readOnly && !withdrawing && <button className="link tiny subtle" style={{ alignSelf: "flex-start" }}
          onClick={() => setWithdrawing(true)} data-testid="withdraw-request">{t("ביטול הבקשה…", "Withdraw the request…")}</button>}
      </div>
      {withdrawing && ws && staff && finish && <RationaleForm label={t("למה לבטל את הבקשה?", "Why withdraw the request?")} submitLabel={t("ביטול הבקשה ללקוח", "Withdraw the request to the customer")} required testId="withdraw-form"
        note={t("הבקשה תרד מהאפליקציה של הלקוח, והביטול יירשם ביומן. הממצא עצמו לא משתנה.", "The request will be removed from the customer's app, and the withdrawal logged. The finding itself doesn't change.")}
        submit={(rationale) => (rid) => api.withdrawRequest(ws.case_id, r.customer_request_id, { rationale, request_id: rid })}
        onCancel={() => setWithdrawing(false)} onDone={(res) => finish(res, tr("הבקשה בוטלה והוסרה מהאפליקציה של הלקוח.", "The request was withdrawn and removed from the customer's app."))} />}
    </section>
  );
}

function RequestsList({ requests }: { requests: DeskRequest[] }) {
  const { t } = useLang();
  if (!requests.length) return null;
  return (
    <section className="dp-sec">
      <div className="dp-label">{t("בקשות ללקוח", "Requests to the customer")}</div>
      {requests.map((r) => (
        <div key={r.customer_request_id} className="dreq" data-testid="request-row">
          <div className="row between"><span className="small bold">{locOf(r, "title_he")}</span><Chip tone={r.status === "OPEN" ? "warn" : "ok"}>{locOf(r, "status_he")}</Chip></div>
          <div className="tiny muted"><Orig text={r.message_he} /></div>
          <When at={r.responded_at || r.created_at} by={r.created_by_name ? locOf(r, "created_by_name") : r.created_by_name} />
        </div>
      ))}
    </section>
  );
}

function HistoryList({ entries, bare = false }: { entries: Decision[]; bare?: boolean }) {
  const { en, t } = useLang();
  if (!entries.length) return null;
  const word = (s?: string | null) => (en ? STATUS_WORD_EN : STATUS_WORD)[s || ""];
  return (
    <section className={bare ? "dp-hist" : "dp-sec"} data-testid="decision-history">
      {!bare && <div className="dp-label">{t("היסטוריית החלטות", "Decision history")}</div>}
      {entries.map((d) => (
        <div key={d.decision_id} className="hist">
          <div className="small"><b>{locOf(d, "action_he")}</b> · {locOf(d, "actor_name")} · <span className="ltr">{d.created_at.slice(0, 16).replace("T", " ")}</span></div>
          {d.previous_status !== d.new_status && <div className="tiny muted">{word(d.previous_status) || d.previous_status || "-"} {t("←", "→")} {word(d.new_status) || d.new_status}</div>}
          {d.rationale && <div className="tiny">{t("נימוק פנימי:", "Internal rationale:")} <Orig text={d.rationale} /></div>}
          {d.customer_message && <div className="tiny">{t("הודעה ללקוח:", "Message to the customer:")} <Orig text={d.customer_message} /></div>}
          {d.evidence_refs.length > 0 && <div className="tiny muted">{t("ראיות שתועדו:", "Evidence recorded:")} {d.evidence_refs.map((e) => e.field).join(", ")}</div>}
        </div>
      ))}
    </section>
  );
}

function TechList({ rows }: { rows: [string, ReactNode][] }) {
  return <div className="tech-list">{rows.filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) =>
    <div key={k} className="tiny"><span className="muted">{k}: </span><span className="ltr">{v}</span></div>)}</div>;
}
