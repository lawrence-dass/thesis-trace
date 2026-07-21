"""Tiingo end-of-day price client + FYE-close selection (AD-11, AD-14, D7).

Tiingo (free tier) is the ONLY additional data provider in Phase 1, used solely
for Altman's period-end closing price. The live fetch requires TIINGO_API_KEY and
is NOT exercised by tests (fixtures only). `select_fye_close` is pure and picks the
close on the last trading day on or before fiscal-year-end (AD-14).
"""

from __future__ import annotations

from datetime import date

import httpx

from app.config import get_settings

EOD_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"


def select_fye_close(prices: list[dict], fiscal_year_end: date) -> dict | None:
    """From EOD rows ({'date': ISO, 'close': float, ...}), return the row for the
    last trading day on or before fiscal_year_end, or None if none qualify."""
    candidates = []
    for row in prices:
        d = date.fromisoformat(row["date"][:10])
        if d <= fiscal_year_end:
            candidates.append((d, row))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


async def fetch_eod_prices(  # pragma: no cover — live path, gated
    ticker: str, start: date, end: date
) -> list[dict]:
    api_key = get_settings().tiingo_api_key
    if not api_key:
        raise RuntimeError("TIINGO_API_KEY env var is required for market-price ingestion (D7/AD-11).")
    params = {"startDate": start.isoformat(), "endDate": end.isoformat(), "token": api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(EOD_URL.format(ticker=ticker), params=params, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()
