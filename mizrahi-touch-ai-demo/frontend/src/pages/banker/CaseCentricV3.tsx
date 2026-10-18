import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, timeL, usePolling, type Datum, type DocItem, type IntelSource, type Intelligence, type MissingItem, type Workspace } from "../../api";
import { EvidenceViewer, FactList } from "../../components/EvidenceViewer";
import { scenarios as simulate, type Scenario } from "../../finance";
import { Loc, locList, locOf, Orig, tr, useLang } from "../../i18n";
import { Toast } from "./deskUi";
import { applicantName, enOf, fmt, loanNameEn, MARK, markOf, money, pct, scenarioSource, scLabel, Slider, SourceDrawer, years, type Ctx, type MarkKind } from "./IntelligenceV2";
import { ReplyWorkspace } from "./ReplyWorkspace";
import "./intelligence.css";
import "./casecentric.css";

/** Banker Case-Centric V3: the same intelligence payload as V2, read as one prepared case from top to bottom —
 *  recommendation, the application, the customer's documents, the financial analysis, the alternatives, the reasoning
 *  and the reply. Read-only like V2: every state change happens in the review workspace (V1). */
export function CaseCentricV3({ caseId, ws, openV1 }: { caseId: string; ws: Workspace; openV1: (item?: string | null) => void }) {
  const { en, t } = useLang();
  const intel = usePolling<Intelligence>(() => api.bankerIntelligence(caseId), [caseId],
    (x) => x.recommendation.state === "PROCESSING");
  const [stack, setStack] = useState<IntelSource[]>([]);
  const [doc, setDoc] = useState<DocItem | null>(null);
  const [toast, setToast] = useState<{ text: string; tone: "ok" | "bad" } | null>(null);
  const clearToast = useCallback(() => setToast(null), []);
  const scroller = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLElement>(null);
  const [pinned, setPinned] = useState(false);
  useEffect(() => { setStack([]); setDoc(null); scroller.current?.scrollTo(0, 0); }, [caseId]);
  const x = intel.data && intel.data.case_id === caseId ? intel.data : null;
  useEffect(() => {
    if (!head.current || !scroller.current) return;
    const io = new IntersectionObserver(([e]) => setPinned(!e.isIntersecting), { root: scroller.current, threshold: 0 });
    io.observe(head.current);
    return () => io.disconnect();
  }, [x != null]);
  const open = useCallback((s: string | IntelSource | null | undefined) => {
    if (!s || !x) return;
    const src = typeof s === "string" ? x.sources[s] : s;
    if (src) setStack((prev) => [...prev, src]);
  }, [x]);
  if (!x) return <div className="desk-loading">{intel.error
    ? (en ? <>We couldn't load the case. <button className="link" onClick={intel.reload}>Try again</button></>
      : <>לא הצלחנו לטעון את התיק. <button className="link" onClick={intel.reload}>ניסיון חוזר</button></>)
    : (en ? <><span className="spinner" /> Jeen is preparing the case…</> : <><span className="spinner" /> Jeen מכין את התיק…</>)}</div>;
  const ctx: Ctx = { x, open, openV1 };
  const go = (id: string) => scroller.current?.querySelector(`#${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  return (
    <div className="cc-scroll" ref={scroller} data-testid="cc-root" data-case={caseId}>
      <StickyBar ctx={ctx} shown={pinned} />
      <div className="cc-page">
        <CaseHeader ctx={ctx} innerRef={head} />
        <KeyFigures ctx={ctx} />
        <CaseDetails ctx={ctx} />
        <Documents ctx={ctx} ws={ws} onOpen={setDoc} />
        <Financial ctx={ctx} />
        <Alternatives ctx={ctx} />
        <Recommendation ctx={ctx} go={go} />
        <Reasoning ctx={ctx} />
        <ReplyWorkspace key={x.case_id} ctx={ctx} onToast={setToast} />
        <p className="cc-foot">{locOf(x, "disclaimer_he")} · {t("עודכן", "Updated")} <span className="ltr">{timeL(x.generated_at)}</span></p>
      </div>
      {stack.length > 0 && <SourceDrawer src={stack[stack.length - 1]} depth={stack.length} ws={ws} {...ctx}
        onBack={() => setStack((s) => s.slice(0, -1))} onClose={() => setStack([])} />}
      {doc && <DocDrawer doc={doc} ctx={ctx} onClose={() => setDoc(null)} />}
      <Toast message={toast} onClose={clearToast} />
    </div>
  );
}

// ---------------------------------------------------------------- shared bits
const TONE: Record<string, "ok" | "warn" | "neutral" | "bad"> = { READY_FOR_CREDIT_REVIEW: "ok", PREPARATION_CONFIRMED: "ok",
  CLARIFICATION_REQUIRED: "warn", DOCUMENTS_INCOMPLETE: "warn", NO_DOCUMENTS: "neutral", PROCESSING: "neutral", ERROR: "bad" };
/** A short title per recommendation state; the backend's own sentence follows it as the explanation. */
const TITLE: Record<string, string> = {
  READY_FOR_CREDIT_REVIEW: "מומלץ להתקדם בתהליך ההלוואה",
  PREPARATION_CONFIRMED: "הכנת התיק אושרה, אפשר להתקדם לבחינת האשראי",
  CLARIFICATION_REQUIRED: "נדרש בירור לפני בחינת האשראי",
  DOCUMENTS_INCOMPLETE: "נדרשת השלמת מסמכים לפני בחינת האשראי",
  NO_DOCUMENTS: "טרם התקבלו מסמכים בתיק",
  PROCESSING: "Jeen עדיין בודק את המסמכים",
  ERROR: "בדיקת המסמכים לא הושלמה",
};
const TITLE_EN: Record<string, string> = {
  READY_FOR_CREDIT_REVIEW: "Recommended: proceed with the loan process",
  PREPARATION_CONFIRMED: "Case preparation confirmed; you can proceed to credit review",
  CLARIFICATION_REQUIRED: "Clarification needed before credit review",
  DOCUMENTS_INCOMPLETE: "Documents need completing before credit review",
  NO_DOCUMENTS: "No documents received in the case yet",
  PROCESSING: "Jeen is still checking the documents",
  ERROR: "The document check didn't complete",
};
const loanParts = (x: Intelligence) => [
  { k: "purpose", t: x.loan.purpose_he ? tr(`הלוואה ל${x.loan.purpose_he}`, loanNameEn(x)) : x.loan.product_he && locOf(x.loan, "product_he") },
  { k: "amount", t: x.loan.amount.value != null ? money(x.loan.amount.value) : null },
  { k: "term", t: x.loan.term.value != null ? tr(`${x.loan.term.value} תשלומים`, `${x.loan.term.value} payments`) : null },
].filter((p): p is { k: string; t: string } => !!p.t);
const loanLine = (x: Intelligence) => loanParts(x).map((p) => p.t).join(" · ");
const joinEn = (items: string[]) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);

/** The recommendation sentence in English. The documents-incomplete headline lists the missing items in one Hebrew
 *  sentence the catalogue can't split, so English rebuilds it from the items' own English; anything else without
 *  English stays the Hebrew original. */
function headlineEn(x: Intelligence): string | undefined {
  const r = x.recommendation;
  const own = enOf(r, "headline_he");
  if (own || r.state !== "DOCUMENTS_INCOMPLETE") return own;
  const items = [...x.documents.missing, ...x.documents.corrections.slice(0, 2)].map((m) => enOf(m, "item_he") || enOf(m, "title_he"));
  if (items.some((i) => !i)) return undefined;
  return "Documents need completing before a sufficient financial picture can be formed." + (items.length ? ` Missing: ${joinEn(items as string[])}.` : "");
}

/** A server text in English when the catalogue has it; otherwise the original, marked as such (model or document wording). */
function LocOrig({ he, en, block }: { he?: string | null; en?: string | null; block?: boolean }) {
  const { en: english } = useLang();
  return english && en ? <>{en}</> : <Orig text={he} block={block} />;
}

function Card({ id, title, sub, aside, children, testId, tone }: { id: string; title: string; sub?: ReactNode; aside?: ReactNode; children: ReactNode; testId: string; tone?: string }) {
  return (
    <section className={`cc-card${tone ? ` t-${tone}` : ""}`} id={id} data-testid={testId}>
      <header className="cc-card-head">
        <div><h2>{title}</h2>{sub && <p className="cc-sub">{sub}</p>}</div>
        {aside && <div className="cc-card-aside">{aside}</div>}
      </header>
      <div className="cc-card-body">{children}</div>
    </section>
  );
}

/** A number that opens its source. The provenance is a quiet dot and a tooltip, not a pill next to every value. */
function Num({ ctx, d, testId, exact }: { ctx: Ctx; d?: Datum | null; testId?: string; exact?: boolean }) {
  const { t } = useLang();
  const src = d?.source_id ? ctx.x.sources[d.source_id] : null;
  if (!d || d.value == null) return <span className="cc-num none" data-testid={testId}>{t("לא זמין", "Not available")}</span>;
  const k = markOf(src);
  return (
    <button className={`cc-num k-${k}`} onClick={() => ctx.open(src)} disabled={!src} data-testid={testId || "cc-datum"}
      data-source={d.source_id || ""} data-kind={src?.kind || "none"} title={src ? t(`${MARK[k].title}, לחצו להצגת המקור`, `${MARK[k].title}. Click to show the source`) : undefined}>
      {d.unit === "months" ? <span>{fmt(d.value, d.unit, exact)}</span> : <span className="ltr">{fmt(d.value, d.unit, exact)}</span>}
    </button>
  );
}

function Tag({ kind, children }: { kind: MarkKind; children?: ReactNode }) {
  useLang();
  return <span className={`cc-tag k-${kind}`} title={MARK[kind].title} data-mark={kind}>{children ?? MARK[kind].label}</span>;
}

function SrcText({ ctx, id, children }: { ctx: Ctx; id?: string | null; children?: ReactNode }) {
  useLang();
  const s = id ? ctx.x.sources[id] : null;
  if (!s) return <>{children}</>;
  return <button className="cc-srctext" onClick={() => ctx.open(s)} title={MARK[markOf(s)].title} data-testid="cc-srclink" data-kind={s.kind}>
    {children ?? (s.value_raw != null ? <Orig text={String(s.value_raw)} /> : locOf(s, "label_he"))}</button>;
}

function Toggle({ open, onClick, children, testId }: { open: boolean; onClick: () => void; children: ReactNode; testId: string }) {
  return <button className="cc-toggle" onClick={onClick} aria-expanded={open} data-testid={testId}>{children}<span aria-hidden className="cc-chev">{open ? "▴" : "▾"}</span></button>;
}

// ---------------------------------------------------------------- A · case header and recommendation
function CaseHeader({ ctx, innerRef }: { ctx: Ctx; innerRef: React.RefObject<HTMLElement> }) {
  const { t } = useLang();
  const { x } = ctx;
  const r = x.recommendation;
  const tone = TONE[r.state] || "neutral";
  return (
    <header className="cc-head" ref={innerRef} data-testid="cc-head">
      <div className="cc-head-id">
        <div className="cc-head-top">
          <div className="cc-kicker">{t("בקשת הלוואה · תיק", "Loan application · case")} <span className="ltr">{x.case.display_number}</span></div>
          <span className={`cc-status s-${tone}`} data-testid="cc-status">{locOf(r.documentation, "status_he")}</span>
        </div>
        <h1 data-testid="cc-name">{applicantName(x)}</h1>
        <div className="cc-loanline" data-testid="cc-loanline">{loanParts(x).map((p, i) => (
          <Fragment key={p.k}>{i > 0 && <span className="cc-loan-sep"> · </span>}<span className={`cc-loan-${p.k}`}>{p.t}</span></Fragment>))}</div>
      </div>
      <div className="cc-head-act">
        <button className="cc-primary" onClick={() => ctx.openV1(r.next_action.v1_item)} data-testid="cc-primary">
          {t("מעבר לטיפול בתיק", "Go to case handling")} <span aria-hidden>{t("←", "→")}</span></button>
        <div className="cc-next" data-testid="cc-next">{t("הצעד הבא:", "Next step:")} {r.next_action.detail_he ? locOf(r.next_action, "detail_he") : locOf(r.next_action, "label_he")}</div>
      </div>
    </header>
  );
}

function StickyBar({ ctx, shown }: { ctx: Ctx; shown: boolean }) {
  const { t } = useLang();
  const { x } = ctx;
  const r = x.recommendation;
  return (
    <div className={`cc-sticky${shown ? " on" : ""}`} aria-hidden={!shown} data-testid="cc-sticky">
      <div className="cc-sticky-in">
        <b>{applicantName(x)}</b><span className="cc-sticky-l">{loanLine(x)}</span>
        <span className={`cc-status s-${TONE[r.state] || "neutral"}`}>{locOf(r.documentation, "status_he")}</span>
        <button className="cc-primary sm" tabIndex={shown ? 0 : -1} onClick={() => ctx.openV1(r.next_action.v1_item)}>{t("מעבר לטיפול בתיק ←", "Go to case handling →")}</button>
      </div>
    </div>
  );
}

function Recommendation({ ctx, go }: { ctx: Ctx; go: (id: string) => void }) {
  const { t } = useLang();
  const { x } = ctx;
  const r = x.recommendation;
  const tone = TONE[r.state] || "neutral";
  const d = x.documents;
  const attention: { text: string; target: string; testId: string }[] = [];
  for (const g of x.discrepancies.filter((q) => q.open))
    attention.push({ text: `${locOf(g, "title_he")}${g.first_name_he ? ` · ${locOf(g, "first_name_he")}` : ""}`, target: "cc-fin", testId: "cc-attn-gap" });
  if (d.missing.length) attention.push({ text: d.missing.length === 1 ? t(`חסר בתיק: ${d.missing[0].title_he}`, `Missing from the case: ${locOf(d.missing[0], "title_he")}`)
    : t(`${d.missing.length} פריטים חסרים בתיק`, `${d.missing.length} items missing from the case`),
    target: "cc-docs", testId: "cc-attn-missing" });
  if (d.corrections.length) attention.push({ text: d.corrections.length === 1 ? t("מסמך אחד הוחזר לתיקון אצל הלקוח", "One document was returned to the customer for correction")
    : t(`${d.corrections.length} מסמכים הוחזרו לתיקון אצל הלקוח`, `${d.corrections.length} documents were returned to the customer for correction`),
    target: "cc-docs", testId: "cc-attn-correction" });
  for (const k of x.risks.filter((q) => q.kind === "finding")) attention.push({ text: locOf(k, "title_he"), target: "cc-why", testId: "cc-attn-finding" });
  for (const e of x.bank_context.events.filter((q) => q.returned_checks_12m || q.arrears_12m || q.restrictions_he.length))
    attention.push({ text: t(`אירוע חשבון בהקשר הבנקאי (${e.owner_he}), לאימות במערכות הבנק`, `Account event in the bank context (${locOf(e, "owner_he")}), to verify in the bank's systems`),
      target: "cc-fin", testId: "cc-attn-event" });
  return (
    <section className={`cc-rec t-${tone}`} data-testid="cc-rec" data-state={r.state}>
      <div className="cc-rec-in">
        <div className="cc-rec-top"><span className="cc-jeen">{t("המלצת Jeen", "Jeen's recommendation")}</span></div>
        <span className="cc-rec-mark" aria-hidden>{tone === "ok" ? "✓" : tone === "neutral" ? "…" : "!"}</span>
        <h2 data-testid="cc-rec-title">{t(TITLE[r.state], TITLE_EN[r.state]) || locOf(r.documentation, "status_he")}</h2>
        <p data-testid="cc-rec-text"><Loc he={r.headline_he} en={headlineEn(x)} /></p>
        <RecBasis ctx={ctx} />
        {attention.length > 0 && <ul className="cc-attn" data-testid="cc-attention">
          {attention.map((a, i) => <li key={i} data-testid={a.testId}><span>{a.text}</span>
            <button className="cc-link" onClick={() => go(a.target)}>{t("לפרטים", "Details")}</button></li>)}
        </ul>}
        <div className="cc-rec-nb" data-testid="cc-rec-disclaimer">{t("המלצה לבנקאי בלבד, אינה אישור אשראי", "A recommendation for the banker only, not a credit approval")}</div>
      </div>
    </section>
  );
}

