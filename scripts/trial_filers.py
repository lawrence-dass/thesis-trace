"""Run the live pipeline for candidate filers that are NOT in the universe yet.

Ops 4 (famous-filer demo trial). Runs on whatever DATABASE_URL the env points at,
which for `make py` is the DEV store. Never point it at production: a candidate
only reaches production by being added to PHASE1_UNIVERSE and merged.

    make py F=scripts/trial_filers.py ARGS="AAPL:0000320193 MSFT:0000789019"
    make py F=scripts/trial_filers.py ARGS="--confirm-only AAPL:0000320193"

Each argument is TICKER:CIK, zero-padded to 10 digits. Every pair is first
checked against SEC's own ticker map (www.sec.gov/files/company_tickers.json);
any mismatch stops the run before a single company is fetched.

LIVE fetches, per ticker: data.sec.gov company facts, www.sec.gov filing
archives (Inline XBRL), and Tiingo end-of-day prices.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from ingestion.edgar import _throttle, _user_agent
from pipeline.run import main
from pipeline.universe import PHASE1_UNIVERSE, UniverseEntry

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


def _parse(arg: str) -> tuple[str, str]:
    ticker, _, cik = arg.partition(":")
    if not (ticker and len(cik) == 10 and cik.isdigit()):
        raise SystemExit(f"expected TICKER:0000000000, got {arg!r}")
    if any(e.ticker == ticker for e in PHASE1_UNIVERSE):
        raise SystemExit(f"{ticker} is already in the universe; use `make pipeline`")
    return ticker, cik


async def _confirm(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """Return ticker -> SEC's registered title; exit if any CIK disagrees."""
    await _throttle()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(TICKER_MAP_URL, headers={"User-Agent": _user_agent()})
        resp.raise_for_status()
    by_ticker = {row["ticker"]: row for row in resp.json().values()}
    titles, bad = {}, []
    for ticker, cik in pairs:
        row = by_ticker.get(ticker)
        live = str(row["cik_str"]).zfill(10) if row else None
        print(f"{'MATCH' if live == cik else 'MISMATCH'} {ticker}: given {cik}, SEC {live}"
              f" ({row['title'] if row else 'not listed'})")
        if live != cik:
            bad.append(ticker)
        else:
            titles[ticker] = row["title"]
    if bad:
        raise SystemExit(f"CIK not confirmed for {', '.join(bad)}; nothing fetched")
    return titles


async def run(args: list[str]) -> None:
    confirm_only = "--confirm-only" in args
    pairs = [_parse(a) for a in args if a != "--confirm-only"]
    if not pairs:
        raise SystemExit(__doc__)
    titles = await _confirm(pairs)
    if not confirm_only:
        await main([UniverseEntry(t, titles[t], c) for t, c in pairs])


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
