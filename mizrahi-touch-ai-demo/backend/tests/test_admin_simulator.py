"""The Admin simulator (CONTRACTS §6) and the publish gate's scenario check: every fixture runs through Agent B's
evaluator, a run writes only its own row and event (S40), and a draft that breaks a mandatory scenario can't be
published (AC 18). The gate tests build their own scenarios, so they don't depend on the fixtures' current values."""
import copy

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.followup import contract
from app.main import app
from app.policy import simulator, store

BASE = "/api/admin/loan-completion"
client = TestClient(app)
STAFF = {"authorization": f"Bearer {auth.issue('staff', 'STAFF-DANA')}"}


@pytest.fixture(scope="module", autouse=True)
def _restore_configuration():
    db.connect()
    store.ensure_seeded()
    before = {r["version_id"]: r["status"] for r in db.query("SELECT version_id, status FROM config_versions")}
    yield
    with db.tx() as c:
        for row in c.execute("SELECT version_id FROM config_versions").fetchall():
            if row["version_id"] not in before:
                c.execute("DELETE FROM config_versions WHERE version_id=?", (row["version_id"],))
        for vid, status in before.items():
            c.execute("UPDATE config_versions SET status=? WHERE version_id=?", (status, vid))


@pytest.fixture(autouse=True)
def _no_open_drafts():
    while (d := store.open_draft("loan_policy")) is not None:
        store.discard_draft(d["version_id"], d["revision"], actor="tests")