/** What the conclusion rests on: the document requirements, the income basis and the combined ratio, each in its true state. */
function RecBasis({ ctx }: { ctx: Ctx }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const p = x.documents.progress;
  const rows = x.income.borrowers;
  const a = x.analysis;
  const thr = x.simulation.threshold_pct;
  const docsOk = !!p && p.total > 0 && p.done >= p.total;
  const income = rows.some((q) => q.unresolved_discrepancy) ? { v: t("פער פתוח", "Open gap"), t: "warn" }
    : rows.some((q) => q.quality === "declared") ? { v: t("מוצהרת בלבד", "Declared only"), t: "warn" }
      : rows.length && rows.every((q) => q.quality === "verified") ? { v: t("מאומתת בתלושים", "Verified on payslips"), t: "ok" } : { v: t("חלקית", "Partial"), t: "warn" };
  const dsr = a.combined_dsr?.value;
  return (
    <dl className="cc-basis" data-testid="cc-rec-basis">
      <div className={docsOk ? "ok" : "warn"}><dt>{t("דרישות מסמכים", "Document requirements")}</dt>
        <dd>{p && p.total ? (docsOk ? (en ? <><span className="ltr">{p.done}/{p.total}</span> complete</> : <><span className="ltr">{p.done}/{p.total}</span> הושלמו</>)
          : (en ? <>{p.done} of {p.total}</> : <>{p.done} מתוך {p.total}</>)) : "-"}</dd></div>
      <div className={income.t}><dt>{t("בסיס ההכנסה", "Income basis")}</dt><dd>{income.v}</dd></div>
      <div className={dsr == null ? "" : dsr > thr || a.availability !== "full" ? "warn" : "ok"}><dt>{t("יחס החזר כולל", "Total DSR")}</dt>
        <dd><Num ctx={ctx} d={a.combined_dsr} /> <span className="cc-basis-n">{a.availability === "provisional" ? t("זמני", "provisional") : a.availability === "partial" ? t("חלקי", "partial") : t(`עד ${thr}%`, `up to ${thr}%`)}</span></dd></div>
    </dl>
  );
}

