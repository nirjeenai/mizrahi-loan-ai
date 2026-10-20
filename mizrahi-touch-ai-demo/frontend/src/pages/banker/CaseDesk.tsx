import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ilsL, type CaseFindingItem, type DeskResult, type DocItem, type MissingItem, type QueueItem, type Workspace } from "../../api";
import { IChevron, IDocs } from "../../components/Icons";
import { Loc, locOf, Orig, tr, useLang } from "../../i18n";
import { DecisionPanel } from "./DecisionPanel";
import { BANKER_TONE, newRequestId, Toast, VERDICT_TONE, When } from "./deskUi";
import { DocumentEvidence, FindingEvidence, HandoffBanner, IncomeLine, MONTH_TONE, type Focus } from "./ReviewWorkspace";
import "./casedesk.css";

/** The case desk: the banker's default view of a case. Without an item it is the case overview (where the case stands,
 *  the one next step, the work grouped by who holds it); with an item (`?item=`) it is the focused review of that item
 *  (the document beside the decision, or a missing requirement on its own). Every decision goes through the same
 *  DecisionPanel forms and service routes as the classic review, so state semantics and audit are unchanged. */

type ToastMsg = { text: string; tone: "ok" | "bad" } | null;
type Tier = "yours" | "customer" | "processing" | "done";
const YOURS = ["decide", "judgment", "escalated"];
const CUSTOMER = ["correction", "missing"];
const tierOf = (group: string): Tier => (YOURS.includes(group) ? "yours" : CUSTOMER.includes(group) ? "customer" : group === "processing" ? "processing" : "done");

export function CaseDesk({ ws, selected, onSelect, onOverview, reload, staff, readOnly, stale, openV3, openFollowup }: {
  ws: Workspace; selected: string | null; onSelect: (id: string) => void; onOverview: () => void; reload: () => void; staff: string;
  readOnly: boolean; stale: boolean; openV3: () => void; openFollowup: () => void;
}) {
  const { en, t } = useLang();
  const byId = useMemo(() => Object.fromEntries(ws.items.map((i) => [i.id, i])), [ws.items]);
  const current: QueueItem | undefined = selected ? byId[selected] : undefined;
  const [toast, setToast] = useState<ToastMsg>(null);
  const clearToast = useCallback(() => setToast(null), []);
  const [composing, setComposing] = useState(false);
  const lastOpened = useRef<string | null>(null);
  const open = useCallback((id: string) => { lastOpened.current = id; onSelect(id); }, [onSelect]);
  return (
    <div className="cd" data-testid="case-desk" data-mode={current ? "review" : "overview"}>
      {stale && <div className="desk-stale" role="status">{t("לא הצלחנו לרענן את התיק, ייתכן שהמידע אינו עדכני.", "We couldn't refresh the case; the information may be out of date.")}</div>}
      {readOnly && <div className="desk-stale" role="status">{en ? <>The case is assigned to {locOf(ws.case.banker, "name_he")}. You can view it, but you can't record decisions in it.</>
        : <>התיק משויך ל{ws.case.banker.name_he}. אפשר לצפות בו, אבל אי אפשר לרשום בו החלטות.</>}</div>}
      {(ws.handoffs?.length || 0) > 0 && <div className="cd-handoffs"><HandoffBanner ws={ws} reload={reload} readOnly={readOnly} onToast={setToast} /></div>}
      {current
        ? <ReviewMode key="review" ws={ws} current={current} byId={byId} onSelect={onSelect} onOverview={onOverview} reload={reload} staff={staff}
            readOnly={readOnly} onToast={setToast} />
        : <Overview key="overview" ws={ws} onOpen={open} reload={reload} readOnly={readOnly} onToast={setToast} onCompose={() => setComposing(true)}
            openV3={openV3} openFollowup={openFollowup} returnTo={lastOpened.current} />}
      {composing && <RequestSheet ws={ws} onClose={() => setComposing(false)}
        onDone={(text) => { setComposing(false); setToast({ text, tone: "ok" }); reload(); }} />}
      <Toast message={toast} onClose={clearToast} />
    </div>
  );
}

// ---------------------------------------------------------------- shared helpers

/** "אסמכתה למטרה · " (a document without an owner) reads without the dangling separator; a document the policy only
 *  names "מסמך" takes the requirement's family instead. */
function titleOf(item: QueueItem, ws: Workspace): string {
  let s = locOf(item, "title_he").replace(/[\s·—-]+$/u, "").trim();
  if (item.kind === "document" && (/^(מסמך|Document)$/.test(s) || !s)) {
    const row = ws.requirement_matrix?.find((r) => r.code === item.requirement_code);
    s = (row && (locOf(row, "family_he") || locOf(row, "title_he"))) || locOf(item, "doc_type_he") || s;
  }
  return s;
}

function statusOf(item: QueueItem): { text: string; tone: string } {
  if (item.kind === "document") {
    return item.banker.status === "AWAITING_DECISION"
      ? { text: `AI · ${locOf(item.ai, "verdict_he")}`, tone: VERDICT_TONE[item.ai.verdict || ""] || "neutral" }
      : { text: locOf(item.banker, "status_he"), tone: BANKER_TONE[item.banker.status] || "neutral" };
  }
  if (item.kind === "missing") return item.open_request ? { text: tr("נשלחה בקשה", "Request sent"), tone: "warn" } : { text: locOf(item, "status_he") || tr("לא הועלה", "Not uploaded"), tone: "miss" };
  const f = item.finding;
  if (f.status !== "open") return { text: locOf(f, "status_he"), tone: "neutral" };
  return item.open_request ? { text: tr("ממתין ללקוח", "Waiting for the customer"), tone: "warn" }
    : item.escalated ? { text: tr("בהמשך בירור", "Under further review"), tone: "info" } : { text: tr("לשיקול דעתך", "For your judgment"), tone: "navy" };
}

const groupItems = (ws: Workspace, keys: string[]) => ws.groups.filter((g) => keys.includes(g.key)).flatMap((g) => g.items);
const requestableOf = (ws: Workspace) => ws.items.filter((i): i is MissingItem => i.kind === "missing" && !i.open_request && i.allowed_actions.length > 0);

function Chev({ dir }: { dir: "fwd" | "bwd" }) {
  return <span className={`cd-chev ${dir}`} aria-hidden><IChevron size={16} /></span>;
}

// ---------------------------------------------------------------- overview

