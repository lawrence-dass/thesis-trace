"""FastAPI dependencies for the read API."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("DATABASE_URL is not configured.")
    async with sessionmaker() as session:
        yield session
