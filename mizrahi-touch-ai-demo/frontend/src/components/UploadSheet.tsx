import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, monthHe, VERDICT_HE, type AppAction, type DocView, type UploadOutcome } from "../api";
import { useCase } from "../caseContext";
import { OUTCOME_TONE } from "../pages/customer/DocumentReview";
import { ActionList } from "./AssistantActions";
import { ICheck, IClose, IUpload } from "./Icons";

const STAGES: [string, string][] = [["intake", "קליטה וזיהוי הקובץ"], ["extract", "קריאה וחילוץ (Gemini)"], ["verify_evidence", "אימות כל ערך מול הקובץ"],
  ["deterministic_checks", "בדיקות כללים"], ["judge", "שיפוט לפי רובריקה (LLM-as-a-Judge)"], ["done", "הבדיקה הושלמה"]];

type UploadAction = Extract<AppAction, { type: "NAVIGATE_TO_DOCUMENT_UPLOAD" }>;

export function UploadSheet() {
  const { snap, docs, caseId, upload, closeUpload, reload, openAssistant, assistantOrigin } = useCase();
  const nav = useNavigate();
  const target = (bid: string) => snap?.available_actions?.find((a): a is UploadAction =>
    a.type === "NAVIGATE_TO_DOCUMENT_UPLOAD" && a.params.borrower_id === bid);
  const monthsFor = (bid: string) => {
    const t = target(bid);
    return t ? (t.params.missing_periods.length ? t.params.missing_periods : t.params.period ? [t.params.period] : []) : [];
  };
  const firstBorrower = upload.borrowerId || snap?.case.borrowers[0]?.borrower_id || "";
  const asked = snap?.customer_requests?.find((q) => q.customer_request_id === upload.customerRequestId && q.status === "OPEN");
  const [borrower, setBorrower] = useState(firstBorrower);
  const [period, setPeriod] = useState<string | null>(() => {
    const months = monthsFor(firstBorrower);
    return upload.period && months.includes(upload.period) ? upload.period : months.length === 1 ? months[0] : null;
  });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [answered, setAnswered] = useState(false);
  const [doc, setDoc] = useState<DocView | null>(null);
  const [outcome, setOutcome] = useState<UploadOutcome | null>(null);
  const [outcomeLost, setOutcomeLost] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const months = monthsFor(borrower);
  const requirement = snap?.readiness.requirements.find((r) => r.evaluated_by_ai && r.borrower_id === borrower);
  // a document the AI review sent back to this borrower: the new upload replaces it (the old one stays in the history)
  const rejected = docs.filter((d) => d.borrower_id === borrower && snap?.outcomes?.documents[d.document_id]?.outcome === "BLOCKER"
    && snap.outcomes.documents[d.document_id].by === "ai");
  const presetReplace = upload.replacesDocumentId && rejected.some((d) => d.document_id === upload.replacesDocumentId)
    ? upload.replacesDocumentId : undefined;
  const replaceTarget = asked ? undefined : presetReplace ? rejected.find((d) => d.document_id === presetReplace)
    : rejected.length === 1 ? rejected[0] : undefined;
  const [replaceOn, setReplaceOn] = useState(true);
  const reviewed = doc?.status === "reviewed" || doc?.status === "failed";
  const fromChat = !!assistantOrigin;

  useEffect(() => {
    if (!doc || doc.status === "reviewed" || doc.status === "failed") return;
    const t = window.setInterval(async () => {
      const d = await api.document(doc.document_id);
      setDoc(d);
      if (d.status === "reviewed" || d.status === "failed") reload();
    }, 1000);
    return () => window.clearInterval(t);
  }, [doc, reload]);

  useEffect(() => {
    if (!doc || !reviewed || outcome?.phase === "complete" || outcomeLost) return;
    let alive = true;
    let timer = 0;
    let failures = 0;
    const tick = async () => {
      const o = await api.uploadOutcome(caseId, doc.document_id).catch(() => null);
      if (!alive) return;
      failures = o ? 0 : failures + 1;
      if (o) setOutcome(o);
      if (o?.phase === "complete") reload();
      else if (failures >= 3) setOutcomeLost(true);
      else timer = window.setTimeout(tick, 1500);
    };
    tick();
    return () => { alive = false; window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc?.document_id, reviewed, outcome?.phase, outcomeLost, caseId]);

  const choose = (bid: string) => {
    setBorrower(bid);
    const m = monthsFor(bid);
    setPeriod(m.length === 1 ? m[0] : null);
  };
  const submit = async () => {
    if (!file || !borrower) return;
    setBusy(true); setError(null);
    try {
      const forRequest = asked && (!asked.borrower_id || asked.borrower_id === borrower) ? asked : undefined;
      const r = await api.upload(caseId, file, borrower, { requirementCode: requirement?.code, expectedPeriod: period ?? forRequest?.period,
        actionId: assistantOrigin?.actionId, originTurnId: assistantOrigin?.turnId, customerRequestId: forRequest?.customer_request_id,
        replacesDocumentId: !forRequest && replaceTarget && replaceOn ? replaceTarget.document_id : undefined });
      setDoc(r.document); setNote(r.note || null); setAnswered(!!r.answered_request); reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const backToChat = () => { closeUpload(); openAssistant(); };
  const another = () => { setDoc(null); setFile(null); setNote(null); setOutcome(null); setOutcomeLost(false); choose(borrower); };
  const stageIndex = doc ? STAGES.findIndex(([k]) => k === (doc.status === "reviewed" ? "done" : doc.stage)) : -1;
  const monthHint = months.length > 1
    ? (period ? "הבדיקה תסתמך על החודש שמודפס בתלוש, ותתריע אם הוא שונה מהחודש שבחרתם."
      : `חסרים ${months.length} חודשים. מעלים תלוש אחד בכל פעם — בחרו את החודש של הקובץ הזה, או העלו ונזהה אותו מהתלוש.`)
    : `נבחר ${monthHe(months[0])} לפי מה שחסר בתיק. הבדיקה תסתמך על החודש שמודפס בתלוש.`;
  return (
    <div className="sheet-backdrop" onClick={closeUpload}>
      <div className="sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="העלאת מסמך" data-testid="upload-sheet">
        <div className="grabber" />
        <div className="sheet-head"><h3>העלאת מסמך</h3><button className="icon-btn" onClick={closeUpload} aria-label="סגירה"><IClose /></button></div>
        <div className="sheet-body stack">
          {!doc && (<>
            {fromChat && (
              <div className="upload-context" data-testid="upload-from-chat">
                <span>הגעתם מהשיחה עם העוזר — מילאנו מראש את מה שידוע מהתיק.</span>
                <button className="link small" onClick={backToChat}>חזרה לשיחה</button>
              </div>
            )}
            {asked && (
              <div className="upload-request" data-testid="upload-for-request">
                <div className="bold">{asked.title_he}</div>
                <div className="small">{asked.message_he}</div>
                <div className="tiny muted">הקובץ יצורף לבקשה של {asked.created_by_name || snap?.case.banker.name_he} וייבדק שוב.</div>
              </div>
            )}
            <div className="small bold">עבור מי המסמך?</div>
            <div className="choice">
              {snap?.case.borrowers.map((b) => (
                <label key={b.borrower_id} className={borrower === b.borrower_id ? "on" : ""}>
                  <input type="radio" name="borrower" value={b.borrower_id} checked={borrower === b.borrower_id} onChange={() => choose(b.borrower_id)} />
                  <span>{b.first_name_he}</span>
                </label>
              ))}
            </div>
            <div className="upload-kind">
              <span className="small bold">סוג המסמך</span>
              <span className="kind-chip" data-testid="upload-doc-type" data-requirement={requirement?.code}><ICheck size={12} />תלוש שכר</span>
            </div>
            {months.length > 0 && (
              <div className="stack" style={{ gap: 6 }}>
                <div className="small bold">חודש השכר</div>
                <div className="month-pick" role="radiogroup" aria-label="חודש השכר" data-testid="upload-months">
                  {months.map((m) => (
                    <button key={m} type="button" role="radio" aria-checked={period === m} className={`mchip pick${period === m ? " on" : ""}`}
                      onClick={() => setPeriod(period === m ? null : m)} data-period={m}>{monthHe(m)}</button>
                  ))}
                </div>
                <div className="tiny muted" style={{ lineHeight: 1.55 }} data-testid="upload-month-hint">{monthHint}</div>
              </div>
            )}
            {replaceTarget && (
              <div className="upload-replace" data-testid="upload-replaces" data-replaces={replaceTarget.document_id}>
                {presetReplace ? <span aria-hidden>↺</span>
                  : <input type="checkbox" checked={replaceOn} onChange={(e) => setReplaceOn(e.target.checked)} data-testid="upload-replace-toggle"
                    aria-label="המסמך החדש מחליף את המסמך שהוחזר" />}
                <span>המסמך החדש יחליף את <b className="ltr">{replaceTarget.filename}</b>, שנמצא לא מתאים לדרישה. הקובץ הקודם נשמר בהיסטוריה, והבדיקה תרוץ מחדש.</span>
              </div>
            )}
            <div className="dropzone">
              <input ref={input} type="file" accept="application/pdf,image/png,image/jpeg" className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="file-input" />
              <div style={{ color: "var(--mz-orange)" }}><IUpload size={26} /></div>
              <div className="bold" style={{ marginTop: 6 }}>{file ? file.name : "בחרו קובץ PDF או צילום"}</div>
              <div className="tiny muted" style={{ marginTop: 4 }}>עדיף PDF מקורי מהמעסיק · עד 15MB · הבדיקה רצה מיד אחרי ההעלאה</div>
              <button className="btn btn-ghost" style={{ marginTop: 10 }} onClick={() => input.current?.click()}>בחירת קובץ</button>
            </div>
            {error && <div className="notice">{error}</div>}
            <button className="btn btn-orange" disabled={!file || busy} onClick={submit} data-testid="upload-submit">
              {busy ? <span className="spinner" /> : null}העלאה ובדיקה חכמה
            </button>
            <div className="tiny muted" style={{ lineHeight: 1.6 }}>
              המסמך נשמר בתיק ההדגמה בלבד ונבדק על ידי Gemini. התוצאה היא בדיקת מסמך אוטומטית — לא קבלת המסמך על ידי הבנק.
            </div>
          </>)}
          {doc && (<>
            <div className="card tight">
              <div className="doc-name">{doc.filename}</div>
              {note && <div className="notice" style={{ marginTop: 8 }}>{note}</div>}
              {answered && <div className="tiny" style={{ marginTop: 6, color: "var(--ok)", fontWeight: 700 }} data-testid="upload-answered">
                הקובץ צורף לבקשה של {snap?.case.banker.name_he}. אחרי הבדיקה החכמה הוא יחזור אליה לבדיקה.</div>}
              <div className="stage-list" data-testid="upload-stages">
                {STAGES.map(([k, label], i) => (
                  <div key={k} className={`stage-item ${i < stageIndex || doc.status === "reviewed" ? "done" : i === stageIndex ? "now" : ""}`}>
                    <span className="dot" />{label}{i === stageIndex && doc.status !== "reviewed" ? <span className="spinner" /> : null}
                  </div>
                ))}
              </div>
              {doc.status === "failed" && <div className="notice" style={{ marginTop: 8 }}>הבדיקה נכשלה: {doc.error}</div>}
              {doc.review && (
                <div className="row between" style={{ marginTop: 12 }}>
                  <span className={`badge ${doc.review.verdict}`}>{VERDICT_HE[doc.review.verdict]}</span>
                  <button className="btn btn-dark" onClick={() => { closeUpload(); nav(`/customer/documents/${doc.document_id}`); }}>לתוצאות הבדיקה</button>
                </div>
              )}
            </div>
            {reviewed && outcome?.phase !== "complete" && !outcomeLost && (
              <div className="row small muted" data-testid="upload-rechecking"><span className="spinner" />מעדכנים את תמונת מסמכי השכר בתיק…</div>
            )}
            {outcomeLost && <div className="small muted">לא הצלחנו לקבל את סיכום הבדיקה כרגע. המצב המעודכן יופיע במסך המסמכים ובשיחה עם העוזר.</div>}
            {outcome?.phase === "complete" && snap?.outcomes?.documents[doc.document_id] && !snap.readiness.pending_jobs.length && (
              <div className={`doc-outcome ${OUTCOME_TONE[snap.outcomes.documents[doc.document_id].outcome] || "info"}`}
                data-testid="upload-route" data-outcome={snap.outcomes.documents[doc.document_id].outcome}>
                {snap.outcomes.documents[doc.document_id].label_he}
              </div>
            )}
            {outcome?.phase === "complete" && (
              <div className="outcome" data-testid="upload-outcome">
                <div className="outcome-msg">{outcome.message_he}</div>
                <ActionList actions={outcome.actions} testId="upload-outcome-actions" />
              </div>
            )}
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-dark" onClick={backToChat} data-testid="upload-back-to-chat">{fromChat ? "חזרה לשיחה" : "שאלו את העוזר מה הלאה"}</button>
              <button className="btn btn-ghost" onClick={another}>העלאת מסמך נוסף</button>
            </div>
          </>)}
        </div>
      </div>
    </div>
  );
}
