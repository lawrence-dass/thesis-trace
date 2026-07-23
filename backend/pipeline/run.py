"""Batch pipeline orchestrator (AD-1): ingest -> canonicalize -> validate -> score.

Runs entirely on the write path (Render Cron Job, AD-13); the daily run also
keeps the Supabase free-tier DB from auto-pausing. `run_issuer` is pure w.r.t.
data source (takes an already-fetched payload), so it is fully testable against
fixtures. `main` performs the live universe run and is gated behind the standing
"ask before live fetch" decision — not exercised by the test suite.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.models import Filing
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import MAPPING_VERSION, seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.fx_rates import upsert_fx_rate
from raw_store.market_prices import get_fye_close, upsert_fye_close
from raw_store.repository import persist_company_facts
from scoring.facts import load_facts
from scoring.runner import score_altman, score_beneish, score_piotroski, score_sloan


def _primary_filing_per_year(filings) -> dict:
    """One filing per fiscal year, preferring the original 10-K over any
    10-K/A — a narrow amendment often doesn't restate the full financial
    statements, so its own fiscal_year_end can be less reliable than the
    original filing's (confirmed live 2026-07-23: CP's 10-K/A rows are
    consistently dated to the amendment's own filing date). Mirrors AD-3's
    existing as-originally-filed-over-restated-comparative principle. Works
    for either ParsedFiling (dataclass) or Filing (DB model) rows — both
    expose .fiscal_year/.form_type."""
    values = filings.values() if isinstance(filings, dict) else filings
    by_year: dict = {}
    for f in values:
        existing = by_year.get(f.fiscal_year)
        if existing is None or (existing.form_type == "10-K/A" and f.form_type == "10-K"):
            by_year[f.fiscal_year] = f
    return by_year


async def scoreable_years(session: AsyncSession, issuer_cik: str) -> list[int]:
    """Fiscal years that have a prior year present (needed for year-over-year signals)."""
    facts = await load_facts(session, issuer_cik, mapping_version=MAPPING_VERSION)
    years = facts.fiscal_years()
    return sorted(y for y in years if (y - 1) in years)


async def run_issuer(
    session: AsyncSession,
    payload: dict,
    *,
    ticker: str,
    sector: str | None = None,
    is_financial_sector: bool = False,
    is_capital_intensive: bool = False,
    fye_prices: dict[int, float] | None = None,
    fx_rates: dict[int, float] | None = None,
    reporting_currency: str | None = None,
) -> dict:
    """Full write-path pipeline for one issuer from a Company Facts payload.

    `fye_prices` maps fiscal_year -> period-end close (from Tiingo); when present
    for a year, Altman is also scored for that year (AD-11/AD-14). `fx_rates`
    (fiscal_year -> USD/`reporting_currency` rate) is only needed for filers that
    report in a non-USD currency (e.g. CP reports in CAD) — see AD-11's currency
    fix (2026-07-23): Tiingo's price is always USD, so a non-USD filer's Altman
    X4 needs this conversion or it would silently divide mismatched currencies.
    """
    parsed = parse_company_facts(payload)
    await persist_company_facts(
        session,
        parsed,
        ticker=ticker,
        sector=sector,
        is_financial_sector=is_financial_sector,
        is_capital_intensive=is_capital_intensive,
    )
    await seed_concept_mappings(session)
    await canonicalize_issuer(session, parsed.cik)

    # Persist any provided FYE market prices at the filing's fiscal-year-end.
    fye_prices = fye_prices or {}
    all_filings = (await session.execute(select(Filing).where(Filing.issuer_cik == parsed.cik))).scalars().all()
    filings = _primary_filing_per_year(all_filings)
    for fy, close in fye_prices.items():
        if fy in filings:
            await upsert_fye_close(
                session, issuer_cik=parsed.cik, price_date=filings[fy].fiscal_year_end, close_price=close
            )

    if reporting_currency and reporting_currency != "USD":
        for fy, rate in (fx_rates or {}).items():
            if fy in filings:
                await upsert_fx_rate(
                    session,
                    currency_pair=f"USD{reporting_currency}",
                    rate_date=filings[fy].fiscal_year_end,
                    rate=rate,
                )

    years = await scoreable_years(session, parsed.cik)
    scored = {"piotroski": [], "sloan": [], "beneish": [], "altman": []}
    for year in years:
        await score_piotroski(session, parsed.cik, year)
        scored["piotroski"].append(year)
        await score_sloan(session, parsed.cik, year)
        scored["sloan"].append(year)
        await score_beneish(session, parsed.cik, year)
        scored["beneish"].append(year)
        filing = filings.get(year)
        if filing is not None and await get_fye_close(session, parsed.cik, filing.fiscal_year_end):
            await score_altman(session, parsed.cik, year)
            scored["altman"].append(year)
    await session.commit()
    return {"cik": parsed.cik, "ticker": ticker, "scored_years": years, "scored": scored}


async def _fye_prices_for(payload: dict, ticker: str) -> dict[int, float]:
    """Fetch Tiingo EOD prices covering every filed fiscal-year-end and resolve
    the FYE close per year (AD-11, AD-14). Returns {} — never raises — when
    TIINGO_API_KEY is unset, so Altman degrades to insufficient_data rather
    than blocking Piotroski/Beneish/Sloan for the whole company."""
    from datetime import timedelta

    from app.config import get_settings
    from ingestion.tiingo import fetch_eod_prices, select_fye_close

    if not get_settings().tiingo_api_key:
        print(f"  (no TIINGO_API_KEY — {ticker} Altman will show insufficient_data)")
        return {}

    parsed = parse_company_facts(payload)
    primary = _primary_filing_per_year(parsed.filings)
    fye_dates = sorted({f.fiscal_year_end for f in primary.values()})
    if not fye_dates:
        return {}
    from datetime import date as _date

    start = _date.fromisoformat(fye_dates[0]) - timedelta(days=10)
    end = _date.fromisoformat(fye_dates[-1])
    prices = await fetch_eod_prices(ticker, start, end)

    fye_prices: dict[int, float] = {}
    for fy, f in primary.items():
        fye = _date.fromisoformat(f.fiscal_year_end)
        row = select_fye_close(prices, fye)
        if row is not None:
            fye_prices[fy] = row["close"]
    return fye_prices


def _payload_reporting_currency(payload: dict) -> str | None:
    """The currency unit the issuer's own us-gaap:Assets fact is reported in
    (e.g. 'USD', 'CAD') — confirmed live 2026-07-23 that this varies (CP reports
    entirely in CAD). None if Assets isn't present at all."""
    units = payload.get("facts", {}).get("us-gaap", {}).get("Assets", {}).get("units", {})
    for unit in units:
        return unit
    return None


