"""Every test runs against a throw-away data directory, set before any app module reads its settings,
so no test can touch backend/data. Gemini is disabled; tests that need a review insert it themselves."""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="mcs-tests-")
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_MAX_CALLS_PER_HOUR"] = "0"

import pytest  # noqa: E402


def payslip_only_version() -> str:
    """A loan-policy version that requires payslips only — the payslip regression suites run against it, so the
    payslip workflow is tested on its own while the product default requires the full loan package."""
    from app import db
    from app.policy import store
    row = db.one("SELECT version_id FROM config_versions WHERE change_reason='tests: payslips only'")
    if row:
        return row["version_id"]
    config = store.published("loan_policy")["config"]
    config = {**config, "document_requirements": [r for r in config["document_requirements"] if r["id"] == "PAYSLIPS"]}
    draft = store.create_draft("loan_policy", "tests", config=config, reason="tests: payslips only")
    with db.tx() as c:
        c.execute("UPDATE config_versions SET status='ARCHIVED' WHERE version_id=?", (draft["version_id"],))
    return draft["version_id"]


def pin_cases(version_id: str, case_ids=None) -> None:
    from app import db
    from app.bank.mock_bank import bank
    with db.tx() as c:
        for cid in case_ids or bank.case_ids():
            c.execute("INSERT OR REPLACE INTO case_profile(case_id, requirement_set_version, pinned_at) VALUES (?,?,?)",
                      (cid, version_id, "2026-10-13T00:00:00+00:00"))


@pytest.fixture
def payslip_scope(monkeypatch):
    """Every case reads the payslip-only policy version, even after a reset inside the test."""
    from app import db
    from app.workflow import requirements
    db.connect()
    version = payslip_only_version()
    monkeypatch.setattr(requirements, "pin", lambda case_id: version)
    yield
