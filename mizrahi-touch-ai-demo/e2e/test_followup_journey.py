"""Round 5 — the integrated loan-completion journey in a real Chrome: document review → follow-up engine → simulated
JEEN Talk → secure completion link → corrected upload → task resolved → banker view. Isolated REPLAY stack: zero
Gemini calls, no real call (mock-talk never dials). Resets cases 003, 005, 006, 007, 008, 009 and 010 and the demo
clock.

    # from backend/
    .venv/bin/python ../e2e/replay_backend.py --port 8799 --data ../e2e/artifacts/closeout/data-g5
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/closeout/web 5847 http://127.0.0.1:8799
    FOLLOWUP_E2E_BASE=http://127.0.0.1:5847 backend/.venv/bin/python e2e/test_followup_journey.py

Journeys: A valid package (no follow-up) · B missing document (presence, grace, simulated call, link, completion,
no second contact) · C wrong document (finding, call, link to the replacement, resolution) · D joint application
(one applicant's payslip never satisfies the other's) · F safety (active customer, upload in flight, call window,
kill switch, banker pause, no consent). Admin policy editing (E) is covered by e2e/test_admin_ui.py and
e2e/check_policy_acceptance.py on the same stack."""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("FOLLOWUP_E2E_BASE", "http://127.0.0.1:5847")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
ROOT = Path(__file__).resolve().parent
FIX = ROOT.parent / "fixtures" / "presenter"
SHOTS = ROOT / "artifacts" / "closeout" / "journeys"
IL = ZoneInfo("Asia/Jerusalem")
ID, PAY, PAY_B, BANK, PURPOSE = "ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "PAYSLIPS:BRW-B", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"
F = {"id": "loan_set/id_card_ido.pdf", "jul": "golden_set/01_INITIAL_UPLOADS/ido_2026_07.pdf",
     "aug": "golden_set/01_INITIAL_UPLOADS/ido_2026_08.pdf", "sep": "golden_set/02_CORRECTION/ido_2026_09_CORRECTED.pdf",
     "st": "loan_set/statement_ido_2026-07_09.pdf", "q": "loan_set/car_quote_ido.pdf", "lavi_jul": "../out/main/ido_payslip_2026-07.pdf"}
OPEN = lambda t: t["status"] not in ("RESOLVED", "CANCELED")   # noqa: E731
RESULTS: list[tuple[str, bool, str]] = []
api = httpx.Client(base_url=BASE, timeout=60)


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / f"{name}.png"))


# ---------------------------------------------------------------- API helpers (checks and setup only)
def staff() -> None:
    api.post("/api/session/demo/staff", json={"staff_id": "STAFF-DANA"}).raise_for_status()


def customer(case: str) -> None:
    api.post("/api/session/demo/customer", json={"case_id": case}).raise_for_status()


def reset(case: str) -> None:
    customer(case)
    api.post(f"/api/cases/{case}/reset").raise_for_status()


def clock(**body) -> datetime:
    staff()
    return datetime.fromisoformat(api.post("/api/demo/clock", json=body).json()["now"])


def tick() -> None:
    staff()
    api.post("/api/demo/tick").raise_for_status()


def view(case: str) -> dict:
    staff()
    return api.get(f"/api/banker/cases/{case}/followup").json()


def settle(case: str, timeout: float = 120) -> dict:
    customer(case)
    end = time.time() + timeout
    while time.time() < end:
        s = api.get(f"/api/cases/{case}").json()
        if not s["readiness"]["pending_jobs"] and s["readiness"]["counts"]["processing"] == 0:
            return s
        time.sleep(0.5)
    raise TimeoutError(case)


