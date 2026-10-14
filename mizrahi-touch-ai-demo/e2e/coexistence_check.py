"""Mizrahi #2 (loans) next to Mizrahi #1 (mortgages): both run, and #2's frontend never reaches #1's backend.

Opens #2's Vite dev server (:5192) and #2's built app (:8791) in Chrome and records every request the page makes.
Mizrahi #1 (:8790) is only probed with read-only GETs (health and the demo case list) — never opened in a browser,
never written to.

    backend/.venv/bin/python e2e/coexistence_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.sync_api import sync_playwright

ART = Path(__file__).resolve().parent / "artifacts" / "coexistence"
RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def titles(base: str) -> list[str]:
    return [c["title_he"] for c in httpx.get(f"{base}/api/session/demo/cases", timeout=10).json()]


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    one = titles("http://127.0.0.1:8790")
    two = titles("http://127.0.0.1:8791")
    check("Mizrahi #1 is up on :8790 with its mortgage cases (read-only GET)", any("דירה" in t for t in one), one[0])
    check("Mizrahi #2 is up on :8791 with its loan cases", any("הלוואה" in t for t in two) and not any("דירה" in t for t in two), two[0])
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for name, url in (("vite-5192", "http://localhost:5192/customer"), ("built-8791", "http://127.0.0.1:8791/customer")):
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL")
            page = ctx.new_page()
            hosts: set[str] = set()
            page.on("request", lambda r: hosts.add(urlparse(r.url).netloc) if "/api/" in r.url or "/mcp" in r.url else None)
            page.goto(url)
            page.wait_for_selector("[data-testid=ai-card]", timeout=20000)
            page.wait_for_timeout(1500)
            phone = page.locator(".phone").inner_text()
            origin = urlparse(url).netloc
            check(f"{name}: every API request stays on #2's own origin ({origin})", hosts == {origin}, json.dumps(sorted(hosts)))
            check(f"{name}: the app shows the loan journey, not the mortgage one",
                  "בקשת ההלוואה" in phone and "משכנת" not in phone)
            page.screenshot(path=str(ART / f"{name}.png"))
            ctx.close()
        browser.close()
    after = titles("http://127.0.0.1:8790")
    check("Mizrahi #1 unchanged after the checks (same case list)", after == one)
    (ART / "results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf8")
    passed = sum(r["pass"] for r in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
