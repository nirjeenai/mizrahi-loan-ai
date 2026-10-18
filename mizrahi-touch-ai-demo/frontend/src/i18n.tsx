import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/** Hebrew / English for the whole platform: the customer app, the presenter pane, /banker, /admin and /system share one
 *  language. Hebrew is the default and the approved baseline: every Hebrew string stays where it was, as the first
 *  argument of `t(he, en)`, so the Hebrew screens render exactly as before. `LangProvider` sits above the router, so a
 *  choice made on any page holds on every page; in English `<html>` is `dir="ltr" lang="en"` (Hebrew keeps index.html's
 *  own `rtl`/`he`). Switching never remounts anything, so every screen keeps its state.
 *  VITE_LANG_SWITCH=0 builds the app without the switch: Hebrew only, and no language header is ever sent. */
export type Lang = "he" | "en";
export const LANG_SWITCH = import.meta.env.VITE_LANG_SWITCH !== "0";
const KEY = "mz.lang";

let current: Lang = "he";
/** the platform's language right now */
export const currentLang = (): Lang => current;
/** `t` for helpers outside components; correct while a component that called `useLang()` renders */
export const tr = <T,>(he: T, en: T): T => (current === "en" ? en : he);

/** `?lang=en|he` (a shared link) wins and is remembered; otherwise the remembered choice; otherwise Hebrew */
function initial(): Lang {
  if (!LANG_SWITCH) return "he";
  try {
    const url = new URL(window.location.href);
    const q = url.searchParams.get("lang");
    if (q === "en" || q === "he") {
      remember(q);
      url.searchParams.delete("lang");
      window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
      return q;
    }
  } catch { /* no URL access: fall through */ }
  try { return window.localStorage.getItem(KEY) === "en" ? "en" : "he"; } catch { return "he"; }
}

function remember(lang: Lang) {
  try {
    if (lang === "en") window.localStorage.setItem(KEY, "en");
    else window.localStorage.removeItem(KEY);              // Hebrew is the default: nothing stored
  } catch { /* private mode or blocked storage: the choice lasts for this page only */ }
}

interface LangCtx { lang: Lang; setLang: (l: Lang) => void }
const Ctx = createContext<LangCtx | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initial);
  current = lang;                                          // set while rendering, so tr() in this render agrees
  useEffect(() => {                                        // the page's direction and the tab's title follow; Hebrew keeps index.html's own
    if (lang !== "en") return;
    const html = document.documentElement;
    const before = { title: document.title, dir: html.dir, lang: html.lang };
    html.dir = "ltr"; html.lang = "en"; html.dataset.lang = "en";
    document.title = "Tefahot Touch × Jeen";
    return () => { document.title = before.title; html.dir = before.dir; html.lang = before.lang; delete html.dataset.lang; };
  }, [lang]);
  const value = useMemo<LangCtx>(() => ({ lang, setLang: (l) => { remember(l); setLangState(l); } }), [lang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** The language, its setter and `t(he, en)`. Calling it also re-renders the component when the language changes. */
export function useLang() {
  const v = useContext(Ctx);
  const lang: Lang = v?.lang ?? "he";
  return {
    lang, en: lang === "en", setLang: v?.setLang ?? (() => undefined),
    t: <T,>(he: T, en: T): T => (lang === "en" ? en : he),
  };
}

/** The platform's language switch: one segmented control, the same state as the phone's chip and drawer row. Each
 *  option is written in its own language. `tone="dark"` for the staff console's navy bar. */
export function LangSwitch({ tone = "light", className = "" }: { tone?: "light" | "dark"; className?: string }) {
  const { lang, setLang } = useLang();
  if (!LANG_SWITCH) return null;
  return (
    <div className={`lang-switch lang-switch-${tone} ${className}`} role="radiogroup" aria-label={lang === "en" ? "Language" : "שפה"}
      data-testid="global-lang" data-lang={lang}>
      {(["he", "en"] as Lang[]).map((l) => (
        <button key={l} type="button" role="radio" aria-checked={lang === l} lang={l} className={lang === l ? "on" : ""}
          tabIndex={lang === l ? 0 : -1} onClick={() => setLang(l)} data-testid={`global-lang-${l}`}
          onKeyDown={(e) => { if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) { e.preventDefault(); const o: Lang = l === "he" ? "en" : "he"; setLang(o); (e.currentTarget.parentElement?.querySelector(`[lang=${o}]`) as HTMLElement | null)?.focus(); } }}>
          {l === "he" ? "עברית" : "English"}</button>
      ))}
    </div>
  );
}

/** A server text with an optional English sibling (`title_he` / `title_en`). Hebrew: the Hebrew value, untouched.
 *  English: the English value, or the Hebrew original isolated as Hebrew when the server sent no English. */
export function Loc({ he, en, block }: { he?: string | null; en?: string | null; block?: boolean }) {
  const { en: english } = useLang();
  if (!english) return <>{he ?? ""}</>;
  if (en) return <>{en}</>;
  if (!he) return null;
  return block ? <div lang="he" dir="rtl" className="orig-he">{he}</div> : <bdi lang="he" dir="rtl">{he}</bdi>;
}

/** Source text kept as written — a customer's or banker's own words, a document's printed value, a quote, the model's
 *  own wording. Hebrew: the text, untouched. English: the text in its own direction with an "Original (Hebrew)" tag, so
 *  a visitor can tell it from untranslated interface text. Text with no Hebrew in it shows as is. */
export function Orig({ text, block }: { text?: string | null; block?: boolean }) {
  const { en } = useLang();
  if (!text) return null;
  if (!en || !/[\u0590-\u05FF]/.test(text)) return <>{text}</>;
  const Tag = block ? "div" : "span";
  return <Tag lang="he" dir="rtl" className={block ? "orig-he orig-block" : "orig-he-inline"}>
    <span className="orig-tag" lang="en" dir="ltr">Original (Hebrew)</span> {text}</Tag>;
}

/** the plain-text form of <Loc> (attributes, aria-labels, joins) */
export const loc = (he?: string | null, en?: string | null): string => (current === "en" && en ? en : he ?? "");

/** The English sibling of a server field, by the platform's naming: `title_he` → `title_en`, `labelHe` → `labelEn`,
 *  `summary` → `summary_en`. For a string list, `locList(o, "reasons_he")` pairs each item with its English twin. */
export const enKey = (key: string): string =>
  key.endsWith("_he") ? `${key.slice(0, -3)}_en` : key.endsWith("He") ? `${key.slice(0, -2)}En` : `${key}_en`;
/** `loc(o[key], o[enKey(key)])` */
export const locOf = (o: any, key: string): string => loc(o?.[key], o?.[enKey(key)]);
/** a string list in the platform's language: each item's English twin when there is one, else the Hebrew item */
export const locList = (o: any, key: string): string[] => {
  const he: string[] = o?.[key] || [];
  const en: (string | null)[] | undefined = o?.[enKey(key)];
  return he.map((h, i) => loc(h, en?.[i]));
};
