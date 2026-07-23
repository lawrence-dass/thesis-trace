"""Bank of Canada USD/CAD FX rate client + rate selection (AD-11 currency fix).

Free, no API key. Two series are needed because the Bank of Canada changed
methodology on 2017-05-01 (noon rate -> daily-average rate): FXUSDCAD for
recent dates, the frozen LEGACY_NOON_RATES group (series IEXE0101) for older
ones. Both confirmed live 2026-07-23. `select_rate_on_or_before` is pure and
picks the most recent published rate on or before a given date (FX markets
close weekends/holidays same as equities) — mirrors market_prices.select_fye_close.
"""

from __future__ import annotations

from datetime import date

import httpx

CURRENT_SERIES_URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json"
LEGACY_SERIES_URL = "https://www.bankofcanada.ca/valet/observations/group/LEGACY_NOON_RATES/json"
LEGACY_CUTOVER = date(2017, 1, 3)  # FXUSDCAD's earliest published observation


def select_rate_on_or_before(rates: list[dict], target: date) -> dict | None:
    """From rows ({'date': ISO, 'rate': float}), return the most recent one on or
    before `target`, or None if none qualify."""
    candidates = [r for r in rates if date.fromisoformat(r["date"]) <= target]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["date"])


async def fetch_usd_cad_rates(  # pragma: no cover — live path, gated
    start: date, end: date
) -> list[dict]:
    """Fetch daily USD/CAD rates over [start, end], branching across the
    2017-01-03 methodology cutover transparently — the caller never needs to
    know which series backed a given date."""
    rates: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        if start < LEGACY_CUTOVER:
            legacy_end = min(end, LEGACY_CUTOVER)
            resp = await client.get(
                LEGACY_SERIES_URL,
                params={"start_date": start.isoformat(), "end_date": legacy_end.isoformat()},
            )
            resp.raise_for_status()
            for obs in resp.json().get("observations", []):
                val = obs.get("IEXE0101", {}).get("v")
                if val is not None:
                    rates.append({"date": obs["d"], "rate": float(val)})

        if end >= LEGACY_CUTOVER:
            current_start = max(start, LEGACY_CUTOVER)
            resp = await client.get(
                CURRENT_SERIES_URL,
                params={"start_date": current_start.isoformat(), "end_date": end.isoformat()},
            )
            resp.raise_for_status()
            for obs in resp.json().get("observations", []):
                val = obs.get("FXUSDCAD", {}).get("v")
                if val is not None:
                    rates.append({"date": obs["d"], "rate": float(val)})

    return rates
