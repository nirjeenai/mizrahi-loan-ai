"""Screenshots of the main screens for before/after comparison (no Gemini, no writes except demo sessions).

    SHOTS_BASE=http://127.0.0.1:5846 SHOTS_OUT=docs/plans/baseline backend/.venv/bin/python e2e/baseline_screens.py
"""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("SHOTS_BASE", "http://127.0.0.1:5846")
OUT = Path(os.environ.get("SHOTS_OUT", "docs/plans/baseline"))
CASE = os.environ.get("SHOTS_CASE", "DEMO-MTZ-2026-008")

PAGES = [
    ("customer-home", f"/customer?case={CASE}", (1440, 900)),
    ("customer-documents", "/customer/documents", (1440, 900)),
    ("customer-stages", "/customer/stages", (1440, 900)),
    ("customer-request", "/customer/request", (1440, 900)),
    ("banker-review", f"/banker?case={CASE}", (1600, 1000)),
    ("banker-conversation", f"/banker?case={CASE}&view=conversation", (1600, 1000)),
    ("banker-technical", f"/banker?case={CASE}&view=technical", (1600, 1000)),
    ("system", "/system", (1440, 900)),
    ("admin", "/admin", (1600, 1000)),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, os.environ.get("SHOTS_ONLY", "").split(",")))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        ctx = browser.new_context(locale="he-IL")
        page = ctx.new_page()
        page.goto(BASE + "/customer")
        page.evaluate(f"localStorage.setItem('mz.case', '{CASE}')")
        for name, path, (w, h) in PAGES:
            if only and name not in only:
                continue
            page.set_viewport_size({"width": w, "height": h})
            resp = page.goto(BASE + path)
            if resp is None or resp.status >= 400:
                continue
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
            print("shot", name)
        browser.close()


if __name__ == "__main__":
    main()
