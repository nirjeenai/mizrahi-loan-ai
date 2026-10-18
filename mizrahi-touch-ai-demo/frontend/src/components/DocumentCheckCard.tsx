import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, monthHe, monthL, type AppAction, type CustomerStatus, type Finding } from "../api";
import { useCase } from "../caseContext";
import { useLang } from "../i18n";
import { IAlert, ICheck, IClock, IDocs, ISpark, IUpload } from "./Icons";

type Tone = "action" | "alert" | "info" | "ok";
interface View {
  tone: Tone;
  title: string;
  body?: ReactNode;
  primary: { label: string; run: () => void; expanded?: boolean; upload?: boolean };
  ask: { label: string; prompt: string };
  /** what else is outstanding besides the action this card leads to */
  more?: string;
}
export type UploadAction = Extract<AppAction, { type: "NAVIGATE_TO_DOCUMENT_UPLOAD" }>;

/** "יולי, אוגוסט וספטמבר" */
export const joinHe = (items: string[]) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} ו${items[items.length - 1]}`);
export const monthName = (ym: string) => monthHe(ym).split(" ")[0];
/** "July, August and September" */
export const joinEn = (items: string[]) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);
export const monthNameEn = (ym: string) => monthL(ym).split(" ")[0];
const monthsEn = (months: string[]) => {
  const years = [...new Set(months.map((m) => m.slice(0, 4)))];
  return years.length === 1 ? `${joinEn(months.map(monthNameEn))} ${years[0]}` : joinEn(months.map(monthL));
};
const monthsHe = (months: string[]) => {
  const years = [...new Set(months.map((m) => m.slice(0, 4)))];
  return years.length === 1 ? `${joinHe(months.map(monthName))} ${years[0]}` : joinHe(months.map(monthHe));
};
const BUSY: (CustomerStatus | undefined)[] = ["PROCESSING", "REVALIDATING"];
/** The upload sheet, preset by the Documents screen to one requirement (and month, when there is exactly one). */
export const uploadLink = (a: UploadAction) =>
  `/customer/documents?upload=${encodeURIComponent(a.params.requirement_code)}${a.params.period ? `&period=${a.params.period}` : ""}`;
/** The upload target the card leads to when months are missing: the backend's first one that has a missing month. */
export const nextUpload = (uploads: UploadAction[]) => uploads.find((a) => a.params.missing_periods.length > 0) || uploads[0];

/** The home-screen card for what the customer should do now — or, when nothing is open, what is happening.
 *  The banker's open request comes first, then the backend's next upload target; everything comes from the case snapshot. */
export function DocumentCheckCard() {
  const { snap, docs, caseId, reload, openAssistant } = useCase();
  const nav = useNavigate();
  const [detail, setDetail] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(false);
  const { en, t } = useLang();
  const status = snap?.readiness.customer_status;
  useEffect(() => { setDetail(false); setRetryError(false); }, [status, caseId]);
  if (!snap) return null;

  const r = snap.readiness;
  const reqs = r.requirements.filter((q) => q.evaluated_by_ai);
  const people = Object.fromEntries(snap.case.borrowers.map((b) => [b.borrower_id, b]));
  const first = (id?: string | null) => (en ? people[id || ""]?.first_name_en : undefined) || people[id || ""]?.first_name_he || "";
  const open = snap.findings.filter((f) => f.status === "open");
  const customer = open.filter((f) => f.review_state === "CUSTOMER_ACTION_REQUIRED");
  const banker = open.filter((f) => f.review_state === "NEEDS_BANKER_REVIEW");
  const corrections = customer.filter((f) => f.document_id);
  const correctionDocs = new Set(corrections.map((f) => f.document_id)).size;
  const inFlight = docs.filter((d) => d.status === "queued" || d.status === "processing");
  const bankerName = (en && snap.case.banker.name_en) || snap.case.banker.name_he;
  const L = (o: { title_he: string; title_en?: string }) => (en && o.title_en) || o.title_he;
  const required = r.payslips?.required ?? 0;
  const verified = r.payslips?.verified ?? 0;
  const uploads = (snap.available_actions || []).filter((a): a is UploadAction => a.type === "NAVIGATE_TO_DOCUMENT_UPLOAD");
  const gaps = reqs.flatMap((q) => (q.missing || []).map((m) => ({ borrower: q.borrower_id || "", month: m })));
  const go = (path: string) => () => nav(path);
  const requirementsTarget = "/customer/documents?focus=payslips";
  const uploadedTarget = "/customer/documents?focus=uploaded";
  const progressTarget = r.counts.processing === 1 && inFlight.length === 1 ? `/customer/documents/${inFlight[0].document_id}` : uploadedTarget;

  const retry = async () => {
    setRetrying(true);
    setRetryError(false);
    try {
      const failedIds = (await api.documents(caseId)).filter((d) => d.status === "failed").map((d) => d.document_id);
      if (failedIds.length) await Promise.all(failedIds.map((id) => api.retry(id)));
      else await api.revalidate(caseId);
      reload();
    } catch {
      setRetryError(true);
    } finally {
      setRetrying(false);
    }
  };

  const findingLine = (f: Finding) => [
    snap.statements.some((s) => s.finding_id === f.finding_id) ? t("ההסבר שלכם צורף", "Your explanation is attached") : null,
    snap.handoffs.some((h) => h.status === "IN_BANKER_QUEUE_DEMO" && !h.banker_decision) ? t(`הועבר ל${bankerName}`, `Passed to ${bankerName}`)
      : t(`ממתין לבירור של ${bankerName}`, `Waiting for ${bankerName} to look into it`),
  ].filter(Boolean).join(" · ");

  /** "עוד 3 תלושים של נועה" — the months (and further requests) this card's action does not cover. */
  const moreLine = (rest: { borrower: string }[], extraRequests = 0, otherDocs = 0) => {
    if (en) {
      const who = joinEn([...new Set(rest.map((g) => first(g.borrower)))].filter(Boolean));
      const items = [
        extraRequests ? (extraRequests === 1 ? "1 request" : `${extraRequests} requests`) : null,
        rest.length ? `${rest.length === 1 ? "1 payslip" : `${rest.length} payslips`}${who ? ` for ${who}` : ""}` : null,
        otherDocs ? (otherDocs === 1 ? "1 document" : `${otherDocs} documents`) : null,
      ].filter(Boolean);
      return items.length ? `Also: ${items.join(" · ")}` : undefined;
    }
    const names = joinHe([...new Set(rest.map((g) => first(g.borrower)))].filter(Boolean));
    const parts = [
      extraRequests ? (extraRequests === 1 ? "בקשה אחת" : `${extraRequests} בקשות`) : null,
      rest.length ? `${rest.length === 1 ? "תלוש אחד" : `${rest.length} תלושים`}${names ? ` של ${names}` : ""}` : null,
      otherDocs ? (otherDocs === 1 ? "מסמך אחד" : `${otherDocs} מסמכים`) : null,
    ].filter(Boolean);
    return parts.length ? `עוד ${parts.join(" · ")}` : undefined;
  };

  const asked = (snap.customer_requests || []).filter((q) => q.status === "OPEN");
  const view = ((): View => {
    const n = r.counts.processing;
    if (asked.length && (status === "CORRECTION_REQUIRED" || status === "MISSING_DOCUMENTS" || status === "AWAITING_UPLOAD")) {
      const q = asked[0];
      // a requested month is what the request is about; it is not counted again as "also missing"
      const rest = gaps.filter((g) => !asked.some((x) => x.borrower_id === g.borrower && (!x.period || x.period === g.month)));
      // the request's own title is the action; the banker's message is quoted as written (two lines on screen)
      // the banker's message is quoted as written, in its own language
      return { tone: "alert", title: L(q),
        body: <div className="ai-quote" data-testid="card-request-message"><b>{(en && q.created_by_name === snap.case.banker.name_he ? bankerName : q.created_by_name) || bankerName}:</b> {en
          ? <bdi lang="he" dir="rtl">{q.message_he}</bdi> : q.message_he}</div>,
        primary: { label: q.can_reply ? t("להשבה לבקשה", "Reply to the request") : q.period ? t(`העלאת תלוש ${monthName(q.period)}`, `Upload the ${monthNameEn(q.period)} payslip`)
          : t("להעלאת המסמך", "Upload the document"),
          run: go(`/customer/documents?request=${q.customer_request_id}`), upload: !q.can_reply },
        ask: { label: t("מה בדיוק צריך להעלות?", "What exactly do I need to upload?"), prompt: t("מה בדיוק התבקשתי להעלות?", "What exactly was I asked to upload?") },
        more: moreLine(rest, asked.length - 1) };
    }
    switch (status) {
      case "AWAITING_UPLOAD": {
        const kinds = [...new Set(reqs.map((q) => q.family_he || q.family))];
        const kindsEn = [...new Set(reqs.map((q) => (q.family_en || q.family_he || q.family).toLowerCase().replace(/^id card$/, "ID card")))];
        const months = r.payslips?.requested_months || [];
        return { tone: "action", title: t("ממתינים למסמכים לבקשת ההלוואה", "Waiting for your loan application documents"),
          body: t(`כדי להתקדם, יש להעלות ${joinHe(kinds)}${months.length ? ` (תלושי ${monthsHe(months)})` : ""}. כל מסמך נבדק מיד עם ההעלאה.`,
            `To move forward, please upload your ${joinEn(kindsEn)}${months.length ? ` (payslips for ${monthsEn(months)})` : ""}. Each document is checked as soon as you upload it.`),
          primary: { label: t("העלאת מסמכים", "Upload documents"), run: go(requirementsTarget), upload: true },
          ask: { label: t("אילו מסמכים צריך להעלות?", "Which documents do I need to upload?"), prompt: t("אילו מסמכים צריך להעלות לבקשת ההלוואה?", "Which documents do I need to upload for my loan application?") } };
      }
      case "PROCESSING": {
        const queuedOnly = n > 0 && inFlight.length > 0 && inFlight.every((d) => d.status === "queued");
        return { tone: "info", title: t("בודקים את המסמכים שהעליתם", "Checking the documents you uploaded"),
          body: en ? (n === 0 ? "All documents have been read. Now we're checking them together against the application's requirements."
            : queuedOnly ? `${n === 1 ? "The document is" : `${n} documents are`} in the queue to be checked. The result will appear here automatically.`
              : r.counts.documents === 1 ? "The document is being read and checked now. The result will appear here automatically."
                : `${r.counts.reviewed} of ${r.counts.documents} documents checked. The result will appear here automatically.`)
            : n === 0 ? "כל המסמכים נקראו. עכשיו בודקים את כל המסמכים יחד מול דרישות הבקשה."
            : queuedOnly ? `${n === 1 ? "המסמך ממתין" : `${n} מסמכים ממתינים`} בתור לבדיקה. התוצאה תופיע כאן אוטומטית.`
              : r.counts.documents === 1 ? "המסמך נקרא ונבדק עכשיו. התוצאה תופיע כאן אוטומטית."
                : `נבדקו ${r.counts.reviewed} מתוך ${r.counts.documents} מסמכים. התוצאה תופיע כאן אוטומטית.`,
          primary: { label: t("צפייה בהתקדמות", "View progress"), run: go(progressTarget) },
          ask: { label: t("מה המצב של המסמכים שהעליתי?", "What's the status of the documents I uploaded?"), prompt: t("מה המצב של המסמכים שהעליתי?", "What's the status of the documents I uploaded?") } };
      }
      case "REVALIDATING":
        return { tone: "info", title: t("בודקים מחדש את המסמכים", "Re-checking your documents"),
          body: t(`${n === 0 ? "מעדכנים את בדיקת כל המסמכים בתיק לאחר השינוי האחרון."
            : `בודקים ${n === 1 ? "את המסמך החדש" : `${n} מסמכים חדשים`} ומעדכנים את בדיקת כל המסמכים בתיק.`} התוצאה תופיע כאן אוטומטית.`,
            `${n === 0 ? "Updating the check of all your application's documents after the latest change."
              : `Checking ${n === 1 ? "the new document" : `${n} new documents`} and updating the check of all your application's documents.`} The result will appear here automatically.`),
          primary: { label: t("צפייה בבדיקה", "View the check"), run: go(progressTarget) },
          ask: { label: t("מה המצב של המסמכים שהעליתי?", "What's the status of the documents I uploaded?"), prompt: t("מה המצב של המסמכים שהעליתי?", "What's the status of the documents I uploaded?") } };
      case "CORRECTION_REQUIRED": {
        // one document the AI review sent back: the button opens the upload that replaces it
        const rejected = Object.entries(snap.outcomes?.documents || {}).filter(([, o]) => o.outcome === "BLOCKER" && o.by === "ai").map(([id]) => id);
        const replaceOne = correctionDocs === 1 && rejected.length === 1 ? rejected[0] : null;
        return { tone: "alert", title: correctionDocs === 1 ? t("נמצא מסמך שדורש תיקון", "A document needs a correction") : t("נמצאו מסמכים שדורשים תיקון", "Some documents need a correction"),
          body: en ? (correctionDocs === 1 ? (replaceOne ? `${L(corrections[0])} — please upload a replacement. The check runs again after you upload it.`
            : `${L(corrections[0])}. The check runs again after you upload a corrected document.`)
            : `${correctionDocs} documents need a correction or a replacement. The check runs again after you upload corrected documents.`)
            : correctionDocs === 1 ? (replaceOne ? `${corrections[0].title_he}, נא להעלות מסמך חלופי. אחרי ההעלאה הבדיקה תרוץ מחדש.`
            : `${corrections[0].title_he}. אחרי העלאת מסמך מתוקן הבדיקה תרוץ מחדש.`)
            : `${correctionDocs} מסמכים דורשים תיקון או החלפה. אחרי העלאת מסמכים מתוקנים הבדיקה תרוץ מחדש.`,
          primary: replaceOne ? { label: t("העלאת מסמך חלופי", "Upload a replacement"), run: go(`/customer/documents?replace=${encodeURIComponent(replaceOne)}`), upload: true }
            : { label: t("צפייה בממצאים", "View the findings"), run: go(requirementsTarget) },
          ask: { label: t("מה צריך לתקן?", "What needs correcting?"), prompt: t("מה צריך לתקן במסמכים?", "What needs correcting in my documents?") } };
      }
      case "MISSING_DOCUMENTS": {
        const dup = reqs.flatMap((q) => Object.entries(q.duplicates || {}))[0];
        const dupNote = dup ? t(` התקבלו ${dup[1]} תלושים ל${monthHe(dup[0])}, תלוש כפול נספר פעם אחת בלבד.`,
          ` ${dup[1]} payslips were received for ${monthL(dup[0])}; a duplicate payslip is counted only once.`) : "";
        // the backend's first upload target (the same one the assistant offers), preset to its borrower and month
        const next = nextUpload(uploads);
        const rest = next ? gaps.filter((g) => !(g.borrower === next.params.borrower_id && (!next.params.period || g.month === next.params.period))) : [];
        const months = next?.params.missing_periods || [];
        const who = first(next?.params.borrower_id);
        const missingDoc = customer.find((f) => !f.document_id);
        const title = en ? (months.length === 1 ? `${who}'s payslip for ${monthL(months[0])} is missing`
          : months.length ? `${months.length} of ${who}'s payslips are missing`
            : next ? (next.detail_en || next.label_en || next.detail_he || next.label_he)
              : gaps.length ? `${gaps.length} payslips are missing`
                : (missingDoc && L(missingDoc)) || "Another document is needed")
          : months.length === 1 ? `חסר תלוש ${monthHe(months[0])} של ${who}`
          : months.length ? `חסרים ${months.length} תלושים של ${who}`
            : next ? (next.detail_he || next.label_he)
              : gaps.length ? `חסרים ${gaps.length} תלושי שכר`
                : customer.find((f) => !f.document_id)?.title_he || "נדרש מסמך נוסף";
        const body = [months.length > 1 ? t(`החודשים: ${monthsHe(months)}.`, `Months: ${monthsEn(months)}.`) : null, dupNote.trim() || null].filter(Boolean).join(" ");
        const otherUploads = uploads.filter((a) => a !== next && a.params.missing_periods.length === 0).length;
        return { tone: "action", title, body: body || undefined,
          primary: next ? { label: (en && next.label_en) || next.label_he, run: go(uploadLink(next)), upload: true } : { label: t("השלמת מסמכים", "Complete your documents"), run: go(requirementsTarget) },
          ask: { label: t("מה חסר כדי להתקדם?", "What's missing to move forward?"), prompt: t("מה חסר כדי להתקדם?", "What's missing to move forward?") },
          more: moreLine(rest, 0, otherUploads) };
      }
      case "BANKER_REVIEW": {
        const inReview = reqs.reduce((sum, q) => sum + (q.in_review_months?.length || 0), 0);
        return { tone: "info", title: verified >= required ? t("המסמכים התקבלו · נדרש בירור בנקאי", "Documents received · the banker needs to look into something")
          : t("כל המסמכים התקבלו · חלקם בבדיקה בנקאית", "All documents received · some are with the banker"),
          body: en ? `${banker.length === 1 ? `${L(banker[0])}. ${bankerName} will look into it.`
            : banker.length ? `${banker.length} items are waiting for ${bankerName} to look into them.`
              : `${inReview === 1 ? "1 document is" : `${inReview || "Some"} documents are`} waiting for ${bankerName}'s review.`} Nothing is needed from you right now.`
            : `${banker.length === 1 ? `${banker[0].title_he}. הנושא ממתין לבירור של ${bankerName}.`
            : banker.length ? `${banker.length} נושאים ממתינים לבירור של ${bankerName}.`
              : `${inReview === 1 ? "מסמך אחד ממתין" : `${inReview || "כמה"} מסמכים ממתינים`} לבדיקה של ${bankerName}.`} אין צורך בפעולה מצדכם כרגע.`,
          primary: banker.length
            ? { label: detail ? t("הסתרת הפרטים", "Hide the details") : banker.length === 1 ? t("צפייה בממצא", "View the finding") : t("צפייה בממצאים", "View the findings"), run: () => setDetail(!detail), expanded: detail }
            : { label: t("צפייה במסמכים", "View documents"), run: go(uploadedTarget) },
          ask: { label: t(`פנייה ל${bankerName}`, `Contact ${bankerName}`),
            prompt: en ? (banker.length ? `I'd like to contact ${bankerName} about: ${L(banker[0])}` : `I'd like to contact ${bankerName} about the documents under review`)
              : banker.length ? `אני רוצה לפנות ל${bankerName} לגבי: ${banker[0].title_he}` : `אני רוצה לפנות ל${bankerName} לגבי המסמכים שבבדיקה` } };
      }
      case "PREPARATION_CONFIRMED":
        return { tone: "ok", title: t("הכנת מסמכי הבקשה אושרה", "Your application's documents are confirmed"),
          body: t(`האישור ניתן על ידי ${bankerName} ומתייחס להכנת המסמכים בלבד, זו אינה החלטה על ההלוואה.${banker.length
            ? ` ${banker.length === 1 ? "נושא אחד עדיין בבירור" : `${banker.length} נושאים עדיין בבירור`}.` : ""}`,
            `${bankerName} confirmed that your documents are prepared. This is about the documents only — it is not a decision on the loan.${banker.length
              ? ` ${banker.length === 1 ? "One item is still being looked into" : `${banker.length} items are still being looked into`}.` : ""}`),
          primary: { label: t("צפייה בסיכום", "View the summary"), run: go("/customer/documents") },
          ask: { label: t("מה השלב הבא?", "What's the next step?"), prompt: t("מה השלב הבא בתיק?", "What's the next step for my application?") } };
      case "CHECKS_COMPLETE":
        return { tone: "ok", title: t("כל המסמכים הנדרשים הושלמו", "All required documents are complete"),
          body: t(`כל המסמכים לבקשת ההלוואה נמצאו תקינים בבדיקה האוטומטית. התיק מוכן לבדיקה של ${bankerName}, זו אינה החלטה על ההלוואה.`,
            `All your loan application documents passed the automatic check. Your application is ready for ${bankerName}'s review — this is not a decision on the loan.`),
          primary: { label: t("צפייה בסיכום", "View the summary"), run: go("/customer/documents") },
          ask: { label: t("מה השלב הבא?", "What's the next step?"), prompt: t("מה השלב הבא בתיק?", "What's the next step for my application?") } };
      case "ERROR": {
        const failed = docs.filter((d) => d.status === "failed");
        return { tone: "alert", title: t("לא הצלחנו להשלים את הבדיקה", "We couldn't complete the check"),
          body: en ? <>{r.counts.failed === 1 && failed.length === 1 ? <>The check of <span className="ltr">{failed[0].filename}</span> stopped because of a technical problem.</>
            : r.counts.failed ? `The check of ${r.counts.failed} documents stopped because of a technical problem.` : "The check of your documents stopped because of a technical problem."} You can try again — if it happens again, we're happy to help.</>
            : <>{r.counts.failed === 1 && failed.length === 1 ? <>הבדיקה של <span className="ltr">{failed[0].filename}</span> נעצרה בגלל תקלה.</>
            : r.counts.failed ? `הבדיקה של ${r.counts.failed} מסמכים נעצרה בגלל תקלה.` : "בדיקת סט המסמכים נעצרה בגלל תקלה."} אפשר לנסות שוב, ואם זה חוזר, נשמח לעזור.</>,
          primary: { label: t("ניסיון חוזר", "Try again"), run: retry },
          ask: { label: t("קבלת עזרה", "Get help"), prompt: t("הבדיקה של המסמכים שלי לא הושלמה. מה אפשר לעשות?", "The check of my documents didn't finish. What can I do?") } };
      }
      case "NO_PAYSLIPS_REQUIRED":
        return { tone: "info", title: t("אין מסמכים לבדיקה בתיק זה", "There are no documents to check in this application"),
          body: t("מסמכי התיק מטופלים ישירות מול הבנק.", "This application's documents are handled directly with the bank."),
          primary: { label: t("למסמכים", "To documents"), run: go("/customer/documents") },
          ask: { label: t("אילו מסמכים נדרשים בתיק?", "Which documents does my application need?"), prompt: t("אילו מסמכים נדרשים בתיק?", "Which documents does my application need?") } };
      default:
        return { tone: "info", title: (en && r.state_en) || r.state_he, primary: { label: t("למסמכים", "To documents"), run: go("/customer/documents") },
          ask: { label: t("מה חסר כדי להתקדם?", "What's missing to move forward?"), prompt: t("מה חסר כדי להתקדם?", "What's missing to move forward?") } };
    }
  })();

  const acting = view.tone === "action" || view.tone === "alert";
  const icon = status === "ERROR" ? <IAlert size={20} /> : acting ? <IDocs size={20} /> : view.tone === "ok" ? <ICheck size={20} /> : <IClock size={20} />;
  return (
    <section className={`ai-card tone-${view.tone}`} data-testid="ai-card" data-status={status || "UNKNOWN"} data-state={r.state}
      aria-labelledby="ai-card-heading">
      <div className="ai-top">
        <span className="ai-icon" aria-hidden>{icon}</span>
        <div className="grow">
          <div className="ai-head">
            <h2 className="ai-heading" id="ai-card-heading">{acting ? t("מה צריך לעשות עכשיו?", "What do you need to do now?") : t("מה קורה עכשיו?", "What's happening now?")}</h2>
            <img className="ai-logo" src="/brand/jeen-logo.png" alt="JEEN" />
          </div>
          <div className="ai-state" data-testid="readiness-state">{BUSY.includes(status) && <span className="spinner" />}{view.title}</div>
        </div>
      </div>
      {view.body && <div className="ai-body">{view.body}</div>}
      {detail && status === "BANKER_REVIEW" && banker.length > 0 && (
        <div className="ai-detail" data-testid="card-detail">
          {banker.map((f) => (
            <div key={f.finding_id} className="finding NEEDS_BANKER_REVIEW">
              <div className="finding-title">{L(f)}</div>
              <div className="finding-msg">{(en && f.message_en) || (en ? <bdi lang="he" dir="rtl">{f.message_he}</bdi> : f.message_he)}</div>
              <div className="tiny muted" style={{ marginTop: 4 }}>{findingLine(f)}</div>
            </div>
          ))}
        </div>
      )}
      <div className="ai-cta">
        <button className={`btn ${acting ? "btn-orange" : "btn-dark"}`} data-testid="card-primary"
          onClick={view.primary.run} disabled={retrying} aria-expanded={view.primary.expanded}>
          {retrying ? <span className="spinner" /> : view.primary.upload ? <IUpload size={19} /> : null}{view.primary.label}
        </button>
        {retryError && <div className="small" role="alert" style={{ color: "var(--bad)", textAlign: "center" }}>{t("לא הצלחנו לשלוח את הבקשה. נסו שוב בעוד רגע.", "We couldn't send the request. Please try again in a moment.")}</div>}
        <div className="ai-foot">
          {view.more ? (
            <div className="ai-more" data-testid="card-more">
              <span>{view.more}</span>
              <button className="link" onClick={go(requirementsTarget)}>{t("לכל המסמכים החסרים", "All missing documents")}</button>
            </div>
          ) : <span className="ai-by">{t("מופעל על ידי JEEN", "Powered by JEEN")}</span>}
          <button className={`ai-ask${view.more ? " icon" : ""}`} data-testid="card-secondary" onClick={() => openAssistant(view.ask.prompt)}
            aria-label={view.ask.label} title={view.ask.label}><ISpark size={13} />{!view.more && view.ask.label}</button>
        </div>
      </div>
    </section>
  );
}
