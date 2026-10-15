import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api, type CaseChatReply, type DemoLetter, type IntelDraft } from "../../api";
import { DRAFT_NOTE, MARK, markOf, type Ctx } from "./IntelligenceV2";
import "./replyworkspace.css";

type Toast = (t: { text: string; tone: "ok" | "bad" }) => void;
interface Msg {
  id: number; role: "user" | "model"; text: string; intent?: CaseChatReply["intent"]; sources?: CaseChatReply["sources"];
  issues?: string[]; error?: boolean;
  /** applied: the editor took the revision · stale: the draft changed while JEEN worked, so it waits for the banker */
  edit?: { kind: string; text: string; summary_he: string; state: "applied" | "stale" | "undone" };
}
interface AiChange { kind: string; before: string; after: string; msgId: number }

const CHIPS_READY = ["למה מומלץ להתקדם?", "מה עדיין צריך לבדוק?", "תנסח את המכתב יותר פורמלי", "תקצר את המענה"];
const CHIPS_OTHER = ["מה ההמלצה ולמה?", "מה עדיין צריך לבדוק?", "תנסח את המכתב יותר פורמלי", "תקצר את המענה"];
const CHIPS_DEMO = ["תנסח את זה בצורה רשמית יותר ותוסיף הסבר על תנאי ההחזר", "תסביר ללקוחה מה השלב הבא כדי לקבל את הכסף",
  "תקצר את הפתיחה אבל תשאיר את כל התנאים"];
const DEMO = "demo_approval";
const DEMO_TITLE = "אישור הלוואה — הדמיה";
const DEMO_NOTE = "מכתב מפורט לתרחיש שבו הבנקאי אישר את הבקשה בכפוף לתנאים. הדמיה בלבד — ההחלטה בתיק עצמו לא השתנתה.";
const DEMO_COPY_BANNER = "[מסמך הדמיה (DEMO) — אינו החלטת אשראי של הבנק ואינו הסכם הלוואה. לא נשלח ללקוח.]";
const READY = ["READY_FOR_CREDIT_REVIEW", "PREPARATION_CONFIRMED"];
type DemoState = { status: "idle" | "loading" | "ready" | "error"; letter?: DemoLetter; error?: string };

/** Banker V3 "מענה מוצע ללקוח": the editable customer reply (right) and "שאל את JEEN" (left) on ONE draft state.
 *  JEEN answers from the selected case and may return a revision of the draft as the banker sees it; the server has
 *  already checked it, and it is applied only if the draft did not change meanwhile. Mount with key={case_id}: a case
 *  switch drops the conversation, the drafts and any request still in flight. Nothing is sent to the customer. */
