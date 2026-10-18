import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api, type CaseChatReply, type DemoLetter, type IntelDraft } from "../../api";
import { locList, locOf, tr, useLang } from "../../i18n";
import { LetterBody, LetterSheet } from "./BankLetter";
import { MARK, markOf, type Ctx } from "./IntelligenceV2";
import "./replyworkspace.css";

type Toast = (t: { text: string; tone: "ok" | "bad" }) => void;
interface Msg {
  id: number; role: "user" | "model"; text: string; intent?: CaseChatReply["intent"]; sources?: CaseChatReply["sources"];
  issues?: string[]; error?: boolean;
  /** applied: the editor took the revision · stale: the draft changed while JEEN worked, so it waits for the banker */
  edit?: { kind: string; text: string; summary_he: string; state: "applied" | "stale" | "undone" };
}
interface AiChange { kind: string; before: string; after: string; msgId: number }
type DemoState = { status: "idle" | "loading" | "ready" | "error"; letter?: DemoLetter; error?: string };

const DEMO = "demo_approval";
/** Tab labels: short enough for one row of three. */
const TAB: Record<string, string> = { complete_documentation: "אישור מסמכים", conditional_financing: "שיחת המשך",
  financial_clarification: "בקשת הבהרה", missing_documents: "השלמת מסמכים", [DEMO]: "אישור הלוואה" };
/** The document type on the letterhead. */
const DOC: Record<string, string> = { complete_documentation: "אישור קבלת מסמכים", conditional_financing: "חלופות פריסה להמחשה",
  financial_clarification: "בקשת הבהרה", missing_documents: "בקשת השלמת מסמכים", [DEMO]: "אישור בקשת הלוואה" };
const TAB_EN: Record<string, string> = { complete_documentation: "Documents confirmed", conditional_financing: "Follow-up call",
  financial_clarification: "Clarification", missing_documents: "Missing documents", [DEMO]: "Loan approval" };
const DOC_EN: Record<string, string> = { complete_documentation: "Confirmation of documents received", conditional_financing: "Illustrative repayment options",
  financial_clarification: "Request for clarification", missing_documents: "Request for missing documents", [DEMO]: "Loan application approval" };
const COPY_MARK = "[מסמך הדמיה (DEMO), אינו החלטת אשראי של הבנק ואינו הסכם הלוואה. לא נשלח ללקוח.]";
const READY = ["READY_FOR_CREDIT_REVIEW", "PREPARATION_CONFIRMED"];
const CHIPS_READY = ["למה מומלץ להתקדם?", "מה עדיין צריך לבדוק?", "תנסח את המכתב יותר פורמלי", "תקצר את המענה"];
const CHIPS_OTHER = ["מה ההמלצה ולמה?", "מה עדיין צריך לבדוק?", "תנסח את המכתב יותר פורמלי", "תקצר את המענה"];
const CHIPS_DEMO = ["מה השלב הבא אצל הלקוחה?", "מה עדיין צריך לבדוק?", "תוסיף הסבר על תנאי ההחזר", "תקצר את הפתיחה"];
const CHIPS_READY_EN = ["Why is it recommended to proceed?", "What still needs checking?", "Make the letter more formal", "Shorten the reply"];
const CHIPS_OTHER_EN = ["What's the recommendation, and why?", "What still needs checking?", "Make the letter more formal", "Shorten the reply"];
const CHIPS_DEMO_EN = ["What's the customer's next step?", "What still needs checking?", "Add an explanation of the repayment terms", "Shorten the opening"];
/** The document workspace's rewrite actions: a short label and the instruction JEEN receives. */
const REWRITES: [string, string][] = [["רשמי יותר", "תנסח את המכתב בצורה רשמית יותר"], ["קצר יותר", "תקצר את המכתב ושמור על כל המידע החשוב"],
  ["חם ואישי", "תנסח את המכתב בטון חם ואישי יותר"], ["פשוט וברור", "תפשט את הניסוח כך שיהיה ברור ללקוח"]];
const REWRITE_DEMO: [string, string] = ["הסבר על ההחזר", "תוסיף פסקה קצרה שמסבירה ללקוח את תנאי ההחזר"];
const REWRITES_EN: [string, string][] = [["More formal", "Rewrite the letter in a more formal style"], ["Shorter", "Shorten the letter and keep all the important information"],
  ["Warm and personal", "Rewrite the letter in a warmer, more personal tone"], ["Plain and clear", "Simplify the wording so it's clear to the customer"]];
const REWRITE_DEMO_EN: [string, string] = ["Explain repayment", "Add a short paragraph that explains the repayment terms to the customer"];

