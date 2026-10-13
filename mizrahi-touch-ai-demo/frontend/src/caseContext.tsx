import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, AUTH_EVENT, CASE_ID_DEFAULT, usePolling, type DocView, type Session, type Snapshot } from "./api";

/** `replacesDocumentId`: the upload replaces a document the AI review sent back to the customer (no banker request). */
export interface UploadPreset { requirementCode?: string; period?: string | null; customerRequestId?: string; replacesDocumentId?: string }
/** Set when an assistant action took the customer out of the chat; cleared when the chat opens again. */
export interface AssistantOrigin { actionId: string; turnId?: string }

/** The customer's server session (an HttpOnly cookie bound to the cases it was issued for). In demo mode the app obtains
 *  it without a login for the case picked in the selector; "signed-out" means the service issues no demo sessions
 *  (DEMO_IDENTITY=0) and nothing is loaded. `wantCase` is kept for callers and is always null in demo mode. */
export interface AuthState {
  status: "loading" | "signed-out" | "signed-in";
  customer: Session["customer"];
  /** a demo session could not be obtained after the previous one ended */
  expired: boolean;
  wantCase: string | null;
}

interface CaseCtx {
  auth: AuthState;
  /** open a case (the demo session is extended to it) */
  openCase: (id: string) => void;
  caseId: string;
  setCaseId: (id: string) => void;
  snap: Snapshot | null;
  docs: DocView[];
  error: string | null;
  /** the case is on screen but the last refreshes failed (two or more in a row): it may be out of date */
  stale: boolean;
  updatedAt: Date | null;
  reload: () => void;
  assistant: { open: boolean; prompt?: string };
  openAssistant: (prompt?: string) => void;
  closeAssistant: () => void;
  upload: { open: boolean; borrowerId?: string; nonce: number } & UploadPreset;
  openUpload: (borrowerId?: string, preset?: UploadPreset) => void;
  closeUpload: () => void;
  assistantOrigin: AssistantOrigin | null;
  setAssistantOrigin: (origin: AssistantOrigin | null) => void;
}

const Ctx = createContext<CaseCtx | null>(null);

export function CaseProvider({ children }: { children: ReactNode }) {
  const [caseId, setCaseIdState] = useState(() => localStorage.getItem("mz.case") || CASE_ID_DEFAULT);
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [expired, setExpired] = useState(false);
  const caseRef = useRef(caseId);
  caseRef.current = caseId;
  // the session must cover the selected case: ask the service for one (demo mode) when it does not
  const ensureSession = useCallback(async () => {
    const want = caseRef.current;
    let s = await api.session().catch(() => null);
    if (s && !s.customer?.cases.some((c) => c.case_id === want) && s.demo_identity) {
      const issued = await api.demoCustomer(want).catch(() => null);
      if (issued) s = await api.session().catch(() => null);
    }
    setExpired(!!s && !s.customer?.cases.some((c) => c.case_id === want));
    setSession(s);
  }, []);
  useEffect(() => { ensureSession(); }, [caseId, ensureSession]);
  useEffect(() => {
    // a 401 (an expired session): obtain a new one for the selected case
    const onAuth = () => { ensureSession(); };
    window.addEventListener(AUTH_EVENT, onAuth);
    return () => window.removeEventListener(AUTH_EVENT, onAuth);
  }, [ensureSession]);
  const customer = session?.customer || null;
  const mine = (customer?.cases || []).map((c) => c.case_id);
  const ready = !!customer && mine.includes(caseId);
  const [assistant, setAssistant] = useState<{ open: boolean; prompt?: string }>({ open: false });
  const [upload, setUpload] = useState<CaseCtx["upload"]>({ open: false, nonce: 0 });
  const [assistantOrigin, setAssistantOrigin] = useState<AssistantOrigin | null>(null);
  const busy = (s: Snapshot | null) => !!s && s.readiness.pending_jobs.length > 0;
  // nothing is polled while signed out: the loaders resolve to null without a request
  const snap = usePolling<Snapshot | null>(() => (ready ? api.snapshot(caseId) : Promise.resolve(null)), [caseId, ready], busy);
  const docs = usePolling<DocView[] | null>(() => (ready ? api.documents(caseId) : Promise.resolve(null)), [caseId, ready],
    (d) => !!d && d.some((x) => x.status === "queued" || x.status === "processing"));
  const setCaseId = (id: string) => { localStorage.setItem("mz.case", id); setAssistantOrigin(null); setCaseIdState(id); };
  const openCase = (id: string) => setCaseId(id);
  // after a case switch the previous case's data stays in the pollers until the new case loads; never show it
  const current = ready && snap.data?.case.case_id === caseId ? snap.data : null;
  const value: CaseCtx = {
    auth: { status: session === undefined || (!ready && !expired) ? "loading" : ready ? "signed-in" : "signed-out", customer, expired,
      wantCase: null },
    openCase,
    caseId, setCaseId, snap: current, docs: current ? (docs.data || []).filter((d) => d.case_id === caseId) : [], error: snap.error,
    stale: !!current && !!snap.error && snap.failures >= 2, updatedAt: snap.updatedAt,
    reload: () => { snap.reload(); docs.reload(); },
    assistant, openAssistant: (prompt) => { setAssistantOrigin(null); setAssistant({ open: true, prompt }); },
    closeAssistant: () => setAssistant({ open: false }),
    upload, openUpload: (borrowerId, preset) => setUpload((u) => ({ open: true, borrowerId, ...preset, nonce: u.nonce + 1 })),
    closeUpload: () => setUpload((u) => ({ open: false, nonce: u.nonce })),
    assistantOrigin, setAssistantOrigin,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCase(): CaseCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCase outside CaseProvider");
  return v;
}
