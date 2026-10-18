import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, monthHe } from "../api";
import { useCase } from "../caseContext";
import { loc, locList, locOf, tr, useLang } from "../i18n";
import { DEMO_RESET_EVENT, FixtureRow, loadPresenterBundle, monthTag, roleL, type FeaturedStep, type FixtureDoc } from "./FeaturedScenarios";
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
  const { en, t } = useLang();
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
  if (failed) return <div className="small muted">{t("פרופילי הלקוח אינם זמינים בשרת (fixtures/presenter).",
    "The customer profiles aren't available on the server (fixtures/presenter).")}</div>;
  if (!cases?.length) return null;
  return (
    <section className="uc-section" aria-labelledby="uc-heading" data-testid="use-cases">
      <h2 id="uc-heading" className="feat-heading">{t("שישה פרופילי לקוח", "Six customer profiles")}</h2>
      {en ? <div className="small muted feat-sub">Each profile opens a prepared case with the customer, the loan purpose and the
        document list, plus a pack of files to download and upload on the right.</div>
        : <div className="small muted feat-sub">כל פרופיל פותח תיק מוכן עם הלקוח, מטרת ההלוואה ורשימת המסמכים, וחבילת קבצים
        להורדה ולהעלאה מימין.</div>}
      <div className="feat-list">
        {cases.map((u) => <UseCaseCard key={u.id} u={u} docs={docs} isOpen={open.includes(u.id)} onToggle={() => toggle(u.id)} />)}
        {fresh && <NewCustomerCard p={fresh} docs={docs} isOpen={open.includes(fresh.id)} onToggle={() => toggle(fresh.id)} />}
      </div>
    </section>
  );
}

function StepList({ steps, docs, testId }: { steps: FeaturedStep[]; docs: Record<string, FixtureDoc>; testId: string }) {
  useLang();
  return (
    <ul className="fx-list" data-testid={testId}>
      {steps.map((s, i) => (isBanker(s) ? (
        <li key={`${s.file}-${s.role}-${i}`} className="fx uc-banker-step" data-testid="usecase-banker-step" data-role={s.role}>
          <span className="grow fx-main"><span className="fx-label">{loc(s.labelHe, s.labelEn)}</span>
            <span className="fx-sub"><span>{roleL(s.role)}</span></span>
            {s.noteHe && <span className="fx-note">{loc(s.noteHe, s.noteEn)}</span>}</span>
        </li>
      ) : docs[s.file] ? (
        <FixtureRow key={`${s.file}-${i}`} doc={docs[s.file]}
          item={{ ...s, slotHe: [s.slotHe, s.period ? `חודש ${monthHe(s.period)}` : null].filter(Boolean).join(" · "),
            slotEn: [locOf(s, "slotHe"), s.period ? monthTag(s.period) : null].filter(Boolean).join(" · "), period: null }}
          testId="usecase-download" />
      ) : null))}
    </ul>
  );
}

