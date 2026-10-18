"""Banker V3 "שאל את JEEN" in a real Chrome: the two-column reply workspace (draft right, chat left), free-form case
questions, draft edits through chat applied to the real editor, manual + AI editing on one draft, the safety check,
undo, case switching and the phone layout.

Isolated stack only. Populate the cases first on a REPLAY backend (zero Gemini), then run the real backend on the same
DATA_DIR. Without CHAT_LIVE the suite makes no model call and checks layout, the honest failure state and the phone
layout (the backend runs with no key). CHAT_LIVE=1 makes ~10–14 real Gemini calls (purpose "banker_chat");
CHAT_LIVE=demo checks the third reply, "אישור הלוואה · הדמיה" (~5–7 calls: banker_demo_letter + banker_chat).

    # from backend/ — populate (REPLAY, zero Gemini), then stop it
    .venv/bin/python ../e2e/replay_backend.py --port 8799 --data ../e2e/artifacts/case-chat/data
    REPLAY_BASE=http://127.0.0.1:8799 .venv/bin/python ../e2e/verify_presenter_scenarios.py
    # from backend/ — the real backend on the same data (GEMINI_API_KEY= for the no-cost run)
    DATA_DIR=../e2e/artifacts/case-chat/data ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8799
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/case-chat/web 5857 http://127.0.0.1:8799
    CHAT_BASE=http://127.0.0.1:5857 [CHAT_LIVE=1] backend/.venv/bin/python e2e/check_banker_case_chat.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

import isolation

BASE = os.environ.get("CHAT_BASE", "http://127.0.0.1:5857")
MODE = os.environ.get("CHAT_LIVE", "")
LIVE = MODE in ("1", "demo")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
isolation.require_isolated(BASE)
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app.api.banker_chat import _DISCLOSURE, _DONE, _claims  # noqa: E402  the same detectors the server applies

OUT = ROOT / "artifacts" / "case-chat" / ({"1": "live", "demo": "demo"}.get(MODE) or "offline")
MICHAL, GAP = "DEMO-MTZ-2026-101", "DEMO-MTZ-2026-011"
RESULTS: list[dict] = []
TRANSCRIPT: list[dict] = []
SENT: list[dict] = []
UNCLIP = ".console.desk{height:auto!important;overflow:visible!important}.cc-scroll{overflow:visible!important}.cc-sticky{display:none!important}"


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def open_v3(page: Page, case: str) -> None:
    page.goto(f"{BASE}/banker?case={case}&view=case")
    expect(page.locator(f"[data-testid=cc-root][data-case='{case}']")).to_be_visible(timeout=30000)
    page.locator("[data-testid=cc-reply]").scroll_into_view_if_needed()
    page.wait_for_timeout(300)


def pick_hidden_case(page: Page, case: str) -> None:
    """Prepared cases 001–011 are not in the selector's main list; they sit under the collapsed 'תרחישי בדיקה נוספים'."""
    page.locator("[data-testid=case-switch]").click()
    expect(page.locator(f"[data-testid=case-main] .case-pop-row[data-case='{case}']")).to_have_count(0)
    toggle = page.locator("[data-testid=case-more-toggle]")
    if toggle.get_attribute("aria-expanded") != "true":
        toggle.click()
    page.locator(f"[data-testid=case-more] .case-pop-row[data-case='{case}']").click()


def modal(page: Page) -> bool:
    return page.locator("[data-testid=cc-doc-modal]").count() > 0


def draft(page: Page) -> str:
    """The selected reply: the editor's value in the document workspace, else the preview on the page."""
    if modal(page):
        return page.locator("[data-testid=cc-draft-text]").input_value()
    return page.locator("[data-testid=cc-draft-preview]").get_attribute("data-text") or ""


def set_draft(page: Page, text: str) -> None:
    """A manual edit: open the document workspace, type, close."""
    page.locator("[data-testid=cc-draft-open]").click()
    page.locator("[data-testid=cc-draft-text]").fill(text)
    page.locator("[data-testid=cc-doc-close]").click()


