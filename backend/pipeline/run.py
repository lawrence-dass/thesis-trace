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
from raw_store.market_prices import get_fye_close, upsert_fye_close
from raw_store.repository import persist_company_facts
from scoring.facts import load_facts
from scoring.runner import score_altman, score_beneish, score_piotroski, score_sloan


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
) -> dict:
    """Full write-path pipeline for one issuer from a Company Facts payload.

    `fye_prices` maps fiscal_year -> period-end close (from Tiingo); when present
    for a year, Altman is also scored for that year (AD-11/AD-14).
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
    filings = {
        f.fiscal_year: f
        for f in (await session.execute(select(Filing).where(Filing.issuer_cik == parsed.cik))).scalars()
    }
    for fy, close in fye_prices.items():
        if fy in filings:
            await upsert_fye_close(
                session, issuer_cik=parsed.cik, price_date=filings[fy].fiscal_year_end, close_price=close
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


async def main() -> None:  # pragma: no cover — live path, gated
    """Live universe run for the Render Cron Job. Requires network + EDGAR_CONTACT.

    Gated: performs live SEC EDGAR fetches. Only entries with a confirmed CIK run;
    others are reported as skipped so coverage gaps are explicit.
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
        async with sessionmaker() as session:
            summary = await run_issuer(
                session,
                payload,
                ticker=entry.ticker,
                is_financial_sector=entry.is_financial_sector,
            )
        print(f"OK {entry.ticker}: scored {summary['scored_years']}")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
