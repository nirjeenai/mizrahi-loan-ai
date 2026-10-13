import { useEffect, useRef, useState } from "react";
import { api, timeHe, type Turn } from "../api";
import { useCase } from "../caseContext";
import { voice, type VoiceCapability } from "../voice";
import { ActionList } from "./AssistantActions";
import { IClose, IMic, ISend, ISpeaker } from "./Icons";

const TOOL_HE: Record<string, string> = {
  get_case_overview: "מצב התיק", list_documents: "רשימת מסמכים", get_document_review: "תוצאת בדיקת מסמך",
  list_open_items: "פריטים פתוחים", get_upload_guidance: "הנחיות העלאה", explain_finding: "פירוט ממצא",
  get_review_history: "היסטוריית בדיקות", record_customer_statement: "תיעוד הסבר", request_banker_handoff: "העברה לבנקאית",
  request_revalidation: "בדיקה חוזרת",
};
const SUGGESTIONS = ["מה חסר כדי להתקדם?", "למה התלוש של ספטמבר לא נספר?", "יש בעיה בהכנסה של נועה?", "איך מעלים את התלוש החסר?", "אני רוצה לדבר עם הבנקאית"];
const CHANNEL_HE: Record<string, string> = { text: "צ׳אט", voice: "קול", app: "עדכון מהתיק" };

function sourcesOf(t: Turn): string[] {
  if (t.role !== "assistant") return [];
  const out = (t.tool_calls || []).filter((c) => c.name !== "offer_app_actions").map((c) => `${TOOL_HE[c.name] || c.name}${c.ok ? "" : " ✕"}`);
  if (t.channel === "app") out.push("תוצאות הבדיקה ומצב התיק");
  if (t.provenance?.fallback) out.push("מנתוני התיק ללא מודל");
  if (t.provenance?.guard?.blocked) out.push("מסנן בטיחות");
  return [...new Set(out)];
}

