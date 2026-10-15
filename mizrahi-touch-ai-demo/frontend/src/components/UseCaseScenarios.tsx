import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, monthHe } from "../api";
import { useCase } from "../caseContext";
import { DEMO_RESET_EVENT, FixtureRow, loadPresenterBundle, ROLE_HE, type FeaturedStep, type FixtureDoc } from "./FeaturedScenarios";
import { ICheck, IChevronDown } from "./Icons";

/* The six primary demo use cases (UC-01…06), one presenter test case each (TC-01…06), and the new-customer journey.
   Everything shown comes from the presenter manifest (fixtures/presenter, built by fixtures/loan/build_manifest.py):
   the expected checklist is what the demo document policy composes for the profile (checked against the engine by
   backend/tests/test_document_profiles.py), the files are the case's own synthetic pack (checksum-verified downloads),
   and the expected outcome is the routing the scenario is built to show (checked on REPLAY by
   e2e/verify_presenter_scenarios.py) — never a live result and never a credit decision. */

interface UseCaseReq { code: string; titleHe: string; ownerHe: string; intake: "ai_review" | "human_review" }
export interface UseCase {
  id: string; useCaseId: string; badgeHe: string; titleHe: string; personaHe: string; profileHe: string; caseId: string;
  caseDisplay: string; loanHe: string; demonstratesHe: string; requirements: UseCaseReq[]; notRequiredHe?: string[];
  noteHe?: string; bankerAssisted?: boolean; packStatus: string; packNoteHe: string; steps?: FeaturedStep[];
  instructionHe?: string; expectHe?: string; expectedLabelHe?: string; expectedCaseStatus?: string;
}
export interface NewCustomerPack { id: string; titleHe: string; personaHe: string; answersHe: string[]; instructionHe: string; steps: FeaturedStep[]; noteHe: string }

const OPEN_KEY = "mz.presenter.usecases.open.v1";
const readOpen = (): string[] => { try { return JSON.parse(localStorage.getItem(OPEN_KEY) || "[]"); } catch { return []; } };
const isBanker = (s: FeaturedStep) => s.role === "banker_correction" || s.role === "banker_accept";

