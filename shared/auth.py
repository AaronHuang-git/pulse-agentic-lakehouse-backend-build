"""API-key authentication helpers."""
from __future__ import annotations

from typing import Annotated

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session


async def require_tenant(
    db: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Validate the ``Authorization: Bearer <api-key>`` header.

    Returns the matched ``tenant_id`` or raises 401. A Redis cache for
    hot keys is a follow-up; for now we scan ``api_keys`` and bcrypt-check
    each row. Fine for the single-tenant dev workload.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    presented = authorization.split(" ", 1)[1].strip().encode()

    rows = (
        await db.execute(text("SELECT id, tenant_id, key_hash FROM api_keys"))
    ).all()

    for row in rows:
        if bcrypt.checkpw(presented, row.key_hash.encode()):
            await db.execute(
                text("UPDATE api_keys SET last_used_at = NOW() WHERE id = :id"),
                {"id": row.id},
            )
            await db.commit()
            return row.tenant_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )
