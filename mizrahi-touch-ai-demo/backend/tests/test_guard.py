"""Offline tests of the assistant reply guard (no model calls)."""
from __future__ import annotations

from app.agent.agent import SAFE_REPLY, guard_reply


def blocked(text: str) -> bool:
    return guard_reply(text)[1]["blocked"]


def test_negated_statements_pass():
    assert not blocked("זה אינו אישור סופי של המשכנתא.")
    assert not blocked("שלב הבקשה הוא קיבלנו החלטה, ואינו מהווה אישור סופי של המשכנתא.")
    assert not blocked("המשכנתא לא אושרה, וההחלטה אצל הבנקאית.")
    assert not blocked("הבקשה שלכם טרם הושלמה.")


def test_approval_claims_are_blocked():
    assert blocked("המשכנתא שלכם אושרה.")
    assert blocked("קיבלתם אישור סופי.")
    assert blocked("הבנק קיבל את המסמך.")
    assert blocked("Your mortgage has been approved.")
    assert guard_reply("המשכנתא אושרה")[0] == SAFE_REPLY


def test_markdown_stripped_and_ids_masked():
    text, meta = guard_reply("**חסר** תלוש של `ספטמבר` עבור 039812457")
    assert not meta["blocked"]
    assert text.startswith("חסר תלוש") and "`" not in text
    assert "039812457" not in text and text.endswith("******457")
