"""Append-only raw store (AD-2).

Persists parsed Company Facts idempotently: issuers and filings are upserted;
raw_facts are appended and de-duplicated by (accession_number, content_hash).
Re-ingesting the same payload creates no duplicate rows (AD-9 replayable).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataQualityIssue, Filing, Issuer, RawFact
from ingestion.company_facts import ParsedCompanyFacts, ParsedFact


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
        existing_filing = await session.get(Filing, accn)
        if existing_filing is None:
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
        else:
            # Filing metadata is a projection of the parser's current
            # interpretation, not append-only raw evidence. Updating it makes a
            # corrected parser durable on re-ingestion, including fiscal-year
            # end fixes discovered after a prior run.
            existing_filing.issuer_cik = parsed.cik
            existing_filing.form_type = filing.form_type
            existing_filing.filing_date = _to_date(filing.filing_date)
            existing_filing.fiscal_year = filing.fiscal_year
            existing_filing.fiscal_year_end = _to_date(filing.fiscal_year_end)
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
                # Always None from Company Facts (it carries no dimensions at
                # all). Mapped through anyway so the field is LIVE rather than
                # declared: Story 13.2's Inline XBRL path reuses this writer, and
                # an unmapped column would drop every member it parsed while the
                # parse itself looked correct — the same declared-but-unexercised
                # shape this story's own AD-3 rule 0 was written to close.
                dimensions=fact.dimensions,
            )
        )
        counts["raw_facts_added"] += 1
    await session.flush()
    return counts


async def persist_inline_facts(
    session: AsyncSession,
    facts: list[ParsedFact],
    *,
    accession_number: str,
) -> dict[str, int]:
    """Append Inline XBRL facts, reconciling same-identity overlaps with Company Facts (AD-4).

    Two populations, handled differently and deliberately:

    DIMENSIONED facts are inserted unconditionally (subject to the usual
    idempotency key). They are never compared to their undimensioned
    counterparts, because AD-3 rule 0 makes them different facts — a segment's
    revenue is not a competing measurement of consolidated revenue. Company Facts
    carries no dimensional data at all, so there is never an overlapping
    candidate from the primary source to reconcile against.

    UNDIMENSIONED facts CAN genuinely collide with a Company Facts fact for the
    same (taxonomy, concept, unit, period). AD-4 governs: Company Facts wins, the
    Inline value is not written, and the divergence opens a `source_conflict`
    row. `issue_type = 'source_conflict'` has been an anticipated value in
    `app/models.py` since Epic 1 and had never been emitted by anything — this is
    the first writer for it.

    The dedup ignores issue STATUS, so a `dismissed` conflict is not resurrected
    as a fresh `needs_review` one on the next run — the same requirement
    `canonicalize_issuer` and `run_validation` already carry, because
    `pipeline/run.py` is a daily cron over the same inputs.
    """
    counts = {"raw_facts_added": 0, "source_conflicts": 0, "company_facts_preferred": 0}
    if not facts:
        return counts

    existing_hashes = {
        h
        for (h,) in (
            await session.execute(
                select(RawFact.content_hash).where(RawFact.accession_number == accession_number)
            )
        ).all()
    }

    # Company Facts facts for this filing, keyed by identity-without-value. Keep
    # all values: Company Facts can itself contain repeated same-identity rows
    # with different values, and choosing the last row would make this source
    # reconciliation depend on database iteration order.
    primary: dict[tuple, set[Decimal]] = {}
    for rf in (
        await session.execute(
            select(RawFact).where(
                RawFact.accession_number == accession_number,
                RawFact.source == "company_facts",
            )
        )
    ).scalars():
        if rf.value is None:
            continue
        key = (rf.taxonomy, rf.concept, rf.unit, rf.period_start, rf.period_end)
        primary.setdefault(key, set()).add(Decimal(str(rf.value)))

    existing_conflicts = {
        (
            d.get("taxonomy"),
            d.get("concept"),
            d.get("unit"),
            d.get("period_start"),
            d.get("period_end"),
        )
        for d in (
            await session.execute(
                select(DataQualityIssue.detail).where(
                    DataQualityIssue.accession_number == accession_number,
                    DataQualityIssue.issue_type == "source_conflict",
                )
            )
        ).scalars()
        if d
    }

    for fact in facts:
        if fact.accession_number != accession_number:
            raise ValueError(
                f"Inline fact accession {fact.accession_number!r} does not match the filing "
                f"accession {accession_number!r}"
            )
        if fact.content_hash in existing_hashes:
            continue

        if not fact.dimensions:
            key = (
                fact.taxonomy,
                fact.concept,
                fact.unit,
                _to_date(fact.period_start),
                _to_date(fact.period_end),
            )
            if key in primary:
                primary_values = primary[key]
                inline_value = Decimal(str(fact.value))
                if inline_value not in primary_values:
                    counts["company_facts_preferred"] += 1
                    dedup = (
                        fact.taxonomy,
                        fact.concept,
                        fact.unit,
                        fact.period_start,
                        fact.period_end,
                    )
                    if dedup not in existing_conflicts:
                        existing_conflicts.add(dedup)
                        counts["source_conflicts"] += 1
                        company_facts_value: float | list[float]
                        if len(primary_values) == 1:
                            company_facts_value = float(next(iter(primary_values)))
                        else:
                            company_facts_value = sorted(float(value) for value in primary_values)
                        session.add(
                            DataQualityIssue(
                                accession_number=accession_number,
                                issue_type="source_conflict",
                                raised_by="ingestion",
                                detail={
                                    "taxonomy": fact.taxonomy,
                                    "concept": fact.concept,
                                    "unit": fact.unit,
                                    "period_start": fact.period_start,
                                    "period_end": fact.period_end,
                                    "company_facts_value": company_facts_value,
                                    "inline_xbrl_value": fact.value,
                                    "resolution": (
                                        "Company Facts wins (AD-4); the Inline XBRL value "
                                        "was not written."
                                    ),
                                },
                            )
                        )
                # Whether or not the values agree, Company Facts already holds
                # this fact — Inline supplies only what the primary source omits.
                continue

        existing_hashes.add(fact.content_hash)
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
                dimensions=fact.dimensions,
            )
        )
        counts["raw_facts_added"] += 1

    await session.flush()
    return counts
