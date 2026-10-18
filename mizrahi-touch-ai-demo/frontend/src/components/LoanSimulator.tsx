import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, monthHe, monthL, type Simulation, type SimSnapshot } from "../api";
import { tr, useLang } from "../i18n";
import {
  affordability, comparison, compute, ilsWhole, issueMessageEn, issues as ruleIssues, normalize, shortIssue, shortIssueEn, targetSolution,
  type DeferralPolicy, type Issue, type Params, type Product,
} from "../loanCalc";
import { IAlert, ICheck, IChevronDown } from "./Icons";
import "../loanSimulator.css";

/** Product, rate and asset labels in the app's language (the server sends the English beside the Hebrew). */
const pLabel = (p: Product) => tr(p.label_he, p.label_en || p.label_he);
const rLabel = (r: Product["rate"]) => tr(r.label_he, r.label_en || r.label_he);
const aLabel = (p: Product) => tr(p.asset!.label_he, p.asset!.label_en || p.asset!.label_he);
const short = (i: Issue, p: Product) => tr(shortIssue(i, p), shortIssueEn(i, p));
const fullIssue = (i: Issue, p: Product) => tr(i.message_he, issueMessageEn(i, p));
/** English money as the card shows it: "₪12,345" (Hebrew keeps "12,345 ₪") */
const ilsW = (n: number) => tr(ilsWhole(n), `₪${Math.round(n).toLocaleString("en-US")}`);

/** The loan simulator, as part of the assistant's message in the application chat (/customer/apply). Moving a control
 *  recalculates here, with the same deterministic engine as the server (loanCalc.ts ↔ loan_calc.py), and saves an
 *  unconfirmed draft without a message; "זה התרחיש שלי" sends one turn, and the server records amount and payments
 *  through the questionnaire. Products, limits and the rate come from the server; nothing on this card decides a term. */
