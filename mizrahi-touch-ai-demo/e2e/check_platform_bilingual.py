"""The whole platform in Hebrew and English, in a real Chrome — REPLAY stack, no model call.

What it proves:
- The global switch: Hebrew on a fresh browser; EN on /banker turns the page LTR without changing the URL (the open
  case and view stay); the choice survives a reload and navigation to /admin, /system and /customer (the phone agrees);
  עברית restores RTL and stores nothing.
- An English banker journey on case 006: the V3 case, a document's evidence drawer, the V2 briefing, the V1 review desk,
  and the Jeen chat — its answer mocked in the browser (the request must carry X-MZ-Lang: en), so no model is called.
- Admin (every tab), the system page and the presenter pane in English.
- For every English screen: the visible Hebrew left outside marked originals (lang=he), printed as a list.
- Layout: no horizontal scroll on /banker, /admin and /system at 390 and 1440 px in English.
- Optional Hebrew regression: with BASELINE_BASE (a build of main in front of the same backend), the Hebrew text of
  /banker (V1/V2/V3), /admin, /system and /customer equals the baseline's, apart from the switch's own labels.

    # from mizrahi-touch-ai-demo/ — the built app in front of an isolated REPLAY backend
    node e2e/serve_frontend.mjs e2e/artifacts/i18n/web 5850 http://127.0.0.1:8792
    PLATFORM_BASE=http://127.0.0.1:5850 [BASELINE_BASE=http://127.0.0.1:5849] backend/.venv/bin/python e2e/check_platform_bilingual.py
Results are REPLAY results."""
from __future__ import annotations

import difflib
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

import isolation

BASE = os.environ.get("PLATFORM_BASE", "http://127.0.0.1:5850")
BASELINE = os.environ.get("BASELINE_BASE")
for b in filter(None, (BASE, BASELINE)):
    if any(p in b for p in (":8790", ":8791", ":5192")):
        sys.exit(f"refusing to run against {b}: use an isolated stack")
isolation.require_isolated(BASE)
CASE = "DEMO-MTZ-2026-006"
OUT = Path(__file__).resolve().parent / "artifacts" / "i18n" / "platform"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list[tuple[str, bool, str]] = []
LEFT: dict[str, list[str]] = {}


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def shot(page: Page, name: str, full: bool = False) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)


# visible text with Hebrew letters, outside what is Hebrew by design: the switches, text marked as the Hebrew original
HEBREW_LEFT_JS = """() => {
  const skip = '[data-testid=global-lang], .lang-chip, [data-testid=drawer-lang], [lang=he], .orig-he, .orig-he-inline';
  const out = new Set();
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const el = n.parentElement;
    if (!el || el.closest(skip) || !el.getClientRects().length) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    const he = (n.textContent.match(/[\\u0590-\\u05FF]/g) || []).length;
    const latin = (n.textContent.match(/[A-Za-z]/g) || []).length;
    // an English sentence quoting a Hebrew term (a document's printed mark) is English
    if (he && latin <= 3 * he) out.add(n.textContent.trim().slice(0, 120));
  }
  return [...out];
}"""


def hebrew_left(page: Page, screen: str) -> list[str]:
    left = page.evaluate(HEBREW_LEFT_JS)
    LEFT[screen] = left
    return left


def html(page: Page) -> dict:
    return page.evaluate("() => ({dir: document.documentElement.dir, lang: document.documentElement.lang,"
                         " stored: localStorage.getItem('mz.lang')})")


def overflow(page: Page) -> int:
    return page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")


def settle(page: Page, ms: int = 1800) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


def english_screen(page: Page, screen: str, budget: int = 0, full: bool = False) -> None:
    shot(page, f"en-{screen}", full)
    left = hebrew_left(page, screen)
    check(f"{screen}: no unmarked Hebrew on screen", len(left) <= budget,
          f"{len(left)} text(s): {left[:6]}" if left else "")


MOCK = {"intent": "question", "lang": "en", "source_ids": [], "sources": {}, "edit": None, "rejected_issues_he": [],
        "repaired": False, "model": "mock",
        "answer_he": "The income is verified on three consecutive payslips (July–September 2026). "
                     "The bank statement is still open, so the case is not ready for credit review yet."}


