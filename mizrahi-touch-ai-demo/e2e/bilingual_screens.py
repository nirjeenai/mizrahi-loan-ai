"""Customer-app baselines for the bilingual work: screenshots, DOM text and API JSON of every customer screen, on a
REPLAY stack (zero Gemini calls), and a pixel/text/JSON comparison of two captures.

    # REPLAY backend with a FRESH data dir (from backend/), and the isolated frontend build (from mizrahi-touch-ai-demo/)
    .venv/bin/python ../e2e/replay_backend.py --port 8796 --data ../e2e/artifacts/bilingual/data-<tag>
    node e2e/serve_frontend.mjs e2e/artifacts/bilingual/web-<tag> 5851 http://127.0.0.1:8796
    # capture (LANG=he: the app's default, nothing in localStorage; LANG=en: the English UI)
    SHOTS_BASE=http://127.0.0.1:5851 SHOTS_OUT=e2e/artifacts/bilingual/shots-<tag> LANG_UI=he \
        backend/.venv/bin/python e2e/bilingual_screens.py capture
    # compare two Hebrew captures (exit 1 on any difference outside the allowed regions)
    backend/.venv/bin/python e2e/bilingual_screens.py compare e2e/artifacts/bilingual/shots-baseline e2e/artifacts/bilingual/shots-<tag>

Seeding goes through the real upload route, one file at a time and waiting for each review, so two runs on fresh data
dirs produce the same cases. Timestamps are masked in screenshots and replaced in text; ids are normalized in JSON."""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageChops
from playwright.sync_api import Page, expect, sync_playwright

import isolation

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from tests.golden_util import normalize  # noqa: E402

