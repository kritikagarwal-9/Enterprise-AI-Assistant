"""API key authentication.

Two independent key types share one header (X-API-Key):

- The staff key (API_AUTH_KEY) is unrestricted -- internal CS staff need
  to look up different customers all day, so holding this key means
  "I am internal staff," not "I am one specific customer."
- Customer-scoped keys (CUSTOMER_API_KEYS) are the mechanism for when a
  caller must be restricted to exactly one customer_id. This is not a
  general identity/permissions system -- it only enforces that one
  boundary.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Literal

from fastapi import Header, HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class AuthContext:
    scope: Literal["staff", "customer"]
    customer_id: str | None = None


def _parse_customer_api_keys(raw: str) -> dict[str, str]:
    """Parses 'key1:cust_001,key2:cust_002' into {key: customer_id}.

    Never logs or returns the raw input. Splits each entry on the first
    ':' only. An entry with no colon, an empty key, or an empty
    customer_id is dropped. A key that appears more than once is treated
    as ambiguous and dropped entirely (not first-wins) rather than
    guessed at.
    """
    mapping: dict[str, str] = {}
    seen_ambiguous: set[str] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        key, customer_id = entry.split(":", 1)
        key, customer_id = key.strip(), customer_id.strip()
        if not key or not customer_id:
            continue
        if key in mapping or key in seen_ambiguous:
            seen_ambiguous.add(key)
            mapping.pop(key, None)
            continue
        mapping[key] = customer_id
    return mapping


def require_api_key(x_api_key: str | None = Header(default=None)) -> AuthContext:
    provided = x_api_key or ""

    expected_staff_key = settings.api_auth_key
    if expected_staff_key and secrets.compare_digest(provided, expected_staff_key):
        return AuthContext(scope="staff")

    for key, customer_id in _parse_customer_api_keys(settings.customer_api_keys).items():
        if secrets.compare_digest(provided, key):
            return AuthContext(scope="customer", customer_id=customer_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )
