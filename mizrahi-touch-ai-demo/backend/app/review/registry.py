"""The one provider integration point. REVIEW_PROVIDER selects the engine; nothing else
in the application knows which engine reviews a document."""
from __future__ import annotations

from functools import lru_cache

from ..config import settings
from .contract import ReviewProvider
from .gemini_provider import GeminiReviewProvider
from .visiontrace_provider import VisionTraceReviewProvider


@lru_cache(maxsize=1)
def gemini() -> GeminiReviewProvider:
    return GeminiReviewProvider()


@lru_cache(maxsize=1)
def visiontrace() -> VisionTraceReviewProvider:
    return VisionTraceReviewProvider()


def active() -> ReviewProvider:
    choice = settings.review_provider
    if choice == "visiontrace":
        vt = visiontrace()
        if vt.readiness()["state"] == "LIVE":
            return vt
        raise RuntimeError("REVIEW_PROVIDER=visiontrace but the VisionTrace mortgage review is not validated; "
                           "set REVIEW_PROVIDER=gemini")
    if choice == "hybrid":
        raise RuntimeError("REVIEW_PROVIDER=hybrid has no defined division of responsibility yet")
    return gemini()
