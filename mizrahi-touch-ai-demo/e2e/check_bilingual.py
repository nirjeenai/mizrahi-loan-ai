"""The customer app in Hebrew and English, in a real Chrome — REPLAY stack, no model call.

What it proves (each line is one or more checks):
- The language switch on the main customer page: visible, keyboard-operable, labelled; it changes only the language —
  the route, the active case, an unsent message and the conversation stay; no write request and no model call happen.
- The choice persists (reload), `?lang=` deep-links it, and the drawer's language row agrees with the header chip.
- English end to end: home, documents, the document check (code explanations in English, the reviewer's own words
  marked as the Hebrew original), request details, stages, meetings, tools, the assistant (its no-model answer from
  case data in English), the conversational application (typed English understood, the simulator, the summary, the
  case opened, the documents handoff) — with no Hebrew left on screen beyond marked originals and customer data.
- History across languages: a conversation saved before English existed shows in Hebrew with a "Continuing in English"
  marker and the open question asked again live in English; an assistant reply from a Hebrew session is marked
  "Original (Hebrew)" in English, an English one "נכתב באנגלית" in Hebrew.
- Layout: no horizontal scroll and no header overlap at 320 / 390 / 1440 px in both languages.

Hebrew itself is covered by the Hebrew suites and the pixel comparison (e2e/bilingual_screens.py), not here.

    # from backend/ — a fresh REPLAY backend (no Gemini; recorded reviews)
    .venv/bin/python ../e2e/replay_backend.py --port 8797 --data ../e2e/artifacts/bilingual/check-data
    # from mizrahi-touch-ai-demo/ — the built app in front of it
    node e2e/serve_frontend.mjs <built dist> 5852 http://127.0.0.1:8797
    BILINGUAL_BASE=http://127.0.0.1:5852 backend/.venv/bin/python e2e/check_bilingual.py
Results are REPLAY results."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

import isolation
import bilingual_screens as S

BASE = os.environ.get("BILINGUAL_BASE", "http://127.0.0.1:5852")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
isolation.require_isolated(BASE)
OUT = Path(__file__).resolve().parent / "artifacts" / "bilingual" / "check"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list[tuple[str, bool, str]] = []
HEBREW = re.compile(r"[֐-׿]")


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def shot(page: Page, name: str, full: bool = False) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)


def phone(page: Page) -> dict:
    return page.evaluate("() => { const p = document.querySelector('.phone');"
                         " return {lang: p.getAttribute('lang'), dir: p.getAttribute('dir'), data: p.dataset.lang || null} }")


# visible text with Hebrew letters, outside what is Hebrew by design: the chip back to Hebrew, the drawer's language
# row, text marked as the Hebrew original (lang=he), and `allow` (customer data such as a typed name)
HEBREW_LEFT_JS = """allow => {
  const skip = '.lang-chip, [data-testid=drawer-lang], [lang=he], .orig-he, .orig-he-inline, [data-testid=turn-original]';
  const out = [];
  const walk = document.createTreeWalker(document.querySelector('.phone'), NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const el = n.parentElement;
    if (!el || el.closest(skip) || !el.getClientRects().length) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    let t = n.textContent;
    for (const a of allow) t = t.split(a).join('');
    if (/[\\u0590-\\u05FF]/.test(t)) out.push(n.textContent.trim().slice(0, 90));
  }
  return out;
}"""


def hebrew_left(page: Page, allow: tuple[str, ...] = ()) -> list[str]:
    return page.evaluate(HEBREW_LEFT_JS, list(allow))


def no_overflow(page: Page) -> tuple[bool, str]:
    r = page.evaluate("""() => {
      const s = document.scrollingElement, chip = document.querySelector('[data-testid=lang-switch]');
      const pill = document.querySelector('.case-pill'), head = document.querySelector('.touch-header');
      const b = (e) => e ? e.getBoundingClientRect() : null;
      const c = b(chip), p = b(pill), h = b(head);
      const overlap = c && p ? !(c.right <= p.left || p.right <= c.left || c.bottom <= p.top || p.bottom <= c.top) : false;
      const inside = c && h ? c.left >= h.left - 0.5 && c.right <= h.right + 0.5 && c.top >= h.top - 0.5 && c.bottom <= h.bottom + 0.5 : false;
      return {scroll: s.scrollWidth - window.innerWidth, overlap, inside, chip: !!c && c.width > 0};
    }""")
    return r["scroll"] <= 0 and not r["overlap"] and r["inside"] and r["chip"], str(r)


class Requests:
    """Every API call the app makes (fetch/XHR; an <img> or a file download is not one) while recording, with its
    method and language header."""

    def __init__(self, page: Page):
        self.items: list[tuple[str, str, str | None]] = []
        self.on = False
        page.on("request", lambda r: self.on and "/api/" in r.url and r.resource_type in ("fetch", "xhr") and self.items.append(
            (r.method, r.url.split("/api/", 1)[1], r.headers.get("x-mz-lang"))))

    def __enter__(self):
        self.items, self.on = [], True
        return self

    def __exit__(self, *exc):
        self.on = False


def switch(page: Page, via_keyboard: bool = False) -> None:
    chip = page.locator("[data-testid=lang-switch]")
    target = "en" if chip.get_attribute("data-lang") == "he" else "he"
    if via_keyboard:
        chip.focus()
        page.keyboard.press("Enter")
    else:
        chip.click()
    expect(chip).to_have_attribute("data-lang", target, timeout=5000)
    page.wait_for_timeout(400)


def cv2_items(page: Page) -> int:
    return page.locator("[data-testid=cv2-log] > *").count()


def cv2_settle(page: Page, before: int) -> None:
    page.wait_for_function(
        "n => document.querySelectorAll('[data-testid=cv2-log] > *').length > n && !document.querySelector('.cv2-typing')",
        arg=before, timeout=30000)
    page.wait_for_timeout(300)


def say(page: Page, text: str) -> None:
    before = cv2_items(page)
    page.locator("[data-testid=cv2-input]").fill(text)
    page.locator("[data-testid=cv2-send]").click()
    cv2_settle(page, before)


def reply(page: Page, value: str) -> None:
    before = cv2_items(page)
    page.locator(f"[data-testid=cv2-reply][data-value='{value}']").click()
    cv2_settle(page, before)


def last_assistant(page: Page) -> str:
    return page.locator("[data-testid=cv2-msg]:not([data-kind=user])").last.inner_text()


# ---------------------------------------------------------------- 1. the switch on the main page
def main_page(page: Page, api: httpx.Client) -> None:
    S.prepare(page, BASE, "he", S.CORRECTION)
    page.goto(BASE + "/customer")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    S.settle_page(page)
    chip = page.locator("[data-testid=lang-switch]")
    check("he: the switch is visible on the main customer page", chip.is_visible())
    check("he: the switch offers English with an accessible name",
          chip.inner_text().strip() == "EN" and chip.get_attribute("aria-label") == "Switch to English"
          and chip.get_attribute("lang") == "en", f"{chip.inner_text()!r} / {chip.get_attribute('aria-label')!r}")
    check("he: the phone keeps the page's Hebrew direction (no lang/dir override)", phone(page) == {"lang": None, "dir": None, "data": None},
          str(phone(page)))
    title_he = page.title()
    pill_he = page.locator(".case-pill").inner_text()
    stored_case = page.evaluate("() => localStorage.getItem('mz.case')")
    shot(page, "1-home-he")

    with Requests(page) as reqs:
        switch(page, via_keyboard=True)
    check("switch by keyboard (focus + Enter) turns the app English", phone(page) == {"lang": "en", "dir": "ltr", "data": "en"},
          str(phone(page)))
    writes = [r for r in reqs.items if r[0] != "GET"]
    check("switching makes no write request and no model call", not writes, str(writes))
    check("the active case and route stay", page.evaluate("() => localStorage.getItem('mz.case')") == stored_case
          and page.url.rstrip("/").endswith("/customer"), page.url)
    check("en: the header now offers Hebrew back", chip.inner_text().strip() == "עב" and chip.get_attribute("aria-label") == "מעבר לעברית"
          and chip.get_attribute("lang") == "he")
    check("en: the greeting and case pill are English", page.locator("h1").first.inner_text().startswith("Hello")
          and page.locator(".case-pill").inner_text() != pill_he, page.locator(".case-pill").inner_text())
    check("en: the tab title is English", page.title() == "Tefahot Touch × JEEN" and title_he != page.title(), page.title())
    left = hebrew_left(page)
    check("en: no Hebrew left on the home screen", not left, str(left))
    shot(page, "1-home-en")

    with Requests(page) as reqs:
        page.reload()
        expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
        S.settle_page(page)
    check("the choice persists over a reload", phone(page)["lang"] == "en" and page.evaluate("() => localStorage.getItem('mz.lang')") == "en")
    # every read of the customer API carries the language (the presence beacon returns no wording and goes without)
    reads = [(u, h) for m, u, h in reqs.items if m == "GET" and u.startswith(("cases/", "documents/"))]
    check("the English app sends its language on every customer API read", reads and all(h == "en" for _, h in reads),
          str([u for u, h in reads if h != "en"][:4]))

    for path, ready in (("/customer/documents", "[data-testid='req-PAYSLIPS:BRW-A']"), ("/customer/request", ".card"),
                        ("/customer/stages", ".card"), ("/customer/meetings", ".card"), ("/customer/tools", ".card")):
        page.goto(BASE + path)
        expect(page.locator(ready).first).to_be_visible(timeout=20000)
        S.settle_page(page)
        left = hebrew_left(page)
        check(f"en: no Hebrew left on {path}", not left, str(left[:4]))
        shot(page, "1-" + path.rsplit("/", 1)[1] + "-en")

    # the drawer agrees with the chip, and sets Hebrew back
    page.goto(BASE + "/customer")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    page.locator(".touch-header .icon-btn").first.click()
    en_radio, he_radio = page.locator("[data-testid=drawer-lang-en]"), page.locator("[data-testid=drawer-lang-he]")
    expect(en_radio).to_be_visible(timeout=5000)
    check("drawer: the language row shows English selected", en_radio.get_attribute("aria-checked") == "true"
          and he_radio.get_attribute("aria-checked") == "false")
    shot(page, "1-drawer-en")
    check("drawer: one tab stop, on the selected language", en_radio.get_attribute("tabindex") == "0"
          and he_radio.get_attribute("tabindex") == "-1")
    en_radio.focus()
    page.keyboard.press("ArrowRight")                  # the ARIA radio pattern: an arrow key moves to and chooses
    page.wait_for_timeout(400)
    check("drawer: the arrow key chooses עברית: the app turns Hebrew and forgets the choice", phone(page)["lang"] is None
          and page.evaluate("() => localStorage.getItem('mz.lang')") is None and chip.get_attribute("data-lang") == "he")
    page.keyboard.press("Escape")
    page.goto(BASE + "/customer?lang=en")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    check("?lang=en deep-links the English app", phone(page)["lang"] == "en")
    page.goto(BASE + "/customer?lang=he")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    check("?lang=he deep-links the Hebrew app", phone(page)["lang"] is None)


# ---------------------------------------------------------------- 2. layout in both languages
def layout(page: Page) -> None:
    for width, height in ((320, 700), (390, 844), (1440, 900)):
        page.set_viewport_size({"width": width, "height": height})
        for lang in ("he", "en"):
            page.goto(BASE + f"/customer?lang={lang}")
            expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
            page.wait_for_timeout(500)
            ok, detail = no_overflow(page)
            check(f"layout {width}px {lang}: chip inside the header, no overlap, no horizontal scroll", ok, detail)
            if width == 320:
                shot(page, f"2-header-320-{lang}")
    page.set_viewport_size(S.MOBILE)
    page.goto(BASE + "/customer?lang=he")


# ---------------------------------------------------------------- 3. the document check
def document_review(page: Page, api: httpx.Client) -> None:
    docs = api.get(f"/api/cases/{S.CORRECTION}/documents").json()
    doc = next(d for d in docs if d["filename"].endswith("_09.pdf") or "2026_09" in d["filename"])
    page.goto(BASE + f"/customer/documents/{doc['document_id']}?lang=en")
    expect(page.locator(".crit").first).to_be_visible(timeout=20000)
    S.settle_page(page)
    crit = page.locator(".crit")
    rows = [crit.nth(i).inner_text() for i in range(crit.count())]
    code_rows = [r for r in rows if "Deterministic rule" in r]
    judge_rows = [r for r in rows if "LLM judge" in r or "Rule + judge" in r]
    check("en: every criterion title is English", all(not HEBREW.search(r.split("\n")[1] if "\n" in r else r) for r in rows),
          str([r.split("\n")[1][:50] for r in rows if HEBREW.search(r.split("\n")[1] if "\n" in r else r)][:3]))
    printed_values = ("עידו לוי", "אביב מערכות דיגיטל בע״מ")
    english_code = [r for r in code_rows if not HEBREW.search(re.sub("|".join(printed_values), "", r))]
    check("en: explanations the review code wrote are English", code_rows and len(english_code) == len(code_rows),
          f"{len(english_code)}/{len(code_rows)}")
    tagged = page.locator(".crit .orig-tag").count()
    check("en: the reviewer's own words are marked as the Hebrew original", tagged >= 1 and tagged <= len(judge_rows) + 1,
          f"{tagged} tags, {len(judge_rows)} judge rows")
    shot(page, "3-document-en", full=True)


# ---------------------------------------------------------------- 4. the assistant
def assistant(page: Page, api: httpx.Client) -> None:
    # a Hebrew session's answer, saved before this English one
    api.post(f"/api/cases/{S.CORRECTION}/agent/messages", json={"text": "מה חסר לי?", "channel": "text"}).raise_for_status()
    page.goto(BASE + "/customer?lang=en")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    page.locator("[data-testid=fab]").click()
    expect(page.locator("[data-testid=chat-input]")).to_be_visible(timeout=10000)
    page.wait_for_timeout(600)
    check("en: an earlier Hebrew answer is marked 'Original (Hebrew)'",
          page.locator(".bubble.assistant [data-testid=turn-original]").count() >= 1)
    before = page.locator(".bubble.assistant").count()
    with Requests(page) as reqs:
        page.locator("[data-testid=chat-input]").fill("What am I missing?")
        page.locator("[data-testid=chat-send]").click()
        page.wait_for_function("n => document.querySelectorAll('.bubble.assistant').length > n", arg=before, timeout=30000)
        page.wait_for_timeout(600)
    answer = page.locator(".bubble.assistant .bubble-text").last.inner_text()
    check("en: the assistant answers in English (no model: from case data)", not HEBREW.search(answer)
          and answer.endswith("the smart assistant isn't available right now.)"), answer[:160])
    posted = [h for m, u, h in reqs.items if m == "POST" and u.endswith("/agent/messages")]
    check("en: the question was sent with the English language", posted == ["en"], str(posted))
    left = hebrew_left(page)
    check("en: no unmarked Hebrew in the assistant sheet", not left, str(left[:4]))
    shot(page, "4-assistant-en")
    page.goto(BASE + "/customer?lang=he")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    page.locator("[data-testid=fab]").click()
    expect(page.locator("[data-testid=chat-input]")).to_be_visible(timeout=10000)
    page.wait_for_timeout(600)
    marked = page.locator(".bubble.assistant", has=page.locator("[data-testid=turn-original]"))
    check("he: the English answer is marked 'נכתב באנגלית' and read left to right",
          marked.count() >= 1 and marked.last.locator(".bubble-text").get_attribute("dir") == "ltr")
    shot(page, "4-assistant-he")
    page.keyboard.press("Escape")


# ---------------------------------------------------------------- 5. the conversational application
def application(page: Page, api: httpx.Client) -> None:
    s = S.SCRIPT["en"]
    S.prepare(page, BASE, "he", S.CORRECTION)
    page.evaluate("() => localStorage.removeItem('mz.onboarding.draft.v2')")
    page.goto(BASE + "/customer/apply")
    expect(page.locator("[data-testid=cv2-pending]")).to_have_count(1, timeout=20000)
    reply(page, '"personal"')
    check("he: the conversation starts in Hebrew", HEBREW.search(last_assistant(page)) is not None, last_assistant(page)[:60])
    draft = page.locator("[data-testid=apply-v2]").get_attribute("data-draft")
    count = page.locator("[data-testid=cv2-msg]").count()
    page.locator("[data-testid=cv2-input]").fill("Michal")
    with Requests(page) as reqs:
        switch(page)
    check("switch mid-conversation: same draft, same messages, the unsent text kept",
          page.locator("[data-testid=apply-v2]").get_attribute("data-draft") == draft
          and page.locator("[data-testid=cv2-msg]").count() == count
          and page.locator("[data-testid=cv2-input]").input_value() == "Michal")
    check("switch mid-conversation: no write request, no model call", not [r for r in reqs.items if r[0] != "GET"], str(reqs.items))
    check("en: the conversation so far is shown in English", last_assistant(page).startswith("A personal loan"), last_assistant(page)[:80])
    shot(page, "5-apply-switched-en")
    say(page, s["name"])
    check("en: typed English is understood (name)", last_assistant(page).startswith("Nice to meet you, Michal."), last_assistant(page)[:80])
    say(page, s["id"])
    say(page, s["purpose"])
    expect(page.locator("[data-testid=ls-confirm]")).to_be_visible(timeout=15000)
    check("en: the simulator is English", page.locator("[data-testid=ls-confirm]").inner_text().strip() == "This is my scenario"
          and not hebrew_left(page), str(hebrew_left(page)[:3]))
    shot(page, "5-apply-simulator-en")
    page.locator("[data-testid=ls-asset-unknown]").click()
    before = cv2_items(page)
    page.locator("[data-testid=ls-confirm]").click()
    cv2_settle(page, before)
    check("en: the confirmed scenario is worded in English", "car loan: an estimated monthly repayment" in last_assistant(page),
          last_assistant(page)[:100])
    reply(page, '["salaried"]')
    say(page, s["net"])
    check("en: '12,000 net' is read as the income", "Thanks, I noted about ₪12,000 net a month." in last_assistant(page),
          last_assistant(page)[:100])
    say(page, s["solo"])
    expect(page.locator("[data-testid=cv2-summary]")).to_be_visible(timeout=15000)
    page.wait_for_timeout(800)
    lines = page.locator("[data-testid=cv2-line]")
    summary = {lines.nth(i).get_attribute("data-question"): lines.nth(i).inner_text() for i in range(lines.count())}
    check("en: the summary is English and records what was typed", summary.get("name", "").startswith("Name\nMichal Barak")
          and "₪12,000" in summary.get("net", "") and "Personal loan" in summary.get("loan_type", ""), str(summary)[:200])
    left = hebrew_left(page)
    check("en: no Hebrew left on the summary", not left, str(left[:4]))
    shot(page, "5-apply-summary-en", full=True)
    page.locator("[data-testid=cv2-confirm]").click()
    expect(page.locator("[data-testid=cv2-handoff]")).to_be_visible(timeout=20000)
    check("en: the application opens and the handoff is English", page.locator("[data-testid=cv2-handoff]").inner_text().startswith("Michal, your application is ready"),
          page.locator("[data-testid=cv2-handoff]").inner_text()[:80])
    shot(page, "5-apply-handoff-en")


def history(page: Page) -> None:
    """A conversation saved before English existed (no language header at all) opened in the English app."""
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post("/api/session/demo/customer", json={"case_id": S.CORRECTION}).raise_for_status()
    d = c.post("/api/demo/onboarding/v2").json()
    c.post(f"/api/demo/onboarding/{d['draft_id']}/v2/turn", json={"question_id": "loan_type", "value": "personal",
                                                                  "label_he": "הלוואה פרטית", "turn_id": "H-1"}).raise_for_status()
    page.goto(BASE + "/customer/stages")
    page.evaluate("id => { localStorage.setItem('mz.onboarding.draft.v2', id); localStorage.setItem('mz.lang', 'en'); }", d["draft_id"])
    page.goto(BASE + "/customer/apply")
    expect(page.locator("[data-testid=cv2-pending]")).to_have_count(1, timeout=20000)
    page.wait_for_timeout(500)
    msgs = page.locator("[data-testid=cv2-msg]")
    check("history: messages saved before English show in Hebrew, as written",
          all(HEBREW.search(msgs.nth(i).inner_text()) for i in range(msgs.count())), str(msgs.count()))
    live = page.locator("[data-testid=cv2-current-question]")
    check("history: the open question is asked again, live, in English", live.count() == 1
          and live.inner_text().startswith("What's your name?"), live.inner_text() if live.count() else "")
    shot(page, "5-history-en")
    say(page, "Dana Raz")
    check("history: a 'Continuing in English' marker separates the languages",
          page.locator("[data-testid=cv2-lang-divider]").count() == 1
          and page.locator("[data-testid=cv2-lang-divider]").inner_text() == "Continuing in English")
    check("history: the earlier Hebrew messages are unchanged", HEBREW.search(msgs.nth(0).inner_text()) is not None)
    shot(page, "5-history-divider-en")
    switch(page)
    page.wait_for_timeout(400)
    user = page.locator("[data-testid=cv2-msg][data-kind=user]").last
    check("history in Hebrew: every assistant message in Hebrew, no divider, the customer's English read left to right",
          page.locator("[data-testid=cv2-lang-divider]").count() == 0 and user.inner_text() == "Dana Raz"
          and user.get_attribute("dir") == "ltr" and HEBREW.search(last_assistant(page)) is not None,
          f"{page.locator('[data-testid=cv2-lang-divider]').count()} / {user.get_attribute('dir')} / {last_assistant(page)[:40]}")
    shot(page, "5-history-he")


def main() -> None:
    print(f"seeding REPLAY cases through {BASE}…", flush=True)
    S.seed(BASE)
    api = httpx.Client(base_url=BASE, timeout=60)
    api.post("/api/session/demo/customer", json={"case_id": S.CORRECTION}).raise_for_status()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport=S.MOBILE, device_scale_factor=2, locale="he-IL")
        page = ctx.new_page()
        for step in (lambda: main_page(page, api), lambda: layout(page), lambda: document_review(page, api),
                     lambda: assistant(page, api), lambda: application(page, api), lambda: history(page)):
            try:
                step()
            except Exception as exc:                                  # a broken step is a failure, the others still run
                check(f"step {getattr(step, '__name__', '?')} ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
                shot(page, "error")
        browser.close()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed (REPLAY)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