export function AssistantSheet() {
  const { caseId, closeAssistant, assistant, reload, snap, docs } = useCase();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState(assistant.prompt || "");
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);
  const [partial, setPartial] = useState("");
  const [cap, setCap] = useState<VoiceCapability | null>(null);
  const [voiceNote, setVoiceNote] = useState<string | null>(null);
  const stopRef = useRef<() => void>(() => {});
  const log = useRef<HTMLDivElement>(null);

  const working = (snap?.readiness.pending_jobs.length ?? 0) > 0;
  const wasWorking = useRef(working);
  const processing = docs.filter((d) => d.status === "queued" || d.status === "processing");
  const latestActions = [...turns].reverse().find((t) => t.role === "assistant" && (t.actions?.length ?? 0) > 0)?.turn_id;

  useEffect(() => { api.conversation(caseId).then(setTurns); voice.capability().then(setCap); return () => voice.stopSpeaking(); }, [caseId]);
  useEffect(() => {
    if (wasWorking.current && !working) api.conversation(caseId).then(setTurns).catch(() => {});
    wasWorking.current = working;
  }, [working, caseId]);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [turns, sending, partial]);

  const send = async (message: string, channel: "text" | "voice", provenance?: Record<string, unknown>) => {
    const clean = message.trim();
    if (!clean || sending) return;
    setSending(true); setText(""); setPartial("");
    const optimistic: Turn = { turn_id: `tmp-${Date.now()}`, channel, role: "user", text: clean, created_at: new Date().toISOString(), provenance };
    setTurns((t) => [...t, optimistic]);
    try {
      const r = await api.send(caseId, clean, channel, provenance);
      setTurns(await api.conversation(caseId));
      reload();
      if (channel === "voice" && cap?.tts) voice.speak(r.reply);
    } catch (e) {
      setTurns((t) => [...t, { turn_id: `err-${Date.now()}`, channel, role: "assistant", text: `לא הצלחתי לענות כרגע (${(e as Error).message}).`, created_at: new Date().toISOString() }]);
    } finally { setSending(false); }
  };

  const toggleMic = () => {
    if (listening) { stopRef.current(); setListening(false); return; }
    voice.stopSpeaking();
    setVoiceNote(null);
    setListening(true);
    stopRef.current = voice.listen(
      (p) => setPartial(p),
      (finalText, meta) => { setListening(false); send(finalText, "voice", meta); },
      (err) => { setListening(false); setPartial(""); setVoiceNote(err); voice.capability().then(setCap); },
    );
  };

  return (
    <div className="sheet-backdrop" onClick={closeAssistant}>
      <div className="sheet" style={{ height: "88%" }} onClick={(e) => e.stopPropagation()} role="dialog" aria-label="עוזר המסמכים">
        <div className="grabber" />
        <div className="sheet-head">
          <div>
            <h3 className="row" style={{ gap: 8 }}><img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="Jeen" />עוזר המסמכים</h3>
            <div className="tiny muted">עוזר של {snap?.case.banker.name_he || "מומחית המשכנתאות"} · עונה מנתוני התיק בלבד · לא מחליט על המשכנתא</div>
          </div>
          <button className="icon-btn" onClick={closeAssistant} aria-label="סגירה"><IClose /></button>
        </div>
        <div className="chat" style={{ minHeight: 0, flex: 1 }}>
          <div className="chat-log" ref={log} data-testid="chat-log">
            {turns.length === 0 && (
              <div className="bubble assistant">שלום! אני עוזר המסמכים של טפחות טאצ׳. אפשר לשאול אותי בכתב או בקול מה חסר בתיק, מה נמצא בבדיקת המסמכים ואיך מתקנים — ואעביר לבנקאית כל מה שדורש החלטה אנושית.</div>
            )}
            {turns.map((t) => {
              const actions = t.role === "assistant" ? t.actions ?? [] : [];
              const sources = sourcesOf(t);
              return (
                <div key={t.turn_id} className={`bubble ${t.role}${t.channel === "app" ? " app" : ""}${actions.length ? " has-actions" : ""}`}
                  data-role={t.role} data-channel={t.channel} data-turn-id={t.turn_id}>
                  <div className="bubble-text">{t.text}</div>
                  {actions.length > 0 && (
                    <ActionList actions={actions} turnId={t.turn_id} say={(m, p) => send(m, "text", p)} emphasize={t.turn_id === latestActions} />
                  )}
                  <div className="bubble-meta">
                    <span>{CHANNEL_HE[t.channel] || "צ׳אט"}</span>
                    <span>{timeHe(t.created_at).split("|")[1]}</span>
                    {t.role === "user" && t.provenance?.engine && <span>תמלול: {String(t.provenance.engine)}</span>}
                    {t.role === "user" && t.provenance?.source === "app_action" && <span>נשלח מכפתור</span>}
                    {t.role === "assistant" && cap?.tts && <button className="link tiny" onClick={() => voice.speak(t.text)} aria-label="השמעה"><ISpeaker size={12} /></button>}
                  </div>
                  {sources.length > 0 && <div className="bubble-sources">{t.channel === "app" ? "מקור" : "נבדק מול"}: {sources.join(" · ")}</div>}
                </div>
              );
            })}
            {(processing.length > 0 || working) && (
              <div className="chat-status" role="status" data-testid="chat-review-status">
                <span className="spinner" />
                {processing.length ? `בודקים ${processing.length === 1 ? processing[0].filename : `${processing.length} מסמכים`} · ${processing[0].stage_he || "בבדיקה"}`
                  : "מעדכנים את תמונת מסמכי השכר בתיק…"}
              </div>
            )}
            {(sending || partial) && <div className={`bubble ${partial && !sending ? "user" : "assistant"}`}>{partial && !sending ? partial : <span className="spinner" />}</div>}
          </div>
          <div className="suggestions">
            {SUGGESTIONS.map((sug) => <button key={sug} onClick={() => send(sug, "text")} disabled={sending}>{sug}</button>)}
          </div>
          <div className="voice-status">
            {listening ? "מקשיב… דברו בעברית ולחצו שוב לסיום" : voiceNote || (cap ? `קול: ${cap.detail}` : "בודק יכולות קול…")} · {cap?.stt === "server" ? <span className="mode LIVE">VOICE: GEMINI STT</span> : <span className="mode LOCAL">VOICE: BROWSER</span>} <span className="mode BLOCKED">JEEN TALK</span>
          </div>
          <div className="chat-input">
            <button className={`round mic ${listening ? "live" : ""}`} onClick={toggleMic} disabled={!cap || cap.stt === "none" || sending}
              aria-label={listening ? "סיום הקלטה" : "דברו עם העוזר"} data-testid="mic"><IMic /></button>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="כתבו שאלה על התיק…" rows={1} data-testid="chat-input"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text, "text"); } }} />
            <button className="round send" onClick={() => send(text, "text")} disabled={!text.trim() || sending} aria-label="שליחה" data-testid="chat-send"><ISend /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