export function ReplyWorkspace({ ctx, onToast }: { ctx: Ctx; onToast: Toast }) {
  const { x } = ctx;
  const [kind, setKind] = useState<string | null>(x.recommended_draft);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [refs, setRefs] = useState<Record<string, boolean>>({});
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastAi, setLastAi] = useState<AiChange | null>(null);
  const [flash, setFlash] = useState(0);
  const [pane, setPane] = useState<"draft" | "chat">("draft");
  const [demo, setDemo] = useState<DemoState>({ status: "idle" });
  const demoRef = useRef(demo);
  demoRef.current = demo;
  const demoCall = useRef<AbortController | null>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const textsRef = useRef(texts);
  textsRef.current = texts;
  const inflight = useRef<AbortController | null>(null);
  const seq = useRef(0);
  useEffect(() => () => { inflight.current?.abort(); demoCall.current?.abort(); }, []);

  const ready = READY.includes(x.recommendation.state);
  const tabs: IntelDraft[] = x.simulation.enabled
    ? [...x.drafts, { kind: DEMO, title_he: DEMO_TITLE, message_he: demo.letter?.text ?? "", attachments: [] }] : x.drafts;
  const draft = tabs.find((d) => d.kind === kind) || tabs[0] || null;
  const isDemo = draft?.kind === DEMO;
  const demoPending = isDemo && !demo.letter;
  const templateOf = (k: string) => (k === DEMO ? demoRef.current.letter?.text ?? "" : x.drafts.find((d) => d.kind === k)?.message_he ?? "");
  const textOf = (k: string) => textsRef.current[k] ?? templateOf(k);
  const text = draft ? texts[draft.kind] ?? draft.message_he : "";
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [text, pane]);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [msgs.length, busy]);
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
      setDemo((d) => ({ ...d, status: d.letter ? "ready" : "error", error: e instanceof Error && e.message ? e.message : "JEEN לא הצליח להכין את המכתב כרגע." }));
    }
  };
  useEffect(() => {
    if (isDemo && ready && demo.status === "idle") void makeLetter(false);
  }, [isDemo, ready, demo.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const regenerate = () => {
    if (!demo.letter) return;
    const edited = texts[DEMO] != null && texts[DEMO] !== demo.letter.text;
    if (edited && !window.confirm("הכנה מחדש תחליף את המכתב הנוכחי, כולל השינויים שלך ושל JEEN. להמשיך?")) return;
    void makeLetter(!ready);
  };

  const ask = async (message: string, prior: Msg[]) => {
    const q = message.trim();
    if (!q || busy) return;
    const sentKind = draft && !(draft.kind === DEMO && !demoRef.current.letter) ? draft.kind : null;
    const sentText = sentKind ? textOf(sentKind) : "";
    const history = prior.filter((m) => !m.error).slice(-12).map((m) => ({
      role: m.role, text: m.role === "model" && m.edit?.state === "applied" ? `${m.text}\n[עדכנתי את הטיוטה: ${m.edit.summary_he}]` : m.text }));
    const userMsg: Msg = { id: ++seq.current, role: "user", text: q };
    setMsgs([...prior, userMsg]);
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
      setMsgs((prev) => [...prev, { id, role: "model", text: r.answer_he, intent: r.intent, sources: r.sources, issues: r.rejected_issues_he, edit }]);
    } catch (e) {
      if (ctl.signal.aborted) return;
      setMsgs((prev) => [...prev, { id: ++seq.current, role: "model", error: true,
        text: e instanceof Error && e.message && !/^\d+$/.test(e.message) ? e.message : "JEEN לא הצליח לענות כרגע. הטיוטה לא השתנתה." }]);
    } finally {
      if (inflight.current === ctl) { inflight.current = null; setBusy(false); }
    }
  };
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || busy) return;
    const q = input;
    setInput("");
    void ask(q, msgs);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
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
    if (now !== lastAi.after && !window.confirm("ביטול השינוי של JEEN יחזיר את הנוסח שלפניו, ויבטל גם עריכות שעשית אחריו. להמשיך?")) return;
    setText(lastAi.kind, lastAi.before);
    patchMsg(lastAi.msgId, (m) => (m.edit ? { ...m, edit: { ...m.edit, state: "undone" } } : m));
    setLastAi(null);
    onToast({ text: "השינוי האחרון של JEEN בוטל.", tone: "ok" });
  };
  const applyStale = (m: Msg) => {
    if (!m.edit) return;
    if (!window.confirm("הטיוטה השתנתה מאז ששאלת. החלת ההצעה של JEEN תחליף את הנוסח הנוכחי. להמשיך?")) return;
    applyEdit(m.edit, textOf(m.edit.kind), m.id);
    patchMsg(m.id, (p) => (p.edit ? { ...p, edit: { ...p.edit, state: "applied" } } : p));
  };

  const edited = !!draft && !demoPending && texts[draft.kind] != null && texts[draft.kind] !== draft.message_he;
  const byJeen = !!draft && lastAi?.kind === draft.kind && text === lastAi.after;
  const restore = () => {
    if (!draft) return;
    if (!window.confirm("שחזור הנוסח המקורי ימחק את השינויים בטיוטה — שלך ושל JEEN. להמשיך?")) return;
    setText(draft.kind, draft.message_he);
    if (lastAi?.kind === draft.kind) setLastAi(null);
  };
  const chosen = draft ? draft.attachments.filter((a) => refs[`${draft.kind}:${a.document_id}`]) : [];
  const body = chosen.length ? `${text}\n\nמסמכים בתיק שההודעה מתייחסת אליהם: ${chosen.map((a) => a.label_he).join(" · ")}` : text;
  const full = isDemo ? `${DEMO_COPY_BANNER}\n\n${body}\n\n${DEMO_COPY_BANNER}` : body;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(full);
      onToast({ text: "המענה הועתק. הוא לא נשלח ללקוח — השליחה נעשית בערוץ הבנק.", tone: "ok" });
    } catch {
      onToast({ text: "ההעתקה נחסמה בדפדפן. אפשר לסמן את הטקסט ולהעתיק ידנית.", tone: "bad" });
    }
  };
  const chips = isDemo && demo.letter ? CHIPS_DEMO : ready ? CHIPS_READY : CHIPS_OTHER;

  return (
    <section className="cc-card rw" id="cc-reply" data-testid="cc-reply">
      <header className="cc-card-head">
        <div><h2>מענה מוצע ללקוח</h2><p className="cc-sub">טיוטה שהוכנה ממצב התיק. אפשר לערוך ידנית או לבקש מ־JEEN — שום דבר לא נשלח מכאן.</p></div>
        <div className="rw-switch" role="tablist" aria-label="תצוגה" data-testid="cc-pane-switch">
          <button role="tab" aria-selected={pane === "draft"} className={pane === "draft" ? "on" : ""} onClick={() => setPane("draft")} data-testid="cc-pane-draft">טיוטה</button>
          <button role="tab" aria-selected={pane === "chat"} className={pane === "chat" ? "on" : ""} onClick={() => setPane("chat")} data-testid="cc-pane-chat">
            שאל את JEEN{busy && <span className="rw-dot" aria-hidden />}</button>
        </div>
      </header>
      <div className={`cc-card-body rw-grid pane-${pane}`}>
        <div className="rw-draft" data-testid="cc-draft-col">
          {!draft ? <div className="cc-empty">אין טיוטה מתאימה למצב התיק כרגע. אפשר עדיין לשאול את JEEN על התיק.</div> : <>
            {tabs.length > 1 && <div className="cc-dtabs" role="tablist">
              {tabs.map((d) => (
                <button key={d.kind} role="tab" aria-selected={d.kind === draft.kind} className={d.kind === draft.kind ? "on" : ""} onClick={() => setKind(d.kind)}
                  data-testid="cc-draft-tab" data-kind={d.kind}>{d.title_he}{d.kind === x.recommended_draft && <span className="cc-rec-pill">מומלץ</span>}
                  {d.kind === DEMO && <span className="rw-demo-pill">DEMO</span>}
                  {texts[d.kind] != null && texts[d.kind] !== d.message_he && <span className="rw-tab-dot" title="נערך" aria-label="נערך" />}</button>
              ))}
            </div>}
            {isDemo && <DemoStrip demo={demo} ready={ready} onRegenerate={regenerate} />}
            {demoPending ? <DemoGate demo={demo} ready={ready} onMake={(ack, ai) => void makeLetter(ack, ai)} /> : <>
            <div className={`cc-paper${isDemo ? " rw-letter" : ""}${flash && byJeen ? " rw-flash" : ""}`}>
              <div className="cc-paper-bar">
                <b>{draft.title_he}</b><span className="cc-muted">{isDemo ? DEMO_NOTE : DRAFT_NOTE[draft.kind]}</span>
                {byJeen ? <span className="rw-ai-badge" data-testid="cc-draft-ai">עודכן על ידי JEEN</span>
                  : edited && <span className="cc-edited" data-testid="cc-draft-edited">נערך</span>}
                <span className="rw-bar-acts">
                  {lastAi?.kind === draft.kind && <button className="cc-link" onClick={undo} data-testid="cc-draft-undo">בטל שינוי</button>}
                  <button className="cc-link" disabled={!edited} onClick={restore} data-testid="cc-draft-restore">שחזור הנוסח</button>
                </span>
              </div>
              <textarea ref={area} className="cc-paper-text" value={text} onChange={(e) => setText(draft.kind, e.target.value)} dir="rtl"
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
              <button className="cc-primary" onClick={copy} data-testid="cc-draft-copy">{isDemo ? "העתקת המכתב (מסומן כהדמיה)" : "העתקת המענה"}</button>
              <span className="cc-muted cc-small">{isDemo ? "אין שליחה. ההעתקה מוסיפה בראש ובסוף סימון בולט שזהו מסמך הדמיה. המספרים מחושבים בקוד; שינויים של JEEN נבדקים לפני שהם נכנסים למכתב."
                : "אין שליחה אוטומטית. התבנית קבועה; שינויים של JEEN נבדקים בקוד מול נתוני התיק לפני שהם נכנסים לטיוטה."}</span>
            </div>
            </>}
          </>}
        </div>

        <aside className="rw-chat" data-testid="cc-chat" aria-label="שאל את JEEN">
          <header className="rw-chat-head">
            <b>שאל את JEEN</b>
            <span>עוזר AI שמכיר את הבקשה, המסמכים והניתוח הפיננסי</span>
          </header>
          <div className="rw-log" ref={log} aria-live="polite" data-testid="cc-chat-log">
            {msgs.length === 0 && <div className="rw-intro">
              <p>אפשר לשאול על התיק או לבקש שינוי בטיוטה — למשל:</p>
              <div className="rw-chips">{chips.map((c) => (
                <button key={c} className="rw-chip" onClick={() => void ask(c, msgs)} disabled={busy} data-testid="cc-chat-chip">{c}</button>))}</div>
            </div>}
            {msgs.map((m) => <Bubble key={m.id} m={m} ctx={ctx} latest={lastAi?.msgId === m.id} onUndo={undo} onApply={() => applyStale(m)} onRetry={() => retry(m.id)} busy={busy} />)}
            {busy && <div className="rw-msg m-model pending" data-testid="cc-chat-pending"><span className="spinner" /> JEEN בודק בתיק…</div>}
          </div>
          <form className="rw-input" onSubmit={submit}>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={2} dir="rtl" maxLength={2000}
              placeholder={busy ? "JEEN עונה…" : "שאלה על התיק או בקשה לשינוי במכתב"} disabled={busy} aria-label="הודעה ל־JEEN" data-testid="cc-chat-input" />
            <button type="submit" className="rw-send" disabled={busy || !input.trim()} data-testid="cc-chat-send" aria-label="שליחה">שליחה</button>
          </form>
          <p className="rw-foot">JEEN עונה מנתוני התיק בלבד ואינו משנה את הבקשה, הסטטוסים או החלטות הבנקאי.</p>
        </aside>
      </div>
    </section>
  );
}

