import { useEffect, useRef, useState, type RefObject } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { CaseProvider, useCase } from "./caseContext";
import { FeaturedScenarios, NewDemoButton } from "./components/FeaturedScenarios";
import { FollowupSimControls } from "./components/FollowupSimControls";
import { IClose, IPanel } from "./components/Icons";
import { ScenarioPresenter } from "./components/ScenarioPresenter";
import { TouchShell } from "./components/TouchShell";
import { UseCaseScenarios } from "./components/UseCaseScenarios";
import { AdminPage } from "./pages/admin/AdminPage";
import { BankerConsole } from "./pages/banker/BankerConsole";
import { Apply } from "./pages/customer/Apply";
import { ApplyV2 } from "./pages/customer/ApplyV2";
import { LinkLanding } from "./pages/customer/Link";
import { DocumentReview } from "./pages/customer/DocumentReview";
import { Documents } from "./pages/customer/Documents";
import { Home } from "./pages/customer/Home";
import { Meetings, RequestDetails, Stages, Tools } from "./pages/customer/Secondary";
import { SystemPage } from "./pages/system/SystemPage";

// Kept outside React so leaving /customer (banker, system) and coming back keeps it; a fresh page load starts collapsed.
let presenterWasOpen = false;

/** Stays mounted while collapsed: scenario cards, marks, scroll position and inline confirmations survive a toggle. */
function HubSide({ onClose, closeRef }: { onClose: () => void; closeRef: RefObject<HTMLButtonElement> }) {
  const { caseId } = useCase();
  return (
    <aside className="hub-side" id="presenter-panel" aria-label="תרחישים" data-testid="presenter-panel"
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <div className="hub-side-head">
        <span className="hub-side-title"><IPanel />תרחישים</span>
        <button ref={closeRef} className="icon-btn" onClick={onClose} aria-label="סגירת התרחישים" title="סגירה"
          data-testid="presenter-close"><IClose size={20} /></button>
      </div>
      <div className="cobrand"><img src="/brand/mizrahi-logo.svg" alt="מזרחי טפחות" /><span className="brand-x" aria-hidden>×</span>
        <img src="/brand/jeen-logo.png" alt="Jeen" /></div>
      <h1>טפחות טאצ׳ × JEEN</h1>
      <p className="small hub-lead">השלמת מסמכים חכמה לבקשת הלוואה: ה-AI קורא, מאמת, מנתב ומלווה את ההשלמה — הבנקאית מחליטה.</p>
      <div className="hub-bar">
        <NewDemoButton />
        <div className="hub-bar-links">
          <Link className="link small" to={`/banker?case=${encodeURIComponent(caseId)}`}>תצוגת הבנקאית</Link>
          <Link className="link small" to="/system">מערכת ואינטגרציות</Link>
        </div>
      </div>
      <UseCaseScenarios />
      <Link className="btn btn-ghost hub-apply" to="/customer/apply" data-testid="presenter-new-application">
        + בקשת הלוואה חדשה — שאלון לקוח חדש</Link>
      <FollowupSimControls />
      <details className="all-scn more-tests" data-testid="more-tests">
        <summary data-testid="more-tests-toggle">
          <span className="all-scn-title">בדיקות נוספות</span>
          <span className="small muted">15 התרחישים המאומתים: 4 תרחישים מנהלים ו־11 תרחישי בדיקה · עם קבצים להורדה</span>
        </summary>
        <FeaturedScenarios />
        <details className="all-scn" data-testid="all-scenarios">
          <summary data-testid="all-scenarios-toggle">
            <span className="all-scn-title">כל תרחישי הבדיקה</span>
            <span className="small muted">תרחישי הלוואה, קבצים משלימים ותלושי משפחת לביא · לבדיקות ו-QA</span>
          </summary>
          <ScenarioPresenter />
        </details>
      </details>
    </aside>
  );
}

function CustomerApp() {
  const [presenter, setPresenterState] = useState(presenterWasOpen);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const moveFocus = useRef(false);
  const setPresenter = (open: boolean) => { presenterWasOpen = open; moveFocus.current = true; setPresenterState(open); };
  useEffect(() => {
    if (!moveFocus.current) return;
    moveFocus.current = false;
    (presenter ? closeRef : toggleRef).current?.focus({ preventScroll: true });
  }, [presenter]);
  return (
    <div className="hub" data-presenter={presenter ? "open" : "closed"}>
      <TouchShell onPresenter={() => setPresenter(true)}>
        <Routes>
          <Route index element={<Home />} />
          <Route path="documents" element={<Documents />} />
          <Route path="documents/:id" element={<DocumentReview />} />
          <Route path="request" element={<RequestDetails />} />
          <Route path="stages" element={<Stages />} />
          <Route path="meetings" element={<Meetings />} />
          <Route path="tools" element={<Tools />} />
          <Route path="apply" element={<Apply />} />
          <Route path="apply/v2" element={<ApplyV2 />} />
          <Route path="link" element={<LinkLanding />} />
        </Routes>
      </TouchShell>
      <button ref={toggleRef} className="presenter-toggle" onClick={() => setPresenter(!presenter)} aria-expanded={presenter}
        aria-controls="presenter-panel" aria-label="תרחישים" title="תרחישים" data-testid="presenter-toggle">
        <IPanel /><span className="presenter-toggle-label">תרחישים</span>
      </button>
      <div className="hub-scrim" onClick={() => setPresenter(false)} aria-hidden="true" data-testid="presenter-scrim" />
      <HubSide onClose={() => setPresenter(false)} closeRef={closeRef} />
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/customer" replace />} />
        <Route path="/customer/*" element={<CaseProvider><CustomerApp /></CaseProvider>} />
        <Route path="/banker" element={<BankerConsole />} />
        <Route path="/system" element={<SystemPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/customer" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
