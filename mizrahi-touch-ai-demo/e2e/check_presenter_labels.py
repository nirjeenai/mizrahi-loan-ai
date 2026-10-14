"""The presenter pane's fixture labels in a real Chrome: every downloadable file shows its Hebrew label (from the manifest,
checked against the PDF itself), where it is uploaded, and a small technical file name; downloads are byte-identical to
the fixtures; scenario selection and the case reset still work; RTL without sideways scrolling. Isolated REPLAY stack.

    PRESENTER_BASE=http://127.0.0.1:5846 backend/.venv/bin/python e2e/check_presenter_labels.py
    PRESENTER_BASE=http://localhost:5192 PRESENTER_READONLY=1 backend/.venv/bin/python e2e/check_presenter_labels.py  # no reset
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("PRESENTER_BASE", "http://127.0.0.1:5846")
ROOT = Path(__file__).resolve().parent
PRESENTER = ROOT.parent / "fixtures" / "presenter"
MANIFEST = json.loads((PRESENTER / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
DOCS = {d["id"]: d for d in MANIFEST["documents"]}
OUT = ROOT / "artifacts" / "presenter-labels"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def download(page: Page, link) -> bytes:
    with page.expect_download() as dl:
        link.click()
    target = OUT / "downloads" / dl.value.suggested_filename
    target.parent.mkdir(parents=True, exist_ok=True)
    dl.value.save_as(str(target))
    return target.read_bytes()


def same_bytes(page: Page, link) -> tuple[bool, str]:
    doc_id = link.get_attribute("data-doc-id")
    data = download(page, link)
    source = (PRESENTER / DOCS[doc_id]["downloadPath"]).resolve().read_bytes()
    return data == source and hashlib.sha256(data).hexdigest() == DOCS[doc_id]["sha256"], doc_id


def run(page: Page) -> None:
    page.goto(f"{BASE}/customer")
    expect(page.locator("[data-testid=featured-scenarios]")).to_be_visible(timeout=20000)
    side = page.locator(".hub-side")
    check("RTL pane without sideways scrolling", side.evaluate("e => getComputedStyle(e).direction") == "rtl"
          and side.evaluate("e => e.scrollWidth <= e.clientWidth"))
    # featured cards: label first, file name in small print, one compact download per file
    bad = []
    for f in MANIFEST["featured"]:
        rows = page.locator(f"[data-testid=featured-{f['outcome']}] .fx")
        for i in range(rows.count()):
            row = rows.nth(i)
            doc = DOCS[row.get_attribute("data-doc-id")]
            label = row.locator(".fx-label").inner_text()
            small = row.locator(".fx-file").inner_text()
            if label != next(s["labelHe"] for s in f["steps"] if s["file"] == doc["id"]) or small != doc["downloadPath"].split("/")[-1]:
                bad.append(f"{f['outcome']}:{label}|{small}")
    check("featured cards: every file row shows its manifest label and its technical name in small print", not bad, "; ".join(bad))
    wrong = page.locator("[data-testid=featured-CORRECTION] .fx[data-doc-id='01_INITIAL_UPLOADS/ido_2026_09.pdf']")
    check("the September-named payslip is labelled by its printed month (August) and says why it is there",
          "אוגוסט 2026" in wrong.locator(".fx-label").inner_text() and "ספטמבר" not in wrong.locator(".fx-label").inner_text()
          and "אוגוסט" in wrong.locator(".fx-note").inner_text() and "ספטמבר" in wrong.locator(".fx-sub").inner_text(),
          f"{wrong.locator('.fx-label').inner_text()} · {wrong.locator('.fx-note').inner_text()}")
    blocker = page.locator("[data-testid=featured-BLOCKER] .fx.wrong")
    check("wrong-slot file: marked, routed to עידו ← תעודת זהות, with the reason",
          blocker.count() == 1 and "עידו ← תעודת זהות" in blocker.inner_text() and "מסמך שגוי" in blocker.inner_text())
    check("each featured card says how to demo it", page.locator("[data-testid=featured-instruction]").count() == 4)
    page.screenshot(path=str(OUT / "01-featured.png"))
    for doc_id in ("01_INITIAL_UPLOADS/ido_2026_09.pdf", "loan/id_card_ido.pdf", "loan/statement_ido_2026-07_09.pdf"):
        ok, _ = same_bytes(page, page.locator(f"[data-testid=featured-download][data-doc-id='{doc_id}']").first)
        check(f"download is byte-identical to the fixture: {DOCS[doc_id]['displayNameHe']}", ok)
    # the test library
    page.locator("[data-testid=all-scenarios-toggle]").click()
    for sid in ("L-03", "L-05", "L-11"):
        page.locator(f"[data-testid=scn-toggle-{sid}]").click()
    s11 = page.locator("[data-testid=scn-L-11]")
    expect(s11.locator("[data-testid=scn-instruction-L-11]")).to_be_visible()
    labels = s11.locator("[data-testid=scn-file-label]").all_inner_texts()
    check("joint scenario: Lavi files labelled with the applicant and month, routed to עידו ← תלושי שכר (now REPLAY-recorded)",
          labels == ["תלוש שכר — עידו לביא — יולי 2026", "תלוש שכר — עידו לביא — אוגוסט 2026"]
          and s11.locator(".scn-upload").first.inner_text().count("עידו ← תלושי שכר") == 1 and "LIVE בלבד" not in s11.inner_text(),
          " | ".join(labels))
    ok, doc_id = same_bytes(page, s11.locator("[data-testid=scn-download]").first)
    check("Lavi file (fixtures/out) downloads byte-identical through the presenter endpoint", ok, doc_id)
    s05 = page.locator("[data-testid=scn-L-05]")
    check("wrong-type scenario: the payslip row says it goes to the ID card on purpose",
          "עידו ← תעודת זהות" in s05.inner_text() and "מסמך שגוי" in s05.inner_text())
    s03 = page.locator("[data-testid=scn-L-03]")
    check("wrong-month scenario: the third payslip is to be picked as September and is labelled August",
          "חודש ספטמבר 2026" in s03.locator(".scn-upload").nth(2).inner_text()
          and "אוגוסט 2026" in s03.locator("[data-testid=scn-file-label]").nth(2).inner_text())
    check("no big 'הורדת PDF' buttons left", page.locator(".hub-side >> text=הורדת PDF").count() == 0)
    s11.scroll_into_view_if_needed()
    page.screenshot(path=str(OUT / "02-scenarios.png"))
    # supplementary: the remaining Lavi payslips, labelled from the same manifest
    page.locator("[data-testid=scn-supplementary] .scn-head").click()
    supp = page.locator("[data-testid=scn-supplementary] [data-testid=scn-file-label]").all_inner_texts()
    check("supplementary files: the other Lavi payslips with Hebrew labels (one registry, no separate list)",
          len(supp) == 9 and all(t.startswith("תלוש שכר —") for t in supp) and page.locator("[data-testid=lavi-files]").count() == 0,
          f"{len(supp)} files")
    page.locator("[data-testid=scn-supplementary]").scroll_into_view_if_needed()
    page.screenshot(path=str(OUT / "03-supplementary.png"))
    # scenario selection and reset of its case
    s11.locator("[data-testid=scn-open-case-L-11]").click()
    expect(page.locator(".case-pill")).to_contain_text("438838999", timeout=15000)
    check("scenario selection: 'לפתוח את התיק מימין' opens the joint case 438838999", True)
    if os.environ.get("PRESENTER_READONLY"):                # the user's own instance: never reset a case there
        return
    s11.locator("[data-testid=scn-reset-case-L-11]").click()
    s11.locator("[data-testid=scn-reset-case-L-11-confirm]").click()
    expect(s11.locator("text=אופס")).to_be_visible(timeout=15000)
    check("the scenario's case reset still works", True)
    page.goto(f"{BASE}/customer/documents")
    expect(page.locator("[data-testid='req-PAYSLIPS:BRW-B']")).to_be_visible(timeout=15000)
    check("the joint case lists a payslip and an ID requirement for each applicant",
          all(page.locator(f"[data-testid='req-{c}']").count() == 1 for c in ("ID_CARD:BRW-A", "ID_CARD:BRW-B", "PAYSLIPS:BRW-A", "PAYSLIPS:BRW-B")))
    page.screenshot(path=str(OUT / "04-joint-case.png"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="he-IL", accept_downloads=True).new_page()
        try:
            run(page)
        except Exception as exc:
            check("check ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
            page.screenshot(path=str(OUT / "failure.png"))
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} presenter label checks passed · {BASE}"
          + (" · read-only (no reset, no upload)" if os.environ.get("PRESENTER_READONLY") else ""))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
