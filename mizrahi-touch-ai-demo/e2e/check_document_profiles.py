"""Round 1 — smart document profiling in a real Chrome: the six prepared use cases (TC-01…06 ↔ UC-01…06) open the right
persona and checklist, "התיקים שלי" lists the demonstrated customer's applications, the 15 earlier scenarios sit under
"בדיקות נוספות", a document without a review rubric is stored for the banker (never "valid"), and new customers create
persisted cases through the JEEN questionnaire (salaried, self-employed, mixed via correction, joint, company).

Isolated REPLAY stack only (zero Gemini calls; uploads use recorded fixtures). Creates demo applications and uploads to
cases 102 and the cases it creates; resets case 102 first.

    # from backend/ — fresh DATA_DIR
    .venv/bin/python ../e2e/replay_backend.py --port 8792 --data ../e2e/artifacts/loan/data-replay
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/loan/web-replay 5843 http://127.0.0.1:8792
    PROFILES_BASE=http://127.0.0.1:5843 backend/.venv/bin/python e2e/check_document_profiles.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("PROFILES_BASE", "http://127.0.0.1:5843")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT.parent / "fixtures" / "presenter" / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
USE_CASES = MANIFEST["useCases"]
FIX = ROOT.parent / "fixtures" / "presenter" / "loan_set"
OUT = ROOT / "artifacts" / "profiles"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def shot(page: Page, name: str, full: bool = False) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)


def open_presenter(page: Page) -> None:
    if page.locator("[data-testid=presenter-panel]").evaluate("e => getComputedStyle(e).visibility") != "visible":
        page.locator("[data-testid=presenter-toggle]").click()
    expect(page.locator("[data-testid=use-cases]")).to_be_visible(timeout=20000)


def required_rows(page: Page) -> list[str]:
    return page.locator("[data-testid=required-docs] li.dl-row").evaluate_all(
        "els => els.map(e => e.getAttribute('data-testid').replace(/^req-/, ''))")


def drawer_cases(page: Page) -> tuple[list[str], str]:
    page.locator(".touch-header .case-pill").click()
    expect(page.locator("[data-testid=drawer-my-cases] [data-testid=drawer-case]").first).to_be_visible(timeout=10000)
    mine = page.locator("[data-testid=drawer-my-cases] [data-testid=drawer-case]").evaluate_all(
        "els => els.map(e => e.getAttribute('data-case'))")
    head = page.locator(".drawer-panel .small.muted").first.inner_text()
    close_drawer(page)
    return mine, head


def close_drawer(page: Page) -> None:
    box = page.locator(".drawer").bounding_box()
    page.mouse.click(box["x"] + 20, box["y"] + box["height"] / 2)   # the backdrop beside the (RTL, right-hand) panel
    expect(page.locator(".drawer")).to_have_count(0)


def prepared_cases(page: Page) -> None:
    page.goto(f"{BASE}/customer")
    open_presenter(page)
    cards = page.locator("[data-testid=use-cases] article.uc:not(.uc-new)")      # the seventh card is the new-customer journey
    badges = page.locator("[data-testid=usecase-badge]").all_inner_texts()
    check("presenter: six use-case cards, TC-01…06 ↔ UC-01…06 in order", cards.count() == 6
          and all(b.startswith(f"TC-0{i} ↔ UC-0{i}") for i, b in enumerate(badges, 1)), " | ".join(badges))
    for u in USE_CASES:
        c = page.locator(f"[data-testid=usecase-{u['id']}]")
        if not c.locator("[data-testid=usecase-requirements]").count():
            c.locator("[data-testid=usecase-toggle]").click()
    files = sum(1 for u in USE_CASES for st in u["steps"] if not st["role"].startswith("banker"))
    check("presenter: every use-case card offers its pack's downloads (Round 2)",
          page.locator("[data-testid=use-cases] [data-testid=usecase-download]").count() == files, f"{files} files")
    for u in USE_CASES:
        page.locator(f"[data-testid=usecase-{u['id']}] [data-testid=usecase-toggle]").click()
    more = page.locator("[data-testid=more-tests]")
    check("the 15 earlier scenarios sit under a collapsed 'בדיקות נוספות'",
          more.get_attribute("open") is None and "בדיקות נוספות" in page.locator("[data-testid=more-tests-toggle]").inner_text())
    page.locator("[data-testid=more-tests-toggle]").click()
    page.locator("[data-testid=all-scenarios-toggle]").click()
    featured = page.locator("[data-testid=more-tests] [data-testid=featured-scenarios] article.feat").count()
    library = page.locator("[data-testid=all-scenarios] [data-testid^=scn-toggle-L-]").count()
    check("'בדיקות נוספות' holds the 4 featured and the 11 library scenarios", featured == 4 and library == 11,
          f"{featured} featured · {library} library")
    page.locator("[data-testid=all-scenarios-toggle]").click()
    page.locator("[data-testid=more-tests-toggle]").click()
    for u in USE_CASES:
        card = page.locator(f"[data-testid=usecase-{u['id']}]")
        card.scroll_into_view_if_needed()
        card.locator("[data-testid=usecase-open-case]").click()
        expect(page.locator(".touch-header .case-pill")).to_contain_text(u["caseDisplay"], timeout=20000)
        expect(page.locator("[data-testid=required-docs]")).to_be_visible()
        screen = page.locator("main.screen").inner_text()
        expected = [r["code"] for r in u["requirements"]]
        got = required_rows(page)
        check(f"{u['id']} opens case {u['caseDisplay']} with exactly the manifest checklist", sorted(got) == sorted(expected),
              f"app={got}")
        individual = u["useCaseId"] != "UC-06"
        check(f"{u['id']} documents omit the request profile card; income update is offered only for an individual",
              page.locator("[data-testid=document-profile]").count() == 0 and "פרופיל המסמכים של הבקשה" not in screen
              and "loan_policy@" not in screen and page.locator("[data-testid=profile-edit]").is_visible() == individual)
        if not card.locator("[data-testid=usecase-requirements]").count():
            card.locator("[data-testid=usecase-toggle]").click()
        card_codes = card.locator("[data-testid=usecase-req]").evaluate_all("els => els.map(e => e.getAttribute('data-code'))")
        check(f"{u['id']} presenter card lists the same requirements as the app", sorted(card_codes) == sorted(expected))
        human = [r["code"] for r in u["requirements"] if r["intake"] == "human_review"]
        app_human = page.locator("[data-testid=required-docs] li[data-intake=human_review]").evaluate_all(
            "els => els.map(e => e.getAttribute('data-testid').replace(/^req-/, ''))")
        check(f"{u['id']} documents without a rubric are marked for the banker's review", sorted(app_human) == sorted(human))
        page.locator("[data-testid=presenter-panel]").evaluate("e => e.scrollTop = 0")
        card.scroll_into_view_if_needed()
        shot(page, f"{u['id']}-{u['useCaseId']}")
    # "התיקים שלי" follows the demonstrated persona
    page.locator("[data-testid=usecase-TC-01] [data-testid=usecase-open-case]").click()
    expect(page.locator(".touch-header .case-pill")).to_contain_text("438839101", timeout=15000)
    expect(page.locator("[data-testid=required-docs]")).to_be_visible()
    page.locator("[data-testid=presenter-close]").click()
    mine, head = drawer_cases(page)
    check("'התיקים שלי' for מיכל ברק lists her two applications only (renovation 002 + car 101)",
          sorted(mine) == ["DEMO-MTZ-2026-002", "DEMO-MTZ-2026-101"] and "מיכל ברק" in head, f"{mine} · {head}")
    page.locator(".touch-header .case-pill").click()
    shot(page, "drawer-my-cases-barak")
    close_drawer(page)
    open_presenter(page)
    page.locator("[data-testid=usecase-TC-05] [data-testid=usecase-open-case]").click()
    expect(page.locator(".touch-header .case-pill")).to_contain_text("438839105", timeout=15000)
    expect(page.locator("[data-testid=required-docs]")).to_be_visible()
    page.locator("[data-testid=presenter-close]").click()
    mine, head = drawer_cases(page)
    check("switching the scenario switches the persona: 'התיקים שלי' for the Sterns lists case 105 only",
          mine == ["DEMO-MTZ-2026-105"] and "רועי שטרן" in head, f"{mine} · {head}")


def banker_views(page: Page) -> None:
    page.goto(f"{BASE}/banker?case=DEMO-MTZ-2026-105")
    names = page.locator("[data-testid=case-switch] .case-names")
    expect(names).to_contain_text("מאיה שטרן", timeout=20000)
    check("banker view of UC-05 names both borrowers and the profile", "רועי שטרן" in names.inner_text()
          and page.locator("[data-testid=banker-profile-label]").inner_text() == "שני לווים")
    shot(page, "banker-UC-05")
    page.goto(f"{BASE}/banker?case=DEMO-MTZ-2026-106")
    expect(page.locator("[data-testid=banker-assisted]")).to_be_visible(timeout=20000)
    check("banker view of UC-06 shows the company, its signatory and the banker-assisted marker",
          "ש.ג. מערכות מיזוג" in page.locator("[data-testid=case-switch] .case-names").inner_text()
          and "גלעד ששון" in page.locator("[data-testid=case-switch] .case-names").inner_text())
    shot(page, "banker-UC-06")


def human_review_upload(page: Page) -> None:
    page.goto(f"{BASE}/customer")
    open_presenter(page)
    card = page.locator("[data-testid=usecase-TC-06]")
    card.locator("[data-testid=usecase-open-case]").click()
    expect(page.locator(".touch-header .case-pill")).to_contain_text("438839106", timeout=15000)
    expect(page.locator("[data-testid=required-docs]")).to_be_visible()
    if not card.locator("[data-testid=usecase-requirements]").count():
        card.locator("[data-testid=usecase-toggle]").click()
    card.locator("[data-testid=usecase-reset]").click()
    card.locator("[data-testid=usecase-reset-confirm]").click()
    expect(card.get_by_text("התיק אופס")).to_be_visible(timeout=10000)
    page.locator("[data-testid=presenter-close]").click()
    row = page.locator("[data-testid='req-COMPANY_EXTRACT']")
    row.locator(".dl-head").click()
    check("a human-review row explains why it is needed and what else is accepted",
          "מספר החברה" in row.locator("[data-testid=req-why]").inner_text()
          and "נסח חברה מרשם החברות" in row.locator("[data-testid=req-alternatives]").inner_text())
    row.locator("[data-testid='upload-COMPANY_EXTRACT']").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet.locator("[data-testid=upload-human-review]")).to_be_visible()
    sheet.locator("[data-testid=file-input]").set_input_files(str(FIX.parent / "profile_set" / "company_extract_sg.pdf"))
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator("[data-testid=upload-stored]")).to_be_visible(timeout=15000)
    check("upload to a requirement without a rubric: stored for the banker, no AI verdict shown",
          sheet.locator("[data-testid=upload-stages]").count() == 0 and "לא סומן ״תקין״" in sheet.inner_text())
    shot(page, "human-review-upload")
    sheet.locator("[aria-label=סגירה]").click()
    expect(row).to_have_attribute("data-state", "received_pending_review", timeout=15000)
    check("the requirement reads 'received · awaiting the banker', the document card 'לבדיקת הבנקאי'",
          "ממתין לבדיקת הבנקאי" in row.inner_text() and page.locator("[data-testid=doc-human-review]").count() == 1)


def answer(page: Page, qid: str, value=None, *, name=None, multi=None) -> None:
    q = page.locator("[data-testid=onb-question]")
    expect(q).to_have_attribute("data-question", qid, timeout=10000)
    if name:
        page.locator("[data-testid=onb-first]").fill(name[0])
        page.locator("[data-testid=onb-last]").fill(name[1])
        page.locator("[data-testid=onb-send]").click()
    elif multi:
        for v in multi:
            page.locator(f"[data-testid=onb-option][data-value='{v}']").click()
        page.locator("[data-testid=onb-send]").click()
    elif qid in ("company_name", "national_id", "co_national_id", "signatory_id"):
        page.locator("[data-testid=onb-text]").fill(value)
        page.locator("[data-testid=onb-send]").click()
    else:
        page.locator(f"[data-testid=onb-option][data-value='{value}']").click()
    expect(page.locator(f"[data-testid=onb-answered-{qid}]")).to_be_visible(timeout=10000)


def start_application(page: Page) -> None:
    page.goto(f"{BASE}/customer")
    open_presenter(page)
    page.locator("[data-testid=presenter-new-application]").click()
    page.locator("[data-testid=presenter-close]").click()
    expect(page.locator("[data-testid=apply-chat]")).to_be_visible(timeout=15000)
    if page.locator("[data-testid=onb-restart]").count():
        page.locator("[data-testid=onb-restart]").click()
    expect(page.locator("[data-testid=onb-question]")).to_have_attribute("data-question", "entity", timeout=10000)


def summary_codes(page: Page) -> list[str]:
    expect(page.locator("[data-testid=onb-summary]")).to_be_visible(timeout=10000)
    page.wait_for_timeout(900)                                      # the screen scrolls smoothly to the summary
    return page.locator("[data-testid=onb-req]").evaluate_all("els => els.map(e => e.getAttribute('data-code'))")


def confirm_and_open(page: Page) -> str:
    before = page.evaluate("fetch('/api/session/demo/cases').then(r => r.json()).then(d => d.length)")
    # two clicks in the same tick, before React re-renders the button as busy: both requests reach the server
    page.locator("[data-testid=onb-confirm]").evaluate("b => { b.click(); b.click(); }")
    expect(page.locator("[data-testid=required-docs]")).to_be_visible(timeout=20000)
    after = page.evaluate("fetch('/api/session/demo/cases').then(r => r.json()).then(d => d.length)")
    check("confirming (clicked twice) creates exactly one case", after == before + 1, f"{before} → {after}")
    return page.locator(".touch-header .case-pill").inner_text()


def onboarding(page: Page) -> None:
    # salaried: the full flow, persisted, in "התיקים שלי"
    start_application(page)
    answer(page, "entity", "individual")
    answer(page, "name", name=("דנה", "רז"))
    answer(page, "national_id", "DEMO-ID-301")
    answer(page, "purpose", "car")
    answer(page, "income", multi=["salaried"])
    shot(page, "onboarding-questionnaire")
    answer(page, "net", 12000)
    answer(page, "co_borrower", "no")
    answer(page, "amount", 80000)
    answer(page, "payments", 60)
    codes = summary_codes(page)
    check("new salaried customer: the summary shows ID, payslips, statements and purpose proof",
          codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"], str(codes))
    page.locator("[data-testid=onb-summary]").scroll_into_view_if_needed()
    shot(page, "onboarding-summary-salaried")
    pill = confirm_and_open(page)
    check("the created case opens with its own documents checklist",
          sorted(required_rows(page)) == sorted(codes) and "רכישת רכב" in pill, pill)
    shot(page, "created-case-salaried")
    mine, head = drawer_cases(page)
    check("'התיקים שלי' shows the new customer's application (and nobody else's)", len(mine) == 1 and "דנה רז" in head,
          f"{mine} · {head}")
    page.reload()
    expect(page.locator("[data-testid=required-docs]")).to_be_visible(timeout=20000)
    check("the created case persists across a reload", sorted(required_rows(page)) == sorted(codes))
    # upload targets of a generated case feed the real review pipeline (REPLAY answer for this recorded file)
    row = page.locator("[data-testid='req-ID_CARD:BRW-A']")
    row.locator(".dl-head").click()
    row.locator("[data-testid='upload-ID_CARD:BRW-A']").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    sheet.locator("[data-testid=file-input]").set_input_files(str(FIX / "id_card_ido.pdf"))      # not דנה רז's: a real mismatch
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator("[data-testid=upload-stages]")).to_be_visible(timeout=10000)
    expect(sheet.get_by_text("לתוצאות הבדיקה")).to_be_visible(timeout=90000)
    check("generated case: an ID upload goes through the AI review pipeline and gets a result (REPLAY)", True,
          sheet.locator(".badge").first.inner_text())
    shot(page, "created-case-upload-reviewed")
    sheet.locator("[aria-label=סגירה]").click()

    # self-employed (VAT-exempt) → a different checklist; then a correction to mixed income before confirming
    start_application(page)
    answer(page, "entity", "individual")
    answer(page, "name", name=("עומר", "גל"))
    answer(page, "national_id", "DEMO-ID-302")
    answer(page, "purpose", "car")
    answer(page, "income", multi=["self_employed"])
    answer(page, "registration", "vat_exempt")
    answer(page, "net", 8000)
    answer(page, "co_borrower", "no")
    answer(page, "amount", 50000)
    answer(page, "payments", 48)
    codes = summary_codes(page)
    check("new self-employed (עוסק פטור) customer: tax evidence and VAT-exempt certificate, no payslips",
          {"TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= set(codes) and "PAYSLIPS:BRW-A" not in codes, str(codes))
    shot(page, "onboarding-summary-self-employed")
    page.locator("[data-testid=onb-edit-income]").click()
    answer(page, "income", multi=["salaried", "self_employed"])
    codes = summary_codes(page)
    check("correction to salaried + self-employed: payslips added, ID and statements still once",
          {"PAYSLIPS:BRW-A", "TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= set(codes)
          and codes.count("ID_CARD:BRW-A") == 1 and sum(c.startswith("BANK_STATEMENTS") for c in codes) == 1, str(codes))
    shot(page, "onboarding-summary-mixed")
    confirm_and_open(page)
    check("the mixed-income case is created with the corrected checklist", sorted(required_rows(page)) == sorted(codes))

    # joint applicants: each owns their requirements; one joint account
    start_application(page)
    answer(page, "entity", "individual")
    answer(page, "name", name=("ליאת", "כץ"))
    answer(page, "national_id", "DEMO-ID-303")
    answer(page, "purpose", "renovation")
    answer(page, "income", multi=["salaried"])
    answer(page, "net", 12000)
    answer(page, "co_borrower", "yes")
    answer(page, "co_name", name=("אבי", "כץ"))
    answer(page, "co_national_id", "DEMO-ID-304")
    answer(page, "co_income", multi=["self_employed"])
    answer(page, "co_registration", "vat_registered")
    answer(page, "co_net", 16000)
    answer(page, "accounts", "joint")
    answer(page, "amount", 120000)
    answer(page, "payments", 84)
    codes = summary_codes(page)
    owners = page.locator("[data-testid=onb-summary] .onb-owner .tiny.bold").all_inner_texts()
    check("joint applicants: payslips for ליאת, business documents for אבי, one statement for the joint account",
          {"PAYSLIPS:BRW-A", "TAX_ASSESSMENT:BRW-B", "VAT_DEALER_CERT:BRW-B", "PNL_STATEMENT:BRW-B"} <= set(codes)
          and "PAYSLIPS:BRW-B" not in codes and [c for c in codes if c.startswith("BANK_")] == ["BANK_STATEMENTS:ACC-1"]
          and "ליאת כץ" in owners and "אבי כץ" in owners, f"{codes} · {owners}")
    shot(page, "onboarding-summary-joint", full=True)

    # business financing: limited, banker-assisted
    start_application(page)
    answer(page, "entity", "company")
    answer(page, "company_name", "אלפא מערכות בע״מ")
    answer(page, "signatory", name=("רון", "לב"))
    answer(page, "signatory_id", "DEMO-ID-305")
    answer(page, "company_purpose", "business_equipment")
    answer(page, "business_amount", 300000)
    answer(page, "payments", 60)
    codes = summary_codes(page)
    check("business financing: company documents only, marked banker-assisted",
          page.locator("[data-testid=onb-banker-assisted]").is_visible() and "PAYSLIPS:BRW-A" not in codes
          and {"COMPANY_EXTRACT", "SIGNATORY_AUTHORITY", "COMPANY_FINANCIALS"} <= set(codes), str(codes))
    shot(page, "onboarding-summary-company")
    confirm_and_open(page)
    rows = required_rows(page)
    check("the company case opens on its document checklist, without an income-source editor",
          page.locator("[data-testid=profile-edit]").count() == 0 and "PAYSLIPS:BRW-A" not in rows
          and {"COMPANY_EXTRACT", "SIGNATORY_AUTHORITY", "COMPANY_FINANCIALS"} <= set(rows), str(rows))
    shot(page, "created-case-company")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL").new_page()
        for step in (prepared_cases, banker_views, human_review_upload, onboarding):
            try:
                step(page)
            except Exception as exc:
                check(f"{step.__name__} ran to the end", False, f"{type(exc).__name__}: {str(exc)[:400]}")
                shot(page, f"failure-{step.__name__}")
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    (OUT / "results.json").write_text(json.dumps([{"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS],
                                                 ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} document-profile checks passed · {BASE} · REPLAY")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
