import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, customerVerdict, FAMILY_EN, FAMILY_HE, ils, ilsL, monthHe, monthL, timeHe, timeL, type Requirement } from "../../api";
import { useCase } from "../../caseContext";
import { currentLang, tr, useLang } from "../../i18n";
import { ApplyHandoff } from "./ApplyV2";
import { IBag, IBank, IChart, ICheck, IChevron, IChevronDown, IClock, IDocs, IHouse, IPerson, IShield, ISpark, IUpload, IX } from "../../components/Icons";

const LOAN_ICON: Record<string, ReactNode> = { id_document: <IPerson size={18} />, bank_statement: <IBank size={18} />,
  purpose_proof: <IBag size={18} />, tax_form: <IChart size={18} />, business_registration: <IShield size={18} />,
  pnl_statement: <IChart size={18} />, company_registry: <IShield size={18} />, signatory_authority: <IPerson size={18} />,
  financial_statements: <IChart size={18} />, business_bank_statement: <IBank size={18} /> };
/** A requirement the customer can upload for in the app: reviewed by AI, or stored for the banker (no rubric). */
export const uploadable = (r: Requirement) => r.evaluated_by_ai || r.intake === "human_review";
const DONE_STATES = ["extracted", "preparation_confirmed", "checking", "accepted_by_banker"];

/** Income-source correction for an individual borrower, inside the required-documents list.
 *  The same policy recomposes the checklist on the server; uploaded documents stay. */
function IncomeSources() {
  const { snap } = useCase();
  const [editing, setEditing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const { t } = useLang();
  const p = snap?.case.document_profile;
  if (!snap || !p || p.entity !== "individual") return null;
  return (
    <div className="dl-income" data-testid="income-sources">
      {!editing && (
        <button className="link subtle small dx-profile-edit" onClick={() => { setEditing(true); setResult(null); }} data-testid="profile-edit">
          {t("עדכון מקורות ההכנסה", "Update income sources")}</button>
      )}
      {editing && <ProfileEditor onDone={(text) => { setEditing(false); setResult(text); }} />}
      {result && <div className="notice navy small" role="status" data-testid="profile-change-result">{result}</div>}
    </div>
  );
}

const INCOME_OPTS: [string, string, string][] = [["salaried", "שכיר/ה", "Salaried"], ["self_employed", "עצמאי/ת", "Self-employed"]];
const REG_OPTS: [string, string, string][] = [["vat_exempt", "עוסק פטור", "Exempt dealer (Osek Patur)"], ["vat_registered", "עוסק מורשה", "Licensed dealer (Osek Murshe)"]];

/** The customer corrects an income profile after confirming: the same policy recomposes the checklist on the server.
 *  Uploaded documents and their review history are kept. */
function ProfileEditor({ onDone }: { onDone: (text: string | null) => void }) {
  const { snap, caseId, reload } = useCase();
  const people = snap!.case.document_profile!.applicants;
  const [draft, setDraft] = useState(() => Object.fromEntries(people.map((a) => [a.borrower_id,
    { income_sources: a.income_sources, business_registration: a.business_registration || null }])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { en, t } = useLang();
  const toggle = (bid: string, src: string) => setDraft((d) => {
    const cur = d[bid].income_sources;
    return { ...d, [bid]: { ...d[bid], income_sources: cur.includes(src) ? cur.filter((x) => x !== src) : [...cur, src] } };
  });
  const save = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.changeProfile(caseId, draft);
      reload();
      onDone(en ? (!r.changed ? "No change was made to the profile." : [r.added.length ? `Added: ${(r.added_en || r.added).join(" · ")}` : "",
        r.removed.length ? `No longer needed: ${(r.removed_en || r.removed).join(" · ")} (documents already uploaded are kept)` : "",
        r.tasks_canceled.length ? "The related completion requests were canceled." : ""].filter(Boolean).join(". ") || "The profile was updated.")
        : !r.changed ? "לא בוצע שינוי בפרופיל." : [r.added.length ? `נוספו: ${r.added.join(" · ")}` : "",
        r.removed.length ? `לא נדרשים עוד: ${r.removed.join(" · ")} (המסמכים שכבר הועלו נשמרים)` : "",
        r.tasks_canceled.length ? "בקשות ההשלמה הקשורות בוטלו." : ""].filter(Boolean).join(". ") || "הפרופיל עודכן.");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="dx-profile-editor" data-testid="profile-editor">
      {people.map((a) => (
        <div key={a.borrower_id} className="stack" style={{ gap: 6 }} data-testid="profile-editor-person" data-borrower={a.borrower_id}>
          <div className="small bold">{(en && a.name_en) || a.name_he}</div>
          <div className="choice">
            {INCOME_OPTS.map(([k, label, labelEn]) => (
              <label key={k} className={draft[a.borrower_id].income_sources.includes(k) ? "on" : ""}>
                <input type="checkbox" checked={draft[a.borrower_id].income_sources.includes(k)} onChange={() => toggle(a.borrower_id, k)}
                  data-testid={`profile-income-${k}`} /><span>{en ? labelEn : label}</span></label>
            ))}
          </div>
          {draft[a.borrower_id].income_sources.includes("self_employed") && (
            <div className="choice">
              {REG_OPTS.map(([k, label, labelEn]) => (
                <label key={k} className={draft[a.borrower_id].business_registration === k ? "on" : ""}>
                  <input type="radio" name={`reg-${a.borrower_id}`} checked={draft[a.borrower_id].business_registration === k}
                    onChange={() => setDraft((d) => ({ ...d, [a.borrower_id]: { ...d[a.borrower_id], business_registration: k } }))}
                    data-testid={`profile-reg-${k}`} /><span>{en ? labelEn : label}</span></label>
              ))}
            </div>
          )}
        </div>
      ))}
      <div className="tiny muted">{t("רשימת המסמכים תחושב מחדש לפי אותה מדיניות. מסמכים שכבר הועלו נשמרים בתיק.", "The document list will be recalculated under the same policy. Documents you already uploaded stay in your application.")}</div>
      {error && <div className="notice small" role="alert">{error}</div>}
      <div className="row" style={{ gap: 8 }}>
        <button className="btn btn-orange" disabled={busy} onClick={save} data-testid="profile-save">{busy && <span className="spinner" />}{t("שמירת השינוי", "Save the change")}</button>
        <button className="btn btn-ghost" disabled={busy} onClick={() => onDone(null)}>{t("ביטול", "Cancel")}</button>
      </div>
    </div>
  );
}

/** A one-document requirement of the loan (ID, a statement of one account, proof of purpose, tax form, business documents). */
function LoanDocRow({ r, focused, expanded, setExpanded }: { r: Requirement; focused: boolean;
  expanded: Record<string, boolean>; setExpanded: (v: Record<string, boolean>) => void }) {
  const { snap, docs, openUpload, openAssistant } = useCase();
  const { en, t } = useLang();
  if (!snap) return null;
  const mineDocs = new Set(docs.filter((d) => d.requirement_code === r.code).map((d) => d.document_id));
  const findings = snap.findings.filter((f) => f.status === "open" && f.review_state === "CUSTOMER_ACTION_REQUIRED"
    && (mineDocs.has(f.document_id || "") || f.detail?.requirement_code === r.code));
  // a missing document or a gap in the period asks for a first upload, not for replacing an uploaded one
  const firstUpload = r.ai_state === "required_missing" || (findings.length > 0 && !findings.some((f) => f.document_id));
  const isOpen = expanded[r.code] ?? focused;
  const [name, detail] = splitTitle((en && r.title_en) || r.title_he);
  const tone = STATE_TONE[r.ai_state] || (r.ai_state === "required_missing" ? "bad" : "warn");
  const human = r.intake === "human_review";
  return (
    <li id={`req-${r.code}`} data-testid={`req-${r.code}`} data-family={r.family} data-state={r.ai_state} data-intake={r.intake}
      data-focused={focused ? "true" : undefined} className={`dl-row${isOpen ? " open" : ""}${focused ? " focus" : ""}`}>
      <button className="dl-head" onClick={() => setExpanded({ ...expanded, [r.code]: !isOpen })} aria-expanded={isOpen}>
        <span className="dl-ic" aria-hidden>{LOAN_ICON[r.family] || <IDocs size={18} />}</span>
        <span className="grow dl-text">
          <span className="dl-name">{name}</span>
          {detail && <span className="dl-detail" title={detail}>{detail}</span>}
        </span>
        <span className={`dl-pill ${tone}`}>{r.ai_state === "checking" && <span className="spinner" />}
          {r.ai_state === "required_missing" ? t("טרם הועלה", "Not uploaded yet") : (en && r.ai_state_en) || r.ai_state_he}</span>
        <span className="dl-chev" aria-hidden><IChevron size={16} /></span>
      </button>
      {isOpen && (
        <div className="dl-body">
          {r.hint_he && <p className="dl-note">{(en && r.hint_en) || r.hint_he}</p>}
          {(r.owner_he || r.why_he) && (
            <p className="dl-note" data-testid="req-why">{r.owner_he && <><b>{t("עבור: ", "For: ")}</b>{(en && r.owner_en) || r.owner_he}. </>}{r.why_he && <><b>{t("למה: ", "Why: ")}</b>{(en && r.why_en) || r.why_he}</>}</p>
          )}
          {(r.alternatives_he?.length ?? 0) > 0 && (
            <p className="dl-note" data-testid="req-alternatives"><b>{t("מתקבל גם: ", "Also accepted: ")}</b>{en && !r.alternatives_en ? <bdi lang="he" dir="rtl">{r.alternatives_he!.join(" · ")}</bdi>
              : ((en && r.alternatives_en) || r.alternatives_he!).join(" · ")}</p>
          )}
          {human && <p className="dl-note dl-human" data-testid="req-human-review">{en ? <>This document type isn&apos;t checked by AI: the file is stored in your application
            and goes to {snap.case.banker.name_en || snap.case.banker.name_he} for review. It won&apos;t be marked &ldquo;valid&rdquo; automatically.</> : <>סוג מסמך זה אינו נבדק ב-AI: הקובץ נשמר בתיק
            ועובר לבדיקת {snap.case.banker.name_he}. הוא לא יסומן ״תקין״ אוטומטית.</>}</p>}
          {findings.map((f) => <div key={f.finding_id} className="small" style={{ marginTop: 6, lineHeight: 1.55 }}>• {(en && f.message_en) || f.message_he}</div>)}
          <div className="req-actions">
            <button className="link req-more" onClick={() => openAssistant(t(`מה בדיוק צריך להעלות עבור ${name}?`, `What exactly do I need to upload for ${name}?`))}>
              {t("למידע נוסף", "More information")}<IChevron size={14} /></button>
            {!DONE_STATES.includes(r.ai_state) && (
              <button className="btn btn-dark req-upload" onClick={() => openUpload(r.borrower_id || undefined, { requirementCode: r.code })}
                data-testid={`upload-${r.code}`}><IUpload size={15} />{firstUpload ? t("להעלאה", "Upload") : t("העלאה מחדש", "Upload again")}</button>
            )}
          </div>
          <div className="dl-bank"><IClock size={13} />{human ? t("בדיקת בנקאי, ללא בדיקת AI", "Banker review, no AI check") : t("ממתין לאישור הבנק", "Awaiting the bank's approval")}</div>
        </div>
      )}
    </li>
  );
}

/** The bank's requirement titles carry their detail after a dash, in parentheses or as "משועבדת לבנק". */
function splitTitle(title: string): [string, string] {
  const dash = title.indexOf(" — ");
  if (dash > 0) return [title.slice(0, dash), title.slice(dash + 3)];
  const paren = title.match(/^(.+?)\s*\((.+)\)$/);
  if (paren) return [paren[1], paren[2]];
  const pledged = title.indexOf(" משועבדת");
  return pledged > 0 ? [title.slice(0, pledged), title.slice(pledged + 1)] : [title, ""];
}
const FAMILY_ICON: Record<string, ReactNode> = {
  income: <IBank size={18} />, liabilities: <IChart size={18} />, property: <IHouse size={18} />,
  insurance: <IShield size={18} />, collateral: <IDocs size={18} />,
};
const STATE_TONE: Record<string, string> = { extracted: "ok", preparation_confirmed: "ok", needs_banker_review: "info", checking: "neutral",
  received_pending_review: "info", accepted_by_banker: "ok" };

/** The payslip row's pill: what is missing first, otherwise the requirement's AI state. */
function payslipPill(r: Requirement): { text: string; tone: string } {
  const n = r.missing?.length ?? 0;
  if (n) return { text: tr(n === 1 ? "חסר תלוש" : n === (r.required ?? n) ? "חסר" : `חסרים ${n}`, n === 1 ? "1 missing" : n === (r.required ?? n) ? "Missing" : `${n} missing`), tone: "bad" };
  return { text: tr(r.ai_state_he, r.ai_state_en || r.ai_state_he), tone: STATE_TONE[r.ai_state] || "warn" };
}

function MonthChips({ r }: { r: Requirement }) {
  return (
    <div className="month-chips">
      {(r.requested_months || []).map((m) => {
        const copies = r.duplicates?.[m];
        const covered = r.covered?.includes(m);
        const month = <span className="mchip-month">{currentLang() === "en" ? monthL(m) : monthHe(m)}</span>;
        if (!covered) return <span key={m} className="mchip miss">{month} <span className="mchip-state"><IX size={11} />{tr("חסר", "Missing")}</span></span>;
        if (r.pending_review?.includes(m)) return <span key={m} className="mchip review">{month} <span className="mchip-state"><IClock size={11} />{tr("בבדיקה", "Checking")}</span></span>;
        if (copies) return <span key={m} className="mchip dup">{month} <span className="mchip-state"><ICheck size={11} />×{copies}</span></span>;
        return <span key={m} className="mchip ok">{month} <span className="mchip-state"><ICheck size={11} /></span></span>;
      })}
    </div>
  );
}

export function Documents() {
  const { snap, docs, openUpload, openAssistant, caseId, reload } = useCase();
  const nav = useNavigate();
  const [tab, setTab] = useState<"list" | "bank">("list");
  const [params, setParams] = useSearchParams();
  const [focus, setFocus] = useState<string | null>(null);
  const [linkNote, setLinkNote] = useState<string | null>(null);
  const [replying, setReplying] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [replyBusy, setReplyBusy] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);
  const [listOpen, setListOpen] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const { en, t } = useLang();
  const loaded = !!snap;
  useEffect(() => {
    if (!snap) return;
    // req=<requirement>: the follow-up's secure link lands here and opens that requirement's upload, like upload=
    const want = params.get("upload") || params.get("req"), section = params.get("focus"), forCase = params.get("case"), reqId = params.get("request");
    const replace = params.get("replace");
    if (!want && !section && !reqId && !replace) return;
    setParams({}, { replace: true });
    setTab("list");
    if (forCase && forCase !== caseId) { setLinkNote(tr("הקישור שייך לתיק אחר ולכן לא נפתח. מוצג התיק הפעיל שלכם.", "This link belongs to another application, so it wasn't opened. Your active application is shown.")); return; }
    setLinkNote(null);
    if (replace) {
      // replace=<document>: the upload that replaces a document the AI review sent back (checked again by the server)
      const old = docs.find((d) => d.document_id === replace);
      if (snap.outcomes?.documents[replace]?.outcome !== "BLOCKER") { setLinkNote(tr("המסמך הזה כבר אינו ממתין להחלפה.", "This document no longer needs replacing.")); return; }
      setFocus("sec-uploaded");
      openUpload(old?.borrower_id || snap.case.borrowers[0]?.borrower_id, { requirementCode: old?.requirement_code || undefined, replacesDocumentId: replace });
      return;
    }
    if (reqId) {
      const q = snap.customer_requests?.find((x) => x.customer_request_id === reqId);
      if (!q) { setLinkNote(tr("הבקשה לא נמצאה בתיק הפעיל.", "The request wasn't found in your active application.")); return; }
      setFocus(`creq-${q.customer_request_id}`);
      if (q.status !== "OPEN") { setLinkNote(tr("כבר השבתם לבקשה הזו. היא אצל הבנקאי.", "You've already answered this request. It's with your banker.")); return; }
      if (q.can_reply) { setReplying(q.customer_request_id); return; }
      openUpload(q.borrower_id || undefined, { requirementCode: q.requirement_code || undefined, period: q.period, customerRequestId: q.customer_request_id });
      return;
    }
    if (!want) {
      // focus=<requirement code> opens on that requirement's card (home-screen summary rows)
      const one = section && snap.readiness.requirements.some((r) => r.code === section && uploadable(r)) ? `req-${section}` : null;
      setFocus(section === "uploaded" ? "sec-uploaded" : one || "sec-payslips");
      return;
    }
    const req = snap.readiness.requirements.find((r) => r.code === want && uploadable(r));
    if (!req) { setLinkNote(tr("לא ניתן להעלות את סוג המסמך הזה באפליקציה.", "This document type can't be uploaded in the app.")); return; }
    setFocus(`req-${req.code}`);
    openUpload(req.borrower_id || undefined, { requirementCode: req.code, period: params.get("period") });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, loaded]);
  useEffect(() => {
    if (!focus) return;
    setListOpen(true);
    // the list may have been collapsed: scroll after it renders again
    requestAnimationFrame(() => document.getElementById(focus)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [focus]);
  if (!snap) return null;
  const reqs = snap.readiness.requirements;
  const payslips = reqs.filter((r) => r.evaluated_by_ai && r.family === "payslip");
  const loanDocs = reqs.filter((r) => uploadable(r) && r.family !== "payslip");
  const others = reqs.filter((r) => !uploadable(r));
  const progress = snap.readiness.progress;
  const reviewedValid = docs.filter((d) => d.review?.verdict === "VALID").length;
  const customerFindings = snap.findings.filter((f) => f.status === "open" && f.review_state === "CUSTOMER_ACTION_REQUIRED");
  const borrowerName = (id?: string | null) => {
    const b = snap.case.borrowers.find((x) => x.borrower_id === id);
    return (en && b?.first_name_en) || b?.first_name_he || "";
  };
  const bankerName = (en && snap.case.banker.name_en) || snap.case.banker.name_he;
  const docStatus = snap.document_status || {};
  const requests = (snap.customer_requests || []).filter((q) => q.status === "OPEN" || !!q.responded_text
    || (q.responded_document_id && docStatus[q.responded_document_id]?.status !== "ACCEPTED"));
  const docName = (id?: string | null) => docs.find((d) => d.document_id === id)?.filename;
  const familyOf = (code?: string | null) => {
    const r = reqs.find((x) => x.code === code);
    return r ? (en ? r.family_en || FAMILY_EN[r.family] : undefined) || r.family_he || FAMILY_HE[r.family] : "";
  };
  const required = snap.readiness.payslips?.required ?? 0;
  const verified = snap.readiness.payslips?.verified ?? 0;
  const allVerified = required > 0 && verified >= required;
  return (
    <>
      <div className="page-title">{t("מסמכים", "Documents")}</div>
      <p className="page-sub docs-sub">{t("ריכזנו כאן את המסמכים הנדרשים לבקשת ההלוואה. כל מסמך נבדק בבדיקת המסמכים החכמה של JEEN מיד עם ההעלאה.",
        "Here are the documents your loan application needs. Each document goes through JEEN's smart document check as soon as you upload it.")}</p>
      <div className="segmented docs-tabs" role="tablist">
        <button className={tab === "list" ? "on" : ""} onClick={() => setTab("list")} role="tab">{t("רשימת מסמכים", "Document list")}</button>
        <button className={tab === "bank" ? "on" : ""} onClick={() => setTab("bank")} role="tab">{t("אישורים מהבנק", "Bank approvals")}</button>
      </div>
      {linkNote && <div className="notice" role="status" style={{ marginBottom: 12 }} data-testid="link-note">{linkNote}</div>}
      <ApplyHandoff />
      {tab === "list" && (<>
        {requests.length > 0 && (<>
          <div className="section-label" id="sec-requests">{en ? <>Requests from {bankerName}</> : <>בקשות מ{snap.case.banker.name_he}</>}</div>
          {requests.map((q) => {
            const open = q.status === "OPEN";
            const replacement = docs.find((d) => d.document_id === q.responded_document_id);
            return (
              <div key={q.customer_request_id} id={`creq-${q.customer_request_id}`} data-testid="customer-request" data-status={q.status}
                className={`creq-card${open ? " open" : ""}${focus === `creq-${q.customer_request_id}` ? " focus" : ""}`}>
                <div className="creq-from">{open ? t("בקשה חדשה", "New request") : t("המסמך התקבל", "Document received")} · {(en && q.created_by_name === snap.case.banker.name_he ? bankerName : q.created_by_name) || bankerName} · <span className="ltr">{en ? timeL(q.created_at) : timeHe(q.created_at)}</span></div>
                <div className="creq-title">{(en && q.title_en) || q.title_he}</div>
                <div className="creq-msg">{en ? <bdi lang="he" dir="rtl">{q.message_he}</bdi> : q.message_he}</div>
                {q.document_filename && <div className="tiny muted">{t("המסמך שהוחזר: ", "Document sent back: ")}<span className="ltr">{q.document_filename}</span></div>}
                {open && q.can_reply ? (<>
                  {replying === q.customer_request_id ? (
                    <div className="creq-reply" data-testid="request-reply">
                      <textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder={t("כתבו כאן את ההסבר", "Write your explanation here")} maxLength={1000} data-testid="request-reply-text" />
                      <div className="tiny muted">{en ? <>Your explanation will be saved in your application and passed to {bankerName}. It doesn&apos;t close the item; you may also be asked for a supporting document.</>
                        : <>ההסבר יישמר בתיק ויועבר ל{snap.case.banker.name_he}. הוא אינו סוגר את הבירור; ייתכן שתתבקשו גם מסמך תומך.</>}</div>
                      {replyError && <div className="small" role="alert" style={{ color: "var(--bad)" }}>{replyError}</div>}
                      <div className="creq-btns">
                        <button className="btn btn-orange" disabled={replyBusy || !reply.trim()} data-testid="request-reply-send" onClick={async () => {
                          setReplyBusy(true); setReplyError(null);
                          try { await api.replyToRequest(caseId, q.customer_request_id, reply.trim()); setReplying(null); setReply(""); reload(); }
                          catch (e) { setReplyError((e as Error).message); } finally { setReplyBusy(false); }
                        }}>{replyBusy && <span className="spinner" />}{t("שליחת ההסבר", "Send the explanation")}</button>
                        <button className="btn btn-soft" onClick={() => setReplying(null)}>{t("ביטול", "Cancel")}</button>
                      </div>
                    </div>
                  ) : (
                    <div className="creq-btns">
                      <button className="btn btn-orange" data-testid="request-reply-open" onClick={() => setReplying(q.customer_request_id)}>{t("השבה בכתב", "Reply in writing")}</button>
                      <button className="btn btn-ghost" data-testid="request-upload" onClick={() => openUpload(q.borrower_id || undefined,
                        { requirementCode: q.requirement_code || undefined, period: q.period, customerRequestId: q.customer_request_id })}>{t("צירוף מסמך", "Attach a document")}</button>
                    </div>
                  )}
                </>) : open ? (
                  <button className="btn btn-orange creq-btn" data-testid="request-upload"
                    onClick={() => openUpload(q.borrower_id || undefined, { requirementCode: q.requirement_code || undefined, period: q.period,
                      customerRequestId: q.customer_request_id })}>{t("להעלאת המסמך", "Upload the document")}</button>
                ) : q.responded_text ? (
                  <div className="small creq-done" data-testid="request-answered">{en ? <>You replied: &ldquo;{q.responded_text}&rdquo;. Your explanation was passed to {bankerName}.</>
                    : <>השבתם: „{q.responded_text}”. ההסבר הועבר ל{snap.case.banker.name_he}.</>}</div>
                ) : (
                  <div className="small creq-done" data-testid="request-answered">
                    {t("העליתם את ", "You uploaded ")}<span className="ltr">{q.responded_filename || replacement?.filename}</span>
                    {replacement && !replacement.review ? t(", בבדיקה חכמה עכשיו.", " — the smart check is running now.") : t(`, נבדק וממתין לעיון של ${snap.case.banker.name_he}.`, ` — checked and waiting for ${bankerName} to look at it.`)}
                  </div>
                )}
              </div>
            );
          })}
        </>)}
        <section className="dx-jeen" data-testid="docs-jeen-summary" aria-labelledby="dx-jeen-title">
          <div className="dx-jeen-main">
            <span className={`dx-jeen-ic${allVerified ? " ok" : ""}`} aria-hidden>{allVerified ? <ICheck size={18} /> : <ISpark size={18} />}</span>
            <div className="grow">
              <h2 className="dx-jeen-title" id="dx-jeen-title">{t("בדיקת מסמכים חכמה", "Smart document check")}<img src="/brand/jeen-logo.png" alt={t("של JEEN", "by JEEN")} /></h2>
              {progress && progress.total > 0 ? (<>
                <div className="dx-jeen-progress" data-testid="docs-progress">{en ? <><b>{progress.done} of {progress.total}</b> requirements complete</> : <><b>{progress.done} מתוך {progress.total}</b> דרישות הושלמו</>}</div>
                <span className="dx-meter" aria-hidden><span style={{ width: `${Math.round((progress.done / progress.total) * 100)}%` }} /></span>
              </>) : required > 0 && (<>
                <div className="dx-jeen-progress">{en ? <><b>{verified} of {required}</b> payslips complete</> : <><b>{verified} מתוך {required}</b> תלושי שכר הושלמו</>}</div>
                <span className="dx-meter" aria-hidden><span style={{ width: `${Math.round((verified / required) * 100)}%` }} /></span>
              </>)}
              <div className="dx-jeen-text">{en ? <>{reviewedValid === 1 ? "1 document is valid" : `${reviewedValid} documents are valid`} · not yet approved by the bank</>
                : <>{reviewedValid === 1 ? "מסמך אחד נמצא תקין" : `${reviewedValid} מסמכים נמצאו תקינים`} · טרם אושרו בבנק</>}</div>
            </div>
          </div>
          <div className="dx-jeen-note"><span>{t("לאחר העלאת המסמכים נעדכן אתכם בתוצאות הבדיקה ובכל פעולה נדרשת.", "After you upload your documents, we'll let you know the results and anything else that's needed.")}</span><IClock size={18} /></div>
        </section>

        <section className="dl-card" id="sec-payslips" aria-label={t("רשימת המסמכים הנדרשים", "Required documents")} data-testid="required-docs">
          <button className="dl-top" onClick={() => setListOpen(!listOpen)} aria-expanded={listOpen} aria-controls="dl-list">
            <span className="dl-top-ic" aria-hidden><IDocs size={20} /></span>
            <span className="grow dl-text">
              <span className="dl-title">{t("רשימת המסמכים הנדרשים", "Required documents")}</span>
              <span className="dl-sub">{t("לפי מדיניות המסמכים של הבקשה · נבדקים באופן חכם באמצעות JEEN.", "Under the application's document policy · checked smartly with JEEN.")}</span>
            </span>
            <span className={`dl-toggle${listOpen ? " open" : ""}`} aria-hidden><IChevronDown size={18} /></span>
          </button>
          <IncomeSources />
          {listOpen && (
            <ul className="dl-list" id="dl-list">
              {loanDocs.filter((r) => r.family === "id_document").map((r) => (
                <LoanDocRow key={r.code} r={r} focused={focus === `req-${r.code}`} expanded={expanded} setExpanded={setExpanded} />))}
              {payslips.map((r) => {
                const mine = customerFindings.filter((f) => f.borrower_id === r.borrower_id && (f.detail?.family ?? "payslip") === "payslip");
                const open = r.ai_state === "required_missing" || (r.missing?.length ?? 0) > 0 || mine.length > 0;
                const focused = focus === `req-${r.code}` || (focus === "sec-payslips" && open);
                // rows start collapsed; only a deep link to this requirement opens it
                const isOpen = expanded[r.code] ?? focus === `req-${r.code}`;
                const pill = payslipPill(r);
                const name = borrowerName(r.borrower_id);
                return (
                  <li key={r.code} id={`req-${r.code}`} data-testid={`req-${r.code}`} data-focused={focused ? "true" : undefined}
                    className={`dl-row${isOpen ? " open" : ""}${focused ? " focus" : ""}`}>
                    <button className="dl-head" onClick={() => setExpanded({ ...expanded, [r.code]: !isOpen })} aria-expanded={isOpen}>
                      <span className="dl-ic" aria-hidden><IDocs size={18} /></span>
                      <span className="grow dl-text">
                        <span className="dl-name">{name ? t(`תלושי שכר, ${name}`, `Payslips, ${name}`) : (en && r.title_en) || r.title_he}</span>
                        <span className="dl-detail">{r.required ? t(`${r.required} החודשים האחרונים`, `The last ${r.required} months`) : splitTitle((en && r.title_en) || r.title_he)[1]}</span>
                      </span>
                      <span className={`dl-pill ${pill.tone}`}>{r.ai_state === "checking" && <span className="spinner" />}{pill.text}</span>
                      <span className="dl-chev" aria-hidden><IChevron size={16} /></span>
                    </button>
                    {isOpen && (
                      <div className="dl-body">
                        {(r.missing?.length ?? 0) > 0 && <div className="req-new">
                          {en ? (r.missing!.length === 1 ? `Payslip for ${monthL(r.missing![0])} missing` : `${r.missing!.length} payslips missing`)
                            : r.missing!.length === 1 ? `חסר תלוש ${monthHe(r.missing![0])}` : `חסרים ${r.missing!.length} תלושים`}</div>}
                        <MonthChips r={r} />
                        {mine.map((f) => <div key={f.finding_id} className="small" style={{ marginTop: 6, lineHeight: 1.55 }}>• {(en && f.message_en) || f.message_he}</div>)}
                        <div className="req-actions">
                          <button className="link req-more" onClick={() => openAssistant(t(`מה בדיוק צריך להעלות עבור ${name}?`, `What exactly do I need to upload for ${name}?`))}>
                            {t("למידע נוסף", "More information")}<IChevron size={14} /></button>
                          <button className="btn btn-dark req-upload" onClick={() => openUpload(r.borrower_id || undefined, { requirementCode: r.code })}
                            data-testid={`upload-${r.borrower_id}`}><IUpload size={15} />{t("להעלאה", "Upload")}</button>
                        </div>
                        <div className="dl-bank"><IClock size={13} />{t("ממתין לאישור הבנק", "Awaiting the bank's approval")}</div>
                      </div>
                    )}
                  </li>
                );
              })}
              {loanDocs.filter((r) => r.family !== "id_document").map((r) => (
                <LoanDocRow key={r.code} r={r} focused={focus === `req-${r.code}`} expanded={expanded} setExpanded={setExpanded} />))}
              {others.map((r) => {
                const [name, detail] = splitTitle((en && r.title_en) || r.title_he);
                const isOpen = !!expanded[r.code];
                return (
                  <li key={r.code} className={`dl-row${isOpen ? " open" : ""}`} data-code={r.code} data-testid="other-doc">
                    <button className="dl-head" onClick={() => setExpanded({ ...expanded, [r.code]: !isOpen })} aria-expanded={isOpen}>
                      <span className="dl-ic" aria-hidden>{FAMILY_ICON[r.family] || <IDocs size={18} />}</span>
                      <span className="grow dl-text">
                        <span className="dl-name">{name}</span>
                        {detail && <span className="dl-detail" title={detail}>{detail}</span>}
                      </span>
                      <span className="dl-pill neutral">{r.bank_status === "awaiting_documents" ? t("טרם הועלה", "Not uploaded yet") : t("מול הבנק", "With the bank")}</span>
                      <span className="dl-chev" aria-hidden><IChevron size={16} /></span>
                    </button>
                    {isOpen && (
                      <div className="dl-body">
                        <p className="dl-note">{t("המסמך מטופל ישירות מול הבנק ואינו נבדק באפליקציה.", "This document is handled directly with the bank and isn't checked in the app.")}</p>
                        <button className="link req-more" onClick={() => openAssistant(t(`מה צריך לדעת על ${name}?`, `What should I know about ${name}?`))}>{t("שאלו את העוזר", "Ask the assistant")}<IChevron size={14} /></button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {(snap.readiness.inactive_requirements?.length ?? 0) > 0 && (
          <section className="dl-card dl-inactive" data-testid="inactive-requirements" aria-label={t("מסמכים שאינם נדרשים עוד", "Documents no longer needed")}>
            <div className="small bold">{t("לא נדרשים עוד אחרי עדכון הפרופיל", "No longer needed after the profile update")}</div>
            <ul className="dl-list">{snap.readiness.inactive_requirements!.map((r) => (
              <li key={r.code} className="dl-row" data-testid="inactive-requirement" data-code={r.code}>
                <span className="dl-head"><span className="grow dl-text"><span className="dl-name">{(en && r.family_en) || r.family_he}</span>
                  <span className="dl-detail">{en ? <>{r.state_en || r.state_he} · {r.document_ids.length} documents kept in the history</> : <>{r.state_he} · {r.document_ids.length} מסמכים נשמרו בהיסטוריה</>}</span></span></span>
              </li>))}
            </ul>
          </section>
        )}
        <div className="section-label dx-label" id="sec-uploaded">{en ? <>Uploaded documents <span className="dx-count">{docs.length}</span></>
          : <>מסמכים שהועלו <span className="dx-count">{docs.length}</span></>}</div>
        {docs.length === 0 && (
          <div className="dx-empty" data-testid="docs-empty">
            <span className="dx-empty-ic" aria-hidden><IDocs size={22} /></span>
            <div className="dx-empty-title">{t("עוד לא הועלו מסמכים", "No documents uploaded yet")}</div>
            <div className="dx-empty-sub">{t("לחצו ״להעלאה״ באחד הכרטיסים למעלה.", "Tap \u201cUpload\u201d on one of the cards above.")}</div>
          </div>
        )}
        {docs.map((d) => (
          <button key={d.document_id} className="doc-card pressable" onClick={() => nav(`/customer/documents/${d.document_id}`)} data-testid="doc-card">
            <span className="doc-icon">{d.mime === "application/pdf" ? "PDF" : "IMG"}</span>
            <span className="grow">
              <div className="doc-name">{d.filename}</div>
              <div className="doc-meta">
                {[familyOf(d.requirement_code), borrowerName(d.borrower_id)].filter(Boolean).join(" · ")}
                {d.review?.period ? t(` · מודפס ${monthHe(d.review.period)}`, ` · printed ${monthL(d.review.period)}`) : ""}{d.review?.is_scanned ? t(" · סרוק", " · scanned") : ""}
                {d.review?.facts.find((f) => f.field === "net_pay") ? t(` · נטו ${ils(Number(d.review.facts.find((f) => f.field === "net_pay")!.value_normalized))}`,
                  ` · net ${ilsL(Number(d.review.facts.find((f) => f.field === "net_pay")!.value_normalized))}`) : ""}
              </div>
              {docStatus[d.document_id] && (
                <div className={`doc-banker ${docStatus[d.document_id].status}`} data-testid="doc-banker-status">
                  {(en && docStatus[d.document_id].status_en) || docStatus[d.document_id].status_he}
                  {docStatus[d.document_id].replaces && docName(docStatus[d.document_id].replaces) ? t(` במקום ${docName(docStatus[d.document_id].replaces)}`, ` instead of ${docName(docStatus[d.document_id].replaces)}`) : ""}
                </div>
              )}
            </span>
            {d.review ? (() => {
              const v = customerVerdict(d.review.verdict, snap.outcomes?.documents[d.document_id]);
              return <span className={`badge ${v.cls}`} data-testid="doc-verdict">{v.text}</span>;
            })()
              : d.status === "failed" ? <span className="badge bad">{t("נכשל", "Failed")}</span>
              : d.status === "stored" ? <span className="badge info" data-testid="doc-human-review">{t("לבדיקת הבנקאי", "For the banker's review")}</span>
                : <span className="badge neutral"><span className="spinner" />{(en && d.stage_en) || d.stage_he}</span>}
            <span className="chev"><IChevron size={16} /></span>
          </button>
        ))}

      </>)}
      {tab === "bank" && (<>
        {snap.case.preliminary_decision && (
          <div className="card">
            <div className="card-title">{(en && snap.case.preliminary_decision.label_en) || snap.case.preliminary_decision.label_he}</div>
            <div className="kv"><span>{t("סכום", "Amount")}</span><span className="ltr">{en ? ilsL(snap.case.preliminary_decision.amount_ils) : ils(snap.case.preliminary_decision.amount_ils)}</span></div>
            <div className="kv"><span>{t("הונפק", "Issued")}</span><span className="ltr">{snap.case.preliminary_decision.issued_on}</span></div>
            <div className="kv"><span>{t("בתוקף עד", "Valid until")}</span><span className="ltr">{snap.case.preliminary_decision.valid_until}</span></div>
            <div className="tiny muted" style={{ marginTop: 8 }}>{t("אישור עקרוני כפוף לאימות הנתונים ואינו אישור סופי.", "A preliminary approval is subject to verifying the details and is not a final approval.")}</div>
          </div>
        )}
        {snap.readiness.banker_confirmation ? (
          <div className="card"><div className="card-title">{t("הבנקאית אישרה את הכנת מסמכי הבקשה", "Your banker confirmed your documents are prepared")}</div>
            <div className="small muted" style={{ marginTop: 4 }}>{t("אישור הכנת מסמכים בלבד, לא החלטה על ההלוואה.", "This confirms the documents only — it is not a decision on the loan.")}</div></div>
        ) : <div className="card small muted">{t("אישורים נוספים מהבנק יופיעו כאן כשהבנק ינפיק אותם.", "Further approvals from the bank will appear here once the bank issues them.")}</div>}
      </>)}
    </>
  );
}
