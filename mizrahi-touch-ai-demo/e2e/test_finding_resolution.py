"""Resolving a banker finding, end to end in a real Chrome with real Gemini reviews.

LEGACY (mortgage era, not yet adapted to loans): asserts the payslip-only mortgage cases and spends real Gemini
calls. Kept for reference and later adaptation; the loan journey is covered by e2e/test_loan_journey.py (REPLAY).
Never point it at :8791 (Mizrahi #2 main) or :8790 (Mizrahi #1): it uploads to cases and resets them.

Noa declares ₪18,500 net and uploads only September (₪16,900). The banker sees a preliminary one-month comparison,
asks for July and August and for an explanation, the customer answers in the app and uploads both months, Gemini
re-reviews, and the banker closes the finding on documented evidence. The decision survives a refresh and a later
review, the customer never sees the internal reason, chat and MCP report the same open requests, and an AI false
positive on another case is dismissed with an audit trail. Resets DEMO-MTZ-2026-001 and -004, so point it only at a
backend with its own DATA_DIR:

    # from backend/
    DATA_DIR=../e2e/artifacts/finding/data-after ./.venv/bin/python -m uvicorn app.main:app --port 8798
    node e2e/serve_frontend.mjs e2e/artifacts/finding/web-after 5855 http://127.0.0.1:8798
    FINDING_E2E_BASE=http://127.0.0.1:5855 backend/.venv/bin/python e2e/test_finding_resolution.py
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

BASE = os.environ.get("FINDING_E2E_BASE", "http://127.0.0.1:5855")
demo_auth.install(BASE)                   # the service has no anonymous access (see demo_auth.py)
CASE, GOLDEN = "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-004"
DANA = {"X-Staff-Id": "STAFF-DANA"}
ROOT = Path(__file__).resolve().parent
FIX = ROOT.parent / "fixtures"
ART = ROOT / "artifacts" / "finding"
RESULTS: list[dict] = []
RATIONALE = "שלושת התלושים מראים רכיב עמלות משתנה; ההכנסה המתועדת (16,900 ₪) תשמש לחישוב ההחזר"
ANSWER = "חלק מהשכר שלי הוא עמלות שמשתנות מחודש לחודש, ולכן הצהרתי על ממוצע גבוה יותר."


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


def api(method: str, path: str, **kw) -> httpx.Response:
    return httpx.request(method, f"{BASE}{path}", timeout=60, **kw)


def snap(case: str = CASE) -> dict:
    return api("GET", f"/api/cases/{case}").json()


def ws(case: str = CASE) -> dict:
    return api("GET", f"/api/banker/cases/{case}/workspace").json()


def settle(case: str = CASE, timeout: int = 480) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap(case)
        if not s["readiness"]["pending_jobs"] and s["readiness"]["state"] not in ("CHECKING", "RECHECKING"):
            return s
        time.sleep(2)
    raise TimeoutError(f"{case} did not settle")


def upload(case: str, borrower: str, path: Path) -> str:
    with path.open("rb") as fh:
        r = api("POST", f"/api/cases/{case}/documents", files={"file": (path.name, fh, "application/pdf")}, data={"borrower_id": borrower})
    r.raise_for_status()
    return r.json()["document"]["document_id"]


def variance(case: str = CASE, status: str = "open") -> dict | None:
    return next((i for i in ws(case)["items"] if i["kind"] == "case_finding"
                 and i["finding"]["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE" and i["finding"]["status"] == status), None)


def mcp_open_requests() -> int:
    key = os.environ.get("E2E_MCP_KEY") or dict(line.split("=", 1) for line in (ROOT.parent / "backend" / ".env").read_text().splitlines()
                                                 if "=" in line and not line.startswith("#"))["MCP_DEMO_KEY"].strip()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
    url = f"{BASE}/mcp"
    httpx.post(url, headers=headers, timeout=30, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "finding-e2e", "version": "1"}}})
    r = httpx.post(url, headers=headers, timeout=30, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                                          "params": {"name": "list_open_items", "arguments": {"audience": "customer"}}})
    return len(r.json()["result"]["structuredContent"]["banker_requests"])


def panel(page: Page) -> str:
    return page.locator("[data-testid=decision-panel]").inner_text()


def open_item(page: Page, case: str, item_id: str) -> None:
    page.goto(f"{BASE}/banker?case={case}&item={item_id}&view=classic")
    expect(page.locator(f"[data-testid=queue-item][data-item-id='{item_id}']")).to_have_attribute("aria-current", "true", timeout=20000)


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    api("POST", f"/api/cases/{CASE}/reset").raise_for_status()
    api("POST", f"/api/cases/{GOLDEN}/reset").raise_for_status()
    sep = upload(CASE, "BRW-B", FIX / "out" / "main" / "noa_payslip_2026-09.pdf")
    pay_doc = upload(GOLDEN, "BRW-A", FIX / "pay_date" / "out" / "ido_2026_09_PAYDATE_MID_PERIOD.pdf")
    s0 = settle()
    settle(GOLDEN)
    stage0 = s0["case"]["bank_stage"]
    item = variance()
    check("setup · one September payslip opens a banker finding", bool(item), f"doc={sep}")
    fid = item["finding"]["finding_id"]

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL")
        page = ctx.new_page()

        # finding without any explanation, on a one-month comparison
        open_item(page, CASE, f"finding:{fid}")
        page.wait_for_function("() => { const i = document.querySelector('[data-testid=evidence-viewer] img'); return i && i.naturalWidth > 0; }", timeout=20000)
        text = panel(page)
        check("preliminary · basis shown as 1 of 3 months", "השוואה ראשונית · 1 מתוך 3 חודשים" in page.locator("[data-testid=comparison-basis]").inner_text())
        summary = page.locator("[data-testid=income-summary]").inner_text()
        check("preliminary · ₪16,900 is the September payslip, not a three-month average",
              "בתלוש ספטמבר 2026" in summary and "ממוצע" not in summary and "יולי ואוגוסט 2026" in summary, summary.replace("\n", " ")[:160])
        check("preliminary · evidence table labels the single month", "נטו בתלוש ספטמבר 2026" in page.locator("[data-testid=income-table]").inner_text())
        check("no explanation · panel says none was given", "לא נמסר הסבר מהלקוח" in page.locator("[data-testid=customer-said]").inner_text())
        check("no explanation · next step is to complete the documents", "קודם להשלים את המסמכים" in page.locator("[data-testid=next-step]").inner_text())
        labels = [page.locator(f"[data-testid=finding-action-{k}]").inner_text() for k in
                  ("request_missing", "request_explanation", "resolve", "dismiss", "escalate")]
        lead = page.locator("[data-testid=finding-action-request_missing]")
        check("actions · five explicit actions, the recommended one is the single primary",
              "קבלת ההסבר" not in text and labels[0] == "בקשת השלמת מסמך" and "act-primary" in (lead.get_attribute("class") or "")
              and page.locator("[data-testid=decision-actions] .act-primary").count() == 1, " | ".join(labels))
        page.screenshot(path=str(ART / "after-1-panel.png"))

        # a resolution on partial data needs an explicit acknowledgement and shows its impact before saving
        page.locator("[data-testid=finding-action-resolve]").click()
        check("resolve · 'explanation supported' unavailable without an explanation",
              page.locator("[data-testid=reason-explanation_supported]").is_disabled())
        page.locator("[data-testid=reason-professional_judgment]").check()
        page.locator("[data-testid=resolve-rationale]").fill("החלטה זמנית על בסיס חודש אחד, לפי הנחיית מנהל")
        check("resolve · partial basis must be acknowledged", page.locator("[data-testid=resolve-review]").is_disabled())
        page.locator("[data-testid=ack-partial] input").check()
        page.locator("[data-testid=resolve-review]").click()
        confirm = page.locator("[data-testid=resolve-confirm]").inner_text()
        check("resolve · confirmation lists finding, basis, evidence, reason, impact and customer view",
              all(x in confirm for x in ("פער בין ההכנסה המוצהרת", "החלטה מקצועית", "ללא, החלטה מקצועית", "חלקי, 1 מתוך 3",
                                         "פריטים לשיקול דעתך", "שלב הבקשה בבנק לא משתנה", "בלי הנימוק הפנימי")), confirm.replace("\n", " ")[:200])
        page.locator("[data-testid=decision-panel]").screenshot(path=str(ART / "after-2-confirm-partial.png"))
        page.locator("[data-testid=resolve-confirm] button", has_text="חזרה לעריכה").click()
        page.locator("[data-testid=finding-action-resolve]").click()
        check("resolve · nothing saved until confirmed", api("GET", f"/api/banker/cases/{CASE}/package").json()["decisions"] == [])

        # request the missing months and an explanation
        page.locator("[data-testid=finding-action-request_missing]").click()
        check("request · draft asks for July and August", "יולי ואוגוסט 2026" in page.locator("[data-testid=request-missing-form] [data-testid=customer-message]").input_value())
        page.locator("[data-testid=request-missing-form] [data-testid=send-request]").click()
        expect(page.locator("[data-testid=decision-success]")).to_contain_text("2 בקשות", timeout=15000)
        page.locator("[data-testid=finding-action-request_explanation]").click()
        msg = page.locator("[data-testid=request-explanation-form] [data-testid=customer-message]")
        check("request · explanation draft states both amounts", "18,500" in msg.input_value() and "16,900" in msg.input_value(), msg.input_value()[:120])
        page.locator("[data-testid=request-explanation-form] [data-testid=preview-request]").click()
        page.locator("[data-testid=request-explanation-form] [data-testid=send-request]").click()
        expect(page.locator("[data-testid=decision-success]")).to_contain_text("לא נשלחה הודעת SMS", timeout=15000)
        open_requests = [q for q in snap()["customer_requests"] if q["status"] == "OPEN"]
        check("request · three in-app requests saved to the case", sorted(q["kind"] for q in open_requests) ==
              ["explanation", "missing_document", "missing_document"], json.dumps([q["title_he"] for q in open_requests], ensure_ascii=False))
        check("consistency · MCP sees the same open requests", mcp_open_requests() == 3)
        page.screenshot(path=str(ART / "after-3-requests-sent.png"))

        # the customer answers in the app and uploads both months from the requests
        cust = ctx.new_page()
        cust.set_viewport_size({"width": 1366, "height": 940})
        cust.goto(f"{BASE}/customer")
        cust.evaluate(f"localStorage.setItem('mz.case', '{CASE}')")
        cust.goto(f"{BASE}/customer")
        open_requests = [q for q in snap()["customer_requests"] if q["status"] == "OPEN"]
        expect(cust.locator("[data-testid=readiness-state]")).to_have_text(open_requests[0]["title_he"], timeout=20000)
        expect(cust.locator("[data-testid=card-more]")).to_contain_text(f"{len(open_requests) - 1} בקשות")
        check("customer · home card leads with the first request and counts the others", len(open_requests) == 3)
        cust.locator(".fab").click()
        cust.locator("[data-testid=chat-input]").fill("מה הבנקאית ביקשה ממני?")
        before = cust.locator(".bubble.assistant[data-role=assistant]").count()
        cust.locator("[data-testid=chat-send]").click()
        cust.wait_for_function(f"document.querySelectorAll('.bubble.assistant[data-role=assistant]').length > {before}", timeout=90000)
        reply = cust.locator(".bubble.assistant[data-role=assistant]").last.inner_text()
        check("consistency · the assistant answers from the same requests", any(w in reply for w in ("הסבר", "יולי", "אוגוסט")), reply[:140].replace("\n", " "))
        cust.locator(".sheet-head button").click()
        cust.locator(".bottom-nav button", has_text="מסמכים").click()
        cards = cust.locator("[data-testid=customer-request]")
        expect(cards).to_have_count(3, timeout=15000)
        exp = cards.filter(has_text="נדרש הסבר או אסמכתה")
        exp.locator("[data-testid=request-reply-open]").click()
        exp.locator("[data-testid=request-reply-text]").fill(ANSWER)
        cust.locator(".phone").screenshot(path=str(ART / "after-4-customer-reply.png"))
        exp.locator("[data-testid=request-reply-send]").click()
        expect(exp).to_contain_text("השבתם", timeout=15000)
        for month, name in (("יולי 2026", "noa_payslip_2026-07_scan.pdf"), ("אוגוסט 2026", "noa_payslip_2026-08.pdf")):
            card = cards.filter(has_text=f"נדרש תלוש {month}")
            card.locator("[data-testid=request-upload]").click()
            expect(cust.locator("[data-testid=upload-for-request]")).to_contain_text(month)
            cust.locator("[data-testid=file-input]").set_input_files(str(FIX / "out" / "main" / name))
            cust.locator("[data-testid=upload-submit]").click()
            expect(cust.locator("[data-testid=upload-answered]")).to_be_visible(timeout=20000)
            cust.locator(".sheet-head button").click()
        answered = {q["kind"]: q for q in snap()["customer_requests"]}
        check("customer · reply and uploads answer their requests",
              all(q["status"] == "RESPONDED" for q in snap()["customer_requests"]) and answered["explanation"]["responded_text"] == ANSWER)

        # Gemini re-reviews; the finding stays open with the full comparison and the unverified explanation
        settle()
        item = variance()
        check("revalidation · finding still open for the banker, now on all three months",
              item and item["finding"]["finding_id"] == fid and not item["basis"]["partial"] and "על בסיס כל 3 החודשים" in item["finding"]["message_he"],
              (item or {}).get("finding", {}).get("message_he", "")[:160])
        check("revalidation · customer explanation attached, not closing anything",
              item["has_customer_statement"] and item["finding"]["statements"][0]["text"] == ANSWER)
        open_item(page, CASE, f"finding:{fid}")
        check("unverified explanation · panel marks it unverified and asks for support",
              "לא מאומת" in page.locator("[data-testid=customer-said]").inner_text()
              and "הסבר לבדו אינו מספיק" in page.locator("[data-testid=next-step]").inner_text())
        check("unverified explanation · comparison now complete", page.locator("[data-testid=comparison-basis]").inner_text() == "השוואה מלאה")
        page.screenshot(path=str(ART / "after-5-full-comparison.png"))

        # the banker resolves on documented evidence
        page.locator("[data-testid=finding-action-resolve]").click()
        page.locator("[data-testid=reason-explanation_supported]").check()
        boxes = page.locator("[data-testid=evidence-options] input[type=checkbox]")
        for i in range(boxes.count()):
            boxes.nth(i).check()
        page.locator("[data-testid=resolve-rationale]").fill(RATIONALE)
        page.locator("[data-testid=resolve-review]").click()
        confirm = page.locator("[data-testid=resolve-confirm]").inner_text()
        check("supporting evidence · confirmation lists the three payslips", all(m in confirm for m in ("יולי 2026", "אוגוסט 2026", "ספטמבר 2026")))
        page.locator("[data-testid=decision-panel]").screenshot(path=str(ART / "after-6-confirm-evidence.png"))
        page.locator("[data-testid=resolve-submit]").dblclick()
        expect(page.locator("[data-testid=decision-success]")).to_be_visible(timeout=15000)
        decisions = [d for d in api("GET", f"/api/banker/cases/{CASE}/package").json()["decisions"] if d["action"] == "RESOLVE_FINDING"]
        check("resolve · one audited decision with reason, evidence and actor", len(decisions) == 1
              and decisions[0]["reason_code"] == "explanation_supported" and decisions[0]["actor_id"] == "STAFF-DANA"
              and len({e["document_id"] for e in decisions[0]["evidence_refs"]}) >= 3, json.dumps(decisions, ensure_ascii=False)[:200])

        # persistence across a refresh and a later Gemini review
        page.reload()
        expect(page.locator(f"[data-testid=queue-group-done] [data-item-id='finding:{fid}']")).to_be_visible(timeout=20000)
        expect(page.locator("[data-testid=decision-history]")).to_contain_text("סגירת הבירור לאחר בדיקה")
        api("POST", f"/api/banker/cases/{CASE}/recheck", headers=DANA)
        time.sleep(2)
        settle()
        check("persistence · decision survives refresh and a later review",
              variance() is None and next(f for f in snap()["findings"] if f["finding_id"] == fid)["status"] == "resolved")
        page.screenshot(path=str(ART / "after-7-resolved.png"))

        # what the customer sees, and the same state in MCP
        cust.goto(f"{BASE}/customer")
        expect(cust.locator(".timeline")).to_contain_text("הנושא נבדק ונסגר", timeout=20000)
        raw = json.dumps(snap(), ensure_ascii=False)
        check("customer · sees a neutral update, never the internal reason", RATIONALE not in raw and RATIONALE not in cust.locator(".timeline").inner_text())
        cust.locator(".phone").screenshot(path=str(ART / "after-8-customer-timeline.png"))
        selftest = api("POST", "/api/system/mcp-selftest").json()
        check("consistency · MCP overview matches the app after the decision", selftest["consistent"] and mcp_open_requests() == 0,
              f"mcp={selftest['app_state']}")

        # an AI false positive on another case, dismissed with a reason
        golden = ws(GOLDEN)
        doc_item = next(i for i in golden["items"] if i["id"] == f"doc:{pay_doc}")
        pay_finding = next((f for f in doc_item["findings"] if f["code"] == "PAY_DATE_INCONSISTENT" and f["status"] == "open"), None)
        if check("false positive · pay-date fixture raises a banker finding", bool(pay_finding), str([f["code"] for f in doc_item["findings"]])):
            open_item(page, GOLDEN, f"doc:{pay_doc}")
            row = page.locator("[data-testid=desk-finding][data-code=PAY_DATE_INCONSISTENT]")
            row.locator("[data-testid=dismiss-finding]").click()
            page.locator("[data-testid=dismiss-reason]").select_option("rule_not_applicable")
            page.locator("[data-testid=dismiss-form] [data-testid=rationale]").fill("התאריך שמודפס באמצע החודש הוא מקדמה לפי הסכם העבודה; הכלל אינו חל")
            page.locator("[data-testid=dismiss-review]").click()
            page.locator("[data-testid=decision-panel]").screenshot(path=str(ART / "after-9-dismiss-confirm.png"))
            page.locator("[data-testid=dismiss-confirm] [data-testid=confirm-rationale]").click()
            expect(page.locator("[data-testid=decision-success]")).to_be_visible(timeout=15000)
            api("POST", f"/api/banker/cases/{GOLDEN}/recheck", headers=DANA)
            time.sleep(2)
            settle(GOLDEN)
            dismissed = next(f for f in snap(GOLDEN)["findings"] if f["finding_id"] == pay_finding["finding_id"])
            audit = next(e for e in api("GET", f"/api/cases/{GOLDEN}/audit").json() if e["action"] == "banker_finding_decision")
            check("false positive · dismissed, audited with reason and actor, not reopened by a later review",
                  dismissed["status"] == "dismissed" and audit["detail"]["reason_code"] == "rule_not_applicable"
                  and audit["actor"] == "banker:STAFF-DANA"
                  and not [f for f in snap(GOLDEN)["findings"] if f["key"] == pay_finding["key"] and f["status"] == "open"])

        s9 = snap()
        check("bank stage · unchanged by every action", s9["case"]["bank_stage"] == stage0 and snap(GOLDEN)["case"]["bank_stage"]["index"] == 2)
        browser.close()

    failed = [r for r in RESULTS if not r["pass"]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    (ART / "results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
