import { useEffect, useState, type ReactNode } from "react";
import { monthHe, VERDICT_HE, type AuditEvent, type DocView } from "../api";
import { useCase } from "../caseContext";
import { IAlert, IBell, ICheck, IChevronDown, IClock, IDocs, IUpload } from "./Icons";

type Tone = "action" | "ok" | "bad" | "info";
/** a file name inside a Hebrew sentence, bidi-isolated (FSI…PDI) so its dots and brackets stay in place */
const iso = (name?: string | null) => (name ? `\u2068${name}\u2069` : "");
interface Item { key: string; at: string; title: string; body: string; tone: Tone }

function describe(e: AuditEvent, docs: DocView[], banker: string): { title: string; body: string; tone: Tone } | null {
  const doc = docs.find((d) => d.document_id === e.target);
  const file = iso(e.detail?.filename || doc?.filename);
  switch (e.action) {
    case "document_uploaded": return { title: "מסמך הועלה לתיק", body: `${file}, הבדיקה החכמה התחילה.`, tone: "info" };
    case "document_reviewed": {
      // a payslip read correctly can still be the wrong month: say which month it prints when the file name claims another
      const named = doc?.review?.file_name_period;
      if (e.detail?.period && named && named !== e.detail.period)
        return { title: `המסמך זוהה כתלוש ${monthHe(e.detail.period)}`,
          body: `${iso(doc?.filename)}: בשם הקובץ מופיע ${monthHe(named)}, אבל בתלוש מודפס ${monthHe(e.detail.period)}.`, tone: "action" };
      return { title: "הבדיקה החכמה של המסמך הושלמה",
        body: `${iso(doc?.filename)}: ${VERDICT_HE[e.detail?.verdict] || ""}${e.detail?.period ? ` · מודפס ${monthHe(e.detail.period)}` : ""}`,
        tone: e.detail?.verdict === "VALID" ? "ok" : "action" };
    }
    case "case_reviewed": return { title: "תמונת המסמכים בתיק עודכנה", body: "בדקנו מחדש את כל מסמכי הבקשה מול הדרישות.", tone: "info" };
    case "customer_statement_recorded": return { title: "ההסבר שלכם תועד", body: "ההסבר צורף לממצא והועבר לבנקאית. הוא אינו סוגר את הממצא.", tone: "ok" };
    case "banker_handoff_created": return { title: "התיק הועבר לבנקאית", body: "חבילת הממצאים והראיות ממתינה לבנקאית.", tone: "info" };
    case "banker_finding_decision":
      if (e.detail?.action === "REQUEST_DOCUMENT" || e.detail?.action === "REQUEST_EXPLANATION")
        return { title: `בקשה חדשה מ${banker}`, body: e.detail?.customer_message || "", tone: "action" };
      if (e.detail?.action === "ESCALATE_FINDING") return { title: "נושא בבירור נוסף", body: `${banker} ממשיך/ה לבדוק נושא בתיק. אין צורך בפעולה מצדכם כרגע.`, tone: "info" };
      return { title: `${banker} בדק/ה נושא בתיק`, body: e.detail?.action === "DISMISS_FINDING" ? "הממצא נבדק ונמצא לא רלוונטי." : "הנושא נבדק ונסגר.", tone: "ok" };
    case "banker_request_withdrawn": return { title: "בקשה בוטלה", body: `${e.detail?.title_he || "הבקשה"}, אין צורך לפעול לגביה.`, tone: "info" };
    case "banker_handoff_acknowledged": return { title: `${banker} קיבלה את הפנייה שלכם`, body: "הפנייה בטיפול. אם יידרש משהו מצדכם, תופיע כאן בקשה.", tone: "ok" };
    case "banker_document_decision":
      if (e.detail?.action === "REQUEST_CORRECTION") return { title: `בקשה חדשה מ${banker}`, body: e.detail?.customer_message || "", tone: "action" };
      if (e.detail?.action === "ACCEPT_DOCUMENT") return { title: "מסמך התקבל לבדיקת המסמכים", body: `${file} התקבל אצל ${banker}. זה אינו אישור ההלוואה.`, tone: "ok" };
      return { title: "מסמך בבירור נוסף", body: `${file} נבדק אצל ${banker}. אין צורך בפעולה מצדכם כרגע.`, tone: "info" };
    case "banker_requested_document": return { title: `בקשה חדשה מ${banker}`, body: e.detail?.customer_message || "", tone: "action" };
    case "customer_request_responded":
      return e.detail?.statement_id ? { title: "התשובה שלכם נשמרה", body: `ההסבר הועבר ל${banker}. הוא אינו סוגר את הבירור.`, tone: "ok" }
        : { title: "המסמך שהעליתם צורף לבקשה", body: "הוא נבדק בבדיקה החכמה ויחזור לבנקאי לעיון.", tone: "ok" };
    case "banker_confirmed_preparation": return { title: "הבנקאית אישרה את הכנת מסמכי הבקשה", body: "זהו אישור הכנת מסמכים בלבד, לא החלטה על ההלוואה.", tone: "ok" };
    case "document_review_failed":
      // the worker retries a few times; only the last attempt (final) means it stopped
      return { title: "הבדיקה של מסמך נכשלה", tone: "bad", body: String(e.detail?.final) === "True" || e.detail?.final === true
        ? `${file ? `${file}: ` : ""}הבדיקה נעצרה אחרי כמה ניסיונות. אפשר לנסות שוב מהמסך הראשי או להעלות את הקובץ מחדש.`
        : "ננסה שוב אוטומטית; אפשר גם להעלות מחדש." };
    default: return null;
  }
}