def counts() -> dict[str, int]:
    tables = [r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {t: db.one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in tables}


def with_grace(config: dict, minutes: int) -> dict:
    out = copy.deepcopy(config)
    out["followup"]["abandonment_grace_minutes"] = minutes
    return out


def test_the_simulator_runs_every_fixture_on_the_published_policy():
    run = client.post(f"{BASE}/policy/simulate", json={}, headers=STAFF)
    assert run.status_code == 200, run.text
    body = run.json()
    fixtures = contract.load_scenarios()
    assert len(body["results"]) == len(fixtures) and {r["scenario_id"] for r in body["results"]} == {s.id for s in fixtures}
    assert body["side_effects"] is False and body["version_id"] == store.published("loan_policy")["version_id"]
    assert body["passed"] is True and body["mandatory_passed"] is True       # the seed is what the fixtures describe
    assert all(r["actual"]["explanation_he"] and r["actual"]["rule_ids"] for r in body["results"])
    assert contract.SimulationRun.model_validate(body).run_id == body["run_id"]


def test_a_simulation_writes_only_its_run_and_one_event():
    before = counts()
    body = client.post(f"{BASE}/policy/simulate", headers=STAFF,
                       json={"config": with_grace(store.published("loan_policy")["config"], 30)}).json()
    after = counts()
    changed = {t: after[t] - before[t] for t in after if after[t] != before[t]}
    assert changed == {"simulation_runs": 1, "case_events": 1}
    row = db.one("SELECT * FROM simulation_runs WHERE run_id=?", (body["run_id"],))
    assert row["actor"] == "admin:STAFF-DANA" and row["version_id"] is None and row["passed"] == int(body["passed"])
    event = db.one("SELECT * FROM case_events WHERE type='policy.simulation_completed.v1' ORDER BY rowid DESC LIMIT 1")
    assert db.jload(event["payload"])["run_id"] == body["run_id"] and event["case_id"] is None


def test_an_invalid_configuration_fails_closed_in_every_scenario():
    config = store.published("loan_policy")["config"]
    broken = {**config, "followup": {**config["followup"], "max_attempts_per_case": 99}}
    for r in simulator.run(broken):
        assert r.error is None
        assert r.actual.action == "BLOCK" and "CFG-INVALID" in r.actual.blocked_by


def test_one_failing_scenario_does_not_stop_the_others(monkeypatch):
    real = simulator.evaluate
    first = contract.load_scenarios()[0].id

    def flaky(ctx, policy, now):
        if ctx.case_id and flaky.calls == 0:
            flaky.calls += 1
            raise RuntimeError("boom")
        return real(ctx, policy, now)
    flaky.calls = 0
    monkeypatch.setattr(simulator, "evaluate", flaky)
    results = simulator.run(store.published("loan_policy")["config"])
    assert results[0].scenario_id == first and results[0].passed is False and "boom" in results[0].error
    assert all(r.error is None for r in results[1:])


@pytest.fixture
def gate_scenarios(monkeypatch):
    """A mandatory scenario whose expectation depends on the grace period, and a non-mandatory twin."""
    s05 = next(s for s in contract.load_scenarios() if s.id == "S05")
    mine = [s05.model_copy(update={"id": "C05", "policy_overrides": {}, "mandatory": True}),
            s05.model_copy(update={"id": "N05", "policy_overrides": {}, "mandatory": False})]
    monkeypatch.setattr(contract, "load_scenarios", lambda *a, **k: mine)
    return mine


def test_a_draft_that_breaks_a_mandatory_scenario_cannot_be_published(gate_scenarios):
    published = store.published("loan_policy")
    assert all(r.passed for r in simulator.run(published["config"]))           # both hold on the published policy
    d = client.post(f"{BASE}/drafts", json={"kind": "loan_policy"}, headers=STAFF).json()
    saved = client.put(f"{BASE}/drafts/{d['version_id']}", headers=STAFF,
                       json={"config": with_grace(d["config"], 45), "revision": d["revision"]}).json()
    report = client.post(f"{BASE}/drafts/{d['version_id']}/validate", headers=STAFF).json()
    assert report["publishable"] is False and report["scenarios"]["mandatory_failed"] == ["C05"]
    assert set(report["scenarios"]["failed"]) == {"C05", "N05"}
    r = client.post(f"{BASE}/drafts/{d['version_id']}/publish", json={"revision": saved["revision"]}, headers=STAFF)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert len(detail["reasons"]) == 1 and "C05" in detail["reasons"][0] and "N05" not in detail["reasons"][0]
    assert "מועד הפנייה הבא" in detail["reasons"][0]                         # names the part that differs (grace → time)
    assert db.one("SELECT passed FROM simulation_runs WHERE run_id=?", (detail["run_id"],))["passed"] == 0
    assert store.published("loan_policy")["version_id"] == published["version_id"]


def test_a_draft_that_keeps_the_mandatory_scenarios_publishes_with_its_run(gate_scenarios):
    d = client.post(f"{BASE}/drafts", json={"kind": "loan_policy"}, headers=STAFF).json()
    config = copy.deepcopy(d["config"])
    config["validation"]["low_confidence_threshold"] = 0.7
    saved = client.put(f"{BASE}/drafts/{d['version_id']}", headers=STAFF, json={"config": config, "revision": d["revision"]}).json()
    r = client.post(f"{BASE}/drafts/{d['version_id']}/publish", json={"revision": saved["revision"]}, headers=STAFF)
    assert r.status_code == 200, r.text
    run = db.one("SELECT * FROM simulation_runs WHERE run_id=?", (r.json()["simulation_run_id"],))
    assert run["version_id"] == d["version_id"] and run["passed"] == 1


def test_simulate_a_version_or_refuse_an_unknown_one():
    v = store.published("loan_policy")
    assert client.post(f"{BASE}/policy/simulate", json={"version_id": v["version_id"]}, headers=STAFF).json()["version_id"] == v["version_id"]
    assert client.post(f"{BASE}/policy/simulate", json={"version_id": "CFG-NOPE"}, headers=STAFF).status_code == 404
    prompt = store.published("talk_prompt")
    assert client.post(f"{BASE}/policy/simulate", json={"version_id": prompt["version_id"]}, headers=STAFF).status_code == 404
    only = client.post(f"{BASE}/policy/simulate", json={"scenario_ids": ["S01"]}, headers=STAFF).json()
    assert [r["scenario_id"] for r in only["results"]] == ["S01"]


def test_the_simulator_also_shows_what_the_edited_values_do_where_a_scenario_pins_them():
    """Timing scenarios pin seed values so the gate stays a deterministic regression check; the Admin must still see
    the effect of the edit. With grace 20 → 30 the pinned S05 still passes, while the configuration's own decision
    moves 10 minutes later. With the published policy unchanged both agree."""
    seed = copy.deepcopy(store.published("loan_policy")["config"])
    edited = contract.merge_overrides(seed, {"followup": {"abandonment_grace_minutes": 30}})
    r = client.post(f"{BASE}/policy/simulate", json={"config": edited, "version_id": None}, headers=STAFF).json()
    contract.SimulationRun.model_validate(r)                                 # the simulate contract is unchanged
    mine = client.post(f"{BASE}/policy/as-configured", json={"config": edited, "version_id": None}, headers=STAFF).json()
    pinned = next(x for x in r["results"] if x["scenario_id"] == "S05")
    own = mine["S05"]
    assert pinned["passed"] and r["mandatory_passed"]
    assert "followup.abandonment_grace_minutes" in own["pinned"]
    from datetime import datetime, timedelta
    shift = datetime.fromisoformat(own["decision"]["next_eligible_at"]) - datetime.fromisoformat(pinned["actual"]["next_eligible_at"])
    assert shift == timedelta(minutes=10)
    same = client.post(f"{BASE}/policy/simulate", json={"config": seed, "version_id": None}, headers=STAFF).json()
    same_own = client.post(f"{BASE}/policy/as-configured", json={"config": seed, "version_id": None}, headers=STAFF).json()
    s05 = next(x for x in same["results"] if x["scenario_id"] == "S05")
    assert same_own["S05"]["decision"]["next_eligible_at"] == s05["actual"]["next_eligible_at"]
    # scenarios that pin nothing (the hard guards) are not repeated: their pass/fail already uses the draft as is
    assert set(mine) == {s.id for s in contract.load_scenarios() if s.policy_overrides}
