import { useEffect, useRef, useState } from "react";
import type { Fact } from "../api";
import { WITNESS_HE } from "../api";
import { ICheck, IAlert } from "./Icons";

/** The decisive fields of every document family, in reading order (the backend's prompts.FAMILY_FIELDS). */
export const MAIN = ["employee_name", "employee_id", "employer_name", "salary_period", "payment_date", "gross_pay", "total_deductions", "net_pay",
  "holder_name", "holder_id", "date_of_birth", "expiry_date", "bank_name", "account_number", "statement_from", "statement_to",
  "closing_balance", "issuer_name", "document_kind", "subject", "issue_date", "total_amount", "tax_year"];

/** The original page with every extracted value boxed where the file prints it. Only verified
 * boxes are drawn solid; unverified boxes are labelled so. No box is invented on the client. */
export function EvidenceViewer({ documentId, facts, page = 1, focus, onFocus, dpi = 110, interactive = false, quiet = false, autoScroll = true }: {
  documentId: string; facts: Fact[]; page?: number; focus?: string | null; onFocus?: (f: string) => void; dpi?: number; interactive?: boolean;
  /** Only the focused box is highlighted; every other box stays on the page as a faint, clickable outline. */
  quiet?: boolean;
  /** Scroll the focused box into view. Off for a default selection, so the page opens at its top. */
  autoScroll?: boolean;
}) {
  const src = `/api/documents/${documentId}/pages/${page}.png?dpi=${dpi}`;
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);
  const loaded = loadedSrc === src;
  const root = useRef<HTMLDivElement>(null);
  const shown = facts.filter((f) => f.evidence?.bbox && f.evidence.page === page && f.evidence.page_size);
  useEffect(() => {
    if (loaded && focus && autoScroll) root.current?.querySelector(".hl.focus")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [loaded, focus, autoScroll]);
  return (
    <div className={`viewer${interactive ? " interactive" : ""}${loaded ? "" : " loading"}`} ref={root} data-testid="evidence-viewer">
      <img key={src} src={src} alt="עמוד המסמך המקורי" onLoad={() => setLoadedSrc(src)} />
      {!loaded && <div className="viewer-wait"><span className="spinner" /> טוען את עמוד המסמך…</div>}
      {loaded && shown.map((f) => {
        const [x0, y0, x1, y1] = f.evidence!.bbox!;
        const [w, h] = f.evidence!.page_size!;
        const verified = ["text_layer_exact", "vision_reread_confirmed"].includes(f.evidence!.witness);
        const on = focus ? focus === f.field : MAIN.includes(f.field);
        const cls = quiet ? (focus === f.field ? "hl focus" : "hl quiet") : `hl ${on ? "" : "dim"}${focus === f.field ? " focus" : ""}`;
        return (
          <div key={`${documentId}:${page}:${f.field}`} className={cls} title={`${f.label_he}: ${f.value_raw ?? ""}`}
            data-field={f.field}
            style={{ left: `${(x0 / w) * 100 - 0.6}%`, top: `${(y0 / h) * 100 - 0.5}%`, width: `${((x1 - x0) / w) * 100 + 1.2}%`,
              height: `${((y1 - y0) / h) * 100 + 1}%`, borderStyle: verified ? "solid" : "dashed",
              opacity: quiet ? undefined : focus && !on ? 0.25 : 1 }} onClick={() => onFocus?.(f.field)} />
        );
      })}
    </div>
  );
}

export function FactList({ facts, focus, onFocus }: { facts: Fact[]; focus?: string | null; onFocus?: (f: string) => void }) {
  const ordered = [...facts].sort((a, b) => MAIN.indexOf(a.field) - MAIN.indexOf(b.field)).filter((f) => MAIN.includes(f.field));
  return (
    <div>
      {ordered.map((f) => {
        const w = f.evidence?.witness || "unavailable";
        const verified = w === "text_layer_exact" || w === "vision_reread_confirmed";
        return (
          <button key={f.field} className={`fact-row ${focus === f.field ? "on" : ""}`} onClick={() => onFocus?.(f.field)}>
            <span className="muted small">{f.label_he}</span>
            <span className="bold" style={{ color: "var(--mz-ink)" }}><bdi>{f.value_raw}</bdi></span>
            <span className={`badge ${verified ? "ok" : "warn"}`} title={f.evidence?.witness_detail || ""}>
              {verified ? <ICheck size={11} /> : <IAlert size={11} />}{verified ? "אומת" : "לא אומת"}
            </span>
          </button>
        );
      })}
      {focus && (() => {
        const f = facts.find((x) => x.field === focus);
        return f?.evidence ? <div className="tiny muted" style={{ marginTop: 6 }}>{WITNESS_HE[f.evidence.witness]} · {f.evidence.witness_detail}</div> : null;
      })()}
    </div>
  );
}
