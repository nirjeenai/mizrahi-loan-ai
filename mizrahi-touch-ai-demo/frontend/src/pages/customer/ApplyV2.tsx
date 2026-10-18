import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ils, ilsL, type ChatAction, type ChatDraft, type ChatMessage, type ChatStage, type ChatTurn } from "../../api";
import { useCase } from "../../caseContext";
import { tr, useLang } from "../../i18n";
import { ICheck, ISend, ISpark } from "../../components/Icons";
import { LoanSimulator, SimulatorSnapshot } from "../../components/LoanSimulator";

const DRAFT_KEY = "mz.onboarding.draft.v2";

/** The conversational questionnaire (V2): the same server-side draft and confirmation as V1, asked as a conversation.
 *  Quick replies and free text both go through one turn endpoint; the server records every value through the V1
 *  questionnaire (validation, conditions, corrections) and composes every reply. Nothing here decides an answer. */
export function ApplyV2() {
  const { openCase } = useCase();
  const nav = useNavigate();
  const [draft, setDraft] = useState<ChatDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [echo, setEcho] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const composer = useRef<HTMLDivElement>(null);
  const shown = useRef(0);
  const { en, t } = useLang();

  const fresh = async () => {
    const d = await api.chatStart();
    localStorage.setItem(DRAFT_KEY, d.draft_id);
    setDraft(d);
  };
  useEffect(() => {
    const saved = localStorage.getItem(DRAFT_KEY);
    (saved ? api.chat(saved).catch(() => null) : Promise.resolve(null))
      .then((d) => (d && d.status === "draft" ? setDraft(d) : fresh()))
      .catch(() => setError(tr("פתיחת בקשה חדשה אינה זמינה בסביבה זו.", "Starting a new application isn't available in this environment.")));
  }, []);
  const count = draft?.messages.length ?? 0;
  useEffect(() => {
    // bring this turn's new messages into the band between the sticky stages and the sticky composer: the first new
    // message at the top when the turn is taller than the band, otherwise the last one just above the composer
    const el = log.current, screen = el?.closest(".screen");
    if (!el || !screen || !el.lastElementChild) return;
    const items = Array.from(el.children);
    if (!shown.current) { screen.scrollTop = screen.scrollHeight; shown.current = items.length; return; }
    const first = items[Math.min(shown.current, items.length - 1)], last = items[items.length - 1];
    const top = (el.parentElement?.querySelector(".cv2-stages")?.getBoundingClientRect().bottom ?? 0) + 8;
    const bottom = (composer.current?.getBoundingClientRect().top ?? screen.getBoundingClientRect().bottom) - 8;
    const f = first.getBoundingClientRect(), l = last.getBoundingClientRect();
    const delta = l.bottom - f.top > bottom - top ? f.top - top : Math.max(0, l.bottom - bottom);
    if (delta) screen.scrollBy({ top: delta, behavior: "smooth" });
    if (!busy) shown.current = items.length;
  }, [count, busy]);
  const complete = !!draft?.summary && !draft?.pending;
  useEffect(() => {
    if (complete) setTimeout(() => document.querySelector("[data-testid=cv2-summary]")?.scrollIntoView({ behavior: "smooth", block: "start" }), 450);
  }, [complete]);

  const inFlight = useRef(false);
  // the simulator card saves its draft with a debounce; a pending save is sent before the next turn reads the draft
  const flushSim = useRef<(() => Promise<void>) | null>(null);
  const registerFlush = useCallback((fn: (() => Promise<void>) | null) => { flushSim.current = fn; }, []);
  const send = async (turn: ChatTurn, shown: string | null, fromInput = false) => {
    // a ref, not state: two clicks in the same tick must not both send; the turn id makes a retried request a no-op
    if (!draft || inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setError(null); setEcho(shown);
    try {
      await flushSim.current?.();
      setDraft(await api.chatTurn(draft.draft_id, { ...turn, turn_id: crypto.randomUUID() }));
      if (fromInput) setText("");
    } catch (e) { setError((e as Error).message); }
    finally {
      inFlight.current = false;
      setBusy(false); setEcho(null);
      if (fromInput) requestAnimationFrame(() => input.current?.focus());
    }
  };
  // the server's Hebrew label is what it records; the English one (label_en) is the customer's echo in the English app
  const shownLabel = (x: { label_he: string; label_en?: string }) => (en && x.label_en) || x.label_he;
  const withEn = (x: { label_en?: string }) => (en && x.label_en ? { label_en: x.label_en } : {});
  const act = (a: ChatAction) => a.simulation ? send({ action: "simulate_apply", simulation: a.simulation, label_he: a.label_he, ...withEn(a) }, shownLabel(a))
    : a.text ? send({ text: a.text, ...withEn(a) }, shownLabel(a))
    : send({ question_id: a.question_id!, value: a.value, label_he: a.label_he, ...withEn(a) }, shownLabel(a));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (t) send({ text: t }, t, true);
  };
  const confirm = async () => {
    if (!draft || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await api.chatConfirm(draft.draft_id);
      localStorage.removeItem(DRAFT_KEY);
      openCase(r.case_id);
      nav("/customer/documents", { state: { handoff: "v2", first: (en && draft.first_name_en) || draft.first_name_he } });
    } catch (e) { setError((e as Error).message); setBusy(false); }
  };
  const restart = async () => { setBusy(true); setError(null); shown.current = 0; try { await fresh(); } finally { setBusy(false); } };

  const p = draft?.pending;
  const lastAssistant = draft ? [...draft.messages].reverse().find((m) => m.role === "assistant") : undefined;
  // while the assistant asks a clarification, its own choices are the only buttons on screen
  const clarifying = !!lastAssistant?.actions?.length;
  // a pending question asked in the other language: it is asked again here, live, in the app's language (not saved)
  const askedOther = !!draft && !!p && draft.status === "draft" && !!lastAssistant && msgLang(lastAssistant, en) !== (en ? "en" : "he")
    && !(p.kind === "simulator") ? (en ? p.prompt_en : p.prompt_he) : null;
  return (
    <div className="cv2-page">
      {draft && draft.messages.some((m) => m.role === "user") && (
        <div className="cv2-top">
          <button className="link small cv2-restart" onClick={restart} disabled={busy} data-testid="cv2-restart">{t("התחלה מחדש", "Start over")}</button>
        </div>
      )}
      <div className="card cv2" data-testid="apply-v2" data-draft={draft?.draft_id} data-engine={draft?.engine}>
        <div className="cv2-head">
          <AssistantMark size={36} />
          <div className="cv2-id"><b>{t("העוזר הדיגיטלי", "Digital assistant")}</b><span>{t("מזרחי־טפחות · בקשת הלוואה", "Mizrahi-Tefahot · loan application")}</span></div>
        </div>
        {draft && <Stages stages={draft.stages} />}
        <div className="chat-log cv2-log" ref={log} aria-live="polite" data-testid="cv2-log">
          {!draft && !error && <div className="bubble assistant"><span className="spinner" /></div>}
          {draft?.messages.flatMap((m, i) => {
            // a change of language in the transcript is marked once, where the assistant's language changes (the
            // customer's own words never mark it); earlier messages keep their own language
            const prev = m.role === "assistant" ? draft.messages.slice(0, i).reverse().find((x) => x.role === "assistant") : null;
            const divider = prev && msgLang(m, en) !== msgLang(prev, en)
              ? <div key={`lang-${m.id}`} className="cv2-lang-divider" role="separator" data-testid="cv2-lang-divider">
                  {msgLang(m, en) === "en" ? "Continuing in English" : "ממשיכים בעברית"}</div> : null;
            const row = (
              <Message key={m.id} m={m} grouped={i > 0 && draft.messages[i - 1].role === "assistant" && !divider} disabled={busy}
                actions={m.id === lastAssistant?.id ? m.actions : undefined} onAction={act} />
            );
            if (divider && !m.simulator) return [divider, row];
            if (!m.simulator) return divider ? [divider, row] : [row];
            const card = m.simulator.live && draft.simulation && draft.status === "draft"
              ? <LoanSimulator key={`sim-${m.id}`} sim={draft.simulation} draftId={draft.draft_id} busy={busy} registerFlush={registerFlush}
                  onConfirm={(simulation, label) => send({ action: "simulate_confirm", simulation, label_he: label }, label)} />
              : <SimulatorSnapshot key={`sim-${m.id}`} s={m.simulator} />;
            return divider ? [divider, row, card] : [row, card];
          })}
          {askedOther && !busy && (
            <div className="cv2-row" data-testid="cv2-current-question">
              <AssistantMark />
              <div className="cv2-stack"><div className="bubble assistant cv2-live-q">{askedOther}</div></div>
            </div>
          )}
          {echo && <div className="bubble user">{echo}</div>}
          {busy && <div className="bubble assistant cv2-typing" aria-label={t("העוזר כותב", "The assistant is typing")}><i /><i /><i /></div>}
        </div>
        {draft?.status === "draft" && (
          <div className="cv2-composer" ref={composer}>
            {p && p.kind !== "simulator" && p.replies.length > 0 && !clarifying && (
              <div className="onb-replies cv2-replies" role="group" aria-label={(en && p.prompt_en) || p.prompt_he} data-testid="cv2-pending" data-question={p.question_id}>
                {p.replies.map((r) => (
                  <button key={r.label_he} className="onb-reply" disabled={busy} data-testid="cv2-reply" data-value={JSON.stringify(r.value)}
                    onClick={() => send({ question_id: p.question_id, value: r.value, label_he: r.label_he, ...withEn(r) }, shownLabel(r))}>{shownLabel(r)}</button>
                ))}
              </div>
            )}
            {p && (p.kind === "simulator" || p.replies.length === 0 || clarifying) && <span hidden data-testid="cv2-pending" data-question={p.question_id} data-kind={p.kind} />}
            <div className="cv2-suggest">
              {p?.editing && (
                <button className="cv2-chip cancel" disabled={busy} onClick={() => send({ action: "cancel_edit" }, t("ביטול השינוי", "Cancel the change"))}
                  data-testid="cv2-cancel-edit">{t("ביטול השינוי", "Cancel the change")}</button>
              )}
              {!clarifying && draft.suggestions.filter((s) => s !== "למה צריך את זה?").map((s) => {
                const label = (en && draft.suggestions_en?.[draft.suggestions.indexOf(s)]) || s;
                return <button key={s} className="cv2-chip" disabled={busy} onClick={() => send({ text: s, ...(label !== s ? { label_en: label } : {}) }, label)} data-testid="cv2-suggestion">{label}</button>;
              })}
            </div>
            <form className="cv2-input" onSubmit={submit}>
              <input ref={input} className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={500}
                placeholder={en ? (p?.kind === "simulator" ? "You can also type, e.g. just 80,000, or up to 2,500 a month"
                  : p?.placeholder_en || p?.placeholder_he || "Ask me anything about the application…")
                  : p?.kind === "simulator" ? "אפשר גם לכתוב, למשל: רק 80 אלף, או עד 2,500 בחודש"
                  : p?.placeholder_he || "אפשר לשאול אותי כל שאלה על הבקשה…"} enterKeyHint="send" autoComplete="off"
                aria-label={t("הודעה לעוזר", "Message to the assistant")} data-testid="cv2-input" />
              <button className="cv2-send" disabled={busy || !text.trim()} aria-label={t("שליחה", "Send")} data-testid="cv2-send"><ISend size={18} /></button>
            </form>
          </div>
        )}
        {error && <div className="notice" role="alert" style={{ margin: "8px 10px 0" }} data-testid="cv2-error">{error}</div>}
      </div>
      {draft?.summary && !p && <Summary draft={draft} busy={busy} onEdit={(q, label) => send({ question_id: q, action: "edit" }, t(`שינוי ${label}`, `Change: ${label}`))} onConfirm={confirm} />}
    </div>
  );
}

