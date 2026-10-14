import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, monthHe, type AppAction, type CustomerStatus, type Finding } from "../api";
import { useCase } from "../caseContext";
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
  const [retryError, setRetryError] = useState<string | null>(null);
  const status = snap?.readiness.customer_status;
  useEffect(() => { setDetail(false); setRetryError(null); }, [status, caseId]);
  if (!snap) return null;

  const r = snap.readiness;
  const reqs = r.requirements.filter((q) => q.evaluated_by_ai);
  const people = Object.fromEntries(snap.case.borrowers.map((b) => [b.borrower_id, b]));
  const first = (id?: string | null) => people[id || ""]?.first_name_he || "";
  const open = snap.findings.filter((f) => f.status === "open");
  const customer = open.filter((f) => f.review_state === "CUSTOMER_ACTION_REQUIRED");
  const banker = open.filter((f) => f.review_state === "NEEDS_BANKER_REVIEW");
  const corrections = customer.filter((f) => f.document_id);
  const correctionDocs = new Set(corrections.map((f) => f.document_id)).size;
  const inFlight = docs.filter((d) => d.status === "queued" || d.status === "processing");
  const bankerName = snap.case.banker.name_he;
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
    setRetryError(null);
    try {
      const failedIds = (await api.documents(caseId)).filter((d) => d.status === "failed").map((d) => d.document_id);
      if (failedIds.length) await Promise.all(failedIds.map((id) => api.retry(id)));
      else await api.revalidate(caseId);
      reload();
    } catch {
      setRetryError("לא הצלחנו לשלוח את הבקשה. נסו שוב בעוד רגע.");
    } finally {
      setRetrying(false);
    }
  };

  const findingLine = (f: Finding) => [
    snap.statements.some((s) => s.finding_id === f.finding_id) ? "ההסבר שלכם צורף" : null,
    snap.handoffs.some((h) => h.status === "IN_BANKER_QUEUE_DEMO" && !h.banker_decision) ? `הועבר ל${bankerName}` : `ממתין לבירור של ${bankerName}`,
  ].filter(Boolean).join(" · ");

  /** "עוד 3 תלושים של נועה" — the months (and further requests) this card's action does not cover. */
  const moreLine = (rest: { borrower: string }[], extraRequests = 0, otherDocs = 0) => {
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
      return { tone: "alert", title: q.title_he,
        body: <div className="ai-quote" data-testid="card-request-message"><b>{q.created_by_name || bankerName}:</b> {q.message_he}</div>,
        primary: { label: q.can_reply ? "להשבה לבקשה" : q.period ? `העלאת תלוש ${monthName(q.period)}` : "להעלאת המסמך",
          run: go(`/customer/documents?request=${q.customer_request_id}`), upload: !q.can_reply },
        ask: { label: "מה בדיוק צריך להעלות?", prompt: "מה בדיוק התבקשתי להעלות?" },
        more: moreLine(rest, asked.length - 1) };
    }
    switch (status) {
      case "AWAITING_UPLOAD": {
        const kinds = [...new Set(reqs.map((q) => q.family_he || q.family))];
        const months = r.payslips?.requested_months || [];
        return { tone: "action", title: "ממתינים למסמכים לבקשת ההלוואה",
          body: `כדי להתקדם, יש להעלות ${joinHe(kinds)}${months.length ? ` (תלושי ${monthsHe(months)})` : ""}. כל מסמך נבדק מיד עם ההעלאה.`,
          primary: { label: "העלאת מסמכים", run: go(requirementsTarget), upload: true },
          ask: { label: "אילו מסמכים צריך להעלות?", prompt: "אילו מסמכים צריך להעלות לבקשת ההלוואה?" } };
      }
      case "PROCESSING": {
        const queuedOnly = n > 0 && inFlight.length > 0 && inFlight.every((d) => d.status === "queued");
        return { tone: "info", title: "בודקים את המסמכים שהעליתם",
          body: n === 0 ? "כל המסמכים נקראו. עכשיו בודקים את כל המסמכים יחד מול דרישות הבקשה."
            : queuedOnly ? `${n === 1 ? "המסמך ממתין" : `${n} מסמכים ממתינים`} בתור לבדיקה. התוצאה תופיע כאן אוטומטית.`
              : r.counts.documents === 1 ? "המסמך נקרא ונבדק עכשיו. התוצאה תופיע כאן אוטומטית."
                : `נבדקו ${r.counts.reviewed} מתוך ${r.counts.documents} מסמכים. התוצאה תופיע כאן אוטומטית.`,
          primary: { label: "צפייה בהתקדמות", run: go(progressTarget) },
          ask: { label: "מה המצב של המסמכים שהעליתי?", prompt: "מה המצב של המסמכים שהעליתי?" } };
      }
      case "REVALIDATING":
        return { tone: "info", title: "בודקים מחדש את המסמכים",
          body: `${n === 0 ? "מעדכנים את בדיקת כל המסמכים בתיק לאחר השינוי האחרון."
            : `בודקים ${n === 1 ? "את המסמך החדש" : `${n} מסמכים חדשים`} ומעדכנים את בדיקת כל המסמכים בתיק.`} התוצאה תופיע כאן אוטומטית.`,
          primary: { label: "צפייה בבדיקה", run: go(progressTarget) },
          ask: { label: "מה המצב של המסמכים שהעליתי?", prompt: "מה המצב של המסמכים שהעליתי?" } };
      case "CORRECTION_REQUIRED": {
        // one document the AI review sent back: the button opens the upload that replaces it
        const rejected = Object.entries(snap.outcomes?.documents || {}).filter(([, o]) => o.outcome === "BLOCKER" && o.by === "ai").map(([id]) => id);
        const replaceOne = correctionDocs === 1 && rejected.length === 1 ? rejected[0] : null;
        return { tone: "alert", title: correctionDocs === 1 ? "נמצא מסמך שדורש תיקון" : "נמצאו מסמכים שדורשים תיקון",
          body: correctionDocs === 1 ? (replaceOne ? `${corrections[0].title_he} — נא להעלות מסמך חלופי. אחרי ההעלאה הבדיקה תרוץ מחדש.`
            : `${corrections[0].title_he}. אחרי העלאת מסמך מתוקן הבדיקה תרוץ מחדש.`)
            : `${correctionDocs} מסמכים דורשים תיקון או החלפה. אחרי העלאת מסמכים מתוקנים הבדיקה תרוץ מחדש.`,
          primary: replaceOne ? { label: "העלאת מסמך חלופי", run: go(`/customer/documents?replace=${encodeURIComponent(replaceOne)}`), upload: true }
            : { label: "צפייה בממצאים", run: go(requirementsTarget) },
          ask: { label: "מה צריך לתקן?", prompt: "מה צריך לתקן במסמכים?" } };
      }
      case "MISSING_DOCUMENTS": {
        const dup = reqs.flatMap((q) => Object.entries(q.duplicates || {}))[0];
        const dupNote = dup ? ` התקבלו ${dup[1]} תלושים ל${monthHe(dup[0])} — תלוש כפול נספר פעם אחת בלבד.` : "";
        // the backend's first upload target (the same one the assistant offers), preset to its borrower and month
        const next = nextUpload(uploads);
        const rest = next ? gaps.filter((g) => !(g.borrower === next.params.borrower_id && (!next.params.period || g.month === next.params.period))) : [];
        const months = next?.params.missing_periods || [];
        const who = first(next?.params.borrower_id);
        const title = months.length === 1 ? `חסר תלוש ${monthHe(months[0])} של ${who}`
          : months.length ? `חסרים ${months.length} תלושים של ${who}`
            : next ? (next.detail_he || next.label_he)
              : gaps.length ? `חסרים ${gaps.length} תלושי שכר`
                : customer.find((f) => !f.document_id)?.title_he || "נדרש מסמך נוסף";
        const body = [months.length > 1 ? `החודשים: ${monthsHe(months)}.` : null, dupNote.trim() || null].filter(Boolean).join(" ");
        const otherUploads = uploads.filter((a) => a !== next && a.params.missing_periods.length === 0).length;
        return { tone: "action", title, body: body || undefined,
          primary: next ? { label: next.label_he, run: go(uploadLink(next)), upload: true } : { label: "השלמת מסמכים", run: go(requirementsTarget) },
          ask: { label: "מה חסר כדי להתקדם?", prompt: "מה חסר כדי להתקדם?" },
          more: moreLine(rest, 0, otherUploads) };
      }
      case "BANKER_REVIEW": {
        const inReview = reqs.reduce((sum, q) => sum + (q.in_review_months?.length || 0), 0);
        return { tone: "info", title: verified >= required ? "המסמכים התקבלו · נדרש בירור בנקאי" : "כל המסמכים התקבלו · חלקם בבדיקה בנקאית",
          body: `${banker.length === 1 ? `${banker[0].title_he}. הנושא ממתין לבירור של ${bankerName}.`
            : banker.length ? `${banker.length} נושאים ממתינים לבירור של ${bankerName}.`
              : `${inReview === 1 ? "מסמך אחד ממתין" : `${inReview || "כמה"} מסמכים ממתינים`} לבדיקה של ${bankerName}.`} אין צורך בפעולה מצדכם כרגע.`,
          primary: banker.length
            ? { label: detail ? "הסתרת הפרטים" : banker.length === 1 ? "צפייה בממצא" : "צפייה בממצאים", run: () => setDetail(!detail), expanded: detail }
            : { label: "צפייה במסמכים", run: go(uploadedTarget) },
          ask: { label: `פנייה ל${bankerName}`,
            prompt: banker.length ? `אני רוצה לפנות ל${bankerName} לגבי: ${banker[0].title_he}` : `אני רוצה לפנות ל${bankerName} לגבי המסמכים שבבדיקה` } };
      }
      case "PREPARATION_CONFIRMED":
        return { tone: "ok", title: "הכנת מסמכי הבקשה אושרה",
          body: `האישור ניתן על ידי ${bankerName} ומתייחס להכנת המסמכים בלבד — זו אינה החלטה על ההלוואה.${banker.length
            ? ` ${banker.length === 1 ? "נושא אחד עדיין בבירור" : `${banker.length} נושאים עדיין בבירור`}.` : ""}`,
          primary: { label: "צפייה בסיכום", run: go("/customer/documents") },
          ask: { label: "מה השלב הבא?", prompt: "מה השלב הבא בתיק?" } };
      case "CHECKS_COMPLETE":
        return { tone: "ok", title: "כל המסמכים הנדרשים הושלמו",
          body: `כל המסמכים לבקשת ההלוואה נמצאו תקינים בבדיקה האוטומטית. התיק מוכן לבדיקה של ${bankerName} — זו אינה החלטה על ההלוואה.`,
          primary: { label: "צפייה בסיכום", run: go("/customer/documents") },
          ask: { label: "מה השלב הבא?", prompt: "מה השלב הבא בתיק?" } };
      case "ERROR": {
        const failed = docs.filter((d) => d.status === "failed");
        return { tone: "alert", title: "לא הצלחנו להשלים את הבדיקה",
          body: <>{r.counts.failed === 1 && failed.length === 1 ? <>הבדיקה של <span className="ltr">{failed[0].filename}</span> נעצרה בגלל תקלה.</>
            : r.counts.failed ? `הבדיקה של ${r.counts.failed} מסמכים נעצרה בגלל תקלה.` : "בדיקת סט המסמכים נעצרה בגלל תקלה."} אפשר לנסות שוב, ואם זה חוזר — נשמח לעזור.</>,
          primary: { label: "ניסיון חוזר", run: retry },
          ask: { label: "קבלת עזרה", prompt: "הבדיקה של המסמכים שלי לא הושלמה. מה אפשר לעשות?" } };
      }
      case "NO_PAYSLIPS_REQUIRED":
        return { tone: "info", title: "אין מסמכים לבדיקה בתיק זה", body: "מסמכי התיק מטופלים ישירות מול הבנק.",
          primary: { label: "למסמכים", run: go("/customer/documents") },
          ask: { label: "אילו מסמכים נדרשים בתיק?", prompt: "אילו מסמכים נדרשים בתיק?" } };
      default:
        return { tone: "info", title: r.state_he, primary: { label: "למסמכים", run: go("/customer/documents") },
          ask: { label: "מה חסר כדי להתקדם?", prompt: "מה חסר כדי להתקדם?" } };
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
            <h2 className="ai-heading" id="ai-card-heading">{acting ? "מה צריך לעשות עכשיו?" : "מה קורה עכשיו?"}</h2>
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
              <div className="finding-title">{f.title_he}</div>
              <div className="finding-msg">{f.message_he}</div>
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
        {retryError && <div className="small" role="alert" style={{ color: "var(--bad)", textAlign: "center" }}>{retryError}</div>}
        <div className="ai-foot">
          {view.more ? (
            <div className="ai-more" data-testid="card-more">
              <span>{view.more}</span>
              <button className="link" onClick={go(requirementsTarget)}>לכל המסמכים החסרים</button>
            </div>
          ) : <span className="ai-by">מופעל על ידי JEEN</span>}
          <button className={`ai-ask${view.more ? " icon" : ""}`} data-testid="card-secondary" onClick={() => openAssistant(view.ask.prompt)}
            aria-label={view.ask.label} title={view.ask.label}><ISpark size={13} />{!view.more && view.ask.label}</button>
        </div>
      </div>
    </section>
  );
}
