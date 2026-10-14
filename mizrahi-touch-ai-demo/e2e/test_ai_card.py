"""Browser QA for the home-screen document-check card ("בדיקת מסמכים חכמה").

LEGACY (mortgage era, not yet adapted to loans): asserts the payslip-only mortgage cases and spends real Gemini
calls. Kept for reference and later adaptation; the loan journey is covered by e2e/test_loan_journey.py (REPLAY).
Never point it at :8791 (Mizrahi #2 main) or :8790 (Mizrahi #1): it uploads to cases and resets them.

Walks the card through real case states on an ISOLATED Mortgage Case Service: real uploads, real
Gemini reviews, real banker decisions. It records what the card says and where its buttons go. It
resets every case it touches, so point it only at a backend that has its own DATA_DIR.

    # from backend/: the service under test, and a second one whose Gemini calls always fail
    DATA_DIR=../e2e/artifacts/ai-card/data ./.venv/bin/python -m uvicorn app.main:app --port 8793
    DATA_DIR=../e2e/artifacts/ai-card/data-error GEMINI_MAX_CALLS_PER_HOUR=0 ./.venv/bin/python -m uvicorn app.main:app --port 8794
    # the customer app served against each of them
    node e2e/serve_frontend.mjs e2e/artifacts/ai-card/web 5841 http://127.0.0.1:8793
    node e2e/serve_frontend.mjs e2e/artifacts/ai-card/web-error 5842 http://127.0.0.1:8794

    CARD_QA_BASE=http://127.0.0.1:5841 CARD_QA_ERROR_BASE=http://127.0.0.1:5842 \
        backend/.venv/bin/python e2e/test_ai_card.py after

`before` only captures screenshots of the previous card. `after` also checks the title, the counts
against an independent oracle, the borrower rows and the destination of every button. `compare`
renders before/after sheets from the two captures.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from playwright.sync_api import Browser, Page, expect, sync_playwright
import demo_auth  # noqa: E402  (e2e/ is on sys.path when a suite runs as a script)

PHASE = sys.argv[1] if len(sys.argv) > 1 else "after"
AFTER = PHASE == "after"
BASE = os.environ.get("CARD_QA_BASE", "http://127.0.0.1:5841")
ERROR_BASE = os.environ.get("CARD_QA_ERROR_BASE", "")
demo_auth.install(BASE, ERROR_BASE)                   # the service has no anonymous access (see demo_auth.py)
MAIN, NEG, SINGLE, GOLDEN = "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-003", "DEMO-MTZ-2026-002", "DEMO-MTZ-2026-004"
ROOT = Path(__file__).resolve().parent
FIX = ROOT.parent / "fixtures" / "out"
ART = ROOT / "artifacts" / "ai-card"
OUT = ART / PHASE
CARD, TITLE = "[data-testid=ai-card]", "[data-testid=readiness-state]"
STAFF = {"X-Staff-Id": "STAFF-DANA"}
MONTHS_HE = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


# ---------------------------------------------------------------- backend helpers
def call(base: str, method: str, path: str, **kw) -> dict:
    r = httpx.request(method, f"{base}{path}", timeout=60, **kw)
    r.raise_for_status()
    return r.json()


def snap(base: str, case: str) -> dict:
    return call(base, "GET", f"/api/cases/{case}")


def upload(base: str, case: str, borrower: str, rel: str) -> dict:
    path = FIX / rel
    with path.open("rb") as fh:
        return call(base, "POST", f"/api/cases/{case}/documents",
                    files={"file": (path.name, fh, "application/pdf")}, data={"borrower_id": borrower})


def settle(base: str, case: str, timeout: int = 420) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap(base, case)
        if not s["readiness"]["pending_jobs"] and s["readiness"]["state"] not in ("CHECKING", "RECHECKING"):
            return s
        time.sleep(2)
    raise TimeoutError(f"{case} did not settle")


def requested_months(base: str) -> list[str]:
    """The requested salary months, derived here from the rubric policy and the simulation date."""
    sim = date.fromisoformat(call(base, "GET", "/api/health")["simulation_date"])
    policy = max((r for r in call(base, "GET", "/api/system/rubrics") if r["rubric_id"] == "income-set.salaried"),
                 key=lambda r: tuple(int(x) for x in r["version"].split(".")))["policy"]
    latest = sim.year * 12 + sim.month - 1 - (1 if sim.day >= policy["payday_day_of_next_month"] else 2)
    return [f"{(latest - i) // 12:04d}-{(latest - i) % 12 + 1:02d}" for i in reversed(range(policy["requested_months"]))]


def oracle_verified(base: str, case: str, months: list[str]) -> dict[str, int]:
    """Required months per borrower covered by a VALID payslip, from the raw document reviews only."""
    covered: dict[str, set[str]] = {}
    for d in call(base, "GET", f"/api/cases/{case}/documents"):
        r = d.get("review") or {}
        if r.get("verdict") == "VALID" and r.get("doc_type") == "payslip" and r.get("period") in months:
            covered.setdefault(d["borrower_id"], set()).add(r["period"])
    return {k: len(v) for k, v in covered.items()}


def borrowers(base: str, case: str) -> list[tuple[str, str]]:
    s = snap(base, case)
    names = {b["borrower_id"]: b["first_name_he"] for b in s["case"]["borrowers"]}
    return [(r["borrower_id"], names[r["borrower_id"]]) for r in s["readiness"]["requirements"] if r["evaluated_by_ai"]]


def next_upload_label(base: str, case: str) -> str:
    """The missing-documents button is the backend's first upload action that has a missing month (the assistant offers
    the same one); without one the card falls back to the documents list."""
    ups = [a for a in snap(base, case).get("available_actions") or [] if a["type"] == "NAVIGATE_TO_DOCUMENT_UPLOAD"]
    first = next((a for a in ups if a["params"]["missing_periods"]), ups[0] if ups else None)
    return first["label_he"] if first else "השלמת מסמכים"


def missing_title(base: str, case: str) -> str:
    """The missing-documents card is titled by the backend's next upload target: its borrower and missing month(s)."""
    s = snap(base, case)
    ups = [a for a in s.get("available_actions") or [] if a["type"] == "NAVIGATE_TO_DOCUMENT_UPLOAD"]
    a = next((x for x in ups if x["params"]["missing_periods"]), ups[0] if ups else None)
    months = a["params"]["missing_periods"] if a else []
    who = next((b["first_name_he"] for b in s["case"]["borrowers"] if a and b["borrower_id"] == a["params"]["borrower_id"]), "")
    return f"חסר תלוש {month_he(months[0])} של {who}" if len(months) == 1 else f"חסרים {len(months)} תלושים של {who}"


