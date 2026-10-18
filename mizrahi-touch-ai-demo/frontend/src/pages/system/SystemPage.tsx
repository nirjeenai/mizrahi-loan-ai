import { useState } from "react";
import { api, usePolling, type AccessError } from "../../api";
import { Loc, useLang } from "../../i18n";
import { ConsoleTop } from "../banker/BankerConsole";

export function SystemPage() {
  const { en, t } = useLang();
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
        <h2 style={{ color: "var(--mz-ink)" }}>{t("מטריצת אינטגרציות", "Integration matrix")}</h2>
        <div className="panel" style={{ overflowX: "auto" }}>
          <table className="t"><thead><tr><th>{t("רכיב", "Component")}</th><th>{t("מצב", "State")}</th><th>{t("פירוט", "Details")}</th></tr></thead>
            <tbody>{(m?.matrix || []).map((r: any) => (<tr key={r.component}><td className="bold">{r.component}</td>
              <td><span className={`mode ${r.state.startsWith("CONNECTED") ? "LOCAL" : r.state}`}>{r.state}</span></td><td className="small ltr" style={{ textAlign: "left" }}>{r.detail}</td></tr>))}</tbody></table>
        </div>
        <div className="grid2">
          <div className="panel"><h3>{t("Gemini, שימוש ועלויות (ספר קריאות)", "Gemini usage and costs (call ledger)")}</h3>
            {m && (<><div className="grid3">
              <div className="statbox"><b>{m.llm.calls}</b><span>{t("קריאות מודל", "Model calls")}</span></div>
              <div className="statbox"><b>{Math.round((m.llm.prompt_tokens + m.llm.output_tokens) / 1000)}K</b><span>{t("טוקנים", "Tokens")}</span></div>
              <div className="statbox"><b>{m.llm.avg_latency_ms}ms</b><span>{t("זמן ממוצע", "Average latency")}</span></div></div>
              <table className="t" style={{ marginTop: 10 }}><thead><tr><th>{t("מטרה", "Purpose")}</th><th>{t("קריאות", "Calls")}</th><th>{t("ממוצע ms", "Average ms")}</th></tr></thead>
                <tbody>{m.llm.by_purpose.map((b: any) => <tr key={b.purpose}><td className="ltr">{b.purpose}</td><td>{b.calls}</td><td>{Math.round(b.avg_ms)}</td></tr>)}</tbody></table>
              <div className="tiny muted" style={{ marginTop: 6 }}>{t("תקציב", "Budget")}: {m.llm.calls_last_hour}/{m.llm.budget_per_hour} {t("קריאות בשעה האחרונה.", "calls in the last hour.")}</div></>)}
          </div>
          <div className="panel"><h3>{t("שרת MCP של תיק ההלוואה, בדיקה חיה", "Loan case MCP server, live check")}</h3>
            <div className="small muted" style={{ marginBottom: 8 }}>{t("השרת מריץ סבב MCP אמיתי מול ‎/mcp‎ (initialize → tools/list → tools/call) עם מפתח הקשור לתיק, ומשווה לתמונת המצב של האפליקציה.",
              "The server runs a real MCP round against /mcp (initialize → tools/list → tools/call) with a case-bound key, and compares it with the app's snapshot.")}</div>
            <button className="btn btn-dark" disabled={mcpBusy} data-testid="mcp-selftest" onClick={async () => { setMcpBusy(true); setMcpError(null);
              try {
                const me = await api.session();
                if (!me.staff && me.demo_identity) await api.demoStaff();
                setMcp(await api.mcpSelftest());
              } catch (e) { setMcpError((e as AccessError).status === 401 ? t("הבדיקה קוראת נתוני תיק ולכן זמינה רק לצוות הבנק.", "The check reads case data, so it's available to bank staff only.") : (e as Error).message); }
              finally { setMcpBusy(false); } }}>
              {mcpBusy ? <span className="spinner" /> : null}{t("הרצת בדיקת MCP", "Run MCP check")}</button>
            {mcpError && <div className="notice small" role="alert" style={{ marginTop: 8 }} data-testid="mcp-error">{mcpError}</div>}
            {mcp && (<>
              <div className="row" style={{ marginTop: 10, flexWrap: "wrap" }}>
                <span className={`badge ${mcp.consistent ? "ok" : "bad"}`} data-testid="mcp-consistent">{mcp.consistent ? t("תואם לאפליקציה", "Consistent with the app") : t("לא תואם", "Not consistent")}</span>
                <span className="badge neutral ltr">protocol {mcp.protocol}</span><span className="badge neutral">{mcp.tools.length} {t("כלים", "tools")}</span>
                <span className={`badge ${mcp.cross_case_denied ? "ok" : "bad"}`}>{mcp.cross_case_denied ? t("גישה בין תיקים נחסמה", "Cross-case access denied") : t("בידוד תיקים נכשל", "Case isolation failed")}</span>
              </div>
              <pre className="json">{JSON.stringify(mcp.exchange, null, 2)}</pre></>)}
          </div>
        </div>
        <div className="panel"><h3>{t("רובריקות בגרסאות", "Versioned rubrics")}</h3>
          {(rubrics.data || []).map((r: any) => (<details key={`${r.rubric_id}@${r.version}`} style={{ marginBottom: 8 }}>
            <summary className="bold" style={{ cursor: "pointer" }}><span className="ltr">{r.rubric_id}@{r.version}</span> · <Loc he={r.title_he} en={r.title_en} /> · {r.criteria.length} {t("קריטריונים", "criteria")}</summary>
            {r.changelog && <div className="tiny muted" style={{ margin: "6px 0" }}>{r.changelog.map((c: any) => `${c.version}: ${c.changes.join(" ")}`).join(" | ")}</div>}
            <table className="t"><tbody>{r.criteria.map((c: any) => <tr key={c.id}><td className="ltr tiny">{c.id}</td><td><Loc he={c.title_he} en={c.title_en} /></td><td className="tiny">{c.method}</td><td className="tiny">{c.on_fail || c.severity}</td><td className="ltr tiny">{c.reason_code}</td></tr>)}</tbody></table>
          </details>))}
        </div>
        <div className="panel small"><h3>{t("גבול האינטגרציה של VisionTrace", "The VisionTrace integration boundary")}</h3>
          {en ? <div>The document review provider is selected in one place (<span className="ltr">REVIEW_PROVIDER</span>). Active provider: <b className="ltr">{m?.provider}</b>.
            VisionTraceReviewProvider is implemented against the same full contract (start review, status, facts, criteria, verdict, evidence, cross-document consistency, re-review) and will be enabled only after a real document review runs through it and is verified.
            An MCP connection that only lists processes is not a document review integration.</div>
            : <div>ספק בדיקת המסמכים נבחר בנקודה אחת (<span className="ltr">REVIEW_PROVIDER</span>). הספק הפעיל: <b className="ltr">{m?.provider}</b>.
            VisionTraceReviewProvider ממומש מול אותו חוזה מלא (התחלת בדיקה, סטטוס, עובדות, קריטריונים, פסק דין, ראיות, עקביות בין מסמכים, בדיקה חוזרת) ויופעל רק אחרי שבדיקת מסמכים אמיתית תרוץ דרכו ותאומת.
            חיבור MCP שמציג רשימת תהליכים בלבד אינו אינטגרציה של בדיקת מסמכים.</div>}
        </div>
      </main>
    </div>
  );
}
