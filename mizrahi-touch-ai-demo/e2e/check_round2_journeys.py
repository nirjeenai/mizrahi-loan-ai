"""Round 2 — the six complete test cases and the new-customer journey in a real Chrome, on a REPLAY stack.

Path 1 (TC-01…06): open the use case from the presenter, download every file of its pack from the presenter (bytes
compared with the fixture), upload each one through its own requirement card, let the AI review run (REPLAY answers
recorded live), correct what the scenario sends back, and — for the company — do the banker's human review in the
console. TC-02's missing income document goes through the follow-up engine: presence, grace, a simulated JEEN Talk call,
the secure link, the upload and the resolved task. A profile change on TC-01 recomposes the checklist, keeps the
uploaded payslips and cancels the payslip follow-up before its contact could run.
Path 2 (new customer): the JEEN questionnaire with a draft resumed after a reload, a double-clicked confirmation, the
personalised checklist, uploads with a missing month, follow-up through the secure link, and the banker's view.

Isolated stack only. Zero Gemini calls: every model answer is a RECORDED_LIVE REPLAY answer. Resets cases 101–106.

    # from backend/ — fresh DATA_DIR
    .venv/bin/python ../e2e/replay_backend.py --port 8792 --data ../e2e/artifacts/round2/data
    # from mizrahi-touch-ai-demo/
    node e2e/serve_frontend.mjs e2e/artifacts/round2/web 5843 http://127.0.0.1:8792
    ROUND2_BASE=http://127.0.0.1:5843 ROUND2_DATA=e2e/artifacts/round2/data backend/.venv/bin/python e2e/check_round2_journeys.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("ROUND2_BASE", "http://127.0.0.1:5843")
if any(p in BASE for p in (":8790", ":8791", ":5192")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("ROUND2_DATA", ROOT / "artifacts" / "round2" / "data")).resolve()
PRESENTER = ROOT.parent / "fixtures" / "presenter"
MANIFEST = json.loads((PRESENTER / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
DOCS = {d["id"]: d for d in MANIFEST["documents"]}
USE = {u["id"]: u for u in MANIFEST["useCases"]}
OUT = ROOT / "artifacts" / "round2"
DL = OUT / "downloads"
RESULTS: list[tuple[str, bool, str]] = []
api = httpx.Client(base_url=BASE, timeout=60)


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


def shot(page: Page, name: str, full: bool = False) -> None:
    page.wait_for_timeout(350)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)


# ---------------------------------------------------------------- API (checks and clock only; every upload is in the browser)
def staff() -> None:
    api.post("/api/session/demo/staff", json={"staff_id": "STAFF-DANA"}).raise_for_status()


def customer(case: str) -> None:
    api.post("/api/session/demo/customer", json={"case_id": case}).raise_for_status()


def snap(case: str) -> dict:
    customer(case)
    return api.get(f"/api/cases/{case}").json()


def settle(case: str, timeout: float = 120) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = snap(case)
        if not s["readiness"]["pending_jobs"] and s["readiness"]["counts"]["processing"] == 0:
            return s
        time.sleep(0.5)
    raise TimeoutError(case)


def view(case: str) -> dict:
    staff()
    return api.get(f"/api/banker/cases/{case}/followup").json()


def clock(**body) -> None:
    staff()
    api.post("/api/demo/clock", json=body).raise_for_status()


def tick() -> None:
    staff()
    api.post("/api/demo/tick").raise_for_status()


def wait_plan(case: str, states: tuple[str, ...], timeout: float = 90) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        v = view(case)
        if v["plan"]["state"] in states:
            return v
        time.sleep(1)
    return view(case)


def doc_id(case: str, filename: str) -> str:
    customer(case)
    return [d["document_id"] for d in api.get(f"/api/cases/{case}/documents").json() if d["filename"] == filename][-1]


# ---------------------------------------------------------------- browser helpers
def presenter(page: Page) -> None:
    if page.locator(".hub").get_attribute("data-presenter") != "open":
        page.locator("[data-testid=presenter-toggle]").click()
    expect(page.locator("[data-testid=use-cases]")).to_be_visible(timeout=20000)


def close_presenter(page: Page) -> None:
    if page.locator(".hub").get_attribute("data-presenter") == "open":
        page.locator("[data-testid=presenter-close]").click()


def card(page: Page, tc: str):
    c = page.locator(f"[data-testid=usecase-{tc}]")
    c.scroll_into_view_if_needed()
    if not c.locator("[data-testid=usecase-requirements]").count():
        c.locator("[data-testid=usecase-toggle]").click()
    return c


def download_pack(page: Page, tc: str) -> dict[str, Path]:
    """Every file of the card, downloaded through the presenter endpoint and compared with the fixture's bytes."""
    presenter(page)
    c = card(page, tc)
    links = c.locator("[data-testid=usecase-download]")
    out, bad = {}, []
    for i in range(links.count()):
        doc = DOCS[links.nth(i).get_attribute("data-doc-id")]
        dl = fetch(page, tc, links.nth(i), doc["id"])
        target = DL / tc / dl.value.suggested_filename
        target.parent.mkdir(parents=True, exist_ok=True)
        dl.value.save_as(str(target))
        data = target.read_bytes()
        if data != (PRESENTER / doc["downloadPath"]).read_bytes() or hashlib.sha256(data).hexdigest() != doc["sha256"]:
            bad.append(doc["id"])
        out[doc["id"]] = target
    want = {s["file"] for s in USE[tc]["steps"] if not s["role"].startswith("banker")}
    check(f"{tc} · every file of the pack downloads from the presenter, byte-identical to the fixture (SHA-256)",
          not bad and set(out) == want, f"{len(out)} files" + (f" · mismatch {bad}" if bad else ""))
    return out