/** Banker V3 "מענה מוצע ללקוח": a compact preview of the selected reply beside the JEEN assistant, and a document
 *  workspace (modal) for editing it with a rewrite bar. One draft state behind all three surfaces: JEEN's revisions —
 *  already checked by the server — are applied only if the draft did not change meanwhile. Mount with key={case_id}: a
 *  case switch drops the conversation, the drafts and any request in flight. Nothing is sent to the customer. */
export function ReplyWorkspace({ ctx, onToast }: { ctx: Ctx; onToast: Toast }) {
  const { x } = ctx;
  const { en, t } = useLang();
  const [kind, setKind] = useState<string | null>(x.recommended_draft);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [refs, setRefs] = useState<Record<string, boolean>>({});
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [lastAi, setLastAi] = useState<AiChange | null>(null);
  const [flash, setFlash] = useState(0);
  const [pane, setPane] = useState<"draft" | "chat">("draft");
  const [open, setOpen] = useState(false);
  const [demo, setDemo] = useState<DemoState>({ status: "idle" });
  const demoRef = useRef(demo);
  demoRef.current = demo;
  const demoCall = useRef<AbortController | null>(null);
  const textsRef = useRef(texts);
  textsRef.current = texts;
  const inflight = useRef<AbortController | null>(null);
  const seq = useRef(0);
  useEffect(() => () => { inflight.current?.abort(); demoCall.current?.abort(); }, []);

  const ready = READY.includes(x.recommendation.state);
  const tabs: IntelDraft[] = x.simulation.enabled
    ? [...x.drafts, { kind: DEMO, title_he: "אישור הלוואה", message_he: demo.letter?.text ?? "", attachments: [] }] : x.drafts;
  const draft = tabs.find((d) => d.kind === kind) || tabs[0] || null;
  const isDemo = draft?.kind === DEMO;
  const demoPending = isDemo && !demo.letter;
  const templateOf = (k: string) => (k === DEMO ? demoRef.current.letter?.text ?? "" : x.drafts.find((d) => d.kind === k)?.message_he ?? "");
  const textOf = (k: string) => textsRef.current[k] ?? templateOf(k);
  const text = draft ? texts[draft.kind] ?? draft.message_he : "";
  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(0), 2400);
    return () => window.clearTimeout(t);
  }, [flash]);

  const setText = (k: string, v: string) => setTexts((prev) => ({ ...prev, [k]: v }));
  const applyEdit = (e: { kind: string; text: string }, before: string, msgId: number) => {
    setText(e.kind, e.text);
    setLastAi({ kind: e.kind, before, after: e.text, msgId });
    setKind(e.kind);
    setFlash(Date.now());
  };
  const patchMsg = (id: number, f: (m: Msg) => Msg) => setMsgs((prev) => prev.map((m) => (m.id === id ? f(m) : m)));

  const makeLetter = async (acknowledge: boolean, useAi = true) => {
    demoCall.current?.abort();
    const ctl = new AbortController();
    demoCall.current = ctl;
    setDemo((d) => ({ ...d, status: "loading", error: undefined }));
    try {
      const letter = await api.bankerDemoLetter(x.case_id, { acknowledge_open_issues: acknowledge, use_ai: useAi }, ctl.signal);
      if (ctl.signal.aborted) return;
      setTexts((prev) => { const next = { ...prev }; delete next[DEMO]; return next; });
      setLastAi((l) => (l?.kind === DEMO ? null : l));
      setDemo({ status: "ready", letter });
    } catch (e) {
      if (ctl.signal.aborted) return;
      setDemo((d) => ({ ...d, status: d.letter ? "ready" : "error", error: e instanceof Error && e.message ? e.message : tr("Jeen לא הצליח להכין את המכתב כרגע.", "Jeen couldn't prepare the letter right now.") }));
    }
  };
  useEffect(() => {
    if (isDemo && ready && demo.status === "idle") void makeLetter(false);
  }, [isDemo, ready, demo.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const regenerate = () => {
    if (!demo.letter) return;
    const changed = texts[DEMO] != null && texts[DEMO] !== demo.letter.text;
    if (changed && !window.confirm(t("הכנה מחדש תחליף את המכתב הנוכחי, כולל השינויים שלך ושל Jeen. להמשיך?", "Preparing it again will replace the current letter, including your changes and Jeen's. Continue?"))) return;
    void makeLetter(!ready);
  };

  const ask = async (message: string, prior: Msg[]) => {
    const q = message.trim();
    if (!q || busy) return;
    const sentKind = draft && !(draft.kind === DEMO && !demoRef.current.letter) ? draft.kind : null;
    const sentText = sentKind ? textOf(sentKind) : "";
    const history = prior.filter((m) => !m.error).slice(-12).map((m) => ({
      role: m.role, text: m.role === "model" && m.edit?.state === "applied" ? `${m.text}\n[עדכנתי את הטיוטה: ${m.edit.summary_he}]` : m.text }));
    setMsgs([...prior, { id: ++seq.current, role: "user", text: q }]);
    setBusy(true);
    const ctl = new AbortController();
    inflight.current = ctl;
    try {
      const r = await api.bankerChat(x.case_id, { message: q, history, draft: sentKind ? { kind: sentKind, text: sentText } : null }, ctl.signal);
      if (ctl.signal.aborted) return;
      const id = ++seq.current;
      let edit: Msg["edit"];
      if (r.edit) {
        const fresh = textOf(r.edit.kind) === sentText;
        edit = { ...r.edit, state: fresh ? "applied" : "stale" };
        if (fresh) applyEdit(r.edit, sentText, id);
      }
      setMsgs((prev) => [...prev, { id, role: "model", text: locOf(r, "answer_he"), intent: r.intent, sources: r.sources, issues: locList(r, "rejected_issues_he"), edit }]);
    } catch (e) {
      if (ctl.signal.aborted) return;
      setMsgs((prev) => [...prev, { id: ++seq.current, role: "model", error: true,
        text: e instanceof Error && e.message && !/^\d+$/.test(e.message) ? e.message : tr("Jeen לא הצליח לענות כרגע. הטיוטה לא השתנתה.", "Jeen couldn't answer right now. The draft didn't change.") }]);
    } finally {
      if (inflight.current === ctl) { inflight.current = null; setBusy(false); }
    }
  };
  const retry = (errId: number) => {
    const i = msgs.findIndex((m) => m.id === errId);
    const user = msgs[i - 1];
    if (!user || user.role !== "user") return;
    void ask(user.text, msgs.slice(0, i - 1));
  };
  const undo = () => {
    if (!lastAi) return;
    const now = textOf(lastAi.kind);
    if (now !== lastAi.after && !window.confirm(t("ביטול השינוי של Jeen יחזיר את הנוסח שלפניו, ויבטל גם עריכות שעשית אחריו. להמשיך?",
      "Undoing Jeen's change restores the wording before it, and also undoes edits you made after it. Continue?"))) return;
    setText(lastAi.kind, lastAi.before);
    patchMsg(lastAi.msgId, (m) => (m.edit ? { ...m, edit: { ...m.edit, state: "undone" } } : m));
    setLastAi(null);
    onToast({ text: t("השינוי האחרון של Jeen בוטל.", "Jeen's last change was undone."), tone: "ok" });
  };
  const applyStale = (m: Msg) => {
    if (!m.edit) return;
    if (!window.confirm(t("הטיוטה השתנתה מאז ששאלת. החלת ההצעה של Jeen תחליף את הנוסח הנוכחי. להמשיך?",
      "The draft changed since you asked. Applying Jeen's suggestion will replace the current wording. Continue?"))) return;
    applyEdit(m.edit, textOf(m.edit.kind), m.id);
    patchMsg(m.id, (p) => (p.edit ? { ...p, edit: { ...p.edit, state: "applied" } } : p));
  };

  const edited = !!draft && !demoPending && texts[draft.kind] != null && texts[draft.kind] !== draft.message_he;
  const byJeen = !!draft && lastAi?.kind === draft.kind && text === lastAi.after;
  const canUndo = !!draft && lastAi?.kind === draft.kind;
  const restore = () => {
    if (!draft) return;
    if (!window.confirm(t("שחזור הנוסח המקורי ימחק את השינויים בטיוטה, שלך ושל Jeen. להמשיך?", "Restoring the original wording will erase the changes to the draft, yours and Jeen's. Continue?"))) return;
    setText(draft.kind, draft.message_he);
    if (lastAi?.kind === draft.kind) setLastAi(null);
  };
  const chosen = draft ? draft.attachments.filter((a) => refs[`${draft.kind}:${a.document_id}`]) : [];
  const body = chosen.length ? `${text}\n\nמסמכים בתיק שההודעה מתייחסת אליהם: ${chosen.map((a) => a.label_he).join(" · ")}` : text;
  const full = isDemo ? `${COPY_MARK}\n\n${body}\n\n${COPY_MARK}` : body;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(full);
      onToast({ text: t("המענה הועתק. הוא לא נשלח ללקוח, השליחה נעשית בערוץ הבנק.", "The reply was copied. It wasn't sent to the customer — sending is done through the bank's channel."), tone: "ok" });
    } catch {
      onToast({ text: t("ההעתקה נחסמה בדפדפן. אפשר לסמן את הטקסט ולהעתיק ידנית.", "The browser blocked copying. You can select the text and copy it manually."), tone: "bad" });
    }
  };
  const status = byJeen ? <span className="rw-chip-ai" data-testid="cc-draft-ai">{t("עודכן על ידי Jeen", "Updated by Jeen")}</span>
    : edited ? <span className="rw-chip-ed" data-testid="cc-draft-edited">{t("נערך", "Edited")}</span> : null;
  const tabTitle = (d: IntelDraft) => (d.kind === DEMO ? t("אישור הלוואה", "Loan approval") : locOf(d, "title_he"));
  const tabRow = (
    <div className="rw-tabs" role="tablist" aria-label={t("סוג המענה", "Reply type")} style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}>
      {tabs.map((d) => (
        <button key={d.kind} role="tab" aria-selected={d.kind === draft?.kind} className={d.kind === draft?.kind ? "on" : ""} onClick={() => setKind(d.kind)}
          data-testid="cc-draft-tab" data-kind={d.kind} title={tabTitle(d)}>
          <span className="rw-tab-l">{(en ? TAB_EN : TAB)[d.kind] || tabTitle(d)}</span>
          {d.kind === x.recommended_draft && <span className="rw-tab-rec" title={t("מומלץ למצב התיק", "Recommended for the case's state")}>{t("מומלץ", "Recommended")}</span>}
          {texts[d.kind] != null && texts[d.kind] !== d.message_he && <span className="rw-tab-dot" title={t("נערך", "Edited")} aria-label={t("נערך", "Edited")} />}
        </button>
      ))}
    </div>
  );

  return (
    <section className="cc-card rw" id="cc-reply" data-testid="cc-reply">
      <header className="cc-card-head rw-head">
        <div><h2>{t("מענה מוצע ללקוח", "Suggested reply to the customer")}</h2><p className="cc-sub">{t("טיוטה מוכנה לפי מצב התיק. עורכים ידנית או עם Jeen, שום דבר לא נשלח מכאן.",
          "A draft prepared from the case's state, in the customer's language (Hebrew). Edit it yourself or with Jeen — nothing is sent from here.")}</p></div>
        <div className="rw-switch" role="tablist" aria-label={t("תצוגה", "View")} data-testid="cc-pane-switch">
          <button role="tab" aria-selected={pane === "draft"} className={pane === "draft" ? "on" : ""} onClick={() => setPane("draft")} data-testid="cc-pane-draft">{t("טיוטה", "Draft")}</button>
          <button role="tab" aria-selected={pane === "chat"} className={pane === "chat" ? "on" : ""} onClick={() => setPane("chat")} data-testid="cc-pane-chat">
            <img className="rw-switch-mark" src="/brand/jeen-mark.svg" alt="" />Jeen{busy && <span className="rw-dot" aria-hidden />}</button>
        </div>
      </header>
      <div className={`cc-card-body rw-grid pane-${pane}`}>
        <div className="rw-draft" data-testid="cc-draft-col">
          {!draft ? <div className="cc-empty">{t("אין טיוטה מתאימה למצב התיק כרגע. אפשר עדיין לשאול את Jeen על התיק.", "There's no draft that fits the case's state right now. You can still ask Jeen about the case.")}</div> : <>
            {tabs.length > 1 && tabRow}
            <div className={`rw-doc${flash && byJeen ? " rw-flash" : ""}`}>
              {demoPending ? <DemoGate demo={demo} ready={ready} onMake={(ack, ai) => void makeLetter(ack, ai)} />
                : <Preview text={text} kind={draft.kind} demo={isDemo} onOpen={() => setOpen(true)} />}
            </div>
            <div className="rw-foot">
              <div className="rw-foot-meta">
                {status}
                {isDemo && demo.letter && <LetterMeta demo={demo} onRegenerate={regenerate} />}
                {canUndo && <button className="cc-link" onClick={undo} data-testid="cc-draft-undo">{t("בטל שינוי של Jeen", "Undo Jeen's change")}</button>}
                {chosen.length > 0 && <span className="cc-muted">{en ? (chosen.length === 1 ? "One document attached" : `${chosen.length} documents attached`)
                  : chosen.length === 1 ? "מסמך אחד מצורף" : `${chosen.length} מסמכים מצורפים`}</span>}
              </div>
              <div className="rw-foot-acts">
                <button className="rw-btn" onClick={copy} disabled={demoPending} data-testid="cc-draft-copy">{t("העתקה", "Copy")}</button>
                <button className="rw-btn primary" onClick={() => setOpen(true)} disabled={demoPending} data-testid="cc-draft-open">{t("פתיחה לעריכה", "Open for editing")}</button>
              </div>
            </div>
          </>}
        </div>

        <JeenPanel ctx={ctx} msgs={msgs} busy={busy} lastAiId={lastAi?.msgId} onAsk={(q) => void ask(q, msgs)} onUndo={undo}
          onApply={applyStale} onRetry={retry} chips={en ? (isDemo && demo.letter ? CHIPS_DEMO_EN : ready ? CHIPS_READY_EN : CHIPS_OTHER_EN)
            : isDemo && demo.letter ? CHIPS_DEMO : ready ? CHIPS_READY : CHIPS_OTHER} />
      </div>

      {open && draft && !demoPending && (
        <DocModal title={tabTitle(draft)} docType={(en ? DOC_EN : DOC)[draft.kind] || tabTitle(draft)} demo={isDemo}
          customer={en ? x.applicant.borrowers.map((b) => locOf(b, "name_he")).join(" & ") : x.applicant.borrowers.map((b) => b.name_he).join(" ו")} tabs={tabRow} status={status}
          text={text} onText={(v) => setText(draft.kind, v)} flash={!!flash && byJeen} onClose={() => setOpen(false)}
          actions={<>
            {canUndo && <button className="cc-link" onClick={undo} data-testid="cc-modal-undo">{t("בטל שינוי של Jeen", "Undo Jeen's change")}</button>}
            <button className="cc-link" disabled={!edited} onClick={restore} data-testid="cc-draft-restore">{t("שחזור הנוסח", "Restore the wording")}</button>
            <button className="rw-btn" onClick={copy} data-testid="cc-modal-copy">{t("העתקה", "Copy")}</button>
          </>}
          refs={draft.attachments.length > 0 && <div className="rw-refs">
            <span className="rw-refs-k">{t("הפניה למסמכים בתיק (רשות)", "Refer to documents in the case (optional)")}</span>
            {draft.attachments.map((a) => {
              const k = `${draft.kind}:${a.document_id}`;
              return <label key={k} className={`cc-ref${refs[k] ? " on" : ""}`}><input type="checkbox" checked={!!refs[k]} onChange={() => setRefs({ ...refs, [k]: !refs[k] })} />{locOf(a, "label_he")}</label>;
            })}
          </div>}
          rewrite={<RewriteBar msgs={msgs} busy={busy} demo={isDemo} canUndo={canUndo} onUndo={undo} onAsk={(q) => void ask(q, msgs)} />} />
      )}
    </section>
  );
}

