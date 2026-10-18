import { useEffect, useRef, useState } from "react";
import { api, timeHe, timeL, type Turn } from "../api";
import { useCase } from "../caseContext";
import { tr, useLang } from "../i18n";
import { voice, type VoiceCapability } from "../voice";
import { ActionList } from "./AssistantActions";
import { IClose, IMic, ISend, ISpeaker } from "./Icons";

const TOOL_HE: Record<string, string> = {
  get_case_overview: "מצב התיק", list_documents: "רשימת מסמכים", get_document_review: "תוצאת בדיקת מסמך",
  list_open_items: "פריטים פתוחים", get_upload_guidance: "הנחיות העלאה", explain_finding: "פירוט ממצא",
  get_review_history: "היסטוריית בדיקות", record_customer_statement: "תיעוד הסבר", request_banker_handoff: "העברה לבנקאית",
  request_revalidation: "בדיקה חוזרת",
};
const TOOL_EN: Record<string, string> = {
  get_case_overview: "Application status", list_documents: "Document list", get_document_review: "Document check result",
  list_open_items: "Open items", get_upload_guidance: "Upload guidance", explain_finding: "Finding details",
  get_review_history: "Check history", record_customer_statement: "Recording an explanation", request_banker_handoff: "Passing to the banker",
  request_revalidation: "Re-check",
};
const SUGGESTIONS = ["מה חסר כדי להתקדם בבקשת ההלוואה?", "למה התלוש של ספטמבר לא נספר?", "אילו דפי עו״ש צריך להעלות?", "איך מעלים את המסמך החסר?", "אני רוצה לדבר עם הבנקאית"];
const SUGGESTIONS_EN = ["What's missing to move my loan application forward?", "Why wasn't the September payslip counted?",
  "Which bank statements do I need to upload?", "How do I upload the missing document?", "I'd like to talk to my banker"];
const CHANNEL_HE: Record<string, string> = { text: "צ׳אט", voice: "קול", app: "עדכון מהתיק" };
const CHANNEL_EN: Record<string, string> = { text: "Chat", voice: "Voice", app: "Application update" };
/** The transcription engine id the server records ("gemini:<model>", "browser-webspeech-he-IL") is internal; customers see who transcribed. */
const engineHe = (engine: string) => (engine.startsWith("browser") ? tr("הדפדפן", "the browser") : "JEEN");
/** A turn's text in the app's language: a follow-up from the case service carries both languages; anything else is
 *  shown as it was written, in its own direction. */
const turnText = (t: Turn, en: boolean) => (en && t.provenance?.text_en) || t.text;
const turnDir = (t: Turn, en: boolean) => (en ? (t.provenance?.text_en ? "ltr" : "auto") : t.provenance?.lang === "en" ? "ltr" : undefined);

/** the voice capability line in English, from the same capability the Hebrew line describes */
const voiceDetailEn = (cap: VoiceCapability) => `${cap.stt === "browser" ? "the browser's speech recognition" : cap.stt === "server"
  ? "recording and transcription on the JEEN server" : "no voice input in this browser — you can type"}${cap.tts ? " · spoken replies" : " · no voice for spoken replies"}`;

function sourcesOf(t: Turn): string[] {
  if (t.role !== "assistant") return [];
  const names = tr(TOOL_HE, TOOL_EN);
  const out = (t.tool_calls || []).filter((c) => c.name !== "offer_app_actions").map((c) => `${names[c.name] || c.name}${c.ok ? "" : " ✕"}`);
  if (t.channel === "app") out.push(tr("תוצאות הבדיקה ומצב התיק", "Check results and application status"));
  if (t.provenance?.fallback) out.push(tr("מנתוני התיק ללא מודל", "From application data, without a model"));
  if (t.provenance?.guard?.blocked) out.push(tr("מסנן בטיחות", "Safety filter"));
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
  const { en, t: tl } = useLang();

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
      setTurns((t) => [...t, { turn_id: `err-${Date.now()}`, channel, role: "assistant", text: tr(`לא הצלחתי לענות כרגע (${(e as Error).message}).`, `I couldn't answer right now (${(e as Error).message}).`), created_at: new Date().toISOString() }]);
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
      <div className="sheet" style={{ height: "88%" }} onClick={(e) => e.stopPropagation()} role="dialog" aria-label={tl("עוזר המסמכים", "Document assistant")}>
        <div className="grabber" />
        <div className="sheet-head">
          <div>
            <h3 className="row" style={{ gap: 8 }}><img className="jeen-logo-inline" src="/brand/jeen-logo.png" alt="Jeen" />{tl("עוזר המסמכים", "Document assistant")}</h3>
            <div className="tiny muted">{en ? <>{snap?.case.banker.name_en || snap?.case.banker.name_he || "Your banker"}&apos;s assistant · answers from your application&apos;s data only · doesn&apos;t decide on the loan</>
              : <>עוזר של {snap?.case.banker.name_he || "הבנקאית"} · עונה מנתוני התיק בלבד · לא מחליט על ההלוואה</>}</div>
          </div>
          <button className="icon-btn" onClick={closeAssistant} aria-label={tl("סגירה", "Close")}><IClose /></button>
        </div>
        <div className="chat" style={{ minHeight: 0, flex: 1 }}>
          <div className="chat-log" ref={log} data-testid="chat-log">
            {turns.length === 0 && (
              <div className="bubble assistant">{tl("שלום! אני עוזר המסמכים של טפחות טאצ׳. אפשר לשאול אותי בכתב או בקול מה חסר בתיק, מה נמצא בבדיקת המסמכים ואיך מתקנים, ואעביר לבנקאית כל מה שדורש החלטה אנושית.",
                "Hello! I'm the Tefahot Touch document assistant. Ask me in writing or by voice what's missing in your application, what the document check found and how to fix it — and I'll pass anything that needs a human decision to your banker.")}</div>
            )}
            {turns.map((t) => {
              const actions = t.role === "assistant" ? t.actions ?? [] : [];
              const sources = sourcesOf(t);
              return (
                <div key={t.turn_id} className={`bubble ${t.role}${t.channel === "app" ? " app" : ""}${actions.length ? " has-actions" : ""}`}
                  data-role={t.role} data-channel={t.channel} data-turn-id={t.turn_id}>
                  <div className="bubble-text" dir={turnDir(t, en)}>{turnText(t, en)}</div>
                  {actions.length > 0 && (
                    <ActionList actions={actions} turnId={t.turn_id} say={(m, p) => send(m, "text", p)} emphasize={t.turn_id === latestActions} />
                  )}
                  <div className="bubble-meta">
                    <span>{(en ? CHANNEL_EN : CHANNEL_HE)[t.channel] || tl("צ׳אט", "Chat")}</span>
                    <span>{(en ? timeL : timeHe)(t.created_at).split("|")[1]}</span>
                    {t.role === "user" && t.provenance?.engine && <span>{tl("תמלול: ", "Transcribed by ")}{engineHe(String(t.provenance.engine))}</span>}
                    {t.role === "user" && t.provenance?.source === "app_action" && <span>{tl("נשלח מכפתור", "Sent from a button")}</span>}
                    {t.role === "assistant" && cap?.tts && <button className="link tiny" onClick={() => voice.speak(turnText(t, en))} aria-label={tl("השמעה", "Play")}><ISpeaker size={12} /></button>}
                  </div>
                  {sources.length > 0 && <div className="bubble-sources">{t.channel === "app" ? tl("מקור", "Source") : tl("נבדק מול", "Checked against")}: {sources.join(" · ")}</div>}
                </div>
              );
            })}
            {(processing.length > 0 || working) && (
              <div className="chat-status" role="status" data-testid="chat-review-status">
                <span className="spinner" />
                {en ? (processing.length ? `Checking ${processing.length === 1 ? processing[0].filename : `${processing.length} documents`} · ${processing[0].stage_en || processing[0].stage_he || "checking"}`
                  : "Updating the picture of your application's documents…")
                  : processing.length ? `בודקים ${processing.length === 1 ? processing[0].filename : `${processing.length} מסמכים`} · ${processing[0].stage_he || "בבדיקה"}`
                  : "מעדכנים את תמונת המסמכים בתיק…"}
              </div>
            )}
            {(sending || partial) && <div className={`bubble ${partial && !sending ? "user" : "assistant"}`}>{partial && !sending ? partial : <span className="spinner" />}</div>}
          </div>
          <div className="suggestions">
            {(en ? SUGGESTIONS_EN : SUGGESTIONS).map((sug) => <button key={sug} onClick={() => send(sug, "text")} disabled={sending}>{sug}</button>)}
          </div>
          <div className="voice-status">
            {en ? (listening ? "Listening… speak in English and tap again to finish" : voiceNote || (cap ? `Voice: ${voiceDetailEn(cap)}` : "Checking voice support…"))
              : listening ? "מקשיב… דברו בעברית ולחצו שוב לסיום" : voiceNote || (cap ? `קול: ${cap.detail}` : "בודק יכולות קול…")} · {cap?.stt === "server" ? <span className="mode LIVE">VOICE: JEEN STT</span> : <span className="mode LOCAL">VOICE: BROWSER</span>} <span className="mode BLOCKED">JEEN TALK</span>
          </div>
          <div className="chat-input">
            <button className={`round mic ${listening ? "live" : ""}`} onClick={toggleMic} disabled={!cap || cap.stt === "none" || sending}
              aria-label={listening ? tl("סיום הקלטה", "Stop recording") : tl("דברו עם העוזר", "Talk to the assistant")} data-testid="mic"><IMic /></button>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={tl("כתבו שאלה על התיק…", "Ask about your application…")} rows={1} data-testid="chat-input"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text, "text"); } }} />
            <button className="round send" onClick={() => send(text, "text")} disabled={!text.trim() || sending} aria-label={tl("שליחה", "Send")} data-testid="chat-send"><ISend /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