function Overview({ ws, onOpen, reload, readOnly, onToast, onCompose, openV3, openFollowup, returnTo }: {
  ws: Workspace; onOpen: (id: string) => void; reload: () => void; readOnly: boolean; onToast: (t: ToastMsg) => void; onCompose: () => void;
  openV3: () => void; openFollowup: () => void; returnTo: string | null;
}) {
  const { t } = useLang();
  const byId = useMemo(() => Object.fromEntries(ws.items.map((i) => [i.id, i])), [ws.items]);
  const [scrolled, setScrolled] = useState(false);
  const [showDone, setShowDone] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  // coming back from an item: the row it came from is where the eye returns
  useEffect(() => {
    if (!returnTo) return;
    scroller.current?.querySelector(`[data-item-id="${CSS.escape(returnTo)}"]`)?.scrollIntoView({ block: "center" });
  }, [returnTo]);
  const requestable = requestableOf(ws);
  const sections: { key: Tier; title: string; hint: string; ids: string[] }[] = [
    { key: "yours", title: t("לטיפולך", "For you"), hint: t("מסמכים וממצאים שמחכים להחלטה שלך", "Documents and findings waiting for your decision"), ids: groupItems(ws, YOURS) },
    { key: "customer", title: t("אצל הלקוח", "With the customer"), hint: t("מה שחסר או הוחזר לתיקון", "What is missing or was returned for correction"), ids: groupItems(ws, CUSTOMER) },
    { key: "processing", title: t("בבדיקת AI", "Being checked by the AI"), hint: t("מסמכים שה-AI עדיין קורא, או שעיבודם נכשל", "Documents the AI is still reading, or that failed"), ids: groupItems(ws, ["processing"]) },
    { key: "done", title: t("הושלם", "Done"), hint: t("מסמכים שקיבלת או שהוחלפו, וממצאים שהכרעת בהם", "Documents you accepted or that were replaced, and findings you ruled on"), ids: groupItems(ws, ["done"]) },
  ];
  const empty = sections.every((s) => !s.ids.length);
  return (
    <div className={`cd-scroll${scrolled ? " scrolled" : ""}`} ref={scroller} onScroll={(e) => setScrolled((e.target as HTMLElement).scrollTop > 4)}>
      <div className="cd-page cd-enter">
        <CaseHead ws={ws} />
        <section className="cd-status" aria-label={t("מצב התיק והצעד הבא", "Where the case stands and the next step")}>
          <Pipeline ws={ws} onOpen={onOpen} />
          <NextStep ws={ws} onOpen={onOpen} onCompose={onCompose} readOnly={readOnly} reload={reload} onToast={onToast} openV3={openV3} openFollowup={openFollowup} />
        </section>
        <div className="cd-cols">
          <div className="cd-main" data-testid="review-queue">
            {empty && <div className="cd-empty">{t("אין עדיין מסמכים בתיק. כשהלקוח יעלה מסמכים לבקשת ההלוואה, הם יופיעו כאן.",
              "There are no documents in the case yet. When the customer uploads documents for the loan application, they'll appear here.")}</div>}
            {sections.map((s) => {
              if (!s.ids.length) return null;
              const collapsed = s.key === "done" && !showDone;
              return (
                <section key={s.key} className={`cd-sec s-${s.key}`} id={`cd-sec-${s.key}`} data-testid={`desk-section-${s.key}`}>
                  <header className="cd-sec-head">
                    <div className="cd-sec-titles">
                      <h2>{s.title} <span className="cd-count">{s.ids.length}</span></h2>
                      <span className="cd-sec-hint">{s.hint}</span>
                    </div>
                    {s.key === "customer" && requestable.length > 0 && !readOnly && (
                      <button className="cd-btn cd-btn-customer-quiet" onClick={onCompose} data-testid="compose-requests-section">
                        {t(`בקשת השלמה (${requestable.length})`, `Request missing (${requestable.length})`)}</button>
                    )}
                    {s.key === "done" && <button className="cd-btn cd-btn-plain" aria-expanded={!collapsed} onClick={() => setShowDone(!showDone)}
                      data-testid="toggle-done">{collapsed ? t("הצגה", "Show") : t("הסתרה", "Hide")}</button>}
                  </header>
                  {!collapsed && <div className="cd-list">{s.ids.map((id) => byId[id] && <ItemRow key={id} item={byId[id]} ws={ws} onOpen={onOpen} />)}</div>}
                </section>
              );
            })}
          </div>
          <aside className="cd-aside">
            <PrepCard ws={ws} readOnly={readOnly} reload={reload} onToast={onToast} openV3={openV3} />
            <IncomeCard ws={ws} onOpen={onOpen} />
            <RequirementsCard ws={ws} onOpen={onOpen} />
          </aside>
        </div>
      </div>
    </div>
  );
}

function CaseHead({ ws }: { ws: Workspace }) {
  const { en, t } = useLang();
  const p = ws.document_profile;
  const names = en ? ws.case.borrowers.map((b) => locOf(b, "name_he")).join(" & ") : ws.case.borrowers.map((b) => b.name_he).join(" ו");
  const stage = ws.bank_stage;
  return (
    <header className="cd-head">
      <div className="cd-head-main">
        <div className="cd-eyebrow">
          <span>{t("תיק", "Case")} <span className="ltr">{ws.case.display_number}</span></span>
          {p?.profile_label_he && <span className="cd-tag" data-testid="banker-profile-label">{locOf(p, "profile_label_he")}</span>}
          {p?.banker_assisted && <span className="cd-tag" data-testid="banker-assisted">{t("ליווי בנקאי · מסלול עסקי מוגבל", "Banker-assisted · limited business track")}</span>}
        </div>
        <h1 className="cd-title">{p?.company ? locOf(p.company, "name_he") : names}</h1>
        <div className="cd-sub">
          {p?.company && <span>{names}</span>}
          <span>{locOf(ws.case, "title_he")}</span>
          {ws.case.requested_loan_ils ? <span><span className="ltr cd-num">{ilsL(ws.case.requested_loan_ils)}</span></span> : null}
        </div>
      </div>
      <dl className="cd-facts">
        <div title={t("שלב הבקשה כפי שהוא רשום בתיק. פעולות בקונסולה אינן משנות אותו.", "The application's stage as recorded in the case. Actions in the console don't change it.")}>
          <dt>{t("שלב רשמי בבנק", "Bank stage (official)")} <span className="cd-demo">{t("דמו", "demo")}</span></dt>
          <dd data-testid="bank-stage">{locOf(stage, "label_he")} <span className="ltr cd-faint">({stage.index}/{stage.of})</span></dd>
        </div>
        <div>
          <dt>{t("בנקאי/ת מטפל/ת", "Assigned banker")}</dt>
          <dd>{locOf(ws.case.banker, "name_he")}</dd>
        </div>
      </dl>
    </header>
  );
}

