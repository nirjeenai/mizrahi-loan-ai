/** The loan simulator's arithmetic in the browser: a port of backend/app/workflow/loan_calc.py and the rule checks of
 *  loan_products.py / loan_sim.py (same formulas, rounding policy and wording — change them together). The card uses it
 *  for instant feedback while a slider moves; confirming sends the scenario to the server, which recomputes and records it.
 *  Products, bounds and rates always come from the server payload: nothing here knows a bank term. */

export type Model = "annuity" | "equal_principal" | "interest_only";
export type DeferralPolicy = "capitalized" | "interest_only" | "accrued_first_payment";

export interface Rate { available: boolean; source: "bank_quote" | "pricing_config" | "illustrative" | "unavailable";
  annual_rate_pct: number | null; convention: "nominal" | "effective" | null; label_he: string }
export interface ProductBounds { amount_min: number; amount_max: number; amount_max_basis: string; amount_step: number;
  term_min: number; term_min_basis: string; term_max: number; term_max_basis: string }
export interface Deferral { max_months: number; basis: string; verified_policy: string | null;
  illustrative_policies: DeferralPolicy[]; default_policy: DeferralPolicy; term_includes_deferral: boolean; term_basis: string }
export interface Product {
  id: string; label_he: string; short_he: string; source_url: string; verified_he: string[]; not_applicable_he?: string | null;
  amount_field: "amount" | "business_amount"; max_financing_ratio: number | null;
  asset: { label_he: string; hint_he: string } | null;
  features: { repayment_models: ("annuity" | "equal_principal")[]; models_basis?: string; deferral: Deferral | null;
    variable_rate: { basis: string; note_he: string } | null; fees: unknown[] };
  defaults: { amount: number; term: number }; bounds: ProductBounds; rate: Rate;
}
export interface Params {
  amount: number; term: number; asset_price: number | null; asset_unknown: boolean; deferral_months: number;
  deferral_policy: DeferralPolicy | null; model: "annuity" | "equal_principal"; rate_change_pct: number; rate_change_from: number;
}
export interface Row { period: number; month: string; phase: "deferral" | "repay"; payment: number; interest: number; fee: number;
  principal: number; balance: number }
export interface Result {
  principal: number; term_months: number; amortizing_months: number; deferral_months: number; periods: number; model: Model;
  annual_rate_pct: number; monthly_payment: number; first_payment: number; first_payment_month: string | null;
  first_repayment_month: string; last_payment: number; max_payment: number; min_payment: number; total_paid: number;
  total_interest: number; total_fees: number; total_cost: number; rows: Row[];
}
export interface Issue { code: string; field: "amount" | "term" | "deferral" | "asset_price"; fix: number | null; message_he: string;
  ratio_pct?: number; limit_pct?: number }

/** The card's one-line wording of a rule (the full sentence, as the server words it, is the chat's and the title's). */
export function shortIssue(i: Issue, p: Product): string {
  const b = p.bounds, inProduct = (basis: string) => (basis === "verified" ? "במסלול" : "בסימולציה");
  switch (i.code) {
    case "financing_ratio": return `${pct1(i.ratio_pct!)}% מימון, מעל ${i.limit_pct}% ${inProduct("verified")}`;
    case "amount_above_max": return `עד ${ilsWhole(b.amount_max)} ${inProduct(b.amount_max_basis)}`;
    case "amount_below_min": return `לפחות ${ilsWhole(b.amount_min)}`;
    case "term_above_max": return `עד ${b.term_max} חודשים ${inProduct(b.term_max_basis)}`;
    case "term_below_min": return `לפחות ${b.term_min} חודשים`;
    case "asset_required": return `להזין מחיר רכב לבדיקת המימון (עד ${Math.trunc((p.max_financing_ratio ?? 0) * 100)}%), או "עוד אין מחיר"`;
    default: return i.message_he;
  }
}
export interface Afford { new_monthly: number; existing_monthly: number | null; existing_known: boolean; total_monthly: number;
  net_income: number; ratio_pct: number | null; new_only_ratio_pct: number | null; remaining: number }
export type Target = { status: "no_rate" | "met" | "term" | "amount" | "none"; target: number; term?: number; amount?: number;
  monthly_payment?: number | null; total_interest?: number | null; current_total_interest?: number | null; term_max?: number };

/** Integer agorot, ROUND_HALF_UP (away from zero), as Decimal.quantize does on the server. */
const toC = (x: number) => Math.sign(x) * Math.round(Math.abs(x) * 100 + 1e-7);
const fromC = (c: number) => c / 100;
export const money = (x: number) => fromC(toC(x));

