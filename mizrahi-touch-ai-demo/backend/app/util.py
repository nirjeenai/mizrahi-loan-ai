"""Small shared helpers: ids, clocks, hashing, masking."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone

_IL_TZ_OFFSET = "+03:00"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf8")).hexdigest()[:16]


_ID_RUN = re.compile(r"(?<!\d)(\d{9})(?!\d)")


def mask_ids(text: str) -> str:
    """Mask nine-digit identity numbers to their last three digits."""
    return _ID_RUN.sub(lambda m: "******" + m.group(1)[-3:], text or "")