function Bubble({ m, ctx, latest, onUndo, onApply, onRetry, busy }: { m: Msg; ctx: Ctx; latest: boolean; onUndo: () => void; onApply: () => void; onRetry: () => void; busy: boolean }) {
  if (m.role === "user") return <div className="rw-msg m-user" data-testid="cc-chat-msg" data-role="user">{m.text}</div>;
  const ids = Object.keys(m.sources || {});
  return (
    <div className={`rw-msg m-model${m.error ? " err" : ""}`} data-testid="cc-chat-msg" data-role="model" data-intent={m.intent || (m.error ? "error" : "")}>
      <div className="rw-text">{m.text}</div>
      {m.edit && <div className={`rw-edit s-${m.edit.state}`} data-testid="cc-chat-edit" data-state={m.edit.state}>
        {m.edit.state === "applied" && <><span>✓ הטיוטה עודכנה</span>{latest && <button className="cc-link" onClick={onUndo} data-testid="cc-chat-undo">בטל שינוי</button>}</>}
        {m.edit.state === "undone" && <span>השינוי בוטל</span>}
        {m.edit.state === "stale" && <><span>הטיוטה השתנתה בזמן שעבדתי, ולכן לא החלפתי אותה.</span>
          <button className="cc-link" onClick={onApply} data-testid="cc-chat-apply">החלה בכל זאת</button></>}
      </div>}
      {!m.edit && (m.intent === "draft_edit" || m.intent === "question_and_edit" || m.intent === "declined") && (m.issues?.length || m.intent === "declined") ?
        <div className="rw-edit s-kept" data-testid="cc-chat-kept">הטיוטה לא השתנתה</div> : null}
      {ids.length > 0 && <div className="rw-srcs">{ids.map((id) => {
        const s = ctx.x.sources[id];
        const k = s ? markOf(s) : "missing";
        return <button key={id} className={`rw-src k-${k}`} onClick={() => ctx.open(id)} disabled={!s} title={MARK[k].title} data-testid="cc-chat-source" data-source={id}>
          <span className="rw-src-k">{MARK[k].label}</span>{m.sources![id].label_he}</button>;
      })}</div>}
      {m.error && <button className="cc-link" onClick={onRetry} disabled={busy} data-testid="cc-chat-retry">ניסיון חוזר</button>}
    </div>
  );
}

