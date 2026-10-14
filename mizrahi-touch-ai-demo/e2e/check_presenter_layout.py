"""The collapsible presenter in a real Chrome: the customer app is centred and the presenter starts collapsed; its toggle
opens a docked panel (≥1000px) or a drawer (tablet, phone); collapsing and reopening keeps the open case, the app's own
state and the pane's state, and sends nothing to the server; downloads and scenario selection still work; RTL, no
sideways scrolling, no control over the phone. Isolated REPLAY stack (no Gemini); never resets or uploads.

    # from backend/
    .venv/bin/python ../e2e/replay_backend.py --port 8794 --data ../e2e/artifacts/presenter-layout/data
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/presenter-layout/web 5848 http://127.0.0.1:8794
    LAYOUT_BASE=http://127.0.0.1:5848 backend/.venv/bin/python e2e/check_presenter_layout.py
    LAYOUT_BASE=http://127.0.0.1:8791 LAYOUT_READONLY=1 backend/.venv/bin/python e2e/check_presenter_layout.py  # layout only
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("LAYOUT_BASE", "http://127.0.0.1:5848")
READONLY = bool(os.environ.get("LAYOUT_READONLY"))     # the user's own instances: layout and toggling only
ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT.parent / "fixtures" / "presenter" / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
DOCS = {d["id"]: d for d in MANIFEST["documents"]}
FEATURED = {f["outcome"]: f for f in MANIFEST["featured"]}
OUT = ROOT / "artifacts" / "presenter-layout" / (BASE.rsplit(":", 1)[-1].strip("/") + ("-readonly" if READONLY else ""))
RESULTS: list[dict] = []
GEOMETRY = """() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
  return { l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width }; };
  return { phone: r('.phone'), side: r('.hub-side'), toggle: r('[data-testid=presenter-toggle]'), vw: innerWidth, vh: innerHeight,
           overflow: document.documentElement.scrollWidth - innerWidth, pageScroll: document.documentElement.scrollHeight - innerHeight,
           focus: document.activeElement && document.activeElement.dataset.testid }; }"""


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


def geo(page: Page) -> dict:
    return page.evaluate(GEOMETRY)


def overlaps(a: dict | None, b: dict | None) -> bool:
    return bool(a and b and a["w"] and b["w"] and a["l"] < b["r"] and b["l"] < a["r"] and a["t"] < b["b"] and b["t"] < a["b"])


def state(page: Page) -> str:
    return page.locator(".hub").get_attribute("data-presenter") or ""


def set_presenter(page: Page, want: bool, via: str = "toggle") -> None:
    if (state(page) == "open") == want:
        return
    if want and via == "menu":
        page.locator("button[aria-label='תפריט']").click()
        page.locator("[data-testid=drawer-presenter]").click()
    elif want:
        page.locator("[data-testid=presenter-toggle]").click()
    elif via == "escape":
        page.keyboard.press("Escape")
    else:
        page.locator("[data-testid=presenter-close]").click()
    expect(page.locator(".hub")).to_have_attribute("data-presenter", "open" if want else "closed")
    page.wait_for_timeout(350)                       # the 0.22 s slide


def load(page: Page, path: str = "/customer") -> None:
    page.goto(f"{BASE}{path}")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"))


def same_bytes(page: Page, link) -> tuple[bool, str]:
    doc_id = link.get_attribute("data-doc-id")
    with page.expect_download() as dl:
        link.click()
    target = OUT / "downloads" / dl.value.suggested_filename
    target.parent.mkdir(parents=True, exist_ok=True)
    dl.value.save_as(str(target))
    data = target.read_bytes()
    return hashlib.sha256(data).hexdigest() == DOCS[doc_id]["sha256"] and dl.value.suggested_filename == DOCS[doc_id]["downloadPath"].split("/")[-1], doc_id


def desktop(page: Page, w: int, h: int) -> None:
    tag = f"{w}x{h}"
    load(page)
    g = geo(page)
    toggle = page.locator("[data-testid=presenter-toggle]")
    check(f"{tag}: presenter starts collapsed; the toggle 'תרחישי הדגמה' is visible",
          state(page) == "closed" and not page.locator(".hub-side").is_visible() and toggle.is_visible()
          and toggle.get_attribute("aria-expanded") == "false" and "תרחישי הדגמה" in toggle.inner_text())
    closed_phone = g["phone"]
    check(f"{tag}: phone centred in the window, original frame size, toggle clear of it, no sideways scroll",
          abs((g["phone"]["l"] + g["phone"]["r"]) / 2 - g["vw"] / 2) <= 1 and g["phone"]["w"] == 410
          and not overlaps(g["toggle"], g["phone"]) and g["overflow"] <= 0 and g["pageScroll"] <= 1,
          f"phone {g['phone']['l']:.0f}–{g['phone']['r']:.0f} of {g['vw']}")
    shot(page, f"{tag}-collapsed")
    set_presenter(page, True)
    g = geo(page)
    centre = (g["side"]["r"] + g["vw"]) / 2
    check(f"{tag}: toggle opens a docked panel on the left; the phone keeps its size, centred in the rest, beside the panel",
          page.locator(".hub-side").is_visible() and g["side"]["l"] == 0 and 340 <= g["side"]["w"] <= 421
          and g["phone"]["l"] >= g["side"]["r"] and g["phone"]["w"] == closed_phone["w"]
          and abs((g["phone"]["l"] + g["phone"]["r"]) / 2 - centre) <= 2 and g["phone"]["t"] >= 0 and g["phone"]["b"] <= g["vh"]
          and g["overflow"] <= 0 and g["focus"] == "presenter-close",
          f"panel 0–{g['side']['r']:.0f} · phone {g['phone']['l']:.0f}–{g['phone']['r']:.0f} · focus {g['focus']}")
    shot(page, f"{tag}-open")
    set_presenter(page, False)
    g = geo(page)
    check(f"{tag}: the close control collapses it; focus back on the toggle; phone centred again",
          not page.locator(".hub-side").is_visible() and g["focus"] == "presenter-toggle"
          and abs((g["phone"]["l"] + g["phone"]["r"]) / 2 - g["vw"] / 2) <= 1)
    set_presenter(page, True)
    set_presenter(page, False, via="escape")
    check(f"{tag}: Escape inside the panel collapses it", state(page) == "closed")


def functional(page: Page, requests: list[dict]) -> None:
    load(page)
    set_presenter(page, True)
    side = page.locator(".hub-side")
    page.locator("[data-testid=more-tests-toggle]").click()        # the 15 earlier scenarios, under "בדיקות נוספות"
    cards = page.locator("[data-testid=featured-scenarios] article.feat")
    reachable = []
    for i in range(cards.count()):
        cards.nth(i).scroll_into_view_if_needed()
        reachable.append(cards.nth(i).is_visible())
    page.locator("[data-testid=all-scenarios-toggle]").click()
    toggles = page.locator("[data-testid=all-scenarios] [data-testid^=scn-toggle-L-]")
    toggles.last.scroll_into_view_if_needed()
    last, pane = toggles.last.bounding_box(), side.bounding_box()
    check("all scenario cards reachable in the panel: 4 featured, 11 in 'כל תרחישי הבדיקה' (the last one scrolls into view)",
          cards.count() == 4 and all(reachable) and toggles.count() == 11
          and pane["y"] <= last["y"] and last["y"] + last["height"] <= pane["y"] + pane["height"], f"{cards.count()} + {toggles.count()}")
    before = page.locator(".phone").bounding_box()
    side.evaluate("e => e.scrollTop = 0")
    side.evaluate("e => e.scrollTop = 1600")
    check("the panel scrolls on its own; the phone and the page stay put",
          side.evaluate("e => e.scrollTop") > 0 and page.locator(".phone").bounding_box() == before
          and page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1"), f"scrollTop={side.evaluate('e => e.scrollTop')}")
    if READONLY:
        return

    ok_all = []
    for doc_id in ("loan/id_card_ido.pdf", "01_INITIAL_UPLOADS/ido_2026_09.pdf", "loan/statement_ido_2026-07_09.pdf"):
        ok_all.append(same_bytes(page, page.locator(f"[data-testid=featured-download][data-doc-id='{doc_id}']").first))
    page.locator("[data-testid=scn-toggle-L-11]").click()
    ok_all.append(same_bytes(page, page.locator("[data-testid=scn-L-11] [data-testid=scn-download]").first))
    check("fixture PDFs download from the panel byte-identical to the manifest (featured cards and the test library)",
          all(ok for ok, _ in ok_all), ", ".join(d for _, d in ok_all))

    review = page.locator("[data-testid=featured-REVIEW]")
    review.locator("[data-testid=featured-open-case]").click()
    expect(page.locator(".case-pill")).to_contain_text(FEATURED["REVIEW"]["caseDisplay"], timeout=15000)
    page.locator("[data-testid=scn-L-11] [data-testid=scn-open-case-L-11]").click()
    expect(page.locator(".case-pill")).to_contain_text("438838999", timeout=15000)
    review.locator("[data-testid=featured-open-case]").click()
    expect(page.locator(".case-pill")).to_contain_text(FEATURED["REVIEW"]["caseDisplay"], timeout=15000)
    check("scenario selection opens the right case in the app, with the panel still open",
          state(page) == "open", FEATURED["REVIEW"]["caseDisplay"])

    # state kept across collapse / reopen
    review.locator("[data-testid=featured-toggle]").click()
    expect(review.locator("[data-testid=featured-playbook]")).to_be_visible()
    page.locator(".bottom-nav button", has_text="מסמכים").click()
    expect(page.locator("[data-testid^='req-']").first).to_be_visible(timeout=15000)
    page.evaluate("document.querySelector('.phone').dataset.probe = 'same-node'; document.querySelector('.screen').scrollTop = 160")
    side.evaluate("e => e.scrollTop = 900")
    page.wait_for_timeout(600)                       # the app's screen scrolls smoothly
    pill, url = page.locator(".case-pill").inner_text(), page.url
    app_scroll, pane_scroll = page.evaluate("document.querySelector('.screen').scrollTop"), side.evaluate("e => e.scrollTop")
    mark = len(requests)
    set_presenter(page, False)
    page.wait_for_timeout(300)
    set_presenter(page, True)
    page.wait_for_timeout(300)
    during = [r for r in requests[mark:] if "/api/" in r["url"]]
    noisy = [r for r in during if not (r["url"].endswith("/presence") and '"heartbeat"' in (r["body"] or ""))]
    kept = {"case": page.locator(".case-pill").inner_text() == pill, "screen": page.url == url,
            "dom": page.evaluate("document.querySelector('.phone').dataset.probe") == "same-node",
            "scroll": page.evaluate("document.querySelector('.screen').scrollTop") == app_scroll}
    check("collapse + reopen keeps the open case, the screen, the app's own DOM and scroll — the app is not rebuilt",
          all(kept.values()) and app_scroll > 0, f"{pill} · {url.split(BASE)[-1]} · {kept} · app scrollTop {app_scroll}")
    check("…and the panel's own state: open card playbook, open test library, expanded scenario, scroll position",
          review.locator("[data-testid=featured-playbook]").is_visible()
          and page.locator("[data-testid=all-scenarios]").get_attribute("open") is not None
          and page.locator("[data-testid=scn-toggle-L-11]").get_attribute("aria-expanded") == "true"
          and abs(side.evaluate("e => e.scrollTop") - pane_scroll) <= 1, f"scrollTop {pane_scroll}")
    check("toggling sends nothing to the server (no case call, no customer-activity presence for the follow-up engine)",
          not noisy, "; ".join(f"{r['method']} {r['url'].split(BASE)[-1]} {r['body'] or ''}"[:120] for r in noisy))

    page.locator(".bottom-nav button", has_text="ראשי").click()
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible()
    open_nav = state(page) == "open"
    set_presenter(page, False)
    page.locator(".bottom-nav button", has_text="שלבים").click()
    page.wait_for_timeout(300)
    closed_nav = state(page) == "closed"
    set_presenter(page, True)
    page.locator(".hub-bar a", has_text="תצוגת הבנקאית").click()
    expect(page.locator("[data-testid=banker-readiness], [data-testid=review-queue]").first).to_be_visible(timeout=20000)
    page.go_back()
    expect(page.locator(".hub")).to_be_visible(timeout=15000)
    back = state(page) == "open"
    page.reload()
    expect(page.locator(".case-pill")).not_to_contain_text("טוען", timeout=20000)
    check("navigating inside the app keeps the chosen state (open and closed); banker view and back keeps it; a reload starts collapsed",
          open_nav and closed_nav and back and state(page) == "closed", f"open={open_nav} closed={closed_nav} back={back}")

    load(page)
    set_presenter(page, True)
    title, close = page.locator(".hub-side-title").bounding_box(), page.locator("[data-testid=presenter-close]").bounding_box()
    heading = page.locator("[data-testid=use-cases] h2")
    font = side.evaluate("e => getComputedStyle(e).fontFamily")
    check("RTL and Hebrew typography kept: dir=rtl, panel rtl, title on the right and close on the left, headings right-aligned, Open Sans",
          page.evaluate("document.documentElement.dir") == "rtl" and side.evaluate("e => getComputedStyle(e).direction") == "rtl"
          and title["x"] > close["x"] and heading.evaluate("e => getComputedStyle(e).textAlign") in ("start", "right")
          and "Open Sans" in font and side.evaluate("e => e.scrollWidth <= e.clientWidth"), font)
    shot(page, "1440x900-open-functional")


def tablet(page: Page) -> None:
    load(page)
    g = geo(page)
    check("820×1100: collapsed, phone centred, the compact toggle is clear of the phone",
          state(page) == "closed" and abs((g["phone"]["l"] + g["phone"]["r"]) / 2 - g["vw"] / 2) <= 1
          and page.locator("[data-testid=presenter-toggle]").is_visible() and not overlaps(g["toggle"], g["phone"]) and g["overflow"] <= 0)
    shot(page, "820x1100-collapsed")
    before = g["phone"]
    set_presenter(page, True)
    g = geo(page)
    check("820×1100: opens as a drawer over a backdrop; the phone is not squeezed or moved",
          page.locator("[data-testid=presenter-scrim]").is_visible() and g["side"]["w"] <= 400 and g["phone"] == before and g["overflow"] <= 0,
          f"drawer {g['side']['w']:.0f}px")
    shot(page, "820x1100-open")
    page.mouse.click(g["vw"] - 40, g["vh"] / 2)
    expect(page.locator(".hub")).to_have_attribute("data-presenter", "closed")
    check("820×1100: a click on the backdrop closes it", True)


def mobile(page: Page) -> None:
    load(page)
    g = geo(page)
    check("390×844: the app is full width; no presenter control over it; no sideways scroll",
          state(page) == "closed" and not page.locator("[data-testid=presenter-toggle]").is_visible()
          and g["phone"]["w"] == 390 and g["overflow"] <= 0)
    shot(page, "390x844-collapsed")
    set_presenter(page, True, via="menu")
    g = geo(page)
    check("390×844: the menu's 'הדגמה' section opens the presenter full width; it closes with its own control",
          page.locator(".hub-side").is_visible() and g["side"]["w"] == 390 and g["overflow"] <= 0
          and page.locator("[data-testid=use-cases]").is_visible())
    shot(page, "390x844-open")
    set_presenter(page, False)
    check("390×844: closed again, the app is back as it was", not page.locator(".hub-side").is_visible()
          and page.locator("[data-testid=readiness-state]").is_visible() and geo(page)["overflow"] <= 0)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        try:
            for w, h in ((1440, 900), (1280, 800), (1024, 768)):
                ctx = browser.new_context(viewport={"width": w, "height": h}, locale="he-IL")
                desktop(ctx.new_page(), w, h)
                ctx.close()
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL", accept_downloads=True)
            page = ctx.new_page()
            requests: list[dict] = []
            page.on("request", lambda r: requests.append({"method": r.method, "url": r.url, "body": r.post_data}))
            functional(page, requests)
            ctx.close()
            ctx = browser.new_context(viewport={"width": 820, "height": 1100}, locale="he-IL")
            tablet(ctx.new_page())
            ctx.close()
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True, has_touch=True)
            mobile(ctx.new_page())
            ctx.close()
        except Exception as exc:
            check("check ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
            for c in browser.contexts:
                for i, pg in enumerate(c.pages):
                    pg.screenshot(path=str(OUT / f"failure-{i}.png"))
        browser.close()
    passed = sum(r["pass"] for r in RESULTS)
    (OUT / "results.json").write_text(json.dumps({"base": BASE, "readonly": READONLY, "passed": passed, "total": len(RESULTS),
                                                  "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} presenter layout checks passed · {BASE}" + (" · read-only" if READONLY else ""))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
