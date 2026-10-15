"""Loan simulator inside the application chat, in a real Chrome on a phone viewport (390×844, touch): the card replaces
the amount and term questions right after the purpose, recalculates locally with the server's numbers, enforces the
product rules, confirms into the questionnaire and continues the conversation; conversation ↔ card in both directions;
the instant loan's deferral; the personal (V2) picture and a target payment; a reload; mobile layout.

Isolated stack only, no model (every reply is deterministic; the results say which engine answered). No review runs.

    # from backend/ — fresh DATA_DIR, Gemini switched off
    DATA_DIR=../e2e/artifacts/loan-sim/data GEMINI_API_KEY= GEMINI_MAX_CALLS_PER_HOUR=0 \
      ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8796
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/loan-sim/web 5849 http://127.0.0.1:8796
    LOANSIM_BASE=http://127.0.0.1:5849 backend/.venv/bin/python e2e/check_loan_simulator.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("LOANSIM_BASE", "http://127.0.0.1:5849")
if any(p in BASE for p in (":8790", ":8791", ":5192", ":5190")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
OUT = Path(__file__).resolve().parent / "artifacts" / "loan-sim"
RESULTS: list[tuple[str, bool, str]] = []
ENGINE = {"value": "?"}


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def shot(page: Page, name: str, el=None) -> None:
    (el or page).screenshot(path=str(OUT / f"{name}.png"))


def items(page: Page) -> int:
    return page.locator("[data-testid=cv2-log] > *").count()


def settle(page: Page, before: int) -> None:
    page.wait_for_function(
        "n => document.querySelectorAll('[data-testid=cv2-log] > *').length > n && !document.querySelector('.cv2-typing')",
        arg=before, timeout=20000)
    page.wait_for_timeout(300)


def say(page: Page, text: str) -> None:
    before = items(page)
    page.locator("[data-testid=cv2-input]").fill(text)
    page.locator("[data-testid=cv2-input]").press("Enter")
    settle(page, before)


def reply(page: Page, label: str) -> None:
    before = items(page)
    page.locator("[data-testid=cv2-reply]", has_text=label).first.click()
    settle(page, before)


def click_and_settle(page: Page, locator) -> None:
    before = items(page)
    locator.click()
    settle(page, before)


def bot(page: Page) -> str:
    return page.locator(".cv2-row [data-testid=cv2-msg]").last.inner_text()


def pending(page: Page) -> tuple[str | None, str | None]:
    loc = page.locator("[data-testid=cv2-pending]")
    return (loc.first.get_attribute("data-question"), loc.first.get_attribute("data-kind")) if loc.count() else (None, None)


def server(page: Page) -> dict:
    did = page.locator("[data-testid=apply-v2]").get_attribute("data-draft")
    v1 = page.evaluate(f"fetch('/api/demo/onboarding/{did}').then(r => r.json())")
    v2 = page.evaluate(f"fetch('/api/demo/onboarding/{did}/v2').then(r => r.json())")
    return {"answers": {a["question_id"]: a["answer"] for a in v1["asked"]}, "sim": v2["simulation"], "messages": v2["messages"],
            "engine": v2["engine"]}


def card(page: Page):
    return page.locator("[data-testid=ls-card]")


def wait_saved(page: Page, key: str, value) -> dict:
    """The card saves its draft with a debounce; wait until the server holds it, then return the server's view."""
    for _ in range(30):
        s = server(page)
        if s["sim"] and s["sim"]["draft"].get(key) == value:
            return s
        page.wait_for_timeout(150)
    return server(page)


def open_chat(page: Page) -> None:
    page.goto(f"{BASE}/customer/apply")
    expect(page.locator("[data-testid=apply-v2]")).to_be_visible(timeout=15000)
    expect(page.locator("[data-testid=cv2-pending]").first).to_be_attached(timeout=10000)
    if page.locator("[data-testid=cv2-restart]").count():
        page.locator("[data-testid=cv2-restart]").click()
        page.wait_for_timeout(800)
    expect(page.locator("[data-testid=cv2-pending]").first).to_have_attribute("data-question", "loan_type", timeout=10000)
    ENGINE["value"] = page.locator("[data-testid=apply-v2]").get_attribute("data-engine") or "?"