PRESENTER = ROOT.parent / "fixtures" / "presenter"
MANIFEST = json.loads((PRESENTER / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
DOCS = {d["id"]: d for d in MANIFEST["documents"]}
FEATURED = {f["outcome"]: f for f in MANIFEST["featured"]}
CORRECTION, PASS, BLOCKER, EMPTY = "DEMO-MTZ-2026-009", "DEMO-MTZ-2026-006", "DEMO-MTZ-2026-008", "DEMO-MTZ-2026-101"
MOBILE, DESKTOP = {"width": 390, "height": 844}, {"width": 1440, "height": 900}
# times shown to the customer come from the server clock: masked in pictures, replaced in text
# the rendered PDF page is source data whose rasterization varies by a few anti-aliased pixels between renders: it is
# masked, and the evidence boxes drawn over it are compared through their positions in the DOM text instead
MASK = ".upd-time, time, [data-testid=card-stale], .statusbar, .bubble-meta, [data-testid=evidence-viewer] img"
TIME_RE = re.compile(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}(?:,?\s*\|?\s*\d{1,2}:\d{2}(?::\d{2})?)?|\b\d{1,2}:\d{2}(?::\d{2})?\b")

# what the customer types in each language (the Hebrew script is the baseline's)
SCRIPT = {
    "he": {"name": "מיכל ברק", "id": "DEMO-ID-201", "purpose": "רכישת רכב", "net": "12 אלף נטו", "solo": "לא, רק אני",
           "ask": "מה חסר לי?"},
    "en": {"name": "Michal Barak", "id": "DEMO-ID-201", "purpose": "Buying a car", "net": "12,000 net", "solo": "No, just me",
           "ask": "What am I missing?"},
}


# ---------------------------------------------------------------- seeding (API, through the frontend's proxy)
def seed(base: str) -> dict[str, list[dict]]:
    c = httpx.Client(base_url=base, timeout=60)
    for case in (CORRECTION, PASS, BLOCKER, EMPTY):
        c.post("/api/session/demo/customer", json={"case_id": case}).raise_for_status()
    uploads: dict[str, list[dict]] = {}
    for route, case in (("CORRECTION", CORRECTION), ("PASS", PASS), ("BLOCKER", BLOCKER)):
        steps = FEATURED[route]["steps"]
        if route == "CORRECTION":
            steps = [s for s in steps if "CORRECTED" not in s["file"]]       # leave the case with its findings open
        for i, s in enumerate(steps, 1):
            d = DOCS[s["file"]]
            code = s.get("uploadAs") or d["uploadAs"]
            data = {"requirement_code": code}
            if code.endswith(":BRW-A"):
                data["borrower_id"] = "BRW-A"
            if s.get("period") and code.startswith("PAYSLIPS"):
                data["expected_period"] = s["period"]
            path = PRESENTER / d["downloadPath"]
            time.sleep(1.1)                  # one upload per second: equal timestamps would order documents by random id
            r = c.post(f"/api/cases/{case}/documents", data=data, files={"file": (path.name, path.read_bytes(), "application/pdf")})
            r.raise_for_status()
            uploads.setdefault(case, []).append(r.json())
            settle(c, case, i)
    return uploads


def settle(c: httpx.Client, case: str, documents: int, timeout: float = 120) -> None:
    end = time.time() + timeout
    while time.time() < end:
        s = c.get(f"/api/cases/{case}").json()
        n = s["readiness"]["counts"]
        if n["documents"] >= documents and not s["readiness"]["pending_jobs"] and n["processing"] == 0 and s["case_review"]:
            return
        time.sleep(0.6)
    raise TimeoutError(f"{case} did not settle")


def api_json(base: str, lang: str) -> dict:
    c = httpx.Client(base_url=base, timeout=60, headers={"X-MZ-Lang": lang} if lang == "en" else {})
    for case in (CORRECTION, PASS, BLOCKER, EMPTY):
        c.post("/api/session/demo/customer", json={"case_id": case}).raise_for_status()
    out: dict = {}
    names: dict[str, str] = {}
    for case in (CORRECTION, PASS, BLOCKER, EMPTY):
        docs = c.get(f"/api/cases/{case}/documents").json()
        names.update({d["document_id"]: f"DOC[{case[-3:]}:{d['filename']}]" for d in docs})
        out[case] = {"snapshot": c.get(f"/api/cases/{case}").json(), "documents": docs,
                     "followup": c.get(f"/api/cases/{case}/followup").json(),
                     "pages": {d["filename"]: c.get(f"/api/documents/{d['document_id']}").json() for d in docs}}
    # a document's id is random; its case and file name are not (every seeded file name is unique within its case)
    text = json.dumps(out, ensure_ascii=False)
    for did, name in names.items():
        text = text.replace(did, name)
    def unordered(v):                  # readiness sorts document_ids by their random ids
        if isinstance(v, dict):
            return {k: sorted(x) if k == "document_ids" and isinstance(x, list) else unordered(x) for k, x in v.items()}
        return [unordered(x) for x in v] if isinstance(v, list) else v
    return normalize(unordered(json.loads(text)))


# ---------------------------------------------------------------- capture
def prepare(page: Page, base: str, lang: str, case: str) -> None:
    page.goto(base + "/customer/stages")
    page.evaluate("([c, l]) => { localStorage.setItem('mz.case', c); if (l === 'en') localStorage.setItem('mz.lang', 'en');"
                  " else localStorage.removeItem('mz.lang'); }", [case, lang])


def settle_page(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.locator(".spinner").first.wait_for(state="detached", timeout=15000) if page.locator(".spinner").count() else None
    try:
        expect(page.locator("[data-testid=evidence-viewer].loading")).to_have_count(0, timeout=10000)
    except AssertionError:
        pass
    page.wait_for_timeout(1200)


class Capture:
    def __init__(self, out: Path, lang: str):
        self.out, self.lang = out, lang
        (out / "png").mkdir(parents=True, exist_ok=True)
        (out / "text").mkdir(parents=True, exist_ok=True)
        self.names: list[str] = []

    def shot(self, page: Page, name: str, full: bool = False) -> None:
        settle_page(page)
        page.screenshot(path=str(self.out / "png" / f"{name}.png"), animations="disabled", caret="hide",
                        mask=[page.locator(MASK)], mask_color="#ff00ff", full_page=full)
        text = page.evaluate("() => (document.querySelector('.phone') || document.body).innerText")
        side = page.evaluate("() => { const s = document.querySelector('.hub-side'); return s && s.offsetParent ? s.innerText : ''; }")
        attrs = page.evaluate("""() => { const p = document.querySelector('.phone'); const h = document.documentElement;
            return {html_lang: h.lang, html_dir: h.dir, phone_lang: p && p.getAttribute('lang'), phone_dir: p && p.getAttribute('dir'),
                    title: document.title, mz_lang: localStorage.getItem('mz.lang'),
                    evidence_boxes: [...document.querySelectorAll('.hl')].map(e => [e.dataset.field, e.style.left, e.style.top,
                                                                                     e.style.width, e.style.height, e.className])}; }""")
        body = TIME_RE.sub("<TIME>", text) + ("\n\n--- presenter pane ---\n" + TIME_RE.sub("<TIME>", side) if side else "")
        (self.out / "text" / f"{name}.txt").write_text(json.dumps(attrs, ensure_ascii=False) + "\n\n" + body, encoding="utf8")
        self.names.append(name)
        print("shot", name, flush=True)


def customer_screens(page: Page, cap: Capture, base: str, tag: str, mobile: bool) -> None:
    lang = cap.lang
    s = SCRIPT[lang]
    # the case with open findings: every customer screen
    prepare(page, base, lang, CORRECTION)
    page.goto(base + "/customer")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
    cap.shot(page, f"{tag}-home-correction", full=True)
    page.goto(base + "/customer/documents")
    expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).to_be_visible(timeout=15000)
    cap.shot(page, f"{tag}-documents-correction", full=True)
    docs = httpx.Client(base_url=base, timeout=30)
    docs.post("/api/session/demo/customer", json={"case_id": CORRECTION})
    listing = {d["filename"]: d["document_id"] for d in docs.get(f"/api/cases/{CORRECTION}/documents").json()}
    page.goto(base + f"/customer/documents/{listing['ido_2026_09.pdf']}")
    expect(page.locator(".page-title").first).to_be_visible(timeout=15000)
    cap.shot(page, f"{tag}-review-wrong-month", full=True)
    page.goto(base + f"/customer/documents/{listing['id_card_ido.pdf']}")
    expect(page.locator(".page-title").first).to_be_visible(timeout=15000)
    cap.shot(page, f"{tag}-review-id-valid", full=True)
    for route in ("stages", "request", "meetings", "tools"):
        page.goto(base + f"/customer/{route}")
        page.wait_for_timeout(300)
        cap.shot(page, f"{tag}-{route}", full=True)
    if mobile:
        page.goto(base + "/customer")
        expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
        page.locator(".touch-header .icon-btn").first.click()
        expect(page.locator(".drawer-panel")).to_be_visible()
        cap.shot(page, f"{tag}-drawer")
        page.locator(".drawer").click(position={"x": 370, "y": 400})
        page.goto(base + "/customer/documents")
        row = page.locator("[data-testid='req-PAYSLIPS:BRW-A']")
        expect(row).to_be_visible(timeout=15000)
        if not page.locator("[data-testid=upload-BRW-A]").count():
            row.locator(".dl-head").first.click()
        page.locator("[data-testid=upload-BRW-A]").first.click()
        expect(page.locator("[data-testid=upload-sheet]")).to_be_visible()
        cap.shot(page, f"{tag}-upload-sheet")
        page.goto(base + "/customer")
        expect(page.locator("[data-testid=fab]")).to_be_visible(timeout=20000)
        page.locator("[data-testid=fab]").click()
        expect(page.locator("[data-testid=chat-input]")).to_be_visible()
        page.locator("[data-testid=chat-input]").fill(s["ask"])
        page.locator("[data-testid=chat-send]").click()
        expect(page.locator("[data-testid=chat-log] .bubble.assistant")).to_have_count(1, timeout=30000)
        page.wait_for_timeout(1500)                          # the sheet's and the log's own animations end first
        cap.shot(page, f"{tag}-assistant")
    # complete case, blocker case, empty case
    for case, name in ((PASS, "pass"), (BLOCKER, "blocker"), (EMPTY, "empty")):
        prepare(page, base, lang, case)
        page.goto(base + "/customer")
        expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
        cap.shot(page, f"{tag}-home-{name}", full=True)
        page.goto(base + "/customer/documents")
        page.wait_for_timeout(600)
        cap.shot(page, f"{tag}-documents-{name}", full=True)
    # the conversational application: start, simulator, summary
    prepare(page, base, lang, CORRECTION)
    page.goto(base + "/customer/apply")
    expect(page.locator("[data-testid=cv2-pending]")).to_have_count(1, timeout=20000)
    cap.shot(page, f"{tag}-apply-start")

    def say(text: str) -> None:
        n = page.locator("[data-testid=cv2-msg]").count()
        page.locator("[data-testid=cv2-input]").fill(text)
        page.locator("[data-testid=cv2-send]").click()
        expect(page.locator("[data-testid=cv2-msg]")).to_have_count(n + 2, timeout=30000)
        page.wait_for_timeout(300)

    def reply(value: str) -> None:
        n = page.locator("[data-testid=cv2-msg]").count()
        page.locator(f"[data-testid=cv2-reply][data-value='{value}']").click()
        expect(page.locator("[data-testid=cv2-msg]")).to_have_count(n + 2, timeout=30000)
        page.wait_for_timeout(300)

    reply('"personal"')
    say(s["name"])
    say(s["id"])
    say(s["purpose"])
    expect(page.locator("[data-testid=ls-confirm]")).to_be_visible(timeout=15000)
    page.wait_for_timeout(700)                               # the log's own smooth scroll ends first
    page.locator("[data-testid=ls-hero]").evaluate("e => e.scrollIntoView({block: 'start'})")
    cap.shot(page, f"{tag}-apply-simulator")
    page.locator("[data-testid=ls-asset-unknown]").click()
    n = page.locator("[data-testid=cv2-msg]").count()
    page.locator("[data-testid=ls-confirm]").click()
    expect(page.locator("[data-testid=cv2-msg]")).to_have_count(n + 2, timeout=30000)
    reply('["salaried"]')
    say(s["net"])
    cap.shot(page, f"{tag}-apply-indication")
    say(s["solo"])
    expect(page.locator("[data-testid=cv2-summary]")).to_be_visible(timeout=15000)
    page.wait_for_timeout(1800)
    cap.shot(page, f"{tag}-apply-summary", full=True)


def capture(base: str, out: Path, lang: str) -> None:
    isolation.require_isolated(base)
    out.mkdir(parents=True, exist_ok=True)
    uploads = seed(base)
    (out / "uploads.json").write_text(json.dumps(normalize(uploads), ensure_ascii=False, indent=1), encoding="utf8")
    (out / "api.json").write_text(json.dumps(api_json(base, lang), ensure_ascii=False, indent=1), encoding="utf8")
    cap = Capture(out, lang)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for tag, viewport, mobile in (("m", MOBILE, True), ("d", DESKTOP, False)):
            ctx = browser.new_context(viewport=viewport, device_scale_factor=2 if mobile else 1, locale="he-IL",
                                      has_touch=mobile, is_mobile=mobile)
            page = ctx.new_page()
            customer_screens(page, cap, base, tag, mobile)
            if not mobile:                            # the presenter pane beside the app (Hebrew in both languages)
                prepare(page, base, lang, CORRECTION)
                page.goto(base + "/customer")
                expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=20000)
                page.locator("[data-testid=presenter-toggle]").click()
                expect(page.locator(".hub-side")).to_be_visible()
                cap.shot(page, "d-presenter-open")
            ctx.close()
        browser.close()
    (out / "index.json").write_text(json.dumps({"lang": lang, "screens": cap.names}, indent=1), encoding="utf8")
    print(f"captured {len(cap.names)} screens into {out}")


# ---------------------------------------------------------------- compare
def compare(a: Path, b: Path, allow: dict[str, list[tuple[int, int, int, int]]] | None = None) -> int:
    """Pixel, text and JSON differences between two captures. `allow`: per screen, regions (css px) where a difference
    is expected (the language switch). Writes <b>/diff/<screen>.png for every screen that differs."""
    allow = allow or {}
    bad = 0
    (b / "diff").mkdir(exist_ok=True)
    report = []
    for png in sorted((a / "png").glob("*.png")):
        other = b / "png" / png.name
        name = png.stem
        if not other.exists():
            report.append(f"MISSING  {name}")
            bad += 1
            continue
        x, y = Image.open(png).convert("RGB"), Image.open(other).convert("RGB")
        if x.size != y.size:
            report.append(f"SIZE     {name}: {x.size} → {y.size}")
            bad += 1
            continue
        diff = ImageChops.difference(x, y)
        box = diff.getbbox()
        scale = 2 if name.startswith("m-") else 1
        if box:
            mask = diff.convert("L").point(lambda v: 255 if v else 0)
            for (l, t, r, btm) in allow.get(name, []) + allow.get("*", []):
                mask.paste(0, (l * scale, t * scale, r * scale, btm * scale))
            box = mask.getbbox()
            if box:
                changed = sum(1 for v in mask.get_flattened_data() if v)
                overlay = y.copy()
                overlay.paste((255, 0, 0), mask=mask)
                overlay.save(b / "diff" / png.name)
                report.append(f"PIXELS   {name}: {changed} px changed in css box "
                              f"{tuple(v // scale for v in box)}")
                bad += 1
                continue
        report.append(f"same     {name}")
    for txt in sorted((a / "text").glob("*.txt")):
        other = b / "text" / txt.name
        if not other.exists():
            continue
        u = list(difflib.unified_diff(txt.read_text(encoding="utf8").splitlines(), other.read_text(encoding="utf8").splitlines(),
                                      "baseline", "now", lineterm="", n=0))
        if u:
            report.append(f"TEXT     {txt.stem}:\n    " + "\n    ".join(u[2:14]))
            bad += 1
    for f in ("api.json",):                       # uploads.json is a log: a worker may already be on the job
        if (a / f).exists() and (b / f).exists() and (a / f).read_text(encoding="utf8") != (b / f).read_text(encoding="utf8"):
            u = list(difflib.unified_diff((a / f).read_text(encoding="utf8").splitlines(),
                                          (b / f).read_text(encoding="utf8").splitlines(), lineterm="", n=0))
            report.append(f"JSON     {f}:\n    " + "\n    ".join(u[2:14]))
            bad += 1
    print("\n".join(report))
    print(f"\n{bad} difference(s) between {a.name} and {b.name}")
    (b / "compare-report.txt").write_text("\n".join(report) + f"\n\n{bad} difference(s) vs {a}\n", encoding="utf8")
    return 1 if bad else 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "capture"
    if mode == "capture":
        capture(os.environ.get("SHOTS_BASE", "http://127.0.0.1:5851"),
                Path(os.environ.get("SHOTS_OUT", ROOT / "artifacts" / "bilingual" / "shots")).resolve(),
                os.environ.get("LANG_UI", "he"))
    elif mode == "compare":
        regions = json.loads(os.environ.get("ALLOW_REGIONS", "{}"))
        sys.exit(compare(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(),
                         {k: [tuple(r) for r in v] for k, v in regions.items()}))
