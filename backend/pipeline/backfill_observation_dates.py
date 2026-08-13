"""One-time backfill: re-date market prices and FX rates that were stored under a
fiscal-year-end instead of the day they were observed.

Ingestion was fixed on 2026-08-11 to carry the provider's own date, but THE FIX IS
INERT UNTIL THIS RUNS. `uq_market_prices_key` is (issuer_cik, price_date, source),
so a corrected row is a NEW row rather than an update — and `get_fye_close` takes
the latest row on or before the fiscal-year-end, which is the mislabelled weekend
row. Correct dates get written and never read.

WHAT THE DEV STORE ACTUALLY CONTAINS, checked 2026-08-13 before writing this:
20 weekend-dated market_prices rows and 4 weekend-dated fx_rates rows — and NOT ONE
of them has a correctly-dated partner. The recorded diagnosis assumed both rows
existed side by side; they do not, because the corrected ingestion has never been
re-run. That changes the safe order of operations completely:

    WRITE THE CORRECT ROW FIRST, THEN DELETE THE MISLABELLED ONE.

Deleting first — the order the original note implies — would destroy the only copy
of that year's close, and if the subsequent fetch failed or the API key were
missing, Altman and the reverse DCF would silently lose their market inputs for
those years. In this order the data is never absent, and a failed fetch simply
leaves the row untouched for the next attempt.

THE CLOSE IS VERIFIED, NOT ASSUMED. The stored figure should already be the correct
trading day's close (`select_fye_close` picked it); only the label was wrong. This
re-fetches and compares rather than trusting that, because a silent mismatch would
mean the price itself was wrong too — a much worse defect than a bad date, and one
nothing else would catch.

Run:  uv run python -m pipeline.backfill_observation_dates          # dry run
      uv run python -m pipeline.backfill_observation_dates --apply
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FxRate, Issuer, MarketPrice
from raw_store.observation_dates import is_weekend, previous_trading_day

#: How far before a mislabelled date the true observation can sit. A weekend end
#: is one or two days after the Friday close; the extra room covers a long weekend
#: without ever reaching into a prior fiscal year.
MAX_LOOKBACK = timedelta(days=7)


@dataclass(frozen=True)
class Mislabelled:
    """One row whose stored date is not a day the market was open."""

    kind: str  # "market_price" | "fx_rate"
    key: str  # ticker, or currency pair
    stored_date: date
    stored_value: Decimal
    #: Where the observation most likely belongs. A HYPOTHESIS used to bound the
    #: provider query — never written without the provider confirming it.
    expected_date: date


def plan_market_prices(rows: list[MarketPrice], tickers: dict[str, str]) -> list[Mislabelled]:
    """Which market-price rows are mislabelled. Pure — no session, no network."""
    return [
        Mislabelled(
            kind="market_price",
            key=tickers.get(row.issuer_cik, row.issuer_cik),
            stored_date=row.price_date,
            stored_value=row.close_price,
            expected_date=previous_trading_day(row.price_date),
        )
        for row in rows
        if is_weekend(row.price_date)
    ]


def plan_fx_rates(rows: list[FxRate]) -> list[Mislabelled]:
    """Which FX rows are mislabelled. Pure — no session, no network."""
    return [
        Mislabelled(
            kind="fx_rate",
            key=row.currency_pair,
            stored_date=row.rate_date,
            stored_value=row.rate,
            expected_date=previous_trading_day(row.rate_date),
        )
        for row in rows
        if is_weekend(row.rate_date)
    ]


async def survey(session: AsyncSession) -> list[Mislabelled]:
    """Everything currently stored under a non-trading date."""
    issuers = (await session.execute(select(Issuer))).scalars().all()
    tickers = {issuer.cik: issuer.ticker for issuer in issuers}
    prices = list((await session.execute(select(MarketPrice))).scalars().all())
    rates = list((await session.execute(select(FxRate))).scalars().all())
    return plan_market_prices(prices, tickers) + plan_fx_rates(rates)


async def relabel_market_price(
    session: AsyncSession,
    *,
    issuer_cik: str,
    stored_date: date,
    observed_date: date,
    close_price: float,
    source: str = "tiingo",
) -> str:
    """Write the correctly-dated row, then drop the mislabelled one.

    Returns a one-line outcome. Idempotent: a second run finds no weekend row and
    does nothing, and re-writing an already-correct row hits the existing-row path.
    """
    if is_weekend(observed_date):
        return f"REFUSED {issuer_cik} {stored_date}: provider date {observed_date} is also a weekend"

    existing_correct = (
        await session.execute(
            select(MarketPrice).where(
                MarketPrice.issuer_cik == issuer_cik,
                MarketPrice.price_date == observed_date,
                MarketPrice.source == source,
            )
        )
    ).scalars().first()

    if existing_correct is None:
        session.add(
            MarketPrice(
                issuer_cik=issuer_cik,
                price_date=observed_date,
                close_price=close_price,
                source=source,
            )
        )
        await session.flush()

    stale = (
        await session.execute(
            select(MarketPrice).where(
                MarketPrice.issuer_cik == issuer_cik,
                MarketPrice.price_date == stored_date,
                MarketPrice.source == source,
            )
        )
    ).scalars().first()
    if stale is not None:
        await session.delete(stale)
    return f"OK {issuer_cik} {stored_date} -> {observed_date} close={close_price}"


async def relabel_fx_rate(
    session: AsyncSession,
    *,
    currency_pair: str,
    stored_date: date,
    observed_date: date,
    rate: float,
    source: str = "bank_of_canada",
) -> str:
    """The FX analogue of `relabel_market_price`, same write-then-delete order."""
    if is_weekend(observed_date):
        return f"REFUSED {currency_pair} {stored_date}: provider date {observed_date} is also a weekend"

    existing_correct = (
        await session.execute(
            select(FxRate).where(
                FxRate.currency_pair == currency_pair,
                FxRate.rate_date == observed_date,
                FxRate.source == source,
            )
        )
    ).scalars().first()
    if existing_correct is None:
        session.add(
            FxRate(currency_pair=currency_pair, rate_date=observed_date, rate=rate, source=source)
        )
        await session.flush()

    stale = (
        await session.execute(
            select(FxRate).where(
                FxRate.currency_pair == currency_pair,
                FxRate.rate_date == stored_date,
                FxRate.source == source,
            )
        )
    ).scalars().first()
    if stale is not None:
        await session.delete(stale)
    return f"OK {currency_pair} {stored_date} -> {observed_date} rate={rate}"


async def main() -> None:  # pragma: no cover — live path, gated
    """Survey, and with --apply re-date every mislabelled row against the provider.

    Performs LIVE fetches (Tiingo, Bank of Canada). Gated behind the standing
    ask-before-live-fetch rule.
    """
    import sys

    from app.db import get_sessionmaker
    from ingestion.fx import fetch_usd_cad_rates, select_rate_on_or_before
    from ingestion.tiingo import fetch_eod_prices, select_fye_close

    apply = "--apply" in sys.argv
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("DATABASE_URL is not configured.")

    async with sessionmaker() as session:
        findings = await survey(session)
        if not findings:
            print("Nothing stored under a non-trading date. Nothing to do.")
            return

        print(f"{len(findings)} row(s) stored under a non-trading date:\n")
        for item in findings:
            print(
                f"  {item.kind:13s} {item.key:8s} {item.stored_date} "
                f"({item.stored_date.strftime('%a')}) value={item.stored_value} "
                f"-> expected {item.expected_date} ({item.expected_date.strftime('%a')})"
            )
        if not apply:
            print("\nDRY RUN. Re-run with --apply to fetch the real dates and rewrite.")
            return

        issuers = {i.ticker: i for i in (await session.execute(select(Issuer))).scalars().all()}
        mismatches: list[str] = []

        for item in (f for f in findings if f.kind == "market_price"):
            issuer = issuers.get(item.key)
            if issuer is None:
                print(f"SKIP {item.key}: no issuer row")
                continue
            prices = await fetch_eod_prices(
                issuer.ticker, item.stored_date - MAX_LOOKBACK, item.stored_date
            )
            row = select_fye_close(prices, item.stored_date)
            if row is None:
                print(f"SKIP {item.key} {item.stored_date}: provider returned no close in window")
                continue
            observed = date.fromisoformat(row["date"][:10])
            # The price itself must not change. If it does, the stored figure was
            # wrong too, which is a bigger finding than the date and must not be
            # silently overwritten.
            if Decimal(str(row["close"])) != Decimal(str(item.stored_value)):
                mismatches.append(
                    f"  {item.key} {item.stored_date}: stored {item.stored_value}, "
                    f"provider {row['close']} on {observed}"
                )
                continue
            print(await relabel_market_price(
                session,
                issuer_cik=issuer.cik,
                stored_date=item.stored_date,
                observed_date=observed,
                close_price=row["close"],
            ))

        for item in (f for f in findings if f.kind == "fx_rate"):
            rates = await fetch_usd_cad_rates(item.stored_date - MAX_LOOKBACK, item.stored_date)
            row = select_rate_on_or_before(rates, item.stored_date)
            if row is None:
                print(f"SKIP {item.key} {item.stored_date}: provider returned no rate in window")
                continue
            observed = date.fromisoformat(row["date"])
            if Decimal(str(row["rate"])) != Decimal(str(item.stored_value)):
                mismatches.append(
                    f"  {item.key} {item.stored_date}: stored {item.stored_value}, "
                    f"provider {row['rate']} on {observed}"
                )
                continue
            print(await relabel_fx_rate(
                session,
                currency_pair=item.key,
                stored_date=item.stored_date,
                observed_date=observed,
                rate=row["rate"],
            ))

        if mismatches:
            # Deliberately NOT applied. A changed value means the original figure
            # was wrong, not just its label, and that deserves a decision.
            print("\nVALUE MISMATCHES — left untouched, these need a look:")
            for line in mismatches:
                print(line)

        await session.commit()
        remaining = await survey(session)
        print(f"\nDone. Rows still on a non-trading date: {len(remaining)}")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