def layout(page: Page, tag: str) -> None:
    m = page.evaluate("""() => { const s = document.querySelector('.screen'), c = document.querySelector('[data-testid=ls-card]');
      const r = c ? c.getBoundingClientRect() : null;
      return { doc: document.documentElement.scrollWidth, vw: innerWidth, screen: s ? s.scrollWidth - s.clientWidth : 0,
               left: r ? r.left : 0, right: r ? r.right : 0,
               wide: [...document.querySelectorAll('[data-testid=ls-card] *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).length }; }""")
    check(f"mobile · {tag}: no horizontal overflow, the card inside the viewport",
          m["doc"] <= m["vw"] and m["screen"] <= 1 and m["left"] >= 0 and m["right"] <= m["vw"] and m["wide"] == 0, json.dumps(m))


# ---------------------------------------------------------------- journey 1: car
def car(page: Page) -> None:
    open_chat(page)
    reply(page, "הלוואה פרטית")
    say(page, "ניר נקש")
    say(page, "DEMO-ID-201")
    reply(page, "רכישת רכב")
    c = card(page)
    expect(c).to_be_visible(timeout=5000)
    q, kind = pending(page)
    texts = [m["text_he"] for m in server(page)["messages"] if m["role"] == "assistant"]
    check("J1 · the purpose opens the simulator card inside the chat, before any amount question",
          c.get_attribute("data-state") == "draft" and q == "amount" and kind == "simulator"
          and not any("איזה סכום" in t or "כמה תשלומים" in t for t in texts), f"{q}/{kind}")
    check("J1 · the assistant introduces it (car wording) and no amount chips are offered",
          bot(page).startswith("מעולה 🚗") and page.locator("[data-testid=cv2-reply]").count() == 0, bot(page)[:60])
    page.locator("[data-testid=ls-product]").click()
    tracks = page.locator("[data-testid=ls-track]").count()
    page.locator("[data-testid=ls-product]").click()
    check("J1 · the car loan configuration: product picker (4 candidates), vehicle price field, illustrative rate tag",
          c.get_attribute("data-product") == "car" and tracks == 4 and page.locator("[data-testid=ls-track]").count() == 0
          and page.locator("[data-testid=ls-asset-input]").count() == 1 and "המחשה" in c.inner_text())
    check("J1 · the in-chat card has no schedule table and no assumptions block",
          c.locator("table").count() == 0 and "לוח סילוקין" not in c.inner_text() and "על מה החישוב מבוסס" not in c.inner_text())
    height = c.bounding_box()["height"]
    check("mobile · the open car card fits within one phone screen (≤ 560px of 844)", height <= 560, f"{height:.0f}px")
    layout(page, "car card")
    c.scroll_into_view_if_needed()
    shot(page, "01-car-card")

    before = c.get_attribute("data-monthly")
    page.locator("[data-testid=ls-amount-input]").fill("180000")
    after_amount = c.get_attribute("data-monthly")
    rng = page.locator("[data-testid=ls-term-range]")
    rng.fill("48")
    s = wait_saved(page, "term", 48)
    check("J1 · typing the amount and moving the term recalculate immediately, without a chat message",
          before != after_amount != c.get_attribute("data-monthly") and c.get_attribute("data-term") == "48"
          and not s["answers"].get("amount"), f"{before} → {after_amount} → {c.get_attribute('data-monthly')}")
    srv = s["sim"]["draft_eval"]["result"]["monthly_payment"]
    check("J1 · the card's figure is the server engine's figure (parity)", float(c.get_attribute("data-monthly")) == srv,
          f"card {c.get_attribute('data-monthly')} · server {srv}")
    box = page.locator("[data-testid=ls-amount-range]").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.25, box["y"] + box["height"] / 2, steps=8)
    page.mouse.up()
    dragged = int(c.get_attribute("data-amount"))
    check("J1 · dragging the amount slider moves the amount (RTL: leftwards is more)", dragged > 180000, str(dragged))
    page.locator("[data-testid=ls-amount-input]").fill("180000")
    page.locator("[data-testid=ls-asset-input]").fill("200000")
    page.wait_for_timeout(250)
    issue = page.locator("[data-testid=ls-issue], .ls-issue[data-code=financing_ratio]")
    check("J1 · 180,000 on a 200,000 car: 90% financing shown above the 85% rule, constructively, confirm disabled",
          issue.count() >= 1 and "90% מימון, מעל 85% במסלול" in page.locator("[data-testid=ls-issues]").inner_text()
          and "גבוה משיעור המימון" in (page.locator(".ls-issue p").first.get_attribute("title") or "")
          and page.locator("[data-testid=ls-ratio]").get_attribute("data-pct") == "90"
          and page.locator("[data-testid=ls-confirm]").is_disabled())
    shot(page, "02-car-ratio", c)
    page.locator("[data-testid=ls-fix]").first.click()
    page.wait_for_timeout(200)
    check("J1 · the fix lowers the amount to 85% (170,000) and enables confirmation",
          c.get_attribute("data-amount") == "170000" and page.locator("[data-testid=ls-confirm]").is_enabled())
    click_and_settle(page, page.locator("[data-testid=ls-confirm]"))
    s = server(page)
    q, kind = pending(page)
    check("J1 · confirming records amount and payments in the application and the conversation continues",
          s["answers"].get("amount") == 170000 and s["answers"].get("payments") == 48 and q == "income"
          and card(page).get_attribute("data-state") == "confirmed", json.dumps({k: s["answers"].get(k) for k in ("amount", "payments")}))
    check("J1 · the reply states the confirmed scenario from the engine (no approval wording)",
          "170,000" in bot(page) and "3,992" in bot(page) and "לא הצעה" in bot(page), bot(page)[:90])
    check("J1 · the earlier card is now a one-line record", page.locator("[data-testid=ls-snapshot]").count() >= 1)
    shot(page, "03-car-confirmed")

    # conversation → card
    say(page, "בעצם אני רוצה רק 80 אלף")
    s = server(page)
    check("J1 · 'בעצם רק 80 אלף' updates the scenario (term kept) and the live card follows",
          s["answers"]["amount"] == 80000 and s["answers"]["payments"] == 48 and card(page).get_attribute("data-amount") == "80000", bot(page)[:70])
    say(page, "אני רוצה לפרוס את זה ל־60 תשלומים")
    s = server(page)
    check("J1 · 'לפרוס ל־60 תשלומים' updates the term and keeps the amount",
          s["answers"]["payments"] == 60 and s["answers"]["amount"] == 80000 and card(page).get_attribute("data-term") == "60")
    reply(page, "משכורת")
    say(page, "12 אלף נטו")
    reply(page, "לא, רק אני")
    asked = [m.get("question_id") for m in server(page)["messages"] if m["role"] == "assistant"]
    check("J1 · no separate amount or term question was asked at any point", "payments" not in asked, str(asked))
    expect(page.locator("[data-testid=cv2-summary]")).to_be_visible(timeout=10000)
    line = page.locator("[data-testid=cv2-line][data-question=simulation]").inner_text()
    check("J1 · the summary shows the confirmed scenario (product, estimated repayment, vehicle price)",
          "הלוואה לרכב" in line and "200,000" in line and "המחשה" in line, line)
    page.locator("[data-testid=cv2-confirm]").click()
    expect(page.locator("[data-testid=required-docs]")).to_be_visible(timeout=20000)
    check("J1 · the existing workflow continues: the case opens on Documents with the checklist",
          page.locator("[data-testid=required-docs] li.dl-row").count() >= 4)
    shot(page, "04-car-documents")


