"""Presenter "תרחישי בדיקה" pane — browser checks in a real Chrome against the running backend (:8791).

LEGACY (mortgage era, not yet adapted to loans): asserts the 10 golden CASE-xx scenarios and 21 golden files; --live
spends real Gemini calls. Kept for reference and later adaptation; the loan presenter pane is covered by
e2e/test_loan_journey.py (REPLAY). Never point --live at :8791 (Mizrahi #2 main) or :8790 (Mizrahi #1): it resets cases.

    backend/.venv/bin/python e2e/test_presenter.py          # pane, all 21 downloads + SHA-256, RTL, marks, no regression
    backend/.venv/bin/python e2e/test_presenter.py --live   # + CASE-01 → CASE-02 uploaded through the real app (real Gemini)
    PRESENTER_BASE=http://127.0.0.1:5196 ...                # against an isolated stack (see e2e/serve_frontend.mjs)

The live part downloads each PDF from the left pane and uploads it through the app's own upload sheet, then records the
actual review next to the golden expected output. Differences are reported, never asserted away.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Browser, Locator, Page, expect, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import demo_auth  # noqa: E402  (e2e/ is on sys.path when a suite runs as a script)

BASE = os.environ.get("PRESENTER_BASE", "http://127.0.0.1:8791")
demo_auth.install(BASE)                   # the service has no anonymous access (see demo_auth.py)
PRESENTER_CASE, QA_CASE = "DEMO-MTZ-2026-004", "DEMO-MTZ-2026-005"
ROOT = Path(__file__).resolve().parent
PRESENTER = ROOT.parent / "fixtures" / "presenter"
ART = ROOT / "artifacts" / "presenter"
DL = ART / "downloads"
RESULTS: list[tuple[str, bool, str]] = []
FRESH_TAB_RETRIES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(ART / f"{name}.png"))


def scenario(page: Page, sid: str) -> Locator:
    return page.locator(f"[data-testid=scn-{sid}]")


def set_open(page: Page, sid: str, want: bool) -> None:
    toggle = page.locator(f"[data-testid=scn-toggle-{sid}]")
    if (toggle.get_attribute("aria-expanded") == "true") != want:
        toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true" if want else "false")


def download(page: Page, card: Locator) -> tuple[Path, str]:
    try:
        with page.expect_download(timeout=8000) as info:
            card.locator("[data-testid=scn-download]").click()
        d = info.value
    except PlaywrightTimeout:
        # Chrome's per-tab multiple-download limiter can swallow rapid scripted clicks; a fresh tab starts clean.
        doc_id = card.get_attribute("data-doc-id")
        FRESH_TAB_RETRIES.append(doc_id)
        fresh = page.context.new_page()
        fresh.goto(f"{BASE}/customer")
        with fresh.expect_download(timeout=20000) as info:
            fresh.locator(f"[data-testid=scn-file][data-doc-id='{doc_id}'] [data-testid=scn-download]").first.click()
        d = info.value
        d.path()
        fresh.close()
    target = DL / d.suggested_filename
    d.save_as(target)
    return target, d.suggested_filename


def open_all(page: Page) -> None:
    """The technical scenarios live in the collapsed 'כל תרחישי הבדיקה' section of the pane."""
    section = page.locator("[data-testid=all-scenarios]")
    expect(section).to_be_attached(timeout=15000)
    if section.get_attribute("open") is None:
        page.locator("[data-testid=all-scenarios-toggle]").click()
    expect(page.locator("[data-testid=scenario-presenter]")).to_be_visible(timeout=15000)


def side_scroll_to(page: Page, locator: Locator, offset: int = 12) -> None:
    locator.evaluate("(el, off) => { const s = document.querySelector('.hub-side'); "
                     "s.scrollTop += el.getBoundingClientRect().top - s.getBoundingClientRect().top - off; }", offset)
    page.wait_for_timeout(250)


# ------------------------------------------------------------------ pane checks (no Gemini)
def pane_checks(browser: Browser, manifest: dict) -> None:
    docs = {d["id"]: d for d in manifest["documents"]}
    scenarios = manifest["scenarios"]
    n01, total = len(scenarios[0]["files"]), sum(len(s["files"]) for s in scenarios)
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="he-IL", accept_downloads=True)
    page = ctx.new_page()
    writes: list[str] = []
    # the app obtaining its demo session (POST /api/session/demo/…) is not a write of case data
    page.on("request", lambda r: writes.append(f"{r.method} {r.url}") if r.method != "GET" and "/api/session/" not in r.url else None)
    page.goto(f"{BASE}/customer")
    expect(page.locator(".ribbon")).to_contain_text("הדגמת קונספט")
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=15000)
    pane = page.locator("[data-testid=scenario-presenter]")
    check("the 10 scenarios sit in 'כל תרחישי הבדיקה', collapsed by default, below the featured scenarios",
          page.locator("[data-testid=all-scenarios]").get_attribute("open") is None
          and page.locator("[data-testid=featured-scenarios] article.feat").count() == 3)
    open_all(page)
    page.locator("[data-testid=lavi-files] > summary").click()
    expect(pane).to_be_visible(timeout=15000)

    # existing split screen and left-pane features
    phone, side = page.locator(".phone").bounding_box(), page.locator(".hub-side").bounding_box()
    check("split layout preserved: live app right, files pane left", phone["x"] >= side["x"] + side["width"] - 1,
          f"pane x={side['x']:.0f}-{side['x'] + side['width']:.0f} phone x={phone['x']:.0f}")
    fixtures = httpx.get(f"{BASE}/api/fixtures").json()
    old = page.locator(".hub-side a.hub-link[href^='/api/fixtures/file']")
    with page.expect_download() as info:
        old.first.click()
    old_dl = info.value
    old_path = DL / f"existing-{old_dl.suggested_filename}"
    old_dl.save_as(old_path)
    old_manifest = json.loads((ROOT.parent / "fixtures" / "out" / "manifest.json").read_text(encoding="utf8"))["files"]
    check("existing synthetic-documents list unchanged and still downloads", old.count() == len(fixtures)
          and sha(old_path) == next(f["sha256"] for f in old_manifest if f["file"] == fixtures[0]["file"]),
          f"{old.count()} files · {old_dl.suggested_filename}")
    check("existing banker / system links still in the pane", page.locator(".hub-bar a", has_text="תצוגת הבנקאית").count() == 1
          and page.locator(".hub-bar a", has_text="מערכת ואינטגרציות").count() == 1)
    expect(pane).to_contain_text("נתוני הדגמה בלבד")
    expect(pane).to_contain_text(manifest["disclosureHe"])
    check("pane marks data as synthetic and expected ≠ actual", True)

    # accordion structure
    titles = [page.locator(f"[data-testid=scn-toggle-{s['id']}] .scn-title").inner_text() for s in scenarios]
    check("10 scenarios in manifest order with exact Hebrew titles", titles == [s["titleHe"] for s in scenarios],
          " | ".join(t.split(" · ")[0] for t in titles))
    states = {s["id"]: page.locator(f"[data-testid=scn-toggle-{s['id']}]").get_attribute("aria-expanded") for s in scenarios}
    check("01 expanded by default, the other nine collapsed", states["CASE-01"] == "true"
          and all(v == "false" for k, v in states.items() if k != "CASE-01"))
    shot(page, "presenter-01-default")

    # every scenario: content, file order, verdict labels, downloads
    seen: dict[str, tuple[str, str]] = {}
    content_problems: list[str] = []
    for s in scenarios:
        set_open(page, s["id"], True)
        card = scenario(page, s["id"])
        if s["goalHe"] not in card.locator(".scn-goal").inner_text():
            content_problems.append(f"{s['id']} goal")
        block = card.locator(f"[data-testid=scn-expected-case-{s['id']}]")
        text = block.inner_text()
        content_problems += [f"{s['id']} expected line" for line in s["expectedCaseHe"] if line not in text]
        content_problems += [f"{s['id']} code {c}" for c in s.get("expectedReasonCodes", [])
                             if block.locator(f"[data-code={c}]").count() == 0]
        files = card.locator("[data-testid=scn-file]")
        order = [files.nth(i).get_attribute("data-doc-id") for i in range(files.count())]
        if order != s["files"]:
            content_problems.append(f"{s['id']} file order {order}")
        for i, doc_id in enumerate(s["files"]):
            fc, doc = files.nth(i), docs[doc_id]
            if fc.locator(".scn-name").inner_text() != doc["displayNameHe"]:
                content_problems.append(f"{doc_id} name")
            verdict = fc.locator(".scn-verdict")                   # under the file's collapsed 'פרטים טכניים'
            if verdict.get_attribute("data-verdict") != doc["expectedDocumentVerdict"] or not (verdict.text_content() or "").startswith("צפוי:"):
                content_problems.append(f"{doc_id} verdict")
            if doc_id not in seen:
                path, name = download(page, fc)
                seen[doc_id] = (name, sha(path))
        if s["id"] != "CASE-01":
            set_open(page, s["id"], False)
    page.locator("[data-testid=scn-supplementary] .scn-head").click()
    extras = page.locator("[data-testid=scn-supplementary] [data-testid=scn-file]")
    for i in range(extras.count()):
        doc_id = extras.nth(i).get_attribute("data-doc-id")
        path, name = download(page, extras.nth(i))
        seen[doc_id] = (name, sha(path))
    page.locator("[data-testid=scn-supplementary] .scn-head").click()
    check("each scenario shows goal, expected case findings, reason codes and its files in order", not content_problems,
          "; ".join(content_problems[:6]))
    bad = [d for d in docs if seen.get(d, ("", ""))[1] != docs[d]["sha256"]]
    src_bad = [d for d in docs if sha(PRESENTER / docs[d]["downloadPath"]) != docs[d]["sha256"]]
    check("all 21 PDFs downloaded from the pane; SHA-256 equals manifest and source file", len(seen) == 21 and not bad and not src_bad,
          f"downloaded={len(seen)} mismatched={bad + src_bad} fresh-tab retries={len(FRESH_TAB_RETRIES)}")
    names = {d: seen[d][0] for d in seen}
    check("browser filenames are the exact fixture names (no whitespace, no renames)",
          all(names[d] == Path(docs[d]["downloadPath"]).name and not any(ch.isspace() for ch in names[d]) for d in names))
    r = httpx.get(f"{BASE}/api/presenter/file", params={"id": "01_INITIAL_UPLOADS/ido_2026_09.pdf"})
    check("download served as application/pdf attachment with the original filename",
          r.headers["content-type"] == "application/pdf" and r.headers["content-disposition"] == 'attachment; filename="ido_2026_09.pdf"')
    probes = ["../../backend/.env", "golden_set/CASE_PROFILE.json", "01_INITIAL_UPLOADS/../../../backend/.env", "/etc/passwd"]
    codes = [httpx.get(f"{BASE}/api/presenter/file", params={"id": p}).status_code for p in probes]
    check("download route only serves manifest-listed PDFs", all(c == 404 for c in codes), str(codes))

    # the critical example: a readable August payslip named September
    c1 = scenario(page, "CASE-01")
    crit = c1.locator("[data-testid=scn-file][data-doc-id='01_INITIAL_UPLOADS/ido_2026_09.pdf']")
    exp_doc = crit.locator("[data-testid=scn-expected-doc]")
    found = [code for code in ("DUPLICATE_PERIOD", "FILENAME_CONTENT_PERIOD_MISMATCH", "REQUIRED_PERIOD_MISSING")
             if exp_doc.locator(f"[data-code={code}]").count()]
    status = c1.locator("[data-testid=scn-expected-case-CASE-01] .scn-status").text_content() or ""   # collapsed details
    check("ido_2026_09: document VALID, yet case shows duplicate Aug, missing Sep and filename mismatch",
          crit.locator(".scn-verdict").get_attribute("data-verdict") == "VALID" and len(found) == 3
          and "ספטמבר 2026" in crit.locator(".scn-warnline").inner_text() and "NEEDS_CUSTOMER_ACTION" in status
          and "NOT_EVALUATED" in status, f"case codes={found}")
    check("expected output never styled as an app verdict badge", pane.locator(".badge").count() == 0)
    side_scroll_to(page, crit)
    shot(page, "presenter-02-critical-ido_2026_09")

    # RTL, compactness and independent scrolling
    side_el = page.locator(".hub-side")
    num, name = crit.locator(".scn-num").bounding_box(), crit.locator(".scn-name").bounding_box()
    check("RTL: document dir=rtl, pane direction rtl, sequence badge on the right of the title",
          page.evaluate("document.documentElement.dir") == "rtl" and pane.evaluate("e => getComputedStyle(e).direction") == "rtl"
          and num["x"] > name["x"])
    check("LTR isolation for filenames and reason codes",
          crit.locator(".scn-filename .ltr").evaluate("e => getComputedStyle(e).direction") == "ltr"
          and crit.locator(".scn-code code").first.evaluate("e => getComputedStyle(e).direction") == "ltr")
    check("no horizontal scrolling in the pane or the page", side_el.evaluate("e => e.scrollWidth <= e.clientWidth")
          and page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    before = page.locator(".phone").bounding_box()
    side_el.evaluate("e => e.scrollTop = 0")
    side_el.evaluate("e => e.scrollTop = 1800")
    after = page.locator(".phone").bounding_box()
    check("pane scrolls independently; the live app stays in place", side_el.evaluate("e => e.scrollTop") > 0
          and before == after and page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1"),
          f"pane scrollTop={side_el.evaluate('e => e.scrollTop')}")

    # prerequisites
    pre1 = page.locator("[data-testid=scn-prereq-CASE-01]").inner_text()
    set_open(page, "CASE-02", True)
    pre2_loc = page.locator("[data-testid=scn-prereq-CASE-02]")
    pre2 = pre2_loc.inner_text()
    set_open(page, "CASE-05", True)
    pre5 = page.locator("[data-testid=scn-prereq-CASE-05]").inner_text()
    check("prerequisites: 01 reset first, 02 continue after 01 without reset, QA cases isolated",
          "מתחילים מתיק נקי" in pre1 and "438839004" in pre1 and page.locator("[data-testid=scn-reset-case-CASE-01]").count() == 1
          and "ממשיכים מתרחיש 01" in pre2 and page.locator("[data-testid=scn-reset-case-CASE-02]").count() == 0
          and "תיק QA מבודד" in pre5 and "438839005" in pre5)
    declared = page.locator("[data-testid=scn-declared-CASE-01]").inner_text()
    in_01 = "03_SUPPORTING_DOCS/application_declarations.pdf" in scenarios[0]["files"]
    check("01: declared income comes from the case data as CUSTOMER_DECLARED; the declarations PDF is not in the upload sequence",
          "CUSTOMER_DECLARED" in declared and "לא מאומתת" in declared and not in_01
          and scenario(page, "CASE-01").locator("[data-testid=scn-file][data-doc-id$='application_declarations.pdf']").count() == 0)
    set_open(page, "CASE-02", False)

    # presenter marks: local only, persistent, mutually exclusive verdict marks, independent reset
    first = c1.locator("[data-testid=scn-file]").first
    first.locator("[data-testid=mark-uploaded]").check()
    first.locator("[data-testid=mark-matched]").check()
    first.locator("[data-testid=mark-mismatch]").check()
    c1.locator("[data-testid=scn-expected-case-CASE-01] [data-testid=mark-uploaded]").check()
    count = page.locator("[data-testid=scn-count-CASE-01]").inner_text()
    exclusive = first.locator("[data-testid=mark-mismatch]").is_checked() and not first.locator("[data-testid=mark-matched]").is_checked()
    flagged = page.locator("[data-testid=scn-toggle-CASE-01] .scn-chip.warn").count() == 1
    page.reload()
    open_all(page)
    expect(page.locator("[data-testid=scn-count-CASE-01]")).to_be_visible(timeout=15000)
    first = scenario(page, "CASE-01").locator("[data-testid=scn-file]").first
    persisted = first.locator("[data-testid=mark-uploaded]").is_checked() and first.locator("[data-testid=mark-mismatch]").is_checked()
    check("presenter checkboxes: count x/y, exclusive match/mismatch, flag, persisted across reload",
          f"1/{n01}" in count and exclusive and flagged and persisted
          and f"1/{total}" in page.locator("[data-testid=scn-progress]").inner_text(), count)
    check("checkboxes never call the backend", not [w for w in writes if "/api/" in w], str(writes))
    page.locator("[data-testid=scn-reset-marks]").click()
    page.locator("[data-testid=scn-reset-marks-confirm]").click()
    expect(page.locator("[data-testid=scn-count-CASE-01]")).to_contain_text(f"0/{n01}")
    check("'איפוס סימון בדיקות' clears marks only", not first.locator("[data-testid=mark-uploaded]").is_checked()
          and f"0/{total}" in page.locator("[data-testid=scn-progress]").inner_text() and not [w for w in writes if "/api/" in w])

    # keyboard
    t3 = page.locator("[data-testid=scn-toggle-CASE-03]")
    t3.focus()
    page.keyboard.press("Enter")
    opened = t3.get_attribute("aria-expanded") == "true"
    box = scenario(page, "CASE-03").locator("[data-testid=scn-file]").first.locator("[data-testid=mark-uploaded]")
    box.focus()
    page.keyboard.press("Space")
    toggled = box.is_checked()
    page.keyboard.press("Space")
    t3.focus()
    page.keyboard.press("Space")
    check("keyboard: Enter/Space toggle accordions and checkboxes", opened and toggled and t3.get_attribute("aria-expanded") == "false")

    # technical details stay hidden until asked
    tech = scenario(page, "CASE-01").locator("[data-testid=scn-tech-CASE-01]")
    hidden_first = not tech.locator("pre.json").is_visible()
    tech.locator("summary").click()
    tech_text = tech.inner_text()
    check("'פרטים טכניים' collapsed by default; shows expected JSON, rubrics, figures, provenance",
          hidden_first and "initial_review_expected.json" in tech_text and "PAYSLIP_REVIEW@1.0-demo" in tech_text
          and "DECLARED_INCOME_REVIEW" in tech_text and "₪18,500" in tech_text and "₪1,600" in tech_text
          and "תואם למניפסט" in tech_text)
    side_scroll_to(page, tech)
    shot(page, "presenter-03-technical-details")
    tech.locator("summary").click()

    # open the scenario case on the right, and the guarded reset of the (empty) isolated QA case
    page.locator("[data-testid=scn-open-case-CASE-05]").click()
    expect(page.locator(".case-pill")).to_contain_text("438839005", timeout=15000)
    expect(page.locator("[data-testid=scn-prereq-CASE-05]")).to_contain_text("פתוח עכשיו מימין")
    page.locator("[data-testid=scn-reset-case-CASE-05]").click()
    expect(page.locator("[data-testid=scn-prereq-CASE-05] .scn-confirm")).to_contain_text("מוחק מתיק 438839005")
    before_confirm = list(writes)
    page.locator("[data-testid=scn-reset-case-CASE-05-confirm]").click()
    expect(page.locator("[data-testid=scn-prereq-CASE-05] [role=status]")).to_contain_text("אופס", timeout=15000)
    resets = [w for w in writes if w not in before_confirm]
    check("'open on the right' switches the live app's case; case reset needs inline confirmation and hits only that case",
          page.url.endswith("/customer/documents") and not [w for w in before_confirm if "/api/" in w]
          and resets == [f"POST {BASE}/api/cases/{QA_CASE}/reset"], str(resets))
    page.locator("[data-testid=scn-open-case-CASE-01]").click()
    expect(page.locator(".case-pill")).to_contain_text("438839004", timeout=15000)
    set_open(page, "CASE-05", False)
    side_scroll_to(page, scenario(page, "CASE-01"))
    shot(page, "presenter-04-split-case01-on-documents")

    # no regression: app navigation, banker view, system page
    page.locator(".bottom-nav button", has_text="ראשי").click()
    expect(page.locator("[data-testid=readiness-state]")).to_be_visible()
    page.locator(".bottom-nav button", has_text="מסמכים").click()
    expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).to_be_visible()
    page.locator(".hub-bar a", has_text="תצוגת הבנקאית").click()
    expect(page.locator("[data-testid=banker-readiness]")).to_be_visible(timeout=20000)
    page.go_back()
    open_all(page)
    page.locator(".hub-bar a", has_text="מערכת ואינטגרציות").click()
    expect(page.locator("body")).to_contain_text("MCP", timeout=20000)
    check("app navigation, banker view and system page still work from the pane", "/system" in page.url)
    ctx.close()

    # responsive: tablet stacks below the app with normal page scroll; phone hides the pane as before
    tab = browser.new_page(viewport={"width": 820, "height": 1100}, locale="he-IL")
    tab.goto(f"{BASE}/customer")
    expect(tab.locator("[data-testid=featured-scenarios]")).to_be_visible(timeout=15000)
    tp, ts = tab.locator(".phone").bounding_box(), tab.locator(".hub-side").bounding_box()
    check("tablet: single column, pane below the app, page scrolls, no horizontal overflow",
          ts["y"] >= tp["y"] + tp["height"] - 1 and tab.evaluate("document.documentElement.scrollHeight > innerHeight")
          and tab.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    tab.locator(".hub-side").scroll_into_view_if_needed()
    tab.screenshot(path=str(ART / "presenter-05-tablet.png"))
    tab.close()
    mob = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="he-IL")
    mob.goto(f"{BASE}/customer")
    expect(mob.locator("[data-testid=readiness-state]")).to_be_visible(timeout=15000)
    check("phone: pane hidden as before, app unchanged", not mob.locator(".hub-side").is_visible())
    mob.screenshot(path=str(ART / "presenter-06-mobile.png"))
    mob.close()


# ------------------------------------------------------------------ live CASE-01 → CASE-02 (real Gemini)
APP_CODE = {"FILENAME_CONTENT_PERIOD_MISMATCH": "FILE_NAME_PERIOD_MISMATCH",
            "DECLARED_NET_INCOME_VARIANCE": "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"}
APP_BORROWER = {"IDO": "BRW-A", "NOA": "BRW-B"}


def snap(case: str) -> dict:
    return httpx.get(f"{BASE}/api/cases/{case}", timeout=30).json()


def wait_settled(case: str, timeout: int = 480) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap(case)
        if not s["readiness"]["pending_jobs"] and s["readiness"]["state"] not in ("CHECKING", "RECHECKING"):
            return s
        time.sleep(2)
    raise TimeoutError(f"{case} did not settle")


def open_row(page: Page, code: str) -> None:
    """Requirement rows on the Documents screen start collapsed."""
    head = page.locator(f"[data-testid='req-{code}'] .dl-head")
    expect(head).to_be_visible(timeout=15000)
    if head.get_attribute("aria-expanded") != "true":
        head.click()


def upload(page: Page, borrower: str, path: Path) -> None:
    open_row(page, f"PAYSLIPS:{borrower}")
    page.locator(f"[data-testid=upload-{borrower}]").click()
    page.locator("[data-testid=file-input]").set_input_files(str(path))
    page.locator("[data-testid=upload-submit]").click()
    page.wait_for_selector("[data-testid=upload-stages]", timeout=20000)
    page.locator(".sheet-head button").click()


def actual(case: str) -> dict:
    s = snap(case)
    docs = httpx.get(f"{BASE}/api/cases/{case}/documents", timeout=30).json()

    def fact(r: dict, field: str):
        f = next((x for x in r.get("facts", []) if x["field"] == field), None)
        return f and f.get("value_normalized")

    def ps10(r: dict) -> dict | None:
        c = next((c for c in r.get("criteria", []) if c["criterion_id"] == "PS-10"), None)
        return c and {"outcome": c["outcome"], "decided_by": c["decided_by"], "explanation": c["explanation_he"]}

    return {
        "readiness": s["readiness"]["state"], "readiness_he": s["readiness"]["state_he"], "scope": s["readiness"]["scope"],
        "not_evaluated": s["readiness"]["not_evaluated"], "customer_actions": s["readiness"]["counts"]["customer_actions"],
        "bank_stage": {k: s["case"]["bank_stage"][k] for k in ("label_he", "index", "of", "authoritative")},
        "documents": [{"document_id": d["document_id"], "filename": d["filename"], "borrower_id": d["borrower_id"], "status": d["status"],
                       **({k: (d["review"] or {}).get(k) for k in ("verdict", "doc_type", "period", "file_name_period", "verdict_reason_codes")}),
                       "net": fact(d["review"] or {}, "net_pay"), "gross": fact(d["review"] or {}, "gross_pay"),
                       "facts": {f["field"]: {"value": f.get("value_raw"), "witness": (f.get("evidence") or {}).get("witness")}
                                 for f in (d["review"] or {}).get("facts", [])},
                       "ps10": ps10(d["review"] or {})} for d in docs],
        "requirements": {r["borrower_id"]: {k: r.get(k) for k in ("ai_state_he", "covered", "missing", "duplicates", "pending_review")}
                         for r in s["readiness"]["requirements"] if r["evaluated_by_ai"]},
        "findings": [{k: f.get(k) for k in ("code", "status", "review_state", "borrower_id", "period", "resolution", "title_he")}
                     for f in s["findings"]],
        "income": {bid: {**{k: v.get(k) for k in ("declared_net_monthly_ils", "declared_provenance", "average_documented_net_ils",
                                                   "difference_ils", "difference_pct", "months_compared")},
                         "months": {m: {k: x.get(k) for k in ("document_id", "document_verdict", "net")} for m, x in (v.get("months") or {}).items()}}
                   for bid, v in ((s.get("case_review") or {}).get("income") or {}).items()},
    }


def row(item: str, expected, got, verdict: str, note: str = "") -> dict:
    return {"item": item, "expected": expected, "actual": got, "result": verdict, "note": note}


def finding_rows(expected_findings: list[dict], act: dict) -> list[dict]:
    rows = []
    for f in expected_findings:
        code = APP_CODE.get(f["reason_code"], f["reason_code"])
        cands = [a for a in act["findings"] if a["code"] == code
                 and (not f.get("borrower_ref") or a["borrower_id"] == APP_BORROWER.get(f["borrower_ref"]))
                 and (not f.get("period") or a["period"] in (None, f["period"]))]
        a = cands[0] if cands else None
        want = f"{f['state']}{' · ' + f['owner'] if f.get('owner') else ''}"
        if not a:
            rows.append(row(f"ממצא {f['reason_code']}", want, "לא נמצא", "שונה"))
            continue
        got = f"{a['status']} · {a['review_state']}{' · ' + a['resolution'] if a.get('resolution') else ''}"
        st = f["state"]
        if st == "RESOLVED":
            res = "תואם" if a["status"] == "resolved" else "שונה"
        elif st == "SUPERSEDED":
            res = "תואם" if a["status"] in ("resolved", "superseded") else "תואם חלקית" if a["review_state"] == "INFO" else "שונה"
        elif st == "READY_FOR_BANKER":
            res = "תואם" if a["status"] == "open" and a["review_state"] == "NEEDS_BANKER_REVIEW" else "שונה"
        else:
            res = ("תואם" if a["status"] == "open" and a["review_state"] == "CUSTOMER_ACTION_REQUIRED"
                   else "תואם חלקית" if a["status"] == "open" else "שונה")
        rows.append(row(f"ממצא {f['reason_code']}", want, got, res, f"קוד באפליקציה: {code}" if code != f["reason_code"] else ""))
    return rows


def document_rows(scenario_files: list[str], docs: dict, act: dict) -> list[dict]:
    rows = []
    for doc_id in scenario_files:
        d = docs[doc_id]
        name = Path(d["downloadPath"]).name
        a = next((x for x in act["documents"] if x["filename"] == name), None)
        if not a:
            rows.append(row(f"{name} · verdict", d["expectedDocumentVerdict"], "לא הועלה", "שונה"))
            continue
        rows.append(row(f"{name} · verdict", d["expectedDocumentVerdict"], a["verdict"],
                        "תואם" if a["verdict"] == d["expectedDocumentVerdict"] else "שונה",
                        f"doc_type={a['doc_type']} codes={a['verdict_reason_codes']}"
                        + (f" · PS-10 {a['ps10']['outcome']} ({a['ps10']['decided_by']}): {a['ps10']['explanation']}" if a.get("ps10") else "")))
        if d["expectedPrintedPeriod"]:
            rows.append(row(f"{name} · חודש מודפס", d["expectedPrintedPeriod"], a["period"],
                            "תואם" if a["period"] == d["expectedPrintedPeriod"] else "שונה"))
        if d["expectedNetILS"] is not None:
            rows.append(row(f"{name} · נטו", d["expectedNetILS"], a["net"],
                            "תואם" if a["net"] is not None and float(a["net"]) == float(d["expectedNetILS"]) else "שונה"))
    return rows


def case_rows(exp: dict, act: dict, phase: str) -> list[dict]:
    rows = []
    for key, bid in APP_BORROWER.items():
        e, a = exp["by_borrower"][key], act["requirements"].get(bid, {})
        rows.append(row(f"{key} · חודשים חסרים", e["missing_periods"], a.get("missing"),
                        "תואם" if sorted(e["missing_periods"]) == sorted(a.get("missing") or []) else "שונה"))
        dups = sorted((a.get("duplicates") or {}).keys())
        rows.append(row(f"{key} · חודשים כפולים", e["duplicate_periods"], dups,
                        "תואם" if sorted(e["duplicate_periods"]) == dups else "שונה",
                        "בגולדן הכפילות הופכת ל-SUPERSEDED; באפליקציה הקובץ הישן עדיין נספר" if phase == "after" and dups else ""))
    rows += finding_rows(exp["expected_findings"], act)
    sample = exp["income_check"].get("sample_months", 3)
    for key, bid in APP_BORROWER.items():
        e, a = exp["income_check"][key], act["income"].get(bid, {})
        avg, diff, months = a.get("average_documented_net_ils"), a.get("difference_ils"), a.get("months_compared") or []
        valid = sum(1 for d in act["documents"] if d["borrower_id"] == bid and d["doc_type"] == "payslip" and d["verdict"] == "VALID")
        basis = f"ממוצע על {len(months)} חודשים ({', '.join(months)})" if avg is not None else f"לא חושב ממוצע — {valid} תלושים במצב VALID"
        if e.get("document_monthly_avg") is None:
            res = "תואם" if avg is None else "שונה"
            note = f"הגולדן דוחה ממוצע עד שהכיסוי מלא · {basis}" if avg is not None else ""
        else:
            same = avg is not None and abs(avg - e["document_monthly_avg"]) < 0.01 and abs(abs(diff) - e["difference"]) < 0.01
            res = ("תואם" if len(months) == sample else "תואם חלקית") if same else "שונה"
            note = basis
        rows.append(row(f"{key} · הכנסה (מוצהר/ממוצע/פער)", f"{e['declared']}/{e['document_monthly_avg']}/{e['difference']}",
                        f"{a.get('declared_net_monthly_ils')}/{avg}/{diff}", res, note))
    want_ready = {"NEEDS_CUSTOMER_ACTION": ("ACTION_REQUIRED",),
                  "READY_FOR_BANKER_REVIEW": ("READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS", "READY_FOR_HUMAN_REVIEW")}[exp["salary_documents_readiness"]]
    rows.append(row("מוכנות מסמכי השכר", exp["salary_documents_readiness"], act["readiness"],
                    "תואם" if act["readiness"] in want_ready else "שונה"))
    rows.append(row("אין אישור בנק / החלטת אשראי", "bank_decision=null", f"{act['bank_stage']['label_he']} · authoritative={act['bank_stage']['authoritative']}",
                    "תואם" if act["readiness"] != "PREPARATION_CONFIRMED" and not act["bank_stage"]["authoritative"] else "שונה"))
    expected_codes = {APP_CODE.get(f["reason_code"], f["reason_code"]) for f in exp["expected_findings"]}
    extra = [f"{f['code']} ({f['status']} · {f['review_state']})" for f in act["findings"] if f["code"] not in expected_codes]
    if extra:
        rows.append(row("ממצאים נוספים בפועל", "—", extra, "שונה", "לא קיימים ב-Expected"))
    return rows


def verify_corrected_behaviour(sid: str, act: dict) -> None:
    payslips = [d for d in act["documents"] if d["doc_type"] == "payslip"]
    variance = [f for f in act["findings"] if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE" and f["borrower_id"] == "BRW-B"]
    noa = act["income"].get("BRW-B", {})
    gap_open = (noa.get("average_documented_net_ils") == 16900 and noa.get("difference_ils") == -1600
                and noa.get("months_compared") == ["2026-07", "2026-08", "2026-09"] and noa.get("declared_provenance") == "CUSTOMER_DECLARED"
                and len(variance) == 1 and variance[0]["status"] == "open" and variance[0]["review_state"] == "NEEDS_BANKER_REVIEW")
    if sid == "CASE-01":
        check("live CASE-01: PS-10 decided by code as NOT_APPLICABLE on every golden payslip; payment date unknown, issue date kept apart",
              len(payslips) == 6 and all(d["ps10"]["outcome"] == "NOT_APPLICABLE" and d["ps10"]["decided_by"] == "code"
                                         and "payment_date" not in d["facts"] and "issue_date" in d["facts"] for d in payslips),
              "; ".join(f"{d['filename']}={d['ps10']['outcome']}" for d in payslips))
        check("live CASE-01: document verdicts VALID; period and net verified against the PDF text layer",
              all(d["verdict"] == "VALID" and d["facts"]["salary_period"]["witness"] == "text_layer_exact"
                  and d["facts"]["net_pay"]["witness"] == "text_layer_exact" for d in payslips),
              "; ".join(f"{d['filename']}={d['verdict']}" for d in payslips))
        check("live CASE-01: Noa's declared ₪18,500 vs documented ₪16,900 (−₪1,600) is open for the banker", gap_open, json.dumps(noa, ensure_ascii=False)[:220])
        ido = act["requirements"].get("BRW-A", {})
        check("live CASE-01: Ido September missing, August twice; the case needs customer action",
              ido.get("missing") == ["2026-09"] and ido.get("duplicates") == {"2026-08": 2} and act["readiness"] == "ACTION_REQUIRED",
              f"state={act['readiness']} missing={ido.get('missing')} duplicates={ido.get('duplicates')}")
    else:
        missing = [f for f in act["findings"] if f["code"] == "REQUIRED_PERIOD_MISSING" and f["borrower_id"] == "BRW-A"]
        check("live CASE-02: salary subset complete; September resolved by the new evidence; no open customer action",
              act["requirements"]["BRW-A"]["missing"] == [] and act["requirements"]["BRW-B"]["missing"] == []
              and all(f["status"] == "resolved" for f in missing) and act["customer_actions"] == 0,
              f"customer_actions={act['customer_actions']} missing_finding={[f['status'] for f in missing]}")
        check("live CASE-02: the income gap stays open for the banker", gap_open)
        check("live CASE-02: ready for banker review with open findings; whole mortgage case not evaluated; no bank approval",
              act["readiness"] == "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS" and act["scope"] == "income_documents.payslips"
              and len(act["not_evaluated"]) > 0 and not act["bank_stage"]["authoritative"] and act["bank_stage"]["label_he"] == "קיבלנו החלטה",
              f"state={act['readiness']} scope={act['scope']} not_evaluated={len(act['not_evaluated'])}")


def pay_date_run() -> list[dict]:
    """The printed-date branch of PS-10, in the isolated QA case (reset before and after)."""
    folder = ROOT.parent / "fixtures" / "pay_date" / "out"
    fixtures = json.loads((folder / "manifest.json").read_text(encoding="utf8"))["files"]
    httpx.post(f"{BASE}/api/cases/{QA_CASE}/reset", timeout=30).raise_for_status()
    for f in sorted(fixtures, key=lambda f: f["expect"]["PS-10"] != "FAIL"):      # the FAIL slip first: it must still count for income
        with open(folder / f["file"], "rb") as fh:
            httpx.post(f"{BASE}/api/cases/{QA_CASE}/documents", files={"file": (f["file"], fh, "application/pdf")},
                       data={"borrower_id": "BRW-A"}, timeout=60).raise_for_status()
        time.sleep(1.1)
    wait_settled(QA_CASE)
    act = actual(QA_CASE)
    (ART / "live-actual-pay-date.json").write_text(json.dumps(act, ensure_ascii=False, indent=2), encoding="utf8")
    rows = []
    for f in fixtures:
        d = next(x for x in act["documents"] if x["filename"] == f["file"])
        pay = d["facts"].get("payment_date") or {}
        ok = (d["ps10"]["outcome"] == f["expect"]["PS-10"] and d["verdict"] == f["expect"]["verdict"]
              and pay.get("value") == f["payment_date"] and pay.get("witness") == "text_layer_exact"
              and (d["facts"].get("issue_date") or {}).get("value") == f["issue_date"])
        check(f"live pay date {f['payment_date']} (issue {f['issue_date']}): PS-10 {f['expect']['PS-10']}, verdict {f['expect']['verdict']}", ok,
              f"actual PS-10={d['ps10']['outcome']} ({d['ps10']['decided_by']}) verdict={d['verdict']} payment_date={pay.get('value')} issue_date={(d['facts'].get('issue_date') or {}).get('value')}")
        rows.append(row(f"{f['file']} · PS-10", f["expect"]["PS-10"], d["ps10"]["outcome"], "תואם" if d["ps10"]["outcome"] == f["expect"]["PS-10"] else "שונה",
                        d["ps10"]["explanation"]))
        rows.append(row(f"{f['file']} · verdict", f["expect"]["verdict"], d["verdict"], "תואם" if d["verdict"] == f["expect"]["verdict"] else "שונה"))
    first = next(f for f in fixtures if f["expect"]["PS-10"] == "FAIL")
    first_id = next(x["document_id"] for x in act["documents"] if x["filename"] == first["file"])
    september = act["income"].get("BRW-A", {}).get("months", {}).get("2026-09", {})
    check("live: a payslip held for review on its payment date still feeds the income comparison",
          september.get("document_id") == first_id and september.get("document_verdict") == "NEEDS_REVIEW", json.dumps(september))
    httpx.post(f"{BASE}/api/cases/{QA_CASE}/reset", timeout=30).raise_for_status()
    return rows


def live_run(browser: Browser, manifest: dict) -> dict:
    docs = {d["id"]: d for d in manifest["documents"]}
    by_id = {s["id"]: s for s in manifest["scenarios"]}
    expected = {s["id"]: json.loads((PRESENTER / s["expectedJson"]).read_text(encoding="utf8")) for s in manifest["scenarios"] if s.get("expectedJson")}
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL", accept_downloads=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/customer")
    expect(page.locator("[data-testid=scenario-presenter]")).to_be_visible(timeout=15000)
    report: dict = {}

    # CASE-01 prerequisite through the pane: guarded reset, then open the scenario case on the right
    set_open(page, "CASE-01", True)
    page.locator("[data-testid=scn-reset-case-CASE-01]").click()
    page.locator("[data-testid=scn-reset-case-CASE-01-confirm]").click()
    expect(page.locator("[data-testid=scn-prereq-CASE-01] [role=status]")).to_contain_text("אופס", timeout=15000)
    page.locator("[data-testid=scn-open-case-CASE-01]").click()
    expect(page.locator(".case-pill")).to_contain_text("438839004", timeout=15000)
    check("live: presenter case reset via the pane and opened on the right", len(httpx.get(f"{BASE}/api/cases/{PRESENTER_CASE}/documents").json()) == 0)

    for sid in ("CASE-01", "CASE-02"):
        s = by_id[sid]
        set_open(page, sid, True)
        card = scenario(page, sid)
        started = time.time()
        for i, doc_id in enumerate(s["files"]):
            fc = card.locator("[data-testid=scn-file]").nth(i)
            path, name = download(page, fc)
            assert sha(path) == docs[doc_id]["sha256"], f"{name} checksum"
            borrower = "BRW-B" if docs[doc_id]["expectedBorrower"] == "NOA" else "BRW-A"
            upload(page, borrower, path)
            fc.locator("[data-testid=mark-uploaded]").check()
        settled = wait_settled(PRESENTER_CASE)
        act = actual(PRESENTER_CASE)
        uploaded = [d for d in act["documents"] if d["filename"] in {Path(docs[x]["downloadPath"]).name for x in s["files"]}]
        check(f"live {sid}: every PDF downloaded from the pane, uploaded through the app UI and reviewed",
              len(uploaded) == len(s["files"]) and all(d["status"] == "reviewed" for d in uploaded),
              f"{len(uploaded)}/{len(s['files'])} reviewed in {time.time() - started:.0f}s · state={settled['readiness']['state']}")
        verify_corrected_behaviour(sid, act)
        exp = expected[sid]
        rows = document_rows(s["files"], docs, act) + case_rows(exp, act, "initial" if sid == "CASE-01" else "after")
        report[sid] = {"expected_json": s["expectedJson"], "actual": act, "comparison": rows}
        (ART / f"live-actual-{sid}.json").write_text(json.dumps(act, ensure_ascii=False, indent=2), encoding="utf8")
        for r in rows:
            print(f"  {r['result']:<10} {r['item']} · expected={r['expected']} · actual={r['actual']}{' · ' + r['note'] if r['note'] else ''}")

        # split-screen evidence: expected (left) beside actual (right)
        page.goto(f"{BASE}/customer/documents")
        expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        side_scroll_to(page, scenario(page, sid).locator(f"[data-testid=scn-expected-case-{sid}]"))
        shot(page, f"live-{sid}-expected-vs-documents")
        if sid == "CASE-01":
            target = scenario(page, sid).locator("[data-testid=scn-file][data-doc-id='01_INITIAL_UPLOADS/ido_2026_09.pdf']")
            side_scroll_to(page, target)
            page.locator("[data-testid=doc-card]", has_text="ido_2026_09.pdf").first.click()
            expect(page.locator("[data-testid=review-verdict]")).to_be_visible(timeout=15000)
            page.wait_for_timeout(1200)
            shot(page, "live-CASE-01-ido_2026_09-expected-vs-review")
        page.goto(f"{BASE}/customer")
        expect(page.locator("[data-testid=readiness-state]")).to_be_visible(timeout=15000)
        page.wait_for_timeout(600)
        side_scroll_to(page, scenario(page, sid).locator(f"[data-testid=scn-expected-case-{sid}] .scn-status"), 300)
        shot(page, f"live-{sid}-expected-vs-home")
        page.goto(f"{BASE}/customer/documents")
        expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).to_be_visible(timeout=15000)
        set_open(page, sid, False)
    ctx.close()
    return report


def write_report(report: dict) -> None:
    lines = ["# Presenter live run — expected (golden set) vs actual (running app)", "",
             "Expected = static golden-set ground truth. Actual = the app's real Gemini review of the same PDFs, uploaded through its UI.", ""]
    for sid, data in report.items():
        lines += [f"## {sid} · expected JSON `{data['expected_json']}`", "", "| item | expected | actual | result | note |", "|---|---|---|---|---|"]
        for r in data["comparison"]:
            cell = lambda v: str(v).replace("|", "\\|")
            lines.append(f"| {cell(r['item'])} | {cell(r['expected'])} | {cell(r['actual'])} | {r['result']} | {cell(r['note'])} |")
        counts = {k: sum(1 for r in data["comparison"] if r["result"] == k) for k in ("תואם", "תואם חלקית", "שונה")}
        lines += ["", f"Totals: {counts}", ""]
    (ART / "live-comparison.md").write_text("\n".join(lines), encoding="utf8")
    (ART / "live-comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")


def main() -> int:
    live = "--live" in sys.argv
    DL.mkdir(parents=True, exist_ok=True)
    manifest = httpx.get(f"{BASE}/api/presenter/scenarios", timeout=30).json()["manifest"]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        pane_checks(browser, manifest)
        if live:
            report = live_run(browser, manifest)
            report["PAY-DATE"] = {"expected_json": "fixtures/pay_date/out/manifest.json", "actual": None, "comparison": pay_date_run()}
            write_report(report)
        browser.close()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    (ART / "presenter-results.json").write_text(json.dumps([{"check": n, "pass": ok, "detail": d} for n, ok, d in RESULTS],
                                                           ensure_ascii=False, indent=2), encoding="utf8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
