"""English for the staff side of the platform: the banker console, the presenter pane, the system page and admin.

The customer responses get their English from hand-built overlays (views.py). The staff responses are larger and are
composed from many small Hebrew templates (banker_intelligence, banker_package, review_desk, readiness, case_review…),
so their English comes from one catalogue instead: `translate(he)` returns the English of a Hebrew text the code wrote,
or None. `overlay(value)` walks a response (a deep copy, through i18n.localized) and adds an English sibling next to
every Hebrew string it can translate: `title_he` → `title_en`, `labelHe` → `labelEn`, `summary` → `summary_en`, and for
a list of strings a parallel list (`reasons_he` → `reasons_en`, None where an item has no English).

The catalogue (`staff_catalog/*.json`, one file per area) holds:
- "exact": {Hebrew: English} for fixed texts;
- "templates": [[Hebrew pattern, English pattern], …] for texts with values in them. A placeholder in braces stands
  for one value; its letter says what it is and how it is carried over:
    {n} {n2} …  a figure, an amount, a date, a count, a percentage, an id: copied as printed
    {m} {m2} …  a Hebrew month label ("ספטמבר 2026", "ספטמבר"): its English month
    {p} {p2} …  a demo person's or company's name (en.NAMES): its Latin spelling
    {t} {t2} …  a nested text: translated by these same rules (the template fails when it can't be)
    {x} {x2} …  anything else (a file name, a code, a quote): copied as written
  Patterns are matched against the whole text; longer patterns are tried first.
Where neither matches, a text built from parts ("A · B", "A — B", sentences) is translated part by part when every
part translates. Nothing else is translated: a banker's own words, a customer's words, a document's printed values and
the model's own wording keep no sibling, and the app shows them as the original, marked as such. Nothing here changes
a figure, a status, a verdict or a permission: the English is a second rendering of the same values."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

from . import criteria_en, en

HE = re.compile(r"[֐-׿]")
CATALOG_DIR = Path(__file__).with_name("staff_catalog")

# subtrees that hold original source content (messages as written, raw model answers, an editable configuration);
# keys whose value is a document's or a person's own words
SKIP_TREES = {"conversation", "runs", "raw", "config", "published", "draft_config", "model_output", "history"}
SKIP_KEYS = {"quote", "value_raw", "value_normalized", "filename", "reply_text", "customer_text", "note_text",
             "printed", "as_printed", "source_text", "original_he", "text_typed"}

_MONTHS_HE = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
_N = r"[-−+]?₪?\s?\d[\d,./:\-]*%?|[-−+]?\d+(?:\.\d+)?%"
_KINDS: dict[str, str] = {"n": rf"(?:{_N})", "m": r"(?:{0})(?: \d{{4}})?".format("|".join(_MONTHS_HE)),
                          "p": r".+?", "t": r".+?", "x": r".+?"}
_PH = re.compile(r"\{([nmptx])(\d*)\}")


def _month(he: str) -> Optional[str]:
    name, _, year = he.partition(" ")
    if name not in _MONTHS_HE or (year and not re.fullmatch(r"\d{4}", year)):
        return None
    return en.MONTHS[_MONTHS_HE.index(name)] + (f" {year}" if year else "")


Template = tuple[re.Pattern, str]


def _compile(he: str) -> re.Pattern:
    out, pos = [], 0
    for m in _PH.finditer(he):
        out.append(re.escape(he[pos:m.start()]))
        out.append(f"(?P<{m[1]}{m[2] or '0'}>{_KINDS[m[1]]})")
        pos = m.end()
    out.append(re.escape(he[pos:]))
    return re.compile("".join(out), re.S)


_stamp: tuple = ()


def refresh() -> None:
    """Reload the catalogue when one of its files changed (a catalogue edit shows without a restart)."""
    global _stamp
    stamp = tuple((f.name, f.stat().st_mtime_ns) for f in sorted(CATALOG_DIR.glob("*.json")))
    if stamp != _stamp:
        _stamp = stamp
        catalog.cache_clear()
        translate.cache_clear()


@lru_cache(maxsize=1)
def catalog() -> tuple[dict[str, str], list[Template]]:
    exact: dict[str, str] = {}
    templates: list[tuple[str, str]] = []
    for f in sorted(CATALOG_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        exact.update({k.strip(): v for k, v in (data.get("exact") or {}).items()})
        templates += [(he, en_) for he, en_ in data.get("templates") or []]
    # the most specific pattern first: more literal text, then fewer placeholders
    templates.sort(key=lambda t: (-len(_PH.sub("", t[0])), len(_PH.findall(t[0]))))
    return exact, [(_compile(he), en_) for he, en_ in templates]


def _value(kind: str, v: str, depth: int) -> Optional[str]:
    if kind in ("n", "x"):
        return v
    if kind == "m":
        return _month(v)
    if kind == "p":
        return en.NAMES.get(v.strip())
    return _tr(v, depth + 1)


def _fill(rx: re.Pattern, english: str, m: re.Match, depth: int) -> Optional[str]:
    values: dict[str, str] = {}
    for key, v in m.groupdict().items():
        got = _value(key[0], v, depth)
        if got is None:
            return None
        values[key] = got
    return _PH.sub(lambda p: values.get(f"{p[1]}{p[2] or '0'}", p[0]), english)


_SPLITS = ["\n", " · ", " — ", " – ", " | ", "; "]
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=\S)")


def _parts(text: str, depth: int) -> Optional[str]:
    for sep in _SPLITS:
        if sep in text:
            parts = text.split(sep)
            out = [_tr(p, depth + 1) if p.strip() else p for p in parts]
            return sep.join(out) if all(o is not None for o in out) else None
    sentences = _SENTENCE.split(text)
    if len(sentences) > 1:
        out = [_tr(s, depth + 1) for s in sentences]
        return " ".join(out) if all(o is not None for o in out) else None
    for sep in (": ", ", "):
        if sep in text:
            head, _, tail = text.partition(sep)
            a, b = _tr(head, depth + 1), _tr(tail, depth + 1)
            if a is not None and b is not None:
                return f"{a}{sep}{b}"
    return None


def _known(text: str) -> Optional[str]:
    exact, _ = catalog()
    if text in exact:
        return exact[text]
    if text in en.NAMES:
        return en.NAMES[text]
    month = _month(text)
    if month:
        return month
    got = criteria_en.explanation(text) or en.error(text)
    if got:
        return got
    from .views import requirement_title
    try:
        return requirement_title(text)
    except Exception:                                   # no published policy yet (tests, a fresh DATA_DIR)
        return None


def _tr(text: str, depth: int = 0) -> Optional[str]:
    if not HE.search(text):
        return text
    if depth > 6:
        return None
    lead, core, trail = re.match(r"(\s*)(.*?)(\s*)$", text, re.S).groups()
    got = _known(core)
    if got is None and core[-1:] in ".:" and len(core) > 1:
        inner = _known(core[:-1])
        got = inner + core[-1] if inner is not None else None
    if got is None:
        _, templates = catalog()
        for rx, english in templates:
            m = rx.fullmatch(core)
            if m and (got := _fill(rx, english, m, depth)) is not None:
                break
    if got is None:
        got = _parts(core, depth)
    return None if got is None else f"{lead}{got}{trail}"


@lru_cache(maxsize=20000)
def translate(text: Optional[str]) -> Optional[str]:
    """The English of a Hebrew text the platform's code wrote; None when there is none (or no Hebrew in it)."""
    if not text or not HE.search(text):
        return None
    got = _tr(text)
    if got is not None and re.search(r"\s·\s*$", text):  # a title whose last part is empty ("אסמכתה למטרה · ")
        got = re.sub(r"\s*·\s*$", "", got)
    return got if got is not None and got != text else None


