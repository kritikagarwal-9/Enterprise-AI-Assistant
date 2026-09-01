"""Checks a single API key header against API_AUTH_KEY from config."""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = settings.api_auth_key
    provided = x_api_key or ""
    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
