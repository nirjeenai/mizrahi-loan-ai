import type { ReactNode } from "react";
import { useLang } from "../../i18n";
import "./bankletter.css";

/** A customer letter on Mizrahi-Tefahot letterhead: logo and document type, the brand rule, the body, and a footer with
 *  the bank's name and the draft status. One layout for every reply type; `demo` puts the non-binding line in the footer.
 *  The letter is the customer's (Hebrew): in English the banker-facing labels change and the sheet stays right-to-left. */
export function LetterSheet({ docType, demo, compact, children }: { docType: string; demo?: boolean; compact?: boolean; children: ReactNode }) {
  const { en, t } = useLang();
  return (
    <article className={`bl${compact ? " compact" : ""}`} data-testid="cc-letter" {...(en ? { dir: "rtl", lang: "he" } : {})}>
      <header className="bl-head">
        <img className="bl-logo" src="/brand/mizrahi-logo.svg" alt={t("מזרחי טפחות", "Mizrahi-Tefahot")} />
        <div className="bl-head-meta" {...(en ? { lang: "en" } : {})}>
          <span className="bl-doctype">{docType}</span>
          <span className="bl-state">{t("טיוטה · טרם נשלחה", "Draft · not sent yet")}</span>
        </div>
      </header>
      <div className="bl-rule" aria-hidden><i /><i /></div>
      <div className="bl-body">{children}</div>
      <footer className="bl-foot">
        <span className="bl-foot-bank">בנק מזרחי טפחות בע״מ</span>
        <span {...(en ? { lang: "en" } : {})}>{demo ? t("אינו החלטת אשראי ואינו הסכם הלוואה · לא נשלח ללקוח", "Not a credit decision and not a loan agreement · not sent to the customer")
          : t("טיוטה לעיון הבנקאי · לא נשלחה ללקוח", "Draft for the banker's review · not sent to the customer")}</span>
      </footer>
    </article>
  );
}

type Block =
  | { t: "title" | "greet" | "h"; text: string }
  | { t: "p" | "ul" | "ol" | "sign" | "notice"; lines: string[] }
  | { t: "meta" | "kv"; rows: [string, string][] };

const META = /^(תאריך|לכבוד|סימוכין|הנדון):\s*(.*)$/;
const GREET = /^(שלום|לכבוד)\s.+,$/;
const SIGN = /^(בברכה|בכבוד רב|בברכה רבה),?$/;
const RULE = /^[—–-]{3,}$/;
const BULLET = /^•\s*/;
const NUM = /^\d+[.)]\s+/;

/** Reads structure out of the plain-text letter — nothing is added, dropped or reworded; the editor keeps plain text. */
export function parseLetter(text: string): Block[] {
  const L = text.split("\n").map((l) => l.trim());
  const out: Block[] = [];
  const first = L.findIndex(Boolean);
  const special = (s: string) => !s || BULLET.test(s) || NUM.test(s) || SIGN.test(s) || RULE.test(s) || META.test(s);
  let i = 0;
  while (i < L.length) {
    const s = L[i];
    if (!s) { i++; continue; }
    if (i === first && !GREET.test(s) && !META.test(s) && s.length < 90 && !/[.,:;!?]$/.test(s)) { out.push({ t: "title", text: s }); i++; continue; }
    if (META.test(s)) {
      const rows: [string, string][] = [];
      while (i < L.length && META.test(L[i])) { const m = L[i].match(META)!; rows.push([m[1], m[2]]); i++; }
      out.push({ t: "meta", rows });
      continue;
    }
    if (GREET.test(s) && !out.some((b) => b.t === "greet")) { out.push({ t: "greet", text: s }); i++; continue; }
    if (SIGN.test(s)) {
      const lines: string[] = [];
      while (i < L.length && L[i]) lines.push(L[i++]);
      out.push({ t: "sign", lines });
      continue;
    }
    if (RULE.test(s)) {
      out.push({ t: "notice", lines: L.slice(i + 1).filter(Boolean) });
      break;
    }
    if (BULLET.test(s)) {
      const items: string[] = [];
      while (i < L.length && BULLET.test(L[i])) items.push(L[i++].replace(BULLET, ""));
      out.push(items.every((x) => /^[^:]{2,40}:\s/.test(x))
        ? { t: "kv", rows: items.map((x) => { const k = x.indexOf(":"); return [x.slice(0, k), x.slice(k + 1).trim()] as [string, string]; }) }
        : { t: "ul", lines: items });
      continue;
    }
    if (NUM.test(s)) {
      const items: string[] = [];
      while (i < L.length && NUM.test(L[i])) items.push(L[i++].replace(NUM, ""));
      out.push({ t: "ol", lines: items });
      continue;
    }
    const next = L[i + 1] || "";
    if (s.length <= 40 && !/[.,:;!?)]$/.test(s) && (i === 0 || !L[i - 1]) && next && !BULLET.test(s)) { out.push({ t: "h", text: s }); i++; continue; }
    const lines: string[] = [];
    while (i < L.length && L[i] && !(lines.length && special(L[i]))) lines.push(L[i++]);
    out.push({ t: "p", lines });
  }
  return out;
}

const br = (lines: string[]) => lines.map((l, i) => <span key={i}>{l}{i < lines.length - 1 && <br />}</span>);

export function LetterBody({ text }: { text: string }) {
  return <>{parseLetter(text).map((b, i) => {
    switch (b.t) {
      case "title": return <h2 key={i} className="bl-title">{b.text}</h2>;
      case "meta": return <dl key={i} className="bl-meta">{b.rows.map(([k, v]) => <div key={k} className={k === "הנדון" ? "subj" : ""}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
      case "greet": return <p key={i} className="bl-greet">{b.text}</p>;
      case "h": return <h3 key={i} className="bl-h">{b.text}</h3>;
      case "kv": return <dl key={i} className="bl-terms">{b.rows.map(([k, v], j) => <div key={j}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
      case "ul": return <ul key={i} className="bl-ul">{b.lines.map((l, j) => <li key={j}>{l}</li>)}</ul>;
      case "ol": return <ol key={i} className="bl-ol">{b.lines.map((l, j) => <li key={j}>{l}</li>)}</ol>;
      case "sign": return <div key={i} className="bl-sign">{b.lines.map((l, j) => <span key={j} className={j === 1 ? "name" : j > 1 ? "role" : ""}>{l}</span>)}</div>;
      case "notice": return <aside key={i} className="bl-notice">{br(b.lines)}</aside>;
      default: return <p key={i} className="bl-p">{br(b.lines)}</p>;
    }
  })}</>;
}