def month_he(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS_HE[int(m) - 1]} {y}"


# ---------------------------------------------------------------- browser helpers
def open_case(page: Page, base: str, case: str) -> None:
    page.goto(f"{base}/customer")
    page.evaluate(f"localStorage.setItem('mz.case', '{case}')")
    page.goto(f"{base}/customer")
    page.wait_for_selector(TITLE, timeout=20000)


def home(page: Page, base: str) -> None:
    page.goto(f"{base}/customer")
    page.wait_for_selector(TITLE, timeout=20000)


def sync(page: Page, base: str, case: str, timeout: int = 25000) -> dict:
    """Wait until the card reflects the backend's current state (the app polls every 1.2-4 s)."""
    r = snap(base, case)["readiness"]
    if AFTER:
        expect(page.locator(CARD)).to_have_attribute("data-status", r["customer_status"], timeout=timeout)
    else:
        expect(page.locator(TITLE)).to_have_text(r["state_he"], timeout=timeout)
    return r


def wait_ui(page: Page, after_statuses: tuple[str, ...], before_titles: tuple[str, ...], timeout: int = 25000) -> None:
    if AFTER:
        page.wait_for_function("([sel, ok]) => ok.includes(document.querySelector(sel)?.dataset.status)",
                               arg=[CARD, list(after_statuses)], timeout=timeout)
    else:
        page.wait_for_function("([sel, ok]) => ok.includes(document.querySelector(sel)?.innerText.trim())",
                               arg=[TITLE, list(before_titles)], timeout=timeout)


def shot(page: Page, name: str) -> None:
    card = page.locator(CARD)
    card.evaluate("el => el.scrollIntoView({ block: 'start' })")
    page.wait_for_timeout(700)
    card.screenshot(path=str(OUT / f"{name}.png"))
    page.locator(".phone").screenshot(path=str(OUT / f"{name}--phone.png"))


def mobile_shot(browser: Browser, base: str, case: str, name: str) -> None:
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="he-IL")
    page = ctx.new_page()
    open_case(page, base, case)
    page.locator(CARD).evaluate("el => el.scrollIntoView({ block: 'start' })")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / f"{name}--mobile.png"))
    ctx.close()