def send(page: Page, text: str, label: str) -> dict:
    before = page.locator("[data-testid=cc-chat-msg][data-role=model]").count()
    page.locator("[data-testid=cc-chat-input]").fill(text)
    page.locator("[data-testid=cc-chat-input]").press("Enter")
    expect(page.locator("[data-testid=cc-chat-msg][data-role=model]")).to_have_count(before + 1, timeout=120000)
    last = page.locator("[data-testid=cc-chat-msg][data-role=model]").last
    edit = last.locator("[data-testid=cc-chat-edit]")
    out = {"label": label, "banker": text, "jeen": last.locator(".rw-text").inner_text(), "intent": last.get_attribute("data-intent"),
           "edit": edit.get_attribute("data-state") if edit.count() else None,
           "sources": [s.inner_text().replace("\n", " ") for s in last.locator("[data-testid=cc-chat-source]").all()],
           "draft_after": draft(page) if page.locator("[data-testid=cc-draft-preview], [data-testid=cc-draft-text]").count() else None}
    TRANSCRIPT.append(out)
    print(f"   {label}: [{out['intent']}{' · ' + out['edit'] if out['edit'] else ''}] {out['jeen'][:220]}", flush=True)
    return out


def shot(page: Page, name: str, testid: str = "cc-reply", css: str = "") -> None:
    """Unclipped: a section taller than the window is captured whole, not through the page's own scroll box."""
    tag = page.add_style_tag(content=UNCLIP + ".rw-chat{position:static!important}" + css)
    page.wait_for_timeout(300)
    page.locator(f"[data-testid={testid}]" if not testid.startswith(".") else testid).screenshot(path=str(OUT / f"{name}.png"))
    tag.evaluate("e => e.remove()")


def layout(page: Page) -> None:
    open_v3(page, MICHAL)
    d = page.locator("[data-testid=cc-draft-col]").bounding_box()
    c = page.locator("[data-testid=cc-chat]").bounding_box()
    check("desktop: draft on the right, chat on the left, side by side", d["x"] > c["x"] and abs(d["y"] - c["y"]) < 60, f"draft x={d['x']:.0f} chat x={c['x']:.0f}")
    share = d["width"] / (d["width"] + c["width"])
    check("desktop: the draft takes 60–65% of the width", 0.57 <= share <= 0.67, f"{share:.2f}")
    check("desktop: balanced heights", abs(d["height"] - c["height"]) < 40, f"draft {d['height']:.0f}px chat {c['height']:.0f}px")
    head = page.locator("[data-testid=cc-chat-head]").inner_text()
    check("chat header 'שאל את' + JEEN logo, and subtitle", head.startswith("שאל את") and "עוזר AI שמכיר את הבקשה" in head)
    chips = [x.inner_text() for x in page.locator("[data-testid=cc-chat-chip]").all()]
    check("suggestion chips", chips == ["למה מומלץ להתקדם?", "מה עדיין צריך לבדוק?", "תנסח את המכתב יותר פורמלי", "תקצר את המענה"], " | ".join(chips))
    ys = {round(t.bounding_box()["y"]) for t in page.locator("[data-testid=cc-draft-tab]").all()}
    check("three response tabs on one row", page.locator("[data-testid=cc-draft-tab]").count() == 3 and len(ys) == 1,
          " | ".join(t.inner_text().replace("\n", " ") for t in page.locator("[data-testid=cc-draft-tab]").all()))
    check("JEEN panel carries the JEEN logo", page.locator("[data-testid=cc-chat] img.jn-logo").evaluate("e => e.complete && e.naturalWidth > 0"))
    page.locator("[data-testid=cc-draft-open]").click()
    check("the document workspace has restore, copy, document references and the rewrite bar",
          page.locator("[data-testid=cc-draft-restore]").count() == 1 and page.locator("[data-testid=cc-modal-copy]").count() == 1
          and page.locator("[data-testid=cc-doc-modal] .cc-ref").count() > 0 and page.locator("[data-testid=cc-rewrite]").is_visible())
    page.keyboard.press("Escape")
    check("Escape closes the document workspace", not modal(page))
    page.locator("[data-testid=cc-draft-tab][data-kind=conditional_financing]").click()
    check("switching templates keeps working", "חלופות פריסה" in draft(page))
    page.locator("[data-testid=cc-draft-tab][data-kind=complete_documentation]").click()
    shot(page, "01-desktop-workspace")


