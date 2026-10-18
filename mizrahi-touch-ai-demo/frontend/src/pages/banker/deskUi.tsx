import { useEffect, useState, type ReactNode } from "react";
import { timeL } from "../../api";

/** One id per form submission: a double click or a retry is recognised by the service as the same decision. */
export function newRequestId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `req-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function Chip({ tone = "neutral", children, testId, title }: { tone?: string; children: ReactNode; testId?: string; title?: string }) {
  return <span className={`chip ${tone}`} data-testid={testId} title={title}>{children}</span>;
}

export const VERDICT_TONE: Record<string, string> = { VALID: "ok", NEEDS_REVIEW: "warn", INVALID: "bad" };
export const BANKER_TONE: Record<string, string> = {
  AWAITING_DECISION: "navy", AWAITING_CUSTOMER_FIX: "warn", ACCEPTED: "ok", CORRECTION_REQUESTED: "warn", ESCALATED: "info",
  REPLACED: "neutral", PROCESSING: "neutral", FAILED: "bad",
};

export function Toast({ message, onClose }: { message: { text: string; tone: "ok" | "bad" } | null; onClose: () => void }) {
  useEffect(() => {
    if (!message) return;
    const t = window.setTimeout(onClose, 6000);
    return () => window.clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return <div className={`desk-toast ${message.tone}`} role="status" data-testid="desk-toast">{message.text}</div>;
}

export function When({ at, by }: { at?: string | null; by?: string | null }) {
  return <span className="tiny muted"><span className="ltr">{timeL(at)}</span>{by ? ` · ${by}` : ""}</span>;
}

export function useOutsideClose(open: boolean, close: () => void) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    const onClick = (e: MouseEvent) => { if (!(e.target as HTMLElement).closest("[data-popover]")) close(); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("mousedown", onClick); };
  }, [open, close]);
}

export function Expand({ label, children, defaultOpen = false, testId }: { label: ReactNode; children: ReactNode; defaultOpen?: boolean; testId?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`expand${open ? " open" : ""}`} data-testid={testId}>
      <button className="expand-head" onClick={() => setOpen(!open)} aria-expanded={open}>{label}<span className="expand-chev" aria-hidden>▾</span></button>
      {open && <div className="expand-body">{children}</div>}
    </div>
  );
}