/** The assistant's next-step note on the Documents screen, shown once after a V2 application is opened. */
export function ApplyHandoff() {
  const loc = useLocation();
  const nav = useNavigate();
  const { en, t } = useLang();
  const state = loc.state as { handoff?: string; first?: string | null } | null;
  if (state?.handoff !== "v2") return null;
  return (
    <div className="cv2-handoff" role="status" data-testid="cv2-handoff">
      <AssistantMark size={26} />
      <div className="grow">
        {en ? <>{state.first ? `${state.first}, ` : ""}your application is ready. Next come the documents that help the bank review it.
          You can upload them here, and I&apos;ll help you see whether anything is missing. Opening the application is not a loan approval.</>
          : <>{state.first ? `${state.first}, ` : ""}סיימנו להכין את הבקשה שלך. עכשיו נעבור למסמכים שיעזרו לבנק לבדוק אותה
        אפשר להעלות אותם כאן, ואני אעזור לך להבין אם משהו חסר. פתיחת הבקשה עדיין אינה אישור הלוואה.</>}
      </div>
      <button className="link tiny" onClick={() => nav(loc.pathname, { replace: true, state: null })} aria-label={t("סגירה", "Close")}>{t("הבנתי", "Got it")}</button>
    </div>
  );
}

function Stages({ stages }: { stages: ChatStage[] }) {
  const { en } = useLang();
  const i = stages.findIndex((s) => s.state === "current");
  const cur = stages[i];
  const label = (s: ChatStage) => (en && s.label_en) || s.label_he;
  const caption = !cur ? "" : en ? (cur.id === "summary" ? "Almost done — just review the summary and confirm"
    : `Step ${i + 1} of ${stages.length} · ${label(cur)}${cur.total > 1 ? ` · question ${Math.min(cur.answered + 1, cur.total)} of ${cur.total}` : ""}`)
    : cur.id === "summary" ? "כמעט סיימנו, נשאר לעבור על הסיכום ולאשר"
    : `שלב ${i + 1} מתוך ${stages.length} · ${cur.label_he}${cur.total > 1 ? ` · שאלה ${Math.min(cur.answered + 1, cur.total)} מתוך ${cur.total}` : ""}`;
  return (
    <div className="cv2-stages" data-testid="cv2-stages">
      <ol>
        {stages.map((s) => (
          <li key={s.id} className={s.state} data-testid={`cv2-stage-${s.id}`} data-state={s.state} aria-current={s.state === "current" ? "step" : undefined}>
            <span className="dot">{s.state === "done" ? <ICheck size={11} /> : null}</span>
            <span className="lbl">{label(s)}</span>
          </li>
        ))}
      </ol>
      <div className="tiny muted cv2-caption" data-testid="cv2-caption">{caption}</div>
    </div>
  );
}