def en_key(key: str) -> str:
    """the sibling's name: `title_he` → `title_en`, `labelHe` → `labelEn`, `summary` → `summary_en`"""
    if key.endswith("_he"):
        return key[:-3] + "_en"
    if key.endswith("He"):
        return key[:-2] + "En"
    return key + "_en"


def _is_english_key(key: str) -> bool:
    return key.endswith("_en") or key.endswith("En")


def response(value: Any) -> None:
    """i18n.staff's overlay: the catalogue as it is on disk now, then `overlay`."""
    refresh()
    overlay(value)


def overlay(value: Any, translate_fn: Callable[[str], Optional[str]] = translate) -> None:
    """Add English siblings, in place, everywhere in `value` (call it on a deep copy: i18n.localized does)."""
    if isinstance(value, list):
        for item in value:
            overlay(item, translate_fn)
        return
    if not isinstance(value, dict):
        return
    for key in list(value.keys()):
        v = value[key]
        if not isinstance(key, str) or _is_english_key(key) or key in SKIP_KEYS:
            continue
        if key in SKIP_TREES:
            continue
        if isinstance(v, str):
            target = en_key(key)
            if target not in value and HE.search(v):
                english = translate_fn(v)
                if english:
                    value[target] = english
        elif isinstance(v, list) and v and all(isinstance(i, str) for i in v):
            target = en_key(key)
            if target not in value and any(HE.search(i) for i in v):
                english = [translate_fn(i) if HE.search(i) else i for i in v]
                if any(e and HE.search(o) for e, o in zip(english, v)):
                    value[target] = english
        else:
            overlay(v, translate_fn)


def coverage(value: Any) -> tuple[int, list[str]]:
    """(Hebrew strings seen, the ones with no English) in a response — for tests and the catalogue's upkeep."""
    seen: list[str] = []
    missing: list[str] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str) and (k in SKIP_TREES or k in SKIP_KEYS or _is_english_key(k)):
                    continue
                if isinstance(v, str) and HE.search(v):
                    seen.append(v)
                    if translate(v) is None:
                        missing.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for i in o:
                if isinstance(i, str) and HE.search(i):
                    seen.append(i)
                    if translate(i) is None:
                        missing.append(i)
                else:
                    walk(i)
    walk(value)
    return len(seen), missing
