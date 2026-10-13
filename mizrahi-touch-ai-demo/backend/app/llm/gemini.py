"""Gemini REST client — structured output, function calling, bounded retries, an hourly
call budget and a ledger row for every call (FinOps / observability)."""
from __future__ import annotations

import base64
import json
import time
from typing import Any, Optional

import httpx

from .. import db
from ..config import settings
from ..util import now_iso

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRYABLE = {429, 500, 502, 503, 504}


class GeminiError(RuntimeError):
    pass


class BudgetExceeded(GeminiError):
    pass


def text_part(text: str) -> dict:
    return {"text": text}


def inline_part(data: bytes, mime: str) -> dict:
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}


def S(type_: str, **kw: Any) -> dict:
    """A responseSchema node (OpenAPI subset)."""
    return {"type": type_, **kw}


def _record(model: str, purpose: str, run_id: Optional[str], usage: dict, latency_ms: int, ok: bool, error: str = "") -> None:
    with db.tx() as c:
        c.execute("INSERT INTO llm_calls(at, model, purpose, run_id, prompt_tokens, output_tokens, thought_tokens, latency_ms, ok, error)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (now_iso(), model, purpose, run_id, usage.get("promptTokenCount"), usage.get("candidatesTokenCount"),
                   usage.get("thoughtsTokenCount"), latency_ms, int(ok), error[:500]))


def _calls_last_hour() -> int:
    row = db.one("SELECT COUNT(*) AS n FROM llm_calls WHERE at >= datetime('now', '-1 hour')")
    return int(row["n"]) if row else 0


def generate(model: str, contents: list[dict], *, purpose: str, run_id: Optional[str] = None,
             system: Optional[str] = None, schema: Optional[dict] = None, tools: Optional[list[dict]] = None,
             thinking: str = "low", temperature: float = 0.0, timeout: float = 120.0) -> dict:
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is not configured")
    if _calls_last_hour() >= settings.max_llm_calls_per_hour:
        raise BudgetExceeded(f"hourly Gemini call budget reached ({settings.max_llm_calls_per_hour})")
    gen: dict[str, Any] = {"temperature": temperature, "thinkingConfig": {"thinkingLevel": thinking}}
    if schema is not None:
        gen["responseMimeType"] = "application/json"
        gen["responseSchema"] = schema
    body: dict[str, Any] = {"contents": contents, "generationConfig": gen}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if tools:
        body["tools"] = [{"functionDeclarations": tools}]
        body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json",
               "User-Agent": "mizrahi-touch-jeen-demo/0.1"}
    last_error = ""
    for attempt in range(3):
        started = time.monotonic()
        try:
            resp = httpx.post(ENDPOINT.format(model=model), headers=headers, json=body, timeout=timeout)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            _record(model, purpose, run_id, {}, int((time.monotonic() - started) * 1000), False, last_error)
            time.sleep(1.5 * (attempt + 1) ** 2)
            continue
        latency = int((time.monotonic() - started) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            _record(model, purpose, run_id, data.get("usageMetadata", {}), latency, True)
            cand = (data.get("candidates") or [{}])[0]
            if cand.get("finishReason") not in (None, "STOP", "MAX_TOKENS") and not cand.get("content"):
                raise GeminiError(f"Gemini returned no content (finishReason={cand.get('finishReason')})")
            return data
        last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
        _record(model, purpose, run_id, {}, latency, False, last_error)
        if resp.status_code not in RETRYABLE:
            break
        time.sleep(1.5 * (attempt + 1) ** 2)
    raise GeminiError(last_error or "Gemini call failed")


def response_text(data: dict) -> str:
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def response_json(data: dict) -> Any:
    text = response_text(data).strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1] if "\n" in text else text
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"Gemini returned malformed JSON: {exc}") from None


def usage_of(data: dict) -> dict:
    u = data.get("usageMetadata") or {}
    return {"prompt_tokens": u.get("promptTokenCount", 0), "output_tokens": u.get("candidatesTokenCount", 0),
            "thought_tokens": u.get("thoughtsTokenCount", 0)}


def ledger_summary() -> dict:
    row = db.one("SELECT COUNT(*) AS calls, SUM(ok) AS ok, SUM(prompt_tokens) AS pt, SUM(output_tokens) AS ot,"
                 " SUM(thought_tokens) AS tt, AVG(latency_ms) AS lat FROM llm_calls") or {}
    by_purpose = db.query("SELECT purpose, COUNT(*) AS calls, AVG(latency_ms) AS avg_ms FROM llm_calls GROUP BY purpose ORDER BY calls DESC")
    last = db.one("SELECT at, model, ok, error FROM llm_calls ORDER BY call_id DESC LIMIT 1")
    return {"calls": row.get("calls") or 0, "ok": row.get("ok") or 0, "prompt_tokens": row.get("pt") or 0,
            "output_tokens": row.get("ot") or 0, "thought_tokens": row.get("tt") or 0,
            "avg_latency_ms": round(row.get("lat") or 0), "by_purpose": by_purpose, "last": last,
            "budget_per_hour": settings.max_llm_calls_per_hour, "calls_last_hour": _calls_last_hour()}
