import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, timeHe, usePolling, type Datum, type DocItem, type IntelSource, type Intelligence, type SourceInput, type Workspace } from "../../api";
import { EvidenceViewer } from "../../components/EvidenceViewer";
import { scenarios as simulate, type Scenario } from "../../finance";
import { Toast } from "./deskUi";
import "./intelligence.css";

/** Banker Intelligence V2: one case, the conclusion first. Read-only — every state change happens in the review
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
  const ctx: Ctx = { x, open, openV1 };
  return (
    <div className="bi-scroll" data-testid="bi-root" data-case={caseId}>
      <div className="bi-page">
        <Briefing ctx={ctx} />
        <div className="bi-grid">
          <main className="bi-main">
            <Overview ctx={ctx} />
            <Financial ctx={ctx} />
            <Simulator ctx={ctx} />
            <EvidenceRisks ctx={ctx} />
            <p className="bi-foot">{x.disclaimer_he} · עודכן <span className="ltr">{timeHe(x.generated_at)}</span></p>
          </main>
          <aside className="bi-aside"><ActionPanel ctx={ctx} onToast={setToast} /></aside>
        </div>
      </div>
      {stack.length > 0 && <SourceDrawer src={stack[stack.length - 1]} depth={stack.length} ws={ws} ctx={ctx}
        onBack={() => setStack((s) => s.slice(0, -1))} onClose={() => setStack([])} />}
      <Toast message={toast} onClose={clearToast} />
    </div>
  );
}

interface Ctx { x: Intelligence; open: (s: string | IntelSource | null | undefined) => void; openV1: (item?: string | null) => void }

// ---------------------------------------------------------------- formatting and provenance marks
const nf0 = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("he-IL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const money = (v?: number | null, exact = false) => (v == null ? "—" : `₪${(exact ? nf2 : nf0).format(v)}`);
const pct = (v?: number | null) => (v == null ? "—" : `${v.toFixed(1)}%`);
const fmt = (v: number | string | null | undefined, unit?: string, exact = false) =>
  v == null ? "—" : typeof v === "string" ? v : unit === "pct" ? pct(v) : unit === "months" ? `${v} תשלומים` : money(v, exact);
const years = (m: number) => (m % 12 === 0 ? `${m / 12} שנים` : `${(m / 12).toFixed(1)} שנים`);

type MarkKind = "verified" | "reviewed" | "unverified" | "declared" | "demo" | "calc" | "assume" | "missing" | "sim";
const MARK: Record<MarkKind, { label: string; title: string }> = {
  verified: { label: "מסמך ✓", title: "חולץ ממסמך ואומת מול הקובץ" },
  reviewed: { label: "נבדק ✓✓", title: "חולץ ממסמך, אומת מול הקובץ, והמסמך התקבל על ידי הבנקאי" },
  unverified: { label: "מסמך", title: "חולץ ממסמך — לא אומת מול הקובץ" },
  declared: { label: "מוצהר", title: "הצהרת הלקוח בבקשה — לא מאומת" },
  demo: { label: "דמו", title: "נתון בנקאי סינתטי להדגמה — לא נתון אמיתי ולא מאומת" },
  calc: { label: "חישוב", title: "חושב בקוד מנתונים אחרים — לחצו לנוסחה ולקלטים" },
  assume: { label: "הנחה", title: "הנחת הדגמה — אינה מדיניות או ריבית של הבנק" },
  missing: { label: "חסר", title: "הנתון אינו זמין" },
  sim: { label: "סימולציה", title: "ערך שהוזן בסימולציה — לא נשמר ואינו משנה את הבקשה" },
};
function markOf(s?: IntelSource | null): MarkKind {
  if (!s) return "missing";
  if (s.kind === "document") return s.banker_reviewed ? "reviewed" : s.verified ? "verified" : "unverified";
  return ({ declared: "declared", synthetic_bank: "demo", calculated: "calc", assumption: "assume", missing: "missing" } as Record<string, MarkKind>)[s.kind] || "missing";
}
function Mark({ kind }: { kind: MarkKind }) {
  return <span className={`bi-mark m-${kind}`} title={MARK[kind].title} data-testid="bi-mark" data-mark={kind}>{MARK[kind].label}</span>;
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

function Section({ title, sub, children, testId, aside }: { title: string; sub?: ReactNode; children: ReactNode; testId: string; aside?: ReactNode }) {
  return (
    <section className="bi-sec" data-testid={testId}>
      <header className="bi-sec-head"><div><h2>{title}</h2>{sub && <p className="bi-sub">{sub}</p>}</div>{aside}</header>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------- the conclusion first
const STATE_TONE: Record<string, string> = { READY_FOR_CREDIT_REVIEW: "ok", PREPARATION_CONFIRMED: "ok", CLARIFICATION_REQUIRED: "warn",
  DOCUMENTS_INCOMPLETE: "warn", NO_DOCUMENTS: "neutral", PROCESSING: "neutral", ERROR: "bad" };
const FIN_TONE: Record<string, string> = { full: "ok", partial: "warn", provisional: "warn", unavailable: "neutral" };

function Briefing({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const r = x.recommendation;
  const [why, setWhy] = useState(true);
  const counts = useMemo(() => {
    const used = new Set<string>();
    const walk = (id?: string | null) => {
      if (!id || used.has(id) || !x.sources[id]) return;
      used.add(id);
      for (const i of x.sources[id].inputs || []) walk(i.source_id);
    };
    r.considerations.forEach((c) => c.source_ids.forEach(walk));
    Object.values(x.analysis).forEach((v) => { if (v && typeof v === "object" && "source_id" in v) walk((v as Datum).source_id); });
    const by: Record<string, number> = {};
    used.forEach((id) => { const k = markOf(x.sources[id]); by[k] = (by[k] || 0) + 1; });
    return by;
  }, [x, r.considerations]);
  return (
    <section className={`bi-brief t-${STATE_TONE[r.state] || "neutral"}`} data-testid="bi-brief" data-state={r.state}>
      <div className="bi-brief-main">
        <div className="bi-eyebrow">
          <span className="bi-jeen">סיכום JEEN</span>
          <span>תיק <b className="ltr">{x.case.display_number}</b> · {x.applicant.company?.name_he || x.applicant.borrowers.map((b) => b.name_he).join(" ו")}</span>
          <span className="bi-eyebrow-sep" />
          <span className="bi-state" data-testid="bi-rec-state">{r.documentation.status_he}</span>
        </div>
        <h1 className="bi-headline" data-testid="bi-headline">{r.headline_he}</h1>
        <div className="bi-tracks">
          <div className="bi-track" data-testid="bi-track-docs">
            <div className="bi-track-k">מסלול המסמכים</div>
            <div className="bi-track-v">{r.documentation.status_he}
              {x.documents.progress && x.documents.progress.total > 0 && <span className="bi-track-n ltr">{x.documents.progress.done}/{x.documents.progress.total}</span>}</div>
            <div className="bi-track-t">{x.documents.missing.length + x.documents.corrections.length > 0
              ? `${x.documents.missing.length + x.documents.corrections.length} פריטים ממתינים ללקוח`
              : x.documents.open_findings ? `${x.documents.open_findings === 1 ? "ממצא אחד" : `${x.documents.open_findings} ממצאים`} לשיקול דעתך`
                : x.documents.awaiting_decision ? `${x.documents.awaiting_decision === 1 ? "מסמך אחד ממתין" : `${x.documents.awaiting_decision} מסמכים ממתינים`} לקבלה פורמלית שלך`
                  : x.documents.total ? "כל המסמכים טופלו" : "טרם הועלו מסמכים"}</div>
          </div>
          <div className={`bi-track fin f-${FIN_TONE[r.financial.availability]}`} data-testid="bi-track-fin" data-availability={r.financial.availability}>
            <div className="bi-track-k">הערכה פיננסית להמחשה</div>
            <div className="bi-track-v">{r.financial.status_he}</div>
            <div className="bi-track-t">{r.financial.text_he}</div>
            {r.financial.suggested && <div className="bi-suggest" data-testid="bi-suggested">
              <b>{r.financial.suggested.term_months ? `חלופה להמחשה: ${r.financial.suggested.term_months} תשלומים` : "אין חלופה בתוך הנחת ההדגמה"}</b> · {r.financial.suggested.why_he}
              <span className="bi-suggest-tag">{r.financial.suggested.label_he}</span></div>}
          </div>
          <div className="bi-next" data-testid="bi-next-action">
            <div className="bi-track-k">הפעולה הבאה שלך</div>
            <button className="bi-next-btn" onClick={() => ctx.openV1(r.next_action.v1_item)} disabled={r.next_action.kind === "wait"}
              data-testid="bi-next-btn">{r.next_action.label_he} <span aria-hidden>←</span></button>
            <div className="bi-track-t">פעולות נרשמות בסקירת המסמכים (V1), עם נימוק וביומן.</div>
          </div>
        </div>
      </div>
      <div className="bi-why">
        <button className="bi-why-head" onClick={() => setWhy(!why)} aria-expanded={why} data-testid="bi-why-toggle">
          למה זו ההמלצה <span className="bi-why-n">{r.considerations.length} שיקולים · {r.verify.length} לאימות</span><span aria-hidden>{why ? "▴" : "▾"}</span></button>
        {why && <div className="bi-why-body" data-testid="bi-considerations">
          <ul className="bi-cons">
            {r.considerations.map((c, i) => (
              <li key={i} className={`c-${c.tone}`} data-testid="bi-consideration">
                <span className="bi-cons-t">{c.text_he}</span>
                <span className="bi-cons-src">{c.source_ids.filter((id) => x.sources[id]).map((id) => (
                  <button key={id} className="bi-chipsrc" onClick={() => ctx.open(id)} title={x.sources[id].label_he}><Mark kind={markOf(x.sources[id])} /></button>))}</span>
              </li>
            ))}
          </ul>
          <div className="bi-verify">
            <div className="bi-verify-k">מה עוד צריך לאמת לפני החלטה</div>
            <ul>{r.verify.map((v, i) => <li key={i}>{v.v1_item ? <button className="link" onClick={() => ctx.openV1(v.v1_item)}>{v.text_he}</button> : v.text_he}</li>)}</ul>
          </div>
        </div>}
        <div className="bi-legend" data-testid="bi-legend">
          <span className="bi-legend-k">מקורות הנתונים בסיכום:</span>
          {(["reviewed", "verified", "declared", "demo", "calc", "assume"] as MarkKind[]).filter((k) => counts[k]).map((k) => (
            <span key={k} className="bi-legend-i"><Mark kind={k} /> <span className="ltr">{counts[k]}</span></span>))}
          <span className="bi-legend-tip">לחיצה על מספר מציגה מאיפה הגיע</span>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- customer and loan
function Overview({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const d = x.documents;
  return (
    <div className="bi-overview" data-testid="bi-overview">
      <div className="bi-card">
        <div className="bi-card-k">{x.applicant.entity === "company" ? "החברה המבקשת" : x.applicant.borrowers.length > 1 ? "המבקשים" : "המבקש/ת"}</div>
        {x.applicant.company && <div className="bi-card-title">{x.applicant.company.name_he} <span className="muted small ltr">{x.applicant.company.company_number}</span></div>}
        {x.applicant.borrowers.map((b) => (
          <div key={b.borrower_id} className="bi-person">
            <div className="bi-card-title">{b.name_he} <span className="bi-role">{b.role_he}</span></div>
            <div className="bi-line">{b.profile_he || x.applicant.profile_label_he}</div>
            {b.employer_document_source_id ? <div className="bi-line">מעסיק: <SrcLink ctx={ctx} id={b.employer_document_source_id}>{String(x.sources[b.employer_document_source_id].value_raw)}</SrcLink></div>
              : b.employer_declared_he ? <div className="bi-line">מעסיק/עסק (מוצהר): {b.employer_declared_he}</div> : null}
          </div>
        ))}
      </div>
      <div className="bi-card">
        <div className="bi-card-k">הבקשה</div>
        <div className="bi-card-title">{x.loan.purpose_he} <span className="muted small">· {x.loan.product_he}</span></div>
        <div className="bi-kv"><span>סכום מבוקש</span><Val ctx={ctx} d={x.loan.amount} testId="bi-loan-amount" /></div>
        <div className="bi-kv"><span>תשלומים</span><Val ctx={ctx} d={x.loan.term} /></div>
        {x.loan.asset && <div className="bi-kv"><span>{x.loan.asset.label_he}</span><Val ctx={ctx} d={x.loan.asset.price} testId="bi-asset-price" /></div>}
        {x.loan.asset?.subject_source_id && <div className="bi-line muted"><SrcLink ctx={ctx} id={x.loan.asset.subject_source_id}>{String(x.sources[x.loan.asset.subject_source_id].value_raw)}</SrcLink></div>}
        {x.loan.note_he && <div className="bi-line muted">„{x.loan.note_he}”</div>}
      </div>
      <div className="bi-card">
        <div className="bi-card-k">מסמכים</div>
        <div className="bi-card-title">{d.state_he}</div>
        <div className="bi-docbar" aria-label="דרישות מסמכים">
          {d.requirements.map((q, i) => <span key={i} className={q.satisfied ? "ok" : "miss"} title={`${q.title_he} · ${q.state_he}`} />)}
        </div>
        <div className="bi-kv"><span>דרישות שהושלמו</span><b className="ltr">{d.progress ? `${d.progress.done}/${d.progress.total}` : "—"}</b></div>
        <div className="bi-kv"><span>התקבלו על ידך</span><b className="ltr">{d.accepted}/{d.total}</b></div>
        {d.awaiting_decision > 0 && <button className="bi-linkrow" onClick={() => ctx.openV1(null)}>
          {d.awaiting_decision === 1 ? "מסמך אחד ממתין" : `${d.awaiting_decision} מסמכים ממתינים`} לקבלה בסקירת המסמכים ←</button>}
        <div className="bi-line muted">שלב רשמי בבנק: {x.case.bank_stage.label_he} <span className="bi-mark m-demo">דמו</span></div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- financial picture
function Financial({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const a = x.analysis;
  const bc = x.bank_context;
  const thr = x.simulation.threshold_pct;
  return (
    <Section title="תמונה פיננסית" testId="bi-financial"
      sub={<>הכנסה מהמסמכים, התחייבויות מנתוני הבנק (דמו) ויחסי החזר מחושבים. <span className={`bi-avail a-${a.availability}`}>{a.status_he}</span></>}>
      <div className="bi-kpis">
        <Kpi ctx={ctx} label="הכנסה נטו לחישוב" d={a.income} testId="bi-kpi-income" />
        <Kpi ctx={ctx} label="החזרים קיימים בחודש" d={a.existing_debt} testId="bi-kpi-existing" note={a.existing_debt.value == null ? "אין נתוני התחייבויות" : undefined} />
        <Kpi ctx={ctx} label="יחס החזר קיים" d={a.existing_dsr} testId="bi-kpi-existing-dsr" />
        <Kpi ctx={ctx} label="יחס משולב בבקשה" d={a.combined_dsr} testId="bi-kpi-combined" tone={a.combined_dsr?.value != null ? (a.combined_dsr.value > thr ? "warn" : "ok") : undefined}
          note={a.combined_dsr?.value != null ? `הנחת הדגמה: עד ${thr}%` : undefined} />
        <Kpi ctx={ctx} label="שיעור מימון מהאסמכתה" d={a.ltv} testId="bi-kpi-ltv" tone={a.ltv?.value != null && a.ltv.value > 100 ? "warn" : undefined} />
      </div>
      {a.declared_alternative && <div className="bi-alt" data-testid="bi-declared-alt">
        על בסיס ההכנסה המוצהרת ({money(a.declared_alternative.income_ils)}) היחס המשולב היה <b className="ltr">{pct(a.declared_alternative.combined_dsr_pct)}</b> —
        הניתוח לא בוחר בנתון שמציג את הבקשה טוב יותר עד לבירור הפער.</div>}
      <div className="bi-fin-cols">
        <div className="bi-panel" data-testid="bi-income">
          <h3>הכנסה</h3>
          {x.income.borrowers.map((r) => (
            <div key={r.borrower_id} className="bi-income">
              <div className="bi-income-head"><b>{r.first_name_he}</b>
                <span className={`bi-q q-${r.quality}`}>{{ verified: "מאומת בתלושים", partial: "חלקי", declared: "מוצהר בלבד", missing: "אין נתון" }[r.quality]}</span>
                {r.unresolved_discrepancy && <span className="bi-q q-gap">פער פתוח</span>}</div>
              {r.months.length > 0 && <div className="bi-months">
                {r.months.map((m) => {
                  const max = Math.max(...r.months.map((y) => y.net_ils || 0));
                  return (
                    <button key={m.period} className="bi-month" onClick={() => ctx.open(m.source_id)} disabled={!m.source_id} data-testid="bi-income-month" data-period={m.period}>
                      <span className="bi-month-bar"><span style={{ height: `${Math.max(18, ((m.net_ils || 0) / (max || 1)) * 100)}%` }} /></span>
                      <span className="bi-month-v ltr">{money(m.net_ils)}</span>
                      <span className="bi-month-k">{m.period_he.split(" ")[0]}</span>
                      {m.source_id && <Mark kind={markOf(x.sources[m.source_id])} />}
                    </button>
                  );
                })}
              </div>}
              <div className="bi-kv"><span>ממוצע בתלושים</span><Val ctx={ctx} d={r.documented_avg} testId="bi-income-avg" /></div>
              <div className="bi-kv"><span>מוצהר בבקשה</span><Val ctx={ctx} d={r.declared} /></div>
              {r.variability_pct != null && <div className="bi-kv"><span>תנודתיות בין החודשים</span><b className="ltr">{pct(r.variability_pct)}</b></div>}
            </div>
          ))}
        </div>
        <div className="bi-panel" data-testid="bi-obligations">
          <h3>התחייבויות וחשיפת אשראי <span className="bi-mark m-demo">דמו</span></h3>
          {!bc.available ? <div className="bi-empty">אין נתוני הקשר בנקאי להדגמה עבור {bc.missing_for.join(", ") || "המבקשים"}. ההתחייבויות הקיימות לא ידועות — היחס המשולב כולל רק את ההלוואה המבוקשת.</div> : <>
            <div className="bi-src-note">מקור: {bc.fixture_ids.join(", ")} · נכון ל־<span className="ltr">{bc.observed_at}</span> · סינתטי, לא נשלף ממערכות הבנק{bc.missing_for.length ? ` · חסר עבור ${bc.missing_for.join(", ")}` : ""}</div>
            <table className="bi-table">
              <thead><tr><th>הלוואה קיימת</th><th>יתרת קרן</th><th>החזר חודשי</th><th>נותרו</th></tr></thead>
              <tbody>{bc.loans.length ? bc.loans.map((l) => (
                <tr key={l.id}><td>{l.type_he}<div className="tiny muted">{l.lender_he} · {l.owner_he}</div></td>
                  <td><Val ctx={ctx} d={l.outstanding} /></td><td><Val ctx={ctx} d={l.monthly} testId="bi-loan-monthly" /></td>
                  <td className="ltr">{l.remaining_payments}</td></tr>)) : <tr><td colSpan={4} className="muted">אין הלוואות קיימות בנתוני הדמו</td></tr>}</tbody>
            </table>
            <table className="bi-table">
              <thead><tr><th>מסגרת אשראי</th><th>מסגרת</th><th>מנוצל</th><th /></tr></thead>
              <tbody>{bc.credit_lines.map((l) => (
                <tr key={l.id}><td>{l.type_he}<div className="tiny muted">{l.owner_he}</div></td><td className="ltr">{money(l.limit_ils)}</td>
                  <td><button className="bi-val" onClick={() => ctx.open(l.source_id)}><span className="bi-num ltr">{money(l.utilized_ils)}</span><Mark kind="demo" /></button></td>
                  <td><div className="bi-meter"><span style={{ width: `${Math.min(100, (l.utilized_ils / (l.limit_ils || 1)) * 100)}%` }} /></div></td></tr>))}</tbody>
            </table>
            {bc.exposure && <div className="bi-exposure">
              <div><span>אובליגו מאושר</span><Val ctx={ctx} d={bc.exposure.approved} testId="bi-exposure-approved" /></div>
              <div><span>אובליגו מנוצל</span><Val ctx={ctx} d={bc.exposure.utilized} testId="bi-exposure-utilized" /></div>
            </div>}
            <ul className="bi-notes">
              <li><b>לא נספר פעמיים:</b> יתרות ומסגרות הן חשיפה (אובליגו), לא החזר חודשי. רק ההחזרים החודשיים נכנסים ליחס ההחזר.</li>
              {bc.card_spending.map((s) => <li key={s.source_id}>חיובי כרטיס ({s.owner_he}): <button className="bi-val" onClick={() => ctx.open(s.source_id)}><span className="bi-num ltr">{money(s.avg_monthly_ils)}</span><Mark kind="demo" /></button> בממוצע לחודש — הוצאה שוטפת, אינה החזר חוב ואינה נכללת ביחס.</li>)}
              {bc.events.map((e) => <li key={e.source_id} className={e.returned_checks_12m || e.arrears_12m ? "warn" : ""}>אירועי חשבון ב־12 חודשים ({e.owner_he}): {e.returned_checks_12m || e.arrears_12m ? e.detail_he.join(" ") : "ללא שיקים חוזרים, פיגורים או הגבלות"} <button className="bi-chipsrc" onClick={() => ctx.open(e.source_id)}><Mark kind="demo" /></button></li>)}
            </ul>
          </>}
          <div className="bi-kv bi-remaining"><span>הכנסה שנותרת אחרי החזרי חוב (תיאורי)</span><Val ctx={ctx} d={a.remaining_after_debt} testId="bi-remaining" /></div>
        </div>
      </div>
    </Section>
  );
}

function Kpi({ ctx, label, d, note, tone, testId }: { ctx: Ctx; label: string; d?: Datum | null; note?: string; tone?: string; testId: string }) {
  return (
    <div className={`bi-kpi${tone ? ` k-${tone}` : ""}`} data-testid={testId}>
      <div className="bi-kpi-k">{label}</div>
      <Val ctx={ctx} d={d} big />
      {note && <div className="bi-kpi-n">{note}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- scenarios and What-if
const SC_LABEL: Record<string, string> = { short: "תקופה קצרה", requested: "לפי הבקשה", long: "תקופה ארוכה" };

function Simulator({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const s = x.simulation;
  const base = s.inputs;
  const [principal, setPrincipal] = useState(base.principal);
  const [term, setTerm] = useState(base.term_months);
  const [rate, setRate] = useState(base.annual_rate_pct);
  useEffect(() => { setPrincipal(base.principal); setTerm(base.term_months); setRate(base.annual_rate_pct); }, [x.case_id, base.principal, base.term_months, base.annual_rate_pct]);
  const changed = principal !== base.principal || term !== base.term_months || rate !== base.annual_rate_pct;
  const rows: Scenario[] = useMemo(() => simulate(principal, term, rate, s.income_ils, s.existing_debt_ils, s.asset_price_ils, s.bounds),
    [principal, term, rate, s]);
  if (!s.enabled) return (
    <Section title="חלופות מימון וסימולציה" testId="bi-simulator"><div className="bi-empty">אין בבקשה סכום ומספר תשלומים לחישוב.</div></Section>);
  const short = rows[0], long = rows[rows.length - 1];
  const thr = s.threshold_pct;
  const dsrs = rows.map((r) => r.combined_dsr_pct).filter((v): v is number => v != null);
  const provisional = x.analysis.availability !== "full";
  const calcSource = (r: Scenario, what: "pay" | "dsr" | "total"): IntelSource => {
    const inP: SourceInput = { label_he: "קרן (P)", value: principal, unit: "ils", source_id: principal === base.principal ? "app:amount" : null, origin: "sim" };
    const inN: SourceInput = { label_he: "תשלומים (n)", value: r.term_months, unit: "months", source_id: r.term_months === base.term_months ? "app:term" : null,
      origin: r.term_months === term ? "sim" : "calc" };
    const inR: SourceInput = { label_he: "ריבית שנתית", value: rate, unit: "pct", source_id: rate === base.annual_rate_pct ? s.rate_source_id : null, origin: "sim" };
    const pay: SourceInput = { label_he: "החזר חודשי", value: r.monthly_payment_ils, unit: "ils", source_id: null, origin: "calc" };
    if (what === "pay") return { id: `sim:pay:${r.key}`, kind: "calculated", label_he: `החזר חודשי — ${r.term_months} תשלומים`, value: r.monthly_payment_ils,
      unit: "ils", formula_he: "P·r ÷ (1 − (1 + r)^−n), r = ריבית שנתית ÷ 12", inputs: [inP, inN, inR],
      note_he: "חושב בדפדפן באותה נוסחה ובאותו עיגול כמו בשרת. ערכי סימולציה אינם נשמרים." };
    if (what === "total") return { id: `sim:total:${r.key}`, kind: "calculated", label_he: `עלות המימון — ${r.term_months} תשלומים`, value: r.total_interest_ils,
      unit: "ils", formula_he: "החזר חודשי × n − P", inputs: [pay, inN, inP],
      note_he: "מחושב מההחזר הלא מעוגל — התשלום האחרון סופג את עיגול האגורות. בריבית 0% עלות המימון היא 0." };
    return { id: `sim:dsr:${r.key}`, kind: "calculated", label_he: `יחס החזר משולב — ${r.term_months} תשלומים`, value: r.combined_dsr_pct, unit: "pct",
      formula_he: "(החזר משוער + החזרים קיימים) ÷ הכנסה נטו × 100",
      inputs: [pay,
        { label_he: "החזרים קיימים", value: s.existing_debt_ils, unit: "ils", source_id: s.existing_source_id },
        { label_he: "הכנסה נטו", value: s.income_ils, unit: "ils", source_id: s.income_source_id }],
      note_he: r.combined_includes_existing ? null : "אין נתוני התחייבויות קיימות — היחס כולל רק את ההלוואה המבוקשת." };
  };
  return (
    <Section title="חלופות מימון וסימולציה" testId="bi-simulator"
      sub={<>הלוואה בריבית קבועה (שפיצר). כל שינוי מחושב מחדש מיד — <b>אינו משנה את הבקשה, ההכנסה או ההתחייבויות</b>, ואינו הצעה של הבנק.</>}
      aside={<button className="btn btn-ghost btn-sm" onClick={() => { setPrincipal(base.principal); setTerm(base.term_months); setRate(base.annual_rate_pct); }}
        disabled={!changed} data-testid="bi-wi-reset">חזרה לנתוני הבקשה</button>}>
      {provisional && <div className="bi-provisional" data-testid="bi-sim-provisional">{x.analysis.availability === "unavailable" ? "ניתוח היחסים אינו זמין לתיק זה — מוצגים החזרים ועלויות בלבד."
        : "הסימולציה מוצגת להמחשה בלבד — הניתוח הפיננסי " + (x.analysis.availability === "provisional" ? "זמני עד לבירור הפער." : "חלקי: " + x.analysis.reasons_he.join(" "))}</div>}
      <div className="bi-whatif" data-testid="bi-whatif">
        <Slider label="סכום ההלוואה" value={principal} min={10000} max={s.bounds.principal_max} step={1000} onChange={setPrincipal} display={money(principal)}
          testId="bi-wi-principal" changed={principal !== base.principal} />
        <Slider label="תקופה (תשלומים)" value={term} min={s.bounds.term_min} max={s.bounds.term_max} step={6} onChange={setTerm}
          display={`${term} · ${years(term)}`} testId="bi-wi-term" changed={term !== base.term_months} />
        <Slider label="ריבית שנתית להמחשה" value={rate} min={0} max={15} step={0.1} onChange={(v) => setRate(Math.round(v * 10) / 10)} display={`${rate.toFixed(1)}%`}
          testId="bi-wi-rate" changed={rate !== base.annual_rate_pct}
          hint={<>ברירת מחדל <SrcLink ctx={ctx} id={s.rate_source_id}>{base.annual_rate_pct.toFixed(1)}%</SrcLink></>} />
      </div>
      <div className="bi-scenarios">
        {rows.map((r) => {
          const suggested = !changed && s.suggested?.key === r.key;
          const over = r.combined_dsr_pct != null && r.combined_dsr_pct > thr;
          return (
            <article key={r.key} className={`bi-sc${r.key === "requested" ? " mid" : ""}${suggested ? " suggested" : ""}`} data-testid="bi-scenario"
              data-key={r.key} data-term={r.term_months}>
              <header><span className="bi-sc-k">{r.key === "requested" && changed ? "התקופה שנבחרה" : SC_LABEL[r.key]}</span>
                {r.key === "requested" && !changed && <span className="bi-sc-tag">בקשת הלקוח</span>}
                {suggested && <span className="bi-sc-tag sug" title={s.suggested?.label_he}>חלופה להמחשה</span>}</header>
              <div className="bi-sc-term"><b className="ltr">{r.term_months}</b> תשלומים · {years(r.term_months)}</div>
              <button className="bi-sc-pay" onClick={() => ctx.open(calcSource(r, "pay"))} data-testid="bi-sc-pay" data-value={r.monthly_payment_ils}>
                <span className="ltr">{money(r.monthly_payment_ils)}</span><small>לחודש</small><Mark kind={changed ? "sim" : "calc"} /></button>
              <dl>
                <div><dt>סך התשלומים</dt><dd className="ltr" data-testid="bi-sc-total">{money(r.total_payments_ils)}</dd></div>
                <div><dt>עלות המימון</dt><dd><button className="bi-val" onClick={() => ctx.open(calcSource(r, "total"))} data-testid="bi-sc-interest" data-value={r.total_interest_ils}>
                  <span className="bi-num ltr">{money(r.total_interest_ils)}</span></button></dd></div>
                <div><dt>שיעור מימון</dt><dd className="ltr">{pct(r.ltv_pct)}</dd></div>
              </dl>
              <button className={`bi-dsr${over ? " over" : ""}`} onClick={() => ctx.open(calcSource(r, "dsr"))} data-testid="bi-sc-dsr" data-value={r.combined_dsr_pct ?? ""}>
                <span className="bi-dsr-k">יחס החזר משולב{r.combined_includes_existing ? "" : " (ללא התחייבויות קיימות)"}</span>
                <span className="bi-dsr-v ltr">{pct(r.combined_dsr_pct)}</span>
                {r.combined_dsr_pct != null && <span className="bi-dsr-track"><span className="fill" style={{ width: `${Math.min(100, r.combined_dsr_pct / 60 * 100)}%` }} />
                  <span className="thr" style={{ insetInlineStart: `${thr / 60 * 100}%` }} title={`הנחת הדגמה: ${thr}%`} /></span>}
              </button>
            </article>
          );
        })}
      </div>
      {rows.length > 1 && <div className="bi-compare" data-testid="bi-compare">
        בפריסה ל־<b className="ltr">{long.term_months}</b> תשלומים ההחזר החודשי נמוך ב־<b className="ltr">{money(short.monthly_payment_ils - long.monthly_payment_ils)}</b> מאשר
        ב־<b className="ltr">{short.term_months}</b>, אך עלות המימון גבוהה ב־<b className="ltr">{money(long.total_interest_ils - short.total_interest_ils)}</b>.
        {dsrs.length > 0 && <> יחס ההחזר המשולב נע בין <b className="ltr">{pct(Math.min(...dsrs))}</b> ל־<b className="ltr">{pct(Math.max(...dsrs))}</b> (הנחת הדגמה: עד <SrcLink ctx={ctx} id={s.threshold_source_id}>{thr}%</SrcLink>).</>}
      </div>}
      {x.analysis.illustrative_max_principal != null && <div className="bi-maxp" data-testid="bi-max-principal">להמחשה: בהנחות אלה, סכום של עד <b className="ltr">{money(x.analysis.illustrative_max_principal)}</b> ל־{base.term_months} תשלומים משאיר את היחס המשולב בתוך {thr}% — אינו סכום מאושר.</div>}
    </Section>
  );
}

function Slider({ label, value, min, max, step, onChange, display, testId, changed, hint }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; display: string; testId: string; changed: boolean; hint?: ReactNode }) {
  return (
    <label className={`bi-slider${changed ? " changed" : ""}`}>
      <span className="bi-slider-k">{label}{changed && <span className="bi-mark m-sim">סימולציה</span>}</span>
      <span className="bi-slider-v ltr" data-testid={`${testId}-value`}>{display}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} data-testid={testId} aria-label={label} />
      {hint && <span className="bi-slider-h">{hint}</span>}
    </label>
  );
}

// ---------------------------------------------------------------- evidence, gaps and unknowns
function EvidenceRisks({ ctx }: { ctx: Ctx }) {
  const { x } = ctx;
  const docSources = Object.values(x.sources).filter((s) => s.kind === "document");
  return (
    <Section title="ראיות, פערים ומידע חסר" testId="bi-evidence" sub="כל ממצא עם המקור שלו. הפערים הם נקודות לבירור — לא חשד ולא החלטה.">
      {x.discrepancies.map((d, i) => (
        <div key={i} className={`bi-gap${d.open ? " open" : ""}`} data-testid="bi-discrepancy" data-kind={d.kind} data-open={d.open}>
          <div className="bi-gap-head"><b>{d.title_he}{d.first_name_he ? ` · ${d.first_name_he}` : ""}</b><span className="bi-gap-st">{d.status_he}</span></div>
          <div className="bi-gap-grid">
            <div><span>{d.kind === "income" ? "מוצהר" : "בבקשה"}</span><Val ctx={ctx} d={d.declared} /></div>
            <div><span>{d.kind === "income" ? "ממוצע בתלושים" : "בהצעת המחיר"}</span><Val ctx={ctx} d={d.documented} /></div>
            <div><span>הפרש</span><b className="ltr">{money(d.difference_ils != null ? Math.abs(d.difference_ils) : null)}{d.difference_pct != null ? ` · ${Math.abs(d.difference_pct).toFixed(1)}%` : ""}</b></div>
            {d.tolerance_pct != null && <div><span>סף סבולת (בקוד)</span><b className="ltr">{d.tolerance_pct}%</b></div>}
          </div>
          <p>{d.explanation_he}</p>
          <div className="bi-gap-act"><span>{d.action_he}</span><button className="btn btn-ghost btn-sm" onClick={() => ctx.openV1(d.v1_item)} data-testid="bi-gap-open">פתיחה בסקירת המסמכים</button></div>
        </div>
      ))}
      {x.risks.length > 0 && <ul className="bi-risks" data-testid="bi-risks">
        {x.risks.map((r, i) => (
          <li key={i} className={`r-${r.kind}`}>
            <span className="bi-risk-who">{r.who_he}</span>
            <span className="bi-risk-t"><b>{r.title_he}</b>{r.text_he ? ` — ${r.text_he}` : ""}</span>
            {r.source_ids.map((id) => <button key={id} className="bi-chipsrc" onClick={() => ctx.open(id)}><Mark kind={markOf(x.sources[id])} /></button>)}
            <button className="link small" onClick={() => ctx.openV1(r.v1_item)}>פתיחה ←</button>
          </li>
        ))}
      </ul>}
      <div className="bi-ev-cols">
        <div>
          <h3>נתונים שחולצו ממסמכים ושימשו בניתוח</h3>
          {docSources.length ? <ul className="bi-evlist" data-testid="bi-evlist">{docSources.map((s) => (
            <li key={s.id}><button className="bi-evrow" onClick={() => ctx.open(s)} data-testid="bi-evrow" data-field={s.field}>
              <span>{s.label_he}</span><span className="ltr bold">{s.value_raw}</span><Mark kind={markOf(s)} /></button></li>))}</ul>
            : <div className="bi-empty">אין עדיין נתונים שחולצו ממסמכים.</div>}
        </div>
        <div>
          <h3>מה לא נבדק</h3>
          <ul className="bi-unknowns">{x.unknowns.map((u, i) => <li key={i}><b>{u.label_he}:</b> {u.text_he}</li>)}</ul>
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------- banker action and the editable draft
const DRAFT_NOTE: Record<string, string> = {
  complete_documentation: "אישור קבלה והעברה לבדיקת הבנק — ללא התחייבות לאישור.",
  missing_documents: "בקשה מדויקת לפריטים שחסרים בתיק.",
  financial_clarification: "בקשת הבהרה על פער מתועד — בלי הנימוק הפנימי.",
  conditional_financing: "חלופות להמחשה בלבד, עם התנאים במפורש. לא הצעה מחייבת.",
};

function ActionPanel({ ctx, onToast }: { ctx: Ctx; onToast: (t: { text: string; tone: "ok" | "bad" }) => void }) {
  const { x } = ctx;
  const [kind, setKind] = useState<string | null>(x.recommended_draft);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [refs, setRefs] = useState<Record<string, boolean>>({});
  useEffect(() => { setKind(x.recommended_draft); setTexts({}); setRefs({}); }, [x.case_id, x.recommended_draft]);
  const draft = x.drafts.find((d) => d.kind === kind) || x.drafts[0];
  if (!draft) return <div className="bi-action"><div className="bi-empty">אין טיוטה מתאימה למצב התיק כרגע.</div></div>;
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
    <div className="bi-action" data-testid="bi-action">
      <h2>תשובה ללקוח</h2>
      <p className="bi-sub">טיוטה שהוכנה ממצב התיק. אפשר לערוך ולהעתיק; שום דבר לא נשלח מכאן.</p>
      <div className="bi-dtabs" role="tablist">
        {x.drafts.map((d) => (
          <button key={d.kind} role="tab" aria-selected={d.kind === draft.kind} className={d.kind === draft.kind ? "on" : ""} onClick={() => setKind(d.kind)}
            data-testid="bi-draft-tab" data-kind={d.kind}>{d.title_he}{d.kind === x.recommended_draft && <span className="bi-rec">מומלץ</span>}</button>
        ))}
      </div>
      <div className="bi-dnote">{DRAFT_NOTE[draft.kind]}</div>
      <textarea className="bi-dtext" value={text} onChange={(e) => setTexts({ ...texts, [draft.kind]: e.target.value })} dir="rtl"
        data-testid="bi-draft-text" data-kind={draft.kind} aria-label="טיוטת ההודעה ללקוח" />
      {draft.attachments.length > 0 && <div className="bi-refs">
        <div className="bi-refs-k">הפניה למסמכים בתיק (רשות)</div>
        {draft.attachments.map((a) => {
          const k = `${draft.kind}:${a.document_id}`;
          return <label key={k} className={`bi-ref${refs[k] ? " on" : ""}`}><input type="checkbox" checked={!!refs[k]} onChange={() => setRefs({ ...refs, [k]: !refs[k] })} />{a.label_he}</label>;
        })}
      </div>}
      <div className="bi-dbar">
        <button className="btn btn-dark btn-sm" onClick={copy} data-testid="bi-draft-copy">העתקת הטיוטה</button>
        <button className="btn btn-soft btn-sm" disabled={!edited} onClick={() => setTexts({ ...texts, [draft.kind]: draft.message_he })} data-testid="bi-draft-restore">שחזור הנוסח</button>
        {edited && <span className="bi-edited" data-testid="bi-draft-edited">נערך על ידך</span>}
      </div>
      <div className="bi-dfoot">אין שליחה אוטומטית ואין אישור מסירה. נוסח ההודעה נבנה מתבנית קבועה — לא מטקסט של מודל, ובלי יחסי ההחזר או הערות פנימיות.</div>
    </div>
  );
}

// ---------------------------------------------------------------- the source drawer
const KIND_HE: Record<string, string> = { document: "נתון ממסמך", declared: "הצהרת לקוח", synthetic_bank: "נתון בנקאי סינתטי (דמו)",
  calculated: "חישוב", assumption: "הנחת הדגמה", missing: "נתון חסר" };

function SourceDrawer({ src, depth, ws, ctx, onBack, onClose }: { src: IntelSource; depth: number; ws: Workspace; ctx: Ctx; onBack: () => void; onClose: () => void }) {
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
          {depth > 1 && <button className="btn btn-soft btn-sm" onClick={onBack} data-testid="bi-drawer-back">→ חזרה</button>}
          <span className="bi-dr-kind">{KIND_HE[src.kind]}</span><Mark kind={kind} />
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
            <button className="btn btn-dark btn-sm" onClick={() => { onClose(); ctx.openV1(src.v1_item); }} data-testid="bi-drawer-v1">פתיחה בסקירת המסמכים</button>
            <a className="btn btn-ghost btn-sm" href={`/api/documents/${src.document_id}/file`} target="_blank" rel="noreferrer">הקובץ המקורי ↗</a>
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
              const s = i.source_id ? ctx.x.sources[i.source_id] : null;
              return <tr key={n}><td>{i.label_he}</td><td className="ltr">{fmt(i.value, i.unit, true)}</td>
                <td>{s ? <button className="bi-srclink" onClick={() => ctx.open(s)} data-testid="bi-drawer-input">{KIND_HE[s.kind]}<Mark kind={markOf(s)} /></button>
                  : <Mark kind={i.origin || "missing"} />}</td></tr>;
            })}</tbody></table>}
          {src.note_he && <p className="muted">{src.note_he}</p>}
        </div>}
      </aside>
    </div>
  );
}