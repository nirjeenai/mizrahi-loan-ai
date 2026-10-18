import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AccessError, api, monthHe, monthL, request } from "../api";
import { useCase } from "../caseContext";
import { loc, locList, locOf, tr, useLang } from "../i18n";
import { IAlert, ICheck, IChevronDown, IDownload, IX } from "./Icons";
import type { UseCase } from "./UseCaseScenarios";

/* The featured executive-demo scenarios and the "start a new demo" control. Everything shown comes from the
   presenter manifest (fixtures/presenter): the expected label is the JEEN routing expectation for golden-set facts,
   never a live result. Downloading a file changes nothing in the app; the presenter uploads it on the right. */

export type Route = "PASS" | "REVIEW" | "BLOCKER" | "CORRECTION";
export type FileRole = "upload" | "setup" | "wrong" | "replacement" | "alternative" | "banker_correction" | "banker_accept";
/** One file of a scenario as the manifest resolves it: what it is, where it goes, which month to pick, why it is there. */
export interface ScenarioFile {
  file: string; labelHe: string; slotHe: string; uploadAs: string; period: string | null; role: FileRole; noteHe?: string | null;
  labelEn?: string | null; slotEn?: string | null; noteEn?: string | null;
}
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
  bundlePromise ??= request("/api/presenter/scenarios").then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .catch((e) => { bundlePromise = null; throw e; });
  return bundlePromise;
}

const OPEN_KEY = "mz.presenter.featured.v1";
const TONE: Record<Route, string> = { PASS: "ok", REVIEW: "warn", BLOCKER: "bad", CORRECTION: "info" };
export const ROLE_HE: Record<FileRole, string> = { upload: "", setup: "הכנה", wrong: "הקובץ השגוי", replacement: "התיקון",
  alternative: "חלופה (רשות)", banker_correction: "פעולת הבנקאית", banker_accept: "פעולת הבנקאית" };
const ROLE_EN: Record<FileRole, string> = { upload: "", setup: "Setup", wrong: "The wrong file", replacement: "The correction",
  alternative: "Alternative (optional)", banker_correction: "The banker's action", banker_accept: "The banker's action" };
/** a file's role in the platform's language ("" for a plain upload) */
export const roleL = (role?: FileRole) => (role ? tr(ROLE_HE[role], ROLE_EN[role]) : "");
/** "חודש ספטמבר 2026" / "September 2026" */
export const monthTag = (period: string) => tr(`חודש ${monthHe(period)}`, monthL(period));
export const fileName = (path: string) => path.split("/").pop() || path;

/** A downloadable fixture: its Hebrew label first, then where it is uploaded, the technical file name in small print, and
 *  the reason an intentionally invalid file is there. Everything shown comes from the presenter manifest. */
export function FixtureRow({ doc, item, testId }: { doc: FixtureDoc; item?: Partial<ScenarioFile>; testId: string }) {
  const { t } = useLang();
  const label = loc(item?.labelHe, item?.labelEn) || locOf(doc, "displayNameHe");
  const note = item?.noteHe != null ? loc(item.noteHe, item.noteEn) : locOf(doc, "issueHe");
  const where = [item?.slotHe != null ? loc(item.slotHe, item.slotEn) : locOf(doc, "slotHe"), item?.period ? monthTag(item.period) : null,
    roleL(item?.role) || null].filter(Boolean).join(" · ");
  return (
    <li className={`fx${item?.role === "wrong" ? " wrong" : ""}`} data-doc-id={doc.id}>
      <span className="grow fx-main">
        <span className="fx-label">{label}</span>
        <span className="fx-sub">{where && <span>{where}</span>}<span className="ltr fx-file">{fileName(doc.downloadPath)}</span></span>
        {note && <span className="fx-note"><IAlert size={12} />{note}</span>}
      </span>
      <a className="fx-dl" href={`/api/presenter/file?id=${encodeURIComponent(doc.id)}`} download={fileName(doc.downloadPath)}
        data-testid={testId} data-doc-id={doc.id} aria-label={t(`הורדת ${label}`, `Download ${label}`)}
        title={t(`הורדת ${fileName(doc.downloadPath)}`, `Download ${fileName(doc.downloadPath)}`)}>
        <IDownload size={15} /></a>
    </li>
  );
}
const readOpen = (): string[] => { try { return JSON.parse(localStorage.getItem(OPEN_KEY) || "[]"); } catch { return []; } };

