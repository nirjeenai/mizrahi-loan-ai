"""Banker Intelligence V2 in a real Chrome: the briefing for a complete case (Michal Barak, 101), an income-gap case (011)
and an incomplete case (008); the three scenarios and the What-if recomputation against the backend's own arithmetic;
evidence from a number to the document; the editable draft; and V1 still working beside it.

Isolated REPLAY stack only (zero Gemini calls). Read-only: it uploads nothing and records no decision — populate the
cases first with verify_presenter_scenarios.py on the same stack.

    # from backend/
    .venv/bin/python ../e2e/replay_backend.py --port 8793 --data ../e2e/artifacts/bi-v2/data-replay
    # from mizrahi-touch-ai-demo/
    REPLAY_BASE=http://127.0.0.1:8793 backend/.venv/bin/python e2e/verify_presenter_scenarios.py
    node e2e/serve_frontend.mjs e2e/artifacts/bi-v2/web 5844 http://127.0.0.1:8793
    BI_BASE=http://127.0.0.1:5844 backend/.venv/bin/python e2e/check_banker_intelligence.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("BI_BASE", "http://127.0.0.1:5844")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app.workflow import finance  # noqa: E402  the canonical arithmetic the browser must reproduce

OUT = ROOT / "artifacts" / "bi-v2" / "shots"
MICHAL, GAP, INCOMPLETE = "DEMO-MTZ-2026-101", "DEMO-MTZ-2026-011", "DEMO-MTZ-2026-008"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def api() -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post("/api/session/demo/staff", json={}).raise_for_status()
    return c


def open_v2(page: Page, case: str) -> None:
    page.goto(f"{BASE}/banker?case={case}&view=intel")
    expect(page.locator(f"[data-testid=bi-root][data-case='{case}']")).to_be_visible(timeout=30000)
    page.wait_for_timeout(300)


def unclip(page: Page) -> None:
    """The console scrolls inside a fixed-height pane; let it grow so a full-page screenshot shows everything."""
    page.add_style_tag(content=".console.desk{height:auto!important;overflow:visible!important}.bi-scroll{overflow:visible!important}")


def cards(page: Page) -> list[dict]:
    return page.locator("[data-testid=bi-scenario]").evaluate_all(
        """els => els.map(e => ({key: e.dataset.key, term: +e.dataset.term,
            pay: +e.querySelector('[data-testid=bi-sc-pay]').dataset.value,
            interest: +e.querySelector('[data-testid=bi-sc-interest]').dataset.value,
            dsr: e.querySelector('[data-testid=bi-sc-dsr]').dataset.value}))""")


def expected(principal: float, term: int, rate: float, s: dict) -> list[dict]:
    rows = finance.scenarios(principal, term, rate, s["income_ils"], s["existing_debt_ils"], s["asset_price_ils"])
    return [{"key": r["key"], "term": r["term_months"], "pay": r["monthly_payment_ils"], "interest": r["total_interest_ils"],
             "dsr": "" if r["combined_dsr_pct"] is None else str(r["combined_dsr_pct"])} for r in rows]


def norm(rows: list[dict]) -> list[dict]:
    return [{**r, "dsr": "" if r["dsr"] in ("", None) else str(float(r["dsr"]))} for r in rows]


def michal(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{MICHAL}/intelligence").json()
    s = x["simulation"]
    open_v2(page, MICHAL)
    page.screenshot(path=str(OUT / "01-desktop-1440x900.png"))
    unclip(page)
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "02-full-page.png"), full_page=True)
    open_v2(page, MICHAL)
    brief = page.locator("[data-testid=bi-brief]")
    check("complete: the recommendation is the first thing on screen and matches the document state",
          brief.get_attribute("data-state") == "READY_FOR_CREDIT_REVIEW" == x["recommendation"]["state"]
          and page.locator("[data-testid=bi-headline]").inner_text() == x["recommendation"]["headline_he"]
          and brief.bounding_box()["y"] < 200, x["recommendation"]["headline_he"][:60])
    check("complete: documentation and financial tracks are separate; no approval wording",
          page.locator("[data-testid=bi-track-docs]").is_visible() and page.locator("[data-testid=bi-track-fin]").get_attribute("data-availability") == "full"
          and "מאושרת" not in brief.inner_text() and "ההלוואה אושרה" not in brief.inner_text())
    marks = page.locator("[data-testid=bi-obligations] [data-mark=demo]").count()
    check("complete: obligations and exposure carry the synthetic DEMO mark and the fixture's date",
          marks >= 4 and "BFC-DEMO-BARAK-01" in page.locator("[data-testid=bi-obligations]").inner_text()
          and "2026-10-11" in page.locator("[data-testid=bi-obligations]").inner_text(), f"{marks} DEMO marks")
    months = page.locator("[data-testid=bi-income-month] [data-mark=verified]").count()
    check("complete: verified income — three payslip months, each marked as a verified document value", months == 3)
    got = norm(cards(page))
    want = norm(expected(s["inputs"]["principal"], s["inputs"]["term_months"], s["inputs"]["annual_rate_pct"], s))
    check("complete: three scenarios, identical to the backend's arithmetic (payment, interest, combined ratio)",
          len(got) == 3 and got == want and got == norm([{"key": r["key"], "term": r["term_months"], "pay": r["monthly_payment_ils"],
                                                          "interest": r["total_interest_ils"], "dsr": str(r["combined_dsr_pct"])} for r in s["scenarios"]]),
          json.dumps(got, ensure_ascii=False))
    sim = page.locator("[data-testid=bi-simulator]")
    sim.scroll_into_view_if_needed()
    sim.screenshot(path=str(OUT / "03-simulator-three-scenarios.png"))
    # What-if: the term, then the rate (zero interest), then reset
    page.locator("[data-testid=bi-wi-term]").fill("84")
    page.wait_for_timeout(150)
    got = norm(cards(page))
    check("what-if: term 84 recomputes all three cards (60/84/108) exactly as finance.py",
          got == norm(expected(90000, 84, 6.0, s)), json.dumps([(r["term"], r["pay"], r["dsr"]) for r in got], ensure_ascii=False))
    check("what-if: the changed input is labelled as a simulation and the comparison updates",
          page.locator(".bi-slider.changed .m-sim").count() == 1 and page.locator("[data-testid=bi-sc-pay] [data-mark=sim]").count() == 3
          and "108" in page.locator("[data-testid=bi-compare]").inner_text())
    sim.screenshot(path=str(OUT / "03b-simulator-whatif-term84.png"))
    page.locator("[data-testid=bi-wi-rate]").fill("0")
    page.wait_for_timeout(150)
    zero = cards(page)
    check("what-if: zero interest → payment = principal ÷ term and exactly no interest",
          all(abs(r["pay"] - round(90000 / r["term"], 2)) < 0.005 and r["interest"] == 0 for r in zero)
          and norm(zero) == norm(expected(90000, 84, 0, s)), json.dumps([(r["term"], r["pay"], r["interest"]) for r in zero]))
    page.locator("[data-testid=bi-wi-reset]").click()
    page.wait_for_timeout(150)
    check("what-if: reset returns to the application's own scenario; the suggestion reappears",
          norm(cards(page)) == want and page.locator(".bi-sc.suggested").count() == 1)
    after = c.get(f"/api/banker/cases/{MICHAL}/intelligence").json()
    check("what-if: the case's application, income and obligations are unchanged on the server",
          after["simulation"]["inputs"] == s["inputs"] and after["analysis"]["income"] == x["analysis"]["income"]
          and after["analysis"]["existing_debt"] == x["analysis"]["existing_debt"])
    # evidence: an income month → the document, boxed
    page.locator("[data-testid=bi-income-month][data-period='2026-07']").click()
    drawer = page.locator("[data-testid=bi-drawer]")
    expect(drawer).to_have_attribute("data-kind", "document")
    expect(drawer.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_count(1, timeout=15000)
    check("evidence: a verified income figure opens the existing evidence viewer on its own box",
          drawer.locator("[data-testid=bi-drawer-value]").inner_text().strip() == "21,000.00"
          and drawer.get_attribute("data-source").endswith(":net_pay"))
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "04-evidence-income-to-document.png"))
    page.locator("[data-testid=bi-drawer-close]").click()
    # a calculated ratio → formula and inputs → a synthetic input
    page.locator("[data-testid=bi-kpi-combined] button").click()
    expect(drawer.locator("[data-testid=bi-drawer-formula]")).to_be_visible()
    inputs = drawer.locator("[data-testid=bi-drawer-input]").count()
    drawer.locator("[data-testid=bi-drawer-input]").nth(1).click()
    expect(drawer).to_have_attribute("data-kind", "calculated")
    drawer.locator("[data-testid=bi-drawer-input]").first.click()
    expect(drawer).to_have_attribute("data-kind", "synthetic_bank")
    check("evidence: the combined ratio explains its formula, and its inputs lead down to the synthetic loan record",
          inputs == 3 and "BFC-DEMO-BARAK-01" in drawer.inner_text() and "2026-10-11" in drawer.inner_text())
    page.screenshot(path=str(OUT / "04b-evidence-calc-to-synthetic.png"))
    page.locator("[data-testid=bi-drawer-close]").click()
    # the draft
    tabs = page.locator("[data-testid=bi-draft-tab]").evaluate_all("els => els.map(e => e.dataset.kind)")
    text = page.locator("[data-testid=bi-draft-text]")
    original = text.input_value()
    text.click()
    text.evaluate("e => e.setSelectionRange(e.value.length, e.value.length)")
    text.type("\nנשמח לתאם שיחה השבוע.")
    check("draft: complete-documentation draft is recommended, customer-specific and editable",
          tabs == ["complete_documentation", "conditional_financing"] and "מיכל" in original and "₪90,000" in original
          and "אינה אישור הלוואה" in original and page.locator("[data-testid=bi-draft-edited]").is_visible()
          and text.input_value().endswith("נשמח לתאם שיחה השבוע."), str(tabs))
    page.locator("[data-testid=bi-draft-tab][data-kind=conditional_financing]").click()
    cond = text.input_value()
    check("draft: the financing draft lists the illustrative scenarios with conditions and no internal ratio",
          all(f"{r['term_months']} תשלומים" in cond for r in s["scenarios"]) and "אינם הצעה מחייבת" in cond and "יחס" not in cond)
    page.locator("[data-testid=bi-draft-tab][data-kind=complete_documentation]").click()
    page.locator("[data-testid=bi-draft-copy]").click()
    expect(page.locator("[data-testid=desk-toast]")).to_contain_text("לא נשלחה")
    page.locator("[data-testid=bi-action]").screenshot(path=str(OUT / "05-editable-draft.png"))
    # the next action opens V1 at the document
    open_v2(page, MICHAL)
    target = x["recommendation"]["next_action"]["v1_item"]
    page.locator("[data-testid=bi-next-btn]").click()
    expect(page.locator("[data-testid=evidence-pane]")).to_be_visible(timeout=15000)
    check("next action: opens the V1 review workspace at the first document awaiting the banker",
          f"item={target.replace(':', '%3A')}" in page.url or f"item={target}" in page.url, page.url)


def gap(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{GAP}/intelligence").json()
    open_v2(page, GAP)
    check("human review: clarification state, provisional analysis, no suggested scenario",
          page.locator("[data-testid=bi-brief]").get_attribute("data-state") == "CLARIFICATION_REQUIRED"
          and page.locator("[data-testid=bi-track-fin]").get_attribute("data-availability") == "provisional"
          and page.locator("[data-testid=bi-suggested]").count() == 0 and page.locator(".bi-sc.suggested").count() == 0)
    card = page.locator("[data-testid=bi-discrepancy][data-kind=income]")
    check("human review: the income gap shows declared vs documented with sources, and the declared alternative ratio",
          card.get_attribute("data-open") == "true" and "₪16,500" in card.inner_text() and "₪14,700" in card.inner_text()
          and page.locator("[data-testid=bi-declared-alt]").is_visible() and page.locator("[data-testid=bi-sim-provisional]").is_visible())
    card.locator("[data-testid=bi-datum]").nth(1).click()
    drawer = page.locator("[data-testid=bi-drawer]")
    expect(drawer.locator("[data-testid=bi-drawer-formula]")).to_be_visible()
    drawer.locator("[data-testid=bi-drawer-input]").first.click()
    expect(drawer).to_have_attribute("data-kind", "document")
    expect(drawer.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_count(1, timeout=15000)
    check("human review: the documented average opens its payslip evidence", True)
    page.locator("[data-testid=bi-drawer-close]").click()
    check("human review: the clarification draft is recommended and asks for an explanation",
          page.locator("[data-testid=bi-draft-text]").get_attribute("data-kind") == "financial_clarification"
          and "הסבר" in page.locator("[data-testid=bi-draft-text]").input_value())
    page.locator(".bi-scroll").evaluate("e => e.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    page.screenshot(path=str(OUT / "06-human-review-1440x900.png"))
    check("human review: the requested amount above the car quote is a second, sourced discrepancy",
          page.locator("[data-testid=bi-discrepancy][data-kind=purpose_amount]").count() == 1)
    card.scroll_into_view_if_needed()
    page.locator("[data-testid=bi-evidence]").screenshot(path=str(OUT / "06b-human-review-gap.png"))


def incomplete(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{INCOMPLETE}/intelligence").json()
    open_v2(page, INCOMPLETE)
    brief = page.locator("[data-testid=bi-brief]").inner_text()
    check("incomplete: documents-incomplete state with the missing items and no positive credit conclusion",
          page.locator("[data-testid=bi-brief]").get_attribute("data-state") == "DOCUMENTS_INCOMPLETE"
          and "נדרשת השלמת מסמכים" in brief and page.locator("[data-testid=bi-suggested]").count() == 0
          and "ניתן להתקדם" not in brief, x["recommendation"]["headline_he"][:80])
    tabs = page.locator("[data-testid=bi-draft-tab]").evaluate_all("els => els.map(e => e.dataset.kind)")
    check("incomplete: only a missing-documents draft, listing the missing items",
          tabs == ["missing_documents"] and all(m["item_he"] in page.locator("[data-testid=bi-draft-text]").input_value()
                                                for m in x["documents"]["missing"]))
    page.screenshot(path=str(OUT / "07-incomplete-1440x900.png"))


def v1(page: Page) -> None:
    page.evaluate("localStorage.removeItem('mz.banker.ui')")
    page.goto(f"{BASE}/banker?case={MICHAL}")
    expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    check("V1: without a choice the console opens the existing review workspace", page.locator("[data-testid=bi-root]").count() == 0)
    page.locator("[data-testid=case-switch]").click()
    page.locator(".case-pop-row", has_text="438839011").click()
    expect(page.locator("[data-testid=review-queue]")).to_be_visible()
    check("V1: case switching still works", "DEMO-MTZ-2026-011" in page.url)
    page.locator("[data-testid=ui-v2]").click()
    expect(page.locator(f"[data-testid=bi-root][data-case='{GAP}']")).to_be_visible(timeout=20000)
    page.goto(f"{BASE}/banker?case={MICHAL}")
    expect(page.locator(f"[data-testid=bi-root][data-case='{MICHAL}']")).to_be_visible(timeout=20000)
    check("switch: V2 follows the selected case and the choice is remembered", True)
    page.locator("[data-testid=ui-v1]").click()
    expect(page.locator("[data-testid=review-queue]")).to_be_visible()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = api()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL")
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for step in (michal, gap, incomplete):
            try:
                step(page, c)
            except Exception as exc:                                  # report and continue with the next scenario
                check(f"{step.__name__}: ran to the end", False, repr(exc)[:300])
                page.screenshot(path=str(OUT / f"error-{step.__name__}.png"))
        try:
            v1(page)
        except Exception as exc:
            check("v1: ran to the end", False, repr(exc)[:300])
        check("no uncaught page errors", not errors, " | ".join(errors[:3]))
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    (OUT.parent / "results.json").write_text(json.dumps({"mode": "REPLAY", "base": BASE, "results": [
        {"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS]}, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed · REPLAY")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
