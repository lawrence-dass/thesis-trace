"""Story 1.8 — read-only query API + provenance (FR-3/FR-7 surfaced; AD-1, AD-10, AD-19).

Seeds the pipeline end-to-end (ingest -> canonicalize -> score) with a committed
transaction, then queries via the ASGI app with the session dependency overridden
to the test engine.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.deps import get_session
from api.repository import get_company_overview
from app.main import app
from app.models import (
    Applicability,
    Base,
    Filing,
    Issuer,
    Model,
    ScoreResult,
    ScoreRun,
    SignalStatus,
)
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
async def test_verdict_prefers_latest_year_with_a_value(db_session) -> None:
    """Regression guard: a model is scored every scoreable year regardless of
    whether its inputs resolve (e.g. Beneish always gets a ScoreRun row, even
    insufficient_data) — naively taking the newest run per model can hide a
    real, valid result behind an unrelated later year missing an input.
    Confirmed live 2026-07-29: QSR has 7 real Beneish years (2017-2023) and
    OTEX has 9 (2011-2019) that the old "just take the newest" selection
    hid behind their unrelated FY2025 insufficient_data run. The Verdict
    must show the latest year that actually resolved, falling back to the
    latest run's insufficient_data only when no year ever did."""
    cik = "9999999999"
    accn = "0000000000-99-000001"
    db_session.add(Issuer(cik=cik, ticker="TEST", name="Test Co"))
    db_session.add(
        Filing(
            accession_number=accn,
            issuer_cik=cik,
            form_type="10-K",
            filing_date=date(2025, 2, 1),
            fiscal_year=2025,
            fiscal_year_end=date(2024, 12, 31),
        )
    )
    await db_session.flush()

    valid_run = ScoreRun(
        issuer_cik=cik,
        model=Model.beneish,
        fiscal_year=2023,
        formula_version="beneish_v1",
        accession_number=accn,
        aggregate_value=-2.5,
        applicability=Applicability.computed,
    )
    insufficient_run = ScoreRun(
        issuer_cik=cik,
        model=Model.beneish,
        fiscal_year=2024,
        formula_version="beneish_v1",
        accession_number=accn,
        aggregate_value=None,
        applicability=Applicability.computed,
    )
    db_session.add_all([valid_run, insufficient_run])
    await db_session.flush()

    db_session.add(
        ScoreResult(
            score_run_id=valid_run.id,
            model=Model.beneish,
            signal_key="dsri",
            value=1.0,
            status=SignalStatus.pass_,
            band_label="No manipulation flag",
        )
    )
    db_session.add(
        ScoreResult(
            score_run_id=insufficient_run.id,
            model=Model.beneish,
            signal_key="dsri",
            value=None,
            status=SignalStatus.insufficient_data,
        )
    )
    await db_session.commit()

    overview = await get_company_overview(db_session, "TEST")
    beneish_verdict = next(v for v in overview.verdict if v.model == "beneish")
    assert beneish_verdict.fiscal_year == 2023
    assert beneish_verdict.aggregate_value == -2.5


@requires_db
async def test_verdict_falls_back_to_latest_when_never_valid(db_session) -> None:
    """Companion to the test above: when a model NEVER resolves for any year
    (e.g. CP's Beneish — genuinely no COGS/SGA tags), the Verdict must still
    show the model with its latest insufficient_data run, not silently drop
    it from the Verdict entirely."""
    cik = "9999999998"
    accn = "0000000000-99-000002"
    db_session.add(Issuer(cik=cik, ticker="TEST2", name="Test Co 2"))
    db_session.add(
        Filing(
            accession_number=accn,
            issuer_cik=cik,
            form_type="10-K",
            filing_date=date(2025, 2, 1),
            fiscal_year=2025,
            fiscal_year_end=date(2024, 12, 31),
        )
    )
    await db_session.flush()

    run_2023 = ScoreRun(
        issuer_cik=cik,
        model=Model.beneish,
        fiscal_year=2023,
        formula_version="beneish_v1",
        accession_number=accn,
        aggregate_value=None,
        applicability=Applicability.computed,
    )
    run_2024 = ScoreRun(
        issuer_cik=cik,
        model=Model.beneish,
        fiscal_year=2024,
        formula_version="beneish_v1",
        accession_number=accn,
        aggregate_value=None,
        applicability=Applicability.computed,
    )
    db_session.add_all([run_2023, run_2024])
    await db_session.flush()

    # run_2024 (the one Verdict picks) has a mix of pass/insufficient signals —
    # only the insufficient ones should show up in missing_signals.
    db_session.add(
        ScoreResult(score_run_id=run_2024.id, model=Model.beneish, signal_key="dsri", value=1.0, status=SignalStatus.pass_)
    )
    db_session.add(
        ScoreResult(score_run_id=run_2024.id, model=Model.beneish, signal_key="gmi", value=None, status=SignalStatus.insufficient_data)
    )
    db_session.add(
        ScoreResult(score_run_id=run_2024.id, model=Model.beneish, signal_key="sgai", value=None, status=SignalStatus.insufficient_data)
    )
    await db_session.commit()

    overview = await get_company_overview(db_session, "TEST2")
    beneish_verdict = next(v for v in overview.verdict if v.model == "beneish")
    assert beneish_verdict.fiscal_year == 2024  # still the latest, never silently dropped
    assert beneish_verdict.aggregate_value is None
    assert set(beneish_verdict.missing_signals) == {"gmi", "sgai"}  # not dsri, which passed


