"""API-key authentication dependency."""
from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> None:
    """
    Require X-API-Key header matching API_SECRET_KEY.
    Returns None on success; raises 403 on failure.
    The key must NEVER be forwarded by the Next.js proxy —
    it lives only in server-side environment variables.
    """
    if not api_key or api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )
