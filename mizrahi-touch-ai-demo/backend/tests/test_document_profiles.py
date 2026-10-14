"""Smart document profiling: one policy composition for the six prepared use cases and for new customers.

The six presenter test cases (TC-01…06 in the presenter manifest) map one-to-one to UC-01…06 and to their own prepared
case; the requirements each case gets come from the published demo loan policy and must equal what the manifest shows.
New customers answer a deterministic questionnaire; the case is created once, on confirmation, through the same policy.
A document family without a review rubric is stored for the banker — never reviewed or marked valid by AI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.bank.mock_bank import bank
from app.main import app
from app.policy import store
from app.store import repo
from app.workflow import readiness, requirements
from tests.loan_helpers import client_for

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / "fixtures" / "presenter" / "presenter_scenarios_manifest.json").read_text(encoding="utf8"))
USE_CASES = MANIFEST["useCases"]
PDF = ROOT / "fixtures" / "out" / "main" / "ido_payslip_2026-07.pdf"
PACK = ROOT / "fixtures" / "presenter" / "profile_set"


@pytest.fixture(autouse=True)
def _db():
    db.connect()
    store.ensure_seeded()


def codes(case_id: str) -> list[str]:
    return [r["code"] for r in bank.requirements(case_id)]


# ---------------------------------------------------------------- six use cases ↔ six presenter test cases
def test_six_use_cases_map_one_to_one_to_six_test_cases_and_their_own_cases():
    assert [u["id"] for u in USE_CASES] == [f"TC-0{i}" for i in range(1, 7)]
    assert [u["useCaseId"] for u in USE_CASES] == [f"UC-0{i}" for i in range(1, 7)]
    case_ids = [u["caseId"] for u in USE_CASES]
    assert len(set(case_ids)) == 6
    existing = {s["caseId"] for s in MANIFEST["featured"]} | {s["caseId"] for s in MANIFEST["scenarios"]}
    assert not set(case_ids) & existing                          # collision-free: no earlier scenario's case is reused
    for u in USE_CASES:
        case = bank.get_case(u["caseId"])
        assert case["use_case"] == u["useCaseId"] and case["display_number"] == u["caseDisplay"]
        assert case["banker"]["staff_id"] == "STAFF-DANA" and case["executive_demo"]
        assert u["packStatus"] == "READY" and u["steps"] and u["expectedCaseStatus"] == "READY_FOR_BANKER"


def test_the_manifest_checklists_are_exactly_what_the_policy_composes():
    for u in USE_CASES:
        engine = {r["code"]: r for r in bank.requirements(u["caseId"])}
        assert list(engine) == [r["code"] for r in u["requirements"]], u["id"]
        for r in u["requirements"]:
            got = engine[r["code"]]
            assert (got["title_he"], got["owner_he"], got["intake"]) == (r["titleHe"], r["ownerHe"], r["intake"]), r["code"]
            assert got["why_he"] and got["policy_version"].startswith("loan_policy@v")


def test_every_persona_is_consistent_across_manifest_case_and_session_rows():
    rows = {r["case_id"]: r for r in client_for().get("/api/session/demo/cases").json()}
    for u in USE_CASES:
        case = bank.get_case(u["caseId"])
        assert all(b["first_name_he"] in u["personaHe"] for b in case["borrowers"]), u["id"]
        row = rows[u["caseId"]]
        assert row["persona_id"] == case["persona_id"] and row["use_case"] == u["useCaseId"] and not row["qa"]
    # UC-01 reuses the seeded identity of case 002 (מיכל ברק): her two applications share one persona
    assert bank.get_case("DEMO-MTZ-2026-002")["persona_id"] == bank.get_case("DEMO-MTZ-2026-101")["persona_id"]
    # the Lavi (לביא) and Levy (לוי) families never share a persona; QA cases have none
    assert bank.persona_of("DEMO-MTZ-2026-001") != bank.persona_of("DEMO-MTZ-2026-006")
    assert all(rows[c]["qa"] and not rows[c]["persona_id"] for c in ("DEMO-MTZ-2026-003", "DEMO-MTZ-2026-004", "DEMO-MTZ-2026-005"))


def test_profiles_get_different_checklists_without_duplicates():
    salaried, exempt, registered, mixed = (set(codes(f"DEMO-MTZ-2026-10{i}")) for i in (1, 2, 3, 4))
    assert "PAYSLIPS:BRW-C" in salaried and not {c for c in salaried if c.startswith(("TAX_", "VAT_", "PNL_"))}
    assert {"TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= exempt
    assert not {c for c in exempt if c.startswith(("PAYSLIPS", "PNL_", "VAT_DEALER"))}      # no VAT returns from a פטור
    assert {"TAX_ASSESSMENT:BRW-A", "VAT_DEALER_CERT:BRW-A", "PNL_STATEMENT:BRW-A"} <= registered
    assert {"PAYSLIPS:BRW-A", "TAX_ASSESSMENT:BRW-A", "VAT_EXEMPT_CERT:BRW-A"} <= mixed
    for i in range(1, 7):
        cs = codes(f"DEMO-MTZ-2026-10{i}")
        assert len(cs) == len(set(cs))
    m = codes("DEMO-MTZ-2026-104")
    assert sum(c.startswith("ID_CARD") for c in m) == 1 and sum(c.startswith("BANK_STATEMENTS") for c in m) == 1


def test_joint_applicants_own_their_requirements_and_a_joint_account_holder_is_not_a_borrower():
    reqs = {r["code"]: r for r in bank.requirements("DEMO-MTZ-2026-105")}
    assert reqs["PAYSLIPS:BRW-A"]["owner_he"] == "רועי שטרן" and "PAYSLIPS:BRW-B" not in reqs
    assert reqs["TAX_ASSESSMENT:BRW-B"]["owner_he"] == "מאיה שטרן" and "TAX_ASSESSMENT:BRW-A" not in reqs
    assert reqs["BANK_STATEMENTS:ACC-1"]["holders"] == ["BRW-A", "BRW-B"]           # one shared statement requirement
    assert reqs["BANK_STATEMENTS:ACC-2"]["holders"] == ["BRW-A"]                     # רחל is a holder, not a borrower
    assert {b["borrower_id"] for b in bank.get_case("DEMO-MTZ-2026-105")["borrowers"]} == {"BRW-A", "BRW-B"}
    assert not any("HLD-RACHEL" in r["holders"] for r in reqs.values())


def test_the_company_path_is_limited_banker_assisted_and_free_of_consumer_rules():
    case = bank.get_case("DEMO-MTZ-2026-106")
    assert case["applicant_type"] == "company" and case["banker_assisted"]
    assert case["loan"]["product"] == "business_financing.inquiry"
    reqs = bank.requirements("DEMO-MTZ-2026-106")
    ids = {r["requirement_id"] for r in reqs}
    assert not ids & {"PAYSLIPS", "BANK_STATEMENTS", "PURPOSE_PROOF", "TAX_ASSESSMENT"}
    assert {r["intake"] for r in reqs if r["requirement_id"] != "ID_CARD"} == {"human_review"}
    assert case["document_profile"]["banker_assisted"] and case["document_profile"]["entity"] == "company"


# ---------------------------------------------------------------- honest intake for a family without a rubric
def test_an_upload_without_a_rubric_is_stored_for_the_banker_and_never_marked_valid():
    case_id = "DEMO-MTZ-2026-106"
    repo.reset_case(case_id)
    c = client_for(case_id)
    with (PACK / "company_extract_sg.pdf").open("rb") as fh:
        r = c.post(f"/api/cases/{case_id}/documents", data={"requirement_code": "COMPANY_EXTRACT"},
                   files={"file": ("company_extract.pdf", fh, "application/pdf")})
    assert r.status_code == 202, r.text
    doc = r.json()["document"]
    assert doc["status"] == "stored" and doc["review"] is None
    assert not db.query("SELECT 1 FROM jobs WHERE document_id=?", (doc["document_id"],))      # no AI review queued
    state = readiness.compute(case_id)
    req = next(q for q in state["requirements"] if q["code"] == "COMPANY_EXTRACT")
    assert req["ai_state"] == "received_pending_review" and req["units_verified"] == 0
    snap = c.get(f"/api/cases/{case_id}").json()
    assert snap["outcomes"]["documents"][doc["document_id"]]["outcome"] == "HUMAN_REVIEW_PENDING"
    assert state["progress"]["human_review_received"] == 1
    repo.reset_case(case_id)


# ---------------------------------------------------------------- new-customer questionnaire
def run(answers: list[tuple[str, object]]) -> tuple[TestClient, str, dict]:
    c = TestClient(app)
    d = c.post("/api/demo/onboarding").json()
    for qid, value in answers:
        assert d["next"]["question_id"] == qid, (d["next"], qid)
        r = c.post(f"/api/demo/onboarding/{d['draft_id']}/answers", json={"question_id": qid, "value": value})
        assert r.status_code == 200, r.text
        d = r.json()
    assert d["next"] is None and d["summary"]
    return c, d["draft_id"], d


ME = [("entity", "individual"), ("name", {"first": "דנה", "last": "רז"}), ("national_id", "DEMO-ID-301"), ("purpose", "car")]
TAIL = [("amount", 80000), ("payments", 60)]


def summary_codes(d: dict) -> list[str]:
    return [r["code"] for r in d["summary"]["requirements"]]


def test_a_salaried_customer_creates_one_persisted_case_once():
    c, draft, d = run(ME + [("income", ["salaried"]), ("net", 12000), ("co_borrower", "no")] + TAIL)
    assert summary_codes(d) == ["ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"]
    assert not any(r["case_id"].startswith("DEMO-LN") and r.get("persona_id", "").endswith(draft[-4:])
                   for r in c.get("/api/session/demo/cases").json())                       # a draft is not a case
    first = c.post(f"/api/demo/onboarding/{draft}/confirm").json()
    again = c.post(f"/api/demo/onboarding/{draft}/confirm").json()
    assert first["created"] and not again["created"] and first["case_id"] == again["case_id"]
    case_id = first["case_id"]
    assert codes(case_id) == summary_codes(d)
    rows = {r["case_id"]: r for r in c.get("/api/session/demo/cases").json()}
    assert rows[case_id]["persona_id"].startswith("PRS-NEW-") and rows[case_id]["applicants_he"] == ["דנה רז"]
    snap = c.get(f"/api/cases/{case_id}").json()
    assert snap["readiness"]["state"] == "NOT_CHECKED" and snap["case"]["document_profile"]["entity"] == "individual"
    assert c.post(f"/api/demo/onboarding/{draft}/answers", json={"question_id": "net", "value": 9000}).status_code == 409
    assert not db.query("SELECT 1 FROM completion_tasks WHERE case_id=?", (case_id,))       # no follow-up for a new case


def test_concurrent_confirmations_create_one_case():
    from concurrent.futures import ThreadPoolExecutor
    c, draft, _ = run(ME + [("income", ["salaried"]), ("net", 12000), ("co_borrower", "no")] + TAIL)
    before = db.one("SELECT COUNT(*) AS n FROM demo_applications")["n"]
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: TestClient(app).post(f"/api/demo/onboarding/{draft}/confirm").json(), range(4)))
    assert len({r["case_id"] for r in results}) == 1 and sum(r["created"] for r in results) == 1
    assert db.one("SELECT COUNT(*) AS n FROM demo_applications")["n"] == before + 1


def test_self_employed_mixed_joint_and_company_answers_compose_different_checklists():
    _, _, exempt = run(ME + [("income", ["self_employed"]), ("registration", "vat_exempt"), ("net", 9000),
                             ("co_borrower", "no")] + TAIL)
    assert summary_codes(exempt) == ["ID_CARD:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF", "TAX_ASSESSMENT:BRW-A",
                                     "VAT_EXEMPT_CERT:BRW-A"]
    _, _, mixed = run(ME + [("income", ["salaried", "self_employed"]), ("registration", "vat_registered"), ("net", 20000),
                            ("co_borrower", "no")] + TAIL)
    m = summary_codes(mixed)
    assert {"PAYSLIPS:BRW-A", "TAX_ASSESSMENT:BRW-A", "VAT_DEALER_CERT:BRW-A", "PNL_STATEMENT:BRW-A"} <= set(m)
    assert m.count("ID_CARD:BRW-A") == 1 and len(m) == len(set(m))
    _, _, joint = run(ME + [("income", ["salaried"]), ("net", 12000), ("co_borrower", "yes"),
                            ("co_name", {"first": "יוני", "last": "רז"}), ("co_national_id", "DEMO-ID-302"),
                            ("co_income", ["self_employed"]),
                            ("co_registration", "vat_exempt"), ("co_net", 8000), ("accounts", "joint")] + TAIL)
    j = {r["code"]: r for r in joint["summary"]["requirements"]}
    assert j["PAYSLIPS:BRW-A"]["owner_he"] == "דנה רז" and j["VAT_EXEMPT_CERT:BRW-B"]["owner_he"] == "יוני רז"
    assert [k for k in j if k.startswith("BANK_STATEMENTS")] == ["BANK_STATEMENTS:ACC-1"]   # one joint account
    c, draft, company = run([("entity", "company"), ("company_name", "אלפא מערכות בע״מ"),
                             ("signatory", {"first": "רון", "last": "לב"}), ("signatory_id", "DEMO-ID-303"),
                             ("company_purpose", "business_equipment"),
                             ("business_amount", 300000), ("payments", 60)])
    assert company["summary"]["profile"]["banker_assisted"]
    assert {r["code"] for r in company["summary"]["requirements"]} == {
        "ID_CARD:BRW-A", "COMPANY_EXTRACT", "SIGNATORY_AUTHORITY", "COMPANY_FINANCIALS", "COMPANY_INTERIM",
        "BUSINESS_STATEMENTS:ACC-1"}
    case_id = c.post(f"/api/demo/onboarding/{draft}/confirm").json()["case_id"]
    assert bank.get_case(case_id)["applicant_type"] == "company"


def test_a_correction_before_confirmation_changes_the_branch_and_the_checklist():
    c, draft, d = run(ME + [("income", ["self_employed"]), ("registration", "vat_registered"), ("net", 15000),
                            ("co_borrower", "no")] + TAIL)
    assert "PNL_STATEMENT:BRW-A" in summary_codes(d)
    d = c.post(f"/api/demo/onboarding/{draft}/answers", json={"question_id": "income", "value": ["salaried"]}).json()
    assert d["next"] is None and "registration" not in {a["question_id"] for a in d["asked"]}
    assert "PAYSLIPS:BRW-A" in summary_codes(d) and "PNL_STATEMENT:BRW-A" not in summary_codes(d)
    bad = c.post(f"/api/demo/onboarding/{draft}/answers", json={"question_id": "registration", "value": "vat_exempt"})
    assert bad.status_code == 422                                   # not asked for a salaried-only applicant
    # clearing and re-answering the income keeps the hidden VAT answer: mixed income needs no second VAT question
    c.post(f"/api/demo/onboarding/{draft}/answers", json={"question_id": "income", "value": None})
    d = c.post(f"/api/demo/onboarding/{draft}/answers",
               json={"question_id": "income", "value": ["salaried", "self_employed"]}).json()
    assert d["next"] is None and {"PAYSLIPS:BRW-A", "PNL_STATEMENT:BRW-A"} <= set(summary_codes(d))
    assert c.post(f"/api/demo/onboarding/{draft}/confirm").status_code == 200


def test_an_unfinished_draft_cannot_be_confirmed_and_resumes_where_it_stopped():
    c = TestClient(app)
    d = c.post("/api/demo/onboarding").json()
    c.post(f"/api/demo/onboarding/{d['draft_id']}/answers", json={"question_id": "entity", "value": "individual"})
    assert c.post(f"/api/demo/onboarding/{d['draft_id']}/confirm").status_code == 409
    resumed = c.get(f"/api/demo/onboarding/{d['draft_id']}").json()
    assert resumed["next"]["question_id"] == "name" and resumed["status"] == "draft" and resumed["case_id"] is None
    c.post(f"/api/demo/onboarding/{d['draft_id']}/answers", json={"question_id": "name", "value": {"first": "נטע", "last": "אלון"}})
    for bad in ("123456789", "DEMO-201", "<script>"):
        assert c.post(f"/api/demo/onboarding/{d['draft_id']}/answers",
                      json={"question_id": "national_id", "value": bad}).status_code == 422, bad
    ok = c.post(f"/api/demo/onboarding/{d['draft_id']}/answers", json={"question_id": "national_id", "value": "311204572"})
    assert ok.status_code == 200 and ok.json()["next"]["question_id"] == "purpose"
    assert c.post(f"/api/demo/onboarding/{d['draft_id']}/answers",
                  json={"question_id": "name", "value": {"first": "<b>", "last": "x"}}).status_code == 422


# ---------------------------------------------------------------- existing data directories
def test_the_seed_upgrade_adds_new_requirements_once_and_keeps_admin_removals(monkeypatch):
    seed = store.seed_config("loan_policy")
    old = {**seed, "document_requirements": [r for r in seed["document_requirements"]
                                             if r["id"] in ("ID_CARD", "PAYSLIPS", "BANK_STATEMENTS", "PURPOSE_PROOF")]}
    old["product"] = {**seed["product"], "purposes": {k: v for k, v in seed["product"]["purposes"].items()
                                                      if v.get("entity", "individual") == "individual"}}
    row = {**store.published("loan_policy"), "config": old}
    monkeypatch.setattr(store, "published", lambda kind: row)
    monkeypatch.setattr(store, "versions", lambda kind: [row])
    calls = []
    monkeypatch.setattr(store, "create_draft", lambda kind, actor, config=None, reason="": calls.append(config) or
                        {"version_id": "X", "revision": 1})
    monkeypatch.setattr(store, "publish", lambda vid, rev, actor: {"version_id": vid})
    assert store.upgrade_from_seed() == {"version_id": "X"}
    upgraded = calls[0]
    assert {r["id"] for r in upgraded["document_requirements"]} == {r["id"] for r in seed["document_requirements"]}
    by_id = {r["id"]: r for r in upgraded["document_requirements"]}
    assert by_id["BANK_STATEMENTS"]["condition"]["entity"] == ["individual"] and "business_equipment" in upgraded["product"]["purposes"]
    # a requirement the Admin removed in an earlier version is not brought back
    removed = {**row, "config": {**old, "document_requirements": old["document_requirements"][:-1]}}
    monkeypatch.setattr(store, "published", lambda kind: removed)
    monkeypatch.setattr(store, "versions", lambda kind: [removed, row])
    calls.clear()
    store.upgrade_from_seed()
    assert "PURPOSE_PROOF" not in {r["id"] for r in calls[0]["document_requirements"]}


def test_existing_cases_keep_exactly_the_four_requirement_package():
    for cid in ("DEMO-MTZ-2026-006", "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-002"):
        case = bank.get_case(cid)
        pol, row = store.policy()
        heads = [r["code"].split(":")[0] for r in requirements.compose(case, pol, row["label"])]
        assert sorted(set(heads)) == ["BANK_STATEMENTS", "ID_CARD", "PAYSLIPS", "PURPOSE_PROOF"], cid


# ---------------------------------------------------------------- Round 2: document intelligence and profile changes
def test_new_rubrics_review_individuals_while_company_documents_stay_with_the_banker():
    intake = {r["code"]: r["intake"] for c in ("DEMO-MTZ-2026-102", "DEMO-MTZ-2026-103", "DEMO-MTZ-2026-106")
              for r in bank.requirements(c)}
    assert intake["VAT_EXEMPT_CERT:BRW-A"] == intake["PNL_STATEMENT:BRW-A"] == "ai_review"
    company = {r["code"]: r for r in bank.requirements("DEMO-MTZ-2026-106")}
    assert company["COMPANY_INTERIM"]["family"] == "pnl_statement" and company["COMPANY_INTERIM"]["intake"] == "human_review"
    assert company["ID_CARD:BRW-A"]["intake"] == "ai_review"
    vat = {r["code"]: r for r in bank.requirements("DEMO-MTZ-2026-102")}["VAT_EXEMPT_CERT:BRW-A"]
    assert vat["rules"]["registration"] == "vat_exempt"


def test_registration_and_pnl_checks_are_decided_by_code():
    from datetime import date
    from app.review import family_checks, rubrics
    yoav = {"borrower_id": "BRW-A", "name_he": "יואב כרמי", "national_id": "DEMO-ID-102"}
    def run(family, facts, rules):
        return family_checks.outcomes(family, rubrics.for_family(family), val=lambda n: facts.get(n), norm=lambda n: facts.get(n),
                                      as_of=date(2026, 10, 12), borrowers={"BRW-A": yoav}, assigned=yoav, matched="BRW-A",
                                      hits=[], unverified=[], present_decisive=list(facts), rules=rules, allowed_holders=None,
                                      labels={})
    ok = run("business_registration", {"holder_name": "יואב כרמי", "dealer_number": "DEMO-ID-102",
                                       "registration_type": "עוסק פטור"}, {"registration": "vat_exempt"})
    assert ok["BR-03"][0] == ok["BR-04"][0] == ok["BR-05"][0] == "PASS"
    wrong = run("business_registration", {"holder_name": "יואב כרמי", "dealer_number": "DEMO-ID-999",
                                          "registration_type": "עוסק מורשה"}, {"registration": "vat_exempt"})
    assert wrong["BR-04"][0] == "FAIL" and wrong["BR-05"][0] == "FAIL"
    stale = run("pnl_statement", {"holder_name": "יואב כרמי", "period_to": "2025-12-31", "issuer_name": "רו״ח"}, {"max_age_days": 120})
    fresh = run("pnl_statement", {"holder_name": "יואב כרמי", "period_from": "2026-01-01", "period_to": "2026-09-30"},
                {"max_age_days": 120})
    assert stale["PL-04"][0] == "FAIL" and fresh["PL-04"][0] == "PASS" and fresh["PL-05"][0] == "NEEDS_REVIEW"


def test_payslip_months_are_asked_only_of_borrowers_with_a_payslip_requirement():
    from tests.loan_helpers import run_case
    for case_id, expect in (("DEMO-MTZ-2026-102", set()), ("DEMO-MTZ-2026-105", {"BRW-A"}), ("DEMO-MTZ-2026-106", set())):
        repo.reset_case(case_id)
        run_case(case_id)
        who = {f["borrower_id"] for f in repo.findings(case_id, status="open") if f["code"] == "REQUIRED_PERIOD_MISSING"}
        assert who == expect, case_id
        repo.reset_case(case_id)


def test_a_banker_review_upload_resolves_its_follow_up_task():
    from app.followup import tasks
    from tests.loan_helpers import run_case
    case_id = "DEMO-MTZ-2026-106"
    repo.reset_case(case_id)
    c = client_for(case_id)
    with (PACK / "id_card_gilad.pdf").open("rb") as fh:                  # one document so the set review runs
        c.post(f"/api/cases/{case_id}/documents", data={"requirement_code": "ID_CARD:BRW-A"},
               files={"file": ("id.pdf", fh, "application/pdf")})
    run_case(case_id)
    tasks.sync(case_id)
    assert any(t["requirement_code"] == "COMPANY_EXTRACT" and t["status"] in tasks.OPEN for t in tasks.all_for(case_id))
    with (PACK / "company_extract_sg.pdf").open("rb") as fh:
        c.post(f"/api/cases/{case_id}/documents", data={"requirement_code": "COMPANY_EXTRACT"},
               files={"file": ("extract.pdf", fh, "application/pdf")})
    run_case(case_id)
    tasks.sync(case_id)
    task = next(t for t in tasks.all_for(case_id) if t["requirement_code"] == "COMPANY_EXTRACT")
    assert task["status"] == "RESOLVED" and "ממתין לבדיקת הבנקאי" in task["history"][-1]["note"]
    repo.reset_case(case_id)


def test_a_profile_change_recomposes_keeps_history_and_cancels_obsolete_follow_up():
    from app.followup import tasks
    from app.util import now_iso
    from tests.loan_helpers import run_case
    case_id = "DEMO-MTZ-2026-101"
    repo.reset_case(case_id)
    c = client_for(case_id)
    with (PACK / "payslip_michal_2026-07.pdf").open("rb") as fh:
        doc = c.post(f"/api/cases/{case_id}/documents", data={"requirement_code": "PAYSLIPS:BRW-C", "borrower_id": "BRW-C"},
                     files={"file": ("p.pdf", fh, "application/pdf")}).json()["document"]
    run_case(case_id)
    tasks.sync(case_id)
    payslip_tasks = [t["task_id"] for t in tasks.open_for(case_id) if t["requirement_code"] == "PAYSLIPS:BRW-C"]
    assert payslip_tasks
    now = now_iso()
    with db.tx() as cx:                                    # a simulated call queued about the payslips only
        cx.execute("INSERT INTO contact_attempts(attempt_id, case_id, channel, provider, simulated, idempotency_key, status,"
                   " task_ids, created_at, updated_at, history, request) VALUES ('ATT-T1',?,?,?,?,?,?,?,?,?,?,?)",
                   (case_id, "voice", "mock-talk", 1, "test-key-1", "QUEUED", db.jdump(payslip_tasks), now, now, "[]", "{}"))
    before = {r["code"] for r in bank.requirements(case_id)}
    r = c.post(f"/api/cases/{case_id}/profile",
               json={"borrowers": {"BRW-C": {"income_sources": ["self_employed"], "business_registration": "vat_exempt"}}})
    assert r.status_code == 200, r.text
    out = r.json()
    after = {q["code"] for q in out["requirements"]}
    assert "PAYSLIPS:BRW-C" in before and "PAYSLIPS:BRW-C" not in after
    assert {"TAX_ASSESSMENT:BRW-C", "VAT_EXEMPT_CERT:BRW-C"} <= after and out["removed_codes"] == ["PAYSLIPS:BRW-C"]
    assert set(out["tasks_canceled"]) == set(payslip_tasks) and out["calls_canceled"] == 1
    assert db.one("SELECT status FROM contact_attempts WHERE attempt_id='ATT-T1'")["status"] == "CANCELED"
    assert repo.document(doc["document_id"])                                       # the uploaded payslip is kept
    state = readiness.compute(case_id)
    assert [i["code"] for i in state["inactive_requirements"]] == ["PAYSLIPS:BRW-C"]
    assert not any(f["code"] == "REQUIRED_PERIOD_MISSING" for f in repo.findings(case_id, status="open"))
    case = bank.get_case(case_id)
    assert case["borrowers"][0]["borrower_id"] == "BRW-C" and case["borrowers"][0]["income_sources"] == ["self_employed"]
    assert case["document_profile"]["profile_label_he"] == "עצמאי/ת (עוסק פטור)"
    assert requirements.income_sources(bank.get_case("DEMO-MTZ-2026-002")["borrowers"][0]) == ["salaried"]   # 002 untouched
    staff = client_for(case_id)
    matrix = staff.get(f"/api/banker/cases/{case_id}/workspace").json()["requirement_matrix"]
    assert any(m.get("inactive") and m["code"] == "PAYSLIPS:BRW-C" for m in matrix)
    assert c.post(f"/api/cases/{case_id}/profile", json={"borrowers": {"BRW-C": {"income_sources": ["self_employed"]}}}
                  ).status_code == 422                                              # a self-employed profile needs its VAT status
    assert c.post("/api/cases/DEMO-MTZ-2026-106/profile", json={"borrowers": {}}).status_code in (403, 409)
    repo.reset_case(case_id)
    assert "PAYSLIPS:BRW-C" in {q["code"] for q in bank.requirements(case_id)}     # a reset restores the prepared profile
