"""Executive demo — PASS / REVIEW / BLOCKER end to end in a real Chrome, against a REPLAY backend (zero Gemini calls).

LEGACY (mortgage era): superseded by e2e/test_loan_journey.py, which covers the four loan scenarios. This suite still
asserts three mortgage scenarios and the 21 golden files, so it fails on the loan cases by design (2/6 on 2026-10-14).

Every review in this run is REPLAY: the model's answers come from e2e/replay/recordings.json (recorded live answers
for the golden payslips; one labelled AUTHORED answer for the bank statement), looked up by the uploaded file's
SHA-256. Evidence verification, rules, verdicts, case review, findings, outcomes, the banker desk and the reset are the
production code. This proves the workflow and the UI, not the model's accuracy. It resets cases 006–008 only.

    # from backend/ — fresh DATA_DIR
    .venv/bin/python ../e2e/replay_backend.py --port 8798 --data ../e2e/artifacts/featured/data-replay
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/featured/web-replay 5846 http://127.0.0.1:8798
    FEATURED_E2E_BASE=http://127.0.0.1:5846 FEATURED_DATA=e2e/artifacts/featured/data-replay \
        backend/.venv/bin/python e2e/test_featured_demo.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("FEATURED_E2E_BASE", "http://127.0.0.1:5846")
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("FEATURED_DATA", ROOT / "artifacts" / "featured" / "data-replay")).resolve()
ART = ROOT / "artifacts" / "featured"
SHOTS = ART / "screens"
GOLDEN = ROOT.parent / "fixtures" / "presenter" / "golden_set"
MANIFEST = json.loads((ROOT.parent / "fixtures" / "presenter" / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
DOCS = {d["id"]: d for d in MANIFEST["documents"]}
FEATURED = {f["outcome"]: f for f in MANIFEST["featured"]}
PASS, REVIEW, BLOCKER = (FEATURED[k]["caseId"] for k in ("PASS", "REVIEW", "BLOCKER"))
LABEL = {"PASS": "עבר בדיקת AI, ממתין לקבלת הבנקאי", "REVIEW": "נדרש בירור בנקאי, נמצא פער בהכנסה",
         "BLOCKER": "המסמך אינו מתאים לדרישה, נא להעלות מסמך חלופי"}
RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


# ---------------------------------------------------------------- API (the same sessions the app obtains in demo mode)
api = httpx.Client(base_url=BASE, timeout=60)


def sessions() -> None:
    for case in (PASS, REVIEW, BLOCKER, "DEMO-MTZ-2026-004"):
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


def settle(case: str, documents: int, timeout: float = 90) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap(case)
        c = s["readiness"]["counts"]
        if c["documents"] >= documents and not s["readiness"]["pending_jobs"] and c["processing"] == 0 and s["case_review"]:
            return s
        time.sleep(0.8)
    raise TimeoutError(f"{case} did not settle")


# ---------------------------------------------------------------- browser helpers
def shot(page: Page, name: str) -> None:
    """A screenshot once the page has settled: case selector loaded, page images drawn."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    try:
        if page.locator(".case-pill").count():
            expect(page.locator(".case-pill")).not_to_contain_text("טוען", timeout=10000)
        if page.locator("[data-testid=evidence-viewer]").count():
            expect(page.locator("[data-testid=evidence-viewer].loading")).to_have_count(0, timeout=10000)
    except AssertionError:
        pass
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def card(page: Page, route: str):
    return page.locator(f"[data-testid=featured-{route}]")


def download_all(page: Page, route: str) -> list[Path]:
    out = []
    links = card(page, route).locator("[data-testid=featured-download]")
    for i in range(links.count()):
        with page.expect_download() as dl:
            links.nth(i).click()
        target = ART / "downloads" / dl.value.suggested_filename
        target.parent.mkdir(parents=True, exist_ok=True)
        dl.value.save_as(str(target))
        out.append(target)
    return out


def open_case(page: Page, route: str) -> None:
    card(page, route).locator("[data-testid=featured-open-case]").click()
    expect(page.locator(".case-pill")).to_contain_text(FEATURED[route]["caseDisplay"], timeout=15000)
    expect(page.locator("[data-testid=ai-card]")).to_be_visible(timeout=15000)


def open_row(page: Page, code: str) -> None:
    """Requirement rows on the Documents screen start collapsed."""
    head = page.locator(f"[data-testid='req-{code}'] .dl-head")
    expect(head).to_be_visible(timeout=15000)
    if head.get_attribute("aria-expanded") != "true":
        head.click()


