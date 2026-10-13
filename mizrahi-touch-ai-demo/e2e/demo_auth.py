"""Sessions for the browser suites' direct API calls. The service has no anonymous access (backend/app/auth.py). In
demo mode (DEMO_IDENTITY=1, the default) the app in the browser obtains its sessions by itself, so pages need nothing;
the suites' own httpx calls get theirs here from the same demo-session endpoints.

    import demo_auth
    demo_auth.install(BASE)          # every httpx call to BASE carries a session that fits its path

How install() picks the session for a request to BASE:
- /api/banker/* and the staff-only reads (/api/cases/{id}/findings|audit|runs, /api/runs/*, /api/documents/*,
  /api/system/mcp-selftest): a staff session. An X-Staff-Id header (as the suites were written) names the staff member
  and is removed — the server ignores that header; an unknown id gets no session. Without the header, reads use the
  demo banker (Dana) and writes get no session, so a suite can still check that an anonymous write is refused.
- /api/cases/{id}/*: a customer session for that case; /api/cases and /api/voice: case 001.
- Anything else (health, fixtures, presenter, session, /mcp) is sent as is, and so is any request that already has an
  Authorization header or the header X-No-Auth (removed before sending) — that is how suites check refusals."""
from __future__ import annotations

import re
from typing import Any, Optional

import httpx

_original = httpx.Client.request
_bases: list[str] = []
_tokens: dict[tuple, Optional[str]] = {}
DEFAULT_CASE = "DEMO-MTZ-2026-001"
DEMO_STAFF = "STAFF-DANA"
STAFF_ONLY = re.compile(r"^/api/(cases/[^/]+/(findings|audit|runs)|runs/|documents/|system/mcp-selftest)")


def _raw(method: str, url: str, **kw: Any) -> httpx.Response:
    with httpx.Client(timeout=60) as c:
        return _original(c, method, url, **kw)


def token(base: str, role: str, who: str) -> Optional[str]:
    """A bearer token: a customer session for case `who`, or the staff session of staff id `who` (None if unknown)."""
    key = (base, role, who)
    if key not in _tokens:
        if role == "customer":
            r = _raw("POST", f"{base}/api/session/demo/customer", json={"case_id": who})
        else:
            r = _raw("POST", f"{base}/api/session/demo/staff", json={"staff_id": who})
            if r.status_code == 404:
                _tokens[key] = None
                return None
        r.raise_for_status()
        _tokens[key] = r.json()["token"]
    return _tokens[key]


def _session_for(base: str, method: str, path: str, staff_header: Optional[str]) -> Optional[str]:
    if STAFF_ONLY.match(path) or path.startswith("/api/banker/"):
        if staff_header:
            return token(base, "staff", staff_header)
        return token(base, "staff", DEMO_STAFF) if method.upper() == "GET" or STAFF_ONLY.match(path) else None
    m = re.match(r"^/api/cases/([^/?]+)", path)
    if m:
        return token(base, "customer", m.group(1))
    if path.startswith("/api/cases") or path.startswith("/api/voice"):
        return token(base, "customer", DEFAULT_CASE)
    return None


def _request(self: httpx.Client, method: str, url: Any, **kw: Any) -> httpx.Response:
    text = str(url)
    base = next((b for b in _bases if text.startswith(b)), None)
    if base is None:
        return _original(self, method, url, **kw)
    headers = dict(kw.get("headers") or {})
    lower = {k.lower(): k for k in headers}
    if "x-no-auth" in lower:
        headers.pop(lower["x-no-auth"])
        return _original(self, method, url, **{**kw, "headers": headers})
    if "authorization" in lower:
        return _original(self, method, url, **kw)
    staff_header = headers.pop(lower["x-staff-id"]) if "x-staff-id" in lower else None
    path = text[len(base):].split("?", 1)[0]
    bearer = _session_for(base, method, path, staff_header)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return _original(self, method, url, **{**kw, "headers": headers})


def install(*bases: str) -> None:
    for b in bases:
        if b and b.rstrip("/") not in _bases:
            _bases.append(b.rstrip("/"))
    httpx.Client.request = _request
