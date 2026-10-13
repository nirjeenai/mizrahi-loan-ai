"""Banker review workspace, end to end in a real Chrome with real Gemini reviews: the banker opens a case,
inspects evidence, accepts one payslip and sends a mislabeled one back; the customer sees the request in
the app and uploads a replacement from it; the replacement is re-reviewed and returns to the banker with
its history. Also: refresh, duplicate submissions, invalid transitions, unauthorized calls, and the bank
stage never moving. Resets case DEMO-MTZ-2026-001, so point it only at a backend with its own DATA_DIR:

    # from backend/
    DATA_DIR=../e2e/artifacts/banker/data-e2e ./.venv/bin/uvicorn app.main:app --port 8796
    node e2e/serve_frontend.mjs e2e/artifacts/banker/web-e2e 5853 http://127.0.0.1:8796
    BANKER_E2E_BASE=http://127.0.0.1:5853 backend/.venv/bin/python e2e/test_banker_review.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright
import demo_auth  # noqa: E402  (e2e/ is on sys.path when a suite runs as a script)

BASE = os.environ.get("BANKER_E2E_BASE", "http://127.0.0.1:5853")
demo_auth.install(BASE)                   # the service has no anonymous access (see demo_auth.py)
CASE = "DEMO-MTZ-2026-001"
DANA = {"X-Staff-Id": "STAFF-DANA"}
ROOT = Path(__file__).resolve().parent
FIX = ROOT.parent / "fixtures" / "out" / "main"
ART = ROOT / "artifacts" / "banker" / "e2e"
RESULTS: list[dict] = []
EXPECTED_DRAFT = ("שלום עידו, המסמך שהעלית עבור ספטמבר מציג את חודש אוגוסט. "
                  "כדי להמשיך בבדיקת מסמכי ההכנסה, נא להעלות את תלוש ספטמבר 2026.")


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


def api(method: str, path: str, **kw) -> httpx.Response:
    return httpx.request(method, f"{BASE}{path}", timeout=60, **kw)


def snap() -> dict:
    return api("GET", f"/api/cases/{CASE}").json()


def ws() -> dict:
    return api("GET", f"/api/banker/cases/{CASE}/workspace").json()


def settle(timeout: int = 480) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap()
        if not s["readiness"]["pending_jobs"] and s["readiness"]["state"] not in ("CHECKING", "RECHECKING"):
            return s
        time.sleep(2)
    raise TimeoutError("case did not settle")


def upload(borrower: str, name: str) -> str:
    with (FIX / name).open("rb") as fh:
        r = api("POST", f"/api/cases/{CASE}/documents", files={"file": (name, fh, "application/pdf")}, data={"borrower_id": borrower})
    r.raise_for_status()
    return r.json()["document"]["document_id"]


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(ART / f"{name}.png"))


def select(page: Page, item_id: str) -> None:
    page.locator(f"[data-testid=queue-item][data-item-id='{item_id}']").click()
    expect(page.locator(f"[data-testid=queue-item][data-item-id='{item_id}']")).to_have_attribute("aria-current", "true")


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    api("POST", f"/api/cases/{CASE}/reset").raise_for_status()
    docs = {"ido07": upload("BRW-A", "ido_payslip_2026-07.pdf"), "ido08": upload("BRW-A", "ido_payslip_2026-08.pdf"),
            "ido09": upload("BRW-A", "ido_payslip_2026-09.pdf"), "noa07": upload("BRW-B", "noa_payslip_2026-07_scan.pdf"),
            "noa08": upload("BRW-B", "noa_payslip_2026-08.pdf"), "noa09": upload("BRW-B", "noa_payslip_2026-09.pdf")}
    s0 = settle()
    stage0 = s0["case"]["bank_stage"]
    verdicts = {k: next(d for d in api("GET", f"/api/cases/{CASE}/documents").json() if d["document_id"] == v)["review"]["verdict"]
                for k, v in docs.items()}
    check("setup · six payslips reviewed by Gemini", all(verdicts.values()), json.dumps(verdicts))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL")
        page = ctx.new_page()

        # 1–2 · open the case and see what needs attention
        page.goto(f"{BASE}/banker?case={CASE}")
        expect(page.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
        w = ws()
        decide = next(g for g in w["groups"] if g["key"] == "decide")["items"]
        missing = next(g for g in w["groups"] if g["key"] == "missing")["items"]
        first = page.locator("[data-testid=queue-group-decide] [data-testid=queue-item]").first.get_attribute("data-item-id")
        check("1 queue · uploaded documents wait for a decision", f"doc:{docs['ido07']}" in decide and f"doc:{docs['ido09']}" in decide,
              f"decide={len(decide)}")
        check("2 queue · the mislabeled payslip is first in line", first == f"doc:{docs['ido09']}", f"first={first}")
        group = page.locator("[data-testid=queue-group-missing]")
        check("2 queue · missing months are one collapsed section with a summary", group.locator("[data-testid=queue-item]").count() == 0
              and "ספטמבר" in group.locator(".queue-group-summary").inner_text())
        group.locator(".queue-group-head").click()
        check("2 queue · missing September is listed as missing, not as an uploaded document",
              "missing:BRW-A:2026-09" in missing and page.locator("[data-item-id='missing:BRW-A:2026-09'][data-kind=missing]").count() == 1)
        progress = page.locator("[data-testid=case-progress]").inner_text()
        check("2 status · progress counts required payslips, not reviewed files",
              f"{w['summary']['payslips_verified']}/6" in progress and "תלושים נדרשים מאומתים" in progress, progress.replace("\n", " "))
        page.locator("[data-testid=coverage-toggle]").click()
        ido_income = page.locator("[data-testid=income-line]").first
        check("2 status · Ido's small income gap follows the rubric (informational)",
              ido_income.get_attribute("data-outcome") == "PASS" and "INCONSISTENT" not in page.locator("[data-testid=borrower-strip]").inner_text(),
              ido_income.inner_text().replace("\n", " "))
        shot(page, "01-workspace")

        # 3–5 · select the document, inspect the source and the AI summary
        select(page, f"doc:{docs['ido09']}")
        page.wait_for_function("() => { const i = document.querySelector('[data-testid=evidence-viewer] img'); return i && i.naturalWidth > 0; }", timeout=20000)
        boxes = page.locator("[data-testid=evidence-viewer] .hl").count()
        check("4 evidence · original page rendered with highlighted fields", boxes >= 5, f"boxes={boxes}")
        attention = page.locator("[data-testid=attention]").inner_text()
        check("5 AI summary · plain-language reason for attention",
              "הקובץ שהועלה עבור ספטמבר מכיל בפועל תלוש של חודש אוגוסט." in attention, attention[:120])
        expect(page.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_attribute("data-field", "salary_period")
        check("4 evidence · only the evidence behind the attention line is highlighted by default",
              page.locator("[data-testid=evidence-viewer] .hl.quiet").count() == boxes - 1)
        page.locator("[data-testid=key-field][data-field=net_pay]").click()
        expect(page.locator("[data-testid=evidence-viewer] .hl.focus")).to_have_attribute("data-field", "net_pay")
        check("4 evidence · clicking a value focuses its box on the page", True)
        check("5 AI summary · technical metadata hidden by default",
              "payslip.il.salaried" not in page.locator("[data-testid=decision-panel]").inner_text())
        shot(page, "02-evidence-focus")

        # 6 · accept a valid document (double click must not create two decisions)
        select(page, f"doc:{docs['ido07']}")
        page.locator("[data-testid=action-accept]").click()
        expect(page.locator("[data-testid=accept-form]")).to_contain_text("אינה החלטת אשראי")
        page.locator("[data-testid=confirm-accept]").dblclick()
        expect(page.locator("[data-testid=decision-success]")).to_be_visible(timeout=15000)
        accepts = [d for d in api("GET", f"/api/banker/cases/{CASE}/package").json()["decisions"]
                   if d["action"] == "ACCEPT_DOCUMENT" and d["document_id"] == docs["ido07"]]
        check("6 accept · persisted once with actor and status change", len(accepts) == 1 and accepts[0]["actor_id"] == "STAFF-DANA"
              and accepts[0]["previous_status"] == "AWAITING_DECISION" and accepts[0]["new_status"] == "ACCEPTED", json.dumps(accepts, ensure_ascii=False)[:200])
        s1 = snap()
        check("6 accept · bank stage untouched, no preparation confirmed", s1["case"]["bank_stage"] == stage0
              and s1["readiness"]["state"] != "PREPARATION_CONFIRMED")
        shot(page, "03-accepted")

        # 7–8 · request a correction with an edited customer message
        select(page, f"doc:{docs['ido09']}")
        page.locator("[data-testid=action-correction]").click()
        msg_box = page.locator("[data-testid=customer-message]")
        check("8 correction · suggested Hebrew message drafted from the review", msg_box.input_value() == EXPECTED_DRAFT, msg_box.input_value())
        edited = EXPECTED_DRAFT + " תודה!"
        msg_box.fill(edited)
        page.locator("[data-testid=internal-rationale]").fill("פנימי: שם הקובץ מציין ספטמבר, התוכן אוגוסט")
        page.locator("[data-testid=preview-request]").click()
        preview = page.locator("[data-testid=request-preview]").inner_text()
        check("8 correction · confirmation preview shows the customer's view", edited in preview and "נדרש תלוש ספטמבר 2026" in preview)
        check("8 correction · no claim that an SMS or e-mail was sent", "לא נשלחת הודעת SMS" in page.locator("[data-testid=correction-form]").inner_text())
        shot(page, "04-correction-preview")
        page.locator("[data-testid=send-request]").click()
        expect(page.locator("[data-testid=decision-success]")).to_contain_text("מוצגת ללקוח באפליקציה", timeout=15000)
        requests = [q for q in snap()["customer_requests"] if q["status"] == "OPEN"]
        check("7 correction · persisted as an open in-app customer request", len(requests) == 1 and requests[0]["message_he"] == edited
              and requests[0]["period"] == "2026-09", json.dumps(requests, ensure_ascii=False)[:200])
        check("7 correction · internal rationale never reaches the customer API", "פנימי:" not in json.dumps(snap(), ensure_ascii=False))
        shot(page, "05-correction-sent")

        # 15 · refresh keeps the selection and the persisted state
        page.reload()
        expect(page.locator(f"[data-item-id='doc:{docs['ido09']}']")).to_have_attribute("aria-current", "true", timeout=15000)
        expect(page.locator("[data-testid=document-state]")).to_contain_text("הוחזר לתיקון")
        check("refresh · selection and decision survive a reload", True)

        # 9 · the customer sees the request inside the app
        cust = ctx.new_page()
        cust.set_viewport_size({"width": 1366, "height": 940})
        cust.goto(f"{BASE}/customer")
        cust.evaluate(f"localStorage.setItem('mz.case', '{CASE}')")
        cust.goto(f"{BASE}/customer")
        card = cust.locator("[data-testid=ai-card]")
        # the home action card is titled by the request itself ("נדרש תלוש ספטמבר 2026 — עידו") and quotes the banker's message
        expect(cust.locator("[data-testid=readiness-state]")).to_have_text(requests[0]["title_he"], timeout=20000)
        check("9 customer · home card shows the banker's request", edited in card.inner_text(), card.inner_text().replace("\n", " ")[:160])
        cust.locator(".phone").screenshot(path=str(ART / "06-customer-home.png"))
        timeline = cust.locator(".timeline").inner_text()
        check("9 customer · timeline shows the request without the internal note", edited in timeline and "פנימי" not in timeline)

        # 10 · upload the replacement from the request's own button
        cust.locator("[data-testid=card-primary]").click()
        expect(cust.locator("[data-testid=upload-sheet]")).to_be_visible(timeout=10000)
        expect(cust.locator("[data-testid=upload-for-request]")).to_contain_text("נדרש תלוש ספטמבר 2026")
        check("10 customer · request button opens the upload preset to the request", "/customer/documents" in cust.url)
        cust.locator(".phone").screenshot(path=str(ART / "07-customer-upload-sheet.png"))
        cust.locator("[data-testid=file-input]").set_input_files(str(FIX / "ido_payslip_2026-09_corrected.pdf"))
        cust.locator("[data-testid=upload-submit]").click()
        expect(cust.locator("[data-testid=upload-answered]")).to_be_visible(timeout=20000)
        answered = next(q for q in snap()["customer_requests"] if q["customer_request_id"] == requests[0]["customer_request_id"])
        new_doc = answered["responded_document_id"]
        check("10 customer · upload linked to the request", answered["status"] == "RESPONDED" and bool(new_doc))

        # 11 · real re-review of the replacement and of the whole set
        s2 = settle()
        new_review = next(d for d in api("GET", f"/api/cases/{CASE}/documents").json() if d["document_id"] == new_doc)["review"]
        check("11 revalidation · Gemini reviewed the replacement", bool(new_review) and new_review["period"] == "2026-09",
              f"verdict={new_review and new_review['verdict']} period={new_review and new_review['period']}")
        gap = next(f for f in s2["findings"] if f["key"] == "REQUIRED_PERIOD_MISSING:BRW-A:2026-09")
        check("11 revalidation · September gap closed by new evidence", gap["status"] == "resolved" and gap["resolution"] == "resolved_by_new_evidence")
        cust.reload()
        cust.locator(".bottom-nav button", has_text="מסמכים").click()
        expect(cust.locator("[data-testid=customer-request]").first).to_have_attribute("data-status", "RESPONDED", timeout=15000)
        cust.locator(".phone").screenshot(path=str(ART / "08-customer-after-upload.png"))

        # 12–13 · back in the console: new result, history and old evidence preserved
        page.goto(f"{BASE}/banker?case={CASE}")
        expect(page.locator(f"[data-item-id='doc:{new_doc}']")).to_be_visible(timeout=20000)
        w2 = ws()
        old = next(i for i in w2["items"] if i["id"] == f"doc:{docs['ido09']}")
        new = next(i for i in w2["items"] if i["id"] == f"doc:{new_doc}")
        check("12 console · replacement waits for a decision, linked to the old file",
              new["group"] == "decide" and new["replaces"]["document_id"] == docs["ido09"], f"group={new['group']}")
        check("13 history · old document kept as replaced with its decision and evidence",
              old["banker"]["status"] == "REPLACED" and old["history"][0]["action"] == "REQUEST_CORRECTION"
              and len(old["ai"]["facts"]) >= 5 and all(f["status"] != "open" for f in old["findings"] if f["document_id"] == docs["ido09"]))
        select(page, f"doc:{new_doc}")
        page.wait_for_function("() => { const i = document.querySelector('[data-testid=evidence-viewer] img'); return i && i.naturalWidth > 0; }", timeout=20000)
        check("12 console · new evidence shown for the replacement", page.locator("[data-testid=evidence-viewer] .hl").count() >= 5)
        shot(page, "09-replacement")
        page.locator(".ev-chain button").click()
        expect(page.locator(f"[data-item-id='doc:{docs['ido09']}']")).to_have_attribute("aria-current", "true")
        expect(page.locator("[data-testid=decision-history]")).to_contain_text("החזרה לתיקון")
        check("13 history · the replacement links back to the document it replaced", True)
        shot(page, "10-old-document-history")

        # 14 · open items still tracked
        open_banker = [f for f in s2["findings"] if f["status"] == "open" and f["review_state"] == "NEEDS_BANKER_REVIEW"]
        listed = {i["finding"]["finding_id"] for i in w2["items"] if i["kind"] == "case_finding" and i["group"] == "judgment"}
        listed |= {f["finding_id"] for i in w2["items"] if i["kind"] == "document" for f in i["findings"] if f["status"] == "open"}
        check("14 tracking · every open banker finding stays in the queue", all(f["finding_id"] in listed for f in open_banker),
              f"open_banker={[f['code'] for f in open_banker]}")
        closed_by_ai = [f for f in s2["findings"] if f["review_state"] == "NEEDS_BANKER_REVIEW" and f["status"] != "open"
                        and f.get("resolution") not in ("accepted_by_banker", "dismissed_by_banker", "correction_requested_by_banker",
                                                        "replaced_by_customer_upload")]
        check("14 tracking · no banker finding closed without a banker", not closed_by_ai, str([f["code"] for f in closed_by_ai]))
        variance = [i for i in w2["items"] if i["kind"] == "case_finding" and i["group"] == "judgment"]
        if variance:
            select(page, variance[0]["id"])
            expect(page.locator("[data-testid=income-summary]")).to_be_visible()
            shot(page, "11-income-variance")

        # keyboard
        before = page.locator("[data-testid=queue-item][aria-current=true]").get_attribute("data-item-id")
        page.locator("body").press("j")
        after = page.locator("[data-testid=queue-item][aria-current=true]").get_attribute("data-item-id")
        check("keyboard · J moves to the next queue item", before != after, f"{before} → {after}")

        # duplicates, invalid transitions, access
        base = f"/api/banker/cases/{CASE}/documents"
        replay = api("POST", f"/api/banker/cases/{CASE}/missing-requests", headers=DANA,
                     json={"borrower_id": "BRW-A", "period": "2026-09", "customer_message": "x", "request_id": "e2e-m"})
        check("invalid · request for a month that is no longer missing is refused", replay.status_code == 409, replay.text[:120])
        r = api("POST", f"{base}/{docs['ido09']}/decision", headers=DANA, json={"action": "accept", "acknowledged_finding_ids": []})
        check("invalid · a replaced document cannot be accepted", r.status_code == 409, r.text[:120])
        r = api("POST", f"{base}/{new_doc}/decision", headers=DANA, json={"action": "escalate"})
        check("invalid · escalation without a reason is refused", r.status_code == 422, r.text[:120])
        r = api("POST", f"{base}/{new_doc}/decision", json={"action": "accept", "acknowledged_finding_ids": []})
        check("unauthorized · no staff identity is refused", r.status_code == 401)
        r = api("POST", f"{base}/{new_doc}/decision", headers={"X-Staff-Id": "STAFF-ORI"}, json={"action": "accept", "acknowledged_finding_ids": []})
        check("unauthorized · a banker not assigned to the case is refused", r.status_code == 403)
        target = next(i for i in ws()["items"] if i["kind"] == "document" and "accept" in i["banker"]["allowed_actions"]
                      and i["document_id"] != new_doc)
        body = {"action": "accept", "acknowledged_finding_ids": target["banker"]["acknowledge_finding_ids"], "request_id": "e2e-dup",
                "rationale": "בדיקת e2e: קבלה חוזרת"}
        first_accept = api("POST", f"{base}/{target['document_id']}/decision", headers=DANA, json=body)
        again = api("POST", f"{base}/{target['document_id']}/decision", headers=DANA, json=body)
        count = len([d for d in api("GET", f"/api/banker/cases/{CASE}/package").json()["decisions"]
                     if d["document_id"] == target["document_id"] and d["action"] == "ACCEPT_DOCUMENT"])
        check("duplicate · replaying the same submission records one decision", first_accept.status_code == 200
              and again.status_code == 200 and again.json()["duplicate"] is True and count == 1,
              f"{first_accept.status_code}/{again.status_code} decisions={count}")

        s3 = snap()
        check("15 bank stage · unchanged after every banker and customer action", s3["case"]["bank_stage"] == stage0,
              f"{stage0['label_he']} → {s3['case']['bank_stage']['label_he']}")
        check("15 bank stage · no credit decision anywhere in the state", s3["readiness"]["state"] != "PREPARATION_CONFIRMED")
        page.set_viewport_size({"width": 1180, "height": 900})
        page.wait_for_timeout(400)
        shot(page, "12-narrow")
        browser.close()

    failed = [r for r in RESULTS if not r["pass"]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    (ART / "results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
