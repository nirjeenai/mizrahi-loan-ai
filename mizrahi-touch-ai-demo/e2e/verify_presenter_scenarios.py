"""Runs every presenter scenario — the six use cases (TC-01…06, banker steps included), the featured cards and the test library — through the real upload endpoint on a
REPLAY backend and reports what the app actually produced next to what the manifest advertises (zero Gemini calls).
Resets each scenario's case before it runs, so point it only at an isolated stack.

    # from backend/
    .venv/bin/python ../e2e/replay_backend.py --port 8798 --data ../e2e/artifacts/presenter-labels/data
    # from mizrahi-touch-ai-demo/
    REPLAY_BASE=http://127.0.0.1:8798 backend/.venv/bin/python e2e/verify_presenter_scenarios.py

Uploads follow the manifest: each file goes to the requirement in `uploadAs` (the scenario's, else the document's), a
payslip for the month in its step (featured) or `uploadPeriod`, and a file marked as the replacement replaces the
document the AI sent back. A check fails when an advertised reason code never appears or the final case state differs
from `expectedCaseStatus` or from the end state the scenario claims (`expectedResult`)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

import isolation

BASE = os.environ.get("REPLAY_BASE", "http://127.0.0.1:8798")
isolation.require_isolated(BASE)
ROOT = Path(__file__).resolve().parent
PRESENTER = ROOT.parent / "fixtures" / "presenter"
MANIFEST = json.loads((PRESENTER / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
DOCS = {d["id"]: d for d in MANIFEST["documents"]}
OUT = ROOT / "artifacts" / "presenter-labels" / "scenario-results.json"
CASE_OF_STATE = {"isolated_qa_case": "DEMO-MTZ-2026-005", "reset_case_before": "DEMO-MTZ-2026-004"}


def settle(c: httpx.Client, case: str, timeout: float = 120) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = c.get(f"/api/cases/{case}").json()
        if not s["readiness"]["pending_jobs"] and s["readiness"]["counts"]["processing"] == 0:
            return s
        time.sleep(0.6)
    raise TimeoutError(case)


def summary(c: httpx.Client, case: str, s: dict) -> dict:
    names = {d["document_id"]: d["filename"] for d in c.get(f"/api/cases/{case}/documents").json()}
    r = s["readiness"]
    return {"case_status": r.get("case_status"), "customer_status": r.get("customer_status"), "progress": r.get("progress"),
            "requirements": {q["code"]: q["ai_state"] for q in r["requirements"] if q.get("evaluated_by_ai")},
            "findings": sorted({f"{f['code']}:{f['review_state']}" for f in s["findings"] if f["status"] == "open"}),
            "documents": {names.get(k, k): v["outcome"] for k, v in (s.get("outcomes") or {}).get("documents", {}).items()}}


def steps_of(item: dict, featured: bool) -> list[dict]:
    rows = item["steps"] if featured else item.get("items") or [{"file": f} for f in item["files"]]
    return [{"file": st["file"], "period": st.get("period"), "role": st.get("role", "upload"), "uploadAs": st.get("uploadAs"),
             "borrower": st.get("borrower")} for st in rows if not st.get("optional")]


VERIFIED = {"text_layer_exact", "vision_reread_confirmed"}


def end_state(c: httpx.Client, case: str, s: dict, uploaded: dict[str, str], want: dict) -> list[str]:
    """What the scenario claims about its final state (manifest `expectedResult`), compared with what the app holds."""
    errors = []
    r = s["readiness"]
    reqs = {q["code"]: q for q in r["requirements"]}
    if "openFindings" in want:
        got = sorted({f["code"] for f in s["findings"] if f["status"] == "open" and f["review_state"] != "INFO"})
        if got != sorted(want["openFindings"]):
            errors.append(f"open findings {got} ≠ {sorted(want['openFindings'])}")
    if "progress" in want and [r["progress"]["done"], r["progress"]["total"]] != want["progress"]:
        errors.append(f"progress {r['progress']} ≠ {want['progress']}")
    routes = (s.get("outcomes") or {}).get("documents", {})
    for file, outcome in (want.get("documents") or {}).items():
        got = routes.get(uploaded.get(file, ""), {}).get("outcome")
        if got != outcome:
            errors.append(f"{file.split('/')[-1]} routed {got} ≠ {outcome}")
    for code, state in (want.get("requirements") or {}).items():
        if reqs.get(code, {}).get("ai_state") != state:
            errors.append(f"{code} {reqs.get(code, {}).get('ai_state')} ≠ {state}")
    if want.get("tasks"):
        c.post("/api/session/demo/staff", json={}).raise_for_status()
        tasks = {t["requirement_code"]: t["status"] for t in c.get(f"/api/banker/cases/{case}/followup").json()["tasks"]}
        for code, status in want["tasks"].items():
            if tasks.get(code) != status:
                errors.append(f"follow-up task {code} {tasks.get(code)} ≠ {status}")
    for code, months in (want.get("missing") or {}).items():
        if sorted(reqs.get(code, {}).get("missing") or []) != months:
            errors.append(f"{code} missing {reqs.get(code, {}).get('missing')} ≠ {months}")
    if "income" in want:
        inc = (s.get("case_review") or {}).get("income", {}).get("BRW-A", {})
        got = {"declared": inc.get("declared_net_monthly_ils"), "average": inc.get("average_documented_net_ils"),
               "difference": inc.get("difference_ils"), "months": len(inc.get("months_compared") or [])}
        verified = all(m.get("net_witness") in VERIFIED for m in (inc.get("months") or {}).values())
        if got != want["income"] or not verified:
            errors.append(f"income {got} (net values verified: {verified}) ≠ {want['income']}")
    for file in want.get("unverified") or []:
        facts = c.get(f"/api/documents/{uploaded.get(file, '')}").json().get("review", {}).get("facts", [])
        if any((f.get("evidence") or {}).get("witness") in VERIFIED for f in facts):
            errors.append(f"{file.split('/')[-1]} has verified fields although it is unreadable")
    return errors


def run(c: httpx.Client, item: dict, case: str, featured: bool) -> dict:
    c.post("/api/session/demo/customer", json={"case_id": case}).raise_for_status()
    c.post(f"/api/cases/{case}/reset").raise_for_status()
    trail = []
    uploaded: dict[str, str] = {}
    for st in steps_of(item, featured):
        doc = DOCS[st["file"]]
        code = st["uploadAs"] or (item.get("uploadAs") or {}).get(st["file"]) or doc["uploadAs"]
        if st["role"] in ("banker_correction", "banker_accept"):
            trail.append({"file": st["file"], "as": st["role"], "period": None, "replaces": None, "created": None,
                          **banker_step(c, case, uploaded[st["file"]], st["role"])})
            continue
        data = {"requirement_code": code}
        if code.startswith(("ID_CARD", "PAYSLIPS", "TAX_", "VAT_", "PNL_")):
            data["borrower_id"] = st["borrower"] or (code.split(":")[1] if ":" in code else "BRW-A")
        asked = next((q for q in c.get(f"/api/cases/{case}").json().get("customer_requests") or []
                      if q["status"] == "OPEN" and q["requirement_code"] == code), None)
        if asked:
            data["customer_request_id"] = asked["customer_request_id"]
        if st["period"]:
            data["expected_period"] = st["period"]
        s = c.get(f"/api/cases/{case}").json()
        sent_back = [k for k, v in (s.get("outcomes") or {}).get("documents", {}).items() if v["outcome"] == "BLOCKER" and v.get("by") == "ai"]
        if sent_back and st["role"] in ("replacement", "upload"):
            mine = [d["document_id"] for d in c.get(f"/api/cases/{case}/documents").json()
                    if d["document_id"] in sent_back and d["requirement_code"] == code]
            if mine:
                data["replaces_document_id"] = mine[-1]
        path = PRESENTER / doc["downloadPath"]
        with path.open("rb") as fh:
            r = c.post(f"/api/cases/{case}/documents", data=data, files={"file": (path.name, fh, "application/pdf")})
        r.raise_for_status()
        uploaded[st["file"]] = r.json()["document"]["document_id"]
        s = settle(c, case)
        trail.append({"file": st["file"], "as": code, "period": st["period"], "replaces": data.get("replaces_document_id"),
                      "created": r.json()["created"], **summary(c, case, s)})
    seen = {f.split(":")[0] for t in trail for f in t["findings"]}
    expected = set(item.get("expectedReasonCodes") or [])
    final = trail[-1]["case_status"] if trail else None
    want = item.get("expectedCaseStatus")
    errors = end_state(c, case, settle(c, case), uploaded, item.get("expectedResult") or {})
    ok = expected <= seen and (want is None or want == final) and not errors
    return {"id": item["id"], "case": case, "ok": ok, "missing_codes": sorted(expected - seen), "final_status": final,
            "expected_status": want, "errors": errors, "trail": trail}


def banker_step(c: httpx.Client, case: str, document_id: str, role: str) -> dict:
    """The banker's human review of a document no rubric covers: a correction request, or the acceptance."""
    c.post("/api/session/demo/staff", json={}).raise_for_status()
    body = {"action": "request_correction", "customer_message": "נבקש נסח חברה שהופק ב־30 הימים האחרונים.",
            "request_id": f"verify-{role}-{document_id}"} if role == "banker_correction" else \
        {"action": "accept", "rationale": "נבדק ידנית מול המקור, תקין לצורך הכנת התיק", "acknowledged_finding_ids": [],
         "request_id": f"verify-{role}-{document_id}"}
    r = c.post(f"/api/banker/cases/{case}/documents/{document_id}/decision", json=body)
    r.raise_for_status()
    return summary(c, case, settle(c, case))


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    results = []
    for u in MANIFEST.get("useCases", []):
        results.append(run(c, u, u["caseId"], True))
    for f in MANIFEST.get("featured", []):
        results.append(run(c, f, f["caseId"], True))
    for s in MANIFEST["scenarios"]:
        if s.get("verification") == "live":
            results.append({"id": s["id"], "ok": None, "note": "LIVE only — no REPLAY recording for its files"})
            continue
        results.append(run(c, s, s.get("caseId") or CASE_OF_STATE.get(s.get("state", ""), "DEMO-MTZ-2026-005"), False))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf8")
    for r in results:
        if r["ok"] is None:
            print(f"SKIP · {r['id']} · {r['note']}")
            continue
        print(f"{'PASS' if r['ok'] else 'FAIL'} · {r['id']} · {r['case']} · final {r['final_status']}"
              + (f" (expected {r['expected_status']})" if r['expected_status'] else "")
              + (f" · missing codes {r['missing_codes']}" if r["missing_codes"] else "")
              + (f"\n     END STATE: {'; '.join(r['errors'])}" if r["errors"] else ""))
        if os.environ.get("QUIET"):
            continue
        for t in r["trail"]:
            print(f"     {t['file'].split('/')[-1]:34} → {t['as']:22} {t['period'] or '':8} created={t['created']} "
                  f"status={t['case_status']} progress={t['progress']}\n        findings={t['findings']}\n        docs={t['documents']}")
    bad = [r for r in results if r["ok"] is False]
    print(f"\n{sum(1 for r in results if r['ok'])}/{sum(1 for r in results if r['ok'] is not None)} scenarios produce what they advertise · REPLAY")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
