import { useState, type ReactNode } from "react";
import { tr, useLang } from "../i18n";
import { useNavigate } from "react-router-dom";
import { ActionRefusal, api, type AppAction } from "../api";
import { useCase } from "../caseContext";
import { IBag, IChevron, IClock, IDocs, IList, IPerson, IUpload } from "./Icons";

type Kind = AppAction["type"];
type Of<K extends Kind> = AppAction & { type: K };
type Say = (text: string, provenance: Record<string, unknown>) => void;
interface Deps { go: (path: string) => void; say: Say }

/** Everything the app can do for an action, through its own router and sheets. Types the app does not know are never rendered. */
const HANDLERS: { [K in Kind]: (a: Of<K>, d: Deps) => void } = {
  NAVIGATE_TO_DOCUMENT_UPLOAD: (a, d) => d.go(`/customer/documents?${new URLSearchParams({
    case: a.case_id, upload: a.params.requirement_code, ...(a.params.period ? { period: a.params.period } : {}) })}`),
  VIEW_MISSING_DOCUMENTS: (a, d) => d.go(`/customer/documents?${new URLSearchParams({ case: a.case_id, focus: "payslips" })}`),
  VIEW_REVIEW_STATUS: (a, d) => d.go(`/customer/documents?${new URLSearchParams({ case: a.case_id, focus: "uploaded" })}`),
  VIEW_DOCUMENT_REVIEW: (a, d) => d.go(`/customer/documents/${encodeURIComponent(a.params.document_id)}${
    a.params.finding_ids[0] ? `?finding=${encodeURIComponent(a.params.finding_ids[0])}` : ""}`),
  VIEW_CASE_DETAILS: (_a, d) => d.go("/customer/request"),
  CONTACT_BANKER: (a, d) => d.say(tr(a.params.message_he, a.params.message_en || a.params.message_he), { source: "app_action", action_id: a.action_id }),
};

const ICONS: Record<Kind, ReactNode> = {
  NAVIGATE_TO_DOCUMENT_UPLOAD: <IUpload size={16} />, VIEW_DOCUMENT_REVIEW: <IDocs size={16} />, VIEW_MISSING_DOCUMENTS: <IList size={16} />,
  VIEW_REVIEW_STATUS: <IClock size={16} />, VIEW_CASE_DETAILS: <IBag size={16} />, CONTACT_BANKER: <IPerson size={16} />,
};

const STALE_HE: Record<Kind, string> = {
  NAVIGATE_TO_DOCUMENT_UPLOAD: "✓ כבר לא נדרש", VIEW_DOCUMENT_REVIEW: "הממצא כבר טופל", VIEW_MISSING_DOCUMENTS: "✓ אין מסמכים חסרים",
  VIEW_REVIEW_STATUS: "הבדיקה הסתיימה", VIEW_CASE_DETAILS: "לא זמין כרגע", CONTACT_BANKER: "התיק כבר הועבר",
};
const STALE_EN: Record<Kind, string> = {
  NAVIGATE_TO_DOCUMENT_UPLOAD: "✓ No longer needed", VIEW_DOCUMENT_REVIEW: "The finding was already handled", VIEW_MISSING_DOCUMENTS: "✓ No missing documents",
  VIEW_REVIEW_STATUS: "The check has finished", VIEW_CASE_DETAILS: "Not available right now", CONTACT_BANKER: "The application was already passed on",
};

const supported = (a: { type: string }): a is AppAction => a.type in HANDLERS;

/** Re-validates an action with the Mortgage Case Service, then performs it. */
export function useActionRunner(say?: Say) {
  const { caseId, closeAssistant, closeUpload, openAssistant, assistantOrigin, setAssistantOrigin } = useCase();
  const nav = useNavigate();
  return async (offered: AppAction, turnId?: string) => {
    if (offered.case_id !== caseId) throw new ActionRefusal(403, tr("הפעולה שייכת לתיק אחר ולא בוצעה.", "This action belongs to another application and was not carried out."));
    const action = await api.resolveAction(caseId, offered.action_id, turnId);
    const deps: Deps = {
      go: (path) => {
        setAssistantOrigin({ actionId: action.action_id, turnId: turnId ?? assistantOrigin?.turnId });
        closeAssistant();
        closeUpload();
        nav(path);
      },
      say: say ?? ((text) => { closeUpload(); openAssistant(text); }),
    };
    // the English message of a banker hand-off comes with the resolved action; the offered one carries it too
    const english = (action.params as { message_en?: string }).message_en || (offered.params as { message_en?: string }).message_en;
    const resolved = english ? { ...action, params: { ...action.params, message_en: english } } as AppAction : action;
    (HANDLERS[resolved.type] as (a: AppAction, d: Deps) => void)(resolved, deps);
  };
}

export function ActionList({ actions, turnId, say, testId, emphasize = true }:
  { actions: AppAction[]; turnId?: string; say?: Say; testId?: string; emphasize?: boolean }) {
  const { snap } = useCase();
  const { en, t } = useLang();
  const run = useActionRunner(say);
  const [busy, setBusy] = useState<string | null>(null);
  const [refused, setRefused] = useState<Set<string>>(new Set());
  const [note, setNote] = useState<string | null>(null);
  const live = snap?.available_actions ? new Map(snap.available_actions.map((a) => [a.action_id, a])) : null;
  const rows = actions.filter(supported).map((offered) => {
    const current = live?.get(offered.action_id);
    return { action: current ?? offered, stale: (live !== null && !current) || refused.has(offered.action_id) };
  });
  if (!rows.length) return null;
  const primary = emphasize ? rows.findIndex((r) => !r.stale) : -1;

  const click = async (a: AppAction) => {
    setBusy(a.action_id);
    setNote(null);
    try {
      await run(a, turnId);
    } catch (e) {
      if (e instanceof ActionRefusal) {
        setRefused((s) => new Set(s).add(a.action_id));
        setNote(e.message);
      } else setNote(t("לא הצלחתי לפתוח את הפעולה כרגע. נסו שוב.", "I couldn't open that right now. Please try again."));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="act-list" role="group" aria-label={t("פעולות מוצעות", "Suggested actions")} data-testid={testId}>
      {rows.map(({ action: a, stale }, i) => (
        <button key={a.action_id} type="button" className={`act-btn${i === primary ? " primary" : ""}${stale ? " stale" : ""}`}
          disabled={stale || busy !== null} onClick={() => click(a)}
          data-action-id={a.action_id} data-action-type={a.type} data-stale={stale ? "true" : undefined}>
          <span className="act-ic" aria-hidden>{ICONS[a.type]}</span>
          <span className="act-txt">
            <span className="act-label">{(en && a.label_en) || a.label_he}</span>
            {(stale || a.detail_he) && <span className="act-detail">{stale ? (en ? STALE_EN : STALE_HE)[a.type] : (en && a.detail_en) || a.detail_he}</span>}
          </span>
          {busy === a.action_id ? <span className="spinner" /> : !stale && <span className="act-go" aria-hidden><IChevron size={16} /></span>}
        </button>
      ))}
      {note && <div className="act-note" role="status">{note}</div>}
    </div>
  );
}