def fetch(page: Page, tc: str, link, doc_id_: str):
    """A download from the presenter. Chrome may hold back a long series of downloads in one tab; the retry then fetches
    the same manifest file from a fresh tab (the bytes are compared with the fixture either way)."""
    try:
        with page.expect_download(timeout=15000) as dl:
            link.click()
        return dl
    except Exception:
        fresh = page.context.new_page()
        fresh.goto(f"{BASE}/customer")
        presenter(fresh)
        retry = card(fresh, tc).locator(f"[data-testid=usecase-download][data-doc-id='{doc_id_}']")
        with fresh.expect_download(timeout=30000) as dl:
            retry.click()
        dl.value.path()
        fresh.close()
        RETRIES.append(doc_id_)
        return dl


RETRIES: list[str] = []


def open_case(page: Page, tc: str) -> None:
    presenter(page)
    card(page, tc).locator("[data-testid=usecase-open-case]").click()
    expect(page.locator("[data-testid=document-profile]")).to_have_attribute("data-use-case", USE[tc]["useCaseId"], timeout=20000)
    close_presenter(page)


def reset_case(page: Page, tc: str) -> None:
    open_case(page, tc)
    presenter(page)
    c = card(page, tc)
    c.locator("[data-testid=usecase-reset]").click()
    c.locator("[data-testid=usecase-reset-confirm]").click()
    expect(c.get_by_text("התיק אופס")).to_be_visible(timeout=15000)
    close_presenter(page)


def sheet_submit(page: Page, path: Path, period: str | None) -> str:
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible(timeout=15000)
    if period:
        chip = sheet.locator(f".mchip[data-period='{period}']")
        if chip.count() and chip.get_attribute("aria-checked") != "true":
            chip.click()
    sheet.locator("[data-testid=file-input]").set_input_files(str(path))
    sheet.locator("[data-testid=upload-submit]").click()
    done = sheet.locator("[data-testid=upload-outcome], [data-testid=upload-stored]")
    expect(done.first).to_be_visible(timeout=90000)
    text = done.first.inner_text()
    sheet.locator("button[aria-label='סגירה']").click()
    return text


def upload(page: Page, code: str, path: Path, period: str | None = None, via_request: bool = False) -> str:
    page.goto(f"{BASE}/customer/documents")
    if via_request:
        q = page.locator("[data-testid=customer-request][data-status=OPEN]").first
        expect(q).to_be_visible(timeout=15000)
        q.locator("[data-testid=request-upload]").click()
        return sheet_submit(page, path, period)
    row = page.locator(f"[data-testid='req-{code}']")
    expect(row).to_be_visible(timeout=15000)
    head = row.locator(".dl-head")
    if head.get_attribute("aria-expanded") != "true":
        head.click()
    who = code.split(":")[1] if code.startswith("PAYSLIPS") else None
    button = row.locator(f"[data-testid=upload-{who}]") if who else row.locator(f"[data-testid='upload-{code}']")
    button.first.click()
    return sheet_submit(page, path, period)


