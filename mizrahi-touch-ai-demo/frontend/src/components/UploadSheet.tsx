import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, customerVerdict, FAMILY_EN, FAMILY_HE, monthHe, monthL, type AppAction, type DocView, type Requirement, type UploadOutcome } from "../api";
import { useCase } from "../caseContext";
import { useLang } from "../i18n";
import { OUTCOME_TONE } from "../pages/customer/DocumentReview";
import { reportPresence } from "../presence";
import { ActionList } from "./AssistantActions";
import { ICheck, IClose, IUpload } from "./Icons";

const STAGES: [string, string, string][] = [["intake", "קליטה וזיהוי הקובץ", "Receiving and identifying the file"],
  ["extract", "קריאה וחילוץ הנתונים", "Reading and extracting the data"], ["verify_evidence", "אימות כל ערך מול הקובץ", "Verifying each value against the file"],
  ["deterministic_checks", "בדיקות כללים", "Rule checks"], ["judge", "שיפוט לפי רובריקה (LLM-as-a-Judge)", "Checking against the rubric (LLM-as-a-Judge)"],
  ["done", "הבדיקה הושלמה", "Check complete"]];

type UploadAction = Extract<AppAction, { type: "NAVIGATE_TO_DOCUMENT_UPLOAD" }>;

/** The requirement an upload is for: the preset one, the banker request's, the person's payslips, or the first open one. */
function initialRequirement(reqs: Requirement[], preset?: string, borrowerId?: string, asked?: string | null): string {
  if (preset && reqs.some((r) => r.code === preset)) return preset;
  if (asked && reqs.some((r) => r.code === asked)) return asked;
  const open = (r: Requirement) => !["extracted", "preparation_confirmed"].includes(r.ai_state);
  return (reqs.find((r) => r.family === "payslip" && r.borrower_id === borrowerId && open(r))
    || reqs.find((r) => r.borrower_id === borrowerId && open(r)) || reqs.find(open) || reqs[0])?.code || "";
}

