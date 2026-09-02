"""Story 1.4 — canonicalization selection + validation (AD-2, AD-3, AD-17)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, DataQualityIssue, Filing, IssueStatus, Issuer, RawFact
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

async def test_an_ambiguity_is_flagged_once_not_once_per_mapping_version(db_session):
    """The ambiguity writer needs an idempotency key, like every other pipeline writer.

    `session.add(DataQualityIssue(...))` ran unconditionally. That is invisible in
    daily operation, because an already-canonicalized issuer is skipped wholesale
    before reaching the flagging branch — but a MAPPING-VERSION BUMP re-resolves
    every concept and so re-flags every unresolvable one. Found 2026-08-21 by
    rendering SHOP's page after the concepts_v9 bump: a wall of 24 identical
    "Ambiguous source selection" rows, with CP at 18 and BCE's and OTEX's four
    apiece doubled to eight. No test saw it, because no test canonicalized the same
    issuer under two versions.

    Same class as the `run_validation` accumulation fixed in PR #22 — this was the
    one writer that was missed.
    """
    cik = await _ingest(db_session)
    db_session.add(
        RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Assets",
            unit="USD",
            period_end=date(2024, 12, 31),
            value=99999999999,
            source="inline_xbrl",
            content_hash="conflict-hash-idempotency",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()

    async def issue_count() -> int:
        rows = (
            await db_session.execute(
                select(DataQualityIssue).where(
                    DataQualityIssue.issue_type == "ambiguous_selection"
                )
            )
        ).scalars().all()
        return len(rows)

    await canonicalize_issuer(db_session, cik)
    await db_session.flush()
    after_first = await issue_count()
    assert after_first >= 1, "the conflicting fact should have been flagged at all"

    # A NEW mapping version: every concept is re-resolved, so the flagging branch
    # runs again. This is the exact condition that produced the wall of duplicates.
    await canonicalize_issuer(db_session, cik, mapping_version="concepts_probe")
    await db_session.flush()
    assert await issue_count() == after_first, (
        "a mapping-version bump re-flagged an ambiguity that was already on record — "
        "the writer has lost its idempotency key, and the UI will show the same "
        "warning once per version bump"
    )

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


# --- Amendment supersession (canonical_facts_amendment_gap, AD-6) ------------
#
# The gap was an ARRIVAL-ORDER bug: within one pass the ranking saw every raw
# fact, but the idempotency skip across passes froze whichever value was
# written first. So every test here simulates the production order — original
# canonicalized, THEN the amendment ingested, THEN a second pass — rather than
# merely loading both at once (which the finding showed cannot reproduce it).

SHOP_FY2024_10K = "0001594805-25-000010"
SHOP_FY2024_10KA = "0001594805-25-000099"


async def _file_amendment(db_session, cik: str, *, assets_value: int, decimals: int | None = -6) -> None:
    """Ingest a 10-K/A for SHOP FY2024 restating total assets."""
    db_session.add(
        Filing(
            accession_number=SHOP_FY2024_10KA,
            issuer_cik=cik,
            form_type="10-K/A",
            filing_date=date(2025, 6, 30),
            fiscal_year=2024,
            fiscal_year_end=date(2024, 12, 31),
        )
    )
    await db_session.flush()  # raw_facts FK to filings; no relationship orders the flush
    db_session.add(
        RawFact(
            accession_number=SHOP_FY2024_10KA,
            taxonomy="us-gaap",
            concept="Assets",
            unit="USD",
            period_end=date(2024, 12, 31),
            value=assets_value,
            decimals=decimals,
            source="company_facts",
            content_hash=f"amend-assets-{assets_value}",
            fetched_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()


async def _total_assets_rows(db_session) -> list[CanonicalFact]:
    return list(
        (
            await db_session.execute(
                select(CanonicalFact)
                .where(CanonicalFact.canonical_concept == "total_assets", CanonicalFact.fiscal_year == 2024)
                .order_by(CanonicalFact.created_at, CanonicalFact.superseded.desc())
            )
        ).scalars()
    )


@requires_db
async def test_amendment_arriving_after_canonicalization_supersedes_the_original(db_session) -> None:
    """The production shape: FY2024 canonicalized from the 10-K; months later a
    10-K/A restates total assets; the next pass must make the restated value
    current WITHOUT deleting or mutating the row prior score runs point at."""
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)
    (original,) = await _total_assets_rows(db_session)
    assert original.value == 13100000000

    await _file_amendment(db_session, cik, assets_value=13250000000)
    counts = await canonicalize_issuer(db_session, cik)
    assert counts["canonical_facts_superseded"] == 1
    assert counts["canonical_facts_added"] == 1

    rows = await _total_assets_rows(db_session)
    assert len(rows) == 2, "supersession appends; it never deletes"
    old = next(r for r in rows if r.id == original.id)
    new = next(r for r in rows if r.id != original.id)
    assert old.value == 13100000000 and old.superseded is True and old.superseded_by == new.id
    assert new.value == 13250000000 and new.superseded is False
    assert new.accession_number == SHOP_FY2024_10KA

    # A third pass is a no-op — the amendment does not re-supersede itself.
    third = await canonicalize_issuer(db_session, cik)
    assert third["canonical_facts_added"] == 0
    assert third["canonical_facts_superseded"] == 0
    assert len(await _total_assets_rows(db_session)) == 2


@requires_db
async def test_amendment_restating_an_identical_figure_does_not_rewrite_history(db_session) -> None:
    """A 10-K/A that re-files the same number (here at higher precision, so it
    would win the ranking) changes no figure, so the original row stays current:
    provenance is rewritten only when a value actually moves."""
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)
    (original,) = await _total_assets_rows(db_session)

    await _file_amendment(db_session, cik, assets_value=13100000000, decimals=-3)
    counts = await canonicalize_issuer(db_session, cik)
    assert counts["canonical_facts_superseded"] == 0
    assert counts["canonical_facts_added"] == 0
    (still,) = await _total_assets_rows(db_session)
    assert still.id == original.id and still.superseded is False
    assert still.accession_number == SHOP_FY2024_10K


@requires_db
async def test_same_year_amendment_outranks_its_original_without_an_ambiguity_flag(db_session) -> None:
    """Single pass, both filings present: the amendment is the filer's own
    supersession of the original, not a conflict the rules cannot separate, so
    it wins outright and no needs_review row is raised (AD-3 flags genuine
    ambiguity; AD-6 requires the restated value to be the one scored)."""
    cik = await _ingest(db_session)
    await _file_amendment(db_session, cik, assets_value=13250000000)
    counts = await canonicalize_issuer(db_session, cik)
    assert counts["ambiguities_flagged"] == 0

    (current,) = await _total_assets_rows(db_session)
    assert current.value == 13250000000
    assert current.accession_number == SHOP_FY2024_10KA
    issues = (await db_session.execute(select(DataQualityIssue))).scalars().all()
    assert not [i for i in issues if i.issue_type == "ambiguous_selection"]


@requires_db
async def test_superseding_an_operand_re_derives_the_dependent_fact(db_session) -> None:
    """A derived fact is only as current as its operands. Synthetic filer that
    never tags Liabilities (SHOP's real shape): total_liabilities is derived as
    assets - equity. When a 10-K/A restates assets, the derived row must be
    superseded and recomputed — never edited in place."""
    cik = "0000000042"
    db_session.add(Issuer(cik=cik, ticker="SYN", name="Synthetic Filer"))
    db_session.add(
        Filing(
            accession_number="0000000042-25-000001",
            issuer_cik=cik,
            form_type="10-K",
            filing_date=date(2025, 2, 15),
            fiscal_year=2024,
            fiscal_year_end=date(2024, 12, 31),
        )
    )
    await db_session.flush()
    for concept, value in (("Assets", 1000), ("StockholdersEquity", 400)):
        db_session.add(
            RawFact(
                accession_number="0000000042-25-000001",
                taxonomy="us-gaap",
                concept=concept,
                unit="USD",
                period_end=date(2024, 12, 31),
                value=value,
                decimals=0,
                source="company_facts",
                content_hash=f"syn-{concept}",
                fetched_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            )
        )
    await seed_concept_mappings(db_session)
    await db_session.flush()
    await canonicalize_issuer(db_session, cik)

    async def liabilities() -> list[CanonicalFact]:
        return list(
            (
                await db_session.execute(
                    select(CanonicalFact).where(
                        CanonicalFact.issuer_cik == cik,
                        CanonicalFact.canonical_concept == "total_liabilities",
                    )
                )
            ).scalars()
        )

    (derived,) = await liabilities()
    assert derived.value == 600 and derived.derivation == "assets_minus_equity"

    db_session.add(
        Filing(
            accession_number="0000000042-25-000002",
            issuer_cik=cik,
            form_type="10-K/A",
            filing_date=date(2025, 6, 30),
            fiscal_year=2024,
            fiscal_year_end=date(2024, 12, 31),
        )
    )
    await db_session.flush()
    db_session.add(
        RawFact(
            accession_number="0000000042-25-000002",
            taxonomy="us-gaap",
            concept="Assets",
            unit="USD",
            period_end=date(2024, 12, 31),
            value=1100,
            decimals=0,
            source="company_facts",
            content_hash="syn-Assets-amended",
            fetched_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()
    counts = await canonicalize_issuer(db_session, cik)
    # One filed supersession (total_assets) and one derived (total_liabilities).
    assert counts["canonical_facts_superseded"] == 2

    rows = await liabilities()
    assert len(rows) == 2
    old = next(r for r in rows if r.id == derived.id)
    new = next(r for r in rows if r.id != derived.id)
    assert old.value == 600 and old.superseded is True and old.superseded_by == new.id
    assert new.value == 700 and new.superseded is False
    assert new.derivation == "assets_minus_equity"
    assert new.accession_number == "0000000042-25-000002", "provenance anchor follows the amendment"
