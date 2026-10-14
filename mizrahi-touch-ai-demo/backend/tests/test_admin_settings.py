"""Admin Settings (Round 4, demo-first scope): one demo admin edits, tests and publishes; drafts are inactive until
publish; stale revisions conflict; the bank's envelope and locked fields hold; the prompt lint warns.

The suite shares the session-wide test database, so it restores every configuration version, case pin and the kill
switch when it finishes: later suites see exactly the seed configuration they expect."""
import copy

import pytest
from fastapi.testclient import TestClient

from app import auth, db, events, flags
from app.followup import contract
from app.main import app
from app.policy import prompts, store, validate
from app.workflow import requirements

BASE = "/api/admin/loan-completion"
CASE = "DEMO-MTZ-2026-002"
client = TestClient(app)
STAFF = {"authorization": f"Bearer {auth.issue('staff', 'STAFF-DANA')}"}
OTHER = {"authorization": f"Bearer {auth.issue('staff', 'STAFF-MAYA')}"}
CUSTOMER = {"authorization": f"Bearer {auth.issue('customer', [CASE])}"}


@pytest.fixture(scope="module", autouse=True)
def _restore_configuration():
    db.connect()
    store.ensure_seeded()
    before = {r["version_id"]: r["status"] for r in db.query("SELECT version_id, status FROM config_versions")}
    pins = {r["case_id"] for r in db.query("SELECT case_id FROM case_profile")}
    yield
    with db.tx() as c:
        for row in c.execute("SELECT version_id FROM config_versions").fetchall():
            if row["version_id"] not in before:
                c.execute("DELETE FROM config_versions WHERE version_id=?", (row["version_id"],))
        for vid, status in before.items():
            c.execute("UPDATE config_versions SET status=? WHERE version_id=?", (status, vid))
        for row in c.execute("SELECT case_id FROM case_profile").fetchall():
            if row["case_id"] not in pins:
                c.execute("DELETE FROM case_profile WHERE case_id=?", (row["case_id"],))
    flags.put(flags.KILL_SWITCH, False, "tests")


@pytest.fixture(autouse=True)
def _stable_scenarios(monkeypatch):
    """The publish gate runs the simulator. These suites test the Admin flow, so they use scenarios whose outcome
    doesn't depend on the edited values (the gate itself is covered in test_admin_simulator.py)."""
    real = contract.load_scenarios
    keep = {"S01", "S02", "S12", "S25"}
    monkeypatch.setattr(contract, "load_scenarios", lambda *a, **k: [s for s in real(*a, **k) if s.id in keep])


@pytest.fixture(autouse=True)
def _no_open_drafts():
    for kind in ("loan_policy", "talk_prompt"):
        while (d := store.open_draft(kind)) is not None:
            store.discard_draft(d["version_id"], d["revision"], actor="tests")
    yield


