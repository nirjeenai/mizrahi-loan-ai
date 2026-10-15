"""The banker's case selector (the same case bar in V1, V2 and V3), in a real Chrome on an isolated stack (no Gemini):
the main list is the six official profiles (UC-01…06) and every customer-created application, most recent activity
first; every other prepared case is under a collapsed "תרחישי בדיקה נוספים". A new chat application and a meaningful
update move a case to the top of its list without a reload; a hidden case opened by a link (as the presenter does) is
shown as the selected case, with its section open. /banker without a case opens the remembered case if it still exists,
else the most recently active main-list case (a default that is not remembered); a case in the URL always wins.

    cd backend && GEMINI_API_KEY= GEMINI_MAX_CALLS_PER_HOUR=0 ONBOARDING_LLM=0 VISIONTRACE_MCP_KEY= \\
        DATA_DIR=../e2e/artifacts/case-selector/data ./.venv/bin/python -m uvicorn app.main:app --port 8812   # fresh data
    node e2e/serve_frontend.mjs e2e/artifacts/case-selector/web 5862 http://127.0.0.1:8812
    SELECTOR_BASE=http://127.0.0.1:5862 backend/.venv/bin/python e2e/check_banker_case_selector.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

import isolation

BASE = os.environ.get("SELECTOR_BASE", "http://127.0.0.1:5862")
isolation.require_isolated(BASE)
OUT = Path(__file__).resolve().parent / "artifacts" / "case-selector"
OUT.mkdir(parents=True, exist_ok=True)
OFFICIAL = {f"DEMO-MTZ-2026-{n}" for n in range(101, 107)}
LEGACY = {f"DEMO-MTZ-2026-{n:03d}" for n in range(1, 12)}
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def ids(page: Page, testid: str) -> list[str]:
    loc = page.locator(f"[data-testid={testid}] .case-pop-row")
    return loc.evaluate_all("els => els.map(e => e.getAttribute('data-case'))") if page.locator(f"[data-testid={testid}]").count() else []


def open_selector(page: Page) -> None:
    if page.locator(".case-pop").count():
        page.locator("[data-testid=case-switch]").click()
    page.locator("[data-testid=case-switch]").click()
    expect(page.locator("[data-testid=case-main] .case-pop-row").first).to_be_visible(timeout=10000)
    page.wait_for_timeout(500)                 # the list is fetched again on every open


def close_selector(page: Page) -> None:
    if page.locator(".case-pop").count():
        page.locator("[data-testid=case-switch]").click()


def chat_application(api: httpx.Client, name: str) -> str:
    draft = api.post("/api/demo/onboarding/v2").json()["draft_id"]
    for body in ({"question_id": "loan_type", "value": "personal"}, {"text": name}, {"text": "DEMO-ID-311"},
                 {"text": "אני שכירה, מרוויחה 15 אלף נטו, רוצה הלוואה של 70 אלף לרכב לחמש שנים."}, {"text": "לא, רק אני"}):
        api.post(f"/api/demo/onboarding/{draft}/v2/turn", json=body).raise_for_status()
    out = api.post(f"/api/demo/onboarding/{draft}/v2/confirm").json()
    assert out["created"], out
    return out["case_id"]


def opened(page: Page, path: str = "/banker") -> str:
    """The case the console settles on: the URL's case once the workspace of that case is shown."""
    page.goto(f"{BASE}{path}")
    expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)
    return page.evaluate("new URLSearchParams(location.search).get('case')")


def default_selection(browser, note, order, numbers) -> None:
    """/banker without a case: the remembered case if it still exists, else the most recently active main-list case;
    that default is never remembered, an explicit URL always wins."""
    top_main = lambda: next(c for c in order() if c in OFFICIAL or c.startswith("DEMO-LN-"))  # noqa: E731
    fresh = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL")
    page = fresh.new_page()
    first = opened(page)
    check("first visit (nothing chosen): opens the most recently active main-list case, not 001",
          first == top_main() and first not in LEGACY, f"{first} vs {top_main()}")
    number = next(r["display_number"] for r in numbers() if r["case_id"] == first)
    check("…and the case bar shows it", number in page.locator("[data-testid=case-switch]").inner_text(), number)
    same = True
    for v, root in (("ui-v2", "bi-brief"), ("ui-v3", "cc-root"), ("ui-v1", "review-queue")):
        page.locator(f"[data-testid={v}]").click()
        expect(page.locator(f"[data-testid={root}]")).to_be_visible(timeout=20000)
        same = same and f"case={first}" in page.url
    check("V1, V2 and V3 keep the default case", same)

    note("DEMO-MTZ-2026-106")
    again = opened(page)
    check("the default is not remembered: after an update elsewhere, the next visit opens the new top case",
          again == "DEMO-MTZ-2026-106", again)
    check("an explicit case in the URL is respected", opened(page, "/banker?case=DEMO-MTZ-2026-005") == "DEMO-MTZ-2026-005")

    open_selector(page)
    page.locator("[data-testid=case-main] .case-pop-row[data-case='DEMO-MTZ-2026-103']").click()
    expect(page.locator("[data-testid=case-switch]")).to_contain_text("438839103", timeout=15000)
    note("DEMO-MTZ-2026-101")
    check("a chosen case is remembered on return, even after other cases were updated", opened(page) == "DEMO-MTZ-2026-103")
    page.evaluate("localStorage.setItem('mz.banker.case', 'DEMO-LN-9999-GONE')")
    gone = opened(page)
    check("a remembered case that no longer exists falls back to the top of the main list", gone == "DEMO-MTZ-2026-101", gone)
    fresh.close()


