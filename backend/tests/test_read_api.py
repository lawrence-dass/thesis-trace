"""Story 1.8 — read-only query API + provenance (FR-3/FR-7 surfaced; AD-1, AD-10, AD-19).

Seeds the pipeline end-to-end (ingest -> canonicalize -> score) with a committed
transaction, then queries via the ASGI app with the session dependency overridden
to the test engine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.deps import get_session
from app.main import app
from app.models import Base
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from scoring.runner import score_piotroski, score_sloan
from tests.conftest import TEST_DB_URL, requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


@pytest_asyncio.fixture
async def seeded_app():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
        await persist_company_facts(session, parsed, ticker="SHOP")
        await seed_concept_mappings(session)
        await canonicalize_issuer(session, parsed.cik)
        await score_piotroski(session, parsed.cik, 2024)
        await score_sloan(session, parsed.cik, 2024)
        await session.commit()

    async def _override():
        async with sm() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    yield app
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@requires_db
async def test_overview_returns_scores_with_provenance(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        resp = await client.get("/api/companies/SHOP/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "ok"
    assert body["ticker"] == "SHOP"
    assert set(body["lenses_live"]) == {"piotroski", "sloan"}

    piotroski = next(s for s in body["scores"] if s["model"] == "piotroski")
    assert len(piotroski["signals"]) == 9
    roa = next(s for s in piotroski["signals"] if s["signal_key"] == "roa_positive")
    assert roa["status"] == "pass"
    # Provenance travels with the value (AD-19).
    assert roa["provenance"]
    assert roa["provenance"][0]["accession_number"].startswith("0001594805")


@requires_db
async def test_uncovered_company_is_not_available(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        resp = await client.get("/api/companies/ZZZZ/overview")
    assert resp.status_code == 200  # not an error
    assert resp.json()["state"] == "not_available"


@requires_db
async def test_companies_list(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        resp = await client.get("/api/companies")
    tickers = [c["ticker"] for c in resp.json()]
    assert "SHOP" in tickers
