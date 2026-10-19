import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, timeL, usePolling, type Datum, type DocItem, type IntelSource, type Intelligence, type SourceInput, type Workspace } from "../../api";
import { EvidenceViewer } from "../../components/EvidenceViewer";
import { scenarios as simulate, type Scenario } from "../../finance";
import { enKey, Loc, locList, locOf, Orig, tr, useLang } from "../../i18n";
import { Toast } from "./deskUi";
import "./intelligence.css";

/** Banker Intelligence V2 — a compact, executive-first dashboard for one case: the recommendation, three numbers, the
 *  financing alternatives, then supporting detail on demand. Read-only — every state change happens in the review
 *  workspace (V1), which this view links into. Numbers come from GET /api/banker/cases/{id}/intelligence; the What-if
 *  simulator recomputes locally (finance.ts) and never writes back. Server texts carry English siblings (`*_en`) from
 *  the staff catalogue; the customer drafts stay Hebrew, as the customer receives them. */
export function IntelligenceV2({ caseId, ws, openV1 }: { caseId: string; ws: Workspace; openV1: (item?: string | null) => void }) {
  const { en } = useLang();
  const intel = usePolling<Intelligence>(() => api.bankerIntelligence(caseId), [caseId],
    (x) => x.recommendation.state === "PROCESSING");
  const [stack, setStack] = useState<IntelSource[]>([]);
  const [toast, setToast] = useState<{ text: string; tone: "ok" | "bad" } | null>(null);
  const clearToast = useCallback(() => setToast(null), []);
  useEffect(() => { setStack([]); }, [caseId]);
  const x = intel.data && intel.data.case_id === caseId ? intel.data : null;
  const open = useCallback((s: string | IntelSource | null | undefined) => {
    if (!s || !x) return;
    const src = typeof s === "string" ? x.sources[s] : s;
    if (src) setStack((prev) => [...prev, src]);
  }, [x]);
  if (!x) return <div className="desk-loading">{intel.error
    ? (en ? <>We couldn't load the case snapshot. <button className="link" onClick={intel.reload}>Try again</button></>
      : <>לא הצלחנו לטעון את תמונת המצב. <button className="link" onClick={intel.reload}>ניסיון חוזר</button></>)
    : (en ? <><span className="spinner" /> Jeen is putting together the case snapshot…</> : <><span className="spinner" /> Jeen מרכז את תמונת המצב של התיק…</>)}</div>;
  return (
    <div className="bi-scroll" data-testid="bi-root" data-case={caseId}>
      <Dashboard key={caseId} x={x} open={open} openV1={openV1} onToast={setToast} />
      {stack.length > 0 && <SourceDrawer src={stack[stack.length - 1]} depth={stack.length} ws={ws} x={x} open={open} openV1={openV1}
        onBack={() => setStack((s) => s.slice(0, -1))} onClose={() => setStack([])} />}
      <Toast message={toast} onClose={clearToast} />
    </div>
  );
}

export interface Ctx { x: Intelligence; open: (s: string | IntelSource | null | undefined) => void; openV1: (item?: string | null) => void }
interface Sim { principal: number; term: number; rate: number }

function Dashboard({ x, open, openV1, onToast }: Ctx & { onToast: (t: { text: string; tone: "ok" | "bad" }) => void }) {
  const { t } = useLang();
  const ctx: Ctx = { x, open, openV1 };
  const s = x.simulation;
  const base: Sim = { principal: s.inputs.principal, term: s.inputs.term_months, rate: s.inputs.annual_rate_pct };
  const [sim, setSim] = useState<Sim>(base);
  const changed = sim.principal !== base.principal || sim.term !== base.term || sim.rate !== base.rate;
  const rows: Scenario[] = useMemo(() => s.enabled ? simulate(sim.principal, sim.term, sim.rate, s.income_ils, s.existing_debt_ils, s.asset_price_ils, s.bounds) : [],
    [sim, s]);
  const live = rows.find((r) => r.key === "requested");
  return (
    <div className="bi-page">
      <Header ctx={ctx} />
      <div className="bi-grid">
        <main className="bi-main">
          <Kpis ctx={ctx} live={live} changed={changed} sim={sim} />
          <Simulator ctx={ctx} sim={sim} setSim={setSim} base={base} changed={changed} rows={rows} />
          <Supporting ctx={ctx} />
          <p className="bi-foot">{locOf(x, "disclaimer_he")} · {t("עודכן", "Updated")} <span className="ltr">{timeL(x.generated_at)}</span> · <SourceLegend /></p>
        </main>
        <aside className="bi-aside">
          <Reasons ctx={ctx} />
          <DraftCard ctx={ctx} onToast={onToast} />
        </aside>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- formatting and provenance
const nf0 = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("he-IL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const money = (v?: number | null, exact = false) => (v == null ? "-" : `₪${(exact ? nf2 : nf0).format(v)}`);
export const pct = (v?: number | null) => (v == null ? "-" : `${v.toFixed(1)}%`);
export const fmt = (v: number | string | null | undefined, unit?: string, exact = false) =>
  v == null ? "-" : typeof v === "string" ? v : unit === "pct" ? pct(v) : unit === "months" ? tr(`${v} תשלומים`, `${v} payments`) : money(v, exact);
export const years = (m: number) => tr(m % 12 === 0 ? `${m / 12} שנים` : `${(m / 12).toFixed(1)} שנים`,
  m === 12 ? "1 year" : m % 12 === 0 ? `${m / 12} years` : `${(m / 12).toFixed(1)} years`);

/** a server field's English sibling, for <Loc en=…> (undefined when the catalogue has none) */
export const enOf = (o: any, key: string): string | undefined => o?.[enKey(key)] ?? undefined;
/** The applicant(s) as one line: the company, or the borrowers' names joined */
export const applicantName = (x: Intelligence) => (x.applicant.company?.name_he && locOf(x.applicant.company, "name_he"))
  || x.applicant.borrowers.map((b) => locOf(b, "name_he")).join(tr(" ו", " and "));
/** English for "הלוואה ל<purpose>": a short loan name per known purpose; otherwise the purpose itself */
const LOAN_EN: Record<string, string> = { "רכישת רכב": "Car loan", "שיפוץ": "Renovation loan", "אירוע משפחתי": "Family celebration loan",
  "מטרה אחרת": "Loan for another purpose", "מימון ציוד לעסק": "Business equipment financing", "הון חוזר לעסק": "Working capital financing" };
export const loanNameEn = (x: Intelligence) => x.loan.purpose_he
  ? LOAN_EN[x.loan.purpose_he] || `Loan: ${locOf(x.loan, "purpose_he")}` : locOf(x.case, "title_he");

export type MarkKind = "verified" | "reviewed" | "unverified" | "declared" | "demo" | "calc" | "assume" | "missing" | "sim";
/** Small provenance icons: the distinction stays (document · declared · calculated · bank context · assumption · simulation ·
 *  missing), the noise goes. The full explanation is one click away in the source drawer. */
const MARK_HE: Record<MarkKind, { icon: string; label: string; title: string }> = {
  verified: { icon: "✓", label: "מסמך", title: "חולץ ממסמך ואומת מול הקובץ" },
  reviewed: { icon: "✓", label: "נבדק", title: "חולץ ממסמך, אומת מול הקובץ, והמסמך התקבל על ידי הבנקאי" },
  unverified: { icon: "!", label: "מסמך · לא אומת", title: "חולץ ממסמך, לא אומת מול הקובץ" },
  declared: { icon: "✎", label: "מוצהר", title: "הצהרת הלקוח בבקשה, לא מאומת" },
  demo: { icon: "בנק", label: "נתוני בנק", title: "נתון מההקשר הבנקאי של התיק, לא אומת מול מערכות הבנק" },
  calc: { icon: "ƒ", label: "חישוב", title: "חושב בקוד מנתונים אחרים, לחצו לנוסחה ולקלטים" },
  assume: { icon: "≈", label: "הנחה", title: "הנחה לצורך החישוב, אינה מדיניות או ריבית של הבנק" },
  missing: { icon: "?", label: "חסר", title: "הנתון אינו זמין" },
  sim: { icon: "◇", label: "סימולציה", title: "ערך סימולציה, לא נשמר ואינו משנה את הבקשה" },
};
const MARK_EN: Record<MarkKind, { icon?: string; label: string; title: string }> = {
  verified: { label: "Document", title: "Extracted from a document and verified against the file" },
  reviewed: { label: "Reviewed", title: "Extracted from a document, verified against the file, and the document was accepted by the banker" },
  unverified: { label: "Document · not verified", title: "Extracted from a document, not verified against the file" },
  declared: { label: "Declared", title: "The customer's declaration in the application, not verified" },
  demo: { icon: "Bank", label: "Bank data", title: "A figure from the case's bank context, not verified against the bank's systems" },
  calc: { label: "Calculation", title: "Calculated in code from other figures; click for the formula and inputs" },
  assume: { label: "Assumption", title: "An assumption for the calculation; not the bank's policy or rate" },
  missing: { label: "Missing", title: "The figure isn't available" },
  sim: { label: "Simulation", title: "A simulation value; not saved and doesn't change the application" },
};
/** each entry reads in the platform's language when it renders */
export const MARK = Object.fromEntries((Object.keys(MARK_HE) as MarkKind[]).map((k) => [k, {
  get icon() { return tr(MARK_HE[k].icon, MARK_EN[k].icon ?? MARK_HE[k].icon); },
  get label() { return tr(MARK_HE[k].label, MARK_EN[k].label); },
  get title() { return tr(MARK_HE[k].title, MARK_EN[k].title); },
}])) as Record<MarkKind, { icon: string; label: string; title: string }>;
export function markOf(s?: IntelSource | null): MarkKind {
  if (!s) return "missing";
  if (s.kind === "document") return s.banker_reviewed ? "reviewed" : s.verified ? "verified" : "unverified";
  return ({ declared: "declared", synthetic_bank: "demo", calculated: "calc", assumption: "assume", missing: "missing" } as Record<string, MarkKind>)[s.kind] || "missing";
}
export function Mark({ kind }: { kind: MarkKind }) {
  useLang();
  return <span className={`bi-ic m-${kind}`} title={MARK[kind].title} aria-label={MARK[kind].label} role="img" data-testid="bi-mark" data-mark={kind}>{MARK[kind].icon}</span>;
}
function SourceLegend() {
  useLang();
  return <span className="bi-legend" data-testid="bi-legend">{(["verified", "declared", "calc", "demo", "assume"] as MarkKind[]).map((k) =>
    <span key={k}><Mark kind={k} /> {MARK[k].label}</span>)}</span>;
}

/** A number and where it came from. Click opens the source drawer; a value without a source says so. */
function Val({ ctx, d, big, exact, testId }: { ctx: Ctx; d?: Datum | null; big?: boolean; exact?: boolean; testId?: string }) {
  const { t } = useLang();
  const src = d?.source_id ? ctx.x.sources[d.source_id] : null;
  if (!d || d.value == null) return <span className={`bi-val none${big ? " big" : ""}`} data-testid={testId}><span className="bi-num">{t("לא זמין", "Not available")}</span><Mark kind="missing" /></span>;
  return (
    <button className={`bi-val${big ? " big" : ""}`} onClick={() => ctx.open(src)} disabled={!src} data-testid={testId || "bi-datum"}
      data-source={d.source_id || ""} data-kind={src?.kind || "none"} title={src ? t(`מקור: ${src.label_he}`, `Source: ${locOf(src, "label_he")}`) : undefined}>
      <span className="bi-num ltr">{fmt(d.value, d.unit, exact)}</span>{src && <Mark kind={markOf(src)} />}
    </button>
  );
}
function SrcLink({ ctx, id, children }: { ctx: Ctx; id: string | null | undefined; children?: ReactNode }) {
  useLang();
  const s = id ? ctx.x.sources[id] : null;
  if (!s) return null;
  return <button className="bi-srclink" onClick={() => ctx.open(s)} data-testid="bi-srclink" data-kind={s.kind}>{children ?? <Loc he={s.label_he} en={s.label_en} />}<Mark kind={markOf(s)} /></button>;
}

// ---------------------------------------------------------------- header: who, what, the recommendation, one action
const TITLE: Record<string, string> = {
  READY_FOR_CREDIT_REVIEW: "מומלץ להתקדם לבחינת האשראי", PREPARATION_CONFIRMED: "הכנת התיק אושרה, אפשר להתקדם לבחינת האשראי",
  CLARIFICATION_REQUIRED: "נדרש בירור לפני המשך הטיפול", DOCUMENTS_INCOMPLETE: "נדרשת השלמת מסמכים", NO_DOCUMENTS: "ממתינים למסמכים מהלקוח",
  PROCESSING: "Jeen בודק את המסמכים", ERROR: "תקלה בבדיקת המסמכים",
};
const TITLE_EN: Record<string, string> = {
  READY_FOR_CREDIT_REVIEW: "Recommended: proceed to credit review", PREPARATION_CONFIRMED: "Case preparation confirmed; you can proceed to credit review",
  CLARIFICATION_REQUIRED: "Clarification needed before handling continues", DOCUMENTS_INCOMPLETE: "Documents need completing",
  NO_DOCUMENTS: "Waiting for documents from the customer", PROCESSING: "Jeen is checking the documents", ERROR: "The document check failed",
};
const TONE: Record<string, string> = { READY_FOR_CREDIT_REVIEW: "ok", PREPARATION_CONFIRMED: "ok", CLARIFICATION_REQUIRED: "warn",
  DOCUMENTS_INCOMPLETE: "warn", NO_DOCUMENTS: "neutral", PROCESSING: "neutral", ERROR: "bad" };

/** One sentence for a case that is ready: built from the briefing's own numbers. Other states use the briefing's headline. */
function explanation(x: Intelligence): string {
  const r = x.recommendation;
  if (r.state === "DOCUMENTS_INCOMPLETE") {
    const n = x.documents.missing.length + x.documents.corrections.length;
    return tr(`${n === 1 ? "פריט אחד חסר" : `${n} פריטים חסרים`} בתיק (מפורטים למטה). עד להשלמתם לא ניתן לגבש תמונה פיננסית מספקת, והחלופות מוצגות להמחשה בלבד.`,
      `${n === 1 ? "One item is" : `${n} items are`} missing from the case (listed below). Until they arrive, a sufficient financial picture can't be formed, and the alternatives are illustrative only.`);
  }
  if (!["READY_FOR_CREDIT_REVIEW", "PREPARATION_CONFIRMED"].includes(r.state)) return locOf(r, "headline_he");
  if (x.analysis.availability === "unavailable") return tr(`המסמכים הושלמו. ${x.analysis.reasons_he[0] || ""}`, `Documents complete. ${locList(x.analysis, "reasons_he")[0] || ""}`).trim();
  const verified = x.income.borrowers.every((b) => b.quality === "verified" || b.chosen.value == null);
  const parts = tr([r.state === "PREPARATION_CONFIRMED" ? "הכנת התיק אושרה" : "המסמכים הושלמו",
    `${verified ? "ההכנסה הממוצעת המאומתת היא" : "ההכנסה לחישוב (חלקה מוצהרת) היא"} ${money(x.analysis.income.value)}`],
  [r.state === "PREPARATION_CONFIRMED" ? "Case preparation confirmed" : "Documents complete",
    `${verified ? "the verified average income is" : "the income used (partly declared) is"} ${money(x.analysis.income.value)}`]);
  if (x.analysis.combined_dsr?.value != null) parts.push(tr(`יחס ההחזר המשולב בסימולציה הוא ${pct(x.analysis.combined_dsr.value)}`,
    `the simulated combined DSR is ${pct(x.analysis.combined_dsr.value)}`));
  const last = parts.pop();
  const verify = x.bank_context.available ? tr("נדרש אימות נתוני הבנק לפני החלטה.", "The bank data must be verified before a decision.")
    : tr("אין נתוני התחייבויות קיימות, נדרש אימות לפני החלטה.", "There is no data on existing obligations; verification is needed before a decision.");
  return tr(`${parts.join(", ")} ו${last}. ${verify}`, `${parts.join(", ")} and ${last}. ${verify}`);
}

function docStatus(x: Intelligence): { primary: string; tone: string; banker: string | null } {
  const d = x.documents;
  const pending = d.missing.length + d.corrections.length;
  if (x.recommendation.state === "PROCESSING") return { primary: tr("המסמכים בבדיקת Jeen", "Documents being checked by Jeen"), tone: "neutral", banker: null };
  if (!d.total && pending) return { primary: tr("טרם הועלו מסמכים", "No documents uploaded yet"), tone: "neutral", banker: null };
  if (pending) return { primary: tr(pending === 1 ? "חסר פריט אחד" : `חסרים ${pending} פריטים`, pending === 1 ? "One item missing" : `${pending} items missing`), tone: "warn", banker: null };
  const banker = x.recommendation.state === "PREPARATION_CONFIRMED" ? tr("הכנת התיק אושרה על ידך", "You confirmed the case preparation")
    : d.open_findings ? tr(d.open_findings === 1 ? "ממצא אחד לבירור בנקאי" : `${d.open_findings} ממצאים לבירור בנקאי`,
      d.open_findings === 1 ? "One finding for banker clarification" : `${d.open_findings} findings for banker clarification`)
      : d.awaiting_decision ? tr("ממתין לבדיקת בנקאי", "Awaiting the banker's review") : tr("המסמכים התקבלו על ידך", "You accepted the documents");
  return { primary: tr("מסמכים הושלמו", "Documents complete"), tone: "ok", banker };
}

function Header({ ctx }: { ctx: Ctx }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const r = x.recommendation;
  const ds = docStatus(x);
  const who = applicantName(x);
  const blockers = [
    ...x.discrepancies.filter((d) => d.open).map((d) => ({ key: d.v1_item + d.kind, text: d.kind === "income"
      ? t(`פער הכנסה פתוח: מוצהר ${money(d.declared.value)} · בתלושים ${money(d.documented.value)}`,
        `Open income gap: declared ${money(d.declared.value)} · payslips ${money(d.documented.value)}`)
      : t(`הסכום המבוקש (${money(d.declared.value)}) גבוה מהצעת המחיר (${money(d.documented.value)})`,
        `The requested amount (${money(d.declared.value)}) is higher than the price quote (${money(d.documented.value)})`), item: d.v1_item })),
    ...x.documents.missing.slice(0, 4).map((m) => ({ key: m.v1_item, text: t(`חסר: ${m.title_he}`, `Missing: ${locOf(m, "title_he")}`), item: m.v1_item })),
    ...x.documents.corrections.map((c) => ({ key: c.v1_item, text: t(`לתיקון: ${c.title_he}`, `To correct: ${locOf(c, "title_he")}`), item: c.v1_item })),
  ];
  const more = x.documents.missing.length - 4;
  return (
    <section className={`bi-head t-${TONE[r.state] || "neutral"}`} data-testid="bi-brief" data-state={r.state}>
      <div className="bi-head-ctx" data-testid="bi-context">
        <span className="bi-who">{who}</span>
        <span className="bi-what">{en ? loanNameEn(x) : x.loan.purpose_he ? `הלוואה ל${x.loan.purpose_he.replace(/^רכישת /, "")}` : x.case.title_he}</span>
        <span className="bi-sep" aria-hidden>·</span>
        <span className="ltr bi-amt">{money(x.loan.amount.value)}</span><span className="bi-sep" aria-hidden>·</span>
        <span>{t(`${x.loan.term.value} תשלומים`, `${x.loan.term.value} payments`)}</span>
        {x.applicant.profile_label_he && <><span className="bi-sep" aria-hidden>·</span><span className="muted"><Loc he={x.applicant.profile_label_he} en={enOf(x.applicant, "profile_label_he")} /></span></>}
        <span className="bi-case muted">{t("תיק", "Case")} <span className="ltr">{x.case.display_number}</span></span>
      </div>
      <div className="bi-head-body">
        <div className="bi-rec">
          <h1 className="bi-rec-title" data-testid="bi-headline"><span className="bi-dot" aria-hidden />{t(TITLE[r.state], TITLE_EN[r.state]) || locOf(r.documentation, "status_he")}</h1>
          <p className="bi-rec-text" data-testid="bi-rec-text">{explanation(x)}</p>
          {blockers.length > 0 && <ul className="bi-blockers" data-testid="bi-blockers">
            {blockers.map((b) => <li key={b.key}><button onClick={() => ctx.openV1(b.item)}>{b.text}</button></li>)}
            {more > 0 && <li className="muted">{t(`ועוד ${more}`, `and ${more} more`)}</li>}
          </ul>}
        </div>
        <div className="bi-act">
          <button className="bi-primary" onClick={() => ctx.openV1(r.next_action.v1_item)} disabled={r.next_action.kind === "wait"}
            data-testid="bi-next-btn">{locOf(r.next_action, "label_he")}<span aria-hidden>{t("←", "→")}</span></button>
          {r.next_action.detail_he && <div className="bi-act-detail">{locOf(r.next_action, "detail_he")}</div>}
          <div className="bi-status" data-testid="bi-doc-status">
            <span className={`bi-pill p-${ds.tone}`} data-testid="bi-doc-primary">{ds.primary}</span>
            {ds.banker && <span className="bi-pill p-line" data-testid="bi-doc-banker">{ds.banker}</span>}
          </div>
          <div className="bi-disclaimer">{t("המלצת המשך בלבד · לא אישור אשראי", "A next-step recommendation only · not a credit approval")}</div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- the three numbers
function Kpis({ ctx, live, changed, sim }: { ctx: Ctx; live?: Scenario; changed: boolean; sim: Sim }) {
  const { t } = useLang();
  const { x } = ctx;
  const a = x.analysis;
  const thr = x.simulation.threshold_pct;
  const income = x.income.borrowers;
  const incomeNote = a.availability === "provisional" ? t("הנמוך מבין מוצהר למתועד, עד לבירור", "The lower of declared and documented, pending clarification")
    : income.some((b) => b.quality === "declared") ? t("מוצהר, טרם אומת במסמכים", "Declared, not yet verified by documents")
      : income.some((b) => b.quality === "partial") ? t("חלק מהחודשים", "Some of the months") : income.length > 1 ? t("סך הלווים", "All borrowers combined") : t("ממוצע תלושים מאומתים", "Average of verified payslips");
  const paySrc: IntelSource | null = !live ? null : !changed && a.proposed_payment?.source_id ? x.sources[a.proposed_payment.source_id] : {
    id: "sim:kpi:pay", kind: "calculated", label_he: `החזר חודשי בסימולציה, ${live.term_months} תשלומים`, label_en: `Simulated monthly payment, ${live.term_months} payments`,
    value: live.monthly_payment_ils, unit: "ils",
    formula_he: "P·r ÷ (1 − (1 + r)^−n), r = ריבית שנתית ÷ 12", formula_en: "P·r ÷ (1 − (1 + r)^−n), r = annual rate ÷ 12",
    inputs: [{ label_he: "קרן (P)", label_en: "Principal (P)", value: sim.principal, unit: "ils", source_id: null, origin: "sim" },
      { label_he: "תשלומים (n)", label_en: "Payments (n)", value: sim.term, unit: "months", source_id: null, origin: "sim" },
      { label_he: "ריבית שנתית", label_en: "Annual interest rate", value: sim.rate, unit: "pct", source_id: null, origin: "sim" }],
    note_he: "ערכי סימולציה, לא נשמרים.", note_en: "Simulation values, not saved." };
  const dsrSrc: IntelSource | null = !live || live.combined_dsr_pct == null ? null : !changed && a.combined_dsr?.source_id ? x.sources[a.combined_dsr.source_id] : {
    id: "sim:kpi:dsr", kind: "calculated", label_he: "יחס החזר משולב בסימולציה", label_en: "Simulated combined DSR", value: live.combined_dsr_pct, unit: "pct",
    formula_he: "(החזר משוער + החזרים קיימים) ÷ הכנסה נטו × 100", formula_en: "(estimated payment + existing payments) ÷ net income × 100",
    inputs: [{ label_he: "החזר משוער", label_en: "Estimated payment", value: live.monthly_payment_ils, unit: "ils", source_id: null, origin: "calc" },
      { label_he: "החזרים קיימים", label_en: "Existing payments", value: x.simulation.existing_debt_ils, unit: "ils", source_id: x.simulation.existing_source_id },
      { label_he: "הכנסה נטו", label_en: "Net income", value: x.simulation.income_ils, unit: "ils", source_id: x.simulation.income_source_id }] };
  const over = live?.combined_dsr_pct != null && live.combined_dsr_pct > thr;
  return (
    <div className="bi-kpis" data-testid="bi-kpis">
      <div className="bi-kpi" data-testid="bi-kpi-income">
        <div className="bi-kpi-k">{t("הכנסה חודשית נטו ממוצעת", "Average net monthly income")}</div>
        <Val ctx={ctx} d={a.income} big />
        <div className="bi-kpi-n">{incomeNote}</div>
      </div>
      <div className="bi-kpi" data-testid="bi-kpi-payment">
        <div className="bi-kpi-k">{t("החזר חודשי חדש בסימולציה", "New monthly payment (simulated)")}</div>
        {live && paySrc ? <button className="bi-val big" onClick={() => ctx.open(paySrc)} data-testid="bi-kpi-payment-value" data-value={live.monthly_payment_ils}>
          <span className="bi-num ltr">{money(live.monthly_payment_ils)}</span><Mark kind={changed ? "sim" : "calc"} /></button> : <Val ctx={ctx} d={null} big />}
        <div className="bi-kpi-n">{live ? t(`${money(live.principal_ils)} · ${live.term_months} תשלומים · ${pct(live.annual_rate_pct)}`,
          `${money(live.principal_ils)} · ${live.term_months} payments · ${pct(live.annual_rate_pct)}`) : "-"}</div>
      </div>
      <div className={`bi-kpi${live?.combined_dsr_pct != null ? (over ? " k-warn" : " k-ok") : ""}`} data-testid="bi-kpi-combined">
        <div className="bi-kpi-k">{t("יחס החזר כולל בסימולציה", "Total DSR (simulated)")}</div>
        {live && dsrSrc ? <button className="bi-val big" onClick={() => ctx.open(dsrSrc)} data-testid="bi-kpi-combined-value" data-value={live.combined_dsr_pct ?? ""}>
          <span className="bi-num ltr">{pct(live.combined_dsr_pct)}</span><Mark kind={changed ? "sim" : "calc"} /></button> : <Val ctx={ctx} d={null} big />}
        <div className="bi-kpi-n">{live?.combined_dsr_pct == null ? t("אין הכנסה לחישוב", "No income to calculate with")
          : t(`${live.combined_includes_existing ? "כולל התחייבויות קיימות" : "ללא התחייבויות קיימות (אין נתונים)"} · סף להמחשה ${thr}%`,
            `${live.combined_includes_existing ? "Includes existing obligations" : "Excludes existing obligations (no data)"} · illustrative threshold ${thr}%`)}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- financing alternatives and What-if
export const SC_LABEL: Record<string, string> = { short: "תקופה קצרה", requested: "לפי הבקשה", long: "תקופה ארוכה" };
const SC_LABEL_EN: Record<string, string> = { short: "Shorter term", requested: "As requested", long: "Longer term" };
export const scLabel = (key: string) => tr(SC_LABEL[key], SC_LABEL_EN[key]);

/** The calculation behind one scenario figure, as a source the drawer opens: formula, inputs and where each input came from. */
export function scenarioSource(s: Intelligence["simulation"], r: Scenario, what: "pay" | "dsr" | "total",
  principal: number, term: number, rate: number): IntelSource {
  const base = s.inputs;
  const inP: SourceInput = { label_he: "קרן (P)", label_en: "Principal (P)", value: principal, unit: "ils", source_id: principal === base.principal ? "app:amount" : null, origin: "sim" };
  const inN: SourceInput = { label_he: "תשלומים (n)", label_en: "Payments (n)", value: r.term_months, unit: "months", source_id: r.term_months === base.term_months ? "app:term" : null,
    origin: r.term_months === term ? "sim" : "calc" };
  const inR: SourceInput = { label_he: "ריבית שנתית", label_en: "Annual interest rate", value: rate, unit: "pct", source_id: rate === base.annual_rate_pct ? s.rate_source_id : null, origin: "sim" };
  const pay: SourceInput = { label_he: "החזר חודשי", label_en: "Monthly payment", value: r.monthly_payment_ils, unit: "ils", source_id: null, origin: "calc" };
  if (what === "pay") return { id: `sim:pay:${r.key}`, kind: "calculated", label_he: `החזר חודשי, ${r.term_months} תשלומים`,
    label_en: `Monthly payment, ${r.term_months} payments`, value: r.monthly_payment_ils,
    unit: "ils", formula_he: "P·r ÷ (1 − (1 + r)^−n), r = ריבית שנתית ÷ 12", formula_en: "P·r ÷ (1 − (1 + r)^−n), r = annual rate ÷ 12", inputs: [inP, inN, inR],
    note_he: "חושב בדפדפן באותה נוסחה ובאותו עיגול כמו בשרת. ערכי סימולציה אינם נשמרים.",
    note_en: "Calculated in the browser with the same formula and rounding as the server. Simulation values are not saved." };
  if (what === "total") return { id: `sim:total:${r.key}`, kind: "calculated", label_he: `עלות המימון, ${r.term_months} תשלומים`,
    label_en: `Financing cost, ${r.term_months} payments`, value: r.total_interest_ils,
    unit: "ils", formula_he: "החזר חודשי × n − P", formula_en: "Monthly payment × n − P", inputs: [pay, inN, inP],
    note_he: "מחושב מההחזר הלא מעוגל, התשלום האחרון סופג את עיגול האגורות. בריבית 0% עלות המימון היא 0.",
    note_en: "Computed from the unrounded payment; the last payment absorbs the agora rounding. At 0% interest the financing cost is 0." };
  return { id: `sim:dsr:${r.key}`, kind: "calculated", label_he: `יחס החזר משולב, ${r.term_months} תשלומים`,
    label_en: `Combined DSR, ${r.term_months} payments`, value: r.combined_dsr_pct, unit: "pct",
    formula_he: "(החזר משוער + החזרים קיימים) ÷ הכנסה נטו × 100", formula_en: "(estimated payment + existing payments) ÷ net income × 100",
    inputs: [pay,
      { label_he: "החזרים קיימים", label_en: "Existing payments", value: s.existing_debt_ils, unit: "ils", source_id: s.existing_source_id },
      { label_he: "הכנסה נטו", label_en: "Net income", value: s.income_ils, unit: "ils", source_id: s.income_source_id }],
    note_he: r.combined_includes_existing ? null : "אין נתוני התחייבויות קיימות, היחס כולל רק את ההלוואה המבוקשת.",
    note_en: r.combined_includes_existing ? null : "There is no data on existing obligations; the ratio includes only the requested loan." };
}

function Simulator({ ctx, sim, setSim, base, changed, rows }: { ctx: Ctx; sim: Sim; setSim: (s: Sim) => void; base: Sim; changed: boolean; rows: Scenario[] }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const s = x.simulation;
  const thr = s.threshold_pct;
  if (!s.enabled) return <section className="bi-sec" data-testid="bi-simulator"><h2>{t("חלופות מימון", "Financing alternatives")}</h2>
    <div className="bi-empty">{t("אין בבקשה סכום ומספר תשלומים לחישוב.", "The application has no amount and number of payments to calculate with.")}</div></section>;
  const short = rows[0], long = rows[rows.length - 1];
  const calcSource = (r: Scenario, what: "pay" | "dsr" | "total") => scenarioSource(s, r, what, sim.principal, sim.term, sim.rate);
  const caution = x.analysis.availability === "unavailable" ? t("ניתוח יחסי ההחזר אינו זמין לתיק זה, מוצגים החזרים ועלויות בלבד.",
    "Repayment-ratio analysis isn't available for this case; only payments and costs are shown.")
    : x.analysis.availability === "provisional" ? t("להמחשה בלבד, הניתוח זמני עד לבירור הפער בהכנסה.", "Illustrative only; the analysis is provisional until the income gap is clarified.")
      : x.analysis.availability === "partial" ? t(`להמחשה בלבד, ${x.analysis.reasons_he[0] || "הניתוח חלקי."}`,
        `Illustrative only. ${locList(x.analysis, "reasons_he")[0] || "The analysis is partial."}`) : null;
  return (
    <section className="bi-sec bi-simsec" data-testid="bi-simulator">
      <header className="bi-sec-head">
        <div><h2>{t("חלופות מימון", "Financing alternatives")}</h2><p className="bi-sub">{t("שלוש חלופות מחושבות על בסיס הנתונים בתיק. ניתן להשוות החזר חודשי ועלות כוללת.",
          "Three alternatives calculated from the case data. Compare the monthly payment and the total cost.")}</p></div>
        <button className="bi-ghost" onClick={() => setSim(base)} disabled={!changed} data-testid="bi-wi-reset">{t("חזרה לנתוני הבקשה", "Back to the application's figures")}</button>
      </header>
      {caution && <div className="bi-caution" data-testid="bi-sim-provisional">{caution}</div>}
      <div className="bi-scenarios">
        {rows.map((r) => {
          const suggested = !changed && s.suggested?.key === r.key;
          const over = r.combined_dsr_pct != null && r.combined_dsr_pct > thr;
          return (
            <article key={r.key} className={`bi-sc${r.key === "requested" ? " mid" : ""}${suggested ? " suggested" : ""}`} data-testid="bi-scenario"
              data-key={r.key} data-term={r.term_months}>
              <header>
                <span className="bi-sc-k">{r.key === "requested" && changed ? t("התקופה שנבחרה", "Selected term") : scLabel(r.key)}</span>
                {r.key === "requested" && !changed && <span className="bi-tag">{t("בקשת הלקוח", "Customer's request")}</span>}
                {suggested && <span className="bi-tag ok" title={locOf(s.suggested, "label_he")}>{t("חלופה להמחשה", "Illustrative alternative")}</span>}
              </header>
              <div className="bi-sc-meta"><span className="ltr">{money(r.principal_ils)}</span> · <b className="ltr">{r.term_months}</b> {t("תשלומים", "payments")} ({years(r.term_months)})</div>
              <button className="bi-sc-pay" onClick={() => ctx.open(calcSource(r, "pay"))} data-testid="bi-sc-pay" data-value={r.monthly_payment_ils}>
                <span className="ltr">{money(r.monthly_payment_ils)}</span><small>{t("לחודש", "/month")}</small><Mark kind={changed ? "sim" : "calc"} /></button>
              <dl>
                <div><dt>{t("סך ההחזר", "Total repaid")}</dt><dd className="ltr" data-testid="bi-sc-total">{money(r.total_payments_ils)}</dd></div>
                <div><dt>{t("עלות המימון", "Financing cost")}</dt><dd><button className="bi-val" onClick={() => ctx.open(calcSource(r, "total"))} data-testid="bi-sc-interest" data-value={r.total_interest_ils}>
                  <span className="bi-num ltr">{money(r.total_interest_ils)}</span></button></dd></div>
              </dl>
              <button className={`bi-dsr${over ? " over" : ""}`} onClick={() => ctx.open(calcSource(r, "dsr"))} data-testid="bi-sc-dsr" data-value={r.combined_dsr_pct ?? ""}
                disabled={r.combined_dsr_pct == null}>
                <span className="bi-dsr-k">{t("יחס החזר כולל", "Total DSR")}</span><span className="bi-dsr-v ltr">{pct(r.combined_dsr_pct)}</span>
                {r.combined_dsr_pct != null && <span className="bi-dsr-track"><span className="fill" style={{ width: `${Math.min(100, r.combined_dsr_pct / 60 * 100)}%` }} />
                  <span className="thr" style={{ insetInlineStart: `${thr / 60 * 100}%` }} title={t(`סף להמחשה: ${thr}%`, `Illustrative threshold: ${thr}%`)} /></span>}
              </button>
            </article>
          );
        })}
      </div>
      {rows.length > 1 && (en ? <p className="bi-compare" data-testid="bi-compare">
        Spread over <b className="ltr">{long.term_months}</b> payments, the monthly payment is <b className="ltr">{money(short.monthly_payment_ils - long.monthly_payment_ils)}</b> lower
        than over <b className="ltr">{short.term_months}</b>, but the financing cost is <b className="ltr">{money(long.total_interest_ils - short.total_interest_ils)}</b> higher.</p>
        : <p className="bi-compare" data-testid="bi-compare">
        בפריסה ל־<b className="ltr">{long.term_months}</b> תשלומים ההחזר החודשי נמוך ב־<b className="ltr">{money(short.monthly_payment_ils - long.monthly_payment_ils)}</b> מאשר
        ב־<b className="ltr">{short.term_months}</b>, אך עלות המימון גבוהה ב־<b className="ltr">{money(long.total_interest_ils - short.total_interest_ils)}</b>.</p>)}
      <div className="bi-whatif" data-testid="bi-whatif">
        <span className="bi-whatif-k">{t("קלטי סימולציה", "Simulation inputs")}<small>{t("לא נשמרים בבקשה", "Not saved to the application")}</small></span>
        <Slider label={t("סכום", "Amount")} value={sim.principal} min={10000} max={s.bounds.principal_max} step={1000} onChange={(v) => setSim({ ...sim, principal: v })}
          display={money(sim.principal)} testId="bi-wi-principal" changed={sim.principal !== base.principal} />
        <Slider label={t("תשלומים", "Payments")} value={sim.term} min={s.bounds.term_min} max={s.bounds.term_max} step={6} onChange={(v) => setSim({ ...sim, term: v })}
          display={`${sim.term} · ${years(sim.term)}`} testId="bi-wi-term" changed={sim.term !== base.term} />
        <Slider label={t("ריבית להמחשה", "Illustrative rate")} value={sim.rate} min={0} max={15} step={0.1} onChange={(v) => setSim({ ...sim, rate: Math.round(v * 10) / 10 })}
          display={`${sim.rate.toFixed(1)}%`} testId="bi-wi-rate" changed={sim.rate !== base.rate}
          hint={<SrcLink ctx={ctx} id={s.rate_source_id}>{t(`ברירת מחדל ${base.rate.toFixed(1)}%`, `Default ${base.rate.toFixed(1)}%`)}</SrcLink>} />
      </div>
    </section>
  );
}

export function Slider({ label, value, min, max, step, onChange, display, testId, changed, hint }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; display: string; testId: string; changed: boolean; hint?: ReactNode }) {
  return (
    <label className={`bi-slider${changed ? " changed" : ""}`}>
      <span className="bi-slider-k">{label}{changed && <Mark kind="sim" />}</span>
      <span className="bi-slider-v ltr" data-testid={`${testId}-value`}>{display}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} data-testid={testId} aria-label={label} />
      {hint && <span className="bi-slider-h">{hint}</span>}
    </label>
  );
}

// ---------------------------------------------------------------- why: three reasons, the rest on demand
const TONE_RANK: Record<string, number> = { warn: 0, ok: 1, info: 2 };

function Reasons({ ctx }: { ctx: Ctx }) {
  const { t } = useLang();
  const { x } = ctx;
  const r = x.recommendation;
  const [all, setAll] = useState(false);
  const d = x.documents;
  const pending = d.missing.length + d.corrections.length;
  const progress = d.progress ? `${d.progress.done}/${d.progress.total}` : d.total;
  const docLine = { text_he: pending ? `חסרים ${pending} פריטים בתיק, ראו בראש המסך.`
    : d.open_findings ? `המסמכים הושלמו; ${d.open_findings === 1 ? "ממצא אחד ממתין" : `${d.open_findings} ממצאים ממתינים`} לבירור שלך.`
      : d.total ? `המסמכים הנדרשים הושלמו (${progress}).` : "טרם הועלו מסמכים.",
    text_en: pending ? `${pending === 1 ? "One item is" : `${pending} items are`} missing from the case; see the top of the screen.`
      : d.open_findings ? `Documents complete; ${d.open_findings === 1 ? "one finding awaits" : `${d.open_findings} findings await`} your clarification.`
        : d.total ? `The required documents are complete (${progress}).` : "No documents uploaded yet.",
    tone: pending || d.open_findings ? "warn" : d.total ? "ok" : "info", source_ids: [] as string[] };
  const ranked = [docLine, ...[...r.considerations].sort((a, b) => (TONE_RANK[a.tone] ?? 3) - (TONE_RANK[b.tone] ?? 3))];
  const shown = all ? ranked : ranked.slice(0, 3);
  return (
    <section className="bi-card bi-why" data-testid="bi-considerations">
      <h2>{t("למה זו ההמלצה", "Why this recommendation")}</h2>
      <ul className="bi-cons">
        {shown.map((c, i) => (
          <li key={i} className={`c-${c.tone}`} data-testid="bi-consideration">
            <span><Loc he={c.text_he} en={(c as { text_en?: string }).text_en} /></span>
            {all && c.source_ids.filter((id) => x.sources[id]).length > 0 && <span className="bi-cons-src">
              {c.source_ids.filter((id) => x.sources[id]).map((id) => <button key={id} className="bi-chipsrc" onClick={() => ctx.open(id)} title={locOf(x.sources[id], "label_he")}><Mark kind={markOf(x.sources[id])} /></button>)}</span>}
          </li>
        ))}
      </ul>
      {all && <div className="bi-verify" data-testid="bi-verify">
        <div className="bi-verify-k">{t("לאמת לפני החלטה", "Verify before a decision")}</div>
        <ul>{r.verify.map((v, i) => <li key={i}>{v.v1_item ? <button className="bi-link" onClick={() => ctx.openV1(v.v1_item)}>{locOf(v, "text_he")}</button> : <Loc he={v.text_he} en={(v as { text_en?: string }).text_en} />}</li>)}</ul>
        <div className="bi-fin-note"><Loc he={r.financial.text_he} en={enOf(r.financial, "text_he")} /></div>
      </div>}
      <button className="bi-more" onClick={() => setAll(!all)} aria-expanded={all} data-testid="bi-why-toggle">
        {all ? t("פחות", "Less") : t(`הצג את כל הנימוקים (${ranked.length}) ומה לאמת`, `Show all reasons (${ranked.length}) and what to verify`)}</button>
    </section>
  );
}

// ---------------------------------------------------------------- supporting detail, collapsed by default
function Panel({ title, summary, children, testId, defaultOpen = false, demo }: { title: string; summary?: ReactNode; children: ReactNode; testId: string;
  defaultOpen?: boolean; demo?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={`bi-panel${open ? " open" : ""}`} data-testid={testId}>
      <button className="bi-panel-head" onClick={() => setOpen(!open)} aria-expanded={open} data-testid={`${testId}-toggle`}>
        <span className="bi-panel-t">{title}{demo && <Mark kind="demo" />}</span>
        {summary && <span className="bi-panel-s">{summary}</span>}
        <span className="bi-chev" aria-hidden>▾</span>
      </button>
      {open && <div className="bi-panel-body">{children}</div>}
    </section>
  );
}

function Supporting({ ctx }: { ctx: Ctx }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const a = x.analysis;
  const bc = x.bank_context;
  const d = x.documents;
  const [slips, setSlips] = useState(false);
  const openItems = x.discrepancies.filter((g) => g.open).length + x.risks.length;
  const docSources = Object.values(x.sources).filter((s) => s.kind === "document");
  const inc = x.income.borrowers;
  const missingFor = locList(bc, "missing_for");
  return (
    <div className="bi-support">
      <Panel title={t("חריגות ותנאים", "Exceptions and conditions")} testId="bi-evidence" defaultOpen={openItems > 0}
        summary={openItems ? <span className="warn-text">{t(openItems === 1 ? "פריט פתוח אחד" : `${openItems} פריטים פתוחים`, openItems === 1 ? "One open item" : `${openItems} open items`)}</span>
          : t("אין פריטים פתוחים", "No open items")}>
        {x.discrepancies.map((g, i) => (
          <div key={i} className={`bi-gap${g.open ? " open" : ""}`} data-testid="bi-discrepancy" data-kind={g.kind} data-open={g.open}>
            <div className="bi-gap-head"><b>{locOf(g, "title_he")}{g.first_name_he ? ` · ${locOf(g, "first_name_he")}` : ""}</b><span className="bi-tag warn">{locOf(g, "status_he")}</span></div>
            <div className="bi-gap-grid">
              <div><span>{g.kind === "income" ? t("מוצהר", "Declared") : t("בבקשה", "In the application")}</span><Val ctx={ctx} d={g.declared} /></div>
              <div><span>{g.kind === "income" ? t("ממוצע בתלושים", "Payslip average") : t("בהצעת המחיר", "In the price quote")}</span><Val ctx={ctx} d={g.documented} /></div>
              <div><span>{t("הפרש", "Difference")}</span><b className="ltr">{money(g.difference_ils != null ? Math.abs(g.difference_ils) : null)}{g.difference_pct != null ? ` · ${Math.abs(g.difference_pct).toFixed(1)}%` : ""}</b></div>
              {g.tolerance_pct != null && <div><span>{t("סף סבולת", "Tolerance")}</span><b className="ltr">{g.tolerance_pct}%</b></div>}
            </div>
            <p><Loc he={g.explanation_he} en={enOf(g, "explanation_he")} /></p>
            <div className="bi-gap-act"><span><Loc he={g.action_he} en={enOf(g, "action_he")} /></span><button className="bi-ghost" onClick={() => ctx.openV1(g.v1_item)} data-testid="bi-gap-open">{t("פתיחה בסקירת המסמכים", "Open in the document review")}</button></div>
          </div>
        ))}
        {a.declared_alternative && (en ? <div className="bi-caution" data-testid="bi-declared-alt">Based on the declared income ({money(a.declared_alternative.income_ils)}) the combined ratio would be{" "}
          <b className="ltr">{pct(a.declared_alternative.combined_dsr_pct)}</b>; the analysis doesn't pick the figure that makes the application look better.</div>
          : <div className="bi-caution" data-testid="bi-declared-alt">על בסיס ההכנסה המוצהרת ({money(a.declared_alternative.income_ils)}) היחס המשולב היה{" "}
          <b className="ltr">{pct(a.declared_alternative.combined_dsr_pct)}</b>, הניתוח לא בוחר בנתון שמציג את הבקשה טוב יותר.</div>)}
        {x.risks.length > 0 && <ul className="bi-risks" data-testid="bi-risks">
          {x.risks.map((r, i) => (
            <li key={i} className={`r-${r.kind}`}><span className="bi-tag warn"><Loc he={r.who_he} en={enOf(r, "who_he")} /></span>
              <span className="bi-risk-t"><b><Loc he={r.title_he} en={enOf(r, "title_he")} /></b>{r.text_he ? <> — <Loc he={r.text_he} en={(r as { text_en?: string }).text_en} /></> : ""}</span>
              {r.source_ids.map((id) => <button key={id} className="bi-chipsrc" onClick={() => ctx.open(id)}><Mark kind={markOf(x.sources[id])} /></button>)}
              <button className="bi-link" onClick={() => ctx.openV1(r.v1_item)}>{t("פתיחה", "Open")}</button></li>))}
        </ul>}
        {en ? <div className="bi-unknowns"><b>Not included in the check:</b> {x.unknowns.map((u) => `${locOf(u, "label_he")}: ${locOf(u, "text_he")}`).join(" · ")}</div>
          : <div className="bi-unknowns"><b>לא נכלל בבדיקה:</b> {x.unknowns.map((u) => `${u.label_he}, ${u.text_he}`).join(" · ")}</div>}
      </Panel>

      <Panel title={t("התחייבויות ואובליגו", "Obligations and credit exposure")} testId="bi-obligations" demo={bc.available}
        summary={bc.available ? (en ? <>Existing payments <b className="ltr">{money(a.existing_debt.value)}</b> · utilized exposure <b className="ltr">{money(bc.exposure?.utilized.value)}</b></>
          : <>החזרים קיימים <b className="ltr">{money(a.existing_debt.value)}</b> · אובליגו מנוצל <b className="ltr">{money(bc.exposure?.utilized.value)}</b></>) : t("אין נתוני הקשר בנקאי", "No bank-context data")}>
        <div className="bi-mini">
          <div><span>{t("יחס החזר קיים", "Existing DSR")}</span><Val ctx={ctx} d={a.existing_dsr} /></div>
          <div><span>{t("החזרים קיימים בחודש", "Existing monthly payments")}</span><Val ctx={ctx} d={a.existing_debt} /></div>
          <div><span>{t("שיעור מימון מהאסמכתה", "Financing vs. the proof amount")}</span><Val ctx={ctx} d={a.ltv} testId="bi-kpi-ltv" /></div>
          <div><span>{t("הכנסה שנותרת אחרי החזרים (תיאורי)", "Income left after payments (descriptive)")}</span><Val ctx={ctx} d={a.remaining_after_debt} testId="bi-remaining" /></div>
          {bc.exposure && <div><span>{t("אובליגו מאושר", "Approved exposure (obligo)")}</span><Val ctx={ctx} d={bc.exposure.approved} testId="bi-exposure-approved" /></div>}
          {bc.exposure && <div><span>{t("אובליגו מנוצל", "Utilized exposure (obligo)")}</span><Val ctx={ctx} d={bc.exposure.utilized} testId="bi-exposure-utilized" /></div>}
        </div>
        {!bc.available ? <div className="bi-empty">{t(`אין נתוני הקשר בנקאי עבור ${bc.missing_for.join(", ") || "המבקשים"}, ההתחייבויות הקיימות לא ידועות, והיחס כולל רק את ההלוואה המבוקשת.`,
          `No bank-context data for ${missingFor.join(", ") || "the applicants"}; existing obligations are unknown, and the ratio includes only the requested loan.`)}</div> : <>
          <div className="bi-src-note">{t("נתוני בנק · נכון ל־", "Bank data · as of ")}<span className="ltr">{bc.observed_at}</span>{t(" · לא מאומת", " · not verified")}
            {bc.missing_for.length ? t(` · חסר עבור ${bc.missing_for.join(", ")}`, ` · missing for ${missingFor.join(", ")}`) : ""}</div>
          <table className="bi-table">
            <thead><tr><th>{t("הלוואה קיימת", "Existing loan")}</th><th>{t("יתרת קרן", "Outstanding principal")}</th><th>{t("החזר חודשי", "Monthly payment")}</th><th>{t("נותרו", "Remaining")}</th></tr></thead>
            <tbody>{bc.loans.length ? bc.loans.map((l) => (
              <tr key={l.id}><td><Loc he={l.type_he} en={enOf(l, "type_he")} /><div className="tiny muted">{locOf(l, "lender_he")} · {locOf(l, "owner_he")}</div></td>
                <td><Val ctx={ctx} d={l.outstanding} /></td><td><Val ctx={ctx} d={l.monthly} testId="bi-loan-monthly" /></td><td className="ltr">{l.remaining_payments}</td></tr>))
              : <tr><td colSpan={4} className="muted">{t("אין הלוואות קיימות בהקשר הבנקאי", "No existing loans in the bank context")}</td></tr>}</tbody>
          </table>
          <table className="bi-table">
            <thead><tr><th>{t("מסגרת אשראי", "Credit line")}</th><th>{t("מסגרת", "Limit")}</th><th>{t("מנוצל", "Utilized")}</th><th /></tr></thead>
            <tbody>{bc.credit_lines.map((l) => (
              <tr key={l.id}><td><Loc he={l.type_he} en={enOf(l, "type_he")} /><div className="tiny muted">{locOf(l, "owner_he")}</div></td><td className="ltr">{money(l.limit_ils)}</td>
                <td><button className="bi-val" onClick={() => ctx.open(l.source_id)}><span className="bi-num ltr">{money(l.utilized_ils)}</span><Mark kind="demo" /></button></td>
                <td><div className="bi-meter"><span style={{ width: `${Math.min(100, (l.utilized_ils / (l.limit_ils || 1)) * 100)}%` }} /></div></td></tr>))}</tbody>
          </table>
          <ul className="bi-notes">
            <li>{t("יתרות ומסגרות הן חשיפה (אובליגו), לא החזר חודשי, רק ההחזרים החודשיים נכנסים ליחס ההחזר.",
              "Balances and credit lines are exposure (obligo), not monthly payments; only the monthly payments count toward the DSR.")}</li>
            {bc.card_spending.map((c) => en
              ? <li key={c.source_id}>Card charges ({locOf(c, "owner_he")}): <button className="bi-val" onClick={() => ctx.open(c.source_id)}><span className="bi-num ltr">{money(c.avg_monthly_ils)}</span><Mark kind="demo" /></button> a month, an ongoing expense, not counted as debt service.</li>
              : <li key={c.source_id}>חיובי כרטיס ({c.owner_he}): <button className="bi-val" onClick={() => ctx.open(c.source_id)}><span className="bi-num ltr">{money(c.avg_monthly_ils)}</span><Mark kind="demo" /></button> בחודש, הוצאה שוטפת, לא נספרת כהחזר חוב.</li>)}
            {bc.events.map((e) => <li key={e.source_id} className={e.returned_checks_12m || e.arrears_12m ? "warn-text" : ""}>{en
              ? <>Account events in the last 12 months ({locOf(e, "owner_he")}): {e.returned_checks_12m || e.arrears_12m ? locList(e, "detail_he").join(" ") : "no returned cheques, arrears or restrictions"}</>
              : <>אירועי חשבון ב־12 חודשים ({e.owner_he}): {e.returned_checks_12m || e.arrears_12m ? e.detail_he.join(" ") : "ללא שיקים חוזרים, פיגורים או הגבלות"}</>} <button className="bi-chipsrc" onClick={() => ctx.open(e.source_id)}><Mark kind="demo" /></button></li>)}
          </ul>
        </>}
        {a.illustrative_max_principal != null && (en
          ? <div className="bi-maxp" data-testid="bi-max-principal">For illustration: an amount of up to <b className="ltr">{money(a.illustrative_max_principal)}</b> over {x.simulation.inputs.term_months} payments keeps the combined ratio within {x.simulation.threshold_pct}%; this is not an approved amount.</div>
          : <div className="bi-maxp" data-testid="bi-max-principal">להמחשה: סכום של עד <b className="ltr">{money(a.illustrative_max_principal)}</b> ל־{x.simulation.inputs.term_months} תשלומים משאיר את היחס המשולב בתוך {x.simulation.threshold_pct}%, אינו סכום מאושר.</div>)}
      </Panel>

      <Panel title={t("נתונים ומקורות", "Data and sources")} testId="bi-data"
        summary={en ? <>{inc[0]?.documented_avg.value != null ? <>Average income <b className="ltr">{money(inc[0].documented_avg.value)}</b>{inc[0].variability_pct != null ? <> · variability <span className="ltr">{pct(inc[0].variability_pct)}</span></> : null} · </> : null}
          {d.total} files · {docSources.length} figures from documents</>
          : <>{inc[0]?.documented_avg.value != null ? <>הכנסה ממוצעת <b className="ltr">{money(inc[0].documented_avg.value)}</b>{inc[0].variability_pct != null ? <> · תנודתיות <span className="ltr">{pct(inc[0].variability_pct)}</span></> : null} · </> : null}
          {d.total} קבצים · {docSources.length} נתונים ממסמכים</>}>
        <div className="bi-data-cols">
          <div>
            <h3>{t("הכנסה", "Income")}</h3>
            {inc.map((b) => (
              <div key={b.borrower_id} className="bi-income" data-testid="bi-income">
                <div className="bi-income-line"><b>{locOf(b, "first_name_he")}</b>
                  <span>{t("ממוצע", "Average")} <Val ctx={ctx} d={b.documented_avg} testId="bi-income-avg" /></span>
                  <span>{t("מוצהר", "Declared")} <Val ctx={ctx} d={b.declared} /></span>
                  {b.variability_pct != null && <span>{t("תנודתיות", "Variability")} <b className="ltr">{pct(b.variability_pct)}</b></span>}
                  {b.months.length > 0 && <button className="bi-link" onClick={() => setSlips(!slips)} aria-expanded={slips} data-testid="bi-slips-toggle">{slips ? t("הסתר תלושים", "Hide payslips") : t("הצג תלושים", "Show payslips")}</button>}
                </div>
                {slips && <div className="bi-months">{b.months.map((m) => (
                  <button key={m.period} className="bi-month" onClick={() => ctx.open(m.source_id)} disabled={!m.source_id} data-testid="bi-income-month" data-period={m.period}>
                    <span className="bi-month-k">{locOf(m, "period_he")}</span><span className="bi-month-v ltr">{money(m.net_ils)}</span>{m.source_id && <Mark kind={markOf(x.sources[m.source_id])} />}
                  </button>))}</div>}
              </div>
            ))}
            <h3>{t("הבקשה", "Application")}</h3>
            <dl className="bi-dl">
              <div><dt>{t("מטרה", "Purpose")}</dt><dd><Loc he={x.loan.purpose_he} en={enOf(x.loan, "purpose_he")} />{x.loan.note_he ? <> · <Loc he={x.loan.note_he} en={enOf(x.loan, "note_he")} /></> : ""}</dd></div>
              <div><dt>{t("מוצר", "Product")}</dt><dd><Loc he={x.loan.product_he} en={enOf(x.loan, "product_he")} /></dd></div>
              <div><dt>{t("סכום", "Amount")}</dt><dd><Val ctx={ctx} d={x.loan.amount} testId="bi-loan-amount" /></dd></div>
              <div><dt>{t("תשלומים", "Payments")}</dt><dd><Val ctx={ctx} d={x.loan.term} /></dd></div>
              {x.loan.asset && <div><dt>{locOf(x.loan.asset, "label_he")}</dt><dd><Val ctx={ctx} d={x.loan.asset.price} testId="bi-asset-price" /></dd></div>}
              {x.applicant.borrowers.map((b) => <div key={b.borrower_id}><dt><Loc he={b.name_he} en={enOf(b, "name_he")} /></dt><dd>{b.profile_he
                ? <Loc he={b.profile_he} en={enOf(b, "profile_he")} /> : <Loc he={x.applicant.profile_label_he} en={enOf(x.applicant, "profile_label_he")} />}
                {b.employer_document_source_id ? <> · <SrcLink ctx={ctx} id={b.employer_document_source_id}><Orig text={String(x.sources[b.employer_document_source_id].value_raw)} /></SrcLink></>
                  : b.employer_declared_he ? <> · <Loc he={b.employer_declared_he} en={enOf(b, "employer_declared_he")} /></> : ""}</dd></div>)}
            </dl>
            <h3>{t("מסמכים", "Documents")}</h3>
            <dl className="bi-dl" data-testid="bi-doc-detail">
              <div><dt>{t("דרישות שהושלמו", "Requirements met")}</dt><dd className="ltr">{d.progress ? `${d.progress.done}/${d.progress.total}` : "-"}</dd></div>
              <div><dt>{t("קבצים שהתקבלו", "Files received")}</dt><dd className="ltr">{d.total}</dd></div>
              <div><dt>{t("התקבלו על ידך", "Accepted by you")}</dt><dd className="ltr">{d.accepted}/{d.total}</dd></div>
              <div><dt>{t("שלב רשמי בבנק", "Official bank stage")}</dt><dd><Loc he={x.case.bank_stage.label_he} en={enOf(x.case.bank_stage, "label_he")} /> <Mark kind="demo" /></dd></div>
            </dl>
            {d.awaiting_decision > 0 && <button className="bi-link" onClick={() => ctx.openV1(null)}>{t(`${d.awaiting_decision === 1 ? "מסמך אחד ממתין" : `${d.awaiting_decision} מסמכים ממתינים`} לקבלה בסקירת המסמכים`,
              `${d.awaiting_decision === 1 ? "One document is awaiting" : `${d.awaiting_decision} documents are awaiting`} acceptance in the document review`)}</button>}
          </div>
          <div>
            <h3>{t("נתונים שחולצו ממסמכים", "Figures extracted from documents")}</h3>
            {docSources.length ? <ul className="bi-evlist" data-testid="bi-evlist">{docSources.map((src) => (
              <li key={src.id}><button className="bi-evrow" onClick={() => ctx.open(src)} data-testid="bi-evrow" data-field={src.field}>
                <span><Loc he={src.label_he} en={src.label_en} /></span><span className="ltr"><Orig text={src.value_raw} /></span><Mark kind={markOf(src)} /></button></li>))}</ul>
              : <div className="bi-empty">{t("אין עדיין נתונים שחולצו ממסמכים.", "No figures extracted from documents yet.")}</div>}
          </div>
        </div>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- the customer draft: a preview, editing on demand
export const DRAFT_NOTE: Record<string, string> = {
  complete_documentation: "אישור קבלה והעברה לבדיקת הבנק, ללא התחייבות לאישור.",
  missing_documents: "בקשה מדויקת לפריטים שחסרים בתיק.",
  financial_clarification: "בקשת הבהרה על פער מתועד, בלי הנימוק הפנימי.",
  conditional_financing: "חלופות להמחשה בלבד, עם התנאים במפורש. לא הצעה מחייבת.",
};
const DRAFT_NOTE_EN: Record<string, string> = {
  complete_documentation: "Acknowledges receipt and the move to the bank's review, with no commitment to approve.",
  missing_documents: "A precise request for the items missing from the case.",
  financial_clarification: "Asks about a documented gap, without the internal reasoning.",
  conditional_financing: "Illustrative alternatives only, with the conditions spelled out. Not a binding offer.",
};

function DraftCard({ ctx, onToast }: { ctx: Ctx; onToast: (t: { text: string; tone: "ok" | "bad" }) => void }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const [kind, setKind] = useState<string | null>(x.recommended_draft);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [refs, setRefs] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState(false);
  const draft = x.drafts.find((d) => d.kind === kind) || x.drafts[0];
  if (!draft) return <section className="bi-card bi-draft"><h2>{t("טיוטת מענה ללקוח", "Customer reply draft")}</h2><div className="bi-empty">{t("אין טיוטה מתאימה למצב התיק כרגע.", "No draft fits the case's current state.")}</div></section>;
  const text = texts[draft.kind] ?? draft.message_he;
  const edited = texts[draft.kind] != null && texts[draft.kind] !== draft.message_he;
  const chosen = draft.attachments.filter((a) => refs[`${draft.kind}:${a.document_id}`]);
  const full = chosen.length ? `${text}\n\nמסמכים בתיק שההודעה מתייחסת אליהם: ${chosen.map((a) => a.label_he).join(" · ")}` : text;
  const he = en ? { lang: "he", dir: "rtl" } : {};
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(full);
      onToast({ text: t("הטיוטה הועתקה. היא לא נשלחה ללקוח, השליחה נעשית בערוץ הבנק.", "The draft was copied. It wasn't sent to the customer; sending happens in the bank's channel."), tone: "ok" });
    } catch {
      onToast({ text: t("ההעתקה נחסמה בדפדפן. אפשר לסמן את הטקסט ולהעתיק ידנית.", "The browser blocked copying. You can select the text and copy it manually."), tone: "bad" });
    }
  };
  return (
    <section className={`bi-card bi-draft${editing ? " editing" : ""}`} data-testid="bi-action">
      <div className="bi-draft-head">
        <h2>{t("טיוטת מענה ללקוח", "Customer reply draft")}</h2>
        {edited && <span className="bi-tag sim" data-testid="bi-draft-edited">{t("נערך", "Edited")}</span>}
      </div>
      <div className="bi-dtabs" role="tablist">
        {x.drafts.map((d) => (
          <button key={d.kind} role="tab" aria-selected={d.kind === draft.kind} className={d.kind === draft.kind ? "on" : ""} onClick={() => setKind(d.kind)}
            data-testid="bi-draft-tab" data-kind={d.kind}>{locOf(d, "title_he")}{d.kind === x.recommended_draft && <span className="bi-rec-dot" title={t("מומלץ למצב התיק", "Recommended for the case's state")} aria-label={t("מומלץ", "Recommended")} />}</button>
        ))}
      </div>
      {en && <div className="bi-dnote bi-dlang" data-testid="bi-draft-lang">The customer receives this message in Hebrew, as written below.</div>}
      {!editing ? <>
        <button className="bi-preview" onClick={() => setEditing(true)} data-testid="bi-draft-preview" data-kind={draft.kind} {...he}>{text}</button>
        <div className="bi-dbar">
          <button className="bi-btn" onClick={() => setEditing(true)} data-testid="bi-draft-edit">{t("עריכה", "Edit")}</button>
          <button className="bi-ghost" onClick={copy} data-testid="bi-draft-copy">{t("העתקה", "Copy")}</button>
        </div>
      </> : <>
        <div className="bi-dnote">{t(DRAFT_NOTE[draft.kind], DRAFT_NOTE_EN[draft.kind])}</div>
        <textarea className="bi-dtext" value={text} onChange={(e) => setTexts({ ...texts, [draft.kind]: e.target.value })} dir="rtl"
          data-testid="bi-draft-text" data-kind={draft.kind} aria-label={t("טיוטת ההודעה ללקוח", "Draft message to the customer")} autoFocus {...(en ? { lang: "he" } : {})} />
        {draft.attachments.length > 0 && <div className="bi-refs">
          <div className="bi-refs-k">{t("הפניה למסמכים בתיק (רשות)", "Refer to documents in the case (optional)")}</div>
          {draft.attachments.map((a) => {
            const k = `${draft.kind}:${a.document_id}`;
            return <label key={k} className={`bi-ref${refs[k] ? " on" : ""}`}><input type="checkbox" checked={!!refs[k]} onChange={() => setRefs({ ...refs, [k]: !refs[k] })} />{locOf(a, "label_he")}</label>;
          })}
        </div>}
        <div className="bi-dbar">
          <button className="bi-btn" onClick={copy} data-testid="bi-draft-copy">{t("העתקה", "Copy")}</button>
          <button className="bi-ghost" disabled={!edited} onClick={() => setTexts({ ...texts, [draft.kind]: draft.message_he })} data-testid="bi-draft-restore">{t("שחזור הנוסח", "Restore the wording")}</button>
          <button className="bi-ghost" onClick={() => setEditing(false)} data-testid="bi-draft-collapse">{t("סגירה", "Close")}</button>
        </div>
      </>}
      <div className="bi-dfoot">{t("שום דבר לא נשלח מכאן. נוסח מתבנית קבועה, לא טקסט של מודל, בלי יחסי החזר או הערות פנימיות.",
        "Nothing is sent from here. The wording comes from a fixed template, not from a model, with no repayment ratios or internal notes.")}</div>
    </section>
  );
}

// ---------------------------------------------------------------- the source drawer
const KIND_HE: Record<string, string> = { document: "נתון ממסמך", declared: "הצהרת לקוח", synthetic_bank: "נתון מההקשר הבנקאי (לא מאומת)",
  calculated: "חישוב", assumption: "הנחה לצורך החישוב", missing: "נתון חסר" };
const KIND_EN: Record<string, string> = { document: "Figure from a document", declared: "Customer declaration", synthetic_bank: "Bank-context figure (not verified)",
  calculated: "Calculation", assumption: "Assumption for the calculation", missing: "Missing figure" };

export function SourceDrawer({ src, depth, ws, x, open, openV1, onBack, onClose }: Ctx & { src: IntelSource; depth: number; ws: Workspace; onBack: () => void; onClose: () => void }) {
  const { t } = useLang();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const doc = src.kind === "document" ? ws.items.find((i): i is DocItem => i.kind === "document" && i.document_id === src.document_id) : undefined;
  const kind = markOf(src);
  return (
    <div className="bi-drawer-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className="bi-drawer" role="dialog" aria-label={t(`מקור: ${src.label_he}`, `Source: ${locOf(src, "label_he")}`)} data-testid="bi-drawer" data-kind={src.kind} data-source={src.id}>
        <header className="bi-dr-head">
          {depth > 1 && <button className="bi-ghost" onClick={onBack} data-testid="bi-drawer-back">{t("→ חזרה", "← Back")}</button>}
          <Mark kind={kind} /><span className="bi-dr-kind">{t(KIND_HE[src.kind], KIND_EN[src.kind])}</span>
          <button className="bi-dr-x" onClick={onClose} aria-label={t("סגירה", "Close")} data-testid="bi-drawer-close">×</button>
        </header>
        <div className="bi-dr-title"><Loc he={src.label_he} en={src.label_en} /></div>
        <div className="bi-dr-value ltr" data-testid="bi-drawer-value">{src.kind === "document" ? <Orig text={src.value_raw} /> : fmt(src.value ?? null, src.unit, true)}</div>
        {src.kind === "document" && <>
          <div className={`bi-dr-witness${src.verified ? " ok" : ""}`}><Loc he={src.witness_he} en={enOf(src, "witness_he")} />{src.banker_reviewed ? t(" · המסמך התקבל על ידי הבנקאי", " · The document was accepted by the banker") : ""}</div>
          <dl className="bi-dr-meta">
            <div><dt>{t("קובץ", "File")}</dt><dd className="ltr">{src.filename}</dd></div>
            <div><dt>{t("סוג", "Type")}</dt><dd><Loc he={src.doc_type_he} en={enOf(src, "doc_type_he")} />{src.period_he ? ` · ${locOf(src, "period_he")}` : ""}</dd></div>
            <div><dt>{t("בדיקת AI", "AI check")}</dt><dd><Loc he={src.ai_verdict_he} en={enOf(src, "ai_verdict_he")} /></dd></div>
            <div><dt>{t("החלטת בנקאי", "Banker decision")}</dt><dd><Loc he={src.banker_status_he} en={enOf(src, "banker_status_he")} /></dd></div>
            <div><dt>{t("מיקום", "Location")}</dt><dd>{src.has_location ? t(`עמוד ${src.page}, מסומן על המסמך`, `Page ${src.page}, marked on the document`) : t("אין מיקום מדויק, מוצג העמוד בלבד", "No exact location; only the page is shown")}</dd></div>
          </dl>
          <div className="bi-dr-actions">
            <button className="bi-btn" onClick={() => { onClose(); openV1(src.v1_item); }} data-testid="bi-drawer-v1">{t("פתיחה בסקירת המסמכים", "Open in the document review")}</button>
            <a className="bi-ghost" href={`/api/documents/${src.document_id}/file`} target="_blank" rel="noreferrer">{t("הקובץ המקורי ↗", "Original file ↗")}</a>
          </div>
          {doc ? <div className="bi-dr-viewer" data-testid="bi-drawer-evidence">
            <EvidenceViewer documentId={doc.document_id} facts={doc.ai.facts} page={src.page || 1} focus={src.field} dpi={130} quiet autoScroll={false} />
          </div> : <div className="bi-empty">{t("המסמך אינו זמין בסקירה הנוכחית, לא מוצגת ראיה.", "The document isn't available in the current review, so no evidence is shown.")}</div>}
        </>}
        {src.kind === "declared" && <div className="bi-dr-box">
          <p><b>{t("מקור:", "Source:")}</b> <Loc he={src.origin_he} en={enOf(src, "origin_he")} /></p>{src.note_he && <p><b>{t("הערת הלקוח:", "Customer's note:")}</b> <Loc he={src.note_he} en={src.note_en} /></p>}
          <p className="muted">{t("נתון שהלקוח מסר. אינו מאומת עד שמסמך תומך בו.", "A figure the customer provided. It isn't verified until a document supports it.")}</p></div>}
        {src.kind === "synthetic_bank" && <div className="bi-dr-box demo" data-testid="bi-drawer-synthetic">
          <p><b>{t("מקור:", "Source:")}</b> <Loc he={src.source_he} en={enOf(src, "source_he")} /></p>
          <p><b>{t("נכון לתאריך:", "As of:")}</b> <span className="ltr">{src.observed_at}</span></p>
          {src.detail_he && <p><Loc he={src.detail_he} en={enOf(src, "detail_he")} /></p>}
          <p className="muted"><Loc he={src.note_he} en={src.note_en} /></p></div>}
        {src.kind === "assumption" && <div className="bi-dr-box"><p><Loc he={src.note_he} en={src.note_en} /></p></div>}
        {src.kind === "calculated" && <div className="bi-dr-box" data-testid="bi-drawer-formula">
          <div className="bi-formula"><Loc he={src.formula_he} en={src.formula_en} /></div>
          {src.inputs && src.inputs.length > 0 && <table className="bi-table"><thead><tr><th>{t("קלט", "Input")}</th><th>{t("ערך", "Value")}</th><th>{t("מקור", "Source")}</th></tr></thead>
            <tbody>{src.inputs.map((i, n) => {
              const s = i.source_id ? x.sources[i.source_id] : null;
              return <tr key={n}><td><Loc he={i.label_he} en={i.label_en} /></td><td className="ltr">{fmt(i.value, i.unit, true)}</td>
                <td>{s ? <button className="bi-srclink" onClick={() => open(s)} data-testid="bi-drawer-input">{t(KIND_HE[s.kind], KIND_EN[s.kind])}<Mark kind={markOf(s)} /></button>
                  : <span className="bi-plain"><Mark kind={i.origin || "missing"} /> {MARK[i.origin || "missing"].label}</span>}</td></tr>;
            })}</tbody></table>}
          {src.note_he && <p className="muted"><Loc he={src.note_he} en={src.note_en} /></p>}
        </div>}
      </aside>
    </div>
  );
}
