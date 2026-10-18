"""Hebrew / English for the platform's language switch.

Hebrew is the product's language and the default. The app sends `X-MZ-Lang: he|en` on every API request
(frontend/src/api.ts); only the routes that call `lang(request)` read it — the customer routes (overlays in views.py)
and the staff routes: banker console, presenter pane, system page and admin (`staff`, catalogue in staff_en.py). MCP
and every caller without the header get exactly the responses they got before.

With the header, a response keeps every `*_he` field unchanged and gains `*_en` siblings (`localized`): English the
customer app shows when its language is English. The overlay works on a deep copy, never on a cached policy or rubric
object, and a failure in it returns the Hebrew response untouched (logged), so English can never break Hebrew. Text
that has no English source — a banker's own message, an AI reviewer's explanation, a document's content — gets no
sibling; the app shows it in its original language, marked as such. Nothing here changes a figure, a status, a verdict
or a permission: the English is a second rendering of the same values.

`I18N_EN=0` turns English off: the header is ignored and nothing is added."""
from __future__ import annotations

import copy
import logging
from typing import Any, Callable, Optional, TypeVar

from ..config import settings

HEADER = "X-MZ-Lang"
log = logging.getLogger("i18n")
T_ = TypeVar("T_")


def lang(request: Any) -> Optional[str]:
    """'he' or 'en' when the customer app sent its language (and English is on); None for every other caller."""
    if not settings.i18n_en or request is None:
        return None
    value = (request.headers.get(HEADER) or "").strip().lower()
    return value if value in ("he", "en") else None


def T(language: Optional[str], he: T_, en: T_) -> T_:
    """The Hebrew value unless the language is English."""
    return en if language == "en" else he


def localized(language: Optional[str], value: T_, overlay: Callable[[Any], None]) -> T_:
    """`value` with `*_en` siblings added by `overlay` (in place, on a deep copy) when the customer app sent its
    language; `value` itself otherwise. Any error leaves the Hebrew response as it was."""
    if language is None:
        return value
    try:
        out = copy.deepcopy(value)
        overlay(out)
        return out
    except Exception:                                   # English must never cost the customer the Hebrew answer
        log.exception("English overlay failed; the response is returned without it")
        return value


def staff(request: Any, value: T_) -> T_:
    """A staff or presenter response with English siblings from the staff catalogue (staff_en) when the app sent its
    language; the response itself otherwise."""
    from . import staff_en
    return localized(lang(request), value, staff_en.response)


async def http_exception_handler(request: Any, exc: Any):
    """FastAPI's own handler; when the customer app sent its language, a known Hebrew message also gets `detail_en`."""
    from fastapi.exception_handlers import http_exception_handler as default
    response = await default(request, exc)
    if lang(request) and isinstance(getattr(exc, "detail", None), str):
        from .staff_en import translate
        from .views import error_text
        english = error_text(exc.detail) or translate(exc.detail)
        if english:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": exc.detail, "detail_en": english}, status_code=exc.status_code,
                                headers=getattr(exc, "headers", None))
    return response
