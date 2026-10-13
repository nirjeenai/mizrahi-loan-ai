"""Screenshots of the banker console for before/after comparison. Read-only: it only navigates.

    BANKER_SHOTS_BASE=http://127.0.0.1:5851 backend/.venv/bin/python e2e/banker_screens.py before
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PHASE = sys.argv[1] if len(sys.argv) > 1 else "after"
BASE = os.environ.get("BANKER_SHOTS_BASE", "http://127.0.0.1:5851")
OUT = Path(__file__).resolve().parent / "artifacts" / "banker" / PHASE
CASES = os.environ.get("BANKER_SHOTS_CASES", "DEMO-MTZ-2026-001,DEMO-MTZ-2026-004").split(",")
DISPLAY = {"DEMO-MTZ-2026-001": "438838921", "DEMO-MTZ-2026-003": "438838999", "DEMO-MTZ-2026-004": "438839004"}
OLD_TABS = [("overview", "סקירה"), ("documents", "מסמכים וראיות"), ("findings", "ממצאים"), ("runs", "ריצות וביקורת")]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="he-IL")
        page.goto(f"{BASE}/banker")
        page.wait_for_selector("[data-testid=banker-readiness]", timeout=20000)
        for case in CASES:
            if PHASE == "before":
                page.locator(".case-item", has_text=DISPLAY[case]).first.click()
                page.wait_for_timeout(1500)
                for key, label in OLD_TABS:
                    page.locator(".tabs button", has_text=label).first.click()
                    page.wait_for_timeout(1200)
                    page.screenshot(path=str(OUT / f"{case[-3:]}-{key}.png"), full_page=True)
            else:
                tag = case[-3:]
                page.goto(f"{BASE}/banker?case={case}")
                page.wait_for_selector("[data-testid=review-queue]", timeout=20000)
                page.wait_for_timeout(1800)
                page.screenshot(path=str(OUT / f"{tag}-workspace.png"))
                actions = page.locator("[data-testid=action-correction]")
                if actions.count() and actions.is_enabled():
                    actions.click()
                    page.wait_for_timeout(400)
                    page.screenshot(path=str(OUT / f"{tag}-correction-form.png"))
                    page.locator("[data-testid=preview-request]").click()
                    page.wait_for_timeout(400)
                    page.screenshot(path=str(OUT / f"{tag}-correction-preview.png"))
                evidence = page.locator("[data-testid=show-evidence]")
                if evidence.count():
                    evidence.first.click()
                    page.wait_for_timeout(1200)
                    page.screenshot(path=str(OUT / f"{tag}-finding-evidence.png"))
                if page.locator("[data-testid=queue-group-missing] .queue-group-head").count():
                    page.locator("[data-testid=queue-group-missing] .queue-group-head").click()
                missing = page.locator("[data-testid=queue-item][data-kind=missing]")
                if missing.count():
                    missing.first.click()
                    page.wait_for_timeout(800)
                    page.screenshot(path=str(OUT / f"{tag}-missing.png"))
                page.set_viewport_size({"width": 1180, "height": 900})
                page.wait_for_timeout(500)
                page.screenshot(path=str(OUT / f"{tag}-narrow.png"))
                page.set_viewport_size({"width": 1440, "height": 900})
        browser.close()
    print("screenshots in", OUT)


if __name__ == "__main__":
    main()
