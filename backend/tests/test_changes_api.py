"""Story 5.3 — change-detection read API (FR-22; AD-1, AD-10).

Seeds score runs directly rather than through the pipeline, so each test pins
exact `computed_at` instants and values. The endpoint is exercised through the
real ASGI app with the session dependency overridden.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.deps import get_session
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
from tests.conftest import TEST_DB_URL, requires_db

CIK = "0001594805"
ACC_OLD = "0000000000-24-000001"
ACC_NEW = "0000000000-25-000001"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
SINCE = datetime(2026, 2, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _run(**kw) -> ScoreRun:
    base = dict(
        id=uuid.uuid4(), issuer_cik=CIK, model=Model.altman, fiscal_year=2024,
        formula_version="altman_v1", accession_number=ACC_OLD,
        aggregate_value=Decimal("2.5"), applicability=Applicability.computed,
        superseded=False, computed_at=T0,
    )
    base.update(kw)
    return ScoreRun(**base)


async def _seed(session, runs_spec, *, filing_created: dict[str, datetime] | None = None):
    session.add(Issuer(cik=CIK, ticker="TEST", name="Test Corp"))
    created = filing_created or {ACC_OLD: T0, ACC_NEW: T0}
    for acc, fy in ((ACC_OLD, 2024), (ACC_NEW, 2025)):
        session.add(
            Filing(
                accession_number=acc, issuer_cik=CIK, form_type="10-K",
                filing_date=date(fy + 1, 2, 1), fiscal_year=fy,
                fiscal_year_end=date(fy, 12, 31), created_at=created[acc],
            )
        )
    await session.flush()
    for spec in runs_spec:
        band = spec.pop("band", "Grey")
        run = _run(**spec)
        session.add(run)
        await session.flush()
        session.add(
            ScoreResult(
                score_run_id=run.id, model=run.model, signal_key="aggregate",
                value=run.aggregate_value, status=SignalStatus.pass_, band_label=band,
            )
        )
    await session.flush()


@pytest_asyncio.fixture
async def client_factory():
    engine = create_async_engine(TEST_DB_URL)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _make(runs_spec, **seed_kw):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        async with sm() as s:
            await _seed(s, runs_spec, **seed_kw)
            await s.commit()

        async def _override():
            async with sm() as s:
                yield s

        app.dependency_overrides[get_session] = _override
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), sm

    yield _make
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@requires_db
async def test_explicit_since_returns_the_structured_diff(client_factory) -> None:
    client, _ = await client_factory([
        dict(aggregate_value=Decimal("2.5"), band="Grey", computed_at=T0, superseded=True),
        dict(aggregate_value=Decimal("1.1"), band="Distress", computed_at=T1),
    ])
    async with client as c:
        r = await c.get("/api/companies/TEST/changes", params={"since": SINCE.isoformat()})
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "ok"
    assert body["comparison_state"] == "changes"
    assert body["since_basis"] == "explicit"
    rc = body["run_changes"][0]
    assert "band_change" in rc["kinds"]
    assert rc["prior_band_label"] == "Grey"
    assert rc["current_band_label"] == "Distress"


@requires_db
async def test_no_prior_state_is_not_an_error_and_not_an_empty_diff(client_factory) -> None:
    """Three-way state: the UI must be able to tell these apart (FR-22)."""
    client, _ = await client_factory([dict(computed_at=T1)])
    async with client as c:
        r = await c.get("/api/companies/TEST/changes", params={"since": SINCE.isoformat()})
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "ok"             # not an error
    assert body["comparison_state"] == "no_prior_state"
    assert body["run_changes"] == []


@requires_db
async def test_no_change_is_distinct_from_no_prior_state(client_factory) -> None:
    client, _ = await client_factory([dict(computed_at=T0)])
    async with client as c:
        r = await c.get("/api/companies/TEST/changes", params={"since": SINCE.isoformat()})
    body = r.json()
    assert body["comparison_state"] == "no_change"
    assert body["comparison_state"] != "no_prior_state"
    assert body["run_changes"] == []


@requires_db
async def test_default_since_pivots_on_the_latest_filing(client_factory) -> None:
    """Omitting `since` must not compare against last night's rescore.

    The newest filing lands at SINCE; the run before it and the run after it
    differ, so the default pivot has to surface that change.
    """
    client, _ = await client_factory(
        [
            dict(aggregate_value=Decimal("2.5"), band="Grey", computed_at=T0, superseded=True),
            dict(aggregate_value=Decimal("1.1"), band="Distress", computed_at=T1,
                 accession_number=ACC_NEW),
        ],
        filing_created={ACC_OLD: T0, ACC_NEW: SINCE},
    )
    async with client as c:
        r = await c.get("/api/companies/TEST/changes")
    body = r.json()
    assert body["since_basis"] == "latest_filing"
    assert body["since_accession"] == ACC_NEW
    assert body["comparison_state"] == "changes"
    assert "band_change" in body["run_changes"][0]["kinds"]


@requires_db
async def test_unknown_ticker_is_honest_coverage_not_an_error(client_factory) -> None:
    client, _ = await client_factory([dict(computed_at=T0)])
    async with client as c:
        r = await c.get("/api/companies/NOPE/changes")
    assert r.status_code == 200
    assert r.json()["state"] == "not_available"


@requires_db
async def test_request_never_triggers_scoring_or_writes(client_factory) -> None:
    """AD-1: the read path cannot cause computation.

    Counts score_runs before and after — a request that recomputed would add a
    run, since `scoring.runner` always appends rather than mutating.
    """
    client, sm = await client_factory([
        dict(aggregate_value=Decimal("2.5"), computed_at=T0, superseded=True),
        dict(aggregate_value=Decimal("1.1"), computed_at=T1),
    ])
    async with sm() as s:
        before = (await s.execute(select(func.count()).select_from(ScoreRun))).scalar()
    async with client as c:
        for _ in range(3):
            await c.get("/api/companies/TEST/changes", params={"since": SINCE.isoformat()})
    async with sm() as s:
        after = (await s.execute(select(func.count()).select_from(ScoreRun))).scalar()
        results = (await s.execute(select(func.count()).select_from(ScoreResult))).scalar()
    assert after == before, "a read request created a score_run"
    assert results == 2, "a read request created score_results"


@requires_db
async def test_response_cites_both_endpoints(client_factory) -> None:
    """AD-19: a change must be auditable to the filings on both sides."""
    client, _ = await client_factory([
        dict(aggregate_value=Decimal("2.5"), computed_at=T0, superseded=True,
             accession_number=ACC_OLD),
        dict(aggregate_value=Decimal("1.1"), computed_at=T1, accession_number=ACC_NEW),
    ])
    async with client as c:
        r = await c.get("/api/companies/TEST/changes", params={"since": SINCE.isoformat()})
    rc = r.json()["run_changes"][0]
    assert rc["prior_accession_number"] == ACC_OLD
    assert rc["current_accession_number"] == ACC_NEW


@requires_db
async def test_malformed_since_is_rejected_rather_than_silently_defaulted(client_factory) -> None:
    """A bad timestamp must not quietly fall back to the default pivot —
    that would answer a different question than the caller asked."""
    client, _ = await client_factory([dict(computed_at=T0)])
    async with client as c:
        r = await c.get("/api/companies/TEST/changes?since=not-a-date")
    assert r.status_code == 422
