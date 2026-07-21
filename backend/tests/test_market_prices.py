"""Story 2.1 — Tiingo FYE-close selection + market_prices persistence (AD-11, AD-14)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ingestion.tiingo import select_fye_close
from raw_store.market_prices import get_fye_close, upsert_fye_close
from tests.conftest import requires_db

PRICES = json.loads((Path(__file__).parent / "fixtures" / "shop_tiingo_prices.json").read_text())


def test_select_fye_close_picks_last_trading_day_on_or_before_fye() -> None:
    # FYE 2024-12-31 is a trading day in the fixture -> that close.
    row = select_fye_close(PRICES, date(2024, 12, 31))
    assert row["close"] == 106.20

    # FYE on a weekend (2023-12-31 Sun) -> last trading day before it (2023-12-29).
    row = select_fye_close(PRICES, date(2023, 12, 31))
    assert row["close"] == 77.86


def test_select_fye_close_none_when_no_prior_trading_day() -> None:
    assert select_fye_close(PRICES, date(2020, 1, 1)) is None


@requires_db
async def test_market_price_persist_is_idempotent(db_session) -> None:
    from app.models import Issuer

    db_session.add(Issuer(cik="0001594805", ticker="SHOP", name="Shopify Inc."))
    await db_session.flush()

    p1 = await upsert_fye_close(
        db_session, issuer_cik="0001594805", price_date=date(2024, 12, 31), close_price=106.20
    )
    p2 = await upsert_fye_close(
        db_session, issuer_cik="0001594805", price_date=date(2024, 12, 31), close_price=106.20
    )
    assert p1.id == p2.id  # idempotent, no duplicate

    fetched = await get_fye_close(db_session, "0001594805", date(2024, 12, 31))
    assert fetched is not None and float(fetched.close_price) == 106.20
