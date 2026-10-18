"""The banker review desk in English: with `X-MZ-Lang` the staff responses (case list, package, workspace, intelligence)
gain `*_en` / `*En` siblings from the staff catalogue and keep every original value; without the header they are exactly
what they were. The desk's refusals carry `detail_en`. Cases are built from stored reviews, Gemini is never called."""
from __future__ import annotations

import json
from typing import Any

import pytest

from app import db
from app.i18n import staff_en
from app.review import case_review
from app.store import repo
from tests.loan_helpers import client_for, id_card, purpose, run_case, statement
from tests.test_review_desk import add_doc

PARTIAL, GAP = "DEMO-MTZ-2026-009", "DEMO-MTZ-2026-011"
staff = client_for()
EN = {"X-MZ-Lang": "en"}
VOLATILE = {"generated_at"}


@pytest.fixture(autouse=True)
def cases(monkeypatch):
    for case in (PARTIAL, GAP):
        repo.reset_case(case)
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
    monkeypatch.setattr(case_review, "_semantic", lambda req, borrowers, income: {"borrowers": [
        {"borrower_id": bid, "definitions_equivalent": True, "income_assessment": "CONSISTENT", "explanation_he": "",
         "evidence_needed_he": [], "identity_assessment": "CONSISTENT"} for bid, s in income.items() if s.get("months")],
        "limitations_he": []})
    # a partial package: two payslips and an ID card, so months, a statement and the purpose proof are missing
    for m in ("2026-07", "2026-08"):
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=PARTIAL)
    id_card(PARTIAL)
    run_case(PARTIAL)
    # a complete package whose payslips are well below the declared income: an open income finding for the banker
    for m in ("2026-07", "2026-08", "2026-09"):
        add_doc("BRW-A", m, 11000, f"ido_{m}.pdf", case=GAP)
    id_card(GAP)
    statement(GAP)
    purpose(GAP)
    run_case(GAP)
    yield


def _english_key(key: str) -> bool:
    return key.endswith("_en") or key.endswith("En")


def _strip(value: Any) -> Any:
    """the response without its English siblings and without the per-request timestamp"""
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if not (isinstance(k, str) and (_english_key(k) or k in VOLATILE))}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _english_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [k for k in value if isinstance(k, str) and _english_key(k)] + [x for v in value.values() for x in _english_keys(v)]
    if isinstance(value, list):
        return [x for v in value for x in _english_keys(v)]
    return []


def staff_en_texts(value: Any) -> list[str]:
    """every Hebrew string `staff_en.coverage` counts"""
    if isinstance(value, dict):
        return [x for k, v in value.items() if not (isinstance(k, str) and (k in staff_en.SKIP_TREES or k in staff_en.SKIP_KEYS
                                                                           or _english_key(k))) for x in staff_en_texts(v)]
    if isinstance(value, list):
        return [x for v in value for x in staff_en_texts(v)]
    return [value] if isinstance(value, str) and staff_en.HE.search(value) else []


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _get(url: str, headers: dict | None = None) -> Any:
    r = staff.get(url, headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()


URLS = ["/api/banker/cases"] + [f"/api/banker/cases/{c}/{area}" for c in (PARTIAL, GAP)
                                for area in ("package", "workspace", "intelligence")]


@pytest.mark.parametrize("url", URLS)
def test_english_only_adds_siblings_and_hebrew_is_unchanged(url):
    he = _get(url)
    assert _english_keys(he) == [], "a header-less response gained English"
    en = _get(url, EN)
    assert _english_keys(en), "the English response has no English siblings"
    assert _dump(_strip(en)) == _dump(_strip(he))


def test_workspace_english_coverage_and_terms():
    he = _get(f"/api/banker/cases/{GAP}/workspace")
    seen, missing = staff_en.coverage(he)
    distinct, untranslated = len(set(staff_en_texts(he))), set(missing)
    # what stays Hebrew is the reviewer's own wording (the stored reviews' "עבר" / "סיכום") and their fact labels
    assert seen > 100 and 1 - len(untranslated) / distinct >= 0.9, (distinct, sorted(untranslated)[:30])
    en = _get(f"/api/banker/cases/{GAP}/workspace", EN)
    groups = {g["key"]: g["title_en"] for g in en["groups"]}
    assert groups["decide"] == "Awaiting your decision" and groups["missing"] == "Missing documents"
    finding = next(i for i in en["items"] if i["kind"] == "case_finding")
    assert finding["title_en"] == "Gap between declared income and payslips, Ido"
    assert finding["income"]["documented_label_en"] == "on average across the 3 payslips"
    partial = _get(f"/api/banker/cases/{PARTIAL}/workspace", EN)
    month = next(i for i in partial["items"] if i["id"] == "missing:BRW-A:2026-09")
    assert month["title_en"] == "September 2026 payslip · Ido"
    assert month["draft"]["message_he"].startswith("שלום עידו") and month["draft"]["message_en"].startswith("Hello Ido, ")
    assert partial["can_confirm"]["reason_en"].split(" · ")[:2] == ["One payslip missing", "Missing: Bank statement, Proof of purpose"]


def test_desk_refusals_carry_english_detail():
    body = {"action": "accept", "request_id": "req-i18n-refusal"}
    r = staff.post(f"/api/banker/cases/{PARTIAL}/documents/DOC-NOT-HERE/decision", json=body, headers=EN)
    assert r.status_code == 404
    assert r.json() == {"detail": "המסמך אינו שייך לתיק.", "detail_en": "The document doesn't belong to this case."}
    assert staff.post(f"/api/banker/cases/{PARTIAL}/documents/DOC-NOT-HERE/decision", json=body).json() == \
        {"detail": "המסמך אינו שייך לתיק."}
    assert not repo.decisions(PARTIAL)