function KeyFigures({ ctx }: { ctx: Ctx }) {
  const { t } = useLang();
  const { x } = ctx;
  const a = x.analysis;
  const thr = x.simulation.threshold_pct;
  const rows = x.income.borrowers;
  const months = rows.reduce((n, r) => n + r.months.filter((m) => m.net_ils != null).length, 0);
  const incomeNote = a.availability === "provisional" ? t("זמני, הנתון הנמוך מבין ההצהרה לתלושים", "Provisional: the lower of the declaration and the payslips")
    : rows.some((r) => r.quality === "declared") ? t("כולל הכנסה מוצהרת שטרם אומתה", "Includes declared income not yet verified")
      : rows.length && rows.every((r) => r.quality === "verified") ? t(`ממוצע ${months} תלושי שכר מאומתים`, `Average of ${months} verified payslips`) : locOf(a, "status_he");
  const dsr = a.combined_dsr?.value;
  return (
    <div className="cc-figs" data-testid="cc-figures">
      <div className="cc-fig" data-testid="cc-fig-income"><div className="cc-fig-k">{t("הכנסה חודשית נטו", "Net monthly income")}</div>
        <div className="cc-fig-v"><Num ctx={ctx} d={a.income} /></div><div className="cc-fig-n">{incomeNote}</div></div>
      <div className="cc-fig" data-testid="cc-fig-payment"><div className="cc-fig-k">{t("החזר חודשי משוער", "Estimated monthly payment")}</div>
        <div className="cc-fig-v"><Num ctx={ctx} d={a.proposed_payment} /></div>
        <div className="cc-fig-n">{x.loan.term.value ? t(`ל־${x.loan.term.value} תשלומים · ריבית להמחשה ${x.simulation.inputs.annual_rate_pct.toFixed(1)}%`,
          `Over ${x.loan.term.value} payments · illustrative rate ${x.simulation.inputs.annual_rate_pct.toFixed(1)}%`) : t("אין בבקשה מספר תשלומים", "The application has no number of payments")}</div></div>
      <div className={`cc-fig${dsr != null && dsr > thr ? " warn" : ""}`} data-testid="cc-fig-dsr"><div className="cc-fig-k">{t("יחס החזר כולל בסימולציה", "Total DSR (simulated)")}</div>
        <div className="cc-fig-v"><Num ctx={ctx} d={a.combined_dsr} /></div>
        <div className="cc-fig-n">{a.combined_dsr?.value == null ? locOf(a, "status_he")
          : t(`סף משוער: עד ${thr}%${a.availability === "provisional" ? " · זמני" : a.availability === "partial" ? " · ניתוח חלקי" : ""}`,
            `Assumed threshold: up to ${thr}%${a.availability === "provisional" ? " · provisional" : a.availability === "partial" ? " · partial analysis" : ""}`)}</div></div>
    </div>
  );
}

// ---------------------------------------------------------------- B · customer and loan
function KV({ k, children, testId }: { k: string; children: ReactNode; testId?: string }) {
  return <div className="cc-kv" data-testid={testId}><dt>{k}</dt><dd>{children}</dd></div>;
}

function CaseDetails({ ctx }: { ctx: Ctx }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const [more, setMore] = useState(false);
  const many = x.applicant.borrowers.length > 1;
  return (
    <Card id="cc-details" title={t("פרטי הלקוח והבקשה", "Customer and application details")} testId="cc-details">
      <div className="cc-group-k">{x.applicant.entity === "company" ? t("החברה המבקשת", "Applicant company") : many ? t("המבקשים", "Applicants") : t("הלקוח", "Customer")}</div>
      {x.applicant.company && <dl className="cc-kvs">
        <KV k={t("שם החברה", "Company name")}><Loc he={x.applicant.company.name_he} en={enOf(x.applicant.company, "name_he")} /></KV>
        <KV k={t("מספר חברה", "Company number")}><span className="ltr">{x.applicant.company.company_number}</span></KV>
      </dl>}
      {x.applicant.borrowers.map((b) => (
        <dl key={b.borrower_id} className="cc-kvs" data-testid="cc-borrower">
          <KV k={t("שם מלא", "Full name")}><b><Loc he={b.name_he} en={enOf(b, "name_he")} /></b>{many && <span className="cc-role">{locOf(b, "role_he")}</span>}</KV>
          <KV k={t("פרופיל", "Profile")}>{b.profile_he ? <Loc he={b.profile_he} en={enOf(b, "profile_he")} />
            : x.applicant.profile_label_he ? <Loc he={x.applicant.profile_label_he} en={enOf(x.applicant, "profile_label_he")} /> : "-"}</KV>
          <KV k={t("מעסיק / עסק", "Employer / business")}>{b.employer_document_source_id ? <SrcText ctx={ctx} id={b.employer_document_source_id} />
            : b.employer_declared_he ? <><Loc he={b.employer_declared_he} en={enOf(b, "employer_declared_he")} /> <Tag kind="declared" /></> : "-"}</KV>
        </dl>
      ))}
      <div className="cc-group-k">{t("הבקשה", "Application")}</div>
      <dl className="cc-kvs">
        <KV k={t("סוג הלוואה", "Loan type")}>{x.loan.product_he ? <Loc he={x.loan.product_he} en={enOf(x.loan, "product_he")} /> : "-"}</KV>
        <KV k={t("מטרה", "Purpose")}>{x.loan.purpose_he ? <Loc he={x.loan.purpose_he} en={enOf(x.loan, "purpose_he")} /> : "-"}</KV>
        <KV k={t("סכום מבוקש", "Requested amount")} testId="cc-loan-amount"><Num ctx={ctx} d={x.loan.amount} /></KV>
        <KV k={t("תקופה מבוקשת", "Requested term")} testId="cc-loan-term"><Num ctx={ctx} d={x.loan.term} />{x.loan.term.value ? <span className="cc-muted"> · {years(x.loan.term.value)}</span> : null}</KV>
        {x.loan.asset && <KV k={locOf(x.loan.asset, "label_he")} testId="cc-asset-price"><Num ctx={ctx} d={x.loan.asset.price} /></KV>}
        {x.loan.asset?.subject_source_id && <KV k={t("הפריט באסמכתה", "Item on the proof")}><SrcText ctx={ctx} id={x.loan.asset.subject_source_id} /></KV>}
        {x.applicant.co_borrowers.length > 0 && <KV k={t("לווים נוספים", "Co-borrowers")}>{locList(x.applicant, "co_borrowers").join(", ")}</KV>}
      </dl>
      {x.loan.note_he && (en ? <p className="cc-quote">“<Loc he={x.loan.note_he} en={enOf(x.loan, "note_he")} />” <span className="cc-muted">from the application</span></p>
        : <p className="cc-quote">„{x.loan.note_he}” <span className="cc-muted">מתוך הבקשה</span></p>)}
      <Toggle open={more} onClick={() => setMore(!more)} testId="cc-details-more">{more ? t("פחות פרטים", "Fewer details") : t("פרטים נוספים", "More details")}</Toggle>
      {more && <dl className="cc-kvs cc-kvs-quiet" data-testid="cc-details-extra">
        <KV k={t("מספר תיק", "Case number")}><span className="ltr">{x.case.display_number}</span></KV>
        <KV k={t("מזהה בקשה", "Application ID")}><span className="ltr">{x.case_id}</span></KV>
        <KV k={t("בנקאי מטפל", "Handling banker")}><Loc he={x.case.banker.name_he} en={enOf(x.case.banker, "name_he")} /></KV>
        <KV k={t("שלב רשמי בבנק", "Official bank stage")}><Loc he={x.case.bank_stage.label_he} en={enOf(x.case.bank_stage, "label_he")} /> <Tag kind="demo" /></KV>
        {x.case.submitted_at && <KV k={t("הוגשה", "Submitted")}><span className="ltr">{timeL(x.case.submitted_at)}</span></KV>}
      </dl>}
    </Card>
  );
}

