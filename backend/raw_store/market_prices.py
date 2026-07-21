"""Persist and read period-end market prices (AD-14). Idempotent by
(issuer_cik, price_date, source)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketPrice


async def upsert_fye_close(
    session: AsyncSession,
    *,
    issuer_cik: str,
    price_date: date,
    close_price: float,
    source: str = "tiingo",
) -> MarketPrice:
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
    session: AsyncSession, issuer_cik: str, fiscal_year_end: date
) -> MarketPrice | None:
    """Latest persisted close on or before FYE (AD-14) — never a live fetch (AD-1)."""
    return (
        await session.execute(
            select(MarketPrice)
            .where(MarketPrice.issuer_cik == issuer_cik, MarketPrice.price_date <= fiscal_year_end)
            .order_by(MarketPrice.price_date.desc())
            .limit(1)
        )
    ).scalars().first()