/** The simulated-approval indicator above the third letter: what this is, where the text came from, and regeneration. */
function DemoStrip({ demo, ready, onRegenerate }: { demo: DemoState; ready: boolean; onRegenerate: () => void }) {
  const l = demo.letter;
  return (
    <div className="rw-demo" data-testid="cc-demo-strip">
      <div className="rw-demo-main"><span className="rw-demo-pill">DEMO</span><b>תרחיש הדגמה: בקשת ההלוואה אושרה בכפוף לתנאים</b></div>
      <div className="rw-demo-sub">ההחלטה מדומה ואינה נשמרת: סטטוס התיק, החלטות המסמכים והנתונים הפיננסיים לא השתנו, ושום דבר לא נשלח.
        {!ready && " התיק עצמו אינו מוכן לבחינת אשראי — הפריטים הפתוחים נשארים בתיק."}</div>
      {l && <div className="rw-demo-meta" data-testid="cc-demo-source" data-source={l.source}>
        {l.source === "ai" ? <span>הניסוח נכתב על ידי JEEN מנתוני התיק; הסכומים חושבו בקוד.</span>
          : <span className="warn">נוסח בסיס קבוע — לא נכתב ב-AI{l.check_issues_he.length ? " (הניסוח של JEEN לא עבר את הבדיקה)" : ""}.</span>}
        <button className="cc-link" onClick={onRegenerate} disabled={demo.status === "loading"} data-testid="cc-demo-regenerate">
          {demo.status === "loading" ? "מכין מחדש…" : "הכנה מחדש עם JEEN"}</button></div>}
      {l && l.open_issues_he.length > 0 && <details className="rw-demo-issues" open={!ready} data-testid="cc-demo-issues">
        <summary>פריטים פתוחים בתיק האמיתי ({l.open_issues_he.length})</summary>
        <ul>{l.open_issues_he.map((t, i) => <li key={i}>{t}</li>)}</ul></details>}
    </div>
  );
}