export function UseCaseScenarios() {
  const [cases, setCases] = useState<UseCase[] | null>(null);
  const [docs, setDocs] = useState<Record<string, FixtureDoc>>({});
  const [fresh, setFresh] = useState<NewCustomerPack | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string[]>(readOpen);
  useEffect(() => {
    loadPresenterBundle().then((b) => {
      setCases(b.manifest.useCases || []);
      setDocs(Object.fromEntries(b.manifest.documents.map((d) => [d.id, d])));
      setFresh(b.manifest.newCustomer || null);
    }).catch(() => setFailed(true));
  }, []);
  useEffect(() => { localStorage.setItem(OPEN_KEY, JSON.stringify(open)); }, [open]);
  useEffect(() => {
    const collapse = () => setOpen([]);
    window.addEventListener(DEMO_RESET_EVENT, collapse);
    return () => window.removeEventListener(DEMO_RESET_EVENT, collapse);
  }, []);
  const toggle = (id: string) => setOpen((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  if (failed) return <div className="small muted">פרופילי הלקוח אינם זמינים בשרת (fixtures/presenter).</div>;
  if (!cases?.length) return null;
  return (
    <section className="uc-section" aria-labelledby="uc-heading" data-testid="use-cases">
      <h2 id="uc-heading" className="feat-heading">שישה פרופילי לקוח</h2>
      <div className="small muted feat-sub">כל פרופיל פותח תיק מוכן עם הלקוח, מטרת ההלוואה ורשימת המסמכים, וחבילת קבצים
        להורדה ולהעלאה מימין.</div>
      <div className="feat-list">
        {cases.map((u) => <UseCaseCard key={u.id} u={u} docs={docs} isOpen={open.includes(u.id)} onToggle={() => toggle(u.id)} />)}
        {fresh && <NewCustomerCard p={fresh} docs={docs} isOpen={open.includes(fresh.id)} onToggle={() => toggle(fresh.id)} />}
      </div>
    </section>
  );
}

function StepList({ steps, docs, testId }: { steps: FeaturedStep[]; docs: Record<string, FixtureDoc>; testId: string }) {
  return (
    <ul className="fx-list" data-testid={testId}>
      {steps.map((s, i) => (isBanker(s) ? (
        <li key={`${s.file}-${s.role}-${i}`} className="fx uc-banker-step" data-testid="usecase-banker-step" data-role={s.role}>
          <span className="grow fx-main"><span className="fx-label">{s.labelHe}</span>
            <span className="fx-sub"><span>{ROLE_HE[s.role]}</span></span>
            {s.noteHe && <span className="fx-note">{s.noteHe}</span>}</span>
        </li>
      ) : docs[s.file] ? (
        <FixtureRow key={`${s.file}-${i}`} doc={docs[s.file]}
          item={{ ...s, slotHe: [s.slotHe, s.period ? `חודש ${monthHe(s.period)}` : null].filter(Boolean).join(" · "), period: null }}
          testId="usecase-download" />
      ) : null))}
    </ul>
  );
}

function UseCaseCard({ u, docs, isOpen, onToggle }: { u: UseCase; docs: Record<string, FixtureDoc>; isOpen: boolean; onToggle: () => void }) {
  const { caseId, auth, openCase, reload } = useCase();
  const nav = useNavigate();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const here = caseId === u.caseId && auth.status === "signed-in";
  const human = u.requirements.filter((r) => r.intake === "human_review").length;
  const owners = [...new Set(u.requirements.map((r) => r.ownerHe))];
  const files = (u.steps || []).filter((s) => !isBanker(s)).length;
  const reset = async () => {
    setBusy(true); setMsg(null);
    try { await api.reset(u.caseId); reload(); setMsg("התיק אופס, אין בו מסמכים."); }
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
      <div className="feat-line uc-desc" title={u.demonstratesHe} data-testid="usecase-description">{u.demonstratesHe}</div>
      {u.bankerAssisted && <div className="feat-line uc-assisted" data-testid="usecase-banker-assisted">מסלול מוגבל, דורש טיפול בנקאי; אין חיתום עסקי.</div>}
      <div className="feat-expected info" data-testid="usecase-expected">
        <span className="feat-k">תוצאה צפויה</span>
        <span>{u.expectedLabelHe || `${u.requirements.length} מסמכים`}</span>
        <span className="tiny uc-counts">{u.requirements.length} דרישות{human ? ` · ${human} לבדיקת בנקאי (ללא AI)` : ""}
          {files ? ` · ${files} קבצים להורדה` : ""}</span>
      </div>
      <div className="feat-actions">
        <button type="button" className="btn btn-dark scn-btn" data-testid="usecase-open-case"
          onClick={() => { openCase(u.caseId); nav("/customer/documents"); }}>{here ? "למסמכי התיק מימין" : "פתיחת התיק מימין"}</button>
        <button type="button" className="link feat-more" aria-expanded={isOpen} onClick={onToggle} data-testid="usecase-toggle">
          מסמכים וקבצים <span className="scn-chev" aria-hidden><IChevronDown size={14} /></span>
        </button>
      </div>
      {isOpen && (
        <div className="feat-body" data-testid="usecase-requirements">
          {u.expectHe && <div className="feat-line"><b>מה מצופה: </b>{u.expectHe}</div>}
          {u.steps?.length ? (<><div className="scn-label">סדר העלאה וקבצים להורדה</div>
            <StepList steps={u.steps} docs={docs} testId="usecase-files" /></>) : null}
          <div className="scn-label">רשימת המסמכים של התיק</div>
          {owners.map((o) => (
            <div key={o}>
              <div className="tiny bold muted">{o}</div>
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

function NewCustomerCard({ p, docs, isOpen, onToggle }: { p: NewCustomerPack; docs: Record<string, FixtureDoc>; isOpen: boolean; onToggle: () => void }) {
  return (
    <article className={`feat uc uc-new${isOpen ? " open" : ""}`} data-testid="usecase-NEW-CUSTOMER">
      <div className="feat-top"><span className="feat-badge ok">מסלול 7 · לקוח חדש</span></div>
      <h3 className="feat-title">{p.titleHe}</h3>
      <div className="feat-line"><b>לקוחה: </b>{p.personaHe}, אין לה תיק מוכן; התיק נוצר מהשאלון.</div>
      <div className="feat-line feat-do"><b>איך מריצים: </b>{p.instructionHe}</div>
      <div className="feat-actions">
        <Link className="btn btn-dark scn-btn" to="/customer/apply" data-testid="usecase-new-start">פתיחת השאלון מימין</Link>
        <button type="button" className="link feat-more" aria-expanded={isOpen} onClick={onToggle} data-testid="usecase-new-toggle">
          תשובות וקבצים <span className="scn-chev" aria-hidden><IChevronDown size={14} /></span>
        </button>
      </div>
      {isOpen && (
        <div className="feat-body" data-testid="usecase-new-body">
          <div className="scn-label">התשובות בשאלון</div>
          <ul className="feat-bullets">{p.answersHe.map((a) => <li key={a}>{a}</li>)}</ul>
          <div className="scn-label">קבצים להורדה</div>
          <StepList steps={p.steps} docs={docs} testId="usecase-new-files" />
        </div>
      )}
    </article>
  );
}
