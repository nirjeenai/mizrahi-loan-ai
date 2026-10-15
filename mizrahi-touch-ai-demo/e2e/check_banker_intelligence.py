"""Banker Intelligence V2 (compact executive dashboard) in a real Chrome: the briefing for a complete case (Michal Barak,
101), an income-gap case (011) and an incomplete case (008); what sits above the fold at 1440×900; the three KPIs and the
three scenarios against the backend's own arithmetic, What-if and reset; every collapsible section; evidence from a number
to the document; the collapsed, editable draft; responsive widths; and V1 still working beside it.

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

import isolation

BASE = os.environ.get("BI_BASE", "http://127.0.0.1:5844")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
isolation.require_isolated(BASE)
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


def expand(page: Page, panel: str) -> None:
    if page.locator(f"[data-testid={panel}-toggle]").get_attribute("aria-expanded") != "true":
        page.locator(f"[data-testid={panel}-toggle]").click()


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


def kpi(page: Page, name: str) -> str:
    return page.locator(f"[data-testid=bi-kpi-{name}-value]").get_attribute("data-value") or ""


def michal(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{MICHAL}/intelligence").json()
    s, a = x["simulation"], x["analysis"]
    open_v2(page, MICHAL)
    page.screenshot(path=str(OUT / "01-desktop-1440x900.png"))
    head = page.locator("[data-testid=bi-brief]")
    hb = head.bounding_box()
    check("header: compact (≤ 220 px), actual case context, short recommendation, one action, disclaimer",
          hb["height"] <= 220 and "מיכל ברק" in page.locator("[data-testid=bi-context]").inner_text()
          and "₪90,000" in page.locator("[data-testid=bi-context]").inner_text() and "60 תשלומים" in page.locator("[data-testid=bi-context]").inner_text()
          and page.locator("[data-testid=bi-headline]").inner_text().strip() == "מומלץ להתקדם לבחינת האשראי"
          and page.locator("[data-testid=bi-next-btn]").inner_text().startswith("מעבר לטיפול בתיק")
          and "לא אישור אשראי" in head.inner_text(), f"height {hb['height']:.0f}px")
    text = page.locator("[data-testid=bi-rec-text]").inner_text()
    check("header: one explanation sentence built from the briefing's numbers",
          "₪21,050" in text and "14.1%" in text and "במערכות הבנק" not in head.inner_text(), text)
    banker_he = "ממתין לבדיקת בנקאי" if x["documents"]["awaiting_decision"] else "המסמכים התקבלו על ידך"
    check("documents: completion and banker review are two separate statuses",
          page.locator("[data-testid=bi-doc-primary]").inner_text() == "מסמכים הושלמו"
          and page.locator("[data-testid=bi-doc-banker]").inner_text() == banker_he
          and "אושר" not in page.locator("[data-testid=bi-doc-status]").inner_text(),
          f"{x['documents']['accepted']}/{x['documents']['total']} accepted by the banker · {banker_he}")
    sims = page.locator("[data-testid=bi-scenario]").evaluate_all("els => els.map(e => e.getBoundingClientRect().top)")
    pay_bottom = page.locator("[data-testid=bi-sc-pay]").first.evaluate("e => e.getBoundingClientRect().bottom")
    check("above the fold at 1440×900: context, recommendation, action, three KPIs and the three scenarios' payments",
          page.locator(".bi-kpi").count() == 3 and page.locator("[data-testid=bi-kpis]").bounding_box()["y"] < 450
          and len(sims) == 3 and max(sims) < 600 and pay_bottom < 900, f"scenario tops {[round(v) for v in sims]}, payment bottom {pay_bottom:.0f}")
    check("KPIs: income, new monthly payment and combined ratio equal the briefing",
          a["income"]["value"] == 21050 and float(kpi(page, "payment")) == a["proposed_payment"]["value"]
          and float(kpi(page, "combined")) == a["combined_dsr"]["value"], f"{kpi(page, 'payment')} · {kpi(page, 'combined')}%")
    got = norm(cards(page))
    want = norm(expected(s["inputs"]["principal"], s["inputs"]["term_months"], s["inputs"]["annual_rate_pct"], s))
    check("simulator: three scenarios, identical to the backend's arithmetic", len(got) == 3 and got == want and got == norm(
        [{"key": r["key"], "term": r["term_months"], "pay": r["monthly_payment_ils"], "interest": r["total_interest_ils"],
          "dsr": str(r["combined_dsr_pct"])} for r in s["scenarios"]]), json.dumps(got, ensure_ascii=False))
    page.locator("[data-testid=bi-simulator]").screenshot(path=str(OUT / "03-simulator-three-scenarios.png"))
    page.locator("[data-testid=bi-wi-term]").fill("84")
    page.wait_for_timeout(150)
    got = norm(cards(page))
    check("what-if: term 84 recomputes the three cards (60/84/108) and the KPIs follow",
          got == norm(expected(90000, 84, 6.0, s)) and float(kpi(page, "payment")) == finance.monthly_payment(90000, 84, 6.0)
          and page.locator(".bi-slider.changed [data-mark=sim]").count() == 1 and page.locator("[data-testid=bi-sc-pay] [data-mark=sim]").count() == 3,
          json.dumps([(r["term"], r["pay"], r["dsr"]) for r in got], ensure_ascii=False))
    page.locator("[data-testid=bi-wi-rate]").fill("0")
    page.wait_for_timeout(150)
    zero = cards(page)
    check("what-if: zero interest → payment = principal ÷ term and exactly no interest",
          all(abs(r["pay"] - round(90000 / r["term"], 2)) < 0.005 and r["interest"] == 0 for r in zero), json.dumps([(r["term"], r["pay"], r["interest"]) for r in zero]))
    page.locator("[data-testid=bi-wi-reset]").click()
    page.wait_for_timeout(150)
    after = c.get(f"/api/banker/cases/{MICHAL}/intelligence").json()
    check("what-if: reset restores the application's scenario and the KPIs; nothing changed on the server",
          norm(cards(page)) == want and float(kpi(page, "payment")) == a["proposed_payment"]["value"] and page.locator(".bi-sc.suggested").count() == 1
          and after["simulation"]["inputs"] == s["inputs"] and after["analysis"]["income"] == a["income"] and after["analysis"]["existing_debt"] == a["existing_debt"])
    # reasons: three by default, the rest on demand
    shown = page.locator("[data-testid=bi-consideration]").count()
    page.locator("[data-testid=bi-why-toggle]").click()
    check("reasons: three by default; 'show all' reveals the rest and what to verify",
          shown == 3 and page.locator("[data-testid=bi-consideration]").count() == len(x["recommendation"]["considerations"]) + 1
          and page.locator("[data-testid=bi-verify]").is_visible())
    page.locator("[data-testid=bi-why-toggle]").click()
    # supporting sections collapsed by default; each expands
    closed = [page.locator(f"[data-testid={p}-toggle]").get_attribute("aria-expanded") for p in ("bi-evidence", "bi-obligations", "bi-data")]
    for p in ("bi-evidence", "bi-obligations", "bi-data"):
        expand(page, p)
    ob = page.locator("[data-testid=bi-obligations]")
    check("sections: collapsed by default for a clean case, and each expands",
          closed == ["false", "false", "false"] and ob.locator("[data-testid=bi-exposure-utilized]").is_visible()
          and page.locator("[data-testid=bi-evlist]").is_visible(), str(closed))
    check("obligations: bank-data marks and date (no fixture ids), exposure and LTV inside the details",
          ob.locator("[data-mark=demo]").count() >= 4 and "DEMO" not in ob.inner_text() and "2026-10-11" in ob.inner_text()
          and ob.locator("[data-testid=bi-kpi-ltv]").inner_text().startswith("68.2%"))
    page.locator("[data-testid=bi-slips-toggle]").click()
    check("income: compact summary; 'show payslips' reveals three verified (or banker-accepted) months",
          page.locator("[data-testid=bi-income-month] [data-mark=verified], [data-testid=bi-income-month] [data-mark=reviewed]").count() == 3)
    page.locator("[data-testid=bi-income-month][data-period='2026-07']").click()
    drawer = page.locator("[data-testid=bi-drawer]")
    expect(drawer).to_have_attribute("data-kind", "document")
    expect(drawer.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_count(1, timeout=15000)
    check("evidence: a payslip month opens the existing evidence viewer on its own box",
          drawer.locator("[data-testid=bi-drawer-value]").inner_text().strip() == "21,000.00")
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "04-evidence-income-to-document.png"))
    page.locator("[data-testid=bi-drawer-close]").click()
    page.locator(".bi-scroll").evaluate("e => e.scrollTo(0, 0)")
    page.locator("[data-testid=bi-kpi-combined-value]").click()
    expect(drawer.locator("[data-testid=bi-drawer-formula]")).to_be_visible()
    inputs = drawer.locator("[data-testid=bi-drawer-input]").count()
    drawer.locator("[data-testid=bi-drawer-input]").nth(1).click()
    expect(drawer).to_have_attribute("data-kind", "calculated")
    drawer.locator("[data-testid=bi-drawer-input]").first.click()
    expect(drawer).to_have_attribute("data-kind", "synthetic_bank")
    check("evidence: the combined-ratio KPI explains its formula and leads down to the bank-context loan record",
          inputs == 3 and "2026-10-11" in drawer.inner_text() and "DEMO" not in drawer.inner_text())
    page.screenshot(path=str(OUT / "04b-evidence-calc-to-synthetic.png"))
    page.locator("[data-testid=bi-drawer-close]").click()
    # the draft: collapsed preview → edit → collapse keeps the edit → copy
    check("draft: collapsed by default — a preview, no editor",
          page.locator("[data-testid=bi-draft-preview]").is_visible() and page.locator("[data-testid=bi-draft-text]").count() == 0
          and page.locator("[data-testid=bi-draft-preview]").get_attribute("data-kind") == "complete_documentation")
    page.locator("[data-testid=bi-draft-edit]").click()
    area = page.locator("[data-testid=bi-draft-text]")
    original = area.input_value()
    area.evaluate("e => e.setSelectionRange(e.value.length, e.value.length)")
    area.type("\nנשמח לתאם שיחה השבוע.")
    page.locator("[data-testid=bi-action]").screenshot(path=str(OUT / "05-editable-draft.png"))
    page.locator("[data-testid=bi-draft-collapse]").scroll_into_view_if_needed()
    check("draft: with the editor open, its buttons can be reached", page.locator("[data-testid=bi-draft-collapse]").is_visible()
          and page.locator("[data-testid=bi-draft-collapse]").evaluate("e => e.getBoundingClientRect().bottom <= window.innerHeight"))
    page.locator("[data-testid=bi-draft-collapse]").click()
    kept = "נשמח לתאם שיחה השבוע." in page.locator("[data-testid=bi-draft-preview]").inner_text()
    page.locator("[data-testid=bi-draft-edit]").click()
    check("draft: editable, customer-specific; collapsing and reopening keeps the edit",
          "מיכל" in original and "₪90,000" in original and "אינה אישור הלוואה" in original and kept
          and area.input_value().endswith("נשמח לתאם שיחה השבוע.") and page.locator("[data-testid=bi-draft-edited]").is_visible())
    page.locator("[data-testid=bi-draft-tab][data-kind=conditional_financing]").click()
    cond = page.locator("[data-testid=bi-draft-text]").input_value()
    check("draft: the financing draft lists the illustrative scenarios with conditions and no internal ratio",
          all(f"{r['term_months']} תשלומים" in cond for r in s["scenarios"]) and "אינם הצעה מחייבת" in cond and "יחס" not in cond)
    page.locator("[data-testid=bi-draft-tab][data-kind=complete_documentation]").click()
    page.locator("[data-testid=bi-draft-copy]").click()
    expect(page.locator("[data-testid=desk-toast]")).to_contain_text("לא נשלחה")
    check("draft: copy works and says nothing was sent", True)
    # full page with every section open, on a fresh load
    open_v2(page, MICHAL)
    for p in ("bi-evidence", "bi-obligations", "bi-data"):
        expand(page, p)
    unclip(page)
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "02-full-page.png"), full_page=True)
    open_v2(page, MICHAL)
    target = x["recommendation"]["next_action"]["v1_item"]
    page.locator("[data-testid=bi-next-btn]").click()
    expect(page.locator("[data-testid=evidence-pane]")).to_be_visible(timeout=15000)
    check("next action 'מעבר לטיפול בתיק' opens the V1 workspace" + (" at the first document awaiting the banker" if target else ""),
          (f"item={target.replace(':', '%3A')}" in page.url or f"item={target}" in page.url) if target else "view=intel" not in page.url, page.url)


def gap(page: Page, c: httpx.Client) -> None:
    open_v2(page, GAP)
    head = page.locator("[data-testid=bi-brief]")
    check("human review: clarification state with the gap visible in the header (not behind 'show more')",
          head.get_attribute("data-state") == "CLARIFICATION_REQUIRED" and page.locator("[data-testid=bi-headline]").inner_text().strip() == "נדרש בירור לפני המשך הטיפול"
          and "פער הכנסה פתוח" in page.locator("[data-testid=bi-blockers]").inner_text() and "₪16,500" in page.locator("[data-testid=bi-blockers]").inner_text()
          and page.locator("[data-testid=bi-next-btn]").inner_text().startswith("בירור הפער"))
    page.screenshot(path=str(OUT / "06-human-review-1440x900.png"))
    ev = page.locator("[data-testid=bi-evidence]")
    check("human review: the conditions section opens by itself, with both discrepancies and the declared-income alternative",
          page.locator("[data-testid=bi-evidence-toggle]").get_attribute("aria-expanded") == "true"
          and ev.locator("[data-testid=bi-discrepancy][data-kind=income][data-open=true]").count() == 1
          and ev.locator("[data-testid=bi-discrepancy][data-kind=purpose_amount]").count() == 1
          and page.locator("[data-testid=bi-declared-alt]").is_visible() and page.locator("[data-testid=bi-sim-provisional]").is_visible()
          and page.locator(".bi-sc.suggested").count() == 0)
    card = ev.locator("[data-testid=bi-discrepancy][data-kind=income]")
    card.locator("[data-testid=bi-datum]").nth(1).click()
    drawer = page.locator("[data-testid=bi-drawer]")
    expect(drawer.locator("[data-testid=bi-drawer-formula]")).to_be_visible()
    drawer.locator("[data-testid=bi-drawer-input]").first.click()
    expect(drawer).to_have_attribute("data-kind", "document")
    expect(drawer.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_count(1, timeout=15000)
    check("human review: the documented average opens its payslip evidence", True)
    page.locator("[data-testid=bi-drawer-close]").click()
    check("human review: the clarification draft is recommended",
          page.locator("[data-testid=bi-draft-preview]").get_attribute("data-kind") == "financial_clarification"
          and "הסבר" in page.locator("[data-testid=bi-draft-preview]").inner_text())
    card.scroll_into_view_if_needed()
    ev.screenshot(path=str(OUT / "06b-human-review-gap.png"))


def incomplete(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{INCOMPLETE}/intelligence").json()
    open_v2(page, INCOMPLETE)
    head = page.locator("[data-testid=bi-brief]").inner_text()
    check("incomplete: completion state, missing items in the header, no positive credit wording or suggestion",
          page.locator("[data-testid=bi-brief]").get_attribute("data-state") == "DOCUMENTS_INCOMPLETE"
          and page.locator("[data-testid=bi-headline]").inner_text().strip() == "נדרשת השלמת מסמכים"
          and page.locator("[data-testid=bi-blockers] li").count() >= 3 and "מומלץ להתקדם" not in head
          and page.locator(".bi-sc.suggested").count() == 0 and page.locator("[data-testid=bi-doc-primary]").inner_text().startswith("חסרים"))
    preview = page.locator("[data-testid=bi-draft-preview]")
    check("incomplete: only a missing-documents draft, listing the missing items",
          page.locator("[data-testid=bi-draft-tab]").count() == 1 and preview.get_attribute("data-kind") == "missing_documents"
          and all(m["item_he"] in preview.inner_text() for m in x["documents"]["missing"]))
    page.screenshot(path=str(OUT / "07-incomplete-1440x900.png"))


def responsive(page: Page) -> None:
    for w, h, name in ((1100, 800, "08-small-desktop-1100.png"), (390, 844, "09-mobile-390.png")):
        page.set_viewport_size({"width": w, "height": h})
        open_v2(page, MICHAL)
        over = max(page.locator(".bi-scroll").evaluate("e => e.scrollWidth - e.clientWidth"),
                   page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
        page.screenshot(path=str(OUT / name))
        check(f"responsive {w}px: no horizontal overflow; KPIs and scenarios render", over <= 1 and page.locator("[data-testid=bi-scenario]").count() == 3, f"overflow {over}px")
    page.set_viewport_size({"width": 1440, "height": 900})


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
        for step in (responsive, v1):
            try:
                step(page)
            except Exception as exc:
                check(f"{step.__name__}: ran to the end", False, repr(exc)[:300])
        check("no uncaught page errors", not errors, " | ".join(errors[:3]))
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    (OUT.parent / "results.json").write_text(json.dumps({"mode": "REPLAY", "base": BASE, "results": [
        {"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS]}, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed · REPLAY")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