export function UploadSheet() {
  const { snap, docs, caseId, upload, closeUpload, reload, openAssistant, assistantOrigin } = useCase();
  const nav = useNavigate();
  const { en, t } = useLang();
  const reqs = (snap?.readiness.requirements || []).filter((r) => r.evaluated_by_ai || r.intake === "human_review");
  const asked = snap?.customer_requests?.find((q) => q.customer_request_id === upload.customerRequestId && q.status === "OPEN");
  const [code, setCode] = useState(() => initialRequirement(reqs, upload.requirementCode, upload.borrowerId, asked?.requirement_code));
  const requirement = reqs.find((r) => r.code === code);
  const target = (c: string) => snap?.available_actions?.find((a): a is UploadAction =>
    a.type === "NAVIGATE_TO_DOCUMENT_UPLOAD" && a.params.requirement_code === c);
  const monthsFor = (c: string) => {
    const r = reqs.find((x) => x.code === c);
    const t = target(c);
    if (r?.family !== "payslip" || !t) return [];
    return t.params.missing_periods.length ? t.params.missing_periods : t.params.period ? [t.params.period] : [];
  };
  const borrower = requirement?.borrower_id || "";
  const [period, setPeriod] = useState<string | null>(() => {
    const months = monthsFor(code);
    return upload.period && months.includes(upload.period) ? upload.period : months.length === 1 ? months[0] : null;
  });
  // the sheet can open before the case snapshot has arrived (a deep link, or the document page's own fetch winning the
  // race): its requirement is resolved from the preset once the snapshot's requirements are there
  const resolvable = reqs.some((r) => r.code === code);
  useEffect(() => {
    if (resolvable || !reqs.length) return;
    const next = initialRequirement(reqs, upload.requirementCode, upload.borrowerId, asked?.requirement_code);
    const months = monthsFor(next);
    setCode(next);
    setPeriod(upload.period && months.includes(upload.period) ? upload.period : months.length === 1 ? months[0] : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvable, reqs.length]);
  // one chip per document kind; per-person kinds then offer the people who need it
  const kinds = [...new Map(reqs.map((r) => [r.requirement_id || r.family, r])).values()];
  const sameKind = requirement ? reqs.filter((r) => (r.requirement_id || r.family) === (requirement.requirement_id || requirement.family)) : [];
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [noteEn, setNoteEn] = useState<string | null>(null);
  const [answered, setAnswered] = useState(false);
  const [doc, setDoc] = useState<DocView | null>(null);
  const [outcome, setOutcome] = useState<UploadOutcome | null>(null);
  const [outcomeLost, setOutcomeLost] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const months = monthsFor(code);
  // a document the AI review sent back for this requirement: the new upload replaces it (the old one stays in the history)
  const rejected = docs.filter((d) => d.requirement_code === code && snap?.outcomes?.documents[d.document_id]?.outcome === "BLOCKER"
    && snap.outcomes.documents[d.document_id].by === "ai");
  const presetReplace = upload.replacesDocumentId && rejected.some((d) => d.document_id === upload.replacesDocumentId)
    ? upload.replacesDocumentId : undefined;
  const replaceTarget = asked ? undefined : presetReplace ? rejected.find((d) => d.document_id === presetReplace)
    : rejected.length === 1 ? rejected[0] : undefined;
  const [replaceOn, setReplaceOn] = useState(true);
  const reviewed = doc?.status === "reviewed" || doc?.status === "failed";
  // a family without a review rubric: the file is kept for the banker, there is no AI result to wait for
  const stored = doc?.status === "stored";
  const human = requirement?.intake === "human_review";
  const fromChat = !!assistantOrigin;

  useEffect(() => {
    if (!doc || doc.status === "reviewed" || doc.status === "failed" || doc.status === "stored") return;
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

  const choose = (next: string) => {
    setCode(next);
    const m = monthsFor(next);
    setPeriod(m.length === 1 ? m[0] : null);
  };
  const chooseKind = (r: Requirement) => {
    const id = r.requirement_id || r.family;
    choose((reqs.find((x) => (x.requirement_id || x.family) === id && x.borrower_id === borrower) || r).code);
  };
  const submit = async () => {
    if (!file || !requirement) return;
    setBusy(true); setError(null);
    reportPresence("upload_started", requirement.code);
    try {
      const forRequest = asked && (!asked.borrower_id || asked.borrower_id === borrower) ? asked : undefined;
      const r = await api.upload(caseId, file, borrower || null, { requirementCode: requirement.code, expectedPeriod: period ?? forRequest?.period,
        actionId: assistantOrigin?.actionId, originTurnId: assistantOrigin?.turnId, customerRequestId: forRequest?.customer_request_id,
        replacesDocumentId: !forRequest && replaceTarget && replaceOn ? replaceTarget.document_id : undefined });
      setDoc(r.document); setNote(r.note || null); setNoteEn(r.note_en || null); setAnswered(!!r.answered_request); reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); reportPresence("upload_completed", requirement.code); }
  };
  const backToChat = () => { closeUpload(); openAssistant(); };
  const another = () => { setDoc(null); setFile(null); setNote(null); setOutcome(null); setOutcomeLost(false); choose(code); };
  const holders = (requirement?.holders || []).map((h) => snap?.case.borrowers.find((b) => b.borrower_id === h)?.first_name_he).filter(Boolean);
  const bankerName = (en && snap?.case.banker.name_en) || snap?.case.banker.name_he;
  const familyName = (r?: Requirement) => (en ? r?.family_en || FAMILY_EN[r?.family || ""] : undefined) || r?.family_he || FAMILY_HE[r?.family || ""];
  const stageIndex = doc ? STAGES.findIndex(([k]) => k === (doc.status === "reviewed" ? "done" : doc.stage)) : -1;
  const monthHint = en ? (months.length > 1
    ? (period ? "The check relies on the month printed on the payslip and will flag it if it differs from the month you chose."
      : `${months.length} months are missing. Upload one payslip at a time: choose this file's month, or upload it and we'll read the month from the payslip.`)
    : `${monthL(months[0])} was selected based on what's missing. The check relies on the month printed on the payslip.`)
    : months.length > 1
    ? (period ? "הבדיקה תסתמך על החודש שמודפס בתלוש, ותתריע אם הוא שונה מהחודש שבחרתם."
      : `חסרים ${months.length} חודשים. מעלים תלוש אחד בכל פעם, בחרו את החודש של הקובץ הזה, או העלו ונזהה אותו מהתלוש.`)
    : `נבחר ${monthHe(months[0])} לפי מה שחסר בתיק. הבדיקה תסתמך על החודש שמודפס בתלוש.`;
  return (
    <div className="sheet-backdrop" onClick={closeUpload}>
      <div className="sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={t("העלאת מסמך", "Upload a document")} data-testid="upload-sheet">
        <div className="grabber" />
        <div className="sheet-head"><h3>{t("העלאת מסמך", "Upload a document")}</h3><button className="icon-btn" onClick={closeUpload} aria-label={t("סגירה", "Close")}><IClose /></button></div>
        <div className="sheet-body stack">
          {!doc && (<>
            {fromChat && (
              <div className="upload-context" data-testid="upload-from-chat">
                <span>{t("הגעתם מהשיחה עם העוזר, מילאנו מראש את מה שידוע מהתיק.", "You came here from the assistant, so we've pre-filled what we know from your application.")}</span>
                <button className="link small" onClick={backToChat}>{t("חזרה לשיחה", "Back to chat")}</button>
              </div>
            )}
            {asked && (
              <div className="upload-request" data-testid="upload-for-request">
                <div className="bold">{(en && asked.title_en) || asked.title_he}</div>
                <div className="small">{en ? <bdi lang="he" dir="rtl">{asked.message_he}</bdi> : asked.message_he}</div>
                <div className="tiny muted">{en ? <>The file will be attached to {bankerName}&apos;s request and checked again.</>
                  : <>הקובץ יצורף לבקשה של {asked.created_by_name || snap?.case.banker.name_he} וייבדק שוב.</>}</div>
              </div>
            )}
            <div className="upload-kind">
              <span className="small bold">{t("סוג המסמך", "Document type")}</span>
              {upload.requirementCode || asked || kinds.length < 2 ? (
                <span className="kind-chip" data-testid="upload-doc-type" data-requirement={requirement?.code} data-family={requirement?.family}>
                  <ICheck size={12} />{familyName(requirement) || t("מסמך", "Document")}</span>
              ) : (
                <div className="choice wrap" role="radiogroup" aria-label={t("סוג המסמך", "Document type")} data-testid="upload-doc-type"
                  data-requirement={requirement?.code} data-family={requirement?.family}>
                  {kinds.map((k) => {
                    const on = (k.requirement_id || k.family) === (requirement?.requirement_id || requirement?.family);
                    return (
                      <label key={k.code} className={on ? "on" : ""}>
                        <input type="radio" name="kind" checked={on} onChange={() => chooseKind(k)} data-kind={k.family} />
                        <span>{familyName(k)}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
            {requirement?.hint_he && <div className="tiny muted" data-testid="upload-hint">{(en && requirement.hint_en) || requirement.hint_he}</div>}
            {human && <div className="tiny upload-human" data-testid="upload-human-review">{en ? <>This document type isn&apos;t checked by AI; the file will be stored
              and passed to {bankerName || "the banker"} for review.</> : <>סוג מסמך זה אינו נבדק ב-AI, הקובץ יישמר
              ויועבר לבדיקת {snap?.case.banker.name_he || "הבנקאי"}.</>}</div>}
            {sameKind.length > 1 && requirement?.account_id == null && (<>
              <div className="small bold">{t("עבור מי המסמך?", "Who is the document for?")}</div>
              <div className="choice">
                {sameKind.map((r) => {
                  const b = snap?.case.borrowers.find((x) => x.borrower_id === r.borrower_id);
                  return (
                    <label key={r.code} className={code === r.code ? "on" : ""}>
                      <input type="radio" name="borrower" value={r.borrower_id || ""} checked={code === r.code} onChange={() => choose(r.code)} />
                      <span>{(en && b?.first_name_en) || b?.first_name_he || (en && r.title_en) || r.title_he}</span>
                    </label>
                  );
                })}
              </div>
            </>)}
            {requirement?.account_id && holders.length > 0 && (
              <div className="tiny muted" data-testid="upload-account">{(en && requirement.title_en) || requirement.title_he}</div>
            )}
            {months.length > 0 && (
              <div className="stack" style={{ gap: 6 }}>
                <div className="small bold">{t("חודש השכר", "Pay month")}</div>
                <div className="month-pick" role="radiogroup" aria-label={t("חודש השכר", "Pay month")} data-testid="upload-months">
                  {months.map((m) => (
                    <button key={m} type="button" role="radio" aria-checked={period === m} className={`mchip pick${period === m ? " on" : ""}`}
                      onClick={() => setPeriod(period === m ? null : m)} data-period={m}>{en ? monthL(m) : monthHe(m)}</button>
                  ))}
                </div>
                <div className="tiny muted" style={{ lineHeight: 1.55 }} data-testid="upload-month-hint">{monthHint}</div>
              </div>
            )}
            {replaceTarget && (
              <div className="upload-replace" data-testid="upload-replaces" data-replaces={replaceTarget.document_id}>
                {presetReplace ? <span aria-hidden>↺</span>
                  : <input type="checkbox" checked={replaceOn} onChange={(e) => setReplaceOn(e.target.checked)} data-testid="upload-replace-toggle"
                    aria-label={t("המסמך החדש מחליף את המסמך שהוחזר", "The new document replaces the one sent back")} />}
                <span>{en ? <>The new document will replace <b className="ltr">{replaceTarget.filename}</b>, which didn&apos;t match the requirement. The previous file is kept in the history, and the check runs again.</>
                  : <>המסמך החדש יחליף את <b className="ltr">{replaceTarget.filename}</b>, שנמצא לא מתאים לדרישה. הקובץ הקודם נשמר בהיסטוריה, והבדיקה תרוץ מחדש.</>}</span>
              </div>
            )}
            <div className="dropzone">
              <input ref={input} type="file" accept="application/pdf,image/png,image/jpeg" className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="file-input" />
              <div style={{ color: "var(--mz-orange)" }}><IUpload size={26} /></div>
              <div className="bold" style={{ marginTop: 6 }}>{file ? file.name : t("בחרו קובץ PDF או צילום", "Choose a PDF or a photo")}</div>
              <div className="tiny muted" style={{ marginTop: 4 }}>{t("עדיף PDF מקורי · עד 15MB · הבדיקה רצה מיד אחרי ההעלאה", "An original PDF is best · up to 15MB · the check runs right after upload")}</div>
              <button className="btn btn-ghost" style={{ marginTop: 10 }}
                onClick={() => { reportPresence("file_picker_opened", requirement?.code); input.current?.click(); }}>{t("בחירת קובץ", "Choose a file")}</button>
            </div>
            {error && <div className="notice">{error}</div>}
            <button className="btn btn-orange" disabled={!file || busy} onClick={submit} data-testid="upload-submit">
              {busy ? <span className="spinner" /> : null}{human ? t("העלאה לבדיקת הבנקאי", "Upload for the banker's review") : t("העלאה ובדיקה חכמה", "Upload and smart check")}
            </button>
            <div className="tiny muted" style={{ lineHeight: 1.6 }}>
              {t("המסמך נשמר בתיק ונבדק בבדיקת המסמכים החכמה של JEEN. התוצאה היא בדיקת מסמך אוטומטית, לא קבלת המסמך על ידי הבנק.",
                "The document is saved in your application and goes through JEEN's smart document check. The result is an automatic document check, not the bank accepting the document.")}
            </div>
          </>)}
          {doc && (<>
            <div className="card tight">
              <div className="doc-name">{doc.filename}</div>
              {note && <div className="notice" style={{ marginTop: 8 }}>{(en && noteEn) || note}</div>}
              {answered && <div className="tiny" style={{ marginTop: 6, color: "var(--ok)", fontWeight: 700 }} data-testid="upload-answered">
                {en ? <>The file was attached to {bankerName}&apos;s request. After the smart check it goes back to the request for review.</>
                  : <>הקובץ צורף לבקשה של {snap?.case.banker.name_he}. אחרי הבדיקה החכמה הוא יחזור אליה לבדיקה.</>}</div>}
              {stored ? (
                <div className="doc-outcome info" style={{ marginTop: 10 }} data-testid="upload-stored" data-outcome="HUMAN_REVIEW_PENDING">
                  {en ? <>The document was saved and will be passed to {bankerName || "the banker"} for review. This document type has no AI check, so it wasn&apos;t marked &ldquo;valid&rdquo;.</>
                    : <>המסמך נשמר בתיק ויועבר לבדיקת {snap?.case.banker.name_he || "הבנקאי"}. לסוג מסמך זה אין בדיקת AI, ולכן הוא לא סומן ״תקין״.</>}
                </div>
              ) : (<>
              <div className="jeen-by" style={{ marginTop: 10 }}><img src="/brand/jeen-mark.png" alt="" />{t("עיבוד מסמכים באמצעות JEEN", "Document processing by JEEN")}</div>
              <div className="stage-list" data-testid="upload-stages">
                {STAGES.map(([k, label, labelEn], i) => (
                  <div key={k} className={`stage-item ${i < stageIndex || doc.status === "reviewed" ? "done" : i === stageIndex ? "now" : ""}`}>
                    <span className="dot" />{en ? labelEn : label}{i === stageIndex && doc.status !== "reviewed" ? <span className="spinner" /> : null}
                  </div>
                ))}
              </div>
              </>)}
              {doc.status === "failed" && <div className="notice" style={{ marginTop: 8 }}>{t("הבדיקה נכשלה בגלל תקלה זמנית בעיבוד המסמך. אפשר לנסות שוב בעוד רגע.", "The check failed because of a temporary problem processing the document. You can try again in a moment.")}</div>}
              {doc.review && (
                <div className="row between" style={{ marginTop: 12 }}>
                  {(() => {
                    const v = customerVerdict(doc.review.verdict, snap?.readiness.pending_jobs.length ? undefined : snap?.outcomes?.documents[doc.document_id]);
                    return <span className={`badge ${v.cls}`}>{v.text}</span>;
                  })()}
                  <button className="btn btn-dark" onClick={() => { closeUpload(); nav(`/customer/documents/${doc.document_id}`); }}>{t("לתוצאות הבדיקה", "See the check results")}</button>
                </div>
              )}
            </div>
            {reviewed && outcome?.phase !== "complete" && !outcomeLost && (
              <div className="row small muted" data-testid="upload-rechecking"><span className="spinner" />{t("מעדכנים את תמונת המסמכים בתיק…", "Updating the picture of your application's documents…")}</div>
            )}
            {outcomeLost && <div className="small muted">{t("לא הצלחנו לקבל את סיכום הבדיקה כרגע. המצב המעודכן יופיע במסך המסמכים ובשיחה עם העוזר.", "We couldn't get the check's summary right now. The updated status will appear on the Documents screen and in the assistant chat.")}</div>}
            {outcome?.phase === "complete" && snap?.outcomes?.documents[doc.document_id] && !snap.readiness.pending_jobs.length && (
              <div className={`doc-outcome ${OUTCOME_TONE[snap.outcomes.documents[doc.document_id].outcome] || "info"}`}
                data-testid="upload-route" data-outcome={snap.outcomes.documents[doc.document_id].outcome}>
                {(en && snap.outcomes.documents[doc.document_id].label_en) || snap.outcomes.documents[doc.document_id].label_he}
              </div>
            )}
            {outcome?.phase === "complete" && (
              <div className="outcome" data-testid="upload-outcome">
                <div className="outcome-msg">{(en && outcome.message_en) || outcome.message_he}</div>
                <ActionList actions={outcome.actions} testId="upload-outcome-actions" />
              </div>
            )}
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-dark" onClick={backToChat} data-testid="upload-back-to-chat">{fromChat ? t("חזרה לשיחה", "Back to chat") : t("שאלו את העוזר מה הלאה", "Ask the assistant what's next")}</button>
              <button className="btn btn-ghost" onClick={another}>{t("העלאת מסמך נוסף", "Upload another document")}</button>
            </div>
          </>)}
        </div>
      </div>
    </div>
  );
}
