"""The follow-up loop end to end, through the HTTP API and the orchestrator, with a fixed clock and no Gemini:
self-service in the app → grace → simulated call → secure link → corrected upload → ready for the banker
(AC 6, 10–11, 13; 03 §5 S01, S05–S08, S12, S14, S18, S24, S25, S29). Reviews are stored results
(`tests/loan_helpers.py`), the case review runs for real."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth, clock, db, flags
from app.comms import mock_talk
from app.followup import orchestrator, tasks
from app.main import app
from app.review import case_review
from app.store import repo
from app.util import new_id, now_iso
from tests.loan_helpers import JOURNEY, id_card, purpose, run_case, statement
from tests.test_review_desk import add_doc

NO_CONSENT = "DEMO-MTZ-2026-010"
START = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)          # Tuesday 11:00 in Israel, inside the call window


class FakeWall:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def advance(self, **kw) -> datetime:
        self.t += timedelta(**kw)
        return self.t


@pytest.fixture
def wall(monkeypatch):
    w = FakeWall(START)
    monkeypatch.setattr(clock, "wall", w)
    return w


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    db.connect()
    for case in (JOURNEY, NO_CONSENT):
        repo.reset_case(case)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
        c.execute("DELETE FROM provider_events")
        c.execute("DELETE FROM system_flags")
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})
    yield


def customer(*cases: str) -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIES["customer"], auth.issue("customer", list(cases)))
    return c


def staff(staff_id: str = "STAFF-DANA") -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIES["staff"], auth.issue("staff", staff_id))
    return c


def package(case: str = JOURNEY, months=("2026-07", "2026-08"), with_purpose: bool = True) -> None:
    """Every document but the listed payslip months: one open customer task per missing kind."""
    for m in months:
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=case)
    id_card(case)
    statement(case)
    if with_purpose:
        purpose(case)
    run_case(case)


def presence(client: TestClient, event: str, seq: int, case: str = JOURNEY, session: str = "tab-1", **kw):
    r = client.post(f"/api/cases/{case}/presence", json={"session_id": session, "event": event, "seq": seq,
                                                         "visible": True, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def plan_state(case: str = JOURNEY) -> str:
    return (orchestrator.plan(case) or {}).get("state", "IDLE")


def dispatched_call(wall: FakeWall, case: str = JOURNEY) -> dict:
    """Open the task, let the customer leave, wait out the grace period: the mock call goes out."""
    package(case)
    orchestrator.on_event(case, "review_finished")
    wall.advance(minutes=21)
    orchestrator.tick()
    rows = orchestrator.attempts(case)
    assert len(rows) == 1, rows
    return rows[0]


# ---------------------------------------------------------------- the journey
def test_journey_from_self_service_to_ready_for_banker(wall):
    ido, dana = customer(JOURNEY), staff()
    package()
    orchestrator.on_event(JOURNEY, "review_finished")
    open_tasks = tasks.open_for(JOURNEY)
    assert [(t["requirement_code"], t["reason_code"]) for t in open_tasks] == [("PAYSLIPS:BRW-A", "REQUIRED_PERIOD_MISSING")]
    assert plan_state() == "WAITING"                           # nobody in the app yet: grace from the issue

    # the customer is on the correction screen: in-app only (S01)
    assert presence(ido, "session_started", 1, screen="document", requirement_code="PAYSLIPS:BRW-A")["state"] == "ACTIVE"
    assert plan_state() == "IN_APP" and tasks.open_for(JOURNEY)[0]["status"] == "IN_APP_PROMPTED"
    view = ido.get(f"/api/cases/{JOURNEY}/followup").json()
    assert view["open_items"][0]["requirement_code"] == "PAYSLIPS:BRW-A" and view["simulated"] is True

    # the customer leaves: grace (S05)
    wall.advance(minutes=1)
    presence(ido, "session_ended", 2)
    decision = orchestrator.plan(JOURNEY)["decision"]
    assert decision["action"] == "WAIT" and decision["blocked_by"] == ["CFG-GRACE"]
    wall.advance(minutes=10)
    orchestrator.tick()
    assert orchestrator.attempts(JOURNEY) == []

    # grace over: scheduled, through the gate, a simulated call (S06)
    wall.advance(minutes=11)
    orchestrator.tick()
    [attempt] = orchestrator.attempts(JOURNEY)
    assert attempt["provider"] == "mock-talk" and attempt["simulated"] and attempt["status"] == "DISPATCHING"
    assert orchestrator.case_status(JOURNEY) == "FOLLOWUP_IN_PROGRESS"
    assert "[secure-link]" == attempt["request"]["call"]["variables"]["secure_upload_link"]
    assert attempt["request"]["call"]["variables"]["missing_documents"] == ["חסר תלוש לחודש נדרש"]
    assert attempt["request"]["call"]["contact_ref"] == "TEST-LINE-01"

    # the mock script: dialing, connected, link sent
    for _ in range(3):
        orchestrator.tick()
        wall.advance(seconds=45)
    orchestrator.tick()
    [attempt] = orchestrator.attempts(JOURNEY)
    assert (attempt["status"], attempt["outcome"]) == ("COMPLETED", "LINK_SENT")
    assert [h["status"] for h in attempt["history"]] == ["QUEUED", "DISPATCHING", "DIALING", "CONNECTED", "COMPLETED"]
    assert plan_state() == "AWAITING_CUSTOMER" and orchestrator.case_status(JOURNEY) == "AWAITING_CUSTOMER"
    orchestrator.tick()
    assert len(orchestrator.attempts(JOURNEY)) == 1            # no second call: spacing + one plan

    # the link: the presenter reads it, a fresh browser redeems it into a session for this case only
    sent = dana.get(f"/api/demo/cases/{JOURNEY}/sent-links").json()
    assert sent["label_he"] == "סימולציה" and len(sent["links"]) == 1
    token = sent["links"][0]["token"]
    row = db.one("SELECT token_hash FROM upload_links WHERE case_id=?", (JOURNEY,))
    assert row["token_hash"] != token and token not in json.dumps(orchestrator.attempts(JOURNEY), default=str)
    phone = TestClient(app)
    r = phone.post("/api/links/redeem", json={"token": token})
    assert r.json() == {"state": "ok", "case_id": JOURNEY, "target": "/customer/documents?req=PAYSLIPS:BRW-A"}
    assert phone.get(f"/api/cases/{JOURNEY}/followup").status_code == 200
    assert phone.get(f"/api/cases/{NO_CONSENT}/followup").status_code == 403

    # the corrected upload passes review: task resolved, plan completed, ready for the banker (S08, AC 10–11)
    add_doc("BRW-A", "2026-09", 14700, "ido_2026-09.pdf", case=JOURNEY)
    run_case()
    orchestrator.on_event(JOURNEY, "review_finished")
    [task] = tasks.all_for(JOURNEY)
    assert task["status"] == "RESOLVED" and task["document_id"]
    assert plan_state() == "COMPLETED" and orchestrator.case_status(JOURNEY) == "READY_FOR_BANKER"
    assert phone.post("/api/links/redeem", json={"token": token}).json()["state"] == "resolved"
    wall.advance(days=2)
    orchestrator.tick()
    assert len(orchestrator.attempts(JOURNEY)) == 1

    # the banker sees why and when, in Hebrew, with the whole timeline
    view = dana.get(f"/api/banker/cases/{JOURNEY}/followup").json()
    assert view["plan"]["state"] == "COMPLETED" and view["attempts"][0]["simulated"] is True
    assert view["decision"]["action"] == "RESOLVE_AND_CANCEL" and view["decision"]["explanation_he"]
    types = {e["type"] for e in dana.get(f"/api/banker/cases/{JOURNEY}/timeline").json()}
    assert {"completion.required.v1", "completion.resolved.v1", "followup.scheduled.v1", "talk.call.status_changed.v1",
            "case.ready_for_banker.v1", "followup.policy_evaluated.v1", "customer.presence_changed.v1"} <= types
    assert db.one("SELECT COUNT(*) n FROM policy_decisions WHERE case_id=?", (JOURNEY,))["n"] >= 5


def test_one_task_per_issue_and_one_consolidated_call(wall):
    package(months=("2026-07",), with_purpose=False)          # August and September missing, and the purpose proof
    orchestrator.on_event(JOURNEY, "review_finished")
    tasks.sync(JOURNEY)
    open_tasks = tasks.open_for(JOURNEY)
    assert sorted((t["requirement_code"], t["reason_code"]) for t in open_tasks) == [
        ("PAYSLIPS:BRW-A", "REQUIRED_PERIOD_MISSING"), ("PURPOSE_PROOF", "REQUIRED_DOCUMENT_MISSING")]
    wall.advance(minutes=21)
    orchestrator.tick()
    [attempt] = orchestrator.attempts(JOURNEY)
    assert sorted(attempt["task_ids"]) == sorted(t["task_id"] for t in open_tasks)
    assert len(attempt["request"]["call"]["variables"]["missing_documents"]) == 2
    assert "CFG-CONSOLIDATE" in orchestrator.plan(JOURNEY)["decision"]["rule_ids"]


def test_a_banker_request_merges_with_the_ai_task_on_the_same_requirement(wall):
    package()
    with db.tx() as c:
        c.execute("INSERT INTO customer_requests(customer_request_id, case_id, kind, borrower_id, requirement_code,"
                  " message_he, status, created_at, updated_at, title_he) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (new_id("CRQ"), JOURNEY, "missing", "BRW-A", "PAYSLIPS:BRW-A", "נא להעלות את תלוש ספטמבר 2026",
                   "OPEN", now_iso(), now_iso(), "תלוש ספטמבר"))
    tasks.sync(JOURNEY)
    [task] = tasks.open_for(JOURNEY)
    assert task["customer_text_he"] == "נא להעלות את תלוש ספטמבר 2026"


# ---------------------------------------------------------------- guards
def test_kill_switch_cancels_a_waiting_plan_and_a_call_not_yet_connected(wall):
    package()
    orchestrator.on_event(JOURNEY, "review_finished")
    flags.put(flags.KILL_SWITCH, True, "admin:test")
    wall.advance(minutes=21)
    orchestrator.tick()
    assert orchestrator.attempts(JOURNEY) == [] and plan_state() == "CANCELED"
    assert orchestrator.plan(JOURNEY)["decision"]["blocked_by"] == ["HG-KILL-SWITCH"]
    flags.put(flags.KILL_SWITCH, False, "admin:test")
    orchestrator.tick()
    [attempt] = orchestrator.attempts(JOURNEY)                  # re-enabled: the plan resumes, no catch-up blast
    flags.put(flags.KILL_SWITCH, True, "admin:test")
    orchestrator.tick()
    assert orchestrator.attempts(JOURNEY)[0]["status"] == "CANCELED"


def test_opt_out_mid_plan_cancels_and_no_call_follows(wall):
    ido = customer(JOURNEY)
    package()
    orchestrator.on_event(JOURNEY, "review_finished")
    assert plan_state() == "WAITING"
    r = ido.post(f"/api/cases/{JOURNEY}/contact-preferences", json={"opt_out_voice": True})
    assert r.status_code == 200 and r.json()["contact"]["voice_allowed"] is False
    assert plan_state() == "CANCELED" and orchestrator.plan(JOURNEY)["decision"]["blocked_by"] == ["HG-OPT-OUT"]
    wall.advance(hours=3)
    orchestrator.tick()
    assert orchestrator.attempts(JOURNEY) == []


def test_case_without_consent_is_blocked_with_a_reason(wall):
    package(NO_CONSENT)
    orchestrator.on_event(NO_CONSENT, "review_finished")
    wall.advance(minutes=30)
    orchestrator.tick()
    assert orchestrator.attempts(NO_CONSENT) == [] and plan_state(NO_CONSENT) == "BLOCKED"
    view = staff().get(f"/api/banker/cases/{NO_CONSENT}/followup").json()
    assert view["decision"]["blocked_by"] == ["HG-NO-CONSENT"] and "אין הרשאת קשר" in view["decision"]["explanation_he"]


def test_manual_call_goes_through_the_same_guards(wall):
    dana, ido = staff(), customer(JOURNEY)
    package()
    orchestrator.on_event(JOURNEY, "review_finished")
    ido.post(f"/api/cases/{JOURNEY}/contact-preferences", json={"opt_out_voice": True})
    r = dana.post(f"/api/banker/cases/{JOURNEY}/followups", json={"reason": "הלקוח ביקש שנתקשר"})
    assert r.status_code == 409 and r.json()["blocked_by"] == ["HG-OPT-OUT"]
    ido.post(f"/api/cases/{JOURNEY}/contact-preferences", json={"opt_out_voice": False})
    r = dana.post(f"/api/banker/cases/{JOURNEY}/followups", json={"reason": "הלקוח ביקש שנתקשר"})
    assert r.status_code == 201 and r.json()["simulated"] is True     # no grace for a banker's call
    assert len(orchestrator.attempts(JOURNEY)) == 1


def test_banker_pause_and_resume(wall):
    dana = staff()
    package()
    orchestrator.on_event(JOURNEY, "review_finished")
    r = dana.post(f"/api/banker/cases/{JOURNEY}/followup-override", json={"type": "pause", "reason": "אטפל בעצמי"})
    assert r.status_code == 200 and r.json()["plan"]["state"] == "PAUSED"
    wall.advance(minutes=30)
    orchestrator.tick()
    assert orchestrator.attempts(JOURNEY) == []
    dana.post(f"/api/banker/cases/{JOURNEY}/followup-override", json={"type": "resume", "reason": "חזרה לאוטומציה"})
    assert len(orchestrator.attempts(JOURNEY)) == 1


def test_customer_projection_has_no_internals(wall):
    ido = customer(JOURNEY)
    dispatched_call(wall)
    body = ido.get(f"/api/cases/{JOURNEY}/followup").text
    for internal in ("HG-", "CFG-", "OP-", "PREF-", "rule_ids", "blocked_by", "attempt", "policy_version",
                     "loan_policy@", "explanation", "TEST-LINE", "mock-talk"):
        assert internal not in body, internal
    snoozed = ido.post(f"/api/cases/{JOURNEY}/followup-snooze", json={"minutes": 60}).json()
    assert snoozed["snooze_until"] and set(snoozed) == {"state_he", "nudge", "nudge_text_he", "open_items",
                                                       "snooze_until", "contact", "simulated"}


def test_access_uses_the_existing_session_checks(wall):
    package()
    anon, other, ori = TestClient(app), customer(NO_CONSENT), staff("STAFF-ORI")
    for path in (f"/api/cases/{JOURNEY}/followup", f"/api/banker/cases/{JOURNEY}/followup",
                 f"/api/banker/cases/{JOURNEY}/timeline"):
        assert anon.get(path).status_code == 401, path
    assert anon.post(f"/api/cases/{JOURNEY}/presence", json={"session_id": "tab-1", "event": "heartbeat", "seq": 1}).status_code == 401
    assert other.get(f"/api/cases/{JOURNEY}/followup").status_code == 403
    assert other.get(f"/api/banker/cases/{JOURNEY}/followup").status_code == 401        # a customer is not staff
    assert ori.get(f"/api/banker/cases/{JOURNEY}/followup").status_code == 200          # any banker reads
    assert ori.post(f"/api/banker/cases/{JOURNEY}/followup-override",
                    json={"type": "pause", "reason": "לא שלי"}).status_code == 403    # only the assigned one writes
    assert ori.post(f"/api/banker/cases/{JOURNEY}/followups", json={"reason": "בדיקה"}).status_code == 403
    assert anon.post("/api/demo/tick").status_code == 401
    assert other.post(f"/api/demo/cases/{JOURNEY}/customer-left").status_code == 403


def test_demo_controls_drive_the_loop(wall):
    dana, ido = staff(), customer(JOURNEY)
    package()
    presence(ido, "session_started", 1, screen="documents")
    r = ido.post(f"/api/demo/cases/{JOURNEY}/customer-left").json()          # the presenter, from the customer app
    assert r["label_he"] == "סימולציה" and r["decision"]["action"] == "WAIT"
    clock_state = dana.post("/api/demo/clock", json={"advance_minutes": 25}).json()
    assert clock_state["offset_seconds"] == 1500 and clock_state["label_he"] == "סימולציה"
    assert dana.post("/api/demo/tick").json()["evaluated"] == [JOURNEY]
    assert len(orchestrator.attempts(JOURNEY)) == 1
    dana.post("/api/demo/tick")                                                # DIALING
    callback = clock.now() + timedelta(hours=5)                                # beyond the envelope's 4 h spacing
    r = dana.post(f"/api/demo/cases/{JOURNEY}/talk-outcome", json={"outcome": "CALLBACK_REQUESTED",
                  "callback_at": callback.isoformat()})
    assert r.status_code == 200 and r.json()["outcome"] == "CALLBACK_REQUESTED"
    d = orchestrator.plan(JOURNEY)["decision"]
    assert d["action"] == "SCHEDULE_CALL" and "PREF-CALLBACK" in d["rule_ids"]
    assert datetime.fromisoformat(d["next_eligible_at"]) == callback.replace(microsecond=0)
    assert dana.post(f"/api/demo/cases/{JOURNEY}/talk-outcome", json={"outcome": "REFUSED"}).status_code == 409
    assert dana.post("/api/demo/clock", json={"reset": True}).json()["offset_seconds"] == 0
    assert db.one("SELECT COUNT(*) n FROM audit WHERE action LIKE 'demo_%'")["n"] >= 4


def test_refused_call_opts_out_and_a_human_request_escalates(wall):
    dispatched_call(wall)
    orchestrator.set_talk_outcome(JOURNEY, "REFUSED", None)
    assert orchestrator.preferences(JOURNEY)["opt_out_voice"] is True
    assert orchestrator.plan(JOURNEY)["decision"]["blocked_by"] == ["HG-OPT-OUT"]
    repo.reset_case(JOURNEY)
    dispatched_call(wall)
    orchestrator.set_talk_outcome(JOURNEY, "HUMAN_REQUESTED", None)
    assert plan_state() == "ESCALATED" and tasks.open_for(JOURNEY)[0]["status"] == "ESCALATED"


def test_talk_failure_does_not_block_uploads(wall, monkeypatch):
    def broken(self, req):
        raise ConnectionError("talk down")
    monkeypatch.setattr(mock_talk.MockTalkProvider, "create_call", broken)
    [attempt] = [dispatched_call(wall)]
    assert attempt["status"] == "FAILED"
    ido = customer(JOURNEY)
    pdf = (repo.document(repo.documents(JOURNEY)[0]["document_id"])["storage_path"])
    with open(pdf, "rb") as fh:
        r = ido.post(f"/api/cases/{JOURNEY}/documents", files={"file": ("ido_2026-09_new.pdf", fh.read() + b"%new",
                                                                           "application/pdf")},
                     data={"borrower_id": "BRW-A", "requirement_code": "PAYSLIPS:BRW-A"})
    assert r.status_code == 202, r.text
    orchestrator.on_event(JOURNEY, "document_uploaded")
    assert orchestrator.plan(JOURNEY)["decision"]["blocked_by"] == ["HG-IN-FLIGHT"]     # S09: hold while it is checked
