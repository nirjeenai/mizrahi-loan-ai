import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/* Customer presence for the follow-up engine (CONTRACTS §8): the server decides from these events whether the customer
   is on the screen that fixes an open task, elsewhere in the app, uploading, idle or gone — and never contacts a
   customer who is busy resolving the issue. One session per tab; `seq` orders the events; the end goes by beacon. */
type Screen = "home" | "documents" | "document" | "other";
export type PresenceEvent = "session_started" | "heartbeat" | "user_activity" | "file_picker_opened" | "upload_started"
  | "upload_completed" | "session_resumed" | "session_ended";

const SESSION = `tab-${Math.random().toString(36).slice(2, 12)}`;
const HEARTBEAT_MS = 30_000;
const ACTIVITY_THROTTLE_MS = 15_000;
let seq = 0;
let current: { caseId: string; screen: Screen; requirement?: string } | null = null;

const screenOf = (path: string): Screen =>
  path === "/customer" || path === "/customer/" ? "home"
    : /^\/customer\/documents\/[^/]+/.test(path) ? "document"
      : path.startsWith("/customer/documents") ? "documents" : "other";

const ACTIVITY: PresenceEvent[] = ["user_activity", "file_picker_opened", "upload_started", "upload_completed"];
let ended = false;            // the server ended this tab's session (it left, or the presenter said so): activity resumes it

/** Send one presence event for the case on screen (no-op outside the customer app). Never throws. */
export function reportPresence(event: PresenceEvent, requirementCode?: string): void {
  if (!current) return;
  const sent: PresenceEvent = ended && ACTIVITY.includes(event) ? "session_resumed" : event;
  const body = JSON.stringify({ session_id: SESSION, event: sent, seq: ++seq, visible: document.visibilityState === "visible",
    screen: current.screen, requirement_code: requirementCode ?? current.requirement ?? null });
  const url = `/api/cases/${encodeURIComponent(current.caseId)}/presence`;
  if (event === "session_ended" && navigator.sendBeacon) {
    navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
    return;
  }
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body, credentials: "same-origin", keepalive: true })
    .then((r) => (r.ok ? r.json() : null))
    .then((r: { state?: string } | null) => {
      if (!r?.state) return;
      ended = r.state === "ENDED" || r.state === "NONE";
      if (ended && ACTIVITY.includes(sent)) reportPresence("session_resumed");     // came back to a session the server closed
    })
    .catch(() => undefined);
}

/** Mount once in the customer shell, for the signed-in case. */
export function usePresence(caseId: string, active: boolean): void {
  const { pathname } = useLocation();
  useEffect(() => {
    if (!active) return;
    current = { caseId, screen: screenOf(pathname) };
    reportPresence("session_started");
    let lastActivity = Date.now();
    const beat = window.setInterval(() => reportPresence("heartbeat"), HEARTBEAT_MS);
    const activity = (e: Event) => {
      // the presenter pane beside the phone is not the customer
      if (e.target instanceof Element && e.target.closest(".hub-side")) return;
      if (Date.now() - lastActivity < ACTIVITY_THROTTLE_MS && !ended) return;
      lastActivity = Date.now();
      reportPresence("user_activity");
    };
    const visibility = () => reportPresence(document.visibilityState === "visible" ? "session_resumed" : "heartbeat");
    const leave = () => reportPresence("session_ended");
    window.addEventListener("pointerdown", activity);
    window.addEventListener("keydown", activity);
    window.addEventListener("scroll", activity, true);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", leave);
    return () => {
      window.clearInterval(beat);
      window.removeEventListener("pointerdown", activity);
      window.removeEventListener("keydown", activity);
      window.removeEventListener("scroll", activity, true);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", leave);
      reportPresence("session_ended");
      current = null;
    };
  }, [caseId, active]);
  useEffect(() => {
    if (!active || !current) return;
    current = { ...current, screen: screenOf(pathname) };
    reportPresence("user_activity");
  }, [pathname, active]);
}
