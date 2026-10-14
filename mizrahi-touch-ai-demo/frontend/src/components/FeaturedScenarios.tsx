import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AccessError, api, monthHe } from "../api";
import { useCase } from "../caseContext";
import { IAlert, ICheck, IChevronDown, IDownload, IX } from "./Icons";
import type { UseCase } from "./UseCaseScenarios";

/* The featured executive-demo scenarios and the "start a new demo" control. Everything shown comes from the
   presenter manifest (fixtures/presenter): the expected label is the JEEN routing expectation for golden-set facts,
   never a live result. Downloading a file changes nothing in the app; the presenter uploads it on the right. */

export type Route = "PASS" | "REVIEW" | "BLOCKER" | "CORRECTION";
export type FileRole = "upload" | "setup" | "wrong" | "replacement";
/** One file of a scenario as the manifest resolves it: what it is, where it goes, which month to pick, why it is there. */
export interface ScenarioFile { file: string; labelHe: string; slotHe: string; uploadAs: string; period: string | null; role: FileRole; noteHe?: string | null }
export interface FeaturedStep extends ScenarioFile { borrower: string; optional?: boolean }
export interface Featured {
  id: string; outcome: Route; badgeHe: string; titleHe: string; checksHe: string; expectHe: string; expectedLabelHe: string;
  instructionHe?: string; caseId: string; caseDisplay: string; borrowerHe: string; destinationHe: string; steps: FeaturedStep[];
  appShowsHe: string[]; playbookHe: string[]; sayHe: string; avoidHe?: string;
  /** a file uploaded into another requirement's card than its own (a wrong-slot scenario) */
  uploadAs?: Record<string, string>;
}
export interface FixtureDoc {
  id: string; downloadPath: string; displayNameHe: string; uploadAs?: string; category?: string;
  ownerHe?: string | null; periodHe?: string | null; slotHe?: string; issueHe?: string | null; casesHe?: string | null;
}
export interface PresenterBundle {
  manifest: { featured?: Featured[]; featuredNoteHe?: string; documents: FixtureDoc[]; useCases?: UseCase[]; useCasesNoteHe?: string;
    [k: string]: any };
  files: Record<string, { available: boolean; sha256_matches_manifest: boolean }>;
  [k: string]: any;
}

let bundlePromise: Promise<PresenterBundle> | null = null;
/** One fetch of the presenter bundle for the whole side pane (it checksums every golden PDF on the server). */
export function loadPresenterBundle(): Promise<PresenterBundle> {
  bundlePromise ??= fetch("/api/presenter/scenarios").then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .catch((e) => { bundlePromise = null; throw e; });
  return bundlePromise;
}

const OPEN_KEY = "mz.presenter.featured.v1";
const TONE: Record<Route, string> = { PASS: "ok", REVIEW: "warn", BLOCKER: "bad", CORRECTION: "info" };
const ROLE_HE: Record<FileRole, string> = { upload: "", setup: "הכנה", wrong: "הקובץ השגוי", replacement: "התיקון" };
export const fileName = (path: string) => path.split("/").pop() || path;

/** A downloadable fixture: its Hebrew label first, then where it is uploaded, the technical file name in small print, and
 *  the reason an intentionally invalid file is there. Everything shown comes from the presenter manifest. */
export function FixtureRow({ doc, item, testId }: { doc: FixtureDoc; item?: Partial<ScenarioFile>; testId: string }) {
  const label = item?.labelHe || doc.displayNameHe;
  const note = item?.noteHe ?? doc.issueHe;
  const where = [item?.slotHe ?? doc.slotHe, item?.period ? `חודש ${monthHe(item.period)}` : null,
    item?.role && ROLE_HE[item.role] ? ROLE_HE[item.role] : null].filter(Boolean).join(" · ");
  return (
    <li className={`fx${item?.role === "wrong" ? " wrong" : ""}`} data-doc-id={doc.id}>
      <span className="grow fx-main">
        <span className="fx-label">{label}</span>
        <span className="fx-sub">{where && <span>{where}</span>}<span className="ltr fx-file">{fileName(doc.downloadPath)}</span></span>
        {note && <span className="fx-note"><IAlert size={12} />{note}</span>}
      </span>
      <a className="fx-dl" href={`/api/presenter/file?id=${encodeURIComponent(doc.id)}`} download={fileName(doc.downloadPath)}
        data-testid={testId} data-doc-id={doc.id} aria-label={`הורדת ${label}`} title={`הורדת ${fileName(doc.downloadPath)}`}>
        <IDownload size={15} /></a>
    </li>
  );
}
const readOpen = (): string[] => { try { return JSON.parse(localStorage.getItem(OPEN_KEY) || "[]"); } catch { return []; } };

