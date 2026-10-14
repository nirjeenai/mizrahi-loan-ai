/** Synthetic illustration data for the "ביצועים ותובנות" tab. Not measured, not produced by the follow-up engine or
 *  JEEN Talk, and not read from any case. Three follow-up variants that differ only in the grace period, 80 cases each. */

/** A count split by how the customer came back: on their own (no contact) or after a mock call. */
export interface Lane { self: number; call: number }

export interface Variant {
  id: "A" | "B" | "C";
  name: string;
  graceMinutes: number;
  cases: number;
  /** returned (any channel) ⊇ completed all missing documents ⊇ package ready for banker review */
  returned: Lane;
  uploaded: Lane;
  ready: Lane;
  /** mock JEEN Talk events: attempts across the contacted cases (at most 2 per case), answered, mean answered duration */
  calls: { attempts: number; answered: number; avgSeconds: number };
  question: string;
}

export const PERIOD_HE = "ספטמבר 2026";

export const HELD_EQUAL = [
  "אותו סדר ערוצים: תיקון עצמי באפליקציה, ואז שיחה",
  "עד 2 פניות לתיק",
  "אותו חלון פנייה ואותם סוגי מסמכים",
  "80 תיקים לכל גרסה",
];

export const VARIANTS: Variant[] = [
  {
    id: "A", name: "גרסה א׳", graceMinutes: 5, cases: 80,
    returned: { self: 10, call: 24 }, uploaded: { self: 9, call: 21 }, ready: { self: 8, call: 16 },
    calls: { attempts: 104, answered: 52, avgSeconds: 74 },
    question: "האם פנייה אחרי 5 דקות מגיעה לפני שהלקוח הספיק לחזור בעצמו?",
  },
  {
    id: "B", name: "גרסה ב׳", graceMinutes: 20, cases: 80,
    returned: { self: 22, call: 22 }, uploaded: { self: 20, call: 20 }, ready: { self: 19, call: 17 },
    calls: { attempts: 80, answered: 50, avgSeconds: 125 },
    question: "האם הפער נשמר גם בשעות אחרות של היום ובסוגי מסמכים אחרים?",
  },
  {
    id: "C", name: "גרסה ג׳", graceMinutes: 60, cases: 80,
    returned: { self: 26, call: 8 }, uploaded: { self: 24, call: 7 }, ready: { self: 21, call: 5 },
    calls: { attempts: 70, answered: 36, avgSeconds: 108 },
    question: "האם המתנה של שעה מאבדת לקוחות שהיו חוזרים אחרי תזכורת מוקדמת יותר?",
  },
];

export const sum = (l: Lane) => l.self + l.call;

/** Everything the charts show for one variant, derived from the counts above. */
export function derive(v: Variant) {
  const returned = sum(v.returned), uploaded = sum(v.uploaded), ready = sum(v.ready);
  const contacted = v.cases - v.returned.self;
  return {
    returned, uploaded, ready, contacted,
    inProgress: returned - ready,
    notReturned: v.cases - returned,
    unanswered: v.calls.attempts - v.calls.answered,
    readyRate: ready / v.cases,
    returnRate: returned / v.cases,
  };
}

export function totals(vs: Variant[] = VARIANTS) {
  const add = (pick: (v: Variant) => Lane): Lane => ({ self: vs.reduce((n, v) => n + pick(v).self, 0), call: vs.reduce((n, v) => n + pick(v).call, 0) });
  const cases = vs.reduce((n, v) => n + v.cases, 0);
  const returned = add((v) => v.returned), ready = add((v) => v.ready);
  const attempts = vs.reduce((n, v) => n + v.calls.attempts, 0);
  const answered = vs.reduce((n, v) => n + v.calls.answered, 0);
  return { cases, returned, ready, attempts, answered, unanswered: attempts - answered };
}

/** The invariants every number on the page relies on; an empty list means the dataset reconciles. */
export function problems(vs: Variant[] = VARIANTS): string[] {
  const out: string[] = [];
  for (const v of vs) {
    const d = derive(v);
    const lanes: [string, keyof Lane][] = [["self", "self"], ["call", "call"]];
    for (const [label, k] of lanes) {
      if (!(v.returned[k] >= v.uploaded[k] && v.uploaded[k] >= v.ready[k] && v.ready[k] >= 0)) out.push(`${v.id}: ${label} lane not monotonic`);
    }
    if (d.returned > v.cases) out.push(`${v.id}: more returns than cases`);
    if (v.calls.attempts < d.contacted || v.calls.attempts > d.contacted * 2) out.push(`${v.id}: attempts outside 1–2 per contacted case`);
    if (v.calls.answered < v.returned.call || v.calls.answered > d.contacted) out.push(`${v.id}: answered calls inconsistent`);
  }
  return out;
}

export const pct = (x: number, digits = 1) => `${Number((x * 100).toFixed(digits))}%`;
export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
