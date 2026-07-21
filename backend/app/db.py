"""Async database access (SQLAlchemy 2.0, asyncpg).

Python owns all data access (AD-8). The read path only ever queries
materialized Postgres and never triggers a write or computation (AD-1, AD-10).
The engine is created lazily so the app can start and serve `/health` even when
DATABASE_URL is unset (e.g. local dev without a database).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker | None = None


def get_engine() -> AsyncEngine | None:
    """Return the shared async engine, or None if DATABASE_URL is unset."""
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine
    database_url = get_settings().database_url
    if not database_url:
        return None
    _engine = create_async_engine(database_url, pool_pre_ping=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker | None:
    if _sessionmaker is None:
        get_engine()
    return _sessionmaker
