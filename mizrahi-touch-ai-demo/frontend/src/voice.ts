/**
 * Voice channel boundary. The assistant brain is the same for every channel: a voice turn
 * is posted to the same agent endpoint with channel="voice". Swapping the browser channel
 * for JEEN Talk replaces only this adapter.
 */
import { api } from "./api";

export interface VoiceCapability { stt: "browser" | "server" | "none"; tts: boolean; detail: string }
export interface VoiceChannel {
  id: "browser" | "jeen-talk";
  label: string;
  capability(): Promise<VoiceCapability>;
  listen(onPartial: (t: string) => void, onFinal: (t: string, meta: Record<string, unknown>) => void, onError: (e: string) => void): () => void;
  speak(text: string): Promise<void>;
  stopSpeaking(): void;
}

type SR = any;
const SRClass: SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

const voiceParam = new URLSearchParams(window.location.search).get("voice");
if (voiceParam) localStorage.setItem("mz.voice", voiceParam);

/** Re-encodes a MediaRecorder capture (webm/opus in Chrome) as 16 kHz mono PCM WAV, a format Gemini accepts. */
async function toWav(blob: Blob): Promise<Blob> {
  const ctx = new AudioContext();
  try {
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    const rate = 16000;
    const offline = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * rate)), rate);
    const src = offline.createBufferSource();
    src.buffer = decoded;
    src.connect(offline.destination);
    src.start();
    const pcm = (await offline.startRendering()).getChannelData(0);
    const view = new DataView(new ArrayBuffer(44 + pcm.length * 2));
    const ascii = (offset: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i)); };
    ascii(0, "RIFF"); view.setUint32(4, 36 + pcm.length * 2, true); ascii(8, "WAVE");
    ascii(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    ascii(36, "data"); view.setUint32(40, pcm.length * 2, true);
    for (let i = 0; i < pcm.length; i++) view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 0x7fff, true);
    return new Blob([view], { type: "audio/wav" });
  } finally {
    ctx.close();
  }
}

function hebrewVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis?.getVoices() || [];
  return voices.find((v) => v.lang?.toLowerCase().startsWith("he")) || voices.find((v) => /carmit/i.test(v.name));
}

async function browserSttAvailable(): Promise<boolean> {
  if (!SRClass) return false;
  if (typeof SRClass.available === "function") {
    try {
      const r = await SRClass.available({ langs: ["he-IL"], processLocally: false });
      return r === "available" || r === "downloadable" || r === true;
    } catch { return true; }
  }
  return true;
}

export class BrowserVoice implements VoiceChannel {
  id = "browser" as const;
  label = "קול בדפדפן";
  private sttMode: "browser" | "server" | "none" | null = null;

  async capability(): Promise<VoiceCapability> {
    if (window.speechSynthesis && !window.speechSynthesis.getVoices().length) {
      await new Promise((r) => { window.speechSynthesis.onvoiceschanged = () => r(null); setTimeout(r, 800); });
    }
    const tts = !!hebrewVoice();
    const forced = localStorage.getItem("mz.voice");
    const browser = forced === "server" ? false : await browserSttAvailable();
    const server = !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
    this.sttMode = browser ? "browser" : server ? "server" : "none";
    const detail = this.sttMode === "browser" ? "זיהוי דיבור עברי של הדפדפן" :
      this.sttMode === "server" ? "הקלטה ותמלול עברי בשרת JEEN" : "אין קלט קולי בדפדפן זה — אפשר להקליד";
    return { stt: this.sttMode, tts, detail: `${detail}${tts ? " · הקראה בקול עברי" : " · אין קול עברי להקראה"}` };
  }

  listen(onPartial: (t: string) => void, onFinal: (t: string, meta: Record<string, unknown>) => void, onError: (e: string) => void) {
    if (this.sttMode === "server") return this.listenServer(onPartial, onFinal, onError);
    if (!SRClass) { onError("זיהוי דיבור אינו זמין"); return () => {}; }
    const rec = new SRClass();
    rec.lang = "he-IL";
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = "";
    let confidence = 0;
    rec.onresult = (ev: any) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) { finalText += r[0].transcript; confidence = r[0].confidence; } else interim += r[0].transcript;
      }
      onPartial((finalText + interim).trim());
    };
    rec.onerror = (ev: any) => {
      if (ev.error === "language-not-supported" || ev.error === "network") {
        this.sttMode = "server";
        onError("זיהוי הדיבור של הדפדפן אינו זמין — עובר לתמלול בשרת. לחצו שוב על המיקרופון.");
      } else if (ev.error !== "no-speech" && ev.error !== "aborted") onError(`שגיאת מיקרופון: ${ev.error}`);
    };
    rec.onend = () => { if (finalText.trim()) onFinal(finalText.trim(), { source: "asr", engine: "browser-webspeech-he-IL", confidence }); };
    rec.start();
    return () => { try { rec.stop(); } catch { /* already stopped */ } };
  }

  private listenServer(onPartial: (t: string) => void, onFinal: (t: string, meta: Record<string, unknown>) => void, onError: (e: string) => void) {
    let recorder: MediaRecorder | null = null;
    let stream: MediaStream | null = null;
    const chunks: Blob[] = [];
    let stopped = false;
    navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => {
      stream = s;
      recorder = new MediaRecorder(s);
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = async () => {
        stream?.getTracks().forEach((t) => t.stop());
        onPartial("מתמלל…");
        try {
          const captured = new Blob(chunks, { type: recorder?.mimeType || "audio/webm" });
          const r = await api.transcribe(await toWav(captured).catch(() => captured));
          if (r.text) onFinal(r.text, { source: "asr", engine: r.engine, latency_ms: r.latency_ms });
          else onError("לא זוהה דיבור");
        } catch { onError("לא הצלחתי לתמלל את ההקלטה — נסו שוב או הקלידו את השאלה"); }
      };
      recorder.start();
      if (stopped) recorder.stop();
    }).catch(() => onError("אין הרשאה למיקרופון"));
    return () => { stopped = true; if (recorder && recorder.state !== "inactive") recorder.stop(); };
  }

  speak(text: string): Promise<void> {
    return new Promise((resolve) => {
      if (!window.speechSynthesis) return resolve();
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[*#•]/g, ""));
      const v = hebrewVoice();
      if (v) u.voice = v;
      u.lang = "he-IL";
      u.rate = 1.02;
      u.onend = () => resolve();
      u.onerror = () => resolve();
      window.speechSynthesis.speak(u);
    });
  }

  stopSpeaking() { window.speechSynthesis?.cancel(); }
}

/** JEEN Talk slot — becomes active when JEEN Talk credentials and an agent with the Case MCP tools exist. */
export class JeenTalkVoice implements VoiceChannel {
  id = "jeen-talk" as const;
  label = "JEEN Talk";
  async capability(): Promise<VoiceCapability> {
    return { stt: "none", tts: false, detail: "JEEN Talk אינו מחובר בסביבה זו — נדרשים כתובת, מפתח Developer API וסוכן עברי" };
  }
  listen(_p: (t: string) => void, _f: (t: string, m: Record<string, unknown>) => void, onError: (e: string) => void) {
    onError("JEEN Talk אינו מחובר");
    return () => {};
  }
  async speak() { /* not connected */ }
  stopSpeaking() { /* not connected */ }
}

export const voice: VoiceChannel = new BrowserVoice();