export function FeaturedScenarios() {
  const [bundle, setBundle] = useState<PresenterBundle | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string[]>(readOpen);
  useEffect(() => { loadPresenterBundle().then(setBundle).catch(() => setFailed(true)); }, []);
  useEffect(() => { localStorage.setItem(OPEN_KEY, JSON.stringify(open)); }, [open]);
  useEffect(() => {
    const collapse = () => setOpen([]);
    window.addEventListener(DEMO_RESET_EVENT, collapse);
    return () => window.removeEventListener(DEMO_RESET_EVENT, collapse);
  }, []);
  if (failed) return <div className="small muted">התרחישים המומלצים אינם זמינים בשרת (fixtures/presenter).</div>;
  const featured = bundle?.manifest.featured;
  if (!featured?.length) return null;
  const docs = Object.fromEntries(bundle!.manifest.documents.map((d) => [d.id, d]));
  return (
    <section className="feat-section" aria-labelledby="feat-heading" data-testid="featured-scenarios">
      <h2 id="feat-heading" className="feat-heading">תרחישים מומלצים לדמו</h2>
      <div className="small muted feat-sub">מורידים קובץ כאן, מעלים אותו באפליקציה מימין, ומראים מה ה-AI עשה איתו.</div>
      <div className="feat-list">
        {featured.map((f, i) => (
          <FeaturedCard key={f.id} f={f} index={i} docs={docs} isOpen={open.includes(f.id)}
            onToggle={() => setOpen((ids) => (ids.includes(f.id) ? ids.filter((x) => x !== f.id) : [...ids, f.id]))} />
        ))}
      </div>
      {bundle!.manifest.featuredNoteHe && <div className="tiny muted feat-note">{bundle!.manifest.featuredNoteHe}</div>}
    </section>
  );
}

function FeaturedCard({ f, index, docs, isOpen, onToggle }: {
  f: Featured; index: number; docs: Record<string, FixtureDoc>; isOpen: boolean; onToggle: () => void;
}) {
  const { caseId, auth, openCase } = useCase();
  const nav = useNavigate();
  const here = caseId === f.caseId && auth.status === "signed-in" && !auth.wantCase;
  const files = f.steps.filter((s, i) => f.steps.findIndex((x) => x.file === s.file) === i);
  return (
    <article className={`feat feat-${TONE[f.outcome]}${isOpen ? " open" : ""}`} data-testid={`featured-${f.outcome}`} data-case={f.caseId}>
      <div className="feat-top">
        <span className={`feat-badge ${TONE[f.outcome]}`} data-testid="featured-badge">{index + 1} · {f.badgeHe}</span>
        {here && <span className="scn-on"><ICheck size={12} />פתוח מימין</span>}
      </div>
      <h3 className="feat-title">{f.titleHe}</h3>
      <div className="feat-line"><b>מה בודקים: </b>{f.checksHe}</div>
      <div className="feat-line"><b>מה מצופה: </b>{f.expectHe}</div>
      {f.instructionHe && <div className="feat-line feat-do" data-testid="featured-instruction"><b>איך מדגימים: </b>{f.instructionHe}</div>}
      <ul className="fx-list" data-testid="featured-files">
        {files.map((s) => (docs[s.file] ? <FixtureRow key={s.file} doc={docs[s.file]} item={s} testId="featured-download" /> : null))}
      </ul>
      <div className="feat-line feat-where" data-testid="featured-destination">
        <b>מעלים עבור: </b>{f.borrowerHe} · תיק <span className="ltr">{f.caseDisplay}</span> · {f.destinationHe}
      </div>
      <div className={`feat-expected ${TONE[f.outcome]}`} data-testid="featured-expected">
        <span className="feat-k">תוצאה צפויה</span>
        <span>{f.expectedLabelHe}</span>
      </div>
      <div className="feat-actions">
        <button type="button" className="btn btn-dark scn-btn" data-testid="featured-open-case"
          onClick={() => { openCase(f.caseId); nav("/customer"); }}>{here ? "לבית התיק מימין" : "פתיחת התיק מימין"}</button>
        <button type="button" className="link feat-more" aria-expanded={isOpen} onClick={onToggle} data-testid="featured-toggle">
          איך מציגים <span className="scn-chev" aria-hidden><IChevronDown size={14} /></span>
        </button>
      </div>
      {isOpen && (
        <div className="feat-body" data-testid="featured-playbook">
          <div className="scn-label">סדר העלאה</div>
          <ol className="feat-steps">
            {f.steps.map((s, i) => (
              <li key={`${s.file}-${i}`} className={s.optional ? "optional" : ""}>
                <span className="feat-step-file">{s.labelHe || docs[s.file]?.displayNameHe || fileName(s.file)}</span>
                <span className="tiny muted" data-testid="featured-step-slot">
                  {[s.slotHe, s.period ? `חודש ${monthHe(s.period)}` : null, ROLE_HE[s.role] || null, s.noteHe].filter(Boolean).join(" · ")}
                </span>
              </li>
            ))}
          </ol>
          <div className="scn-label">באפליקציה תראו</div>
          <ul className="feat-bullets">{f.appShowsHe.map((t) => <li key={t}>{t}</li>)}</ul>
          <div className="scn-label">מה עושים</div>
          <ol className="feat-bullets">{f.playbookHe.map((t) => <li key={t}>{t}</li>)}</ol>
          <div className="feat-say"><b>מה אומרים: </b>{f.sayHe}</div>
          {f.avoidHe && <div className="feat-avoid"><IAlert size={13} />{f.avoidHe}</div>}
          <a className="link small" href={`/banker?case=${encodeURIComponent(f.caseId)}`} target="_blank" rel="noreferrer"
            data-testid="featured-banker-link">פתיחה בתצוגת הבנקאית (לשונית חדשה)</a>
        </div>
      )}
    </article>
  );
}

