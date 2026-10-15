"""Sessions and access checks for the customer app and the banker console.

Every route checks a server-issued, HMAC-signed, expiring session: an HttpOnly, SameSite=Strict cookie for the
browser, or the same token as a bearer for API clients. A customer session is bound to the cases it was issued for
and never reaches another case or the banker API; a staff session is needed for the banker console and for the raw
review data, and writes need the case's assigned banker. Nothing the browser sends (a header, localStorage) can choose
an identity on its own.

There is no identity provider in this concept demo. With DEMO_IDENTITY=1 (the default) the app obtains its sessions
without a login: the customer app asks for a session for the case picked in its case selector, and the banker console
for the demo banker's. That keeps the demo frictionless; it also means anyone who can reach the server can obtain a
demo session. Outside a demo set DEMO_IDENTITY=0 and issue sessions from the bank's SSO/OTP instead (`issue`)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .bank.mock_bank import bank
from .config import settings
from .store import repo

class _CookieNames:
    """Browsers scope cookies by host, not port, so every instance of this app on 127.0.0.1 (the main one, isolated
    stacks, previews) would share one cookie name and overwrite each other's sessions, each signed with its own
    DATA_DIR secret. The name carries a tag derived from this instance's secret: stable across restarts, distinct per
    instance, and distinct from Mizrahi #1's mz_*."""

    def __getitem__(self, role: str) -> str:
        tag = hashlib.sha256(b"mzl-cookie:" + settings.session_secret).hexdigest()[:8]
        return f"mzl_{role}_{tag}"


COOKIES = _CookieNames()
# Every 401 names the session that would satisfy it, so the app can renew exactly that one and retry once.
AUTH_HEADER = "X-Auth-Required"
NEED_CUSTOMER = "נדרש חיבור לתיק."
NEED_STAFF = "נדרש חיבור של איש צוות הבנק."
NOT_YOURS = "התיק אינו שייך לחיבור הנוכחי."
DEMO_STAFF = "STAFF-DANA"
MAX_CASES = 8


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(settings.session_secret, body.encode(), hashlib.sha256).digest())


