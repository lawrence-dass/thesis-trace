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

from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import MAPPING_VERSION, seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from scoring.facts import load_facts
from scoring.runner import score_piotroski, score_sloan


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
) -> dict:
    """Full write-path pipeline for one issuer from a Company Facts payload."""
    parsed = parse_company_facts(payload)
    await persist_company_facts(
        session, parsed, ticker=ticker, sector=sector, is_financial_sector=is_financial_sector
    )
    await seed_concept_mappings(session)
    await canonicalize_issuer(session, parsed.cik)

    years = await scoreable_years(session, parsed.cik)
    for year in years:
        await score_piotroski(session, parsed.cik, year)
        await score_sloan(session, parsed.cik, year)
    await session.commit()
    return {"cik": parsed.cik, "ticker": ticker, "scored_years": years}


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
