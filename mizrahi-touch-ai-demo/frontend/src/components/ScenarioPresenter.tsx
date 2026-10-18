import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ilsL, monthL } from "../api";
import { useCase } from "../caseContext";
import { loc, locList, locOf, tr, useLang } from "../i18n";
import { fileName as baseName, loadPresenterBundle, monthTag, type ScenarioFile } from "./FeaturedScenarios";
import { IAlert, ICheck, IChevronDown, IDownload } from "./Icons";

/* Expected outputs here are static golden-set ground truth (fixtures/presenter). They must never be fed into,
   or presented as, the live review results shown in the app on the right. */

type DocVerdict = "VALID" | "NEEDS_REVIEW" | "INVALID" | "DUPLICATE";
interface PresenterDoc {
  id: string; downloadPath: string; displayNameHe: string; category: string; uploadGuidanceHe: string;
  expectedDocumentVerdict: DocVerdict; expectedBorrower: "IDO" | "NOA" | "OTHER" | null; expectedPrintedPeriod: string | null;
  expectedNetILS: number | null; expectedGrossILS: number | null; expectedNoteHe: string; expectedRequiredFollowup: string | null;
  isSynthetic: boolean; sha256: string; uploadAs?: string;
  ownerHe?: string | null; periodHe?: string | null; slotHe?: string; issueHe?: string | null; casesHe?: string | null;
}
interface PresenterScenario {
  id: string; titleHe: string; goalHe: string; state?: string; dependsOn?: string; files: string[]; uploadAs?: Record<string, string>;
  instructionHe?: string; bankerHe?: string; caseId?: string; items?: ScenarioFile[]; verification?: "live";
  expectedCaseHe: string[]; expectedReasonCodes?: string[]; expectedJson?: string;
  declaredIncome?: { source: string; provenance: string; verified: boolean; noteHe: string };
}
interface ExpectedFinding { id: string; reason_code: string; state: string; owner?: string; period?: string; evidence_refs?: string[]; resolved_by?: string }
interface NegativeTest { test_id: string; input: string; condition: string; expected_reason_codes: string[]; expected_verdict: string; safety: string }
interface FileInfo { available: boolean; bytes: number; sha256_matches_manifest: boolean; pages: number | null; input_mode: string | null }
interface Rubric { rubric_id: string; version: string; document_type: string; family?: string; parameters?: { threshold_ils?: number }; criteria: { id: string }[] }
interface Bundle {
  manifest: { titleHe: string; disclosureHe: string; caseContext: { borrowers: string[] }; documents: PresenterDoc[]; scenarios: PresenterScenario[]; notesHe: string[] };
  files: Record<string, FileInfo>;
  expected: Record<string, any>;
  negative_tests: NegativeTest[];
  rubrics: Rubric[];
}
interface CaseLink { code: string; state?: string; owner?: string; period?: string }
type Mark = { uploaded?: boolean; matched?: boolean; mismatch?: boolean };
interface Ctx {
  bundle: Bundle; docs: Record<string, PresenterDoc>; marks: Record<string, Mark>;
  toggle: (key: string, field: keyof Mark) => void; cases: Record<string, { display_number: string; title_he: string; title_en?: string }>;
}

const PRESENTER_CASE = "DEMO-MTZ-2026-004";
const QA_CASE = "DEMO-MTZ-2026-005";
const MARKS_KEY = "mz.presenter.marks.v1";
const OPEN_KEY = "mz.presenter.open.v1";
const SUPPLEMENTARY = "SUPPLEMENTARY";

const CATEGORY_FAMILY: Record<string, string> = { PAYSLIP: "payslip", BANK_STATEMENT: "bank_statement", ID_CARD: "id_document",
  PURPOSE_PROOF: "purpose_proof", TAX_FORM: "tax_form" };
