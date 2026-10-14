"""G5 cross-feature wiring: the review pipeline tells the follow-up engine what changed, the engine's due work runs
in the worker loop, a follow-up failure never breaks an upload or a review, and the follow-up context is a read-only
tool for the assistant and MCP. No Gemini (tests/conftest.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.agent import tools
from app.review import case_review
from app.followup import orchestrator, tasks
from app.main import app
from app.store import repo
from app.workflow import engine
from tests.loan_helpers import CODES, JOURNEY, client_for, id_card, run_case
from tests.test_review_desk import add_doc

FIX = engine.Path(__file__).resolve().parents[2] / "fixtures" / "presenter" / "loan_set" / "id_card_ido.pdf"


@pytest.fixture(autouse=True)
def _no_model(monkeypatch):
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})


def _fresh() -> None:
    repo.reset_case(JOURNEY)
    with db.tx() as c:
        c.execute("DELETE FROM jobs WHERE case_id=?", (JOURNEY,))


def _triggers() -> list[str]:
    return [r["trigger"] for r in db.query("SELECT trigger FROM policy_decisions WHERE case_id=? ORDER BY evaluated_at", (JOURNEY,))]


def test_an_accepted_upload_and_a_finished_case_review_reach_the_follow_up_engine():
    _fresh()
    with FIX.open("rb") as fh:
        r = client_for(JOURNEY).post(f"/api/cases/{JOURNEY}/documents", data={"requirement_code": CODES["id"], "borrower_id": "BRW-A"},
                                     files={"file": (FIX.name, fh, "application/pdf")})
    assert r.status_code == 202 and "document_uploaded" in _triggers()
    for m in ("2026-07", "2026-08"):
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=JOURNEY)
    id_card()
    run_case()                                         # the case review: September is missing
    assert "review_finished" in _triggers()
    open_ = {t["requirement_code"] for t in tasks.open_for(JOURNEY)}
    assert CODES["pay"] in open_                       # a task for the genuine outstanding issue only
    assert CODES["id"] not in open_
    _fresh()


def test_a_follow_up_failure_never_breaks_an_upload_a_review_or_the_worker(monkeypatch):
    _fresh()

    def boom(*a, **k):
        raise RuntimeError("follow-up down")
    monkeypatch.setattr(orchestrator, "on_event", boom)
    monkeypatch.setattr(orchestrator, "tick", boom)
    with FIX.open("rb") as fh:
        r = client_for(JOURNEY).post(f"/api/cases/{JOURNEY}/documents", data={"requirement_code": CODES["id"], "borrower_id": "BRW-A"},
                                     files={"file": (FIX.name, fh, "application/pdf")})
    assert r.status_code == 202
    add_doc("BRW-A", "2026-07", 14700, "ido_2026-07.pdf", case=JOURNEY)
    run_case()                                         # completes despite the follow-up error
    assert repo.latest_case_result(JOURNEY)
    engine._tick_followups()                           # the worker's tick swallows and logs it
    _fresh()


def test_the_follow_up_context_is_a_read_only_tool_on_every_channel_including_mcp():
    spec = tools.TOOLS["get_followup_context"]
    assert spec["write"] is False and tools.on_channel("get_followup_context", "mcp")
    _fresh()
    add_doc("BRW-A", "2026-07", 14700, "ido_2026-07.pdf", case=JOURNEY)
    run_case()
    out = tools.call("get_followup_context", JOURNEY, {}, {"channel": "mcp"})
    assert out["open_tasks"] and "rule_ids" not in str(out) and "attempts" not in out
    _fresh()


def test_the_system_page_shows_the_follow_up_engine_and_the_simulated_talk_provider():
    rows = {r["component"]: r for r in TestClient(app).get("/api/system/integrations").json()["matrix"]}
    engine_row = next(v for k, v in rows.items() if k.startswith("Follow-up engine"))
    talk = next(v for k, v in rows.items() if k.startswith("JEEN Talk"))
    assert "review-worker-0" in engine_row["detail"] and talk["state"] == "DEMO" and "never dials" in talk["detail"]
