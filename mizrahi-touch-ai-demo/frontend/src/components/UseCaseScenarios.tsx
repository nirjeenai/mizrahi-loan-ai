import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useCase } from "../caseContext";
import { DEMO_RESET_EVENT, loadPresenterBundle } from "./FeaturedScenarios";
import { ICheck, IChevronDown } from "./Icons";

/* The six primary demo use cases (UC-01…06), one presenter test case each (TC-01…06). Everything shown comes from the
   presenter manifest (fixtures/presenter, built by fixtures/loan/build_manifest.py); the expected checklist is what the
   demo document policy composes for the profile — checked against the engine by backend/tests/test_document_profiles.py.
   Round 1 has no file packs: nothing here offers a download. */

interface UseCaseReq { code: string; titleHe: string; ownerHe: string; intake: "ai_review" | "human_review" }
export interface UseCase {
  id: string; useCaseId: string; badgeHe: string; titleHe: string; personaHe: string; profileHe: string; caseId: string;
  caseDisplay: string; loanHe: string; demonstratesHe: string; requirements: UseCaseReq[]; notRequiredHe?: string[];
  noteHe?: string; bankerAssisted?: boolean; packStatus: string; packNoteHe: string;
}

const OPEN_KEY = "mz.presenter.usecases.open.v1";
const readOpen = (): string[] => { try { return JSON.parse(localStorage.getItem(OPEN_KEY) || "[]"); } catch { return []; } };