def seed(case: str, *items: tuple[str, str, str | None]) -> None:
    """Setup through the same upload endpoint the app uses (the journeys' own steps go through the browser)."""
    customer(case)
    for key, code, period in items:
        p = FIX / F[key]
        who = code.split(":")[1] if ":" in code and code.split(":")[1].startswith("BRW") else "BRW-A"
        data = {"requirement_code": code, **({"borrower_id": who} if code != PURPOSE else {}),
                **({"expected_period": period} if period else {})}
        with p.open("rb") as fh:
            api.post(f"/api/cases/{case}/documents", data=data, files={"file": (p.name, fh, "application/pdf")}).raise_for_status()
    settle(case)


def wait_plan(case: str, states: tuple[str, ...], timeout: float = 90) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        v = view(case)
        if v["plan"]["state"] in states:
            return v
        time.sleep(1)
    return view(case)


def minutes_until(v: dict, now: datetime) -> float | None:
    nxt = (v.get("decision") or {}).get("next_eligible_at")
    return (datetime.fromisoformat(nxt) - now).total_seconds() / 60 if nxt else None


# ---------------------------------------------------------------- browser helpers
def open_case(page: Page, case: str, path: str = "/customer") -> None:
    page.goto(f"{BASE}/customer")
    page.evaluate(f"localStorage.setItem('mz.case', '{case}')")
    page.goto(f"{BASE}{path}")
    expect(page.locator(".case-pill")).not_to_contain_text("טוען", timeout=20000)


def upload_ui(page: Page, code: str, key: str, period: str | None = None) -> str:
    page.goto(f"{BASE}/customer/documents")
    row = page.locator(f"[data-testid='req-{code}']")
    expect(row).to_be_visible(timeout=15000)
    head = row.locator(".dl-head")
    if head.get_attribute("aria-expanded") != "true":
        head.click()
    who = code.split(":")[1] if code.startswith("PAYSLIPS") else None
    button = row.locator(f"[data-testid=upload-{who}]") if who else row.locator(f"[data-testid='upload-{code}']")
    button.first.click()
    return submit_in_sheet(page, key, period)


def submit_in_sheet(page: Page, key: str, period: str | None = None) -> str:
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible(timeout=15000)
    if period:
        chip = sheet.locator(f".mchip[data-period='{period}']")
        if chip.count() and chip.get_attribute("aria-checked") != "true":
            chip.click()
    sheet.locator("[data-testid=file-input]").set_input_files(str((FIX / F[key]).resolve()))
    sheet.locator("[data-testid=upload-submit]").click()
    expect(sheet.locator("[data-testid=upload-outcome]")).to_be_visible(timeout=90000)
    message = sheet.locator(".outcome-msg").inner_text()
    sheet.locator("button[aria-label='סגירה']").click()
    return message


def sim(page: Page, testid: str) -> str:
    if page.locator(".hub").get_attribute("data-presenter") != "open":     # the presenter starts collapsed on each load
        page.locator("[data-testid=presenter-toggle]").click()
    box = page.locator("[data-testid=followup-sim]")
    if box.get_attribute("open") is None:
        box.locator("summary").click()
    page.locator(f"[data-testid={testid}]").click()
    line = page.locator("[data-testid=sim-line]")
    expect(line).to_be_visible(timeout=15000)
    page.wait_for_timeout(800)
    return line.inner_text()