// ---------------------------------------------------------------- C · the customer's documents
function Documents({ ctx, ws, onOpen }: { ctx: Ctx; ws: Workspace; onOpen: (d: DocItem) => void }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const d = x.documents;
  const [reqs, setReqs] = useState(false);
  const [old, setOld] = useState(false);
  const docs = ws.items.filter((i): i is DocItem => i.kind === "document");
  const active = docs.filter((i) => !i.replaced_by);
  const replaced = docs.filter((i) => i.replaced_by);
  const missing = ws.items.filter((i): i is MissingItem => i.kind === "missing");
  const p = d.progress;
  const waiting = d.missing.length + d.corrections.length;
  const unmet = d.requirements.filter((q) => !q.satisfied);
  const primary = !p || !p.total ? { text: locOf(d, "state_he"), tone: "neutral" }
    : waiting ? { text: t(`התקבלו ${p.done} מתוך ${p.total} דרישות · ${waiting === 1 ? "פריט אחד ממתין" : `${waiting} פריטים ממתינים`} ללקוח`,
      `${p.done} of ${p.total} requirements received · ${waiting === 1 ? "one item is" : `${waiting} items are`} waiting on the customer`), tone: "warn" }
      : p.done >= p.total ? { text: t("כל המסמכים הנדרשים התקבלו ונבדקו ב-AI", "All the required documents were received and checked by AI"), tone: "ok" }
        : { text: t(`${p.done} מתוך ${p.total} דרישות הושלמו · ${unmet.map((q) => `${q.title_he}, ${q.state_he}`).join(" · ")}`,
          `${p.done} of ${p.total} requirements complete · ${unmet.map((q) => `${locOf(q, "title_he")}, ${locOf(q, "state_he")}`).join(" · ")}`), tone: "warn" };
  const banker = d.open_findings ? t(`${d.open_findings === 1 ? "ממצא אחד" : `${d.open_findings} ממצאים`} לשיקול דעתך`,
    `${d.open_findings === 1 ? "One finding" : `${d.open_findings} findings`} for your judgment`)
    : d.awaiting_decision ? t(`${d.awaiting_decision === 1 ? "מסמך אחד נבדק ב-AI וממתין" : `${d.awaiting_decision} מסמכים נבדקו ב-AI וממתינים`} לקבלה פורמלית שלך`,
      `${d.awaiting_decision === 1 ? "One document was checked by AI and awaits" : `${d.awaiting_decision} documents were checked by AI and await`} your formal acceptance`)
      : d.total && d.accepted >= d.total ? t("כל המסמכים התקבלו על ידך", "You accepted all the documents") : null;
  return (
    <Card id="cc-docs" title={t("מסמכים שצירף הלקוח", "Documents the customer attached")} testId="cc-docs"
      aside={p && p.total ? <span className={`cc-count t-${primary.tone}`} data-testid="cc-doc-count"><span className="ltr">{p.done}/{p.total}</span> {t("דרישות", "requirements")}</span> : undefined}>
      <div className="cc-docstate" data-testid="cc-docstate">
        <div className={`cc-docstate-main t-${primary.tone}`} data-testid="cc-docstate-main">{primary.text}</div>
        {banker && <div className="cc-docstate-sub" data-testid="cc-docstate-banker"><b>{t("בדיקת בנקאי:", "Banker check:")}</b> {banker}
          {d.awaiting_decision > 0 && <button className="cc-link" onClick={() => ctx.openV1(null)}>{t("לסקירת המסמכים", "To the document review")}</button>}</div>}
      </div>
      <div className="cc-gallery" data-testid="cc-gallery">
        {active.map((i) => <DocTile key={i.document_id} doc={i} onOpen={() => onOpen(i)} />)}
        {missing.map((m) => (
          <button key={m.id} className="cc-doc missing" onClick={() => ctx.openV1(m.id)} data-testid="cc-missing" title={t("פתיחה בסקירת המסמכים", "Open in the document review")}>
            <span className="cc-thumb"><span className="cc-thumb-miss">{t("חסר", "Missing")}</span></span>
            <span className="cc-doc-meta"><span className="cc-doc-name"><Loc he={m.title_he} en={enOf(m, "title_he")} /></span>
              <span className="cc-doc-st t-warn">{m.open_request ? t("נשלחה בקשה ללקוח", "Request sent to the customer") : <Loc he={m.status_he} en={enOf(m, "status_he")} />}</span></span>
          </button>
        ))}
        {!active.length && !missing.length && <div className="cc-empty">{t("טרם הועלו מסמכים לתיק.", "No documents have been uploaded to the case yet.")}</div>}
      </div>
      <div className="cc-docfoot">
        <Toggle open={reqs} onClick={() => setReqs(!reqs)} testId="cc-reqs-toggle">{t("דרישות המסמכים לפי מדיניות ההלוואה", "Document requirements under the loan policy")}</Toggle>
        {replaced.length > 0 && <Toggle open={old} onClick={() => setOld(!old)} testId="cc-replaced-toggle">
          {en ? (replaced.length === 1 ? "One replaced document" : `${replaced.length} replaced documents`)
            : (replaced.length === 1 ? "מסמך אחד שהוחלף" : `${replaced.length} מסמכים שהוחלפו`)}</Toggle>}
      </div>
      {reqs && <ul className="cc-reqs" data-testid="cc-reqs">{d.requirements.map((q, i) => (
        <li key={i} className={q.satisfied ? "ok" : "miss"}><span className="cc-req-i" aria-hidden>{q.satisfied ? "✓" : "•"}</span>
          <span><Loc he={q.title_he} en={enOf(q, "title_he")} /></span><span className="cc-muted"><Loc he={q.state_he} en={enOf(q, "state_he")} /></span></li>))}</ul>}
      {old && <div className="cc-gallery quiet" data-testid="cc-replaced">{replaced.map((i) => <DocTile key={i.document_id} doc={i} onOpen={() => onOpen(i)} />)}</div>}
    </Card>
  );
}

function DocTile({ doc, onOpen }: { doc: DocItem; onOpen: () => void }) {
  const { t } = useLang();
  const [failed, setFailed] = useState(false);
  const ext = (doc.filename.split(".").pop() || "").toUpperCase();
  return (
    <button className={`cc-doc${doc.replaced_by ? " old" : ""}`} onClick={onOpen} data-testid="cc-doc" data-doc={doc.document_id} title={t(`פתיחת ${doc.filename}`, `Open ${doc.filename}`)}>
      <span className="cc-thumb">
        {failed ? <span className="cc-thumb-icon" data-testid="cc-thumb-fallback">{ext || t("קובץ", "File")}</span>
          : <img src={`/api/documents/${doc.document_id}/pages/1.png?dpi=60`} alt={t(`עמוד ראשון, ${doc.doc_type_he}`, `First page, ${locOf(doc, "doc_type_he")}`)} loading="lazy" onError={() => setFailed(true)} data-testid="cc-thumb" />}
        {doc.pages > 1 && <span className="cc-thumb-pages">{t(`${doc.pages} עמ׳`, `${doc.pages} pp.`)}</span>}
      </span>
      <span className="cc-doc-meta">
        <span className="cc-doc-name"><Loc he={doc.doc_type_he} en={enOf(doc, "doc_type_he")} />{doc.period_he ? ` · ${locOf(doc, "period_he")}` : ""}</span>
        <span className="cc-doc-file ltr">{doc.filename}</span>
        <span className={`cc-doc-st t-${doc.ai.tone}`}>{doc.replaced_by ? t("הוחלף במסמך חדש", "Replaced by a new document") : `AI: ${locOf(doc.ai, "verdict_he")}`}</span>
        {!doc.replaced_by && <span className="cc-doc-bk"><Loc he={doc.banker.status_he} en={enOf(doc.banker, "status_he")} /></span>}
      </span>
    </button>
  );
}

