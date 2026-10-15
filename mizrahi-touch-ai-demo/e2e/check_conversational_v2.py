"""Conversational questionnaire (V2) in a real Chrome: a salaried car loan by free text and quick replies, a proactive
DEMO indication with its explanation, a policy question mid-flow that resumes the same question, a reload, a later
correction to mixed income, an edit from the summary, one case on a double confirmation, the mixed-income sentence
on a phone viewport, and V1 still working next to it.

Isolated stack only — no review runs and no Gemini call (the questionnaire never calls a model). Creates demo
applications in its own DATA_DIR.

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

BASE = os.environ.get("CONV_BASE", "http://127.0.0.1:5847")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
OUT = Path(__file__).resolve().parent / "artifacts" / "conv-v2"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def shot(page: Page, name: str, full: bool = False) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)


def msgs(page: Page) -> int:
    return page.locator("[data-testid=cv2-log] > *").count()


def settle(page: Page, before: int) -> None:
    page.wait_for_function(
        "n => document.querySelectorAll('[data-testid=cv2-log] > *').length > n && !document.querySelector('.cv2-typing')",
        arg=before, timeout=15000)
    page.wait_for_timeout(250)


def say(page: Page, text: str) -> None:
    before = msgs(page)
    page.locator("[data-testid=cv2-input]").fill(text)
    page.locator("[data-testid=cv2-input]").press("Enter")
    settle(page, before)


def reply(page: Page, label: str) -> None:
    before = msgs(page)
    page.locator("[data-testid=cv2-reply]", has_text=label).first.click()
    settle(page, before)


def pending(page: Page) -> str | None:
    loc = page.locator("[data-testid=cv2-pending]")
    return loc.first.get_attribute("data-question") if loc.count() else None


def stages(page: Page) -> dict[str, str]:
    return dict(page.locator("[data-testid=cv2-stages] li").evaluate_all(
        "els => els.map(e => [e.getAttribute('data-testid').replace('cv2-stage-', ''), e.getAttribute('data-state')])"))


def last_text(page: Page, kind: str | None = None) -> str:
    sel = f"[data-testid=cv2-msg][data-kind={kind}]" if kind else "[data-testid=cv2-msg]"
    return page.locator(sel).last.inner_text()


def draft_answers(page: Page) -> dict:
    did = page.locator("[data-testid=apply-v2]").get_attribute("data-draft")
    asked = page.evaluate(f"fetch('/api/demo/onboarding/{did}').then(r => r.json()).then(d => d.asked)")
    return {a["question_id"]: a["answer"] for a in asked}


def summary_codes(page: Page) -> list[str]:
    expect(page.locator("[data-testid=cv2-summary]")).to_be_visible(timeout=10000)
    return page.locator("[data-testid=cv2-req]").evaluate_all("els => els.map(e => e.getAttribute('data-code'))")


def open_v2(page: Page, fresh: bool = True) -> None:
    page.goto(f"{BASE}/customer/apply")
    expect(page.locator("[data-testid=apply-chat]")).to_be_visible(timeout=15000)
    page.locator("[data-testid=apply-switch-v2]").click()
    expect(page.locator("[data-testid=apply-v2]")).to_be_visible(timeout=15000)
    expect(page.locator("[data-testid=cv2-pending]").first).to_be_attached(timeout=10000)
    if fresh and page.locator("[data-testid=cv2-restart]").count():
        page.locator("[data-testid=cv2-restart]").click()
        page.wait_for_timeout(600)
    expect(page.locator("[data-testid=cv2-pending]").first).to_have_attribute("data-question", "entity", timeout=10000)


def salaried_car(page: Page) -> None:
    open_v2(page)
    st = stages(page)
    check("A · the stages start at the introduction, nothing done",
          list(st) == ["intro", "loan", "profile", "summary"] and st["intro"] == "current"
          and all(v == "upcoming" for k, v in st.items() if k != "intro"), str(st))
    shot(page, "01-desktop-start")
    say(page, "אני רוצה לקנות רכב ב־80 אלף שקל")
    a = draft_answers(page)
    check("A · one free-text sentence records purpose, amount and the private-loan path",
          a == {"entity": "individual", "purpose": "car", "amount": 80000} and pending(page) == "name", json.dumps(a, ensure_ascii=False))
    check("A · contextual reply mentions the car", "הרכב" in page.locator("[data-testid=cv2-msg][data-kind=text]").last.inner_text())
    say(page, "מיכל ברק")
    check("A · the assistant uses the customer's name", "מיכל" in last_text(page, "question"), last_text(page, "question"))
    say(page, "DEMO-ID-201")
    check("E · no personalised amount before the income is known",
          page.locator("[data-testid=cv2-insight]").count() == 0 and pending(page) == "payments")
    reply(page, "60 תשלומים")
    say(page, "אני שכירה, מרוויחה בערך 16 אלף נטו")
    ins = page.locator("[data-testid=cv2-insight]")
    check("D · the indication appears on its own once income, amount and term are known",
          ins.count() == 1 and ins.first.get_attribute("data-max") == "248000", ins.first.get_attribute("data-max") or "")
    txt = ins.first.inner_text()
    check("D · labelled as a DEMO illustration, not an offer or approval",
          "הדגמה" in txt and "לא הצעה ולא אישור" in txt, txt[:80])
    check("D · the questionnaire continues at the next question", pending(page) == "co_borrower")
    ins.first.scroll_into_view_if_needed()
    shot(page, "02-desktop-indication")
    before = msgs(page)
    page.locator("[data-testid=cv2-explain]").click()
    settle(page, before)
    explain = page.locator("[data-testid=cv2-msg][data-kind=text]").last.inner_text()
    check("D · the explanation shows the declared income and the demo assumptions",
          "16,000" in explain and "30%" in explain and "6%" in explain and "60 תשלומים" in explain, explain[:90])
    check("D · after the explanation the same question is pending", pending(page) == "co_borrower")
    shot(page, "03-desktop-explanation")

    say(page, "למה צריך שלושה תלושי שכר?")
    q = last_text(page, "question")
    answer = page.locator("[data-testid=cv2-msg][data-kind=text]").last.inner_text()
    check("C · a policy question mid-flow is answered from the policy (months by simulation date)",
          "3 תלושים" in answer and "ספטמבר 2026" in answer, answer[:90])
    check("C · and resumes the exact pending question with its quick replies",
          q.startswith("נמשיך") and pending(page) == "co_borrower"
          and page.locator("[data-testid=cv2-reply]", has_text="לא, רק אני").count() == 1, q[:60])
    shot(page, "04-desktop-interruption")

    count = msgs(page)
    page.reload()
    expect(page.locator("[data-testid=apply-v2]")).to_be_visible(timeout=15000)
    expect(page.locator("[data-testid=cv2-pending]").first).to_be_attached(timeout=10000)
    page.wait_for_timeout(400)
    check("G · a reload restores the transcript, the stages and the pending question",
          msgs(page) == count and pending(page) == "co_borrower" and stages(page)["profile"] == "current", f"{count} → {msgs(page)}")

    reply(page, "לא, רק אני")
    codes = summary_codes(page)
    check("A · the summary lists the salaried checklist from the policy",
          codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"], str(codes))
    check("A · all question stages done, summary current",
          stages(page) == {"intro": "done", "loan": "done", "profile": "done", "summary": "current"}, str(stages(page)))
    page.locator("[data-testid=cv2-summary]").scroll_into_view_if_needed()
    shot(page, "05-desktop-summary")

    say(page, "בעצם יש לי גם עסק קטן כעוסק פטור")
    a = draft_answers(page)
    codes = summary_codes(page)
    insights = page.locator("[data-testid=cv2-insight]")
    check("F · a later correction to mixed income updates the profile",
          a.get("income") == ["salaried", "self_employed"] and a.get("registration") == "vat_exempt", json.dumps(a, ensure_ascii=False))
    check("F · and the checklist (payslips kept, tax assessment and VAT-exempt certificate added)",
          {"PAYSLIPS:BRW-A", "TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= set(codes), str(codes))
    check("F · the indication is recalculated (more conservative) and the old one marked out of date",
          insights.count() == 2 and insights.nth(0).get_attribute("data-stale") == "1"
          and insights.nth(1).get_attribute("data-max") == "206000", insights.nth(1).get_attribute("data-max") or "")

    before = msgs(page)
    page.locator("[data-testid=cv2-edit-amount]").click()
    settle(page, before)
    check("F · editing from the summary re-asks that question, the loan stage becomes current",
          pending(page) == "amount" and stages(page)["loan"] == "current"
          and page.locator("[data-testid=cv2-cancel-edit]").is_visible())
    reply(page, "120,000 ₪")
    a = draft_answers(page)
    check("F · the edit is saved and the summary returns",
          a["amount"] == 120000 and page.locator("[data-testid=cv2-summary]").is_visible()
          and "120,000" in page.locator("[data-testid=cv2-line][data-question=amount]").inner_text())
    final_codes = summary_codes(page)

    before_cases = page.evaluate("fetch('/api/session/demo/cases').then(r => r.json()).then(d => d.length)")
    page.locator("[data-testid=cv2-confirm]").evaluate("b => { b.click(); b.click(); }")
    expect(page.locator("[data-testid=document-profile]")).to_be_visible(timeout=20000)
    after_cases = page.evaluate("fetch('/api/session/demo/cases').then(r => r.json()).then(d => d.length)")
    check("H · confirming (clicked twice) creates exactly one case", after_cases == before_cases + 1, f"{before_cases} → {after_cases}")
    rows = page.locator("[data-testid=required-docs] li.dl-row").evaluate_all(
        "els => els.map(e => e.getAttribute('data-testid').replace(/^req-/, ''))")
    check("H · the case opens on Documents with exactly the summary's checklist", sorted(rows) == sorted(final_codes), str(rows))
    check("H · the assistant explains the next step without implying approval",
          page.locator("[data-testid=cv2-handoff]").is_visible()
          and "אינה אישור" in page.locator("[data-testid=cv2-handoff]").inner_text())
    shot(page, "06-desktop-documents")


def mixed_mobile(page: Page) -> None:
    open_v2(page)
    shot(page, "07-mobile-start")
    say(page, "אני שכיר ויש לי גם עוסק פטור, אני רוצה 80 אלף שקל לרכב")
    a = draft_answers(page)
    check("B · the mixed-income sentence captures both sources, VAT-exempt, purpose and amount",
          a.get("income") == ["salaried", "self_employed"] and a.get("registration") == "vat_exempt"
          and a.get("purpose") == "car" and a.get("amount") == 80000, json.dumps(a, ensure_ascii=False))
    check("B · the reply acknowledges both income sources", "גם ממשכורת וגם מעסק" in
          page.locator("[data-testid=cv2-msg][data-kind=text]").last.inner_text())
    shot(page, "08-mobile-mixed")
    say(page, "יוסי לוי")
    say(page, "DEMO-ID-202")
    reply(page, "48 תשלומים")
    check("B · the VAT question is skipped (already answered) and the income question asks for both together",
          pending(page) == "net" and "מהמשכורת ומהעסק יחד" in last_text(page, "question"), last_text(page, "question")[:60])
    say(page, "בערך 14 אלף")
    page.locator("[data-testid=cv2-insight]").last.scroll_into_view_if_needed()
    shot(page, "09-mobile-indication")
    reply(page, "לא, רק אני")
    codes = summary_codes(page)
    check("B · the mixed checklist: payslips, tax assessment and VAT-exempt certificate",
          {"PAYSLIPS:BRW-A", "TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= set(codes) and "VAT_DEALER_CERT:BRW-A" not in codes, str(codes))
    page.locator("[data-testid=cv2-summary]").scroll_into_view_if_needed()
    shot(page, "10-mobile-summary")
    page.locator("[data-testid=cv2-input]").scroll_into_view_if_needed()
    box = page.locator("[data-testid=cv2-input]").bounding_box()
    check("B · on a phone the text input stays usable (16px, within the viewport width)",
          box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390
          and page.locator("[data-testid=cv2-input]").evaluate("e => getComputedStyle(e).fontSize") == "16px")


def v1_still_works(page: Page) -> None:
    page.goto(f"{BASE}/customer/apply")
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
    check("I · V1 questionnaire unchanged: same salaried checklist",
          codes == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"], str(codes))
    page.locator("[data-testid=onb-confirm]").click()
    expect(page.locator("[data-testid=document-profile]")).to_be_visible(timeout=20000)
    check("I · V1 confirmation opens the case on Documents, without the V2 note",
          page.locator("[data-testid=cv2-handoff]").count() == 0)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        desk = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL").new_page()
        phone = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True,
                                    has_touch=True, device_scale_factor=2).new_page()
        for step, page in ((salaried_car, desk), (mixed_mobile, phone), (v1_still_works, desk)):
            try:
                step(page)
            except Exception as exc:
                check(f"{step.__name__} completed", False, repr(exc)[:300])
                shot(page, f"error-{step.__name__}", full=True)
        browser.close()
    failed = [r for r in RESULTS if not r[1]]
    (OUT / "results.json").write_text(json.dumps({"base": BASE, "passed": len(RESULTS) - len(failed), "failed": len(failed),
                                                  "results": [{"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS]},
                                                 ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
