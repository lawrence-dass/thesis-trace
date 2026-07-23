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

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, DataQualityIssue, Filing, IssueStatus, RawFact
from canonicalization.mappings import MAPPING_VERSION, SOURCE_PRIORITY, SOURCE_TO_CANONICAL

# A 10-K's own accession routinely tags BOTH the true annual duration figure
# AND quarterly sub-periods under the exact same (fy, fp="FY") label — e.g. a
# "selected quarterly financial data" footnote disclosure. Confirmed live
# 2026-07-23 against CP's us-gaap:Revenues, fy=2016: the accession carries
# Q1-Q4 facts (~90-day spans) alongside the genuine full-year fact (~365-day
# span), all sharing fy=2016/fp=FY/form=10-K — grouping by period_end.year
# alone can't tell them apart and both land in the same candidate pool.
# Filtering to full-year spans before grouping resolves the true annual figure
# cleanly instead of flagging it ambiguous_selection against a quarter.
_MIN_FULL_YEAR_DAYS = 300  # excludes quarterly (~90d) and half-year (~180d) spans

# A new-accounting-standard adoption (e.g. ASC 606/842) is commonly disclosed
# with a cumulative-effect balance "as of the beginning of the year" — an
# instantaneous fact dated the FIRST day of the fiscal year, alongside the true
# closing balance dated the LAST day, both under the same fy/calendar year.
# Confirmed live 2026-07-23: QSR's FY2018 10-K tags us-gaap:Assets at both
# end=2018-01-01 (val=21,308,000,000, the Jan-1 opening/adjusted balance) and
# end=2018-12-31 (val=20,141,000,000, the true closing balance) — grouping by
# period_end.year alone puts both in fiscal_year=2018 and neither AD-3 tiebreak
# can separate them, spuriously flagging a cleanly resolvable case as
# ambiguous_selection. A fact only belongs in the annual bucket if its
# period_end actually falls near the issuer's own recognized fiscal-year-end
# day-of-year (tolerant of the odd few-day shift — e.g. OTEX's 2011 10-K FYE
# landed on 2011-07-07, not its usual June 30).
_FYE_DAY_TOLERANCE = 10


def _is_full_year_duration(rf: RawFact) -> bool:
    """True for instantaneous facts (no period_start — balance-sheet items like
    total_assets, unaffected by this filter) and for duration facts whose span
    is a genuine fiscal year rather than a quarterly/partial-period breakdown."""
    if rf.period_start is None or rf.period_end is None:
        return True
    return (rf.period_end - rf.period_start).days >= _MIN_FULL_YEAR_DAYS


def _day_of_year(month: int, day: int) -> int:
    return date(2001, month, day).toordinal() - date(2001, 1, 1).toordinal()


def _issuer_fye_day(filings: dict[str, Filing]) -> int | None:
    """The most common day-of-year among this issuer's own ORIGINAL 10-K
    fiscal-year-ends (never 10-K/A — an amendment's own fiscal_year_end can be
    unreliable, per the collision fix in pipeline.run._primary_filing_per_year)."""
    counts = Counter(
        _day_of_year(f.fiscal_year_end.month, f.fiscal_year_end.day)
        for f in filings.values()
        if f.form_type == "10-K"
    )
    return counts.most_common(1)[0][0] if counts else None


def _matches_fiscal_year_end(rf: RawFact, fye_day: int | None) -> bool:
    if fye_day is None or rf.period_end is None:
        return True
    actual = _day_of_year(rf.period_end.month, rf.period_end.day)
    return abs(actual - fye_day) <= _FYE_DAY_TOLERANCE


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
    fye_day = _issuer_fye_day(filings)
    grouped: dict[tuple[str, int], list[RawFact]] = defaultdict(list)
    for rf in raw_facts:
        canonical = SOURCE_TO_CANONICAL.get((rf.taxonomy, rf.concept))
        if canonical is None or rf.period_end is None:
            continue
        if not _is_full_year_duration(rf):
            continue
        if not _matches_fiscal_year_end(rf, fye_day):
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
    await _derive_total_liabilities(session, issuer_cik, mapping_version=mapping_version)
    await session.flush()
    return counts


async def _derive_total_liabilities(
    session: AsyncSession, issuer_cik: str, *, mapping_version: str
) -> None:
    """Fallback for filers that never tag us-gaap:Liabilities directly (confirmed
    live 2026-07-22: SHOP's 10-Ks report LiabilitiesAndStockholdersEquity and
    StockholdersEquity but never a standalone Liabilities total). Derives
    total_liabilities = total_assets - stockholders_equity — the basic accounting
    identity (Assets = Liabilities + Equity), verified exact against SHOP's real
    FY2024/FY2025 figures before relying on it. Only fires when total_liabilities
    is genuinely absent and both operands exist for the same fiscal year; never
    overrides a directly-tagged value. The derived fact's accession_number/
    period_end are taken from the total_assets fact — the same balance-sheet
    date, a faithful provenance root for a value with no single source line."""
    facts = (
        await session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == issuer_cik,
                CanonicalFact.mapping_version == mapping_version,
                CanonicalFact.canonical_concept.in_(("total_assets", "stockholders_equity", "total_liabilities")),
            )
        )
    ).scalars().all()

    by_year: dict[int, dict[str, CanonicalFact]] = defaultdict(dict)
    for f in facts:
        by_year[f.fiscal_year][f.canonical_concept] = f

    for fiscal_year, concepts in by_year.items():
        if "total_liabilities" in concepts:
            continue
        total_assets = concepts.get("total_assets")
        equity = concepts.get("stockholders_equity")
        if total_assets is None or equity is None:
            continue

        session.add(
            CanonicalFact(
                issuer_cik=issuer_cik,
                accession_number=total_assets.accession_number,
                canonical_concept="total_liabilities",
                fiscal_year=fiscal_year,
                period_end=total_assets.period_end,
                value=Decimal(str(total_assets.value)) - Decimal(str(equity.value)),
                unit=total_assets.unit,
                mapping_version=mapping_version,
                selected_from_raw_fact_id=None,
            )
        )
