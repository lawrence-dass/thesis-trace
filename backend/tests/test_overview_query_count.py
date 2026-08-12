"""Query-count guard for `get_company_overview` (risk-assessment finding 3.10).

The N+1 here is REAL and measured, not hypothetical: against live data the overview
issues 484 queries for OTEX (20 fiscal years), 343 for CP (13) and 100 for SHOP (5).
Story 6.5 measured it again with the reverse DCF wired in and found +2 to +3, FLAT —
it inherits the N+1 rather than causing it.

This file does NOT fix that. Batching the per-run and per-signal loads is its own
piece of work (Track P). What it does is stop the number moving silently in the
meantime: an unrelated change that turns 484 into 900 currently has nothing to trip
over, and a linear cost that quietly becomes quadratic would show up first as a slow
page rather than as a failing test.

Two things are asserted, and the second matters more than the first:

  1. The exact count for a known history length, so ANY change is visible.
  2. That the count grows LINEARLY with the number of fiscal years — measured by
     running two different history lengths and comparing the per-year slope. An
     exact count alone would still pass if someone made the per-year cost worse
     while shortening the fixed prelude.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from api.repository import get_company_overview
from app.models import (
    Applicability,
    Filing,
    Issuer,
    Model,
    ScoreResult,
    ScoreRun,
    SignalStatus,
)
from sqlalchemy import event
from tests.conftest import requires_db

MODELS = (Model.piotroski, Model.altman, Model.beneish, Model.sloan)
SIGNALS_PER_RUN = 3


@contextmanager
def _count_queries(session):
    """Count statements actually sent to the server.

    Hooks `before_cursor_execute` on the SYNC engine underneath the async one —
    that is the layer every statement passes through, so nothing the ORM emits
    lazily can slip past the counter.
    """
    bind = session.get_bind()
    engine = getattr(bind, "sync_engine", bind)
    counter = {"n": 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    event.listen(engine, "before_cursor_execute", _before)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _before)


async def _seed_issuer(db_session, cik: str, ticker: str, years: int) -> None:
    """One issuer with `years` fiscal years scored across all four models."""
    db_session.add(Issuer(cik=cik, ticker=ticker, name=f"{ticker} Test Co"))
    accn = f"{cik[:10]}-99-000001"
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

    for offset in range(years):
        fiscal_year = 2025 - offset
        for model in MODELS:
            run = ScoreRun(
                issuer_cik=cik,
                model=model,
                fiscal_year=fiscal_year,
                formula_version=f"{model.value}_v1",
                accession_number=accn,
                aggregate_value=1.0,
                applicability=Applicability.computed,
            )
            db_session.add(run)
            await db_session.flush()
            for index in range(SIGNALS_PER_RUN):
                db_session.add(
                    ScoreResult(
                        score_run_id=run.id,
                        model=model,
                        signal_key=f"signal_{index}",
                        value=1.0,
                        status=SignalStatus.pass_,
                    )
                )
    await db_session.commit()


@requires_db
async def test_overview_query_count_is_pinned_and_linear(db_session) -> None:
    short_years, long_years = 2, 6

    await _seed_issuer(db_session, "9999900001", "SHORT", short_years)
    await _seed_issuer(db_session, "9999900002", "LONGH", long_years)

    with _count_queries(db_session) as short_counter:
        short_overview = await get_company_overview(db_session, "SHORT")
    with _count_queries(db_session) as long_counter:
        long_overview = await get_company_overview(db_session, "LONGH")

    assert short_overview is not None and long_overview is not None

    short_count, long_count = short_counter["n"], long_counter["n"]

    # The per-year slope. Asserted rather than the totals alone: a change that made
    # each year more expensive while trimming the fixed prelude would keep a single
    # pinned total looking right.
    per_year = (long_count - short_count) / (long_years - short_years)

    assert per_year == PER_YEAR_QUERIES, (
        f"query cost per fiscal year moved: {per_year} vs the recorded "
        f"{PER_YEAR_QUERIES} ({short_count} queries for {short_years} years, "
        f"{long_count} for {long_years}). If this went DOWN the N+1 was batched — "
        "update this number and say so. If it went UP, something added a per-year "
        "round trip."
    )
    assert short_count == SHORT_HISTORY_QUERIES, (
        f"overview issued {short_count} queries for {short_years} fiscal years, "
        f"recorded {SHORT_HISTORY_QUERIES}"
    )
    assert long_count == LONG_HISTORY_QUERIES, (
        f"overview issued {long_count} queries for {long_years} fiscal years, "
        f"recorded {LONG_HISTORY_QUERIES}"
    )


# Recorded 2026-08-12 by running the test. These are the CURRENT cost, deliberately
# not a target: the point is that changing them requires saying why.
#
# THESE ARE NOT THE LIVE NUMBERS AND ARE NOT MEANT TO BE. The fixture above gives
# every run 3 signals; the real models carry 5-9, and a live issuer also has debt,
# maturity, market-price and reverse-DCF reads on top. So 484-for-OTEX and 100-for-
# six-synthetic-years measure the same defect at different scales, and neither is
# wrong. What transfers between them is the SHAPE: cost per fiscal year is constant
# and non-zero, which is the definition of the N+1 this guards.
SHORT_HISTORY_QUERIES = 36
LONG_HISTORY_QUERIES = 100
PER_YEAR_QUERIES = 16