export function FeaturedScenarios() {
  const { t } = useLang();
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
  if (failed) return <div className="small muted">{t("התרחישים המומלצים אינם זמינים בשרת (fixtures/presenter).",
    "The recommended scenarios aren't available on the server (fixtures/presenter).")}</div>;
  const featured = bundle?.manifest.featured;
  if (!featured?.length) return null;
  const docs = Object.fromEntries(bundle!.manifest.documents.map((d) => [d.id, d]));
  return (
    <section className="feat-section" aria-labelledby="feat-heading" data-testid="featured-scenarios">
      <h2 id="feat-heading" className="feat-heading">{t("תרחישים מומלצים", "Recommended scenarios")}</h2>
      <div className="small muted feat-sub">{t("מורידים קובץ כאן, מעלים אותו באפליקציה מימין, ומראים מה ה-AI עשה איתו.",
        "Download a file here, upload it in the app on the right, and show what the AI did with it.")}</div>
      <div className="feat-list">
        {featured.map((f, i) => (
          <FeaturedCard key={f.id} f={f} index={i} docs={docs} isOpen={open.includes(f.id)}
            onToggle={() => setOpen((ids) => (ids.includes(f.id) ? ids.filter((x) => x !== f.id) : [...ids, f.id]))} />
        ))}
      </div>
    </section>
  );
}