@requires_db
async def test_verdict_carries_caveat_reason_alongside_missing_signals(db_session) -> None:
    """Regression guard for the Overview grid's caveat-reason gap (PR #113):
    caveat_reason must flow from the ScoreRun through to the VerdictItem the
    Overview page reads, and — the live-verified Suncor shape — a run can be
    BOTH computed_with_caveat AND aggregate_value=None at once (the cross-filer
    comparability layer in scoring/runner.py's _applicability can promote an
    insufficient_data run to computed_with_caveat), so missing_signals and
    caveat_reason must coexist rather than being mutually exclusive."""
    cik = "9999999997"
    accn = "0000000000-99-000003"
    db_session.add(Issuer(cik=cik, ticker="TEST3", name="Test Co 3"))
    db_session.add(
        Filing(
            accession_number=accn,
            issuer_cik=cik,
            form_type="10-K",
            filing_date=date(2025, 2, 1),
            fiscal_year=2025,
            fiscal_year_end=date(2024, 12, 31),
        )
    )
    await db_session.flush()

    caveated_no_value = ScoreRun(
        issuer_cik=cik,
        model=Model.altman,
        fiscal_year=2025,
        formula_version="altman_v1",
        accession_number=accn,
        aggregate_value=None,
        applicability=Applicability.computed_with_caveat,
        caveat_reason="this is a capital-intensive company, for which the model runs structurally low",
    )
    caveated_with_value = ScoreRun(
        issuer_cik=cik,
        model=Model.beneish,
        fiscal_year=2025,
        formula_version="beneish_v1",
        accession_number=accn,
        aggregate_value=-2.5,
        applicability=Applicability.computed_with_caveat,
        caveat_reason="the gross margin is an approximation rather than a reported figure",
    )
    plain_computed = ScoreRun(
        issuer_cik=cik,
        model=Model.piotroski,
        fiscal_year=2025,
        formula_version="piotroski_v1",
        accession_number=accn,
        aggregate_value=6,
        applicability=Applicability.computed,
    )
    db_session.add_all([caveated_no_value, caveated_with_value, plain_computed])
    await db_session.flush()

    db_session.add(
        ScoreResult(
            score_run_id=caveated_no_value.id,
            model=Model.altman,
            signal_key="working_capital_ratio",
            value=None,
            status=SignalStatus.insufficient_data,
        )
    )
    db_session.add(
        ScoreResult(
            score_run_id=caveated_with_value.id,
            model=Model.beneish,
            signal_key="gmi",
            value=1.0,
            status=SignalStatus.pass_,
            band_label="No manipulation flag",
        )
    )
    await db_session.commit()

    overview = await get_company_overview(db_session, "TEST3")
    altman_verdict = next(v for v in overview.verdict if v.model == "altman")
    assert altman_verdict.aggregate_value is None
    assert altman_verdict.missing_signals == ["working_capital_ratio"]
    assert altman_verdict.caveat_reason == (
        "this is a capital-intensive company, for which the model runs structurally low"
    )

    beneish_verdict = next(v for v in overview.verdict if v.model == "beneish")
    assert beneish_verdict.aggregate_value == -2.5
    assert beneish_verdict.caveat_reason == "the gross margin is an approximation rather than a reported figure"
    serialized_beneish = next(item for item in overview.model_dump()["verdict"] if item["model"] == "beneish")
    assert serialized_beneish["caveat_reason"] == "the gross margin is an approximation rather than a reported figure"

    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/companies/TEST3/overview")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert response.status_code == 200
    endpoint_beneish = next(item for item in response.json()["verdict"] if item["model"] == "beneish")
    assert endpoint_beneish["caveat_reason"] == "the gross margin is an approximation rather than a reported figure"

    piotroski_verdict = next(v for v in overview.verdict if v.model == "piotroski")
    assert piotroski_verdict.caveat_reason is None  # plain computed never carries a caveat


@requires_db
async def test_companies_list(seeded_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=seeded_app), base_url="http://test") as client:
        resp = await client.get("/api/companies")
    cards = resp.json()
    tickers = [c["ticker"] for c in cards]
    assert "SHOP" in tickers
    # FR-1 card carries a last-updated date.
    shop = next(c for c in cards if c["ticker"] == "SHOP")
    assert shop["last_updated"] is not None
