"""Conversational questionnaire (V2) in a real Chrome — the reported conversation defects and the full journey:
loan type first (business is not automatically a company), one coherent reply per submission (gross income, sent
twice; a double click), direct answers (approval, weather, the amount limit), several facts in one sentence, the
proactive indication framed on the requested amount, a reload, corrections and an edit from the summary, ambiguous
side jobs, a contextual policy question, one case on a double confirmation, the Documents handoff, V1 unchanged.

Isolated stack only. It runs whichever understanding the backend has: with no Gemini key (as below) every
reply comes from the deterministic path, and the results say so (`engine`). No review runs.

    # from backend/ — fresh DATA_DIR, Gemini switched off
    DATA_DIR=../e2e/artifacts/conv-v2/data GEMINI_API_KEY= GEMINI_MAX_CALLS_PER_HOUR=0 \
      ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8794
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/conv-v2/web 5847 http://127.0.0.1:8794
    CONV_BASE=http://127.0.0.1:5847 backend/.venv/bin/python e2e/check_conversational_v2.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

import isolation

BASE = os.environ.get("CONV_BASE", "http://127.0.0.1:5847")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
isolation.require_isolated(BASE)
OUT = Path(__file__).resolve().parent / "artifacts" / "conv-v2"
RESULTS: list[tuple[str, bool, str]] = []
ENGINE = {"value": "?"}


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def shot(page: Page, name: str, full: bool = False) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)


def items(page: Page) -> int:
    return page.locator("[data-testid=cv2-log] > *").count()


def settle(page: Page, before: int) -> None:
    page.wait_for_function(
        "n => document.querySelectorAll('[data-testid=cv2-log] > *').length > n && !document.querySelector('.cv2-typing')",
        arg=before, timeout=20000)
    page.wait_for_timeout(250)


def say(page: Page, text: str) -> None:
    before = items(page)
    page.locator("[data-testid=cv2-input]").fill(text)
    page.locator("[data-testid=cv2-input]").press("Enter")
    settle(page, before)


def reply(page: Page, label: str) -> None:
    before = items(page)
    page.locator("[data-testid=cv2-reply]", has_text=label).first.click()
    settle(page, before)


def action(page: Page, label: str) -> None:
    before = items(page)
    page.locator("[data-testid=cv2-action]", has_text=label).first.click()
    settle(page, before)


def pending(page: Page) -> str | None:
    loc = page.locator("[data-testid=cv2-pending]")
    return loc.first.get_attribute("data-question") if loc.count() else None


def stages(page: Page) -> dict[str, str]:
    return dict(page.locator("[data-testid=cv2-stages] li").evaluate_all(
        "els => els.map(e => [e.getAttribute('data-testid').replace('cv2-stage-', ''), e.getAttribute('data-state')])"))


def bot(page: Page) -> str:
    return page.locator(".cv2-row [data-testid=cv2-msg]").last.inner_text()


def state(page: Page) -> dict:
    did = page.locator("[data-testid=apply-v2]").get_attribute("data-draft")
    v1 = page.evaluate(f"fetch('/api/demo/onboarding/{did}').then(r => r.json())")
    v2 = page.evaluate(f"fetch('/api/demo/onboarding/{did}/v2').then(r => r.json())")
    return {"answers": {a["question_id"]: a["answer"] for a in v1["asked"]}, "loan": v2["loan"], "engine": v2["engine"],
            "messages": v2["messages"]}


def summary_codes(page: Page) -> list[str]:
    expect(page.locator("[data-testid=cv2-summary]")).to_be_visible(timeout=10000)
    return page.locator("[data-testid=cv2-req]").evaluate_all("els => els.map(e => e.getAttribute('data-code'))")


def open_v2(page: Page) -> None:
    page.goto(f"{BASE}/customer/apply")
    expect(page.locator("[data-testid=apply-v2]")).to_be_visible(timeout=15000)
    expect(page.locator("[data-testid=cv2-pending]").first).to_be_attached(timeout=10000)
    if page.locator("[data-testid=cv2-restart]").count():
        page.locator("[data-testid=cv2-restart]").click()
        page.wait_for_timeout(700)
    expect(page.locator("[data-testid=cv2-pending]").first).to_have_attribute("data-question", "loan_type", timeout=10000)
    ENGINE["value"] = page.locator("[data-testid=apply-v2]").get_attribute("data-engine") or "?"


def defects(page: Page) -> None:
    open_v2(page)
    labels = page.locator("[data-testid=cv2-reply]").all_inner_texts()
    check("A · the first question is the loan type: פרטית / עסקית",
          labels == ["הלוואה פרטית", "הלוואה עסקית"] and "איזו הלוואה מעניינת אותך" in bot(page), str(labels))
    shot(page, "01-desktop-welcome")

    for i in (1, 2):
        before = items(page)
        say(page, "אני מרוויח 19 אלף ברוטו, אפשר לחשב לי לפי זה?")
        text = bot(page)
        check(f"B · gross income (submission {i}): exactly one reply", items(page) == before + 2, f"{before} → {items(page)}")
        check(f"B · gross income (submission {i}): asks for net, keeps the loan-type question, no fallback",
              "נטו, ולא ברוטו" in text and "מידע מאומת" not in text and text.endswith("פרטית או עסקית?")
              and pending(page) == "loan_type", text)
    s = state(page)
    check("B · nothing recorded and no indication from a gross figure",
          s["answers"] == {} and page.locator("[data-testid=cv2-insight]").count() == 0, json.dumps(s["answers"]))
    shot(page, "02-desktop-gross")

    say(page, "אתה מבטיח לי שהבנק יאשר את ההלוואה?")
    check("H · approval: no promise, conditional review, the flow continues",
          bot(page).startswith("אני לא יכול להבטיח אישור, אבל אפשר לבדוק את הבקשה") and pending(page) == "loan_type", bot(page)[:70])
    say(page, "מה מזג האוויר בתל אביב מחר?")
    check("G · off-topic: short, no fabricated weather, state kept",
          "לא אוכל לתת תחזית מזג אוויר" in bot(page) and pending(page) == "loan_type", bot(page)[:70])
    say(page, "אני רוצה הלוואה של 300 אלף שקל.")
    check("F · 300k: the flow's limit (עד 250,000 ₪), nothing capped or recorded",
          "עד 250,000 ₪" in bot(page) and "amount" not in state(page)["answers"], bot(page)[:80])

    before = items(page)
    page.locator("[data-testid=cv2-reply]", has_text="הלוואה עסקית").evaluate("b => { b.click(); b.click(); }")
    settle(page, before)
    page.wait_for_timeout(600)
    s = state(page)
    users = [m for m in s["messages"] if m["role"] == "user" and m["text_he"] == "הלוואה עסקית"]
    check("B · a double click sends one turn", len(users) == 1 and items(page) == before + 2, f"{len(users)} user turns")
    check("A · a business loan asks how the business is registered — not automatically a company",
          pending(page) == "business_form" and "entity" not in s["answers"] and s["loan"]["type"] == "business",
          json.dumps(s["loan"]))
    reply(page, "עוסק פטור")
    s = state(page)
    check("A · business + עוסק פטור: the owner's individual path with business income and VAT-exempt",
          s["answers"].get("entity") == "individual" and s["answers"].get("income") == ["self_employed"]
          and s["answers"].get("registration") == "vat_exempt", json.dumps(s["answers"]))


def salaried(page: Page) -> None:
    open_v2(page)
    reply(page, "הלוואה פרטית")
    say(page, "מיכל ברק")
    check("A · personal loan → individual path; the assistant uses the name", "מיכל" in bot(page)
          and state(page)["answers"].get("entity") == "individual")
    say(page, "DEMO-ID-201")
    check("J · no indication before the income is known", page.locator("[data-testid=cv2-insight]").count() == 0)
    say(page, "אני שכירה, מרוויחה 16 אלף נטו, רוצה הלוואה של 80 אלף לרכב לחמש שנים.")
    a = state(page)["answers"]
    check("E · one sentence: purpose, amount, term, income and net captured; no repeat of captured facts",
          a.get("purpose") == "car" and a.get("amount") == 80000 and a.get("payments") == 60 and a.get("income") == ["salaried"]
          and a.get("net") == 16000 and pending(page) == "co_borrower", json.dumps(a, ensure_ascii=False))
    card = page.locator("[data-testid=cv2-insight]")
    check("J · proactive indication framed on the requested amount (deterministic 248,000 theoretical max)",
          card.count() == 1 and card.first.get_attribute("data-requested") == "80000" and card.first.get_attribute("data-max") == "248000"
          and "הבקשה שלך ל־80,000 ₪ נראית אפשרית להמשך בדיקה ראשונית" in bot(page), bot(page)[:90])
    visible = card.first.inner_text()
    check("J · the card leads with the request and the monthly payment; the ceiling is not on its face",
          "80,000" in visible and "1,550" in visible and "248,000" not in visible and "לא אישור הלוואה" in visible, visible[:80])
    card.first.locator("[data-testid=cv2-insight-more]").click()
    details = card.first.locator("[data-testid=cv2-insight-facts]").inner_text()
    check("J · disclaimer: not an eligibility check or approval; the ceiling and inputs are one tap away",
          "לא בדיקת זכאות או אישור" in bot(page) and "לא מסגרת אשראי" in details and "248,000" in details
          and "16,000" in details and "30%" in details and "6%" in details, details[:90])
    card.first.scroll_into_view_if_needed()
    shot(page, "03-desktop-indication")
    check("J · the indication card has no 'איך חישבת' button", page.locator("[data-testid=cv2-explain]").count() == 0)
    say(page, "איך חישבת את האינדיקציה?")
    text = bot(page)
    check("J · the explanation shows the real inputs and assumptions",
          "16,000" in text and "30%" in text and "6%" in text and "1,550" in text and pending(page) == "co_borrower", text[:90])

    count = items(page)
    page.reload()
    expect(page.locator("[data-testid=apply-v2]")).to_be_visible(timeout=15000)
    expect(page.locator("[data-testid=cv2-pending]").first).to_be_attached(timeout=10000)
    page.wait_for_timeout(500)
    check("K · reload restores the conversation, the stages and the pending question",
          items(page) == count and pending(page) == "co_borrower" and stages(page)["profile"] == "current", f"{count} → {items(page)}")

    reply(page, "לא, רק אני")
    codes = summary_codes(page)
    check("L · salaried summary: the policy's checklist", codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1",
                                                                     "PURPOSE_PROOF"], str(codes))
    check("L · loan type shown in the summary",
          "הלוואה פרטית" in page.locator("[data-testid=cv2-line][data-question=loan_type]").inner_text())
    page.locator("[data-testid=cv2-summary]").scroll_into_view_if_needed()
    shot(page, "04-desktop-summary")

    say(page, "בעצם אני רוצה 120 אלף במקום 80.")
    check("D · 'במקום': the amount is corrected without restarting",
          state(page)["answers"]["amount"] == 120000 and page.locator("[data-testid=cv2-summary]").is_visible())
    say(page, "אני לא שכיר, אני רק עצמאי.")
    a = state(page)["answers"]
    check("D · explicit correction: salaried removed, the VAT question opens, other answers kept",
          a["income"] == ["self_employed"] and pending(page) == "registration" and a["amount"] == 120000
          and stages(page)["profile"] == "current", json.dumps(a, ensure_ascii=False))
    reply(page, "עוסק פטור")
    codes = summary_codes(page)
    cards = page.locator("[data-testid=cv2-insight]")
    check("J · the checklist and the indication follow the change; older indications marked out of date",
          {"TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= set(codes) and "PAYSLIPS:BRW-A" not in codes
          and cards.nth(0).get_attribute("data-stale") == "1" and cards.last.get_attribute("data-stale") == "0"
          and cards.last.get_attribute("data-max") == "206000", str(codes))

    before = page.evaluate("fetch('/api/session/demo/cases').then(r => r.json()).then(d => d.length)")
    page.locator("[data-testid=cv2-confirm]").evaluate("b => { b.click(); b.click(); }")
    expect(page.locator("[data-testid=required-docs]")).to_be_visible(timeout=20000)
    after = page.evaluate("fetch('/api/session/demo/cases').then(r => r.json()).then(d => d.length)")
    check("L · confirming (clicked twice) creates exactly one case", after == before + 1, f"{before} → {after}")
    rows = page.locator("[data-testid=required-docs] li.dl-row").evaluate_all(
        "els => els.map(e => e.getAttribute('data-testid').replace(/^req-/, ''))")
    check("L · Documents shows exactly the summary's checklist", sorted(rows) == sorted(codes), str(rows))
    check("L · the next-step note without implying approval",
          "אינה אישור" in page.locator("[data-testid=cv2-handoff]").inner_text())
    shot(page, "05-desktop-documents")


def mixed_mobile(page: Page) -> None:
    open_v2(page)
    shot(page, "06-mobile-welcome")
    reply(page, "הלוואה פרטית")
    say(page, "אני שכיר ויש לי גם עוסק פטור, אני מרוויח בערך 16 אלף נטו ורוצה 80 אלף לרכב לחמש שנים.")
    a = state(page)["answers"]
    check("E · mixed income in one sentence: both sources, VAT-exempt, net, amount, term, purpose",
          a.get("income") == ["salaried", "self_employed"] and a.get("registration") == "vat_exempt" and a.get("net") == 16000
          and a.get("amount") == 80000 and a.get("payments") == 60 and a.get("purpose") == "car", json.dumps(a, ensure_ascii=False))
    check("E · acknowledges two incomes and asks only for what is missing (the name)",
          "שתי" in bot(page) and pending(page) == "name", bot(page)[:90])
    say(page, "יוסי לוי")
    say(page, "DEMO-ID-202")
    page.locator(".cv2-row").last.scroll_into_view_if_needed()
    shot(page, "07-mobile-mixed")
    say(page, "למה אני צריך גם אישור עוסק?")
    check("I · contextual policy answer: the VAT-exempt certificate, from the policy; pending question kept",
          "אישור עוסק פטור" in bot(page) and "נמשיך מהנקודה" not in bot(page) and pending(page) == "co_borrower", bot(page)[:90])

    before = items(page)
    page.locator("[data-testid=cv2-summary]").count()
    page.locator("[data-testid=cv2-input]").fill("לשנות את מקור ההכנסה")
    page.locator("[data-testid=cv2-input]").press("Enter")
    settle(page, before)
    say(page, "אני עובד פה ושם, לפעמים כשכיר ולפעמים עושה עבודות מהצד. לא ממש יודע איך להגדיר את עצמי.")
    a = state(page)["answers"]
    acts = page.locator("[data-testid=cv2-action]").all_inner_texts()
    check("C · ambiguous side jobs: clarifying question, no confident reclassification",
          "עסק עצמאי" in bot(page) and a.get("income") == ["salaried", "self_employed"] and pending(page) == "income"
          and "הכול כשכיר" in acts, f"{acts} · {bot(page)[:60]}")
    shot(page, "08-mobile-clarify")
    action(page, "הכול כשכיר")
    check("C · the clarification answer is recorded through the questionnaire",
          state(page)["answers"].get("income") == ["salaried"] and pending(page) == "co_borrower")
    reply(page, "לא, רק אני")
    page.locator("[data-testid=cv2-insight]").last.scroll_into_view_if_needed()
    shot(page, "09-mobile-indication")
    box = page.locator("[data-testid=cv2-input]").bounding_box()
    check("mobile · the text input stays usable (16px, inside the viewport)",
          box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390
          and page.locator("[data-testid=cv2-input]").evaluate("e => getComputedStyle(e).fontSize") == "16px")


def v1_still_works(page: Page) -> None:
    page.goto(f"{BASE}/customer/apply/classic")
    expect(page.locator("[data-testid=apply-chat]")).to_be_visible(timeout=15000)
    if page.locator("[data-testid=onb-restart]").count():
        page.locator("[data-testid=onb-restart]").click()
    expect(page.locator("[data-testid=onb-question]")).to_have_attribute("data-question", "entity", timeout=10000)

    def pick(qid: str, value: str) -> None:
        page.locator(f"[data-testid=onb-option][data-value='{value}']").click()
        expect(page.locator(f"[data-testid=onb-answered-{qid}]")).to_be_visible(timeout=10000)

    pick("entity", "individual")
    page.locator("[data-testid=onb-first]").fill("דנה")
    page.locator("[data-testid=onb-last]").fill("רז")
    page.locator("[data-testid=onb-send]").click()
    expect(page.locator("[data-testid=onb-answered-name]")).to_be_visible(timeout=10000)
    page.locator("[data-testid=onb-text]").fill("DEMO-ID-301")
    page.locator("[data-testid=onb-send]").click()
    expect(page.locator("[data-testid=onb-answered-national_id]")).to_be_visible(timeout=10000)
    pick("purpose", "car")
    page.locator("[data-testid=onb-option][data-value='salaried']").click()
    page.locator("[data-testid=onb-send]").click()
    expect(page.locator("[data-testid=onb-answered-income]")).to_be_visible(timeout=10000)
    pick("net", "12000")
    pick("co_borrower", "no")
    pick("amount", "80000")
    pick("payments", "60")
    expect(page.locator("[data-testid=onb-summary]")).to_be_visible(timeout=10000)
    codes = page.locator("[data-testid=onb-req]").evaluate_all("els => els.map(e => e.getAttribute('data-code'))")
    check("M · V1 questionnaire unchanged (entity first, same checklist)",
          codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"], str(codes))
    page.locator("[data-testid=onb-confirm]").click()
    expect(page.locator("[data-testid=required-docs]")).to_be_visible(timeout=20000)
    check("M · V1 confirmation opens Documents without the V2 note", page.locator("[data-testid=cv2-handoff]").count() == 0)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        desk = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL").new_page()
        phone = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True,
                                    has_touch=True, device_scale_factor=2).new_page()
        for step, page in ((defects, desk), (salaried, desk), (mixed_mobile, phone), (v1_still_works, desk)):
            try:
                step(page)
            except Exception as exc:
                check(f"{step.__name__} completed", False, repr(exc)[:300])
                shot(page, f"error-{step.__name__}", full=True)
        browser.close()
    failed = [r for r in RESULTS if not r[1]]
    (OUT / "results.json").write_text(json.dumps({"base": BASE, "engine": ENGINE["value"], "passed": len(RESULTS) - len(failed),
                                                  "failed": len(failed), "results": [{"check": n, "ok": ok, "detail": d}
                                                                                     for n, ok, d in RESULTS]},
                                                 ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed · understanding engine: {ENGINE['value']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