// ---------------------------------------------------------------- the compact preview
function Preview({ text, kind, demo, onOpen }: { text: string; kind: string; demo: boolean; onOpen: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [clipped, setClipped] = useState(false);
  const { en, t } = useLang();
  useLayoutEffect(() => {
    const el = box.current;
    if (el) setClipped(el.scrollHeight > el.clientHeight + 2);
  }, [text]);
  return (
    <div className={`rw-prev${clipped ? " clipped" : ""}`}>
      <div ref={box} className="rw-prev-desk" data-testid="cc-draft-preview" data-kind={kind} data-text={text} onClick={onOpen} dir="rtl"
        title={t("פתיחה לעריכה", "Open for editing")}>
        <LetterSheet docType={(en ? DOC_EN : DOC)[kind] || ""} demo={demo} compact><LetterBody text={text} /></LetterSheet>
      </div>
      {clipped && <button className="rw-prev-more" onClick={onOpen} data-testid="cc-draft-more">{t("הצגת המסמך המלא", "Show the full document")}</button>}
    </div>
  );
}

/** Where the loan letter's wording came from, its regeneration, and what is still open on the real case. */
function LetterMeta({ demo, onRegenerate }: { demo: DemoState; onRegenerate: () => void }) {
  const l = demo.letter!;
  const { en, t } = useLang();
  const issues = locList(l, "open_issues_he");
  return <>
    <span className={l.source === "ai" ? "rw-src-ai" : "rw-src-base"} data-testid="cc-demo-source" data-source={l.source}>
      {l.source === "ai" ? t("נוסח על ידי Jeen · הסכומים מחושבים במערכת", "Worded by Jeen · amounts computed by the system") : t("נוסח בסיס קבוע (ללא AI)", "Fixed base wording (no AI)")}</span>
    <button className="cc-link" onClick={onRegenerate} disabled={demo.status === "loading"} data-testid="cc-demo-regenerate">
      {demo.status === "loading" ? t("מכין…", "Preparing…") : t("ניסוח מחדש", "Reword")}</button>
    {l.open_issues_he.length > 0 && <details className="rw-issues" data-testid="cc-demo-issues">
      <summary>{en ? (l.open_issues_he.length === 1 ? "One open item in the case" : `${l.open_issues_he.length} open items in the case`)
        : l.open_issues_he.length === 1 ? "פריט פתוח אחד בתיק" : `${l.open_issues_he.length} פריטים פתוחים בתיק`}</summary>
      <ul>{issues.map((t, i) => <li key={i}>{t}</li>)}</ul></details>}
  </>;
}

function DemoGate({ demo, ready, onMake }: { demo: DemoState; ready: boolean; onMake: (acknowledge: boolean, useAi: boolean) => void }) {
  const { en, t } = useLang();
  if (demo.status === "loading") return (
    <div className="rw-gate" data-testid="cc-demo-loading"><span className="rw-gate-mark" aria-hidden><img src="/brand/jeen-mark.svg" alt="" /></span>
      <b>{t("Jeen מכין את מכתב האישור", "Jeen is preparing the approval letter")}</b><span className="cc-muted">{t("מנסח מנתוני התיק; הסכומים מחושבים במערכת.", "Worded from the case data; the amounts are computed by the system.")}</span><span className="rw-bar" aria-hidden /></div>);
  return (
    <div className="rw-gate" data-testid="cc-demo-gate">
      {demo.status === "error" ? <p className="rw-gate-err" data-testid="cc-demo-error">{demo.error}</p>
        : !ready ? (en ? <p><b>The case isn't ready for credit review yet.</b><br />You can prepare an approval letter anyway: the open items stay in the case, and the letter will include a condition to complete them.</p>
          : <p><b>התיק עדיין אינו מוכן לבחינת אשראי.</b><br />אפשר להכין מכתב אישור בכל זאת: הפריטים הפתוחים יישארו בתיק, והמכתב יכלול תנאי להשלמתם.</p>)
          : <p>{t("מכתב אישור מפורט עם עיקרי התנאים, מנוסח על ידי Jeen מנתוני התיק.", "A detailed approval letter with the main terms, worded by Jeen from the case data.")}</p>}
      <div className="rw-gate-acts">
        <button className="rw-btn primary" onClick={() => onMake(!ready, true)} data-testid="cc-demo-make">
          {demo.status === "error" ? t("ניסיון חוזר", "Try again") : ready ? t("הכנת מכתב האישור", "Prepare the approval letter") : t("הכנת מכתב אישור בכל זאת", "Prepare an approval letter anyway")}</button>
        {demo.status === "error" && <button className="rw-btn" onClick={() => onMake(!ready, false)} data-testid="cc-demo-base">{t("נוסח בסיס (ללא AI)", "Base wording (no AI)")}</button>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- JEEN assistant panel
function JeenPanel({ ctx, msgs, busy, lastAiId, chips, onAsk, onUndo, onApply, onRetry }: {
  ctx: Ctx; msgs: Msg[]; busy: boolean; lastAiId?: number; chips: string[]; onAsk: (q: string) => void; onUndo: () => void;
  onApply: (m: Msg) => void; onRetry: (id: number) => void }) {
  const [input, setInput] = useState("");
  const { en, t } = useLang();
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [msgs.length, busy]);
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || busy) return;
    onAsk(input);
    setInput("");
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
  };
  return (
    <aside className="rw-chat jn" data-testid="cc-chat" aria-label={t("שאל את Jeen", "Ask Jeen")}>
      <span className="jn-strip" aria-hidden><i /><i /><i /></span>
      <header className="jn-head" data-testid="cc-chat-head">
        <h3 className="jn-title">{t("שאל את", "Ask")}<img className="jn-logo" src="/brand/jeen-logo.svg" alt="Jeen" /></h3>
        <p className="jn-sub">{t("עוזר AI שמכיר את הבקשה, המסמכים והניתוח הפיננסי", "An AI assistant that knows the application, the documents and the financial analysis")}</p>
      </header>
      <div className="rw-log" ref={log} aria-live="polite" data-testid="cc-chat-log">
        {msgs.length === 0 && <div className="jn-intro">
          <p>{t("שאלו על התיק, או בקשו שינוי בטיוטה שמימין.", "Ask about the case, or request a change to the draft on the left.")}</p>
          <div className="rw-chips">{chips.map((c) => (
            <button key={c} className="rw-chip" onClick={() => onAsk(c)} disabled={busy} data-testid="cc-chat-chip">{c}</button>))}</div>
        </div>}
        {msgs.map((m) => <Bubble key={m.id} m={m} ctx={ctx} latest={lastAiId === m.id} onUndo={onUndo} onApply={() => onApply(m)} onRetry={() => onRetry(m.id)} busy={busy} />)}
        {busy && <div className="rw-msg m-model pending" data-testid="cc-chat-pending"><span className="jn-typing" aria-hidden><i /><i /><i /></span> {t("Jeen בודק בתיק", "Jeen is checking the case")}</div>}
      </div>
      <form className="jn-compose" onSubmit={submit}>
        <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={2} dir={en ? "auto" : "rtl"} maxLength={2000}
          placeholder={busy ? t("Jeen עונה…", "Jeen is answering…") : t("שאלה על התיק או בקשה לשינוי במכתב", "A question about the case, or a change to the letter")} disabled={busy} aria-label={t("הודעה ל־Jeen", "Message to Jeen")} data-testid="cc-chat-input" />
        <button type="submit" className="jn-send" disabled={busy || !input.trim()} data-testid="cc-chat-send" aria-label={t("שליחה ל־Jeen", "Send to Jeen")}>
          <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden><path d="M16 10H4m0 0 5-5m-5 5 5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </form>
      <p className="jn-foot">{t("עונה מנתוני התיק בלבד ואינו משנה את התיק", "Answers from the case data only, and doesn't change the case")}</p>
    </aside>
  );
}

function Bubble({ m, ctx, latest, onUndo, onApply, onRetry, busy }: { m: Msg; ctx: Ctx; latest: boolean; onUndo: () => void; onApply: () => void; onRetry: () => void; busy: boolean }) {
  const { t } = useLang();
  if (m.role === "user") return <div className="rw-msg m-user" data-testid="cc-chat-msg" data-role="user">{m.text}</div>;
  const ids = Object.keys(m.sources || {});
  return (
    <div className={`rw-msg m-model${m.error ? " err" : ""}`} data-testid="cc-chat-msg" data-role="model" data-intent={m.intent || (m.error ? "error" : "")}>
      <div className="rw-text">{m.text}</div>
      <EditState m={m} latest={latest} onUndo={onUndo} onApply={onApply} />
      {ids.length > 0 && <div className="rw-srcs">{ids.map((id) => {
        const s = ctx.x.sources[id];
        const k = s ? markOf(s) : "missing";
        return <button key={id} className={`rw-src k-${k}`} onClick={() => ctx.open(id)} disabled={!s} title={MARK[k].title} data-testid="cc-chat-source" data-source={id}>
          <span className="rw-src-k">{MARK[k].label}</span>{locOf(m.sources![id], "label_he")}</button>;
      })}</div>}
      {m.error && <button className="cc-link" onClick={onRetry} disabled={busy} data-testid="cc-chat-retry">{t("ניסיון חוזר", "Try again")}</button>}
    </div>
  );
}

function EditState({ m, latest, onUndo, onApply }: { m: Msg; latest: boolean; onUndo: () => void; onApply?: () => void }) {
  const { t } = useLang();
  if (m.edit) return (
    <div className={`rw-edit s-${m.edit.state}`} data-testid="cc-chat-edit" data-state={m.edit.state}>
      {m.edit.state === "applied" && <><span>{t("✓ הטיוטה עודכנה", "✓ The draft was updated")}</span>{latest && <button className="cc-link" onClick={onUndo} data-testid="cc-chat-undo">{t("בטל שינוי", "Undo change")}</button>}</>}
      {m.edit.state === "undone" && <span>{t("השינוי בוטל", "The change was undone")}</span>}
      {m.edit.state === "stale" && <><span>{t("הטיוטה השתנתה בזמן שעבדתי, ולכן לא החלפתי אותה.", "The draft changed while I was working, so I didn't replace it.")}</span>
        {onApply && <button className="cc-link" onClick={onApply} data-testid="cc-chat-apply">{t("החלה בכל זאת", "Apply anyway")}</button>}</>}
    </div>);
  if ((m.intent === "draft_edit" || m.intent === "question_and_edit" || m.intent === "declined") && (m.issues?.length || m.intent === "declined"))
    return <div className="rw-edit s-kept" data-testid="cc-chat-kept">{t("הטיוטה לא השתנתה", "The draft didn't change")}</div>;
  return null;
}

// ---------------------------------------------------------------- the document workspace
function DocModal({ title, docType, demo, customer, tabs, status, text, onText, flash, onClose, actions, refs, rewrite }: {
  title: string; docType: string; demo: boolean; customer: string; tabs: ReactNode; status: ReactNode; text: string; onText: (v: string) => void;
  flash: boolean; onClose: () => void; actions: ReactNode; refs: ReactNode; rewrite: ReactNode }) {
  const area = useRef<HTMLTextAreaElement>(null);
  const [mode, setMode] = useState<"edit" | "view">("edit");
  const { en, t } = useLang();
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [text, mode]);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") close.current(); };
    window.addEventListener("keydown", onKey);
    const root = document.documentElement, prev = root.style.overflow;
    root.style.overflow = "hidden";
    area.current?.focus({ preventScroll: true });
    area.current?.setSelectionRange(0, 0);
    return () => { window.removeEventListener("keydown", onKey); root.style.overflow = prev; };
  }, []);
  return createPortal(
    <div className="rw-modal-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="rw-modal" role="dialog" aria-modal="true" aria-label={en ? `Editing ${title}` : `עריכת ${title}`} data-testid="cc-doc-modal">
        <header className="rw-modal-head">
          <div className="rw-modal-t">
            <span className="rw-modal-k">{t("מענה ללקוח", "Reply to the customer")} · {customer}</span>
            <h3>{title}</h3>
          </div>
          <div className="rw-modal-tabs">{tabs}</div>
          <button className="rw-x" onClick={onClose} aria-label={t("סגירה", "Close")} data-testid="cc-doc-close">×</button>
        </header>
        <div className="rw-modal-tools">
          <div className="rw-mode" role="tablist" aria-label={t("תצוגה", "View")} data-testid="cc-doc-mode">
            <button role="tab" aria-selected={mode === "edit"} className={mode === "edit" ? "on" : ""} onClick={() => setMode("edit")} data-testid="cc-doc-mode-edit">{t("עריכה", "Edit")}</button>
            <button role="tab" aria-selected={mode === "view"} className={mode === "view" ? "on" : ""} onClick={() => setMode("view")} data-testid="cc-doc-mode-view">{t("תצוגת מכתב", "Letter view")}</button>
          </div>
          {status}<span className="rw-modal-acts">{actions}</span>
        </div>
        <div className="rw-modal-body">
          <div className={`rw-sheet${flash ? " rw-flash" : ""}${mode === "edit" ? " editing" : ""}`}>
            <LetterSheet docType={docType} demo={demo}>
              {mode === "edit"
                ? <textarea ref={area} className="bl-edit" value={text} onChange={(e) => onText(e.target.value)} dir="rtl"
                  data-testid="cc-draft-text" aria-label={t("טיוטת המענה ללקוח", "Draft reply to the customer")} />
                : <div className="rw-view" onClick={() => setMode("edit")} title={t("לחיצה לעריכה", "Click to edit")} data-testid="cc-doc-view"><LetterBody text={text} /></div>}
            </LetterSheet>
          </div>
          {refs}
        </div>
        {rewrite}
      </div>
    </div>, document.body);
}