function DemoGate({ demo, ready, onMake }: { demo: DemoState; ready: boolean; onMake: (acknowledge: boolean, useAi: boolean) => void }) {
  if (demo.status === "loading") return (
    <div className="rw-gate" data-testid="cc-demo-loading"><span className="spinner" /> JEEN מכין מכתב אישור מפורט לתרחיש ההדמיה מנתוני התיק…</div>);
  return (
    <div className="rw-gate" data-testid="cc-demo-gate">
      {demo.status === "error" && <p className="rw-gate-err" data-testid="cc-demo-error">{demo.error}</p>}
      {!ready && demo.status !== "error" && <>
        <p><b>התיק אינו מוכן לבחינת אשראי.</b> מכתב אישור יוכן רק כתרחיש הדמיה שתבחר/י במפורש. הפריטים הפתוחים נשארים בתיק, והמכתב יכלול תנאי להשלמתם.</p>
      </>}
      <div className="rw-gate-acts">
        <button className="cc-primary" onClick={() => onMake(!ready, true)} data-testid="cc-demo-make">
          {demo.status === "error" ? "ניסיון חוזר" : ready ? "הכנת מכתב האישור עם JEEN" : "הכנת מכתב לתרחיש הדמיה בכל זאת"}</button>
        {demo.status === "error" && <button className="btn btn-ghost btn-sm" onClick={() => onMake(!ready, false)} data-testid="cc-demo-base">
          שימוש בנוסח הבסיס (ללא AI)</button>}
      </div>
    </div>
  );
}
