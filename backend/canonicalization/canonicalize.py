"""Deterministic canonical-fact selection (AD-2, AD-3).

For each (issuer, canonical_concept, fiscal_year), choose one raw_fact by the
ordered rules:
  1. as-originally-filed  (fact from the filing whose fiscal_year == the period's
     year) over a restated comparative carried in a later filing;
  2. concept priority (when several source XBRL concepts map to one canonical
     concept — e.g. shares_outstanding's CommonStockSharesOutstanding-first,
     WeightedAverageNumberOfSharesOutstandingBasic-fallback chain — the lower
     priority number wins outright rather than being compared for ambiguity
     against a fundamentally different measurement);
  3. higher `decimals` precision;
  4. earliest `fetched_at` as a stable final tiebreak.
Ambiguity (distinct values tied through rule 2 — including a Company-Facts-vs-
Inline-XBRL conflict on the *same* source concept, AD-4) writes a
`data_quality_issues` row with status needs_review — never a defaulted guess
(AD-3). Canonical facts are derived, never mutated in place; a mapping-version
change produces new rows (AD-2).
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, DataQualityIssue, Filing, IssueStatus, RawFact
from canonicalization.mappings import MAPPING_VERSION, SOURCE_PRIORITY, SOURCE_TO_CANONICAL


async def canonicalize_issuer(
    session: AsyncSession, issuer_cik: str, *, mapping_version: str = MAPPING_VERSION
) -> dict[str, int]:
    """Build canonical_facts for one issuer. Returns counts (facts, ambiguities)."""
    counts = {"canonical_facts_added": 0, "ambiguities_flagged": 0}

    filings = {
        f.accession_number: f
        for f in (
            await session.execute(select(Filing).where(Filing.issuer_cik == issuer_cik))
        ).scalars()
    }
    accns = list(filings)
    if not accns:
        return counts

    raw_facts = (
        await session.execute(select(RawFact).where(RawFact.accession_number.in_(accns)))
    ).scalars().all()

    # Group candidate raw_facts by (canonical_concept, fiscal_year).
    grouped: dict[tuple[str, int], list[RawFact]] = defaultdict(list)
    for rf in raw_facts:
        canonical = SOURCE_TO_CANONICAL.get((rf.taxonomy, rf.concept))
        if canonical is None or rf.period_end is None:
            continue
        grouped[(canonical, rf.period_end.year)].append(rf)

    # Existing canonical rows for this version to keep the pass idempotent.
    existing = set(
        (
            await session.execute(
                select(CanonicalFact.issuer_cik, CanonicalFact.canonical_concept, CanonicalFact.fiscal_year).where(
                    CanonicalFact.issuer_cik == issuer_cik,
                    CanonicalFact.mapping_version == mapping_version,
                )
            )
        ).all()
    )

    for (canonical, fiscal_year), candidates in grouped.items():
        if (issuer_cik, canonical, fiscal_year) in existing:
            continue

        def rank(rf: RawFact) -> tuple:
            originally_filed = filings[rf.accession_number].fiscal_year == fiscal_year
            concept_priority = SOURCE_PRIORITY.get((rf.taxonomy, rf.concept), 0)
            return (
                0 if originally_filed else 1,  # originally filed first
                concept_priority,  # lower-priority source concept wins outright
                -(rf.decimals if rf.decimals is not None else -9),  # higher decimals first
                rf.fetched_at,  # stable
            )

        candidates.sort(key=rank)
        best = candidates[0]
        # Tie tier = (originally_filed, concept_priority) — a lower-priority concept never
        # contends for "ambiguous" against a higher-priority one (they measure different
        # things); decimals/fetched_at remain pure tiebreaks within a genuinely tied tier,
        # so two same-priority facts with different values (incl. a company_facts-vs-
        # inline_xbrl conflict on the same concept, AD-4) are still correctly flagged.
        top_tier = [c for c in candidates if rank(c)[:2] == rank(best)[:2]]
        distinct_values = {c.value for c in top_tier}

        if len(distinct_values) > 1:
            # Rules cannot separate conflicting values — flag, do not guess (AD-3).
            session.add(
                DataQualityIssue(
                    accession_number=best.accession_number,
                    issue_type="ambiguous_selection",
                    detail={
                        "canonical_concept": canonical,
                        "fiscal_year": fiscal_year,
                        "values": sorted(str(v) for v in distinct_values),
                    },
                    status=IssueStatus.needs_review,
                    raised_by="canonicalization",
                )
            )
            counts["ambiguities_flagged"] += 1
            continue

        session.add(
            CanonicalFact(
                issuer_cik=issuer_cik,
                accession_number=best.accession_number,
                canonical_concept=canonical,
                fiscal_year=fiscal_year,
                period_end=best.period_end,
                value=best.value,
                unit=best.unit,
                mapping_version=mapping_version,
                selected_from_raw_fact_id=best.id,
            )
        )
        counts["canonical_facts_added"] += 1

    await session.flush()
    return counts
