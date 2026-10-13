"""Chat-to-action navigation, end to end in a real Chrome on a mobile viewport: real agent turns,
real uploads through the existing upload sheet, real Gemini reviews, the follow-up in the same
conversation, stale actions, a voice request, and refusals for another case.

Run (backend serving the built frontend; E2E_BASE defaults to :8790):
    backend/.venv/bin/python e2e/test_chat_actions.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Locator, Page, expect, sync_playwright
import demo_auth  # noqa: E402  (e2e/ is on sys.path when a suite runs as a script)

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8790")
demo_auth.install(BASE)                   # the service has no anonymous access (see demo_auth.py)
CASE, QA = "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-003"
ROOT = Path(__file__).resolve().parent
FIX = ROOT.parent / "fixtures" / "out"
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)
RESULTS: list[tuple[str, bool, str]] = []
MISSING = "מה חסר כדי להתקדם?"
VOICE_PHRASE = "תעביר אותי להעלאת התלוש של נועה"


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def get(path: str):
    return httpx.get(f"{BASE}{path}", timeout=30).json()


def resolve(case: str, action_id: str, turn_id: str | None) -> httpx.Response:
    return httpx.post(f"{BASE}/api/cases/{case}/actions/resolve", json={"action_id": action_id, "turn_id": turn_id}, timeout=30)


def conversation(case: str = CASE) -> list[dict]:
    return get(f"/api/cases/{case}/conversation")


def shot(page: Page, name: str) -> None:
    page.wait_for_timeout(400)
    page.screenshot(path=str(ART / f"actions-{name}.png"), animations="disabled")


def reply_to(text: str, channel: str, timeout: float = 150) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        turns = conversation()
        asked = [i for i, t in enumerate(turns) if t["role"] == "user" and t["channel"] == channel and (not text or t["text"] == text)]
        if asked:
            answer = next((t for t in turns[asked[-1] + 1:] if t["role"] == "assistant" and t["channel"] == channel), None)
            if answer:
                return answer
        time.sleep(1)
    raise TimeoutError(f"no {channel} reply to {text!r}")


def ask(page: Page, text: str) -> tuple[dict, Locator]:
    page.locator("[data-testid=chat-input]").fill(text)
    page.locator("[data-testid=chat-send]").click()
    turn = reply_to(text, "text")
    bubble = page.locator(f".bubble[data-turn-id='{turn['turn_id']}']")
    bubble.wait_for(timeout=20000)
    return turn, bubble


def open_chat(page: Page) -> None:
    page.locator("[data-testid=fab]").click()
    page.wait_for_selector("[data-testid=chat-log]")
    page.wait_for_timeout(600)


def close_chat(page: Page) -> None:
    page.locator(".sheet-head button").click()
    page.wait_for_selector("[data-testid=chat-log]", state="detached")


def upload_in_sheet(page: Page, path: Path, period: str | None = None) -> None:
    if period:
        chip = page.locator(f"[data-testid=upload-months] [data-period='{period}']")
        if chip.get_attribute("aria-checked") != "true":
            chip.click()
    page.locator("[data-testid=file-input]").set_input_files(str(path))
    page.locator("[data-testid=upload-submit]").click()
    page.wait_for_selector("[data-testid=upload-stages]", timeout=20000)


def outcome_text(page: Page) -> str:
    page.wait_for_selector("[data-testid=upload-outcome]", timeout=420000)
    return page.locator("[data-testid=upload-outcome] .outcome-msg").inner_text()


def wait_settled(case: str = CASE, timeout: int = 420) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = get(f"/api/cases/{case}")
        if not s["readiness"]["pending_jobs"] and s["readiness"]["state"] not in ("CHECKING", "RECHECKING"):
            return s
        time.sleep(2)
    raise TimeoutError("case did not settle")


def requirement(snap: dict, code: str) -> dict:
    return next(r for r in snap["readiness"]["requirements"] if r["code"] == code)


def make_voice_wav() -> Path:
    aiff, wav = ART / "voice_nav.aiff", ART / "voice_nav.wav"
    subprocess.run(["say", "-v", "Carmit", "-o", str(aiff), VOICE_PHRASE], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(aiff), str(wav)], check=True)
    return wav


def main() -> int:
    for case in (CASE, QA):
        httpx.post(f"{BASE}/api/cases/{case}/reset", timeout=30).raise_for_status()
    with (FIX / "negative" / "ido_payslip_unreadable.pdf").open("rb") as fh:
        foreign_doc = httpx.post(f"{BASE}/api/cases/{QA}/documents", files={"file": ("qa_doc.pdf", fh, "application/pdf")},
                                 data={"borrower_id": "BRW-A"}, timeout=60).json()["document"]["document_id"]
    calls_before = get("/api/system/llm")["calls"]
    wav = make_voice_wav()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={wav}%noloop"])
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                  locale="he-IL", permissions=["microphone"])
        page = ctx.new_page()
        page.goto(f"{BASE}/customer")
        page.evaluate(f"localStorage.setItem('mz.case', '{CASE}')")
        page.goto(f"{BASE}/customer?voice=server")
        expect(page.locator("[data-testid=fab]")).to_be_visible(timeout=20000)
        rtl = page.evaluate("document.documentElement.dir")

        # 1–2 · a fresh case: the assistant reads the real requirements and offers structured actions
        open_chat(page)
        first, bubble = ask(page, MISSING)
        tools_used = [c["name"] for c in first["tool_calls"] or []]
        offered = {a["action_id"]: a for a in first["actions"]}
        snap = get(f"/api/cases/{CASE}")
        available = {a["action_id"]: a for a in snap["available_actions"]}
        check("assistant retrieves the real requirements before answering",
              bool({"get_case_overview", "get_upload_guidance", "list_open_items"} & set(tools_used)) and "offer_app_actions" in tools_used,
              f"tools={tools_used}")
        check("offered actions are backend-derived for both borrowers",
              {"upload:PAYSLIPS:BRW-A", "upload:PAYSLIPS:BRW-B"} <= set(offered) and all(offered[k] == available[k] for k in offered)
              and offered["upload:PAYSLIPS:BRW-B"]["params"]["missing_periods"] == ["2026-07", "2026-08", "2026-09"],
              ", ".join(offered))
        buttons = bubble.locator(".act-btn")
        check("actions render as buttons under the answer, most important first",
              buttons.count() == len(offered) and "primary" in (buttons.first.get_attribute("class") or "")
              and bubble.locator(".act-btn", has_text="העלאת תלושים לנועה").count() == 1
              and bubble.locator(".bubble-sources").count() == 1 and bubble.locator(".tool-chip").count() == 0,
              f"reply ({len(first['text'])} chars): {first['text'][:160]}".replace("\n", " "))
        check("mobile layout is RTL", rtl == "rtl" and page.locator(".act-btn").first.evaluate("e => getComputedStyle(e).direction") == "rtl")
        shot(page, "01-chat-actions")

        # 3–5 · the action opens the existing Documents screen and upload sheet with Noa and Payslip preselected
        bubble.locator(".act-btn", has_text="העלאת תלושים לנועה").click()
        page.wait_for_selector("[data-testid=upload-sheet]", timeout=15000)
        months = page.locator("[data-testid=upload-months] .mchip")
        check("navigates to the Documents screen and focuses Noa's payslips",
              page.url.endswith("/customer/documents") and page.locator("[data-testid='req-PAYSLIPS:BRW-B']").get_attribute("data-focused") == "true",
              page.url)
        check("Noa and Payslip preselected; several missing months are listed but none is chosen",
              page.locator("input[name=borrower][value=BRW-B]").is_checked()
              and page.locator("[data-testid=upload-doc-type]").get_attribute("data-requirement") == "PAYSLIPS:BRW-B"
              and months.count() == 3 and page.locator("[data-testid=upload-months] [aria-checked=true]").count() == 0
              and "חסרים 3 חודשים" in page.locator("[data-testid=upload-month-hint]").inner_text(),
              page.locator("[data-testid=upload-month-hint]").inner_text())
        shot(page, "02-upload-preselected-noa")

        # 6–8 · a real synthetic PDF through the existing workflow; Gemini reviews it; the case is re-checked
        upload_in_sheet(page, FIX / "main" / "noa_payslip_2026-09.pdf", period="2026-09")
        page.wait_for_timeout(2500)
        shot(page, "03-processing")
        noa_text = outcome_text(page)
        snap = get(f"/api/cases/{CASE}")
        docs = get(f"/api/cases/{CASE}/documents")
        noa_doc = next(d for d in docs if d["filename"] == "noa_payslip_2026-09.pdf")
        review = noa_doc["review"] or {}
        check("Gemini reviewed the uploaded document", review.get("identity", {}).get("provider", "").startswith("gemini")
              and review.get("usage", {}).get("llm_calls", 0) > 0 and review.get("period") == "2026-09",
              f"verdict={review.get('verdict')} models={review.get('identity', {}).get('models')} run={review.get('run_id')}")
        noa_req = requirement(snap, "PAYSLIPS:BRW-B")
        check("case state reflects the review", "2026-09" in noa_req["covered"] and noa_req["missing"] == ["2026-07", "2026-08"],
              f"covered={noa_req['covered']} missing={noa_req['missing']}")
        check("outcome is stated only after the real review, from case data",
              noa_text.startswith("התלוש של נועה לספטמבר 2026 התקבל ונבדק") and "נותרו להעלות" in noa_text, noa_text)
        shot(page, "04-upload-outcome")

        # 9 · back to the same conversation: history intact, one follow-up from the case, old actions refreshed
        page.locator("[data-testid=upload-back-to-chat]").click()
        page.wait_for_selector("[data-testid=chat-log]")
        follow = page.locator(".bubble[data-channel=app]").last
        follow.wait_for(timeout=20000)
        follow_turn = [t for t in conversation() if t["channel"] == "app"][-1]
        old_noa = page.locator(f".bubble[data-turn-id='{first['turn_id']}'] [data-action-id='upload:PAYSLIPS:BRW-B']")
        check("returning to chat keeps the history and adds the real outcome",
              page.locator(f".bubble[data-turn-id='{first['turn_id']}']").count() == 1 and "התלוש של נועה" in follow.inner_text()
              and {"upload:PAYSLIPS:BRW-A", "upload:PAYSLIPS:BRW-B"} <= {a["action_id"] for a in follow_turn["actions"]},
              follow_turn["text"])
        check("an earlier action still needed is refreshed, not duplicated",
              old_noa.get_attribute("data-stale") is None and "יולי ואוגוסט 2026" in old_noa.inner_text(), old_noa.inner_text().replace("\n", " "))
        check("only the latest answer's next step is emphasized",
              page.locator(f".bubble[data-turn-id='{first['turn_id']}'] .act-btn.primary").count() == 0
              and follow.locator(".act-btn.primary").count() == 1)
        shot(page, "05-chat-after-upload")

        # 10 · Ido: two months through the same flow, then a single missing month that is preselected
        follow.locator(".act-btn", has_text="לעידו").click()
        page.wait_for_selector("[data-testid=upload-sheet]")
        check("Ido preselected from the follow-up action", page.locator("input[name=borrower][value=BRW-A]").is_checked())
        upload_in_sheet(page, FIX / "main" / "ido_payslip_2026-07.pdf", period="2026-07")
        outcome_text(page)
        page.locator("[data-testid=upload-sheet] button", has_text="העלאת מסמך נוסף").click()
        upload_in_sheet(page, FIX / "main" / "ido_payslip_2026-08.pdf", period="2026-08")
        outcome_text(page)
        page.locator("[data-testid=upload-back-to-chat]").click()
        page.wait_for_selector("[data-testid=chat-log]")
        page.wait_for_timeout(1500)
        follow_two = [t for t in conversation() if t["channel"] == "app"][-1]
        check("both uploads summarised in one follow-up", follow_two["turn_id"] != follow_turn["turn_id"]
              and "ליולי 2026" in follow_two["text"] and "לאוגוסט 2026" in follow_two["text"], follow_two["text"])
        second, bubble2 = ask(page, MISSING)
        ido_action = next((a for a in second["actions"] if a["action_id"] == "upload:PAYSLIPS:BRW-A"), None)
        check("a single missing month becomes a specific action", bool(ido_action) and ido_action["params"]["period"] == "2026-09"
              and ido_action["label_he"] == "העלאת תלוש ספטמבר לעידו", json.dumps(ido_action, ensure_ascii=False)[:220])
        bubble2.locator("[data-action-id='upload:PAYSLIPS:BRW-A']").click()
        page.wait_for_selector("[data-testid=upload-sheet]")
        check("the missing month is preselected", page.locator("input[name=borrower][value=BRW-A]").is_checked()
              and page.locator("[data-testid=upload-months] .mchip").count() == 1
              and page.locator("[data-testid=upload-months] [data-period='2026-09']").get_attribute("aria-checked") == "true")
        shot(page, "06-upload-preselected-month")

        # a mismatched file: the outcome states the real finding and keeps the right next action
        upload_in_sheet(page, FIX / "main" / "ido_payslip_2026-09.pdf")
        mismatch = outcome_text(page)
        mismatch_actions = page.locator("[data-testid=upload-outcome-actions] .act-btn")
        check("a mismatched month is reported with the next action",
              "מודפס בו אוגוסט 2026, ולא ספטמבר 2026 כפי שבחרתם" in mismatch and "עידו — ספטמבר 2026" in mismatch
              and page.locator("[data-testid=upload-outcome-actions] [data-action-id='upload:PAYSLIPS:BRW-A']").count() == 1,
              f"{mismatch} · actions={mismatch_actions.all_inner_texts()}".replace("\n", " "))
        shot(page, "07-mismatch-outcome")
        page.locator("[data-testid=upload-outcome-actions] [data-action-id='upload:PAYSLIPS:BRW-A']").click()
        page.wait_for_selector("[data-testid=upload-months] [data-period='2026-09'][aria-checked=true]")
        upload_in_sheet(page, FIX / "main" / "ido_payslip_2026-09_corrected.pdf")
        fixed = outcome_text(page)
        check("the corrected payslip closes Ido's gap", fixed.startswith("התלוש של עידו לספטמבר 2026 התקבל ונבדק — נמצא תקין")
              and "עידו" not in fixed.split("נותרו להעלות")[-1], fixed)

        # 12 · stale actions: the earlier "September for Ido" is disabled and refused by the server
        page.locator("[data-testid=upload-back-to-chat]").click()
        page.wait_for_selector("[data-testid=chat-log]")
        stale = page.locator(f".bubble[data-turn-id='{second['turn_id']}'] [data-action-id='upload:PAYSLIPS:BRW-A']")
        stale.wait_for()
        expect(stale).to_have_attribute("data-stale", "true", timeout=15000)
        refused = resolve(CASE, "upload:PAYSLIPS:BRW-A", second["turn_id"])
        check("stale actions are disabled in the chat and refused by the server", stale.is_disabled() and refused.status_code == 409,
              f"{stale.inner_text()} · HTTP {refused.status_code} {refused.json().get('detail')}".replace("\n", " "))
        shot(page, "08-stale-actions")

        # 7 · voice: the same agent resolves the same structured action; the app does not navigate by itself
        url_before = page.url
        page.locator("[data-testid=mic]").click()
        page.wait_for_timeout(4500)
        page.locator("[data-testid=mic]").click()
        voice_turn = reply_to("", "voice", 150)
        voice_user = [t for t in conversation() if t["channel"] == "voice" and t["role"] == "user"]
        page.locator(f".bubble[data-turn-id='{voice_turn['turn_id']}'] [data-action-id='upload:PAYSLIPS:BRW-B']").wait_for(timeout=20000)
        check("a spoken request becomes the same visible action, without navigating",
              len(voice_user) > 0 and any(a["action_id"] == "upload:PAYSLIPS:BRW-B" for a in voice_turn["actions"])
              and page.url == url_before and page.locator("[data-testid=upload-sheet]").count() == 0,
              f"heard='{voice_user[-1]['text'] if voice_user else ''}' reply='{voice_turn['text'][:120]}'".replace("\n", " "))
        shot(page, "09-voice-action")

        # 11 · another case: refused by the server, by the deep link and by the document page
        foreign = resolve(QA, "upload:PAYSLIPS:BRW-B", first["turn_id"])
        close_chat(page)
        page.goto(f"{BASE}/customer/documents?case={QA}&upload=PAYSLIPS:BRW-A")
        expect(page.locator("[data-testid=link-note]")).to_contain_text("תיק אחר", timeout=15000)
        no_sheet = page.locator("[data-testid=upload-sheet]").count() == 0
        shot(page, "10-foreign-link")
        page.goto(f"{BASE}/customer/documents/{foreign_doc}")
        expect(page.locator("[data-testid=foreign-document]")).to_be_visible(timeout=15000)
        check("navigation cannot target a different case", foreign.status_code == 403 and no_sheet,
              f"resolve HTTP {foreign.status_code} · deep link blocked · foreign document hidden")

        # closed and reopened chat, then a full reload: the same conversation and its live actions
        page.goto(f"{BASE}/customer")
        open_chat(page)
        count_open = page.locator(".bubble[data-turn-id]").count()
        close_chat(page)
        page.reload()
        open_chat(page)
        count_reload = page.locator(".bubble[data-turn-id]").count()
        stored = len(conversation())
        check("chat survives close, reopen and reload with actions intact", count_open == count_reload == stored
              and page.locator(f".bubble[data-turn-id='{voice_turn['turn_id']}'] [data-action-id='upload:PAYSLIPS:BRW-B']").count() == 1,
              f"turns={stored}")
        shot(page, "11-chat-reopened")

        desk = browser.new_page(viewport={"width": 1366, "height": 940}, locale="he-IL")
        desk.goto(f"{BASE}/customer")
        desk.locator("[data-testid=fab]").click()
        desk.wait_for_selector(".bubble[data-turn-id]")
        desk.wait_for_timeout(1200)
        desk.screenshot(path=str(ART / "actions-12-desktop-chat.png"), animations="disabled")
        browser.close()

    calls = get("/api/system/llm")["calls"] - calls_before
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed · {calls} Gemini calls")
    (ART / "actions-results.json").write_text(json.dumps({"base": BASE, "gemini_calls": calls, "checks": [
        {"check": n, "pass": ok, "detail": d} for n, ok, d in RESULTS]}, ensure_ascii=False, indent=2), encoding="utf8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