export function monthlyRate(annualPct: number, convention: "nominal" | "effective" = "nominal"): number {
  const a = annualPct / 100;
  return convention === "nominal" ? a / 12 : (1 + a) ** (1 / 12) - 1;
}

export function annuityPayment(principal: number, r: number, months: number, fv = 0): number {
  if (r === 0) return (principal - fv) / months;
  const f = (1 + r) ** months;
  return ((principal * f - fv) * r) / (f - 1);
}

export function addMonths(ym: string, k: number): string {
  const t = Number(ym.slice(0, 4)) * 12 + Number(ym.slice(5, 7)) - 1 + k;
  return `${String(Math.floor(t / 12)).padStart(4, "0")}-${String((t % 12) + 1).padStart(2, "0")}`;
}

export function schedule(principal: number, months: number, annualPct: number, o: {
  convention?: "nominal" | "effective"; model?: Model; rateChanges?: { from_period: number; annual_rate_pct: number }[];
  deferral?: { months: number; policy: DeferralPolicy; term_includes_deferral: boolean } | null; monthlyFee?: number;
  upfrontFee?: number; balloon?: number; startMonth: string }): Result | null {
  const model = o.model ?? "annuity", conv = o.convention ?? "nominal", b = o.balloon ?? 0;
  const d = o.deferral?.months ?? 0, policy = o.deferral?.policy ?? "capitalized", inclusive = !!o.deferral?.term_includes_deferral;
  if (!(principal > 0) || !Number.isInteger(months) || months < 1 || months > 600 || !(annualPct >= 0) || annualPct > 100) return null;
  if (!Number.isInteger(d) || d < 0 || d > 24 || (inclusive && d >= months) || b < 0 || b >= principal) return null;
  const feeM = o.monthlyFee ?? 0, fee0 = o.upfrontFee ?? 0;
  const rates = new Map((o.rateChanges ?? []).map((c) => [c.from_period, monthlyRate(c.annual_rate_pct, conv)]));
  const amort = inclusive ? months - d : months, total = d + amort;
  let bal = principal, accrued = 0, r = monthlyRate(annualPct, conv), pmt: number | null = null, level: number | null = null;
  const raw: { k: number; pay: number; int: number; fee: number; bal: number; phase: Row["phase"] }[] = [];
  for (let k = 1; k <= total; k++) {
    const changed = rates.has(k);
    if (changed) r = rates.get(k)!;
    const i = bal * r;
    if (k <= d) {
      let pay = 0;
      if (policy === "capitalized") bal += i;
      else if (policy === "interest_only") pay = i;
      else accrued += i;
      raw.push({ k, pay: pay + feeM, int: i, fee: feeM, bal, phase: "deferral" });
      continue;
    }
    const j = k - d, remaining = amort - j + 1;
    let pay: number;
    if (model === "annuity") {
      if (pmt === null || changed) pmt = annuityPayment(bal, r, remaining, b);
      pay = j === amort ? bal + i : pmt;
    } else if (model === "equal_principal") {
      if (level === null) level = bal / amort;
      pay = j === amort ? bal + i : level + i;
    } else pay = j === amort ? bal + i : i;
    bal = bal + i - pay;
    if (j === 1 && accrued) { pay += accrued; accrued = 0; }
    raw.push({ k, pay: pay + feeM, int: i, fee: feeM, bal, phase: "repay" });
  }
  const interestC = toC(raw.reduce((s, x) => s + x.int, 0));
  const feesC = toC(feeM * total);
  const paidC = toC(principal) + interestC + feesC;
  let paid = 0, interest = 0;
  const rows: Row[] = raw.map((x, n) => {
    const last = n === raw.length - 1;
    const payC = last ? paidC - paid : toC(x.pay), iC = last ? interestC - interest : toC(x.int), feeC = toC(x.fee);
    paid += payC; interest += iC;
    return { period: x.k, month: addMonths(o.startMonth, x.k - 1), phase: x.phase, payment: fromC(payC), interest: fromC(iC),
      fee: fromC(feeC), principal: fromC(payC - iC - feeC), balance: last ? 0 : money(x.bal) };
  });
  const repay = rows.filter((x) => x.phase === "repay"), paying = rows.filter((x) => x.payment > 0);
  const regular = d && policy === "accrued_first_payment" && repay.length > 1 ? repay[1] : repay[0];
  return {
    principal: money(principal), term_months: months, amortizing_months: amort, deferral_months: d, periods: total, model,
    annual_rate_pct: annualPct, monthly_payment: regular.payment, first_payment: paying[0]?.payment ?? 0,
    first_payment_month: paying[0]?.month ?? null, first_repayment_month: repay[0].month, last_payment: rows[rows.length - 1].payment,
    max_payment: Math.max(...repay.map((x) => x.payment)), min_payment: Math.min(...repay.map((x) => x.payment)),
    total_paid: fromC(paidC), total_interest: fromC(interestC), total_fees: fromC(feesC + toC(fee0)),
    total_cost: fromC(interestC + feesC + toC(fee0)), rows,
  };
}

export function yearly(rows: Row[]) {
  const out: { year: number; from_month: string; to_month: string; paid: number; interest: number; principal: number; balance: number }[] = [];
  for (let n = 0; n < rows.length; n += 12) {
    const b = rows.slice(n, n + 12);
    out.push({ year: n / 12 + 1, from_month: b[0].month, to_month: b[b.length - 1].month,
      paid: fromC(b.reduce((s, x) => s + toC(x.payment), 0)), interest: fromC(b.reduce((s, x) => s + toC(x.interest), 0)),
      principal: fromC(b.reduce((s, x) => s + toC(x.principal), 0)), balance: b[b.length - 1].balance });
  }
  return out;
}

/** loan_sim.compute: the schedule at the product's rate, or null when no rate may be used. */
export function compute(p: Product, prm: Params, startMonth: string): Result | null {
  const rate = p.rate;
  if (!rate.available || rate.annual_rate_pct == null) return null;
  const changes = prm.rate_change_pct && prm.rate_change_from < prm.term + prm.deferral_months
    ? [{ from_period: prm.rate_change_from, annual_rate_pct: rate.annual_rate_pct + prm.rate_change_pct }] : [];
  const d = p.features.deferral;
  const deferral = prm.deferral_months && d
    ? { months: prm.deferral_months, policy: prm.deferral_policy ?? d.default_policy, term_includes_deferral: d.term_includes_deferral } : null;
  return schedule(prm.amount, prm.term, rate.annual_rate_pct, { convention: rate.convention ?? "nominal", model: prm.model,
    rateChanges: changes, deferral, startMonth });
}

/** loan_sim._params: the product's defaults, and nothing the product does not support. */
export function normalize(p: Product, base: Partial<Params>): Params {
  const d = p.features.deferral, f = p.features;
  return {
    amount: base.amount || p.defaults.amount, term: base.term || p.defaults.term,
    asset_price: p.asset ? base.asset_price ?? null : null, asset_unknown: p.asset ? !!base.asset_unknown : false,
    deferral_months: d ? Math.min(base.deferral_months || 0, d.max_months) : 0,
    deferral_policy: d ? (base.deferral_policy && d.illustrative_policies.includes(base.deferral_policy) ? base.deferral_policy : d.default_policy) : null,
    model: base.model && f.repayment_models.includes(base.model) ? base.model : "annuity",
    rate_change_pct: f.variable_rate ? base.rate_change_pct || 0 : 0, rate_change_from: base.rate_change_from || 13,
  };
}

/** Whole shekels, rounded like the server's wording (loan_sim._ils), so the card and the chat show the same figure. */
export const ilsWhole = (n: number) => `${Math.round(n).toLocaleString("en-US")} ₪`;
const pct1 = (x: number) => String(Math.round(x * 10) / 10);

