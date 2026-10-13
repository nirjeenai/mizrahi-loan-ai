"""The customer-status precedence (pure; no database, no model)."""
from __future__ import annotations

from app.workflow.readiness import customer_status, policy_months

BASE = dict(required=6, documents=0, failed=0, review_failed=False, busy=False, reviewed_before=False,
            correction=0, missing=0, confirmed=False, banker=0, verified=0)


def status(**changes) -> str:
    return customer_status(**{**BASE, **changes})


def test_nothing_uploaded_is_awaiting_upload_even_without_findings():
    assert status(missing=6) == "AWAITING_UPLOAD"
    assert status() == "AWAITING_UPLOAD"


def test_first_review_versus_revalidation():
    assert status(documents=1, busy=True) == "PROCESSING"
    assert status(documents=4, busy=True, reviewed_before=True) == "REVALIDATING"


def test_work_in_progress_outranks_results_it_may_change():
    assert status(documents=4, busy=True, reviewed_before=True, correction=1, missing=2, banker=1) == "REVALIDATING"


def test_a_stopped_review_outranks_everything_after_upload():
    assert status(documents=3, failed=1, busy=True, missing=2) == "ERROR"
    assert status(documents=3, review_failed=True) == "ERROR"


def test_document_to_fix_outranks_missing_months():
    assert status(documents=2, reviewed_before=True, correction=1, missing=3) == "CORRECTION_REQUIRED"


def test_missing_months_including_a_duplicate():
    assert status(documents=3, reviewed_before=True, missing=2, verified=2) == "MISSING_DOCUMENTS"


def test_customer_action_outranks_banker_items():
    assert status(documents=6, reviewed_before=True, missing=1, banker=1, verified=5) == "MISSING_DOCUMENTS"


def test_banker_review_with_complete_or_incomplete_verification():
    assert status(documents=6, reviewed_before=True, banker=1, verified=6) == "BANKER_REVIEW"
    assert status(documents=6, reviewed_before=True, verified=5) == "BANKER_REVIEW"


def test_complete_needs_every_month_verified_not_just_an_empty_findings_list():
    assert status(documents=6, reviewed_before=True, verified=6) == "CHECKS_COMPLETE"
    assert status(documents=6, reviewed_before=True, verified=0) != "CHECKS_COMPLETE"


def test_banker_confirmation_only_without_customer_actions():
    assert status(documents=6, reviewed_before=True, confirmed=True, banker=1, verified=6) == "PREPARATION_CONFIRMED"
    assert status(documents=6, reviewed_before=True, confirmed=True, missing=1, verified=5) == "MISSING_DOCUMENTS"


def test_no_payslip_requirement():
    assert status(required=0, documents=2) == "NO_PAYSLIPS_REQUIRED"


def test_required_months_known_before_any_review():
    assert policy_months() == ["2026-07", "2026-08", "2026-09"]