def main() -> int:
    staff = httpx.Client(base_url=BASE, timeout=30)
    staff.post("/api/session/demo/staff", json={}).raise_for_status()
    note = lambda cid: staff.post(f"/api/banker/cases/{cid}/notes", json={"text": "עדכון לבדיקת הסדר"}).raise_for_status()  # noqa: E731
    order = lambda: [r["case_id"] for r in staff.get("/api/banker/cases").json()]  # noqa: E731
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="he-IL")
        page.goto(f"{BASE}/banker?case=DEMO-MTZ-2026-101")
        expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)

        open_selector(page)
        main_ids = ids(page, "case-main")
        check("main list: exactly the six official profiles (plus any customer application)",
              OFFICIAL <= set(main_ids) and all(c in OFFICIAL or c.startswith("DEMO-LN-") for c in main_ids), str(main_ids))
        check("main list keeps the server's recent-activity order",
              main_ids == [c for c in order() if c in set(main_ids)], str(main_ids))
        check("'תרחישי בדיקה נוספים' is collapsed by default",
              page.locator("[data-testid=case-more]").count() == 0
              and page.locator("[data-testid=case-more-toggle]").get_attribute("aria-expanded") == "false")
        page.screenshot(path=str(OUT / "01-default.png"))
        page.locator("[data-testid=case-more-toggle]").click()
        more = ids(page, "case-more")
        check("expanded: every other case (001–011) is there, none of the main list", set(more) == LEGACY, str(more))
        page.screenshot(path=str(OUT / "02-expanded.png"))
        close_selector(page)

        note("DEMO-MTZ-2026-104")
        open_selector(page)
        check("an update to an official profile moves it to the top (no reload)", ids(page, "case-main")[0] == "DEMO-MTZ-2026-104",
              str(ids(page, "case-main")[:3]))
        close_selector(page)

        new = chat_application(httpx.Client(base_url=BASE, timeout=30), "דנה שחר")
        open_selector(page)
        top = page.locator("[data-testid=case-main] .case-pop-row").first
        check("a newly confirmed chat application appears first in the main list (no reload, no restart)",
              top.get_attribute("data-case") == new and "דנה שחר" in top.inner_text(), top.inner_text()[:80])
        page.screenshot(path=str(OUT / "03-new-chat-case.png"))
        close_selector(page)

        note("DEMO-MTZ-2026-102")
        open_selector(page)
        check("an update to another official profile moves it above the chat application",
              ids(page, "case-main")[:2] == ["DEMO-MTZ-2026-102", new], str(ids(page, "case-main")[:3]))
        close_selector(page)

        note("DEMO-MTZ-2026-005")
        open_selector(page)
        check("an update to a hidden case keeps it out of the main list", "DEMO-MTZ-2026-005" not in ids(page, "case-main")
              and ids(page, "case-main")[0] == "DEMO-MTZ-2026-102")
        page.locator("[data-testid=case-more-toggle]").click()
        check("…and puts it first in 'תרחישי בדיקה נוספים'", ids(page, "case-more")[0] == "DEMO-MTZ-2026-005",
              str(ids(page, "case-more")[:3]))
        page.locator("[data-testid=case-more] .case-pop-row[data-case='DEMO-MTZ-2026-003']").click()
        expect(page.locator("[data-testid=case-switch]")).to_contain_text("438838999", timeout=15000)
        check("a hidden case chosen from the expanded section opens", "case=DEMO-MTZ-2026-003" in page.url)

        # the presenter opens a case with /banker?case=… in a new tab
        page.goto(f"{BASE}/banker?case=DEMO-MTZ-2026-004")
        expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
        bar = page.locator("[data-testid=case-switch]")
        check("a hidden case opened by a link is the selected case in the case bar", "438839004" in bar.inner_text(), bar.inner_text())
        open_selector(page)
        sel = page.locator("[data-testid=case-more] .case-pop-row[aria-selected=true]")
        check("…and the selector opens with its section expanded and the case marked, scrolled into view",
              sel.count() == 1 and sel.get_attribute("data-case") == "DEMO-MTZ-2026-004" and sel.evaluate(
                  "e => { const r = e.getBoundingClientRect(), p = e.closest('.case-pop').getBoundingClientRect();"
                  " return r.top >= p.top && r.bottom <= p.bottom; }"))
        page.screenshot(path=str(OUT / "04-hidden-case-by-link.png"))
        close_selector(page)
        same = True
        for v, root in (("ui-v2", "bi-brief"), ("ui-v3", "cc-root"), ("ui-v1", "review-queue")):
            page.locator(f"[data-testid={v}]").click()
            expect(page.locator(f"[data-testid={root}]")).to_be_visible(timeout=20000)
            same = same and "438839004" in bar.inner_text()
        check("V1, V2 and V3 keep the hidden case selected", same)
        default_selection(browser, note, order, lambda: staff.get("/api/banker/cases").json())
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} case-selector checks passed · isolated stack, no Gemini")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