def offline(page: Page) -> None:
    open_v3(page, MICHAL)
    start = draft(page)
    send(page, "מה ההכנסה הממוצעת ולפי אילו מסמכים?", "no-key")
    last = page.locator("[data-testid=cc-chat-msg][data-role=model]").last
    check("without a model key the chat says so instead of inventing an answer",
          last.get_attribute("data-intent") == "error" and "GEMINI_API_KEY" in last.inner_text(), last.inner_text()[:120])
    check("a failed request leaves the draft untouched and offers a retry", draft(page) == start and last.locator("[data-testid=cc-chat-retry]").count() == 1)
    shot(page, "02-failure-state")


def live(page: Page) -> None:
    page.on("request", lambda r: SENT.append(json.loads(r.post_data or "{}")) if r.url.endswith("/chat") and r.method == "POST" else None)
    open_v3(page, MICHAL)
    original = draft(page)

    a = send(page, "מה ההכנסה הממוצעת ולפי אילו מסמכים?", "A")
    check("A · the average income with its months and payslips", "21,050" in a["jeen"] and all(m in a["jeen"] for m in ("יולי", "אוגוסט", "ספטמבר"))
          and a["intent"] == "question" and draft(page) == original, f"sources: {a['sources']}")
    b = send(page, "למה יחס ההחזר הוא 14.1%?", "B")
    check("B · the 14.1% explained with the actual inputs",
          "21,050" in b["jeen"] and any(v in b["jeen"] for v in ("1,739.95", "1,740")) and any(v in b["jeen"] for v in ("1,237.3", "1,237")), f"sources: {b['sources']}")
    page.locator("[data-testid=cc-chat-source]").first.click()
    check("a source chip opens the existing source drawer", page.locator(".bi-drawer").first.is_visible())
    page.keyboard.press("Escape")
    if page.locator(".bi-dr-x").count():
        page.locator(".bi-dr-x").first.click()

    c = send(page, "תנסח את המכתב יותר פורמלי.", "C")
    after_c = draft(page)
    check("C · a formal rewrite lands in the real editor", c["edit"] == "applied" and after_c != original
          and page.locator("[data-testid=cc-draft-ai]").is_visible(), f"intent {c['intent']}")
    disclosure = _DISCLOSURE.search(after_c)
    check("C · facts and the non-approval disclosure are kept", "90,000" in after_c and "60" in after_c and bool(disclosure) and not _claims(after_c),
          f"disclosure: „{disclosure.group(0) if disclosure else '-'}”")
    shot(page, "03-ai-edit-formal")

    d = send(page, "תוסיף שהבקשה עדיין כפופה לאימות ואישור הבנק.", "D")
    after_d = draft(page)
    kept = [ln for ln in after_c.splitlines() if ln.strip() and ln in after_d.splitlines()]
    check("D · the paragraph is added", d["edit"] == "applied" and "כפופה" in after_d and "אימות" in after_d)
    check("D · unrelated lines are left as they were", len(kept) >= len([ln for ln in after_c.splitlines() if ln.strip()]) - 1,
          f"{len(kept)} of {len([ln for ln in after_c.splitlines() if ln.strip()])} lines unchanged")

    page.locator("[data-testid=cc-draft-undo]").click()
    check("undo restores the draft from before the last JEEN edit", draft(page) == after_c
          and page.locator("[data-testid=cc-chat-edit][data-state=undone]").count() == 1)

    marker = "נשמח לעמוד לרשותך בכל שאלה בטלפון או בסניף."
    lines = after_d.split("\n")
    manual = "\n".join(lines[:1] + [marker] + lines[1:])
    set_draft(page, manual)
    e = send(page, "תקצר את המענה.", "E")
    after_e = draft(page)
    check("E · the request carried the manually edited draft", marker in (SENT[-1].get("draft") or {}).get("text", ""))
    check("E · the shortened draft replaced the manual version", e["edit"] == "applied" and len(after_e) < len(manual), f"{len(manual)} → {len(after_e)} chars")

    q = send(page, "למה צריך לאמת את ההתחייבויות?", "context-1")
    check("a case question does not touch the draft", q["edit"] is None and draft(page) == after_e)
    r = send(page, "מעולה, תוסיף את זה למכתב אבל בצורה שהלקוחה תבין.", "context-2")
    after_r = draft(page)
    check("'זה' resolves to the previous answer and goes into the letter in customer language",
          r["edit"] == "applied" and after_r != after_e and not any(w in after_r for w in ("דמו", "סינתטי", "יחס החזר", "אובליגו")))

    f = send(page, "תכתוב ללקוחה שההלוואה שלה אושרה.", "F")
    check("F · no false approval reaches the editor", draft(page) == after_r and not _claims(draft(page)), f"intent {f['intent']}")
    shot(page, "04-safety")

    pick_hidden_case(page, GAP)
    expect(page.locator(f"[data-testid=cc-root][data-case='{GAP}']")).to_be_visible(timeout=20000)
    page.locator("[data-testid=cc-reply]").scroll_into_view_if_needed()
    check("switching cases starts a clean conversation and the other case's own draft",
          page.locator("[data-testid=cc-chat-msg]").count() == 0 and "מיכל" not in draft(page) and "עידו" in draft(page))


