import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ils, type OnboardingDraft, type OnboardingQuestion } from "../../api";
import { useCase } from "../../caseContext";
import { ICheck } from "../../components/Icons";
import { VersionSwitch } from "./ApplyV2";

const DRAFT_KEY = "mz.onboarding.draft.v1";

/** A new loan application: JEEN asks a few deterministic questions (server-side draft, resumable), shows the profile and
 *  the documents the demo policy composes for it, and creates the case only when the customer confirms. Nothing here is
 *  an eligibility check, and no model decides which documents are required. */
export function Apply() {
  const { openCase } = useCase();
  const nav = useNavigate();
  const [draft, setDraft] = useState<OnboardingDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const log = useRef<HTMLDivElement>(null);

  const fresh = async () => {
    const d = await api.onboardingStart();
    localStorage.setItem(DRAFT_KEY, d.draft_id);
    setDraft(d);
  };
  useEffect(() => {
    const saved = localStorage.getItem(DRAFT_KEY);
    (saved ? api.onboarding(saved).catch(() => null) : Promise.resolve(null))
      .then((d) => (d && d.status === "draft" ? setDraft(d) : fresh()))
      .catch(() => setError("פתיחת בקשה חדשה אינה זמינה בסביבה זו."));
  }, []);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [draft]);
  const complete = !!draft?.summary;
  useEffect(() => {
    if (complete) requestAnimationFrame(() => document.querySelector("[data-testid=onb-summary]")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [complete]);

  const answer = async (questionId: string, value: unknown) => {
    if (!draft || busy) return;
    setBusy(true); setError(null);
    try { setDraft(await api.onboardingAnswer(draft.draft_id, questionId, value)); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!draft || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await api.onboardingConfirm(draft.draft_id);
      localStorage.removeItem(DRAFT_KEY);
      openCase(r.case_id);
      nav("/customer/documents");
    } catch (e) { setError((e as Error).message); setBusy(false); }
  };
  const restart = async () => { setBusy(true); setError(null); try { await fresh(); } finally { setBusy(false); } };

  return (
    <>
      <VersionSwitch v={1} />
      <div className="page-title">בקשת הלוואה חדשה</div>
      <p className="page-sub">כמה שאלות קצרות, ואחריהן נציג בדיוק אילו מסמכים נדרשים — לפני שהבקשה נפתחת.</p>
      <div className="card onb" data-testid="apply-chat" data-draft={draft?.draft_id}>
        <div className="onb-head">
          <img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="Jeen" />
          <span className="small bold">שאלון פתיחת בקשה</span>
          {draft && draft.asked.length > 0 && (
            <button className="link small onb-restart" onClick={restart} disabled={busy} data-testid="onb-restart">התחלה מחדש</button>
          )}
        </div>
        <div className="chat-log onb-log" ref={log}>
          {!draft && !error && <div className="bubble assistant"><span className="spinner" /></div>}
          {draft?.asked.map((a) => (
            <div key={a.question_id} className="onb-pair" data-testid={`onb-answered-${a.question_id}`}>
              <div className="bubble assistant">{a.prompt_he}</div>
              <div className="bubble user onb-answer">
                <span>{a.answer_he}</span>
                {!busy && <button className="onb-edit" onClick={() => answer(a.question_id, null)} data-testid={`onb-edit-${a.question_id}`}
                  aria-label={`שינוי התשובה: ${a.prompt_he}`}>שינוי</button>}
              </div>
            </div>
          ))}
          {draft?.next && <div className="bubble assistant" data-testid="onb-question" data-question={draft.next.question_id}>{draft.next.prompt_he}</div>}
          {busy && <div className="bubble assistant"><span className="spinner" /></div>}
        </div>
        {draft?.next && <QuestionInput key={draft.next.question_id} q={draft.next} disabled={busy} onAnswer={(v) => answer(draft.next!.question_id, v)} />}
        {error && <div className="notice" role="alert" style={{ margin: "8px 0 0" }}>{error}</div>}
      </div>
      {draft?.summary && <Summary draft={draft} busy={busy} onConfirm={confirm} />}
      <div className="tiny muted" style={{ marginTop: 10 }}>{draft?.note_he} בקשת הדגמה עם נתונים סינתטיים — אינה מגיעה לבנק.</div>
    </>
  );
}

function QuestionInput({ q, disabled, onAnswer }: { q: OnboardingQuestion; disabled: boolean; onAnswer: (v: unknown) => void }) {
  const [picked, setPicked] = useState<(string | number)[]>([]);
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [text, setText] = useState("");
  if (q.kind === "choice") {
    return (
      <div className="onb-replies" role="group" aria-label={q.prompt_he}>
        {q.options.map((o) => (
          <button key={String(o.value)} className="onb-reply" disabled={disabled} onClick={() => onAnswer(o.value)}
            data-testid="onb-option" data-value={String(o.value)}>{o.label_he}</button>
        ))}
      </div>
    );
  }
  if (q.kind === "multi") {
    const toggle = (v: string | number) => setPicked((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]));
    return (
      <div className="onb-replies" role="group" aria-label={q.prompt_he}>
        {q.options.map((o) => (
          <button key={String(o.value)} className={`onb-reply${picked.includes(o.value) ? " on" : ""}`} aria-pressed={picked.includes(o.value)}
            disabled={disabled} onClick={() => toggle(o.value)} data-testid="onb-option" data-value={String(o.value)}>
            {picked.includes(o.value) && <ICheck size={12} />}{o.label_he}</button>
        ))}
        <button className="btn btn-orange onb-send" disabled={disabled || !picked.length}
          onClick={() => onAnswer(q.options.map((o) => o.value).filter((v) => picked.includes(v)))} data-testid="onb-send">המשך</button>
      </div>
    );
  }
  if (q.kind === "name") {
    const ok = first.trim().length > 1 && last.trim().length > 1;
    return (
      <form className="onb-form" onSubmit={(e) => { e.preventDefault(); if (ok) onAnswer({ first, last }); }}>
        <input className="input" placeholder="שם פרטי" value={first} onChange={(e) => setFirst(e.target.value)} data-testid="onb-first" autoFocus />
        <input className="input" placeholder="שם משפחה" value={last} onChange={(e) => setLast(e.target.value)} data-testid="onb-last" />
        <button className="btn btn-orange onb-send" disabled={disabled || !ok} data-testid="onb-send">המשך</button>
      </form>
    );
  }
  if (q.kind === "number") {
    return (
      <div className="onb-replies">
        {q.options.map((o) => (
          <button key={String(o.value)} className="onb-reply" disabled={disabled} onClick={() => onAnswer(o.value)}
            data-testid="onb-option" data-value={String(o.value)}>{o.label_he}</button>
        ))}
        <form className="onb-form inline" onSubmit={(e) => { e.preventDefault(); if (text) onAnswer(Number(text)); }}>
          <input className="input ltr" type="number" min={0} placeholder="סכום אחר" value={text} onChange={(e) => setText(e.target.value)}
            data-testid="onb-number" />
          <button className="btn btn-ghost onb-send" disabled={disabled || !text} data-testid="onb-send">אישור</button>
        </form>
      </div>
    );
  }
  return (
    <form className="onb-form" onSubmit={(e) => { e.preventDefault(); if (text.trim().length > 1) onAnswer(text); }}>
      <input className="input" value={text} onChange={(e) => setText(e.target.value)} data-testid="onb-text" autoFocus />
      <button className="btn btn-orange onb-send" disabled={disabled || text.trim().length < 2} data-testid="onb-send">המשך</button>
    </form>
  );
}

