import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Requirement } from "../api";
import { useCase } from "../caseContext";
import { tr, useLang } from "../i18n";
import { joinEn, joinHe, monthName, monthNameEn, nextUpload, uploadLink, type UploadAction } from "./DocumentCheckCard";
import { IChevron, IInfo, IPerson, ISpark, IUpload } from "./Icons";

function rowLabel(q: Requirement): { text: string; tone: string } {
  const missing = q.missing || [];
  const payslip = q.family === "payslip";
  if (!payslip) {
    if (q.ai_state === "required_missing") return { text: tr("טרם הועלה", "Not uploaded yet"), tone: "" };
    if (q.customer_status === "CHECKS_COMPLETE") return { text: tr("נמצא תקין", "Valid"), tone: "ok" };
    if (q.customer_status === "MISSING_DOCUMENTS") return { text: q.open_customer_requests ? tr("בקשה מהבנק", "Request from the bank") : tr("חסרה תקופה", "A period is missing"), tone: "warn" };
  }
  switch (q.customer_status) {
    case "AWAITING_UPLOAD": return { text: payslip ? tr("טרם הועלו תלושים", "No payslips uploaded yet") : tr("טרם הועלה", "Not uploaded yet"), tone: "" };
    case "ERROR": return { text: tr("הבדיקה לא הושלמה", "The check didn't finish"), tone: "bad" };
    case "PROCESSING": case "REVALIDATING": return { text: tr("בבדיקה", "Checking"), tone: "info" };
    case "CORRECTION_REQUIRED": return { text: missing.length === 1 ? tr(`נדרש תלוש ${monthName(missing[0])}`, `${monthNameEn(missing[0])} payslip needed`) : tr("נדרש תיקון", "Needs a correction"), tone: "bad" };
    case "MISSING_DOCUMENTS":
      return { text: tr(missing.length === 1 ? `חסר תלוש ${monthName(missing[0])}` : missing.length === 2 ? `חסרים ${joinHe(missing.map(monthName))}`
        : missing.length ? `חסרים ${missing.length} תלושים` : q.open_customer_requests ? "בקשה מהבנק" : "חסר מסמך",
        missing.length === 1 ? `${monthNameEn(missing[0])} payslip missing` : missing.length === 2 ? `${joinEn(missing.map(monthNameEn))} missing`
          : missing.length ? `${missing.length} payslips missing` : q.open_customer_requests ? "Request from the bank" : "Document missing"), tone: "warn" };
    case "BANKER_REVIEW": return { text: tr("בבירור בנקאי", "With the banker"), tone: "info" };
    case "PREPARATION_CONFIRMED": return { text: tr("הכנה אושרה", "Preparation confirmed"), tone: "ok" };
    case "CHECKS_COMPLETE": return { text: tr("נמצאו תקינים", "All valid"), tone: "ok" };
    default: return { text: tr(q.ai_state_he, q.ai_state_en || q.ai_state_he), tone: "" };
  }
}

/** Below the action card: how far each borrower's required payslips are, counted the way the backend counts them.
 *  Uploaded, reviewed, accepted by the banker and fulfilled months are four different numbers and stay separate. */
