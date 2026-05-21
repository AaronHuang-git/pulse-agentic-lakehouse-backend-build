"""SQLAlchemy engines and session factories (async for FastAPI, sync for Celery)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from shared.config import get_settings

settings = get_settings()

# ----- Async engine: used by FastAPI endpoints. -----

engine = create_async_engine(
    settings.postgres_dsn_async,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a database session per request."""
    async with SessionLocal() as session:
        yield session


# ----- Sync engine: used by Celery workers (no asyncio in worker code). -----

sync_engine = create_engine(
    settings.postgres_dsn_sync,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # cheap heartbeat to avoid stale conns in long-lived workers
)

SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False, class_=Session)
