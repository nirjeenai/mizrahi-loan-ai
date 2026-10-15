/** The What-if simulator's arithmetic: a port of backend/app/workflow/finance.py (same formulas, bounds and rounding —
 *  change both together). Exploratory only: nothing computed here is sent back or stored. */

export interface Scenario {
  key: "short" | "requested" | "long"; term_months: number; principal_ils: number; annual_rate_pct: number;
  monthly_payment_ils: number; total_payments_ils: number; total_interest_ils: number;
  combined_debt_service_ils: number; combined_dsr_pct: number | null; combined_includes_existing: boolean;
  ltv_pct: number | null; remaining_after_debt_ils: number | null;
}

const round2 = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100;

function rawPayment(principal: number, termMonths: number, annualRatePct: number): number | null {
  if (!(principal > 0) || !Number.isInteger(termMonths) || termMonths <= 0 || !(annualRatePct >= 0)) return null;
  const r = annualRatePct / 100 / 12;
  return r === 0 ? principal / termMonths : (principal * r) / (1 - (1 + r) ** -termMonths);
}
export function ratioPct(numerator: number | null, denominator: number | null): number | null {
  if (numerator == null || !denominator || denominator <= 0) return null;
  return Math.round((numerator / denominator) * 1000) / 10;
}

export function scenarioTerms(term: number, min: number, max: number, step: number): [Scenario["key"], number][] {
  const keys: [Scenario["key"], number][] = [["short", Math.max(min, term - step)], ["requested", term], ["long", Math.min(max, term + step)]];
  const seen = new Set<number>();
  return keys.filter(([, t]) => (seen.has(t) ? false : (seen.add(t), true)));
}

export function scenarios(principal: number, term: number, rate: number, income: number | null, existing: number | null,
  asset: number | null, bounds: { term_min: number; term_max: number; step: number }): Scenario[] {
  const out: Scenario[] = [];
  for (const [key, t] of scenarioTerms(term, bounds.term_min, bounds.term_max, bounds.step)) {
    const raw = rawPayment(principal, t, rate);
    if (raw == null) continue;
    const pay = round2(raw);
    const interest = rate === 0 ? 0 : round2(raw * t - principal);
    const combined = round2(pay + (existing ?? 0));
    out.push({ key, term_months: t, principal_ils: round2(principal), annual_rate_pct: rate, monthly_payment_ils: pay,
      total_payments_ils: round2(principal + interest), total_interest_ils: interest, combined_debt_service_ils: combined,
      combined_dsr_pct: ratioPct(combined, income), combined_includes_existing: existing != null,
      ltv_pct: ratioPct(principal, asset), remaining_after_debt_ils: income ? round2(income - combined) : null });
  }
  return out;
}