def sim(page: Page, testid: str) -> str:
    if page.locator(".hub").get_attribute("data-presenter") != "open":
        page.locator("[data-testid=presenter-toggle]").click()
    box = page.locator("[data-testid=followup-sim]")
    if box.get_attribute("open") is None:
        box.locator("summary").click()
    page.locator(f"[data-testid={testid}]").click()
    line = page.locator("[data-testid=sim-line]")
    expect(line).to_be_visible(timeout=15000)
    page.wait_for_timeout(800)
    return line.inner_text()


def banker_decide(banker: Page, case: str, document_id: str, action: str) -> None:
    banker.goto(f"{BASE}/banker?case={case}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    banker.locator(f"[data-item-id='doc:{document_id}']").click()
    expect(banker.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=20000)
    if action == "correction":
        banker.locator("[data-testid=action-correction]").click()
        msg = banker.locator("[data-testid=customer-message]")
        msg.fill("שלום גלעד, נבקש נסח חברה שהופק ב־30 הימים האחרונים. הנסח שהועלה הופק ביוני 2026.")
        banker.locator("[data-testid=preview-request]").click()
        banker.locator("[data-testid=send-request]").click()
    else:
        banker.locator("[data-testid=action-accept]").click()
        banker.locator("[data-testid=accept-rationale]").fill("נבדק ידנית מול המקור — תקין לצורך הכנת התיק")
        banker.locator("[data-testid=confirm-accept]").click()
    banker.wait_for_timeout(1200)


def final_state(tc: str, s: dict) -> None:
    u = USE[tc]
    r = s["readiness"]
    want = u["expectedResult"]
    routes = {d["filename"]: (s["outcomes"]["documents"].get(d["document_id"]) or {}).get("outcome")
              for d in api.get(f"/api/cases/{u['caseId']}/documents").json()}
    bad = [f"{f} {routes.get(Path(DOCS[f]['downloadPath']).name)}≠{o}" for f, o in (want.get("documents") or {}).items()
           if routes.get(Path(DOCS[f]["downloadPath"]).name) != o]
    reqs = {q["code"]: q["ai_state"] for q in r["requirements"]}
    bad += [f"{c} {reqs.get(c)}≠{st}" for c, st in (want.get("requirements") or {}).items() if reqs.get(c) != st]
    opened = sorted({f["code"] for f in s["findings"] if f["status"] == "open" and f["review_state"] != "INFO"})
    check(f"{tc} · end state: {u['expectedLabelHe']}",
          r["case_status"] == u["expectedCaseStatus"] and [r["progress"]["done"], r["progress"]["total"]] == want["progress"]
          and opened == want.get("openFindings", opened) and not bad,
          f"{r['case_status']} · {r['progress']['done']}/{r['progress']['total']} · open {opened}" + (f" · {bad}" if bad else ""))


# ---------------------------------------------------------------- Path 1: the six test cases
def run_tc(page: Page, banker: Page, tc: str) -> None:
    u = USE[tc]
    reset_case(page, tc)
    files = download_pack(page, tc)
    open_case(page, tc)
    profile = page.locator("[data-testid=document-profile]")
    names = profile.locator("[data-testid=profile-applicant] b").all_inner_texts()
    check(f"{tc} · the app shows {u['personaHe']} with the checklist of the profile",
          all(n.split()[0] in u["personaHe"] for n in names) and
          sorted(page.locator("[data-testid=required-docs] li.dl-row").evaluate_all(
              "els => els.map(e => e.getAttribute('data-testid').replace(/^req-/, ''))")) == sorted(r["code"] for r in u["requirements"]),
          " / ".join(names))
    seen: list[str] = []
    for st in u["steps"]:
        if st.get("optional"):
            continue
        if st["role"].startswith("banker"):
            banker_decide(banker, u["caseId"], doc_id(u["caseId"], Path(DOCS[st["file"]]["downloadPath"]).name),
                          "correction" if st["role"] == "banker_correction" else "accept")
            settle(u["caseId"])
            continue
        if tc == "TC-02" and st["role"] == "replacement":
            followup_tc02(page, files[st["file"]])
            continue
        asked = any(q["status"] == "OPEN" and q["requirement_code"] == st["uploadAs"] for q in snap(u["caseId"]).get("customer_requests") or [])
        msg = upload(page, st["uploadAs"], files[st["file"]], st.get("period"), via_request=asked)
        s = settle(u["caseId"])
        seen += [f["code"] for f in s["findings"] if f["status"] == "open"]
        if st["role"] == "wrong":
            route = (s["outcomes"]["documents"].get(doc_id(u["caseId"], files[st["file"]].name)) or {}).get("outcome")
            check(f"{tc} · {st['labelHe']}: {'sent back by the AI' if DOCS[st['file']]['intake'] == 'ai_review' else 'waits for the banker'}",
                  route == ("BLOCKER" if DOCS[st["file"]]["intake"] == "ai_review" else "HUMAN_REVIEW_PENDING"), f"{route} · {msg[:70]}")
            page.goto(f"{BASE}/customer/documents")
            shot(page, f"{tc}-wrong-{Path(st['file']).stem}")
    s = settle(u["caseId"])
    missing = set(u["expectedReasonCodes"]) - set(seen) - {"REQUIRED_DOCUMENT_MISSING"}
    check(f"{tc} · the advertised reason codes appeared during the journey", not missing, f"missing {sorted(missing)}" if missing else "")
    final_state(tc, s)
    page.goto(f"{BASE}/customer/documents")
    expect(page.locator("[data-testid=docs-progress]")).to_contain_text(f"{s['readiness']['progress']['done']} מתוך", timeout=15000)
    shot(page, f"{tc}-final-documents")
    banker.goto(f"{BASE}/banker?case={u['caseId']}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    shot(banker, f"{tc}-banker")


def followup_tc02(page: Page, cpa_letter: Path) -> None:
    """The missing income document: an open task, presence protection, grace, a simulated call, the secure link."""
    case = USE["TC-02"]["caseId"]
    clock(reset=True)
    page.goto(f"{BASE}/customer/documents")
    page.wait_for_timeout(1500)
    tick()
    v = view(case)
    open_tasks = [t for t in v["tasks"] if t["status"] not in ("RESOLVED", "CANCELED")]
    check("TC-02 · follow-up: one open task — the missing tax assessment / CPA letter",
          [t["requirement_code"] for t in open_tasks] == ["TAX_ASSESSMENT:BRW-A"], str([(t["requirement_code"], t["status"]) for t in v["tasks"]]))
    check("TC-02 · presence: the customer is on the documents screen — no contact", not v["attempts"],
          (v.get("decision") or {}).get("action", ""))
    page.goto(f"{BASE}/customer")
    sim(page, "sim-customer-left")
    v = view(case)
    check("TC-02 · the customer leaves → the engine waits the grace period", v["decision"]["action"] == "WAIT", v["decision"]["action"])
    sim(page, "sim-clock-20")
    v = wait_plan(case, ("DISPATCHING", "IN_CALL", "AWAITING_CUSTOMER"))
    a = v["attempts"][0] if v["attempts"] else {}
    check("TC-02 · after the grace period one simulated JEEN Talk call (mock-talk, never dials)",
          len(v["attempts"]) == 1 and a.get("simulated") is True and a.get("provider") == "mock-talk", v["plan"]["state"])
    sim(page, "sim-outcome-LINK_SENT")
    wait_plan(case, ("AWAITING_CUSTOMER",))
    page.locator("[data-testid=sim-open-link]").click()
    sheet = page.locator("[data-testid=upload-sheet]")
    expect(sheet).to_be_visible(timeout=20000)
    check("TC-02 · the secure link opens the upload of the missing income document",
          sheet.locator("[data-testid=upload-doc-type]").get_attribute("data-requirement") == "TAX_ASSESSMENT:BRW-A")
    shot(page, "TC-02-secure-link-upload")
    sheet_submit(page, cpa_letter, None)
    settle(case)
    v = wait_plan(case, ("COMPLETED",), 60)
    task = next(t for t in v["tasks"] if t["requirement_code"] == "TAX_ASSESSMENT:BRW-A")
    check("TC-02 · the CPA letter (accepted alternative) passes: task resolved, follow-up completed",
          task["status"] == "RESOLVED" and v["plan"]["state"] == "COMPLETED", f"{task['status']} · {v['plan']['state']}")
    clock(advance_minutes=2880)
    tick()
    check("TC-02 · no second contact after completion", len(view(case)["attempts"]) == 1)
    clock(reset=True)


def profile_change(page: Page, banker: Page) -> None:
    """TC-01: payslips missing a month → the customer leaves (a contact is pending) → the profile changes to
    self-employed: payslips become inactive and are kept, the payslip task is canceled, and its call never runs."""
    u = USE["TC-01"]
    case = u["caseId"]
    reset_case(page, "TC-01")
    files = {Path(s["file"]).name: DL / "TC-01" / Path(DOCS[s["file"]]["downloadPath"]).name for s in u["steps"]}
    open_case(page, "TC-01")
    for name, code, period in (("id_card_michal.pdf", "ID_CARD:BRW-C", None), ("payslip_michal_2026-07.pdf", "PAYSLIPS:BRW-C", "2026-07"),
                               ("payslip_michal_2026-08.pdf", "PAYSLIPS:BRW-C", "2026-08")):
        upload(page, code, files[name], period)
    settle(case)
    clock(reset=True)
    page.goto(f"{BASE}/customer")
    sim(page, "sim-customer-left")
    v = view(case)
    pay_tasks = [t["task_id"] for t in v["tasks"] if t["requirement_code"] == "PAYSLIPS:BRW-C" and t["status"] not in ("RESOLVED", "CANCELED")]
    check("profile change · before: a payslip follow-up task is open and the engine waits to contact", bool(pay_tasks)
          and v["decision"]["action"] == "WAIT", v["decision"]["action"])
    close_presenter(page)
    page.goto(f"{BASE}/customer/documents")
    page.locator("[data-testid=profile-edit]").click()
    ed = page.locator("[data-testid=profile-editor]")
    ed.locator("label:has([data-testid=profile-income-salaried])").click()          # the app's choice chips are labels
    ed.locator("label:has([data-testid=profile-income-self_employed])").click()
    ed.locator("label:has([data-testid=profile-reg-vat_exempt])").click()
    shot(page, "profile-change-editor")
    ed.locator("[data-testid=profile-save]").click()
    result = page.locator("[data-testid=profile-change-result]")
    expect(result).to_be_visible(timeout=15000)
    s = settle(case)
    codes = {r["code"] for r in s["readiness"]["requirements"]}
    check("profile change · the checklist is recomposed: payslips out, tax evidence and VAT-exempt certificate in",
          "PAYSLIPS:BRW-C" not in codes and {"TAX_ASSESSMENT:BRW-C", "VAT_EXEMPT_CERT:BRW-C"} <= codes, result.inner_text()[:120])
    expect(page.locator("[data-testid=inactive-requirement][data-code='PAYSLIPS:BRW-C']")).to_be_visible(timeout=15000)
    kept = [d for d in api.get(f"/api/cases/{case}/documents").json() if d["requirement_code"] == "PAYSLIPS:BRW-C"]
    check("profile change · the two uploaded payslips are kept and shown as no longer required",
          len(kept) == 2 and all(d["review"] for d in kept))
    shot(page, "profile-change-after")
    sim(page, "sim-clock-20")
    tick()
    time.sleep(2)
    v = view(case)
    canceled = {t["task_id"]: t["status"] for t in v["tasks"]}
    about_payslips = [a for a in v["attempts"] if set(a.get("task_ids") or []) & set(pay_tasks)]
    check("profile change · the payslip task is canceled and no contact about payslips ever runs",
          all(canceled.get(t) == "CANCELED" for t in pay_tasks) and not about_payslips,
          f"tasks {[canceled.get(t) for t in pay_tasks]} · attempts {len(v['attempts'])}")
    banker.goto(f"{BASE}/banker?case={case}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    staff()
    matrix = api.get(f"/api/banker/cases/{case}/workspace").json()["requirement_matrix"]
    check("profile change · the banker's requirement matrix shows the inactive payslip requirement with its documents",
          any(m.get("inactive") and m["code"] == "PAYSLIPS:BRW-C" and len(m["document_ids"]) == 2 for m in matrix))
    clock(reset=True)
    reset_case(page, "TC-01")


# ---------------------------------------------------------------- Path 2: a new customer
ANSWERS = [("entity", "individual"), ("name", ("נטע", "אלון")), ("national_id", "DEMO-ID-201"), ("purpose", "car"),
           ("income", ["salaried"]), ("net", "12000"), ("co_borrower", "no"), ("amount", "80000"), ("payments", "60")]


def answer(page: Page, qid: str, value) -> None:
    expect(page.locator("[data-testid=onb-question]")).to_have_attribute("data-question", qid, timeout=10000)
    if isinstance(value, tuple):
        page.locator("[data-testid=onb-first]").fill(value[0])
        page.locator("[data-testid=onb-last]").fill(value[1])
        page.locator("[data-testid=onb-send]").click()
    elif isinstance(value, list):
        for v in value:
            page.locator(f"[data-testid=onb-option][data-value='{v}']").click()
        page.locator("[data-testid=onb-send]").click()
    elif page.locator("[data-testid=onb-text]").count():
        page.locator("[data-testid=onb-text]").fill(value)
        page.locator("[data-testid=onb-send]").click()
    else:
        page.locator(f"[data-testid=onb-option][data-value='{value}']").click()
    expect(page.locator(f"[data-testid=onb-answered-{qid}]")).to_be_visible(timeout=10000)


def fetch_new(page: Page, link, doc_id_: str):
    try:
        with page.expect_download(timeout=15000) as dl:
            link.click()
        return dl
    except Exception:
        fresh = page.context.new_page()
        fresh.goto(f"{BASE}/customer")
        presenter(fresh)
        c = fresh.locator("[data-testid=usecase-NEW-CUSTOMER]")
        c.scroll_into_view_if_needed()
        c.locator("[data-testid=usecase-new-toggle]").click()
        with fresh.expect_download(timeout=30000) as dl:
            c.locator(f"[data-testid=usecase-download][data-doc-id='{doc_id_}']").click()
        dl.value.path()
        fresh.close()
        RETRIES.append(doc_id_)
        return dl


def new_customer(page: Page, banker: Page) -> None:
    pack = MANIFEST["newCustomer"]
    presenter(page)
    c = page.locator("[data-testid=usecase-NEW-CUSTOMER]")
    c.scroll_into_view_if_needed()
    c.locator("[data-testid=usecase-new-toggle]").click()
    files = {}
    for link in c.locator("[data-testid=usecase-download]").all():
        doc = DOCS[link.get_attribute("data-doc-id")]
        dl = fetch_new(page, link, doc["id"])
        target = DL / "NEW" / dl.value.suggested_filename
        target.parent.mkdir(parents=True, exist_ok=True)
        dl.value.save_as(str(target))
        files[doc["id"]] = target
    check("new customer · the presenter offers the matching pack (byte-identical downloads)",
          set(files) == {s["file"] for s in pack["steps"]}
          and all(p.read_bytes() == (PRESENTER / DOCS[i]["downloadPath"]).read_bytes() for i, p in files.items()))
    c.locator("[data-testid=usecase-new-start]").click()
    close_presenter(page)
    expect(page.locator("[data-testid=apply-chat]")).to_be_visible(timeout=15000)
    if page.locator("[data-testid=onb-restart]").count():
        page.locator("[data-testid=onb-restart]").click()
    for qid, value in ANSWERS[:4]:
        answer(page, qid, value)
    draft = page.locator("[data-testid=apply-chat]").get_attribute("data-draft")
    page.reload()
    expect(page.locator("[data-testid=onb-question]")).to_have_attribute("data-question", "income", timeout=15000)
    check("new customer · the draft resumes after a reload, at the next unanswered question",
          page.locator("[data-testid=apply-chat]").get_attribute("data-draft") == draft
          and page.locator("[data-testid=onb-answered-national_id]").is_visible())
    shot(page, "NEW-questionnaire")
    for qid, value in ANSWERS[4:]:
        answer(page, qid, value)
    expect(page.locator("[data-testid=onb-summary]")).to_be_visible(timeout=10000)
    page.wait_for_timeout(900)
    shot(page, "NEW-summary")
    before = len(api.get("/api/session/demo/cases").json())
    page.locator("[data-testid=onb-confirm]").evaluate("b => { b.click(); b.click(); }")
    expect(page.locator("[data-testid=document-profile]")).to_be_visible(timeout=20000)
    rows = api.get("/api/session/demo/cases").json()
    case = next(r["case_id"] for r in rows if r.get("applicants_he") == ["נטע אלון"])
    check("new customer · one persisted case for a double-clicked confirmation", len(rows) == before + 1, case)
    s = settle(case)
    check("new customer · the personalised checklist (salaried, car)",
          [q["code"] for q in s["readiness"]["requirements"]] == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"])
    page.locator(".touch-header .case-pill").click()
    expect(page.locator("[data-testid=drawer-my-cases] [data-testid=drawer-case]").first).to_be_visible(timeout=10000)
    mine = page.locator("[data-testid=drawer-my-cases] [data-testid=drawer-case]").evaluate_all("els => els.map(e => e.getAttribute('data-case'))")
    check("new customer · 'התיקים שלי' shows her application only", mine == [case], str(mine))
    box = page.locator(".drawer").bounding_box()
    page.mouse.click(box["x"] + 20, box["y"] + box["height"] / 2)
    for st in pack["steps"][:-1]:
        upload(page, st["uploadAs"], files[st["file"]], st.get("period"))
    s = settle(case)
    pay = next(q for q in s["readiness"]["requirements"] if q["code"] == "PAYSLIPS:BRW-A")
    check("new customer · real REPLAY reviews of her documents; September is missing",
          pay["missing"] == ["2026-09"] and s["readiness"]["progress"]["done"] == 3, f"{s['readiness']['progress']}")
    shot(page, "NEW-missing-month")
    clock(reset=True)
    page.goto(f"{BASE}/customer")
    sim(page, "sim-customer-left")
    sim(page, "sim-clock-20")
    v = wait_plan(case, ("DISPATCHING", "IN_CALL", "AWAITING_CUSTOMER"))
    check("new customer · follow-up: one simulated call about the missing payslip", len(v["attempts"]) == 1, v["plan"]["state"])
    sim(page, "sim-outcome-LINK_SENT")
    wait_plan(case, ("AWAITING_CUSTOMER",))
    page.locator("[data-testid=sim-open-link]").click()
    expect(page.locator("[data-testid=upload-sheet]")).to_be_visible(timeout=20000)
    sheet_submit(page, files[pack["steps"][-1]["file"]], "2026-09")
    s = settle(case)
    v = wait_plan(case, ("COMPLETED",), 60)
    check("new customer · completed through the secure link: ready for the banker, follow-up completed",
          s["readiness"]["case_status"] == "READY_FOR_BANKER" and v["plan"]["state"] == "COMPLETED",
          f"{s['readiness']['case_status']} · {v['plan']['state']}")
    clock(reset=True)
    page.goto(f"{BASE}/customer/documents")
    shot(page, "NEW-complete")
    banker.goto(f"{BASE}/banker?case={case}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    id_doc = doc_id(case, "id_card_neta.pdf")
    banker.locator(f"[data-item-id='doc:{id_doc}']").click()
    expect(banker.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=20000)
    expect(banker.locator(".hl[data-field=holder_id]")).to_have_count(1, timeout=15000)
    check("new customer · the banker sees her ID with the identity number boxed on the original page",
          "נטע אלון" in banker.locator("[data-testid=case-switch] .case-names").inner_text())
    shot(banker, "NEW-banker-evidence")


def banker_checks(banker: Page) -> None:
    case = USE["TC-05"]["caseId"]
    banker.goto(f"{BASE}/banker?case={case}")
    expect(banker.locator("[data-testid=review-queue]")).to_be_visible(timeout=20000)
    copy = doc_id(case, "id_card_maya_COPY.pdf")
    item = banker.locator(f"[data-item-id='doc:{copy}']")
    if not item.is_visible():                                  # a replaced document sits in the collapsed "טופלו" group
        banker.locator(".queue-group", has_text="טופלו").locator("button, summary").first.click()
    item.click()
    expect(banker.locator("[data-testid=evidence-viewer] img")).to_be_visible(timeout=20000)
    text = banker.locator("body").inner_text()
    check("TC-05 · banker: Maya's ID filed under Roy is marked replaced, attributed to מאיה שטרן", "הוחלף" in text and "מאיה" in text)
    shot(banker, "TC-05-banker-replaced-id")
    case = USE["TC-06"]["caseId"]
    banker.goto(f"{BASE}/banker?case={case}")
    expect(banker.locator("[data-testid=banker-assisted]")).to_be_visible(timeout=20000)
    staff()
    matrix = {m["code"]: m["ai_state"] for m in api.get(f"/api/banker/cases/{case}/workspace").json()["requirement_matrix"]}
    check("TC-06 · banker: company documents accepted by the banker, the signatory's ID verified by AI — no AI verdict on company documents",
          matrix.get("ID_CARD:BRW-A") == "extracted" and all(matrix.get(c) == "accepted_by_banker" for c in
          ("COMPANY_EXTRACT", "SIGNATORY_AUTHORITY", "COMPANY_FINANCIALS", "COMPANY_INTERIM", "BUSINESS_STATEMENTS:ACC-1")),
          json.dumps(matrix, ensure_ascii=False))
    ext = doc_id(case, "company_extract_sg.pdf")
    customer(case)
    d = api.get(f"/api/documents/{ext}").json()
    check("TC-06 · the company extract was stored for human review: no AI run, no fabricated evidence",
          d["status"] == "stored" and d["review"] is None and not d["runs"])


def mobile(browser) -> None:
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="he-IL", is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/customer")
    page.evaluate("localStorage.setItem('mz.case', 'DEMO-MTZ-2026-105')")
    page.goto(f"{BASE}/customer/documents")
    expect(page.locator("[data-testid=document-profile]")).to_be_visible(timeout=20000)
    over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check("mobile 390×844 · TC-05 documents with the profile card: RTL, no sideways scroll",
          over <= 0 and page.evaluate("document.documentElement.dir") == "rtl", f"overflow {over}")
    shot(page, "mobile-TC-05-documents")
    ctx.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock = (OUT / ".lock").open("w")
    try:                                   # two copies against one stack would mix their cases and overwrite results
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another check_round2_journeys run is in progress against this artifacts folder")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_context(viewport={"width": 1440, "height": 920}, locale="he-IL", accept_downloads=True).new_page()
        banker = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="he-IL").new_page()
        page.goto(f"{BASE}/customer")
        steps = [(f"run {t}", (lambda pg, bk, t=t: run_tc(pg, bk, t))) for t in USE] + [
            ("banker checks", banker_checks_step), ("profile change", profile_change), ("new customer", new_customer)]
        for name, step in steps:
            try:
                step(page, banker)
            except Exception as exc:
                check(f"{name} ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
                shot(page, f"failure-{len(RESULTS)}")
                shot(banker, f"failure-banker-{len(RESULTS)}")
                clock(reset=True)
        try:
            mobile(browser)
        except Exception as exc:
            check("mobile ran to the end", False, f"{type(exc).__name__}: {str(exc)[:300]}")
        browser.close()
    log = [json.loads(line) for line in (DATA / "replay-transport.jsonl").read_text(encoding="utf8").splitlines()] \
        if (DATA / "replay-transport.jsonl").exists() else []
    served = [e for e in log if e.get("purpose") in ("extract", "judge")]
    check("REPLAY only: every extract/judge answer came from a RECORDED_LIVE recording; no network call",
          bool(served) and all(e["served"] for e in served) and {e.get("provenance") for e in served} <= {"RECORDED_LIVE"},
          f"{len(served)} answers")
    if RETRIES:
        print(f"note: {len(RETRIES)} download(s) fetched again from a fresh tab: {RETRIES}")
    passed = sum(ok for _, ok, _ in RESULTS)
    (OUT / "results.json").write_text(json.dumps({"mode": "REPLAY", "passed": passed, "total": len(RESULTS),
                                                  "results": [{"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS]},
                                                 ensure_ascii=False, indent=1), encoding="utf8")
    print(f"\n{passed}/{len(RESULTS)} Round 2 checks passed · {BASE} · REPLAY")
    return 0 if passed == len(RESULTS) else 1


def banker_checks_step(page: Page, banker: Page) -> None:
    banker_checks(banker)


if __name__ == "__main__":
    sys.exit(main())