# ---------------------------------------------------------------- journey 2: celebration
def celebration(page: Page) -> None:
    open_chat(page)
    reply(page, "הלוואה פרטית")
    say(page, "מיכל ברק")
    say(page, "DEMO-ID-203")
    say(page, "חתונה")
    c = card(page)
    check("J2 · wedding → the celebration loan, no vehicle fields",
          c.get_attribute("data-product") == "happy_event" and page.locator("[data-testid=ls-asset-input]").count() == 0
          and bot(page).startswith("מזל טוב"), bot(page)[:40])
    check("J2 · the amount slider's top is the product cap (100,000) and the term's is 84",
          page.locator("[data-testid=ls-amount-range]").get_attribute("max") == "100000"
          and page.locator("[data-testid=ls-term-range]").get_attribute("max") == "84")
    page.locator("[data-testid=ls-amount-input]").fill("120000")
    page.wait_for_timeout(200)
    check("J2 · 120,000 is above the cap: explained, confirm disabled",
          "עד 100,000" in page.locator("[data-testid=ls-issues]").inner_text() and page.locator("[data-testid=ls-confirm]").is_disabled())
    shot(page, "05-celebration-cap", c)
    page.locator("[data-testid=ls-fix]").first.click()
    click_and_settle(page, page.locator("[data-testid=ls-confirm]"))
    s = server(page)
    check("J2 · confirmation at the cap works", s["answers"].get("amount") == 100000 and pending(page)[0] == "income")


