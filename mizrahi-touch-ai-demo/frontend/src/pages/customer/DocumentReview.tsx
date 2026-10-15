import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, customerVerdict, monthHe, OUTCOME_HE, timeHe, usePolling } from "../../api";
import { useCase } from "../../caseContext";
import { EvidenceViewer, FactList } from "../../components/EvidenceViewer";
import { IChevron, ISpark } from "../../components/Icons";

export const OUTCOME_TONE: Record<string, string> = { PASS: "ok", ACCEPTED: "ok", CONFIRMED: "ok", REVIEW: "warn", BLOCKER: "bad",
  NOT_COMPLETED: "bad", REPLACED: "info", INCOMPLETE: "warn", AWAITING_UPLOAD: "info" };

export function DocumentReview() {
  const { id } = useParams();
  const nav = useNavigate();
  const { openAssistant, openUpload, snap, caseId } = useCase();
  // polled like the rest of the app (fast while the review runs): banker decisions and requests appear without a reload
  const polled = usePolling(() => api.document(id!), [id], (d) => d.status !== "reviewed" && d.status !== "failed");
  const doc = polled.data && polled.data.document_id === id ? polled.data : null;
  const [focus, setFocus] = useState<string | null>(null);
  const findingId = useSearchParams()[0].get("finding");
  useEffect(() => {
    if (doc && findingId) document.getElementById(`finding-${findingId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [doc?.document_id, findingId]);
  if (!doc) return polled.error ? (
    <div className="notice" style={{ marginTop: 16 }} data-testid="foreign-document">
      המסמך אינו זמין בתיק הפעיל שלכם.{" "}
      <button className="link" onClick={() => nav("/customer/documents")}>למסמכים של התיק הפעיל</button>
    </div>
  ) : <div className="page-sub" style={{ marginTop: 40, textAlign: "center" }}><span className="spinner" /></div>;
  if (doc.case_id !== caseId) {
    return (
      <div className="notice" style={{ marginTop: 16 }} data-testid="foreign-document">
        המסמך הזה שייך לתיק אחר, ולכן אינו מוצג בתיק הפעיל.{" "}
        <button className="link" onClick={() => nav("/customer/documents")}>למסמכים של התיק הפעיל</button>
      </div>
    );
  }
  const r = doc.review;
  const borrower = snap?.case.borrowers.find((b) => b.borrower_id === doc.borrower_id);
  const openFindings = doc.findings.filter((f) => f.status === "open");
  const asked = snap?.customer_requests?.find((q) => q.status === "OPEN" && q.document_id === doc.document_id);
  const needsAction = openFindings.some((f) => f.review_state === "CUSTOMER_ACTION_REQUIRED") || !!asked;
  // while the set is re-checked a document's route can still change (an income gap is found only then)
  const settling = !r || (snap?.readiness.pending_jobs.length ?? 0) > 0;
  const outcome = doc.outcome && !settling ? doc.outcome : null;
  const aiBlocker = !asked && outcome?.outcome === "BLOCKER" && outcome.by === "ai";
  return (
    <>
      <button className="link" style={{ textDecoration: "none", marginTop: 8, display: "flex", alignItems: "center", gap: 2 }} onClick={() => nav("/customer/documents")}>
        <span style={{ transform: "scaleX(-1)", display: "inline-flex" }}><IChevron size={16} /></span>חזרה למסמכים
      </button>
      <div className="page-title" style={{ fontSize: 18, direction: "ltr", textAlign: "right" }}>{doc.filename}</div>
      <div className="row" style={{ flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
        {r ? <span className={`badge ${customerVerdict(r.verdict, outcome ?? undefined).cls}`} data-testid="review-verdict">
          {customerVerdict(r.verdict, outcome ?? undefined).text}</span> : <span className="badge neutral"><span className="spinner" />{doc.stage_he}</span>}
        {r && <span className="badge neutral">{r.doc_type_he}</span>}
        {borrower && <span className="badge neutral">הועלה עבור {borrower.first_name_he}</span>}
        {r?.period && <span className="badge info">מודפס: {monthHe(r.period)}</span>}
        {r?.is_scanned && <span className="badge warn">סריקה</span>}
      </div>
      {outcome && outcome.outcome !== "IN_PROGRESS" && (
        <div className={`doc-outcome ${OUTCOME_TONE[outcome.outcome] || "info"}`} data-testid="document-outcome" data-outcome={outcome.outcome}>
          {outcome.label_he}
        </div>
      )}
      {asked && (
        <div className="creq-card open" data-testid="document-request">
          <div className="creq-from">בקשה מ{asked.created_by_name || snap?.case.banker.name_he}</div>
          <div className="creq-title">{asked.title_he}</div>
          <div className="creq-msg">{asked.message_he}</div>
          <button className="btn btn-orange creq-btn" onClick={() => openUpload(asked.borrower_id || undefined,
            { requirementCode: asked.requirement_code || undefined, period: asked.period, customerRequestId: asked.customer_request_id })}>להעלאת המסמך</button>
        </div>
      )}
      {!asked && doc.banker_status && <div className="notice navy" style={{ marginBottom: 10 }} data-testid="document-banker-status">{doc.banker_status.status_he}.
        {doc.banker_status.status === "ACCEPTED" ? " זו בדיקת מסמכים בלבד ואינה אישור ההלוואה." : ""}</div>}
      {r?.file_name_period && r.period && r.file_name_period !== r.period && (
        <div className="notice" style={{ marginBottom: 10 }}>שם הקובץ מציין <b>{monthHe(r.file_name_period)}</b>, אבל במסמך עצמו מודפס <b>{monthHe(r.period)}</b>. הבדיקה מסתמכת על התוכן.</div>
      )}
      {r && (<>
        <EvidenceViewer documentId={doc.document_id} facts={r.facts} focus={focus} onFocus={setFocus} />
        <div className="card" style={{ marginTop: 12 }}>
          <div className="row between"><div className="card-title">מה קראנו מהמסמך</div><span className="tiny muted">לחצו על שורה לסימון במסמך</span></div>
          <FactList facts={r.facts} focus={focus} onFocus={(f) => setFocus(focus === f ? null : f)} />
          <div className="jeen-by" style={{ marginTop: 10 }}><img src="/brand/jeen-mark.png" alt="" />חולץ ונבדק באמצעות JEEN</div>
        </div>
        <div className="card">
          <div className="row between"><div className="card-title">הבדיקה לפי הרובריקה</div><span className="tiny muted ltr">{r.rubric_id}@{r.rubric_version}</span></div>
          {r.summary_he && <div className="small" style={{ margin: "6px 0 4px", lineHeight: 1.6 }}>{r.summary_he}</div>}
          {r.criteria.map((c) => (
            <div className="crit" key={c.criterion_id}>
              <span className={`badge ${c.outcome}`}>{OUTCOME_HE[c.outcome]}</span>
              <div>
                <div className="bold small" style={{ color: "var(--mz-ink)" }}>{c.title_he} <span className="crit-id">{c.criterion_id} · {c.decided_by === "judge" ? "שופט LLM" : c.decided_by === "code" ? "כלל דטרמיניסטי" : "כלל + שופט"}</span></div>
                <div className="small muted" style={{ lineHeight: 1.55 }}>{c.explanation_he}</div>
              </div>
            </div>
          ))}
        </div>
      </>)}
      {openFindings.length > 0 && (<>
        <div className="section-label">ממצאים הקשורים למסמך</div>
        {openFindings.map((f) => (
          <div key={f.finding_id} id={`finding-${f.finding_id}`} className={`finding ${f.review_state}${f.finding_id === findingId ? " focus" : ""}`}>
            <div className="finding-title">{f.title_he}</div>
            <div className="finding-msg">{f.message_he}</div>
            <div className="tiny muted" style={{ marginTop: 4 }}>{f.review_state === "CUSTOMER_ACTION_REQUIRED" ? "לטיפולכם" : f.review_state === "NEEDS_BANKER_REVIEW" ? "בבדיקת הבנקאית" : "לידיעה"}</div>
          </div>
        ))}
      </>)}
      <div className="card">
        <div className="card-title">מה עושים עכשיו?</div>
        <div className="small" style={{ margin: "6px 0 10px", lineHeight: 1.6 }}>
          {!r ? "הבדיקה עדיין רצה, התוצאה תופיע כאן אוטומטית." : needsAction ? "יש פריט שמחכה לכם. אפשר להעלות מסמך מתוקן, הבדיקה תרוץ מחדש על כל סט המסמכים." :
            r.verdict === "VALID" ? "אין צורך בפעולה מצדכם לגבי מסמך זה. הבנקאית תעבור עליו." : "המסמך הועבר לבדיקת הבנקאית. אם יידרש משהו, נעדכן."}
        </div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          {needsAction && <button className="btn btn-dark" data-testid="document-replace" onClick={() => openUpload(doc.borrower_id || undefined, asked
            ? { requirementCode: asked.requirement_code || undefined, period: asked.period, customerRequestId: asked.customer_request_id }
            : { requirementCode: doc.requirement_code || undefined, replacesDocumentId: aiBlocker ? doc.document_id : undefined })}>
            {aiBlocker ? "העלאת מסמך חלופי" : "להעלאת מסמך מתוקן"}</button>}
          {aiBlocker && <button className="btn btn-soft" data-testid="document-dispute"
            onClick={() => openAssistant(`אני חושב שהמסמך ${doc.filename} כן מתאים לדרישה. אבקש שהבנקאית תבדוק אותו.`)}>המסמך כן נכון? פנייה לבנקאית</button>}
          <button className="btn btn-soft" onClick={() => openAssistant(`תסביר לי את תוצאת הבדיקה של ${doc.filename}`)}><ISpark size={12} />שאלו את העוזר על המסמך</button>
        </div>
      </div>
      {r && (
        <details className="card small">
          <summary className="bold" style={{ cursor: "pointer", color: "var(--mz-ink)" }}>פרטי ההרצה והמגבלות</summary>
          <div className="kv"><span>עיבוד המסמך</span><span className="ltr">JEEN · {r.identity.mode}</span></div>
          <div className="kv"><span>מזהה הרצה</span><span className="ltr">{r.run_id}</span></div>
          <div className="kv"><span>הסתיים</span><span className="ltr">{timeHe(r.finished_at)}</span></div>
          <div className="kv"><span>קריאות מודל / טוקנים</span><span className="ltr">{r.usage.llm_calls} / {(r.usage.prompt_tokens || 0) + (r.usage.output_tokens || 0)}</span></div>
          {r.limitations_he.map((l, i) => <div key={i} className="tiny muted" style={{ marginTop: 6 }}>• {l}</div>)}
          {r.uncertainty_he.map((l, i) => <div key={`u${i}`} className="tiny muted" style={{ marginTop: 4 }}>? {l}</div>)}
          <div className="tiny muted" style={{ marginTop: 6 }}>היסטוריה: {doc.runs.length} הרצות למסמך זה.</div>
        </details>
      )}
    </>
  );
}
