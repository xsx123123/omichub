"""PostgreSQL transaction-scoped concurrency boundary."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_resource(db: AsyncSession, key: str) -> None:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})
