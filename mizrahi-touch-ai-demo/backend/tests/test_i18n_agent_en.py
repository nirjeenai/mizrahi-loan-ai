"""The in-app assistant for an English customer app (app/i18n/agent_en.py, agent.respond(lang=...)).

- An English session: English system prompt, English reply (model or the no-model fallback from case data), English guard;
  both turns are marked lang=en.
- A Hebrew session with the header: the Hebrew assistant exactly, plus an English twin of a reply the code wrote.
- Follow-ups after an assistant-started upload carry their English when the app sent its language, and nothing otherwise.
- The tools (shared with the MCP server) are untouched: no English in their results."""
from __future__ import annotations

import re

import pytest

from app.agent import agent, continuation, tools
from app.i18n import agent_en
from app.llm import gemini as g
from app.store import repo
from app.util import now_iso
from tests.loan_helpers import client_for, run_case
from tests.test_review_desk import add_doc

from .test_golden_hebrew_api import FULL, GAPS, customer_api, seeded  # noqa: F401  (the seeded cases)

HEBREW = re.compile(r"[֐-׿]")


def _seed_gaps() -> None:
    for m in ("2026-07", "2026-08"):
        add_doc("BRW-A", m, 14700, f"ido_{m}.pdf", case=GAPS)
    run_case(GAPS)


@pytest.mark.parametrize("text,blocked", [
    ("Your loan is approved.", True), ("Good news: the application has been approved", True),
    ("This is the final approval.", True), ("Your application is complete.", True), ("An interest rate of 4.5%", True),
    ("The bank accepted the document.", True), ("Your loan is not approved yet; the banker decides.", False),
    ("The payslip for September 2026 is still missing.", False), ("No decision has been made; it isn't approved.", False),
])
def test_the_english_guard(text, blocked):
    assert agent_en.blocked(text) is blocked


def test_an_english_session_without_a_model_answers_from_case_data_in_english():
    _seed_gaps()
    c = client_for(GAPS)
    r = c.post(f"/api/cases/{GAPS}/agent/messages", json={"text": "What am I missing?", "channel": "text"},
               headers={"X-MZ-Lang": "en"}).json()
    assert r["fallback"] is True and not HEBREW.search(r["reply"]), r["reply"]
    assert r["reply"].startswith("Your application's stage in the bank's system: Document completion.")
    assert "Items for you: 4, items for the banker's review: 1. Missing: ID card — Ido." in r["reply"]     # as the Hebrew
    turns = c.get(f"/api/cases/{GAPS}/conversation", headers={"X-MZ-Lang": "en"}).json()
    assert [t["provenance"]["lang"] for t in turns[-2:]] == ["en", "en"]
    assert all(a.get("label_en") for a in turns[-1]["actions"]), turns[-1]["actions"]
    plain = c.get(f"/api/cases/{GAPS}/conversation").json()
    assert all("lang" not in (t["provenance"] or {}) and "text_en" not in (t["provenance"] or {}) for t in plain)


def test_a_hebrew_session_keeps_the_hebrew_answer_and_stores_its_english_twin():
    _seed_gaps()
    c = client_for(GAPS)
    plain = c.post(f"/api/cases/{GAPS}/agent/messages", json={"text": "מה חסר לי?"}).json()
    he = c.post(f"/api/cases/{GAPS}/agent/messages", json={"text": "מה חסר לי?"}, headers={"X-MZ-Lang": "he"}).json()
    assert he["reply"] == plain["reply"] and HEBREW.search(he["reply"])
    assert he["reply_en"] == agent_en.fallback(GAPS) and "reply_en" not in plain
    turn = repo.turn(he["turn_id"])
    assert turn["provenance"]["text_en"] == he["reply_en"] and "lang" not in turn["provenance"]


def test_a_live_english_turn_uses_the_english_prompt_and_the_english_guard(monkeypatch):
    _seed_gaps()
    seen: list[str] = []
    replies = iter(["Your loan is approved!", "The payslip for September 2026 is still missing.", "חסר תלוש ספטמבר 2026."])

    def fake_generate(model, contents, *, system=None, **kw):
        seen.append(system)
        return {"candidates": [{"content": {"role": "model", "parts": [{"text": next(replies)}]}}]}
    monkeypatch.setattr(g, "generate", fake_generate)
    monkeypatch.setattr(g, "response_text", lambda data: data["candidates"][0]["content"]["parts"][0]["text"])
    first = agent.respond(GAPS, "Is my loan approved?", lang="en")
    assert first["guard"]["blocked"] and first["reply"] == agent_en.SAFE_REPLY and first["actions"] == []
    second = agent.respond(GAPS, "What am I missing?", lang="en")
    assert not second["guard"]["blocked"] and second["reply"] == "The payslip for September 2026 is still missing."
    assert all(s.startswith("You are the digital assistant for loan applications at Mizrahi-Tefahot.") for s in seen)
    assert "Answer in English" in seen[0] and "Ido" in seen[0] and not HEBREW.search(seen[0])
    hebrew = agent.respond(GAPS, "מה חסר לי?")
    assert seen[-1].startswith("אתה העוזר הדיגיטלי") and "lang" not in repo.turn(hebrew["turn_id"])["provenance"]


def test_a_followup_after_an_assistant_upload_carries_its_english_only_with_the_header():
    _seed_gaps()
    for lang in ("he", None):
        origin = repo.add_turn(GAPS, "text", "assistant", "אפשר להעלות עכשיו:", {"actions": []})
        doc = add_doc("BRW-A", "2026-09", 14700, f"ido_2026_09_{lang}.pdf", case=GAPS)
        repo.save_upload_intent({"document_id": doc, "case_id": GAPS, "requirement_code": "PAYSLIPS:BRW-A",
                                 "expected_period": "2026-09", "action_id": None, "origin_turn_id": origin["turn_id"],
                                 "created_new": 1, "created_at": now_iso()})
        run_case(GAPS)
        posted = continuation.sync_conversation(GAPS, lang)
        turn = repo.turn(posted["turn_id"]) if posted else None
        assert turn and HEBREW.search(turn["text"])
        if lang:
            assert turn["provenance"]["text_en"].startswith("Ido's payslip for September 2026 was received and checked")
            assert not HEBREW.search(turn["provenance"]["text_en"])
        else:
            assert "text_en" not in turn["provenance"]


def test_the_shared_tools_answer_exactly_as_before():
    _seed_gaps()
    ctx = {"case_id": GAPS, "channel": "mcp", "actor": "customer", "turn_id": None, "trace_id": "TR-TEST"}
    for name in ("get_case_overview", "list_open_items"):
        out = tools.call(name, GAPS, {}, ctx)
        assert HEBREW.search(out["spoken_he"]) and not any(k.endswith("_en") for k in out), name
