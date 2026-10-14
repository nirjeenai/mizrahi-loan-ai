"""The Admin's policy simulator (CONTRACTS §6, doc 03 S40): runs a loan-policy configuration through the follow-up
evaluator on every scenario fixture in `backend/policy/scenarios/`, with no side effects on cases.

`run` is pure: it evaluates and compares, nothing more. `simulate` adds exactly one `simulation_runs` row and one
`policy.simulation_completed.v1` event; no other table changes. The evaluator, the fixtures and the comparison are
Agent B's (`followup/policy.py`, `contract.load_scenarios`, `contract.matches`), so a simulation and the engine's own
tests can't disagree."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from .. import db, events
from ..followup import contract
from ..followup.policy import evaluate
from ..util import new_id, stable_hash
from . import schema

ISRAEL = ZoneInfo("Asia/Jerusalem")


def run(config: dict, scenario_ids: Optional[list[str]] = None,
        scenarios: Optional[list[contract.Scenario]] = None) -> list[contract.ScenarioResult]:
    """Every scenario's result for one configuration. An exception in one scenario fails only that scenario."""
    out = []
    for s in scenarios if scenarios is not None else contract.load_scenarios():
        if scenario_ids is not None and s.id not in scenario_ids:
            continue
        try:
            try:
                policy = schema.parse("loan_policy", contract.merge_overrides(config, s.policy_overrides))
            except ValidationError:
                policy = None                                   # an invalid configuration fails closed (CFG-INVALID)
            decision = evaluate(s.context, policy, s.now)
            out.append(contract.ScenarioResult(scenario_id=s.id, title_he=s.title_he, mandatory=s.mandatory,
                                               passed=contract.matches(s.expect, decision), expected=s.expect,
                                               actual=decision))
        except Exception as exc:  # noqa: BLE001 — reported per scenario, never raised
            out.append(contract.ScenarioResult(scenario_id=s.id, title_he=s.title_he, mandatory=s.mandatory, passed=False,
                                               expected=s.expect, error=f"{type(exc).__name__}: {exc}"))
    return out


def mismatch_he(result: contract.ScenarioResult) -> str:
    """Which part of the expectation the decision missed (the same parts `contract.matches` compares)."""
    if result.actual is None:
        return f"שגיאה בהרצה ({result.error})"
    e, d = result.expected, result.actual
    parts = []
    if d.action != e.action:
        parts.append(f"פעולה צפויה {e.action}, בפועל {d.action}")
    missing = [r for r in e.rule_ids_include if r not in d.rule_ids]
    if missing:
        parts.append("חסרים כללים: " + ", ".join(missing))
    unblocked = [r for r in e.blocked_by_include if r not in d.blocked_by]
    if unblocked:
        parts.append("לא נחסם לפי: " + ", ".join(unblocked))
    if e.next_eligible_at is not None and d.next_eligible_at != e.next_eligible_at:
        parts.append(f"מועד הפנייה הבא צפוי {_local(e.next_eligible_at)}, בפועל {_local(d.next_eligible_at)}")
    return "; ".join(parts)


def _local(at: Optional[datetime]) -> str:
    return at.astimezone(ISRAEL).strftime("%d.%m %H:%M") if at else "ללא מועד"


def mandatory_failures(results: list[contract.ScenarioResult]) -> list[contract.ScenarioResult]:
    return [r for r in results if r.mandatory and not r.passed]


def simulate(config: dict, version_id: Optional[str], actor: str, scenario_ids: Optional[list[str]] = None,
             scenarios: Optional[list[contract.Scenario]] = None) -> contract.SimulationRun:
    results = run(config, scenario_ids, scenarios)
    sim = contract.SimulationRun(
        run_id=new_id("SIM"), version_id=version_id, config_hash=stable_hash(db.jdump(config)), actor=actor,
        created_at=datetime.now(timezone.utc).replace(microsecond=0), passed=all(r.passed for r in results),
        mandatory_passed=not mandatory_failures(results), results=tuple(results))
    body = sim.model_dump(mode="json")
    with db.tx() as c:
        c.execute("INSERT INTO simulation_runs(run_id, version_id, created_at, actor, results, passed) VALUES (?,?,?,?,?,?)",
                  (sim.run_id, version_id, body["created_at"], actor, db.jdump(body["results"]), int(sim.passed)))
        events.emit("policy.simulation_completed.v1", None, actor,
                    {"kind": "loan_policy", "run_id": sim.run_id, "version_id": version_id, "config_hash": sim.config_hash,
                     "passed": sim.passed, "mandatory_passed": sim.mandatory_passed, "scenarios": len(results),
                     "failed": [r.scenario_id for r in results if not r.passed]}, conn=c)
    return sim
