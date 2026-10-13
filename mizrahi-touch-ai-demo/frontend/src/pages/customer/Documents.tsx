import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ils, monthHe, timeHe, VERDICT_HE, type Requirement } from "../../api";
import { useCase } from "../../caseContext";
import { ICheck, IClock, IChevron, IX } from "../../components/Icons";

function MonthChips({ r }: { r: Requirement }) {
  return (
    <div className="month-chips">
      {(r.requested_months || []).map((m) => {
        const copies = r.duplicates?.[m];
        const covered = r.covered?.includes(m);
        if (!covered) return <span key={m} className="mchip miss"><IX size={11} />{monthHe(m)} חסר</span>;
        if (r.pending_review?.includes(m)) return <span key={m} className="mchip review"><IClock size={11} />{monthHe(m)} · בבדיקה</span>;
        if (copies) return <span key={m} className="mchip dup"><ICheck size={11} />{monthHe(m)} ×{copies}</span>;
        return <span key={m} className="mchip ok"><ICheck size={11} />{monthHe(m)}</span>;
      })}
    </div>
  );
}

export function Documents() {
  const { snap, docs, openUpload, openAssistant, caseId, reload } = useCase();
  const nav = useNavigate();
  const [tab, setTab] = useState<"list" | "bank">("list");
  const [params, setParams] = useSearchParams();
  const [focus, setFocus] = useState<string | null>(null);
  const [linkNote, setLinkNote] = useState<string | null>(null);
  const [replying, setReplying] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [replyBusy, setReplyBusy] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);
  const loaded = !!snap;
  useEffect(() => {
    if (!snap) return;
    const want = params.get("upload"), section = params.get("focus"), forCase = params.get("case"), reqId = params.get("request");
    const replace = params.get("replace");
    if (!want && !section && !reqId && !replace) return;
    setParams({}, { replace: true });
    setTab("list");
    if (forCase && forCase !== caseId) { setLinkNote("הקישור שייך לתיק אחר ולכן לא נפתח. מוצג התיק הפעיל שלכם."); return; }
    setLinkNote(null);
    if (replace) {
      // replace=<document>: the upload that replaces a document the AI review sent back (checked again by the server)
      const old = docs.find((d) => d.document_id === replace);
      if (snap.outcomes?.documents[replace]?.outcome !== "BLOCKER") { setLinkNote("המסמך הזה כבר אינו ממתין להחלפה."); return; }
      setFocus("sec-uploaded");
      openUpload(old?.borrower_id || snap.case.borrowers[0]?.borrower_id, { requirementCode: old?.requirement_code || undefined, replacesDocumentId: replace });
      return;
    }
    if (reqId) {
      const q = snap.customer_requests?.find((x) => x.customer_request_id === reqId);
      if (!q) { setLinkNote("הבקשה לא נמצאה בתיק הפעיל."); return; }
      setFocus(`creq-${q.customer_request_id}`);
      if (q.status !== "OPEN") { setLinkNote("כבר השבתם לבקשה הזו. היא אצל הבנקאי."); return; }
      if (q.can_reply) { setReplying(q.customer_request_id); return; }
      openUpload(q.borrower_id || undefined, { requirementCode: q.requirement_code || undefined, period: q.period, customerRequestId: q.customer_request_id });
      return;
    }
    if (!want) {
      // focus=PAYSLIPS:<borrower> opens on that borrower's payslip card (home-screen summary rows)
      const one = section && snap.readiness.requirements.some((r) => r.code === section && r.evaluated_by_ai) ? `req-${section}` : null;
      setFocus(section === "uploaded" ? "sec-uploaded" : one || "sec-payslips");
      return;
    }
    const req = snap.readiness.requirements.find((r) => r.code === want && r.evaluated_by_ai && r.borrower_id);
    if (!req) { setLinkNote("לא ניתן להעלות את סוג המסמך הזה באפליקציה."); return; }
    setFocus(`req-${req.code}`);
    openUpload(req.borrower_id!, { requirementCode: req.code, period: params.get("period") });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, loaded]);
  useEffect(() => {
    if (focus) document.getElementById(focus)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focus]);
  if (!snap) return null;
  const reqs = snap.readiness.requirements;
  const payslips = reqs.filter((r) => r.evaluated_by_ai);
  const others = reqs.filter((r) => !r.evaluated_by_ai);
  const reviewedValid = docs.filter((d) => d.review?.verdict === "VALID").length;
  const customerFindings = snap.findings.filter((f) => f.status === "open" && f.review_state === "CUSTOMER_ACTION_REQUIRED");
  const borrowerName = (id?: string | null) => snap.case.borrowers.find((b) => b.borrower_id === id)?.first_name_he || "";
  const docStatus = snap.document_status || {};
  const requests = (snap.customer_requests || []).filter((q) => q.status === "OPEN" || !!q.responded_text
    || (q.responded_document_id && docStatus[q.responded_document_id]?.status !== "ACCEPTED"));
  const docName = (id?: string | null) => docs.find((d) => d.document_id === id)?.filename;
  return (
    <>
      <div className="page-title">מסמכים</div>
      <p className="page-sub">ריכזנו עבורכם את רשימת המסמכים הנחוצים להשלמת תהליך קבלת המשכנתה. מסמכי השכר נבדקים בבדיקה חכמה מיד עם ההעלאה.</p>
      <div className="segmented" role="tablist">
        <button className={tab === "list" ? "on" : ""} onClick={() => setTab("list")} role="tab">רשימת מסמכים</button>
        <button className={tab === "bank" ? "on" : ""} onClick={() => setTab("bank")} role="tab">אישורים מהבנק</button>
      </div>
      {linkNote && <div className="notice" role="status" style={{ marginBottom: 12 }} data-testid="link-note">{linkNote}</div>}
      {tab === "list" && (<>
        {requests.length > 0 && (<>
          <div className="section-label" id="sec-requests">בקשות מ{snap.case.banker.name_he}</div>
          {requests.map((q) => {
            const open = q.status === "OPEN";
            const replacement = docs.find((d) => d.document_id === q.responded_document_id);
            return (
              <div key={q.customer_request_id} id={`creq-${q.customer_request_id}`} data-testid="customer-request" data-status={q.status}
                className={`creq-card${open ? " open" : ""}${focus === `creq-${q.customer_request_id}` ? " focus" : ""}`}>
                <div className="creq-from">{open ? "בקשה חדשה" : "המסמך התקבל"} · {q.created_by_name || snap.case.banker.name_he} · <span className="ltr">{timeHe(q.created_at)}</span></div>
                <div className="creq-title">{q.title_he}</div>
                <div className="creq-msg">{q.message_he}</div>
                {q.document_filename && <div className="tiny muted">המסמך שהוחזר: <span className="ltr">{q.document_filename}</span></div>}
                {open && q.can_reply ? (<>
                  {replying === q.customer_request_id ? (
                    <div className="creq-reply" data-testid="request-reply">
                      <textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="כתבו כאן את ההסבר" maxLength={1000} data-testid="request-reply-text" />
                      <div className="tiny muted">ההסבר יישמר בתיק ויועבר ל{snap.case.banker.name_he}. הוא אינו סוגר את הבירור; ייתכן שתתבקשו גם מסמך תומך.</div>
                      {replyError && <div className="small" role="alert" style={{ color: "var(--bad)" }}>{replyError}</div>}
                      <div className="creq-btns">
                        <button className="btn btn-orange" disabled={replyBusy || !reply.trim()} data-testid="request-reply-send" onClick={async () => {
                          setReplyBusy(true); setReplyError(null);
                          try { await api.replyToRequest(caseId, q.customer_request_id, reply.trim()); setReplying(null); setReply(""); reload(); }
                          catch (e) { setReplyError((e as Error).message); } finally { setReplyBusy(false); }
                        }}>{replyBusy && <span className="spinner" />}שליחת ההסבר</button>
                        <button className="btn btn-soft" onClick={() => setReplying(null)}>ביטול</button>
                      </div>
                    </div>
                  ) : (
                    <div className="creq-btns">
                      <button className="btn btn-orange" data-testid="request-reply-open" onClick={() => setReplying(q.customer_request_id)}>השבה בכתב</button>
                      <button className="btn btn-ghost" data-testid="request-upload" onClick={() => openUpload(q.borrower_id || undefined,
                        { requirementCode: q.requirement_code || undefined, period: q.period, customerRequestId: q.customer_request_id })}>צירוף מסמך</button>
                    </div>
                  )}
                </>) : open ? (
                  <button className="btn btn-orange creq-btn" data-testid="request-upload"
                    onClick={() => openUpload(q.borrower_id || undefined, { requirementCode: q.requirement_code || undefined, period: q.period,
                      customerRequestId: q.customer_request_id })}>להעלאת המסמך</button>
                ) : q.responded_text ? (
                  <div className="small creq-done" data-testid="request-answered">השבתם: „{q.responded_text}”. ההסבר הועבר ל{snap.case.banker.name_he}.</div>
                ) : (
                  <div className="small creq-done" data-testid="request-answered">
                    העליתם את <span className="ltr">{q.responded_filename || replacement?.filename}</span>
                    {replacement && !replacement.review ? " — בבדיקה חכמה עכשיו." : ` — נבדק וממתין לעיון של ${snap.case.banker.name_he}.`}
                  </div>
                )}
              </div>
            );
          })}
        </>)}
        <div className="card card-row tight">
          <span className="circle-icon small" style={{ background: "var(--ok)" }}><ICheck size={16} /></span>
          <span className="grow bold" style={{ color: "var(--mz-ink)" }}>{reviewedValid} מסמכים נמצאו תקינים בבדיקה החכמה</span>
          <span className="tiny muted">טרם אושרו בבנק</span>
        </div>

        <div className="section-label" id="sec-payslips">תלושי שכר — לטיפולכם</div>
        {payslips.map((r) => {
          const mine = customerFindings.filter((f) => f.borrower_id === r.borrower_id);
          const open = r.ai_state === "required_missing" || (r.missing?.length ?? 0) > 0 || mine.length > 0;
          const focused = focus === `req-${r.code}` || (focus === "sec-payslips" && open);
          return (
            <div className={`req-card${focused ? " focus" : ""}`} key={r.code} id={`req-${r.code}`} data-testid={`req-${r.code}`}
              data-focused={focused ? "true" : undefined}>
              <div className="req-body">
                <div className="row between">
                  <div><div className="req-title">{r.title_he}</div>{(r.missing?.length ?? 0) > 0 && <div className="req-new">חדש · חסר מסמך</div>}</div>
                  <span className={`badge ${r.ai_state === "extracted" || r.ai_state === "preparation_confirmed" ? "ok" : r.ai_state === "needs_banker_review" ? "info" : r.ai_state === "checking" ? "neutral" : "warn"}`}>
                    {r.ai_state === "checking" && <span className="spinner" />}{r.ai_state_he}
                  </span>
                </div>
                <MonthChips r={r} />
                {mine.map((f) => <div key={f.finding_id} className="small" style={{ marginTop: 6, lineHeight: 1.55 }}>• {f.message_he}</div>)}
                <div className="req-actions">
                  <button className="link" onClick={() => openAssistant(`מה בדיוק צריך להעלות עבור ${borrowerName(r.borrower_id)}?`)}>למידע נוסף</button>
                  <button className="btn btn-dark" onClick={() => openUpload(r.borrower_id || undefined, { requirementCode: r.code })}
                    data-testid={`upload-${r.borrower_id}`}>להעלאה</button>
                </div>
              </div>
              <div className="bank-strip"><span className="row" style={{ gap: 6 }}><IClock size={13} />ממתין לאישור הבנק</span></div>
            </div>
          );
        })}

        <div className="section-label" id="sec-uploaded">מסמכים שהועלו ({docs.length})</div>
        {docs.length === 0 && <div className="card small muted">עוד לא הועלו מסמכים. לחצו ״להעלאה״ באחד הכרטיסים.</div>}
        {docs.map((d) => (
          <button key={d.document_id} className="doc-card pressable" onClick={() => nav(`/customer/documents/${d.document_id}`)} data-testid="doc-card">
            <span className="doc-icon">{d.mime === "application/pdf" ? "PDF" : "IMG"}</span>
            <span className="grow">
              <div className="doc-name">{d.filename}</div>
              <div className="doc-meta">
                {borrowerName(d.borrower_id)}{d.review?.period ? ` · מודפס ${monthHe(d.review.period)}` : ""}{d.review?.is_scanned ? " · סרוק" : ""}
                {d.review?.facts.find((f) => f.field === "net_pay") ? ` · נטו ${ils(Number(d.review.facts.find((f) => f.field === "net_pay")!.value_normalized))}` : ""}
              </div>
              {docStatus[d.document_id] && (
                <div className={`doc-banker ${docStatus[d.document_id].status}`} data-testid="doc-banker-status">
                  {docStatus[d.document_id].status_he}
                  {docStatus[d.document_id].replaces && docName(docStatus[d.document_id].replaces) ? ` במקום ${docName(docStatus[d.document_id].replaces)}` : ""}
                </div>
              )}
            </span>
            {d.review ? <span className={`badge ${d.review.verdict}`} data-testid="doc-verdict">{VERDICT_HE[d.review.verdict]}</span>
              : d.status === "failed" ? <span className="badge bad">נכשל</span>
                : <span className="badge neutral"><span className="spinner" />{d.stage_he}</span>}
            <span className="chev"><IChevron size={16} /></span>
          </button>
        ))}

        <div className="section-label">מסמכים נוספים בתיק</div>
        {others.map((r) => (
          <div key={r.code} className="card tight row between">
            <span className="small" style={{ color: "var(--mz-ink)", fontWeight: 600 }}>{r.title_he}</span>
            <span className="badge neutral">לא נבדק בהדגמה</span>
          </div>
        ))}
      </>)}
      {tab === "bank" && (<>
        {snap.case.preliminary_decision && (
          <div className="card">
            <div className="card-title">{snap.case.preliminary_decision.label_he}</div>
            <div className="kv"><span>סכום</span><span className="ltr">{ils(snap.case.preliminary_decision.amount_ils)}</span></div>
            <div className="kv"><span>הונפק</span><span className="ltr">{snap.case.preliminary_decision.issued_on}</span></div>
            <div className="kv"><span>בתוקף עד</span><span className="ltr">{snap.case.preliminary_decision.valid_until}</span></div>
            <div className="tiny muted" style={{ marginTop: 8 }}>אישור עקרוני כפוף לאימות הנתונים ואינו אישור סופי.</div>
          </div>
        )}
        {snap.readiness.banker_confirmation ? (
          <div className="card"><div className="card-title">הבנקאית אישרה את הכנת מסמכי השכר</div>
            <div className="small muted" style={{ marginTop: 4 }}>אישור הכנת מסמכים בלבד — לא החלטה על המשכנתא.</div></div>
        ) : <div className="card small muted">אישורים נוספים מהבנק יופיעו כאן כשהבנק ינפיק אותם.</div>}
      </>)}
    </>
  );
}