/** The assistant's avatar (a synthetic banking-assistant portrait, always labelled "העוזר הדיגיטלי"); the spark mark
 *  is the fallback when the image cannot load. */
export function AssistantMark({ size = 26 }: { size?: number }) {
  const [broken, setBroken] = useState(false);
  return (
    <span className={`cv2-mark${broken ? "" : " photo"}`} style={{ width: size, height: size }} aria-hidden="true">
      {broken ? <ISpark size={Math.round(size * 0.55)} />
        : <img src="/people/digital-assistant.jpg" alt="" onError={() => setBroken(true)} />}
    </span>
  );
}

/** The language a message is shown in: English when the app is English and the message has an English rendering;
 *  otherwise Hebrew — every assistant message has its Hebrew (text_he) — except the customer's own English words. */
function msgLang(m: ChatMessage, en: boolean): "he" | "en" {
  if (en && m.text_en) return "en";
  return m.role === "user" && m.lang === "en" && !m.text_en ? "en" : "he";
}

function Message({ m, grouped, disabled, actions, onAction }: {
  m: ChatMessage; grouped: boolean; disabled: boolean;
  actions?: ChatAction[]; onAction: (a: ChatAction) => void;
}) {
  const { en } = useLang();
  const text = (en && m.text_en) || m.text_he;
  // a message shown in a language other than the app's (an earlier turn, or the customer's own words) keeps its direction
  const dir = en ? (m.text_en ? undefined : "auto") : m.lang === "en" && !m.text_en ? "ltr" : undefined;
  if (m.role === "user") return <div className="bubble user" data-testid="cv2-msg" data-kind="user" dir={dir}>{text}</div>;
  const legacyInsight = m.kind === "insight";
  return (
    <div className={`cv2-row${grouped ? " grouped" : ""}`}>
      {grouped ? <span className="cv2-mark-space" /> : <AssistantMark />}
      <div className="cv2-stack">
        {m.indication && <IndicationCard m={m} />}
        {!legacyInsight && (
          <div className={`bubble assistant${m.kind === "withdrawn" || m.insight === "withdrawn" ? " cv2-muted" : ""}${actions?.length ? " has-actions" : ""}`}
            data-testid="cv2-msg" data-kind={m.kind} data-question={m.question_id} data-engine={m.engine} dir={dir}>
            {text}
            {actions && actions.length > 0 && (
              <div className="cv2-actions">
                {actions.map((a) => <button key={a.label_he} className="onb-reply" disabled={disabled} onClick={() => onAction(a)} data-testid="cv2-action">{(en && a.label_en) || a.label_he}</button>)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const nis = (n: number) => tr(`${Math.round(n).toLocaleString("en-US")} ₪`, `₪${Math.round(n).toLocaleString("en-US")}`);
const BANK_PATH = ["הערכה", "מסמכים", "בדיקת הבנק", "החלטת הבנק"];
const BANK_PATH_EN = ["Assessment", "Documents", "Bank review", "Bank decision"];

/** The DEMO preliminary assessment, read in three seconds: what was requested, what it costs a month, whether to go
 *  on. The bank's process sits under it as a path with the customer on its first step, so a preliminary assessment is
 *  never read as a decision. The formula's inputs, the theoretical ceiling and the caveats live behind "איך הגענו לזה". */
function IndicationCard({ m }: { m: ChatMessage }) {
  const ind = m.indication!;
  const [open, setOpen] = useState(false);
  const { en, t } = useLang();
  if (m.stale) {
    return (
      <div className="cv2-insight stale" data-testid="cv2-insight" data-stale="1" data-max={ind.max_amount_ils} data-requested={ind.requested_amount_ils}>
        <span className="ia-k">{t("הערכה קודמת", "Earlier assessment")}</span>
        <s className="ia-old">{nis(ind.requested_amount_ils)}</s>
        {en ? <span className="ia-k">· {ind.payments} payments</span> : <span className="ia-k">· {ind.payments} תשלומים</span>}
        <span className="ia-badge" data-testid="cv2-insight-stale">{t("עודכנה", "Updated")}</span>
      </div>
    );
  }
  return (
    <div className={`cv2-insight ${ind.within ? "ok" : "warn"}`} data-testid="cv2-insight" data-stale="0"
      data-max={ind.max_amount_ils} data-requested={ind.requested_amount_ils} role="group" aria-label={t("הערכה ראשונית לבקשה", "Preliminary assessment of the application")}>
      <div className="ia-head">
        <img src="/brand/jeen-mark.png" alt="" aria-hidden />
        <span>{t("הערכה ראשונית", "Preliminary assessment")}</span>
        <span className="ia-not">{t("לא אישור הלוואה", "Not a loan approval")}</span>
      </div>
      <div className="ia-amount" data-testid="cv2-insight-amount">
        <span className="ia-k">{t("ביקשת", "You asked for")}</span>
        <b>{en ? <><i>₪</i><span className="ltr">{ind.requested_amount_ils.toLocaleString("en-US")}</span></>
          : <><span className="ltr">{ind.requested_amount_ils.toLocaleString("en-US")}</span><i>₪</i></>}</b>
      </div>
      <p className="ia-monthly" data-testid="cv2-insight-monthly">
        {en ? <>About <b>{nis(ind.requested_monthly_ils)}</b> a month<span className="ia-dot">·</span>{ind.payments} payments</>
          : <>כ־<b>{nis(ind.requested_monthly_ils)}</b> בחודש<span className="ia-dot">·</span>{ind.payments} תשלומים</>}
      </p>
      <div className="ia-status" data-testid="cv2-insight-status">
        <span className="ia-icon" aria-hidden>{ind.within ? <ICheck size={13} /> : "!"}</span>
        <div>
          <b>{ind.within ? t("אפשר להמשיך לבדיקת הבנק", "You can go on to the bank's review") : t("גבוה מההערכה הראשונית", "Higher than the preliminary assessment")}</b>
          <span>{ind.within ? t("הצעד הבא: עוד כמה פרטים, ואז מסמכים", "Next: a few more details, then documents") : t("אפשר להמשיך כך, הבנק יבדוק את הבקשה", "You can continue as is — the bank will review the application")}</span>
        </div>
      </div>
      <ol className="ia-path" aria-label={t("השלבים עד החלטת הבנק", "The steps to the bank's decision")}>
        {BANK_PATH.map((s, i) => <li key={s} className={i === 0 ? "here" : ""} aria-current={i === 0 ? "step" : undefined}><i />{en ? BANK_PATH_EN[i] : s}</li>)}
      </ol>
      <button className="ia-more" aria-expanded={open} onClick={() => setOpen((o) => !o)} data-testid="cv2-insight-more">
        {en ? <>How we got here <span aria-hidden>{open ? "−" : "+"}</span></> : <>איך הגענו לזה <span aria-hidden>{open ? "−" : "+"}</span></>}
      </button>
      {open && (
        <dl className="ia-facts" data-testid="cv2-insight-facts">
          <div><dt>{t("הכנסה נטו שמסרת", "Net income you gave")}</dt><dd>{nis(ind.declared_net_ils)}<small>{t("הצהרה", "Declared")}</small></dd></div>
          {ind.ratio != null && <div><dt>{t("חלק מההכנסה להחזר (הנחה)", "Share of income for repayment (assumption)")}</dt><dd>{Math.round(ind.ratio * 100)}%</dd></div>}
          {ind.annual_rate != null && <div><dt>{t("ריבית להמחשה", "Illustrative rate")}</dt><dd>{+(ind.annual_rate * 100).toFixed(2)}{t("% לשנה", "% a year")}</dd></div>}
          <div><dt>{t("תקרה תיאורטית בנוסחה", "Theoretical ceiling in the formula")}</dt><dd>{nis(ind.max_amount_ils)}<small>{t("לא מסגרת אשראי", "Not a credit limit")}</small></dd></div>
          <p>{en ? <>{ind.co_borrower_pending ? "The co-borrower's income isn't included yet. " : ""}Based only on what you told us and general calculation assumptions — no credit data, accounts or obligations. This is not an eligibility check and not an approval.</>
            : <>{ind.co_borrower_pending ? "ההכנסה של הלווה הנוסף עוד לא נכללה. " : ""}לפי מה שמסרת והנחות חישוב כלליות בלבד, בלי נתוני אשראי, חשבונות או התחייבויות. זו לא בדיקת זכאות ולא אישור.</>}</p>
        </dl>
      )}
    </div>
  );
}

function Summary({ draft, busy, onEdit, onConfirm }: { draft: ChatDraft; busy: boolean; onEdit: (q: string, label: string) => void; onConfirm: () => void }) {
  const s = draft.summary!;
  const { en, t } = useLang();
  const owners = [...new Set(s.requirements.map((r) => r.owner_he || ""))];
  return (
    <section className="card onb-summary cv2-summary" data-testid="cv2-summary" data-entity={s.profile.entity}>
      <div className="card-title">{t("סיכום הבקשה", "Application summary")}</div>
      <p className="small muted" style={{ margin: "4px 0 6px", lineHeight: 1.6 }}>{(en && s.intro_en) || s.intro_he}</p>
      {s.lines.map((l) => (
        <div key={l.question_id} className="kv cv2-line" data-testid="cv2-line" data-question={l.question_id}>
          <span>{(en && l.label_en) || l.label_he}</span>
          <span><span className="cv2-val">{(en && l.value_en) || l.value_he}</span>
            <button className="link tiny cv2-edit" disabled={busy} onClick={() => onEdit(l.question_id, (en && l.label_en) || l.label_he)}
              data-testid={`cv2-edit-${l.question_id}`} aria-label={t(`שינוי ${l.label_he}`, `Change ${l.label_en || l.label_he}`)}>{t("שינוי", "Change")}</button></span>
        </div>
      ))}
      {draft.indication && (
        <div className="cv2-summary-ind" data-testid="cv2-summary-indication">
          {en ? <>Preliminary indication: your request for <b className="ltr">{ilsL(draft.indication.requested_amount_ils)}</b>{" "}
            {draft.indication.within ? "looks possible to take forward for an initial review" : "is higher than the preliminary assessment shows as possible"} (estimated repayment
            about <span className="ltr">{ilsL(draft.indication.requested_monthly_ils)}</span> over {draft.indication.payments} payments), based on the income
            you gave and general calculation assumptions. This is not an eligibility check and not an approval.</>
            : <>אינדיקציה ראשונית: הבקשה ל־<b className="ltr">{ils(draft.indication.requested_amount_ils)}</b>{" "}
          {draft.indication.within ? "נראית אפשרית להמשך בדיקה ראשונית" : "גבוהה ממה שההערכה הראשונית מראה כאפשרי"} (החזר משוער
          כ־<span className="ltr">{ils(draft.indication.requested_monthly_ils)}</span> ב־{draft.indication.payments} תשלומים), לפי ההכנסה
          שמסרת והנחות חישוב כלליות. זו אינה בדיקת זכאות ואינה אישור.</>}
        </div>
      )}
      {s.profile.banker_assisted && (
        <div className="notice navy small" style={{ marginTop: 10 }} data-testid="cv2-banker-assisted">
          {t("מסלול עסקי מוגבל: הבקשה מטופלת בליווי הבנקאית. כאן אוספים את מסמכי הזיהוי והדוחות, אין חיתום עסקי ואין החלטת אשראי אוטומטית.",
            "Limited business path: your banker handles this application. Here we collect the ID and financial documents; there's no business underwriting and no automatic credit decision.")}</div>
      )}
      <div className="section-label" style={{ margin: "14px 0 6px" }}>{en ? <>Documents you&apos;ll need ({s.requirements.length})</> : <>המסמכים שיידרשו ({s.requirements.length})</>}</div>
      <ul className="onb-reqs">
        {owners.flatMap((o) => s.requirements.filter((r) => (r.owner_he || "") === o)).map((r) => (
          <li key={r.code} data-testid="cv2-req" data-code={r.code} data-owner={r.owner_he || ""}>{(en && r.title_en) || r.title_he}</li>
        ))}
      </ul>
      <div className="tiny muted" style={{ lineHeight: 1.6, marginTop: 8 }}>
        {en ? <>Opening the application is not a loan approval — it prepares the document list for the bank&apos;s review. Policy version: <span className="ltr">{s.policy_version}</span>.</>
          : <>פתיחת הבקשה אינה אישור הלוואה, היא מכינה את רשימת המסמכים לבדיקת הבנק. גרסת מדיניות: <span className="ltr">{s.policy_version}</span>.</>}</div>
      <button className="btn btn-orange" style={{ width: "100%", marginTop: 12 }} disabled={busy} onClick={onConfirm} data-testid="cv2-confirm">
        {busy && <span className="spinner" />}{t("אישור ופתיחת הבקשה", "Confirm and open the application")}</button>
    </section>
  );
}