def card_rows(page: Page) -> list[tuple[str, str]]:
    loc = page.locator("[data-testid=card-borrower]")
    return [(loc.nth(i).locator(".who").inner_text().strip(), loc.nth(i).locator(".frac").inner_text().strip())
            for i in range(loc.count())]


def expect_card(page: Page, base: str, case: str, label: str, status: str, title: str, primary: str) -> dict:
    """Title, primary action, the total and per-borrower counts (against the oracle) and wording."""
    r = sync(page, base, case)
    if not AFTER:
        return r
    months = requested_months(base)
    people = borrowers(base, case)
    verified = oracle_verified(base, case, months)
    want_rows = [(name, f"{verified.get(bid, 0)}/{len(months)}") for bid, name in people]
    want_total = f"{sum(verified.get(bid, 0) for bid, _ in people)} מתוך {len(months) * len(people)}"
    total = page.locator("[data-testid=card-total]").inner_text().strip()
    text = page.locator(CARD).inner_text()
    banned = [w for w in ("אין פריטים שמחכים לכם", "GEMINI", "Gemini", "סטים", "טרם נבדק") if w in text]
    check(f"{label} · status {status}", r["customer_status"] == status, r["customer_status"])
    check(f"{label} · title", page.locator(TITLE).inner_text().strip() == title, page.locator(TITLE).inner_text().strip())
    check(f"{label} · total and borrower rows match the oracle", want_total in total and card_rows(page) == want_rows,
          f"total='{total}' rows={card_rows(page)} expected={want_total} {want_rows}")
    got = page.locator("[data-testid=card-primary]").inner_text().strip()
    check(f"{label} · primary action", got == primary, got)
    check(f"{label} · single primary action", page.locator(f"{CARD} .btn").count() == 1, str(page.locator(f"{CARD} .btn").count()))
    check(f"{label} · no misleading or technical wording", not banned, ", ".join(banned))
    return r


def primary_goes(page: Page, base: str, label: str, fragment: str) -> None:
    if not AFTER:
        return
    page.locator("[data-testid=card-primary]").click()
    try:
        page.wait_for_url(lambda u: fragment in u, timeout=10000)
        ok = True
    except Exception:
        ok = False
    check(f"{label} · primary action opens {fragment}", ok, page.url.replace(base, ""))
    home(page, base)


def secondary_prefills(page: Page, label: str, contains: str) -> None:
    if not AFTER:
        return
    page.locator("[data-testid=card-secondary]").click()
    box = page.locator("[data-testid=chat-input]")
    expect(box).to_be_visible(timeout=8000)
    value = box.input_value()
    check(f"{label} · secondary action opens the assistant with case context", contains in value, value)
    page.locator(".sheet-head button").click()
    expect(box).to_have_count(0)


