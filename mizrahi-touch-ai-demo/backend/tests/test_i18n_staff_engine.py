"""The staff English engine (app/i18n/staff_en.py) on its own: composed texts, Hebrew lists, names, and the rule that
an English rendering never carries Hebrew it merely failed to recognise."""
from __future__ import annotations

import pytest

from app.i18n import staff_en


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    staff_en.refresh()
    staff_en.translate.cache_clear()
    monkeypatch.setattr(staff_en, "_people", lambda: frozenset({"מיה", "מיה ברקוביץ"}))
    yield
    staff_en.translate.cache_clear()


def test_hebrew_and_list_is_split_into_english():
    assert staff_en.translate("תלושי שכר של אוגוסט וספטמבר 2026") == "Payslips for August and September 2026"


def test_composed_headline_translates_by_its_parts():
    he = ("נדרשת השלמת מסמכים לפני שניתן לגבש תמונה פיננסית מספקת. חסר: תלושי שכר של אוגוסט וספטמבר 2026, "
          "דפי עו״ש ל־3 החודשים האחרונים — חשבון עו״ש 1 (עידו) ואסמכתה למטרת ההלוואה — רכישת רכב.")
    english = staff_en.translate(he)
    assert english and not staff_en.HE.search(english)
    assert "Payslips for August and September 2026" in english and " and Proof of the loan's purpose" in english


def test_a_typed_borrower_name_stays_as_typed_but_other_hebrew_does_not_pass_as_a_name():
    assert staff_en.translate("ההכנסה של מיה מוצהרת בלבד, טרם אומתה במסמכים.") == \
        "מיה's income is declared only and not yet verified by documents."
    assert staff_en.translate("ההכנסה של Michal מוצהרת בלבד, טרם אומתה במסמכים.") == \
        "Michal's income is declared only and not yet verified by documents."
    assert staff_en.translate("ההכנסה של שולחן מוצהרת בלבד, טרם אומתה במסמכים.") is None


def test_a_half_recognised_title_is_not_english():
    english = staff_en.translate("תעודת זהות — מאיה שטרן (צילום נוסף)")
    assert english == "ID card — Maya Stern (additional photo)"
    assert staff_en.translate("תעודת זהות — מאיה שטרן (משהו שלא קוטלג)") is None


def test_an_empty_last_part_leaves_no_dangling_separator():
    assert staff_en.translate("אסמכתה למטרה · ") == "Proof of purpose"