def issue(role: str, subject: Any, ttl_minutes: Optional[int] = None) -> str:
    """A signed session. Customer subject: the list of case ids it may reach; staff subject: a staff id."""
    now = int(time.time())
    ttl = settings.session_ttl_minutes if ttl_minutes is None else ttl_minutes
    body = _b64(json.dumps({"r": role, "s": subject, "iat": now, "exp": now + 60 * ttl, "n": secrets.token_hex(6)},
                           separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def verify(token: Optional[str], role: str) -> Optional[dict]:
    if not token or token.count(".") != 1:
        return None
    body, sig = token.split(".")
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        payload = json.loads(_unb64(body))
    except ValueError:
        return None
    if payload.get("r") != role or int(payload.get("exp", 0)) <= time.time():
        return None
    return payload


def _credential(request: Request, role: str) -> Optional[str]:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()                  # an explicit bearer is the only credential considered
    return request.cookies.get(COOKIES[role])


def customer(request: Request) -> Optional[dict]:
    p = verify(_credential(request, "customer"), "customer")
    cases = [c for c in (p or {}).get("s") or [] if isinstance(c, str) and c in bank.case_ids()] if p else []
    return {"cases": cases, "exp": p["exp"]} if cases else None


def staff(request: Request) -> Optional[dict]:
    p = verify(_credential(request, "staff"), "staff")
    person = bank.staff(p["s"]) if p and isinstance(p.get("s"), str) else None
    return {**person, "exp": p["exp"]} if person else None


def _known_case(case_id: str) -> dict:
    try:
        return bank.get_case(case_id)
    except KeyError:
        raise HTTPException(404, "no such case") from None


def unauthorized(detail: str, *roles: str) -> HTTPException:
    return HTTPException(401, detail, headers={AUTH_HEADER: ", ".join(roles)})


def require_customer(request: Request) -> dict:
    c = customer(request)
    if not c:
        raise unauthorized(NEED_CUSTOMER, "customer")
    return c


def require_customer_case(request: Request, case_id: str) -> dict:
    c = require_customer(request)
    _known_case(case_id)
    if case_id not in c["cases"]:
        raise HTTPException(403, NOT_YOURS)
    return c


def require_staff(request: Request) -> dict:
    s = staff(request)
    if not s:
        raise unauthorized(NEED_STAFF, "staff")
    return s


def require_assigned_staff(request: Request, case_id: str) -> dict:
    s = require_staff(request)
    assigned = _known_case(case_id)["banker"]
    if assigned.get("staff_id") != s["staff_id"]:
        raise HTTPException(403, f"התיק משויך ל{assigned['name_he']} — אין הרשאה לבצע בו פעולות.")
    return s


def require_reader(request: Request, case_id: str) -> tuple[str, dict]:
    """Read access to a case's documents: any bank staff session, or a customer session for that case."""
    s = staff(request)
    if s:
        _known_case(case_id)
        return "staff", s
    if not customer(request):
        raise unauthorized(NEED_CUSTOMER, "staff", "customer")
    return "customer", require_customer_case(request, case_id)


def require_case_actor(request: Request, case_id: str) -> tuple[str, dict]:
    """A write the customer and the case's banker may both make (retry a failed review, demo reset)."""
    s = staff(request)
    if s:
        return "staff", require_assigned_staff(request, case_id)
    if not customer(request):
        raise unauthorized(NEED_CUSTOMER, "staff", "customer")
    return "customer", require_customer_case(request, case_id)


# ---------------------------------------------------------------- session routes
router = APIRouter(prefix="/api/session")


class DemoCustomer(BaseModel):
    case_id: str = Field(..., max_length=40)


class DemoStaff(BaseModel):
    staff_id: str = Field(DEMO_STAFF, max_length=40)


class Logout(BaseModel):
    role: Literal["customer", "staff", "all"] = "all"


def _set(response: Response, role: str, token: str) -> None:
    response.set_cookie(COOKIES[role], token, max_age=60 * settings.session_ttl_minutes, httponly=True,
                        samesite="strict", path="/")


set_session = _set


def _case_rows(case_ids: list[str]) -> list[dict]:
    rows = []
    for cid in case_ids:
        c = bank.get_case(cid)
        rows.append({**{k: c[k] for k in ("case_id", "display_number", "title_he")}, "persona_id": c.get("persona_id"),
                     "qa": bool(c.get("qa")), "use_case": c.get("use_case"),
                     "applicants_he": [b["name_he"] for b in c["borrowers"]],
                     "company_he": (c.get("company") or {}).get("name_he")})
    return rows


def _demo_only() -> None:
    if not settings.demo_identity:
        raise HTTPException(404, "demo sessions are switched off")


@router.get("")
def current(request: Request):
    c, s = customer(request), staff(request)
    return {"customer": {"cases": _case_rows(c["cases"]), "expires_at": c["exp"]} if c else None,
            "staff": {k: s[k] for k in ("staff_id", "name_he", "role_he", "exp")} if s else None,
            "demo_identity": settings.demo_identity}


@router.get("/demo/cases")
def demo_cases():
    """The demo case selector: case number and title only, never case data."""
    _demo_only()
    return _case_rows(bank.case_ids())


@router.post("/demo/customer")
def demo_customer(body: DemoCustomer, request: Request, response: Response):
    """Demo mode: a customer session for the case picked in the app (added to the cases this browser already holds)."""
    _demo_only()
    _known_case(body.case_id)
    held = (customer(request) or {}).get("cases", [])
    cases = list(dict.fromkeys([body.case_id] + held))[:MAX_CASES]
    token = issue("customer", cases)
    _set(response, "customer", token)
    repo.audit(body.case_id, "customer", "demo_session_started", body.case_id, {"role": "customer"})
    return {"role": "customer", "cases": _case_rows(cases), "token": token}


@router.post("/demo/staff")
def demo_staff(body: DemoStaff, response: Response):
    """Demo mode: the banker console's session (the demo banker unless a known staff id is named)."""
    _demo_only()
    person = bank.staff(body.staff_id)
    if not person:
        raise HTTPException(404, "no such staff member")
    token = issue("staff", person["staff_id"])
    _set(response, "staff", token)
    repo.audit(None, f"banker:{person['staff_id']}", "demo_session_started", person["staff_id"], {"role": "staff"})
    return {"role": "staff", "staff": person, "token": token}


@router.post("/logout")
def logout(body: Logout, response: Response):
    for role in (("customer", "staff") if body.role == "all" else (body.role,)):
        response.delete_cookie(COOKIES[role], path="/", samesite="strict", httponly=True)
    return {"ok": True}
