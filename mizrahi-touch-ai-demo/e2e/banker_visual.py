"""Before/after screenshots of the banker workspace at fixed viewports and case state, plus overflow checks.
Read-only: it only navigates. Point it at a backend whose case DEMO-MTZ-2026-001 is already populated.

    BANKER_VISUAL_BASE=http://127.0.0.1:5856 backend/.venv/bin/python e2e/banker_visual.py before
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright
import demo_auth  # noqa: E402  (e2e/ is on sys.path when a suite runs as a script)

PHASE = sys.argv[1] if len(sys.argv) > 1 else "after"
BASE = os.environ.get("BANKER_VISUAL_BASE", "http://127.0.0.1:5856")
demo_auth.install(BASE)                   # the service has no anonymous access (see demo_auth.py)
CASE = "DEMO-MTZ-2026-001"
OUT = Path(__file__).resolve().parent / "artifacts" / "visual" / PHASE
OVERFLOW_JS = """() => {
  const out = [];
  const doc = document.documentElement;
  if (doc.scrollWidth > doc.clientWidth + 1) out.push(`page ${doc.scrollWidth}>${doc.clientWidth}`);
  for (const sel of ['.case-bar', '.desk-summary', '.borrower-strip', '.desk-queue', '.desk-evidence', '.desk-panel']) {
    const el = document.querySelector(sel);
    if (el && el.scrollWidth > el.clientWidth + 1) out.push(`${sel} ${el.scrollWidth}>${el.clientWidth}`);
  }
  for (const el of document.querySelectorAll('.kf-value bdi, .kf-label')) {
    if (el.scrollWidth > el.clientWidth + 1 && !el.closest('[data-testid=key-fields] .kf:not(.static)')) out.push(`clipped field: "${(el.textContent || '').trim().slice(0, 30)}"`);
  }
  for (const el of document.querySelectorAll('.desk-panel button, .desk-queue button, .desk-summary *')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow === 'hidden' && !el.classList.contains('qrow-file'))
      out.push(`clipped: ${el.className} "${(el.textContent || '').trim().slice(0, 30)}"`);
  }
  return out;
}"""


def wait_ready(page: Page) -> None:
    page.wait_for_selector("[data-testid=review-queue]", timeout=20000)
    page.wait_for_function("() => { const i = document.querySelector('[data-testid=evidence-viewer] img');"
                           " return !document.querySelector('[data-testid=evidence-viewer]') || (i && i.naturalWidth > 0); }", timeout=20000)
    page.wait_for_timeout(700)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = httpx.get(f"{BASE}/api/banker/cases/{CASE}/workspace", timeout=30).json()
    items = {i["id"]: i for i in w["items"]}
    decide = next(g for g in w["groups"] if g["key"] == "decide")["items"]
    clean = next(i for i in decide if not items[i]["attention"])
    scenes = [("01-default", None), ("02-income-finding", next(i for i in items if i.startswith("finding:"))),
              ("03-missing", next(i for i in items if i.startswith("missing:"))), ("04-clean-document", clean)]
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for width in (1440, 1366):
            page = browser.new_page(viewport={"width": width, "height": 900}, locale="he-IL")
            for name, item in scenes if width == 1440 else scenes[:2]:
                page.goto(f"{BASE}/banker?case={CASE}" + (f"&item={item}" if item else ""))
                wait_ready(page)
                tag = f"{name}-{width}"
                page.screenshot(path=str(OUT / f"{tag}.png"))
                report[tag] = page.evaluate(OVERFLOW_JS)
            page.close()
        browser.close()
    (OUT / "overflow.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    for tag, issues in report.items():
        print(f"{'OK  ' if not issues else 'WARN'} {tag} {issues if issues else ''}")


if __name__ == "__main__":
    main()