function FeaturedCard({ f, index, docs, isOpen, onToggle }: {
  f: Featured; index: number; docs: Record<string, FixtureDoc>; isOpen: boolean; onToggle: () => void;
}) {
  const { caseId, auth, openCase } = useCase();
  const { t } = useLang();
  const nav = useNavigate();
  const here = caseId === f.caseId && auth.status === "signed-in" && !auth.wantCase;
  const files = f.steps.filter((s, i) => f.steps.findIndex((x) => x.file === s.file) === i);
  return (
    <article className={`feat feat-${TONE[f.outcome]}${isOpen ? " open" : ""}`} data-testid={`featured-${f.outcome}`} data-case={f.caseId}>
      <div className="feat-top">
        <span className={`feat-badge ${TONE[f.outcome]}`} data-testid="featured-badge">{index + 1} · {locOf(f, "badgeHe")}</span>
        {here && <span className="scn-on"><ICheck size={12} />{t("פתוח מימין", "Open on the right")}</span>}
      </div>
      <h3 className="feat-title">{locOf(f, "titleHe")}</h3>
      <div className="feat-line"><b>{t("מה בודקים: ", "What's checked: ")}</b>{locOf(f, "checksHe")}</div>
      <div className="feat-line"><b>{t("מה מצופה: ", "What to expect: ")}</b>{locOf(f, "expectHe")}</div>
      {f.instructionHe && <div className="feat-line feat-do" data-testid="featured-instruction"><b>{t("איך מדגימים: ", "How to demo it: ")}</b>{locOf(f, "instructionHe")}</div>}
      <ul className="fx-list" data-testid="featured-files">
        {files.map((s) => (docs[s.file] ? <FixtureRow key={s.file} doc={docs[s.file]} item={s} testId="featured-download" /> : null))}
      </ul>
      <div className="feat-line feat-where" data-testid="featured-destination">
        <b>{t("מעלים עבור: ", "Upload for: ")}</b>{locOf(f, "borrowerHe")} · {t("תיק", "case")} <span className="ltr">{f.caseDisplay}</span> · {locOf(f, "destinationHe")}
      </div>
      <div className={`feat-expected ${TONE[f.outcome]}`} data-testid="featured-expected">
        <span className="feat-k">{t("תוצאה צפויה", "Expected outcome")}</span>
        <span>{locOf(f, "expectedLabelHe")}</span>
      </div>
      <div className="feat-actions">
        <button type="button" className="btn btn-dark scn-btn" data-testid="featured-open-case"
          onClick={() => { openCase(f.caseId); nav("/customer"); }}>{here ? t("לבית התיק מימין", "Go to the case home on the right") : t("פתיחת התיק מימין", "Open the case on the right")}</button>
        <button type="button" className="link feat-more" aria-expanded={isOpen} onClick={onToggle} data-testid="featured-toggle">
          {t("איך מציגים", "How to present it")} <span className="scn-chev" aria-hidden><IChevronDown size={14} /></span>
        </button>
      </div>
      {isOpen && (
        <div className="feat-body" data-testid="featured-playbook">
          <div className="scn-label">{t("סדר העלאה", "Upload order")}</div>
          <ol className="feat-steps">
            {f.steps.map((s, i) => (
              <li key={`${s.file}-${i}`} className={s.optional ? "optional" : ""}>
                <span className="feat-step-file">{loc(s.labelHe, s.labelEn) || locOf(docs[s.file], "displayNameHe") || fileName(s.file)}</span>
                <span className="tiny muted" data-testid="featured-step-slot">
                  {[loc(s.slotHe, s.slotEn), s.period ? monthTag(s.period) : null, roleL(s.role) || null, loc(s.noteHe, s.noteEn)].filter(Boolean).join(" · ")}
                </span>
              </li>
            ))}
          </ol>
          <div className="scn-label">{t("באפליקציה תראו", "What you'll see in the app")}</div>
          <ul className="feat-bullets">{locList(f, "appShowsHe").map((x, i) => <li key={f.appShowsHe[i]}>{x}</li>)}</ul>
          <div className="scn-label">{t("מה עושים", "What to do")}</div>
          <ol className="feat-bullets">{locList(f, "playbookHe").map((x, i) => <li key={f.playbookHe[i]}>{x}</li>)}</ol>
          <div className="feat-say"><b>{t("מה אומרים: ", "What to say: ")}</b>{locOf(f, "sayHe")}</div>
          {f.avoidHe && <div className="feat-avoid"><IAlert size={13} />{locOf(f, "avoidHe")}</div>}
          <a className="link small" href={`/banker?case=${encodeURIComponent(f.caseId)}`} target="_blank" rel="noreferrer"
            data-testid="featured-banker-link">{t("פתיחה בתצוגת הבנקאית (לשונית חדשה)", "Open in the banker view (new tab)")}</a>
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
  const { en, t } = useLang();
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
          const msg = (e as { detailHe?: string }).detailHe || (e as Error).message || "";
          if (!(e instanceof AccessError) && msg.includes("האיפוס יתבצע") && Date.now() - started < 60000) {
            setNote({ tone: "warn", text: tr("בדיקת מסמך עדיין רצה באחד התיקים, ממתינים לסיומה ומאפסים מיד אחריה…",
              "A document check is still running in one of the cases — waiting for it to finish, then resetting right after…") });
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
      setNote({ tone: "ok", text: tr("מוכן: התיקים ריקים, ותיק 438839101 (TC-01) פתוח מימין.",
        "Ready: the cases are empty, and case 438839101 (TC-01) is open on the right.") });
    } catch (e) {
      setNote({ tone: "bad", text: e instanceof AccessError && e.status === 401
        ? tr("כדי להתחיל מחדש צריך להיות מחוברים לאפליקציה מימין.", "To start over, you need to be signed in to the app on the right.")
        : tr(`האיפוס לא הושלם: ${(e as Error).message}`, `The reset didn't complete: ${(e as Error).message}`) });
    } finally {
      setBusy(false);
      setAsking(false);
    }
  };

  return (
    <div className="new-demo" data-testid="new-demo">
      {!asking ? (
        <button type="button" className="btn btn-orange new-demo-btn" onClick={() => setAsking(true)} disabled={busy} data-testid="new-demo-button">
          {t("התחלה מחדש", "Start a new demo")}
        </button>
      ) : (
        <div className="new-demo-confirm" role="group" aria-label={t("התחלה מחדש", "Start a new demo")}>
          {en ? <div className="small">The cases (<span className="ltr">438839006–011</span> and the six profile cases <span className="ltr">438839101–106</span>)
            will go back to empty: documents, findings, banker decisions and conversations will be deleted.
            Other cases, the files, the policy and the rubrics don't change.</div>
            : <div className="small">התיקים (<span className="ltr">438839006–011</span> ושישת תיקי הפרופילים <span className="ltr">438839101–106</span>)
            יחזרו למצב ריק: מסמכים, ממצאים, החלטות בנקאי ושיחות יימחקו.
            תיקים אחרים, הקבצים, המדיניות והרובריקות לא משתנים.</div>}
          <div className="row" style={{ gap: 6 }}>
            <button type="button" className="btn btn-orange scn-btn" disabled={busy} onClick={run} data-testid="new-demo-confirm">
              {busy ? <span className="spinner" /> : null}{t("כן, להתחיל מחדש", "Yes, start over")}
            </button>
            <button type="button" className="btn btn-ghost scn-btn" disabled={busy} onClick={() => setAsking(false)}>{t("ביטול", "Cancel")}</button>
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
