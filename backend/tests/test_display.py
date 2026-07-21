"""Stories 2.4 & 2.5 — lens-category grouping + data-quality surfacing (FR-5, FR-8; AD-17)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.deps import get_session
from app.main import app
from app.models import Base, DataQualityIssue, IssueStatus
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from scoring.runner import score_beneish, score_piotroski, score_sloan
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
        await score_beneish(session, parsed.cik, 2024)
        # Seed a data-quality warning tied to the FY2024 filing.
        session.add(
            DataQualityIssue(
                accession_number="0001594805-25-000010",
                issue_type="identity_violation:demo",
                status=IssueStatus.needs_review,
                raised_by="validation",
                detail={"note": "seeded for display test"},
            )
        )
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
async def test_overview_groups_by_category_and_surfaces_data_quality(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        resp = await client.get("/api/companies/SHOP/overview")
    body = resp.json()

    cats = {s["model"]: s["category"] for s in body["scores"]}
    assert cats["piotroski"] == "quality_health"
    assert cats["sloan"] == "integrity"
    assert cats["beneish"] == "integrity"

    # Data-quality warning surfaced, never hidden (FR-8, AD-17).
    assert any(dq["issue_type"] == "identity_violation:demo" for dq in body["data_quality"])
