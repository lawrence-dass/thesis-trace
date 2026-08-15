"""Persist and read USD/CAD FX rates (AD-11 currency fix). Idempotent by
(currency_pair, rate_date, source). Never a live fetch during a read (AD-1)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FxRate
from raw_store.observation_dates import assert_tradeable_observation_date


async def upsert_fx_rate(
    session: AsyncSession,
    *,
    currency_pair: str,
    rate_date: date,
    rate: float,
    source: str = "bank_of_canada",
) -> FxRate:
    # Same rule as `upsert_fye_close`: the date is when the rate was PUBLISHED, not
    # the fiscal-year-end it will be applied to. The Bank of Canada publishes no
    # rate on a weekend, so a weekend-dated row is always a mislabel.
    assert_tradeable_observation_date(rate_date, what=f"{currency_pair} rate")
    existing = (
        await session.execute(
            select(FxRate).where(
                FxRate.currency_pair == currency_pair,
                FxRate.rate_date == rate_date,
                FxRate.source == source,
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing
    row = FxRate(currency_pair=currency_pair, rate_date=rate_date, rate=rate, source=source)
    session.add(row)
    await session.flush()
    return row


async def get_fx_rate_on_or_before(
    session: AsyncSession, currency_pair: str, target_date: date, *, source: str = "bank_of_canada"
) -> FxRate | None:
    """Most recent persisted rate on or before `target_date` — never a live fetch."""
    return (
        await session.execute(
            select(FxRate)
            .where(
                FxRate.currency_pair == currency_pair,
                FxRate.rate_date <= target_date,
                FxRate.source == source,
            )
            .order_by(FxRate.rate_date.desc())
            .limit(1)
        )
    ).scalars().first()