// ---------------------------------------------------------------- pipeline: the documentation track in four steps

type StepState = "done" | "you" | "customer" | "working" | "ready" | "idle" | "bad";
interface Step { key: string; label: string; detail: string; state: StepState; target?: string | null }

function steps(ws: Workspace): Step[] {
  const s = ws.summary;
  const g = s.groups;
  const yours = (g.decide || 0) + (g.judgment || 0) + (g.escalated || 0);
  const missing = g.missing || 0;
  const corr = g.correction || 0;
  const asked = ws.customer_requests.filter((q) => q.status === "OPEN" && q.kind !== "missing_document" && q.kind !== "correction").length;
  const requested = ws.items.filter((i) => i.kind === "missing" && i.open_request).length;
  const working = s.processing > 0 || ["CHECKING", "RECHECKING"].includes(ws.review_state.state);
  const p = ws.progress;
  const firstOf = (keys: string[]) => groupItems(ws, keys)[0] || null;
  const collect: Step = {
    key: "collect", label: tr("מסמכים מהלקוח", "Customer documents"), target: firstOf(CUSTOMER),
    state: missing + corr + asked ? "customer" : s.documents ? "done" : "idle",
    detail: missing + corr + asked
      ? [missing ? tr(`חסרים ${missing}`, `${missing} missing`) : "", requested ? (requested === missing ? tr("כולם נתבקשו", "all requested") : tr(`${requested} נתבקשו`, `${requested} requested`)) : "",
        corr ? tr(`${corr} לתיקון`, `${corr} to correct`) : "", asked ? tr(`${asked} בקשות הסבר`, `${asked} explanation requests`) : ""].filter(Boolean).join(" · ")
      : s.documents ? (p?.total ? tr(`${p.done}/${p.total} דרישות הושלמו`, `${p.done}/${p.total} requirements met`) : tr("התקבלו", "Received")) : tr("אין דרישות פתוחות", "No open requirements"),
  };
  const ai: Step = ws.review_state.state === "ERROR"
    ? { key: "ai", label: tr("בדיקת AI", "AI check"), state: "bad", detail: locOf(ws.review_state, "label_he"), target: firstOf(["processing"]) }
    : working ? { key: "ai", label: tr("בדיקת AI", "AI check"), state: "working", detail: s.processing ? tr(`בודק ${s.processing} מסמכים`, `Checking ${s.processing} documents`) : tr("בודק את סט המסמכים", "Checking the document set") }
      : { key: "ai", label: tr("בדיקת AI", "AI check"), state: s.documents ? "done" : "idle", detail: s.documents ? tr(`${s.documents} מסמכים נבדקו`, `${s.documents} documents checked`) : tr("ממתין למסמכים", "Waiting for documents") };
  const review: Step = {
    key: "review", label: tr("הסקירה שלך", "Your review"), target: firstOf(YOURS),
    state: yours ? "you" : (g.done || 0) > 0 ? "done" : "idle",
    detail: yours ? tr(`${yours} ממתינים להחלטתך`, `${yours} awaiting your decision`) : (g.done || 0) > 0 ? tr("אין פריטים פתוחים", "No open items") : tr("אין עדיין מה להחליט", "Nothing to decide yet"),
  };
  const prep: Step = ws.preparation
    ? { key: "prep", label: tr("הכנת התיק", "Case preparation"), state: "done", detail: tr("ההכנה אושרה", "Preparation confirmed") }
    : ws.can_confirm.allowed ? { key: "prep", label: tr("הכנת התיק", "Case preparation"), state: yours ? "idle" : "ready",
      detail: yours ? tr("אפשר לאשר כבר עכשיו", "Can be confirmed already") : tr("מוכן לאישור שלך", "Ready for your confirmation") }
      : { key: "prep", label: tr("הכנת התיק", "Case preparation"), state: "idle", detail: tr("אחרי השלמת המסמכים", "After the documents are complete") };
  return [collect, ai, review, prep];
}

