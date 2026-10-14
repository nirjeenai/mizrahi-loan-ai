"""Admin Settings (/admin) — browser checks in a real Chrome against an isolated stack (Agent C: :8797, own DATA_DIR).

    . AGENT_ENV.sh && backend/.venv/bin/python e2e/test_admin_ui.py         # ADMIN_BASE defaults to $MZ_API
    ADMIN_BASE=http://127.0.0.1:8797 backend/.venv/bin/python e2e/test_admin_ui.py

The demo admin edits the grace period, saves a draft, sees the diff, publishes, sees the version list update, rolls
back, toggles the kill switch, and sees the prompt lint and the envelope refusal. No Gemini call is made. The suite
ends by restoring the configuration that was active when it started (a rollback, so the history shows it) and the
kill switch. Never run it against :8791 or another agent's stack."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("ADMIN_BASE") or os.environ.get("MZ_API") or "http://127.0.0.1:8797"
API = f"{BASE}/api/admin/loan-completion"
ART = Path(__file__).resolve().parent / "artifacts" / "agent-c"
RESULTS: list[tuple[str, bool, str]] = []
if any(p in BASE for p in (":8790", ":8791", ":8796", ":8798", ":8801")):
    sys.exit(f"refusing to run against {BASE}: not Agent C's stack")


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(ART / f"{name}.png"), full_page=False)


def settings(page: Page) -> dict:
    return page.request.get(f"{API}/settings").json()


def tab(page: Page, key: str) -> None:
    page.get_by_test_id(f"tab-{key}").click()
    expect(page.get_by_test_id(f"tab-body-{key}")).to_be_visible()


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="he-IL")
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/admin")
        expect(page.get_by_test_id("admin-page")).to_be_visible(timeout=15000)
        start = settings(page)
        v0 = start["published"]["loan_policy"]
        grace0 = v0["config"]["followup"]["abandonment_grace_minutes"]
        for kind in ("loan_policy", "talk_prompt"):                  # start from a clean slate
            if start["drafts"][kind]:
                page.request.post(f"{API}/drafts/{start['drafts'][kind]['version_id']}/discard",
                                  data={"revision": start["drafts"][kind]["revision"]})
        if start["kill_switch"]["value"]:
            page.request.post(f"{API}/followups/pause", data={"paused": False, "reason": "e2e start"})
        page.reload()
        expect(page.get_by_test_id("admin-page")).to_be_visible()
        check("environment banner", "סביבת הדגמה · נתונים סינתטיים" in page.get_by_test_id("env-banner").inner_text())
        check("no persona switcher, demo staff session", "מחובר/ת:" in page.locator(".console-top").inner_text())
        shot(page, "01-documents")

        # 1. edit the grace period and save a draft
        tab(page, "followup")
        new_grace = grace0 + 10
        page.get_by_test_id("f-abandonment_grace_minutes").fill(str(new_grace))
        expect(page.get_by_test_id("save-loan_policy")).to_be_enabled()
        page.get_by_test_id("save-loan_policy").click()
        expect(page.get_by_test_id("draft-chip-loan_policy")).to_be_visible(timeout=10000)
        s = settings(page)
        check("draft saved, not active", s["drafts"]["loan_policy"] is not None
              and s["published"]["loan_policy"]["version_id"] == v0["version_id"]
              and s["published"]["loan_policy"]["config"]["followup"]["abandonment_grace_minutes"] == grace0)
        page.get_by_test_id("diff-toggle-loan_policy").click()
        check("inline diff shows the field", "followup.abandonment_grace_minutes" in page.get_by_test_id("actions-loan_policy").inner_text())
        check("locked guards shown read-only", "HG-KILL-SWITCH" in page.get_by_test_id("locked-rules").inner_text())
        shot(page, "02-followup-draft")

        # 2. the diff in the test-and-versions tab
        tab(page, "versions")
        diff_text = page.get_by_test_id("pending-diff-loan_policy").inner_text()
        check("diff in versions tab", "followup.abandonment_grace_minutes" in diff_text and str(new_grace) in diff_text)
        shot(page, "03-versions-diff")

        # 3. simulate the draft through every scenario fixture of the follow-up engine
        page.get_by_test_id("simulate").click()
        expect(page.get_by_test_id("sim-summary")).to_be_visible(timeout=15000)
        fixtures = page.get_by_test_id("sim-table").locator("tbody tr").count()
        run = page.request.post(f"{API}/policy/simulate", data={"config": s["drafts"]["loan_policy"]["config"]}).json()
        check("simulator runs every fixture", fixtures == len(run["results"]) > 0, f"{fixtures} scenarios")
        mandatory_failed = [r["scenario_id"] for r in run["results"] if r["mandatory"] and not r["passed"]]
        shot(page, "04-simulation")
        expected, edited = new_grace, "abandonment_grace_minutes"

        # 4. publish (same admin, no approval step); a draft that breaks a mandatory scenario is refused (AC 18)
        if mandatory_failed:
            page.get_by_test_id("publish-loan_policy").first.click()
            page.get_by_test_id("confirm-publish-loan_policy").first.click()
            expect(page.get_by_test_id("reasons-loan_policy").first).to_contain_text("תרחיש חובה", timeout=10000)
            check("publish gate refuses a draft that breaks mandatory scenarios",
                  settings(page)["published"]["loan_policy"]["version_id"] == v0["version_id"], ", ".join(mandatory_failed))
            print(f"NOTE · the grace edit breaks fixtures {mandatory_failed}; until Agent B pins their config values in "
                  "policy_overrides, the suite publishes a change no fixture depends on", flush=True)
            shot(page, "04b-gate-refused")
            tab(page, "followup")
            page.get_by_test_id("f-abandonment_grace_minutes").fill(str(grace0))
            spacing = v0["config"]["followup"]["min_hours_between_calls"] + 24
            page.get_by_test_id("f-min_hours_between_calls").fill(str(spacing))
            expected, edited = spacing, "min_hours_between_calls"
            tab(page, "versions")
        page.get_by_test_id("publish-loan_policy").first.click()
        page.get_by_test_id("confirm-publish-loan_policy").first.click()
        expect(page.get_by_test_id("published-loan_policy")).not_to_contain_text(f"v{v0['number']}", timeout=10000)
        s = settings(page)
        v1 = s["published"]["loan_policy"]
        v1_number = v1["number"]
        check("published: the engine's version moved", v1["version_id"] != v0["version_id"]
              and v1["config"]["followup"][edited] == expected and s["drafts"]["loan_policy"] is None, edited)
        row = page.get_by_test_id(f"version-loan_policy-{v1_number}")
        expect(row).to_contain_text("פעילה")
        check("version list updated", "פעילה" in row.inner_text()
              and "בארכיון" in page.get_by_test_id(f"version-loan_policy-{v0['number']}").inner_text())
        shot(page, "04-published")

        # 4. roll back to the version that was active before
        page.get_by_test_id(f"rollback-loan_policy-{v0['number']}").click()
        page.get_by_test_id("rollback-go-loan_policy").click()
        expect(page.get_by_test_id("published-loan_policy")).not_to_contain_text(f"v{v1_number}", timeout=10000)
        s = settings(page)
        v2 = s["published"]["loan_policy"]
        check("rollback publishes a new version with the old config", v2["number"] > v1_number
              and v2["config"] == v0["config"] and v2["based_on"] == v0["version_id"])
        audit = page.get_by_test_id("audit").inner_text()
        check("audit lists each step", all(x in audit for x in ("טיוטה נשמרה", "מדיניות הופעלה", "שחזור גרסה")))
        shot(page, "05-rolled-back")

        # 5. kill switch
        tab(page, "followup")
        page.get_by_test_id("kill-toggle").click()
        expect(page.get_by_test_id("kill-chip")).to_be_visible(timeout=10000)
        check("kill switch on", settings(page)["kill_switch"]["value"] is True)
        shot(page, "06-kill-switch-on")
        page.get_by_test_id("kill-toggle").click()
        expect(page.get_by_test_id("kill-chip")).to_have_count(0, timeout=10000)
        check("kill switch off", settings(page)["kill_switch"]["value"] is False)

        # 6. envelope refusal (S39): calling before 08:00 can't be published
        page.get_by_test_id("w-from").fill("07:00")
        expect(page.get_by_test_id("actions-loan_policy")).to_contain_text("שגיאות", timeout=10000)
        check("envelope error blocks publish", page.get_by_test_id("publish-loan_policy").is_disabled()
              and "08:00" in page.get_by_test_id("tab-body-followup").inner_text())
        shot(page, "07-envelope-error")
        page.get_by_test_id("discard-loan_policy").click()
        expect(page.get_by_test_id("w-from")).to_have_value(v0["config"]["followup"]["call_window"]["from"], timeout=10000)

        # 7. prompt lint and preview (S38)
        tab(page, "prompt")
        box = page.get_by_test_id("prompt-instructions")
        original = box.input_value()
        box.fill(original + " התקשרי מיד, ההלוואה אושרה.")
        expect(page.get_by_test_id("lint-instructions")).to_be_visible(timeout=10000)
        lint = page.get_by_test_id("lint-instructions").inner_text()
        check("prompt lint warns", "התקשרי מיד" in lint and "ההלוואה אושרה" in lint)
        check("opening is locked", page.get_by_test_id("opening-locked").is_visible()
              and page.locator("[data-testid=opening-locked] textarea, [data-testid=opening-locked] input").count() == 0)
        check("preview uses synthetic values", "תלוש שכר לספטמבר 2026" in page.get_by_test_id("tab-body-prompt").inner_text())
        shot(page, "08-prompt-lint")
        page.get_by_test_id("discard-talk_prompt").click()
        expect(box).to_have_value(original, timeout=10000)

        tab(page, "documents")
        shot(page, "09-documents")
        end = settings(page)
        check("ends on the starting configuration", end["published"]["loan_policy"]["config"] == v0["config"]
              and end["drafts"] == {"loan_policy": None, "talk_prompt": None} and end["kill_switch"]["value"] is False)
        browser.close()
    # the refused publish is an expected 422 that the page handles; the browser still logs the failed request
    real = [e for e in errors if "favicon" not in e and "status of 422" not in e]
    check("no console errors", not real, "; ".join(real[:3]))
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed · screenshots in {ART}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
