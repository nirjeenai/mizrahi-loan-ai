"""Banker V3 "שאל את JEEN" in a real Chrome: the two-column reply workspace (draft right, chat left), free-form case
questions, draft edits through chat applied to the real editor, manual + AI editing on one draft, the safety check,
undo, case switching and the phone layout.

Isolated stack only. Populate the cases first on a REPLAY backend (zero Gemini), then run the real backend on the same
DATA_DIR. Without CHAT_LIVE=1 the suite makes no model call and checks layout, the honest failure state and the phone
layout (the backend runs with no key). With CHAT_LIVE=1 it makes ~10–14 real Gemini calls (purpose "banker_chat").

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
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("CHAT_BASE", "http://127.0.0.1:5857")
LIVE = os.environ.get("CHAT_LIVE") == "1"
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app.api.banker_chat import _DISCLOSURE, _claims  # noqa: E402  the same detectors the server applies

OUT = ROOT / "artifacts" / "case-chat" / ("live" if LIVE else "offline")
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


def draft(page: Page) -> str:
    return page.locator("[data-testid=cc-draft-text]").input_value()


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
           "draft_after": draft(page) if page.locator("[data-testid=cc-draft-text]").count() else None}
    TRANSCRIPT.append(out)
    print(f"   {label}: [{out['intent']}{' · ' + out['edit'] if out['edit'] else ''}] {out['jeen'][:220]}", flush=True)
    return out


def shot(page: Page, name: str) -> None:
    page.add_style_tag(content=".cc-sticky{display:none!important}")
    page.locator("[data-testid=cc-reply]").scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    page.locator("[data-testid=cc-reply]").screenshot(path=str(OUT / f"{name}.png"))


def layout(page: Page) -> None:
    open_v3(page, MICHAL)
    d = page.locator("[data-testid=cc-draft-col]").bounding_box()
    c = page.locator("[data-testid=cc-chat]").bounding_box()
    check("desktop: draft on the right, chat on the left, side by side", d["x"] > c["x"] and abs(d["y"] - c["y"]) < 60, f"draft x={d['x']:.0f} chat x={c['x']:.0f}")
    share = d["width"] / (d["width"] + c["width"])
    check("desktop: the draft takes 60–65% of the width", 0.57 <= share <= 0.67, f"{share:.2f}")
    check("desktop: balanced heights", abs(d["height"] - c["height"]) < 40, f"draft {d['height']:.0f}px chat {c['height']:.0f}px")
    check("chat header and subtitle", page.locator(".rw-chat-head").inner_text().startswith("שאל את JEEN")
          and "עוזר AI שמכיר את הבקשה" in page.locator(".rw-chat-head").inner_text())
    chips = [x.inner_text() for x in page.locator("[data-testid=cc-chat-chip]").all()]
    check("suggestion chips", chips == ["למה מומלץ להתקדם?", "מה עדיין צריך לבדוק?", "תנסח את המכתב יותר פורמלי", "תקצר את המענה"], " | ".join(chips))
    check("templates, restore, copy and document references are still there",
          page.locator("[data-testid=cc-draft-tab]").count() == 2 and page.locator("[data-testid=cc-draft-restore]").count() == 1
          and page.locator("[data-testid=cc-draft-copy]").count() == 1 and page.locator(".cc-ref").count() > 0)
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
          f"disclosure: „{disclosure.group(0) if disclosure else '—'}”")
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
    page.locator("[data-testid=cc-draft-text]").fill(manual)
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

    page.locator("[data-testid=case-switch]").click()
    page.locator(".case-pop-row", has_text="438839011").click()
    expect(page.locator(f"[data-testid=cc-root][data-case='{GAP}']")).to_be_visible(timeout=20000)
    page.locator("[data-testid=cc-reply]").scroll_into_view_if_needed()
    check("switching cases starts a clean conversation and the other case's own draft",
          page.locator("[data-testid=cc-chat-msg]").count() == 0 and "מיכל" not in draft(page) and "עידו" in draft(page))


def phone(browser) -> None:
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL")
    page = ctx.new_page()
    open_v3(page, MICHAL)
    top = page.locator(".console-top").evaluate("e => e.scrollWidth")
    page.add_style_tag(content=".console-top{max-width:100vw;overflow:hidden}")   # the shared top bar is wider than a phone (V1 too)
    page.evaluate("window.scrollTo(0, window.scrollY)")
    check("phone: Draft / Chat switch instead of two squeezed columns", page.locator("[data-testid=cc-pane-switch]").is_visible()
          and page.locator("[data-testid=cc-draft-col]").is_visible() and not page.locator("[data-testid=cc-chat]").is_visible())
    box = page.locator("[data-testid=cc-draft-text]")
    box.fill(box.input_value() + "\nשורה מהטלפון.")
    page.locator("[data-testid=cc-pane-chat]").click()
    check("phone: the chat pane opens", page.locator("[data-testid=cc-chat]").is_visible() and not page.locator("[data-testid=cc-draft-col]").is_visible())
    page.locator("[data-testid=cc-chat-input]").fill("טיוטת שאלה")
    page.add_style_tag(content=".cc-sticky{display:none!important}")
    page.locator("[data-testid=cc-reply]").screenshot(path=str(OUT / "05-phone-chat.png"))
    page.locator("[data-testid=cc-pane-draft]").click()
    check("phone: switching panes keeps the draft and the typed question", "שורה מהטלפון." in box.input_value()
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
        layout(page)
        live(page) if LIVE else offline(page)
        phone(browser)
        browser.close()
    passed = sum(r["ok"] for r in RESULTS)
    (OUT / "results.json").write_text(json.dumps({"mode": "LIVE" if LIVE else "NO-MODEL", "passed": passed, "total": len(RESULTS),
                                                  "results": RESULTS, "transcript": TRANSCRIPT}, ensure_ascii=False, indent=2), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} checks passed · {'LIVE' if LIVE else 'NO-MODEL'} · {OUT}")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
