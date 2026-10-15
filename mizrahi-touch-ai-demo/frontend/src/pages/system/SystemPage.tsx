import { useState } from "react";
import { api, usePolling, type AccessError } from "../../api";
import { ConsoleTop } from "../banker/BankerConsole";

export function SystemPage() {
  const integ = usePolling(() => api.integrations(), [], () => false);
  const rubrics = usePolling(() => api.rubrics(), [], () => false);
  const [mcp, setMcp] = useState<any>(null);
  const [mcpBusy, setMcpBusy] = useState(false);
  const [mcpError, setMcpError] = useState<string | null>(null);
  const m = integ.data;
  return (
    <div className="console">
      <ConsoleTop active="system" />
      <main className="console-main" style={{ maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <h2 style={{ color: "var(--mz-ink)" }}>מטריצת אינטגרציות</h2>
        <div className="panel" style={{ overflowX: "auto" }}>
          <table className="t"><thead><tr><th>רכיב</th><th>מצב</th><th>פירוט</th></tr></thead>
            <tbody>{(m?.matrix || []).map((r: any) => (<tr key={r.component}><td className="bold">{r.component}</td>
              <td><span className={`mode ${r.state.startsWith("CONNECTED") ? "LOCAL" : r.state}`}>{r.state}</span></td><td className="small ltr" style={{ textAlign: "left" }}>{r.detail}</td></tr>))}</tbody></table>
        </div>
        <div className="grid2">
          <div className="panel"><h3>Gemini — שימוש ועלויות (ספר קריאות)</h3>
            {m && (<><div className="grid3">
              <div className="statbox"><b>{m.llm.calls}</b><span>קריאות מודל</span></div>
              <div className="statbox"><b>{Math.round((m.llm.prompt_tokens + m.llm.output_tokens) / 1000)}K</b><span>טוקנים</span></div>
              <div className="statbox"><b>{m.llm.avg_latency_ms}ms</b><span>זמן ממוצע</span></div></div>
              <table className="t" style={{ marginTop: 10 }}><thead><tr><th>מטרה</th><th>קריאות</th><th>ממוצע ms</th></tr></thead>
                <tbody>{m.llm.by_purpose.map((b: any) => <tr key={b.purpose}><td className="ltr">{b.purpose}</td><td>{b.calls}</td><td>{Math.round(b.avg_ms)}</td></tr>)}</tbody></table>
              <div className="tiny muted" style={{ marginTop: 6 }}>תקציב: {m.llm.calls_last_hour}/{m.llm.budget_per_hour} קריאות בשעה האחרונה.</div></>)}
          </div>
          <div className="panel"><h3>שרת MCP של תיק ההלוואה — בדיקה חיה</h3>
            <div className="small muted" style={{ marginBottom: 8 }}>השרת מריץ סבב MCP אמיתי מול ‎/mcp‎ (initialize → tools/list → tools/call) עם מפתח הקשור לתיק, ומשווה לתמונת המצב של האפליקציה.</div>
            <button className="btn btn-dark" disabled={mcpBusy} data-testid="mcp-selftest" onClick={async () => { setMcpBusy(true); setMcpError(null);
              try {
                const me = await api.session();
                if (!me.staff && me.demo_identity) await api.demoStaff();
                setMcp(await api.mcpSelftest());
              } catch (e) { setMcpError((e as AccessError).status === 401 ? "הבדיקה קוראת נתוני תיק ולכן זמינה רק לצוות הבנק." : (e as Error).message); }
              finally { setMcpBusy(false); } }}>
              {mcpBusy ? <span className="spinner" /> : null}הרצת בדיקת MCP</button>
            {mcpError && <div className="notice small" role="alert" style={{ marginTop: 8 }} data-testid="mcp-error">{mcpError}</div>}
            {mcp && (<>
              <div className="row" style={{ marginTop: 10, flexWrap: "wrap" }}>
                <span className={`badge ${mcp.consistent ? "ok" : "bad"}`} data-testid="mcp-consistent">{mcp.consistent ? "תואם לאפליקציה" : "לא תואם"}</span>
                <span className="badge neutral ltr">protocol {mcp.protocol}</span><span className="badge neutral">{mcp.tools.length} כלים</span>
                <span className={`badge ${mcp.cross_case_denied ? "ok" : "bad"}`}>{mcp.cross_case_denied ? "גישה בין תיקים נחסמה" : "בידוד תיקים נכשל"}</span>
              </div>
              <pre className="json">{JSON.stringify(mcp.exchange, null, 2)}</pre></>)}
          </div>
        </div>
        <div className="panel"><h3>רובריקות בגרסאות</h3>
          {(rubrics.data || []).map((r: any) => (<details key={`${r.rubric_id}@${r.version}`} style={{ marginBottom: 8 }}>
            <summary className="bold" style={{ cursor: "pointer" }}><span className="ltr">{r.rubric_id}@{r.version}</span> · {r.title_he} · {r.criteria.length} קריטריונים</summary>
            {r.changelog && <div className="tiny muted" style={{ margin: "6px 0" }}>{r.changelog.map((c: any) => `${c.version}: ${c.changes.join(" ")}`).join(" | ")}</div>}
            <table className="t"><tbody>{r.criteria.map((c: any) => <tr key={c.id}><td className="ltr tiny">{c.id}</td><td>{c.title_he}</td><td className="tiny">{c.method}</td><td className="tiny">{c.on_fail || c.severity}</td><td className="ltr tiny">{c.reason_code}</td></tr>)}</tbody></table>
          </details>))}
        </div>
        <div className="panel small"><h3>גבול האינטגרציה של VisionTrace</h3>
          <div>ספק בדיקת המסמכים נבחר בנקודה אחת (<span className="ltr">REVIEW_PROVIDER</span>). הספק הפעיל: <b className="ltr">{m?.provider}</b>.
            VisionTraceReviewProvider ממומש מול אותו חוזה מלא (התחלת בדיקה, סטטוס, עובדות, קריטריונים, פסק דין, ראיות, עקביות בין מסמכים, בדיקה חוזרת) ויופעל רק אחרי שבדיקת מסמכים אמיתית תרוץ דרכו ותאומת.
            חיבור MCP שמציג רשימת תהליכים בלבד אינו אינטגרציה של בדיקת מסמכים.</div>
        </div>
      </main>
    </div>
  );
}
