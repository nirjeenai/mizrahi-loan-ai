import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, timeHe, usePolling, type Datum, type DocItem, type IntelSource, type Intelligence, type MissingItem, type Workspace } from "../../api";
import { EvidenceViewer, FactList } from "../../components/EvidenceViewer";
import { scenarios as simulate, type Scenario } from "../../finance";
import { Toast } from "./deskUi";
import { DRAFT_NOTE, fmt, MARK, markOf, money, pct, SC_LABEL, scenarioSource, Slider, SourceDrawer, years, type Ctx, type MarkKind } from "./IntelligenceV2";
import "./intelligence.css";
import "./casecentric.css";

/** Banker Case-Centric V3: the same intelligence payload as V2, read as one prepared case from top to bottom —
 *  recommendation, the application, the customer's documents, the financial analysis, the alternatives, the reasoning
 *  and the reply. Read-only like V2: every state change happens in the review workspace (V1). */
export function CaseCentricV3({ caseId, ws, openV1 }: { caseId: string; ws: Workspace; openV1: (item?: string | null) => void }) {
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
  if (!x) return <div className="desk-loading">{intel.error ? <>לא הצלחנו לטעון את התיק. <button className="link" onClick={intel.reload}>ניסיון חוזר</button></>
    : <><span className="spinner" /> JEEN מכין את התיק…</>}</div>;
  const ctx: Ctx = { x, open, openV1 };
  const go = (id: string) => scroller.current?.querySelector(`#${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  return (
    <div className="cc-scroll" ref={scroller} data-testid="cc-root" data-case={caseId}>
      <StickyBar ctx={ctx} shown={pinned} />
      <div className="cc-page">
        <CaseHeader ctx={ctx} innerRef={head} />
        <Recommendation ctx={ctx} go={go} />
        <KeyFigures ctx={ctx} />
        <CaseDetails ctx={ctx} />
        <Documents ctx={ctx} ws={ws} onOpen={setDoc} />
        <Financial ctx={ctx} />
        <Alternatives ctx={ctx} />
        <Reasoning ctx={ctx} />
        <Reply ctx={ctx} onToast={setToast} />
        <p className="cc-foot">{x.disclaimer_he} · עודכן <span className="ltr">{timeHe(x.generated_at)}</span></p>
      </div>
      {stack.length > 0 && <SourceDrawer src={stack[stack.length - 1]} depth={stack.length} ws={ws} ctx={ctx}
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
  READY_FOR_CREDIT_REVIEW: "מומלץ להתקדם לבחינת האשראי",
  PREPARATION_CONFIRMED: "הכנת התיק אושרה — אפשר להתקדם לבחינת האשראי",
  CLARIFICATION_REQUIRED: "נדרש בירור לפני בחינת האשראי",
  DOCUMENTS_INCOMPLETE: "נדרשת השלמת מסמכים לפני בחינת האשראי",
  NO_DOCUMENTS: "טרם התקבלו מסמכים בתיק",
  PROCESSING: "JEEN עדיין בודק את המסמכים",
  ERROR: "בדיקת המסמכים לא הושלמה",
};
const applicantName = (x: Intelligence) => x.applicant.company?.name_he || x.applicant.borrowers.map((b) => b.name_he).join(" ו");
const loanLine = (x: Intelligence) => [x.loan.purpose_he ? `הלוואה ל${x.loan.purpose_he}` : x.loan.product_he,
  x.loan.amount.value != null ? money(x.loan.amount.value) : null, x.loan.term.value != null ? `${x.loan.term.value} תשלומים` : null].filter(Boolean).join(" · ");

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
  const src = d?.source_id ? ctx.x.sources[d.source_id] : null;
  if (!d || d.value == null) return <span className="cc-num none" data-testid={testId}>לא זמין</span>;
  const k = markOf(src);
  return (
    <button className={`cc-num k-${k}`} onClick={() => ctx.open(src)} disabled={!src} data-testid={testId || "cc-datum"}
      data-source={d.source_id || ""} data-kind={src?.kind || "none"} title={src ? `${MARK[k].title} — לחצו להצגת המקור` : undefined}>
      {d.unit === "months" ? <span>{fmt(d.value, d.unit, exact)}</span> : <span className="ltr">{fmt(d.value, d.unit, exact)}</span>}
    </button>
  );
}

function Tag({ kind, children }: { kind: MarkKind; children?: ReactNode }) {
  return <span className={`cc-tag k-${kind}`} title={MARK[kind].title} data-mark={kind}>{children ?? MARK[kind].label}</span>;
}

function SrcText({ ctx, id, children }: { ctx: Ctx; id?: string | null; children?: ReactNode }) {
  const s = id ? ctx.x.sources[id] : null;
  if (!s) return <>{children}</>;
  return <button className="cc-srctext" onClick={() => ctx.open(s)} title={MARK[markOf(s)].title} data-testid="cc-srclink" data-kind={s.kind}>
    {children ?? String(s.value_raw ?? s.label_he)}</button>;
}

function Toggle({ open, onClick, children, testId }: { open: boolean; onClick: () => void; children: ReactNode; testId: string }) {
  return <button className="cc-toggle" onClick={onClick} aria-expanded={open} data-testid={testId}>{children}<span aria-hidden className="cc-chev">{open ? "▴" : "▾"}</span></button>;
}

// ---------------------------------------------------------------- A · case header and recommendation
function CaseHeader({ ctx, innerRef }: { ctx: Ctx; innerRef: React.RefObject<HTMLElement> }) {
  const { x } = ctx;
  const r = x.recommendation;
  const tone = TONE[r.state] || "neutral";
  return (
    <header className="cc-head" ref={innerRef} data-testid="cc-head">
      <div className="cc-head-id">
        <div className="cc-kicker">בקשת הלוואה · תיק <span className="ltr">{x.case.display_number}</span></div>
        <h1 data-testid="cc-name">{applicantName(x)}</h1>
        <div className="cc-loanline" data-testid="cc-loanline">{loanLine(x)}</div>
      </div>
      <div className="cc-head-act">
        <span className={`cc-status s-${tone}`} data-testid="cc-status">{r.documentation.status_he}</span>
        <button className="cc-primary" onClick={() => ctx.openV1(r.next_action.v1_item)} data-testid="cc-primary">
          מעבר לטיפול בתיק <span aria-hidden>←</span></button>
        <div className="cc-next" data-testid="cc-next">הצעד הבא בסקירת המסמכים: {r.next_action.label_he}</div>
      </div>
    </header>
  );
}

function StickyBar({ ctx, shown }: { ctx: Ctx; shown: boolean }) {
  const { x } = ctx;
  const r = x.recommendation;
  return (
    <div className={`cc-sticky${shown ? " on" : ""}`} aria-hidden={!shown} data-testid="cc-sticky">
      <div className="cc-sticky-in">
        <b>{applicantName(x)}</b><span className="cc-sticky-l">{loanLine(x)}</span>
        <span className={`cc-status s-${TONE[r.state] || "neutral"}`}>{r.documentation.status_he}</span>
        <button className="cc-primary sm" tabIndex={shown ? 0 : -1} onClick={() => ctx.openV1(r.next_action.v1_item)}>מעבר לטיפול בתיק ←</button>
      </div>
    </div>
  );
}

function Recommendation({ ctx, go }: { ctx: Ctx; go: (id: string) => void }) {
  const { x } = ctx;
  const r = x.recommendation;
  const tone = TONE[r.state] || "neutral";
  const d = x.documents;
  const attention: { text: string; target: string; testId: string }[] = [];
  for (const g of x.discrepancies.filter((q) => q.open))
    attention.push({ text: `${g.title_he}${g.first_name_he ? ` · ${g.first_name_he}` : ""}`, target: "cc-fin", testId: "cc-attn-gap" });
  if (d.missing.length) attention.push({ text: d.missing.length === 1 ? `חסר בתיק: ${d.missing[0].title_he}` : `${d.missing.length} פריטים חסרים בתיק`,
    target: "cc-docs", testId: "cc-attn-missing" });
  if (d.corrections.length) attention.push({ text: d.corrections.length === 1 ? "מסמך אחד הוחזר לתיקון אצל הלקוח" : `${d.corrections.length} מסמכים הוחזרו לתיקון אצל הלקוח`,
    target: "cc-docs", testId: "cc-attn-correction" });
  for (const k of x.risks.filter((q) => q.kind === "finding")) attention.push({ text: k.title_he, target: "cc-why", testId: "cc-attn-finding" });
  for (const e of x.bank_context.events.filter((q) => q.returned_checks_12m || q.arrears_12m || q.restrictions_he.length))
    attention.push({ text: `אירוע חשבון בנתוני הדמו (${e.owner_he}) — לאימות במערכות הבנק`, target: "cc-fin", testId: "cc-attn-event" });
  return (
    <section className={`cc-rec t-${tone}`} data-testid="cc-rec" data-state={r.state}>
      <div className="cc-rec-mark" aria-hidden>{tone === "ok" ? "✓" : tone === "neutral" ? "…" : "!"}</div>
      <div className="cc-rec-body">
        <div className="cc-rec-top"><span className="cc-jeen">המלצת JEEN</span><span className="cc-rec-nb">המלצה לבנקאי בלבד — אינה אישור אשראי</span></div>
        <h2 data-testid="cc-rec-title">{TITLE[r.state] || r.documentation.status_he}</h2>
        <p data-testid="cc-rec-text">{r.headline_he}</p>
        {attention.length > 0 && <ul className="cc-attn" data-testid="cc-attention">
          {attention.map((a, i) => <li key={i} data-testid={a.testId}><span>{a.text}</span>
            <button className="cc-link" onClick={() => go(a.target)}>לפרטים</button></li>)}
        </ul>}
      </div>
    </section>
  );
}

function KeyFigures({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const a = x.analysis;
  const thr = x.simulation.threshold_pct;
  const rows = x.income.borrowers;
  const months = rows.reduce((n, r) => n + r.months.filter((m) => m.net_ils != null).length, 0);
  const incomeNote = a.availability === "provisional" ? "זמני — הנתון הנמוך מבין ההצהרה לתלושים"
    : rows.some((r) => r.quality === "declared") ? "כולל הכנסה מוצהרת שטרם אומתה"
      : rows.length && rows.every((r) => r.quality === "verified") ? `ממוצע ${months} תלושי שכר מאומתים` : a.status_he;
  const dsr = a.combined_dsr?.value;
  return (
    <div className="cc-figs" data-testid="cc-figures">
      <div className="cc-fig" data-testid="cc-fig-income"><div className="cc-fig-k">הכנסה חודשית נטו</div>
        <div className="cc-fig-v"><Num ctx={ctx} d={a.income} /></div><div className="cc-fig-n">{incomeNote}</div></div>
      <div className="cc-fig" data-testid="cc-fig-payment"><div className="cc-fig-k">החזר חודשי משוער</div>
        <div className="cc-fig-v"><Num ctx={ctx} d={a.proposed_payment} /></div>
        <div className="cc-fig-n">{x.loan.term.value ? `ל־${x.loan.term.value} תשלומים · ריבית להמחשה ${x.simulation.inputs.annual_rate_pct.toFixed(1)}%` : "אין בבקשה מספר תשלומים"}</div></div>
      <div className={`cc-fig${dsr != null && dsr > thr ? " warn" : ""}`} data-testid="cc-fig-dsr"><div className="cc-fig-k">יחס החזר כולל בסימולציה</div>
        <div className="cc-fig-v"><Num ctx={ctx} d={a.combined_dsr} /></div>
        <div className="cc-fig-n">{a.combined_dsr?.value == null ? a.status_he : `הנחת הדגמה: עד ${thr}%${a.availability === "provisional" ? " · זמני" : a.availability === "partial" ? " · ניתוח חלקי" : ""}`}</div></div>
    </div>
  );
}

// ---------------------------------------------------------------- B · customer and loan
function KV({ k, children, testId }: { k: string; children: ReactNode; testId?: string }) {
  return <div className="cc-kv" data-testid={testId}><dt>{k}</dt><dd>{children}</dd></div>;
}

function CaseDetails({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const [more, setMore] = useState(false);
  const many = x.applicant.borrowers.length > 1;
  return (
    <Card id="cc-details" title="פרטי הלקוח והבקשה" testId="cc-details">
      <div className="cc-group-k">{x.applicant.entity === "company" ? "החברה המבקשת" : many ? "המבקשים" : "הלקוח"}</div>
      {x.applicant.company && <dl className="cc-kvs">
        <KV k="שם החברה">{x.applicant.company.name_he}</KV>
        <KV k="מספר חברה"><span className="ltr">{x.applicant.company.company_number}</span></KV>
      </dl>}
      {x.applicant.borrowers.map((b) => (
        <dl key={b.borrower_id} className="cc-kvs" data-testid="cc-borrower">
          <KV k="שם מלא"><b>{b.name_he}</b>{many && <span className="cc-role">{b.role_he}</span>}</KV>
          <KV k="פרופיל">{b.profile_he || x.applicant.profile_label_he || "—"}</KV>
          <KV k="מעסיק / עסק">{b.employer_document_source_id ? <SrcText ctx={ctx} id={b.employer_document_source_id} />
            : b.employer_declared_he ? <>{b.employer_declared_he} <Tag kind="declared" /></> : "—"}</KV>
        </dl>
      ))}
      <div className="cc-group-k">הבקשה</div>
      <dl className="cc-kvs">
        <KV k="סוג הלוואה">{x.loan.product_he || "—"}</KV>
        <KV k="מטרה">{x.loan.purpose_he || "—"}</KV>
        <KV k="סכום מבוקש" testId="cc-loan-amount"><Num ctx={ctx} d={x.loan.amount} /></KV>
        <KV k="תקופה מבוקשת" testId="cc-loan-term"><Num ctx={ctx} d={x.loan.term} />{x.loan.term.value ? <span className="cc-muted"> · {years(x.loan.term.value)}</span> : null}</KV>
        {x.loan.asset && <KV k={x.loan.asset.label_he} testId="cc-asset-price"><Num ctx={ctx} d={x.loan.asset.price} /></KV>}
        {x.loan.asset?.subject_source_id && <KV k="הפריט באסמכתה"><SrcText ctx={ctx} id={x.loan.asset.subject_source_id} /></KV>}
        {x.applicant.co_borrowers.length > 0 && <KV k="לווים נוספים">{x.applicant.co_borrowers.join(", ")}</KV>}
      </dl>
      {x.loan.note_he && <p className="cc-quote">„{x.loan.note_he}” <span className="cc-muted">— מתוך הבקשה</span></p>}
      <Toggle open={more} onClick={() => setMore(!more)} testId="cc-details-more">{more ? "פחות פרטים" : "פרטים נוספים"}</Toggle>
      {more && <dl className="cc-kvs cc-kvs-quiet" data-testid="cc-details-extra">
        <KV k="מספר תיק"><span className="ltr">{x.case.display_number}</span></KV>
        <KV k="מזהה בקשה"><span className="ltr">{x.case_id}</span></KV>
        <KV k="בנקאי מטפל">{x.case.banker.name_he}</KV>
        <KV k="שלב רשמי בבנק">{x.case.bank_stage.label_he} <Tag kind="demo" /></KV>
        {x.case.submitted_at && <KV k="הוגשה"><span className="ltr">{timeHe(x.case.submitted_at)}</span></KV>}
      </dl>}
    </Card>
  );
}

// ---------------------------------------------------------------- C · the customer's documents
function Documents({ ctx, ws, onOpen }: { ctx: Ctx; ws: Workspace; onOpen: (d: DocItem) => void }) {
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
  const primary = !p || !p.total ? { text: d.state_he, tone: "neutral" }
    : waiting ? { text: `התקבלו ${p.done} מתוך ${p.total} דרישות · ${waiting === 1 ? "פריט אחד ממתין" : `${waiting} פריטים ממתינים`} ללקוח`, tone: "warn" }
      : p.done >= p.total ? { text: "כל המסמכים הנדרשים התקבלו ונבדקו ב-AI", tone: "ok" }
        : { text: `${p.done} מתוך ${p.total} דרישות הושלמו · ${unmet.map((q) => `${q.title_he} — ${q.state_he}`).join(" · ")}`, tone: "warn" };
  const banker = d.open_findings ? `${d.open_findings === 1 ? "ממצא אחד" : `${d.open_findings} ממצאים`} לשיקול דעתך`
    : d.awaiting_decision ? `${d.awaiting_decision === 1 ? "מסמך אחד נבדק ב-AI וממתין" : `${d.awaiting_decision} מסמכים נבדקו ב-AI וממתינים`} לקבלה פורמלית שלך`
      : d.total && d.accepted >= d.total ? "כל המסמכים התקבלו על ידך" : null;
  return (
    <Card id="cc-docs" title="מסמכים שצירף הלקוח" testId="cc-docs"
      aside={p && p.total ? <span className={`cc-count t-${primary.tone}`} data-testid="cc-doc-count"><span className="ltr">{p.done}/{p.total}</span> דרישות</span> : undefined}>
      <div className="cc-docstate" data-testid="cc-docstate">
        <div className={`cc-docstate-main t-${primary.tone}`} data-testid="cc-docstate-main">{primary.text}</div>
        {banker && <div className="cc-docstate-sub" data-testid="cc-docstate-banker"><b>בדיקת בנקאי:</b> {banker}
          {d.awaiting_decision > 0 && <button className="cc-link" onClick={() => ctx.openV1(null)}>לסקירת המסמכים</button>}</div>}
      </div>
      <div className="cc-gallery" data-testid="cc-gallery">
        {active.map((i) => <DocTile key={i.document_id} doc={i} onOpen={() => onOpen(i)} />)}
        {missing.map((m) => (
          <button key={m.id} className="cc-doc missing" onClick={() => ctx.openV1(m.id)} data-testid="cc-missing" title="פתיחה בסקירת המסמכים">
            <span className="cc-thumb"><span className="cc-thumb-miss">חסר</span></span>
            <span className="cc-doc-meta"><span className="cc-doc-name">{m.title_he}</span>
              <span className="cc-doc-st t-warn">{m.open_request ? "נשלחה בקשה ללקוח" : m.status_he}</span></span>
          </button>
        ))}
        {!active.length && !missing.length && <div className="cc-empty">טרם הועלו מסמכים לתיק.</div>}
      </div>
      <div className="cc-docfoot">
        <Toggle open={reqs} onClick={() => setReqs(!reqs)} testId="cc-reqs-toggle">דרישות המסמכים לפי מדיניות ההלוואה</Toggle>
        {replaced.length > 0 && <Toggle open={old} onClick={() => setOld(!old)} testId="cc-replaced-toggle">
          {replaced.length === 1 ? "מסמך אחד שהוחלף" : `${replaced.length} מסמכים שהוחלפו`}</Toggle>}
      </div>
      {reqs && <ul className="cc-reqs" data-testid="cc-reqs">{d.requirements.map((q, i) => (
        <li key={i} className={q.satisfied ? "ok" : "miss"}><span className="cc-req-i" aria-hidden>{q.satisfied ? "✓" : "•"}</span>
          <span>{q.title_he}</span><span className="cc-muted">{q.state_he}</span></li>))}</ul>}
      {old && <div className="cc-gallery quiet" data-testid="cc-replaced">{replaced.map((i) => <DocTile key={i.document_id} doc={i} onOpen={() => onOpen(i)} />)}</div>}
    </Card>
  );
}

function DocTile({ doc, onOpen }: { doc: DocItem; onOpen: () => void }) {
  const [failed, setFailed] = useState(false);
  const ext = (doc.filename.split(".").pop() || "").toUpperCase();
  return (
    <button className={`cc-doc${doc.replaced_by ? " old" : ""}`} onClick={onOpen} data-testid="cc-doc" data-doc={doc.document_id} title={`פתיחת ${doc.filename}`}>
      <span className="cc-thumb">
        {failed ? <span className="cc-thumb-icon" data-testid="cc-thumb-fallback">{ext || "קובץ"}</span>
          : <img src={`/api/documents/${doc.document_id}/pages/1.png?dpi=60`} alt={`עמוד ראשון — ${doc.doc_type_he}`} loading="lazy" onError={() => setFailed(true)} data-testid="cc-thumb" />}
        {doc.pages > 1 && <span className="cc-thumb-pages">{doc.pages} עמ׳</span>}
      </span>
      <span className="cc-doc-meta">
        <span className="cc-doc-name">{doc.doc_type_he}{doc.period_he ? ` · ${doc.period_he}` : ""}</span>
        <span className="cc-doc-file ltr">{doc.filename}</span>
        <span className={`cc-doc-st t-${doc.ai.tone}`}>{doc.replaced_by ? "הוחלף במסמך חדש" : `AI: ${doc.ai.verdict_he}`}</span>
        {!doc.replaced_by && <span className="cc-doc-bk">{doc.banker.status_he}</span>}
      </span>
    </button>
  );
}

function DocDrawer({ doc, ctx, onClose }: { doc: DocItem; ctx: Ctx; onClose: () => void }) {
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
  return (
    <div className="bi-drawer-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className="bi-drawer cc-docdrawer" role="dialog" aria-label={`מסמך: ${doc.filename}`} data-testid="cc-docdrawer" data-doc={doc.document_id}>
        <header className="bi-dr-head">
          <span className="bi-dr-kind">מסמך שצירף הלקוח</span>
          <button className="bi-dr-x" onClick={onClose} aria-label="סגירה" data-testid="cc-docdrawer-close">×</button>
        </header>
        <div className="bi-dr-title">{doc.doc_type_he}{doc.period_he ? ` · ${doc.period_he}` : ""}</div>
        <div className="cc-muted ltr">{doc.filename}</div>
        <dl className="bi-dr-meta">
          <div><dt>בדיקת AI</dt><dd className={`cc-doc-st t-${doc.ai.tone}`}>{doc.ai.verdict_he}</dd></div>
          <div><dt>החלטת בנקאי</dt><dd>{doc.banker.status_he}</dd></div>
          {doc.ai.summary_he && <div className="cc-span2"><dt>סיכום הבדיקה</dt><dd>{doc.ai.summary_he}</dd></div>}
        </dl>
        {doc.ai.attention_he.length > 0 && <ul className="cc-drawer-attn">{doc.ai.attention_he.map((t, i) => <li key={i}>{t}</li>)}</ul>}
        <div className="bi-dr-actions">
          <button className="btn btn-dark btn-sm" onClick={() => { onClose(); ctx.openV1(doc.id); }} data-testid="cc-doc-v1">פתיחה בסקירת המסמכים</button>
          <a className="btn btn-ghost btn-sm" href={`/api/documents/${doc.document_id}/file`} target="_blank" rel="noreferrer" data-testid="cc-doc-original">הקובץ המקורי ↗</a>
          {doc.pages > 1 && <span className="cc-pager">
            <button className="btn btn-soft btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>→</button>
            <span>עמוד <span className="ltr">{page}/{doc.pages}</span></span>
            <button className="btn btn-soft btn-sm" disabled={page >= doc.pages} onClick={() => setPage(page + 1)}>←</button></span>}
        </div>
        <div className="bi-dr-viewer" data-testid="cc-doc-evidence">
          <EvidenceViewer documentId={doc.document_id} facts={doc.ai.facts} page={page} focus={focus} onFocus={pick} interactive dpi={130} autoScroll={!!focus} />
        </div>
        {doc.ai.facts.length > 0 && <div className="cc-facts" data-testid="cc-doc-facts">
          <div className="cc-group-k">נתונים שחולצו מהמסמך</div>
          <FactList facts={doc.ai.facts} focus={focus} onFocus={pick} />
        </div>}
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------- D · financial analysis
function Financial({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const a = x.analysis;
  const gaps = x.discrepancies;
  return (
    <Card id="cc-fin" title="ניתוח פיננסי" testId="cc-financial"
      sub="הכנסה מתלושי השכר, התחייבויות מנתוני הבנק (דמו) ויחסי החזר שחושבו בקוד."
      aside={<span className={`cc-avail a-${a.availability}`} data-testid="cc-availability">{a.status_he}</span>}>
      {gaps.map((g, i) => (
        <div key={i} className={`cc-gap${g.open ? " open" : ""}`} data-testid="cc-discrepancy" data-kind={g.kind} data-open={g.open}>
          <div className="cc-gap-head"><b>{g.title_he}{g.first_name_he ? ` · ${g.first_name_he}` : ""}</b><span className="cc-gap-st">{g.status_he}</span></div>
          <div className="cc-gap-vals">
            <div><span>{g.kind === "income" ? "מוצהר בבקשה" : "בבקשה"}</span><Num ctx={ctx} d={g.declared} /></div>
            <div><span>{g.kind === "income" ? "ממוצע בתלושים" : "בהצעת המחיר"}</span><Num ctx={ctx} d={g.documented} /></div>
            <div><span>הפרש</span><b className="ltr">{money(g.difference_ils != null ? Math.abs(g.difference_ils) : null)}{g.difference_pct != null ? ` · ${Math.abs(g.difference_pct).toFixed(1)}%` : ""}</b></div>
          </div>
          <p>{g.explanation_he}</p>
          <div className="cc-gap-act"><span>{g.action_he}</span>
            <button className="btn btn-ghost btn-sm" onClick={() => ctx.openV1(g.v1_item)} data-testid="cc-gap-open">בירור בסקירת המסמכים</button></div>
        </div>
      ))}
      {a.declared_alternative && <div className="cc-note warn" data-testid="cc-declared-alt">
        על בסיס ההכנסה המוצהרת ({money(a.declared_alternative.income_ils)}) היחס הכולל היה <b className="ltr">{pct(a.declared_alternative.combined_dsr_pct)}</b>.
        הניתוח לא בוחר בנתון שמציג את הבקשה טוב יותר עד לבירור הפער.</div>}
      {a.availability === "partial" && a.reasons_he.length > 0 && <div className="cc-note warn" data-testid="cc-partial">{a.reasons_he.join(" ")}</div>}
      {x.income.borrowers.map((r) => <IncomeRow key={r.borrower_id} ctx={ctx} r={r} />)}
      <Obligations ctx={ctx} />
      <CalcDetails ctx={ctx} />
    </Card>
  );
}

function IncomeRow({ ctx, r }: { ctx: Ctx; r: Intelligence["income"]["borrowers"][number] }) {
  const [open, setOpen] = useState(false);
  const max = Math.max(1, ...r.months.map((m) => m.net_ils || 0));
  const q = { verified: "מאומת בתלושים", partial: "חלקי", declared: "מוצהר בלבד", missing: "אין נתון" }[r.quality];
  return (
    <div className="cc-block" data-testid="cc-income" data-borrower={r.borrower_id}>
      <div className="cc-block-head">
        <div>
          <h3>הכנסה{ctx.x.income.borrowers.length > 1 ? ` — ${r.first_name_he}` : ""} <span className={`cc-q q-${r.quality}`}>{q}</span>
            {r.unresolved_discrepancy && <span className="cc-q q-gap">פער פתוח</span>}</h3>
          <div className="cc-line">
            {r.documented_avg.value != null ? <>הכנסה ממוצעת: <Num ctx={ctx} d={r.documented_avg} testId="cc-income-avg" /></>
              : <>מוצהר בבקשה: <Num ctx={ctx} d={r.declared} /></>}
            {r.variability_pct != null && <> · שונות בין חודשים: <b className="ltr">{pct(r.variability_pct)}</b></>}
            {r.documented_avg.value != null && r.declared.value != null && <> · מוצהר בבקשה: <Num ctx={ctx} d={r.declared} /></>}
          </div>
        </div>
        {r.months.length > 0 && <Toggle open={open} onClick={() => setOpen(!open)} testId="cc-payslips-toggle">{open ? "הסתר תלושי שכר" : "הצג תלושי שכר"}</Toggle>}
      </div>
      {open && <table className="cc-table cc-months" data-testid="cc-months">
        <thead><tr><th>חודש</th><th>נטו בתלוש</th><th /><th>מקור</th></tr></thead>
        <tbody>{r.months.map((m) => {
          const s = m.source_id ? ctx.x.sources[m.source_id] : null;
          return (
            <tr key={m.period}>
              <td>{m.period_he}</td>
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
  const { x } = ctx;
  const bc = x.bank_context;
  const a = x.analysis;
  const [open, setOpen] = useState(false);
  const flagged = bc.events.filter((e) => e.returned_checks_12m || e.arrears_12m || e.restrictions_he.length);
  return (
    <div className="cc-block" data-testid="cc-obligations">
      <div className="cc-block-head">
        <div>
          <h3>התחייבויות ומסגרות אשראי {bc.available && <Tag kind="demo">נתוני דמו</Tag>}</h3>
          {!bc.available ? <div className="cc-line cc-muted">אין נתוני הקשר בנקאי להדגמה עבור {bc.missing_for.join(", ") || "המבקשים"} — ההתחייבויות הקיימות לא ידועות,
            והיחס הכולל כולל רק את ההלוואה המבוקשת.</div>
            : <div className="cc-line">החזרים קיימים: <Num ctx={ctx} d={a.existing_debt} testId="cc-existing" /> לחודש
              {" · "}{bc.loans.length === 1 ? "הלוואה אחת" : `${bc.loans.length} הלוואות`}
              {bc.exposure && <> · אובליגו מנוצל <Num ctx={ctx} d={bc.exposure.utilized} testId="cc-exposure-utilized" /> מתוך <Num ctx={ctx} d={bc.exposure.approved} /></>}
            </div>}
        </div>
        {bc.available && <Toggle open={open} onClick={() => setOpen(!open)} testId="cc-obligations-toggle">{open ? "הסתר פירוט" : "הצג פירוט"}</Toggle>}
      </div>
      {flagged.map((e) => <div key={e.source_id} className="cc-note warn" data-testid="cc-event">אירועי חשבון ב־12 חודשים ({e.owner_he}): {e.detail_he.join(" ")}{" "}
        <SrcText ctx={ctx} id={e.source_id}>מקור</SrcText> · יש לאמת במערכות הבנק.</div>)}
      {open && bc.available && <div className="cc-obl" data-testid="cc-obligations-detail">
        <table className="cc-table">
          <thead><tr><th>הלוואה קיימת</th><th>יתרת קרן</th><th>החזר חודשי</th><th>נותרו</th></tr></thead>
          <tbody>{bc.loans.length ? bc.loans.map((l) => (
            <tr key={l.id}><td>{l.type_he}<div className="cc-tiny">{l.lender_he} · {l.owner_he}</div></td>
              <td><Num ctx={ctx} d={l.outstanding} /></td><td><Num ctx={ctx} d={l.monthly} testId="cc-loan-monthly" /></td>
              <td className="ltr">{l.remaining_payments}</td></tr>)) : <tr><td colSpan={4} className="cc-muted">אין הלוואות קיימות בנתוני הדמו</td></tr>}</tbody>
        </table>
        {bc.credit_lines.length > 0 && <table className="cc-table">
          <thead><tr><th>מסגרת אשראי</th><th>מסגרת</th><th>מנוצל</th><th>ניצול</th></tr></thead>
          <tbody>{bc.credit_lines.map((l) => (
            <tr key={l.id}><td>{l.type_he}<div className="cc-tiny">{l.owner_he}</div></td><td className="ltr">{money(l.limit_ils)}</td>
              <td><button className="cc-num k-demo" onClick={() => ctx.open(l.source_id)}><span className="ltr">{money(l.utilized_ils)}</span></button></td>
              <td><span className="cc-bar demo"><span style={{ width: `${Math.min(100, (l.utilized_ils / (l.limit_ils || 1)) * 100)}%` }} /></span></td></tr>))}</tbody>
        </table>}
        <ul className="cc-notes">
          <li><b>לא נספר פעמיים:</b> יתרות ומסגרות הן חשיפה (אובליגו), לא החזר חודשי. רק ההחזרים החודשיים נכנסים ליחס ההחזר.</li>
          {bc.card_spending.map((s) => <li key={s.source_id}>חיובי כרטיס ({s.owner_he}): <button className="cc-num k-demo" onClick={() => ctx.open(s.source_id)}>
            <span className="ltr">{money(s.avg_monthly_ils)}</span></button> בממוצע לחודש — הוצאה שוטפת, אינה החזר חוב ואינה נכללת ביחס.</li>)}
          {bc.events.filter((e) => !flagged.includes(e)).map((e) => <li key={e.source_id}>אירועי חשבון ב־12 חודשים ({e.owner_he}): ללא שיקים חוזרים, פיגורים או הגבלות.</li>)}
        </ul>
        <div className="cc-srcnote">מקור: {bc.fixture_ids.join(", ")} · נכון ל־<span className="ltr">{bc.observed_at}</span> · נתונים סינתטיים להדגמה, לא נשלפו ממערכות הבנק
          {bc.missing_for.length ? ` · חסר עבור ${bc.missing_for.join(", ")}` : ""}</div>
      </div>}
    </div>
  );
}

function CalcDetails({ ctx }: { ctx: Ctx }) {
  const a = ctx.x.analysis;
  const [open, setOpen] = useState(false);
  return (
    <div className="cc-block quiet">
      <Toggle open={open} onClick={() => setOpen(!open)} testId="cc-calc-toggle">פירוט החישוב</Toggle>
      {open && <dl className="cc-kvs cc-kvs-quiet" data-testid="cc-calc">
        <KV k="הכנסה נטו לחישוב"><Num ctx={ctx} d={a.income} /></KV>
        <KV k="החזרים קיימים בחודש"><Num ctx={ctx} d={a.existing_debt} /></KV>
        <KV k="יחס החזר קיים"><Num ctx={ctx} d={a.existing_dsr} /></KV>
        <KV k="יחס החזר כולל בבקשה"><Num ctx={ctx} d={a.combined_dsr} testId="cc-calc-combined" /></KV>
        <KV k="שיעור מימון מהאסמכתה"><Num ctx={ctx} d={a.ltv} /></KV>
        <KV k="הכנסה שנותרת אחרי החזרי חוב (תיאורי)"><Num ctx={ctx} d={a.remaining_after_debt} /></KV>
      </dl>}
    </div>
  );
}

// ---------------------------------------------------------------- E · financing alternatives
function Alternatives({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const s = x.simulation;
  const base = s.inputs;
  const [principal, setPrincipal] = useState(base.principal);
  const [term, setTerm] = useState(base.term_months);
  const [rate, setRate] = useState(base.annual_rate_pct);
  const [whatIf, setWhatIf] = useState(false);
  useEffect(() => { setPrincipal(base.principal); setTerm(base.term_months); setRate(base.annual_rate_pct); }, [x.case_id, base.principal, base.term_months, base.annual_rate_pct]);
  const changed = principal !== base.principal || term !== base.term_months || rate !== base.annual_rate_pct;
  const rows: Scenario[] = useMemo(() => simulate(principal, term, rate, s.income_ils, s.existing_debt_ils, s.asset_price_ils, s.bounds),
    [principal, term, rate, s]);
  const reset = () => { setPrincipal(base.principal); setTerm(base.term_months); setRate(base.annual_rate_pct); };
  if (!s.enabled) return (
    <Card id="cc-alt" title="חלופות מימון" testId="cc-alternatives"><div className="cc-empty">אין בבקשה סכום ומספר תשלומים לחישוב.</div></Card>);
  const thr = s.threshold_pct;
  const short = rows[0], long = rows[rows.length - 1];
  const src = (r: Scenario, what: "pay" | "dsr" | "total") => scenarioSource(s, r, what, principal, term, rate);
  return (
    <Card id="cc-alt" title="חלופות מימון" testId="cc-alternatives"
      sub="שלוש חלופות להמחשת השפעת תקופת ההחזר על התשלום החודשי ועלות המימון. להמחשה בלבד — לא הצעה מחייבת."
      aside={<>
        {changed && <button className="btn btn-soft btn-sm" onClick={reset} data-testid="cc-wi-reset">חזרה לנתוני הבקשה</button>}
        <Toggle open={whatIf} onClick={() => setWhatIf(!whatIf)} testId="cc-whatif-toggle">מה יקרה אם?</Toggle></>}>
      {x.analysis.availability !== "full" && <div className="cc-note warn" data-testid="cc-sim-provisional">
        {x.analysis.availability === "unavailable" ? "ניתוח היחסים אינו זמין לתיק זה — מוצגים החזרים ועלויות בלבד."
          : x.analysis.availability === "provisional" ? "החלופות מוצגות להמחשה בלבד — הניתוח הפיננסי זמני עד לבירור הפער."
            : "החלופות מוצגות להמחשה בלבד — הניתוח הפיננסי חלקי."}</div>}
      {whatIf && <div className="cc-whatif" data-testid="cc-whatif">
        <Slider label="סכום ההלוואה" value={principal} min={10000} max={s.bounds.principal_max} step={1000} onChange={setPrincipal} display={money(principal)}
          testId="cc-wi-principal" changed={principal !== base.principal} />
        <Slider label="תקופה (תשלומים)" value={term} min={s.bounds.term_min} max={s.bounds.term_max} step={6} onChange={setTerm}
          display={`${term} · ${years(term)}`} testId="cc-wi-term" changed={term !== base.term_months} />
        <Slider label="ריבית שנתית להמחשה" value={rate} min={0} max={15} step={0.1} onChange={(v) => setRate(Math.round(v * 10) / 10)} display={`${rate.toFixed(1)}%`}
          testId="cc-wi-rate" changed={rate !== base.annual_rate_pct}
          hint={<>ברירת מחדל <SrcText ctx={ctx} id={s.rate_source_id}>{base.annual_rate_pct.toFixed(1)}%</SrcText> · הנחת הדגמה</>} />
        <p className="cc-whatif-n">השינויים מחושבים מיד ואינם נשמרים — הבקשה, ההכנסה וההתחייבויות אינן משתנות.</p>
      </div>}
      {changed && <div className="cc-simbadge" data-testid="cc-sim-active">סימולציה פעילה: {money(principal)} · {term} תשלומים · {rate.toFixed(1)}%</div>}
      <div className="cc-scs">
        {rows.map((r) => {
          const requested = r.key === "requested";
          const suggested = !changed && s.suggested?.key === r.key;
          const over = r.combined_dsr_pct != null && r.combined_dsr_pct > thr;
          return (
            <article key={r.key} className={`cc-sc${requested ? " req" : ""}${suggested ? " sug" : ""}`} data-testid="cc-scenario" data-key={r.key} data-term={r.term_months}>
              <header>
                <span className="cc-sc-k">{requested && changed ? "התקופה שנבחרה" : SC_LABEL[r.key]}</span>
                {requested && !changed && <span className="cc-sc-tag">הבקשה המקורית</span>}
                {suggested && <span className="cc-sc-tag sug" title={s.suggested?.label_he}>חלופה להמחשה</span>}
              </header>
              <div className="cc-sc-term"><b className="ltr">{r.term_months}</b> תשלומים · {years(r.term_months)} · <span className="ltr">{money(r.principal_ils)}</span></div>
              <button className="cc-sc-pay" onClick={() => ctx.open(src(r, "pay"))} data-testid="cc-sc-pay" data-value={r.monthly_payment_ils}>
                <span className="ltr">{money(r.monthly_payment_ils)}</span><small>לחודש</small></button>
              <dl>
                <div><dt>סך התשלומים</dt><dd className="ltr" data-testid="cc-sc-total">{money(r.total_payments_ils)}</dd></div>
                <div><dt>עלות המימון</dt><dd><button className="cc-num k-calc" onClick={() => ctx.open(src(r, "total"))} data-testid="cc-sc-interest"
                  data-value={r.total_interest_ils}><span className="ltr">{money(r.total_interest_ils)}</span></button></dd></div>
                <div><dt>יחס החזר כולל</dt><dd><button className={`cc-num k-calc${over ? " over" : ""}`} onClick={() => ctx.open(src(r, "dsr"))} data-testid="cc-sc-dsr"
                  data-value={r.combined_dsr_pct ?? ""}><span className="ltr">{pct(r.combined_dsr_pct)}</span></button></dd></div>
              </dl>
            </article>
          );
        })}
      </div>
      {rows.length > 1 && <p className="cc-compare" data-testid="cc-compare">
        בפריסה ל־<b className="ltr">{long.term_months}</b> תשלומים ההחזר החודשי נמוך ב־<b className="ltr">{money(short.monthly_payment_ils - long.monthly_payment_ils)}</b> מאשר
        ב־<b className="ltr">{short.term_months}</b>, אך עלות המימון גבוהה ב־<b className="ltr">{money(long.total_interest_ils - short.total_interest_ils)}</b>.
        {" "}הריבית (<SrcText ctx={ctx} id={s.rate_source_id}>{rate.toFixed(1)}%</SrcText>) והסף ליחס ההחזר (<SrcText ctx={ctx} id={s.threshold_source_id}>{thr}%</SrcText>) הם הנחות הדגמה.</p>}
      {x.analysis.illustrative_max_principal != null && <p className="cc-muted cc-small" data-testid="cc-max-principal">להמחשה: בהנחות אלה, סכום של עד <b className="ltr">{money(x.analysis.illustrative_max_principal)}</b> ל־{base.term_months} תשלומים
        משאיר את היחס הכולל בתוך {thr}% — אינו סכום מאושר.</p>}
    </Card>
  );
}

// ---------------------------------------------------------------- F · reasoning and conditions
function Reasoning({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const r = x.recommendation;
  const [more, setMore] = useState(false);
  const open = x.risks.filter((k) => k.kind !== "missing");
  const docSources = Object.values(x.sources).filter((s) => s.kind === "document");
  return (
    <Card id="cc-why" title="נימוקי ההמלצה ותנאים להתקדמות" testId="cc-reasoning">
      <div className="cc-cols">
        <div>
          <h3>ממצאים עיקריים</h3>
          <ul className="cc-cons" data-testid="cc-considerations">{r.considerations.map((c, i) => (
            <li key={i} className={`c-${c.tone}`} data-testid="cc-consideration"><span>{c.text_he}</span>
              <ConsSources ctx={ctx} ids={c.source_ids} />
            </li>))}</ul>
        </div>
        <div>
          <h3>נדרש לפני החלטה</h3>
          <ul className="cc-verify" data-testid="cc-verify">{r.verify.map((v, i) => <li key={i}>{v.v1_item
            ? <button className="cc-link" onClick={() => ctx.openV1(v.v1_item)}>{v.text_he}</button> : v.text_he}</li>)}</ul>
        </div>
      </div>
      {open.length > 0 && <ul className="cc-risks" data-testid="cc-risks">{open.map((k, i) => (
        <li key={i}><span className="cc-risk-who">{k.who_he}</span><span><b>{k.title_he}</b>{k.text_he ? ` — ${k.text_he}` : ""}</span>
          <button className="cc-link" onClick={() => ctx.openV1(k.v1_item)}>פתיחה</button></li>))}</ul>}
      <Toggle open={more} onClick={() => setMore(!more)} testId="cc-why-more">{more ? "הסתר פירוט ונימוקים" : "הצג פירוט ונימוקים"}</Toggle>
      {more && <div className="cc-cols cc-why-more" data-testid="cc-why-detail">
        <div>
          <h3>נתונים שחולצו ממסמכים ושימשו בניתוח</h3>
          {docSources.length ? <ul className="cc-evlist" data-testid="cc-evlist">{docSources.map((s) => (
            <li key={s.id}><button className="cc-evrow" onClick={() => ctx.open(s)} data-testid="cc-evrow" data-field={s.field}>
              <span>{s.label_he}</span><span className="ltr">{s.value_raw}</span><Tag kind={markOf(s)} /></button></li>))}</ul>
            : <div className="cc-empty">אין עדיין נתונים שחולצו ממסמכים.</div>}
        </div>
        <div>
          <h3>מה לא נבדק</h3>
          <ul className="cc-unknowns">{x.unknowns.map((u, i) => <li key={i}><b>{u.label_he}:</b> {u.text_he}</li>)}</ul>
          <h3>סימוני מקור</h3>
          <ul className="cc-legend">{(["reviewed", "verified", "declared", "demo", "calc", "assume"] as MarkKind[]).map((k) => (
            <li key={k}><Tag kind={k} /> {MARK[k].title}</li>))}</ul>
        </div>
      </div>}
    </Card>
  );
}

/** One link per kind of source behind a finding; a kind with several sources opens them one after another in the drawer's stack. */
function ConsSources({ ctx, ids }: { ctx: Ctx; ids: string[] }) {
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
      <button key={k} className="cc-srctext" onClick={() => list.slice().reverse().forEach((s) => ctx.open(s))} data-testid="cc-cons-src" data-kind={k}
        title={list.map((s) => s.label_he).join(" · ")}>{MARK[k].label}{list.length > 1 ? ` ×${list.length}` : ""}</button>))}</span>
  );
}

// ---------------------------------------------------------------- G · the reply to the customer
function Reply({ ctx, onToast }: { ctx: Ctx; onToast: (t: { text: string; tone: "ok" | "bad" }) => void }) {
  const { x } = ctx;
  const [kind, setKind] = useState<string | null>(x.recommended_draft);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [refs, setRefs] = useState<Record<string, boolean>>({});
  const area = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { setKind(x.recommended_draft); setTexts({}); setRefs({}); }, [x.case_id, x.recommended_draft]);
  const draft = x.drafts.find((d) => d.kind === kind) || x.drafts[0];
  const text = draft ? texts[draft.kind] ?? draft.message_he : "";
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [text]);
  if (!draft) return <Card id="cc-reply" title="מענה מוצע ללקוח" testId="cc-reply"><div className="cc-empty">אין טיוטה מתאימה למצב התיק כרגע.</div></Card>;
  const edited = texts[draft.kind] != null && texts[draft.kind] !== draft.message_he;
  const chosen = draft.attachments.filter((a) => refs[`${draft.kind}:${a.document_id}`]);
  const full = chosen.length ? `${text}\n\nמסמכים בתיק שההודעה מתייחסת אליהם: ${chosen.map((a) => a.label_he).join(" · ")}` : text;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(full);
      onToast({ text: "המענה הועתק. הוא לא נשלח ללקוח — השליחה נעשית בערוץ הבנק.", tone: "ok" });
    } catch {
      onToast({ text: "ההעתקה נחסמה בדפדפן. אפשר לסמן את הטקסט ולהעתיק ידנית.", tone: "bad" });
    }
  };
  return (
    <Card id="cc-reply" title="מענה מוצע ללקוח" testId="cc-reply" sub="טיוטה שהוכנה ממצב התיק. אפשר לערוך ולהעתיק — שום דבר לא נשלח מכאן.">
      {x.drafts.length > 1 && <div className="cc-dtabs" role="tablist">
        {x.drafts.map((d) => (
          <button key={d.kind} role="tab" aria-selected={d.kind === draft.kind} className={d.kind === draft.kind ? "on" : ""} onClick={() => setKind(d.kind)}
            data-testid="cc-draft-tab" data-kind={d.kind}>{d.title_he}{d.kind === x.recommended_draft && <span className="cc-rec-pill">מומלץ</span>}</button>
        ))}
      </div>}
      <div className="cc-paper">
        <div className="cc-paper-bar">
          <b>{draft.title_he}</b><span className="cc-muted">{DRAFT_NOTE[draft.kind]}</span>
          {edited && <span className="cc-edited" data-testid="cc-draft-edited">נערך על ידך</span>}
          <button className="cc-link" disabled={!edited} onClick={() => setTexts({ ...texts, [draft.kind]: draft.message_he })} data-testid="cc-draft-restore">שחזור הנוסח</button>
        </div>
        <textarea ref={area} className="cc-paper-text" value={text} onChange={(e) => setTexts({ ...texts, [draft.kind]: e.target.value })} dir="rtl"
          data-testid="cc-draft-text" data-kind={draft.kind} aria-label="טיוטת המענה ללקוח" />
      </div>
      {draft.attachments.length > 0 && <div className="cc-refs">
        <span className="cc-refs-k">הפניה למסמכים בתיק (רשות):</span>
        {draft.attachments.map((a) => {
          const k = `${draft.kind}:${a.document_id}`;
          return <label key={k} className={`cc-ref${refs[k] ? " on" : ""}`}><input type="checkbox" checked={!!refs[k]} onChange={() => setRefs({ ...refs, [k]: !refs[k] })} />{a.label_he}</label>;
        })}
      </div>}
      <div className="cc-dbar">
        <button className="cc-primary" onClick={copy} data-testid="cc-draft-copy">העתקת המענה</button>
        <span className="cc-muted cc-small">אין שליחה אוטומטית ואין אישור מסירה. הנוסח נבנה מתבנית קבועה — לא מטקסט של מודל, ובלי יחסי החזר או הערות פנימיות.</span>
      </div>
    </Card>
  );
}
