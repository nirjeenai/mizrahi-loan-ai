import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Requirement } from "../api";
import { useCase } from "../caseContext";
import { joinHe, monthName, nextUpload, uploadLink, type UploadAction } from "./DocumentCheckCard";
import { IChevron, IInfo, IPerson, ISpark, IUpload } from "./Icons";

function rowLabel(q: Requirement): { text: string; tone: string } {
  const missing = q.missing || [];
  const payslip = q.family === "payslip";
  if (!payslip) {
    if (q.ai_state === "required_missing") return { text: "טרם הועלה", tone: "" };
    if (q.customer_status === "CHECKS_COMPLETE") return { text: "נמצא תקין", tone: "ok" };
    if (q.customer_status === "MISSING_DOCUMENTS") return { text: q.open_customer_requests ? "בקשה מהבנק" : "חסרה תקופה", tone: "warn" };
  }
  switch (q.customer_status) {
    case "AWAITING_UPLOAD": return { text: payslip ? "טרם הועלו תלושים" : "טרם הועלה", tone: "" };
    case "ERROR": return { text: "הבדיקה לא הושלמה", tone: "bad" };
    case "PROCESSING": case "REVALIDATING": return { text: "בבדיקה", tone: "info" };
    case "CORRECTION_REQUIRED": return { text: missing.length === 1 ? `נדרש תלוש ${monthName(missing[0])}` : "נדרש תיקון", tone: "bad" };
    case "MISSING_DOCUMENTS":
      return { text: missing.length === 1 ? `חסר תלוש ${monthName(missing[0])}` : missing.length === 2 ? `חסרים ${joinHe(missing.map(monthName))}`
        : missing.length ? `חסרים ${missing.length} תלושים` : q.open_customer_requests ? "בקשה מהבנק" : "חסר מסמך", tone: "warn" };
    case "BANKER_REVIEW": return { text: "בבירור בנקאי", tone: "info" };
    case "PREPARATION_CONFIRMED": return { text: "הכנה אושרה", tone: "ok" };
    case "CHECKS_COMPLETE": return { text: "נמצאו תקינים", tone: "ok" };
    default: return { text: q.ai_state_he, tone: "" };
  }
}

/** Below the action card: how far each borrower's required payslips are, counted the way the backend counts them.
 *  Uploaded, reviewed, accepted by the banker and fulfilled months are four different numbers and stay separate. */