export function UseCaseScenarios() {
  const [cases, setCases] = useState<UseCase[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string[]>(readOpen);
  useEffect(() => {
    loadPresenterBundle().then((b) => { setCases(b.manifest.useCases || []); setNote(b.manifest.useCasesNoteHe || null); })
      .catch(() => setFailed(true));
  }, []);
  useEffect(() => { localStorage.setItem(OPEN_KEY, JSON.stringify(open)); }, [open]);
  useEffect(() => {
    const collapse = () => setOpen([]);
    window.addEventListener(DEMO_RESET_EVENT, collapse);
    return () => window.removeEventListener(DEMO_RESET_EVENT, collapse);
  }, []);
  if (failed) return <div className="small muted">פרופילי ההדגמה אינם זמינים בשרת (fixtures/presenter).</div>;
  if (!cases?.length) return null;
  return (
    <section className="uc-section" aria-labelledby="uc-heading" data-testid="use-cases">
      <h2 id="uc-heading" className="feat-heading">שישה פרופילי לקוח לדמו</h2>
      <div className="small muted feat-sub">כל פרופיל פותח תיק מוכן עם הלקוח, מטרת ההלוואה ורשימת המסמכים שנגזרה ממדיניות המסמכים.</div>
      <div className="feat-list">
        {cases.map((u) => (
          <UseCaseCard key={u.id} u={u} isOpen={open.includes(u.id)}
            onToggle={() => setOpen((ids) => (ids.includes(u.id) ? ids.filter((x) => x !== u.id) : [...ids, u.id]))} />
        ))}
      </div>
      {note && <div className="tiny muted feat-note">{note}</div>}
    </section>
  );
}

function UseCaseCard({ u, isOpen, onToggle }: { u: UseCase; isOpen: boolean; onToggle: () => void }) {
  const { caseId, auth, openCase, reload } = useCase();
  const nav = useNavigate();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const here = caseId === u.caseId && auth.status === "signed-in";
  const human = u.requirements.filter((r) => r.intake === "human_review").length;
  const owners = [...new Set(u.requirements.map((r) => r.ownerHe))];
  const reset = async () => {
    setBusy(true); setMsg(null);
    try { await api.reset(u.caseId); reload(); setMsg("התיק אופס — אין בו מסמכים."); }
    catch (e) { setMsg(`האיפוס לא הושלם: ${(e as Error).message}`); } finally { setBusy(false); setAsking(false); }
  };
  return (
    <article className={`feat uc${here ? " here" : ""}${isOpen ? " open" : ""}`} data-testid={`usecase-${u.id}`} data-case={u.caseId}
      data-use-case={u.useCaseId}>
      <div className="feat-top">
        <span className="feat-badge info" data-testid="usecase-badge">{u.id} ↔ {u.useCaseId} · {u.badgeHe}</span>
        {here && <span className="scn-on"><ICheck size={12} />פתוח מימין</span>}
      </div>
      <h3 className="feat-title">{u.titleHe}</h3>
      <div className="feat-line" data-testid="usecase-persona"><b>לקוח: </b>{u.personaHe} · {u.profileHe}</div>
      <div className="feat-line"><b>בקשה: </b>{u.loanHe} · תיק <span className="ltr">{u.caseDisplay}</span></div>
      <div className="feat-line"><b>מה מדגימים: </b>{u.demonstratesHe}</div>
      {u.bankerAssisted && <div className="feat-line uc-assisted" data-testid="usecase-banker-assisted">מסלול מוגבל — דורש טיפול בנקאי; אין חיתום עסקי.</div>}
      <div className="feat-expected info" data-testid="usecase-expected">
        <span className="feat-k">רשימה צפויה</span>
        <span>{u.requirements.length} מסמכים{human ? ` · ${human} לבדיקת בנקאי (ללא AI)` : ""}</span>
      </div>
      <div className="feat-actions">
        <button type="button" className="btn btn-dark scn-btn" data-testid="usecase-open-case"
          onClick={() => { openCase(u.caseId); nav("/customer/documents"); }}>{here ? "למסמכי התיק מימין" : "פתיחת התיק מימין"}</button>
        <button type="button" className="link feat-more" aria-expanded={isOpen} onClick={onToggle} data-testid="usecase-toggle">
          המסמכים הצפויים <span className="scn-chev" aria-hidden><IChevronDown size={14} /></span>
        </button>
      </div>
      {isOpen && (
        <div className="feat-body" data-testid="usecase-requirements">
          {owners.map((o) => (
            <div key={o}>
              <div className="scn-label">{o}</div>
              <ul className="uc-reqs">
                {u.requirements.filter((r) => r.ownerHe === o).map((r) => (
                  <li key={r.code} data-testid="usecase-req" data-code={r.code} data-intake={r.intake}>
                    <span className="grow">{r.titleHe}</span>
                    <span className={`badge ${r.intake === "human_review" ? "neutral" : "jeen"}`}>{r.intake === "human_review" ? "בנקאי" : "AI"}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {(u.notRequiredHe?.length ?? 0) > 0 && <div className="tiny muted"><b>לא נדרש: </b>{u.notRequiredHe!.join(" · ")}</div>}
          {u.noteHe && <div className="tiny muted" style={{ marginTop: 4 }}>{u.noteHe}</div>}
          <div className="tiny muted uc-pack" data-testid="usecase-pack" data-status={u.packStatus}>{u.packNoteHe}</div>
          <div className="row" style={{ gap: 10, marginTop: 8, flexWrap: "wrap" }}>
            <a className="link small" href={`/banker?case=${encodeURIComponent(u.caseId)}`} target="_blank" rel="noreferrer"
              data-testid="usecase-banker-link">תצוגת הבנקאית (לשונית חדשה)</a>
            {here && !asking && <button className="link small" onClick={() => setAsking(true)} data-testid="usecase-reset">איפוס התיק</button>}
            {here && asking && (
              <span className="row" style={{ gap: 6 }}>
                <button className="btn btn-orange scn-btn" disabled={busy} onClick={reset} data-testid="usecase-reset-confirm">
                  {busy && <span className="spinner" />}כן, לאפס</button>
                <button className="btn btn-ghost scn-btn" disabled={busy} onClick={() => setAsking(false)}>ביטול</button>
              </span>
            )}
          </div>
          {msg && <div className="tiny" role="status" style={{ marginTop: 4 }}>{msg}</div>}
        </div>
      )}
    </article>
  );
}
