"""Follow-up policy changes, end to end through the Admin API on an integrated isolated REPLAY stack (zero Gemini,
no real call): a legitimate grace or call-window edit can be simulated and published, the running follow-up engine then
uses the new timing, invalid or unsafe configurations are refused, the hard guards keep holding, and rollback restores
the old behaviour. Resets case 009 and leaves the policy as it found it (a rollback, so the history shows it).

    POLICY_BASE=http://127.0.0.1:8799 backend/.venv/bin/python e2e/check_policy_acceptance.py
"""
from __future__ import annotations

import copy
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

import isolation

BASE = os.environ.get("POLICY_BASE", "http://127.0.0.1:8799")
if any(p in BASE for p in (":8790", ":8791")):
    sys.exit(f"refusing to run against {BASE}: use an isolated stack")
isolation.require_isolated(BASE)
ADMIN = "/api/admin/loan-completion"
CASE = "DEMO-MTZ-2026-009"
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "presenter"
RESULTS: list[tuple[str, bool, str]] = []
c = httpx.Client(base_url=BASE, timeout=60)


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def seed_missing_payslip() -> None:
    """Case 009 with the ID card and two payslips: September is an open, verified customer task."""
    c.post("/api/session/demo/customer", json={"case_id": CASE}).raise_for_status()
    c.post(f"/api/cases/{CASE}/reset").raise_for_status()
    for path, code, period in (("loan_set/id_card_ido.pdf", "ID_CARD:BRW-A", None),
                               ("golden_set/01_INITIAL_UPLOADS/ido_2026_07.pdf", "PAYSLIPS:BRW-A", "2026-07"),
                               ("golden_set/01_INITIAL_UPLOADS/ido_2026_08.pdf", "PAYSLIPS:BRW-A", "2026-08")):
        p = FIX / path
        with p.open("rb") as fh:
            c.post(f"/api/cases/{CASE}/documents", data={"requirement_code": code, "borrower_id": "BRW-A",
                                                        **({"expected_period": period} if period else {})},
                   files={"file": (p.name, fh, "application/pdf")}).raise_for_status()
    for _ in range(240):
        s = c.get(f"/api/cases/{CASE}").json()
        if not s["readiness"]["pending_jobs"] and s["readiness"]["counts"]["processing"] == 0 and s["case_review"]:
            return
        time.sleep(0.5)
    raise TimeoutError("case 009 did not settle")


def grace_now() -> tuple[float | None, dict]:
    """The engine's own decision when the customer leaves: minutes until it may next contact them."""
    r = c.post(f"/api/demo/cases/{CASE}/customer-left").json()
    d = r["decision"]
    now = datetime.fromisoformat(c.post("/api/demo/clock", json={}).json()["now"])
    nxt = d.get("next_eligible_at")
    return ((datetime.fromisoformat(nxt) - now).total_seconds() / 60 if nxt else None), d


def draft_with(change) -> dict:
    d = c.post(f"{ADMIN}/drafts", json={"kind": "loan_policy", "reason": "acceptance"}).json()
    cfg = copy.deepcopy(d["config"])
    change(cfg)
    return c.put(f"{ADMIN}/drafts/{d['version_id']}", json={"config": cfg, "revision": d["revision"], "reason": "acceptance"})


def publish(draft: dict) -> httpx.Response:
    return c.post(f"{ADMIN}/drafts/{draft['version_id']}/publish", json={"revision": draft["revision"]})


def discard_open() -> None:
    d = c.post(f"{ADMIN}/drafts", json={"kind": "loan_policy"}).json()
    if d.get("status") == "DRAFT":
        c.post(f"{ADMIN}/drafts/{d['version_id']}/discard", json={"revision": d["revision"]})


