"""Live end-to-end journey against a running backend (real Gemini calls, synthetic documents).

Usage:  backend/.venv/bin/python backend/tests/live_journey.py [--scene initial|correction|negative|all] [--reset]
Prints document verdicts, criteria and case findings so a run is auditable."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8791"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "e2e"))
import demo_auth  # noqa: E402
demo_auth.install(BASE)                                  # the service has no anonymous access
CASE = "DEMO-MTZ-2026-001"
FIX = Path(__file__).resolve().parents[2] / "fixtures" / "out"
MANIFEST = json.loads((FIX / "manifest.json").read_text(encoding="utf8"))


def wait_idle(client: httpx.Client, timeout: float = 600) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        snap = client.get(f"{BASE}/api/cases/{CASE}").json()
        if snap["readiness"]["pending_jobs"] or snap["readiness"]["state"] in ("CHECKING", "RECHECKING"):
            time.sleep(2)
            continue
        return snap
    raise TimeoutError("backend did not settle")


def upload(client: httpx.Client, entry: dict, case: str | None = None) -> dict:
    case = case or CASE
    path = FIX / entry["file"]
    with path.open("rb") as fh:
        r = client.post(f"{BASE}/api/cases/{case}/documents", files={"file": (path.name, fh, "application/pdf")},
                        data={"borrower_id": entry["upload_as"]})
    r.raise_for_status()
    return r.json()["document"]


def report(client: httpx.Client) -> None:
    docs = client.get(f"{BASE}/api/cases/{CASE}/documents").json()
    for d in docs:
        r = d.get("review") or {}
        print(f"\n■ {d['filename']}  [{d['status']}]  verdict={r.get('verdict')}  type={r.get('doc_type')}  "
              f"period={r.get('period')}  file_name={r.get('file_name_period')}  scanned={r.get('is_scanned')}  "
              f"usage={r.get('usage')}")
        for f in r.get("facts", []):
            e = f.get("evidence") or {}
            if f["field"] in ("employee_name", "employee_id", "salary_period", "gross_pay", "net_pay"):
                print(f"    {f['field']:<14} {str(f['value_raw']):<22} {e.get('witness')}")
        for c in r.get("criteria", []):
            if c["outcome"] != "PASS":
                print(f"    ✗ {c['criterion_id']} {c['outcome']:<12} {c['explanation_he'][:110]}")
    snap = client.get(f"{BASE}/api/cases/{CASE}").json()
    print("\nREADINESS:", snap["readiness"]["state"], snap["readiness"]["counts"])
    for f in snap["findings"]:
        print(f"  [{f['status']:<9}] {f['review_state']:<24} {f['key']:<52} {f['title_he']}")
    cr = snap.get("case_review") or {}
    for bid, inc in (cr.get("income") or {}).items():
        print("  income", bid, {k: inc.get(k) for k in ("declared_net_monthly_ils", "average_documented_net_ils", "difference_pct")})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="initial")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--case", default=CASE)
    args = ap.parse_args()
    globals()["CASE"] = args.case
    with httpx.Client(timeout=60) as client:
        if args.reset:
            client.post(f"{BASE}/api/cases/{CASE}/reset").raise_for_status()
        scenes = ["initial", "correction"] if args.scene == "all" else [args.scene]
        for scene in scenes:
            started = time.time()
            for entry in MANIFEST["files"]:
                if entry["scene"] == scene:
                    d = upload(client, entry)
                    print(f"uploaded {entry['file']} → {d['document_id']} ({d['status']})")
            wait_idle(client)
            print(f"\n=== scene {scene} settled in {time.time() - started:.1f}s ===")
            report(client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
