"""Server-side capability checks for staff routes.

The capability lists live in the staff directory (`bank/mock_bank.py`; a real adapter takes them from bank SSO). A
route names what it needs; the signed session decides who the caller is. Nothing the browser sends grants a
capability."""
from __future__ import annotations

from fastapi import HTTPException, Request

from . import auth

FORBIDDEN = "אין לך הרשאה לבצע פעולה זו."


def has(person: dict, capability: str) -> bool:
    return capability in (person.get("capabilities") or [])


def require(request: Request, *capabilities: str, any_of: bool = False) -> dict:
    """The staff member behind the session if they hold every listed capability (at least one with any_of=True).
    401 without a staff session, 403 without the capability."""
    person = auth.require_staff(request)
    missing = [c for c in capabilities if not has(person, c)]
    if missing and (not any_of or len(missing) == len(capabilities)):
        raise HTTPException(403, f"{FORBIDDEN} ({', '.join(missing)})")
    return person