const VERDICT: Record<DocVerdict, { he: string; tone: string }> = {
  VALID: { he: "מסמך תקין לפי קריטריון", tone: "ok" }, NEEDS_REVIEW: { he: "נדרש בירור", tone: "warn" },
  INVALID: { he: "לא תקין", tone: "bad" }, DUPLICATE: { he: "כפול", tone: "info" },
};
const ALT_VERDICT_HE: Record<string, string> = {
  INVALID_OR_NEEDS_REVIEW: "מקובל גם ״נדרש בירור״", VALID_IF_OCR_VERIFIED: "תקין רק אם עובדות הסריקה אומתו בפועל",
};
const CODE_HE: Record<string, string> = {
  REQUIRED_PERIOD_MISSING: "חודש נדרש חסר", DUPLICATE_PERIOD: "אותו חודש הוגש פעמיים",
  FILENAME_CONTENT_PERIOD_MISMATCH: "שם הקובץ סותר את החודש המודפס", DECLARED_NET_INCOME_VARIANCE: "פער בין נטו מוצהר לנטו בתלושים",
  BORROWER_IDENTITY_MISMATCH: "המסמך שייך ללווה אחר", ACCOUNT_OWNER_MISMATCH: "בעל החשבון אינו לווה בתיק",
  DOCUMENT_UNREADABLE: "המסמך אינו קריא", EXACT_FILE_DUPLICATE: "אותו קובץ בדיוק הועלה שוב",
  FILE_NAME_PERIOD_MISMATCH: "שם הקובץ סותר את החודש המודפס", REQUIRED_DOCUMENT_MISSING: "מסמך נדרש טרם הועלה",
  STATEMENT_PERIOD_GAP: "חסרה תקופה בדפי העו״ש", UNEXPECTED_DOCUMENT_TYPE: "סוג המסמך אינו מתאים לדרישה",
  ID_EXPIRED: "תוקף תעודת הזהות פג", DOCUMENT_STALE: "המסמך אינו עדכני", DECLARED_VS_DOCUMENT_INCOME_VARIANCE: "פער בין נטו מוצהר לנטו בתלושים",
};
const STATE_HE: Record<string, string> = { OPEN: "פתוח", RESOLVED: "נסגר", SUPERSEDED: "הוחלף · נשמר בהיסטוריה", READY_FOR_BANKER: "ממתין לבנקאי" };
const OWNER_HE: Record<string, string> = { CUSTOMER: "באחריות הלקוח", BANKER: "באחריות הבנקאי" };
const READINESS_HE: Record<string, string> = {
  NEEDS_CUSTOMER_ACTION: "נדרשת פעולת לקוח", READY_FOR_BANKER_REVIEW: "מוכן לבדיקת בנקאי", NOT_EVALUATED: "לא נבדק",
};
const MARK_HE: Record<keyof Mark, string> = { uploaded: "הועלה", matched: "התוצאה תואמת", mismatch: "לא תואמת / לבדיקה" };
const VERDICT_EN: Record<DocVerdict, string> = { VALID: "A valid document per the criteria", NEEDS_REVIEW: "Needs review",
  INVALID: "Not valid", DUPLICATE: "Duplicate" };
const ALT_VERDICT_EN: Record<string, string> = {
  INVALID_OR_NEEDS_REVIEW: "\"Needs review\" is also accepted", VALID_IF_OCR_VERIFIED: "Valid only if the scan's facts were actually verified",
};
const CODE_EN: Record<string, string> = {
  REQUIRED_PERIOD_MISSING: "A required month is missing", DUPLICATE_PERIOD: "The same month was submitted twice",
  FILENAME_CONTENT_PERIOD_MISMATCH: "The file name contradicts the printed month", DECLARED_NET_INCOME_VARIANCE: "A gap between declared net and the payslips' net",
  BORROWER_IDENTITY_MISMATCH: "The document belongs to another borrower", ACCOUNT_OWNER_MISMATCH: "The account holder isn't a borrower on the case",
  DOCUMENT_UNREADABLE: "The document can't be read", EXACT_FILE_DUPLICATE: "The exact same file was uploaded again",
  FILE_NAME_PERIOD_MISMATCH: "The file name contradicts the printed month", REQUIRED_DOCUMENT_MISSING: "A required document isn't uploaded yet",
  STATEMENT_PERIOD_GAP: "A period is missing from the bank statements", UNEXPECTED_DOCUMENT_TYPE: "The document type doesn't match the requirement",
  ID_EXPIRED: "The ID card has expired", DOCUMENT_STALE: "The document isn't recent", DECLARED_VS_DOCUMENT_INCOME_VARIANCE: "A gap between declared net and the payslips' net",
};
const STATE_EN: Record<string, string> = { OPEN: "Open", RESOLVED: "Closed", SUPERSEDED: "Superseded · kept in the history", READY_FOR_BANKER: "Awaiting the banker" };
const OWNER_EN: Record<string, string> = { CUSTOMER: "The customer's to handle", BANKER: "The banker's to handle" };
const READINESS_EN: Record<string, string> = {
  NEEDS_CUSTOMER_ACTION: "Customer action needed", READY_FOR_BANKER_REVIEW: "Ready for the banker's review", NOT_EVALUATED: "Not checked",
};
const MARK_EN: Record<keyof Mark, string> = { uploaded: "Uploaded", matched: "Result matches", mismatch: "Doesn't match / to check" };
/** a label from one of the maps above in the platform's language; `fallback` (the code) when it has none */
const lbl = (he: Record<string, string>, en: Record<string, string>, key: string, fallback = key) => tr(he[key], en[key]) ?? fallback;
const COVERAGE_CODES = ["REQUIRED_PERIOD_MISSING", "DUPLICATE_PERIOD", "FILENAME_CONTENT_PERIOD_MISMATCH"];