export function DocumentSummary() {
  const { snap, caseId } = useCase();
  const nav = useNavigate();
  const { en, t } = useLang();
  const [how, setHow] = useState(false);
  useEffect(() => setHow(false), [caseId]);
  if (!snap) return null;
  const r = snap.readiness;
  const status = r.customer_status;
  const reqs = r.requirements.filter((q) => q.evaluated_by_ai);
  const people = Object.fromEntries(snap.case.borrowers.map((b) => [b.borrower_id, b]));
  const bankerName = (en && snap.case.banker.name_en) || snap.case.banker.name_he;
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
  const facts = !c.documents ? null : en ? `Files: ${[
    `${c.documents} uploaded`, `${c.reviewed} checked`,
    c.documents_accepted ? `${c.documents_accepted} accepted by ${bankerFirst}` : null,
  ].filter(Boolean).join(" · ")}` : `קבצים: ${[
    c.documents === 1 ? "1 הועלה" : `${c.documents} הועלו`,
    c.reviewed === 1 ? "1 נבדק" : `${c.reviewed} נבדקו`,
    c.documents_accepted ? `${c.documents_accepted} ${c.documents_accepted === 1 ? "התקבל" : "התקבלו"} אצל ${bankerFirst}` : null,
  ].filter(Boolean).join(" · ")}`;
  const others = r.not_evaluated.length;

  return (
    <section className="card sum-card" aria-labelledby="sum-heading" data-testid="doc-summary">
      <div className="sum-head">
        <span className="sum-ic" aria-hidden><ISpark size={18} /></span>
        <div className="grow">
          <h2 className="sum-title with-brand" id="sum-heading">{t("בדיקת מסמכים חכמה", "Smart document check")}<img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt={t("של JEEN", "by JEEN")} /></h2>
          {showProgress
            ? <div className="sum-total" data-testid="card-total">{en ? <><b>{verified} of {required}</b> document requirements complete</>
              : <><b>{verified} מתוך {required}</b> דרישות מסמכים הושלמו</>}</div>
            : <div className="sum-total">{status === "NO_PAYSLIPS_REQUIRED" ? t("אין מסמכים לבדיקה בתיק זה", "There are no documents to check in this application") : t("טוען…", "Loading…")}</div>}
        </div>
        <button className="icon-btn sum-go" onClick={() => nav("/customer/documents")} aria-label={t("לכל המסמכים", "All documents")}><IChevron /></button>
      </div>

      {showProgress && (<>
        <ul className="sum-rows">
          {reqs.map((q) => {
            const label = rowLabel(q);
            const done = q.units_verified ?? q.verified_months?.length ?? 0;
            const of = q.units_required ?? q.required ?? 0;
            const person = (en ? people[q.borrower_id || ""]?.first_name_en : undefined) || people[q.borrower_id || ""]?.first_name_he || "";
            const kind = (en && q.family_en) || q.family_he || q.family;
            const name = q.family === "payslip" ? `${t("תלושי שכר", "Payslips")}${person ? ` · ${person}` : ""}`
              : `${kind}${person && snap.case.borrowers.length > 1 ? ` · ${person}` : ""}`;
            return (
              <li key={q.code}>
                <button className="sum-row pressable" data-testid="card-borrower" data-borrower={q.borrower_id || ""} data-requirement={q.code}
                  onClick={() => nav(`/customer/documents?focus=${encodeURIComponent(q.code)}`)} aria-label={t(`${name}: ${done} מתוך ${of} הושלמו, ${label.text}`, `${name}: ${done} of ${of} complete, ${label.text}`)}>
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
        <span className="sum-facts" data-testid="card-facts">{facts || t("עוד לא הועלו קבצים", "No files uploaded yet")}</span>
        <button className="sum-how" onClick={() => setHow(!how)} aria-expanded={how} aria-controls="sum-how" data-testid="summary-how"
          aria-label={t("איך סופרים את הדרישות", "How requirements are counted")} title={t("איך סופרים את הדרישות", "How requirements are counted")}><IInfo size={16} />
        </button>
      </div>
      {how && (
        <div className="sum-more" id="sum-how" data-testid="summary-how-detail">
          {showProgress && <p>{en ? <>A requirement is complete only when all its documents passed the smart check or were accepted by {bankerName}: for payslips, each required month counts once; for bank statements, the whole period is covered. A file that was uploaded or checked doesn't complete a requirement on its own.</>
            : <>דרישה מושלמת רק כשכל המסמכים שלה נמצאו תקינים בבדיקה החכמה או התקבלו אצל {bankerName}: בתלושים, כל חודש נדרש נספר פעם אחת; בדפי עו״ש, התקופה כולה מכוסה. קובץ שהועלה או נבדק עדיין לא משלים דרישה.</>}</p>}
          {others > 0 && (
            <button className="sum-others" onClick={() => nav("/customer/documents")}>
              <span>{en ? <>{others} more documents in this application are handled directly with the bank</> : <>עוד {others} מסמכים בתיק מטופלים ישירות מול הבנק</>}</span><IChevron size={14} />
            </button>
          )}
          <div className="sum-note"><img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="Jeen" />
            <span>{t("בדיקת המסמכים מסייעת בהכנת התיק. האישור הסופי נתון לבנק.", "The document check helps prepare your application. The final decision rests with the bank.")}</span></div>
        </div>
      )}
      {secondary && (
        <button className="btn btn-ghost sum-upload" data-testid="summary-upload" onClick={() => nav(uploadLink(secondary))}>
          <IUpload size={18} />{(en && secondary.label_en) || secondary.label_he}
        </button>
      )}
    </section>
  );
}
