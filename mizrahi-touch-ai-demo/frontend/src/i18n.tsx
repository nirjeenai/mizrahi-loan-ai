import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/** Hebrew / English for the customer app (/customer). Hebrew is the default and the approved baseline: every Hebrew
 *  string stays where it was, as the first argument of `t(he, en)`, so the Hebrew screens render exactly as before.
 *  The language applies to the customer phone only (TouchShell puts dir/lang on `.phone`); the presenter pane, /banker,
 *  /system and /admin stay Hebrew. Switching never remounts anything, so every screen keeps its state.
 *  VITE_LANG_SWITCH=0 builds the app without the switch: Hebrew only, and no language header is ever sent. */
export type Lang = "he" | "en";
export const LANG_SWITCH = import.meta.env.VITE_LANG_SWITCH !== "0";
const KEY = "mz.lang";

let current: Lang = "he";
/** the customer app's language right now (Hebrew outside /customer) */
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
  useEffect(() => () => { current = "he"; }, []);          // leaving /customer: everything else is Hebrew
  useEffect(() => {                                        // the tab's title follows; Hebrew keeps index.html's own
    if (lang !== "en") return;
    const before = document.title;
    document.title = "Tefahot Touch × Jeen";
    return () => { document.title = before; };
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

/** A server text with an optional English sibling (`title_he` / `title_en`). Hebrew: the Hebrew value, untouched.
 *  English: the English value, or the Hebrew original isolated as Hebrew when the server sent no English. */
export function Loc({ he, en, block }: { he?: string | null; en?: string | null; block?: boolean }) {
  const { en: english } = useLang();
  if (!english) return <>{he ?? ""}</>;
  if (en) return <>{en}</>;
  if (!he) return null;
  return block ? <div lang="he" dir="rtl" className="orig-he">{he}</div> : <bdi lang="he" dir="rtl">{he}</bdi>;
}

/** the plain-text form of <Loc> (attributes, aria-labels, joins) */
export const loc = (he?: string | null, en?: string | null): string => (current === "en" && en ? en : he ?? "");