async def _fx_rates_for(payload: dict, reporting_currency: str | None) -> dict[int, float]:
    """Fetch USD/{reporting_currency} rates covering every filed fiscal-year-end
    (AD-11 currency fix). Only Bank of Canada USD/CAD is supported; any other
    non-USD currency returns {} and Altman degrades to insufficient_data for
    that filer rather than silently mixing currencies."""
    if not reporting_currency or reporting_currency == "USD":
        return {}
    if reporting_currency != "CAD":
        print(f"  (no FX source for USD/{reporting_currency} — Altman X4 will show insufficient_data)")
        return {}

    from datetime import date as _date
    from datetime import timedelta

    from ingestion.fx import fetch_usd_cad_rates, select_rate_on_or_before

    parsed = parse_company_facts(payload)
    primary = _primary_filing_per_year(parsed.filings)
    fye_dates = sorted({f.fiscal_year_end for f in primary.values()})
    if not fye_dates:
        return {}

    start = _date.fromisoformat(fye_dates[0]) - timedelta(days=10)
    end = _date.fromisoformat(fye_dates[-1])
    rates = await fetch_usd_cad_rates(start, end)

    fx_rates: dict[int, float] = {}
    for fy, f in primary.items():
        fye = _date.fromisoformat(f.fiscal_year_end)
        row = select_rate_on_or_before(rates, fye)
        if row is not None:
            fx_rates[fy] = row["rate"]
    return fx_rates


async def main() -> None:  # pragma: no cover — live path, gated
    """Live universe run for the Render Cron Job. Requires network + EDGAR_CONTACT.

    Gated: performs live SEC EDGAR fetches. Only entries with a confirmed CIK run;
    others are reported as skipped so coverage gaps are explicit. Tiingo (AD-11)
    is fetched per company and passed through so Altman is scored wherever a
    market price resolves; if TIINGO_API_KEY is unset, everything else still
    scores and Altman degrades to insufficient_data rather than failing the run.
    """
    from app.db import get_sessionmaker
    from ingestion.edgar import fetch_company_facts
    from pipeline.universe import PHASE1_UNIVERSE

    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("DATABASE_URL is not configured.")

    for entry in PHASE1_UNIVERSE:
        if entry.cik is None:
            print(f"SKIP {entry.ticker}: CIK not yet confirmed against EDGAR")
            continue
        payload = await fetch_company_facts(entry.cik)
        fye_prices = await _fye_prices_for(payload, entry.ticker)
        reporting_currency = _payload_reporting_currency(payload)
        fx_rates = await _fx_rates_for(payload, reporting_currency)
        async with sessionmaker() as session:
            summary = await run_issuer(
                session,
                payload,
                ticker=entry.ticker,
                is_financial_sector=entry.is_financial_sector,
                is_capital_intensive=entry.capital_intensive,
                fye_prices=fye_prices,
                fx_rates=fx_rates,
                reporting_currency=reporting_currency,
            )
        print(f"OK {entry.ticker}: scored {summary['scored_years']} (altman: {summary['scored']['altman']})")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
