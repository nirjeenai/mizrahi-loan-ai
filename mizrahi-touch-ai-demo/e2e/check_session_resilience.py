"""Case loading never needs a manual reload: the regression check for the intermittent "נדרש חיבור לתיק." / "אין חיבור
לתיק" errors, in a real Chrome against two isolated instances of the app on 127.0.0.1 (as a preview or isolated stack
runs beside the main instance).

Root cause it guards: browsers scope cookies by host, not port, so every instance on 127.0.0.1 shared one session cookie
name while signing it with its own DATA_DIR secret — opening any other instance logged this one out, and a one-shot
request (an upload, a document, a banker action) failed until the page was reloaded.

Covers: two instances side by side (no 401 on the first), an upload after the session was lost (the screenshot case),
the banker V1/V2/V3 switch after the session was lost, rapid case and version switching, refresh and direct case URLs,
back/forward, a transient 503 and a dropped connection on reads, and a slow network. Zero Gemini calls: the backends run
without a key and no step asks a model.

    # from backend/ — two instances with their own data (fresh DATA_DIRs; the check uploads one file to case 101)
    GEMINI_API_KEY= DATA_DIR=../e2e/artifacts/resilience/data-a ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8792
    GEMINI_API_KEY= DATA_DIR=../e2e/artifacts/resilience/data-b ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8795
    # from mizrahi-touch-ai-demo/ (each backend serves the last frontend/dist build)
    RES_A=http://127.0.0.1:8792 RES_B=http://127.0.0.1:8795 backend/.venv/bin/python e2e/check_session_resilience.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Route, expect, sync_playwright

import isolation

A = os.environ.get("RES_A", "http://127.0.0.1:8792")
B = os.environ.get("RES_B", "http://127.0.0.1:8795")
ROUNDS = int(os.environ.get("RES_ROUNDS", "3"))
for base in (A, B):
    if any(p in base for p in (":8790", ":8791", ":5192")):
        sys.exit(f"refusing to run against {base}: use isolated stacks")
    isolation.require_isolated(base)
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "resilience"
OUT.mkdir(parents=True, exist_ok=True)
PDF = ROOT.parent / "fixtures" / "out" / "main" / "ido_payslip_2026-09.pdf"
CASES = ["DEMO-MTZ-2026-101", "DEMO-MTZ-2026-011", "DEMO-MTZ-2026-008", "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-105"]
BAD = ("נדרש חיבור", "אין חיבור לתיק", "אין חיבור של צוות", "לא הצלחנו לטעון", "השרת אינו זמין")
RESULTS: list[dict] = []
ERRORS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{f' · {detail}' if detail else ''}", flush=True)


def errors_on(page: Page) -> list[str]:
    text = page.locator("body").inner_text()
    return [b for b in BAD if b in text]


def calm(page: Page, seconds: float = 2.5) -> list[str]:
    """Every error phrase visible at any moment during `seconds` (a flash of an error counts)."""
    seen: set[str] = set()
    end = time.time() + seconds
    while time.time() < end:
        seen.update(errors_on(page))
        page.wait_for_timeout(200)
    return sorted(seen)


def customer_on(page: Page, base: str, case_id: str, path: str = "/customer") -> None:
    page.goto(f"{base}/customer")
    page.evaluate("id => localStorage.setItem('mz.case', id)", case_id)
    page.goto(f"{base}{path}")


def lose_session(ctx: BrowserContext) -> None:
    """The session cookie is gone or unusable — what another instance's cookie, an expiry or a restart used to cause."""
    ctx.clear_cookies()


def banker_loaded(page: Page, view: str, timeout: int = 30000) -> None:
    sel = {"review": "[data-testid=bank-stage]", "intel": "[data-testid=bi-legend]", "case": "[data-testid=cc-name]"}[view]
    expect(page.locator(sel).first).to_be_visible(timeout=timeout)


def open_upload(page: Page, case_id: str) -> None:
    """Documents → the payslip row → its upload sheet with a file chosen, ready to submit."""
    customer_on(page, A, case_id, "/customer/documents")
    expect(page.locator("[data-testid=required-docs]")).to_be_visible(timeout=30000)
    page.locator(".dl-head", has_text="תלושי שכר").first.click()
    page.locator("[data-testid=required-docs] button.req-upload, [data-testid=required-docs] button[data-testid^='upload-BRW']").first.click()
    expect(page.locator("[data-testid=upload-sheet]")).to_be_visible()
    page.locator("[data-testid=file-input]").set_input_files(str(PDF))


