"""Rounds 1–2 audit: walk every screen of Mizrahi #2 in Chrome (desktop and mobile) over seeded loan states, take a
screenshot of each and record what is on it — visible upload entry points, mortgage wording, headings. REPLAY stack only.

    AUDIT_BASE=http://127.0.0.1:5843 backend/.venv/bin/python e2e/audit_explore.py
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

BASE = os.environ.get("AUDIT_BASE", "http://127.0.0.1:5843")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "audit" / os.environ.get("AUDIT_TAG", "before")
FIX = ROOT.parent / "fixtures" / "presenter"
MORTGAGE = re.compile(r"משכנת|נכס|דירה|מומחי|Golden Set|לביא")
UPLOAD_WORD = re.compile(r"העלא|להעלאה|צירוף מסמך|מסמך חלופי")
F = {"id": "loan_set/id_card_ido.pdf", "id_exp": "loan_set/id_card_ido_EXPIRED.pdf", "p07": "golden_set/01_INITIAL_UPLOADS/ido_2026_07.pdf",
     "p08": "golden_set/01_INITIAL_UPLOADS/ido_2026_08.pdf", "p09w": "golden_set/01_INITIAL_UPLOADS/ido_2026_09.pdf",
     "p09": "golden_set/02_CORRECTION/ido_2026_09_CORRECTED.pdf", "st": "loan_set/statement_ido_2026-07_09.pdf",
     "st07": "loan_set/statement_ido_2026-07.pdf", "st09": "loan_set/statement_ido_2026-09.pdf", "q": "loan_set/car_quote_ido.pdf",
     "q_old": "loan_set/car_quote_ido_OLD.pdf"}
ID, PAY, BANK, PURPOSE = "ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"
SEEDS = {
    "DEMO-MTZ-2026-009": [("id", ID, None), ("p07", PAY, "2026-07"), ("p08", PAY, "2026-08"), ("p09w", PAY, "2026-09"),
                          ("st", BANK, None), ("q", PURPOSE, None)],
    "DEMO-MTZ-2026-008": [("p07", ID, None)],
    "DEMO-MTZ-2026-006": [("id", ID, None), ("p07", PAY, "2026-07"), ("p08", PAY, "2026-08"), ("p09", PAY, "2026-09"),
                          ("st", BANK, None), ("q", PURPOSE, None)],
    "DEMO-MTZ-2026-011": [("id", ID, None), ("p07", PAY, "2026-07"), ("p08", PAY, "2026-08"), ("p09", PAY, "2026-09"),
                          ("st", BANK, None), ("q", PURPOSE, None)],
    "DEMO-MTZ-2026-005": [("st07", BANK, None), ("st09", BANK, None), ("q_old", PURPOSE, None), ("id_exp", ID, None)],
}
INVENTORY: list[dict] = []
api = httpx.Client(base_url=BASE, timeout=60)


def seed() -> None:
    for case, steps in SEEDS.items():
        api.post("/api/session/demo/customer", json={"case_id": case}).raise_for_status()
        if api.get(f"/api/cases/{case}/documents").json():
            continue
        for key, code, period in steps:
            path = FIX / F[key]
            with path.open("rb") as fh:
                data = {"borrower_id": "BRW-A", "requirement_code": code, **({"expected_period": period} if period else {})}
                if code == PURPOSE:
                    data.pop("borrower_id")
                api.post(f"/api/cases/{case}/documents", data=data, files={"file": (path.name, fh, "application/pdf")}).raise_for_status()
        end = time.time() + 120
        while time.time() < end:
            s = api.get(f"/api/cases/{case}").json()
            if not s["readiness"]["pending_jobs"] and s["readiness"]["counts"]["processing"] == 0 and s["case_review"]:
                break
            time.sleep(0.8)
    api.post("/api/session/demo/staff", json={"staff_id": "STAFF-DANA"}).raise_for_status()


def record(page: Page, name: str, scope: str = "body") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / f"{name}.png"))
    text = page.locator(scope).first.inner_text() if page.locator(scope).count() else ""
    buttons = page.locator(f"{scope} button:visible, {scope} a:visible")
    uploads = []
    for i in range(buttons.count()):
        t = " ".join(buttons.nth(i).inner_text().split())
        if UPLOAD_WORD.search(t):
            uploads.append(t[:60])
    INVENTORY.append({"screen": name, "url": page.url.replace(BASE, ""), "upload_entry_points": uploads,
                      "mortgage_terms": sorted(set(MORTGAGE.findall(text))),
                      "headings": [" ".join(h.split())[:60] for h in page.locator(f"{scope} h1, {scope} h2, {scope} .page-title").all_inner_texts()][:8]})


def customer(page: Page, case: str, tag: str) -> None:
    page.goto(f"{BASE}/customer")
    page.evaluate(f"localStorage.setItem('mz.case', '{case}')")
    page.goto(f"{BASE}/customer")
    page.wait_for_selector("[data-testid=ai-card]", timeout=20000)
    record(page, f"{tag}-home", ".phone")
    page.goto(f"{BASE}/customer/documents")
    page.wait_for_selector("[data-testid=required-docs]", timeout=20000)
    record(page, f"{tag}-documents", ".phone")
    page.locator(".screen").evaluate("e => e.scrollTo(0, e.scrollHeight)")
    record(page, f"{tag}-documents-bottom", ".phone")
    if page.locator("[data-testid=doc-card]").count():
        page.locator("[data-testid=doc-card]").last.click()
        page.wait_for_selector("[data-testid=evidence-viewer]", timeout=20000)
        record(page, f"{tag}-document-review", ".phone")


def run() -> None:
    seed()
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        desk = b.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL")
        page = desk.new_page()
        for case, tag in (("DEMO-MTZ-2026-009", "c009-wrong-month"), ("DEMO-MTZ-2026-008", "c008-wrong-type"),
                          ("DEMO-MTZ-2026-006", "c006-complete"), ("DEMO-MTZ-2026-011", "c011-income"),
                          ("DEMO-MTZ-2026-005", "c005-gap-stale-expired"), ("DEMO-MTZ-2026-001", "c001-two-applicants-empty")):
            customer(page, case, tag)
        # every upload entry point in case 009
        page.evaluate("localStorage.setItem('mz.case', 'DEMO-MTZ-2026-009')")
        page.goto(f"{BASE}/customer")
        page.wait_for_selector("[data-testid=ai-card]")
        page.locator("[data-testid=card-primary]").click()
        page.wait_for_timeout(1200)
        record(page, "c009-entry-home-card", ".phone")
        page.keyboard.press("Escape")
        page.goto(f"{BASE}/customer")
        page.wait_for_selector("[data-testid=ai-card]")
        if page.locator("[data-testid=summary-upload]").count():
            page.locator("[data-testid=summary-upload]").click()
            page.wait_for_timeout(1200)
            record(page, "c009-entry-home-summary", ".phone")
        page.goto(f"{BASE}/customer/documents")
        page.locator("[data-testid='req-PAYSLIPS:BRW-A'] .dl-head").click()
        page.locator("[data-testid=upload-BRW-A]").first.click()
        record(page, "c009-entry-payslip-row", ".phone")
        page.goto(f"{BASE}/customer/documents")
        page.locator("[data-testid='req-ID_CARD:BRW-A'] .dl-head").click()
        page.wait_for_timeout(300)
        if page.locator("[data-testid='upload-ID_CARD:BRW-A']").count():
            page.locator("[data-testid='upload-ID_CARD:BRW-A']").click()
            record(page, "c009-entry-id-row", ".phone")
        # the chat (REPLAY: the no-model fallback answers from case data, with action buttons)
        page.goto(f"{BASE}/customer")
        page.locator("[data-testid=fab]").click()
        page.wait_for_selector("[data-testid=assistant-sheet], .sheet", timeout=10000)
        box = page.locator(".sheet textarea, .sheet input[type=text]").first
        box.fill("מה חסר כדי להתקדם?")
        box.press("Enter")
        page.wait_for_timeout(4000)
        record(page, "c009-chat", ".phone")
        if page.locator(".act-btn").count():
            page.locator(".act-btn").first.click()
            page.wait_for_timeout(1500)
            record(page, "c009-entry-chat-action", ".phone")
        for path, name in (("/customer/request", "c009-request-details"), ("/customer/stages", "c009-stages"),
                           ("/customer/meetings", "c009-meetings"), ("/customer/tools", "c009-tools"), ("/customer/apply", "c009-apply")):
            page.goto(f"{BASE}{path}")
            record(page, name, ".phone")
        page.goto(f"{BASE}/customer")
        page.locator("button[aria-label='תפריט']").click()
        record(page, "c009-drawer", ".phone")
        # presenter side pane
        page.goto(f"{BASE}/customer")
        page.wait_for_selector("[data-testid=featured-scenarios]")
        record(page, "presenter-top", ".hub-side")
        page.locator("[data-testid=all-scenarios-toggle]").click()
        page.wait_for_timeout(500)
        page.locator("[data-testid=scn-toggle-L-07]").click()
        page.locator(".hub-side").evaluate("e => e.scrollTo(0, e.scrollHeight * 0.55)")
        record(page, "presenter-scenarios", ".hub-side")
        page.locator(".hub-side").evaluate("e => e.scrollTo(0, e.scrollHeight)")
        record(page, "presenter-bottom", ".hub-side")
        # banker
        bank = b.new_context(viewport={"width": 1600, "height": 1000}, locale="he-IL").new_page()
        for case, tag in (("DEMO-MTZ-2026-009", "c009"), ("DEMO-MTZ-2026-008", "c008"), ("DEMO-MTZ-2026-011", "c011"),
                          ("DEMO-MTZ-2026-005", "c005"), ("DEMO-MTZ-2026-006", "c006")):
            bank.goto(f"{BASE}/banker?case={case}&view=classic")
            bank.wait_for_selector("[data-testid=review-queue]", timeout=20000)
            record(bank, f"banker-{tag}-review")
        bank.locator("[data-testid=coverage-toggle]").click()
        record(bank, "banker-c006-matrix")
        bank.goto(f"{BASE}/banker?case=DEMO-MTZ-2026-009&view=conversation")
        record(bank, "banker-c009-conversation")
        bank.goto(f"{BASE}/banker?case=DEMO-MTZ-2026-009&view=technical")
        record(bank, "banker-c009-technical")
        bank.goto(f"{BASE}/system")
        bank.wait_for_timeout(2500)
        record(bank, "system")
        # mobile
        mob = b.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True, has_touch=True).new_page()
        mob.goto(f"{BASE}/customer")
        mob.evaluate("localStorage.setItem('mz.case', 'DEMO-MTZ-2026-009')")
        mob.goto(f"{BASE}/customer")
        mob.wait_for_selector("[data-testid=ai-card]", timeout=20000)
        record(mob, "mobile-home")
        mob.goto(f"{BASE}/customer/documents")
        record(mob, "mobile-documents")
        mob.locator("[data-testid='req-PAYSLIPS:BRW-A'] .dl-head").click()
        mob.locator("[data-testid=upload-BRW-A]").first.click()
        record(mob, "mobile-upload-sheet")
        mob.goto(f"{BASE}/banker?case=DEMO-MTZ-2026-009&view=classic")
        mob.wait_for_timeout(2500)
        record(mob, "mobile-banker")
        b.close()
    (OUT / "inventory.json").write_text(json.dumps(INVENTORY, ensure_ascii=False, indent=1), encoding="utf8")
    for row in INVENTORY:
        print(f"{row['screen']:34} uploads={len(row['upload_entry_points'])} {row['upload_entry_points'][:4]} mortgage={row['mortgage_terms']}")


if __name__ == "__main__":
    run()
