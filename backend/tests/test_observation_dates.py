"""Observation dates must be days the market was actually open.

Ingestion used to store Tiingo closes and Bank of Canada rates under the filer's
FISCAL-YEAR-END rather than the day the observation was made, so any filer whose
year ended on a weekend carried a quote dated to a shut market. Confirmed reachable
for BCE, Cameco, CP, OTEX, QSR and Suncor — 20 rows in the dev store.

The label was wrong, not the price, so nothing scored incorrectly. But the
reverse-DCF card publishes "observed on {date}" as provenance, and a Sunday there
is a citation that cannot be true.

Two halves, and the second matters more:
  1. The writers REFUSE a weekend date, so the defect cannot be reintroduced.
  2. The backfill re-dates the rows already stored, writing before deleting.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import FxRate, Issuer, MarketPrice
from pipeline.backfill_observation_dates import (
    plan_fx_rates,
    plan_market_prices,
    relabel_fx_rate,
    relabel_market_price,
    survey,
)
from raw_store.fx_rates import upsert_fx_rate
from raw_store.market_prices import get_fye_close, upsert_fye_close
from raw_store.observation_dates import (
    NonTradingObservationDate,
    assert_tradeable_observation_date,
    is_weekend,
    previous_trading_day,
)
from tests.conftest import requires_db

CIK = "0000000888"
TICKER = "OBSV"

# 2023-12-31 is a SUNDAY and is a real fiscal-year-end for CP, BCE and Cameco —
# this is the actual shape of the defect, not an invented one.
FYE_SUNDAY = date(2023, 12, 31)
TRUE_FRIDAY = date(2023, 12, 29)
CLOSE = 79.06  # CP's real stored close for that year


# --- the rule itself ----------------------------------------------------------


def test_weekend_detection_covers_both_days() -> None:
    assert is_weekend(date(2023, 12, 30))  # Saturday
    assert is_weekend(FYE_SUNDAY)
    assert not is_weekend(TRUE_FRIDAY)
    # 2016-12-31 (Sat) and 2022-12-31 (Sat) are the other real cases.
    assert is_weekend(date(2016, 12, 31))
    assert is_weekend(date(2022, 12, 31))


def test_previous_trading_day_walks_back_off_the_weekend() -> None:
    assert previous_trading_day(FYE_SUNDAY) == TRUE_FRIDAY
    assert previous_trading_day(date(2022, 12, 31)) == date(2022, 12, 30)
    # OTEX's June year end, the other real shape.
    assert previous_trading_day(date(2024, 6, 30)) == date(2024, 6, 28)


def test_a_weekday_is_returned_unchanged() -> None:
    assert previous_trading_day(TRUE_FRIDAY) == TRUE_FRIDAY


def test_the_assertion_names_the_day_and_the_reason() -> None:
    # An error that just says "invalid date" sends the reader to the wrong place.
    with pytest.raises(NonTradingObservationDate, match="Sunday"):
        assert_tradeable_observation_date(FYE_SUNDAY, what="market price for CP")
    assert_tradeable_observation_date(TRUE_FRIDAY, what="market price for CP")


# --- the writers refuse to reintroduce it -------------------------------------


@requires_db
async def test_upsert_fye_close_refuses_a_weekend_observation(db_session) -> None:
    """THE GUARD. Storing a quote under the fiscal-year-end is how every one of the
    20 bad rows was created; this makes that impossible rather than merely
    detectable after the fact."""
    db_session.add(Issuer(cik=CIK, ticker=TICKER, name="Observation Test Co"))
    await db_session.flush()

    with pytest.raises(NonTradingObservationDate):
        await upsert_fye_close(
            db_session, issuer_cik=CIK, price_date=FYE_SUNDAY, close_price=CLOSE
        )

    # And the legitimate call still works, so the guard is not simply refusing
    # everything — the failure mode that would make the test above meaningless.
    stored = await upsert_fye_close(
        db_session, issuer_cik=CIK, price_date=TRUE_FRIDAY, close_price=CLOSE
    )
    assert stored.price_date == TRUE_FRIDAY


@requires_db
async def test_upsert_fx_rate_refuses_a_weekend_observation(db_session) -> None:
    """The Bank of Canada publishes no rate on a weekend, so a weekend-dated FX row
    is always a mislabel — the same defect, one table over."""
    with pytest.raises(NonTradingObservationDate):
        await upsert_fx_rate(
            db_session, currency_pair="USDCAD", rate_date=FYE_SUNDAY, rate=1.3226
        )
    stored = await upsert_fx_rate(
        db_session, currency_pair="USDCAD", rate_date=TRUE_FRIDAY, rate=1.3226
    )
    assert stored.rate_date == TRUE_FRIDAY


# --- the backfill's planning half, pure ---------------------------------------


def test_planning_selects_only_the_weekend_rows() -> None:
    rows = [
        MarketPrice(issuer_cik=CIK, price_date=FYE_SUNDAY, close_price=Decimal("79.06")),
        MarketPrice(issuer_cik=CIK, price_date=TRUE_FRIDAY, close_price=Decimal("79.06")),
    ]
    plan = plan_market_prices(rows, {CIK: TICKER})
    assert [p.stored_date for p in plan] == [FYE_SUNDAY]
    assert plan[0].expected_date == TRUE_FRIDAY
    assert plan[0].key == TICKER


def test_planning_covers_fx_rows_too() -> None:
    rows = [
        FxRate(currency_pair="USDCAD", rate_date=FYE_SUNDAY, rate=Decimal("1.3226")),
        FxRate(currency_pair="USDCAD", rate_date=TRUE_FRIDAY, rate=Decimal("1.3226")),
    ]
    plan = plan_fx_rates(rows)
    assert [p.stored_date for p in plan] == [FYE_SUNDAY]
    assert plan[0].expected_date == TRUE_FRIDAY


# --- the backfill's rewriting half --------------------------------------------


async def _seed_mislabelled(db_session) -> None:
    """Insert the bad row the way ingestion once did — bypassing the writer, which
    now refuses it. That bypass is the point: this is legacy data, and a fixture
    that could not represent it would leave the backfill untested."""
    db_session.add(Issuer(cik=CIK, ticker=TICKER, name="Observation Test Co"))
    await db_session.flush()
    db_session.add(
        MarketPrice(
            issuer_cik=CIK, price_date=FYE_SUNDAY, close_price=Decimal(str(CLOSE)), source="tiingo"
        )
    )
    await db_session.flush()


@requires_db
async def test_relabelling_moves_the_row_to_its_real_trading_day(db_session) -> None:
    await _seed_mislabelled(db_session)

    outcome = await relabel_market_price(
        db_session,
        issuer_cik=CIK,
        stored_date=FYE_SUNDAY,
        observed_date=TRUE_FRIDAY,
        close_price=CLOSE,
    )
    await db_session.flush()

    assert outcome.startswith("OK")
    rows = (await db_session.execute(select(MarketPrice))).scalars().all()
    assert len(rows) == 1, "the mislabelled row was not removed"
    assert rows[0].price_date == TRUE_FRIDAY
    assert Decimal(str(rows[0].close_price)) == Decimal(str(CLOSE))


@requires_db
async def test_the_price_is_still_resolvable_for_the_fiscal_year_end(db_session) -> None:
    """THE POINT OF THE WHOLE EXERCISE, and the thing a careless fix would break.

    `get_fye_close` takes the latest row on or before the year end, within a
    7-day bound. Re-dating Sunday the 31st to Friday the 29th must keep the year
    end resolvable — otherwise the backfill would trade a wrong date for a missing
    market cap, and Altman and the reverse DCF would lose the year entirely.
    """
    await _seed_mislabelled(db_session)
    await relabel_market_price(
        db_session,
        issuer_cik=CIK,
        stored_date=FYE_SUNDAY,
        observed_date=TRUE_FRIDAY,
        close_price=CLOSE,
    )
    await db_session.flush()

    resolved = await get_fye_close(db_session, CIK, FYE_SUNDAY)
    assert resolved is not None, "the fiscal year end no longer resolves to a price"
    assert resolved.price_date == TRUE_FRIDAY


@requires_db
async def test_relabelling_writes_before_it_deletes(db_session) -> None:
    """Order matters, and the recorded diagnosis had it backwards.

    It assumed a correct row already sat beside each bad one, so deletion alone
    would do. The dev store has NO such partners — every weekend row is the only
    copy of that year's close. Deleting first would destroy it, and a failed fetch
    would leave the year with no price at all. Asserted by relabelling to a date
    that does not exist yet and requiring the value to survive.
    """
    await _seed_mislabelled(db_session)
    before = (await db_session.execute(select(MarketPrice))).scalars().all()
    assert [r.price_date for r in before] == [FYE_SUNDAY], "fixture should have no partner row"

    await relabel_market_price(
        db_session,
        issuer_cik=CIK,
        stored_date=FYE_SUNDAY,
        observed_date=TRUE_FRIDAY,
        close_price=CLOSE,
    )
    await db_session.flush()

    after = (await db_session.execute(select(MarketPrice))).scalars().all()
    assert len(after) == 1
    assert Decimal(str(after[0].close_price)) == Decimal(str(CLOSE))


@requires_db
async def test_relabelling_twice_is_idempotent(db_session) -> None:
    """The backfill may be re-run — after a partial failure, or simply by someone
    checking. A second pass must not duplicate the corrected row."""
    await _seed_mislabelled(db_session)
    for _ in range(2):
        await relabel_market_price(
            db_session,
            issuer_cik=CIK,
            stored_date=FYE_SUNDAY,
            observed_date=TRUE_FRIDAY,
            close_price=CLOSE,
        )
        await db_session.flush()

    rows = (await db_session.execute(select(MarketPrice))).scalars().all()
    assert len(rows) == 1
    assert rows[0].price_date == TRUE_FRIDAY


@requires_db
async def test_relabelling_refuses_a_provider_date_that_is_also_a_weekend(db_session) -> None:
    """If the provider somehow answers with a weekend date, the row is left alone
    rather than rewritten to another impossible day."""
    await _seed_mislabelled(db_session)
    outcome = await relabel_market_price(
        db_session,
        issuer_cik=CIK,
        stored_date=FYE_SUNDAY,
        observed_date=date(2023, 12, 30),  # Saturday
        close_price=CLOSE,
    )
    assert outcome.startswith("REFUSED")
    rows = (await db_session.execute(select(MarketPrice))).scalars().all()
    assert [r.price_date for r in rows] == [FYE_SUNDAY], "the bad row was touched anyway"


@requires_db
async def test_fx_relabelling_moves_the_row(db_session) -> None:
    db_session.add(
        FxRate(
            currency_pair="USDCAD",
            rate_date=FYE_SUNDAY,
            rate=Decimal("1.3226"),
            source="bank_of_canada",
        )
    )
    await db_session.flush()

    outcome = await relabel_fx_rate(
        db_session,
        currency_pair="USDCAD",
        stored_date=FYE_SUNDAY,
        observed_date=TRUE_FRIDAY,
        rate=1.3226,
    )
    await db_session.flush()

    assert outcome.startswith("OK")
    rows = (await db_session.execute(select(FxRate))).scalars().all()
    assert len(rows) == 1
    assert rows[0].rate_date == TRUE_FRIDAY


@requires_db
async def test_survey_reports_clean_once_the_rows_are_fixed(db_session) -> None:
    """The completion check the operator actually reads."""
    await _seed_mislabelled(db_session)
    assert len(await survey(db_session)) == 1

    await relabel_market_price(
        db_session,
        issuer_cik=CIK,
        stored_date=FYE_SUNDAY,
        observed_date=TRUE_FRIDAY,
        close_price=CLOSE,
    )
    await db_session.flush()
    assert await survey(db_session) == []