def submit_upload(page: Page) -> tuple[bool, list[str]]:
    page.locator("[data-testid=upload-submit]").click()
    stored = page.locator("[data-testid=upload-stored], [data-testid=upload-stages], [data-testid=upload-outcome]").first
    try:
        expect(stored).to_be_visible(timeout=20000)
        return True, errors_on(page)
    except AssertionError:
        return False, errors_on(page)


def two_instances(ctx: BrowserContext) -> None:
    """Pages of A stay open (no reload) while instance B is opened in another tab — the demo situation."""
    a = ctx.new_page()
    open_upload(a, "DEMO-MTZ-2026-101")
    desk = ctx.new_page()
    desk.goto(f"{A}/banker?case=DEMO-MTZ-2026-101&view=review")
    banker_loaded(desk, "review")
    b = ctx.new_page()
    customer_on(b, B, "DEMO-MTZ-2026-001")
    expect(b.locator(".greeting")).to_be_visible(timeout=30000)
    b.goto(f"{B}/banker?case=DEMO-MTZ-2026-001")
    banker_loaded(b, "review")
    denied: list[str] = []
    for pg in (a, desk):
        pg.on("response", lambda r: denied.append(r.url.split("/api/")[-1]) if r.status == 401 else None)
    a.bring_to_front()
    ok, seen = submit_upload(a)
    a.screenshot(path=str(OUT / "two-instances-upload.png"))
    check("two instances: an upload on A after B was opened is stored, without 'נדרש חיבור לתיק'", ok and not seen, f"seen: {seen}")
    desk.bring_to_front()
    seen_desk: set[str] = set()
    for view, button in (("intel", "ui-v2"), ("case", "ui-v3")):
        desk.locator(f"[data-testid={button}]").click()
        banker_loaded(desk, view)
        seen_desk.update(calm(desk, 1.5))
    check("two instances: A's banker console switches to V2 and V3 after B was opened, without an error",
          not seen_desk, f"seen: {sorted(seen_desk)}")
    check("two instances: B's sessions do not log A out (no 401 on A)", not denied, f"401s: {denied[:4]}")
    for pg in (a, desk, b):
        pg.close()


def upload_after_lost_session(ctx: BrowserContext, n: int) -> None:
    page = ctx.new_page()
    open_upload(page, "DEMO-MTZ-2026-101")
    lose_session(ctx)
    ok, seen = submit_upload(page)
    page.screenshot(path=str(OUT / f"upload-after-lost-session-{n}.png"))
    check(f"round {n}: an upload after the session was lost is stored without 'נדרש חיבור לתיק'", ok and not seen, f"seen: {seen}")
    page.close()


def banker_after_lost_session(ctx: BrowserContext, n: int) -> None:
    page = ctx.new_page()
    page.goto(f"{A}/banker?case=DEMO-MTZ-2026-101&view=review")      # the console otherwise reopens the last choice
    banker_loaded(page, "review")
    lose_session(ctx)
    seen: set[str] = set()
    for view, button in (("intel", "ui-v2"), ("case", "ui-v3"), ("review", "ui-v1"), ("case", "ui-v3")):
        page.locator(f"[data-testid={button}]").click()
        banker_loaded(page, view)
        seen.update(calm(page, 0.8))
    check(f"round {n}: V1/V2/V3 switching right after the staff session was lost loads every view without an error",
          not seen, f"seen: {sorted(seen)}")
    page.close()