def run_english(page: Page) -> None:
    seen_lang: list[str] = []

    def chat(route):
        seen_lang.append(route.request.headers.get("x-mz-lang", ""))
        route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK))
    page.route("**/api/banker/cases/*/chat", chat)

    # fresh browser → Hebrew
    page.goto(f"{BASE}/banker?case={CASE}&view=case"); settle(page)
    h = html(page)
    check("fresh browser is Hebrew (rtl, nothing stored)", h["dir"] == "rtl" and h["stored"] is None, str(h))
    check("global switch is in the console bar", page.locator(".console-top [data-testid=global-lang]").is_visible())
    shot(page, "he-banker-v3")
    url_before = page.url

    # HE → EN on the banker console
    page.click("[data-testid=global-lang-en]"); page.wait_for_timeout(600)
    h = html(page)
    check("EN: page is ltr/en and remembered", h["dir"] == "ltr" and h["lang"] == "en" and h["stored"] == "en", str(h))
    check("EN: the open case and view stay (URL unchanged)", page.url == url_before, page.url)
    settle(page)
    english_screen(page, "banker-v3", full=True)

    # evidence drawer
    docs = page.locator("[data-testid=cc-doc]")
    if docs.count():
        docs.first.click(); page.wait_for_timeout(1500)
        drawer = page.locator("[data-testid=cc-docdrawer]")
        check("V3: document drawer opens", drawer.is_visible())
        english_screen(page, "banker-v3-document")
        page.keyboard.press("Escape"); page.wait_for_timeout(400)
        if drawer.is_visible():
            page.click("[data-testid=cc-docdrawer-close]")
    else:
        check("V3: case has documents", False)

    # Jeen chat (mocked)
    tab = page.locator("[data-testid=cc-pane-chat]")      # a tab only where the draft and the chat share one column
    if tab.is_visible():
        tab.click()
    page.locator("[data-testid=cc-chat-input]").scroll_into_view_if_needed()
    page.fill("[data-testid=cc-chat-input]", "Is the income verified?")
    page.click("[data-testid=cc-chat-send]")
    page.wait_for_timeout(1500)
    msgs = page.locator("[data-testid=cc-chat-msg]")
    text = " ".join(msgs.all_inner_texts())
    check("chat: request carries X-MZ-Lang: en", seen_lang[-1:] == ["en"], str(seen_lang))
    check("chat: English answer shown", "verified on three consecutive payslips" in text, text[-160:])
    page.locator("[data-testid=cc-chat]").scroll_into_view_if_needed()
    shot(page, "en-banker-chat")

    # reload keeps English
    page.reload(); settle(page)
    check("EN survives a reload", html(page)["dir"] == "ltr")

    page.goto(f"{BASE}/banker?case={CASE}&view=intel"); settle(page, 2500)
    english_screen(page, "banker-v2", full=True)
    page.goto(f"{BASE}/banker?case={CASE}"); settle(page, 2500)
    english_screen(page, "banker-v1", full=True)
    items = page.locator(".ws-doc, [data-testid^=doc-row], [data-testid=review-item]")
    if items.count():
        items.first.click(); page.wait_for_timeout(1500)
        english_screen(page, "banker-v1-document")

    # navigation keeps English: admin (every tab), system, customer + presenter
    page.click("[data-testid=nav-admin]"); settle(page)
    check("EN holds after navigating to /admin", html(page)["dir"] == "ltr")
    english_screen(page, "admin")
    tabs = page.locator("nav.view-tabs button")
    for i in range(tabs.count()):
        tabs.nth(i).click(); page.wait_for_timeout(1200)
        english_screen(page, f"admin-tab{i + 1}")
    page.goto(f"{BASE}/system"); settle(page)
    english_screen(page, "system", full=True)
    page.goto(f"{BASE}/customer"); settle(page)
    phone = page.evaluate("() => document.querySelector('.phone')?.getAttribute('lang')")
    check("/customer: the phone follows the global language", phone == "en", str(phone))
    page.click("[data-testid=presenter-toggle]"); page.wait_for_timeout(900)
    more = page.locator("[data-testid=more-tests-toggle]")
    if more.count():
        more.first.click(); page.wait_for_timeout(500)
    english_screen(page, "presenter")

    # layout
    for path in (f"/banker?case={CASE}&view=case", "/admin", "/system"):
        page.goto(BASE + path); settle(page, 1200)
        check(f"1440px EN {path}: no horizontal scroll", overflow(page) <= 1, str(overflow(page)))

    # EN → HE
    page.goto(f"{BASE}/banker?case={CASE}&view=case"); settle(page)
    url_before = page.url
    page.click("[data-testid=global-lang-he]"); page.wait_for_timeout(600)
    h = html(page)
    check("HE restored: rtl/he, nothing stored, same URL", h["dir"] == "rtl" and h["stored"] is None and page.url == url_before, str(h))


def run_mobile(browser) -> None:
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.add_init_script("try{localStorage.setItem('mz.lang','en')}catch(e){}")
    page = ctx.new_page()
    for name, path in (("banker", f"/banker?case={CASE}&view=case"), ("admin", "/admin"), ("system", "/system"),
                       ("customer", "/customer")):
        page.goto(BASE + path); settle(page, 1500)
        check(f"390px EN {path}: no horizontal scroll", overflow(page) <= 1, str(overflow(page)))
        shot(page, f"en-mobile-{name}")
    ctx.close()


HE_PAGES = [("banker-v1", f"/banker?case={CASE}"), ("banker-v2", f"/banker?case={CASE}&view=intel"),
            ("banker-v3", f"/banker?case={CASE}&view=case"), ("admin", "/admin"), ("system", "/system"),
            ("customer", "/customer")]
# the switch's own labels are the one intended Hebrew difference
SWITCH = ("עברית", "English")


def he_text(browser, base: str, path: str) -> list[str]:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(base + path); settle(page, 2500)
    text = page.evaluate("() => document.body.innerText")
    ctx.close()
    return [ln for ln in (s.strip() for s in text.splitlines()) if ln and ln not in SWITCH]


def run_hebrew_regression(browser) -> None:
    for name, path in HE_PAGES:
        a, b = he_text(browser, BASELINE, path), he_text(browser, BASE, path)
        diff = [d for d in difflib.unified_diff(a, b, lineterm="", n=0) if d[:1] in "+-" and d[:3] not in ("+++", "---")]
        check(f"Hebrew {name}: text identical to main", not diff, "; ".join(diff[:8]))


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    try:
        run_english(page)
    finally:
        ctx.close()
    run_mobile(browser)
    if BASELINE:
        run_hebrew_regression(browser)
    browser.close()

(OUT / "hebrew-left.json").write_text(json.dumps(LEFT, ensure_ascii=False, indent=1), encoding="utf-8")
failed = [r for r in RESULTS if not r[1]]
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed (REPLAY) · screenshots in {OUT}")
sys.exit(1 if failed else 0)