export function DocumentSummary() {
  const { snap, caseId } = useCase();
  const nav = useNavigate();
  const [how, setHow] = useState(false);
  useEffect(() => setHow(false), [caseId]);
  if (!snap) return null;
  const r = snap.readiness;
  const status = r.customer_status;
  const reqs = r.requirements.filter((q) => q.evaluated_by_ai);
  const people = Object.fromEntries(snap.case.borrowers.map((b) => [b.borrower_id, b]));
  const bankerName = snap.case.banker.name_he;
  const required = r.progress?.total ?? r.payslips?.required ?? 0;
  const verified = r.progress?.done ?? r.payslips?.verified ?? 0;
  const showProgress = !!status && status !== "NO_PAYSLIPS_REQUIRED" && required > 0;
  const c = r.counts;

  // a second upload entry only for a borrower the action card above does not already lead to; a borrower with an
  // open banker request is answered through that request, so it never gets a plain upload here
  const uploads = (snap.available_actions || []).filter((a): a is UploadAction => a.type === "NAVIGATE_TO_DOCUMENT_UPLOAD");
  const asked = (snap.customer_requests || []).filter((q) => q.status === "OPEN");
  const covered = new Set<string>(asked.map((q) => q.borrower_id || "*"));
  if (!asked.length && status === "MISSING_DOCUMENTS" && nextUpload(uploads)) covered.add(nextUpload(uploads).params.requirement_code);
  if (!asked.length && status === "CORRECTION_REQUIRED")
    snap.findings.filter((f) => f.status === "open" && f.review_state === "CUSTOMER_ACTION_REQUIRED" && f.document_id)
      .forEach((f) => covered.add(f.borrower_id || "*"));
  const secondary = (status === "MISSING_DOCUMENTS" || status === "CORRECTION_REQUIRED") && !covered.has("*")
    ? uploads.find((a) => !covered.has(a.params.requirement_code) && !covered.has(a.params.borrower_id || "")) : undefined;

  // files, not months: uploaded → reviewed by the AI check → accepted by the banker (the fulfilled months are the total above)
  const bankerFirst = bankerName.split(" ")[0];
  const facts = c.documents ? `קבצים: ${[
    c.documents === 1 ? "1 הועלה" : `${c.documents} הועלו`,
    c.reviewed === 1 ? "1 נבדק" : `${c.reviewed} נבדקו`,
    c.documents_accepted ? `${c.documents_accepted} ${c.documents_accepted === 1 ? "התקבל" : "התקבלו"} אצל ${bankerFirst}` : null,
  ].filter(Boolean).join(" · ")}` : null;
  const others = r.not_evaluated.length;

  return (
    <section className="card sum-card" aria-labelledby="sum-heading" data-testid="doc-summary">
      <div className="sum-head">
        <span className="sum-ic" aria-hidden><ISpark size={18} /></span>
        <div className="grow">
          <h2 className="sum-title with-brand" id="sum-heading">בדיקת מסמכים חכמה<img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="של JEEN" /></h2>
          {showProgress
            ? <div className="sum-total" data-testid="card-total"><b>{verified} מתוך {required}</b> דרישות מסמכים הושלמו</div>
            : <div className="sum-total">{status === "NO_PAYSLIPS_REQUIRED" ? "אין מסמכים לבדיקה בתיק זה" : "טוען…"}</div>}
        </div>
        <button className="icon-btn sum-go" onClick={() => nav("/customer/documents")} aria-label="לכל המסמכים"><IChevron /></button>
      </div>

      {showProgress && (<>
        <ul className="sum-rows">
          {reqs.map((q) => {
            const label = rowLabel(q);
            const done = q.units_verified ?? q.verified_months?.length ?? 0;
            const of = q.units_required ?? q.required ?? 0;
            const person = people[q.borrower_id || ""]?.first_name_he || "";
            const kind = q.family_he || q.family;
            const name = q.family === "payslip" ? `תלושי שכר${person ? ` · ${person}` : ""}`
              : `${kind}${person && snap.case.borrowers.length > 1 ? ` · ${person}` : ""}`;
            return (
              <li key={q.code}>
                <button className="sum-row pressable" data-testid="card-borrower" data-borrower={q.borrower_id || ""} data-requirement={q.code}
                  onClick={() => nav(`/customer/documents?focus=${encodeURIComponent(q.code)}`)} aria-label={`${name}: ${done} מתוך ${of} הושלמו, ${label.text}`}>
                  <span className={`sum-person${label.tone === "ok" ? " ok" : ""}`} aria-hidden><IPerson size={18} /></span>
                  <span className="sum-who grow"><span className="who">{name}</span><span className={`what ${label.tone}`}>{label.text}</span></span>
                  <span className="sum-meter" aria-hidden><span style={{ width: `${of ? Math.round((done / of) * 100) : 0}%` }} /></span>
                  <b className="frac"><span className="ltr">{done}/{of}</span></b>
                  <span className="chev" aria-hidden><IChevron size={16} /></span>
                </button>
              </li>
            );
          })}
        </ul>
      </>)}

      <div className="sum-foot">
        <span className="sum-facts" data-testid="card-facts">{facts || "עוד לא הועלו קבצים"}</span>
        <button className="sum-how" onClick={() => setHow(!how)} aria-expanded={how} aria-controls="sum-how" data-testid="summary-how"
          aria-label="איך סופרים את הדרישות" title="איך סופרים את הדרישות"><IInfo size={16} />
        </button>
      </div>
      {how && (
        <div className="sum-more" id="sum-how" data-testid="summary-how-detail">
          {showProgress && <p>דרישה מושלמת רק כשכל המסמכים שלה נמצאו תקינים בבדיקה החכמה או התקבלו אצל {bankerName}: בתלושים, כל חודש נדרש נספר פעם אחת; בדפי עו״ש, התקופה כולה מכוסה. קובץ שהועלה או נבדק עדיין לא משלים דרישה.</p>}
          {others > 0 && (
            <button className="sum-others" onClick={() => nav("/customer/documents")}>
              <span>עוד {others} מסמכים בתיק מטופלים ישירות מול הבנק</span><IChevron size={14} />
            </button>
          )}
          <div className="sum-note"><img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="Jeen" />
            <span>בדיקת המסמכים מסייעת בהכנת התיק. האישור הסופי נתון לבנק.</span></div>
        </div>
      )}
      {secondary && (
        <button className="btn btn-ghost sum-upload" data-testid="summary-upload" onClick={() => nav(uploadLink(secondary))}>
          <IUpload size={18} />{secondary.label_he}
        </button>
      )}
    </section>
  );
}
