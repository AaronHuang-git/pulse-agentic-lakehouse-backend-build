"""Opaque cursor encoding for paginated query results."""
from __future__ import annotations

import base64

from fastapi import HTTPException, status


def encode_cursor(offset: int) -> str:
    """Encode an offset integer as a base64-url cursor."""
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    """Decode a cursor back to an offset. Returns 0 for None."""
    if not cursor:
        return 0
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor.",
        ) from exc