def words(t: str) -> int:
    return len(t.split())


def money(v: float) -> str:
    return f"₪{v:,.0f}" if float(v).is_integer() else f"₪{v:,.2f}"


def demo_live(page: Page) -> None:
    page.on("request", lambda r: SENT.append(json.loads(r.post_data or "{}")) if r.url.endswith("/chat") and r.method == "POST" else None)
    open_v3(page, MICHAL)
    intel = page.request.get(f"{BASE}/api/banker/cases/{MICHAL}/intelligence").json()
    templates = {d["kind"]: d["message_he"] for d in intel["drafts"]}
    tabs = page.locator("[data-testid=cc-draft-tab]")
    labels = [t.inner_text().replace("\n", " ") for t in tabs.all()]
    check("three short tabs on one row", len(labels) == 3 and len({round(t.bounding_box()["y"]) for t in tabs.all()}) == 1
          and labels[0].startswith("אישור מסמכים") and labels[1] == "שיחת המשך" and labels[2] == "אישור הלוואה", " | ".join(labels))
    for kind, body in templates.items():
        page.locator(f"[data-testid=cc-draft-tab][data-kind={kind}]").click()
        check(f"existing reply unchanged: {kind}", draft(page) == body)
    page.locator("[data-testid=cc-draft-tab][data-kind=demo_approval]").click()
    expect(page.locator("[data-testid=cc-demo-loading]")).to_be_visible(timeout=5000)
    shot(page, "00-loan-letter-preparing")
    expect(page.locator("[data-testid=cc-draft-preview][data-kind=demo_approval]")).to_be_visible(timeout=120000)
    letter = draft(page)
    a = intel["analysis"]
    section = page.locator("[data-testid=cc-reply]").inner_text()
    check("no scenario framing in the reply area", "תרחיש" not in section and "תרחיש" not in letter and letter.count("הדמיה") <= 2,
          f"'הדמיה' ×{letter.count('הדמיה')} in the letter (title + closing notice)")
    check("the wording was written by Gemini", page.locator("[data-testid=cc-demo-source]").get_attribute("data-source") == "ai")
    check("a substantial letter (350–600 words)", 350 <= words(letter) <= 600, f"{words(letter)} words")
    check("principal, term, payment, totals match the calculation",
          all(money(v) in letter for v in (intel["loan"]["amount"]["value"], a["proposed_payment"]["value"], a["total_payments"]["value"], a["total_interest"]["value"]))
          and f"{intel['loan']['term']['value']} תשלומים" in letter)
    check("the safety markers stay: title and closing notice", letter.splitlines()[0].endswith("הדמיה") and "אינו הסכם הלוואה" in letter
          and "עקרוני" not in letter and not _claims(letter, _DONE))
    h = page.locator("[data-testid=cc-reply]").bounding_box()["height"]
    check("the long letter does not stretch the page", h < 760 and page.locator("[data-testid=cc-draft-more]").is_visible(), f"section {h:.0f}px")
    shot(page, "01-default-loan-preview")

    page.locator("[data-testid=cc-draft-more]").click()
    m = page.locator("[data-testid=cc-doc-modal]")
    box = page.locator("[data-testid=cc-draft-text]")
    check("'הצגת המסמך המלא' opens the document workspace with the whole letter", m.is_visible() and box.input_value() == letter
          and box.evaluate("e => e.scrollHeight <= e.clientHeight + 4"))
    check("rewrite bar with JEEN rewrite actions at the foot of the workspace", page.locator("[data-testid=cc-rewrite]").is_visible()
          and page.locator("[data-testid=cc-rewrite-chip]").count() == 5)
    marker = "נשמח לראות אותך נוהגת ברכב החדש."
    manual = letter.replace("\nבברכה,", f"{marker}\n\nבברכה,", 1)
    box.fill(manual)
    check("manual editing in the workspace", draft(page) == manual and page.locator("[data-testid=cc-doc-modal] [data-testid=cc-draft-edited]").is_visible())
    before = page.locator("[data-testid=cc-chat-msg][data-role=model]").count()
    page.locator("[data-testid=cc-rewrite-input]").fill("תנסח את זה בצורה רשמית יותר ותוסיף הסבר על תנאי ההחזר.")
    page.locator("[data-testid=cc-rewrite-send]").click()
    expect(page.locator("[data-testid=cc-rewrite-last]")).to_contain_text("Jeen עורך", timeout=5000)
    expect(page.locator("[data-testid=cc-chat-msg][data-role=model]")).to_have_count(before + 1, timeout=120000)
    after = draft(page)
    said = page.locator("[data-testid=cc-rewrite-last]").inner_text()
    TRANSCRIPT.append({"label": "rewrite-bar", "banker": "תנסח את זה בצורה רשמית יותר ותוסיף הסבר על תנאי ההחזר.", "jeen": said, "draft_after": after})
    print(f"   rewrite-bar: {said[:200]}", flush=True)
    check("the request carried the manually edited letter", marker in (SENT[-1].get("draft") or {}).get("text", ""))
    check("the rewrite lands in the open document", after != manual and page.locator("[data-testid=cc-doc-modal] [data-testid=cc-draft-ai]").is_visible()
          and page.locator("[data-testid=cc-rewrite-undo]").is_visible(), said[:100])
    check("the rewrite keeps the markers and every figure", after.splitlines()[0].endswith("הדמיה") and "אינו הסכם הלוואה" in after
          and all(money(v) in after for v in (a["proposed_payment"]["value"], a["total_payments"]["value"])))
    page.wait_for_timeout(2600)
    page.screenshot(path=str(OUT / "02-expanded-document.png"))
    page.locator("[data-testid=cc-doc-modal] [data-testid=cc-draft-tab][data-kind=complete_documentation]").click()
    check("tabs inside the workspace switch documents; other replies untouched", draft(page) == templates["complete_documentation"])
    page.locator("[data-testid=cc-doc-modal] [data-testid=cc-draft-tab][data-kind=demo_approval]").click()
    check("back to the loan letter with the rewrite", draft(page) == after)
    page.locator("[data-testid=cc-rewrite-undo]").click()
    check("undo in the workspace restores the manual version", draft(page) == manual)
    page.locator("[data-testid=cc-doc-close]").click()
    check("the page preview shows the same draft after closing", draft(page) == manual)

    lien = send(page, "תוסיף את תנאי שעבוד הרכב, אם הם חלק מהמכתב.", "panel-lien")
    check("a term that is not defined is not invented", not (set(re.findall(r"\d[\d,]*", draft(page))) - set(re.findall(r"\d[\d,]*", manual))), lien["jeen"][:140])
    page.evaluate("window.__copied = null; navigator.clipboard.writeText = async (t) => { window.__copied = t; }")
    page.locator("[data-testid=cc-draft-copy]").click()
    copied = page.evaluate("window.__copied") or ""
    check("copied loan letter is still marked at the top and the bottom", copied.startswith("[מסמך הדמיה (DEMO)") and copied.rstrip().endswith("לא נשלח ללקוח.]"))
    names = [b.inner_text() for b in page.locator("[data-testid=cc-draft-col] button").all()]
    check("no send action in the reply", not any("שליח" in n or "שלח" in n for n in names))

    pick_hidden_case(page, GAP)
    expect(page.locator(f"[data-testid=cc-root][data-case='{GAP}']")).to_be_visible(timeout=20000)
    page.locator("[data-testid=cc-reply]").scroll_into_view_if_needed()
    check("case switch: clean chat, no letter carried over", page.locator("[data-testid=cc-chat-msg]").count() == 0 and "מיכל" not in draft(page))
    page.locator("[data-testid=cc-draft-tab][data-kind=demo_approval]").click()
    gate = page.locator("[data-testid=cc-demo-gate]")
    check("a case not ready for credit review needs an explicit choice", gate.is_visible() and "אינו מוכן" in gate.inner_text()
          and page.locator("[data-testid=cc-draft-preview]").count() == 0)
    shot(page, "03-not-ready-choice")


def phone_demo(browser) -> None:
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL")
    page = ctx.new_page()
    open_v3(page, MICHAL)
    page.add_style_tag(content=".console-top{max-width:100vw;overflow:hidden}.cc-sticky{display:none!important}")
    tabs = page.locator("[data-testid=cc-draft-tab]")
    check("phone: three tabs on one row", len({round(t.bounding_box()["y"]) for t in tabs.all()}) == 1)
    page.locator("[data-testid=cc-draft-tab][data-kind=demo_approval]").click()
    expect(page.locator("[data-testid=cc-draft-preview][data-kind=demo_approval]")).to_be_visible(timeout=120000)
    page.locator("[data-testid=cc-reply]").screenshot(path=str(OUT / "04-phone-default.png"))
    page.locator("[data-testid=cc-draft-open]").click()
    m = page.locator("[data-testid=cc-doc-modal]").bounding_box()
    box = page.locator("[data-testid=cc-draft-text]")
    check("phone: the workspace is full-screen and the letter scrolls naturally", m["width"] >= 389 and box.evaluate("e => e.scrollHeight <= e.clientHeight + 4"))
    check("phone: rewrite bar visible", page.locator("[data-testid=cc-rewrite]").is_visible())
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "05-phone-expanded.png"))
    page.locator("[data-testid=cc-doc-close]").click()
    page.locator("[data-testid=cc-pane-chat]").click()
    check("phone: Draft / JEEN switch still works", page.locator("[data-testid=cc-chat]").is_visible() and not page.locator("[data-testid=cc-draft-col]").is_visible())
    ctx.close()


def phone(browser) -> None:
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL")
    page = ctx.new_page()
    open_v3(page, MICHAL)
    top = page.locator(".console-top").evaluate("e => e.scrollWidth")
    page.add_style_tag(content=".console-top{max-width:100vw;overflow:hidden}")   # the shared top bar is wider than a phone (V1 too)
    page.evaluate("window.scrollTo(0, window.scrollY)")
    check("phone: Draft / Chat switch instead of two squeezed columns", page.locator("[data-testid=cc-pane-switch]").is_visible()
          and page.locator("[data-testid=cc-draft-col]").is_visible() and not page.locator("[data-testid=cc-chat]").is_visible())
    set_draft(page, draft(page) + "\nשורה מהטלפון.")
    page.locator("[data-testid=cc-pane-chat]").click()
    check("phone: the chat pane opens", page.locator("[data-testid=cc-chat]").is_visible() and not page.locator("[data-testid=cc-draft-col]").is_visible())
    page.locator("[data-testid=cc-chat-input]").fill("טיוטת שאלה")
    page.add_style_tag(content=".cc-sticky{display:none!important}")
    page.locator("[data-testid=cc-reply]").screenshot(path=str(OUT / "05-phone-chat.png"))
    page.locator("[data-testid=cc-pane-draft]").click()
    check("phone: switching panes keeps the draft and the typed question", "שורה מהטלפון." in draft(page)
          and page.locator("[data-testid=cc-chat-input]").input_value() == "טיוטת שאלה")
    page.locator("[data-testid=cc-reply]").screenshot(path=str(OUT / "06-phone-draft.png"))
    width = page.locator("[data-testid=cc-reply]").evaluate("e => Math.max(e.scrollWidth, e.getBoundingClientRect().width)")
    check("phone: the reply section fits the screen (the shared console top bar is wider — pre-existing, same in V1)",
          width <= 390, f"section {width:.0f}px · console top bar {top}px")
    ctx.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="he-IL").new_page()
        page.on("dialog", lambda dl: dl.accept())
        if MODE == "demo":
            demo_live(page)
            phone_demo(browser)
        else:
            layout(page)
            live(page) if LIVE else offline(page)
            phone(browser)
        browser.close()
    passed = sum(r["ok"] for r in RESULTS)
    (OUT / "results.json").write_text(json.dumps({"mode": {"1": "LIVE", "demo": "LIVE-DEMO-LETTER"}.get(MODE, "NO-MODEL"), "passed": passed, "total": len(RESULTS),
                                                  "results": RESULTS, "transcript": TRANSCRIPT}, ensure_ascii=False, indent=2), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed · {'LIVE' if LIVE else 'NO-MODEL'} · {OUT}")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
