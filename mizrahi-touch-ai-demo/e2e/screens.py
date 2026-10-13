"""Visual QA: capture the main screens in a real Chrome (Playwright, channel=chrome)."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8790"
OUT = Path(__file__).resolve().parent / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)


def main(tag: str = "qa") -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        desk = browser.new_page(viewport={"width": 1366, "height": 940}, locale="he-IL")
        desk.goto(f"{BASE}/customer")
        desk.wait_for_selector("[data-testid=readiness-state]")
        desk.wait_for_timeout(800)
        desk.screenshot(path=str(OUT / f"{tag}-01-home-desktop.png"))
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="he-IL")
        mobile.goto(f"{BASE}/customer")
        mobile.wait_for_selector("[data-testid=readiness-state]")
        mobile.wait_for_timeout(600)
        mobile.screenshot(path=str(OUT / f"{tag}-02-home-mobile.png"))
        mobile.goto(f"{BASE}/customer/documents")
        mobile.wait_for_selector("[data-testid=doc-card]")
        mobile.wait_for_timeout(500)
        mobile.screenshot(path=str(OUT / f"{tag}-03-documents-mobile.png"), full_page=False)
        mobile.locator("[data-testid=doc-card]").filter(has_text="2026-09").first.click()
        mobile.wait_for_selector("[data-testid=review-verdict]")
        mobile.wait_for_timeout(1200)
        mobile.screenshot(path=str(OUT / f"{tag}-04-review-mobile.png"))
        desk.goto(f"{BASE}/banker")
        desk.wait_for_selector("[data-testid=banker-readiness]")
        desk.wait_for_timeout(800)
        desk.screenshot(path=str(OUT / f"{tag}-05-banker.png"))
        desk.goto(f"{BASE}/system")
        desk.wait_for_timeout(1500)
        desk.screenshot(path=str(OUT / f"{tag}-06-system.png"))
        browser.close()
    print("saved to", OUT)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "qa")