const unique = <T,>(xs: T[]) => Array.from(new Set(xs));
const codesIn = (text?: string | null) => unique(text?.match(/\b[A-Z]+(?:_[A-Z]+)+\b/g) ?? []).filter((c) => c !== "NEEDS_REVIEW");
const scenarioNumber = (id: string) => id.replace(/^CASE-/, "");
const targetCase = (s: PresenterScenario) => s.caseId ?? (s.state === "isolated_qa_case" ? QA_CASE : PRESENTER_CASE);
const scenarioItems = (s: PresenterScenario, docs: Record<string, PresenterDoc>): Partial<ScenarioFile>[] =>
  s.items ?? s.files.filter((id) => docs[id]).map((id) => ({ file: id }));
const markKey = (s: PresenterScenario, docId?: string) => (docId ? `${s.id}/${docId}` : s.id);

function prerequisite(s: PresenterScenario): { chip: string; text: string; resettable: boolean } {
  if (s.dependsOn) {
    const n = scenarioNumber(s.dependsOn);
    return { chip: tr(`אחרי ${n}`, `After ${n}`), text: tr(`ממשיכים מתרחיש ${n} באותו תיק, בלי איפוס.`,
      `Continue from scenario ${n} in the same case, without a reset.`), resettable: false };
  }
  if (s.state === "isolated_qa_case") {
    return { chip: tr("QA מבודד", "Isolated QA"), text: tr("תיק QA מבודד, מאפסים אותו לפני התרחיש, כדי לא לזהם את תיק ההצגה.",
      "An isolated QA case: reset it before the scenario, so the presentation case stays clean."), resettable: true };
  }
  return { chip: tr("תיק נקי", "Clean case"), text: tr("מתחילים מתיק נקי, מאפסים את תיק התרחישים לפני ההעלאה הראשונה.",
    "Start from a clean case: reset the scenario case before the first upload."), resettable: true };
}

function negativeCodes(ctx: Ctx, docId: string) {
  return ctx.bundle.negative_tests.filter((t) => t.input === docId).flatMap((t) => t.expected_reason_codes);
}

function docCodes(ctx: Ctx, d: PresenterDoc) {
  return unique([...negativeCodes(ctx, d.id), ...codesIn(d.expectedNoteHe), ...codesIn(d.expectedRequiredFollowup)]);
}

function expectedFindings(ctx: Ctx, s?: PresenterScenario): ExpectedFinding[] {
  return (s?.expectedJson && ctx.bundle.expected[s.expectedJson]?.expected_findings) || [];
}

/** Case-level findings that this document is evidence for (or resolves) in the scenario's ground truth. */
function caseLinks(ctx: Ctx, d: PresenterDoc, s?: PresenterScenario): CaseLink[] {
  const exp = s?.expectedJson ? ctx.bundle.expected[s.expectedJson] : undefined;
  const findings = expectedFindings(ctx, s);
  const toLink = (f: ExpectedFinding): CaseLink => ({ code: f.reason_code, state: f.state, owner: f.owner, period: f.period });
  const links = findings.filter((f) => exp?.supplement_document === d.id || f.resolved_by === d.id
    || (f.evidence_refs || []).some((ref) => ref.split("#")[0] === d.id)).map(toLink);
  for (const code of docCodes(ctx, d)) {
    if (links.some((l) => l.code === code)) continue;
    const f = findings.find((x) => x.reason_code === code);
    links.push(f ? toLink(f) : { code });
  }
  return links;
}

function scenarioLinks(ctx: Ctx, s: PresenterScenario): CaseLink[] {
  const findings = expectedFindings(ctx, s);
  if (findings.length) return findings.map((f) => ({ code: f.reason_code, state: f.state, owner: f.owner, period: f.period }));
  return (s.expectedReasonCodes ?? unique(s.files.flatMap((id) => (ctx.docs[id] ? docCodes(ctx, ctx.docs[id]) : []))))
    .map((code) => ({ code }));
}

function useStored<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => { localStorage.setItem(key, JSON.stringify(value)); }, [key, value]);
  return [value, setValue] as const;
}

