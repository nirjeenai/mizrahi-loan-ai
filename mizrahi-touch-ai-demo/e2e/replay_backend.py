"""REPLAY backend: the real Mortgage Case Service with only the Gemini HTTP transport replaced by recorded answers.

    # from backend/ — a fresh DATA_DIR every run; nothing here ever reaches the network
    .venv/bin/python ../e2e/replay_backend.py --port 8797 --data ../e2e/artifacts/featured/data-replay

Everything above the transport runs for real: generate() (budget, retries, usage ledger), GeminiReviewProvider
(evidence verification against the uploaded PDF's text layer, deterministic rules, merge, verdict policy), case review
(coverage, IS-04 arithmetic), findings, outcomes, banker desk, routes and DB. What is replayed:

  extract / judge   e2e/replay/recordings.json, looked up by the SHA-256 of the file inside the request — never by
                    filename. RECORDED_LIVE entries restate the 2026-10-12 live review; AUTHORED entries are labelled.
                    A file with no recording gets HTTP 404, so its review fails visibly; nothing is invented.
  semantic_review   a fixed rule, not model output: definitions_equivalent=true, INCONSISTENT when |difference_pct| > 5.
  agent, voice      HTTP 400, so the app answers from case data without a model (its own fallback).

Every call is appended to <DATA_DIR>/replay-transport.jsonl. Model ids read "replay-recorded", so the review pages,
the usage ledger and /system show that these are REPLAY results, not LIVE ones."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
RECORDINGS = json.loads((HERE / "replay" / "recordings.json").read_text(encoding="utf8"))["documents"]
_ctx = threading.local()
_log_lock = threading.Lock()
LOG: Path | None = None


def _log(entry: dict) -> None:
    if LOG:
        with _log_lock, LOG.open("a", encoding="utf8") as fh:
            fh.write(json.dumps({"at": time.strftime("%H:%M:%S"), **entry}, ensure_ascii=False) + "\n")


class _Resp:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body
        self.text = json.dumps(body, ensure_ascii=False)[:300]

    def json(self) -> dict:
        return self._body


def _answer(obj: Any) -> _Resp:
    return _Resp(200, {"candidates": [{"content": {"parts": [{"text": json.dumps(obj, ensure_ascii=False)}]}, "finishReason": "STOP"}],
                       "usageMetadata": {"promptTokenCount": 0, "candidatesTokenCount": 0}})


def _file_sha(body: dict) -> str | None:
    for content in body.get("contents") or []:
        for part in content.get("parts") or []:
            data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
            if data:
                return hashlib.sha256(base64.b64decode(data)).hexdigest()
    return None


def _prompt(body: dict) -> str:
    return "\n".join(p.get("text", "") for c in body.get("contents") or [] for p in c.get("parts") or [] if p.get("text"))


def _semantic(body: dict) -> dict:
    text = _prompt(body)
    payload = json.loads(text[text.index("["):text.rindex("]") + 1])
    out = []
    for b in payload:
        c = b.get("computed") or {}
        pct = c.get("difference_pct") or 0
        gap = abs(pct) > 5
        out.append({"borrower_id": b["borrower_id"], "income_assessment": "INCONSISTENT" if gap else "CONSISTENT",
                    "definitions_equivalent": True,
                    "explanation_he": (f"ממוצע הנטו בתלושים {c.get('average_documented_net_ils'):,.0f} ₪ לעומת הצהרה של "
                                       f"{b['declared']['net_monthly_ils']:,.0f} ₪ ({pct:+.1f}%)."),
                    "possible_reasons_he": ["רכיב שכר משתנה או מענק שאינו מופיע בתלושים", "הצהרה על בסיס שכר צפוי"] if gap else [],
                    "evidence_needed_he": ["אישור מעסיק על רכיבי שכר משתנים או טופס 106"] if gap else [],
                    "customer_statement_note_he": None, "identity_assessment": "CONSISTENT",
                    "identity_explanation_he": "השם המודפס זהה בכל המסמכים."})
    return {"borrowers": out, "limitations_he": ["REPLAY: הערכה סמנטית לפי כלל קבוע, לא תשובת מודל."]}


class _Transport:
    """Stands in for httpx inside app.llm.gemini; only generateContent requests are answered, never forwarded."""

    def __init__(self, real: Any):
        self._real = real

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def post(self, url: str, headers: dict | None = None, json: dict | None = None, timeout: float | None = None):  # noqa: A002
        body = json or {}
        purpose = getattr(_ctx, "purpose", "?")
        if "generativelanguage.googleapis.com" not in url:
            raise self._real.HTTPError(f"REPLAY backend refuses outbound request to {url}")
        sha = _file_sha(body)
        rec = RECORDINGS.get(sha or "")
        if purpose in ("extract", "judge"):
            if not rec:
                _log({"purpose": purpose, "sha256": sha, "served": False})
                return _Resp(404, {"error": {"message": "no REPLAY recording for this file"}})
            if purpose == "extract":
                answer = rec["extract"]
            else:
                ids = body["generationConfig"]["responseSchema"]["properties"]["criteria"]["items"]["properties"]["criterion_id"]["enum"]
                answer = {"criteria": [{"criterion_id": cid, "outcome": rec["judge"]["criteria"][cid]["outcome"],
                                        "explanation_he": rec["judge"]["criteria"][cid]["explanation_he"], "cited_fields": [],
                                        "confidence": 0.9} for cid in ids if cid in rec["judge"]["criteria"]],
                          **{k: rec["judge"][k] for k in ("summary_he", "limitations_he", "uncertainty_he")}}
            _log({"purpose": purpose, "sha256": sha, "file": rec["file"], "provenance": rec["provenance"], "served": True})
            return _answer(answer)
        if purpose == "semantic_review":
            _log({"purpose": purpose, "provenance": "REPLAY_RULE", "served": True})
            return _answer(_semantic(body))
        _log({"purpose": purpose, "served": False, "reason": "no model in REPLAY; the app uses its no-model fallback"})
        return _Resp(400, {"error": {"message": f"REPLAY backend has no model for '{purpose}'"}})


def install(data_dir: Path) -> None:
    global LOG
    from app.llm import gemini as g
    LOG = data_dir / "replay-transport.jsonl"
    real_generate = g.generate

    def generate(model, contents, *, purpose, run_id=None, **kw):
        _ctx.purpose = purpose
        return real_generate(model, contents, purpose=purpose, run_id=run_id, **kw)

    g.generate = generate
    g.httpx = _Transport(g.httpx)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    data = Path(a.data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    # set before the app reads its settings; environment variables win over backend/.env
    os.environ.update({"DATA_DIR": str(data), "REVIEW_PROVIDER": "gemini", "GEMINI_API_KEY": "replay-no-network",
                       "GEMINI_MODEL_EXTRACT": "replay-recorded", "GEMINI_MODEL_JUDGE": "replay-recorded",
                       "GEMINI_MODEL_AGENT": "replay-recorded", "VISIONTRACE_MCP_KEY": "", "VISIONTRACE_MCP_URL": "",
                       "MCP_DEMO_KEY": "replay-mcp-key-001", "MCP_DEMO_KEY_2": "replay-mcp-key-002",
                       "SESSION_SECRET": "replay-session-secret", "DEMO_PERSONAS": "1", "DEMO_RESET": "1"})
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    import uvicorn
    from app.main import app
    install(data)
    print(f"REPLAY backend · DATA_DIR={data} · port {a.port} · {len(RECORDINGS)} recorded files", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