def upload(page: Page, borrower: str, path: Path, period: str | None) -> None:
    page.goto(f"{BASE}/customer/documents")
    open_row(page, f"PAYSLIPS:{borrower}")
    page.locator(f"[data-testid=upload-{borrower}]").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible()
    if period:
        chip = sheet.locator(f".mchip[data-period='{period}']")
        if chip.count() and chip.get_attribute("aria-checked") != "true":
            chip.click()
    sheet.locator("[data-testid=file-input]").set_input_files(str(path))
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator(".doc-name")).to_have_text(path.name, timeout=15000)
    expect(sheet.locator("[data-testid=upload-outcome]")).to_be_visible(timeout=60000)
    sheet.locator("button[aria-label='סגירה']").click()


def home(page: Page) -> None:
    page.goto(f"{BASE}/customer")
    expect(page.locator("[data-testid=ai-card]")).to_be_visible(timeout=15000)


def consistent(case: str) -> tuple[bool, str]:
    """The customer's snapshot and the banker's workspace route every document the same way."""
    cust = snap(case)["outcomes"]["documents"]
    desk = {i["document_id"]: i["outcome"]["outcome"] for i in ws(case)["items"] if i["kind"] == "document"}
    ok = desk == {d: o["outcome"] for d, o in cust.items()}
    return ok, json.dumps(desk)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(page: Page, banker: Page) -> None:
    page.goto(f"{BASE}/customer")
    expect(page.locator("[data-testid=featured-scenarios]")).to_be_visible(timeout=20000)

    # ------------------------------------------------------------ the presenter pane
    cards = page.locator("[data-testid=featured-scenarios] article.feat")
    order = [cards.nth(i).get_attribute("data-testid") for i in range(cards.count())]
    check("exactly three featured scenarios, in order PASS · REVIEW · BLOCKER",
          order == ["featured-PASS", "featured-REVIEW", "featured-BLOCKER"], str(order))
    complete = True
    for route, f in FEATURED.items():
        c = card(page, route)
        text = c.inner_text()
        complete &= all(x in text for x in (f["titleHe"], f["checksHe"], f["expectHe"], f["expectedLabelHe"], f["caseDisplay"], f["borrowerHe"]))
        complete &= c.locator("[data-testid=featured-download]").count() == len({s["file"] for s in f["steps"]})
        complete &= c.locator("[data-testid=featured-playbook]").count() == 0          # playbook collapsed by default
    check("each card shows title, what is checked, what is expected, files, borrower + case + destination, expected label",
          complete)
    check("expected labels are the business outcomes",
          [card(page, r).locator("[data-testid=featured-expected]").inner_text().split("\n")[-1] for r in ("PASS", "REVIEW", "BLOCKER")]
          == [LABEL[r] for r in ("PASS", "REVIEW", "BLOCKER")])
    all_scn = page.locator("[data-testid=all-scenarios]")
    bundle = httpx.get(f"{BASE}/api/presenter/scenarios", timeout=60).json()
    check("'כל תרחישי הבדיקה' is collapsed by default and keeps all 10 scenarios, the 21 golden files and the Lavi files",
          all_scn.get_attribute("open") is None and all_scn.locator("[data-testid^=scn-toggle-CASE-]").count() == 10
          and len(bundle["files"]) == 21 and all(f["sha256_matches_manifest"] for f in bundle["files"].values())
          and all_scn.locator("a[href^='/api/fixtures/file']").count() >= 11)
    side = page.locator(".hub-side")
    check("split screen kept: presenter pane left, live app right, no horizontal scroll",
          page.locator(".phone").bounding_box()["x"] >= side.bounding_box()["x"] + side.bounding_box()["width"] - 1
          and side.evaluate("e => e.scrollWidth <= e.clientWidth"))
    shot(page, "01-presenter-default")

    writes: list[str] = []
    page.on("request", lambda r: writes.append(f"{r.method} {r.url}") if r.method != "GET" and "/api/" in r.url else None)

    # ------------------------------------------------------------ start clean
    page.locator("[data-testid=new-demo-button]").click()
    page.locator("[data-testid=new-demo-confirm]").click()
    expect(page.locator("[data-testid=new-demo-status]")).to_contain_text("הדמו מוכן", timeout=30000)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("ממתינים להעלאת תלושי שכר", timeout=15000)
    expect(page.locator(".case-pill")).to_contain_text(FEATURED["PASS"]["caseDisplay"], timeout=15000)
    sessions()
    other_before = ws("DEMO-MTZ-2026-004")["summary"]["documents"]
    check("'התחל דמו חדש' opens case 438839006 on the right, empty",
          FEATURED["PASS"]["caseDisplay"] in page.locator(".case-pill").inner_text()
          and all(snap(c)["readiness"]["counts"]["documents"] == 0 for c in (PASS, REVIEW, BLOCKER)))

    # ------------------------------------------------------------ PASS
    writes.clear()
    files = download_all(page, "PASS")
    check("PASS: downloads are the exact golden files (SHA-256) and downloading writes nothing",
          [sha(p) for p in files] == [DOCS[s["file"]]["sha256"] for s in FEATURED["PASS"]["steps"]] and not writes, str(writes))
    open_case(page, "PASS")
    for p, s in zip(files, FEATURED["PASS"]["steps"]):
        upload(page, "BRW-A", p, s["period"])
    s = settle(PASS, 3)
    home(page)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("בדיקת תלושי השכר הושלמה", timeout=15000)
    check("PASS: home card 'בדיקת תלושי השכר הושלמה', 3 of 3, no open finding",
          s["readiness"]["customer_status"] == "CHECKS_COMPLETE" and not [f for f in s["findings"] if f["status"] == "open"]
          and "3 מתוך 3" in page.locator("[data-testid=card-total]").inner_text())
    shot(page, "03-pass-home")
    first = next(d for d in api.get(f"/api/cases/{PASS}/documents").json() if d["filename"] == files[0].name)
    page.goto(f"{BASE}/customer/documents/{first['document_id']}")
    expect(page.locator("[data-testid=document-outcome]")).to_have_text(LABEL["PASS"], timeout=15000)
    witnesses = {f["field"]: f["evidence"]["witness"] for f in first["review"]["facts"]}
    check("PASS: document page shows the outcome; every decisive value verified against the PDF text layer (REPLAY answers)",
          all(witnesses.get(k) == "text_layer_exact" for k in ("employee_name", "employee_id", "salary_period", "gross_pay", "net_pay"))
          and first["review"]["identity"]["models"]["extract"] == "replay-recorded", json.dumps(witnesses))
    shot(page, "04-pass-document")
    banker.goto(f"{BASE}/banker?case={PASS}")
    expect(banker.locator("[data-testid=queue-group-decide] [data-testid=queue-item]")).to_have_count(3, timeout=20000)
    banker.locator("[data-testid=queue-group-decide] [data-testid=queue-item]").first.click()
    shot(banker, "05-pass-banker")
    stage = snap(PASS)["case"]["bank_stage"]
    for _ in range(3):
        banker.locator("[data-testid=queue-group-decide] [data-testid=queue-item]").first.click()
        banker.locator("[data-testid=action-accept]").click()
        banker.locator("[data-testid=confirm-accept]").click()
        expect(banker.locator("[data-testid=decision-success]")).to_be_visible(timeout=15000)
    page.goto(f"{BASE}/customer/documents/{first['document_id']}")
    expect(page.locator("[data-testid=document-outcome]")).to_contain_text("לא אישור משכנתא", timeout=15000)
    s = snap(PASS)
    check("PASS: the banker accepts all three in the console; the customer sees a documentary acceptance, never an approval",
          s["readiness"]["counts"]["documents_accepted"] == 3 and s["case"]["bank_stage"] == stage
          and s["readiness"]["state"] != "PREPARATION_CONFIRMED")
    shot(page, "06-pass-accepted")
    ok, detail = consistent(PASS)
    check("PASS: customer and banker route every document the same way", ok, detail)

    # ------------------------------------------------------------ REVIEW
    files = download_all(page, "REVIEW")
    open_case(page, "REVIEW")
    for p, st in zip(files, FEATURED["REVIEW"]["steps"]):
        upload(page, "BRW-B", p, st["period"])
    s = settle(REVIEW, 3)
    home(page)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("תלושי השכר הושלמו · נדרש בירור בנקאי", timeout=15000)
    gap = [f for f in s["findings"] if f["status"] == "open" and f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"]
    check("REVIEW: all three payslips pass, the income gap (₪18,500 vs ₪16,900 over 3 months) goes to the banker",
          len(gap) == 1 and gap[0]["review_state"] == "NEEDS_BANKER_REVIEW" and gap[0]["detail"]["basis"] == "complete"
          and s["outcomes"]["borrowers"]["BRW-B"]["label_he"] == LABEL["REVIEW"]
          and {d["review"]["verdict"] for d in api.get(f"/api/cases/{REVIEW}/documents").json()} == {"VALID"})
    shot(page, "07-review-home")
    banker.goto(f"{BASE}/banker?case={REVIEW}")
    item = banker.locator("[data-testid=queue-group-judgment] [data-testid=queue-item]")
    expect(item).to_have_count(1, timeout=20000)
    item.click()
    expect(banker.locator("[data-testid=income-summary]")).to_be_visible(timeout=10000)
    desk_text = banker.locator("body").inner_text()
    check("REVIEW: the banker sees the comparison (declared ₪18,500, average ₪16,900, 3/3 months) and a next step",
          all(x in desk_text for x in ("18,500", "16,900", "3/3")) and banker.locator("[data-testid=next-step]").count() > 0)
    shot(banker, "08-review-banker")
    fid = gap[0]["finding_id"]
    finding = next(i for i in ws(REVIEW)["items"] if i["kind"] == "case_finding")
    r = api.post(f"/api/banker/cases/{REVIEW}/findings/{fid}/decision",
                 json={"action": "request_explanation", "customer_message": finding["drafts"]["explanation"]["message_he"], "request_id": "e2e-exp"})
    q = next(x for x in snap(REVIEW)["customer_requests"] if x["kind"] == "explanation")
    api.post(f"/api/cases/{REVIEW}/customer-requests/{q['customer_request_id']}/reply", json={"text": "יש לי מענק שנתי שמשולם בדצמבר."})
    settle(REVIEW, 3)
    still = next(f for f in snap(REVIEW)["findings"] if f["finding_id"] == fid)
    check("REVIEW: the banker asks for an explanation, the customer answers, the gap stays open for a human decision",
          r.status_code == 200 and still["status"] == "open")
    ok, detail = consistent(REVIEW)
    check("REVIEW: customer and banker route every document the same way", ok, detail)

    # ------------------------------------------------------------ BLOCKER
    files = {Path(p).name: p for p in download_all(page, "BLOCKER")}
    open_case(page, "BLOCKER")
    steps = FEATURED["BLOCKER"]["steps"]
    for st in steps[:3]:
        upload(page, "BRW-A", files[st["file"].split("/")[-1]], st["period"])
    s = settle(BLOCKER, 3)
    home(page)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("נמצא מסמך שדורש תיקון", timeout=15000)
    wrong = next(d for d in api.get(f"/api/cases/{BLOCKER}/documents").json() if d["filename"] == "bank_statement_Jul_Sep_2026.pdf")
    check("BLOCKER: the bank statement is not a payslip, customer correction, 'העלאת מסמך חלופי' on the home card",
          wrong["review"]["verdict"] == "INVALID" and s["outcomes"]["documents"][wrong["document_id"]]["outcome"] == "BLOCKER"
          and page.locator("[data-testid=card-primary]").inner_text().strip() == "העלאת מסמך חלופי")
    shot(page, "09-blocker-home")
    banker.goto(f"{BASE}/banker?case={BLOCKER}")
    row = banker.locator(f"[data-testid=queue-group-correction] [data-testid=queue-item][data-item-id='doc:{wrong['document_id']}']")
    expect(row).to_be_visible(timeout=20000)
    row.click()
    refused = api.post(f"/api/banker/cases/{BLOCKER}/documents/{wrong['document_id']}/decision",
                       json={"action": "accept", "acknowledged_finding_ids": [], "request_id": "e2e-accept-wrong"})
    check("BLOCKER: the banker sees it under 'תיקון אצל הלקוח' and cannot accept it as a payslip",
          refused.status_code == 409 and banker.locator("[data-testid=action-accept]").is_disabled())
    shot(banker, "10-blocker-banker")
    home(page)
    page.locator("[data-testid=card-primary]").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet.locator("[data-testid=upload-replaces]")).to_contain_text("bank_statement_Jul_Sep_2026.pdf", timeout=15000)
    shot(page, "11-blocker-replace-sheet")
    sheet.locator("[data-testid=file-input]").set_input_files(str(files["ido_2026_09_CORRECTED.pdf"]))
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator("[data-testid=upload-route]")).to_have_text(LABEL["PASS"], timeout=60000)
    sheet.locator("button[aria-label='סגירה']").click()
    s = settle(BLOCKER, 4)
    new = next(d for d in api.get(f"/api/cases/{BLOCKER}/documents").json() if d["filename"] == "ido_2026_09_CORRECTED.pdf")
    old_finding = next(f for f in s["findings"] if f["document_id"] == wrong["document_id"])
    home(page)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("בדיקת תלושי השכר הושלמה", timeout=15000)
    check("BLOCKER: the replacement is revalidated, the customer finding closes as replaced, the old file stays in history",
          old_finding["status"] == "superseded" and s["outcomes"]["documents"][wrong["document_id"]]["outcome"] == "REPLACED"
          and s["outcomes"]["documents"][new["document_id"]]["outcome"] == "PASS" and s["readiness"]["customer_status"] == "CHECKS_COMPLETE"
          and s["document_status"][wrong["document_id"]]["status"] == "REPLACED")
    shot(page, "12-blocker-after")
    banker.goto(f"{BASE}/banker?case={BLOCKER}")
    new_row = banker.locator(f"[data-testid=queue-item][data-item-id='doc:{new['document_id']}']")
    expect(new_row).to_be_visible(timeout=20000)
    new_row.click()
    desk_new = next(i for i in ws(BLOCKER)["items"] if i["id"] == f"doc:{new['document_id']}")
    check("BLOCKER: the banker sees the new file as a customer replacement linked to the rejected one",
          desk_new["replaces"]["document_id"] == wrong["document_id"] and desk_new["replaces"]["by"] == "customer"
          and "שהלקוח העלה" in banker.locator("body").inner_text())
    shot(banker, "13-blocker-banker-replacement")
    ok, detail = consistent(BLOCKER)
    check("BLOCKER: customer and banker route every document the same way", ok, detail)

    # ------------------------------------------------------------ refresh keeps everything
    card(page, "BLOCKER").locator("[data-testid=featured-toggle]").click()
    page.reload()
    expect(page.locator("[data-testid=ai-card]")).to_be_visible(timeout=15000)
    check("refresh: the same case, the same state and the presenter's open playbook survive a reload",
          FEATURED["BLOCKER"]["caseDisplay"] in page.locator(".case-pill").inner_text()
          and page.locator("[data-testid=readiness-state]").inner_text() == "בדיקת תלושי השכר הושלמה"
          and card(page, "BLOCKER").locator("[data-testid=featured-playbook]").count() == 1)
    shot(page, "02-featured-playbook")

    # ------------------------------------------------------------ start a new demo
    page.locator("[data-testid=new-demo-button]").click()
    page.locator("[data-testid=new-demo-confirm]").click()
    expect(page.locator("[data-testid=new-demo-status]")).to_contain_text("הדמו מוכן", timeout=30000)
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("ממתינים להעלאת תלושי שכר", timeout=15000)
    sessions()
    clean = all(snap(c)["readiness"]["counts"]["documents"] == 0 and not snap(c)["findings"] and not snap(c)["customer_requests"]
                and not snap(c)["outcomes"]["documents"] for c in (PASS, REVIEW, BLOCKER))
    check("'התחל דמו חדש' leaves cases 006–008 empty (documents, findings, requests, decisions) and opens 438839006",
          clean and FEATURED["PASS"]["caseDisplay"] in page.locator(".case-pill").inner_text()
          and card(page, "BLOCKER").locator("[data-testid=featured-playbook]").count() == 0)
    check("'התחל דמו חדש' leaves every other case untouched", ws("DEMO-MTZ-2026-004")["summary"]["documents"] == other_before)
    page.reload()
    expect(page.locator("[data-testid=readiness-state]")).to_have_text("ממתינים להעלאת תלושי שכר", timeout=15000)
    check("the fresh demo survives a reload", FEATURED["PASS"]["caseDisplay"] in page.locator(".case-pill").inner_text())
    shot(page, "14-new-demo")
    page.locator("[data-testid=all-scenarios-toggle]").click()
    expect(page.locator("[data-testid=scn-toggle-CASE-01]")).to_be_visible()
    page.locator("[data-testid=all-scenarios]").scroll_into_view_if_needed()
    shot(page, "15-all-scenarios-open")

    # ------------------------------------------------------------ REPLAY provenance
    log = [json.loads(line) for line in (DATA / "replay-transport.jsonl").read_text(encoding="utf8").splitlines()]
    reviews = [e for e in log if e["purpose"] in ("extract", "judge")]
    check("REPLAY only: every model answer came from a recording (looked up by file SHA-256), no network call was made",
          reviews and all(e["served"] for e in reviews),
          f"{len(reviews)} extract/judge answers · " + ", ".join(sorted({f"{e['provenance']}" for e in reviews})))


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 960}, locale="he-IL", accept_downloads=True)
        page, banker = ctx.new_page(), ctx.new_page()
        try:
            run(page, banker)
        except Exception as exc:                                  # a failed step is a failed check, with a screenshot
            check("suite completed without an exception", False, f"{type(exc).__name__}: {exc}"[:400])
            shot(page, "zz-failure-customer")
            shot(banker, "zz-failure-banker")
        browser.close()
    passed = sum(r["pass"] for r in RESULTS)
    (ART / "results.json").write_text(json.dumps({"mode": "REPLAY", "passed": passed, "total": len(RESULTS), "checks": RESULTS},
                                                 ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed · mode REPLAY (no Gemini calls)")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