# ---------------------------------------------------------------- journey 3: instant loan
def instant(page: Page) -> None:
    open_chat(page)
    say(page, "הלוואה ברגע")
    say(page, "דנה רז")
    say(page, "DEMO-ID-202")
    say(page, "חופשה")
    c = card(page)
    check("J3 · 'הלוואה ברגע' at the first question → personal loan, the instant-loan configuration (2–72, ≤125,000)",
          c.get_attribute("data-product") == "express" and page.locator("[data-testid=ls-term-range]").get_attribute("min") == "2"
          and page.locator("[data-testid=ls-term-range]").get_attribute("max") == "72"
          and page.locator("[data-testid=ls-amount-range]").get_attribute("max") == "125000")
    plain = float(c.get_attribute("data-monthly"))
    page.locator("[data-testid=ls-options-toggle]").click()
    page.locator("[data-testid=ls-deferral-opt][data-months='3']").click()
    page.wait_for_timeout(250)
    cap = float(c.get_attribute("data-monthly"))
    first = page.locator("[data-testid=ls-first-payment]").inner_text()
    extra = page.locator("[data-testid=ls-deferral-extra]").inner_text()
    check("J3 · a 3-month deferral moves the first payment to February 2027 and costs interest (capitalized, labelled)",
          "פברואר 2027" in first and cap > plain and "לא חישוב רשמי" in c.inner_text() and extra.strip() not in ("0 ₪", ""),
          f"{plain} → {cap} · {first} · {extra}")
    page.locator("[data-testid=ls-policy][data-policy=interest_only]").click()
    page.wait_for_timeout(200)
    io = float(c.get_attribute("data-monthly"))
    check("J3 · the interest-only policy keeps the regular installment and shows the interest paid meanwhile",
          io == plain and "ריבית בלבד" in page.locator("[data-testid=ls-deferral-impact]").inner_text(), f"{io} vs {plain}")
    c.scroll_into_view_if_needed()
    shot(page, "06-instant-deferral", c)
    click_and_settle(page, page.locator("[data-testid=ls-confirm]"))
    s = server(page)
    r = s["sim"]["confirmed_eval"]["result"]
    check("J3 · confirmed with the deferral: the server's schedule matches the configured policy",
          s["answers"].get("payments") == 36 and r["deferral_months"] == 3 and r["first_repayment_month"] == "2027-02"
          and r["first_payment_month"] == "2026-11" and "פברואר 2027" in bot(page), bot(page)[:80])