function Pipeline({ ws, onOpen }: { ws: Workspace; onOpen: (id: string) => void }) {
  const { t } = useLang();
  const list = steps(ws);
  return (
    <ol className="cd-pipe" data-testid="case-progress" aria-label={t("מצב מסמכי התיק", "Where the case documents stand")}>
      {list.map((s, i) => {
        const body = (<>
          <span className={`cd-node ${s.state}`} aria-hidden>{s.state === "done" ? "✓" : s.state === "working" ? <span className="spinner" /> : s.state === "bad" ? "!" : i + 1}</span>
          <span className="cd-step-text">
            <span className="cd-step-label">{s.label}</span>
            <span className="cd-step-detail">{s.detail}</span>
          </span>
          {i < list.length - 1 && <span className="cd-rail" aria-hidden />}
        </>);
        return (
          <li key={s.key} className={`cd-step s-${s.state}`} data-step={s.key} data-state={s.state}>
            {s.target ? <button className="cd-step-btn" onClick={() => onOpen(s.target!)}>{body}</button> : <div className="cd-step-btn static">{body}</div>}
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------- the next step

function NextStep({ ws, onOpen, onCompose, readOnly, reload, onToast, openV3, openFollowup }: {
  ws: Workspace; onOpen: (id: string) => void; onCompose: () => void; readOnly: boolean; reload: () => void; onToast: (t: ToastMsg) => void;
  openV3: () => void; openFollowup: () => void;
}) {
  const { t } = useLang();
  const [confirming, setConfirming] = useState(false);
  const s = ws.summary;
  const g = s.groups;
  const yoursIds = groupItems(ws, YOURS);
  const customerIds = groupItems(ws, CUSTOMER);
  const requestable = requestableOf(ws);
  const working = s.processing > 0 || ["CHECKING", "RECHECKING"].includes(ws.review_state.state);
  const firstAttention = yoursIds.map((id) => ws.items.find((i) => i.id === id)).find((i) => i?.attention);
  let tone: "you" | "customer" | "working" | "ready" | "done" | "bad" | "idle";
  let title: string; let body: ReactNode = null;
  let primary: ReactNode = null; const secondary: ReactNode[] = [];
  const btn = (label: string, onClick: () => void, cls: string, testId: string, disabled = false) =>
    <button key={testId} className={`cd-btn ${cls}`} onClick={onClick} data-testid={testId} disabled={disabled}>{label}</button>;
  if (yoursIds.length) {
    tone = "you";
    title = yoursIds.length === 1 ? t("פריט אחד ממתין להחלטתך", "One item is waiting for your decision") : t(`${yoursIds.length} פריטים ממתינים להחלטתך`, `${yoursIds.length} items are waiting for your decision`);
    const gap = (g.judgment || 0) > 0;
    body = firstAttention && firstAttention.kind === "document" && firstAttention.ai.attention_he[0]
      ? <><b>{titleOf(firstAttention, ws)}:</b> <Loc he={firstAttention.ai.attention_he[0]} en={(firstAttention.ai as { attention_en?: (string | null)[] }).attention_en?.[0]} /></>
      : gap ? t("ה-AI סיים לבדוק את המסמכים ומצא פער שה-AI אינו סוגר בעצמו. הוא מחכה לשיקול דעתך, לצד המסמכים לקבלה.",
          "The AI finished checking the documents and found a gap it doesn't close by itself. It waits for your judgment, alongside the documents to accept.")
        : t("ה-AI סיים לבדוק את המסמכים. עברו עליהם אחד אחד: קבלה, החזרה לתיקון או העברה לבירור.",
          "The AI finished checking the documents. Go through them one by one: accept, return for correction, or escalate.");
    primary = btn(t("התחלת הסקירה", "Start the review"), () => onOpen((firstAttention?.id) || yoursIds[0]), "cd-btn-primary", "next-step-primary");
    if (requestable.length && !readOnly) secondary.push(btn(requestable.length === 1 ? t("בקשת המסמך החסר", "Request the missing document")
      : t(`בקשת ${requestable.length} מסמכים חסרים`, `Request ${requestable.length} missing documents`), onCompose, "cd-btn-secondary", "compose-requests"));
  } else if (working) {
    tone = "working";
    title = t("ה-AI בודק את המסמכים", "The AI is checking the documents");
    body = t("התיק יתעדכן כאן מעצמו כשהבדיקה תסתיים. בינתיים אין מה להחליט.", "The case updates here by itself when the check finishes. There's nothing to decide in the meantime.");
  } else if (ws.review_state.state === "ERROR") {
    tone = "bad";
    title = locOf(ws.review_state, "label_he");
    body = t("עיבוד של מסמך או של סט המסמכים נכשל. אפשר לפתוח את המסמך ולבקש מהלקוח להעלות אותו שוב.", "Processing a document or the document set failed. You can open the document and ask the customer to upload it again.");
    const first = groupItems(ws, ["processing"])[0];
    if (first) primary = btn(t("פתיחת המסמך", "Open the document"), () => onOpen(first), "cd-btn-primary", "next-step-primary");
  } else if (requestable.length) {
    tone = "customer";
    const n = requestable.length;
    const what = n === 1 ? t("חסר מסמך אחד", "One document is missing") : t(`חסרים ${n} מסמכים`, `${n} documents are missing`);
    title = !s.documents ? `${what}${t(" כדי להתחיל בבדיקה", " before the review can start")}` : what;
    body = n === 1 ? t("הבקשה תופיע ללקוח באפליקציה עם כפתור העלאה, בלי SMS או דוא״ל.", "The request appears to the customer in the app with an upload button — no SMS or email.")
      : t("אפשר לבקש את כולם בפעולה אחת. כל מסמך יופיע ללקוח באפליקציה עם כפתור העלאה משלו, בלי SMS או דוא״ל.",
        "You can request them all in one step. Each document appears to the customer in the app with its own upload button — no SMS or email.");
    if (!readOnly) primary = btn(n === 1 ? t("בקשת המסמך מהלקוח", "Request the document") : t("בקשת המסמכים מהלקוח", "Request the documents"), onCompose, "cd-btn-customer", "compose-requests");
    secondary.push(btn(t("מעבר פריט אחר פריט", "Go item by item"), () => onOpen(requestable[0].id), "cd-btn-secondary", "next-step-item"));
  } else if (customerIds.length) {
    tone = "customer";
    title = t("ממתינים ללקוח", "Waiting for the customer");
    const corr = g.correction || 0; const missing = g.missing || 0;
    body = [missing ? t(`${missing} בקשות להשלמת מסמך פתוחות`, `${missing} open requests for missing documents`) : "",
      corr ? t(`${corr} מסמכים הוחזרו לתיקון`, `${corr} documents returned for correction`) : ""].filter(Boolean).join(" · ")
      + t(". הבקשות מוצגות ללקוח באפליקציה; כשיעלה מסמך, ה-AI יבדוק אותו והוא יחזור אלייך.", ". The requests are shown to the customer in the app; when a document arrives, the AI checks it and it comes back to you.");
    primary = btn(t("מעקב השלמה", "Completion follow-up"), openFollowup, "cd-btn-primary", "next-step-primary");
    secondary.push(btn(t("פתיחת הפריטים", "Open the items"), () => onOpen(customerIds[0]), "cd-btn-secondary", "next-step-item"));
  } else if (ws.preparation) {
    tone = "done";
    title = t("הכנת מסמכי הבקשה אושרה", "The application documents are confirmed as prepared");
    body = <>{t("האישור נרשם בתיק עם חבילת הראיות", "The confirmation is recorded in the case with the evidence package")} <When at={ws.preparation.confirmed_at} />{ws.preparation.note ? <> · <Orig text={ws.preparation.note} /></> : null}.
      {" "}{t("זו אינה החלטת אשראי.", "This is not a credit decision.")}</>;
    primary = btn(t("פתיחת התיק המוכן", "Open the prepared case"), openV3, "cd-btn-ok", "open-ready-case");
  } else if (ws.can_confirm.allowed) {
    tone = "ready";
    title = t("המסמכים מוכנים לאישור ההכנה", "The documents are ready for your confirmation");
    body = <>{t("כל הדרישות התקבלו ונבדקו. אישור ההכנה נרשם בתיק עם חבילת הראיות; הוא אינו החלטת אשראי ואינו משנה את שלב הבקשה בבנק.",
      "Every requirement was received and checked. The confirmation is recorded in the case with the evidence package; it isn't a credit decision and doesn't change the application's stage at the bank.")}
      {ws.can_confirm.open_banker_items > 0 && <> {t(`${ws.can_confirm.open_banker_items} ממצאים לשיקול דעתך יישארו פתוחים ויתועדו בחבילה.`, `${ws.can_confirm.open_banker_items} findings for your judgment will stay open and be recorded in the package.`)}</>}</>;
    if (!readOnly) primary = btn(t("אישור הכנת המסמכים", "Confirm document preparation"), () => setConfirming(true), "cd-btn-ok", "confirm-preparation");
    secondary.push(btn(t("פתיחת התיק המוכן", "Open the prepared case"), openV3, "cd-btn-secondary", "open-ready-case"));
  } else {
    tone = "idle";
    title = t("אין עדיין מסמכים בתיק", "There are no documents in the case yet");
    body = locOf(ws.can_confirm, "reason_he") || null;
  }
  return (
    <section className={`cd-next t-${tone}`} data-testid="next-step" data-tone={tone} aria-live="polite">
      <div className="cd-next-eyebrow" data-testid="banker-readiness">{locOf(ws.review_state, "label_he")}</div>
      <h2 className="cd-next-title">{title}</h2>
      {body && <p className="cd-next-body">{body}</p>}
      {!ws.preparation && ws.preparation_stale && <p className="cd-next-note" data-testid="preparation-stale">{tr(
        `האישור מ־${ws.preparation_stale.confirmed_at.slice(0, 10)} אינו בתוקף עוד: ${ws.preparation_stale.reason_he}. יש לאשר שוב אחרי הבדיקה.`,
        `The confirmation from ${ws.preparation_stale.confirmed_at.slice(0, 10)} is no longer valid: ${locOf(ws.preparation_stale, "reason_he")}. Confirm again after the review.`)}</p>}
      {confirming ? <ConfirmPrep ws={ws} onCancel={() => setConfirming(false)} onDone={(text) => { setConfirming(false); onToast({ text, tone: "ok" }); reload(); }}
        onError={(text) => onToast({ text, tone: "bad" })} />
        : (primary || secondary.length > 0) && <div className="cd-next-actions">{primary}{secondary}</div>}
    </section>
  );
}

function ConfirmPrep({ ws, onCancel, onDone, onError }: { ws: Workspace; onCancel: () => void; onDone: (text: string) => void; onError: (text: string) => void }) {
  const { t } = useLang();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [rid] = useState(newRequestId);
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  const go = async () => {
    setBusy(true);
    try {
      await api.confirmPreparation(ws.case_id, { note, request_id: rid });
      onDone(t("הכנת מסמכי הבקשה אושרה ונשמרה עם חבילת הראיות. שלב הבקשה בבנק לא השתנה.",
        "The application documents were confirmed as prepared and saved with the evidence package. The application's stage at the bank didn't change."));
    } catch (e) { onError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="cd-confirm" data-testid="confirm-preparation-form">
      <textarea ref={ref} className="cd-input" placeholder={t("הערה פנימית (רשות)", "Internal note (optional)")} value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="cd-next-actions">
        <button className="cd-btn cd-btn-ok" disabled={busy} onClick={go} data-testid="confirm-preparation-submit">{busy && <span className="spinner" />}{t("אישור הכנת מסמכי הבקשה", "Confirm the application documents are prepared")}</button>
        <button className="cd-btn cd-btn-plain" disabled={busy} onClick={onCancel}>{t("ביטול", "Cancel")}</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- rows

function Thumb({ item }: { item: QueueItem }) {
  const [failed, setFailed] = useState(false);
  if (item.kind === "document" && !failed) {
    return <span className="cd-thumb"><img src={`/api/documents/${item.document_id}/pages/1.png?dpi=60`} alt="" loading="lazy" onError={() => setFailed(true)} /></span>;
  }
  if (item.kind === "case_finding") return <span className="cd-thumb finding" aria-hidden>≠</span>;
  return <span className={`cd-thumb ${item.kind === "missing" ? "missing" : "file"}`} aria-hidden><IDocs size={18} /></span>;
}

function ItemRow({ item, ws, onOpen }: { item: QueueItem; ws: Workspace; onOpen: (id: string) => void }) {
  const { en, t } = useLang();
  const st = statusOf(item);
  let meta: ReactNode = null;
  let why: ReactNode = null;
  if (item.kind === "document") {
    meta = <><span className="ltr">{item.filename}</span>{item.replaces && <span className="cd-row-note">{t("מסמך חלופי", "Replacement document")}</span>}</>;
    if (item.attention && item.ai.attention_he[0]) why = en ? <Loc he={item.ai.attention_he[0]} en={(item.ai as { attention_en?: (string | null)[] }).attention_en?.[0]} /> : item.ai.attention_he[0];
  } else if (item.kind === "missing") {
    meta = item.open_request ? <>{t("בקשה נשלחה", "Requested")} <When at={item.open_request.created_at} /></> : null;
  } else {
    meta = item.income?.difference_pct != null ? <span>{t("פער", "Gap")} <span className="ltr">{Math.abs(item.income.difference_pct).toFixed(1)}%</span> · {item.basis.partial
      ? t(`${item.basis.months_compared.length} מתוך ${item.basis.months_required.length} חודשים`, `${item.basis.months_compared.length} of ${item.basis.months_required.length} months`)
      : t(`${item.basis.months_required.length} חודשים`, `${item.basis.months_required.length} months`)}</span> : null;
    why = item.income ? locOf(item.income, "summary_he") : null;
  }
  return (
    <button className={`cd-row k-${item.kind}${item.attention ? " attn" : ""}`} onClick={() => onOpen(item.id)}
      data-testid="queue-item" data-item-id={item.id} data-kind={item.kind}>
      <Thumb item={item} />
      <span className="cd-row-main">
        <span className="cd-row-title">{item.attention && <span className="cd-attn" aria-label={t("דורש תשומת לב", "Needs attention")} />}{titleOf(item, ws)}</span>
        {meta && <span className="cd-row-meta">{meta}</span>}
        {why && <span className="cd-row-why">{why}</span>}
      </span>
      <span className={`cd-pill ${st.tone}`}>{st.text}</span>
      <Chev dir="fwd" />
    </button>
  );
}

// ---------------------------------------------------------------- side cards

function PrepCard({ ws, readOnly, reload, onToast, openV3 }: { ws: Workspace; readOnly: boolean; reload: () => void; onToast: (t: ToastMsg) => void; openV3: () => void }) {
  const { t } = useLang();
  const [confirming, setConfirming] = useState(false);
  const yours = groupItems(ws, YOURS).length;
  // when nothing else is open the next-step card already carries this step
  if (ws.preparation || (ws.can_confirm.allowed && !yours && !requestableOf(ws).length && !groupItems(ws, CUSTOMER).length)) return null;
  const ready = ws.can_confirm.allowed;
  return (
    <section className="cd-card" data-testid="case-step" data-ready={ready ? "true" : "false"}>
      <h3 className="cd-card-title">{t("הכנת התיק", "Case preparation")}</h3>
      <p className="cd-card-text">{ready ? t("אפשר לאשר את הכנת המסמכים כבר עכשיו; פריטים פתוחים לשיקול דעתך יתועדו בחבילה.",
        "You can confirm the documents as prepared now; items open for your judgment are recorded in the package.") : locOf(ws.can_confirm, "reason_he")}</p>
      {confirming ? <ConfirmPrep ws={ws} onCancel={() => setConfirming(false)} onDone={(text) => { setConfirming(false); onToast({ text, tone: "ok" }); reload(); }}
        onError={(text) => onToast({ text, tone: "bad" })} />
        : <div className="cd-card-actions">
          <button className="cd-btn cd-btn-secondary cd-btn-sm" disabled={!ready} onClick={openV3} data-testid="open-ready-case">{t("פתיחת התיק המוכן", "Open the prepared case")}</button>
          {ready && !readOnly && <button className="cd-btn cd-btn-plain cd-btn-sm" onClick={() => setConfirming(true)} data-testid="confirm-preparation">{t("אישור הכנה…", "Confirm preparation…")}</button>}
        </div>}
    </section>
  );
}

function IncomeCard({ ws, onOpen }: { ws: Workspace; onOpen: (id: string) => void }) {
  const { t } = useLang();
  const rows = ws.borrowers.filter((b) => b.months.length > 0 || b.income.declared_net_monthly_ils != null);
  if (!rows.length) return null;
  const go = (bid: string, m: Workspace["borrowers"][number]["months"][number]) => {
    if (m.state === "missing" || m.state === "requested") onOpen(`missing:${bid}:${m.period}`);
    else if (m.documents[0]) onOpen(`doc:${m.documents[0]}`);
  };
  return (
    <section className="cd-card" data-testid="borrower-strip">
      <h3 className="cd-card-title">{t("תלושים והכנסה", "Payslips and income")}</h3>
      {rows.map((b) => (
        <div key={b.borrower_id} className="cd-income">
          <div className="cd-income-name">{locOf(b, "name_he")}</div>
          {b.months.length > 0 && <div className="cd-months">
            {b.months.map((m) => (
              <button key={m.period} className={`cd-month ${MONTH_TONE[m.state] || "neutral"}`} onClick={() => go(b.borrower_id, m)} title={locOf(m, "state_he")}
                data-testid="month-chip" data-state={m.state}>
                <span className="cd-month-dot" aria-hidden />
                <span className="cd-month-name">{locOf(m, "label_he").split(" ")[0]}</span>
                <span className="cd-month-state">{locOf(m, "state_he")}{m.copies > 1 ? ` · ×${m.copies}` : ""}</span>
              </button>
            ))}
          </div>}
          <IncomeLine income={b.income} />
        </div>
      ))}
    </section>
  );
}

const REQ_TONE: Record<string, string> = { extracted: "ok", preparation_confirmed: "ok", accepted_by_banker: "ok", needs_banker_review: "navy", checking: "neutral",
  required_missing: "miss", needs_customer_action: "warn" };

function RequirementsCard({ ws, onOpen }: { ws: Workspace; onOpen: (id: string) => void }) {
  const { en, t } = useLang();
  const rows = ws.requirement_matrix || [];
  if (!rows.length) return null;
  const open = (code: string) => {
    const missing = ws.items.find((i) => i.id === `missing:${code}` || (i.kind === "missing" && i.requirement_code === code));
    const doc = ws.items.find((i): i is DocItem => i.kind === "document" && i.requirement_code === code && i.banker.status !== "REPLACED");
    const target = missing || doc;
    if (target) onOpen(target.id);
  };
  return (
    <section className="cd-card" data-testid="requirement-matrix">
      <h3 className="cd-card-title">{t("דרישות המסמכים", "Document requirements")}</h3>
      <p className="cd-card-fine">{en ? <>Per policy {rows[0].policy_version || ""}, pinned to the case</> : <>לפי מדיניות {rows[0].policy_version || ""}, שהוצמדה לתיק</>}</p>
      <ul className="cd-reqs">
        {rows.map((r) => (
          <li key={r.code}>
            <button className={`cd-req ${REQ_TONE[r.ai_state] || "neutral"}`} onClick={() => open(r.code)} data-testid="requirement-row" data-code={r.code} data-state={r.ai_state} title={locOf(r, "title_he")}>
              <span className="cd-month-dot" aria-hidden />
              <span className="cd-req-name">{locOf(r, "family_he")}{r.borrower_he && r.family !== "purpose_proof" ? <span className="cd-faint"> · {locOf(r, "borrower_he")}</span> : null}</span>
              <span className="cd-req-state">{locOf(r, "ai_state_he")}{r.family === "payslip" ? <span className="ltr"> · {r.units}</span> : null}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------- focused review of one item

function ReviewMode({ ws, current, byId, onSelect, onOverview, reload, staff, readOnly, onToast }: {
  ws: Workspace; current: QueueItem; byId: Record<string, QueueItem>; onSelect: (id: string) => void; onOverview: () => void; reload: () => void;
  staff: string; readOnly: boolean; onToast: (t: ToastMsg) => void;
}) {
  const { t } = useLang();
  const [focus, setFocus] = useState<Focus | null>(null);
  useEffect(() => { setFocus(null); }, [current.id]);
  const order = useMemo(() => ws.groups.flatMap((g) => g.items).filter((id) => byId[id]), [ws.groups, byId]);
  const actionable = useMemo(() => groupItems(ws, [...YOURS, ...CUSTOMER]), [ws]);
  const move = useCallback((step: number) => {
    if (!order.length) return;
    const i = order.indexOf(current.id);
    onSelect(order[(i + step + order.length) % order.length]);
  }, [order, current.id, onSelect]);
  const nextActionable = useCallback(() => {
    const i = order.indexOf(current.id);
    const after = actionable.filter((id) => id !== current.id);
    const next = after.find((id) => order.indexOf(id) > i) || after[0];
    if (next) onSelect(next);
  }, [actionable, order, current.id, onSelect]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input, textarea, select, [contenteditable], [role=dialog]") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.code === "KeyJ") { e.preventDefault(); move(1); }
      if (e.code === "KeyK") { e.preventDefault(); move(-1); }
      if (e.code === "KeyN") { e.preventDefault(); nextActionable(); }
      if (e.key === "Escape") { e.preventDefault(); onOverview(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, nextActionable, onOverview]);
  const docItem = (id?: string | null) => ws.items.find((i): i is DocItem => i.kind === "document" && i.document_id === id);
  const showEvidence = (f: Focus) => {
    const target = docItem(f.documentId);
    if (target && target.id !== current.id && current.kind !== "case_finding") onSelect(target.id);
    setFocus(f);
  };
  const panel = <DecisionPanel key={current.id} item={current} ws={ws} staff={staff} readOnly={readOnly} focus={focus} solo={current.kind === "missing"}
    onDone={(text) => { onToast({ text, tone: "ok" }); reload(); }} onError={(text) => onToast({ text, tone: "bad" })}
    onNext={nextActionable} hasNext={actionable.some((id) => id !== current.id)} showEvidence={showEvidence} />;
  return (
    <div className="cd-review">
      <Navigator ws={ws} current={current} order={order} byId={byId} onSelect={onSelect} onOverview={onOverview} move={move} />
      {current.kind === "missing" ? (
        <div className="cd-solo-wrap" data-testid="evidence-pane">
          <div className="cd-solo cd-enter" key={current.id} data-testid="missing-evidence">
            <MissingHead item={current} ws={ws} />
            <div className="cd-solo-panel" data-testid="decision-panel">{panel}</div>
          </div>
        </div>
      ) : (
        <div className="cd-split">
          <section className="cd-canvas" aria-label={t("המסמך והראיות", "The document and the evidence")} data-testid="evidence-pane">
            {current.kind === "document" ? <DocumentEvidence key={current.id} item={current} focus={focus} setFocus={setFocus} onSelect={onSelect} ws={ws} />
              : <FindingEvidence key={current.id} item={current as CaseFindingItem} focus={focus} setFocus={setFocus} ws={ws} />}
          </section>
          <aside className="cd-inspector" aria-label={t("סיכום והחלטה", "Summary and decision")} data-testid="decision-panel">{panel}</aside>
        </div>
      )}
    </div>
  );
}

function MissingHead({ item, ws }: { item: MissingItem; ws: Workspace }) {
  const { en } = useLang();
  const borrower = ws.case.borrowers.find((b) => b.borrower_id === item.borrower_id);
  return (
    <header className="cd-solo-head">
      <span className="cd-thumb missing lg" aria-hidden><IDocs size={22} /></span>
      <h2 className="cd-solo-title" data-testid="missing-title">{en ? (item.period_he ? `No ${locOf(item, "period_he")} payslip received from ${borrower ? locOf(borrower, "name_he") : ""}`
        : `${locOf(item, "status_he")}: ${titleOf(item, ws)}`)
        : item.period_he ? `לא התקבל תלוש ${item.period_he} של ${borrower?.name_he || ""}` : `${item.status_he}: ${titleOf(item, ws)}`}</h2>
    </header>
  );
}

const TIER_LABEL: Record<Tier, [string, string]> = { yours: ["לטיפולך", "For you"], customer: ["אצל הלקוח", "With the customer"],
  processing: ["בבדיקת AI", "Being checked"], done: ["הושלם", "Done"] };

function Navigator({ ws, current, order, byId, onSelect, onOverview, move }: {
  ws: Workspace; current: QueueItem; order: string[]; byId: Record<string, QueueItem>; onSelect: (id: string) => void; onOverview: () => void;
  move: (step: number) => void;
}) {
  const { t } = useLang();
  const i = order.indexOf(current.id);
  const tier = tierOf(current.group);
  const sameTier = order.filter((id) => tierOf(byId[id].group) === tier);
  let lastTier: Tier | null = null;
  return (
    <nav className="cd-nav" aria-label={t("ניווט בין פריטי התיק", "Move between the case's items")} data-testid="review-queue">
      <button className="cd-back" onClick={onOverview} data-testid="back-to-case" title={t("חזרה לסקירת התיק (Esc)", "Back to the case overview (Esc)")}>
        <Chev dir="bwd" />{t("סקירת התיק", "Case overview")}</button>
      <div className="cd-nav-where" aria-live="polite">
        <span className={`cd-nav-tier t-${tier}`}>{t(...TIER_LABEL[tier])}</span>
        <span className="cd-nav-pos">{t(`${sameTier.indexOf(current.id) + 1} מתוך ${sameTier.length}`, `${sameTier.indexOf(current.id) + 1} of ${sameTier.length}`)}</span>
      </div>
      <div className="cd-dots" role="list" aria-label={t("כל הפריטים", "All items")}>
        {order.map((id) => {
          const it = byId[id];
          const tr2 = tierOf(it.group);
          const gap = lastTier !== null && tr2 !== lastTier;
          lastTier = tr2;
          return (
            <button key={id} role="listitem" className={`cd-dot t-${tr2} k-${it.kind}${id === current.id ? " on" : ""}${gap ? " gap" : ""}${it.attention ? " attn" : ""}`}
              onClick={() => onSelect(id)} title={`${titleOf(it, ws)} · ${statusOf(it).text}`} aria-label={titleOf(it, ws)} aria-current={id === current.id ? "true" : undefined}
              data-testid="nav-dot" data-item-id={id} />
          );
        })}
      </div>
      <div className="cd-stepper">
        <button onClick={() => move(-1)} aria-label={t("הפריט הקודם (K)", "Previous item (K)")} title={t("הקודם · K", "Previous · K")} data-testid="nav-prev"><Chev dir="bwd" /></button>
        <span className="ltr cd-stepper-count">{i + 1} / {order.length}</span>
        <button onClick={() => move(1)} aria-label={t("הפריט הבא (J)", "Next item (J)")} title={t("הבא · J", "Next · J")} data-testid="nav-next"><Chev dir="fwd" /></button>
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------- one sheet for every missing document

function RequestSheet({ ws, onClose, onDone }: { ws: Workspace; onClose: () => void; onDone: (text: string) => void }) {
  const { en, t } = useLang();
  const items = useMemo(() => requestableOf(ws), [ws]);
  const [picked, setPicked] = useState<Set<string>>(() => new Set(items.map((i) => i.id)));
  const [messages, setMessages] = useState<Record<string, string>>(() => Object.fromEntries(items.map((i) => [i.id, i.draft.message_he])));
  const [editing, setEditing] = useState<string | null>(null);
  const [rationale, setRationale] = useState("");
  const [step, setStep] = useState<"pick" | "preview">("pick");
  const [ids] = useState(() => Object.fromEntries(items.map((i) => [i.id, newRequestId()])));
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const sheet = useRef<HTMLDivElement>(null);
  useEffect(() => {
    sheet.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) { e.stopPropagation(); onClose(); } };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [busy, onClose]);
  const chosen = items.filter((i) => picked.has(i.id));
  const from = ws.case.banker.name_he;
  const cardTitle = (i: MissingItem) => {
    const b = ws.case.borrowers.find((x) => x.borrower_id === i.borrower_id);
    return i.period_he ? `נדרש תלוש ${i.period_he}, ${b?.first_name_he || ""}` : `נדרש: ${i.title_he}`;
  };
  const toggle = (id: string, on: boolean) => { const next = new Set(picked); if (on) next.add(id); else next.delete(id); setPicked(next); };
  const go = async () => {
    setBusy(true); setErrors([]);
    const failed: string[] = [];
    let ok = 0;
    for (const i of chosen) {
      const body = { customer_message: messages[i.id].trim(), rationale: rationale.trim(), request_id: ids[i.id] };
      try {
        const r: DeskResult = i.period
          ? await api.requestMissing(ws.case_id, { borrower_id: i.borrower_id!, period: i.period, ...body })
          : await api.requestRequirement(ws.case_id, i.requirement_code!, body);
        if (r) ok++;
      } catch (e) { failed.push(`${titleOf(i, ws)}: ${(e as Error).message}`); }
    }
    setBusy(false);
    if (failed.length) { setErrors(failed); return; }
    onDone(tr(`${ok} בקשות נשמרו ומוצגות ללקוח באפליקציה, כל מסמך עם כפתור העלאה משלו. לא נשלחה הודעת SMS, דוא״ל או התראה.`,
      `${ok} requests were saved and are shown to the customer in the app, each document with its own upload button. No SMS, email or notification was sent.`));
  };
  return (
    <div className="cd-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="cd-sheet" role="dialog" aria-modal="true" aria-labelledby="cd-sheet-title" ref={sheet} data-testid="request-sheet">
        <header className="cd-sheet-head">
          <div>
            <h2 id="cd-sheet-title">{step === "pick" ? t("בקשת מסמכים חסרים", "Request missing documents") : t("כך יופיעו הבקשות ללקוח", "How the requests will appear to the customer")}</h2>
            <p>{step === "pick" ? t("לכל מסמך נוצרת בקשה נפרדת עם ההודעה שלו. ההודעות נבנו מנתוני התיק, ואפשר לערוך כל אחת.",
              "Each document gets its own request with its own message. The messages are built from the case data, and you can edit each one.")
              : t("הבקשות יישמרו בתיק ויוצגו ללקוח באפליקציה. לא נשלחת הודעת SMS, דוא״ל או התראה.", "The requests will be saved in the case and shown to the customer in the app. No SMS, email or notification is sent.")}</p>
          </div>
          <button className="cd-icon-btn" onClick={onClose} disabled={busy} aria-label={t("סגירה", "Close")}>✕</button>
        </header>
        <div className="cd-sheet-body">
          {step === "pick" ? (<>
            <ul className="cd-pick">
              {items.map((i, n) => (
                <li key={i.id} className={picked.has(i.id) ? "on" : ""}>
                  <label className="cd-pick-row">
                    <input type="checkbox" checked={picked.has(i.id)} onChange={(e) => toggle(i.id, e.target.checked)} data-testid="request-pick" {...(n === 0 ? { "data-autofocus": true } : {})} />
                    <span className="cd-pick-main">
                      <span className="cd-pick-title">{titleOf(i, ws)}</span>
                      {editing !== i.id && <span className="cd-pick-msg" {...(en ? { dir: "rtl", lang: "he" } : {})}>{messages[i.id]}</span>}
                    </span>
                  </label>
                  {editing === i.id ? (
                    <div className="cd-pick-edit">
                      <textarea className="cd-input" value={messages[i.id]} maxLength={600} onChange={(e) => setMessages({ ...messages, [i.id]: e.target.value })} dir="rtl" lang="he" autoFocus />
                      <div className="cd-pick-edit-foot"><span className="ltr cd-faint">{messages[i.id].length}/600</span>
                        <button className="cd-btn cd-btn-plain cd-btn-sm" onClick={() => setEditing(null)}>{t("סיום עריכה", "Done editing")}</button></div>
                    </div>
                  ) : <button className="cd-link" onClick={() => setEditing(i.id)}>{t("עריכת ההודעה", "Edit message")}</button>}
                </li>
              ))}
            </ul>
            <label className="cd-field">{t("נימוק פנימי", "Internal rationale")} <span className="cd-faint">{t("(לא מוצג ללקוח, רשות)", "(not shown to the customer, optional)")}</span>
              <textarea className="cd-input" value={rationale} onChange={(e) => setRationale(e.target.value)} {...(en ? { dir: "auto" } : {})} /></label>
          </>) : (
            <div className="cd-previews">
              {chosen.map((i) => (
                <div key={i.id} className="req-preview-card" dir="rtl" lang="he">
                  <div className="req-preview-from">בקשה מ{from}</div>
                  <div className="bold">{cardTitle(i)}</div>
                  <p className="small">{messages[i.id].trim()}</p>
                  <span className="req-preview-btn">להעלאת המסמך</span>
                </div>
              ))}
            </div>
          )}
          {errors.length > 0 && <div className="dp-err" role="alert">{errors.map((e) => <div key={e}>{e}</div>)}</div>}
        </div>
        <footer className="cd-sheet-foot">
          {step === "pick" ? (<>
            <button className="cd-btn cd-btn-primary" disabled={!chosen.length || chosen.some((i) => !messages[i.id].trim())} onClick={() => setStep("preview")} data-testid="request-preview">
              {t("המשך לתצוגה מקדימה", "Continue to preview")}</button>
            <span className="cd-faint">{t(`${chosen.length} מתוך ${items.length} נבחרו`, `${chosen.length} of ${items.length} selected`)}</span>
          </>) : (<>
            <button className="cd-btn cd-btn-customer" disabled={busy} onClick={go} data-testid="send-requests">{busy && <span className="spinner" />}
              {t(`שמירה והצגה ללקוח באפליקציה (${chosen.length})`, `Save and show to the customer in the app (${chosen.length})`)}</button>
            <button className="cd-btn cd-btn-plain" disabled={busy} onClick={() => setStep("pick")}>{t("חזרה לעריכה", "Back to editing")}</button>
          </>)}
        </footer>
      </div>
    </div>
  );
}