# ---------------------------------------------------------------- journeys
def main_journey(browser: Browser) -> None:
    base = BASE
    for case in (MAIN, NEG, SINGLE, GOLDEN):
        call(base, "POST", f"/api/cases/{case}/reset")
    months = requested_months(base)
    ctx = browser.new_context(viewport={"width": 1366, "height": 940}, device_scale_factor=2, locale="he-IL")
    page = ctx.new_page()
    open_case(page, base, MAIN)

    # 1 · fresh case, nothing uploaded
    expect_card(page, base, MAIN, "1 fresh case", "AWAITING_UPLOAD", "ממתינים להעלאת תלושי שכר", "העלאת מסמכים")
    if AFTER:
        text = page.locator(CARD).inner_text()
        check("1 fresh case · explanation and required months", "יש להעלות את תלושי השכר הנדרשים" in text
              and all(MONTHS_HE[int(m.split("-")[1]) - 1] in text for m in months), text.replace("\n", " | ")[:160])
    shot(page, "01-fresh")
    mobile_shot(browser, base, MAIN, "01-fresh")

    # the primary action leads to the required-document upload; one real upload through that screen
    if AFTER:
        page.locator("[data-testid=card-primary]").click()
    else:
        page.get_by_role("button", name="למסמכים", exact=True).click()
    page.wait_for_url(lambda u: "/customer/documents" in u)
    if AFTER:
        req = page.locator("[data-testid='req-PAYSLIPS:BRW-A']")
        expect(req).to_contain_text(f"{month_he(months[0])} חסר", timeout=10000)
        check("1 fresh case · upload screen lists the required months before any review", True)
    page.locator("[data-testid=upload-BRW-A]").click()
    page.locator("[data-testid=file-input]").set_input_files(str(FIX / "main" / "ido_payslip_2026-07.pdf"))
    page.locator("[data-testid=upload-submit]").click()
    page.wait_for_selector("[data-testid=upload-stages]", timeout=20000)
    page.locator(".sheet-head button").click()
    home(page, base)

    # 5 · document awaiting / under Gemini review
    wait_ui(page, ("PROCESSING",), ("בבדיקה",))
    if AFTER:
        check("5 under review · title", page.locator(TITLE).inner_text().strip() == "בודקים את המסמכים שהעליתם",
              page.locator(TITLE).inner_text())
        check("5 under review · no all-clear while checking", "נמצאו תקינים" not in page.locator(CARD).inner_text())
    shot(page, "05-processing")
    if AFTER:
        expect(page.locator("[data-testid=card-primary]")).to_have_text("צפייה בהתקדמות")
        primary_goes(page, base, "5 under review", "/customer/documents/DOC-")

    # 2 · one correctly uploaded payslip
    settle(base, MAIN)
    expect_card(page, base, MAIN, "2 one payslip", "MISSING_DOCUMENTS", missing_title(base, MAIN), next_upload_label(base, MAIN))
    shot(page, "02-one-payslip")
    primary_goes(page, base, "2 one payslip", "/customer/documents")

    # 4 · a required month still missing (July and August uploaded)
    upload(base, MAIN, "BRW-A", "main/ido_payslip_2026-08.pdf")
    settle(base, MAIN)
    expect_card(page, base, MAIN, "4 missing month", "MISSING_DOCUMENTS", missing_title(base, MAIN), next_upload_label(base, MAIN))
    if AFTER:
        row = page.locator("[data-testid=card-borrower][data-borrower=BRW-A]").inner_text()
        check("4 missing month · borrower row names the missing month", MONTHS_HE[int(months[-1].split('-')[1]) - 1] in row, row)
    shot(page, "04-missing-month")

    # 3 · duplicate month: the file named 09 prints August, plus a byte-identical re-upload
    upload(base, MAIN, "BRW-A", "main/ido_payslip_2026-09.pdf")
    settle(base, MAIN)
    expect_card(page, base, MAIN, "3 duplicate month", "MISSING_DOCUMENTS", missing_title(base, MAIN), next_upload_label(base, MAIN))
    again = upload(base, MAIN, "BRW-A", "main/ido_payslip_2026-08.pdf")
    check("3 duplicate month · identical re-upload is not a new document", again["created"] is False, str(again.get("note")))
    if AFTER:
        sync(page, base, MAIN)
        row = page.locator("[data-testid=card-borrower][data-borrower=BRW-A]").inner_text()
        check("3 duplicate month · duplicate August not counted twice", f"2/{len(months)}" in row, row)
        check("3 duplicate month · explanation mentions the duplicate", "כפול" in page.locator(CARD).inner_text())
    shot(page, "03-duplicate")

    # Noa's three payslips: her set completes while Ido's September is still missing
    for rel in ("main/noa_payslip_2026-07_scan.pdf", "main/noa_payslip_2026-08.pdf", "main/noa_payslip_2026-09.pdf"):
        upload(base, MAIN, "BRW-B", rel)
    settle(base, MAIN)
    expect_card(page, base, MAIN, "mixed · customer action outranks banker review", "MISSING_DOCUMENTS",
                missing_title(base, MAIN), next_upload_label(base, MAIN))
    shot(page, "05b-mixed")

    # 7 · correction uploaded and re-validation running
    upload(base, MAIN, "BRW-A", "main/ido_payslip_2026-09_corrected.pdf")
    wait_ui(page, ("REVALIDATING",), ("בבדיקה חוזרת",))
    if AFTER:
        check("7 revalidation · title", page.locator(TITLE).inner_text().strip() == "בודקים מחדש את המסמכים",
              page.locator(TITLE).inner_text())
        expect(page.locator("[data-testid=card-primary]")).to_have_text("צפייה בבדיקה")
    shot(page, "07-revalidation")

    # 8 + 9 · every required month covered, the income variance waits for the banker
    s = settle(base, MAIN)
    verified = oracle_verified(base, MAIN, months)
    complete = all(verified.get(bid, 0) == len(months) for bid, _ in borrowers(base, MAIN))
    banker = [f for f in s["findings"] if f["status"] == "open" and f["review_state"] == "NEEDS_BANKER_REVIEW"]
    expect_card(page, base, MAIN, "8-9 covered, banker review", "BANKER_REVIEW",
                "תלושי השכר הושלמו · נדרש בירור בנקאי" if complete else "כל התלושים התקבלו · חלקם בבדיקה בנקאית",
                "צפייה בממצא" if len(banker) == 1 else "צפייה בממצאים")
    shot(page, "08-covered-banker-review")
    if AFTER:
        page.locator("[data-testid=card-primary]").click()
        detail = page.locator("[data-testid=card-detail]")
        expect(detail).to_be_visible()
        check("9 banker review · primary action shows the outstanding finding",
              all(f["title_he"] in detail.inner_text() for f in banker), detail.inner_text().replace("\n", " | ")[:160])
        shot(page, "09-banker-finding-open")
        page.locator("[data-testid=card-primary]").click()
        expect(detail).to_have_count(0)
        secondary_prefills(page, "9 banker review", s["case"]["banker"]["name_he"])

    # all in-scope checks complete: the banker accepts the explanation
    for f in banker:
        call(base, "POST", f"/api/banker/cases/{MAIN}/findings/{f['finding_id']}/decision",
             json={"action": "accept_explanation", "rationale": "QA: ההסבר התקבל"}, headers=STAFF)
    expect_card(page, base, MAIN, "all checks complete", "CHECKS_COMPLETE" if complete else "BANKER_REVIEW",
                "בדיקת תלושי השכר הושלמה" if complete else "כל התלושים התקבלו · חלקם בבדיקה בנקאית",
                "צפייה בסיכום" if complete else "צפייה במסמכים")
    if AFTER:
        text = page.locator(CARD).inner_text()
        check("all checks complete · never claims mortgage approval", "אושרה" not in text and "המשכנתא אושר" not in text)
    shot(page, "11-checks-complete")
    primary_goes(page, base, "all checks complete", "/customer/documents")

    # the banker confirms the preparation (a document-preparation step, not a credit decision)
    call(base, "POST", f"/api/banker/cases/{MAIN}/confirm-preparation", json={"note": "QA"}, headers=STAFF)
    expect_card(page, base, MAIN, "banker confirmed", "PREPARATION_CONFIRMED", "הכנת תלושי השכר אושרה", "צפייה בסיכום")
    if AFTER:
        check("banker confirmed · says it is not a mortgage decision", "אינה החלטה על המשכנתא" in page.locator(CARD).inner_text())
    shot(page, "12-confirmed")

    # 10b · the API stops answering while the page is open, and on a cold load
    page.route("**/api/**", lambda route: route.abort())
    if AFTER:
        expect(page.locator("[data-testid=card-stale]")).to_be_visible(timeout=15000)
        check("10b API unreachable · card flags stale data instead of a silent status", True)
    else:
        page.wait_for_timeout(9000)
    shot(page, "10b-api-unreachable")
    cold = ctx.new_page()
    cold.route("**/api/**", lambda route: route.abort())
    cold.goto(f"{base}/customer")
    cold.wait_for_timeout(5000)
    if AFTER:
        expect(cold.get_by_text("לא הצלחנו לטעון את התיק")).to_be_visible()
        check("10b API unreachable · cold load shows an error with a retry, not an endless spinner", True)
    cold.locator(".phone").screenshot(path=str(OUT / "10c-api-unreachable-cold--phone.png"))
    cold.close()
    page.unroute("**/api/**")
    if AFTER:
        expect(page.locator("[data-testid=card-stale]")).to_have_count(0, timeout=15000)
        check("10b API unreachable · notice clears when the API answers again", True)

    # 6 · QA case: an unreadable scan and another borrower's payslip, both uploaded for Ido
    open_case(page, base, NEG)
    upload(base, NEG, "BRW-A", "negative/ido_payslip_unreadable.pdf")
    upload(base, NEG, "BRW-A", "negative/noa_payslip_2026-08_uploaded_as_ido.pdf")
    settle(base, NEG)
    expect_card(page, base, NEG, "6 invalid documents", "CORRECTION_REQUIRED", "נמצאו מסמכים שדורשים תיקון", "צפייה בממצאים")
    shot(page, "06-invalid")
    primary_goes(page, base, "6 invalid documents", "/customer/documents")
    secondary_prefills(page, "6 invalid documents", "לתקן")

    # counts and names come from each case: one borrower (002), the presenter case (004)
    open_case(page, base, SINGLE)
    expect_card(page, base, SINGLE, "single-borrower case", "AWAITING_UPLOAD", "ממתינים להעלאת תלושי שכר", "העלאת מסמכים")
    shot(page, "13-single-borrower")
    open_case(page, base, GOLDEN)
    expect_card(page, base, GOLDEN, "presenter case 004", "AWAITING_UPLOAD", "ממתינים להעלאת תלושי שכר", "העלאת מסמכים")
    shot(page, "14-case-004")

    # neighbouring screens still render from the same state
    if AFTER:
        page.goto(f"{base}/banker")
        expect(page.locator("[data-testid=banker-readiness]")).to_be_visible(timeout=20000)
        page.goto(f"{base}/customer/stages")
        expect(page.locator(".stage-item.now")).to_have_count(1, timeout=15000)
        check("banker console and stages page render", True)
    open_case(page, base, MAIN)
    ctx.close()


