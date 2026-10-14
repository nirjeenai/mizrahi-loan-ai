"""Personal-loan journey end to end in a real Chrome, against a REPLAY backend (zero Gemini calls).

Every model answer comes from e2e/replay/recordings.json — RECORDED_LIVE answers of the live Gemini review of these exact
files (2026-10-14), looked up by SHA-256. Evidence verification against each PDF, the deterministic family checks, the
case review, findings, readiness, the banker desk and the presenter pane are the production code. Resets the executive
demo cases (006–011) via "התחל דמו חדש" and nothing else.

    # from backend/ — fresh DATA_DIR every run
    .venv/bin/python ../e2e/replay_backend.py --port 8792 --data ../e2e/artifacts/loan/data-replay
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/loan/web-replay 5843 http://127.0.0.1:8792
    LOAN_E2E_BASE=http://127.0.0.1:5843 LOAN_DATA=e2e/artifacts/loan/data-replay backend/.venv/bin/python e2e/test_loan_journey.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("LOAN_E2E_BASE", "http://127.0.0.1:5843")
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("LOAN_DATA", ROOT / "artifacts" / "loan" / "data-replay")).resolve()
ART = ROOT / "artifacts" / "loan"
SHOTS = ART / "screens"
MANIFEST = json.loads((ROOT.parent / "fixtures" / "presenter" / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
DOCS = {d["id"]: d for d in MANIFEST["documents"]}
FEATURED = {f["outcome"]: f for f in MANIFEST["featured"]}
JOURNEY, BLOCKER, PASS = "DEMO-MTZ-2026-009", "DEMO-MTZ-2026-008", "DEMO-MTZ-2026-006"
ID, PAY, BANK, PURPOSE = "ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"
MORTGAGE = re.compile(r"משכנת|נכס|דירה יד שנייה|מומחי משכנתאות")
RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


api = httpx.Client(base_url=BASE, timeout=60)


def sessions() -> None:
    for case in (JOURNEY, BLOCKER, PASS):
        api.post("/api/session/demo/customer", json={"case_id": case}).raise_for_status()
    api.post("/api/session/demo/staff", json={"staff_id": "STAFF-DANA"}).raise_for_status()


def snap(case: str) -> dict:
    r = api.get(f"/api/cases/{case}")
    r.raise_for_status()
    return r.json()


def ws(case: str) -> dict:
    r = api.get(f"/api/banker/cases/{case}/workspace")
    r.raise_for_status()
    return r.json()


def settle(case: str, documents: int, timeout: float = 120) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap(case)
        c = s["readiness"]["counts"]
        if c["documents"] >= documents and not s["readiness"]["pending_jobs"] and c["processing"] == 0 and s["case_review"]:
            return s
        time.sleep(0.8)
    raise TimeoutError(f"{case} did not settle")


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    try:
        if page.locator("[data-testid=evidence-viewer]").count():
            expect(page.locator("[data-testid=evidence-viewer].loading")).to_have_count(0, timeout=10000)
    except AssertionError:
        pass
    page.wait_for_timeout(350)
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def card(page: Page, route: str):
    return page.locator(f"[data-testid=featured-{route}]")


def show_presenter(page: Page) -> None:
    """The presenter starts collapsed on every page load; its toggle opens it beside the app."""
    if page.locator(".hub").get_attribute("data-presenter") != "open":
        page.locator("[data-testid=presenter-toggle]").click()
    expect(page.locator(".hub-side")).to_be_visible()
    # the four featured cards now sit under "בדיקות נוספות", after the six use cases
    if page.locator("[data-testid=more-tests]").get_attribute("open") is None:
        page.locator("[data-testid=more-tests-toggle]").click()


def download(page: Page, route: str) -> dict[str, Path]:
    show_presenter(page)
    out = {}
    links = card(page, route).locator("[data-testid=featured-download]")
    for i in range(links.count()):
        doc_id = links.nth(i).get_attribute("data-doc-id")
        with page.expect_download() as dl:
            links.nth(i).click()
        target = ART / "downloads" / dl.value.suggested_filename
        target.parent.mkdir(parents=True, exist_ok=True)
        dl.value.save_as(str(target))
        out[doc_id] = target
    return out


def open_case(page: Page, route: str) -> None:
    show_presenter(page)
    card(page, route).locator("[data-testid=featured-open-case]").click()
    expect(page.locator(".case-pill")).to_contain_text(FEATURED[route]["caseDisplay"], timeout=15000)
    expect(page.locator("[data-testid=ai-card]")).to_be_visible(timeout=15000)


def upload(page: Page, code: str, path: Path, period: str | None = None) -> str:
    """Through the requirement's own card on the Documents screen; returns the upload's final message."""
    page.goto(f"{BASE}/customer/documents")
    row = page.locator(f"[data-testid='req-{code}']")
    expect(row).to_be_visible(timeout=15000)
    button = page.locator("[data-testid=upload-BRW-A]") if code.startswith("PAYSLIPS") else row.locator(f"[data-testid='upload-{code}']")
    if not button.count():
        row.locator(".dl-head").click()
    button.first.click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible()
    if period:
        chip = sheet.locator(f".mchip[data-period='{period}']")
        if chip.count() and chip.get_attribute("aria-checked") != "true":
            chip.click()
    sheet.locator("[data-testid=file-input]").set_input_files(str(path))
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator(".doc-name")).to_have_text(path.name, timeout=15000)
    expect(sheet.locator("[data-testid=upload-outcome]")).to_be_visible(timeout=90000)
    message = sheet.locator(".outcome-msg").inner_text()
    sheet.locator("button[aria-label='סגירה']").click()
    return message


def home(page: Page) -> None:
    page.goto(f"{BASE}/customer")
    expect(page.locator("[data-testid=ai-card]")).to_be_visible(timeout=15000)


def boxes(page: Page, selector: str, n: int = 1) -> bool:
    """Evidence boxes are drawn once the page image has loaded; wait for them."""
    try:
        expect(page.locator(selector)).to_have_count(n, timeout=15000)
        return True
    except AssertionError:
        return False


def doc_id(case: str, filename: str) -> str:
    return next(d["document_id"] for d in api.get(f"/api/cases/{case}/documents").json() if d["filename"] == filename)


def run(page: Page, banker: Page) -> None:
    page.goto(f"{BASE}/customer")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    check("presenter: collapsed on load, the app centred in the window",
          page.locator(".hub").get_attribute("data-presenter") == "closed" and not page.locator(".hub-side").is_visible()
          and page.evaluate("(() => { const b = document.querySelector('.phone').getBoundingClientRect(); "
                            "return Math.abs((b.left + b.right) / 2 - innerWidth / 2) <= 1; })()"))
    show_presenter(page)
    expect(page.locator("[data-testid=featured-scenarios]")).to_be_visible(timeout=20000)

    # ------------------------------------------------------------ the presenter pane, adapted to loans
    cards = page.locator("[data-testid=featured-scenarios] article.feat")
    order = [cards.nth(i).get_attribute("data-testid") for i in range(cards.count())]
    check("presenter: four featured loan scenarios, PASS · REVIEW · BLOCKER · CORRECTION",
          order == ["featured-PASS", "featured-REVIEW", "featured-BLOCKER", "featured-CORRECTION"], str(order))
    complete = True
    for route, f in FEATURED.items():
        c = card(page, route)
        text = c.inner_text()
        complete &= all(x in text for x in (f["titleHe"], f["checksHe"], f["expectHe"], f["expectedLabelHe"], f["caseDisplay"], f["borrowerHe"]))
        complete &= c.locator("[data-testid=featured-download]").count() == len({s["file"] for s in f["steps"]})
        complete &= c.locator("[data-testid=featured-playbook]").count() == 0          # playbook collapsed by default
    check("presenter: each card shows title, what is checked, what is expected, files, borrower + case, expected label", complete)
    side = page.locator(".hub-side")
    check("presenter: split screen kept — presenter pane left, live app right, no horizontal scroll",
          page.locator(".phone").bounding_box()["x"] >= side.bounding_box()["x"] + side.bounding_box()["width"] - 1
          and side.evaluate("e => e.scrollWidth <= e.clientWidth"))
    bundle = httpx.get(f"{BASE}/api/presenter/scenarios", timeout=60).json()
    all_scn = page.locator("[data-testid=all-scenarios]")
    check("presenter: the test-case library keeps its infrastructure — 11 loan scenarios, 25 checksum-verified files, engine rubrics",
          all_scn.locator("[data-testid^=scn-toggle-L-]").count() == 11 and len(bundle["files"]) == 25
          and all(f["sha256_matches_manifest"] for f in bundle["files"].values())
          and {r["rubric_id"] for r in bundle["rubrics"]} >= {"id_document.il", "bank_statement.il", "purpose_proof.il"})
    side = page.locator(".hub-side").inner_text()
    check("presenter: no mortgage wording left in the side pane", not MORTGAGE.search(side), (MORTGAGE.search(side) or [""])[0])
    shot(page, "01-presenter")

    page.locator("[data-testid=new-demo-button]").click()
    page.locator("[data-testid=new-demo-confirm]").click()
    expect(page.locator("[data-testid=new-demo-status]")).to_contain_text("הדמו מוכן", timeout=30000)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("ממתינים למסמכים לבקשת ההלוואה", timeout=15000)
    sessions()
    check("'התחל דמו חדש' empties the loan demo cases and opens the first use case (TC-01, 438839101)",
          all(snap(c)["readiness"]["counts"]["documents"] == 0 for c in (PASS, JOURNEY, BLOCKER))
          and "438839101" in page.locator(".case-pill").inner_text())
    shot(page, "02-new-demo-home")

    # ------------------------------------------------------------ the journey: customer upload → AI validation → finding
    files = download(page, "CORRECTION")
    check("journey: the downloads are the manifest's exact files (SHA-256)",
          all(hashlib.sha256(p.read_bytes()).hexdigest() == DOCS[i]["sha256"] for i, p in files.items()))
    open_case(page, "CORRECTION")
    page.goto(f"{BASE}/customer/documents")
    expect(page.locator(f"[data-testid='req-{PURPOSE}']")).to_be_visible(timeout=15000)
    rows = [page.locator(f"[data-testid='req-{c}']").count() for c in (ID, PAY, BANK, PURPOSE)]
    check("documents screen lists the four loan requirements of the pinned policy", rows == [1, 1, 1, 1], str(rows))
    shot(page, "03-documents-empty")
    upload(page, ID, files["loan/id_card_ido.pdf"])
    upload(page, PAY, files["01_INITIAL_UPLOADS/ido_2026_07.pdf"], "2026-07")
    upload(page, PAY, files["01_INITIAL_UPLOADS/ido_2026_08.pdf"], "2026-08")
    wrong = upload(page, PAY, files["01_INITIAL_UPLOADS/ido_2026_09.pdf"], "2026-09")
    check("AI validation: the September upload is read as an August payslip, said in the customer's words",
          "מודפס בו אוגוסט 2026, ולא ספטמבר 2026" in wrong, wrong)
    upload(page, BANK, files["loan/statement_ido_2026-07_09.pdf"])
    upload(page, PURPOSE, files["loan/car_quote_ido.pdf"])
    s = settle(JOURNEY, 6)
    req = {r["code"]: r for r in s["readiness"]["requirements"]}
    open_codes = sorted({f["code"] for f in s["findings"] if f["status"] == "open"})
    check("document findings: September missing, August duplicated, file name vs printed month — ID, statement and proof satisfied",
          req[PAY]["missing"] == ["2026-09"] and {"REQUIRED_PERIOD_MISSING", "DUPLICATE_PERIOD", "FILE_NAME_PERIOD_MISMATCH"} <= set(open_codes)
          and all(req[c]["ai_state"] == "extracted" for c in (ID, BANK, PURPOSE))
          and s["readiness"]["progress"] == {"done": 3, "total": 4, "missing_units": 1}, json.dumps(open_codes))
    wrong_id = doc_id(JOURNEY, files["01_INITIAL_UPLOADS/ido_2026_09.pdf"].name)
    wrong_doc = api.get(f"/api/documents/{wrong_id}").json()
    facts = {f["field"]: f for f in wrong_doc["review"]["facts"]}
    check("evidence: the printed month and the identity are verified against the PDF text layer (no invented identity mismatch)",
          wrong_doc["review"]["verdict"] == "VALID" and wrong_doc["review"]["period"] == "2026-08"
          and facts["salary_period"]["evidence"]["witness"] == "text_layer_exact"
          and facts["employee_id"]["evidence"]["witness"] == "text_layer_exact"
          and "BORROWER_MISMATCH" not in wrong_doc["review"]["verdict_reason_codes"]
          and wrong_doc["review"]["identity"]["models"]["extract"] == "replay-recorded")
    home(page)
    expect(page.locator("[data-testid=readiness-state]")).to_contain_text("חסר תלוש ספטמבר 2026 של עידו", timeout=15000)
    check("customer home: the next action is the missing September payslip; 3 of 4 requirements done",
          "3 מתוך 4" in page.locator("[data-testid=card-total]").inner_text())
    shot(page, "04-journey-home-missing")
    page.goto(f"{BASE}/customer/documents/{wrong_id}")
    expect(page.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=15000)
    expect(page.locator("[data-testid=evidence-viewer]:not(.loading)")).to_be_visible(timeout=15000)
    check("customer document page: the original page with evidence boxes", page.locator("[data-testid=evidence-viewer] .hl").count() > 3)
    shot(page, "05-journey-document")

    # ------------------------------------------------------------ banker review → evidence inspection
    banker.goto(f"{BASE}/banker?case={JOURNEY}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    w = ws(JOURNEY)
    banker.locator("[data-testid=coverage-toggle]").click()
    matrix = banker.locator("[data-testid=requirement-row]")
    states = {matrix.nth(i).get_attribute("data-code"): matrix.nth(i).get_attribute("data-state") for i in range(matrix.count())}
    check("banker: the requirement matrix shows the pinned policy's four requirements and their AI states",
          states == {ID: "extracted", PAY: "needs_customer_action", BANK: "extracted", PURPOSE: "extracted"}, json.dumps(states))
    shot(banker, "06-banker-matrix")
    id_doc = doc_id(JOURNEY, "id_card_ido.pdf")
    banker.locator(f"[data-item-id='doc:{id_doc}']").click()
    expect(banker.locator("[data-testid=evidence-title]")).to_contain_text("תעודת זהות", timeout=10000)
    kf = banker.locator("[data-testid=key-field][data-field=holder_id]")
    expect(banker.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=15000)
    check("banker evidence (ID card): the identity number is a verified key field with a box on the original page",
          "✓" in kf.inner_text() and boxes(banker, ".hl[data-field=holder_id]"))
    banker.locator("[data-testid=key-field][data-field=holder_name]").click()
    expect(banker.locator(".hl.focus[data-field=holder_name]")).to_have_count(1, timeout=5000)
    original = api.get(f"/api/documents/{id_doc}/file")
    check("banker: the original document opens (application/pdf)",
          original.status_code == 200 and original.headers["content-type"].startswith("application/pdf"))
    shot(banker, "07-banker-evidence-id")
    st_doc = doc_id(JOURNEY, "statement_ido_2026-07_09.pdf")
    banker.locator(f"[data-item-id='doc:{st_doc}']").click()
    expect(banker.locator("[data-testid=evidence-title]")).to_contain_text("דף", timeout=10000)
    expect(banker.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=15000)
    check("banker evidence (bank statement): the period end is focused and boxed on the page",
          boxes(banker, ".hl.focus[data-field=statement_to]")
          and "✓" in banker.locator("[data-testid=key-field][data-field=statement_from]").inner_text())
    shot(banker, "08-banker-evidence-statement")
    q_doc = doc_id(JOURNEY, "car_quote_ido.pdf")
    banker.locator(f"[data-item-id='doc:{q_doc}']").click()
    expect(banker.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=15000)
    check("banker evidence (proof of purpose): the amount is verified and boxed",
          boxes(banker, ".hl[data-field=total_amount]")
          and "✓" in banker.locator("[data-testid=key-field][data-field=total_amount]").inner_text())
    banker.locator(f"[data-item-id='doc:{wrong_id}']").click()
    expect(banker.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=15000)
    check("banker evidence (wrong month): opens on the printed month, marks 'uploaded for September'",
          boxes(banker, ".hl.focus[data-field=salary_period]")
          and "ספטמבר 2026" in banker.locator(".ev-meta").inner_text())
    shot(banker, "09-banker-evidence-wrong-month")
    banker.locator("[data-testid=queue-group-missing] .queue-group-head").click()
    banker.locator("[data-item-id='missing:BRW-A:2026-09']").click()
    expect(banker.locator("[data-testid=missing-title]")).to_contain_text("ספטמבר 2026", timeout=10000)
    banker.locator("[data-testid=action-request-missing]").click()
    banker.locator("[data-testid=preview-request]").click()
    banker.locator("[data-testid=send-request]").click()
    expect(banker.locator("[data-testid=missing-status]")).to_contain_text("נשלחה בקשה", timeout=15000)
    check("banker: requests the missing September payslip from the customer (in-app request)",
          any(q["status"] == "OPEN" and q["period"] == "2026-09" for q in snap(JOURNEY)["customer_requests"]))
    shot(banker, "10-banker-request")

    # ------------------------------------------------------------ document correction by the customer
    home(page)
    expect(page.locator("[data-testid=card-request-message]")).to_be_visible(timeout=15000)
    shot(page, "11-customer-request")
    page.locator("[data-testid=card-primary]").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet.locator("[data-testid=upload-for-request]")).to_be_visible(timeout=15000)
    sheet.locator("[data-testid=file-input]").set_input_files(str(files["02_CORRECTION/ido_2026_09_CORRECTED.pdf"]))
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator("[data-testid=upload-answered]")).to_be_visible(timeout=15000)
    expect(sheet.locator("[data-testid=upload-outcome]")).to_be_visible(timeout=90000)
    sheet.locator("button[aria-label='סגירה']").click()
    s = settle(JOURNEY, 7)
    check("correction: the September payslip answers the banker's request and completes the package — READY_FOR_BANKER",
          s["readiness"]["case_status"] == "READY_FOR_BANKER" and s["readiness"]["progress"]["done"] == 4
          and not [f for f in s["findings"] if f["status"] == "open" and f["review_state"] == "CUSTOMER_ACTION_REQUIRED"]
          and any(q["status"] == "RESPONDED" and q["period"] == "2026-09" for q in s["customer_requests"]),
          s["readiness"]["case_status"])
    home(page)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("כל המסמכים הנדרשים הושלמו", timeout=15000)
    body = page.locator("[data-testid=ai-card]").inner_text()
    check("customer home: complete, and explicitly not a loan decision", "אינה החלטה על ההלוואה" in body)
    shot(page, "12-journey-complete")
    banker.reload()
    expect(banker.locator("[data-testid=requirements-progress]")).to_contain_text("4/4", timeout=20000)
    check("banker: 4/4 requirements · 'ready for your review — not a credit decision'",
          "לא החלטת אשראי" in banker.locator("[data-testid=requirements-progress]").inner_text())
    shot(banker, "13-banker-ready")

    # ------------------------------------------------------------ wrong document type → replacement (case 008)
    files_b = download(page, "BLOCKER")
    open_case(page, "BLOCKER")
    upload(page, ID, files_b["01_INITIAL_UPLOADS/ido_2026_07.pdf"])
    s = settle(BLOCKER, 1)
    bad = doc_id(BLOCKER, "ido_2026_07.pdf")
    f = next((x for x in s["findings"] if x["status"] == "open" and x["document_id"] == bad), {})
    check("wrong type: a payslip in the ID card is classified by the AI itself and sent back ('המסמך אינו תעודת זהות')",
          f.get("code") == "UNEXPECTED_DOCUMENT_TYPE" and f.get("title_he") == "המסמך אינו תעודת זהות"
          and s["outcomes"]["documents"][bad]["outcome"] == "BLOCKER"
          and {r["code"]: r for r in s["readiness"]["requirements"]}[PAY]["documents"] == 0, json.dumps(f, ensure_ascii=False)[:200])
    home(page)
    expect(page.locator("[data-testid=card-primary]")).to_have_text(re.compile("העלאת מסמך חלופי"), timeout=15000)
    shot(page, "14-blocker-home")
    banker.goto(f"{BASE}/banker?case={BLOCKER}")
    banker.locator(f"[data-item-id='doc:{bad}']").click()
    expect(banker.locator("[data-testid=action-accept]")).to_be_disabled(timeout=15000)
    check("wrong type: the banker cannot accept it as an ID card", True)
    shot(banker, "15-blocker-banker")
    labels = {a["params"].get("requirement_code"): a["label_he"] for a in snap(BLOCKER)["available_actions"]
              if a["type"] == "NAVIGATE_TO_DOCUMENT_UPLOAD"}
    home(page)
    second = page.locator("[data-testid=summary-upload]")
    check("first-upload wording: requirements never uploaded say 'העלאת …', only the returned ID card says 'העלאה מחדש'",
          labels.get(ID, "").startswith("העלאה מחדש") and all(labels[c].startswith("העלאת") for c in (PAY, BANK, PURPOSE))
          and (not second.count() or not second.inner_text().strip().startswith("העלאה מחדש")), json.dumps(labels, ensure_ascii=False))
    # the same payslip, now under the payslips: a new document reviewed as a payslip, not "already uploaded"
    note = upload(page, PAY, files_b["01_INITIAL_UPLOADS/ido_2026_07.pdf"], "2026-07")
    s = settle(BLOCKER, 2)
    pay = {r["code"]: r for r in s["readiness"]["requirements"]}[PAY]
    refiled = [d for d in api.get(f"/api/cases/{BLOCKER}/documents").json() if d["filename"] == "ido_2026_07.pdf"]
    check("re-filing: a file first put under the ID card can be uploaded under the payslips and counts for July",
          len(refiled) == 2 and {d["requirement_code"] for d in refiled} == {ID, PAY} and "2026-07" in (pay.get("covered") or [])
          and "כבר הועלה" not in note, note[:120])
    page.goto(f"{BASE}/customer/documents/{bad}")
    page.locator("[data-testid=document-replace]").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet.locator("[data-testid=upload-replaces]")).to_be_visible(timeout=15000)
    check("document page: 'העלאת מסמך חלופי' opens the upload for the same requirement (ID card), replacing this file",
          sheet.locator("[data-testid=upload-doc-type]").get_attribute("data-requirement") == ID
          and sheet.locator("[data-testid=upload-replaces]").get_attribute("data-replaces") == bad)
    sheet.locator("button[aria-label='סגירה']").click()
    home(page)
    page.locator("[data-testid=card-primary]").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet.locator("[data-testid=upload-replaces]")).to_be_visible(timeout=15000)
    sheet.locator("[data-testid=file-input]").set_input_files(str(files_b["loan/id_card_ido.pdf"]))
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator("[data-testid=upload-outcome]")).to_be_visible(timeout=90000)
    sheet.locator("button[aria-label='סגירה']").click()
    s = settle(BLOCKER, 3)
    new = doc_id(BLOCKER, "id_card_ido.pdf")
    check("replacement: the ID card replaces the rejected file (kept in history) and the ID requirement is satisfied",
          s["document_status"].get(bad, {}).get("status") == "REPLACED"
          and {r["code"]: r for r in s["readiness"]["requirements"]}[ID]["ai_state"] == "extracted"
          and s["outcomes"]["documents"][new]["outcome"] == "PASS")
    shot(page, "16-blocker-after")

    # ------------------------------------------------------------ an out-of-date quote reads the same everywhere (case 006)
    open_case(page, "PASS")
    old_quote = ROOT.parent / "fixtures" / "presenter" / "loan_set" / "car_quote_ido_OLD.pdf"
    upload(page, PURPOSE, old_quote)
    s = settle(PASS, 1)
    old = doc_id(PASS, old_quote.name)
    page.goto(f"{BASE}/customer/documents")
    badge = page.locator("[data-testid=doc-card]", has_text=old_quote.name).locator("[data-testid=doc-verdict]")
    expect(badge).to_be_visible(timeout=15000)
    page.locator(f"[data-testid='req-{PURPOSE}'] .dl-head").click()
    row_button = page.locator(f"[data-testid='upload-{PURPOSE}']")
    check("stale quote: the file badge, its requirement and its page all ask the customer for a newer document",
          s["outcomes"]["documents"][old]["outcome"] == "BLOCKER" and badge.inner_text() == "לא תקין — נדרש תיקון"
          and row_button.inner_text().strip() == "העלאה מחדש", f"{badge.inner_text()} · {row_button.inner_text()}")
    shot(page, "16b-stale-quote")

    # ------------------------------------------------------------ loan wording across the app (no mortgage leftovers)
    leftovers = []
    for path in ("/customer", "/customer/documents", "/customer/request", "/customer/stages", "/customer/tools", "/system"):
        page.goto(f"{BASE}{path}")
        page.wait_for_timeout(1200)
        text = page.locator(".phone").inner_text() if path.startswith("/customer") else page.locator("body").inner_text()
        if MORTGAGE.search(text):
            leftovers.append(f"{path}: {MORTGAGE.search(text).group(0)}")
    banker.goto(f"{BASE}/banker?case={JOURNEY}")
    banker.wait_for_timeout(1500)
    if MORTGAGE.search(banker.locator("body").inner_text()):
        leftovers.append("/banker")
    check("loan wording: customer screens, banker console and system page carry no mortgage terminology", not leftovers, "; ".join(leftovers))
    page.goto(f"{BASE}/customer/request")
    shot(page, "17-request-details")
    page.goto(f"{BASE}/customer/stages")
    shot(page, "18-stages")

    # ------------------------------------------------------------ start a new application (JEEN questionnaire → policy)
    home(page)
    page.locator("button[aria-label='תפריט']").click()
    page.locator("[data-testid=drawer-apply]").click()
    chat = page.locator("[data-testid=apply-chat]")
    expect(chat.locator("[data-testid=onb-question]")).to_be_visible(timeout=15000)
    if chat.locator("[data-testid=onb-restart]").count():
        chat.locator("[data-testid=onb-restart]").click()

    def reply(qid: str, value: str | None = None, name: tuple[str, str] | None = None, multi: list[str] | None = None) -> None:
        expect(chat.locator("[data-testid=onb-question]")).to_have_attribute("data-question", qid, timeout=10000)
        if name:
            chat.locator("[data-testid=onb-first]").fill(name[0])
            chat.locator("[data-testid=onb-last]").fill(name[1])
            chat.locator("[data-testid=onb-send]").click()
        else:
            for v in multi or [value]:
                chat.locator(f"[data-testid=onb-option][data-value='{v}']").click()
            if multi:
                chat.locator("[data-testid=onb-send]").click()
        expect(chat.locator(f"[data-testid=onb-answered-{qid}]")).to_be_visible(timeout=10000)

    reply("entity", "individual")
    reply("name", name=("מיה", "ברקוביץ"))
    reply("purpose", "renovation")
    reply("income", multi=["self_employed"])
    reply("registration", "vat_exempt")
    shot(page, "19-apply")
    reply("net", "12000")
    reply("co_borrower", "no")
    reply("amount", "80000")
    reply("payments", "60")
    page.locator("[data-testid=onb-confirm]").click()
    expect(page.locator("[data-testid='req-TAX_ASSESSMENT:BRW-A']")).to_be_visible(timeout=20000)
    pill = page.locator(".case-pill").inner_text()
    check("intake: a new self-employed renovation application opens with a tax assessment instead of payslips",
          page.locator("[data-testid='req-PAYSLIPS:BRW-A']").count() == 0 and page.locator("[data-testid='req-PURPOSE_PROOF']").count() == 1
          and "שיפוץ" in pill, pill)
    shot(page, "20-apply-documents")

    log = [json.loads(line) for line in (DATA / "replay-transport.jsonl").read_text(encoding="utf8").splitlines()] \
        if (DATA / "replay-transport.jsonl").exists() else []
    served = [e for e in log if e.get("purpose") in ("extract", "judge")]
    check("REPLAY only: every model answer came from a recording (RECORDED_LIVE), no network call",
          bool(served) and all(e["served"] for e in served) and {e.get("provenance") for e in served} <= {"RECORDED_LIVE"},
          f"{len(served)} extract/judge answers · {sorted({e.get('provenance') for e in served})}")


def overflow(page: Page) -> int:
    return page.evaluate("document.documentElement.scrollWidth - window.innerWidth")


def mobile(page: Page) -> None:
    """The customer app on a phone (390×844): no sideways scrolling, and a requirement's upload opens for that requirement."""
    page.goto(f"{BASE}/customer")
    page.evaluate(f"localStorage.setItem('mz.case', '{BLOCKER}')")
    home(page)
    wide = {"home": overflow(page)}
    shot(page, "21-mobile-home")
    page.goto(f"{BASE}/customer/documents")
    expect(page.locator(f"[data-testid='req-{BANK}']")).to_be_visible(timeout=15000)
    wide["documents"] = overflow(page)
    page.locator(f"[data-testid='req-{BANK}'] .dl-head").click()
    page.locator(f"[data-testid='upload-{BANK}']").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible()
    submit = sheet.locator("[data-testid=upload-submit]")
    submit.scroll_into_view_if_needed()
    box = submit.bounding_box() or {"x": -1, "y": -1, "width": 0, "height": 0}
    shot(page, "22-mobile-upload-sheet")
    check("mobile: no sideways scroll; the statement's upload opens for the statement with its button on screen",
          max(wide.values()) <= 0 and sheet.locator("[data-testid=upload-doc-type]").get_attribute("data-requirement") == BANK
          and 0 <= box["x"] and box["x"] + box["width"] <= 390 and 0 <= box["y"] and box["y"] + box["height"] <= 844, json.dumps(wide))


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        customer = browser.new_context(viewport={"width": 1440, "height": 920}, locale="he-IL", accept_downloads=True)
        staff = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="he-IL")
        phone = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True, has_touch=True)
        try:
            run(customer.new_page(), staff.new_page())
            mobile(phone.new_page())
        except Exception as exc:                       # a failed step is a failed check, with a screenshot
            check("suite ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
            for i, pg in enumerate(customer.pages + staff.pages + phone.pages):
                pg.screenshot(path=str(ART / f"failure-{i}.png"))
        browser.close()
    passed = sum(r["pass"] for r in RESULTS)
    (ART / "results.json").write_text(json.dumps({"mode": "REPLAY", "passed": passed, "total": len(RESULTS), "results": RESULTS},
                                                 ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed · mode REPLAY (no Gemini calls)")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
