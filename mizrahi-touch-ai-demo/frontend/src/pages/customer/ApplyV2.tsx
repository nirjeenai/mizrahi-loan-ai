import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, ils, type ChatDraft, type ChatMessage, type ChatStage, type ChatTurn } from "../../api";
import { useCase } from "../../caseContext";
import { ICheck, ISend } from "../../components/Icons";

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

  const fresh = async () => {
    const d = await api.chatStart();
    localStorage.setItem(DRAFT_KEY, d.draft_id);
    setDraft(d);
  };
  useEffect(() => {
    const saved = localStorage.getItem(DRAFT_KEY);
    (saved ? api.chat(saved).catch(() => null) : Promise.resolve(null))
      .then((d) => (d && d.status === "draft" ? setDraft(d) : fresh()))
      .catch(() => setError("פתיחת בקשה חדשה אינה זמינה בסביבה זו."));
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

  const send = async (turn: ChatTurn, shown: string | null, fromInput = false) => {
    if (!draft || busy) return;
    setBusy(true); setError(null); setEcho(shown);
    try {
      setDraft(await api.chatTurn(draft.draft_id, turn));
      if (fromInput) setText("");
    } catch (e) { setError((e as Error).message); }
    finally {
      setBusy(false); setEcho(null);
      if (fromInput) requestAnimationFrame(() => input.current?.focus());
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (t) send({ text: t }, t, true);
  };
  const confirm = async () => {
    if (!draft || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await api.onboardingConfirm(draft.draft_id);
      localStorage.removeItem(DRAFT_KEY);
      openCase(r.case_id);
      nav("/customer/documents", { state: { handoff: "v2", first: draft.first_name_he } });
    } catch (e) { setError((e as Error).message); setBusy(false); }
  };
  const restart = async () => { setBusy(true); setError(null); shown.current = 0; try { await fresh(); } finally { setBusy(false); } };

  const p = draft?.pending;
  const lastAssistant = draft ? [...draft.messages].reverse().find((m) => m.role === "assistant") : undefined;
  const latestInsight = draft ? [...draft.messages].reverse().find((m) => m.kind === "insight") : undefined;
  return (
    <>
      <VersionSwitch v={2} />
      <div className="page-title">בקשת הלוואה חדשה</div>
      <div className="card cv2" data-testid="apply-v2" data-draft={draft?.draft_id}>
        <div className="cv2-head">
          <img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="Jeen" />
          <span className="small bold">העוזר הדיגיטלי</span>
          {draft && draft.messages.some((m) => m.role === "user") && (
            <button className="link small cv2-restart" onClick={restart} disabled={busy} data-testid="cv2-restart">התחלה מחדש</button>
          )}
        </div>
        {draft && <Stages stages={draft.stages} />}
        <div className="chat-log cv2-log" ref={log} aria-live="polite" data-testid="cv2-log">
          {!draft && !error && <div className="bubble assistant"><span className="spinner" /></div>}
          {draft?.messages.map((m) => (
            <Message key={m.id} m={m} latest={m.id === latestInsight?.id}
              onAsk={(t) => send({ text: t }, t)} disabled={busy}
              actions={m.id === lastAssistant?.id ? m.actions : undefined}
              onAction={(a) => send({ question_id: a.question_id, value: a.value, label_he: a.label_he }, a.label_he)} />
          ))}
          {echo && <div className="bubble user">{echo}</div>}
          {busy && <div className="bubble assistant cv2-typing" aria-label="העוזר כותב"><i /><i /><i /></div>}
        </div>
        {draft?.status === "draft" && (
          <div className="cv2-composer" ref={composer}>
            {p && p.replies.length > 0 && (
              <div className="onb-replies cv2-replies" role="group" aria-label={p.prompt_he} data-testid="cv2-pending" data-question={p.question_id}>
                {p.replies.map((r) => (
                  <button key={r.label_he} className="onb-reply" disabled={busy} data-testid="cv2-reply" data-value={JSON.stringify(r.value)}
                    onClick={() => send({ question_id: p.question_id, value: r.value, label_he: r.label_he }, r.label_he)}>{r.label_he}</button>
                ))}
              </div>
            )}
            {p && p.replies.length === 0 && <span hidden data-testid="cv2-pending" data-question={p.question_id} />}
            <div className="cv2-suggest">
              {p?.editing && (
                <button className="cv2-chip cancel" disabled={busy} onClick={() => send({ action: "cancel_edit" }, "ביטול השינוי")}
                  data-testid="cv2-cancel-edit">ביטול השינוי</button>
              )}
              {draft.suggestions.map((s) => (
                <button key={s} className="cv2-chip" disabled={busy} onClick={() => send({ text: s }, s)} data-testid="cv2-suggestion">{s}</button>
              ))}
            </div>
            <form className="cv2-input" onSubmit={submit}>
              <input ref={input} className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={500}
                placeholder={p?.placeholder_he || "אפשר לשאול אותי כל שאלה על הבקשה…"} enterKeyHint="send" autoComplete="off"
                aria-label="הודעה לעוזר" data-testid="cv2-input" />
              <button className="cv2-send" disabled={busy || !text.trim()} aria-label="שליחה" data-testid="cv2-send"><ISend size={18} /></button>
            </form>
          </div>
        )}
        {error && <div className="notice" role="alert" style={{ margin: "8px 10px 0" }} data-testid="cv2-error">{error}</div>}
      </div>
      {draft?.summary && !p && <Summary draft={draft} busy={busy} onEdit={(q, label) => send({ question_id: q, action: "edit" }, `שינוי ${label}`)} onConfirm={confirm} />}
      <div className="tiny muted" style={{ marginTop: 10 }}>{draft?.note_he}</div>
    </>
  );
}

/** The assistant's next-step note on the Documents screen, shown once after a V2 application is opened. */
export function ApplyHandoff() {
  const loc = useLocation();
  const nav = useNavigate();
  const state = loc.state as { handoff?: string; first?: string | null } | null;
  if (state?.handoff !== "v2") return null;
  return (
    <div className="cv2-handoff" role="status" data-testid="cv2-handoff">
      <img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="" />
      <div className="grow">
        {state.first ? `${state.first}, ` : ""}סיימנו להכין את הבקשה שלך. עכשיו נעבור למסמכים שיעזרו לבנק לבדוק אותה —
        אפשר להעלות אותם כאן, ואני אעזור לך להבין אם משהו חסר. פתיחת הבקשה עדיין אינה אישור הלוואה.
      </div>
      <button className="link tiny" onClick={() => nav(loc.pathname, { replace: true, state: null })} aria-label="סגירה">הבנתי</button>
    </div>
  );
}

export function VersionSwitch({ v }: { v: 1 | 2 }) {
  return (
    <div className="cv2-switch" role="group" aria-label="גרסת השאלון">
      <Link to="/customer/apply" className={v === 1 ? "on" : ""} aria-current={v === 1 ? "page" : undefined} data-testid="apply-switch-v1">שאלון קלאסי</Link>
      <Link to="/customer/apply/v2" className={v === 2 ? "on" : ""} aria-current={v === 2 ? "page" : undefined} data-testid="apply-switch-v2">שיחה עם העוזר</Link>
    </div>
  );
}

function Stages({ stages }: { stages: ChatStage[] }) {
  const i = stages.findIndex((s) => s.state === "current");
  const cur = stages[i];
  const caption = !cur ? "" : cur.id === "summary" ? "כמעט סיימנו — נשאר לעבור על הסיכום ולאשר"
    : `שלב ${i + 1} מתוך ${stages.length} · ${cur.label_he}${cur.total > 1 ? ` · שאלה ${Math.min(cur.answered + 1, cur.total)} מתוך ${cur.total}` : ""}`;
  return (
    <div className="cv2-stages" data-testid="cv2-stages">
      <ol>
        {stages.map((s) => (
          <li key={s.id} className={s.state} data-testid={`cv2-stage-${s.id}`} data-state={s.state} aria-current={s.state === "current" ? "step" : undefined}>
            <span className="dot">{s.state === "done" ? <ICheck size={11} /> : null}</span>
            <span className="lbl">{s.label_he}</span>
          </li>
        ))}
      </ol>
      <div className="tiny muted cv2-caption" data-testid="cv2-caption">{caption}</div>
    </div>
  );
}

function Message({ m, latest, onAsk, disabled, actions, onAction }: {
  m: ChatMessage; latest: boolean; onAsk: (t: string) => void; disabled: boolean;
  actions?: ChatMessage["actions"]; onAction: (a: NonNullable<ChatMessage["actions"]>[number]) => void;
}) {
  if (m.role === "user") return <div className="bubble user" data-testid="cv2-msg" data-kind="user">{m.text_he}</div>;
  if (m.kind === "insight" && m.indication) {
    const ind = m.indication;
    return (
      <div className={`cv2-insight${m.stale ? " stale" : ""}`} data-testid="cv2-insight" data-stale={m.stale ? "1" : "0"} data-max={ind.max_amount_ils}>
        <div className="cv2-insight-eyebrow">
          <span>אינדיקציה ראשונית · הדגמה בלבד</span>
          {m.stale && <span className="badge neutral" data-testid="cv2-insight-stale">עודכנה</span>}
        </div>
        <div className="cv2-insight-figure"><span className="pre">עד כ־</span><b className="ltr">{ils(ind.max_amount_ils)}</b>
          <span className="post">ב־{ind.payments} תשלומים</span></div>
        <div className="cv2-insight-text">{m.text_he}</div>
        {latest && !m.stale && (
          <button className="cv2-chip" disabled={disabled} onClick={() => onAsk("איך הגעת לסכום הזה?")} data-testid="cv2-explain">איך הגעת לסכום הזה?</button>
        )}
      </div>
    );
  }
  return (
    <div className={`bubble assistant${m.kind === "withdrawn" ? " cv2-muted" : ""}${m.kind === "question" ? " cv2-question" : ""}${actions?.length ? " has-actions" : ""}`}
      data-testid="cv2-msg" data-kind={m.kind} data-question={m.question_id}>
      {m.text_he}
      {actions && actions.length > 0 && (
        <div className="cv2-actions">
          {actions.map((a) => <button key={a.label_he} className="onb-reply" disabled={disabled} onClick={() => onAction(a)} data-testid="cv2-action">{a.label_he}</button>)}
        </div>
      )}
    </div>
  );
}

function Summary({ draft, busy, onEdit, onConfirm }: { draft: ChatDraft; busy: boolean; onEdit: (q: string, label: string) => void; onConfirm: () => void }) {
  const s = draft.summary!;
  const owners = [...new Set(s.requirements.map((r) => r.owner_he || ""))];
  return (
    <section className="card onb-summary cv2-summary" data-testid="cv2-summary" data-entity={s.profile.entity}>
      <div className="card-title">סיכום הבקשה</div>
      <p className="small muted" style={{ margin: "4px 0 6px", lineHeight: 1.6 }}>{s.intro_he}</p>
      {s.lines.map((l) => (
        <div key={l.question_id} className="kv cv2-line" data-testid="cv2-line" data-question={l.question_id}>
          <span>{l.label_he}</span>
          <span><span className="cv2-val">{l.value_he}</span>
            <button className="link tiny cv2-edit" disabled={busy} onClick={() => onEdit(l.question_id, l.label_he)}
              data-testid={`cv2-edit-${l.question_id}`} aria-label={`שינוי ${l.label_he}`}>שינוי</button></span>
        </div>
      ))}
      {draft.indication && (
        <div className="cv2-summary-ind" data-testid="cv2-summary-indication">
          אינדיקציה ראשונית להמחשה: עד כ־<b className="ltr">{ils(draft.indication.max_amount_ils)}</b> ב־{draft.indication.payments} תשלומים,
          לפי ההכנסה שהצהרת והנחות הדמו. זו אינה הצעה ואינה אישור.
        </div>
      )}
      {s.profile.banker_assisted && (
        <div className="notice navy small" style={{ marginTop: 10 }} data-testid="cv2-banker-assisted">
          מסלול עסקי מוגבל: הבקשה מטופלת בליווי הבנקאית. כאן אוספים את מסמכי הזיהוי והדוחות — אין חיתום עסקי ואין החלטת אשראי אוטומטית.</div>
      )}
      <div className="section-label" style={{ margin: "14px 0 6px" }}>המסמכים שיידרשו ({s.requirements.length})</div>
      {owners.map((o) => (
        <div key={o} className="onb-owner">
          <div className="tiny bold muted">{o}</div>
          <ul className="onb-reqs">
            {s.requirements.filter((r) => (r.owner_he || "") === o).map((r) => (
              <li key={r.code} data-testid="cv2-req" data-code={r.code}>
                <span className="grow"><b>{r.title_he}</b>{r.why_he && <span className="tiny muted onb-why">{r.why_he}</span>}</span>
                <span className={`badge ${r.intake === "human_review" ? "neutral" : "jeen"}`}>{r.intake === "human_review" ? "בדיקת בנקאי" : "בדיקת AI"}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div className="tiny muted" style={{ lineHeight: 1.6, marginTop: 8 }}>
        פתיחת הבקשה אינה אישור הלוואה — היא מכינה את רשימת המסמכים לבדיקת הבנק. גרסת מדיניות: <span className="ltr">{s.policy_version}</span>.</div>
      <button className="btn btn-orange" style={{ width: "100%", marginTop: 12 }} disabled={busy} onClick={onConfirm} data-testid="cv2-confirm">
        {busy && <span className="spinner" />}אישור ופתיחת הבקשה</button>
    </section>
  );
}