def error_journey(browser: Browser) -> None:
    base = ERROR_BASE
    call(base, "POST", f"/api/cases/{MAIN}/reset")
    ctx = browser.new_context(viewport={"width": 1366, "height": 940}, device_scale_factor=2, locale="he-IL")
    page = ctx.new_page()
    open_case(page, base, MAIN)
    doc = upload(base, MAIN, "BRW-A", "main/ido_payslip_2026-07.pdf")["document"]

    def failed() -> None:
        end = time.time() + 120
        while time.time() < end:
            if call(base, "GET", f"/api/documents/{doc['document_id']}")["status"] == "failed":
                return
            time.sleep(1.5)
        raise TimeoutError("document did not fail")

    failed()
    settle(base, MAIN)
    expect_card(page, base, MAIN, "10 processing error", "ERROR", "לא הצלחנו להשלים את הבדיקה", "ניסיון חוזר")
    shot(page, "10-error")
    if AFTER:
        runs_before = len(call(base, "GET", f"/api/documents/{doc['document_id']}")["runs"])
        page.locator("[data-testid=card-primary]").click()
        wait_ui(page, ("PROCESSING", "REVALIDATING"), ())
        check("10 processing error · retry puts the card back into checking", True)
        failed()
        settle(base, MAIN)
        runs_after = len(call(base, "GET", f"/api/documents/{doc['document_id']}")["runs"])
        check("10 processing error · retry ran a new review in the backend", runs_after > runs_before,
              f"runs {runs_before} → {runs_after}")
        sync(page, base, MAIN)
        check("10 processing error · a retry that fails again returns to the error state",
              page.locator(CARD).get_attribute("data-status") == "ERROR")
        secondary_prefills(page, "10 processing error", "לא הושלמה")
    ctx.close()