function Summary({ draft, busy, onConfirm }: { draft: OnboardingDraft; busy: boolean; onConfirm: () => void }) {
  const s = draft.summary!;
  const p = s.profile;
  const owners = [...new Set(s.requirements.map((r) => r.owner_he || ""))];
  return (
    <section className="card onb-summary" data-testid="onb-summary" data-entity={p.entity}>
      <div className="card-title">סיכום הבקשה</div>
      <div className="kv"><span>סוג הבקשה</span><span>{p.entity_he}</span></div>
      {p.company && <div className="kv"><span>החברה</span><span>{p.company.name_he}</span></div>}
      {p.applicants.map((a) => (
        <div key={a.borrower_id} className="kv" data-testid="onb-applicant"><span>{a.role_he}</span><span>{a.name_he} · {a.profile_he}</span></div>
      ))}
      <div className="kv"><span>מטרה</span><span>{s.loan.purpose_he} · <span className="ltr">{ils(s.loan.requested_amount_ils)}</span> · {s.loan.payments} תשלומים</span></div>
      {p.banker_assisted && (
        <div className="notice navy small" style={{ marginTop: 10 }} data-testid="onb-banker-assisted">
          מסלול עסקי מוגבל: הבקשה מטופלת בליווי הבנקאית. כאן אוספים את מסמכי הזיהוי והדוחות — אין חיתום עסקי ואין החלטת אשראי אוטומטית.</div>
      )}
      <div className="section-label" style={{ margin: "14px 0 6px" }}>המסמכים שיידרשו ({s.requirements.length})</div>
      {owners.map((o) => (
        <div key={o} className="onb-owner">
          <div className="tiny bold muted">{o}</div>
          <ul className="onb-reqs">
            {s.requirements.filter((r) => (r.owner_he || "") === o).map((r) => (
              <li key={r.code} data-testid="onb-req" data-code={r.code} data-intake={r.intake}>
                <span className="grow"><b>{r.title_he}</b>{r.why_he && <span className="tiny muted onb-why">{r.why_he}</span>}</span>
                <span className={`badge ${r.intake === "human_review" ? "neutral" : "jeen"}`}>{r.intake === "human_review" ? "בדיקת בנקאי" : "בדיקת AI"}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div className="tiny muted" style={{ lineHeight: 1.6, marginTop: 8 }}>{p.disclaimer_he} גרסת מדיניות: <span className="ltr">{s.policy_version}</span>.
        אפשר לשנות כל תשובה למעלה לפני האישור.</div>
      <button className="btn btn-orange" style={{ width: "100%", marginTop: 12 }} disabled={busy} onClick={onConfirm} data-testid="onb-confirm">
        {busy && <span className="spinner" />}אישור ופתיחת הבקשה</button>
    </section>
  );
}
