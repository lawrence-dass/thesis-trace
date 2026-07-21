"""Story 1.2 — data-model invariants (AD-2, AD-15, AD-16, AD-17, AD-18)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import (
    Filing,
    Issuer,
    Model,
    RawFact,
    ScoreResult,
    ScoreRun,
    SignalStatus,
)
from tests.conftest import requires_db

EXPECTED_TABLES = {
    "issuers",
    "filings",
    "raw_facts",
    "concept_mappings",
    "canonical_facts",
    "score_runs",
    "score_inputs",
    "score_results",
    "data_quality_issues",
}


@requires_db
async def test_expected_tables_present(db_session) -> None:
    def _tables(sync_conn):
        return set(inspect(sync_conn).get_table_names())

    conn = await db_session.connection()
    tables = await conn.run_sync(_tables)
    assert EXPECTED_TABLES.issubset(tables)


@requires_db
async def test_market_prices_present(db_session) -> None:
    """market_prices arrived in Story 2.1 (Altman/Tiingo, AD-14)."""

    def _tables(sync_conn):
        return set(inspect(sync_conn).get_table_names())

    conn = await db_session.connection()
    tables = await conn.run_sync(_tables)
    assert "market_prices" in tables


@requires_db
async def test_score_results_value_is_numeric(db_session) -> None:
    row = (
        await db_session.execute(
            text(
                "select data_type from information_schema.columns "
                "where table_name='score_results' and column_name='value'"
            )
        )
    ).scalar_one()
    assert row == "numeric"  # never float/double (AD-15)


@requires_db
async def test_raw_facts_append_only_unique(db_session) -> None:
    issuer = Issuer(cik="0001594805", ticker="SHOP", name="Shopify Inc.")
    filing = Filing(
        accession_number="0001594805-25-000010",
        issuer_cik="0001594805",
        form_type="10-K",
        filing_date=date(2025, 2, 1),
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
    )
    db_session.add_all([issuer, filing])
    await db_session.flush()

    def _fact():
        return RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Assets",
            source="company_facts",
            content_hash="abc123",
        )

    db_session.add(_fact())
    await db_session.flush()
    db_session.add(_fact())  # same (accession_number, content_hash) → violates AD-2 uniqueness
    with pytest.raises(IntegrityError):
        await db_session.flush()


@requires_db
async def test_tristate_status_persists(db_session) -> None:
    issuer = Issuer(cik="0001594805", ticker="SHOP", name="Shopify Inc.")
    filing = Filing(
        accession_number="0001594805-25-000010",
        issuer_cik="0001594805",
        form_type="10-K",
        filing_date=date(2025, 2, 1),
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
    )
    db_session.add_all([issuer, filing])
    await db_session.flush()

    run = ScoreRun(
        issuer_cik="0001594805",
        model=Model.piotroski,
        fiscal_year=2024,
        formula_version="piotroski_v1",
        accession_number="0001594805-25-000010",
    )
    db_session.add(run)
    await db_session.flush()

    db_session.add(
        ScoreResult(
            score_run_id=run.id,
            model=Model.piotroski,
            signal_key="roa_positive",
            value=None,
            status=SignalStatus.insufficient_data,  # missing input, never a defaulted 0 (AD-16)
        )
    )
    await db_session.flush()
    stored = (await db_session.execute(text("select status from score_results"))).scalar_one()
    assert stored == "insufficient_data"
