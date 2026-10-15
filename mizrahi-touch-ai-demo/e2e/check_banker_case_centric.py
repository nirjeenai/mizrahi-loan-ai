"""Banker Case-Centric V3 in a real Chrome: the case workspace for a complete case (Michal Barak, 101), an income-gap
case (011) and an incomplete case (008); the document gallery and the original files; evidence from a number to the
document; the three scenarios and the What-if against the backend's own arithmetic; the editable reply; V1 and V2
still working beside it; a phone-width layout.

Isolated REPLAY stack only (zero Gemini calls). Read-only: it uploads nothing and records no decision — populate the
cases first with verify_presenter_scenarios.py on the same stack.

    # from backend/
    .venv/bin/python ../e2e/replay_backend.py --port 8796 --data ../e2e/artifacts/bi-v3/data-replay
    # from mizrahi-touch-ai-demo/
    REPLAY_BASE=http://127.0.0.1:8796 backend/.venv/bin/python e2e/verify_presenter_scenarios.py
    node e2e/serve_frontend.mjs e2e/artifacts/bi-v3/web 5852 http://127.0.0.1:8796
    CC_BASE=http://127.0.0.1:5852 backend/.venv/bin/python e2e/check_banker_case_centric.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("CC_BASE", "http://127.0.0.1:5852")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app.workflow import finance  # noqa: E402  the canonical arithmetic the browser must reproduce

OUT = ROOT / "artifacts" / "bi-v3" / "shots"
MICHAL, GAP, INCOMPLETE = "DEMO-MTZ-2026-101", "DEMO-MTZ-2026-011", "DEMO-MTZ-2026-008"
RESULTS: list[tuple[str, bool, str]] = []
UNCLIP = ".console.desk{height:auto!important;overflow:visible!important}.cc-scroll{overflow:visible!important}.cc-sticky{display:none!important}"


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def api() -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post("/api/session/demo/staff", json={}).raise_for_status()
    return c


def open_v3(page: Page, case: str) -> None:
    page.goto(f"{BASE}/banker?case={case}&view=case")
    expect(page.locator(f"[data-testid=cc-root][data-case='{case}']")).to_be_visible(timeout=30000)
    page.wait_for_timeout(400)


def shot_section(page: Page, testid: str, name: str) -> None:
    page.add_style_tag(content=".cc-sticky{display:none!important}")
    el = page.locator(f"[data-testid={testid}]")
    el.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    el.screenshot(path=str(OUT / name))


def num(page: Page, sel: str) -> str:
    return page.locator(sel).first.inner_text().strip()


def cards(page: Page) -> list[dict]:
    return page.locator("[data-testid=cc-scenario]").evaluate_all(
        """els => els.map(e => ({key: e.dataset.key, term: +e.dataset.term,
            pay: +e.querySelector('[data-testid=cc-sc-pay]').dataset.value,
            interest: +e.querySelector('[data-testid=cc-sc-interest]').dataset.value,
            dsr: e.querySelector('[data-testid=cc-sc-dsr]').dataset.value}))""")


def expected(principal: float, term: int, rate: float, s: dict) -> list[dict]:
    rows = finance.scenarios(principal, term, rate, s["income_ils"], s["existing_debt_ils"], s["asset_price_ils"])
    return [{"key": r["key"], "term": r["term_months"], "pay": r["monthly_payment_ils"], "interest": r["total_interest_ils"],
             "dsr": "" if r["combined_dsr_pct"] is None else str(r["combined_dsr_pct"])} for r in rows]


def norm(rows: list[dict]) -> list[dict]:
    return [{**r, "dsr": "" if r["dsr"] in ("", None) else str(float(r["dsr"]))} for r in rows]


def ils(v: float) -> str:
    return f"₪{round(v):,}"


def michal(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{MICHAL}/intelligence").json()
    ws = c.get(f"/api/banker/cases/{MICHAL}/workspace").json()
    s, a = x["simulation"], x["analysis"]
    open_v3(page, MICHAL)
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "01-v3-desktop-1440x900.png"))
    rec = page.locator("[data-testid=cc-rec]")
    check("complete: header names the customer and the loan from the case", page.locator("[data-testid=cc-name]").inner_text() == "מיכל ברק"
          and page.locator("[data-testid=cc-loanline]").inner_text() == "הלוואה לרכישת רכב · ₪90,000 · 60 תשלומים")
    check("complete: the recommendation is above the fold, matches the state, and is not an approval",
          rec.get_attribute("data-state") == "READY_FOR_CREDIT_REVIEW" == x["recommendation"]["state"]
          and page.locator("[data-testid=cc-rec-title]").inner_text() == "מומלץ להתקדם לבחינת האשראי"
          and page.locator("[data-testid=cc-rec-text]").inner_text() == x["recommendation"]["headline_he"]
          and rec.bounding_box()["y"] + rec.bounding_box()["height"] < 900
          and "אינה אישור אשראי" in rec.inner_text() and "ההלוואה אושרה" not in rec.inner_text()
          and page.locator("[data-testid=cc-attention]").count() == 0)
    figs = (num(page, "[data-testid=cc-fig-income] .cc-num"), num(page, "[data-testid=cc-fig-payment] .cc-num"), num(page, "[data-testid=cc-fig-dsr] .cc-num"))
    check("complete: the three key figures are the API's income, payment and combined ratio",
          figs == (ils(a["income"]["value"]), ils(a["proposed_payment"]["value"]), f"{a['combined_dsr']['value']:.1f}%")
          and page.locator("[data-testid=cc-primary]").bounding_box()["y"] < 900, " · ".join(figs))
    # details
    det = page.locator("[data-testid=cc-details]").inner_text()
    check("details: customer, product, purpose, amount, term, quote price and the car from the quote",
          all(t in det for t in ("מיכל ברק", "שכיר/ה", "הלוואה לכל מטרה", "רכישת רכב", "₪90,000", "60 תשלומים", "₪132,000"))
          and x["sources"][x["loan"]["asset"]["subject_source_id"]]["value_raw"] in det)
    shot_section(page, "cc-details", "02-v3-details.png")
    # documents
    docs = [i for i in ws["items"] if i["kind"] == "document" and not i.get("replaced_by")]
    tiles = page.locator("[data-testid=cc-doc]")
    loaded = page.locator("[data-testid=cc-thumb]").evaluate_all("els => els.map(e => e.complete && e.naturalWidth > 0)")
    check("documents: one tile per document in the case, each with its real first page rendered",
          tiles.count() == len(docs) == 6 and len(loaded) == 6 and all(loaded)
          and sorted(tiles.evaluate_all("els => els.map(e => e.dataset.doc)")) == sorted(d["document_id"] for d in docs))
    check("documents: one documentation status, and the banker's pending acceptance said separately",
          page.locator("[data-testid=cc-docstate-main]").inner_text() == "כל המסמכים הנדרשים התקבלו ונבדקו ב-AI"
          and "6 מסמכים נבדקו ב-AI וממתינים לקבלה פורמלית שלך" in page.locator("[data-testid=cc-docstate-banker]").inner_text()
          and page.locator("[data-testid=cc-missing]").count() == 0)
    shot_section(page, "cc-docs", "03-v3-document-gallery.png")
    pay = next(d for d in docs if d["filename"] == "payslip_michal_2026-07.pdf")
    page.locator(f"[data-testid=cc-doc][data-doc='{pay['document_id']}']").click()
    dr = page.locator("[data-testid=cc-docdrawer]")
    expect(dr.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=15000)
    page.wait_for_timeout(600)
    href = dr.locator("[data-testid=cc-doc-original]").get_attribute("href")
    r = page.request.get(BASE + href)
    boxes = dr.locator("[data-testid=evidence-viewer] .hl").count()
    check("documents: a tile opens that document in the existing evidence viewer, with its boxed fields",
          dr.get_attribute("data-doc") == pay["document_id"] and boxes > 0 and dr.locator("[data-testid=cc-doc-facts] .fact-row").count() > 0, f"{boxes} boxes")
    check("documents: the original file opens (the same PDF the customer uploaded)",
          href == f"/api/documents/{pay['document_id']}/file" and r.status == 200 and r.headers.get("content-type", "").startswith("application/pdf")
          and r.body()[:4] == b"%PDF")
    dr.locator(".fact-row").first.click()
    expect(dr.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_count(1)
    page.screenshot(path=str(OUT / "04-v3-document-evidence.png"))
    page.locator("[data-testid=cc-docdrawer-close]").click()
    # financial analysis
    fin = page.locator("[data-testid=cc-financial]")
    check("financial: income summary with the average and month-to-month variability; obligations marked as demo data",
          ils(x["income"]["borrowers"][0]["documented_avg"]["value"]) in fin.inner_text()
          and f"{x['income']['borrowers'][0]['variability_pct']:.1f}%" in fin.inner_text()
          and page.locator("[data-testid=cc-obligations] [data-mark=demo]").count() == 1
          and page.locator("[data-testid=cc-discrepancy]").count() == 0)
    page.locator("[data-testid=cc-payslips-toggle]").click()
    page.locator("[data-testid=cc-obligations-toggle]").click()
    obl = page.locator("[data-testid=cc-obligations-detail]").inner_text()
    check("financial: three payslip months on demand; obligations detail names the synthetic fixture and its date",
          page.locator("[data-testid=cc-income-month]").count() == 3 and "BFC-DEMO-BARAK-01" in obl and "2026-10-11" in obl and "לא נספר פעמיים" in obl)
    shot_section(page, "cc-financial", "05-v3-financial-analysis.png")
    page.locator("[data-testid=cc-income-month][data-period='2026-07']").click()
    drawer = page.locator("[data-testid=bi-drawer]")
    expect(drawer).to_have_attribute("data-kind", "document")
    expect(drawer.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_count(1, timeout=15000)
    check("evidence: a payslip month opens the shared source drawer on its own box in the document",
          drawer.locator("[data-testid=bi-drawer-value]").inner_text().strip() == "21,000.00" and drawer.get_attribute("data-source").endswith(":net_pay"))
    page.locator("[data-testid=bi-drawer-close]").click()
    page.locator("[data-testid=cc-fig-dsr] .cc-num").click()
    expect(drawer.locator("[data-testid=bi-drawer-formula]")).to_be_visible()
    drawer.locator("[data-testid=bi-drawer-input]").nth(1).click()
    drawer.locator("[data-testid=bi-drawer-input]").first.click()
    expect(drawer).to_have_attribute("data-kind", "synthetic_bank")
    check("evidence: the combined ratio explains its formula and leads down to the synthetic loan record",
          "BFC-DEMO-BARAK-01" in drawer.inner_text())
    page.locator("[data-testid=bi-drawer-close]").click()
    # scenarios and What-if
    want = norm(expected(s["inputs"]["principal"], s["inputs"]["term_months"], s["inputs"]["annual_rate_pct"], s))
    api_rows = norm([{"key": r["key"], "term": r["term_months"], "pay": r["monthly_payment_ils"], "interest": r["total_interest_ils"],
                      "dsr": str(r["combined_dsr_pct"])} for r in s["scenarios"]])
    got = norm(cards(page))
    check("scenarios: three cards, identical to finance.py and to the API (payment, interest, combined ratio)",
          len(got) == 3 and got == want == api_rows
          and page.locator("[data-testid=cc-scenario][data-key=requested] .cc-sc-tag").first.inner_text() == "הבקשה המקורית",
          json.dumps([(r["term"], r["pay"], r["dsr"]) for r in got]))
    shot_section(page, "cc-alternatives", "06-v3-financing-scenarios.png")
    page.locator("[data-testid=cc-whatif-toggle]").click()
    page.locator("[data-testid=cc-wi-term]").fill("84")
    page.wait_for_timeout(150)
    check("what-if: term 84 recomputes all three cards (60/84/108) exactly as finance.py",
          norm(cards(page)) == norm(expected(90000, 84, 6.0, s)) and page.locator("[data-testid=cc-sim-active]").is_visible())
    page.locator("[data-testid=cc-wi-principal]").fill("70000")
    page.locator("[data-testid=cc-wi-rate]").fill("0")
    page.wait_for_timeout(150)
    zero = cards(page)
    check("what-if: amount 70,000 at zero interest → payment = amount ÷ term, no interest",
          all(abs(r["pay"] - round(70000 / r["term"], 2)) < 0.005 and r["interest"] == 0 for r in zero) and norm(zero) == norm(expected(70000, 84, 0, s)))
    shot_section(page, "cc-alternatives", "06b-v3-whatif.png")
    page.locator("[data-testid=cc-wi-reset]").click()
    page.wait_for_timeout(150)
    after = c.get(f"/api/banker/cases/{MICHAL}/intelligence").json()
    check("what-if: reset returns to the application; nothing changed on the server",
          norm(cards(page)) == want and page.locator("[data-testid=cc-sim-active]").count() == 0
          and after["simulation"]["inputs"] == s["inputs"] and after["analysis"]["income"] == a["income"])
    # reasoning
    why = page.locator("[data-testid=cc-reasoning]")
    check("reasoning: every consideration and verification item from the API, the detail behind a toggle",
          why.locator("[data-testid=cc-consideration]").count() == len(x["recommendation"]["considerations"])
          and why.locator("[data-testid=cc-verify] li").count() == len(x["recommendation"]["verify"])
          and page.locator("[data-testid=cc-why-detail]").count() == 0)
    page.locator("[data-testid=cc-why-more]").click()
    check("reasoning: the detail lists every document value used", page.locator("[data-testid=cc-evrow]").count()
          == sum(1 for v in x["sources"].values() if v["kind"] == "document"))
    # reply
    text = page.locator("[data-testid=cc-draft-text]")
    tabs = page.locator("[data-testid=cc-draft-tab]").evaluate_all("els => els.map(e => e.dataset.kind)")
    original = text.input_value()
    text.click()
    text.evaluate("e => e.setSelectionRange(e.value.length, e.value.length)")
    text.type("\nנשמח לתאם שיחה השבוע.")
    check("reply: the recommended draft is the complete-documentation one, customer-specific, and editable",
          tabs == ["complete_documentation", "conditional_financing"] and text.get_attribute("data-kind") == "complete_documentation"
          and "מיכל" in original and "₪90,000" in original and "אינה אישור הלוואה" in original
          and page.locator("[data-testid=cc-draft-edited]").is_visible() and text.input_value().endswith("נשמח לתאם שיחה השבוע."))
    page.locator("[data-testid=cc-draft-copy]").click()
    expect(page.locator("[data-testid=desk-toast]")).to_contain_text("לא נשלח")
    clip = page.evaluate("navigator.clipboard.readText()")
    check("reply: copy puts the edited text on the clipboard and says nothing was sent", clip.endswith("נשמח לתאם שיחה השבוע."))
    shot_section(page, "cc-reply", "07-v3-editable-response.png")
    page.locator("[data-testid=cc-draft-restore]").click()
    check("reply: restore returns the template text", text.input_value() == original)
    page.locator("[data-testid=cc-draft-tab][data-kind=conditional_financing]").click()
    cond = text.input_value()
    check("reply: the financing draft lists the illustrative scenarios as non-binding, without the internal ratio",
          all(f"{r['term_months']} תשלומים" in cond for r in s["scenarios"]) and "אינם הצעה מחייבת" in cond and "יחס" not in cond)
    # full page
    open_v3(page, MICHAL)
    page.add_style_tag(content=UNCLIP)
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "08-v3-full-page.png"), full_page=True)
    # primary action → V1
    open_v3(page, MICHAL)
    target = x["recommendation"]["next_action"]["v1_item"]
    page.locator("[data-testid=cc-primary]").click()
    expect(page.locator("[data-testid=evidence-pane]")).to_be_visible(timeout=15000)
    check("primary action: 'מעבר לטיפול בתיק' opens the V1 review workspace at the next item",
          f"item={target.replace(':', '%3A')}" in page.url or f"item={target}" in page.url, page.url)


def gap(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{GAP}/intelligence").json()
    open_v3(page, GAP)
    page.wait_for_timeout(600)
    rec = page.locator("[data-testid=cc-rec]")
    check("human review: clarification title; the gaps are listed in the recommendation itself",
          rec.get_attribute("data-state") == "CLARIFICATION_REQUIRED" and page.locator("[data-testid=cc-rec-title]").inner_text() == "נדרש בירור לפני בחינת האשראי"
          and page.locator("[data-testid=cc-attn-gap]").count() == 2 and "מומלץ להתקדם" not in rec.inner_text())
    page.screenshot(path=str(OUT / "09-v3-human-review-1440x900.png"))
    card = page.locator("[data-testid=cc-discrepancy][data-kind=income]")
    check("human review: the income gap is open and visible without expanding anything, declared vs documented",
          card.get_attribute("data-open") == "true" and card.is_visible() and "₪16,500" in card.inner_text() and "₪14,700" in card.inner_text()
          and page.locator("[data-testid=cc-declared-alt]").is_visible() and page.locator("[data-testid=cc-sim-provisional]").is_visible()
          and page.locator("[data-testid=cc-discrepancy][data-kind=purpose_amount]").count() == 1)
    check("human review: no scenario is presented as a suggestion while the gap is open",
          page.locator(".cc-sc.sug").count() == 0 and page.locator("[data-testid=cc-availability]").inner_text() == x["analysis"]["status_he"])
    card.locator("[data-testid=cc-datum]").nth(1).click()
    drawer = page.locator("[data-testid=bi-drawer]")
    expect(drawer.locator("[data-testid=bi-drawer-formula]")).to_be_visible()
    drawer.locator("[data-testid=bi-drawer-input]").first.click()
    expect(drawer).to_have_attribute("data-kind", "document")
    expect(drawer.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_count(1, timeout=15000)
    check("human review: the documented average opens its payslip evidence", True)
    page.locator("[data-testid=bi-drawer-close]").click()
    check("human review: the clarification draft is recommended and asks for an explanation",
          page.locator("[data-testid=cc-draft-text]").get_attribute("data-kind") == "financial_clarification"
          and "הסבר" in page.locator("[data-testid=cc-draft-text]").input_value())
    shot_section(page, "cc-financial", "09b-v3-human-review-financial.png")
    page.locator("[data-testid=cc-gap-open]").first.click()
    expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=15000)
    check("human review: 'בירור בסקירת המסמכים' opens the finding in V1", "F-" in page.url, page.url)


def incomplete(page: Page, c: httpx.Client) -> None:
    x = c.get(f"/api/banker/cases/{INCOMPLETE}/intelligence").json()
    open_v3(page, INCOMPLETE)
    page.wait_for_timeout(600)
    rec = page.locator("[data-testid=cc-rec]").inner_text()
    check("incomplete: documents-incomplete title, the missing count up front, no positive credit conclusion",
          page.locator("[data-testid=cc-rec]").get_attribute("data-state") == "DOCUMENTS_INCOMPLETE"
          and page.locator("[data-testid=cc-rec-title]").inner_text() == "נדרשת השלמת מסמכים לפני בחינת האשראי"
          and "5 פריטים חסרים בתיק" in rec and "מומלץ להתקדם" not in rec and "ניתן להתקדם" not in rec)
    page.screenshot(path=str(OUT / "10-v3-incomplete-1440x900.png"))
    miss = page.locator("[data-testid=cc-missing]")
    check("incomplete: each missing item is an honest 'חסר' tile, not a fake thumbnail; the replaced payslip is tucked away",
          miss.count() == len(x["documents"]["missing"]) == 5 and page.locator("[data-testid=cc-doc]").count() == 1
          and page.locator("[data-testid=cc-replaced-toggle]").is_visible()
          and "התקבלו 1 מתוך 4 דרישות" in page.locator("[data-testid=cc-docstate-main]").inner_text())
    shot_section(page, "cc-docs", "10b-v3-incomplete-documents.png")
    check("incomplete: only the missing-documents draft, listing every missing item",
          page.locator("[data-testid=cc-draft-tab]").count() == 0 and page.locator("[data-testid=cc-draft-text]").get_attribute("data-kind") == "missing_documents"
          and all(m["item_he"] in page.locator("[data-testid=cc-draft-text]").input_value() for m in x["documents"]["missing"]))
    check("incomplete: the analysis says it is partial (declared income)", page.locator("[data-testid=cc-partial]").is_visible()
          and "ניתוח חלקי" in page.locator("[data-testid=cc-fig-dsr]").inner_text())
    miss.first.click()
    expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=15000)
    check("incomplete: a missing tile opens that item in V1", "missing" in page.url, page.url)


def switching(page: Page) -> None:
    page.evaluate("localStorage.removeItem('mz.banker.ui')")
    page.goto(f"{BASE}/banker?case={MICHAL}")
    expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    check("V1: without a choice the console opens the existing review workspace", page.locator("[data-testid=cc-root]").count() == 0)
    page.locator("[data-testid=ui-v2]").click()
    expect(page.locator(f"[data-testid=bi-root][data-case='{MICHAL}']")).to_be_visible(timeout=20000)
    check("V2: the intelligence briefing still renders beside V3", page.locator("[data-testid=bi-brief]").is_visible())
    page.locator("[data-testid=ui-v3]").click()
    expect(page.locator(f"[data-testid=cc-root][data-case='{MICHAL}']")).to_be_visible(timeout=20000)
    page.locator("[data-testid=case-switch]").click()
    page.locator(".case-pop-row", has_text="438839011").click()
    expect(page.locator(f"[data-testid=cc-root][data-case='{GAP}']")).to_be_visible(timeout=20000)
    check("V3: case switching keeps V3 and loads the other case", "DEMO-MTZ-2026-011" in page.url and page.locator("[data-testid=cc-name]").inner_text() == "עידו לוי")
    page.goto(f"{BASE}/banker?case={MICHAL}")
    expect(page.locator(f"[data-testid=cc-root][data-case='{MICHAL}']")).to_be_visible(timeout=20000)
    check("V3: the choice is remembered", True)
    page.locator("[data-testid=ui-v1]").click()
    expect(page.locator("[data-testid=review-queue]")).to_be_visible()


def phone(browser) -> None:
    ctx = browser.new_context(viewport={"width": 768, "height": 1024}, locale="he-IL")
    page = ctx.new_page()
    open_v3(page, MICHAL)
    page.wait_for_timeout(800)
    doc = page.evaluate("document.documentElement.scrollWidth")
    check("responsive: at 768 px the whole page fits without horizontal scrolling", doc <= 768, f"document {doc}px")
    page.screenshot(path=str(OUT / "12-v3-tablet-768.png"))
    ctx.close()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", device_scale_factor=2)
    page = ctx.new_page()
    open_v3(page, MICHAL)
    page.wait_for_timeout(800)
    col = page.locator(".cc-page").evaluate("e => Math.max(...[...e.querySelectorAll('.cc-head, .cc-card, .cc-rec, .cc-figs')].map(c => c.getBoundingClientRect().width))")
    top = page.locator(".console-top").evaluate("e => e.scrollWidth")
    check("responsive: at 390 px every V3 section fits the column (the shared console top bar is wider — same in V1)",
          col <= 390, f"widest section {col:.0f}px · console top bar {top}px")
    page.locator(".cc-page").screenshot(path=str(OUT / "11-v3-phone-390-column.png"))
    ctx.close()


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
        for step2 in (lambda: switching(page), lambda: phone(browser)):
            try:
                step2()
            except Exception as exc:
                check("switching/responsive: ran to the end", False, repr(exc)[:300])
        check("no uncaught page errors", not errors, " | ".join(errors[:3]))
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    (OUT.parent / "results.json").write_text(json.dumps({"mode": "REPLAY", "base": BASE, "results": [
        {"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS]}, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed · REPLAY")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
