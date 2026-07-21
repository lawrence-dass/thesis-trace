"""Test fixtures. DB-backed tests use TEST_DATABASE_URL (or DATABASE_URL) and are
skipped entirely when neither is set, so the suite stays green offline.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base

TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")

requires_db = pytest.mark.skipif(not TEST_DB_URL, reason="no TEST_DATABASE_URL/DATABASE_URL configured")


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fresh schema per test against the test database (create_all/drop_all)."""
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
