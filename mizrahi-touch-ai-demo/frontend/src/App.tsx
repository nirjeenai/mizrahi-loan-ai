import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { CaseProvider, useCase } from "./caseContext";
import { FeaturedScenarios, NewDemoButton } from "./components/FeaturedScenarios";
import { ScenarioPresenter } from "./components/ScenarioPresenter";
import { TouchShell } from "./components/TouchShell";
import { AdminPage } from "./pages/admin/AdminPage";
import { BankerConsole } from "./pages/banker/BankerConsole";
import { Apply } from "./pages/customer/Apply";
import { DocumentReview } from "./pages/customer/DocumentReview";
import { Documents } from "./pages/customer/Documents";
import { Home } from "./pages/customer/Home";
import { Meetings, RequestDetails, Stages, Tools } from "./pages/customer/Secondary";
import { SystemPage } from "./pages/system/SystemPage";

function HubSide() {
  const { caseId } = useCase();
  return (
    <aside className="hub-side">
      <div className="cobrand"><img src="/brand/mizrahi-logo.svg" alt="מזרחי טפחות" /><span className="brand-x" aria-hidden>×</span>
        <img src="/brand/jeen-logo.png" alt="Jeen" /></div>
      <h1>טפחות טאצ׳ × JEEN</h1>
      <p className="small hub-lead">השלמת מסמכים חכמה לבקשת הלוואה: ה-AI קורא, מאמת, מנתב ומלווה את ההשלמה — הבנקאית מחליטה.</p>
      <div className="notice small">נתונים סינתטיים בלבד · אין חיבור למערכות מזרחי־טפחות · אין החלטת אשראי אוטומטית.</div>
      <div className="hub-bar">
        <NewDemoButton />
        <div className="hub-bar-links">
          <Link className="link small" to={`/banker?case=${encodeURIComponent(caseId)}`}>תצוגת הבנקאית</Link>
          <Link className="link small" to="/system">מערכת ואינטגרציות</Link>
        </div>
      </div>
      <FeaturedScenarios />
      <details className="all-scn" data-testid="all-scenarios">
        <summary data-testid="all-scenarios-toggle">
          <span className="all-scn-title">כל תרחישי הבדיקה</span>
          <span className="small muted">תרחישי הלוואה, קבצים משלימים ותלושי משפחת לביא · לבדיקות ו-QA</span>
        </summary>
        <ScenarioPresenter />
      </details>
    </aside>
  );
}

function CustomerApp() {
  return (
    <div className="hub">
      <TouchShell>
        <Routes>
          <Route index element={<Home />} />
          <Route path="documents" element={<Documents />} />
          <Route path="documents/:id" element={<DocumentReview />} />
          <Route path="request" element={<RequestDetails />} />
          <Route path="stages" element={<Stages />} />
          <Route path="meetings" element={<Meetings />} />
          <Route path="tools" element={<Tools />} />
          <Route path="apply" element={<Apply />} />
        </Routes>
      </TouchShell>
      <HubSide />
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
