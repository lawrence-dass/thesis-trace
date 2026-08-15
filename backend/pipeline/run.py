"""Batch pipeline orchestrator (AD-1): ingest -> canonicalize -> validate -> score.

Runs entirely on the write path (Render Cron Job, AD-13); the daily run also
keeps the Supabase free-tier DB from auto-pausing. `run_issuer` is pure w.r.t.
data source (takes an already-fetched payload), so it is fully testable against
fixtures. `main` performs the live universe run and is gated behind the standing
"ask before live fetch" decision — not exercised by the test suite.
"""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.models import Filing
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import MAPPING_VERSION, seed_concept_mappings
from canonicalization.taxonomies import FINANCIAL_TAXONOMIES, supersedes
from ingestion.company_facts import parse_company_facts
from raw_store.fx_rates import upsert_fx_rate
from raw_store.market_prices import get_fye_close, upsert_fye_close
from raw_store.repository import persist_company_facts
from scoring.facts import load_facts
from scoring.runner import score_altman, score_beneish, score_piotroski, score_sloan
from validation.checks import run_validation
from valuation.store import materialize_reverse_dcf


def _primary_filing_per_year(filings) -> dict:
    """One filing per fiscal year, preferring the original annual filing over any
    amendment — a narrow amendment often doesn't restate the full financial
    statements, so its own fiscal_year_end can be less reliable than the
    original filing's (confirmed live 2026-07-23: CP's 10-K/A rows are
    consistently dated to the amendment's own filing date). Mirrors AD-3's
    existing as-originally-filed-over-restated-comparative principle. Works
    for either ParsedFiling (dataclass) or Filing (DB model) rows — both
    expose .fiscal_year/.form_type. Regime-agnostic via
    canonicalization.taxonomies.supersedes (10-K/A -> 10-K, 40-F/A -> 40-F)."""
    values = filings.values() if isinstance(filings, dict) else filings
    by_year: dict = {}
    for f in values:
        existing = by_year.get(f.fiscal_year)
        if existing is None or supersedes(f.form_type, existing.form_type):
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
    fye_prices: dict[int, float | tuple[date, float]] | None = None,
    fx_rates: dict[int, float | tuple[date, float]] | None = None,
    reporting_currency: str | None = None,
) -> dict:
    """Full write-path pipeline for one issuer from a Company Facts payload.

    `fye_prices` maps fiscal_year -> period-end close (or `(observed_date, close)`)
    from Tiingo; when present for a year, Altman is also scored for that year
    (AD-11/AD-14). `fx_rates` has the analogous value or dated tuple for the
    USD/`reporting_currency` rate and is only needed for filers that
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

    # Validate stage (AD-17): accounting-identity checks over the canonical facts,
    # between canonicalize and score per the spine's stage order. Advisory only —
    # a violation writes a needs_review data_quality_issues row that the read API
    # surfaces (FR-8); it never blocks scoring, because a single bad identity for
    # one year should not suppress every other year's valid scores.
    validation = await run_validation(session, parsed.cik)

    # Persist any provided FYE market prices at the selected observation date.
    fye_prices = fye_prices or {}
    all_filings = (await session.execute(select(Filing).where(Filing.issuer_cik == parsed.cik))).scalars().all()
    filings = _primary_filing_per_year(all_filings)
    for fy, supplied in fye_prices.items():
        if fy in filings:
            if isinstance(supplied, tuple):
                price_date, close = supplied
            else:
                # Backward-compatible fixture/caller form. Live ingestion uses
                # the tuple form so a weekend FYE does not masquerade as a quote
                # observed on the Sunday itself.
                price_date, close = filings[fy].fiscal_year_end, supplied
            await upsert_fye_close(
                session, issuer_cik=parsed.cik, price_date=price_date, close_price=close
            )

    if reporting_currency and reporting_currency != "USD":
        for fy, supplied in (fx_rates or {}).items():
            if fy in filings:
                if isinstance(supplied, tuple):
                    rate_date, rate = supplied
                else:
                    rate_date, rate = filings[fy].fiscal_year_end, supplied
                await upsert_fx_rate(
                    session,
                    currency_pair=f"USD{reporting_currency}",
                    rate_date=rate_date,
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

    # Reverse DCF (AD-1). Runs AFTER scoring because it reads the same canonical
    # facts and the market/FX rows persisted above — and because it belongs on the
    # write path at all: it was previously solved on every page load, 35 sensitivity
    # cells at a time, which is the computation AD-1 forbids a read from triggering.
    # Upserts, so the daily cron leaves exactly one row.
    reverse_dcf_year = await materialize_reverse_dcf(
        session, parsed.cik, is_capital_intensive=is_capital_intensive
    )

    await session.commit()
    return {
        "cik": parsed.cik,
        "ticker": ticker,
        "scored_years": years,
        "scored": scored,
        "validation": validation,
        "reverse_dcf_year": reverse_dcf_year,
    }


async def _fye_prices_for(payload: dict, ticker: str) -> dict[int, tuple[date, float]]:
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

    fye_prices: dict[int, tuple[date, float]] = {}
    for fy, f in primary.items():
        fye = _date.fromisoformat(f.fiscal_year_end)
        row = select_fye_close(prices, fye)
        if row is not None:
            fye_prices[fy] = (date.fromisoformat(row["date"][:10]), row["close"])
    return fye_prices


def _payload_reporting_currency(payload: dict) -> str | None:
    """The currency unit the issuer's own Assets fact is reported in (e.g. 'USD',
    'CAD') — confirmed live 2026-07-23 that this varies (CP reports entirely in
    CAD). None if no financial taxonomy carries Assets at all.

    READS EVERY FINANCIAL TAXONOMY, not just `us-gaap`. Both use the concept name
    `Assets`, but a 40-F/IFRS filer has no `us-gaap` block whatsoever, so the
    original us-gaap-only lookup returned None for all three IFRS filers and no FX
    rate was ever fetched for them (observed live 2026-08-05: CCJ, BCE and SU each
    reported `currency=None` while every one of their canonical facts carries
    `unit=CAD`).

    That was masked rather than harmless. `scoring/runner.py` derives the currency
    from the CANONICAL facts instead of the payload, so it correctly asked for a
    USDCAD rate and found one — but only because CP had already stored rates for
    the same Dec-31 fiscal-year ends. Remove CP from the universe, give an IFRS
    filer a non-Dec-31 year end, or build a database IFRS-first, and Altman's X4
    would silently divide a USD market cap by CAD liabilities, which is the exact
    failure AD-11's currency fix exists to prevent.

    Sorted for determinism: a payload carrying both taxonomies (a filer mid-
    transition) must not resolve its currency by set-iteration order.
    """
    facts = payload.get("facts", {})
    for taxonomy in sorted(FINANCIAL_TAXONOMIES):
        units = facts.get(taxonomy, {}).get("Assets", {}).get("units", {})
        for unit in units:
            return unit
    return None


async def _fx_rates_for(payload: dict, reporting_currency: str | None) -> dict[int, tuple[date, float]]:
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

    fx_rates: dict[int, tuple[date, float]] = {}
    for fy, f in primary.items():
        fye = _date.fromisoformat(f.fiscal_year_end)
        row = select_rate_on_or_before(rates, fye)
        if row is not None:
            fx_rates[fy] = (date.fromisoformat(row["date"]), row["rate"])
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
        v = summary["validation"]
        flagged = (
            f", validation: {v['issues_raised']} new / {v['issues_existing']} open"
            if v["issues_raised"] or v["issues_existing"]
            else ""
        )
        print(
            f"OK {entry.ticker}: scored {summary['scored_years']} "
            f"(altman: {summary['scored']['altman']}){flagged}"
        )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