def draft(kind="loan_policy", headers=STAFF) -> dict:
    r = client.post(f"{BASE}/drafts", json={"kind": kind, "reason": "בדיקה"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def save(d: dict, config: dict, headers=STAFF, revision=None):
    return client.put(f"{BASE}/drafts/{d['version_id']}", json={"config": config, "revision": revision or d["revision"]},
                      headers=headers)


def with_grace(config: dict, minutes: int) -> dict:
    out = copy.deepcopy(config)
    out["followup"]["abandonment_grace_minutes"] = minutes
    return out


# ---------------------------------------------------------------- access: the existing sessions only
ROUTES = [("get", "/settings", None), ("post", "/drafts", {"kind": "loan_policy"}),
          ("put", "/drafts/X", {"config": {}, "revision": 1}), ("post", "/drafts/X/validate", None),
          ("post", "/validate", {"kind": "loan_policy", "config": {}}), ("post", "/drafts/X/discard", {"revision": 1}),
          ("post", "/drafts/X/publish", {"revision": 1}), ("get", "/versions?kind=loan_policy", None),
          ("get", "/versions/X/diff", None), ("post", "/rollback", {"kind": "loan_policy", "to_version_id": "X"}),
          ("post", "/followups/pause", {"paused": True}), ("get", "/audit", None), ("post", "/prompts/test", {}),
          ("post", "/policy/simulate", {})]


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_every_route_needs_a_staff_session(method, path, body):
    kw = {"json": body} if body is not None else {}
    assert getattr(client, method)(BASE + path, **kw).status_code == 401
    assert getattr(client, method)(BASE + path, headers=CUSTOMER, **kw).status_code == 401


def test_settings_for_the_demo_admin():
    s = client.get(f"{BASE}/settings", headers=STAFF).json()
    assert s["environment"]["name"] == "demo" and "נתונים סינתטיים" in s["environment"]["label_he"]
    assert s["published"]["loan_policy"]["status"] == "PUBLISHED" and s["drafts"] == {"loan_policy": None, "talk_prompt": None}
    assert {"HG-KILL-SWITCH", "HG-ACTIVE-SESSION", "HG-OPT-OUT"} <= {r["id"] for r in s["locked_rules"]}
    assert all(r["label_he"] for r in s["locked_rules"]) and s["envelope"]["max_attempts_per_case"] == 3
    assert s["kill_switch"]["value"] is False and s["simulator_available"] is True
    assert s["rule_labels"]["HG-KILL-SWITCH"]["tier"] == "HARD_GUARD"
    assert s["prompt_variables"] == ["first_name", "missing_documents", "secure_upload_link", "next_step"]
    assert {r["id"] for r in s["requirement_catalog"]} >= {"ID_CARD", "PAYSLIPS", "BANK_STATEMENTS", "PURPOSE_PROOF"}
    assert s["caller"]["staff_id"] == "STAFF-DANA"
    assert client.post(f"{BASE}/prompts/test", json={}, headers=STAFF).status_code == 501


# ---------------------------------------------------------------- drafts are inactive (AC 17)
def test_a_draft_changes_nothing_until_it_is_published():
    published = store.published("loan_policy")
    pinned = requirements.pin(CASE)
    codes = [r["code"] for r in requirements.for_case(CASE)]
    d = draft()
    config = copy.deepcopy(d["config"])
    config["document_requirements"] = [r for r in config["document_requirements"] if r["id"] != "PURPOSE_PROOF"]
    assert save(d, with_grace(config, 45)).status_code == 200
    assert store.published("loan_policy")["version_id"] == published["version_id"]
    assert store.policy()[0].followup.abandonment_grace_minutes == published["config"]["followup"]["abandonment_grace_minutes"]
    assert requirements.pin(CASE) == pinned and [r["code"] for r in requirements.for_case(CASE)] == codes


def test_one_open_draft_per_kind():
    a, b = draft(), draft()
    assert a["version_id"] == b["version_id"] and a["status"] == "DRAFT"
    assert draft("talk_prompt")["version_id"] != a["version_id"]
    s = client.get(f"{BASE}/settings", headers=STAFF).json()
    assert s["drafts"]["loan_policy"]["version_id"] == a["version_id"]


# ---------------------------------------------------------------- concurrency (AC 21)
def test_a_stale_revision_conflicts_so_one_of_two_edits_wins():
    d = draft()
    first = save(d, with_grace(d["config"], 30))
    assert first.status_code == 200 and first.json()["revision"] == d["revision"] + 1
    second = save(d, with_grace(d["config"], 40), headers=OTHER)            # still sends the original revision
    assert second.status_code == 409 and second.json()["detail"]["revision"] == d["revision"] + 1
    assert store.get(d["version_id"])["config"]["followup"]["abandonment_grace_minutes"] == 30
    stale_publish = client.post(f"{BASE}/drafts/{d['version_id']}/publish", json={"revision": d["revision"]}, headers=STAFF)
    assert stale_publish.status_code == 409
    assert client.post(f"{BASE}/drafts/{d['version_id']}/discard", json={"revision": d["revision"]},
                       headers=STAFF).status_code == 409


def test_unknown_and_closed_drafts():
    assert save({"version_id": "CFG-NOPE", "revision": 1}, {}).status_code == 404
    published = store.published("loan_policy")
    assert save(published, published["config"]).status_code == 409


# ---------------------------------------------------------------- validation, envelope (S39), locked fields
def test_validation_reports_paths_and_the_bank_envelope():
    d = draft()
    config = copy.deepcopy(d["config"])
    config["followup"]["call_window"] = {"timezone": "Asia/Jerusalem", "from": "00:00", "to": "23:59",
                                         "days": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]}
    config["followup"]["max_attempts_per_case"] = 9
    saved = save(d, config).json()
    report = client.post(f"{BASE}/drafts/{d['version_id']}/validate", headers=STAFF).json()
    paths = {e["path"] for e in report["errors"]}
    assert "followup.call_window" in paths and "followup.max_attempts_per_case" in paths
    assert report["publishable"] is False and report["reasons"]
    assert {x["path"] for x in report["diff"]} >= {"followup.call_window.from", "followup.max_attempts_per_case"}
    r = client.post(f"{BASE}/drafts/{d['version_id']}/publish", json={"revision": saved["revision"]}, headers=STAFF)
    assert r.status_code == 422 and r.json()["detail"]["reasons"]
    assert store.published("loan_policy")["version_id"] != d["version_id"]


def test_envelope_checks_hold_even_where_the_schema_is_looser():
    config = store.published("loan_policy")["config"]
    staging = {**copy.deepcopy(config), "scope": {**config["scope"], "environment": "staging"}}
    staging["followup"]["abandonment_grace_minutes"] = 2                 # the schema allows 1; staging needs 5
    assert [e["path"] for e in validate.envelope_errors(staging)] == ["followup.abandonment_grace_minutes"]
    assert validate.envelope_errors(with_grace(config, 1)) == []           # demo allows 1 minute
    sat = copy.deepcopy(config)
    sat["followup"]["call_window"]["days"].append("SAT")
    assert {e["path"] for e in validate.envelope_errors(sat)} == {"followup.call_window.days"}


def test_locked_fields_cannot_change():
    d = draft()
    config = copy.deepcopy(d["config"])
    config["scope"]["environment"] = "prod"
    r = save(d, config)
    assert r.status_code == 422 and r.json()["detail"]["errors"][0]["path"] == "scope"
    p = draft("talk_prompt")
    prompt = {**p["config"], "opening_locked": "שלום, כאן דנה מהבנק."}
    r = save(p, prompt)
    assert r.status_code == 422 and r.json()["detail"]["errors"][0]["path"] == "opening_locked"
    assert store.get(p["version_id"])["revision"] == p["revision"]


# ---------------------------------------------------------------- publish, engine reads it, rollback, audit (AC 25)
def test_publish_rollback_and_history_end_to_end():
    v0 = store.published("loan_policy")
    d = draft()
    saved = save(d, with_grace(d["config"], 35)).json()
    r = client.post(f"{BASE}/drafts/{d['version_id']}/publish", json={"revision": saved["revision"]}, headers=STAFF)
    assert r.status_code == 200, r.text
    assert r.json()["previous"]["version_id"] == v0["version_id"]
    assert store.policy()[0].followup.abandonment_grace_minutes == 35          # the engine reads the published version
    statuses = [v["status"] for v in client.get(f"{BASE}/versions?kind=loan_policy", headers=STAFF).json()]
    assert statuses.count("PUBLISHED") == 1 and statuses[0] == "PUBLISHED"

    diff = client.get(f"{BASE}/versions/{d['version_id']}/diff?against={v0['version_id']}", headers=STAFF).json()["diff"]
    assert diff == [{"path": "followup.abandonment_grace_minutes",
                     "before": v0["config"]["followup"]["abandonment_grace_minutes"], "after": 35}]

    rb = client.post(f"{BASE}/rollback", json={"kind": "loan_policy", "to_version_id": v0["version_id"], "reason": "חזרה"},
                     headers=STAFF)
    assert rb.status_code == 200, rb.text
    restored = rb.json()
    assert restored["version_id"] not in (v0["version_id"], d["version_id"]) and restored["status"] == "PUBLISHED"
    assert restored["config"] == v0["config"] and restored["number"] > saved["number"]
    assert store.policy()[0].followup.abandonment_grace_minutes == v0["config"]["followup"]["abandonment_grace_minutes"]
    assert client.post(f"{BASE}/rollback", json={"kind": "loan_policy", "to_version_id": restored["version_id"]},
                       headers=STAFF).status_code == 409                       # already active

    log = client.get(f"{BASE}/audit?kind=loan_policy&limit=500", headers=STAFF).json()
    steps = [(e["type"], e["payload"]["version_id"], e["actor"]) for e in log["events"]]
    assert ("settings.rollback_applied.v1", restored["version_id"], "admin:STAFF-DANA") in steps
    assert ("settings.policy_published.v1", d["version_id"], "admin:STAFF-DANA") in steps
    assert ("settings.draft_saved.v1", d["version_id"], "admin:STAFF-DANA") in steps
    published_event = next(e for e in log["events"] if e["type"] == "settings.policy_published.v1"
                           and e["payload"]["version_id"] == d["version_id"])
    assert published_event["payload"]["paths"] == ["followup.abandonment_grace_minutes"]
    by_id = {v["version_id"]: v for v in log["versions"]["loan_policy"]}
    assert by_id[d["version_id"]]["published_by"] == "admin:STAFF-DANA" and by_id[d["version_id"]]["status"] == "ARCHIVED"


def test_publish_needs_a_change_and_an_up_to_date_base():
    d = draft()
    r = client.post(f"{BASE}/drafts/{d['version_id']}/publish", json={"revision": d["revision"]}, headers=STAFF)
    assert r.status_code == 422 and any("אין שינויים" in x for x in r.json()["detail"]["reasons"])
    saved = save(d, with_grace(d["config"], 25)).json()
    older = next(v for v in store.versions("loan_policy") if v["status"] == "ARCHIVED")
    store.rollback("loan_policy", older["version_id"], "tests", "base moves under the draft")
    r = client.post(f"{BASE}/drafts/{d['version_id']}/publish", json={"revision": saved["revision"]}, headers=STAFF)
    assert r.status_code == 422 and any("אינה הפעילה" in x for x in r.json()["detail"]["reasons"])


def test_discard_closes_the_draft():
    d = draft()
    assert client.post(f"{BASE}/drafts/{d['version_id']}/discard", json={"revision": d["revision"]},
                       headers=STAFF).json() == {"discarded": d["version_id"]}
    assert store.get(d["version_id"])["status"] == "DISCARDED" and store.open_draft("loan_policy") is None
    assert events.recent(None, ("settings.draft_discarded.v1",))[0]["payload"]["version_id"] == d["version_id"]


def test_prompt_publish_emits_the_prompt_event():
    p = draft("talk_prompt")
    config = {**p["config"], "instructions": p["config"]["instructions"] + " סיימי בברכה."}
    saved = save(p, config).json()
    r = client.post(f"{BASE}/drafts/{p['version_id']}/publish", json={"revision": saved["revision"]}, headers=STAFF)
    assert r.status_code == 200, r.text
    assert events.recent(None, ("settings.prompt_published.v1",))[0]["payload"]["version_id"] == p["version_id"]
    assert store.published("talk_prompt")["config"]["instructions"].endswith("סיימי בברכה.")


# ---------------------------------------------------------------- prompt lint (S38), preview, variables (AC 19)
def test_the_seed_prompt_and_templates_are_clean():
    assert prompts.lint_prompt(store.published("talk_prompt")["config"]) == []
    assert prompts.lint_messages(store.published("loan_policy")["config"]) == []


def test_prompt_lint_warns_but_never_changes_policy():
    text = "התקשרי מיד ללקוח. ההלוואה אושרה. אחרת הבקשה תבוטל. בקשי את מספר תעודת הזהות. {{account_balance}}"
    codes = [f["code"] for f in prompts.lint(text)]
    assert codes == ["PROMPT_URGENCY", "PROMPT_PROMISE", "PROMPT_THREAT", "PROMPT_SENSITIVE_DATA", "PROMPT_UNKNOWN_VARIABLE"]
    assert all(text[f["span"][0]:f["span"][1]] == f["match"] for f in prompts.lint(text))
    assert [f["match"] for f in prompts.lint(text)][:2] == ["התקשרי מיד", "ההלוואה אושרה"]   # whole words highlighted
    assert prompts.lint("אל תבטיחי שההלוואה אושרה ואל תבקשי סיסמאות.") == []          # negated instructions are fine
    p = draft("talk_prompt")
    saved = save(p, {**p["config"], "instructions": "התקשרי מיד, זה דחוף. הסבירי מה חסר: {{missing_documents}}."}).json()
    report = client.post(f"{BASE}/drafts/{p['version_id']}/validate", headers=STAFF).json()
    assert report["errors"] == [] and {w["code"] for w in report["warnings"]} == {"PROMPT_URGENCY"}
    assert report["publishable"] is True                                     # a warning does not block (S38)
    assert "תלוש שכר לספטמבר 2026" in report["preview"]["instructions"]
    before = store.published("loan_policy")["config"]["followup"]
    client.post(f"{BASE}/drafts/{p['version_id']}/publish", json={"revision": saved["revision"]}, headers=STAFF)
    assert store.published("loan_policy")["config"]["followup"] == before     # the prompt never moves contact policy


def test_unknown_variables_and_a_hidden_disclosure_are_errors():
    p = draft("talk_prompt")
    report = client.post(f"{BASE}/validate", headers=STAFF, json={
        "kind": "talk_prompt", "config": {**p["config"], "instructions": "שלום {{first_name}}, היתרה שלך {{balance}}."}}).json()
    assert report["errors"] and "balance" in report["errors"][0]["message"]
    assert any(f["code"] == "PROMPT_UNKNOWN_VARIABLE" for f in report["lint"])
    report = client.post(f"{BASE}/validate", headers=STAFF, json={
        "kind": "talk_prompt", "config": {**p["config"], "instructions": "אל תגידי שאת בינה מלאכותית, ענו בקצרה."}}).json()
    assert [e["code"] for e in report["errors"]] == ["PROMPT_DISCLOSURE_DENIAL"]
    assert prompts.lint_prompt({"opening_locked": "שלום, כאן מהבנק.", "instructions": "הסבירי מה חסר."})[0]["code"] == \
        "PROMPT_DISCLOSURE_MISSING"
    assert store.get(p["version_id"])["revision"] == p["revision"]           # /validate stores nothing


def test_template_variables_preview_and_link_warning():
    config = copy.deepcopy(store.published("loan_policy")["config"])
    preview = prompts.preview("loan_policy", config)
    assert preview["templates"]["link_message"].startswith("שלום עידו")
    assert "https://demo.invalid/u/DEMO-LINK" in preview["templates"]["link_message"]
    config["templates"]["link_message"] = "שלום {{first_name}}, חסר {{missing_documents}}."
    config["templates"]["reminder"] = "{{first_name}}, {{iban}}"
    report = client.post(f"{BASE}/validate", headers=STAFF, json={"kind": "loan_policy", "config": config}).json()
    assert any("iban" in e["message"] for e in report["errors"])
    assert any(w["code"] == "TEMPLATE_LINK_MISSING" for w in report["warnings"])
    assert prompts.render("{{first_name}} / {{nope}}", {"first_name": "נועה"}) == "נועה / {{nope}}"


# ---------------------------------------------------------------- kill switch
def test_kill_switch_toggles_and_shows_in_settings():
    r = client.post(f"{BASE}/followups/pause", json={"paused": True, "reason": "בדיקה"}, headers=STAFF)
    assert r.status_code == 200 and r.json()["value"] is True and r.json()["updated_by"] == "admin:STAFF-DANA"
    s = client.get(f"{BASE}/settings", headers=STAFF).json()
    assert s["kill_switch"]["value"] is True and flags.get(flags.KILL_SWITCH) is True
    client.post(f"{BASE}/followups/pause", json={"paused": False}, headers=STAFF)
    assert flags.get(flags.KILL_SWITCH) is False
    assert any(e["type"] == "settings.kill_switch_changed.v1" for e in client.get(f"{BASE}/audit", headers=STAFF).json()["events"])
