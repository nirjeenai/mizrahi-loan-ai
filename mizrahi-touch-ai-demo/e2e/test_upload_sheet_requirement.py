"""Documents screen and upload sheet: the requirement accordion, and the sheet always opening on the requirement the customer clicked — also while the case snapshot is still
loading, after a quick switch between requirements, and from the document page's replacement action. Real Chrome on
an isolated REPLAY stack (zero Gemini calls); resets the QA case 005 only.

The race this guards: the document page renders its replacement button from its own document fetch, independently of
the case snapshot the sheet reads its requirements from. The test makes that ordering certain by holding back the
snapshot response (Playwright route), instead of hoping for an unlucky timing.

    PRESENTER_BASE=http://127.0.0.1:5846 REPLAY_API=http://127.0.0.1:8798 backend/.venv/bin/python e2e/test_upload_sheet_requirement.py
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, Route, expect, sync_playwright

BASE = os.environ.get("PRESENTER_BASE", "http://127.0.0.1:5846")
API = os.environ.get("REPLAY_API", "http://127.0.0.1:8798")
ROOT = Path(__file__).resolve().parent
CASE, ID, BANK, PURPOSE = "DEMO-MTZ-2026-005", "ID_CARD:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def seed_expired_id() -> str:
    c = httpx.Client(base_url=API, timeout=60)
    c.post("/api/session/demo/customer", json={"case_id": CASE}).raise_for_status()
    c.post(f"/api/cases/{CASE}/reset").raise_for_status()
    p = ROOT.parent / "fixtures" / "presenter" / "loan_set" / "id_card_ido_EXPIRED.pdf"
    with p.open("rb") as fh:
        doc = c.post(f"/api/cases/{CASE}/documents", data={"requirement_code": ID, "borrower_id": "BRW-A"},
                     files={"file": (p.name, fh, "application/pdf")}).json()["document"]["document_id"]
    for _ in range(200):
        s = c.get(f"/api/cases/{CASE}").json()
        if not s["readiness"]["pending_jobs"] and s["readiness"]["counts"]["processing"] == 0:
            return doc
        time.sleep(0.5)
    raise TimeoutError("case did not settle")


def sheet_state(page: Page) -> tuple[str | None, int]:
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible(timeout=15000)
    kind = sheet.locator("[data-testid=upload-doc-type]")
    expect(kind).to_have_attribute("data-requirement", re.compile(".+"), timeout=15000)
    return kind.get_attribute("data-requirement"), sheet.locator("[data-testid=upload-replaces]").count()


def release(page: Page, pattern: re.Pattern, held: list[Route]) -> None:
    """Let the held-back snapshot responses through, then stop holding."""
    for route in held:
        try:
            route.continue_()
        except Exception:                       # already answered by the page's own retry
            pass
    held.clear()
    page.unroute(pattern)


def accordion(page: Page) -> None:
    """Documents screen: the list itself is open, each requirement row starts collapsed and toggles on its own, and in
    the two-applicant case each applicant's row uploads for that applicant."""
    page.goto(f"{BASE}/customer")
    page.evaluate("localStorage.setItem('mz.case', 'DEMO-MTZ-2026-003')")
    page.goto(f"{BASE}/customer/documents")
    expect(page.locator("[data-testid='req-PAYSLIPS:BRW-B']")).to_be_visible(timeout=15000)
    heads = page.locator("[data-testid=required-docs] .dl-row .dl-head")
    states = [heads.nth(i).get_attribute("aria-expanded") for i in range(heads.count())]
    check("documents: the required-documents list is open and every requirement row starts collapsed",
          page.locator("[data-testid=required-docs] .dl-top").get_attribute("aria-expanded") == "true"
          and states and all(s == "false" for s in states), str(states))
    a, b = page.locator("[data-testid='req-ID_CARD:BRW-A'] .dl-head"), page.locator("[data-testid='req-ID_CARD:BRW-B'] .dl-head")
    a.click()
    one = (a.get_attribute("aria-expanded"), b.get_attribute("aria-expanded"))
    b.click()
    a.click()
    two = (a.get_attribute("aria-expanded"), b.get_attribute("aria-expanded"))
    check("documents: rows toggle independently", one == ("true", "false") and two == ("false", "true"), f"{one} → {two}")
    page.locator("[data-testid='upload-ID_CARD:BRW-B']").click()
    requirement, _ = sheet_state(page)
    who = page.locator("[data-testid=upload-sheet]").inner_text()
    check("documents: Noa's ID-card row uploads for Noa's requirement", requirement == "ID_CARD:BRW-B" and "נועה" in who, str(requirement))
    page.locator("[data-testid=upload-sheet] button[aria-label='סגירה']").click()


