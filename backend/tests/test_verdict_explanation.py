"""Epic 3 — Verdict (3.1), Methodology (3.4), Explanation (3.5/3.6)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.deps import get_session
from app.main import app
from app.models import Base
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from explanation.llm import polish, rewrite_enabled
from ingestion.company_facts import parse_company_facts
from raw_store.market_prices import upsert_fye_close
from raw_store.repository import persist_company_facts
from scoring.runner import score_altman, score_beneish, score_piotroski, score_sloan
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
        await upsert_fye_close(session, issuer_cik=parsed.cik, price_date=date(2024, 12, 31), close_price=106.20)
        await score_piotroski(session, parsed.cik, 2024)
        await score_sloan(session, parsed.cik, 2024)
        await score_beneish(session, parsed.cik, 2024)
        await score_altman(session, parsed.cik, 2024)
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
async def test_verdict_juxtaposes_four_models_with_phase_honesty(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        body = (await client.get("/api/companies/SHOP/overview")).json()
    verdict_models = {v["model"] for v in body["verdict"]}
    assert verdict_models == {"piotroski", "altman", "beneish", "sloan"}
    # No blended single number: each item carries its own band, not a combined score.
    assert all("band_label" in v for v in body["verdict"])
    # Phase honesty: Value + Growth shown as pending (FR-9).
    assert body["lenses_pending"] == ["value", "growth"]


@requires_db
async def test_methodology_reads_versioned_spec(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        body = (await client.get("/api/methodology/piotroski")).json()
    assert body["state"] == "ok"
    assert body["formula_version"] == "piotroski_v1"
    assert "net_income" in body["inputs"]
    assert "Piotroski" in body["source"]

    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        missing = (await client.get("/api/methodology/nope")).json()
    assert missing["state"] == "not_available"


@requires_db
async def test_explanation_is_cited_and_deterministic(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        body = (await client.get("/api/companies/SHOP/explanation")).json()
    assert body["state"] == "ok"
    assert body["llm_rewrite"] is False  # no key configured in tests
    piotroski = next(e for e in body["explanations"] if e["model"] == "piotroski")
    assert "Piotroski F-Score" in piotroski["text"]
    assert piotroski["citations"]  # grounded in provenance (accession numbers)


async def test_llm_rewrite_disabled_returns_text_unchanged() -> None:
    # No LLM key in tests -> rewrite is a safe no-op (deterministic-only, AD-7).
    assert rewrite_enabled() is False
    original = "Piotroski F-Score for FY2024 is 7 — classified Strong."
    assert await polish(original) == original