export function LoanSimulator({ sim, draftId, busy, onConfirm, registerFlush }: {
  sim: Simulation; draftId: string; busy: boolean;
  onConfirm: (scenario: Partial<Params> & { product: string }, label: string) => void;
  registerFlush: (fn: (() => Promise<void>) | null) => void;
}) {
  const pending = sim.status === "pending";
  const { en, t } = useLang();
  const [open, setOpen] = useState(pending);
  const [picking, setPicking] = useState(false);
  const [pid, setPid] = useState(sim.product_id);
  const product = sim.candidates.find((c) => c.id === pid) ?? sim.candidates[0];
  const fromServer = () => normalize(sim.candidates.find((c) => c.id === sim.product_id) ?? sim.candidates[0],
    (pending ? sim.draft : sim.confirmed) ?? sim.draft);
  const [prm, setPrm] = useState<Params>(fromServer);
  const [obligations, setObligations] = useState<string>(sim.context.obligations != null ? String(sim.context.obligations) : "");
  useEffect(() => {          // a server-side change (rev) resets the card; local moves do not
    setPid(sim.product_id);
    setPrm(fromServer());
    setOpen(pending);
    setPicking(false);
    setObligations(sim.context.obligations != null ? String(sim.context.obligations) : "");
  }, [sim.rev, sim.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- draft persistence: debounced, no message, flushed before the next chat turn
  const timer = useRef<number | undefined>();
  const latest = useRef<() => Promise<void>>(async () => {});
  const save = useCallback((p: Params, id: string, ob: string) => {
    window.clearTimeout(timer.current);
    const run = async () => {
      timer.current = undefined;
      try { await api.chatSimulation(draftId, { ...p, product: id, obligations: ob.trim() ? Number(ob.replace(/\D/g, "")) : null }); } catch { /* the next turn re-sends */ }
    };
    latest.current = run;
    timer.current = window.setTimeout(run, 450);
  }, [draftId]);
  useEffect(() => {
    registerFlush(async () => { if (timer.current !== undefined) { window.clearTimeout(timer.current); await latest.current(); } });
    return () => registerFlush(null);
  }, [registerFlush]);

  const set = (patch: Partial<Params>) => setPrm((cur) => { const next = normalize(product, { ...cur, ...patch }); save(next, pid, obligations); return next; });
  const switchProduct = (id: string) => {
    const np = sim.candidates.find((c) => c.id === id)!;
    setPid(id);
    setPicking(false);
    setPrm((cur) => { const next = normalize(np, cur); save(next, id, obligations); return next; });
  };

  // ---- deterministic evaluation (local, instant)
  const result = useMemo(() => compute(product, prm, sim.start_month), [product, prm, sim.start_month]);
  const found = useMemo(() => ruleIssues(product, prm), [product, prm]);
  const blocking = useMemo(() => ruleIssues(product, prm, true), [product, prm]);
  const ob = obligations.trim() ? Number(obligations.replace(/\D/g, "")) : sim.context.obligations;
  const afford = result ? affordability(result.monthly_payment, sim.context.net_income, ob ?? null) : null;
  const target = targetSolution(product, prm, sim.context.target_monthly, sim.start_month);
  const compare = result ? comparison(product, prm, sim.start_month) : [];
  const c = sim.confirmed;
  const changed = !pending && c && (prm.amount !== c.amount || prm.term !== c.term || pid !== sim.product_id
    || prm.asset_price !== c.asset_price || prm.asset_unknown !== c.asset_unknown || prm.deferral_months !== c.deferral_months
    || prm.deferral_policy !== c.deferral_policy || prm.model !== c.model || prm.rate_change_pct !== c.rate_change_pct);

  const confirm = () => {
    if (blocking.length || busy) return;
    onConfirm({ ...prm, product: pid }, `זה התרחיש שלי: ${ilsWhole(prm.amount)} ב־${prm.term} תשלומים`);   // the echo the server records (it words it in each language)
  };

  const state = !pending && !open ? "confirmed" : pending && !sim.editing ? "draft" : "editing";
  const common = { "data-testid": "ls-card", "data-state": state, "data-product": pid, "data-monthly": result?.monthly_payment ?? "",
    "data-amount": prm.amount, "data-term": prm.term, "aria-label": t("סימולציית הלוואה", "Loan simulation") };

  if (state === "confirmed") {
    return (
      <section className="ls ls-confirmed" {...common}>
        <Compact product={product} prm={prm} monthly={result?.monthly_payment ?? null} afford={afford} busy={busy} onEdit={() => setOpen(true)} />
      </section>
    );
  }
  return (
    <section className={`ls ls-${state}`} {...common}>
      <span className="ls-strip" aria-hidden><i /><i /><i /></span>
      <header className="ls-head">
        <img className="ls-mark" src="/brand/jeen-mark.png" alt="" />
        {sim.candidates.length > 1 ? (
          <button className="ls-product" aria-expanded={picking} onClick={() => setPicking((x) => !x)} disabled={busy} data-testid="ls-product">
            <span>{pLabel(product)}</span><IChevronDown size={14} />
          </button>
        ) : <span className="ls-product static">{pLabel(product)}</span>}
        <RateTag rate={product.rate} />
      </header>
      {picking && (
        <div className="ls-tracks" role="radiogroup" aria-label={t("מסלול לסימולציה", "Product for the simulation")} data-testid="ls-tracks">
          {sim.candidates.map((x) => (
            <button key={x.id} role="radio" aria-checked={x.id === pid} className={x.id === pid ? "on" : ""} disabled={busy}
              onClick={() => switchProduct(x.id)} data-testid="ls-track" data-id={x.id}>{pLabel(x)}</button>
          ))}
          <span className="ls-tracks-note">{t("המסלול לסימולציה בלבד, את המסלול בפועל קובע הבנק", "The product is for the simulation only — the bank sets the actual product")}</span>
        </div>
      )}

      <Hero product={product} result={result} />

      <div className="ls-controls">
        <Slider id="amount" label={sim.amount_field === "business_amount" ? t("סכום המימון", "Financing amount") : t("סכום", "Amount")} unit="₪"
          value={prm.amount} min={product.bounds.amount_min} max={product.bounds.amount_max} step={product.bounds.amount_step}
          onChange={(v) => set({ amount: v })} disabled={busy} format={(v) => v.toLocaleString("en-US")} />
        <Slider id="term" label={t("תקופה", "Term")} unit={t("חודשים", "months")} value={prm.term} min={product.bounds.term_min} max={product.bounds.term_max} step={1}
          hint={en ? (prm.term % 12 === 0 ? `${prm.term / 12} ${prm.term === 12 ? "year" : "years"}` : `${(prm.term / 12).toFixed(1)} years`)
            : prm.term % 12 === 0 ? `${prm.term / 12} ${prm.term === 12 ? "שנה" : "שנים"}` : `${(prm.term / 12).toFixed(1)} שנים`}
          onChange={(v) => set({ term: v })} disabled={busy} format={(v) => String(v)} />
        {product.asset && <AssetField product={product} prm={prm} onChange={set} disabled={busy} />}
      </div>

      {found.length > 0 && <Issues list={found} product={product} onFix={(i) => set(i.field === "term" ? { term: i.fix! } : { amount: i.fix! })} disabled={busy} />}
      {target && <TargetLine t={target} amount={prm.amount} onApply={(p) => set(p)} disabled={busy} />}
      {sim.context.net_income != null && result && (
        <Personal afford={afford} ctx={sim.context} obligations={obligations} disabled={busy}
          onObligations={(v) => { setObligations(v); save(prm, pid, v); }} compare={compare} onTerm={(t) => set({ term: t })} />
      )}
      <Options product={product} prm={prm} result={result} set={set} disabled={busy} start={sim.start_month} />

      <footer className="ls-foot">
        {blocking.length > 0 && !found.length && <p className="ls-need" data-testid="ls-need" title={fullIssue(blocking[0], product)}>{short(blocking[0], product)}</p>}
        <div className="ls-actions">
          <button className="ls-confirm" disabled={busy || blocking.length > 0 || (!pending && !changed)} onClick={confirm} data-testid="ls-confirm">
            <ICheck size={15} />{pending ? t("זה התרחיש שלי", "This is my scenario") : t("עדכון התרחיש", "Update the scenario")}</button>
          {!pending && <button className="ls-link" onClick={() => { setOpen(false); setPrm(fromServer()); setPid(sim.product_id); }} disabled={busy}
            data-testid="ls-cancel">{t("ביטול", "Cancel")}</button>}
        </div>
        <p className="ls-fine">{pending ? t("המחשה, לא הצעת אשראי · נשמר בבקשה רק באישור", "An illustration, not a credit offer · saved to your application only when you confirm")
          : t("השינוי יחול על הבקשה רק אחרי עדכון", "The change applies to your application only after you update")}</p>
      </footer>
    </section>
  );
}

/** An earlier card in the transcript: a one-line record of what it showed. */
export function SimulatorSnapshot({ s }: { s: SimSnapshot }) {
  const { en, t } = useLang();
  return (
    <div className="ls-snap" data-testid="ls-snapshot">
      <img src="/brand/jeen-mark.png" alt="" aria-hidden />
      <span>{s.status === "confirmed" ? t("תרחיש שנבחר", "Chosen scenario") : t("טיוטה", "Draft")}</span>
      <span >{ilsW(s.amount)}</span>{en ? <span>· {s.term} payments</span> : <span>· {s.term} תשלומים</span>}
      {s.monthly_payment != null && <span>· <span >{ilsW(s.monthly_payment)}</span>{t(" בחודש", " a month")}</span>}
    </div>
  );
}

/** The rate the figures use, in the head: an illustration, a quote, or none. */
function RateTag({ rate }: { rate: Product["rate"] }) {
  const { t } = useLang();
  if (!rate.available) return <span className="ls-tag muted" data-testid="ls-badge">{t("ללא ריבית", "No rate")}</span>;
  const label = rate.source === "illustrative" ? t("המחשה", "Illustration") : rate.source === "bank_quote" ? t("הצעה אישית", "Personal quote") : t("תמחור מסלול", "Product pricing");
  return <span className="ls-tag" title={rLabel(rate)} data-testid="ls-badge">{label} · {rate.annual_rate_pct}%</span>;
}

/** The monthly figure and the cost ribbon: where every shekel of the repayment goes. */
function Hero({ product, result }: { product: Product; result: ReturnType<typeof compute> }) {
  const monthly = useTween(result?.monthly_payment ?? 0);
  const { en, t } = useLang();
  if (!result) {
    return (
      <div className="ls-hero none" data-testid="ls-hero" data-available="0">
        <p className="ls-none" data-testid="ls-rate-unavailable">{rLabel(product.rate)}{t(" בוחרים כאן סכום ותקופה, והם יגיעו לבקשה.", " Choose an amount and a term here, and they go into your application.")}</p>
      </div>
    );
  }
  const whole = Math.trunc(monthly), cents = Math.round((monthly - whole) * 100);
  const total = result.total_paid || 1;
  const parts = [{ k: "principal", v: result.principal, l: t("קרן", "Principal") }, { k: "interest", v: result.total_interest, l: t("ריבית", "Interest") },
    ...(result.total_fees ? [{ k: "fees", v: result.total_fees, l: t("עמלות", "Fees") }] : [])];
  const varies = result.max_payment - result.min_payment > 1;
  return (
    <div className="ls-hero" data-testid="ls-hero" data-available="1">
      <div className="ls-figure" data-testid="ls-monthly" aria-live="polite" title={rLabel(product.rate)}>
        {en ? <><i>₪</i><span className="ltr"><b>{whole.toLocaleString("en-US")}</b><small>.{String(cents).padStart(2, "0")}</small></span></>
          : <><span className="ltr"><b>{whole.toLocaleString("en-US")}</b><small>.{String(cents).padStart(2, "0")}</small></span><i>₪</i></>}
        <em>{varies ? (result.model === "equal_principal" ? t("תשלום ראשון, יורד", "first payment, then falling") : t("בחודש, משתנה", "a month, varies")) : t("בחודש, משוער", "a month, estimated")}</em>
      </div>
      {result.deferral_months > 0 && (
        <div className="ls-first" data-testid="ls-first-payment">{en ? <>First payment in {monthL(result.first_repayment_month)}</> : <>תשלום ראשון ב{monthHe(result.first_repayment_month)}</>}</div>
      )}
      <div className="ls-ribbon" role="img" data-testid="ls-ribbon"
        aria-label={t(`סך ההחזר ${ilsWhole(result.total_paid)}: קרן ${ilsWhole(result.principal)}, ריבית ${ilsWhole(result.total_interest)}`,
          `Total repayment ${ilsW(result.total_paid)}: principal ${ilsW(result.principal)}, interest ${ilsW(result.total_interest)}`)}>
        {parts.map((p) => <span key={p.k} className={`seg ${p.k}`} style={{ flexGrow: p.v / total }} />)}
      </div>
      <div className="ls-legend">
        {parts.map((p) => <span key={p.k} className={p.k}><i />{p.l} <b >{ilsW(p.v)}</b></span>)}
        {en ? <span className="total" data-testid="ls-total">Total <b >{ilsW(result.total_paid)}</b></span>
          : <span className="total" data-testid="ls-total">סה״כ <b >{ilsWhole(result.total_paid)}</b></span>}
      </div>
      <span hidden data-testid="ls-interest" data-value={result.total_interest} data-total={result.total_paid} />
    </div>
  );
}

/** One row: the label, the value as editable text, and the slider beneath it. */
function Slider({ id, label, unit, value, min, max, step, onChange, disabled, format, hint }: {
  id: string; label: string; unit: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void;
  disabled: boolean; format: (v: number) => string; hint?: string;
}) {
  const [text, setText] = useState<string | null>(null);
  const { en } = useLang();
  const pct = Math.max(0, Math.min(100, ((Math.min(Math.max(value, min), max) - min) / (max - min || 1)) * 100));
  const cap = id === "term" ? 600 : 10_000_000;            // the server's own input bounds (loan_sim.clean)
  const shown = text ?? format(value);
  const commit = (raw: string) => {
    const n = Number(raw.replace(/[^\d]/g, ""));
    if (/\d/.test(raw) && Number.isFinite(n) && n > 0) onChange(Math.min(n, cap));
  };
  return (
    <div className="ls-field" data-testid={`ls-field-${id}`}>
      <div className="ls-field-row">
        <label htmlFor={`ls-${id}-n`}>{label}</label>
        {hint && <span className="ls-hint">{hint}</span>}
        <span className="ls-val">
          <input id={`ls-${id}-n`} className="ltr" inputMode="numeric" enterKeyHint="done" autoComplete="off" disabled={disabled}
            value={shown} style={{ width: `${Math.max(2, shown.length) + 0.6}ch` }} onFocus={(e) => e.target.select()}
            onChange={(e) => { setText(e.target.value); commit(e.target.value); }}
            onBlur={() => setText(null)} onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
            aria-label={`${label} (${unit})`} data-testid={`ls-${id}-input`} />
          <em>{unit}</em>
        </span>
      </div>
      <input type="range" className="ls-range" min={min} max={max} step={step} value={Math.min(Math.max(value, min), max)} disabled={disabled}
        style={{ ["--p" as string]: `${pct}%` }} onChange={(e) => { setText(null); onChange(Number(e.target.value)); }}
        aria-label={label} aria-valuetext={`${format(value)} ${unit}`} aria-describedby={`ls-${id}-range-l`} data-testid={`ls-${id}-range`} />
      <span id={`ls-${id}-range-l`} className="ls-sr">{en ? <>Between {format(min)} and {format(max)} {unit}</> : <>בין {format(min)} ל־{format(max)} {unit}</>}</span>
    </div>
  );
}

function AssetField({ product, prm, onChange, disabled }: { product: Product; prm: Params; onChange: (p: Partial<Params>) => void; disabled: boolean }) {
  const [text, setText] = useState(prm.asset_price ? String(prm.asset_price) : "");
  useEffect(() => { setText(prm.asset_price ? String(prm.asset_price) : ""); }, [prm.asset_price]);
  const ratio = product.max_financing_ratio!;
  const share = prm.asset_price ? prm.amount / prm.asset_price : null;
  const shown = text ? Number(text).toLocaleString("en-US") : "";
  const { en, t } = useLang();
  return (
    <div className="ls-asset" data-testid="ls-asset">
      <div className="ls-field-row">
        <label htmlFor="ls-asset-n">{aLabel(product)}</label>
        <button className={`ls-chip${prm.asset_unknown ? " on" : ""}`} aria-pressed={prm.asset_unknown} disabled={disabled} data-testid="ls-asset-unknown"
          onClick={() => onChange({ asset_unknown: !prm.asset_unknown, asset_price: prm.asset_unknown ? prm.asset_price : null })}>
          {prm.asset_unknown && <ICheck size={11} />}{t("עוד אין מחיר", "No price yet")}</button>
        <span className={`ls-val${prm.asset_unknown ? " off" : ""}`}>
          <input id="ls-asset-n" className="ltr" inputMode="numeric" autoComplete="off" placeholder="—" disabled={disabled || prm.asset_unknown}
            value={shown} style={{ width: `${Math.max(5, shown.length) + 0.6}ch` }} data-testid="ls-asset-input" aria-label={`${aLabel(product)} (₪)`}
            onChange={(e) => { const d = e.target.value.replace(/\D/g, ""); setText(d); onChange({ asset_price: d && Number(d) >= 1000 ? Number(d) : null }); }} />
          <em>₪</em>
        </span>
      </div>
      {share != null && (
        <div className={`ls-ratio${share > ratio ? " over" : ""}`} data-testid="ls-ratio" data-pct={Math.round(share * 1000) / 10}>
          <div className="ls-ratio-bar" aria-hidden><span style={{ width: `${Math.min(100, share * 100)}%` }} /><i style={{ insetInlineStart: `${ratio * 100}%` }} /></div>
          <span className="ls-ratio-l">{en ? <>Financing <b className="ltr">{Math.round(share * 1000) / 10}%</b> · up to {Math.round(ratio * 100)}% on this product</>
            : <>מימון <b className="ltr">{Math.round(share * 1000) / 10}%</b> · במסלול עד {Math.round(ratio * 100)}%</>}</span>
        </div>
      )}
      {prm.asset_unknown && <p className="ls-fine">{t("שיעור המימון ייבדק מול הצעת המחיר.", "The financing rate will be checked against the price quote.")}</p>}
    </div>
  );
}

function Issues({ list, product, onFix, disabled }: { list: Issue[]; product: Product; onFix: (i: Issue) => void; disabled: boolean }) {
  return (
    <div className="ls-issues" role="status" data-testid="ls-issues">
      {list.map((i) => (
        <div key={i.code} className="ls-issue" data-code={i.code}>
          <IAlert size={14} />
          <p title={fullIssue(i, product)}>{short(i, product)}</p>
          {i.fix != null && (i.field === "amount" || i.field === "term") && (
            <button onClick={() => onFix(i)} disabled={disabled} data-testid="ls-fix">
              {i.field === "term" ? tr(`${i.fix} חודשים`, `${i.fix} months`) : tr(`ל־${ilsWhole(i.fix)}`, `To ${ilsW(i.fix)}`)}</button>
          )}
        </div>
      ))}
    </div>
  );
}

function TargetLine({ t, amount, onApply, disabled }: { t: NonNullable<ReturnType<typeof targetSolution>>; amount: number;
  onApply: (p: Partial<Params>) => void; disabled: boolean }) {
  const { en } = useLang();
  let body: ReactNode = null, act: ReactNode = null;
  if (en) {
    if (t.status === "met") body = <>The repayment is within your target.</>;
    else if (t.status === "term") {
      body = <>For <span >{ilsW(amount)}</span> you need at least {t.term} payments (<span >{ilsW(t.monthly_payment!)}</span>).</>;
      act = <button onClick={() => onApply({ term: t.term })} disabled={disabled} data-testid="ls-target-apply">{t.term} payments</button>;
    } else if (t.status === "amount") {
      body = <>Meets your target with <span >{ilsW(t.amount!)}</span> over {t.term} payments.</>;
      act = <button onClick={() => onApply({ amount: t.amount, term: t.term })} disabled={disabled} data-testid="ls-target-apply">Update</button>;
    } else if (t.status === "none") body = <>No scenario on this product meets your target.</>;
    else body = <>There&apos;s no rate to calculate with on this product.</>;
  } else if (t.status === "met") body = <>ההחזר בתוך היעד.</>;
  else if (t.status === "term") {
    body = <>על <span >{ilsWhole(amount)}</span> צריך לפחות {t.term} תשלומים (<span >{ilsWhole(t.monthly_payment!)}</span>).</>;
    act = <button onClick={() => onApply({ term: t.term })} disabled={disabled} data-testid="ls-target-apply">{t.term} תשלומים</button>;
  } else if (t.status === "amount") {
    body = <>עומד ביעד בסכום של <span >{ilsWhole(t.amount!)}</span> ב־{t.term} תשלומים.</>;
    act = <button onClick={() => onApply({ amount: t.amount, term: t.term })} disabled={disabled} data-testid="ls-target-apply">לעדכן</button>;
  } else if (t.status === "none") body = <>אין תרחיש במסלול שעומד ביעד.</>;
  else body = <>אין ריבית לחישוב במסלול הזה.</>;
  return (
    <div className={`ls-target ${t.status}`} data-testid="ls-target" data-status={t.status}>
      <p><b>{en ? <>Target: up to <span >{ilsW(t.target)}</span> a month.</> : <>יעד: עד <span >{ilsWhole(t.target)}</span> בחודש.</>}</b> {body}</p>{act}
    </div>
  );
}

/** V2: the customer's own figures next to the scenario. Informational indicators only: no threshold, no verdict. */
function Personal({ afford, ctx, obligations, onObligations, compare, onTerm, disabled }: {
  afford: ReturnType<typeof affordability>; ctx: Simulation["context"]; obligations: string; onObligations: (v: string) => void;
  compare: ReturnType<typeof comparison>; onTerm: (t: number) => void; disabled: boolean;
}) {
  if (!afford) return null;
  const net = afford.net_income, ex = afford.existing_monthly ?? 0;
  const w = (v: number) => `${Math.max(0, Math.min(100, (v / net) * 100))}%`;
  const shown = obligations ? Number(obligations).toLocaleString("en-US") : "";
  const { en, t } = useLang();
  return (
    <div className="ls-personal" data-testid="ls-personal" data-ratio={afford.ratio_pct ?? ""}>
      <div className="ls-personal-head">
        <span><b className="ltr" data-testid="ls-ratio-pct">{afford.ratio_pct}%</b>{t(" מההכנסה נטו להחזרי הלוואות", " of net income on loan repayments")}</span>
        <span className="ls-muted">{t("נשארים ", "Remaining ")}<b >{ilsW(afford.remaining)}</b></span>
      </div>
      <div className="ls-budget" aria-hidden>
        {ex > 0 && <span className="ex" style={{ width: w(ex) }} />}
        <span className="new" style={{ width: w(afford.new_monthly) }} />
      </div>
      <div className="ls-field-row ls-ob">
        <label htmlFor="ls-ob-n">{t("החזרי הלוואות קיימים", "Existing loan repayments")}</label>
        <span className="ls-val">
          <input id="ls-ob-n" className="ltr" inputMode="numeric" placeholder="0" value={shown} style={{ width: `${Math.max(2, shown.length) + 0.6}ch` }}
            onChange={(e) => onObligations(e.target.value.replace(/\D/g, ""))} disabled={disabled} aria-label={t("החזרי הלוואות קיימים בחודש (₪)", "Existing loan repayments a month (₪)")}
            data-testid="ls-obligations" />
          <em>₪</em>
        </span>
      </div>
      {compare.length > 1 && (
        <div className="ls-compare" role="group" aria-label={t("השוואת תקופות", "Compare terms")} data-testid="ls-compare">
          {compare.map((x) => (
            <button key={x.term} className={x.chosen ? "on" : ""} disabled={disabled || x.chosen} onClick={() => onTerm(x.term)} data-term={x.term}
              title={t(`ריבית ${ilsWhole(x.total_interest)}`, `Interest ${ilsW(x.total_interest)}`)}>
              <span>{x.term}</span><b >{ilsW(x.monthly_payment)}</b>
            </button>
          ))}
        </div>
      )}
      <p className="ls-fine">{en ? <>Based on what you told us{ctx.co_borrower_pending ? ", without the co-borrower" : ""}. A budget indicator only, not an eligibility check.</>
        : <>לפי מה שסיפרת{ctx.co_borrower_pending ? ", בלי הלווה הנוסף" : ""}. מדד תקציבי בלבד, לא בדיקת זכאות.</>}</p>
    </div>
  );
}

const POLICY_HE: Record<DeferralPolicy, string> = {
  capitalized: "הריבית מצטברת לקרן", interest_only: "ריבית בלבד בינתיים", accrued_first_payment: "הריבית עם התשלום הראשון",
};
const POLICY_EN: Record<DeferralPolicy, string> = {
  capitalized: "Interest added to the principal", interest_only: "Interest only meanwhile", accrued_first_payment: "Interest with the first payment",
};

/** The product's own extra settings, behind one quiet row. Only what the selected product supports appears. */
function Options({ product, prm, result, set, disabled, start }: { product: Product; prm: Params; result: ReturnType<typeof compute>;
  set: (p: Partial<Params>) => void; disabled: boolean; start: string }) {
  const [open, setOpen] = useState(false);
  const { en, t } = useLang();
  const d = product.features.deferral, vr = product.features.variable_rate, models = product.features.repayment_models;
  const base = useMemo(() => (d && prm.deferral_months ? compute(product, { ...prm, deferral_months: 0 }, start) : null), [d, prm, product, start]);
  const flat = useMemo(() => (prm.rate_change_pct ? compute(product, { ...prm, rate_change_pct: 0 }, start) : null), [prm, product, start]);
  const count = (d ? 1 : 0) + (vr ? 1 : 0) + (models.length > 1 ? 1 : 0);
  if (!count || !result) return null;
  const summary = (en ? [d && (prm.deferral_months ? `${prm.deferral_months}-mo deferral` : "Payment deferral"), vr && (prm.rate_change_pct ? `Rate +${prm.rate_change_pct}%` : "Rate change"),
    models.length > 1 && (prm.model === "equal_principal" ? "Equal principal" : "Repayment method")]
    : [d && (prm.deferral_months ? `דחייה ${prm.deferral_months} חו׳` : "דחיית תשלום"), vr && (prm.rate_change_pct ? `ריבית +${prm.rate_change_pct}%` : "שינוי ריבית"),
    models.length > 1 && (prm.model === "equal_principal" ? "קרן שווה" : "שיטת החזר")]).filter(Boolean).join(" · ");
  return (
    <div className={`ls-opts${open ? " open" : ""}`} data-testid="ls-options">
      <button className="ls-opts-h" aria-expanded={open} onClick={() => setOpen((o) => !o)} data-testid="ls-options-toggle">
        <span>{t("אפשרויות נוספות", "More options")}</span><em>{summary}</em><IChevronDown size={15} />
      </button>
      {open && <div className="ls-opts-b">
        {d && (
          <div className="ls-opt" data-testid="ls-deferral">
            <div className="ls-opt-t">{t("דחיית התשלום הראשון", "Defer the first payment")}</div>
            <div className="ls-seg" role="radiogroup" aria-label={t("חודשי דחייה", "Deferral months")}>
              {Array.from({ length: d.max_months + 1 }, (_, m) => (
                <button key={m} role="radio" aria-checked={prm.deferral_months === m} className={prm.deferral_months === m ? "on" : ""}
                  disabled={disabled} onClick={() => set({ deferral_months: m })} data-testid="ls-deferral-opt" data-months={m}>
                  {m === 0 ? t("בלי", "None") : t(`${m} חו׳`, `${m} mo`)}</button>
              ))}
            </div>
            {prm.deferral_months > 0 && <>
              <div className="ls-seg sm" role="radiogroup" aria-label={t("אופן חישוב הדחייה (המחשה)", "How the deferral is calculated (illustration)")}>
                {d.illustrative_policies.map((p) => (
                  <button key={p} role="radio" aria-checked={prm.deferral_policy === p} className={prm.deferral_policy === p ? "on" : ""}
                    disabled={disabled} onClick={() => set({ deferral_policy: p })} data-testid="ls-policy" data-policy={p}>{(en ? POLICY_EN : POLICY_HE)[p]}</button>
                ))}
              </div>
              <p className="ls-opt-r" data-testid="ls-deferral-impact">
                {en ? (prm.deferral_policy === "interest_only"
                  ? <>During the deferral, interest only: <span >{ilsW(result.rows[0].payment)}</span>. </>
                  : <>No payment during the deferral. </>)
                  : prm.deferral_policy === "interest_only"
                  ? <>בחודשי הדחייה ריבית בלבד, <span >{ilsWhole(result.rows[0].payment)}</span>. </>
                  : <>בחודשי הדחייה אין תשלום. </>}
                {base && <>{t("ריבית נוספת: ", "Extra interest: ")}<b data-testid="ls-deferral-extra">{ilsW(result.total_interest - base.total_interest)}</b>.</>}
              </p>
              <p className="ls-fine">{t("הבנק לא פרסם איך מחושבת הדחייה. זו המחשה, לא חישוב רשמי, והדחייה אינה ללא עלות.",
                "The bank hasn't published how the deferral is calculated. This is an illustration, not an official calculation, and the deferral isn't free.")}</p>
            </>}
          </div>
        )}
        {vr && (
          <div className="ls-opt" data-testid="ls-variable">
            <div className="ls-opt-t">{t("מה אם הריבית תעלה אחרי שנה?", "What if the rate rises after a year?")}</div>
            <div className="ls-seg" role="radiogroup" aria-label={t("שינוי ריבית אחרי שנה", "Rate change after a year")}>
              {[0, 1, 2, 3].map((x) => (
                <button key={x} role="radio" aria-checked={prm.rate_change_pct === x} className={prm.rate_change_pct === x ? "on" : ""}
                  disabled={disabled} onClick={() => set({ rate_change_pct: x, rate_change_from: 13 })} data-testid="ls-rate-opt">{x === 0 ? t("קבועה", "Fixed") : `+${x}%`}</button>
              ))}
            </div>
            {flat && <p className="ls-opt-r">{t("מהחודש ה־13: ", "From month 13: ")}<b >{ilsW(result.rows[Math.min(12, result.rows.length - 1)].payment)}</b>{t(" · ריבית נוספת ", " · extra interest ")}<b >{ilsW(result.total_interest - flat.total_interest)}</b></p>}
            <p className="ls-fine">{t("תרחיש, לא תחזית.", "A scenario, not a forecast.")}</p>
          </div>
        )}
        {models.length > 1 && (
          <div className="ls-opt" data-testid="ls-model">
            <div className="ls-opt-t">{t("שיטת החזר (להמחשה)", "Repayment method (illustration)")}</div>
            <div className="ls-seg" role="radiogroup" aria-label={t("שיטת החזר", "Repayment method")}>
              {models.map((m) => (
                <button key={m} role="radio" aria-checked={prm.model === m} className={prm.model === m ? "on" : ""} disabled={disabled}
                  onClick={() => set({ model: m })} data-testid="ls-model-opt" data-model={m}>{m === "annuity" ? t("תשלום קבוע", "Fixed payment") : t("קרן שווה", "Equal principal")}</button>
              ))}
            </div>
            {prm.model === "equal_principal" && <p className="ls-opt-r">{en ? <>Starts at <b >{ilsW(result.max_payment)}</b> and falls to <b >{ilsW(result.min_payment)}</b>.</>
              : <>מתחיל ב־<b >{ilsWhole(result.max_payment)}</b> ויורד עד <b >{ilsWhole(result.min_payment)}</b>.</>}</p>}
          </div>
        )}
      </div>}
    </div>
  );
}

/** Confirmed: one line inside the conversation, reopened with "שינוי". */
function Compact({ product, prm, monthly, afford, onEdit, busy }: { product: Product; prm: Params; monthly: number | null;
  afford: ReturnType<typeof affordability>; onEdit: () => void; busy: boolean }) {
  const { en, t } = useLang();
  return (
    <div className="ls-compact" data-testid="ls-compact">
      <img className="ls-mark" src="/brand/jeen-mark.png" alt="" />
      <div className="ls-compact-t">
        <span className="ls-compact-k"><ICheck size={11} />{pLabel(product)}</span>
        <span className="ls-compact-v">
          {en ? <><span >{ilsW(prm.amount)}</span> · {prm.term} payments</> : <><span >{ilsWhole(prm.amount)}</span> · {prm.term} תשלומים</>}
          {prm.deferral_months > 0 && (en ? <> · {prm.deferral_months}-mo deferral</> : <> · דחייה {prm.deferral_months} חו׳</>)}
          {afford?.ratio_pct != null && <span className="ls-compact-ratio" data-testid="ls-compact-ratio"> · <span className="ltr">{afford.ratio_pct}%</span>{t(" מההכנסה", " of income")}</span>}
        </span>
      </div>
      <div className="ls-compact-m">
        <b data-testid="ls-monthly">{monthly != null ? ilsW(monthly) : "—"}</b>
        <span>{monthly != null ? t("בחודש · המחשה", "a month · illustration") : t("ללא חישוב", "Not calculated")}</span>
      </div>
      <button className="ls-edit" onClick={onEdit} disabled={busy} data-testid="ls-edit" aria-label={t("שינוי התרחיש", "Change the scenario")}>{t("שינוי", "Change")}</button>
    </div>
  );
}

/** A number that eases to its new value (instant when the user prefers reduced motion). */
function useTween(target: number, ms = 220): number {
  const [v, setV] = useState(target);
  const from = useRef(target), raf = useRef(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setV(target); from.current = target; return; }
    const start = performance.now(), a = from.current;
    cancelAnimationFrame(raf.current);
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / ms), e = 1 - (1 - k) ** 3;
      const x = a + (target - a) * e;
      setV(x); from.current = x;
      if (k < 1) raf.current = requestAnimationFrame(step); else { setV(target); from.current = target; }
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target, ms]);
  return v;
}
