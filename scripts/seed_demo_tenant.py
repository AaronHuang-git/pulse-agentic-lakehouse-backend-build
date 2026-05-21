"""Seed the demo tenant and a known API key for local dev."""
from __future__ import annotations

import asyncio

import bcrypt
from sqlalchemy import text

from shared.db import SessionLocal

DEMO_TENANT_ID = "demo"
DEMO_TENANT_NAME = "Demo Tenant"
DEMO_API_KEY = "demo-key-1234"  # local-dev only


async def main() -> None:
    key_hash = bcrypt.hashpw(DEMO_API_KEY.encode(), bcrypt.gensalt()).decode()

    async with SessionLocal() as s:
        await s.execute(
            text(
                "INSERT INTO tenants (id, name) VALUES (:id, :name) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": DEMO_TENANT_ID, "name": DEMO_TENANT_NAME},
        )
        await s.execute(
            text(
                "INSERT INTO api_keys (tenant_id, key_hash, description) "
                "VALUES (:tid, :hash, :desc) "
                "ON CONFLICT (key_hash) DO NOTHING"
            ),
            {"tid": DEMO_TENANT_ID, "hash": key_hash, "desc": "local dev"},
        )
        await s.commit()
    print(f"Seeded tenant={DEMO_TENANT_ID}, api_key={DEMO_API_KEY}")


if __name__ == "__main__":
    asyncio.run(main())
