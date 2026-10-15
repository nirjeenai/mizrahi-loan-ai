import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, timeHe, usePolling, type Datum, type DocItem, type IntelSource, type Intelligence, type SourceInput, type Workspace } from "../../api";
import { EvidenceViewer } from "../../components/EvidenceViewer";
import { scenarios as simulate, type Scenario } from "../../finance";
import { Toast } from "./deskUi";
import "./intelligence.css";

/** Banker Intelligence V2 — a compact, executive-first dashboard for one case: the recommendation, three numbers, the
 *  financing alternatives, then supporting detail on demand. Read-only — every state change happens in the review
 *  workspace (V1), which this view links into. Numbers come from GET /api/banker/cases/{id}/intelligence; the What-if
 *  simulator recomputes locally (finance.ts) and never writes back. */
export function IntelligenceV2({ caseId, ws, openV1 }: { caseId: string; ws: Workspace; openV1: (item?: string | null) => void }) {
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
  if (!x) return <div className="desk-loading">{intel.error ? <>לא הצלחנו לטעון את תמונת המצב. <button className="link" onClick={intel.reload}>ניסיון חוזר</button></>
    : <><span className="spinner" /> JEEN מרכז את תמונת המצב של התיק…</>}</div>;
  return (
    <div className="bi-scroll" data-testid="bi-root" data-case={caseId}>
      <Dashboard key={caseId} x={x} open={open} openV1={openV1} onToast={setToast} />
      {stack.length > 0 && <SourceDrawer src={stack[stack.length - 1]} depth={stack.length} ws={ws} x={x} open={open} openV1={openV1}
        onBack={() => setStack((s) => s.slice(0, -1))} onClose={() => setStack([])} />}
      <Toast message={toast} onClose={clearToast} />
    </div>
  );
}

interface Ctx { x: Intelligence; open: (s: string | IntelSource | null | undefined) => void; openV1: (item?: string | null) => void }
interface Sim { principal: number; term: number; rate: number }

function Dashboard({ x, open, openV1, onToast }: Ctx & { onToast: (t: { text: string; tone: "ok" | "bad" }) => void }) {
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
          <p className="bi-foot">{x.disclaimer_he} · עודכן <span className="ltr">{timeHe(x.generated_at)}</span> · <SourceLegend /></p>
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
const money = (v?: number | null, exact = false) => (v == null ? "—" : `₪${(exact ? nf2 : nf0).format(v)}`);
const pct = (v?: number | null) => (v == null ? "—" : `${v.toFixed(1)}%`);
const fmt = (v: number | string | null | undefined, unit?: string, exact = false) =>
  v == null ? "—" : typeof v === "string" ? v : unit === "pct" ? pct(v) : unit === "months" ? `${v} תשלומים` : money(v, exact);
const years = (m: number) => (m % 12 === 0 ? `${m / 12} שנים` : `${(m / 12).toFixed(1)} שנים`);

type MarkKind = "verified" | "reviewed" | "unverified" | "declared" | "demo" | "calc" | "assume" | "missing" | "sim";
/** Small provenance icons: the distinction stays (document · declared · calculated · DEMO · assumption · simulation ·
 *  missing), the noise goes. The full explanation is one click away in the source drawer. */
const MARK: Record<MarkKind, { icon: string; label: string; title: string }> = {
  verified: { icon: "✓", label: "מסמך", title: "חולץ ממסמך ואומת מול הקובץ" },
  reviewed: { icon: "✓", label: "נבדק", title: "חולץ ממסמך, אומת מול הקובץ, והמסמך התקבל על ידי הבנקאי" },
  unverified: { icon: "!", label: "מסמך · לא אומת", title: "חולץ ממסמך — לא אומת מול הקובץ" },
  declared: { icon: "✎", label: "מוצהר", title: "הצהרת הלקוח בבקשה — לא מאומת" },
  demo: { icon: "DEMO", label: "דמו", title: "נתון בנקאי סינתטי להדגמה — לא נתון אמיתי ולא מאומת" },
  calc: { icon: "ƒ", label: "חישוב", title: "חושב בקוד מנתונים אחרים — לחצו לנוסחה ולקלטים" },
  assume: { icon: "≈", label: "הנחה", title: "הנחת הדגמה — אינה מדיניות או ריבית של הבנק" },
  missing: { icon: "?", label: "חסר", title: "הנתון אינו זמין" },
  sim: { icon: "◇", label: "סימולציה", title: "ערך סימולציה — לא נשמר ואינו משנה את הבקשה" },
};
function markOf(s?: IntelSource | null): MarkKind {
  if (!s) return "missing";
  if (s.kind === "document") return s.banker_reviewed ? "reviewed" : s.verified ? "verified" : "unverified";
  return ({ declared: "declared", synthetic_bank: "demo", calculated: "calc", assumption: "assume", missing: "missing" } as Record<string, MarkKind>)[s.kind] || "missing";
}
function Mark({ kind }: { kind: MarkKind }) {
  return <span className={`bi-ic m-${kind}`} title={MARK[kind].title} aria-label={MARK[kind].label} role="img" data-testid="bi-mark" data-mark={kind}>{MARK[kind].icon}</span>;
}
function SourceLegend() {
  return <span className="bi-legend" data-testid="bi-legend">{(["verified", "declared", "calc", "demo", "assume"] as MarkKind[]).map((k) =>
    <span key={k}><Mark kind={k} /> {MARK[k].label}</span>)}</span>;
}

/** A number and where it came from. Click opens the source drawer; a value without a source says so. */
function Val({ ctx, d, big, exact, testId }: { ctx: Ctx; d?: Datum | null; big?: boolean; exact?: boolean; testId?: string }) {
  const src = d?.source_id ? ctx.x.sources[d.source_id] : null;
  if (!d || d.value == null) return <span className={`bi-val none${big ? " big" : ""}`} data-testid={testId}><span className="bi-num">לא זמין</span><Mark kind="missing" /></span>;
  return (
    <button className={`bi-val${big ? " big" : ""}`} onClick={() => ctx.open(src)} disabled={!src} data-testid={testId || "bi-datum"}
      data-source={d.source_id || ""} data-kind={src?.kind || "none"} title={src ? `מקור: ${src.label_he}` : undefined}>
      <span className="bi-num ltr">{fmt(d.value, d.unit, exact)}</span>{src && <Mark kind={markOf(src)} />}
    </button>
  );
}
function SrcLink({ ctx, id, children }: { ctx: Ctx; id: string | null | undefined; children?: ReactNode }) {
  const s = id ? ctx.x.sources[id] : null;
  if (!s) return null;
  return <button className="bi-srclink" onClick={() => ctx.open(s)} data-testid="bi-srclink" data-kind={s.kind}>{children ?? s.label_he}<Mark kind={markOf(s)} /></button>;
}

// ---------------------------------------------------------------- header: who, what, the recommendation, one action
const TITLE: Record<string, string> = {
  READY_FOR_CREDIT_REVIEW: "מומלץ להתקדם לבחינת האשראי", PREPARATION_CONFIRMED: "הכנת התיק אושרה — אפשר להתקדם לבחינת האשראי",
  CLARIFICATION_REQUIRED: "נדרש בירור לפני המשך הטיפול", DOCUMENTS_INCOMPLETE: "נדרשת השלמת מסמכים", NO_DOCUMENTS: "ממתינים למסמכים מהלקוח",
  PROCESSING: "JEEN בודק את המסמכים", ERROR: "תקלה בבדיקת המסמכים",
};
const TONE: Record<string, string> = { READY_FOR_CREDIT_REVIEW: "ok", PREPARATION_CONFIRMED: "ok", CLARIFICATION_REQUIRED: "warn",
  DOCUMENTS_INCOMPLETE: "warn", NO_DOCUMENTS: "neutral", PROCESSING: "neutral", ERROR: "bad" };

/** One sentence for a case that is ready: built from the briefing's own numbers. Other states use the briefing's headline. */
function explanation(x: Intelligence): string {
  const r = x.recommendation;
  if (r.state === "DOCUMENTS_INCOMPLETE") {
    const n = x.documents.missing.length + x.documents.corrections.length;
    return `${n === 1 ? "פריט אחד חסר" : `${n} פריטים חסרים`} בתיק (מפורטים למטה). עד להשלמתם לא ניתן לגבש תמונה פיננסית מספקת, והחלופות מוצגות להמחשה בלבד.`;
  }
  if (!["READY_FOR_CREDIT_REVIEW", "PREPARATION_CONFIRMED"].includes(r.state)) return r.headline_he;
  if (x.analysis.availability === "unavailable") return `המסמכים הושלמו. ${x.analysis.reasons_he[0] || ""}`.trim();
  const verified = x.income.borrowers.every((b) => b.quality === "verified" || b.chosen.value == null);
  const parts = [r.state === "PREPARATION_CONFIRMED" ? "הכנת התיק אושרה" : "המסמכים הושלמו",
    `${verified ? "ההכנסה הממוצעת המאומתת היא" : "ההכנסה לחישוב (חלקה מוצהרת) היא"} ${money(x.analysis.income.value)}`];
  if (x.analysis.combined_dsr?.value != null) parts.push(`יחס ההחזר המשולב בסימולציה הוא ${pct(x.analysis.combined_dsr.value)}`);
  const last = parts.pop();
  const verify = x.bank_context.available ? "נדרש אימות נתוני הבנק לפני החלטה." : "אין נתוני התחייבויות קיימות — נדרש אימות לפני החלטה.";
  return `${parts.join(", ")} ו${last}. ${verify}`;
}

function docStatus(x: Intelligence): { primary: string; tone: string; banker: string | null } {
  const d = x.documents;
  const pending = d.missing.length + d.corrections.length;
  if (x.recommendation.state === "PROCESSING") return { primary: "המסמכים בבדיקת JEEN", tone: "neutral", banker: null };
  if (!d.total && pending) return { primary: "טרם הועלו מסמכים", tone: "neutral", banker: null };
  if (pending) return { primary: pending === 1 ? "חסר פריט אחד" : `חסרים ${pending} פריטים`, tone: "warn", banker: null };
  const banker = x.recommendation.state === "PREPARATION_CONFIRMED" ? "הכנת התיק אושרה על ידך"
    : d.open_findings ? (d.open_findings === 1 ? "ממצא אחד לבירור בנקאי" : `${d.open_findings} ממצאים לבירור בנקאי`)
      : d.awaiting_decision ? "ממתין לבדיקת בנקאי" : "המסמכים התקבלו על ידך";
  return { primary: "מסמכים הושלמו", tone: "ok", banker };
}

function Header({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const r = x.recommendation;
  const ds = docStatus(x);
  const who = x.applicant.company?.name_he || x.applicant.borrowers.map((b) => b.name_he).join(" ו");
  const blockers = [
    ...x.discrepancies.filter((d) => d.open).map((d) => ({ key: d.v1_item + d.kind, text: d.kind === "income"
      ? `פער הכנסה פתוח: מוצהר ${money(d.declared.value)} · בתלושים ${money(d.documented.value)}`
      : `הסכום המבוקש (${money(d.declared.value)}) גבוה מהצעת המחיר (${money(d.documented.value)})`, item: d.v1_item })),
    ...x.documents.missing.slice(0, 4).map((m) => ({ key: m.v1_item, text: `חסר: ${m.title_he}`, item: m.v1_item })),
    ...x.documents.corrections.map((c) => ({ key: c.v1_item, text: `לתיקון: ${c.title_he}`, item: c.v1_item })),
  ];
  const more = x.documents.missing.length - 4;
  return (
    <section className={`bi-head t-${TONE[r.state] || "neutral"}`} data-testid="bi-brief" data-state={r.state}>
      <div className="bi-head-ctx" data-testid="bi-context">
        <span className="bi-who">{who}</span>
        <span className="bi-what">{x.loan.purpose_he ? `הלוואה ל${x.loan.purpose_he.replace(/^רכישת /, "")}` : x.case.title_he}</span>
        <span className="bi-sep" aria-hidden>·</span>
        <span className="ltr bi-amt">{money(x.loan.amount.value)}</span><span className="bi-sep" aria-hidden>·</span>
        <span>{x.loan.term.value} תשלומים</span>
        {x.applicant.profile_label_he && <><span className="bi-sep" aria-hidden>·</span><span className="muted">{x.applicant.profile_label_he}</span></>}
        <span className="bi-case muted">תיק <span className="ltr">{x.case.display_number}</span></span>
      </div>
      <div className="bi-head-body">
        <div className="bi-rec">
          <h1 className="bi-rec-title" data-testid="bi-headline"><span className="bi-dot" aria-hidden />{TITLE[r.state] || r.documentation.status_he}</h1>
          <p className="bi-rec-text" data-testid="bi-rec-text">{explanation(x)}</p>
          {blockers.length > 0 && <ul className="bi-blockers" data-testid="bi-blockers">
            {blockers.map((b) => <li key={b.key}><button onClick={() => ctx.openV1(b.item)}>{b.text}</button></li>)}
            {more > 0 && <li className="muted">ועוד {more}</li>}
          </ul>}
        </div>
        <div className="bi-act">
          <button className="bi-primary" onClick={() => ctx.openV1(r.next_action.v1_item)} disabled={r.next_action.kind === "wait"}
            data-testid="bi-next-btn">{r.next_action.label_he}<span aria-hidden>←</span></button>
          {r.next_action.detail_he && <div className="bi-act-detail">{r.next_action.detail_he}</div>}
          <div className="bi-status" data-testid="bi-doc-status">
            <span className={`bi-pill p-${ds.tone}`} data-testid="bi-doc-primary">{ds.primary}</span>
            {ds.banker && <span className="bi-pill p-line" data-testid="bi-doc-banker">{ds.banker}</span>}
          </div>
          <div className="bi-disclaimer">המלצת המשך בלבד · לא אישור אשראי</div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- the three numbers
function Kpis({ ctx, live, changed, sim }: { ctx: Ctx; live?: Scenario; changed: boolean; sim: Sim }) {
  const { x } = ctx;
  const a = x.analysis;
  const thr = x.simulation.threshold_pct;
  const income = x.income.borrowers;
  const incomeNote = a.availability === "provisional" ? "הנמוך מבין מוצהר למתועד, עד לבירור"
    : income.some((b) => b.quality === "declared") ? "מוצהר — טרם אומת במסמכים"
      : income.some((b) => b.quality === "partial") ? "חלק מהחודשים" : income.length > 1 ? "סך הלווים" : "ממוצע תלושים מאומתים";
  const paySrc: IntelSource | null = !live ? null : !changed && a.proposed_payment?.source_id ? x.sources[a.proposed_payment.source_id] : {
    id: "sim:kpi:pay", kind: "calculated", label_he: `החזר חודשי בסימולציה — ${live.term_months} תשלומים`, value: live.monthly_payment_ils, unit: "ils",
    formula_he: "P·r ÷ (1 − (1 + r)^−n), r = ריבית שנתית ÷ 12",
    inputs: [{ label_he: "קרן (P)", value: sim.principal, unit: "ils", source_id: null, origin: "sim" },
      { label_he: "תשלומים (n)", value: sim.term, unit: "months", source_id: null, origin: "sim" },
      { label_he: "ריבית שנתית", value: sim.rate, unit: "pct", source_id: null, origin: "sim" }], note_he: "ערכי סימולציה — לא נשמרים." };
  const dsrSrc: IntelSource | null = !live || live.combined_dsr_pct == null ? null : !changed && a.combined_dsr?.source_id ? x.sources[a.combined_dsr.source_id] : {
    id: "sim:kpi:dsr", kind: "calculated", label_he: "יחס החזר משולב בסימולציה", value: live.combined_dsr_pct, unit: "pct",
    formula_he: "(החזר משוער + החזרים קיימים) ÷ הכנסה נטו × 100",
    inputs: [{ label_he: "החזר משוער", value: live.monthly_payment_ils, unit: "ils", source_id: null, origin: "calc" },
      { label_he: "החזרים קיימים", value: x.simulation.existing_debt_ils, unit: "ils", source_id: x.simulation.existing_source_id },
      { label_he: "הכנסה נטו", value: x.simulation.income_ils, unit: "ils", source_id: x.simulation.income_source_id }] };
  const over = live?.combined_dsr_pct != null && live.combined_dsr_pct > thr;
  return (
    <div className="bi-kpis" data-testid="bi-kpis">
      <div className="bi-kpi" data-testid="bi-kpi-income">
        <div className="bi-kpi-k">הכנסה חודשית נטו ממוצעת</div>
        <Val ctx={ctx} d={a.income} big />
        <div className="bi-kpi-n">{incomeNote}</div>
      </div>
      <div className="bi-kpi" data-testid="bi-kpi-payment">
        <div className="bi-kpi-k">החזר חודשי חדש בסימולציה</div>
        {live && paySrc ? <button className="bi-val big" onClick={() => ctx.open(paySrc)} data-testid="bi-kpi-payment-value" data-value={live.monthly_payment_ils}>
          <span className="bi-num ltr">{money(live.monthly_payment_ils)}</span><Mark kind={changed ? "sim" : "calc"} /></button> : <Val ctx={ctx} d={null} big />}
        <div className="bi-kpi-n">{live ? `${money(live.principal_ils)} · ${live.term_months} תשלומים · ${pct(live.annual_rate_pct)}` : "—"}</div>
      </div>
      <div className={`bi-kpi${live?.combined_dsr_pct != null ? (over ? " k-warn" : " k-ok") : ""}`} data-testid="bi-kpi-combined">
        <div className="bi-kpi-k">יחס החזר כולל בסימולציה</div>
        {live && dsrSrc ? <button className="bi-val big" onClick={() => ctx.open(dsrSrc)} data-testid="bi-kpi-combined-value" data-value={live.combined_dsr_pct ?? ""}>
          <span className="bi-num ltr">{pct(live.combined_dsr_pct)}</span><Mark kind={changed ? "sim" : "calc"} /></button> : <Val ctx={ctx} d={null} big />}
        <div className="bi-kpi-n">{live?.combined_dsr_pct == null ? "אין הכנסה לחישוב" : `${live.combined_includes_existing ? "כולל התחייבויות קיימות" : "ללא התחייבויות קיימות (אין נתונים)"} · סף להמחשה ${thr}%`}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- financing alternatives and What-if
const SC_LABEL: Record<string, string> = { short: "תקופה קצרה", requested: "לפי הבקשה", long: "תקופה ארוכה" };

function Simulator({ ctx, sim, setSim, base, changed, rows }: { ctx: Ctx; sim: Sim; setSim: (s: Sim) => void; base: Sim; changed: boolean; rows: Scenario[] }) {
  const { x } = ctx;
  const s = x.simulation;
  const thr = s.threshold_pct;
  if (!s.enabled) return <section className="bi-sec" data-testid="bi-simulator"><h2>חלופות מימון</h2><div className="bi-empty">אין בבקשה סכום ומספר תשלומים לחישוב.</div></section>;
  const short = rows[0], long = rows[rows.length - 1];
  const calcSource = (r: Scenario, what: "pay" | "dsr" | "total"): IntelSource => {
    const inP: SourceInput = { label_he: "קרן (P)", value: sim.principal, unit: "ils", source_id: sim.principal === base.principal ? "app:amount" : null, origin: "sim" };
    const inN: SourceInput = { label_he: "תשלומים (n)", value: r.term_months, unit: "months", source_id: r.term_months === base.term ? "app:term" : null,
      origin: r.term_months === sim.term ? "sim" : "calc" };
    const inR: SourceInput = { label_he: "ריבית שנתית", value: sim.rate, unit: "pct", source_id: sim.rate === base.rate ? s.rate_source_id : null, origin: "sim" };
    const pay: SourceInput = { label_he: "החזר חודשי", value: r.monthly_payment_ils, unit: "ils", source_id: null, origin: "calc" };
    if (what === "pay") return { id: `sim:pay:${r.key}`, kind: "calculated", label_he: `החזר חודשי — ${r.term_months} תשלומים`, value: r.monthly_payment_ils,
      unit: "ils", formula_he: "P·r ÷ (1 − (1 + r)^−n), r = ריבית שנתית ÷ 12", inputs: [inP, inN, inR],
      note_he: "חושב בדפדפן באותה נוסחה ובאותו עיגול כמו בשרת. ערכי סימולציה אינם נשמרים." };
    if (what === "total") return { id: `sim:total:${r.key}`, kind: "calculated", label_he: `עלות המימון — ${r.term_months} תשלומים`, value: r.total_interest_ils,
      unit: "ils", formula_he: "החזר חודשי × n − P", inputs: [pay, inN, inP],
      note_he: "מחושב מההחזר הלא מעוגל — התשלום האחרון סופג את עיגול האגורות. בריבית 0% עלות המימון היא 0." };
    return { id: `sim:dsr:${r.key}`, kind: "calculated", label_he: `יחס החזר משולב — ${r.term_months} תשלומים`, value: r.combined_dsr_pct, unit: "pct",
      formula_he: "(החזר משוער + החזרים קיימים) ÷ הכנסה נטו × 100",
      inputs: [pay, { label_he: "החזרים קיימים", value: s.existing_debt_ils, unit: "ils", source_id: s.existing_source_id },
        { label_he: "הכנסה נטו", value: s.income_ils, unit: "ils", source_id: s.income_source_id }],
      note_he: r.combined_includes_existing ? null : "אין נתוני התחייבויות קיימות — היחס כולל רק את ההלוואה המבוקשת." };
  };
  const caution = x.analysis.availability === "unavailable" ? "ניתוח יחסי ההחזר אינו זמין לתיק זה — מוצגים החזרים ועלויות בלבד."
    : x.analysis.availability === "provisional" ? "להמחשה בלבד — הניתוח זמני עד לבירור הפער בהכנסה."
      : x.analysis.availability === "partial" ? `להמחשה בלבד — ${x.analysis.reasons_he[0] || "הניתוח חלקי."}` : null;
  return (
    <section className="bi-sec bi-simsec" data-testid="bi-simulator">
      <header className="bi-sec-head">
        <div><h2>חלופות מימון</h2><p className="bi-sub">שלוש חלופות מחושבות על בסיס הנתונים בתיק. ניתן להשוות החזר חודשי ועלות כוללת.</p></div>
        <button className="bi-ghost" onClick={() => setSim(base)} disabled={!changed} data-testid="bi-wi-reset">חזרה לנתוני הבקשה</button>
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
                <span className="bi-sc-k">{r.key === "requested" && changed ? "התקופה שנבחרה" : SC_LABEL[r.key]}</span>
                {r.key === "requested" && !changed && <span className="bi-tag">בקשת הלקוח</span>}
                {suggested && <span className="bi-tag ok" title={s.suggested?.label_he}>חלופה להמחשה</span>}
              </header>
              <div className="bi-sc-meta"><span className="ltr">{money(r.principal_ils)}</span> · <b className="ltr">{r.term_months}</b> תשלומים ({years(r.term_months)})</div>
              <button className="bi-sc-pay" onClick={() => ctx.open(calcSource(r, "pay"))} data-testid="bi-sc-pay" data-value={r.monthly_payment_ils}>
                <span className="ltr">{money(r.monthly_payment_ils)}</span><small>לחודש</small><Mark kind={changed ? "sim" : "calc"} /></button>
              <dl>
                <div><dt>סך ההחזר</dt><dd className="ltr" data-testid="bi-sc-total">{money(r.total_payments_ils)}</dd></div>
                <div><dt>עלות המימון</dt><dd><button className="bi-val" onClick={() => ctx.open(calcSource(r, "total"))} data-testid="bi-sc-interest" data-value={r.total_interest_ils}>
                  <span className="bi-num ltr">{money(r.total_interest_ils)}</span></button></dd></div>
              </dl>
              <button className={`bi-dsr${over ? " over" : ""}`} onClick={() => ctx.open(calcSource(r, "dsr"))} data-testid="bi-sc-dsr" data-value={r.combined_dsr_pct ?? ""}
                disabled={r.combined_dsr_pct == null}>
                <span className="bi-dsr-k">יחס החזר כולל</span><span className="bi-dsr-v ltr">{pct(r.combined_dsr_pct)}</span>
                {r.combined_dsr_pct != null && <span className="bi-dsr-track"><span className="fill" style={{ width: `${Math.min(100, r.combined_dsr_pct / 60 * 100)}%` }} />
                  <span className="thr" style={{ insetInlineStart: `${thr / 60 * 100}%` }} title={`סף להמחשה: ${thr}%`} /></span>}
              </button>
            </article>
          );
        })}
      </div>
      {rows.length > 1 && <p className="bi-compare" data-testid="bi-compare">
        בפריסה ל־<b className="ltr">{long.term_months}</b> תשלומים ההחזר החודשי נמוך ב־<b className="ltr">{money(short.monthly_payment_ils - long.monthly_payment_ils)}</b> מאשר
        ב־<b className="ltr">{short.term_months}</b>, אך עלות המימון גבוהה ב־<b className="ltr">{money(long.total_interest_ils - short.total_interest_ils)}</b>.</p>}
      <div className="bi-whatif" data-testid="bi-whatif">
        <span className="bi-whatif-k">קלטי סימולציה<small>לא נשמרים בבקשה</small></span>
        <Slider label="סכום" value={sim.principal} min={10000} max={s.bounds.principal_max} step={1000} onChange={(v) => setSim({ ...sim, principal: v })}
          display={money(sim.principal)} testId="bi-wi-principal" changed={sim.principal !== base.principal} />
        <Slider label="תשלומים" value={sim.term} min={s.bounds.term_min} max={s.bounds.term_max} step={6} onChange={(v) => setSim({ ...sim, term: v })}
          display={`${sim.term} · ${years(sim.term)}`} testId="bi-wi-term" changed={sim.term !== base.term} />
        <Slider label="ריבית להמחשה" value={sim.rate} min={0} max={15} step={0.1} onChange={(v) => setSim({ ...sim, rate: Math.round(v * 10) / 10 })}
          display={`${sim.rate.toFixed(1)}%`} testId="bi-wi-rate" changed={sim.rate !== base.rate}
          hint={<SrcLink ctx={ctx} id={s.rate_source_id}>ברירת מחדל {base.rate.toFixed(1)}%</SrcLink>} />
      </div>
    </section>
  );
}

function Slider({ label, value, min, max, step, onChange, display, testId, changed, hint }: {
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
  const { x } = ctx;
  const r = x.recommendation;
  const [all, setAll] = useState(false);
  const d = x.documents;
  const pending = d.missing.length + d.corrections.length;
  const docLine = { text_he: pending ? `חסרים ${pending} פריטים בתיק — ראו בראש המסך.`
    : d.open_findings ? `המסמכים הושלמו; ${d.open_findings === 1 ? "ממצא אחד ממתין" : `${d.open_findings} ממצאים ממתינים`} לבירור שלך.`
      : d.total ? `המסמכים הנדרשים הושלמו (${d.progress ? `${d.progress.done}/${d.progress.total}` : d.total}).` : "טרם הועלו מסמכים.",
    tone: pending || d.open_findings ? "warn" : d.total ? "ok" : "info", source_ids: [] as string[] };
  const ranked = [docLine, ...[...r.considerations].sort((a, b) => (TONE_RANK[a.tone] ?? 3) - (TONE_RANK[b.tone] ?? 3))];
  const shown = all ? ranked : ranked.slice(0, 3);
  return (
    <section className="bi-card bi-why" data-testid="bi-considerations">
      <h2>למה זו ההמלצה</h2>
      <ul className="bi-cons">
        {shown.map((c, i) => (
          <li key={i} className={`c-${c.tone}`} data-testid="bi-consideration">
            <span>{c.text_he}</span>
            {all && c.source_ids.filter((id) => x.sources[id]).length > 0 && <span className="bi-cons-src">
              {c.source_ids.filter((id) => x.sources[id]).map((id) => <button key={id} className="bi-chipsrc" onClick={() => ctx.open(id)} title={x.sources[id].label_he}><Mark kind={markOf(x.sources[id])} /></button>)}</span>}
          </li>
        ))}
      </ul>
      {all && <div className="bi-verify" data-testid="bi-verify">
        <div className="bi-verify-k">לאמת לפני החלטה</div>
        <ul>{r.verify.map((v, i) => <li key={i}>{v.v1_item ? <button className="bi-link" onClick={() => ctx.openV1(v.v1_item)}>{v.text_he}</button> : v.text_he}</li>)}</ul>
        <div className="bi-fin-note">{r.financial.text_he}</div>
      </div>}
      <button className="bi-more" onClick={() => setAll(!all)} aria-expanded={all} data-testid="bi-why-toggle">
        {all ? "פחות" : `הצג את כל הנימוקים (${ranked.length}) ומה לאמת`}</button>
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
  const { x } = ctx;
  const a = x.analysis;
  const bc = x.bank_context;
  const d = x.documents;
  const [slips, setSlips] = useState(false);
  const openItems = x.discrepancies.filter((g) => g.open).length + x.risks.length;
  const docSources = Object.values(x.sources).filter((s) => s.kind === "document");
  const inc = x.income.borrowers;
  return (
    <div className="bi-support">
      <Panel title="חריגות ותנאים" testId="bi-evidence" defaultOpen={openItems > 0}
        summary={openItems ? <span className="warn-text">{openItems === 1 ? "פריט פתוח אחד" : `${openItems} פריטים פתוחים`}</span> : "אין פריטים פתוחים"}>
        {x.discrepancies.map((g, i) => (
          <div key={i} className={`bi-gap${g.open ? " open" : ""}`} data-testid="bi-discrepancy" data-kind={g.kind} data-open={g.open}>
            <div className="bi-gap-head"><b>{g.title_he}{g.first_name_he ? ` · ${g.first_name_he}` : ""}</b><span className="bi-tag warn">{g.status_he}</span></div>
            <div className="bi-gap-grid">
              <div><span>{g.kind === "income" ? "מוצהר" : "בבקשה"}</span><Val ctx={ctx} d={g.declared} /></div>
              <div><span>{g.kind === "income" ? "ממוצע בתלושים" : "בהצעת המחיר"}</span><Val ctx={ctx} d={g.documented} /></div>
              <div><span>הפרש</span><b className="ltr">{money(g.difference_ils != null ? Math.abs(g.difference_ils) : null)}{g.difference_pct != null ? ` · ${Math.abs(g.difference_pct).toFixed(1)}%` : ""}</b></div>
              {g.tolerance_pct != null && <div><span>סף סבולת</span><b className="ltr">{g.tolerance_pct}%</b></div>}
            </div>
            <p>{g.explanation_he}</p>
            <div className="bi-gap-act"><span>{g.action_he}</span><button className="bi-ghost" onClick={() => ctx.openV1(g.v1_item)} data-testid="bi-gap-open">פתיחה בסקירת המסמכים</button></div>
          </div>
        ))}
        {a.declared_alternative && <div className="bi-caution" data-testid="bi-declared-alt">על בסיס ההכנסה המוצהרת ({money(a.declared_alternative.income_ils)}) היחס המשולב היה{" "}
          <b className="ltr">{pct(a.declared_alternative.combined_dsr_pct)}</b> — הניתוח לא בוחר בנתון שמציג את הבקשה טוב יותר.</div>}
        {x.risks.length > 0 && <ul className="bi-risks" data-testid="bi-risks">
          {x.risks.map((r, i) => (
            <li key={i} className={`r-${r.kind}`}><span className="bi-tag warn">{r.who_he}</span>
              <span className="bi-risk-t"><b>{r.title_he}</b>{r.text_he ? ` — ${r.text_he}` : ""}</span>
              {r.source_ids.map((id) => <button key={id} className="bi-chipsrc" onClick={() => ctx.open(id)}><Mark kind={markOf(x.sources[id])} /></button>)}
              <button className="bi-link" onClick={() => ctx.openV1(r.v1_item)}>פתיחה</button></li>))}
        </ul>}
        <div className="bi-unknowns"><b>לא נבדק בהדגמה:</b> {x.unknowns.map((u) => `${u.label_he} — ${u.text_he}`).join(" · ")}</div>
      </Panel>

      <Panel title="התחייבויות ואובליגו" testId="bi-obligations" demo={bc.available}
        summary={bc.available ? <>החזרים קיימים <b className="ltr">{money(a.existing_debt.value)}</b> · אובליגו מנוצל <b className="ltr">{money(bc.exposure?.utilized.value)}</b></> : "אין נתוני הקשר בנקאי"}>
        <div className="bi-mini">
          <div><span>יחס החזר קיים</span><Val ctx={ctx} d={a.existing_dsr} /></div>
          <div><span>החזרים קיימים בחודש</span><Val ctx={ctx} d={a.existing_debt} /></div>
          <div><span>שיעור מימון מהאסמכתה</span><Val ctx={ctx} d={a.ltv} testId="bi-kpi-ltv" /></div>
          <div><span>הכנסה שנותרת אחרי החזרים (תיאורי)</span><Val ctx={ctx} d={a.remaining_after_debt} testId="bi-remaining" /></div>
          {bc.exposure && <div><span>אובליגו מאושר</span><Val ctx={ctx} d={bc.exposure.approved} testId="bi-exposure-approved" /></div>}
          {bc.exposure && <div><span>אובליגו מנוצל</span><Val ctx={ctx} d={bc.exposure.utilized} testId="bi-exposure-utilized" /></div>}
        </div>
        {!bc.available ? <div className="bi-empty">אין נתוני הקשר בנקאי להדגמה עבור {bc.missing_for.join(", ") || "המבקשים"} — ההתחייבויות הקיימות לא ידועות, והיחס כולל רק את ההלוואה המבוקשת.</div> : <>
          <div className="bi-src-note">מקור: {bc.fixture_ids.join(", ")} · נכון ל־<span className="ltr">{bc.observed_at}</span> · נתונים סינתטיים, לא נשלפו ממערכות הבנק{bc.missing_for.length ? ` · חסר עבור ${bc.missing_for.join(", ")}` : ""}</div>
          <table className="bi-table">
            <thead><tr><th>הלוואה קיימת</th><th>יתרת קרן</th><th>החזר חודשי</th><th>נותרו</th></tr></thead>
            <tbody>{bc.loans.length ? bc.loans.map((l) => (
              <tr key={l.id}><td>{l.type_he}<div className="tiny muted">{l.lender_he} · {l.owner_he}</div></td>
                <td><Val ctx={ctx} d={l.outstanding} /></td><td><Val ctx={ctx} d={l.monthly} testId="bi-loan-monthly" /></td><td className="ltr">{l.remaining_payments}</td></tr>))
              : <tr><td colSpan={4} className="muted">אין הלוואות קיימות בנתוני הדמו</td></tr>}</tbody>
          </table>
          <table className="bi-table">
            <thead><tr><th>מסגרת אשראי</th><th>מסגרת</th><th>מנוצל</th><th /></tr></thead>
            <tbody>{bc.credit_lines.map((l) => (
              <tr key={l.id}><td>{l.type_he}<div className="tiny muted">{l.owner_he}</div></td><td className="ltr">{money(l.limit_ils)}</td>
                <td><button className="bi-val" onClick={() => ctx.open(l.source_id)}><span className="bi-num ltr">{money(l.utilized_ils)}</span><Mark kind="demo" /></button></td>
                <td><div className="bi-meter"><span style={{ width: `${Math.min(100, (l.utilized_ils / (l.limit_ils || 1)) * 100)}%` }} /></div></td></tr>))}</tbody>
          </table>
          <ul className="bi-notes">
            <li>יתרות ומסגרות הן חשיפה (אובליגו), לא החזר חודשי — רק ההחזרים החודשיים נכנסים ליחס ההחזר.</li>
            {bc.card_spending.map((c) => <li key={c.source_id}>חיובי כרטיס ({c.owner_he}): <button className="bi-val" onClick={() => ctx.open(c.source_id)}><span className="bi-num ltr">{money(c.avg_monthly_ils)}</span><Mark kind="demo" /></button> בחודש — הוצאה שוטפת, לא נספרת כהחזר חוב.</li>)}
            {bc.events.map((e) => <li key={e.source_id} className={e.returned_checks_12m || e.arrears_12m ? "warn-text" : ""}>אירועי חשבון ב־12 חודשים ({e.owner_he}): {e.returned_checks_12m || e.arrears_12m ? e.detail_he.join(" ") : "ללא שיקים חוזרים, פיגורים או הגבלות"} <button className="bi-chipsrc" onClick={() => ctx.open(e.source_id)}><Mark kind="demo" /></button></li>)}
          </ul>
        </>}
        {a.illustrative_max_principal != null && <div className="bi-maxp" data-testid="bi-max-principal">להמחשה: סכום של עד <b className="ltr">{money(a.illustrative_max_principal)}</b> ל־{x.simulation.inputs.term_months} תשלומים משאיר את היחס המשולב בתוך {x.simulation.threshold_pct}% — אינו סכום מאושר.</div>}
      </Panel>

      <Panel title="נתונים ומקורות" testId="bi-data"
        summary={<>{inc[0]?.documented_avg.value != null ? <>הכנסה ממוצעת <b className="ltr">{money(inc[0].documented_avg.value)}</b>{inc[0].variability_pct != null ? <> · תנודתיות <span className="ltr">{pct(inc[0].variability_pct)}</span></> : null} · </> : null}
          {d.total} קבצים · {docSources.length} נתונים ממסמכים</>}>
        <div className="bi-data-cols">
          <div>
            <h3>הכנסה</h3>
            {inc.map((b) => (
              <div key={b.borrower_id} className="bi-income" data-testid="bi-income">
                <div className="bi-income-line"><b>{b.first_name_he}</b>
                  <span>ממוצע <Val ctx={ctx} d={b.documented_avg} testId="bi-income-avg" /></span>
                  <span>מוצהר <Val ctx={ctx} d={b.declared} /></span>
                  {b.variability_pct != null && <span>תנודתיות <b className="ltr">{pct(b.variability_pct)}</b></span>}
                  {b.months.length > 0 && <button className="bi-link" onClick={() => setSlips(!slips)} aria-expanded={slips} data-testid="bi-slips-toggle">{slips ? "הסתר תלושים" : "הצג תלושים"}</button>}
                </div>
                {slips && <div className="bi-months">{b.months.map((m) => (
                  <button key={m.period} className="bi-month" onClick={() => ctx.open(m.source_id)} disabled={!m.source_id} data-testid="bi-income-month" data-period={m.period}>
                    <span className="bi-month-k">{m.period_he}</span><span className="bi-month-v ltr">{money(m.net_ils)}</span>{m.source_id && <Mark kind={markOf(x.sources[m.source_id])} />}
                  </button>))}</div>}
              </div>
            ))}
            <h3>הבקשה</h3>
            <dl className="bi-dl">
              <div><dt>מטרה</dt><dd>{x.loan.purpose_he}{x.loan.note_he ? ` · ${x.loan.note_he}` : ""}</dd></div>
              <div><dt>מוצר</dt><dd>{x.loan.product_he}</dd></div>
              <div><dt>סכום</dt><dd><Val ctx={ctx} d={x.loan.amount} testId="bi-loan-amount" /></dd></div>
              <div><dt>תשלומים</dt><dd><Val ctx={ctx} d={x.loan.term} /></dd></div>
              {x.loan.asset && <div><dt>{x.loan.asset.label_he}</dt><dd><Val ctx={ctx} d={x.loan.asset.price} testId="bi-asset-price" /></dd></div>}
              {x.applicant.borrowers.map((b) => <div key={b.borrower_id}><dt>{b.name_he}</dt><dd>{b.profile_he || x.applicant.profile_label_he}
                {b.employer_document_source_id ? <> · <SrcLink ctx={ctx} id={b.employer_document_source_id}>{String(x.sources[b.employer_document_source_id].value_raw)}</SrcLink></> : b.employer_declared_he ? ` · ${b.employer_declared_he}` : ""}</dd></div>)}
            </dl>
            <h3>מסמכים</h3>
            <dl className="bi-dl" data-testid="bi-doc-detail">
              <div><dt>דרישות שהושלמו</dt><dd className="ltr">{d.progress ? `${d.progress.done}/${d.progress.total}` : "—"}</dd></div>
              <div><dt>קבצים שהתקבלו</dt><dd className="ltr">{d.total}</dd></div>
              <div><dt>התקבלו על ידך</dt><dd className="ltr">{d.accepted}/{d.total}</dd></div>
              <div><dt>שלב רשמי בבנק</dt><dd>{x.case.bank_stage.label_he} <Mark kind="demo" /></dd></div>
            </dl>
            {d.awaiting_decision > 0 && <button className="bi-link" onClick={() => ctx.openV1(null)}>{d.awaiting_decision === 1 ? "מסמך אחד ממתין" : `${d.awaiting_decision} מסמכים ממתינים`} לקבלה בסקירת המסמכים</button>}
          </div>
          <div>
            <h3>נתונים שחולצו ממסמכים</h3>
            {docSources.length ? <ul className="bi-evlist" data-testid="bi-evlist">{docSources.map((src) => (
              <li key={src.id}><button className="bi-evrow" onClick={() => ctx.open(src)} data-testid="bi-evrow" data-field={src.field}>
                <span>{src.label_he}</span><span className="ltr">{src.value_raw}</span><Mark kind={markOf(src)} /></button></li>))}</ul>
              : <div className="bi-empty">אין עדיין נתונים שחולצו ממסמכים.</div>}
          </div>
        </div>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- the customer draft: a preview, editing on demand
const DRAFT_NOTE: Record<string, string> = {
  complete_documentation: "אישור קבלה והעברה לבדיקת הבנק — ללא התחייבות לאישור.",
  missing_documents: "בקשה מדויקת לפריטים שחסרים בתיק.",
  financial_clarification: "בקשת הבהרה על פער מתועד — בלי הנימוק הפנימי.",
  conditional_financing: "חלופות להמחשה בלבד, עם התנאים במפורש. לא הצעה מחייבת.",
};

function DraftCard({ ctx, onToast }: { ctx: Ctx; onToast: (t: { text: string; tone: "ok" | "bad" }) => void }) {
  const { x } = ctx;
  const [kind, setKind] = useState<string | null>(x.recommended_draft);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [refs, setRefs] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState(false);
  const draft = x.drafts.find((d) => d.kind === kind) || x.drafts[0];
  if (!draft) return <section className="bi-card bi-draft"><h2>טיוטת מענה ללקוח</h2><div className="bi-empty">אין טיוטה מתאימה למצב התיק כרגע.</div></section>;
  const text = texts[draft.kind] ?? draft.message_he;
  const edited = texts[draft.kind] != null && texts[draft.kind] !== draft.message_he;
  const chosen = draft.attachments.filter((a) => refs[`${draft.kind}:${a.document_id}`]);
  const full = chosen.length ? `${text}\n\nמסמכים בתיק שההודעה מתייחסת אליהם: ${chosen.map((a) => a.label_he).join(" · ")}` : text;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(full);
      onToast({ text: "הטיוטה הועתקה. היא לא נשלחה ללקוח — השליחה נעשית בערוץ הבנק.", tone: "ok" });
    } catch {
      onToast({ text: "ההעתקה נחסמה בדפדפן. אפשר לסמן את הטקסט ולהעתיק ידנית.", tone: "bad" });
    }
  };
  return (
    <section className={`bi-card bi-draft${editing ? " editing" : ""}`} data-testid="bi-action">
      <div className="bi-draft-head">
        <h2>טיוטת מענה ללקוח</h2>
        {edited && <span className="bi-tag sim" data-testid="bi-draft-edited">נערך</span>}
      </div>
      <div className="bi-dtabs" role="tablist">
        {x.drafts.map((d) => (
          <button key={d.kind} role="tab" aria-selected={d.kind === draft.kind} className={d.kind === draft.kind ? "on" : ""} onClick={() => setKind(d.kind)}
            data-testid="bi-draft-tab" data-kind={d.kind}>{d.title_he}{d.kind === x.recommended_draft && <span className="bi-rec-dot" title="מומלץ למצב התיק" aria-label="מומלץ" />}</button>
        ))}
      </div>
      {!editing ? <>
        <button className="bi-preview" onClick={() => setEditing(true)} data-testid="bi-draft-preview" data-kind={draft.kind}>{text}</button>
        <div className="bi-dbar">
          <button className="bi-btn" onClick={() => setEditing(true)} data-testid="bi-draft-edit">עריכה</button>
          <button className="bi-ghost" onClick={copy} data-testid="bi-draft-copy">העתקה</button>
        </div>
      </> : <>
        <div className="bi-dnote">{DRAFT_NOTE[draft.kind]}</div>
        <textarea className="bi-dtext" value={text} onChange={(e) => setTexts({ ...texts, [draft.kind]: e.target.value })} dir="rtl"
          data-testid="bi-draft-text" data-kind={draft.kind} aria-label="טיוטת ההודעה ללקוח" autoFocus />
        {draft.attachments.length > 0 && <div className="bi-refs">
          <div className="bi-refs-k">הפניה למסמכים בתיק (רשות)</div>
          {draft.attachments.map((a) => {
            const k = `${draft.kind}:${a.document_id}`;
            return <label key={k} className={`bi-ref${refs[k] ? " on" : ""}`}><input type="checkbox" checked={!!refs[k]} onChange={() => setRefs({ ...refs, [k]: !refs[k] })} />{a.label_he}</label>;
          })}
        </div>}
        <div className="bi-dbar">
          <button className="bi-btn" onClick={copy} data-testid="bi-draft-copy">העתקה</button>
          <button className="bi-ghost" disabled={!edited} onClick={() => setTexts({ ...texts, [draft.kind]: draft.message_he })} data-testid="bi-draft-restore">שחזור הנוסח</button>
          <button className="bi-ghost" onClick={() => setEditing(false)} data-testid="bi-draft-collapse">סגירה</button>
        </div>
      </>}
      <div className="bi-dfoot">שום דבר לא נשלח מכאן. נוסח מתבנית קבועה — לא טקסט של מודל, בלי יחסי החזר או הערות פנימיות.</div>
    </section>
  );
}

// ---------------------------------------------------------------- the source drawer
const KIND_HE: Record<string, string> = { document: "נתון ממסמך", declared: "הצהרת לקוח", synthetic_bank: "נתון בנקאי סינתטי (דמו)",
  calculated: "חישוב", assumption: "הנחת הדגמה", missing: "נתון חסר" };

function SourceDrawer({ src, depth, ws, x, open, openV1, onBack, onClose }: Ctx & { src: IntelSource; depth: number; ws: Workspace; onBack: () => void; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const doc = src.kind === "document" ? ws.items.find((i): i is DocItem => i.kind === "document" && i.document_id === src.document_id) : undefined;
  const kind = markOf(src);
  return (
    <div className="bi-drawer-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className="bi-drawer" role="dialog" aria-label={`מקור: ${src.label_he}`} data-testid="bi-drawer" data-kind={src.kind} data-source={src.id}>
        <header className="bi-dr-head">
          {depth > 1 && <button className="bi-ghost" onClick={onBack} data-testid="bi-drawer-back">→ חזרה</button>}
          <Mark kind={kind} /><span className="bi-dr-kind">{KIND_HE[src.kind]}</span>
          <button className="bi-dr-x" onClick={onClose} aria-label="סגירה" data-testid="bi-drawer-close">×</button>
        </header>
        <div className="bi-dr-title">{src.label_he}</div>
        <div className="bi-dr-value ltr" data-testid="bi-drawer-value">{src.kind === "document" ? src.value_raw : fmt(src.value ?? null, src.unit, true)}</div>
        {src.kind === "document" && <>
          <div className={`bi-dr-witness${src.verified ? " ok" : ""}`}>{src.witness_he}{src.banker_reviewed ? " · המסמך התקבל על ידי הבנקאי" : ""}</div>
          <dl className="bi-dr-meta">
            <div><dt>קובץ</dt><dd className="ltr">{src.filename}</dd></div>
            <div><dt>סוג</dt><dd>{src.doc_type_he}{src.period_he ? ` · ${src.period_he}` : ""}</dd></div>
            <div><dt>בדיקת AI</dt><dd>{src.ai_verdict_he}</dd></div>
            <div><dt>החלטת בנקאי</dt><dd>{src.banker_status_he}</dd></div>
            <div><dt>מיקום</dt><dd>{src.has_location ? `עמוד ${src.page}, מסומן על המסמך` : "אין מיקום מדויק — מוצג העמוד בלבד"}</dd></div>
          </dl>
          <div className="bi-dr-actions">
            <button className="bi-btn" onClick={() => { onClose(); openV1(src.v1_item); }} data-testid="bi-drawer-v1">פתיחה בסקירת המסמכים</button>
            <a className="bi-ghost" href={`/api/documents/${src.document_id}/file`} target="_blank" rel="noreferrer">הקובץ המקורי ↗</a>
          </div>
          {doc ? <div className="bi-dr-viewer" data-testid="bi-drawer-evidence">
            <EvidenceViewer documentId={doc.document_id} facts={doc.ai.facts} page={src.page || 1} focus={src.field} dpi={130} quiet autoScroll={false} />
          </div> : <div className="bi-empty">המסמך אינו זמין בסקירה הנוכחית — לא מוצגת ראיה.</div>}
        </>}
        {src.kind === "declared" && <div className="bi-dr-box">
          <p><b>מקור:</b> {src.origin_he}</p>{src.note_he && <p><b>הערת הלקוח:</b> {src.note_he}</p>}
          <p className="muted">נתון שהלקוח מסר. אינו מאומת עד שמסמך תומך בו.</p></div>}
        {src.kind === "synthetic_bank" && <div className="bi-dr-box demo" data-testid="bi-drawer-synthetic">
          <p><b>מקור:</b> {src.source_he} · <span className="ltr">{src.fixture_id}</span></p>
          <p><b>נכון לתאריך:</b> <span className="ltr">{src.observed_at}</span></p>
          {src.detail_he && <p>{src.detail_he}</p>}
          <p className="muted">{src.note_he}</p></div>}
        {src.kind === "assumption" && <div className="bi-dr-box"><p>{src.note_he}</p></div>}
        {src.kind === "calculated" && <div className="bi-dr-box" data-testid="bi-drawer-formula">
          <div className="bi-formula">{src.formula_he}</div>
          {src.inputs && src.inputs.length > 0 && <table className="bi-table"><thead><tr><th>קלט</th><th>ערך</th><th>מקור</th></tr></thead>
            <tbody>{src.inputs.map((i, n) => {
              const s = i.source_id ? x.sources[i.source_id] : null;
              return <tr key={n}><td>{i.label_he}</td><td className="ltr">{fmt(i.value, i.unit, true)}</td>
                <td>{s ? <button className="bi-srclink" onClick={() => open(s)} data-testid="bi-drawer-input">{KIND_HE[s.kind]}<Mark kind={markOf(s)} /></button>
                  : <span className="bi-plain"><Mark kind={i.origin || "missing"} /> {MARK[i.origin || "missing"].label}</span>}</td></tr>;
            })}</tbody></table>}
          {src.note_he && <p className="muted">{src.note_he}</p>}
        </div>}
      </aside>
    </div>
  );
}
