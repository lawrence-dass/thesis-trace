"""Tests for the health endpoints and config presence checks (Story 1.1, AC2/AC4/AC5).

The DB-connectivity test is skipped when DATABASE_URL is unset, so the suite is
green with no live database (Story 1.1 testing standard).
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import app


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_health_ok() -> None:
    async with await _client() as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_missing_required_flags_absent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "EDGAR_CONTACT", "TIINGO_API_KEY", "LLM_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert set(settings.missing_required()) == {
        "DATABASE_URL",
        "EDGAR_CONTACT",
        "TIINGO_API_KEY",
        "LLM_API_KEY",
    }


async def test_health_db_503_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Reset any cached engine so the unconfigured path is exercised.
    import app.db as db_module

    db_module._engine = None
    db_module._sessionmaker = None
    async with await _client() as client:
        resp = await client.get("/health/db")
    assert resp.status_code == 503
    body = resp.json()
    assert body["error"]["code"] == "db_unconfigured"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="no live DATABASE_URL configured")
async def test_health_db_ok_with_live_db() -> None:
    async with await _client() as client:
        resp = await client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json()["db"] == "ok"