/** loan_products.issues (+ loan_sim._issues when confirming): the same rules and the same wording as the server. */
export function issues(p: Product, prm: Params, confirming = false): Issue[] {
  const b = p.bounds, out: Issue[] = [], label = p.label_he;
  const { amount, term } = prm;
  if (amount < b.amount_min) out.push({ code: "amount_below_min", field: "amount", fix: b.amount_min, message_he: `הסכום הנמוך בסימולציה הוא ${ilsWhole(b.amount_min)}.` });
  else if (amount > b.amount_max) {
    const where = b.amount_max_basis === "verified" ? `ב${label} אפשר עד` : "בסימולציה אפשר עד";
    out.push({ code: "amount_above_max", field: "amount", fix: b.amount_max, message_he: `${where} ${ilsWhole(b.amount_max)}. אפשר להפחית את הסכום או לבדוק מסלול אחר.` });
  }
  const ratio = p.max_financing_ratio;
  if (ratio && prm.asset_price && amount > Math.floor(ratio * prm.asset_price)) {
    const pct = Math.round((amount / prm.asset_price) * 1000) / 10, limit = Math.trunc(ratio * 100);
    const fix = Math.floor((ratio * prm.asset_price) / b.amount_step) * b.amount_step;
    out.push({ code: "financing_ratio", field: "amount", fix, ratio_pct: pct, limit_pct: limit,
      message_he: `הסכום שבחרת הוא ${pct1(pct)}% ממחיר הרכב, גבוה משיעור המימון במסלול זה (עד ${limit}%). אפשר להפחית את סכום ההלוואה ל־${ilsWhole(fix)} או לבדוק אפשרויות נוספות.` });
  }
  if (term < b.term_min) out.push({ code: "term_below_min", field: "term", fix: b.term_min, message_he: `התקופה הקצרה בסימולציה היא ${b.term_min} חודשים.` });
  else if (term > b.term_max) {
    const where = b.term_max_basis === "verified" ? `ב${label} התקופה עד` : "בסימולציה התקופה עד";
    out.push({ code: "term_above_max", field: "term", fix: b.term_max, message_he: `${where} ${b.term_max} חודשים. אפשר לקצר את התקופה או לבדוק מסלול אחר.` });
  }
  if (confirming && p.asset && ratio && !prm.asset_price && !prm.asset_unknown) {
    out.push({ code: "asset_required", field: "asset_price", fix: null,
      message_he: `כדי לבדוק את שיעור המימון ב${label} (עד ${Math.trunc(ratio * 100)}% ממחיר הרכב) צריך את מחיר הרכב. אפשר להזין אותו, או לציין שעוד אין מחיר סופי.` });
  }
  return out;
}

export function paymentFor(principal: number, months: number, annualPct: number, conv: "nominal" | "effective" = "nominal") {
  return money(annuityPayment(principal, monthlyRate(annualPct, conv), months));
}

export function comparison(p: Product, prm: Params, startMonth: string) {
  const seen = new Set<number>(), rows: { term: number; monthly_payment: number; total_interest: number; chosen: boolean }[] = [];
  for (let t of [prm.term - 12, prm.term, prm.term + 12]) {
    t = Math.max(p.bounds.term_min, Math.min(p.bounds.term_max, t));
    if (seen.has(t)) continue;
    seen.add(t);
    const s = compute(p, { ...prm, term: t }, startMonth);
    if (s) rows.push({ term: t, monthly_payment: s.monthly_payment, total_interest: s.total_interest, chosen: t === prm.term });
  }
  return rows;
}

export function affordability(newMonthly: number, net: number | null, existing: number | null): Afford | null {
  if (!net || net <= 0) return null;
  const nC = toC(newMonthly), eC = existing != null ? toC(existing) : null, tC = nC + (eC ?? 0), netC = toC(net);
  const r = (x: number) => Math.round((x / netC) * 1000 + 1e-9) / 10;
  return { new_monthly: fromC(nC), existing_monthly: eC != null ? fromC(eC) : null, existing_known: eC != null,
    total_monthly: fromC(tC), net_income: fromC(netC), ratio_pct: r(tC), new_only_ratio_pct: r(nC), remaining: fromC(netC - tC) };
}

export function targetSolution(p: Product, prm: Params, target: number | null, startMonth: string): Target | null {
  if (!target) return null;
  const rate = p.rate;
  if (!rate.available || rate.annual_rate_pct == null) return { status: "no_rate", target };
  const b = p.bounds, conv = rate.convention ?? "nominal";
  const current = compute(p, prm, startMonth);
  if (current && current.monthly_payment <= target) return { status: "met", target, monthly_payment: current.monthly_payment };
  for (let n = Math.max(1, b.term_min); n <= b.term_max; n++) {
    if (paymentFor(prm.amount, n, rate.annual_rate_pct, conv) <= target) {
      const s = compute(p, { ...prm, term: n }, startMonth);
      return { status: "term", target, term: n, monthly_payment: s?.monthly_payment ?? null, total_interest: s?.total_interest ?? null,
        current_total_interest: current?.total_interest ?? null };
    }
  }
  const r = monthlyRate(rate.annual_rate_pct, conv), m = b.term_max;
  let amt = Math.floor((r === 0 ? target * m : (target * (1 - (1 + r) ** -m)) / r) / b.amount_step) * b.amount_step;
  while (amt > 0 && paymentFor(amt, m, rate.annual_rate_pct, conv) > target) amt -= b.amount_step;
  if (amt < b.amount_min) return { status: "none", target, term_max: m };
  const s = compute(p, { ...prm, amount: amt, term: m }, startMonth);
  return { status: "amount", target, amount: amt, term: m, monthly_payment: s?.monthly_payment ?? null };
}
