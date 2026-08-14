"""Query-count guard for `get_company_overview` (risk-assessment finding 3.10).

TRACK P IS DONE, AND THIS FILE CHANGED CHARACTER WITH IT. It used to guard an N+1
that existed — 484 queries for OTEX (20 fiscal years), 343 for CP, 100 for SHOP,
growing by a constant 16 per fiscal year forever. Both loads are now single `IN`
queries resolved in memory, and against the live store the overview costs 8 queries
for OTEX instead of 486. The whole universe went from 2,092 queries to 54.

So the interesting assertion is no longer "the number has not moved". It is:

    THE COST DOES NOT DEPEND ON HISTORY LENGTH AT ALL.

That is a much stronger property than the old linear-slope check, and a much
cheaper one to break: anything that reintroduces a per-run or per-signal round trip
puts the slope back above zero and fails here, whatever the totals happen to be.
The exact totals are still pinned underneath, so a change in the fixed prelude is
visible too — but the slope is the load-bearing assertion.

A filer with twenty years of history and one with two must now cost the same.
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
async def test_overview_query_count_does_not_grow_with_history(db_session) -> None:
    # Deliberately far apart. Two lengths one year apart could hide a small
    # per-year cost inside rounding; 2 against 6 cannot.
    short_years, long_years = 2, 6

    await _seed_issuer(db_session, "9999900001", "SHORT", short_years)
    await _seed_issuer(db_session, "9999900002", "LONGH", long_years)

    with _count_queries(db_session) as short_counter:
        short_overview = await get_company_overview(db_session, "SHORT")
    with _count_queries(db_session) as long_counter:
        long_overview = await get_company_overview(db_session, "LONGH")

    assert short_overview is not None and long_overview is not None

    short_count, long_count = short_counter["n"], long_counter["n"]

    # THE LOAD-BEARING ASSERTION. Zero, not "small": a filer with twenty years of
    # history must cost exactly what one with two costs. Anything that reintroduces
    # a per-run or per-signal round trip puts this above zero, whatever the totals
    # do — which is why it is checked before them.
    per_year = (long_count - short_count) / (long_years - short_years)

    assert per_year == PER_YEAR_QUERIES, (
        f"query cost per fiscal year is {per_year}, recorded {PER_YEAR_QUERIES} "
        f"({short_count} queries for {short_years} years, {long_count} for "
        f"{long_years}). Above zero means a per-year round trip came back and the "
        "overview is an N+1 again — the exact defect Track P removed. Batch the new "
        "load the way `_results_for_runs` and `_provenance_for_runs` do."
    )
    assert short_count == SHORT_HISTORY_QUERIES, (
        f"overview issued {short_count} queries for {short_years} fiscal years, "
        f"recorded {SHORT_HISTORY_QUERIES}"
    )
    assert long_count == LONG_HISTORY_QUERIES, (
        f"overview issued {long_count} queries for {long_years} fiscal years, "
        f"recorded {LONG_HISTORY_QUERIES}"
    )
    # Stated separately from the slope so a failure reads as what it is.
    assert short_count == long_count, (
        "a longer history cost more queries than a short one; the overview scales "
        "with history again"
    )


# Recorded by running the test. These are the CURRENT cost, deliberately not a
# target: the point is that changing them requires saying why.
#
# THESE ARE NOT THE LIVE NUMBERS AND ARE NOT MEANT TO BE. The fixture gives every
# run 3 signals; the real models carry 5-9, and a live issuer also has debt,
# maturity, market-price and reverse-DCF reads on top. The two scales are supposed
# to differ. What transfers between them is the SHAPE — and the shape is now flat.
#
# HISTORY OF THESE NUMBERS, kept because the trend is the story:
#   2026-08-12   36 / 100, slope 16   first recorded; the N+1 as found
#   2026-08-13   37 / 101, slope 16   +1 fixed cost, the reverse-DCF row lookup
#   2026-08-13    7 /   7, slope  0   Track P: both loads batched
#
# PER_YEAR_QUERIES IS NOW ZERO, and that is the whole point. It was 16 — sixteen
# round trips per fiscal year, forever, so OTEX's twenty years of history cost 486
# queries and a filer with forty would have cost nearly a thousand. Measured against
# the live store after batching: OTEX 486 -> 8, CP 345 -> 8, and the whole
# seven-filer universe 2,092 -> 54.
#
# If this ever goes above zero again, the overview has become an N+1 again. That is
# the failure this file now exists to catch; the totals below are secondary.
SHORT_HISTORY_QUERIES = 7
LONG_HISTORY_QUERIES = 7
PER_YEAR_QUERIES = 0
