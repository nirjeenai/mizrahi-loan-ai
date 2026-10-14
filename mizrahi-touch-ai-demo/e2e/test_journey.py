"""Browser end-to-end journey in a real Chrome — real uploads, real Gemini reviews, real agent and
voice turns, banker decision and MCP consistency. Prints a PASS/FAIL line per acceptance check.

LEGACY (mortgage era, not yet adapted to loans): asserts the payslip-only mortgage cases and spends real Gemini
calls. Kept for reference and later adaptation; the loan journey is covered by e2e/test_loan_journey.py (REPLAY).
Never point it at :8791 (Mizrahi #2 main) or :8790 (Mizrahi #1): it uploads to cases and resets them.

Run (backend on :8791 serving the built frontend):
    backend/.venv/bin/python e2e/test_journey.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright
import demo_auth  # noqa: E402  (e2e/ is on sys.path when a suite runs as a script)

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8791")
demo_auth.install(BASE)                   # the service has no anonymous access (see demo_auth.py)
CASE, QA = "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-003"
ROOT = Path(__file__).resolve().parent
FIX = ROOT.parent / "fixtures" / "out"
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def snap(case: str = CASE) -> dict:
    return httpx.get(f"{BASE}/api/cases/{case}", timeout=30).json()


def wait_settled(case: str = CASE, timeout: int = 420) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap(case)
        if not s["readiness"]["pending_jobs"] and s["readiness"]["state"] not in ("CHECKING", "RECHECKING"):
            return s
        time.sleep(2)
    raise TimeoutError("case did not settle")


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(ART / f"e2e-{name}.png"))


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


def conversation(case: str = CASE) -> list[dict]:
    return httpx.get(f"{BASE}/api/cases/{case}/conversation", timeout=30).json()


def tools_answering(turns: list[dict], message: str) -> list[str]:
    i = next(i for i, t in enumerate(turns) if t["role"] == "user" and t["text"] == message)
    return [c["name"] for c in (turns[i + 1].get("tool_calls") or [])] if i + 1 < len(turns) else []


def ask(page: Page, text: str, timeout: int = 60000) -> str:
    stored = len(conversation())
    page.wait_for_function(f"document.querySelectorAll('.bubble[data-role]').length >= {stored}", timeout=15000)
    before = page.locator(".bubble.assistant[data-role=assistant]").count()
    page.locator("[data-testid=chat-input]").fill(text)
    page.locator("[data-testid=chat-send]").click()
    page.wait_for_function(f"document.querySelectorAll('.bubble.assistant[data-role=assistant]').length > {before}", timeout=timeout)
    return page.locator(".bubble.assistant[data-role=assistant]").last.inner_text()


def make_voice_wav() -> Path:
    aiff, wav = ART / "question.aiff", ART / "question.wav"
    subprocess.run(["say", "-v", "Carmit", "-o", str(aiff), "מה עוד חסר כדי להשלים את המסמכים?"], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(aiff), str(wav)], check=True)
    return wav


def main() -> int:
    httpx.post(f"{BASE}/api/cases/{CASE}/reset", timeout=30).raise_for_status()
    httpx.post(f"{BASE}/api/cases/{QA}/reset", timeout=30).raise_for_status()
    manifest = json.loads((FIX / "manifest.json").read_text(encoding="utf8"))["files"]
    wav = make_voice_wav()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={wav}%noloop"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 940}, locale="he-IL", permissions=["microphone"])
        page = ctx.new_page()
        page.goto(f"{BASE}/customer?voice=server")
        expect(page.locator(".ribbon")).to_contain_text("הדגמת קונספט")
        expect(page.locator("[data-testid=readiness-state]")).to_have_text("ממתינים להעלאת תלושי שכר", timeout=15000)
        check("app loads with concept label and empty AI state", True)

        # 1–3 · upload the initial set through the UI (digital + scanned), real Gemini review
        page.locator(".bottom-nav button", has_text="מסמכים").click()
        for f in [m for m in manifest if m["scene"] == "initial"]:
            upload(page, f["upload_as"], FIX / f["file"])
        s = wait_settled()
        docs = httpx.get(f"{BASE}/api/cases/{CASE}/documents").json()
        verdicts = {d["filename"]: (d["review"] or {}).get("verdict") for d in docs}
        check("six uploads reviewed through the browser", len(docs) == 6 and all(verdicts.values()), json.dumps(verdicts, ensure_ascii=False))
        scan = next(d for d in docs if "scan" in d["filename"])
        scan_facts = {f["field"]: f for f in scan["review"]["facts"]}
        check("scanned PDF processed by Gemini with re-read evidence", scan["text_layer_chars"] == 0
              and scan_facts["net_pay"]["evidence"]["witness"] == "vision_reread_confirmed"
              and float(scan_facts["net_pay"]["value_normalized"]) == 16900.0, f"net={scan_facts['net_pay']['value_raw']}")
        copy = next(d for d in docs if d["filename"] == "ido_payslip_2026-09.pdf")
        check("financial facts genuinely extracted (file named 09 prints 08)", copy["review"]["period"] == "2026-08"
              and float({f["field"]: f for f in copy["review"]["facts"]}["gross_pay"]["value_normalized"]) == 17500.0)
        keys = {f["key"].rsplit(":", 1)[0] if f["code"] != "REQUIRED_PERIOD_MISSING" and f["code"] != "DUPLICATE_PERIOD" else f["key"]
                for f in s["findings"] if f["status"] == "open"}
        check("cross-document discrepancies found", {"REQUIRED_PERIOD_MISSING:BRW-A:2026-09", "DUPLICATE_PERIOD:BRW-A:2026-08",
                                                     "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"} <= keys, ", ".join(sorted(keys)))
        page.reload()
        open_row(page, "PAYSLIPS:BRW-A")
        expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).to_contain_text("ספטמבר 2026 חסר")
        expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).to_contain_text("אוגוסט 2026 ×2")
        shot(page, "01-documents-gap")
        check("UI shows missing September and duplicate August", True)

        # 5–6 · rubric judge result with criteria and verified evidence
        page.locator("[data-testid=doc-card]", has_text="ido_payslip_2026-09.pdf").click()
        expect(page.locator("[data-testid=review-verdict]")).to_be_visible(timeout=15000)
        page.wait_for_timeout(1200)
        crit = page.locator(".crit").count()
        boxes = page.locator(".hl").count()
        rubric = copy["review"]["rubric_id"] + "@" + copy["review"]["rubric_version"]
        check("LLM-as-a-Judge verdict with rubric criteria and evidence boxes", crit == 10 and boxes >= 5,
              f"rubric={rubric} criteria={crit} boxes={boxes} judge={copy['review']['identity']['models']['judge']}")
        expect(page.locator(".screen .notice").first).to_contain_text("ספטמבר 2026")
        shot(page, "02-review-evidence")

        # 9 · unrestricted Hebrew chat grounded in live data
        page.locator(".fab").click()
        reply = ask(page, "שלום, מה עוד חסר לנו ולמה?")
        check("Gemini agent answers from live case data", "ספטמבר" in reply, reply[:140].replace("\n", " "))
        # 10 · voice turn through the same agent (fake microphone → server transcription)
        before = page.locator(".bubble.assistant[data-role=assistant]").count()
        page.locator("[data-testid=mic]").click()
        page.wait_for_timeout(4200)
        page.locator("[data-testid=mic]").click()
        page.wait_for_function(f"document.querySelectorAll('.bubble.assistant[data-role=assistant]').length > {before}", timeout=90000)
        turns = conversation()
        voice_user = [t for t in turns if t["channel"] == "voice" and t["role"] == "user"]
        voice_reply = [t for t in turns if t["channel"] == "voice" and t["role"] == "assistant"]
        check("voice interface uses the same agent and case tools", bool(voice_user and voice_reply and voice_reply[-1]["tool_calls"]),
              f"heard='{voice_user[-1]['text'] if voice_user else ''}' tools={[c['name'] for c in (voice_reply[-1]['tool_calls'] or [])] if voice_reply else []}")
        shot(page, "03-chat-voice")
        page.locator(".sheet-head button").click()

        # 7–8 · correction and real re-validation
        page.goto(f"{BASE}/customer/documents")
        upload(page, "BRW-A", FIX / "main" / "ido_payslip_2026-09_corrected.pdf")
        s2 = wait_settled()
        missing = [f for f in s2["findings"] if f["key"] == "REQUIRED_PERIOD_MISSING:BRW-A:2026-09"][0]
        dup = [f for f in s2["findings"] if f["key"] == "DUPLICATE_PERIOD:BRW-A:2026-08"][0]
        check("correction triggers re-validation and resolves the gap", missing["status"] == "resolved"
              and missing["resolution"] == "resolved_by_new_evidence" and dup["review_state"] == "INFO",
              f"history={[h['event'] for h in missing['history']]}")
        check("persisted state updated", s2["readiness"]["state"] == "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS", s2["readiness"]["state"])
        page.reload()
        expect(page.locator("[data-testid='req-PAYSLIPS:BRW-A']")).not_to_contain_text("חסר", timeout=15000)
        shot(page, "04-after-correction")

        # customer explanation is attached but never resolves; handoff to the banker
        page.locator(".fab").click()
        m1 = "לגבי הפער בהכנסה של נועה: חלק מההכנסה שלה הוא רכיב משתנה. אני מאשר שתתעדו את ההסבר הזה ותעבירו אותו לבנקאית."
        m2 = "כן, אני מאשר. תעבירו בבקשה את התיק לבנקאית."
        r1 = ask(page, m1, 90000)
        r2 = ask(page, m2, 90000)
        s3 = wait_settled()
        turns = conversation()
        t1, t2 = tools_answering(turns, m1), tools_answering(turns, m2)
        variance = [f for f in s3["findings"] if f["code"] == "DECLARED_VS_DOCUMENT_INCOME_VARIANCE"][0]
        check("customer explanation recorded without resolving the discrepancy", "record_customer_statement" in t1
              and any(st["finding_id"] == variance["finding_id"] for st in s3["statements"])
              and variance["status"] == "open" and variance["review_state"] == "NEEDS_BANKER_REVIEW",
              f"tools={t1} · {r1[:100]}".replace("\n", " "))
        queued = [h for h in s3["handoffs"] if h["status"] == "IN_BANKER_QUEUE_DEMO"]
        check("banker handoff created once by an authorized tool call", "request_banker_handoff" in t1 + t2 and len(queued) == 1,
              f"tools={t2} queued={len(queued)} · {r2[:100]}".replace("\n", " "))
        page.locator(".sheet-head button").click()

        # 13 · reload preserves state, documents and history
        page.goto(f"{BASE}/customer")
        page.reload()
        expect(page.locator("[data-testid=readiness-state]")).to_have_text("תלושי השכר הושלמו · נדרש בירור בנקאי", timeout=15000)
        turns = conversation()
        runs = httpx.get(f"{BASE}/api/cases/{CASE}/runs").json()
        check("reload preserves state, documents and review history", len(turns) >= 8 and len(runs) >= 9,
              f"turns={len(turns)} runs={len(runs)}")

        # 12 · banker evidence package and human decision
        page.goto(f"{BASE}/banker?case={CASE}")
        expect(page.locator("[data-testid=banker-readiness]")).to_be_visible(timeout=20000)
        page.locator("[data-testid=queue-group-judgment] [data-testid=queue-item]").first.click()
        expect(page.locator("[data-testid=decision-panel] .notice", has_text="הסבר הלקוח")).to_be_visible()
        page.wait_for_function("() => { const i = document.querySelector('[data-testid=evidence-viewer] img'); return i && i.naturalWidth > 0; }",
                               timeout=20000)
        shot(page, "05-banker-findings")
        page.locator("[data-testid=confirm-preparation]").click()
        page.locator("[data-testid=confirm-preparation-submit]").click()
        expect(page.locator("[data-testid=banker-readiness]")).to_have_text("הכנת מסמכי השכר אושרה", timeout=15000)
        s4 = snap()
        check("banker confirms preparation; open banker item preserved", s4["readiness"]["state"] == "PREPARATION_CONFIRMED"
              and any(f["status"] == "open" and f["review_state"] == "NEEDS_BANKER_REVIEW" for f in s4["findings"]))
        page.locator("[data-testid=queue-group-decide] [data-testid=queue-item]").first.click()
        page.wait_for_function("() => { const i = document.querySelector('[data-testid=evidence-viewer] img'); return i && i.naturalWidth > 0; }",
                               timeout=20000)
        page.wait_for_timeout(400)
        shot(page, "06-banker-evidence")

        # 11 · MCP returns the same results as the application
        page.goto(f"{BASE}/system")
        page.locator("[data-testid=mcp-selftest]").click()
        expect(page.locator("[data-testid=mcp-consistent]")).to_have_text("תואם לאפליקציה", timeout=30000)
        check("MCP tools return the same results as the app; cross-case access denied", True)
        shot(page, "07-system-mcp")

        # 14 · negative documents never produce false approvals (QA case, uploaded through the UI)
        page.goto(f"{BASE}/customer")
        page.evaluate(f"localStorage.setItem('mz.case', '{QA}')")
        page.goto(f"{BASE}/customer/documents")
        for f in [m for m in manifest if m["scene"] == "negative"]:
            upload(page, f["upload_as"], FIX / f["file"])
        wait_settled(QA)
        neg = httpx.get(f"{BASE}/api/cases/{QA}/documents").json()
        nv = {d["filename"]: (d["review"] or {}).get("verdict") for d in neg}
        check("unreadable / contradictory / wrong-borrower / injection: no false approval",
              len(nv) == 4 and all(v in ("INVALID", "NEEDS_REVIEW") for v in nv.values()), json.dumps(nv, ensure_ascii=False))
        page.reload()
        page.wait_for_timeout(1500)
        shot(page, "08-negative-qa")
        page.evaluate(f"localStorage.setItem('mz.case', '{CASE}')")
        browser.close()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    (ART / "e2e-results.json").write_text(json.dumps([{"check": n, "pass": ok, "detail": d} for n, ok, d in RESULTS],
                                                     ensure_ascii=False, indent=2), encoding="utf8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
