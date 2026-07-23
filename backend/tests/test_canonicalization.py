"""Story 1.4 — canonicalization selection + validation (AD-2, AD-3, AD-17)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, DataQualityIssue, IssueStatus, RawFact
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from validation.checks import run_validation
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


async def _ingest(db_session) -> str:
    parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
    await persist_company_facts(db_session, parsed, ticker="SHOP")
    await seed_concept_mappings(db_session)
    return parsed.cik


@requires_db
async def test_canonicalize_maps_and_selects(db_session) -> None:
    cik = await _ingest(db_session)
    counts = await canonicalize_issuer(db_session, cik)
    assert counts["canonical_facts_added"] > 0
    assert counts["ambiguities_flagged"] == 0

    facts = {
        (f.canonical_concept, f.fiscal_year): f
        for f in (await db_session.execute(select(CanonicalFact))).scalars()
    }
    # total_assets FY2024 = 13.1B, mapped from us-gaap:Assets.
    assert facts[("total_assets", 2024)].value == 13100000000
    assert facts[("net_income", 2023)].value == 132000000


@requires_db
async def test_canonicalize_is_idempotent(db_session) -> None:
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)
    second = await canonicalize_issuer(db_session, cik)
    assert second["canonical_facts_added"] == 0


@requires_db
async def test_conflicting_values_flag_ambiguity_not_guess(db_session) -> None:
    cik = await _ingest(db_session)
    # Inject a SECOND originally-filed Assets fact for FY2024 with a different value
    # under the same filing — the rules cannot separate them, so it must be flagged.
    db_session.add(
        RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Assets",
            unit="USD",
            period_end=date(2024, 12, 31),
            value=99999999999,
            source="inline_xbrl",
            content_hash="conflict-hash",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()

    counts = await canonicalize_issuer(db_session, cik)
    assert counts["ambiguities_flagged"] >= 1

    issue = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.issue_type == "ambiguous_selection")
        )
    ).scalars().first()
    assert issue is not None
    assert issue.status == IssueStatus.needs_review
    # No canonical total_assets FY2024 row was created for the ambiguous case.
    ta_2024 = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "total_assets", CanonicalFact.fiscal_year == 2024
            )
        )
    ).scalars().first()
    assert ta_2024 is None


@requires_db
async def test_shares_outstanding_prefers_point_in_time_over_dei_and_ignores_wrong_year_dei(db_session) -> None:
    """Regression guard (AD-3/AD-11): dei:EntityCommonStockSharesOutstanding is dated to
    the filing date, not FYE — for a December filer that files in Jan/Feb, its `end` date
    falls in the *next* calendar year, so if it were ever (re-)mapped to shares_outstanding
    it would land under the wrong fiscal_year bucket and silently starve Altman's X4 /
    Piotroski's shares_not_diluted of real data. shares_outstanding must resolve correctly
    for the true fiscal year using only the FYE-dated us-gaap fallback chain."""
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)

    shares = {
        f.fiscal_year: f.value
        for f in (
            await db_session.execute(
                select(CanonicalFact).where(CanonicalFact.canonical_concept == "shares_outstanding")
            )
        ).scalars()
    }
    # Fixture's WeightedAverageNumberOfSharesOutstandingBasic (FYE-dated) resolves for
    # both fiscal years — not the dei fact, which is unmapped and correctly ignored.
    assert shares[2023] == 1270000000
    assert shares[2024] == 1290000000

    # The (now-unmapped) dei fact never produced a canonical row of its own — proving it
    # wasn't silently picked up under some other (wrong) fiscal-year key.
    all_years = {
        fy
        for (fy,) in (
            await db_session.execute(
                select(CanonicalFact.fiscal_year).where(CanonicalFact.canonical_concept == "shares_outstanding")
            )
        ).all()
    }
    assert all_years == {2023, 2024}, "no stray shares_outstanding row from the unmapped dei fact"


@requires_db
async def test_quarterly_breakdown_fact_does_not_shadow_annual_figure(db_session) -> None:
    """Regression guard (AD-3/AD-11): a 10-K's "selected quarterly financial
    data" footnote tags quarterly sub-periods under the SAME accession/fy/fp as
    the true annual figure — confirmed live 2026-07-23 against CP's
    us-gaap:Revenues, fy=2016, where a Q4 fact (end=2016-12-31, ~90-day span)
    and the genuine full-year fact (end=2016-12-31, ~365-day span) shared the
    same period_end and so landed in the same (concept, fiscal_year) candidate
    pool, spuriously flagging the clean annual figure as ambiguous_selection.
    Grouping must exclude non-full-year duration facts before selection."""
    cik = await _ingest(db_session)
    # A Q4 2024 revenue breakdown fact, same accession/period_end as the real
    # annual FY2024 Revenues fact (8,880,000,000) but a ~90-day span and a
    # different value — must NOT contend for the fiscal_year=2024 slot.
    db_session.add(
        RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Revenues",
            unit="USD",
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            value=2300000000,
            source="company_facts",
            content_hash="q4-2024-revenue-hash",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()

    counts = await canonicalize_issuer(db_session, cik)
    assert counts["ambiguities_flagged"] == 0

    revenue_2024 = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "revenue", CanonicalFact.fiscal_year == 2024
            )
        )
    ).scalars().one()
    assert revenue_2024.value == 8880000000  # the annual figure, not the Q4 breakdown


@requires_db
async def test_standard_adoption_opening_balance_does_not_shadow_closing_balance(db_session) -> None:
    """Regression guard (AD-3/AD-11): a new-accounting-standard adoption (e.g.
    ASC 606/842) is commonly disclosed with a cumulative-effect balance "as of
    the beginning of the year" — an instantaneous fact dated the FIRST day of
    the fiscal year, alongside the true closing balance dated the LAST day,
    both falling in the SAME calendar year. Confirmed live 2026-07-23 against
    QSR's FY2018 10-K: us-gaap:Assets tagged at both end=2018-01-01 (opening,
    adjusted balance) and end=2018-12-31 (true closing balance) — grouping by
    period_end.year alone put both in fiscal_year=2018, spuriously flagging the
    clean closing balance as ambiguous_selection. Must be resolved by day-of-
    year proximity to the issuer's own recognized fiscal-year-end, not by
    calendar year alone."""
    cik = await _ingest(db_session)
    # A Jan-1-2024 "opening balance" Assets fact, same accession as the real
    # 2024-12-31 closing balance (13,100,000,000 per the fixture) but a
    # different value — must NOT contend for the fiscal_year=2024 slot.
    db_session.add(
        RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Assets",
            unit="USD",
            period_end=date(2024, 1, 1),
            value=12000000000,
            source="company_facts",
            content_hash="jan1-2024-assets-hash",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()

    counts = await canonicalize_issuer(db_session, cik)
    assert counts["ambiguities_flagged"] == 0

    assets_2024 = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "total_assets", CanonicalFact.fiscal_year == 2024
            )
        )
    ).scalars().one()
    assert assets_2024.value == 13100000000  # the true closing balance, not the Jan-1 opening one


@requires_db
async def test_validation_flags_identity_violation(db_session) -> None:
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)
    # Corrupt a canonical fact so current_assets > total_assets for FY2024.
    ca = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "current_assets", CanonicalFact.fiscal_year == 2024
            )
        )
    ).scalars().one()
    ca.value = 99000000000  # > total_assets
    await db_session.flush()

    counts = await run_validation(db_session, cik)
    assert counts["issues_raised"] >= 1
    issue = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.raised_by == "validation")
        )
    ).scalars().first()
    assert issue is not None and "identity_violation" in issue.issue_type