function UseCaseCard({ u, docs, isOpen, onToggle }: { u: UseCase; docs: Record<string, FixtureDoc>; isOpen: boolean; onToggle: () => void }) {
  const { caseId, auth, openCase, reload } = useCase();
  const { t } = useLang();
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
    try { await api.reset(u.caseId); reload(); setMsg(tr("התיק אופס, אין בו מסמכים.", "The case was reset; it has no documents.")); }
    catch (e) { setMsg(tr(`האיפוס לא הושלם: ${(e as Error).message}`, `The reset didn't complete: ${(e as Error).message}`)); } finally { setBusy(false); setAsking(false); }
  };
  const desc = locOf(u, "demonstratesHe");
  return (
    <article className={`feat uc${here ? " here" : ""}${isOpen ? " open" : ""}`} data-testid={`usecase-${u.id}`} data-case={u.caseId}
      data-use-case={u.useCaseId}>
      <div className="feat-top">
        <span className="feat-badge info" data-testid="usecase-badge">{u.id} ↔ {u.useCaseId} · {locOf(u, "badgeHe")}</span>
        {here && <span className="scn-on"><ICheck size={12} />{t("פתוח מימין", "Open on the right")}</span>}
      </div>
      <h3 className="feat-title">{locOf(u, "titleHe")}</h3>
      <div className="feat-line" data-testid="usecase-persona"><b>{t("לקוח: ", "Customer: ")}</b>{locOf(u, "personaHe")} · {locOf(u, "profileHe")}</div>
      <div className="feat-line"><b>{t("בקשה: ", "Application: ")}</b>{locOf(u, "loanHe")} · {t("תיק", "case")} <span className="ltr">{u.caseDisplay}</span></div>
      <div className="feat-line uc-desc" title={desc} data-testid="usecase-description">{desc}</div>
      {u.bankerAssisted && <div className="feat-line uc-assisted" data-testid="usecase-banker-assisted">{t("מסלול מוגבל, דורש טיפול בנקאי; אין חיתום עסקי.",
        "A limited track that needs the banker's handling; no business underwriting.")}</div>}
      <div className="feat-expected info" data-testid="usecase-expected">
        <span className="feat-k">{t("תוצאה צפויה", "Expected outcome")}</span>
        <span>{locOf(u, "expectedLabelHe") || t(`${u.requirements.length} מסמכים`, `${u.requirements.length} documents`)}</span>
        <span className="tiny uc-counts">{t(`${u.requirements.length} דרישות`, `${u.requirements.length} requirements`)}{human ? t(` · ${human} לבדיקת בנקאי (ללא AI)`, ` · ${human} for the banker's review (no AI)`) : ""}
          {files ? t(` · ${files} קבצים להורדה`, ` · ${files} files to download`) : ""}</span>
      </div>
      <div className="feat-actions">
        <button type="button" className="btn btn-dark scn-btn" data-testid="usecase-open-case"
          onClick={() => { openCase(u.caseId); nav("/customer/documents"); }}>{here ? t("למסמכי התיק מימין", "Go to the case's documents on the right") : t("פתיחת התיק מימין", "Open the case on the right")}</button>
        <button type="button" className="link feat-more" aria-expanded={isOpen} onClick={onToggle} data-testid="usecase-toggle">
          {t("מסמכים וקבצים", "Documents and files")} <span className="scn-chev" aria-hidden><IChevronDown size={14} /></span>
        </button>
      </div>
      {isOpen && (
        <div className="feat-body" data-testid="usecase-requirements">
          {u.expectHe && <div className="feat-line"><b>{t("מה מצופה: ", "What to expect: ")}</b>{locOf(u, "expectHe")}</div>}
          {u.steps?.length ? (<><div className="scn-label">{t("סדר העלאה וקבצים להורדה", "Upload order and files to download")}</div>
            <StepList steps={u.steps} docs={docs} testId="usecase-files" /></>) : null}
          <div className="scn-label">{t("רשימת המסמכים של התיק", "The case's document list")}</div>
          {owners.map((o) => {
            const reqs = u.requirements.filter((r) => r.ownerHe === o);
            return (
            <div key={o}>
              <div className="tiny bold muted">{locOf(reqs[0], "ownerHe")}</div>
              <ul className="uc-reqs">
                {reqs.map((r) => (
                  <li key={r.code} data-testid="usecase-req" data-code={r.code} data-intake={r.intake}>
                    <span className="grow">{locOf(r, "titleHe")}</span>
                    <span className={`badge ${r.intake === "human_review" ? "neutral" : "jeen"}`}>{r.intake === "human_review" ? t("בנקאי", "Banker") : "AI"}</span>
                  </li>
                ))}
              </ul>
            </div>
            );
          })}
          {(u.notRequiredHe?.length ?? 0) > 0 && <div className="tiny muted"><b>{t("לא נדרש: ", "Not required: ")}</b>{locList(u, "notRequiredHe").join(" · ")}</div>}
          {u.noteHe && <div className="tiny muted" style={{ marginTop: 4 }}>{locOf(u, "noteHe")}</div>}
          <div className="row" style={{ gap: 10, marginTop: 8, flexWrap: "wrap" }}>
            <a className="link small" href={`/banker?case=${encodeURIComponent(u.caseId)}`} target="_blank" rel="noreferrer"
              data-testid="usecase-banker-link">{t("תצוגת הבנקאית (לשונית חדשה)", "Banker view (new tab)")}</a>
            {here && !asking && <button className="link small" onClick={() => setAsking(true)} data-testid="usecase-reset">{t("איפוס התיק", "Reset the case")}</button>}
            {here && asking && (
              <span className="row" style={{ gap: 6 }}>
                <button className="btn btn-orange scn-btn" disabled={busy} onClick={reset} data-testid="usecase-reset-confirm">
                  {busy && <span className="spinner" />}{t("כן, לאפס", "Yes, reset")}</button>
                <button className="btn btn-ghost scn-btn" disabled={busy} onClick={() => setAsking(false)}>{t("ביטול", "Cancel")}</button>
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
  const { en, t } = useLang();
  return (
    <article className={`feat uc uc-new${isOpen ? " open" : ""}`} data-testid="usecase-NEW-CUSTOMER">
      <div className="feat-top"><span className="feat-badge ok">{t("מסלול 7 · לקוח חדש", "Track 7 · new customer")}</span></div>
      <h3 className="feat-title">{locOf(p, "titleHe")}</h3>
      {en ? <div className="feat-line"><b>Customer: </b>{locOf(p, "personaHe")}, with no prepared case; the case is created from the questionnaire.</div>
        : <div className="feat-line"><b>לקוחה: </b>{p.personaHe}, אין לה תיק מוכן; התיק נוצר מהשאלון.</div>}
      <div className="feat-line feat-do"><b>{t("איך מריצים: ", "How to run it: ")}</b>{locOf(p, "instructionHe")}</div>
      <div className="feat-actions">
        <Link className="btn btn-dark scn-btn" to="/customer/apply" data-testid="usecase-new-start">{t("פתיחת השאלון מימין", "Open the questionnaire on the right")}</Link>
        <button type="button" className="link feat-more" aria-expanded={isOpen} onClick={onToggle} data-testid="usecase-new-toggle">
          {t("תשובות וקבצים", "Answers and files")} <span className="scn-chev" aria-hidden><IChevronDown size={14} /></span>
        </button>
      </div>
      {isOpen && (
        <div className="feat-body" data-testid="usecase-new-body">
          <div className="scn-label">{t("התשובות בשאלון", "The questionnaire answers")}</div>
          <ul className="feat-bullets">{locList(p, "answersHe").map((a, i) => <li key={p.answersHe[i]}>{a}</li>)}</ul>
          <div className="scn-label">{t("קבצים להורדה", "Files to download")}</div>
          <StepList steps={p.steps} docs={docs} testId="usecase-new-files" />
        </div>
      )}
    </article>
  );
}
