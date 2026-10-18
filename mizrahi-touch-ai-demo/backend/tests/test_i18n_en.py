"""The customer app's English (app/i18n): it only adds, and the Hebrew stays exactly as recorded.

- With `X-MZ-Lang` (he or en) every customer response is the Hebrew golden response plus `*_en` siblings: removing
  them gives back tests/golden/api_customer.json byte for byte.
- Every `*_en` value is English: no Hebrew letters (names of the synthetic people have Latin spellings).
- The English tables cover the Hebrew ones they mirror, so a new state, code or criterion cannot silently stay Hebrew.
- I18N_EN=0: the header is ignored."""
from __future__ import annotations

import dataclasses
import json
import re

import pytest

from app import config, i18n
from app.agent import tools
from app.bank import mock_bank
from app.followup import orchestrator
from app.i18n import en
from app.policy import store
from app.review import case_review as CR
from app.review import prompts as P
from app.review import reason_codes as RC
from app.workflow import outcomes, readiness, requirements

from .golden_util import check
from .test_golden_hebrew_api import customer_api, seeded  # noqa: F401  (the same seeded cases)

HEBREW = re.compile(r"[֐-׿]")
ADDED = re.compile(r"(_en|message_detail_he)$")


def strip_english(v):
    if isinstance(v, dict):
        return {k: strip_english(x) for k, x in v.items() if not ADDED.search(k)}
    if isinstance(v, list):
        return [strip_english(x) for x in v]
    return v


