"""Persist and read period-end market prices (AD-14). Idempotent by
(issuer_cik, price_date, source)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FxRate, MarketPrice
from raw_store.fx_rates import get_fx_rate_on_or_before
from raw_store.observation_dates import assert_tradeable_observation_date


@dataclass(frozen=True)
class FyePriceResolution:
    """A persisted FYE price after conversion to the filer's reporting currency.

    ``price`` is the value safe to combine with balance-sheet figures.  It is
    ``None`` when the close or a required FX rate is unavailable; ``reason`` is
    kept so callers can preserve an actionable AD-16 explanation instead of
    reducing every failure to a generic missing market cap.
    """

    price: Decimal | None
    market_price: MarketPrice | None
    fx_rate: FxRate | None
    reporting_currency: str
    reason: str | None = None
    price_date: date | None = None
    price_source: str | None = None
    fx_rate_value: Decimal | None = None
    fx_rate_date: date | None = None
    fx_rate_source: str | None = None


# AD-14 means the last trading day immediately before a fiscal year end, not an
# arbitrary quote from a prior fiscal year. Weekends and statutory holidays fit
# comfortably inside this bound; an older row is treated as missing data.
MAX_FYE_INPUT_AGE = timedelta(days=7)


async def upsert_fye_close(
    session: AsyncSession,
    *,
    issuer_cik: str,
    price_date: date,
    close_price: float,
    source: str = "tiingo",
) -> MarketPrice:
    # `price_date` is WHEN THE QUOTE WAS OBSERVED, not the fiscal-year-end it is
    # being used for. Storing the year end here is the defect this guard closes:
    # the unique key is (issuer_cik, price_date, source), so a fiscal-year-end row
    # both mislabels the observation and outranks the true trading day in
    # `get_fye_close`, which takes the latest row on or before the year end.
    assert_tradeable_observation_date(price_date, what=f"market price for {issuer_cik}")
    existing = (
        await session.execute(
            select(MarketPrice).where(
                MarketPrice.issuer_cik == issuer_cik,
                MarketPrice.price_date == price_date,
                MarketPrice.source == source,
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing
    price = MarketPrice(
        issuer_cik=issuer_cik, price_date=price_date, close_price=close_price, source=source
    )
    session.add(price)
    await session.flush()
    return price


async def get_fye_close(
    session: AsyncSession, issuer_cik: str, fiscal_year_end: date, *, source: str = "tiingo"
) -> MarketPrice | None:
    """Latest persisted close on or before FYE (AD-14) — never a live fetch (AD-1)."""
    return (
        await session.execute(
            select(MarketPrice)
            .where(MarketPrice.issuer_cik == issuer_cik, MarketPrice.price_date <= fiscal_year_end)
            .where(MarketPrice.source == source)
            .order_by(MarketPrice.price_date.desc())
            .limit(1)
        )
    ).scalars().first()


async def resolve_fye_price(
    session: AsyncSession,
    *,
    issuer_cik: str,
    fiscal_year_end: date,
    reporting_currency: str | None,
) -> FyePriceResolution:
    """Resolve the persisted FYE close in the filer's reporting currency.

    Tiingo prices are USD.  Non-USD filers therefore need the persisted Bank of
    Canada rate before the price can be combined with their statement values.
    This is the single implementation of that rule; Altman and reverse DCF must
    not grow separate copies that can disagree about a missing rate or date.
    """

    currency = (reporting_currency or "").strip().upper()
    if not currency:
        return FyePriceResolution(
            price=None,
            market_price=None,
            fx_rate=None,
            reporting_currency="",
            reason="reporting currency is unavailable",
        )
    close = await get_fye_close(session, issuer_cik, fiscal_year_end)
    fx = None
    if close is not None and currency != "USD":
        fx = await get_fx_rate_on_or_before(session, f"USD{currency}", fiscal_year_end)
    return _resolve_fye_rows(
        close=close,
        fx=fx,
        fiscal_year_end=fiscal_year_end,
        reporting_currency=currency,
    )


def _resolve_fye_rows(
    *,
    close: MarketPrice | None,
    fx: FxRate | None,
    fiscal_year_end: date,
    reporting_currency: str,
) -> FyePriceResolution:
    """Apply the FYE, sign, age, and currency rules to already-loaded rows."""

    currency = reporting_currency
    if not reporting_currency:
        return FyePriceResolution(
            price=None,
            market_price=None,
            fx_rate=None,
            reporting_currency="",
            reason="reporting currency is unavailable",
        )
    if close is None:
        return FyePriceResolution(
            price=None,
            market_price=None,
            fx_rate=None,
            reporting_currency=currency,
            reason="no fiscal-year-end market price",
        )
    if fiscal_year_end - close.price_date > MAX_FYE_INPUT_AGE:
        return FyePriceResolution(
            price=None,
            market_price=close,
            fx_rate=None,
            reporting_currency=currency,
            reason="no recent fiscal-year-end market price",
            price_date=close.price_date,
            price_source=close.source,
        )

    price = Decimal(str(close.close_price))
    if not price.is_finite() or price <= 0:
        return FyePriceResolution(
            price=None,
            market_price=close,
            fx_rate=None,
            reporting_currency=currency,
            reason="market price is zero or negative",
            price_date=close.price_date,
            price_source=close.source,
        )
    if currency == "USD":
        return FyePriceResolution(
            price=price,
            market_price=close,
            fx_rate=None,
            reporting_currency=currency,
            price_date=close.price_date,
            price_source=close.source,
        )

    if fx is None:
        return FyePriceResolution(
            price=None,
            market_price=close,
            fx_rate=None,
            reporting_currency=currency,
            reason=f"no USD/{currency} FX rate on or before fiscal year end",
            price_date=close.price_date,
            price_source=close.source,
        )
    fx_value = Decimal(str(fx.rate))
    if not fx_value.is_finite() or fx_value <= 0:
        return FyePriceResolution(
            price=None,
            market_price=close,
            fx_rate=fx,
            reporting_currency=currency,
            reason=f"USD/{currency} FX rate is zero or negative",
            price_date=close.price_date,
            price_source=close.source,
            fx_rate_value=fx_value,
            fx_rate_date=fx.rate_date,
            fx_rate_source=fx.source,
        )
    if fiscal_year_end - fx.rate_date > MAX_FYE_INPUT_AGE:
        return FyePriceResolution(
            price=None,
            market_price=close,
            fx_rate=fx,
            reporting_currency=currency,
            reason=f"no recent USD/{currency} FX rate for fiscal year end",
            price_date=close.price_date,
            price_source=close.source,
            fx_rate_value=fx_value,
            fx_rate_date=fx.rate_date,
            fx_rate_source=fx.source,
        )
    return FyePriceResolution(
        price=price * fx_value,
        market_price=close,
        fx_rate=fx,
        reporting_currency=currency,
        price_date=close.price_date,
        price_source=close.source,
        fx_rate_value=fx_value,
        fx_rate_date=fx.rate_date,
        fx_rate_source=fx.source,
    )


async def resolve_fye_prices(
    session: AsyncSession,
    *,
    issuer_cik: str,
    fiscal_year_ends: dict[int, date],
    reporting_currencies: dict[int, str | None],
) -> dict[int, FyePriceResolution]:
    """Resolve multiple candidate years with one market query and one FX query.

    Reverse DCF selects the newest *fully resolvable* year.  Resolving candidates
    one at a time would turn a long filing history into an N+1 read, so this loads
    the bounded date window once and applies the same per-year rules in Python.
    """

    if not fiscal_year_ends:
        return {}
    targets = list(fiscal_year_ends.values())
    earliest = min(targets) - MAX_FYE_INPUT_AGE
    latest = max(targets)
    market_rows = (
        await session.execute(
            select(MarketPrice)
            .where(
                MarketPrice.issuer_cik == issuer_cik,
                MarketPrice.source == "tiingo",
                MarketPrice.price_date >= earliest,
                MarketPrice.price_date <= latest,
            )
            .order_by(MarketPrice.price_date.desc())
        )
    ).scalars().all()

    normalized = {
        year: (currency or "").strip().upper()
        for year, currency in reporting_currencies.items()
    }
    pairs = {f"USD{currency}" for currency in normalized.values() if currency and currency != "USD"}
    fx_rows = []
    if pairs:
        fx_rows = (
            await session.execute(
                select(FxRate)
                .where(
                    FxRate.currency_pair.in_(pairs),
                    FxRate.source == "bank_of_canada",
                    FxRate.rate_date >= earliest,
                    FxRate.rate_date <= latest,
                )
                .order_by(FxRate.rate_date.desc())
            )
        ).scalars().all()

    results: dict[int, FyePriceResolution] = {}
    for year, fiscal_year_end in fiscal_year_ends.items():
        currency = normalized.get(year, "")
        close = next(
            (row for row in market_rows if row.price_date <= fiscal_year_end),
            None,
        )
        fx = None
        if currency and currency != "USD":
            pair = f"USD{currency}"
            fx = next(
                (row for row in fx_rows if row.currency_pair == pair and row.rate_date <= fiscal_year_end),
                None,
            )
        results[year] = _resolve_fye_rows(
            close=close,
            fx=fx,
            fiscal_year_end=fiscal_year_end,
            reporting_currency=currency,
        )
    return results
