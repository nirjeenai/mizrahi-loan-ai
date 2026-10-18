import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ilsL, timeL, type CaseFindingItem, type DocItem, type MissingItem, type QueueItem, type Workspace } from "../../api";
import { EvidenceViewer } from "../../components/EvidenceViewer";
import { Loc, locOf, Orig, useLang } from "../../i18n";
import { DecisionPanel } from "./DecisionPanel";
import { BANKER_TONE, Chip, newRequestId, Toast, VERDICT_TONE, When } from "./deskUi";

/** Where the evidence pane points: a document, and optionally one field (and page) on it. */
export interface Focus { documentId: string; field?: string | null; page?: number }
const ACTIONABLE = ["decide", "judgment", "escalated", "correction", "missing"];
const MONTH_TONE: Record<string, string> = { verified: "ok", accepted: "ok", in_review: "navy", missing: "miss", requested: "warn", unknown: "neutral" };

export function ReviewWorkspace({ ws, selected, onSelect, reload, staff, readOnly, stale, openV3 }: {
  ws: Workspace; selected: string | null; onSelect: (id: string) => void; reload: () => void; staff: string; readOnly: boolean; stale: boolean;
  openV3: () => void;
}) {
  const { en, t } = useLang();
  const byId = useMemo(() => Object.fromEntries(ws.items.map((i) => [i.id, i])), [ws.items]);
  const order = useMemo(() => ws.groups.flatMap((g) => g.items), [ws.groups]);
  const actionable = useMemo(() => ws.groups.filter((g) => ACTIONABLE.includes(g.key)).flatMap((g) => g.items), [ws.groups]);
  const current: QueueItem | undefined = (selected && byId[selected]) || byId[actionable[0]] || byId[order[0]];
  const [focus, setFocus] = useState<Focus | null>(null);
  const [toast, setToast] = useState<{ text: string; tone: "ok" | "bad" } | null>(null);
  const clearToast = useCallback(() => setToast(null), []);
  useEffect(() => { setFocus(null); }, [current?.id]);

  const move = useCallback((step: number) => {
    if (!order.length) return;
    const i = current ? order.indexOf(current.id) : -1;
    onSelect(order[(i + step + order.length) % order.length]);
  }, [order, current, onSelect]);
  const nextActionable = useCallback(() => {
    const after = actionable.filter((id) => id !== current?.id);
    const i = current ? order.indexOf(current.id) : -1;
    const next = after.find((id) => order.indexOf(id) > i) || after[0];
    if (next) onSelect(next);
  }, [actionable, order, current, onSelect]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, [contenteditable]") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.code === "KeyJ") { e.preventDefault(); move(1); }
      if (e.code === "KeyK") { e.preventDefault(); move(-1); }
      if (e.code === "KeyN") { e.preventDefault(); nextActionable(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, nextActionable]);

  const docItem = (id?: string | null) => ws.items.find((i): i is DocItem => i.kind === "document" && i.document_id === id);
  const showEvidence = (f: Focus) => {
    const target = docItem(f.documentId);
    if (current?.kind === "document" && target && target.id !== current.id) onSelect(target.id);
    setFocus(f);
  };
  return (
    <div className="desk-body">
      {stale && <div className="desk-stale" role="status">{t("לא הצלחנו לרענן את התיק, ייתכן שהמידע אינו עדכני.", "We couldn't refresh the case; the information may be out of date.")}</div>}
      {readOnly && <div className="desk-stale" role="status">{en ? <>The case is assigned to {locOf(ws.case.banker, "name_he")}. You can view it, but you can't record decisions in it.</>
        : <>התיק משויך ל{ws.case.banker.name_he}. אפשר לצפות בו, אבל אי אפשר לרשום בו החלטות.</>}</div>}
      <HandoffBanner ws={ws} reload={reload} readOnly={readOnly} onToast={setToast} />
      <SummaryHeader ws={ws} onSelect={onSelect} />
      <div className="desk-grid">
        <Queue ws={ws} byId={byId} current={current?.id} onSelect={onSelect} reload={reload} readOnly={readOnly} onToast={setToast} openV3={openV3} />
        <section className="desk-evidence" aria-label={t("המסמך והראיות", "The document and the evidence")} data-testid="evidence-pane">
          {!current ? <div className="desk-empty">{t("אין עדיין מסמכים בתיק. כשהלקוח יעלה מסמכים לבקשת ההלוואה, הם יופיעו כאן.", "There are no documents in the case yet. When the customer uploads documents for the loan application, they'll appear here.")}</div>
            : current.kind === "document" ? <DocumentEvidence item={current} focus={focus} setFocus={setFocus} onSelect={onSelect} ws={ws} />
              : current.kind === "missing" ? <MissingEvidence item={current} onSelect={onSelect} ws={ws} />
                : <FindingEvidence item={current} focus={focus} setFocus={setFocus} ws={ws} />}
        </section>
        <aside className="desk-panel" aria-label={t("סיכום והחלטה", "Summary and decision")} data-testid="decision-panel">
          <header className="pane-head">
            <span className="pane-title">{t("סקירה והחלטה", "Review and decision")}</span>
            {current && <span className="pane-sub">{current.kind === "document" ? t("מסמך", "Document") : current.kind === "missing" ? t("דרישה חסרה", "Missing requirement") : t("ממצא ברמת התיק", "Case-level finding")}</span>}
          </header>
          {current && <DecisionPanel key={current.id} item={current} ws={ws} staff={staff} readOnly={readOnly} focus={focus}
            onDone={(text) => { setToast({ text, tone: "ok" }); reload(); }} onError={(text) => setToast({ text, tone: "bad" })}
            onNext={nextActionable} hasNext={actionable.some((id) => id !== current.id)} showEvidence={showEvidence} />}
        </aside>
      </div>
      <Toast message={toast} onClose={clearToast} />
    </div>
  );
}

/** A customer's "pass me to my banker" request (assistant or MCP). The banker takes it into handling; the note stays internal. */
function HandoffBanner({ ws, reload, readOnly, onToast }: { ws: Workspace; reload: () => void; readOnly: boolean;
  onToast: (t: { text: string; tone: "ok" | "bad" }) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const { en, t } = useLang();
  if (!ws.handoffs?.length) return null;
  const take = async (packageId: string) => {
    setBusy(packageId);
    try {
      await api.acknowledgeHandoff(ws.case_id, packageId, { request_id: newRequestId() });
      onToast({ text: t("הפנייה סומנה כבטיפולך. הלקוח רואה שהפנייה התקבלה.", "The request is marked as in your hands. The customer sees that it was received."), tone: "ok" }); reload();
    } catch (e) { onToast({ text: (e as Error).message, tone: "bad" }); } finally { setBusy(null); }
  };
  return (
    <div className="desk-handoffs" role="status" data-testid="handoff-banner">
      {ws.handoffs.map((h) => (
        <div key={h.package_id} className="desk-handoff" data-testid="handoff">
          <span><b>{t("הלקוח ביקש לפנות אלייך", "The customer asked to reach you")}</b> · {h.channel === "voice" ? t("בשיחה קולית", "in a voice call") : h.channel === "mcp" ? t("דרך ערוץ חיצוני", "through an external channel") : t("בצ׳אט באפליקציה", "in the app chat")} · <When at={h.created_at} />
            {h.note ? (en ? <> · <Orig text={h.note} /></> : <> · „{h.note}”</>) : null}</span>
          <button className="btn btn-ghost btn-sm" disabled={readOnly || busy === h.package_id} onClick={() => take(h.package_id)}
            data-testid="handoff-ack">{busy === h.package_id && <span className="spinner" />}{t("קבלת הפנייה לטיפול", "Take the request")}</button>
        </div>
      ))}
    </div>
  );
}

const REVIEW_TONE: Record<string, string> = {
  ACTION_REQUIRED: "warn", READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS: "navy", READY_FOR_HUMAN_REVIEW: "navy",
  PREPARATION_CONFIRMED: "ok", ERROR: "bad", CHECKING: "neutral", RECHECKING: "neutral", NOT_CHECKED: "neutral",
};
const count = (n: number, one: string, many: string) => (n === 1 ? one : `${n} ${many}`);

/** Case at a glance: what waits for the banker, what waits for the customer, and how far the payslips are.
 *  Month-by-month coverage and income stay one click away. */
function SummaryHeader({ ws, onSelect }: { ws: Workspace; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const { en, t } = useLang();
  const s = ws.summary;
  const g = s.groups;
  const waiting = (g.decide || 0) + (g.judgment || 0) + (g.escalated || 0);
  const asked = ws.customer_requests.filter((q) => q.status === "OPEN" && q.kind !== "missing_document").length;
  const pending = (g.missing || 0) + (g.correction || 0) + asked;
  const stage = ws.bank_stage;
  return (<>
    <div className="desk-summary" data-testid="case-progress">
      <div className={`sum-stat${waiting ? " lead" : ""}`}>
        <b>{waiting}</b>
        <span><span className="sum-label">{t("ממתינים להחלטתך", "For your decision")}</span>
          <span className="sum-sub">{(en ? [g.decide ? count(g.decide, "one document", "documents") : "", g.judgment ? count(g.judgment, "one gap", "gaps") : "",
            g.escalated ? `${g.escalated} escalated` : ""].filter(Boolean).join(" · ") || "No open items"
            : [g.decide ? count(g.decide, "מסמך אחד", "מסמכים") : "", g.judgment ? count(g.judgment, "פער אחד", "פערים") : "",
            g.escalated ? `${g.escalated} בבירור` : ""].filter(Boolean).join(" · ") || "אין פריטים פתוחים")}</span></span>
      </div>
      <div className="sum-stat">
        <b>{pending}</b>
        <span><span className="sum-label">{t("ממתין ללקוח", "With the customer")}</span>
          <span className="sum-sub">{(en ? [s.missing ? count(s.missing, "one missing month", "missing months") : "",
            (g.missing || 0) > s.missing ? count((g.missing || 0) - s.missing, "one missing document", "missing documents") : "", g.correction ? `${g.correction} to correct` : "",
            asked ? count(asked, "one explanation request", "explanation requests") : ""].filter(Boolean).join(" · ") || "No open requirements"
            : [s.missing ? count(s.missing, "חודש חסר", "חודשים חסרים") : "",
            (g.missing || 0) > s.missing ? count((g.missing || 0) - s.missing, "מסמך חסר", "מסמכים חסרים") : "", g.correction ? `${g.correction} לתיקון` : "",
            asked ? count(asked, "בקשת הסבר", "בקשות הסבר") : ""].filter(Boolean).join(" · ") || "אין דרישות פתוחות")}</span></span>
      </div>
      {ws.progress && ws.progress.total > 0 && (
        <div className="sum-stat" data-testid="requirements-progress">
          <b className="ltr">{ws.progress.done}/{ws.progress.total}</b>
          <span><span className="sum-label">{t("דרישות מסמכים הושלמו", "Requirements met")}</span>
            <span className="sum-sub">{ws.case_status === "READY_FOR_BANKER" ? t("מוכן לבדיקתך, לא החלטת אשראי", "Ready for your review — not a credit decision")
              : en ? `Payslips: ${s.payslips_verified}/${s.payslips_required}` : `תלושים: ${s.payslips_verified}/${s.payslips_required}`}</span></span>
        </div>
      )}
      {!ws.progress?.total && <div className="sum-stat">
        <b className="ltr">{s.payslips_verified}/{s.payslips_required}</b>
        <span><span className="sum-label">{t("תלושים נדרשים מאומתים", "Required payslips verified")}</span><span className="sum-sub">{t("התקבלו על ידך:", "Accepted by you:")} {s.payslips_accepted}</span></span>
      </div>}
      <div className="sum-fact" title={t("שלב הבקשה כפי שהוא רשום בתיק. פעולות בקונסולה אינן משנות אותו.", "The application's stage as recorded in the case. Actions in the console don't change it.")}>
        <span className="sum-label">{t("שלב רשמי בבנק", "Bank stage (official)")}</span>
        <span className="sum-value" data-testid="bank-stage">{locOf(stage, "label_he")} ({stage.index}/{stage.of})</span>
      </div>
      <div className="sum-fact">
        <span className="sum-label">{t("בדיקת מסמכי הבקשה", "Document review")}</span>
        <Chip tone={REVIEW_TONE[ws.review_state.state] || "neutral"} testId="banker-readiness">{locOf(ws.review_state, "label_he")}</Chip>
      </div>
      <button className="sum-toggle" onClick={() => setOpen(!open)} aria-expanded={open} data-testid="coverage-toggle">
        {t("פירוט דרישות, חודשים והכנסה", "Requirements & income")} <span aria-hidden>{open ? "▴" : "▾"}</span></button>
    </div>
    {open && <RequirementMatrix ws={ws} onSelect={onSelect} />}
    {open && <BorrowerStrip ws={ws} onSelect={onSelect} />}
  </>);
}

const REQ_TONE: Record<string, string> = { extracted: "ok", preparation_confirmed: "ok", needs_banker_review: "navy", checking: "neutral",
  required_missing: "miss", needs_customer_action: "warn" };

/** Every requirement instance of the pinned loan policy, with its AI state; a click opens the document or the missing item. */
function RequirementMatrix({ ws, onSelect }: { ws: Workspace; onSelect: (id: string) => void }) {
  const { en } = useLang();
  if (!ws.requirement_matrix?.length) return null;
  const open = (code: string) => {
    const doc = ws.items.find((i): i is DocItem => i.kind === "document" && i.requirement_code === code && i.banker.status !== "REPLACED");
    const missing = ws.items.find((i) => i.id === `missing:${code}`);
    if (missing) onSelect(missing.id);
    else if (doc) onSelect(doc.id);
  };
  return (
    <div className="req-matrix" data-testid="requirement-matrix">
      <div className="tiny muted">{en ? <>Requirements per policy {ws.requirement_matrix[0].policy_version || ""} (pinned to the case)</>
        : <>דרישות לפי מדיניות {ws.requirement_matrix[0].policy_version || ""} (הוצמדה לתיק)</>}</div>
      <div className="req-matrix-rows">
        {ws.requirement_matrix.map((r) => (
          <button key={r.code} className={`mchip2 ${REQ_TONE[r.ai_state] || "neutral"}`} onClick={() => open(r.code)}
            data-testid="requirement-row" data-code={r.code} data-state={r.ai_state} title={locOf(r, "title_he")}>
            <span className="dot" aria-hidden /><span className="mchip2-month">{locOf(r, "family_he")}{r.borrower_he && r.family !== "purpose_proof" ? ` · ${locOf(r, "borrower_he")}` : ""}</span>
            <span className="mchip2-state">{locOf(r, "ai_state_he")}{r.family === "payslip" ? ` · ${r.units}` : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function BorrowerStrip({ ws, onSelect }: { ws: Workspace; onSelect: (id: string) => void }) {
  const go = (bid: string, m: Workspace["borrowers"][number]["months"][number]) => {
    if (m.state === "missing" || m.state === "requested") onSelect(`missing:${bid}:${m.period}`);
    else if (m.documents[0]) onSelect(`doc:${m.documents[0]}`);
  };
  return (
    <div className="borrower-strip" data-testid="borrower-strip">
      {ws.borrowers.map((b) => (
        <div className="strip-row" key={b.borrower_id}>
          <div className="strip-name">{locOf(b, "name_he")}</div>
          <div className="strip-months">
            {b.months.map((m) => (
              <button key={m.period} className={`mchip2 ${MONTH_TONE[m.state] || "neutral"}`} onClick={() => go(b.borrower_id, m)}
                title={locOf(m, "state_he")} data-testid="month-chip" data-state={m.state}>
                <span className="dot" aria-hidden /><span className="mchip2-month">{locOf(m, "label_he").split(" ")[0]}</span>
                <span className="mchip2-state">{locOf(m, "state_he")}{m.copies > 1 ? ` · ×${m.copies}` : ""}</span>
              </button>
            ))}
          </div>
          <IncomeLine income={b.income} />
        </div>
      ))}
    </div>
  );
}

function IncomeLine({ income }: { income: Workspace["borrowers"][number]["income"] }) {
  const { en } = useLang();
  if (income.declared_net_monthly_ils == null) return null;
  if (en) return (
    <div className={`strip-income ${income.tone}`} data-testid="income-line" data-outcome={income.outcome || ""}>
      <span className="muted">Net income:</span> declared <b className="ltr">{ilsL(income.declared_net_monthly_ils)}</b>
      {income.average_documented_net_ils != null && <> · {locOf(income, "documented_label_he") || "in the payslips"} <b className="ltr">{ilsL(income.average_documented_net_ils)}</b>
        <span className="muted"> ({income.months_compared.length}/{income.months_required} months{income.basis === "preliminary" ? " · preliminary comparison" : ""})</span></>}
      <div className="strip-income-verdict">{locOf(income, "summary_he")}</div>
    </div>
  );
  return (
    <div className={`strip-income ${income.tone}`} data-testid="income-line" data-outcome={income.outcome || ""}>
      <span className="muted">הכנסה נטו:</span> מוצהר <b className="ltr">{ilsL(income.declared_net_monthly_ils)}</b>
      {income.average_documented_net_ils != null && <> · {income.documented_label_he || "בתלושים"} <b className="ltr">{ilsL(income.average_documented_net_ils)}</b>
        <span className="muted"> ({income.months_compared.length}/{income.months_required} חודשים{income.basis === "preliminary" ? " · השוואה ראשונית" : ""})</span></>}
      <div className="strip-income-verdict">{income.summary_he}</div>
    </div>
  );
}

function Queue({ ws, byId, current, onSelect, reload, readOnly, onToast, openV3 }: {
  ws: Workspace; byId: Record<string, QueueItem>; current?: string; onSelect: (id: string) => void; reload: () => void;
  readOnly: boolean; onToast: (t: { text: string; tone: "ok" | "bad" }) => void; openV3: () => void;
}) {
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  const { en, t } = useLang();
  const waiting = ws.groups.filter((g) => DECIDE_GROUPS.includes(g.key)).reduce((n, g) => n + g.items.length, 0);
  let lastTier = "";
  return (
    <aside className="desk-queue" aria-label={t("תור הבדיקה", "Review queue")} data-testid="review-queue">
      <header className="pane-head">
        <span className="pane-title-wrap">
          <span className="pane-title">{t("מסמכי התיק", "Case documents")}</span>
          <span className={`pane-sub${waiting ? " lead" : ""}`}>{waiting ? (en ? `${waiting} awaiting your decision` : `${waiting} ממתינים להחלטתך`) : t("אין פריטים שממתינים להחלטתך", "No items awaiting your decision")}</span>
        </span>
        <span className="kbd-hint" title={t("מעבר בין פריטים במקלדת: J / K, ו-N לפריט הבא שדורש החלטה", "Keyboard navigation: J / K between items, N for the next item that needs a decision")}>J / K · N</span>
      </header>
      <div className="queue-body">
      {ws.groups.map((g) => {
        if (!g.items.length) return null;
        const collapsible = COLLAPSED.includes(g.key);
        const expanded = !collapsible || !!opened[g.key] || (!!current && g.items.includes(current));
        const summary = g.key === "missing" ? missingSummary(g.items.map((id) => byId[id]).filter(Boolean)) : null;
        const tier = DECIDE_GROUPS.includes(g.key) ? "act" : g.key === "done" ? "done" : "wait";
        const tierStart = tier !== lastTier;
        lastTier = tier;
        return (
          <section key={g.key} className={`queue-group g-${g.key} tier-${tier}${tierStart ? " tier-start" : ""}`} data-testid={`queue-group-${g.key}`}>
            <button className="queue-group-head" onClick={collapsible ? () => setOpened({ ...opened, [g.key]: !expanded }) : undefined}
              title={locOf(g, "hint_he")} aria-expanded={collapsible ? expanded : undefined} tabIndex={collapsible ? 0 : -1}>
              <span className="count">{g.items.length}</span><span className="queue-group-title">{locOf(g, "title_he")}</span>
              {collapsible && <span className="queue-group-chev" aria-hidden>{expanded ? "▴" : "▾"}</span>}
            </button>
            {!expanded && summary && <div className="queue-group-summary">{summary}</div>}
            {expanded && <div className="queue-rows">
              {g.items.map((id) => byId[id] && <QueueRow key={id} item={byId[id]} on={id === current} onSelect={onSelect} />)}</div>}
          </section>
        );
      })}
      <CaseStep ws={ws} reload={reload} readOnly={readOnly} onToast={onToast} openV3={openV3} />
      </div>
    </aside>
  );
}

const DECIDE_GROUPS = ["decide", "judgment", "escalated"];
const COLLAPSED = ["missing", "done"];

function missingSummary(items: QueueItem[]): string {
  const by: Record<string, string[]> = {};
  for (const it of items) if (it.kind === "missing") (by[locOf(it, "borrower_he")] ||= []).push(it.period_he ? locOf(it, "period_he").split(" ")[0] : locOf(it, "family_he") || locOf(it, "title_he"));
  return Object.entries(by).map(([who, months]) => `${who}: ${months.join(", ")}`).join(" · ");
}

function QueueRow({ item, on, onSelect }: { item: QueueItem; on: boolean; onSelect: (id: string) => void }) {
  const { en, t } = useLang();
  const status = item.kind === "document"
    ? (item.banker.status !== "AWAITING_DECISION" ? { text: locOf(item.banker, "status_he"), tone: BANKER_TONE[item.banker.status] } : { text: `AI: ${locOf(item.ai, "verdict_he")}`, tone: VERDICT_TONE[item.ai.verdict || ""] || "neutral" })
    : item.kind === "missing" ? { text: item.open_request ? t("נשלחה בקשה", "Request sent") : t("לא הועלה", "Not uploaded"), tone: "neutral" }
      : { text: item.finding.status === "open" ? (item.open_request ? t("ממתין ללקוח", "Waiting for the customer") : item.escalated ? t("בהמשך בירור", "Under further review") : t("לבדיקה", "To review")) : locOf(item.finding, "status_he"), tone: "neutral" };
  const meta = item.kind === "document" ? item.filename : item.kind === "case_finding" && item.income?.difference_pct != null
    ? `${Math.abs(item.income.difference_pct).toFixed(1)}% · ${item.basis.partial ? `${item.basis.months_compared.length}/${item.basis.months_required.length} ${t("חודשים", "months")}` : `${item.basis.months_required.length} ${t("חודשים", "months")}`}` : null;
  return (
    <button className={`qrow k-${item.kind}${on ? " on" : ""}${item.attention ? " attn" : ""}`} onClick={() => onSelect(item.id)}
      aria-current={on ? "true" : undefined} data-testid="queue-item" data-item-id={item.id} data-kind={item.kind}>
      <span className="qrow-main">
        <span className="qrow-title">{item.attention && <span className="attn-dot" aria-label={t("דורש תשומת לב", "Needs attention")} />}{locOf(item, "title_he")}</span>
        <span className="qrow-meta">
          <span className={`qrow-status ${status.tone}`}>{status.text}</span>
          {item.kind === "document" && item.replaces && <span className="qrow-note">{t("מסמך חלופי", "Replacement document")}</span>}
        </span>
        {meta && <span className={`qrow-file${item.kind === "document" ? " ltr" : ""}`}>{meta}</span>}
        {item.attention && item.kind === "document" && item.ai.attention_he[0] && <span className="qrow-why">{en ? <Loc he={item.ai.attention_he[0]} en={(item.ai as { attention_en?: (string | null)[] }).attention_en?.[0]} /> : item.ai.attention_he[0]}</span>}
      </span>
    </button>
  );
}

/** The case-level next step: once the documents are ready, a green call to open the same case in V3 ("תיק מוכן").
 *  Navigation only; confirming preparation stays a separate, quieter action under it. */
function CaseStep({ ws, reload, readOnly, onToast, openV3 }: { ws: Workspace; reload: () => void; readOnly: boolean;
  onToast: (t: { text: string; tone: "ok" | "bad" }) => void; openV3: () => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [rid, setRid] = useState(newRequestId);
  const { en, t } = useLang();
  const c = ws.can_confirm;
  const ready = !!ws.preparation || c.allowed;
  const confirm = async () => {
    setBusy(true);
    try {
      await api.confirmPreparation(ws.case_id, { note, request_id: rid });
      setRid(newRequestId());
      onToast({ text: t("הכנת מסמכי הבקשה אושרה ונשמרה עם חבילת הראיות. שלב הבקשה בבנק לא השתנה.",
        "The application documents were confirmed as prepared and saved with the evidence package. The application's stage at the bank didn't change."), tone: "ok" });
      setOpen(false); reload();
    } catch (e) { onToast({ text: (e as Error).message, tone: "bad" }); } finally { setBusy(false); }
  };
  return (
    <div className={`case-step${ready ? " ready" : ""}`} data-testid="case-step" data-ready={ready ? "true" : "false"}>
      <button className="case-go" disabled={!ready} onClick={openV3} data-testid="open-ready-case"
        title={ready ? t("פתיחת התיק המלא בתצוגת V3. ניווט בלבד, אינו החלטת אשראי ואינו משנה את מצב התיק.", "Open the full case in the V3 view. Navigation only — not a credit decision, and it doesn't change the case.") : undefined}>
        <span className="case-go-mark" aria-hidden>✓</span>
        <span className="case-go-label">{t("מעבר לתיק מוכן", "Go to the prepared case")}</span>
        <span className="case-go-arrow" aria-hidden>{t("←", "→")}</span>
      </button>
      {!ready && c.reason_he && <div className="case-step-why">{locOf(c, "reason_he")}</div>}
      {!ws.preparation && ws.preparation_stale && <div className="tiny warn-text" data-testid="preparation-stale">
        {en ? <>The confirmation from <When at={ws.preparation_stale.confirmed_at} /> is no longer valid: {locOf(ws.preparation_stale, "reason_he")}. Confirm again after the review.</>
          : <>האישור מ־<When at={ws.preparation_stale.confirmed_at} /> אינו בתוקף עוד: {ws.preparation_stale.reason_he}. יש לאשר שוב אחרי הבדיקה.</>}</div>}
      {ws.preparation ? <div className="case-step-why ok-text">{t("הכנת המסמכים אושרה", "Document preparation confirmed")} <When at={ws.preparation.confirmed_at} />{ws.preparation.note ? (en ? <> · <Orig text={ws.preparation.note} /></> : ` · ${ws.preparation.note}`) : ""}</div>
        : !open ? (c.allowed && !readOnly && <button className="link tiny subtle case-step-confirm" onClick={() => setOpen(true)}
            data-testid="confirm-preparation">{t("אישור הכנת המסמכים…", "Confirm document preparation…")}</button>)
        : (
          <div className="stack" style={{ gap: 6 }}>
            {c.open_banker_items > 0 && <div className="tiny">{c.open_banker_items} {t("ממצאים לשיקול דעתך יישארו פתוחים ויתועדו בחבילה.", "findings for your judgment will stay open and be recorded in the package.")}</div>}
            <textarea className="note" placeholder={t("הערה פנימית (רשות)", "Internal note (optional)")} value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="row"><button className="btn btn-dark btn-sm" disabled={busy} onClick={confirm} data-testid="confirm-preparation-submit">{t("אישור הכנת מסמכי הבקשה", "Confirm the application documents are prepared")}</button>
              <button className="btn btn-soft btn-sm" onClick={() => setOpen(false)}>{t("ביטול", "Cancel")}</button></div>
          </div>
        )}
    </div>
  );
}

// ---------------------------------------------------------------- evidence pane
const KEY_FIELDS: [string, string][] = [["employee_name", "שם עובד"], ["salary_period", "חודש שכר"], ["employer_name", "מעסיק"],
  ["gross_pay", "שכר ברוטו"], ["net_pay", "שכר נטו"]];
const KEY_FIELDS_EN: [string, string][] = [["employee_name", "Employee name"], ["salary_period", "Pay month"], ["employer_name", "Employer"],
  ["gross_pay", "Gross pay"], ["net_pay", "Net pay"]];
const MORE_FIELDS = ["employee_id", "payment_date", "total_deductions"];

/** The evidence to show first: the printed month when it contradicts the upload, otherwise the field an open finding cites,
 *  otherwise net pay. Every other box stays on the page, quiet but clickable. */
/** For a non-payslip family: the decisive field shown first (a statement's period end, an ID's number, a quote's amount). */
const FAMILY_FIRST = ["statement_to", "holder_id", "total_amount", "expiry_date", "tax_year", "holder_name"];

function defaultField(item: DocItem): string | null {
  if (item.claimed_period && item.period && item.claimed_period !== item.period) return "salary_period";
  const cited = item.findings.find((f) => f.status === "open" && f.evidence[0]?.document_id === item.document_id)?.evidence[0]?.field;
  const fields = item.ai.facts.map((f) => f.field);
  if (cited && fields.includes(cited)) return cited;
  if (fields.includes("net_pay")) return "net_pay";
  return FAMILY_FIRST.find((f) => fields.includes(f)) || fields[0] || null;
}

function KeyFields({ item, field, onPick }: { item: DocItem; field: string | null; onPick: (f: string) => void }) {
  const [more, setMore] = useState(false);
  const { en, t } = useLang();
  const facts = Object.fromEntries(item.ai.facts.map((f) => [f.field, f]));
  const payslip = !!(facts.salary_period || facts.net_pay || facts.employee_name);
  const extra = payslip ? MORE_FIELDS.filter((f) => facts[f]) : [];
  const keys: [string, string][] = payslip ? (en ? KEY_FIELDS_EN : KEY_FIELDS) : item.ai.facts.map((f) => [f.field, locOf(f, "label_he")]);
  const cell = (key: string, label: string) => {
    const f = facts[key];
    if (!f) return null;
    return (
      <button key={key} className={`kf${field === key ? " on" : ""}`} onClick={() => onPick(key)} data-testid="key-field" data-field={key}
        title={f.verified ? t("אומת מול הקובץ", "Verified against the file") : t("לא אומת מול הקובץ", "Not verified against the file")}>
        <span className="kf-label">{label}</span>
        <span className="kf-value"><bdi {...(en && /[\u0590-\u05FF]/.test(f.value_raw || "") ? { lang: "he", dir: "rtl" } : {})}>{f.value_raw}</bdi>
          {f.verified ? <span className="kf-ok" aria-label={t("אומת", "Verified")}>✓</span> : <span className="kf-warn">{t("לא אומת", "Not verified")}</span>}</span>
      </button>
    );
  };
  return (
    <div className="key-fields" data-testid="key-fields">
      <div className="kf-caption"><span>{t("נתונים שחולצו מהמסמך", "Data extracted from the document (values as printed)")}</span><span className="kf-legend"><b>✓</b> {t("אומת מול הקובץ · לחיצה מסמנת במסמך", "verified against the file · click to mark it on the document")}</span></div>
      <div className="kf-row">{keys.map(([k, l]) => cell(k, l))}</div>
      {more && <div className="kf-row">{extra.map((k) => cell(k, locOf(item.ai.facts.find((f) => f.field === k)!, "label_he")))}</div>}
      {extra.length > 0 && <button className="link tiny subtle" onClick={() => setMore(!more)} data-testid="key-fields-more">
        {more ? t("פחות נתונים", "Fewer details") : en ? `${extra.length} more details` : `עוד ${extra.length} נתונים`}</button>}
    </div>
  );
}

function DocumentEvidence({ item, focus, setFocus, onSelect, ws }: { item: DocItem; focus: Focus | null; setFocus: (f: Focus | null) => void;
  onSelect: (id: string) => void; ws: Workspace }) {
  const picked = focus?.documentId === item.document_id && !!focus.field;
  const field = picked ? focus!.field! : defaultField(item);
  const focusedFact = item.ai.facts.find((f) => f.field === field);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  useEffect(() => { if (focusedFact?.evidence?.page) setPage(focusedFact.evidence.page); }, [focusedFact?.evidence?.page]);
  useEffect(() => { if (focus?.documentId === item.document_id && focus.page) setPage(focus.page); }, [focus, item.document_id]);
  const mismatch = item.claimed_period && item.period && item.claimed_period !== item.period;
  const borrower = ws.case.borrowers.find((b) => b.borrower_id === item.borrower_id);
  const pick = (f: string) => setFocus({ documentId: item.document_id, field: f });
  const { t } = useLang();
  return (
    <div className="ev ev-doc">
      <header className="ev-head">
        <div className="ev-head-row">
          <div>
            <div className="ev-title" data-testid="evidence-title">{locOf(item, "doc_type_he")} · {(borrower ? locOf(borrower, "name_he") : "") || locOf(item, "borrower_he")}</div>
            <div className="ev-meta">
              {item.period_he || item.claimed_period ? <span>{t("חודש מודפס:", "Printed month:")} <b>{locOf(item, "period_he") || "-"}</b></span>
                : <span>{t("סוג:", "Type:")} <b>{locOf(item, "doc_type_he")}</b></span>}
              {mismatch && <span className="warn-text">{t("הועלה עבור:", "Uploaded for:")} <b>{locOf(item, "claimed_period_he")}</b></span>}
              <span className="ltr">{timeL(item.uploaded_at)}</span>
              {item.is_scanned && <span>{t("סריקה", "Scan")}</span>}
              <span className="ltr ev-file">{item.filename}</span>
            </div>
          </div>
          <a className="btn btn-ghost btn-sm ev-open" href={`/api/documents/${item.document_id}/file`} target="_blank" rel="noreferrer">{t("פתיחת הקובץ המקורי ↗", "Open the original file ↗")}</a>
        </div>
        {(item.replaces || item.replaced_by) && (
          <div className="ev-chain">
            {item.replaces && <>{item.replaces.by === "customer" ? t("מסמך חלופי שהלקוח העלה אחרי שבדיקת ה-AI החזירה את", "A replacement the customer uploaded after the AI check returned")
              : t("מסמך חלופי, הועלה לבקשת הבנקאי במקום", "A replacement, uploaded at the banker's request in place of")}{" "}
              <button className="link ltr" onClick={() => onSelect(`doc:${item.replaces!.document_id}`)}>{item.replaces.filename}</button></>}
            {item.replaced_by && <>{t("הוחלף במסמך", "Replaced by")} <button className="link ltr" onClick={() => onSelect(`doc:${item.replaced_by!.document_id}`)}>{item.replaced_by.filename}</button></>}
          </div>
        )}
        {item.ai.facts.length > 0 ? <KeyFields item={item} field={field} onPick={pick} />
          : <div className="tiny muted">{item.ai.status === "reviewed" ? t("לא זוהו נתונים במסמך.", "No data was identified in the document.") : t("ה-AI עדיין קורא את המסמך.", "The AI is still reading the document.")}</div>}
      </header>
      <div className="ev-toolbar">
        <span className="ev-toolbar-file ltr">{item.filename}</span>
        <span className="ev-toolbar-pages">
          {item.pages > 1 ? Array.from({ length: item.pages }, (_, i) => i + 1).map((p) => (
            <button key={p} className={`pg${p === page ? " on" : ""}`} onClick={() => setPage(p)}>{t("עמ׳", "p.")} {p}</button>))
            : <span>{t("עמוד 1 מתוך 1", "Page 1 of 1")}</span>}
        </span>
        <span className="ev-zoom">
          <button onClick={() => setZoom(Math.max(0.7, +(zoom - 0.15).toFixed(2)))} aria-label={t("הקטנה", "Zoom out")}>−</button>
          <button onClick={() => setZoom(1)} aria-label={t("התאמה לרוחב", "Fit to width")} className="ltr">{Math.round(zoom * 100)}%</button>
          <button onClick={() => setZoom(Math.min(1.6, +(zoom + 0.15).toFixed(2)))} aria-label={t("הגדלה", "Zoom in")}>+</button>
        </span>
      </div>
      <div className="ev-page">
        <div style={{ maxWidth: 820 * zoom, margin: "0 auto" }}>
          <EvidenceViewer documentId={item.document_id} facts={item.ai.facts} page={page} focus={field} dpi={160} interactive quiet onFocus={pick}
            autoScroll={picked} />
        </div>
      </div>
    </div>
  );
}

function MissingEvidence({ item, onSelect, ws }: { item: MissingItem; onSelect: (id: string) => void; ws: Workspace }) {
  const borrower = ws.case.borrowers.find((b) => b.borrower_id === item.borrower_id);
  const { en, t } = useLang();
  return (
    <div className="ev ev-missing" data-testid="missing-evidence">
      <div className="missing-card">
        <div className="missing-icon" aria-hidden>?</div>
        <div className="ev-title" data-testid="missing-title">{en ? (item.period_he ? `No ${locOf(item, "period_he")} payslip received from ${borrower ? locOf(borrower, "name_he") : ""}`
          : `${locOf(item, "status_he")}: ${locOf(item, "title_he")}`)
          : item.period_he ? `לא התקבל תלוש ${item.period_he} של ${borrower?.name_he}`
          : `${item.status_he}: ${item.title_he}`}</div>
        <p className="small">{locOf(item, "explanation_he")}</p>
        <p className="tiny muted">{item.period_he ? t("זהו חודש נדרש שלא הועלה, אין מסמך לאשר. אפשר לבקש מהלקוח להשלים אותו.", "This is a required month that wasn't uploaded; there's no document to accept. You can ask the customer to complete it.")
          : t("זו דרישה ממדיניות המסמכים של הבקשה שעדיין לא מולאה, אין מסמך לאשר. אפשר לבקש מהלקוח להשלים אותה.", "This is a requirement of the application's document policy that isn't met yet; there's no document to accept. You can ask the customer to complete it.")}</p>
        {item.related_documents.length > 0 && (
          <div className="missing-related">
            <div className="small bold">{t("ייתכן שקשור:", "Possibly related:")}</div>
            {item.related_documents.map((d) => (
              <button key={d.document_id} className="related-doc" onClick={() => onSelect(`doc:${d.document_id}`)}>
                <span className="ltr">{d.filename}</span><span className="small muted">{locOf(d, "note_he")}</span>
              </button>
            ))}
          </div>
        )}
        {item.duplicate_note_he && <div className="tiny muted" style={{ marginTop: 8 }}>{locOf(item, "duplicate_note_he")}</div>}
      </div>
    </div>
  );
}

function FindingEvidence({ item, focus, setFocus, ws }: { item: CaseFindingItem; focus: Focus | null; setFocus: (f: Focus | null) => void; ws: Workspace }) {
  const active = focus?.documentId || item.evidence_documents[0]?.document_id;
  const doc = ws.items.find((i): i is DocItem => i.kind === "document" && i.document_id === active);
  const ev = item.evidence_documents.find((e) => e.document_id === active);
  const { en, t } = useLang();
  return (
    <div className="ev">
      <header className="ev-head">
        <div className="ev-title">{locOf(item, "title_he")}</div>
        {item.income && (() => {
          const inc = item.income;
          const cells: [string, string, string?][] = en ? [
            ["Declared net", ilsL(inc.declared_net_monthly_ils)],
            [inc.months_compared.length === 1 ? `Net ${locOf(inc, "documented_label_he")}` : "Payslip average", ilsL(inc.average_documented_net_ils)],
            ["Gap", inc.difference_ils != null ? `${ilsL(inc.difference_ils)} (${inc.difference_pct}%)` : "-"],
            ["Comparison basis", `${inc.months_compared.length}/${inc.months_required} months${inc.basis === "preliminary" ? " · preliminary" : ""}`,
              inc.basis === "preliminary" ? "warn" : ""],
            ["Tolerance", `${inc.tolerance_pct}%`]] : [
            ["נטו מוצהר", ilsL(inc.declared_net_monthly_ils)],
            [inc.months_compared.length === 1 ? `נטו ${inc.documented_label_he}` : "ממוצע בתלושים", ilsL(inc.average_documented_net_ils)],
            ["פער", inc.difference_ils != null ? `${ilsL(inc.difference_ils)} (${inc.difference_pct}%)` : "-"],
            ["בסיס ההשוואה", `${inc.months_compared.length}/${inc.months_required} חודשים${inc.basis === "preliminary" ? " · ראשונית" : ""}`,
              inc.basis === "preliminary" ? "warn" : ""],
            ["סף סבולת", `${inc.tolerance_pct}%`]];
          return (
            <div className="key-fields" data-testid="income-table"><div className="kf-row">
              {cells.map(([label, value, tone]) => (
                <div key={label} className={`kf static${tone ? ` ${tone}` : ""}`}><span className="kf-label">{label}</span><span className="kf-value"><bdi>{value}</bdi></span></div>
              ))}
            </div></div>
          );
        })()}
        {item.evidence_documents.length > 0 && (
          <div className="ev-tools">
            <span className="tiny muted">{t("ראיות:", "Evidence:")}</span>
            {item.evidence_documents.map((e) => (
              <button key={e.document_id} className={`pg${e.document_id === active ? " on" : ""}`}
                onClick={() => setFocus({ documentId: e.document_id, field: e.field })}>
                {(e.period_he ? locOf(e, "period_he") : "") || e.filename} · {locOf(e, "label_he")} <span className="ltr">{e.value}</span>
              </button>
            ))}
          </div>
        )}
      </header>
      <div className="ev-page">
        {doc ? <EvidenceViewer documentId={doc.document_id} facts={doc.ai.facts} focus={ev?.field || null} dpi={160} interactive quiet autoScroll={!!focus} />
          : <div className="desk-empty">{t("לממצא זה אין ראיה במסמך מסוים.", "This finding has no evidence on a specific document.")}</div>}
      </div>
    </div>
  );
}