def mobile(page: Page) -> None:
    page.goto(f"{BASE}/customer")
    page.evaluate("localStorage.setItem('mz.case', 'DEMO-MTZ-2026-003')")
    page.goto(f"{BASE}/customer/documents")
    expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).to_be_visible(timeout=15000)
    page.locator("[data-testid='req-PAYSLIPS:BRW-A'] .dl-head").click()
    button = page.locator("[data-testid=upload-BRW-A]").first
    box = button.bounding_box() or {"x": -1, "width": 0}
    wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    page.screenshot(path=str(ROOT / "artifacts" / "closeout" / "mobile-documents.png"))
    check("mobile 390×844: no sideways scroll; an opened row's upload button is on screen",
          wide <= 0 and 0 <= box["x"] and box["x"] + box["width"] <= 390, f"overflow={wide}")


def run(page: Page, doc: str) -> None:
    accordion(page)
    page.goto(f"{BASE}/customer")
    page.evaluate(f"localStorage.setItem('mz.case', '{CASE}')")

    # 1. the replacement action clicked before the case snapshot has arrived
    held: list[Route] = []
    snapshot = re.compile(rf"/api/cases/{CASE}$")
    page.route(snapshot, lambda route: held.append(route))
    page.goto(f"{BASE}/customer/documents/{doc}")
    button = page.locator("[data-testid=document-replace]")
    expect(button).to_be_visible(timeout=15000)
    first_click_before_snapshot = bool(held)
    button.click()
    release(page, snapshot, held)
    requirement, replaces = sheet_state(page)
    check("replacement clicked while the case snapshot is still loading → the ID-card upload that replaces this file",
          first_click_before_snapshot and requirement == ID and replaces == 1,
          f"snapshot held={first_click_before_snapshot} requirement={requirement} replaces={replaces}")
    page.locator("[data-testid=upload-sheet] button[aria-label='סגירה']").click()

    # 2. a quick switch: one requirement's upload, closed at once, then another's
    page.goto(f"{BASE}/customer/documents")
    for code in (BANK, PURPOSE):
        head = page.locator(f"[data-testid='req-{code}'] .dl-head")
        if head.get_attribute("aria-expanded") != "true":
            head.click()
    page.locator(f"[data-testid='upload-{BANK}']").click()
    page.locator("[data-testid=upload-sheet] button[aria-label='סגירה']").click()
    page.locator(f"[data-testid='upload-{PURPOSE}']").click()
    requirement, _ = sheet_state(page)
    check("a quick switch from one requirement to another opens the second one", requirement == PURPOSE, str(requirement))
    page.locator("[data-testid=upload-sheet] button[aria-label='סגירה']").click()

    # 3. a contextual deep link (?upload=) while the snapshot is held back
    held.clear()
    page.route(snapshot, lambda route: held.append(route))
    page.goto(f"{BASE}/customer/documents?upload={BANK}")
    page.wait_for_timeout(400)
    release(page, snapshot, held)
    requirement, _ = sheet_state(page)
    check("a contextual upload link opens the requirement it names, whatever the load order", requirement == BANK, str(requirement))


def main() -> int:
    doc = seed_expired_id()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL").new_page()
        phone = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True, has_touch=True).new_page()
        try:
            run(page, doc)
            mobile(phone)
        except Exception as exc:
            check("test ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
            page.screenshot(path=str(ROOT / "artifacts" / "upload-sheet-failure.png"))
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} upload-sheet requirement checks passed · REPLAY")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