/** A banker closing a finding: the only event kind that is folded when it repeats back to back. */
const isClose = (e: AuditEvent) => e.action === "banker_finding_decision"
  && !["REQUEST_DOCUMENT", "REQUEST_EXPLANATION", "ESCALATE_FINDING"].includes(e.detail?.action);
const FOLD_WINDOW_MS = 10 * 60 * 1000;

/** The short list on the home screen, newest first. Presentation only — the case's audit history is untouched and the
 *  full list shows every event. Set re-checks are left out (the outcome shows elsewhere), an upload is left out once
 *  its review result is listed, retries of one failed review show only the latest attempt, and identical banker
 *  closures in a row become one line. Banker requests, the
 *  customer's own answers and statements are never folded or left out. */
function fold(events: AuditEvent[], docs: DocView[], banker: string): Item[] {
  const reviewed = new Set(events.filter((e) => e.action === "document_reviewed" || e.action === "document_review_failed").map((e) => e.target));
  const out: (Item & { closes?: number; close?: string; last?: number; failed?: string })[] = [];
  for (const e of events) {
    if (e.action === "case_reviewed") continue;
    if (e.action === "document_uploaded" && reviewed.has(e.target)) continue;
    const d = describe(e, docs, banker);
    if (!d) continue;
    const prev = out[out.length - 1];
    if (e.action === "document_review_failed" && prev?.failed === e.target) continue;
    const at = Date.parse(e.at);
    if (isClose(e) && prev?.close === `${d.title}|${d.body}` && prev.last !== undefined && Math.abs(prev.last - at) <= FOLD_WINDOW_MS) {
      prev.closes = (prev.closes || 1) + 1;
      prev.last = at;
      prev.title = `${banker} בדק/ה ${prev.closes} נושאים בתיק`;
      prev.body = e.detail?.action === "DISMISS_FINDING" ? "הממצאים נבדקו ונמצאו לא רלוונטיים." : "כל הנושאים נבדקו ונסגרו.";
      continue;
    }
    out.push({ key: String(e.event_id), at: e.at, ...d, ...(isClose(e) ? { close: `${d.title}|${d.body}`, last: at } : {}),
      ...(e.action === "document_review_failed" ? { failed: e.target } : {}) });
  }
  return out;
}

const ICON: Record<Tone, ReactNode> = { action: <IDocs size={18} />, ok: <ICheck size={18} />, bad: <IAlert size={17} />, info: <IClock size={17} /> };
const dateHe = (iso: string) => new Date(iso).toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" });
const clockHe = (iso: string) => new Date(iso).toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });

/** "עדכונים אחרונים": the three latest customer-visible updates, and the whole list one tap away. */
export function RecentUpdates() {
  const { snap, docs, caseId } = useCase();
  const [all, setAll] = useState(false);
  useEffect(() => setAll(false), [caseId]);
  if (!snap) return null;
  const banker = snap.case.banker.name_he;
  const full: Item[] = snap.updates.flatMap((e) => {
    const d = describe(e, docs, banker);
    return d ? [{ key: String(e.event_id), at: e.at, ...d }] : [];
  });
  const items = all ? full : fold(snap.updates, docs, banker).slice(0, 3);
  return (
    <section className="card upd-card" aria-labelledby="upd-heading" data-testid="recent-updates">
      <div className="upd-head">
        <span className="upd-bell" aria-hidden><IBell size={16} /></span>
        <h2 className="sum-title" id="upd-heading">{all ? "כל העדכונים בתיק" : "עדכונים אחרונים"}</h2>
      </div>
      {full.length === 0 ? (
        <div className="upd-empty">עדיין אין עדכונים בתיק. כשתעלו מסמכים או כשתגיע בקשה מ{banker}, העדכון יופיע כאן.</div>
      ) : (
        <ol className="timeline upd-list">
          {items.map((it) => (
            <li className={`upd-item ${it.tone}`} key={it.key} data-testid="update-item">
              <span className="upd-ic" aria-hidden>{it.tone === "info" && it.title === "מסמך הועלה לתיק" ? <IUpload size={17} /> : ICON[it.tone]}</span>
              <div className="grow">
                <div className="upd-title">{it.title}</div>
                {it.body && <div className="upd-body">{it.body}</div>}
              </div>
              <span className="upd-dot" aria-hidden />
              <time className="upd-time" dateTime={it.at}><span className="ltr">{dateHe(it.at)}</span><span className="ltr">{clockHe(it.at)}</span></time>
            </li>
          ))}
        </ol>
      )}
      {full.length > 3 && (
        <button className="upd-more" onClick={() => setAll(!all)} aria-expanded={all} data-testid="updates-toggle">
          <span>{all ? "הצגת העדכונים האחרונים בלבד" : <>לכל ההיסטוריה <span className="muted">({full.length})</span></>}</span>
          <span className={`upd-chev${all ? " up" : ""}`}><IChevronDown size={16} /></span>
        </button>
      )}
    </section>
  );
}
