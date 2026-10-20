"""The banker case desk (the console's default view, CaseDesk.tsx) in a real Chrome on an isolated stack (no Gemini).

Overview: the four-step pipeline, one next step chosen from the case's state, the work grouped by who holds it.
Journeys: request every missing document in one sheet (edit a message, leave one out, preview, save); open the review,
accept a document, go to the next item, move with J/K and return with Esc; a case-level finding with its income
comparison; the classic V1 review, V2 and V3 one click away; Hebrew and English; 1440, 1100 and 390 px without
horizontal scrolling. It writes customer requests and one acceptance, so it needs an isolated DATA_DIR. Cases are
found through the API: a case with nothing uploaded for the request sheet, a case with documents awaiting a decision
for the review, a case with a case-level finding. A journey without such a case is reported as SKIPPED, not passed.

    cd backend && GEMINI_API_KEY= GEMINI_MAX_CALLS_PER_HOUR=0 DATA_DIR=../e2e/artifacts/case-desk/data \\
        ./.venv/bin/python -m uvicorn app.main:app --port 8813        # reviewed documents need a REPLAY-populated DATA_DIR
    node e2e/serve_frontend.mjs e2e/artifacts/case-desk/web 5863 http://127.0.0.1:8813
    CASEDESK_BASE=http://127.0.0.1:5863 backend/.venv/bin/python e2e/check_case_desk.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

import isolation

BASE = os.environ.get("CASEDESK_BASE", "http://127.0.0.1:5863")
isolation.require_isolated(BASE)
OUT = Path(__file__).resolve().parent / "artifacts" / "case-desk"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list[dict] = []
OVERFLOW = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"


def check(name: str, ok: bool | None, detail: str = "") -> None:
    status = "SKIPPED" if ok is None else "PASS" if ok else "FAIL"
    RESULTS.append({"check": name, "status": status, "detail": detail})
    print(f"{status:7} {name}" + (f" — {detail}" if detail else ""))


def shot(page: Page, name: str) -> None:
    page.wait_for_timeout(450)                      # let the entrance motion settle
    page.screenshot(path=str(OUT / f"{name}.png"))


def find_cases() -> dict[str, str | None]:
    staff = httpx.Client(base_url=BASE, timeout=30)
    staff.post("/api/session/demo/staff", json={}).raise_for_status()
    found: dict[str, str | None] = {"empty": None, "decide": None, "finding": None}
    for row in staff.get("/api/banker/cases").json():
        q = row.get("queue") or {}
        ws = None
        if not found["empty"] and q.get("missing") and not any(q.get(k) for k in ("decide", "judgment", "correction", "done")):
            ws = staff.get(f"/api/banker/cases/{row['case_id']}/workspace").json()
            if ws["summary"]["documents"] == 0 and sum(1 for i in ws["items"] if i["kind"] == "missing" and not i.get("open_request")
                                                       and i["allowed_actions"]) >= 2:
                found["empty"] = row["case_id"]
        if not found["decide"] and (q.get("decide") or 0) >= 2:
            found["decide"] = row["case_id"]
        if not found["finding"] and q.get("judgment"):
            found["finding"] = row["case_id"]
    return found


def overview(page: Page, case: str) -> None:
    page.goto(f"{BASE}/banker?case={case}")
    expect(page.locator("[data-testid=next-step]")).to_be_visible(timeout=20000)


def request_sheet(page: Page, case: str | None) -> None:
    if not case:
        check("request sheet: a case with nothing uploaded", None, "no such case in this DATA_DIR")
        return
    overview(page, case)
    check("overview: four pipeline steps", page.locator("[data-testid=case-progress] [data-step]").count() == 4)
    check("overview: the next step offers the batch request", page.locator("[data-testid=next-step] [data-testid=compose-requests]").count() == 1,
          page.locator(".cd-next-title").inner_text())
    stack = page.locator("[data-testid=work-stack]")
    check("overview: the next step shows the pile of missing documents", stack.count() == 1 and stack.locator(".cd-paper").count() >= 2,
          f"{stack.get_attribute('data-count') if stack.count() else 0} items")
    months = page.locator("[data-testid=months-row]")
    check("overview: a borrower's missing payslip months are one row with a chip per month",
          months.count() >= 1 and months.first.locator("[data-testid=queue-item]").count() >= 2, f"{months.count()} rows")
    shot(page, "01-overview-nothing-uploaded")
    page.locator("[data-testid=next-step] [data-testid=compose-requests]").click()
    sheet = page.locator("[data-testid=request-sheet]")
    expect(sheet).to_be_visible()
    picks = sheet.locator("[data-testid=request-pick]")
    n = picks.count()
    check("sheet: every requestable missing item, all chosen", n >= 2 and all(picks.nth(i).is_checked() for i in range(n)), f"{n} items")
    shot(page, "02-request-sheet")
    picks.nth(n - 1).uncheck()
    sheet.locator(".cd-pick .cd-link").first.click()
    box = sheet.locator(".cd-pick-edit textarea")
    box.fill(box.input_value() + " תודה.")
    sheet.locator("[data-testid=request-preview]").click()
    cards = sheet.locator(".cd-previews .req-preview-card")
    check("preview: one customer card per chosen item, in Hebrew, with the edited text",
          cards.count() == n - 1 and "תודה." in cards.first.inner_text(), f"{cards.count()} cards")
    shot(page, "03-request-preview")
    sheet.locator("[data-testid=send-requests]").click()
    toast = page.locator("[data-testid=desk-toast]")
    expect(toast).to_be_visible(timeout=20000)
    check("saved: the toast names the count and that nothing was sent by SMS or e-mail", str(n - 1) in toast.inner_text() and "SMS" in toast.inner_text(),
          toast.inner_text())
    expect(page.locator("[data-testid=request-sheet]")).to_have_count(0)
    page.wait_for_timeout(1200)
    sent = page.locator("[data-testid=queue-item][data-kind=missing][data-requested=true]").count()
    check("rows: the requested items read 'request sent'", sent == n - 1, f"{sent} rows")
    check("next step: the one item left out is still offered", "1" in page.locator(".cd-next-title").inner_text() or "אחד" in page.locator(".cd-next-title").inner_text(),
          page.locator(".cd-next-title").inner_text())
    shot(page, "04-after-requests")


def review(page: Page, case: str | None) -> None:
    if not case:
        check("review: a case with documents awaiting a decision", None, "no such case in this DATA_DIR")
        return
    overview(page, case)
    page.locator("[data-testid=next-step-primary]").click()
    expect(page.locator("[data-testid=evidence-pane] .ev-title")).to_be_visible(timeout=20000)
    check("review: the document beside the decision, the navigator docked in the case bar",
          page.locator(".cd-canvas").count() == 1 and page.locator(".cd-inspector [data-testid=decision-actions]").count() == 1
          and page.locator(".case-bar #ax-bar-slot [data-testid=nav-dot]").count() >= 2)
    opened = page.url.split("item=")[-1].replace("%3A", ":")
    dots_before = page.locator("[data-testid=nav-dot]").evaluate_all("ds => ds.map(d => d.dataset.itemId)")
    shot(page, "05-review-document")
    first = page.url
    page.locator("[data-testid=action-accept]").click()
    form = page.locator("[data-testid=accept-form]")
    expect(form).to_be_visible()
    if page.locator("[data-testid=accept-rationale]").count():
        page.locator("[data-testid=accept-rationale]").fill("נבדק מול המסמך המקורי (בדיקת דסק)")
    page.locator("[data-testid=confirm-accept]").click()
    expect(page.locator("[data-testid=decision-success]")).to_be_visible(timeout=20000)
    shot(page, "06-accepted")
    page.wait_for_timeout(1500)                                           # the workspace refresh after the decision
    dots_after = page.locator("[data-testid=nav-dot]").evaluate_all("ds => ds.map(d => d.dataset.itemId)")
    dot = page.locator(f"[data-testid=nav-dot][data-item-id='{opened}']")
    check("after a decision: the item keeps its place in the navigator and its dot turns green",
          dots_after[:len(dots_before)] == dots_before and "t-done" in (dot.get_attribute("class") or ""), opened)
    page.locator("[data-testid=next-item]").click()
    page.wait_for_timeout(600)
    check("after a decision: 'next item' opens another item", page.url != first)
    before = page.url
    page.keyboard.press("j"); page.wait_for_timeout(300)
    check("keyboard: J moves to the next item", page.url != before)
    page.keyboard.press("k"); page.wait_for_timeout(300)
    check("keyboard: K moves back", page.url == before)
    page.keyboard.press("Escape")
    expect(page.locator("[data-testid=next-step]")).to_be_visible()
    check("keyboard: Esc returns to the overview; the accepted document is under Done",
          page.locator("[data-testid=desk-section-done]").count() == 1 and "item=" not in page.url)


def finding(page: Page, case: str | None) -> None:
    if not case:
        check("finding: a case with a case-level finding", None, "no such case in this DATA_DIR")
        return
    overview(page, case)
    page.locator("[data-testid=queue-item][data-kind=case_finding]").first.click()
    expect(page.locator("[data-testid=income-table]")).to_be_visible(timeout=20000)
    check("finding: the income comparison and the finding's decisions",
          page.locator("[data-testid=decision-panel] [data-testid=decision-actions]").count() == 1)
    shot(page, "07-finding")


def views(page: Page, case: str) -> None:
    overview(page, case)
    page.locator("[data-testid=more-views]").click()
    page.locator("[data-testid=view-classic]").click()
    expect(page.locator(".desk-grid")).to_be_visible(timeout=20000)
    check("views: the classic V1 review is in the menu", True)
    page.locator("[data-testid=ui-v3]").click()
    expect(page.locator("[data-testid=cc-root]")).to_be_visible(timeout=20000)
    page.locator("[data-testid=ui-v1]").click()
    expect(page.locator("[data-testid=case-desk]")).to_be_visible(timeout=20000)
    check("views: V3 and back to the case desk", True)


def layouts(browser, cases: list[str]) -> None:
    for lang in ("he", "en"):
        for width in (1440, 1100, 390):
            ctx = browser.new_context(viewport={"width": width, "height": 900 if width > 700 else 844})
            page = ctx.new_page()
            for case in cases:
                page.goto(f"{BASE}/banker?case={case}&lang={lang}")
                expect(page.locator("[data-testid=next-step]")).to_be_visible(timeout=20000)
                over = page.evaluate(OVERFLOW)
                check(f"layout {lang} {width}px {case}: no horizontal scrolling", over <= 1, f"{over}px")
                first = page.locator("[data-testid=queue-item]").first
                if first.count():
                    first.click()
                    expect(page.locator("[data-testid=decision-panel]")).to_be_visible(timeout=20000)
                    page.wait_for_timeout(400)
                    over = page.evaluate(OVERFLOW)
                    check(f"layout {lang} {width}px {case}: review without horizontal scrolling", over <= 1, f"{over}px")
                    if case == cases[0]:
                        shot(page, f"10-review-{lang}-{width}")
                    page.keyboard.press("Escape")
            if lang == "he" or width == 1440:
                page.goto(f"{BASE}/banker?case={cases[0]}&lang={lang}")
                expect(page.locator("[data-testid=next-step]")).to_be_visible(timeout=20000)
                shot(page, f"09-overview-{lang}-{width}")
            ctx.close()


def main() -> int:
    cases = find_cases()
    print("cases:", cases)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="he-IL")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        request_sheet(page, cases["empty"])
        review(page, cases["decide"])
        finding(page, cases["finding"])
        views(page, cases["decide"] or cases["empty"] or "DEMO-MTZ-2026-001")
        check("no page errors", not errors, "; ".join(errors[:3]))
        layouts(browser, [c for c in (cases["finding"], cases["empty"]) if c] or ["DEMO-MTZ-2026-001"])
        browser.close()
    (OUT / "results.json").write_text(json.dumps({"base": BASE, "cases": cases, "results": RESULTS}, ensure_ascii=False, indent=2))
    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    print(f"\n{sum(r['status'] == 'PASS' for r in RESULTS)} passed · {len(failed)} failed · "
          f"{sum(r['status'] == 'SKIPPED' for r in RESULTS)} skipped — {OUT / 'results.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