/** Purpose-built for the document: rewrite actions, the latest exchange and an instruction field — the same conversation as the panel. */
function RewriteBar({ msgs, busy, demo, canUndo, onUndo, onAsk }: { msgs: Msg[]; busy: boolean; demo: boolean; canUndo: boolean; onUndo: () => void; onAsk: (q: string) => void }) {
  const [input, setInput] = useState("");
  const { en, t } = useLang();
  const last = [...msgs].reverse().find((m) => m.role === "model");
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || busy) return;
    onAsk(input);
    setInput("");
  };
  return (
    <footer className="rw-rewrite jn" data-testid="cc-rewrite">
      <span className="jn-strip" aria-hidden><i /><i /><i /></span>
      <div className="rw-rewrite-row">
        <img className="rw-rewrite-mark" src="/brand/jeen-mark.svg" alt="" />
        <b className="rw-rewrite-t">{t("שכתוב עם Jeen", "Rewrite with Jeen")}</b>
        <div className="rw-rewrite-chips">{(en ? [...REWRITES_EN, ...(demo ? [REWRITE_DEMO_EN] : [])] : [...REWRITES, ...(demo ? [REWRITE_DEMO] : [])]).map(([label, q]) => (
          <button key={label} className="rw-chip" onClick={() => onAsk(q)} disabled={busy} data-testid="cc-rewrite-chip">{label}</button>))}</div>
      </div>
      {(busy || last) && <div className={`rw-rewrite-last${last?.error ? " err" : ""}`} data-testid="cc-rewrite-last" aria-live="polite">
        {busy ? <><span className="jn-typing" aria-hidden><i /><i /><i /></span> {t("Jeen עורך את המכתב…", "Jeen is editing the letter…")}</>
          : last && <><span className="rw-rewrite-said">{last.text}</span>
            {last.edit?.state === "applied" && canUndo && <button className="cc-link" onClick={onUndo} data-testid="cc-rewrite-undo">{t("בטל", "Undo")}</button>}</>}
      </div>}
      <form className="jn-compose wide" onSubmit={submit}>
        <input value={input} onChange={(e) => setInput(e.target.value)} dir={en ? "auto" : "rtl"} maxLength={2000} disabled={busy}
          placeholder={t("מה לשנות במכתב? למשל: תוסיף שהבקשה כפופה לאימות נתונים", "What should change in the letter? For example: add that the application is subject to data verification")} aria-label={t("הוראת שכתוב ל־Jeen", "Rewrite instruction for Jeen")} data-testid="cc-rewrite-input" />
        <button type="submit" className="rw-btn jeen" disabled={busy || !input.trim()} data-testid="cc-rewrite-send">{t("שכתוב", "Rewrite")}</button>
      </form>
    </footer>
  );
}