# ---------------------------------------------------------------- journeys
def journey_a(page: Page, banker: Page) -> None:
    case = "DEMO-MTZ-2026-006"
    reset(case)
    clock(reset=True)
    open_case(page, case, "/customer/documents")
    for code, key, period in ((ID, "id", None), (PAY, "jul", "2026-07"), (PAY, "aug", "2026-08"), (PAY, "sep", "2026-09"),
                              (BANK, "st", None), (PURPOSE, "q", None)):
        upload_ui(page, code, key, period)
    settle(case)
    clock(advance_minutes=120)
    tick()
    v = view(case)
    check("A · valid package: no open completion task and no contact, even two hours later",
          not [t for t in v["tasks"] if OPEN(t)] and not v["attempts"], v["plan"]["state"])
    check("A · case status: ready for the banker", v["case_status"] == "READY_FOR_BANKER", v["case_status"])
    clock(reset=True)
    banker.goto(f"{BASE}/banker?case={case}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    banker.locator("[data-item-id^='doc:']").first.click()
    expect(banker.locator("[data-testid=evidence-viewer] .hl").first).to_be_visible(timeout=20000)
    check("A · the banker inspects the evidence on the original page", banker.locator("[data-testid=evidence-viewer] .hl").count() > 0)
    shot(banker, "A-banker-evidence")


def journey_b(page: Page, banker: Page) -> None:
    case = "DEMO-MTZ-2026-009"
    reset(case)
    clock(reset=True)
    open_case(page, case, "/customer/documents")
    for code, key, period in ((ID, "id", None), (PAY, "jul", "2026-07"), (PAY, "aug", "2026-08"), (BANK, "st", None), (PURPOSE, "q", None)):
        upload_ui(page, code, key, period)
    settle(case)
    page.goto(f"{BASE}/customer/documents")
    page.wait_for_timeout(1500)
    tick()
    v = view(case)
    open_tasks = [t for t in v["tasks"] if OPEN(t)]
    check("B · one outstanding task: the missing September payslip",
          [(t["requirement_code"], t["reason_code"]) for t in open_tasks] == [(PAY, "REQUIRED_PERIOD_MISSING")],
          str([(t["requirement_code"], t["reason_code"], t["status"]) for t in v["tasks"]]))
    d = v["decision"] or {}
    check("B · presence protection: the customer is on the documents screen, so no contact",
          not v["attempts"] and (d.get("action") in ("IN_APP_ONLY", "IN_APP_NUDGE", "SUPPRESS") or "HG-ACTIVE-SESSION" in d.get("blocked_by", [])),
          f"{d.get('action')} {d.get('blocked_by')}")
    page.goto(f"{BASE}/customer")
    line = sim(page, "sim-customer-left")
    now = clock()
    v = view(case)
    mins = minutes_until(v, now)
    check("B · the customer leaves → the engine waits the 20-minute grace period", v["decision"]["action"] == "WAIT"
          and mins is not None and 19 <= mins <= 21 and "המתנה" in line, f"{v['decision']['action']} · {mins} min")
    sim(page, "sim-clock-20")
    v = wait_plan(case, ("DISPATCHING", "IN_CALL", "AWAITING_CUSTOMER"))
    a = v["attempts"][0] if v["attempts"] else {}
    check("B · after the grace period one simulated JEEN Talk call is placed (mock-talk, never dials)",
          len(v["attempts"]) == 1 and a.get("simulated") is True and a.get("provider") == "mock-talk", f"{v['plan']['state']} · {a.get('status')}")
    page.goto(f"{BASE}/customer")
    notice = page.locator("[data-testid=followup-notice]")
    expect(notice).to_be_visible(timeout=15000)
    check("B · the customer's home says the bank is calling (the attempt above is recorded as simulated)",
          any(t in notice.inner_text() for t in ("מתקשרים אליכם", "בשיחה איתכם")), notice.inner_text()[:80])
    shot(page, "B-customer-call-notice")
    sim(page, "sim-outcome-LINK_SENT")
    v = wait_plan(case, ("AWAITING_CUSTOMER",))
    check("B · the call ends with a secure completion link; the plan waits for the customer",
          v["plan"]["state"] == "AWAITING_CUSTOMER" and v["attempts"][0]["outcome"] == "LINK_SENT" and bool(v["attempts"][0]["link_id"]))
    link = page.locator("[data-testid=sim-open-link]")
    expect(link).to_be_visible(timeout=10000)
    link.click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible(timeout=20000)
    check("B · the link opens the September payslip upload in the app",
          sheet.locator("[data-testid=upload-doc-type]").get_attribute("data-requirement") == PAY, page.url)
    shot(page, "B-link-upload")
    msg = submit_in_sheet(page, "sep", "2026-09")
    settle(case)
    v = wait_plan(case, ("COMPLETED",), 60)
    task = next(t for t in v["tasks"] if t["reason_code"] == "REQUIRED_PERIOD_MISSING")
    check("B · the corrected payslip passes review: task resolved, follow-up completed, ready for the banker",
          task["status"] == "RESOLVED" and v["plan"]["state"] == "COMPLETED" and v["case_status"] == "READY_FOR_BANKER", msg[:80])
    clock(advance_minutes=2880)
    tick()
    tick()
    check("B · no second contact after completion (two days later, repeated ticks)", len(view(case)["attempts"]) == 1)
    clock(reset=True)
    banker.goto(f"{BASE}/banker?case={case}&view=followup")
    expect(banker.locator("[data-testid=followup-view]")).to_be_visible(timeout=20000)
    expect(banker.locator("[data-testid=fu-plan-state]")).to_have_attribute("data-state", "COMPLETED", timeout=15000)
    tl = banker.locator("[data-testid=fu-timeline]").inner_text()
    check("B · the banker sees what was missing, the simulated call, its link and the resolution in the timeline",
          "נשלח קישור" in banker.locator("[data-testid=fu-attempts]").inner_text() and "דרישת השלמה נסגרה" in tl and "שיחה תוזמנה" in tl)
    shot(banker, "B-banker-followup")
    banker.goto(f"{BASE}/banker?case={case}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    customer(case)
    sep = next(d["document_id"] for d in api.get(f"/api/cases/{case}/documents").json() if d["filename"] == "ido_2026_09_CORRECTED.pdf")
    banker.locator(f"[data-item-id='doc:{sep}']").click()
    expect(banker.locator("[data-testid=evidence-viewer] .hl").first).to_be_visible(timeout=20000)
    check("B · the banker opens the September payslip's evidence", banker.locator("[data-testid=evidence-viewer] .hl").count() > 0)


def journey_c(page: Page) -> None:
    case = "DEMO-MTZ-2026-008"
    reset(case)
    clock(reset=True)
    seed(case, ("jul", PAY, "2026-07"), ("aug", PAY, "2026-08"), ("sep", PAY, "2026-09"), ("st", BANK, None), ("q", PURPOSE, None))
    open_case(page, case, "/customer/documents")
    upload_ui(page, ID, "jul")                              # the July payslip, deliberately in the ID-card slot
    s = settle(case)
    f = next((x for x in s["findings"] if x["status"] == "open" and x["code"] == "UNEXPECTED_DOCUMENT_TYPE"), None)
    v = view(case)
    open_tasks = [t for t in v["tasks"] if OPEN(t)]
    check("C · evidence-backed finding on the wrong document, and one open task: the ID card",
          f is not None and bool(f["document_id"]) and [(t["requirement_code"], t["reason_code"]) for t in open_tasks]
          == [(ID, "UNEXPECTED_DOCUMENT_TYPE")], str([(t["requirement_code"], t["reason_code"], t["status"]) for t in v["tasks"]]))
    page.goto(f"{BASE}/customer")
    sim(page, "sim-customer-left")
    sim(page, "sim-clock-20")
    v = wait_plan(case, ("DISPATCHING", "IN_CALL", "AWAITING_CUSTOMER"))
    check("C · after the grace period: one simulated call", len(v["attempts"]) == 1)
    sim(page, "sim-outcome-LINK_SENT")
    page.locator("[data-testid=sim-open-link]").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible(timeout=20000)
    check("C · the link opens the ID-card upload that replaces the wrong file",
          sheet.locator("[data-testid=upload-doc-type]").get_attribute("data-requirement") == ID
          and sheet.locator("[data-testid=upload-replaces]").count() == 1)
    submit_in_sheet(page, "id")
    settle(case)
    v = wait_plan(case, ("COMPLETED",), 60)
    s = settle(case)
    customer(case)
    wrong = next(d["document_id"] for d in api.get(f"/api/cases/{case}/documents").json()
                 if d["filename"] == "ido_2026_07.pdf" and d["requirement_code"] == ID)
    task = next(t for t in v["tasks"] if t["reason_code"] == "UNEXPECTED_DOCUMENT_TYPE")
    check("C · replacement reviewed: wrong file replaced, task resolved, follow-up completed",
          s["document_status"].get(wrong, {}).get("status") == "REPLACED" and task["status"] == "RESOLVED"
          and v["plan"]["state"] == "COMPLETED", f"{s['document_status'].get(wrong, {}).get('status')} · {task['status']} · {v['plan']['state']}")
    tick()
    check("C · no second contact", len(view(case)["attempts"]) == 1)
    clock(reset=True)


def journey_d(page: Page) -> None:
    case = "DEMO-MTZ-2026-003"
    reset(case)
    open_case(page, case, "/customer/documents")
    upload_ui(page, PAY_B, "lavi_jul", "2026-07")            # Ido Lavi's payslip, uploaded under Noa
    s = settle(case)
    req = {r["code"]: r for r in s["readiness"]["requirements"]}
    f = next((x for x in s["findings"] if x["status"] == "open" and x["code"] == "BORROWER_MISMATCH"), None)
    check("D · one applicant's payslip never satisfies the other's: identity mismatch, Noa's months stay missing",
          f is not None and f.get("borrower_id") == "BRW-B" and len(req[PAY_B]["missing"]) == 3
          and len(req[PAY]["missing"]) == 3, f"{(f or {}).get('code')} · Noa missing {req[PAY_B]['missing']}")
    check("D · one shared statement requirement for the joint account (both holders)",
          [r["code"] for r in s["readiness"]["requirements"] if r["family"] == "bank_statement"] == [BANK]
          and req[BANK].get("holders") == ["BRW-A", "BRW-B"])
    shot(page, "D-joint-documents")


def journey_f(page: Page, banker: Page) -> None:
    case = "DEMO-MTZ-2026-005"
    reset(case)
    clock(reset=True)
    seed(case, ("id", ID, None), ("jul", PAY, "2026-07"), ("aug", PAY, "2026-08"), ("st", BANK, None), ("q", PURPOSE, None))
    open_case(page, case, "/customer/documents")
    page.wait_for_timeout(1500)
    tick()
    d = view(case)["decision"] or {}
    check("F · active customer on the task screen: no contact", not view(case)["attempts"]
          and (d.get("action") in ("IN_APP_ONLY", "IN_APP_NUDGE", "SUPPRESS") or "HG-ACTIVE-SESSION" in d.get("blocked_by", [])), d.get("action"))
    row = page.locator(f"[data-testid='req-{PAY}'] .dl-head")
    if row.get_attribute("aria-expanded") != "true":
        row.click()
    page.locator("[data-testid=upload-BRW-A]").first.click()
    with page.expect_file_chooser():
        page.locator("[data-testid=upload-sheet] .dropzone button").click()
    page.wait_for_timeout(1200)
    d = view(case)["decision"] or {}
    check("F · upload in progress (file picker open): no contact", "HG-IN-FLIGHT" in d.get("blocked_by", []),
          f"{d.get('action')} {d.get('blocked_by')}")
    page.keyboard.press("Escape")
    page.goto(f"{BASE}/customer")
    sim(page, "sim-customer-left")
    local = clock().astimezone(IL)
    to_evening = (local.replace(hour=18, minute=30, second=0, microsecond=0) - local).total_seconds() / 60
    if to_evening > 0:
        clock(advance_minutes=int(to_evening))
        tick()
        v = view(case)
        nxt = (v["decision"] or {}).get("next_eligible_at")
        nxt_local = datetime.fromisoformat(nxt).astimezone(IL) if nxt else None
        check("F · outside the call window (18:30): scheduled for the next window, not called",
              not v["attempts"] and nxt_local is not None and 9 <= nxt_local.hour < 18 and nxt_local.date() > local.date(),
              f"{v['decision']['action']} · next {nxt_local}")
    else:
        check("F · outside the call window (skipped: already past 18:30 local)", True)
    clock(reset=True)

    # the kill switch on a case that would otherwise be called now: case 007 (נועה לוי, not called today) with a real
    # open task — עידו's ID card in her slot. עידו's cases already hit the per-customer daily cap after B and C.
    ks = "DEMO-MTZ-2026-007"
    reset(ks)
    seed(ks, ("id", "ID_CARD:BRW-B", None))
    staff()
    api.post(f"/api/demo/cases/{ks}/customer-left")
    api.post("/api/admin/loan-completion/followups/pause", json={"paused": True, "reason": "journey F"}).raise_for_status()
    try:
        clock(advance_minutes=25)
        tick()
        v = view(ks)
        check("F · kill switch on: a case due for a call is blocked, no contact",
              any(OPEN(t) for t in v["tasks"]) and not v["attempts"] and "HG-KILL-SWITCH" in (v["decision"] or {}).get("blocked_by", []),
              str((v["decision"] or {}).get("blocked_by")))
    finally:
        staff()
        api.post("/api/admin/loan-completion/followups/pause", json={"paused": False, "reason": "journey F done"}).raise_for_status()
        clock(reset=True)

    banker.goto(f"{BASE}/banker?case={ks}&view=followup")
    expect(banker.locator("[data-testid=fu-pause]")).to_be_visible(timeout=20000)
    banker.locator("[data-testid=fu-pause]").click()
    expect(banker.locator("[data-testid=fu-note]")).to_be_visible(timeout=15000)
    clock(advance_minutes=25)
    tick()
    v = view(ks)
    check("F · banker pause from the console: blocked, no contact", not v["attempts"]
          and "HG-BANKER-PAUSE" in (v["decision"] or {}).get("blocked_by", []), str((v["decision"] or {}).get("blocked_by")))
    shot(banker, "F-banker-paused")
    banker.locator("[data-testid=fu-resume]").click()
    expect(banker.locator("[data-testid=fu-pause]")).to_be_visible(timeout=15000)
    clock(reset=True)

    nc = "DEMO-MTZ-2026-010"
    reset(nc)
    seed(nc, ("id", ID, None), ("jul", PAY, "2026-07"), ("aug", PAY, "2026-08"), ("st", BANK, None), ("q", PURPOSE, None))
    staff()
    api.post(f"/api/demo/cases/{nc}/customer-left")
    clock(advance_minutes=25)
    tick()
    v = view(nc)
    check("F · no contact consent (case 010): blocked, never called", not v["attempts"]
          and "HG-NO-CONSENT" in (v["decision"] or {}).get("blocked_by", []), str((v["decision"] or {}).get("blocked_by")))
    clock(reset=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_context(viewport={"width": 1440, "height": 920}, locale="he-IL").new_page()
        banker = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="he-IL").new_page()
        for name, run in (("A", lambda: journey_a(page, banker)), ("B", lambda: journey_b(page, banker)),
                          ("C", lambda: journey_c(page)), ("D", lambda: journey_d(page)), ("F", lambda: journey_f(page, banker))):
            try:
                run()
            except Exception as exc:
                check(f"{name} · journey ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
                shot(page, f"{name}-failure-customer")
                shot(banker, f"{name}-failure-banker")
                try:
                    staff()
                    api.post("/api/admin/loan-completion/followups/pause", json={"paused": False, "reason": "cleanup"})
                    clock(reset=True)
                except Exception:
                    pass
        browser.close()
    passed = sum(ok for _, ok, _ in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} follow-up journey checks passed · REPLAY · simulated JEEN Talk only")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