def english_values(v, path=""):
    if isinstance(v, dict):
        for k, x in v.items():
            if k.endswith("_en"):
                yield from ((f"{path}.{k}", s) for s in (x if isinstance(x, list) else [x]) if isinstance(s, str))
            yield from english_values(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from english_values(x, f"{path}[{i}]")


@pytest.mark.parametrize("lang", ["he", "en"])
def test_the_language_header_only_adds_english_siblings(lang):
    out = customer_api({"X-MZ-Lang": lang})
    check("api_customer", strip_english(out))          # the Hebrew golden, byte for byte


def test_english_siblings_are_english_and_cover_the_customer_screens():
    out = customer_api({"X-MZ-Lang": "en"})
    hebrew = [(p, s) for p, s in english_values(out) if HEBREW.search(s)]
    assert not hebrew, hebrew[:5]
    snap = out["DEMO-MTZ-2026-011"]["snapshot"]
    for q in snap["readiness"]["requirements"]:
        assert q["title_en"] and q["family_en"] and q["ai_state_en"] and q["why_en"] and q["owner_en"], q["code"]
    assert {q["code"]: q["title_en"] for q in snap["readiness"]["requirements"]}["PAYSLIPS:BRW-A"] == "Last 3 payslips — Ido"
    assert snap["readiness"]["state_en"] == "Action needed from you" and snap["case"]["title_en"] == "Income gap · case F"
    assert snap["case"]["banker"]["name_en"] == "Dana Cohen" and snap["case"]["bank_stage"]["label_en"] == "Document completion"
    for f in snap["findings"]:
        assert f["title_en"], f["code"]
    titles = {f["code"]: f["title_en"] for f in snap["findings"]}
    assert titles["REQUIRED_PERIOD_MISSING"] == "Payslip for September 2026 missing — Ido"
    assert titles["DOCUMENT_UNREADABLE"] == "The document can't be read"
    for a in snap["available_actions"]:
        assert a["label_en"], a["action_id"]
    assert snap["customer_requests"][0]["title_en"] == "Payslip for September 2026 needed — Ido"
    assert snap["customer_requests"][0]["message_he"] and "message_en" not in snap["customer_requests"][0]   # banker's words
    for group in snap["outcomes"].values():
        for o in group.values():
            assert o["label_en"]
    # the reviewer's own explanation stays the original, marked as such
    unreadable = next(f for f in snap["findings"] if f["code"] == "MANDATORY_FIELD_MISSING")
    assert unreadable["message_en"] == "A required detail is missing in car_quote.pdf." and unreadable["message_detail_he"]
    assert out["upload_duplicate"]["body"]["note_en"].startswith("This file was already uploaded")
    assert out["resolve_unknown_action"]["body"]["detail_en"] == "This action no longer applies to your application."
    assert out["unknown_draft"]["body"]["detail_en"].startswith("This draft wasn't found")
    page = next(iter(out["DEMO-MTZ-2026-009"]["document_pages"].values()))["document"]
    assert page["review"]["doc_type_en"] and all(c["title_en"] for c in page["review"]["criteria"])
    assert all(f["label_en"] for f in page["review"]["facts"])


def test_english_is_off_without_the_switch(monkeypatch):
    monkeypatch.setattr(i18n, "settings", dataclasses.replace(config.settings, i18n_en=False))
    out = customer_api({"X-MZ-Lang": "en"})
    assert not list(english_values(out))
    check("api_customer", out)


# ---------------------------------------------------------------- the English tables cover the Hebrew ones
def test_tables_cover_every_hebrew_vocabulary():
    assert set(readiness.STATE_HE) <= set(en.READINESS)
    assert set(readiness.REQ_STATE_HE) <= set(en.AI_STATE)
    assert set(outcomes.OUTCOME_HE) <= set(en.OUTCOME)
    assert set(tools.STAGE_HE) <= set(en.DOC_STAGE)
    assert set(P.FIELD_LABELS_HE) <= set(en.FIELDS) and set(P.DOC_TYPES_HE) <= set(en.DOC_TYPES)
    assert set(requirements.FAMILY_HE) <= set(en.FAMILY)
    assert set(requirements.ENTITY_HE) <= set(en.ENTITY) and set(requirements.ROLE_HE) <= set(en.ROLE)
    assert set(requirements.INCOME_HE) <= set(en.INCOME) and set(requirements.REGISTRATION_HE) <= set(en.REGISTRATION)
    assert set(orchestrator.CUSTOMER_STATE_HE.values()) <= set(en.FOLLOWUP_STATE)
    assert set(RC.CUSTOMER_SHORT) <= set(en.CUSTOMER_TEXT)
    assert set(RC.DOCUMENT) <= set(en.DOC_FINDINGS) and set(RC.UNCERTAIN) <= set(en.UNCERTAIN_FINDINGS)
    assert set(CR.DOC_FINDING_TEXT) <= set(en.PAYSLIP_FINDINGS) | set(en.DOC_FINDINGS)
    assert set(CR.DOC_FINDING_UNCERTAIN_TEXT) <= set(en.UNCERTAIN_FINDINGS)
    assert {s["code"] for s in mock_bank.STAGE_DICTIONARY} <= set(en.BANK_STAGES)


def test_tables_cover_the_policy_the_rubrics_and_the_demo_people():
    store.ensure_seeded()
    pol = store.published("loan_policy")["config"]
    for r in pol["document_requirements"]:
        assert r["id"] in en.REQUIREMENTS, r["id"]
        assert len(en.REQUIREMENTS[r["id"]][3]) == len(r.get("alternatives_he") or []), r["id"]
    assert set(pol["product"]["purposes"]) <= set(en.PURPOSES)
    paths = sorted(config.settings.rubrics_dir.glob("*.json"))
    assert paths
    for path in paths:
        for c in json.loads(path.read_text(encoding="utf8"))["criteria"]:
            assert c["id"] in en.CRITERIA, (path.name, c["id"])
    cases = [mock_bank.bank.get_case(cid) for cid in mock_bank.bank.case_ids() if cid.startswith("DEMO-MTZ")]
    assert en.case_title("הלוואה לכל מטרה · רכישת רכב") == "All-purpose loan · Buying a car"
    for c in cases:
        assert c["title_he"] in en.CASE_TITLES, c["title_he"]
        for b in c["borrowers"]:
            assert b["name_he"] in en.NAMES and b["first_name_he"] in en.NAMES, b["name_he"]
        assert c["banker"]["name_he"] in en.NAMES and c["banker"]["role_he"] in en.BANKER_ROLES
        for a in c.get("accounts") or []:
            assert not HEBREW.search(en.account_label(a["label_he"])), a["label_he"]