export function ScenarioPresenter() {
  const { en, t } = useLang();
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [failed, setFailed] = useState(false);
  const [cases, setCases] = useState<Ctx["cases"]>({});
  const [marks, setMarks] = useStored<Record<string, Mark>>(MARKS_KEY, {});
  const [open, setOpen] = useStored<string[]>(OPEN_KEY, ["CASE-01"]);

  useEffect(() => {
    loadPresenterBundle().then((b) => setBundle(b as unknown as Bundle)).catch(() => setFailed(true));
    api.demoCases().then((list) => setCases(Object.fromEntries(list.map((c) => [c.case_id, c])))).catch(() => setCases({}));
  }, []);

  const docs = useMemo(() => Object.fromEntries((bundle?.manifest.documents || []).map((d) => [d.id, d])), [bundle]);
  if (failed) return <div className="small muted scn-section">{t("ספריית תרחישי הבדיקה אינה זמינה בשרת (fixtures/presenter).",
    "The test scenario library isn't available on the server (fixtures/presenter).")}</div>;
  if (!bundle) return null;

  const toggle = (key: string, field: keyof Mark) => setMarks((all) => {
    const next: Mark = { ...all[key], [field]: !all[key]?.[field] };
    if (field === "matched" && next.matched) next.mismatch = false;
    if (field === "mismatch" && next.mismatch) next.matched = false;
    return { ...all, [key]: next };
  });
  const ctx: Ctx = { bundle, docs, marks, toggle, cases };
  const { scenarios, documents } = bundle.manifest;
  const slots = scenarios.flatMap((s) => s.files.map((id) => markKey(s, id)));
  const done = slots.filter((k) => marks[k]?.uploaded).length;
  const referenced = new Set(scenarios.flatMap((s) => s.files));
  // the use-case packs (set "profiles") are listed on their own cards, not among the library's supplementary files
  const extras = documents.filter((d) => !referenced.has(d.id) && (d as { set?: string }).set !== "profiles");
  const flip = (id: string) => setOpen((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  return (
    <section className="scn-section" data-testid="scenario-presenter" aria-label={t("כל תרחישי הבדיקה", "All test scenarios")}>
      <div className="small muted">{t(`${scenarios.length} תרחישי בדיקה לבקשת הלוואה, לבדיקות ול-QA: מורידים קובץ, מעלים אותו באפליקציה מימין ומשווים לתוצאה הצפויה.`,
        `${scenarios.length} test scenarios for a loan application, for testing and QA: download a file, upload it in the app on the right and compare with the expected outcome.`)}</div>
      <div className="scn-toolbar">
        {en ? <span className="small" data-testid="scn-progress">Marked as uploaded: <b className="ltr">{done}/{slots.length}</b> documents</span>
          : <span className="small" data-testid="scn-progress">סומנו כהועלו: <b className="ltr">{done}/{slots.length}</b> מסמכים</span>}
        <ConfirmButton label={t("איפוס סימון בדיקות", "Clear test marks")} confirmLabel={t("כן, לנקות סימונים", "Yes, clear the marks")} testId="scn-reset-marks"
          warning={t("מנקה רק את הסימונים בפאנל הזה. מסמכים ותוצאות באפליקציה לא נמחקים.",
            "Clears only the marks in this panel. Documents and results in the app aren't deleted.")}
          onConfirm={() => setMarks({})} className="btn btn-ghost scn-btn" />
      </div>
      <details className="scn-rules">
        <summary>{t("כללי הצגה", "Presentation rules")}</summary>
        <ul>{locList(bundle.manifest, "notesHe").map((n, i) => <li key={bundle.manifest.notesHe[i]}>{n}</li>)}</ul>
      </details>
      <div className="scn-list">
        {scenarios.map((s) => <ScenarioCard key={s.id} s={s} ctx={ctx} isOpen={open.includes(s.id)} onToggle={() => flip(s.id)} />)}
        {extras.length > 0 && (
          <section className={`scn${open.includes(SUPPLEMENTARY) ? " open" : ""}`} data-testid="scn-supplementary">
            <button type="button" className="scn-head" aria-expanded={open.includes(SUPPLEMENTARY)} onClick={() => flip(SUPPLEMENTARY)}>
              <span className="grow">
                <span className="scn-title">{t("קבצים משלימים, מחוץ לתרחישים", "Supplementary files, outside the scenarios")}</span>
                <span className="scn-meta"><span>{t(`${extras.length} קבצים לרפרנס`, `${extras.length} reference files`)}</span></span>
              </span>
              <span className="scn-chev"><IChevronDown /></span>
            </button>
            {open.includes(SUPPLEMENTARY) && (
              <div className="scn-body">{extras.map((d, i) => <FileCard key={d.id} doc={d} index={i} ctx={ctx} />)}</div>
            )}
          </section>
        )}
      </div>
    </section>
  );
}

function ScenarioCard({ s, ctx, isOpen, onToggle }: { s: PresenterScenario; ctx: Ctx; isOpen: boolean; onToggle: () => void }) {
  const { caseId, openCase, reload } = useCase();
  const { t } = useLang();
  const nav = useNavigate();
  const [resetNote, setResetNote] = useState<string | null>(null);
  const target = targetCase(s);
  const caseInfo = ctx.cases[target];
  const caseNo = caseInfo?.display_number ?? target;
  const pre = prerequisite(s);
  const exp = s.expectedJson ? ctx.bundle.expected[s.expectedJson] : undefined;
  const links = scenarioLinks(ctx, s);
  const uploaded = s.files.filter((id) => ctx.marks[markKey(s, id)]?.uploaded).length;
  const flagged = [markKey(s), ...s.files.map((id) => markKey(s, id))].some((k) => ctx.marks[k]?.mismatch);
  const bodyId = `scn-body-${s.id}`;

  return (
    <section className={`scn${isOpen ? " open" : ""}`} data-testid={`scn-${s.id}`}>
      <button type="button" className="scn-head" aria-expanded={isOpen} aria-controls={isOpen ? bodyId : undefined} onClick={onToggle}
        data-testid={`scn-toggle-${s.id}`}>
        <span className="grow">
          <span className="scn-title">{locOf(s, "titleHe")}</span>
          <span className="scn-meta">
            <span data-testid={`scn-count-${s.id}`}><span className="ltr">{uploaded}/{s.files.length}</span> {t("מסמכים בתרחיש", "documents in the scenario")}</span>
            <span className="scn-chip">{pre.chip}</span>
            {s.verification === "live" && <span className="scn-chip warn" title={t("אין הקלטת REPLAY לקבצים, התוצאה נבדקת בהרצה חיה בלבד",
              "The files have no REPLAY recording; the result is checked in a live run only")}>{t("LIVE בלבד", "LIVE only")}</span>}
            {flagged && <span className="scn-chip warn"><IAlert size={11} />{t("לבדיקה", "To check")}</span>}
          </span>
        </span>
        <span className="scn-chev"><IChevronDown /></span>
      </button>
      {isOpen && (
        <div className="scn-body" id={bodyId}>
          <div className="scn-goal"><b>{t("מטרה: ", "Goal: ")}</b>{locOf(s, "goalHe")}</div>
          {s.instructionHe && <div className="scn-do" data-testid={`scn-instruction-${s.id}`}><b>{t("מה עושים: ", "What to do: ")}</b>{locOf(s, "instructionHe")}</div>}

          <div className="scn-box" data-testid={`scn-prereq-${s.id}`}>
            <div className="scn-label">{t("לפני שמתחילים", "Before you start")}</div>
            <div>{pre.text}</div>
            {s.declaredIncome && (
              <div data-testid={`scn-declared-${s.id}`}>
                <b>{t("הכנסה מוצהרת: ", "Declared income: ")}</b>{locOf(s.declaredIncome, "noteHe")}{" "}
                <span className="scn-chip"><span className="ltr">{s.declaredIncome.provenance}</span></span>
                {!s.declaredIncome.verified && <span className="scn-chip">{t("לא מאומתת", "Not verified")}</span>}
              </div>
            )}
            <div className="scn-case">
              <span>{t("תיק באפליקציה: ", "Case in the app: ")}<b className="ltr">{caseNo}</b>{caseInfo ? ` · ${loc(caseInfo.title_he, caseInfo.title_en)}` : ""}</span>
              {caseId === target
                ? <span className="scn-on"><ICheck size={12} />{t("פתוח עכשיו מימין", "Open on the right now")}</span>
                : <button type="button" className="link" onClick={() => { openCase(target); nav("/customer/documents"); }}
                  data-testid={`scn-open-case-${s.id}`}>{t("לפתוח את התיק מימין", "Open the case on the right")}</button>}
            </div>
            {pre.resettable && (
              <ConfirmButton label={t("איפוס התיק באפליקציה…", "Reset the case in the app…")} confirmLabel={t("כן, לאפס את התיק", "Yes, reset the case")} testId={`scn-reset-case-${s.id}`}
                className="link scn-danger"
                warning={t(`מוחק מתיק ${caseNo} את כל המסמכים, הממצאים והשיחה. סימוני המגיש בפאנל נשמרים.`,
                  `Deletes all the documents, findings and the conversation from case ${caseNo}. The presenter's marks in this panel are kept.`)}
                onConfirm={async () => {
                  try {
                    await api.reset(target);
                    if (caseId === target) reload();
                    setResetNote(tr(`תיק ${caseNo} אופס, אפשר להתחיל להעלות.`, `Case ${caseNo} was reset; you can start uploading.`));
                  } catch (e) {
                    setResetNote(tr(`האיפוס נכשל: ${(e as Error).message}`, `The reset failed: ${(e as Error).message}`));
                  }
                }} />
            )}
            {resetNote && <div className="tiny" role="status">{resetNote}</div>}
          </div>

          <div className="scn-expect" data-testid={`scn-expected-case-${s.id}`}>
            <div className="scn-label">{t("מה צריך לראות באפליקציה · Expected ברמת התיק", "What you should see in the app · Expected at case level")}</div>
            <ul>{locList(s, "expectedCaseHe").map((x, i) => <li key={s.expectedCaseHe[i]}>{x}</li>)}</ul>
            {s.bankerHe && <div className="scn-banker" data-testid={`scn-banker-${s.id}`}>{locOf(s, "bankerHe")}</div>}
            <details className="scn-tech" data-testid={`scn-codes-${s.id}`}>
              <summary>{t("פרטים טכניים · קודי ממצא וסטטוסים", "Technical details · finding codes and statuses")}</summary>
              <div className="scn-label">{t("קודי ממצא צפויים", "Expected finding codes")}</div>
              {links.length ? <div className="scn-codes">{links.map((l) => <CodeLine key={l.code} link={l} />)}</div>
                : <div className="tiny muted">{t("ללא קוד ממצא צפוי, ההצלחה נמדדת בחילוץ מאומת של עובדות המסמך.",
                  "No finding code is expected; success is measured by verified extraction of the document's facts.")}</div>}
              {exp && <StatusLines exp={exp} />}
            </details>
            <Checks markId={markKey(s)} ctx={ctx} label={t("סימון מגיש לתוצאת התיק", "Presenter's mark for the case result")} />
          </div>

          <div className="scn-label">{t("סדר העלאה", "Upload order")}</div>
          {scenarioItems(s, ctx.docs).map((it, i) => (ctx.docs[it.file!]
            ? <FileCard key={it.file} doc={ctx.docs[it.file!]} item={it} index={i} scenario={s} ctx={ctx} /> : null))}
          <TechDetails s={s} ctx={ctx} links={links} />
        </div>
      )}
    </section>
  );
}

function FileCard({ doc, item, index, scenario, ctx }: {
  doc: PresenterDoc; item?: Partial<ScenarioFile>; index: number; scenario?: PresenterScenario; ctx: Ctx;
}) {
  const { en, t } = useLang();
  const info = ctx.bundle.files[doc.id];
  const name = baseName(doc.downloadPath);
  const label = loc(item?.labelHe, item?.labelEn) || locOf(doc, "displayNameHe");
  const note = item?.noteHe != null ? loc(item.noteHe, item.noteEn) : locOf(doc, "issueHe");
  const verdict = VERDICT[doc.expectedDocumentVerdict] ?? { he: doc.expectedDocumentVerdict, tone: "info" };
  const verdictText = en ? VERDICT_EN[doc.expectedDocumentVerdict] ?? doc.expectedDocumentVerdict : verdict.he;
  const alt = ctx.bundle.negative_tests.find((x) => x.input === doc.id && ALT_VERDICT_HE[x.expected_verdict]);
  const links = caseLinks(ctx, doc, scenario);

  return (
    <article className={`scn-file${item?.role === "wrong" ? " wrong" : ""}`} data-testid="scn-file" data-doc-id={doc.id}>
      <div className="scn-file-top">
        <span className="scn-num" aria-hidden="true">{index + 1}</span>
        <div className="grow">
          <div className="scn-name" data-testid="scn-file-label">{label}</div>
          <div className="scn-meta">{[locOf(doc, "ownerHe"), locOf(doc, "periodHe")].filter(Boolean).map((x) => <span key={x}>{x}</span>)}</div>
        </div>
        <a className="fx-dl" href={`/api/presenter/file?id=${encodeURIComponent(doc.id)}`} download={name} data-testid="scn-download"
          data-doc-id={doc.id} aria-label={t(`הורדת ${label}`, `Download ${label}`)} title={t(`הורדת ${name}`, `Download ${name}`)}>
          <IDownload size={15} />
        </a>
      </div>
      {note && <div className="scn-warnline" data-testid="scn-file-issue"><IAlert size={13} />{note}</div>}
      <div className="scn-upload">
        {scenario ? (
          <><span className="scn-k">{t("להעלאה מימין:", "Upload on the right:")}</span> {item?.slotHe != null ? loc(item.slotHe, item.slotEn) : locOf(doc, "slotHe")}{item?.period ? ` · ${monthTag(item.period)}` : ""}</>
        ) : <span className="tiny muted">{t("קובץ רפרנס, אינו חלק מתרחיש.", "A reference file, not part of a scenario.")}{doc.casesHe ? ` ${locOf(doc, "casesHe")} · ${locOf(doc, "slotHe")}` : ""}</span>}
      </div>
      <div className="scn-filename">
        <span className="ltr">{name}</span>
        {info?.pages ? <span> · {info.pages} {t("עמ׳", info.pages === 1 ? "page" : "pages")}</span> : null}
        {info?.input_mode === "image_only" && <span> · {t("סרוק, ללא שכבת טקסט", "scanned, no text layer")}</span>}
      </div>
      <details className="scn-tech scn-filetech">
        <summary>{t("פרטים טכניים · תוצאה צפויה למסמך", "Technical details · expected document result")}</summary>
      <div className="scn-exp" data-testid="scn-expected-doc">
        <div className="scn-exp-title">Expected Output</div>
        <div className="scn-exp-row">
          <span className="scn-k">{t("המסמך", "Document")}</span>
          <span className={`scn-verdict ${verdict.tone}`} data-verdict={doc.expectedDocumentVerdict}>{t("צפוי: ", "Expected: ")}{verdictText}</span>
          {alt && <span className="tiny muted">{lbl(ALT_VERDICT_HE, ALT_VERDICT_EN, alt.expected_verdict)}</span>}
        </div>
        {(doc.expectedNetILS != null || doc.expectedGrossILS != null) && (
          <div className="tiny">
            {doc.expectedNetILS != null && <>{t("נטו", "Net")} <span className="ltr">{ilsL(doc.expectedNetILS)}</span></>}
            {doc.expectedNetILS != null && doc.expectedGrossILS != null && " · "}
            {doc.expectedGrossILS != null && <>{t("ברוטו", "Gross")} <span className="ltr">{ilsL(doc.expectedGrossILS)}</span></>}
          </div>
        )}
        <div className="scn-note">{locOf(doc, "expectedNoteHe")}</div>
        <div className="scn-exp-row">
          <span className="scn-k">{t("התיק", "Case")}</span>
          {links.length ? <div className="scn-codes grow">{links.map((l) => <CodeLine key={l.code} link={l} />)}</div>
            : <span className="tiny muted">{t("ללא ממצא ברמת התיק שמשויך למסמך זה", "No case-level finding is linked to this document")}</span>}
        </div>
      </div>
      </details>
      {scenario && <Checks markId={markKey(scenario, doc.id)} ctx={ctx} label={t(`סימון מגיש, ${doc.displayNameHe}`, `Presenter's mark, ${locOf(doc, "displayNameHe")}`)} />}
    </article>
  );
}

function CodeLine({ link }: { link: CaseLink }) {
  useLang();
  return (
    <div className="scn-code" data-code={link.code}>
      <span className="bold">{lbl(CODE_HE, CODE_EN, link.code)}</span>
      {link.period && <span>· {monthL(link.period)}</span>}
      {link.state && <span className={`scn-state ${link.state}`}>· {lbl(STATE_HE, STATE_EN, link.state)}</span>}
      {link.owner && <span>· {lbl(OWNER_HE, OWNER_EN, link.owner)}</span>}
      <code className="ltr">{link.code}</code>
    </div>
  );
}

function StatusLines({ exp }: { exp: any }) {
  const { t } = useLang();
  const value = (code?: string | null) => (code ? <><b>{lbl(READINESS_HE, READINESS_EN, code)}</b> <code className="ltr">{code}</code></> : <b>—</b>);
  return (
    <div className="scn-status">
      <div>{t("מסמכי הבקשה: ", "Application documents: ")}{value(exp.salary_documents_readiness)}</div>
      <div>{t("החלטת בנק: ", "Bank decision: ")}<b>{exp.bank_decision ? String(exp.bank_decision) : t("אין, רק הבנקאי מחליט", "None — only the banker decides")}</b></div>
      {exp.bank_stage && (
        <div>{t("שלב בבנק: ", "Bank stage: ")}<code className="ltr">{exp.bank_stage.value}</code> · <code className="ltr">{exp.bank_stage.source}</code>
          {exp.bank_stage.official_approval_created === false ? t(" · לא נוצר אישור רשמי", " · no official approval was created") : ""}</div>
      )}
    </div>
  );
}

function Checks({ markId, ctx, label }: { markId: string; ctx: Ctx; label: string }) {
  const { t } = useLang();
  const m = ctx.marks[markId] || {};
  return (
    <div className="scn-checks" role="group" aria-label={label} data-testid="scn-checks" data-mark={markId}>
      {(Object.keys(MARK_HE) as (keyof Mark)[]).map((field) => (
        <label key={field}>
          <input type="checkbox" checked={!!m[field]} onChange={() => ctx.toggle(markId, field)} data-testid={`mark-${field}`} />
          {t(MARK_HE[field], MARK_EN[field])}
        </label>
      ))}
    </div>
  );
}

function TechDetails({ s, ctx, links }: { s: PresenterScenario; ctx: Ctx; links: CaseLink[] }) {
  const exp = s.expectedJson ? ctx.bundle.expected[s.expectedJson] : undefined;
  const tests = ctx.bundle.negative_tests.filter((t) => s.files.includes(t.input));
  const codes = links.map((l) => l.code);
  const families = new Set(s.files.map((id) => CATEGORY_FAMILY[ctx.docs[id]?.category ?? ""]));
  const rubrics = ctx.bundle.rubrics.filter((r) => families.has(r.family || r.document_type)
    || (r.document_type === "DOCUMENT_SET" && codes.some((c) => COVERAGE_CODES.includes(c))));
  const income = exp?.income_check;
  const { t } = useLang();
  const golden = locList(ctx.bundle.manifest.caseContext, "borrowers");
  return (
    <details className="scn-tech" data-testid={`scn-tech-${s.id}`}>
      <summary>{t("פרטים טכניים · JSON, רובריקות ומקור הקבצים", "Technical details · JSON, rubrics and file sources")}</summary>
      <div className="scn-tech-body">
        <div className="scn-label">{t("קבצים ומקור", "Files and sources")}</div>
        {s.files.map((id) => {
          const d = ctx.docs[id];
          const f = ctx.bundle.files[id];
          if (!d) return null;
          return (
            <div key={id} className="scn-prov">
              <code className="ltr">{d.downloadPath}</code>
              <div>SHA-256 <code className="ltr" title={d.sha256}>{d.sha256.slice(0, 16)}…</code>
                {f?.sha256_matches_manifest ? t(" · תואם למניפסט (נבדק בשרת)", " · matches the manifest (checked on the server)") : t(" · לא תואם למניפסט", " · doesn't match the manifest")}</div>
              <div>{f?.pages ?? "-"} {t("עמ׳", f?.pages === 1 ? "page" : "pages")} · {f?.input_mode === "image_only" ? t("סרוק ללא שכבת טקסט", "scanned, no text layer") : t("PDF דיגיטלי", "digital PDF")}</div>
              {d.expectedRequiredFollowup && <div dir="ltr">Follow-up: {d.expectedRequiredFollowup}</div>}
            </div>
          );
        })}
        {income && (
          <>
            <div className="scn-label">{t("נתוני הכנסה צפויים (נטו חודשי)", "Expected income figures (monthly net)")}</div>
            <table className="t scn-table">
              <thead><tr><th>{t("לווה", "Borrower")}</th><th>{t("מוצהר", "Declared")}</th><th>{t("ממוצע", "Average")}</th><th>{t("פער", "Gap")}</th><th>{t("תוצאה", "Outcome")}</th></tr></thead>
              <tbody>
                {(["IDO", "NOA"] as const).filter((k) => income[k]).map((k) => (
                  <tr key={k}>
                    <td>{golden[k === "IDO" ? 0 : 1]}</td>
                    <td><span className="ltr">{ilsL(income[k].declared)}</span></td>
                    <td><span className="ltr">{ilsL(income[k].document_monthly_avg)}</span></td>
                    <td><span className="ltr">{ilsL(income[k].difference)}</span></td>
                    <td><code className="ltr">{income[k].outcome}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="tiny muted">{t("מדיניות: ", "Policy: ")}<code className="ltr">{income.policy}</code> · {t("סף", "threshold")} <span className="ltr">{ilsL(income.variance_threshold_ils)}</span></div>
          </>
        )}
        {rubrics.length > 0 && (
          <>
            <div className="scn-label">{t("הרובריקות שהמנוע בודק מולן", "The rubrics the engine checks against")}</div>
            {rubrics.map((r) => (
              <div key={r.rubric_id} className="tiny"><code className="ltr">{r.rubric_id}@{r.version}</code> · <span className="ltr">{r.criteria.map((c) => c.id).join(", ")}</span></div>
            ))}
          </>
        )}
        {tests.length > 0 && (
          <>
            <div className="scn-label">{t("בדיקות שליליות", "Negative tests")}</div>
            {tests.map((t) => (
              <div key={t.test_id} className="tiny" dir="ltr"><b>{t.test_id}</b> · {t.condition} · {t.expected_verdict} · {t.safety}</div>
            ))}
          </>
        )}
        <div className="scn-label">Expected JSON · <span className="ltr">{s.expectedJson ?? "golden_set/05_EXPECTED/negative_test_expectations.json"}</span></div>
        <pre className="json">{JSON.stringify(exp ?? { tests }, null, 2)}</pre>
      </div>
    </details>
  );
}

function ConfirmButton({ label, confirmLabel, warning, onConfirm, testId, className }: {
  label: string; confirmLabel: string; warning: string; onConfirm: () => void | Promise<void>; testId: string; className: string;
}) {
  const { t } = useLang();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!asking) return <button type="button" className={className} onClick={() => setAsking(true)} data-testid={testId}>{label}</button>;
  return (
    <div className="scn-confirm" role="group" aria-label={label}>
      <div className="small">{warning}</div>
      <div className="row" style={{ gap: 6 }}>
        <button type="button" className="btn btn-dark scn-btn" disabled={busy} data-testid={`${testId}-confirm`}
          onClick={async () => {
            setBusy(true);
            try { await onConfirm(); } finally { setBusy(false); setAsking(false); }
          }}>
          {busy ? <span className="spinner" /> : null}{confirmLabel}
        </button>
        <button type="button" className="btn btn-ghost scn-btn" onClick={() => setAsking(false)}>{t("ביטול", "Cancel")}</button>
      </div>
    </div>
  );
}