function DocDrawer({ doc, ctx, onClose }: { doc: DocItem; ctx: Ctx; onClose: () => void }) {
  const { t } = useLang();
  const [focus, setFocus] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const pick = (f: string) => {
    setFocus(f);
    const p = doc.ai.facts.find((q) => q.field === f)?.evidence?.page;
    if (p) setPage(p);
  };
  const attentionEn = enOf(doc.ai, "attention_he") as unknown as (string | null)[] | undefined;
  return (
    <div className="bi-drawer-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className="bi-drawer cc-docdrawer" role="dialog" aria-label={t(`מסמך: ${doc.filename}`, `Document: ${doc.filename}`)} data-testid="cc-docdrawer" data-doc={doc.document_id}>
        <header className="bi-dr-head">
          <span className="bi-dr-kind">{t("מסמך שצירף הלקוח", "Document the customer attached")}</span>
          <button className="bi-dr-x" onClick={onClose} aria-label={t("סגירה", "Close")} data-testid="cc-docdrawer-close">×</button>
        </header>
        <div className="bi-dr-title"><Loc he={doc.doc_type_he} en={enOf(doc, "doc_type_he")} />{doc.period_he ? ` · ${locOf(doc, "period_he")}` : ""}</div>
        <div className="cc-muted ltr">{doc.filename}</div>
        <dl className="bi-dr-meta">
          <div><dt>{t("בדיקת AI", "AI check")}</dt><dd className={`cc-doc-st t-${doc.ai.tone}`}><Loc he={doc.ai.verdict_he} en={enOf(doc.ai, "verdict_he")} /></dd></div>
          <div><dt>{t("החלטת בנקאי", "Banker decision")}</dt><dd><Loc he={doc.banker.status_he} en={enOf(doc.banker, "status_he")} /></dd></div>
          {doc.ai.summary_he && <div className="cc-span2"><dt>{t("סיכום הבדיקה", "Check summary")}</dt><dd><LocOrig he={doc.ai.summary_he} en={enOf(doc.ai, "summary_he")} /></dd></div>}
        </dl>
        {doc.ai.attention_he.length > 0 && <ul className="cc-drawer-attn">{doc.ai.attention_he.map((h, i) => <li key={i}><LocOrig he={h} en={attentionEn?.[i]} /></li>)}</ul>}
        <div className="bi-dr-actions">
          <button className="btn btn-dark btn-sm" onClick={() => { onClose(); ctx.openV1(doc.id); }} data-testid="cc-doc-v1">{t("פתיחה בסקירת המסמכים", "Open in the document review")}</button>
          <a className="btn btn-ghost btn-sm" href={`/api/documents/${doc.document_id}/file`} target="_blank" rel="noreferrer" data-testid="cc-doc-original">{t("הקובץ המקורי ↗", "Original file ↗")}</a>
          {doc.pages > 1 && <span className="cc-pager">
            <button className="btn btn-soft btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("→", "←")}</button>
            <span>{t("עמוד", "Page")} <span className="ltr">{page}/{doc.pages}</span></span>
            <button className="btn btn-soft btn-sm" disabled={page >= doc.pages} onClick={() => setPage(page + 1)}>{t("←", "→")}</button></span>}
        </div>
        <div className="bi-dr-viewer" data-testid="cc-doc-evidence">
          <EvidenceViewer documentId={doc.document_id} facts={doc.ai.facts} page={page} focus={focus} onFocus={pick} interactive dpi={130} autoScroll={!!focus} />
        </div>
        {doc.ai.facts.length > 0 && <div className="cc-facts" data-testid="cc-doc-facts">
          <div className="cc-group-k">{t("נתונים שחולצו מהמסמך", "Figures extracted from the document")}</div>
          <FactList facts={doc.ai.facts} focus={focus} onFocus={pick} />
        </div>}
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------- D · financial analysis
function Financial({ ctx }: { ctx: Ctx }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const a = x.analysis;
  const gaps = x.discrepancies;
  return (
    <Card id="cc-fin" title={t("ניתוח פיננסי", "Financial analysis")} testId="cc-financial"
      sub={t("הכנסה מתלושי השכר, התחייבויות מההקשר הבנקאי (לא מאומת) ויחסי החזר שחושבו בקוד.",
        "Income from the payslips, obligations from the bank context (not verified) and repayment ratios calculated in code.")}
      aside={<span className={`cc-avail a-${a.availability}`} data-testid="cc-availability">{locOf(a, "status_he")}</span>}>
      {gaps.map((g, i) => (
        <div key={i} className={`cc-gap${g.open ? " open" : ""}`} data-testid="cc-discrepancy" data-kind={g.kind} data-open={g.open}>
          <div className="cc-gap-head"><b>{locOf(g, "title_he")}{g.first_name_he ? ` · ${locOf(g, "first_name_he")}` : ""}</b><span className="cc-gap-st">{locOf(g, "status_he")}</span></div>
          <div className="cc-gap-vals">
            <div><span>{g.kind === "income" ? t("מוצהר בבקשה", "Declared in the application") : t("בבקשה", "In the application")}</span><Num ctx={ctx} d={g.declared} /></div>
            <div><span>{g.kind === "income" ? t("ממוצע בתלושים", "Payslip average") : t("בהצעת המחיר", "In the price quote")}</span><Num ctx={ctx} d={g.documented} /></div>
            <div><span>{t("הפרש", "Difference")}</span><b className="ltr">{money(g.difference_ils != null ? Math.abs(g.difference_ils) : null)}{g.difference_pct != null ? ` · ${Math.abs(g.difference_pct).toFixed(1)}%` : ""}</b></div>
          </div>
          <p><Loc he={g.explanation_he} en={enOf(g, "explanation_he")} /></p>
          <div className="cc-gap-act"><span><Loc he={g.action_he} en={enOf(g, "action_he")} /></span>
            <button className="btn btn-ghost btn-sm" onClick={() => ctx.openV1(g.v1_item)} data-testid="cc-gap-open">{t("בירור בסקירת המסמכים", "Clarify in the document review")}</button></div>
        </div>
      ))}
      {a.declared_alternative && (en ? <div className="cc-note warn" data-testid="cc-declared-alt">
        Based on the declared income ({money(a.declared_alternative.income_ils)}) the total ratio would be <b className="ltr">{pct(a.declared_alternative.combined_dsr_pct)}</b>.
        The analysis doesn't pick the figure that makes the application look better until the gap is clarified.</div>
        : <div className="cc-note warn" data-testid="cc-declared-alt">
        על בסיס ההכנסה המוצהרת ({money(a.declared_alternative.income_ils)}) היחס הכולל היה <b className="ltr">{pct(a.declared_alternative.combined_dsr_pct)}</b>.
        הניתוח לא בוחר בנתון שמציג את הבקשה טוב יותר עד לבירור הפער.</div>)}
      {a.availability === "partial" && a.reasons_he.length > 0 && <div className="cc-note warn" data-testid="cc-partial">{locList(a, "reasons_he").join(" ")}</div>}
      {x.income.borrowers.map((r) => <IncomeRow key={r.borrower_id} ctx={ctx} r={r} />)}
      <Obligations ctx={ctx} />
      <CalcDetails ctx={ctx} />
    </Card>
  );
}

function IncomeRow({ ctx, r }: { ctx: Ctx; r: Intelligence["income"]["borrowers"][number] }) {
  const { en, t } = useLang();
  const [open, setOpen] = useState(false);
  const max = Math.max(1, ...r.months.map((m) => m.net_ils || 0));
  const q = t({ verified: "מאומת בתלושים", partial: "חלקי", declared: "מוצהר בלבד", missing: "אין נתון" },
    { verified: "Verified on payslips", partial: "Partial", declared: "Declared only", missing: "No data" })[r.quality];
  return (
    <div className="cc-block" data-testid="cc-income" data-borrower={r.borrower_id}>
      <div className="cc-block-head">
        <div>
          <h3>{t("הכנסה", "Income")}{ctx.x.income.borrowers.length > 1 ? `, ${locOf(r, "first_name_he")}` : ""} <span className={`cc-q q-${r.quality}`}>{q}</span>
            {r.unresolved_discrepancy && <span className="cc-q q-gap">{t("פער פתוח", "Open gap")}</span>}</h3>
          <div className="cc-line">
            {r.documented_avg.value != null ? <>{t("הכנסה ממוצעת:", "Average income:")} <Num ctx={ctx} d={r.documented_avg} testId="cc-income-avg" /></>
              : <>{t("מוצהר בבקשה:", "Declared in the application:")} <Num ctx={ctx} d={r.declared} /></>}
            {r.variability_pct != null && <> · {t("שונות בין חודשים:", "Variability between months:")} <b className="ltr">{pct(r.variability_pct)}</b></>}
            {r.documented_avg.value != null && r.declared.value != null && <> · {en ? "Declared in the application:" : "מוצהר בבקשה:"} <Num ctx={ctx} d={r.declared} /></>}
          </div>
        </div>
        {r.months.length > 0 && <Toggle open={open} onClick={() => setOpen(!open)} testId="cc-payslips-toggle">{open ? t("הסתר תלושי שכר", "Hide payslips") : t("הצג תלושי שכר", "Show payslips")}</Toggle>}
      </div>
      {open && <table className="cc-table cc-months" data-testid="cc-months">
        <thead><tr><th>{t("חודש", "Month")}</th><th>{t("נטו בתלוש", "Net on payslip")}</th><th /><th>{t("מקור", "Source")}</th></tr></thead>
        <tbody>{r.months.map((m) => {
          const s = m.source_id ? ctx.x.sources[m.source_id] : null;
          return (
            <tr key={m.period}>
              <td>{locOf(m, "period_he")}</td>
              <td><button className="cc-num k-verified" onClick={() => ctx.open(s)} disabled={!s} data-testid="cc-income-month" data-period={m.period}>
                <span className="ltr">{money(m.net_ils)}</span></button></td>
              <td className="cc-bar-cell"><span className="cc-bar"><span style={{ width: `${((m.net_ils || 0) / max) * 100}%` }} /></span></td>
              <td>{s ? <Tag kind={markOf(s)} /> : <Tag kind="missing" />}</td>
            </tr>
          );
        })}</tbody>
      </table>}
    </div>
  );
}

function Obligations({ ctx }: { ctx: Ctx }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const bc = x.bank_context;
  const a = x.analysis;
  const [open, setOpen] = useState(false);
  const flagged = bc.events.filter((e) => e.returned_checks_12m || e.arrears_12m || e.restrictions_he.length);
  const missingFor = locList(bc, "missing_for");
  return (
    <div className="cc-block" data-testid="cc-obligations">
      <div className="cc-block-head">
        <div>
          <h3>{t("התחייבויות ומסגרות אשראי", "Obligations and credit lines")} {bc.available && <Tag kind="demo" />}</h3>
          {!bc.available ? (en ? <div className="cc-line cc-muted">No bank-context data for {missingFor.join(", ") || "the applicants"}; existing obligations are unknown,
            and the total ratio includes only the requested loan.</div>
            : <div className="cc-line cc-muted">אין נתוני הקשר בנקאי עבור {bc.missing_for.join(", ") || "המבקשים"}, ההתחייבויות הקיימות לא ידועות,
            והיחס הכולל כולל רק את ההלוואה המבוקשת.</div>)
            : (en ? <div className="cc-line">Existing payments: <Num ctx={ctx} d={a.existing_debt} testId="cc-existing" /> a month
              {" · "}{bc.loans.length === 1 ? "one loan" : `${bc.loans.length} loans`}
              {bc.exposure && <> · utilized exposure <Num ctx={ctx} d={bc.exposure.utilized} testId="cc-exposure-utilized" /> of <Num ctx={ctx} d={bc.exposure.approved} /></>}
            </div>
              : <div className="cc-line">החזרים קיימים: <Num ctx={ctx} d={a.existing_debt} testId="cc-existing" /> לחודש
              {" · "}{bc.loans.length === 1 ? "הלוואה אחת" : `${bc.loans.length} הלוואות`}
              {bc.exposure && <> · אובליגו מנוצל <Num ctx={ctx} d={bc.exposure.utilized} testId="cc-exposure-utilized" /> מתוך <Num ctx={ctx} d={bc.exposure.approved} /></>}
            </div>)}
        </div>
        {bc.available && <Toggle open={open} onClick={() => setOpen(!open)} testId="cc-obligations-toggle">{open ? t("הסתר פירוט", "Hide details") : t("הצג פירוט", "Show details")}</Toggle>}
      </div>
      {flagged.map((e) => en
        ? <div key={e.source_id} className="cc-note warn" data-testid="cc-event">Account events in the last 12 months ({locOf(e, "owner_he")}): {locList(e, "detail_he").join(" ")}{" "}
          <SrcText ctx={ctx} id={e.source_id}>Source</SrcText> · To be verified in the bank's systems.</div>
        : <div key={e.source_id} className="cc-note warn" data-testid="cc-event">אירועי חשבון ב־12 חודשים ({e.owner_he}): {e.detail_he.join(" ")}{" "}
        <SrcText ctx={ctx} id={e.source_id}>מקור</SrcText> · יש לאמת במערכות הבנק.</div>)}
      {open && bc.available && <div className="cc-obl" data-testid="cc-obligations-detail">
        <table className="cc-table">
          <thead><tr><th>{t("הלוואה קיימת", "Existing loan")}</th><th>{t("יתרת קרן", "Outstanding principal")}</th><th>{t("החזר חודשי", "Monthly payment")}</th><th>{t("נותרו", "Remaining")}</th></tr></thead>
          <tbody>{bc.loans.length ? bc.loans.map((l) => (
            <tr key={l.id}><td><Loc he={l.type_he} en={enOf(l, "type_he")} /><div className="cc-tiny">{locOf(l, "lender_he")} · {locOf(l, "owner_he")}</div></td>
              <td><Num ctx={ctx} d={l.outstanding} /></td><td><Num ctx={ctx} d={l.monthly} testId="cc-loan-monthly" /></td>
              <td className="ltr">{l.remaining_payments}</td></tr>)) : <tr><td colSpan={4} className="cc-muted">{t("אין הלוואות קיימות בהקשר הבנקאי", "No existing loans in the bank context")}</td></tr>}</tbody>
        </table>
        {bc.credit_lines.length > 0 && <table className="cc-table">
          <thead><tr><th>{t("מסגרת אשראי", "Credit line")}</th><th>{t("מסגרת", "Limit")}</th><th>{t("מנוצל", "Utilized")}</th><th>{t("ניצול", "Utilization")}</th></tr></thead>
          <tbody>{bc.credit_lines.map((l) => (
            <tr key={l.id}><td><Loc he={l.type_he} en={enOf(l, "type_he")} /><div className="cc-tiny">{locOf(l, "owner_he")}</div></td><td className="ltr">{money(l.limit_ils)}</td>
              <td><button className="cc-num k-demo" onClick={() => ctx.open(l.source_id)}><span className="ltr">{money(l.utilized_ils)}</span></button></td>
              <td><span className="cc-bar demo"><span style={{ width: `${Math.min(100, (l.utilized_ils / (l.limit_ils || 1)) * 100)}%` }} /></span></td></tr>))}</tbody>
        </table>}
        <ul className="cc-notes">
          {en ? <li><b>Not counted twice:</b> balances and credit lines are exposure (obligo), not monthly payments. Only the monthly payments count toward the DSR.</li>
            : <li><b>לא נספר פעמיים:</b> יתרות ומסגרות הן חשיפה (אובליגו), לא החזר חודשי. רק ההחזרים החודשיים נכנסים ליחס ההחזר.</li>}
          {bc.card_spending.map((s) => en
            ? <li key={s.source_id}>Card charges ({locOf(s, "owner_he")}): <button className="cc-num k-demo" onClick={() => ctx.open(s.source_id)}>
              <span className="ltr">{money(s.avg_monthly_ils)}</span></button> a month on average, an ongoing expense; not debt service and not included in the ratio.</li>
            : <li key={s.source_id}>חיובי כרטיס ({s.owner_he}): <button className="cc-num k-demo" onClick={() => ctx.open(s.source_id)}>
            <span className="ltr">{money(s.avg_monthly_ils)}</span></button> בממוצע לחודש, הוצאה שוטפת, אינה החזר חוב ואינה נכללת ביחס.</li>)}
          {bc.events.filter((e) => !flagged.includes(e)).map((e) => <li key={e.source_id}>{t(`אירועי חשבון ב־12 חודשים (${e.owner_he}): ללא שיקים חוזרים, פיגורים או הגבלות.`,
            `Account events in the last 12 months (${locOf(e, "owner_he")}): no returned cheques, arrears or restrictions.`)}</li>)}
        </ul>
        <div className="cc-srcnote">{t("נתוני בנק · נכון ל־", "Bank data · as of ")}<span className="ltr">{bc.observed_at}</span>{t(" · לא מאומת", " · not verified")}
          {bc.missing_for.length ? t(` · חסר עבור ${bc.missing_for.join(", ")}`, ` · missing for ${missingFor.join(", ")}`) : ""}</div>
      </div>}
    </div>
  );
}

function CalcDetails({ ctx }: { ctx: Ctx }) {
  const { t } = useLang();
  const a = ctx.x.analysis;
  const [open, setOpen] = useState(false);
  return (
    <div className="cc-block quiet">
      <Toggle open={open} onClick={() => setOpen(!open)} testId="cc-calc-toggle">{t("פירוט החישוב", "Calculation details")}</Toggle>
      {open && <dl className="cc-kvs cc-kvs-quiet" data-testid="cc-calc">
        <KV k={t("הכנסה נטו לחישוב", "Net income used in the calculation")}><Num ctx={ctx} d={a.income} /></KV>
        <KV k={t("החזרים קיימים בחודש", "Existing monthly payments")}><Num ctx={ctx} d={a.existing_debt} /></KV>
        <KV k={t("יחס החזר קיים", "Existing DSR")}><Num ctx={ctx} d={a.existing_dsr} /></KV>
        <KV k={t("יחס החזר כולל בבקשה", "Total DSR as requested")}><Num ctx={ctx} d={a.combined_dsr} testId="cc-calc-combined" /></KV>
        <KV k={t("שיעור מימון מהאסמכתה", "Financing vs. the proof amount")}><Num ctx={ctx} d={a.ltv} /></KV>
        <KV k={t("הכנסה שנותרת אחרי החזרי חוב (תיאורי)", "Income left after debt payments (descriptive)")}><Num ctx={ctx} d={a.remaining_after_debt} /></KV>
      </dl>}
    </div>
  );
}

// ---------------------------------------------------------------- E · financing alternatives
function Alternatives({ ctx }: { ctx: Ctx }) {
  const { en, t } = useLang();
  const { x } = ctx;
  const s = x.simulation;
  const base = s.inputs;
  const [principal, setPrincipal] = useState(base.principal);
  const [term, setTerm] = useState(base.term_months);
  const [rate, setRate] = useState(base.annual_rate_pct);
  const [whatIf, setWhatIf] = useState(true);
  useEffect(() => { setPrincipal(base.principal); setTerm(base.term_months); setRate(base.annual_rate_pct); }, [x.case_id, base.principal, base.term_months, base.annual_rate_pct]);
  const changed = principal !== base.principal || term !== base.term_months || rate !== base.annual_rate_pct;
  const rows: Scenario[] = useMemo(() => simulate(principal, term, rate, s.income_ils, s.existing_debt_ils, s.asset_price_ils, s.bounds),
    [principal, term, rate, s]);
  const reset = () => { setPrincipal(base.principal); setTerm(base.term_months); setRate(base.annual_rate_pct); };
  if (!s.enabled) return (
    <Card id="cc-alt" title={t("חלופות מימון", "Financing alternatives")} testId="cc-alternatives"><div className="cc-empty">{t("אין בבקשה סכום ומספר תשלומים לחישוב.",
      "The application has no amount and number of payments to calculate with.")}</div></Card>);
  const thr = s.threshold_pct;
  const short = rows[0], long = rows[rows.length - 1];
  const src = (r: Scenario, what: "pay" | "dsr" | "total") => scenarioSource(s, r, what, principal, term, rate);
  return (
    <Card id="cc-alt" title={t("חלופות מימון", "Financing alternatives")} testId="cc-alternatives"
      sub={t("שלוש חלופות להמחשת השפעת תקופת ההחזר על התשלום החודשי ועלות המימון. להמחשה בלבד, לא הצעה מחייבת.",
        "Three alternatives that show how the repayment term affects the monthly payment and the financing cost. Illustrative only, not a binding offer.")}
      aside={<>
        {changed && <button className="btn btn-soft btn-sm" onClick={reset} data-testid="cc-wi-reset">{t("חזרה לנתוני הבקשה", "Back to the application's figures")}</button>}
        <Toggle open={whatIf} onClick={() => setWhatIf(!whatIf)} testId="cc-whatif-toggle">{t("מה יקרה אם?", "What if?")}</Toggle></>}>
      {x.analysis.availability !== "full" && <div className="cc-note warn" data-testid="cc-sim-provisional">
        {x.analysis.availability === "unavailable" ? t("ניתוח היחסים אינו זמין לתיק זה, מוצגים החזרים ועלויות בלבד.", "Ratio analysis isn't available for this case; only payments and costs are shown.")
          : x.analysis.availability === "provisional" ? t("החלופות מוצגות להמחשה בלבד, הניתוח הפיננסי זמני עד לבירור הפער.", "The alternatives are illustrative only; the financial analysis is provisional until the gap is clarified.")
            : t("החלופות מוצגות להמחשה בלבד, הניתוח הפיננסי חלקי.", "The alternatives are illustrative only; the financial analysis is partial.")}</div>}
      {whatIf && <div className="cc-whatif" data-testid="cc-whatif">
        <Slider label={t("סכום ההלוואה", "Loan amount")} value={principal} min={10000} max={s.bounds.principal_max} step={1000} onChange={setPrincipal} display={money(principal)}
          testId="cc-wi-principal" changed={principal !== base.principal} />
        <Slider label={t("תקופה (תשלומים)", "Term (payments)")} value={term} min={s.bounds.term_min} max={s.bounds.term_max} step={6} onChange={setTerm}
          display={`${term} · ${years(term)}`} testId="cc-wi-term" changed={term !== base.term_months} />
        <Slider label={t("ריבית שנתית להמחשה", "Illustrative annual rate")} value={rate} min={0} max={15} step={0.1} onChange={(v) => setRate(Math.round(v * 10) / 10)} display={`${rate.toFixed(1)}%`}
          testId="cc-wi-rate" changed={rate !== base.annual_rate_pct}
          hint={en ? <>Default <SrcText ctx={ctx} id={s.rate_source_id}>{base.annual_rate_pct.toFixed(1)}%</SrcText> · assumption</>
            : <>ברירת מחדל <SrcText ctx={ctx} id={s.rate_source_id}>{base.annual_rate_pct.toFixed(1)}%</SrcText> · הנחה</>} />
        <p className="cc-whatif-n">{t("השינויים מחושבים מיד ואינם נשמרים, הבקשה, ההכנסה וההתחייבויות אינן משתנות.",
          "Changes are calculated instantly and not saved; the application, income and obligations don't change.")}</p>
      </div>}
      {changed && <div className="cc-simbadge" data-testid="cc-sim-active">{t(`סימולציה פעילה: ${money(principal)} · ${term} תשלומים · ${rate.toFixed(1)}%`,
        `Active simulation: ${money(principal)} · ${term} payments · ${rate.toFixed(1)}%`)}</div>}
      <div className="cc-scs">
        {rows.map((r) => {
          const requested = r.key === "requested";
          const suggested = !changed && s.suggested?.key === r.key;
          const over = r.combined_dsr_pct != null && r.combined_dsr_pct > thr;
          return (
            <article key={r.key} className={`cc-sc${requested ? " req" : ""}${suggested ? " sug" : ""}`} data-testid="cc-scenario" data-key={r.key} data-term={r.term_months}>
              <header>
                <span className="cc-sc-k">{requested && changed ? t("התקופה שנבחרה", "Selected term") : scLabel(r.key)}</span>
                {requested && !changed && <span className="cc-sc-tag">{t("הבקשה המקורית", "Original request")}</span>}
                {suggested && <span className="cc-sc-tag sug" title={locOf(s.suggested, "label_he")}>{t("חלופה להמחשה", "Illustrative alternative")}</span>}
              </header>
              <div className="cc-sc-term"><b className="ltr">{r.term_months}</b> {t("תשלומים", "payments")} · {years(r.term_months)} · <span className="ltr">{money(r.principal_ils)}</span></div>
              <button className="cc-sc-pay" onClick={() => ctx.open(src(r, "pay"))} data-testid="cc-sc-pay" data-value={r.monthly_payment_ils}>
                <span className="ltr">{money(r.monthly_payment_ils)}</span><small>{t("לחודש", "/month")}</small></button>
              <dl>
                <div><dt>{t("סך התשלומים", "Total payments")}</dt><dd className="ltr" data-testid="cc-sc-total">{money(r.total_payments_ils)}</dd></div>
                <div><dt>{t("עלות המימון", "Financing cost")}</dt><dd><button className="cc-num k-calc" onClick={() => ctx.open(src(r, "total"))} data-testid="cc-sc-interest"
                  data-value={r.total_interest_ils}><span className="ltr">{money(r.total_interest_ils)}</span></button></dd></div>
                <div><dt>{t("יחס החזר כולל", "Total DSR")}</dt><dd><button className={`cc-num k-calc${over ? " over" : ""}`} onClick={() => ctx.open(src(r, "dsr"))} data-testid="cc-sc-dsr"
                  data-value={r.combined_dsr_pct ?? ""}><span className="ltr">{pct(r.combined_dsr_pct)}</span></button></dd></div>
              </dl>
            </article>
          );
        })}
      </div>
      {rows.length > 1 && (en ? <p className="cc-compare" data-testid="cc-compare">
        Spread over <b className="ltr">{long.term_months}</b> payments, the monthly payment is <b className="ltr">{money(short.monthly_payment_ils - long.monthly_payment_ils)}</b> lower
        than over <b className="ltr">{short.term_months}</b>, but the financing cost is <b className="ltr">{money(long.total_interest_ils - short.total_interest_ils)}</b> higher.
        {" "}The rate (<SrcText ctx={ctx} id={s.rate_source_id}>{rate.toFixed(1)}%</SrcText>) and the DSR threshold (<SrcText ctx={ctx} id={s.threshold_source_id}>{thr}%</SrcText>) are assumptions for the calculation, not the bank's terms.</p>
        : <p className="cc-compare" data-testid="cc-compare">
        בפריסה ל־<b className="ltr">{long.term_months}</b> תשלומים ההחזר החודשי נמוך ב־<b className="ltr">{money(short.monthly_payment_ils - long.monthly_payment_ils)}</b> מאשר
        ב־<b className="ltr">{short.term_months}</b>, אך עלות המימון גבוהה ב־<b className="ltr">{money(long.total_interest_ils - short.total_interest_ils)}</b>.
        {" "}הריבית (<SrcText ctx={ctx} id={s.rate_source_id}>{rate.toFixed(1)}%</SrcText>) והסף ליחס ההחזר (<SrcText ctx={ctx} id={s.threshold_source_id}>{thr}%</SrcText>) הם הנחות לצורך החישוב, לא תנאי הבנק.</p>)}
      {x.analysis.illustrative_max_principal != null && (en
        ? <p className="cc-muted cc-small" data-testid="cc-max-principal">For illustration: under these assumptions, an amount of up to <b className="ltr">{money(x.analysis.illustrative_max_principal)}</b> over {base.term_months} payments
        keeps the total ratio within {thr}%; this is not an approved amount.</p>
        : <p className="cc-muted cc-small" data-testid="cc-max-principal">להמחשה: בהנחות אלה, סכום של עד <b className="ltr">{money(x.analysis.illustrative_max_principal)}</b> ל־{base.term_months} תשלומים
        משאיר את היחס הכולל בתוך {thr}%, אינו סכום מאושר.</p>)}
    </Card>
  );
}

// ---------------------------------------------------------------- F · reasoning and conditions
function Reasoning({ ctx }: { ctx: Ctx }) {
  const { t } = useLang();
  const { x } = ctx;
  const r = x.recommendation;
  const [more, setMore] = useState(false);
  const open = x.risks.filter((k) => k.kind !== "missing");
  const docSources = Object.values(x.sources).filter((s) => s.kind === "document");
  // case actions first (they open V1), then the standing limits of the analysis
  const verify = [...r.verify].sort((a, b) => Number(!!b.v1_item) - Number(!!a.v1_item));
  return (
    <Card id="cc-why" title={t("נימוקי ההמלצה ותנאים להתקדמות", "Reasons for the recommendation and conditions to proceed")} testId="cc-reasoning"
      sub={t("על מה ההמלצה נשענת, ומה עוד צריך לאמת לפני החלטה.", "What the recommendation rests on, and what still needs verifying before a decision.")}>
      {open.length > 0 && <ul className="cc-risks" data-testid="cc-risks">{open.map((k, i) => (
        <li key={i}><span className="cc-risk-who"><Loc he={k.who_he} en={enOf(k, "who_he")} /></span><span><b><Loc he={k.title_he} en={enOf(k, "title_he")} /></b>{k.text_he ? <> — <Loc he={k.text_he} en={enOf(k, "text_he")} /></> : ""}</span>
          <button className="cc-link" onClick={() => ctx.openV1(k.v1_item)}>{t("פתיחה", "Open")}</button></li>))}</ul>}
      <div className="cc-why-grid">
        <section className="cc-why-panel" aria-labelledby="cc-why-cons">
          <header className="cc-why-h"><h3 id="cc-why-cons">{t("ממצאים עיקריים", "Key findings")}</h3><span className="cc-why-n">{r.considerations.length}</span></header>
          <ul className="cc-cons" data-testid="cc-considerations">{r.considerations.map((c, i) => (
            <li key={i} className={`c-${c.tone}`} data-testid="cc-consideration">
              <span className="cc-cons-dot" aria-hidden />
              <div className="cc-cons-body"><p><Loc he={c.text_he} en={enOf(c, "text_he")} /></p><ConsSources ctx={ctx} ids={c.source_ids} /></div>
            </li>))}</ul>
        </section>
        <section className="cc-why-panel cond" aria-labelledby="cc-why-verify">
          <header className="cc-why-h"><h3 id="cc-why-verify">{t("נדרש לפני החלטה", "Required before a decision")}</h3><span className="cc-why-n">{verify.length}</span></header>
          <ul className="cc-verify" data-testid="cc-verify">{verify.map((v, i) => (
            <li key={i} className={v.v1_item ? "is-action" : ""}><span className="cc-check" aria-hidden />
              <div><span><Loc he={v.text_he} en={enOf(v, "text_he")} /></span>
                {v.v1_item && <button className="cc-verify-go" onClick={() => ctx.openV1(v.v1_item)}>{t("פתיחה בסקירת המסמכים ←", "Open in the document review →")}</button>}</div>
            </li>))}</ul>
          <footer className="cc-why-foot">
            <span>{t("ההחלטה נרשמת בסקירת המסמכים, עם נימוק וביומן.", "The decision is recorded in the document review, with a reason and in the log.")}</span>
            <button className="cc-why-cta" onClick={() => ctx.openV1(r.next_action.v1_item)} data-testid="cc-why-cta">{t("מעבר לטיפול בתיק ←", "Go to case handling →")}</button>
          </footer>
        </section>
      </div>
      <button className="cc-disclose" onClick={() => setMore(!more)} aria-expanded={more} data-testid="cc-why-more">
        <span className="cc-disclose-t">{more ? t("הסתר פירוט ונימוקים", "Hide details and reasons") : t("הצג פירוט ונימוקים", "Show details and reasons")}</span>
        <span className="cc-disclose-h">{t("נתונים שחולצו ממסמכים · מה לא נבדק · סימוני מקור", "Figures extracted from documents · What wasn't checked · Source marks")}</span>
        <span aria-hidden className="cc-chev">{more ? "▴" : "▾"}</span>
      </button>
      {more && <div className="cc-why-detail" data-testid="cc-why-detail">
        <section>
          <h4>{t("נתונים שחולצו ממסמכים ושימשו בניתוח", "Figures extracted from documents and used in the analysis")}</h4>
          {docSources.length ? <ul className="cc-evlist" data-testid="cc-evlist">{docSources.map((s) => (
            <li key={s.id}><button className="cc-evrow" onClick={() => ctx.open(s)} data-testid="cc-evrow" data-field={s.field}>
              <span><Loc he={s.label_he} en={s.label_en} /></span><span className="ltr"><Orig text={s.value_raw} /></span><Tag kind={markOf(s)} /></button></li>))}</ul>
            : <div className="cc-empty">{t("אין עדיין נתונים שחולצו ממסמכים.", "No figures extracted from documents yet.")}</div>}
        </section>
        <section>
          <h4>{t("מה לא נבדק", "What wasn't checked")}</h4>
          <dl className="cc-unknowns">{x.unknowns.map((u, i) => <div key={i}><dt><Loc he={u.label_he} en={enOf(u, "label_he")} /></dt><dd><Loc he={u.text_he} en={enOf(u, "text_he")} /></dd></div>)}</dl>
          <h4>{t("סימוני מקור", "Source marks")}</h4>
          <ul className="cc-legend">{(["reviewed", "verified", "declared", "demo", "calc", "assume"] as MarkKind[]).map((k) => (
            <li key={k}><Tag kind={k} /> {MARK[k].title}</li>))}</ul>
        </section>
      </div>}
    </Card>
  );
}

/** One link per kind of source behind a finding; a kind with several sources opens them one after another in the drawer's stack. */
function ConsSources({ ctx, ids }: { ctx: Ctx; ids: string[] }) {
  useLang();
  const by = new Map<MarkKind, IntelSource[]>();
  for (const id of ids) {
    const s = ctx.x.sources[id];
    if (!s) continue;
    const k = markOf(s);
    by.set(k, [...(by.get(k) || []), s]);
  }
  if (!by.size) return null;
  return (
    <span className="cc-cons-src">{[...by.entries()].map(([k, list]) => (
      <button key={k} className={`cc-chip k-${k}`} onClick={() => list.slice().reverse().forEach((s) => ctx.open(s))} data-testid="cc-cons-src" data-kind={k}
        title={list.map((s) => locOf(s, "label_he")).join(" · ")}>{MARK[k].label}{list.length > 1 ? ` ×${list.length}` : ""}</button>))}</span>
  );
}