export const DEMO_RESET_EVENT = "mz-demo-reset";
/** TC-01 ↔ UC-01, the first of the six use cases (fixtures/presenter manifest `useCases`) */
const FIRST_DEMO_CASE = "DEMO-MTZ-2026-101";

/** "התחל דמו חדש": wipes the executive demo cases on the server (006–011 and the six use-case cases 101–106), then returns
 *  the app on the right to the first use case. A review still running makes the server answer 409; the control waits and retries. */
export function NewDemoButton() {
  const { openCase, closeUpload, closeAssistant, reload } = useCase();
  const nav = useNavigate();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "warn" | "bad"; text: string } | null>(null);

  const run = async () => {
    setBusy(true);
    setNote(null);
    const started = Date.now();
    try {
      for (;;) {
        try {
          await api.demoReset();
          break;
        } catch (e) {
          const msg = (e as Error).message || "";
          if (!(e instanceof AccessError) && msg.includes("האיפוס יתבצע") && Date.now() - started < 60000) {
            setNote({ tone: "warn", text: "בדיקת מסמך עדיין רצה באחד מתיקי הדמו — ממתינים לסיומה ומאפסים מיד אחריה…" });
            await new Promise((r) => window.setTimeout(r, 3000));
            continue;
          }
          throw e;
        }
      }
      closeUpload();
      closeAssistant();
      window.dispatchEvent(new CustomEvent(DEMO_RESET_EVENT));
      openCase(FIRST_DEMO_CASE);
      nav("/customer");
      reload();
      setNote({ tone: "ok", text: "הדמו מוכן: תיקי הדמו ריקים, ותיק 438839101 (TC-01) פתוח מימין." });
    } catch (e) {
      setNote({ tone: "bad", text: e instanceof AccessError && e.status === 401
        ? "כדי להתחיל דמו חדש צריך להיות מחוברים לאפליקציה מימין."
        : `האיפוס לא הושלם: ${(e as Error).message}` });
    } finally {
      setBusy(false);
      setAsking(false);
    }
  };

  return (
    <div className="new-demo" data-testid="new-demo">
      {!asking ? (
        <button type="button" className="btn btn-orange new-demo-btn" onClick={() => setAsking(true)} disabled={busy} data-testid="new-demo-button">
          התחל דמו חדש
        </button>
      ) : (
        <div className="new-demo-confirm" role="group" aria-label="התחל דמו חדש">
          <div className="small">תיקי הדמו (<span className="ltr">438839006–011</span> ושישת תיקי הפרופילים <span className="ltr">438839101–106</span>)
            יחזרו למצב ריק: מסמכים, ממצאים, החלטות בנקאי ושיחות יימחקו.
            תיקים אחרים, קבצי ההדגמה, המדיניות והרובריקות לא משתנים.</div>
          <div className="row" style={{ gap: 6 }}>
            <button type="button" className="btn btn-orange scn-btn" disabled={busy} onClick={run} data-testid="new-demo-confirm">
              {busy ? <span className="spinner" /> : null}כן, להתחיל דמו חדש
            </button>
            <button type="button" className="btn btn-ghost scn-btn" disabled={busy} onClick={() => setAsking(false)}>ביטול</button>
          </div>
        </div>
      )}
      {note && (
        <div className={`new-demo-note ${note.tone}`} role="status" data-testid="new-demo-status">
          {note.tone === "ok" ? <ICheck size={13} /> : note.tone === "bad" ? <IX size={13} /> : <span className="spinner" />}
          {note.text}
        </div>
      )}
    </div>
  );
}
