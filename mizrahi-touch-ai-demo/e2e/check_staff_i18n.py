"""English coverage of the staff responses (banker console, presenter pane, system page): which Hebrew texts the staff
catalogue (backend/app/i18n/staff_catalog/*.json) does not translate yet. Read-only, zero Gemini calls.

It fetches each staff response in Hebrew from a running backend (GETs only; the banker's conversation route is
read-only) and translates it here, in this process, with the catalogue on disk — so a catalogue edit shows without
restarting the server. Point DATA_DIR at the backend's data so requirement titles resolve from its published policy.

    # from mizrahi-touch-ai-demo/
    DATA_DIR=e2e/artifacts/loan/data-replay backend/.venv/bin/python e2e/check_staff_i18n.py http://127.0.0.1:8792 [area …]
    # areas: cases package workspace intelligence followup timeline scenarios rubrics (default: all)
    # --list prints every missing text with the key it sits under; --json FILE writes them
"""
from __future__ import annotations

import collections
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATA_DIR", str(ROOT / "e2e" / "artifacts" / "loan" / "data-replay"))
os.environ["DATA_DIR"] = str(Path(os.environ["DATA_DIR"]).resolve())
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from app.i18n import staff_en  # noqa: E402

OUT = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
args = [a for a in sys.argv[1:] if not a.startswith("--") and a != OUT]
BASE = args[0] if args else "http://127.0.0.1:8792"
AREAS = set(args[1:]) or {"cases", "package", "workspace", "intelligence", "followup", "timeline", "scenarios", "rubrics"}
LIST = "--list" in sys.argv

c = httpx.Client(base_url=BASE, timeout=60)
c.headers["Authorization"] = "Bearer " + c.post("/api/session/demo/staff", json={}).json()["token"]
missing: dict[str, dict[str, set[str]]] = collections.defaultdict(lambda: collections.defaultdict(set))
seen: collections.Counter = collections.Counter()


def walk(o, path: str, area: str) -> None:
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(k, str) and (k in staff_en.SKIP_TREES or k in staff_en.SKIP_KEYS or staff_en._is_english_key(k)):
                continue
            walk(v, f"{path}.{k}", area)
    elif isinstance(o, list):
        for v in o:
            walk(v, f"{path}[]", area)
    elif isinstance(o, str) and staff_en.HE.search(o):
        seen[area] += 1
        if staff_en.translate(o) is None:
            missing[area][o].add(path)


def get(area: str, url: str):
    if area not in AREAS and area != "_":
        return None
    r = c.get(url)
    if r.status_code != 200:
        print("!", r.status_code, url)
        return None
    j = r.json()
    if area != "_":
        walk(j, "", area)
    return j


rows = c.get("/api/banker/cases").json()
if "cases" in AREAS:
    walk(rows, "", "cases")
for row in rows:
    cid = row["case_id"]
    for area in ("package", "workspace", "intelligence", "followup", "timeline"):
        get(area, f"/api/banker/cases/{cid}/{area}")
get("scenarios", "/api/presenter/scenarios")
get("rubrics", "/api/system/rubrics")

total_missing = 0
for area in sorted(seen):
    m = missing.get(area, {})
    total_missing += len(m)
    print(f"{area:13} {seen[area]:6} Hebrew texts · {len(m):4} distinct without English")
    if LIST:
        for text, paths in sorted(m.items(), key=lambda kv: sorted(kv[1])[0]):
            print(f"    {sorted(paths)[0][:70]:70} {text[:200]!r}")
if OUT:
    Path(OUT).write_text(json.dumps({a: {t: sorted(p) for t, p in m.items()} for a, m in missing.items()},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{total_missing} distinct texts without English")
