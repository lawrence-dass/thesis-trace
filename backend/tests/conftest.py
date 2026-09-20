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
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


def _database_identity(url: str) -> tuple[str, str, str]:
    """(host, port, database) — what a DSN actually POINTS AT.

    Two DSNs that differ as strings can address one database: a query parameter, a
    trailing slash, a different driver prefix or a spelled-out default port all change
    the text and nothing else. Comparing the text is therefore not a safety check, and
    `drop_all` is not an operation that tolerates an approximate one.
    """
    parsed = urlsplit(url)
    port = parsed.port or 5432
    return (parsed.hostname or "", str(port), (parsed.path or "").lstrip("/"))


def _resolve_test_db_url(env: Mapping[str, str]) -> str | None:
    """The database `db_session` is allowed to drop and recreate.

    `TEST_DATABASE_URL` only, and empty is treated as absent so an exported-but-blank
    variable cannot resolve to something falsy that later code treats as configured.
    See the module docstring for why `DATABASE_URL` is not consulted.

    REFUSES, loudly, when it addresses the same database as `DATABASE_URL`. Verified
    2026-09-20: `.../thesistrace?sslmode=disable` beside `DATABASE_URL=.../thesistrace`
    passed a string comparison and started a full run against the dev store — it
    survived only because asyncpg rejects that parameter, not because anything stopped
    it. The guard belongs here, beside the drop_all, rather than only in the Makefile:
    a direct `pytest` invocation never reaches a make target.
    """
    test_url = env.get("TEST_DATABASE_URL") or None
    if test_url is None:
        return None
    dev_url = env.get("DATABASE_URL") or None
    if dev_url and _database_identity(test_url) == _database_identity(dev_url):
        host, port, name = _database_identity(test_url)
        raise RuntimeError(
            f"TEST_DATABASE_URL and DATABASE_URL both address {name} at {host}:{port}. "
            "The DB fixtures drop every table on setup and teardown; this run would "
            "have destroyed the development database. The two URLs differing as TEXT "
            "is not enough — see .env.example."
        )
    return test_url


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
