import { useState, type ReactNode } from "react";
import { api, monthHe, type CaseFindingItem, type Decision, type DeskFinding, type DeskRequest, type DeskResult, type DocItem,
  type Draft, type MissingItem, type QueueItem, type Workspace } from "../../api";
import { BANKER_TONE, Chip, Expand, newRequestId, VERDICT_TONE, When } from "./deskUi";
import type { Focus } from "./ReviewWorkspace";

interface PanelProps {
  item: QueueItem; ws: Workspace; staff: string; readOnly: boolean; focus?: Focus | null;
  onDone: (text: string) => void; onError: (text: string) => void; onNext: () => void; hasNext: boolean; showEvidence: (f: Focus) => void;
}
type Submit = (requestId: string) => Promise<DeskResult>;
const STATUS_WORD: Record<string, string> = {
  AWAITING_DECISION: "ממתין להחלטה", AWAITING_CUSTOMER_FIX: "תיקון אצל הלקוח", ACCEPTED: "התקבל", CORRECTION_REQUESTED: "הוחזר לתיקון",
  ESCALATED: "בבירור", FAILED: "עיבוד נכשל", REPLACED: "הוחלף", MISSING: "חסר", REQUESTED: "נשלחה בקשה", open: "פתוח", resolved: "נסגר",
  dismissed: "סומן כשגוי", superseded: "נסגר", PREPARATION_CONFIRMED: "הכנה אושרה",
};
const NOT_SENT = "הבקשה נשמרה ומוצגת ללקוח באפליקציה. לא נשלחה הודעת SMS, דוא״ל או התראה.";

export function DecisionPanel(props: PanelProps) {
  const [done, setDone] = useState<string | null>(null);
  const finish = (result: DeskResult, text: string) => {
    const msg = result.duplicate ? "ההחלטה כבר נרשמה קודם — לא נוצרה רשומה כפולה." : text;
    setDone(msg);
    props.onDone(msg);
  };
  const ctx = { ...props, finish };
  return (
    <div className="dp">
      {done && (
        <div className="dp-success" role="status" data-testid="decision-success">
          <span>✓ {done}</span>
          {props.hasNext && <button className="btn btn-dark btn-sm" onClick={props.onNext} data-testid="next-item">לפריט הבא</button>}
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
const DOC_ACTIONS: { key: DocAction; label: string; testId: string }[] = [
  { key: "accept", label: "קבלת המסמך", testId: "action-accept" },
  { key: "request_correction", label: "החזרה לתיקון", testId: "action-correction" },
  { key: "escalate", label: "העברה לבירור", testId: "action-escalate" },
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
  const [mode, setMode] = useState<DocAction | null>(null);
  const b = item.banker;
  const can = (a: DocAction) => b.allowed_actions.includes(a) && !readOnly;
  const borrower = ws.case.borrowers.find((x) => x.borrower_id === item.borrower_id);
  const periods = ws.borrowers.find((x) => x.borrower_id === item.borrower_id)?.months.map((m) => m.period) || [];
  const run = (action: DocAction, body: Record<string, unknown>): Submit => (rid) =>
    api.decideDocument(ws.case_id, item.document_id, { action, request_id: rid, ...body });
  const primary = primaryDocAction(item);
  const tone = item.attention ? "warn" : item.ai.verdict === "VALID" ? "ok" : "neutral";
  const toggle = (a: DocAction) => setMode(mode === a ? null : a);
  return (<>
    <section className="dp-sec dp-summary" data-testid="ai-summary">
      <div className="dp-head"><span className="dp-title">סיכום בדיקת AI</span><img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="Jeen" /></div>
      <div className={`dp-callout ${tone}`} data-testid="attention">
        {item.ai.attention_he.map((t, i) => <p key={i} className={i === 0 ? "lead" : ""}>{t}</p>)}
      </div>
      <div className="dp-statusline">
        <span className={`status-dot ${VERDICT_TONE[item.ai.verdict || ""] || "neutral"}`} data-testid="ai-verdict">בדיקת AI: {item.ai.verdict_he}</span>
        <span className="sep" aria-hidden>·</span>
        <span className={`status-dot ${BANKER_TONE[b.status]}`} data-testid="banker-status">{b.status_he}</span>
      </div>
      {item.ai.security_flags.length > 0 && <div className="notice small">טקסט חשוד שזוהה במסמך (לא בוצע): {item.ai.security_flags[0]}</div>}
    </section>
    <DocumentStatus item={item} />
    {b.allowed_actions.length > 0 && (
      <section className="dp-sec dp-decide" data-testid="decision-actions">
        <div className="dp-label">ההחלטה שלך על המסמך</div>
        {primary && (() => {
          const a = DOC_ACTIONS.find((x) => x.key === primary)!;
          return <button className={`act-primary${mode === a.key ? " on" : ""}`} disabled={!can(a.key)} onClick={() => toggle(a.key)} data-testid={a.testId}>{a.label}</button>;
        })()}
        <div className="act-secondary-row">
          {DOC_ACTIONS.filter((a) => a.key !== primary).map((a) => (
            <button key={a.key} className={`act-secondary${mode === a.key ? " on" : ""}`} disabled={!can(a.key)} onClick={() => toggle(a.key)}
              data-testid={a.testId}>{a.label}</button>
          ))}
        </div>
        {b.blocked_accept_he && <div className="tiny muted">{b.blocked_accept_he}</div>}
        {mode === "accept" && <AcceptForm item={item} onCancel={() => setMode(null)}
          submit={(rationale) => run("accept", { rationale, acknowledged_finding_ids: b.acknowledge_finding_ids })}
          onDone={(r) => finish(r, "המסמך התקבל לשלב בדיקת המסמכים. זו אינה החלטת אשראי ואינה משנה את שלב הבקשה בבנק.")} />}
        {mode === "request_correction" && <CustomerRequestForm from={ws.case.banker.name_he} draft={item.draft} periods={periods} onCancel={() => setMode(null)}
          title={(p) => p ? `נדרש תלוש ${monthHe(p)} — ${borrower?.first_name_he || ""}` : `נדרש תלוש מתוקן במקום ${item.filename} — ${borrower?.first_name_he || ""}`}
          submitLabel="שמירה והצגה ללקוח באפליקציה" testId="correction-form"
          submit={(message, period, rationale) => run("request_correction", { customer_message: message, requested_period: period || null, rationale })}
          onDone={(r) => finish(r, NOT_SENT)} />}
        {mode === "escalate" && <RationaleForm label="מה דורש בירור?" submitLabel="העברה לבירור" required testId="escalate-form"
          note="המסמך יישאר אצלך בקבוצת ״בבירור״. הלקוח אינו מקבל בקשה."
          submit={(rationale) => run("escalate", { rationale })} onCancel={() => setMode(null)}
          onDone={(r) => finish(r, "המסמך הועבר לבירור.")} />}
        {!mode && can("accept") && <BulkAccept item={item} ws={ws} finish={finish} />}
      </section>
    )}
    <Criteria item={item} />
    <FindingsList findings={item.findings} ws={ws} readOnly={readOnly} finish={finish} showEvidence={showEvidence} />
    {/* a correction request still open can be withdrawn here; the document then returns to the banker's decision */}
    {item.requests.filter((r) => r.status === "OPEN").map((r) => (
      <OpenRequest key={r.customer_request_id} r={r} ws={ws} staff={staff} readOnly={readOnly} finish={finish} />))}
    <RequestsList requests={item.requests.filter((r) => r.status !== "OPEN")} />
    <div className="dp-footer">
      {item.history.length > 0 && <Expand label={`היסטוריית החלטות (${item.history.length})`} defaultOpen={DECIDED.includes(b.status)}>
        <HistoryList entries={item.history} bare /></Expand>}
      {!readOnly && <NoteForm submit={(text) => (rid) => api.addNote(ws.case_id, { text, document_id: item.document_id, request_id: rid })} finish={finish} />}
      <Expand label="פרטים טכניים (רובריקה, מודל, הרצה)" testId="technical-details">
        <TechList rows={[["רובריקה", item.ai.technical.rubric], ["מזהה הרצה", item.ai.technical.run_id], ["ספק בדיקה", item.ai.technical.provider],
          ["מודלים", item.ai.technical.models ? Object.entries(item.ai.technical.models).map(([k, v]) => `${k}: ${v}`).join(" · ") : null],
          ["גרסת פרומפט", item.ai.technical.prompt_version], ["הסתיים", item.ai.technical.finished_at],
          ["קודי סיבה", (item.ai.technical.verdict_reason_codes || []).join(", ") || "—"], ["SHA-256", item.ai.technical.sha256],
          ["שגיאה", item.ai.technical.error]]} />
        {[...item.ai.criteria_failed, ...item.ai.criteria_uncertain, ...item.ai.criteria_passed, ...item.ai.criteria_na].map((c) => (
          <div key={c.criterion_id} className="tiny ltr-row"><span className="ltr">{c.criterion_id} · {c.outcome} · {c.decided_by}{c.reason_code ? ` · ${c.reason_code}` : ""}</span> — {c.title_he}</div>
        ))}
        {item.ai.summary_he && <div className="tiny muted" style={{ marginTop: 6 }}>סיכום המודל: {item.ai.summary_he}</div>}
        {item.ai.limitations_he.map((l, i) => <div key={i} className="tiny muted">• {l}</div>)}
        {item.ai.uncertainty_he.map((l, i) => <div key={`u${i}`} className="tiny muted">? {l}</div>)}
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
  if (peers.length < 2) return null;
  const clean = sig === "clean";
  const reason = clean ? "בדיקת ה-AI תקינה וללא ממצאים" : peers[0].findings.find((f) => f.status === "open" && f.review_state === "NEEDS_BANKER_REVIEW")?.title_he;
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
    if (last) finish({ ...last, duplicate: false }, `${chosen.length - failed.length} מסמכים התקבלו לשלב בדיקת המסמכים, כל אחד כהחלטה נפרדת ביומן.`);
  };
  return (
    <div className="bulk" data-testid="bulk-accept">
      {!open ? <button className="link tiny subtle" onClick={() => setOpen(true)} data-testid="bulk-open" title={reason}>
        קבלה מרוכזת · {peers.length} מסמכים באותו מצב</button> : (
        <div className="dp-form">
          <div className="small bold">קבלה מרוכזת · {reason}</div>
          {peers.map((p) => (
            <label key={p.document_id} className="bulk-row">
              <input type="checkbox" checked={picked.has(p.document_id)} onChange={(e) => {
                const next = new Set(picked); if (e.target.checked) next.add(p.document_id); else next.delete(p.document_id); setPicked(next);
              }} />
              <span>{p.title_he}</span><span className="ltr tiny muted">{p.filename}</span>
            </label>
          ))}
          <label className="dp-field">נימוק פנימי {clean ? <span className="muted">(רשות)</span> : <span className="warn-text">(חובה — נרשם בכל אחד מהמסמכים)</span>}
            <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="bulk-rationale" /></label>
          <div className="dp-disclaimer">כל מסמך נרשם כהחלטה נפרדת עם הנימוק, הזהות והשעה. זו קבלה לשלב בדיקת המסמכים בלבד — אינה אישור משכנתא ואינה משנה את שלב הבקשה בבנק.</div>
          {error && <div className="dp-err" role="alert">{error}</div>}
          <div className="row"><button className="btn btn-dark btn-sm" disabled={busy || !picked.size || (!clean && !rationale.trim())} onClick={go}
            data-testid="bulk-submit">{busy && <span className="spinner" />}קבלת {picked.size} המסמכים</button>
            <button className="btn btn-soft btn-sm" onClick={() => setOpen(false)}>ביטול</button></div>
        </div>
      )}
    </div>
  );
}

function DocumentStatus({ item }: { item: DocItem }) {
  const d = item.banker.decision;
  const open = item.requests.find((r) => r.status === "OPEN" && r.document_id === item.document_id);
  switch (item.banker.status) {
    case "ACCEPTED":
      return <div className="dp-state ok" data-testid="document-state">התקבל על ידי {d?.actor_name} <When at={d?.created_at} />
        {d?.rationale && <div className="tiny muted">נימוק פנימי: {d.rationale}</div>}
        <div className="tiny muted">בשלב בדיקת המסמכים בלבד — אינו אישור משכנתא.</div></div>;
    case "CORRECTION_REQUESTED":
      return <div className="dp-state warn" data-testid="document-state">הוחזר לתיקון · ממתין ללקוח <When at={d?.created_at} by={d?.actor_name} />
        {open && <blockquote className="dp-quote">{open.message_he}</blockquote>}</div>;
    case "ESCALATED":
      return <div className="dp-state info" data-testid="document-state">בבירור <When at={d?.created_at} by={d?.actor_name} />
        {d?.rationale && <div className="tiny">{d.rationale}</div>}</div>;
    case "REPLACED":
      return <div className="dp-state neutral" data-testid="document-state">הלקוח העלה מסמך חלופי: <span className="ltr">{item.replaced_by?.filename}</span>. ההחלטה הבאה היא על המסמך החדש.</div>;
    case "AWAITING_CUSTOMER_FIX":
      return <div className="dp-state warn" data-testid="document-state">בדיקת ה-AI מצאה בעיה שהלקוח מתבקש לתקן, והלקוח רואה אותה באפליקציה. אפשר להוסיף בקשה אישית או להעביר לבירור.</div>;
    case "PROCESSING":
      return <div className="dp-state neutral" data-testid="document-state"><span className="spinner" /> ה-AI עדיין בודק את המסמך. אין מה להחליט עדיין.</div>;
    case "FAILED":
      return <div className="dp-state bad" data-testid="document-state">עיבוד ה-AI נכשל. אפשר לבקש מהלקוח להעלות את הקובץ שוב.</div>;
    default:
      return null;
  }
}

function Criteria({ item }: { item: DocItem }) {
  const bad = [...item.ai.criteria_failed, ...item.ai.criteria_uncertain];
  const passed = item.ai.criteria_passed;
  if (!bad.length && !passed.length) return null;
  return (
    <section className="dp-sec">
      <div className="dp-label">קריטריונים</div>
      {bad.map((c) => (
        <div key={c.criterion_id} className={`crit2 ${c.outcome}`}><span className="crit2-mark" aria-hidden>{c.outcome === "FAIL" ? "✕" : "?"}</span>
          <div><div className="small bold">{c.title_he}</div><div className="tiny muted">{c.explanation_he}</div></div></div>
      ))}
      {passed.length > 0 && (
        <Expand label={`${passed.length} קריטריונים עברו${item.ai.criteria_na.length ? ` · ${item.ai.criteria_na.length} לא רלוונטיים` : ""}`}>
          {passed.map((c) => <div key={c.criterion_id} className="crit2 PASS"><span className="crit2-mark" aria-hidden>✓</span>
            <div><div className="small">{c.title_he}</div><div className="tiny muted">{c.explanation_he}</div></div></div>)}
        </Expand>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- findings
function FindingsList({ findings, ws, readOnly, finish, showEvidence }: { findings: DeskFinding[]; ws: Workspace;
  readOnly: boolean; finish: (r: DeskResult, t: string) => void; showEvidence: (f: Focus) => void }) {
  if (!findings.length) return null;
  const open = findings.filter((f) => f.status === "open" && f.review_state !== "INFO");
  const info = findings.filter((f) => f.status === "open" && f.review_state === "INFO");
  const closed = findings.filter((f) => f.status !== "open");
  return (
    <section className="dp-sec">
      <div className="dp-label">ממצאי ה-AI במסמך{open.length ? ` (${open.length} פתוחים)` : ""}</div>
      {open.map((f) => <FindingRow key={f.finding_id} f={f} ws={ws} readOnly={readOnly} finish={finish} showEvidence={showEvidence} />)}
      {!open.length && !info.length && <div className="tiny muted">אין ממצאים פתוחים במסמך.</div>}
      {info.length > 0 && <Expand label={`לידיעה (${info.length})`}>
        {info.map((f) => <FindingRow key={f.finding_id} f={f} ws={ws} readOnly={readOnly} finish={finish} showEvidence={showEvidence} />)}</Expand>}
      {closed.length > 0 && <Expand label={`${closed.length} ממצאים סגורים`}>
        {closed.map((f) => <FindingRow key={f.finding_id} f={f} ws={ws} readOnly showEvidence={showEvidence} finish={finish} />)}</Expand>}
    </section>
  );
}

function FindingRow({ f, ws, readOnly, finish, showEvidence }: { f: DeskFinding; ws: Workspace; readOnly: boolean;
  finish: (r: DeskResult, t: string) => void; showEvidence: (f: Focus) => void }) {
  const [dismissing, setDismissing] = useState(false);
  return (
    <div className={`dfind ${f.review_state}${f.status !== "open" ? " closed" : ""}`} data-testid="desk-finding" data-code={f.code}>
      <div className="row between"><span className="small bold">{f.title_he}</span>
        <Chip tone={f.status !== "open" ? "neutral" : f.review_state === "CUSTOMER_ACTION_REQUIRED" ? "warn" : f.review_state === "INFO" ? "neutral" : "navy"}>
          {f.status === "open" ? f.review_state_he : f.status_he}</Chip></div>
      <div className="small dfind-msg">{f.message_he}</div>
      {f.statements.map((s, i) => <div key={i} className="notice small" style={{ marginTop: 6 }}>הסבר הלקוח ({s.channel === "voice" ? "בקול" : "בצ׳אט"}, לא מאומת): {s.text}</div>)}
      {f.not_reproduced && <div className="tiny muted">הבדיקה האחרונה אינה משחזרת ממצא זה — הוא נשאר פתוח עד להכרעתך.</div>}
      <div className="row wrap" style={{ marginTop: 4 }}>
        {f.evidence.map((e) => (
          <button key={e.evidence_id} className="ev-link" onClick={() => showEvidence({ documentId: e.document_id, field: e.field, page: e.page })}
            data-testid="show-evidence">הצג במסמך: {e.label_he} · עמ׳ {e.page}{e.verified ? "" : " (לא אומת)"}</button>
        ))}
        {f.can_dismiss && !readOnly && !dismissing && <button className="link tiny subtle" onClick={() => setDismissing(true)} data-testid="dismiss-finding">דיווח על טעות בזיהוי ה־AI</button>}
      </div>
      {dismissing && <DismissForm finding={f} ws={ws} onCancel={() => setDismissing(false)} finish={finish}
        impact={["הממצא יסומן כטעות בזיהוי של ה-AI ויתועד ביומן לבקרת איכות.", "זו אינה החלטה על המסמך: הוא נשאר ממתין להחלטתך.",
          "הממצא לא ייפתח מחדש, כי הקובץ עצמו לא משתנה."]}
        customer="הלקוח אינו רואה את הדיווח ואת הנימוק." />}
      {f.history.length > 1 && <details className="tiny muted" style={{ marginTop: 4 }}><summary>היסטוריית הממצא ({f.history.length})</summary>
        {f.history.map((h, i) => <div key={i}><span className="ltr">{h.at?.slice(0, 16).replace("T", " ")}</span> · {h.event}{h.note ? ` · ${h.note}` : ""}</div>)}</details>}
    </div>
  );
}

// ---------------------------------------------------------------- missing document
function MissingPanel({ item, ws, staff, readOnly, finish }: Ctx<MissingItem>) {
  const [open, setOpen] = useState(false);
  const borrower = ws.case.borrowers.find((b) => b.borrower_id === item.borrower_id);
  return (<>
    <section className="dp-sec">
      <div className="dp-label">מסמך חסר</div>
      <div className="row wrap"><Chip tone={item.open_request ? "warn" : "neutral"} testId="missing-status">{item.status_he}</Chip><Chip>{borrower?.name_he}</Chip></div>
      <p className="small">{item.explanation_he}</p>
    </section>
    {item.open_request && <OpenRequest r={item.open_request} ws={ws} staff={staff} readOnly={readOnly} finish={finish} />}
    {item.allowed_actions.includes("request_missing") && !readOnly && (
      <section className="dp-sec dp-decide" data-testid="decision-actions">
        <div className="dp-label">הפעולה שלך</div>
        {!open ? <button className="act-primary" onClick={() => setOpen(true)} data-testid="action-request-missing">בקשת השלמת מסמך</button>
          : <CustomerRequestForm from={ws.case.banker.name_he} draft={item.draft} onCancel={() => setOpen(false)} title={() => `נדרש תלוש ${item.period_he} — ${borrower?.first_name_he || ""}`}
            submitLabel="שמירה והצגה ללקוח באפליקציה" testId="missing-form"
            submit={(message, _p, rationale) => (rid) => api.requestMissing(ws.case_id, { borrower_id: item.borrower_id!, period: item.period,
              customer_message: message, rationale, request_id: rid })}
            onDone={(r) => finish(r, NOT_SENT)} />}
      </section>
    )}
    <RequestsList requests={item.requests.filter((r) => r.status !== "OPEN")} />
    {item.history.length > 0 && <div className="dp-footer"><Expand label={`היסטוריית החלטות (${item.history.length})`} defaultOpen>
      <HistoryList entries={item.history} bare /></Expand></div>}
  </>);
}

// ---------------------------------------------------------------- case-level finding
type FindingMode = "request_missing" | "request_explanation" | "resolve" | "dismiss" | "escalate";
const FINDING_MODES: { key: FindingMode; label: string }[] = [
  { key: "request_missing", label: "בקשת השלמת מסמך" }, { key: "request_explanation", label: "בקשת הסבר / אסמכתה" },
  { key: "resolve", label: "סגירת הבירור לאחר בדיקה" }, { key: "dismiss", label: "דיווח על טעות בזיהוי ה־AI" },
  { key: "escalate", label: "העברה להמשך בירור" },
];

function CaseFindingPanel({ item, ws, staff, readOnly, finish }: Ctx<CaseFindingItem>) {
  const [mode, setMode] = useState<FindingMode | null>(null);
  const f = item.finding;
  const rec = item.recommendation;
  const run = (action: "request_explanation" | "escalate", body: Record<string, unknown>): Submit => (rid) =>
    api.decide(ws.case_id, f.finding_id, { action, request_id: rid, ...body });
  const borrower = ws.case.borrowers.find((b) => b.borrower_id === item.borrower_id);
  const inc = item.income;
  return (<>
    <section className="dp-sec">
      <div className="dp-label">ממצא ברמת התיק</div>
      <div className="row wrap">
        <Chip tone={f.status === "open" ? "navy" : "neutral"}>{f.status === "open" ? f.review_state_he : f.status_he}</Chip>
        {item.escalated && <Chip tone="info">בהמשך בירור</Chip>}
        {inc && inc.basis !== "none" && <Chip tone={item.basis.partial ? "warn" : "ok"} testId="comparison-basis">
          {item.basis.partial ? `השוואה ראשונית · ${item.basis.months_compared.length} מתוך ${item.basis.months_required.length} חודשים` : "השוואה מלאה"}</Chip>}
      </div>
      {!inc && <p className="small">{f.message_he}</p>}
      {inc && <div className={`dp-income ${inc.tone}`} data-testid="income-summary">
        <div className="small bold">{inc.summary_he}</div>
        <div className="tiny muted">{inc.basis_he}. נבדקו: {inc.months_compared_he || "—"}{inc.months_missing?.length ? ` · חסרים: ${inc.months_missing_he}` : ""}.</div>
      </div>}
      {item.reopened_after && <div className="dp-state info" data-testid="reopened-after">נפתח מחדש: הנתונים השתנו מאז ההכרעה הקודמת שלך בממצא זה. ההכרעה הקודמת נשמרה בהיסטוריה.</div>}
    </section>
    <section className="dp-sec" data-testid="customer-said">
      <div className="dp-label">מה הלקוח מסר</div>
      {f.statements.length ? f.statements.map((x, i) => <div key={i} className="notice small">הסבר הלקוח ({x.channel === "voice" ? "בקול" : x.channel === "app" ? "באפליקציה" : "בצ׳אט"}, לא מאומת — אינו ראיה): {x.text} <When at={x.created_at} /></div>)
        : <div className="small muted">לא נמסר הסבר מהלקוח.</div>}
    </section>
    {item.open_request && <OpenRequest r={item.open_request} ws={ws} staff={staff} readOnly={readOnly} finish={finish} />}
    {f.status === "open" && rec && (item.allowed_actions.length === 0 || readOnly) && (
      <section className="dp-sec"><div className="dp-next" data-testid="next-step"><b>{rec.title_he}</b><span>{rec.body_he}</span></div></section>
    )}
    {item.allowed_actions.length > 0 && !readOnly && (
      <section className="dp-sec dp-decide" data-testid="decision-actions">
        <div className="dp-label">ההחלטה שלך</div>
        {f.status === "open" && rec && <div className="dp-next" data-testid="next-step"><b>{rec.title_he}</b><span>{rec.body_he}</span></div>}
        {(() => {
          const lead = FINDING_MODES.find((m) => m.key === rec?.action && item.allowed_actions.includes(m.key));
          const rest = FINDING_MODES.filter((m) => m !== lead && m.key !== "dismiss" && item.allowed_actions.includes(m.key));
          return (<>
            {lead && <button className={`act-primary${mode === lead.key ? " on" : ""}`} onClick={() => setMode(mode === lead.key ? null : lead.key)}
              data-testid={`finding-action-${lead.key}`}>{lead.label}</button>}
            <div className="act-secondary-row">
              {rest.map((m) => <button key={m.key} className={`act-secondary${mode === m.key ? " on" : ""}`} onClick={() => setMode(mode === m.key ? null : m.key)}
                data-testid={`finding-action-${m.key}`}>{m.label}</button>)}
            </div>
            {item.allowed_actions.includes("dismiss") && <button className={`link tiny subtle${mode === "dismiss" ? " on" : ""}`} style={{ alignSelf: "flex-start" }}
              onClick={() => setMode(mode === "dismiss" ? null : "dismiss")} data-testid="finding-action-dismiss">דיווח על טעות בזיהוי ה־AI</button>}
          </>);
        })()}
        {mode === "request_missing" && item.drafts.missing && <MissingMonthsForm item={item} ws={ws} onCancel={() => setMode(null)} finish={finish} />}
        {mode === "request_explanation" && <CustomerRequestForm from={ws.case.banker.name_he} draft={item.drafts.explanation} onCancel={() => setMode(null)}
          title={() => `נדרש הסבר או אסמכתה — ${borrower?.first_name_he || ""}`} submitLabel="שמירה והצגה ללקוח באפליקציה" testId="request-explanation-form"
          note="הלקוח יוכל להשיב בכתב או לצרף מסמך. התשובה תתועד כהסבר לא מאומת, והממצא יישאר פתוח עד להחלטתך."
          submit={(message, _p, rationale) => run("request_explanation", { customer_message: message, rationale })} onDone={(r) => finish(r, NOT_SENT)} />}
        {mode === "resolve" && <ResolveForm item={item} ws={ws} onCancel={() => setMode(null)} finish={finish} />}
        {mode === "dismiss" && <DismissForm finding={f} impact={item.impact.dismiss} customer={item.impact.customer_he} ws={ws}
          onCancel={() => setMode(null)} finish={finish} />}
        {mode === "escalate" && <RationaleForm label="מה דורש המשך בירור?" submitLabel="העברה להמשך בירור" required testId="escalate-finding-form"
          note="הממצא יישאר פתוח בקבוצת ״בבירור״. הלקוח אינו מקבל הודעה." submit={(rationale) => run("escalate", { rationale })}
          onCancel={() => setMode(null)} onDone={(r) => finish(r, "הממצא הועבר להמשך בירור ונשאר פתוח.")} />}
      </section>
    )}
    <RequestsList requests={item.requests.filter((r) => r.status !== "OPEN")} />
    <div className="dp-footer">
    {item.history.length > 0 && <Expand label={`היסטוריית החלטות (${item.history.length})`} defaultOpen={f.status !== "open" || item.escalated}>
      <HistoryList entries={item.history} bare /></Expand>}
    {!readOnly && <NoteForm submit={(text) => (rid) => api.addNote(ws.case_id, { text, finding_id: f.finding_id, request_id: rid })} finish={finish} />}
    <Expand label="פרטים טכניים">
      <TechList rows={[["נוסח הממצא", inc ? f.message_he : null], ["קוד", f.code], ["מפתח", f.key], ["קריטריון", inc?.criterion_id], ["הוכרע על ידי", inc?.decided_by],
        ["הערכת המודל (לא מכריעה)", inc?.model_assessment], ["הסבר המודל", inc?.model_explanation_he]]} />
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
  const go = async () => {
    setBusy(true); setError(null);
    let last: DeskResult | null = null;
    const failed: string[] = [];
    for (const m of months) {
      try { last = await api.requestMissing(ws.case_id, { borrower_id: item.borrower_id!, period: m, customer_message: message.trim(), request_id: ids[m] }); }
      catch (e) { failed.push(`${monthHe(m)}: ${(e as Error).message}`); }
    }
    setBusy(false);
    if (failed.length) setError(failed.join(" · "));
    if (last) finish(last, `נשמרו ${months.length - failed.length} בקשות להשלמת תלושים, והן מוצגות ללקוח באפליקציה. לא נשלחה הודעת SMS או דוא״ל.`);
  };
  return (
    <div className="dp-form" data-testid="request-missing-form">
      <div className="small bold">אילו תלושים לבקש?</div>
      {draft.months.map((m) => (
        <label key={m} className="bulk-row"><input type="checkbox" checked={months.includes(m)}
          onChange={(e) => setMonths(e.target.checked ? [...months, m].sort() : months.filter((x) => x !== m))} /><span>תלוש {monthHe(m)}</span><span /></label>
      ))}
      <label className="dp-field">הודעה ללקוח <span className="muted">טיוטה מוצעת — אפשר לערוך</span>
        <textarea className="note msg" value={message} maxLength={600} onChange={(e) => setMessage(e.target.value)} data-testid="customer-message" /></label>
      <div className="tiny muted">לכל חודש נוצרת בקשה נפרדת עם כפתור העלאה משלה באפליקציה. לא נשלחת הודעת SMS, דוא״ל או התראה.</div>
      {error && <div className="dp-err" role="alert">{error}</div>}
      <div className="row"><button className="btn btn-orange btn-sm" disabled={busy || !months.length || !message.trim()} onClick={go} data-testid="send-request">
        {busy && <span className="spinner" />}שמירה והצגה ללקוח באפליקציה</button>
        <button className="btn btn-soft btn-sm" onClick={onCancel}>ביטול</button></div>
    </div>
  );
}

const RESOLVE_REASONS: { key: string; label: string; hint: string; needsDocs: boolean; needsStatement?: boolean }[] = [
  { key: "verified_with_documents", label: "אומת מול מסמכים בתיק", hint: "סמנו את המסמכים שבדקתם.", needsDocs: true },
  { key: "explanation_supported", label: "הסבר הלקוח נתמך באסמכתה", hint: "הסבר לבדו אינו מספיק — סמנו את המסמך שתומך בו.", needsDocs: true, needsStatement: true },
  { key: "professional_judgment", label: "החלטה מקצועית במסגרת המדיניות", hint: "ללא אסמכתה במסמכים. נדרש נימוק מפורט, והיא נרשמת כהכרעה אנושית.", needsDocs: false },
];
const MIN_OVERRIDE = 15;

function ResolveForm({ item, ws, onCancel, finish }: { item: CaseFindingItem; ws: Workspace; onCancel: () => void;
  finish: (r: DeskResult, t: string) => void }) {
  const [step, setStep] = useState<"edit" | "confirm">("edit");
  const [reason, setReason] = useState<string>(item.has_customer_statement ? "" : "verified_with_documents");
  const [docs, setDocs] = useState<string[]>([]);
  const [rationale, setRationale] = useState("");
  const [ack, setAck] = useState(false);
  const s = useSubmit((r) => finish(r, "הבירור נסגר ונרשם עם הבסיס, המסמכים והנימוק. ללקוח מוצגת רק שורה ניטרלית בעדכונים."));
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
        <div className="small bold">על מה מבוססת סגירת הבירור?</div>
        <div className="reason-list" role="radiogroup">
          {RESOLVE_REASONS.map((r) => {
            const off = !!r.needsStatement && !item.has_customer_statement;
            return (
              <label key={r.key} className={`reason${reason === r.key ? " on" : ""}${off ? " off" : ""}`}>
                <input type="radio" name="resolve-reason" checked={reason === r.key} disabled={off} onChange={() => setReason(r.key)} data-testid={`reason-${r.key}`} />
                <span><b>{r.label}</b><span className="tiny muted">{off ? "לא נמסר הסבר מהלקוח בממצא הזה." : r.hint}</span></span>
              </label>
            );
          })}
        </div>
        {chosen?.needsDocs && (
          <div className="stack" style={{ gap: 4 }} data-testid="evidence-options">
            <div className="small bold">מסמכים תומכים</div>
            {item.evidence_options.map((o) => (
              <label key={o.document_id} className="bulk-row"><input type="checkbox" checked={docs.includes(o.document_id)}
                onChange={(e) => setDocs(e.target.checked ? [...docs, o.document_id] : docs.filter((x) => x !== o.document_id))} />
                <span>{o.period_he || o.filename}{o.net ? ` · נטו ${o.net}` : ""}</span><span className="tiny muted">AI: {o.verdict_he}</span></label>
            ))}
            {!item.evidence_options.length && <div className="tiny muted">אין בתיק מסמכים שנבדקו ללווה הזה.</div>}
          </div>
        )}
        <label className="dp-field">הנימוק שלך <span className="warn-text">(חובה{reason === "professional_judgment" ? " — נימוק מפורט" : ""})</span>
          <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="resolve-rationale" /></label>
        {partial && (
          <label className="partial-ack" data-testid="ack-partial">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
            <span>ההשוואה מבוססת על {item.basis.months_compared.length} מתוך {item.basis.months_required.length} החודשים הנדרשים
              (חסרים {item.income?.months_missing_he || item.months_to_request_he}). אני מכריע/ה עכשיו על בסיס חלקי.</span>
          </label>
        )}
        <div className="row"><button className="btn btn-dark btn-sm" disabled={!valid} onClick={() => setStep("confirm")} data-testid="resolve-review">המשך לסיכום</button>
          <button className="btn btn-soft btn-sm" onClick={onCancel}>ביטול</button></div>
      </>) : (
        <div className="confirm" data-testid="resolve-confirm">
          <div className="confirm-title">אישור סגירת הבירור</div>
          <dl>
            <dt>הממצא</dt><dd>{item.finding.title_he}</dd>
            <dt>בסיס הסגירה</dt><dd>{chosen?.label}</dd>
            <dt>מסמכים תומכים</dt><dd>{picked.length ? picked.map((o) => `${o.period_he || o.filename}${o.net ? ` (נטו ${o.net})` : ""}`).join(" · ") : "ללא — החלטה מקצועית"}</dd>
            {item.has_customer_statement && <><dt>הסבר הלקוח</dt><dd>מצורף כהקשר בלבד, לא מאומת</dd></>}
            <dt>הנימוק שלך</dt><dd>{rationale.trim()}</dd>
            {partial && <><dt>בסיס הנתונים</dt><dd className="warn-text">חלקי — {item.basis.months_compared.length} מתוך {item.basis.months_required.length} חודשים</dd></>}
          </dl>
          <div className="small bold">מה ישתנה בתיק</div>
          <ul className="dp-list small">{item.impact.resolve.map((l, i) => <li key={i}>{l}</li>)}</ul>
          <div className="small bold">מה הלקוח יראה</div>
          <div className="small">{item.impact.customer_he}</div>
          {s.error && <div className="dp-err" role="alert">{s.error}</div>}
          <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy} onClick={() => s.go(submit)} data-testid="resolve-submit">
            {s.busy && <span className="spinner" />}אישור סגירת הבירור</button>
            <button className="btn btn-soft btn-sm" disabled={s.busy} onClick={() => setStep("edit")}>חזרה לעריכה</button></div>
        </div>
      )}
    </div>
  );
}

const DISMISS_REASONS: [string, string][] = [["misread_document", "הנתון נקרא שגוי מהמסמך"], ["rule_not_applicable", "הכלל אינו חל על המקרה"],
  ["duplicate_finding", "כפילות של ממצא אחר"], ["other", "סיבה אחרת"]];

function DismissForm({ finding, impact, customer, ws, onCancel, finish }: { finding: DeskFinding; impact: string[]; customer: string;
  ws: Workspace; onCancel: () => void; finish: (r: DeskResult, t: string) => void }) {
  const [step, setStep] = useState<"edit" | "confirm">("edit");
  const [reason, setReason] = useState("");
  const [rationale, setRationale] = useState("");
  const s = useSubmit((r) => finish(r, "הדיווח על טעות ה-AI נרשם, והממצא סומן כשגוי."));
  const label = DISMISS_REASONS.find(([k]) => k === reason)?.[1];
  return (
    <div className="dp-form" data-testid="dismiss-form">
      {step === "edit" ? (<>
        <label className="dp-field">מה הטעות בזיהוי ה־AI?
          <select value={reason} onChange={(e) => setReason(e.target.value)} data-testid="dismiss-reason">
            <option value="">בחרו סיבה</option>{DISMISS_REASONS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></label>
        <label className="dp-field">הנימוק שלך <span className="warn-text">(חובה — נימוק מפורט)</span>
          <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="rationale" /></label>
        <div className="tiny muted">דיווח על טעות של ה-AI אינו החלטה על המסמך ואינו בקשה מהלקוח.</div>
        <div className="row"><button className="btn btn-dark btn-sm" disabled={!reason || rationale.trim().length < MIN_OVERRIDE} onClick={() => setStep("confirm")}
          data-testid="dismiss-review">המשך לסיכום</button><button className="btn btn-soft btn-sm" onClick={onCancel}>ביטול</button></div>
      </>) : (
        <div className="confirm" data-testid="dismiss-confirm">
          <div className="confirm-title">אישור דיווח על טעות בזיהוי ה־AI</div>
          <dl><dt>הממצא</dt><dd>{finding.title_he}</dd><dt>סוג הטעות</dt><dd>{label}</dd><dt>הנימוק שלך</dt><dd>{rationale.trim()}</dd></dl>
          <div className="small bold">מה ישתנה בתיק</div>
          <ul className="dp-list small">{impact.map((l, i) => <li key={i}>{l}</li>)}</ul>
          <div className="small bold">מה הלקוח יראה</div><div className="small">{customer}</div>
          {s.error && <div className="dp-err" role="alert">{s.error}</div>}
          <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy} data-testid="confirm-rationale"
            onClick={() => s.go((rid) => api.decide(ws.case_id, finding.finding_id, { action: "dismiss", reason_code: reason, rationale: rationale.trim(), request_id: rid }))}>
            {s.busy && <span className="spinner" />}אישור הדיווח</button>
            <button className="btn btn-soft btn-sm" disabled={s.busy} onClick={() => setStep("edit")}>חזרה לעריכה</button></div>
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
  const required = item.banker.accept_requires_rationale;
  const ack = item.findings.filter((f) => item.banker.acknowledge_finding_ids.includes(f.finding_id));
  return (
    <div className="dp-form" data-testid="accept-form">
      {ack.length > 0 && <div className="small"><b>הממצאים הבאים ייסגרו כ״נבדק והתקבל״ עם הנימוק שלך:</b>
        <ul className="dp-list">{ack.map((f) => <li key={f.finding_id}>{f.title_he}</li>)}</ul></div>}
      <label className="dp-field">נימוק פנימי {required ? <span className="warn-text">(חובה — {ack.length ? "יש ממצאים פתוחים" : "ה-AI לא מצא את המסמך תקין"})</span> : <span className="muted">(רשות)</span>}
        <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="accept-rationale" /></label>
      <div className="dp-disclaimer">קבלת המסמך מסמנת אותו כנבדק בשלב בדיקת המסמכים בלבד. זו אינה החלטת אשראי, אינה אישור המשכנתא ואינה משנה את שלב הבקשה בבנק.</div>
      {s.error && <div className="dp-err" role="alert">{s.error}</div>}
      <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy || (required && !rationale.trim())} onClick={() => s.go(submit(rationale.trim()))}
        data-testid="confirm-accept">{s.busy && <span className="spinner" />}אישור קבלת המסמך</button>
        <button className="btn btn-soft btn-sm" onClick={onCancel}>ביטול</button></div>
    </div>
  );
}

function RationaleForm({ label, submitLabel, required, note, submit, onCancel, onDone, testId }: { label: string; submitLabel: string; required?: boolean;
  note?: string; submit: (rationale: string) => Submit; onCancel: () => void; onDone: (r: DeskResult) => void; testId: string }) {
  const [rationale, setRationale] = useState("");
  const s = useSubmit(onDone);
  return (
    <div className="dp-form" data-testid={testId}>
      <label className="dp-field">{label}<textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="rationale" /></label>
      {note && <div className="tiny muted">{note}</div>}
      {s.error && <div className="dp-err" role="alert">{s.error}</div>}
      <div className="row"><button className="btn btn-dark btn-sm" disabled={s.busy || (required && !rationale.trim())} onClick={() => s.go(submit(rationale.trim()))}
        data-testid="confirm-rationale">{s.busy && <span className="spinner" />}{submitLabel}</button>
        <button className="btn btn-soft btn-sm" onClick={onCancel}>ביטול</button></div>
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
  return (
    <div className="dp-form" data-testid={testId}>
      {step === "edit" ? (<>
        <label className="dp-field">מה הלקוח מתבקש להעלות
          {periods ? (
            <select value={period} onChange={(e) => setPeriod(e.target.value)} data-testid="requested-period">
              <option value="">תלוש מתוקן (ללא חודש מסוים)</option>
              {periods.map((p) => <option key={p} value={p}>תלוש {monthHe(p)}</option>)}
            </select>
          ) : <span className="dp-static">{draft.requested_item_he}</span>}
        </label>
        <label className="dp-field">הודעה ללקוח <span className="muted">טיוטה מוצעת מתוך נתוני הבדיקה — אפשר לערוך</span>
          <textarea className="note msg" value={message} maxLength={600} onChange={(e) => setMessage(e.target.value)} data-testid="customer-message" />
          <span className="tiny muted ltr" style={{ alignSelf: "flex-end" }}>{message.length}/600</span></label>
        <label className="dp-field">נימוק פנימי <span className="muted">(לא מוצג ללקוח, רשות)</span>
          <textarea className="note" value={rationale} onChange={(e) => setRationale(e.target.value)} data-testid="internal-rationale" /></label>
        {note && <div className="tiny muted">{note}</div>}
        <div className="row"><button className="btn btn-dark btn-sm" disabled={!message.trim()} onClick={() => setStep("preview")} data-testid="preview-request">המשך לתצוגה מקדימה</button>
          <button className="btn btn-soft btn-sm" onClick={onCancel}>ביטול</button></div>
      </>) : (<>
        <div className="req-preview" data-testid="request-preview">
          <div className="tiny muted">כך תופיע הבקשה באפליקציית הלקוח</div>
          <div className="req-preview-card">
            <div className="req-preview-from">בקשה מ{from}</div>
            <div className="bold">{title(period)}</div>
            <p className="small">{message.trim()}</p>
            <span className="req-preview-btn">להעלאת המסמך</span>
          </div>
        </div>
        <div className="tiny muted">הבקשה תישמר בתיק ותוצג ללקוח באפליקציה. לא נשלחת הודעת SMS, דוא״ל או התראה.</div>
        {s.error && <div className="dp-err" role="alert">{s.error}</div>}
        <div className="row"><button className="btn btn-orange btn-sm" disabled={s.busy} onClick={() => s.go(submit(message.trim(), period, rationale.trim()))}
          data-testid="send-request">{s.busy && <span className="spinner" />}{submitLabel}</button>
          <button className="btn btn-soft btn-sm" onClick={() => setStep("edit")} disabled={s.busy}>חזרה לעריכה</button></div>
      </>)}
    </div>
  );
}

function NoteForm({ submit, finish }: { submit: (text: string) => Submit; finish: (r: DeskResult, t: string) => void }) {
  const [text, setText] = useState("");
  const [key, setKey] = useState(0);
  const s = useSubmit((r) => { finish(r, "ההערה הפנימית נשמרה."); setText(""); setKey(key + 1); });
  return (
    <Expand label="הערה פנימית" key={key}>
      <textarea className="note" value={text} onChange={(e) => setText(e.target.value)} placeholder="נראית רק לצוות הבנק" data-testid="note-text" />
      {s.error && <div className="dp-err" role="alert">{s.error}</div>}
      <button className="btn btn-ghost btn-sm" style={{ marginTop: 6 }} disabled={s.busy || !text.trim()} onClick={() => s.go(submit(text.trim()))}>שמירת הערה</button>
    </Expand>
  );
}

// ---------------------------------------------------------------- read-only blocks
function OpenRequest({ r, ws, staff, readOnly, finish }: { r: DeskRequest; ws?: Workspace; staff?: string; readOnly?: boolean;
  finish?: (res: DeskResult, t: string) => void }) {
  const [withdrawing, setWithdrawing] = useState(false);
  return (
    <section className="dp-sec">
      <div className="dp-state warn" data-testid="open-request">בקשה פתוחה ללקוח: {r.title_he} <When at={r.created_at} by={r.created_by_name} />
        <blockquote className="dp-quote">{r.message_he}</blockquote>
        {ws && staff && finish && !readOnly && !withdrawing && <button className="link tiny subtle" style={{ alignSelf: "flex-start" }}
          onClick={() => setWithdrawing(true)} data-testid="withdraw-request">ביטול הבקשה…</button>}
      </div>
      {withdrawing && ws && staff && finish && <RationaleForm label="למה לבטל את הבקשה?" submitLabel="ביטול הבקשה ללקוח" required testId="withdraw-form"
        note="הבקשה תרד מהאפליקציה של הלקוח, והביטול יירשם ביומן. הממצא עצמו לא משתנה."
        submit={(rationale) => (rid) => api.withdrawRequest(ws.case_id, r.customer_request_id, { rationale, request_id: rid })}
        onCancel={() => setWithdrawing(false)} onDone={(res) => finish(res, "הבקשה בוטלה והוסרה מהאפליקציה של הלקוח.")} />}
    </section>
  );
}

function RequestsList({ requests }: { requests: DeskRequest[] }) {
  if (!requests.length) return null;
  return (
    <section className="dp-sec">
      <div className="dp-label">בקשות ללקוח</div>
      {requests.map((r) => (
        <div key={r.customer_request_id} className="dreq" data-testid="request-row">
          <div className="row between"><span className="small bold">{r.title_he}</span><Chip tone={r.status === "OPEN" ? "warn" : "ok"}>{r.status_he}</Chip></div>
          <div className="tiny muted">{r.message_he}</div>
          <When at={r.responded_at || r.created_at} by={r.created_by_name} />
        </div>
      ))}
    </section>
  );
}

function HistoryList({ entries, bare = false }: { entries: Decision[]; bare?: boolean }) {
  if (!entries.length) return null;
  return (
    <section className={bare ? "dp-hist" : "dp-sec"} data-testid="decision-history">
      {!bare && <div className="dp-label">היסטוריית החלטות</div>}
      {entries.map((d) => (
        <div key={d.decision_id} className="hist">
          <div className="small"><b>{d.action_he}</b> · {d.actor_name} · <span className="ltr">{d.created_at.slice(0, 16).replace("T", " ")}</span></div>
          {d.previous_status !== d.new_status && <div className="tiny muted">{STATUS_WORD[d.previous_status || ""] || d.previous_status || "—"} ← {STATUS_WORD[d.new_status || ""] || d.new_status}</div>}
          {d.rationale && <div className="tiny">נימוק פנימי: {d.rationale}</div>}
          {d.customer_message && <div className="tiny">הודעה ללקוח: {d.customer_message}</div>}
          {d.evidence_refs.length > 0 && <div className="tiny muted">ראיות שתועדו: {d.evidence_refs.map((e) => e.field).join(", ")}</div>}
        </div>
      ))}
    </section>
  );
}

function TechList({ rows }: { rows: [string, ReactNode][] }) {
  return <div className="tech-list">{rows.filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) =>
    <div key={k} className="tiny"><span className="muted">{k}: </span><span className="ltr">{v}</span></div>)}</div>;
}