# ---------------------------------------------------------------- journey 4: personal scenario
def personal(page: Page) -> None:
    open_chat(page)
    reply(page, "הלוואה פרטית")
    say(page, "יעל כהן")
    say(page, "DEMO-ID-204")
    reply(page, "שיפוץ")
    page.locator("[data-testid=ls-amount-input]").fill("100000")
    page.locator("[data-testid=ls-term-range]").fill("48")
    wait_saved(page, "amount", 100000)
    page.reload()
    expect(card(page)).to_be_visible(timeout=15000)
    check("reload · the unconfirmed draft is restored on the card (server-side, no browser storage of figures)",
          card(page).get_attribute("data-amount") == "100000" and card(page).get_attribute("data-term") == "48"
          and page.evaluate("Object.keys(localStorage).filter(k => /sim|loan/i.test(k)).length") == 0)
    say(page, "מאשר")
    s = server(page)
    check("J4 · 'מאשר' in the chat confirms the card's scenario", s["answers"].get("amount") == 100000 and s["answers"].get("payments") == 48)
    say(page, "אני מרוויח 12 אלף נטו, ואני לא רוצה לעבור החזר של 2,500.")
    s = server(page)
    check("J4 · income recorded as a declaration; the 2,500 target is not read as an amount or income",
          s["answers"].get("net") == 12000 and s["answers"]["amount"] == 100000 and s["sim"]["context"]["target_monthly"] == 2500)
    say(page, "יש לי הלוואה קיימת של 1,000 ש\"ח בחודש")
    s = server(page)
    af = s["sim"]["confirmed_eval"]["affordability"]
    check("J4 · existing repayments + the new one as a share of declared net income, no eligibility claim",
          af["existing_monthly"] == 1000 and af["ratio_pct"] is not None and "לא בדיקת זכאות" in bot(page), json.dumps(af))
    page.locator("[data-testid=ls-edit]").click()
    pers = page.locator("[data-testid=ls-personal]")
    check("J4 · the card's personal picture shows the same ratio as the server",
          pers.count() == 1 and pers.get_attribute("data-ratio") == str(af["ratio_pct"]), f"{pers.get_attribute('data-ratio')} vs {af['ratio_pct']}")
    c = card(page)
    c.scroll_into_view_if_needed()
    shot(page, "07-personal", c)
    page.locator("[data-testid=ls-cancel]").click()
    say(page, "אני רוצה לשלם עד 2,000 בחודש")
    s = server(page)
    t = s["sim"]["confirmed_eval"]["target"]
    acts = page.locator("[data-testid=cv2-action]")
    check("J4 · a 2,000 target: the engine proposes a longer term, explains the interest trade-off, and changes nothing yet",
          t["status"] == "term" and s["answers"]["payments"] == 48 and acts.count() >= 1 and "תקופה ארוכה יותר" in bot(page), bot(page)[:90])
    click_and_settle(page, acts.first)
    s = server(page)
    check("J4 · applying the suggestion updates the scenario", s["answers"]["payments"] == t["term"] and s["answers"]["amount"] == 100000,
          str(s["answers"]["payments"]))
    box = page.locator("[data-testid=cv2-input]").bounding_box()
    check("mobile · the composer input stays usable (16px, inside the viewport)",
          box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390
          and page.locator("[data-testid=cv2-input]").evaluate("e => getComputedStyle(e).fontSize") == "16px")


def touch_targets(page: Page) -> None:
    open_chat(page)
    reply(page, "הלוואה פרטית")
    say(page, "אבי לוי")
    say(page, "DEMO-ID-205")
    reply(page, "מטרה אחרת")
    small = page.evaluate("""() => [...document.querySelectorAll('[data-testid=ls-card] button, [data-testid=ls-card] input')]
      .filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect(); return [e.dataset.testid || e.className, Math.round(r.height)]; })
      .filter(([, h]) => h < 32)""")
    check("mobile · every control on the card is at least 32px tall (sliders 36px)", not small, json.dumps(small))
    fs = page.locator("[data-testid=ls-amount-input]").evaluate("e => getComputedStyle(e).fontSize")
    check("mobile · number inputs are 16px (no zoom on focus)", fs == "16px", fs)
    layout(page, "all-purpose card")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        ctx = dict(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True, has_touch=True, device_scale_factor=2)
        for step in (car, celebration, instant, personal, touch_targets):
            page = browser.new_context(**ctx).new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            try:
                step(page)
            except Exception as exc:
                check(f"{step.__name__} completed", False, repr(exc)[:300])
                shot(page, f"error-{step.__name__}")
            check(f"{step.__name__} · no page errors", not errors, "; ".join(errors)[:200])
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
