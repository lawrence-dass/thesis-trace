"""Test fixtures.

DB-backed tests require `TEST_DATABASE_URL` and are skipped entirely when it is
absent, so the suite stays green offline.

`DATABASE_URL` IS DELIBERATELY NOT A FALLBACK. `db_session` runs `drop_all` on
whatever URL it is handed, so a fallback means anyone who exports only
`DATABASE_URL` — the ordinary way to run the application — silently points a
destructive fixture at their development database. That is a real incident in this
project's history and the reason `.env` keeps the two as separate values.

Requiring the explicit variable costs CI nothing: `.github/workflows/ci.yml` sets
both, pointing at the same throwaway service container, because Alembic's `env.py`
reads `DATABASE_URL` while the fixtures below read `TEST_DATABASE_URL`.

The failure mode this closes is silent in the dangerous direction — the fallback
made the suite *run* (against the wrong database) where the absence makes it
*skip*. A skip is visible; a wiped dev database is discovered later.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


def _resolve_test_db_url(env: Mapping[str, str]) -> str | None:
    """The database `db_session` is allowed to drop and recreate.

    `TEST_DATABASE_URL` only, and empty is treated as absent so an exported-but-blank
    variable cannot resolve to something falsy that later code treats as configured.
    See the module docstring for why `DATABASE_URL` is not consulted.
    """
    return env.get("TEST_DATABASE_URL") or None


TEST_DB_URL = _resolve_test_db_url(os.environ)

requires_db = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL is not set (DATABASE_URL is deliberately not a fallback)",
)


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
