import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, customerVerdict, FAMILY_HE, ils, monthHe, timeHe, type Requirement } from "../../api";
import { useCase } from "../../caseContext";
import { ApplyHandoff } from "./ApplyV2";
import { IBag, IBank, IChart, ICheck, IChevron, IChevronDown, IClock, IDocs, IHouse, IPerson, IShield, ISpark, IUpload, IX } from "../../components/Icons";

const LOAN_ICON: Record<string, ReactNode> = { id_document: <IPerson size={18} />, bank_statement: <IBank size={18} />,
  purpose_proof: <IBag size={18} />, tax_form: <IChart size={18} />, business_registration: <IShield size={18} />,
  pnl_statement: <IChart size={18} />, company_registry: <IShield size={18} />, signatory_authority: <IPerson size={18} />,
  financial_statements: <IChart size={18} />, business_bank_statement: <IBank size={18} /> };
/** A requirement the customer can upload for in the app: reviewed by AI, or stored for the banker (no rubric). */
export const uploadable = (r: Requirement) => r.evaluated_by_ai || r.intake === "human_review";
const DONE_STATES = ["extracted", "preparation_confirmed", "checking", "accepted_by_banker"];

/** Who the checklist was composed for, from the case's document profile — the same inputs the policy read. */
function ProfileCard() {
  const { snap } = useCase();
  const [editing, setEditing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const p = snap?.case.document_profile;
  if (!snap || !p) return null;
  const version = snap.readiness.requirements[0]?.policy_version;
  return (
    <section className="dx-profile" data-testid="document-profile" data-entity={p.entity} data-use-case={p.use_case || undefined}>
      <div className="dx-profile-head">
        <span className="bold small">פרופיל המסמכים של הבקשה</span>
        {p.profile_label_he && <span className="badge info" data-testid="profile-label">{p.profile_label_he}</span>}
      </div>
      {p.company && <div className="small" data-testid="profile-company"><b>{p.company.name_he}</b> · <span className="ltr">{p.company.company_number}</span> · {p.company.signatory_role_he}: {p.company.signatory_he}</div>}
      <ul className="dx-profile-people">
        {p.applicants.map((a) => (
          <li key={a.borrower_id} data-testid="profile-applicant" data-borrower={a.borrower_id}>
            <b>{a.name_he}</b> · {a.role_he}{a.profile_he && a.profile_he !== a.role_he ? ` · ${a.profile_he}` : ""}</li>
        ))}
        {p.accounts.flatMap((acc) => acc.other_holders_he).map((h) => <li key={h} className="muted" data-testid="profile-other-holder">{h}</li>)}
      </ul>
      {p.banker_assisted && (
        <div className="notice navy small" data-testid="banker-assisted">מסלול עסקי מוגבל בליווי {snap.case.banker.name_he}: אוספים כאן את מסמכי
          הזיהוי והדוחות של החברה, והבנקאית ממשיכה את הטיפול. אין חיתום עסקי ואין החלטת אשראי אוטומטית.</div>
      )}
      {p.entity === "individual" && !editing && (
        <button className="link small dx-profile-edit" onClick={() => { setEditing(true); setResult(null); }} data-testid="profile-edit">
          עדכון מקורות ההכנסה</button>
      )}
      {editing && <ProfileEditor onDone={(text) => { setEditing(false); setResult(text); }} />}
      {result && <div className="notice navy small" role="status" data-testid="profile-change-result">{result}</div>}
      <div className="tiny muted dx-profile-note">{p.disclaimer_he}{version ? <> · <span className="ltr">{version}</span></> : null}</div>
    </section>
  );
}

const INCOME_OPTS: [string, string][] = [["salaried", "שכיר/ה"], ["self_employed", "עצמאי/ת"]];
const REG_OPTS: [string, string][] = [["vat_exempt", "עוסק פטור"], ["vat_registered", "עוסק מורשה"]];

/** The customer corrects an income profile after confirming: the same policy recomposes the checklist on the server.
 *  Uploaded documents and their review history are kept. */
function ProfileEditor({ onDone }: { onDone: (text: string | null) => void }) {
  const { snap, caseId, reload } = useCase();
  const people = snap!.case.document_profile!.applicants;
  const [draft, setDraft] = useState(() => Object.fromEntries(people.map((a) => [a.borrower_id,
    { income_sources: a.income_sources, business_registration: a.business_registration || null }])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toggle = (bid: string, src: string) => setDraft((d) => {
    const cur = d[bid].income_sources;
    return { ...d, [bid]: { ...d[bid], income_sources: cur.includes(src) ? cur.filter((x) => x !== src) : [...cur, src] } };
  });
  const save = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.changeProfile(caseId, draft);
      reload();
      onDone(!r.changed ? "לא בוצע שינוי בפרופיל." : [r.added.length ? `נוספו: ${r.added.join(" · ")}` : "",
        r.removed.length ? `לא נדרשים עוד: ${r.removed.join(" · ")} (המסמכים שכבר הועלו נשמרים)` : "",
        r.tasks_canceled.length ? "בקשות ההשלמה הקשורות בוטלו." : ""].filter(Boolean).join(". ") || "הפרופיל עודכן.");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="dx-profile-editor" data-testid="profile-editor">
      {people.map((a) => (
        <div key={a.borrower_id} className="stack" style={{ gap: 6 }} data-testid="profile-editor-person" data-borrower={a.borrower_id}>
          <div className="small bold">{a.name_he}</div>
          <div className="choice">
            {INCOME_OPTS.map(([k, label]) => (
              <label key={k} className={draft[a.borrower_id].income_sources.includes(k) ? "on" : ""}>
                <input type="checkbox" checked={draft[a.borrower_id].income_sources.includes(k)} onChange={() => toggle(a.borrower_id, k)}
                  data-testid={`profile-income-${k}`} /><span>{label}</span></label>
            ))}
          </div>
          {draft[a.borrower_id].income_sources.includes("self_employed") && (
            <div className="choice">
              {REG_OPTS.map(([k, label]) => (
                <label key={k} className={draft[a.borrower_id].business_registration === k ? "on" : ""}>
                  <input type="radio" name={`reg-${a.borrower_id}`} checked={draft[a.borrower_id].business_registration === k}
                    onChange={() => setDraft((d) => ({ ...d, [a.borrower_id]: { ...d[a.borrower_id], business_registration: k } }))}
                    data-testid={`profile-reg-${k}`} /><span>{label}</span></label>
              ))}
            </div>
          )}
        </div>
      ))}
      <div className="tiny muted">רשימת המסמכים תחושב מחדש לפי אותה מדיניות. מסמכים שכבר הועלו נשמרים בתיק.</div>
      {error && <div className="notice small" role="alert">{error}</div>}
      <div className="row" style={{ gap: 8 }}>
        <button className="btn btn-orange" disabled={busy} onClick={save} data-testid="profile-save">{busy && <span className="spinner" />}שמירת השינוי</button>
        <button className="btn btn-ghost" disabled={busy} onClick={() => onDone(null)}>ביטול</button>
      </div>
    </div>
  );
}

/** A one-document requirement of the loan (ID, a statement of one account, proof of purpose, tax form, business documents). */
function LoanDocRow({ r, focused, expanded, setExpanded }: { r: Requirement; focused: boolean;
  expanded: Record<string, boolean>; setExpanded: (v: Record<string, boolean>) => void }) {
  const { snap, docs, openUpload, openAssistant } = useCase();
  if (!snap) return null;
  const mineDocs = new Set(docs.filter((d) => d.requirement_code === r.code).map((d) => d.document_id));
  const findings = snap.findings.filter((f) => f.status === "open" && f.review_state === "CUSTOMER_ACTION_REQUIRED"
    && (mineDocs.has(f.document_id || "") || f.detail?.requirement_code === r.code));
  // a missing document or a gap in the period asks for a first upload, not for replacing an uploaded one
  const firstUpload = r.ai_state === "required_missing" || (findings.length > 0 && !findings.some((f) => f.document_id));
  const isOpen = expanded[r.code] ?? focused;
  const [name, detail] = splitTitle(r.title_he);
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
          {r.ai_state === "required_missing" ? "טרם הועלה" : r.ai_state_he}</span>
        <span className="dl-chev" aria-hidden><IChevron size={16} /></span>
      </button>
      {isOpen && (
        <div className="dl-body">
          {r.hint_he && <p className="dl-note">{r.hint_he}</p>}
          {(r.owner_he || r.why_he) && (
            <p className="dl-note" data-testid="req-why">{r.owner_he && <><b>עבור: </b>{r.owner_he}. </>}{r.why_he && <><b>למה: </b>{r.why_he}</>}</p>
          )}
          {(r.alternatives_he?.length ?? 0) > 0 && (
            <p className="dl-note" data-testid="req-alternatives"><b>מתקבל גם: </b>{r.alternatives_he!.join(" · ")}</p>
          )}
          {human && <p className="dl-note dl-human" data-testid="req-human-review">סוג מסמך זה אינו נבדק ב-AI: הקובץ נשמר בתיק
            ועובר לבדיקת {snap.case.banker.name_he}. הוא לא יסומן ״תקין״ אוטומטית.</p>}
          {findings.map((f) => <div key={f.finding_id} className="small" style={{ marginTop: 6, lineHeight: 1.55 }}>• {f.message_he}</div>)}
          <div className="req-actions">
            <button className="link req-more" onClick={() => openAssistant(`מה בדיוק צריך להעלות עבור ${name}?`)}>
              למידע נוסף<IChevron size={14} /></button>
            {!DONE_STATES.includes(r.ai_state) && (
              <button className="btn btn-dark req-upload" onClick={() => openUpload(r.borrower_id || undefined, { requirementCode: r.code })}
                data-testid={`upload-${r.code}`}><IUpload size={15} />{firstUpload ? "להעלאה" : "העלאה מחדש"}</button>
            )}
          </div>
          <div className="dl-bank"><IClock size={13} />{human ? "בדיקת בנקאי — ללא בדיקת AI" : "ממתין לאישור הבנק"}</div>
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
  if (n) return { text: n === 1 ? "חסר תלוש" : n === (r.required ?? n) ? "חסר" : `חסרים ${n}`, tone: "bad" };
  return { text: r.ai_state_he, tone: STATE_TONE[r.ai_state] || "warn" };
}

function MonthChips({ r }: { r: Requirement }) {
  return (
    <div className="month-chips">
      {(r.requested_months || []).map((m) => {
        const copies = r.duplicates?.[m];
        const covered = r.covered?.includes(m);
        const month = <span className="mchip-month">{monthHe(m)}</span>;
        if (!covered) return <span key={m} className="mchip miss">{month} <span className="mchip-state"><IX size={11} />חסר</span></span>;
        if (r.pending_review?.includes(m)) return <span key={m} className="mchip review">{month} <span className="mchip-state"><IClock size={11} />בבדיקה</span></span>;
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
  const loaded = !!snap;
  useEffect(() => {
    if (!snap) return;
    // req=<requirement>: the follow-up's secure link lands here and opens that requirement's upload, like upload=
    const want = params.get("upload") || params.get("req"), section = params.get("focus"), forCase = params.get("case"), reqId = params.get("request");
    const replace = params.get("replace");
    if (!want && !section && !reqId && !replace) return;
    setParams({}, { replace: true });
    setTab("list");
    if (forCase && forCase !== caseId) { setLinkNote("הקישור שייך לתיק אחר ולכן לא נפתח. מוצג התיק הפעיל שלכם."); return; }
    setLinkNote(null);
    if (replace) {
      // replace=<document>: the upload that replaces a document the AI review sent back (checked again by the server)
      const old = docs.find((d) => d.document_id === replace);
      if (snap.outcomes?.documents[replace]?.outcome !== "BLOCKER") { setLinkNote("המסמך הזה כבר אינו ממתין להחלפה."); return; }
      setFocus("sec-uploaded");
      openUpload(old?.borrower_id || snap.case.borrowers[0]?.borrower_id, { requirementCode: old?.requirement_code || undefined, replacesDocumentId: replace });
      return;
    }
    if (reqId) {
      const q = snap.customer_requests?.find((x) => x.customer_request_id === reqId);
      if (!q) { setLinkNote("הבקשה לא נמצאה בתיק הפעיל."); return; }
      setFocus(`creq-${q.customer_request_id}`);
      if (q.status !== "OPEN") { setLinkNote("כבר השבתם לבקשה הזו. היא אצל הבנקאי."); return; }
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
    if (!req) { setLinkNote("לא ניתן להעלות את סוג המסמך הזה באפליקציה."); return; }
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
  const borrowerName = (id?: string | null) => snap.case.borrowers.find((b) => b.borrower_id === id)?.first_name_he || "";
  const docStatus = snap.document_status || {};
  const requests = (snap.customer_requests || []).filter((q) => q.status === "OPEN" || !!q.responded_text
    || (q.responded_document_id && docStatus[q.responded_document_id]?.status !== "ACCEPTED"));
  const docName = (id?: string | null) => docs.find((d) => d.document_id === id)?.filename;
  const familyOf = (code?: string | null) => {
    const r = reqs.find((x) => x.code === code);
    return r ? r.family_he || FAMILY_HE[r.family] : "";
  };
  const required = snap.readiness.payslips?.required ?? 0;
  const verified = snap.readiness.payslips?.verified ?? 0;
  const allVerified = required > 0 && verified >= required;
  return (
    <>
      <div className="page-title">מסמכים</div>
      <p className="page-sub docs-sub">ריכזנו כאן את המסמכים הנדרשים לבקשת ההלוואה. כל מסמך נבדק בבדיקת המסמכים החכמה של JEEN מיד עם ההעלאה.</p>
      <div className="segmented docs-tabs" role="tablist">
        <button className={tab === "list" ? "on" : ""} onClick={() => setTab("list")} role="tab">רשימת מסמכים</button>
        <button className={tab === "bank" ? "on" : ""} onClick={() => setTab("bank")} role="tab">אישורים מהבנק</button>
      </div>
      {linkNote && <div className="notice" role="status" style={{ marginBottom: 12 }} data-testid="link-note">{linkNote}</div>}
      <ApplyHandoff />
      {tab === "list" && (<>
        <ProfileCard />
        {requests.length > 0 && (<>
          <div className="section-label" id="sec-requests">בקשות מ{snap.case.banker.name_he}</div>
          {requests.map((q) => {
            const open = q.status === "OPEN";
            const replacement = docs.find((d) => d.document_id === q.responded_document_id);
            return (
              <div key={q.customer_request_id} id={`creq-${q.customer_request_id}`} data-testid="customer-request" data-status={q.status}
                className={`creq-card${open ? " open" : ""}${focus === `creq-${q.customer_request_id}` ? " focus" : ""}`}>
                <div className="creq-from">{open ? "בקשה חדשה" : "המסמך התקבל"} · {q.created_by_name || snap.case.banker.name_he} · <span className="ltr">{timeHe(q.created_at)}</span></div>
                <div className="creq-title">{q.title_he}</div>
                <div className="creq-msg">{q.message_he}</div>
                {q.document_filename && <div className="tiny muted">המסמך שהוחזר: <span className="ltr">{q.document_filename}</span></div>}
                {open && q.can_reply ? (<>
                  {replying === q.customer_request_id ? (
                    <div className="creq-reply" data-testid="request-reply">
                      <textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="כתבו כאן את ההסבר" maxLength={1000} data-testid="request-reply-text" />
                      <div className="tiny muted">ההסבר יישמר בתיק ויועבר ל{snap.case.banker.name_he}. הוא אינו סוגר את הבירור; ייתכן שתתבקשו גם מסמך תומך.</div>
                      {replyError && <div className="small" role="alert" style={{ color: "var(--bad)" }}>{replyError}</div>}
                      <div className="creq-btns">
                        <button className="btn btn-orange" disabled={replyBusy || !reply.trim()} data-testid="request-reply-send" onClick={async () => {
                          setReplyBusy(true); setReplyError(null);
                          try { await api.replyToRequest(caseId, q.customer_request_id, reply.trim()); setReplying(null); setReply(""); reload(); }
                          catch (e) { setReplyError((e as Error).message); } finally { setReplyBusy(false); }
                        }}>{replyBusy && <span className="spinner" />}שליחת ההסבר</button>
                        <button className="btn btn-soft" onClick={() => setReplying(null)}>ביטול</button>
                      </div>
                    </div>
                  ) : (
                    <div className="creq-btns">
                      <button className="btn btn-orange" data-testid="request-reply-open" onClick={() => setReplying(q.customer_request_id)}>השבה בכתב</button>
                      <button className="btn btn-ghost" data-testid="request-upload" onClick={() => openUpload(q.borrower_id || undefined,
                        { requirementCode: q.requirement_code || undefined, period: q.period, customerRequestId: q.customer_request_id })}>צירוף מסמך</button>
                    </div>
                  )}
                </>) : open ? (
                  <button className="btn btn-orange creq-btn" data-testid="request-upload"
                    onClick={() => openUpload(q.borrower_id || undefined, { requirementCode: q.requirement_code || undefined, period: q.period,
                      customerRequestId: q.customer_request_id })}>להעלאת המסמך</button>
                ) : q.responded_text ? (
                  <div className="small creq-done" data-testid="request-answered">השבתם: „{q.responded_text}”. ההסבר הועבר ל{snap.case.banker.name_he}.</div>
                ) : (
                  <div className="small creq-done" data-testid="request-answered">
                    העליתם את <span className="ltr">{q.responded_filename || replacement?.filename}</span>
                    {replacement && !replacement.review ? " — בבדיקה חכמה עכשיו." : ` — נבדק וממתין לעיון של ${snap.case.banker.name_he}.`}
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
              <h2 className="dx-jeen-title" id="dx-jeen-title">בדיקת מסמכים חכמה<img src="/brand/jeen-logo.png" alt="של JEEN" /></h2>
              {progress && progress.total > 0 ? (<>
                <div className="dx-jeen-progress" data-testid="docs-progress"><b>{progress.done} מתוך {progress.total}</b> דרישות הושלמו</div>
                <span className="dx-meter" aria-hidden><span style={{ width: `${Math.round((progress.done / progress.total) * 100)}%` }} /></span>
              </>) : required > 0 && (<>
                <div className="dx-jeen-progress"><b>{verified} מתוך {required}</b> תלושי שכר הושלמו</div>
                <span className="dx-meter" aria-hidden><span style={{ width: `${Math.round((verified / required) * 100)}%` }} /></span>
              </>)}
              <div className="dx-jeen-text">{reviewedValid === 1 ? "מסמך אחד נמצא תקין" : `${reviewedValid} מסמכים נמצאו תקינים`} · טרם אושרו בבנק</div>
            </div>
          </div>
          <div className="dx-jeen-note"><span>לאחר העלאת המסמכים נעדכן אתכם בתוצאות הבדיקה ובכל פעולה נדרשת.</span><IClock size={18} /></div>
        </section>

        <section className="dl-card" id="sec-payslips" aria-label="רשימת המסמכים הנדרשים" data-testid="required-docs">
          <button className="dl-top" onClick={() => setListOpen(!listOpen)} aria-expanded={listOpen} aria-controls="dl-list">
            <span className="dl-top-ic" aria-hidden><IDocs size={20} /></span>
            <span className="grow dl-text">
              <span className="dl-title">רשימת המסמכים הנדרשים</span>
              <span className="dl-sub">לפי מדיניות המסמכים של הבקשה · נבדקים באופן חכם באמצעות JEEN.</span>
            </span>
            <span className={`dl-toggle${listOpen ? " open" : ""}`} aria-hidden><IChevronDown size={18} /></span>
          </button>
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
                        <span className="dl-name">{name ? `תלושי שכר — ${name}` : r.title_he}</span>
                        <span className="dl-detail">{r.required ? `${r.required} החודשים האחרונים` : splitTitle(r.title_he)[1]}</span>
                      </span>
                      <span className={`dl-pill ${pill.tone}`}>{r.ai_state === "checking" && <span className="spinner" />}{pill.text}</span>
                      <span className="dl-chev" aria-hidden><IChevron size={16} /></span>
                    </button>
                    {isOpen && (
                      <div className="dl-body">
                        {(r.missing?.length ?? 0) > 0 && <div className="req-new">
                          {r.missing!.length === 1 ? `חסר תלוש ${monthHe(r.missing![0])}` : `חסרים ${r.missing!.length} תלושים`}</div>}
                        <MonthChips r={r} />
                        {mine.map((f) => <div key={f.finding_id} className="small" style={{ marginTop: 6, lineHeight: 1.55 }}>• {f.message_he}</div>)}
                        <div className="req-actions">
                          <button className="link req-more" onClick={() => openAssistant(`מה בדיוק צריך להעלות עבור ${name}?`)}>
                            למידע נוסף<IChevron size={14} /></button>
                          <button className="btn btn-dark req-upload" onClick={() => openUpload(r.borrower_id || undefined, { requirementCode: r.code })}
                            data-testid={`upload-${r.borrower_id}`}><IUpload size={15} />להעלאה</button>
                        </div>
                        <div className="dl-bank"><IClock size={13} />ממתין לאישור הבנק</div>
                      </div>
                    )}
                  </li>
                );
              })}
              {loanDocs.filter((r) => r.family !== "id_document").map((r) => (
                <LoanDocRow key={r.code} r={r} focused={focus === `req-${r.code}`} expanded={expanded} setExpanded={setExpanded} />))}
              {others.map((r) => {
                const [name, detail] = splitTitle(r.title_he);
                const isOpen = !!expanded[r.code];
                return (
                  <li key={r.code} className={`dl-row${isOpen ? " open" : ""}`} data-code={r.code} data-testid="other-doc">
                    <button className="dl-head" onClick={() => setExpanded({ ...expanded, [r.code]: !isOpen })} aria-expanded={isOpen}>
                      <span className="dl-ic" aria-hidden>{FAMILY_ICON[r.family] || <IDocs size={18} />}</span>
                      <span className="grow dl-text">
                        <span className="dl-name">{name}</span>
                        {detail && <span className="dl-detail" title={detail}>{detail}</span>}
                      </span>
                      <span className="dl-pill neutral">{r.bank_status === "awaiting_documents" ? "טרם הועלה" : "מול הבנק"}</span>
                      <span className="dl-chev" aria-hidden><IChevron size={16} /></span>
                    </button>
                    {isOpen && (
                      <div className="dl-body">
                        <p className="dl-note">המסמך מטופל ישירות מול הבנק ואינו נבדק באפליקציה.</p>
                        <button className="link req-more" onClick={() => openAssistant(`מה צריך לדעת על ${name}?`)}>שאלו את העוזר<IChevron size={14} /></button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {(snap.readiness.inactive_requirements?.length ?? 0) > 0 && (
          <section className="dl-card dl-inactive" data-testid="inactive-requirements" aria-label="מסמכים שאינם נדרשים עוד">
            <div className="small bold">לא נדרשים עוד אחרי עדכון הפרופיל</div>
            <ul className="dl-list">{snap.readiness.inactive_requirements!.map((r) => (
              <li key={r.code} className="dl-row" data-testid="inactive-requirement" data-code={r.code}>
                <span className="dl-head"><span className="grow dl-text"><span className="dl-name">{r.family_he}</span>
                  <span className="dl-detail">{r.state_he} · {r.document_ids.length} מסמכים נשמרו בהיסטוריה</span></span></span>
              </li>))}
            </ul>
          </section>
        )}
        <div className="section-label dx-label" id="sec-uploaded">מסמכים שהועלו <span className="dx-count">{docs.length}</span></div>
        {docs.length === 0 && (
          <div className="dx-empty" data-testid="docs-empty">
            <span className="dx-empty-ic" aria-hidden><IDocs size={22} /></span>
            <div className="dx-empty-title">עוד לא הועלו מסמכים</div>
            <div className="dx-empty-sub">לחצו ״להעלאה״ באחד הכרטיסים למעלה.</div>
          </div>
        )}
        {docs.map((d) => (
          <button key={d.document_id} className="doc-card pressable" onClick={() => nav(`/customer/documents/${d.document_id}`)} data-testid="doc-card">
            <span className="doc-icon">{d.mime === "application/pdf" ? "PDF" : "IMG"}</span>
            <span className="grow">
              <div className="doc-name">{d.filename}</div>
              <div className="doc-meta">
                {[familyOf(d.requirement_code), borrowerName(d.borrower_id)].filter(Boolean).join(" · ")}
                {d.review?.period ? ` · מודפס ${monthHe(d.review.period)}` : ""}{d.review?.is_scanned ? " · סרוק" : ""}
                {d.review?.facts.find((f) => f.field === "net_pay") ? ` · נטו ${ils(Number(d.review.facts.find((f) => f.field === "net_pay")!.value_normalized))}` : ""}
              </div>
              {docStatus[d.document_id] && (
                <div className={`doc-banker ${docStatus[d.document_id].status}`} data-testid="doc-banker-status">
                  {docStatus[d.document_id].status_he}
                  {docStatus[d.document_id].replaces && docName(docStatus[d.document_id].replaces) ? ` במקום ${docName(docStatus[d.document_id].replaces)}` : ""}
                </div>
              )}
            </span>
            {d.review ? (() => {
              const v = customerVerdict(d.review.verdict, snap.outcomes?.documents[d.document_id]);
              return <span className={`badge ${v.cls}`} data-testid="doc-verdict">{v.text}</span>;
            })()
              : d.status === "failed" ? <span className="badge bad">נכשל</span>
              : d.status === "stored" ? <span className="badge info" data-testid="doc-human-review">לבדיקת הבנקאי</span>
                : <span className="badge neutral"><span className="spinner" />{d.stage_he}</span>}
            <span className="chev"><IChevron size={16} /></span>
          </button>
        ))}

      </>)}
      {tab === "bank" && (<>
        {snap.case.preliminary_decision && (
          <div className="card">
            <div className="card-title">{snap.case.preliminary_decision.label_he}</div>
            <div className="kv"><span>סכום</span><span className="ltr">{ils(snap.case.preliminary_decision.amount_ils)}</span></div>
            <div className="kv"><span>הונפק</span><span className="ltr">{snap.case.preliminary_decision.issued_on}</span></div>
            <div className="kv"><span>בתוקף עד</span><span className="ltr">{snap.case.preliminary_decision.valid_until}</span></div>
            <div className="tiny muted" style={{ marginTop: 8 }}>אישור עקרוני כפוף לאימות הנתונים ואינו אישור סופי.</div>
          </div>
        )}
        {snap.readiness.banker_confirmation ? (
          <div className="card"><div className="card-title">הבנקאית אישרה את הכנת מסמכי הבקשה</div>
            <div className="small muted" style={{ marginTop: 4 }}>אישור הכנת מסמכים בלבד — לא החלטה על ההלוואה.</div></div>
        ) : <div className="card small muted">אישורים נוספים מהבנק יופיעו כאן כשהבנק ינפיק אותם.</div>}
      </>)}
    </>
  );
}