def rapid_switching(ctx: BrowserContext) -> None:
    page = ctx.new_page()
    page.goto(f"{A}/banker?case={CASES[0]}&view=case")
    banker_loaded(page, "case")
    for cid in CASES * 2:                                  # faster than any case loads
        page.goto(f"{A}/banker?case={cid}&view=case", wait_until="commit")
    banker_loaded(page, "case")
    page.wait_for_timeout(1500)
    shown = page.locator("[data-testid=cc-kicker], .cc-kicker").first.inner_text()
    want = page.evaluate("id => fetch('/api/banker/cases').then(r => r.json()).then(rows => rows.find(x => x.case_id === id).display_number)",
                         CASES[-1])
    check("rapid case switching (10 URLs) settles on the last case, with no error", want in shown and not calm(page, 2),
          f"shown '{shown}' want {want}")
    for button in ("ui-v1", "ui-v2", "ui-v3", "ui-v2", "ui-v1", "ui-v3", "ui-v2"):
        page.locator(f"[data-testid={button}]").click()
    banker_loaded(page, "intel")
    check("rapid V1/V2/V3 clicks settle on the last choice (V2), with no error",
          "V2" in page.locator("[data-testid=banker-ui-switch] button.on").inner_text() and not calm(page, 2))
    page.go_back()
    page.go_forward()
    banker_loaded(page, "intel")
    check("back/forward in the banker console keeps a loaded view", not calm(page, 1.5))
    # customer: refresh and direct entry into several cases in a row
    for cid in CASES[:3]:
        customer_on(page, A, cid)
        expect(page.locator(".greeting")).to_be_visible(timeout=30000)
        page.reload()
        expect(page.locator(".greeting")).to_be_visible(timeout=30000)
        pill = page.locator(".touch-header .case-pill").inner_text()
        num = page.evaluate("id => fetch('/api/cases/' + id).then(r => r.json()).then(s => s.case.display_number)", cid)
        check(f"customer: direct entry and refresh in {cid} shows that case", num in pill and not calm(page, 1.5), pill)
    for path in ("/customer/documents", "/customer/stages", "/customer", "/customer/documents"):
        page.goto(f"{A}{path}")
    page.go_back()                                         # → home
    expect(page.locator(".greeting")).to_be_visible(timeout=30000)
    page.go_back()                                         # → stages
    page.go_forward()                                      # → home
    expect(page.locator(".greeting")).to_be_visible(timeout=30000)
    check("customer: back/forward between home, documents and stages", not calm(page, 1.5))
    page.close()


def flaky_network(ctx: BrowserContext) -> None:
    page = ctx.new_page()
    customer_on(page, A, "DEMO-MTZ-2026-011")
    expect(page.locator(".greeting")).to_be_visible(timeout=30000)
    hits = {"503": 0, "abort": 0}

    def once_503(route: Route) -> None:
        if hits["503"] == 0:
            hits["503"] += 1
            route.fulfill(status=503, body="restarting")
        else:
            route.continue_()

    def once_abort(route: Route) -> None:
        if hits["abort"] == 0:
            hits["abort"] += 1
            route.abort("connectionreset")
        else:
            route.continue_()

    page.route("**/api/cases/DEMO-MTZ-2026-011", once_503)
    page.route("**/api/cases/DEMO-MTZ-2026-011/documents", once_abort)
    page.reload()
    expect(page.locator(".greeting")).to_be_visible(timeout=30000)
    check("a transient 503 and a dropped connection on the first reads recover without a reload or an error",
          hits == {"503": 1, "abort": 1} and not calm(page, 2), json.dumps(hits))
    page.unroute("**/api/cases/DEMO-MTZ-2026-011")
    page.unroute("**/api/cases/DEMO-MTZ-2026-011/documents")

    def slow(route: Route) -> None:
        time.sleep(1.2)
        route.continue_()

    page.route("**/api/**", slow)
    page.goto(f"{A}/banker?case=DEMO-MTZ-2026-008&view=case")
    banker_loaded(page, "case", timeout=60000)
    customer_on(page, A, "DEMO-MTZ-2026-008", "/customer/documents")
    expect(page.locator("[data-testid=required-docs]")).to_be_visible(timeout=60000)
    check("slow network (1.2 s per request): banker V3 and customer documents load, no error", not calm(page, 2))
    page.unroute("**/api/**")
    page.close()


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.on("page", lambda pg: pg.on("pageerror", lambda e: ERRORS.append(str(e))))
        steps = [("two instances", lambda: two_instances(ctx))]
        for n in range(1, ROUNDS + 1):
            steps += [(f"upload round {n}", lambda n=n: upload_after_lost_session(ctx, n)),
                      (f"banker round {n}", lambda n=n: banker_after_lost_session(ctx, n))]
        steps += [("rapid switching", lambda: rapid_switching(ctx)), ("flaky network", lambda: flaky_network(ctx))]
        for name, step in steps:
            try:
                step()
            except Exception as exc:  # noqa: BLE001 — a step that cannot finish is a failure, the rest still runs
                check(f"{name}: ran to the end", False, repr(exc)[:300])
        check("no uncaught page errors", not ERRORS, " | ".join(ERRORS[:3]))
        browser.close()
    passed = sum(r["ok"] for r in RESULTS)
    (OUT / "results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
