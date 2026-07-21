"""Append-only raw store (AD-2).

Persists parsed Company Facts idempotently: issuers and filings are upserted;
raw_facts are appended and de-duplicated by (accession_number, content_hash).
Re-ingesting the same payload creates no duplicate rows (AD-9 replayable).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Filing, Issuer, RawFact
from ingestion.company_facts import ParsedCompanyFacts


def _to_date(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if iso else None


async def persist_company_facts(
    session: AsyncSession,
    parsed: ParsedCompanyFacts,
    *,
    ticker: str,
    sector: str | None = None,
    is_financial_sector: bool = False,
    is_capital_intensive: bool = False,
) -> dict[str, int]:
    """Upsert issuer + filings, append new raw_facts. Returns counts of inserts."""
    counts = {"filings_added": 0, "raw_facts_added": 0}

    issuer = await session.get(Issuer, parsed.cik)
    if issuer is None:
        session.add(
            Issuer(
                cik=parsed.cik,
                ticker=ticker,
                name=parsed.entity_name,
                sector=sector,
                is_financial_sector=is_financial_sector,
                is_capital_intensive=is_capital_intensive,
            )
        )
        await session.flush()

    for accn, filing in parsed.filings.items():
        if await session.get(Filing, accn) is None:
            session.add(
                Filing(
                    accession_number=accn,
                    issuer_cik=parsed.cik,
                    form_type=filing.form_type,
                    filing_date=_to_date(filing.filing_date),
                    fiscal_year=filing.fiscal_year,
                    fiscal_year_end=_to_date(filing.fiscal_year_end),
                )
            )
            counts["filings_added"] += 1
    await session.flush()

    # Existing (accession_number, content_hash) pairs to skip (AD-2 append-only, idempotent).
    existing = set(
        (
            await session.execute(select(RawFact.accession_number, RawFact.content_hash))
        ).all()
    )
    for fact in parsed.facts:
        key = (fact.accession_number, fact.content_hash)
        if key in existing:
            continue
        existing.add(key)
        session.add(
            RawFact(
                accession_number=fact.accession_number,
                taxonomy=fact.taxonomy,
                concept=fact.concept,
                unit=fact.unit,
                period_start=_to_date(fact.period_start),
                period_end=_to_date(fact.period_end),
                value=fact.value,
                source=fact.source,
                content_hash=fact.content_hash,
            )
        )
        counts["raw_facts_added"] += 1
    await session.flush()
    return counts