def compare() -> None:
    names = sorted(p.stem for p in (ART / "after").glob("*.png") if "--" not in p.stem)

    def img(path: Path) -> str:
        return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}" if path.exists() else ""

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=1)
        for name in names:
            before, after = img(ART / "before" / f"{name}.png"), img(ART / "after" / f"{name}.png")
            page.set_content(f"""<html dir="rtl"><body style="margin:0;font-family:Arial;background:#e9ebef;padding:24px">
              <div dir="ltr" style="font:700 18px Arial;color:#263040;margin-bottom:14px;text-align:right">{name}</div>
              <div style="display:flex;gap:24px;align-items:flex-start">
                <figure style="margin:0;flex:1"><figcaption style="font:700 14px Arial;margin-bottom:8px">לפני</figcaption>
                  {'<img style="width:100%" src="' + before + '">' if before else '<div>—</div>'}</figure>
                <figure style="margin:0;flex:1"><figcaption style="font:700 14px Arial;margin-bottom:8px">אחרי</figcaption>
                  <img style="width:100%" src="{after}"></figure></div></body></html>""")
            page.wait_for_timeout(150)
            page.screenshot(path=str(ART / f"compare-{name}.png"), full_page=True)
        browser.close()
    print("compare sheets in", ART)


def main() -> int:
    if PHASE == "compare":
        compare()
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        main_journey(browser)
        if ERROR_BASE:
            error_journey(browser)
        browser.close()
    failed = [r for r in RESULTS if not r["pass"]]
    if AFTER:
        print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    (OUT / "results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