def main() -> int:
    c.post("/api/session/demo/staff", json={"staff_id": "STAFF-DANA"}).raise_for_status()
    start = c.get(f"{ADMIN}/settings").json()["published"]["loan_policy"]
    c.post("/api/demo/clock", json={"reset": True})
    seed_missing_payslip()
    try:
        before, d0 = grace_now()
        check("baseline: the engine waits the published grace period (20 min) after the customer leaves",
              before is not None and round(before) == 20 and d0["action"] in ("WAIT", "SCHEDULE_CALL"), f"{before} min · {d0['action']}")

        # 1–3: grace 20 → 30, simulated, published
        r = draft_with(lambda cfg: cfg["followup"].__setitem__("abandonment_grace_minutes", 30))
        draft = r.json()
        sim = c.post(f"{ADMIN}/policy/simulate", json={"config": draft["config"], "version_id": draft["version_id"]}).json()
        own = c.post(f"{ADMIN}/policy/as-configured", json={"config": draft["config"], "version_id": draft["version_id"]}).json()
        s05 = next(x for x in sim["results"] if x["scenario_id"] == "S05")
        shift = (datetime.fromisoformat(own["S05"]["decision"]["next_eligible_at"])
                 - datetime.fromisoformat(s05["actual"]["next_eligible_at"])).total_seconds() / 60
        check("simulate grace 30: every mandatory scenario passes, and the draft's own decision shows the 10 extra minutes",
              r.status_code == 200 and sim["mandatory_passed"] and shift == 10, f"mandatory_passed={sim['mandatory_passed']} shift={shift}")
        pub = publish(draft)
        check("publish grace 30", pub.status_code == 200 and pub.json().get("simulation_run_id"), str(pub.status_code))
        after, d1 = grace_now()
        view = c.get(f"/api/banker/cases/{CASE}/followup").json()
        check("the running engine now waits 30 minutes, under the newly published version",
              after is not None and round(after) == 30 and d1["policy_version"] == pub.json()["published"]["label"],
              f"{after} min · {d1['policy_version']} · banker view {view.get('policy_version') or view.get('plan', {}).get('policy_version')}")

        # 4–5: call window within the bank's bounds
        r = draft_with(lambda cfg: cfg["followup"]["call_window"].update({"from": "10:00", "to": "19:00"}))
        pub = publish(r.json()) if r.status_code == 200 else r
        check("publish a call window of 10:00–19:00 (inside the 08:00–20:00 envelope)", pub.status_code == 200, str(pub.status_code))

        # 6: invalid configurations are refused
        refusals = {}
        for name, change in {
            "window to 21:00": lambda cfg: cfg["followup"]["call_window"].update({"to": "21:00"}),
            "Saturday calls": lambda cfg: cfg["followup"]["call_window"]["days"].append("SAT"),
            "5 attempts per case": lambda cfg: cfg["followup"].__setitem__("max_attempts_per_case", 5),
            "1 hour between calls": lambda cfg: cfg["followup"].__setitem__("min_hours_between_calls", 1),
            "grace 0": lambda cfg: cfg["followup"].__setitem__("abandonment_grace_minutes", 0),
            "locked scope": lambda cfg: cfg["scope"].__setitem__("environment", "prod"),
        }.items():
            discard_open()
            r = draft_with(change)
            refusals[name] = r.status_code if r.status_code != 200 else publish(r.json()).status_code
        discard_open()
        check("invalid or unsafe configurations are refused at save or at publish", all(v == 422 for v in refusals.values()),
              str(refusals))

        # 7: the hard guards hold on the published, edited policy
        sim = c.post(f"{ADMIN}/policy/simulate", json={"version_id": None}).json()
        rules = c.get(f"{ADMIN}/settings").json()["rule_labels"]
        guards = [x for x in sim["results"] if any(rules.get(b, {}).get("tier") == "HARD_GUARD" for b in x["expected"]["blocked_by_include"])]
        names = sorted({b for x in guards for b in x["expected"]["blocked_by_include"]})
        check("presence, upload-in-flight, consent, kill switch, banker pause and the other hard guards still block",
              guards and all(x["passed"] for x in guards) and {"HG-ACTIVE-SESSION", "HG-IN-FLIGHT", "HG-NO-CONSENT",
                                                               "HG-KILL-SWITCH", "HG-BANKER-PAUSE"} <= set(names),
              f"{len(guards)} guard scenarios · {', '.join(names)}")

        # rollback
        rb = c.post(f"{ADMIN}/rollback", json={"kind": "loan_policy", "to_version_id": start["version_id"], "reason": "acceptance: restore"})
        back, d2 = grace_now()
        check("rollback publishes the starting configuration again and the engine is back to 20 minutes",
              rb.status_code == 200 and back is not None and round(back) == 20, f"{rb.status_code} · {back} min · {d2['policy_version']}")
    finally:
        now = c.get(f"{ADMIN}/settings").json()["published"]["loan_policy"]
        if now["config"] != start["config"]:
            c.post(f"{ADMIN}/rollback", json={"kind": "loan_policy", "to_version_id": start["version_id"], "reason": "acceptance: restore"})
        discard_open()
        c.post("/api/demo/clock", json={"reset": True})
    passed = sum(ok for _, ok, _ in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} policy acceptance checks passed · isolated REPLAY stack")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
