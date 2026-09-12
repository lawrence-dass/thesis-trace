"""Dimensioned facts reach `canonical_member_facts` — end to end (Story 13.3).

test_brand_member_mapping.py proves the SPEC resolves members. This file proves
the PIPELINE writes them: raw dimensioned facts in, canonical member facts out,
through the same `canonicalize_issuer` the daily cron calls
(`pipeline/run.py:106`).

That distinction is the whole point. AD-3's "least-dimensioned/most-specific
member" clause and `raw_facts.dimensions` both sat declared and unexecuted for
over a year and read exactly like working code
(`dimensioned_facts_would_contaminate_consolidated_canonical_facts`). A mapping
that resolves in a unit test and never lands a row would be the same defect with
a newer date on it.

Fixtures are CPB's real shape: a 52/53-week fiscal year ending 2024-07-28 and
2025-08-03, and the member names that filing actually carried each year
(story_13_3_brand_member_live_verification).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models import CanonicalFact, CanonicalMemberFact, ConceptMapping, Filing, Issuer, RawFact
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from tests.conftest import requires_db

CPB = "0000016732"
ZTS = "0001555280"
AXIS = "us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis"
CARRYING = "IndefiniteLivedIntangibleAssetsExcludingGoodwill"
IMPAIRMENT = "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill"

FY2024_ACCN = "0000016732-24-000130"
FY2025_ACCN = "0000016732-25-000112"


async def _issuer(db_session, cik: str, ticker: str) -> None:
    db_session.add(Issuer(cik=cik, ticker=ticker, name=f"{ticker} Inc", sector="Consumer"))
    await db_session.flush()


async def _filing(
    db_session, cik: str, accn: str, fiscal_year: int, fye: date, form_type: str = "10-K"
) -> None:
    db_session.add(
        Filing(
            accession_number=accn,
            issuer_cik=cik,
            form_type=form_type,
            filing_date=date(fiscal_year, 9, 20),
            fiscal_year=fiscal_year,
            fiscal_year_end=fye,
        )
    )
    await db_session.flush()


def _fact(accn: str, concept: str, member: str, period_end: date, value: float, tag: str) -> RawFact:
    """A dimensioned instant fact, the shape brand carrying value actually has."""
    return RawFact(
        accession_number=accn,
        taxonomy="us-gaap",
        concept=concept,
        unit="USD",
        period_start=None,
        period_end=period_end,
        value=value,
        dimensions={AXIS: member},
        source="inline_xbrl",
        content_hash=tag,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


async def _cpb_two_years(db_session) -> None:
    await _issuer(db_session, CPB, "CPB")
    await _filing(db_session, CPB, FY2024_ACCN, 2024, date(2024, 7, 28))
    await _filing(db_session, CPB, FY2025_ACCN, 2025, date(2025, 8, 3))
    db_session.add_all(
        [
            # Kettle under the name each filing used — the rename, as filed.
            _fact(FY2024_ACCN, CARRYING, "cpb:TrademarksKettleBrandMember",
                  date(2024, 7, 28), 400_000_000, "kettle-fy2024"),
            _fact(FY2025_ACCN, CARRYING, "cpb:TrademarksKettleBrandMember",
                  date(2025, 8, 3), 395_000_000, "kettle-fy2025"),
            # A real FY2025 impairment: Snyder's of Hanover, 150M.
            _fact(FY2025_ACCN, IMPAIRMENT, "cpb:TrademarksSnydersOfHanoverMember",
                  date(2025, 8, 3), 150_000_000, "snyders-impair-fy2025"),
        ]
    )
    await db_session.flush()
    await seed_concept_mappings(db_session)


@requires_db
async def test_dimensioned_brand_facts_reach_the_member_store(db_session) -> None:
    """The path is LIVE, not merely declared: rows land, per member, per year."""
    await _cpb_two_years(db_session)

    counts = await canonicalize_issuer(db_session, CPB)

    assert counts["member_facts_added"] == 3, counts
    assert counts["member_ambiguities_flagged"] == 0

    rows = (
        await db_session.execute(
            select(CanonicalMemberFact).where(CanonicalMemberFact.superseded.is_(False))
        )
    ).scalars().all()
    by_key = {(r.canonical_concept, r.member_key, r.fiscal_year): r for r in rows}

    kettle_2024 = by_key[("brand_intangible_carrying_value", "kettle", 2024)]
    kettle_2025 = by_key[("brand_intangible_carrying_value", "kettle", 2025)]
    assert kettle_2024.value == 400_000_000
    assert kettle_2025.value == 395_000_000
    assert kettle_2024.axis_as_filed == AXIS

    impairment = by_key[("brand_intangible_impairment", "snyders_of_hanover", 2025)]
    assert impairment.value == 150_000_000
    assert impairment.member_as_filed == "cpb:TrademarksSnydersOfHanoverMember"


@requires_db
async def test_a_renamed_member_stays_one_brand_in_the_store(db_session) -> None:
    """The rename finding, at the database level rather than in the lookup.

    CPB filed Kettle as cpb:TradeNamesKettleMember in FY2022 and
    cpb:TrademarksKettleBrandMember in FY2025. Both must land under ONE
    member_key, each keeping the name its own filing used — otherwise one brand
    becomes two series and its trajectory silently breaks in half.
    """
    await _issuer(db_session, CPB, "CPB")
    await _filing(db_session, CPB, "0000016732-22-000093", 2022, date(2022, 7, 31))
    await _filing(db_session, CPB, FY2025_ACCN, 2025, date(2025, 8, 3))
    db_session.add_all(
        [
            _fact("0000016732-22-000093", CARRYING, "cpb:TradeNamesKettleMember",
                  date(2022, 7, 31), 380_000_000, "kettle-old-name"),
            _fact(FY2025_ACCN, CARRYING, "cpb:TrademarksKettleBrandMember",
                  date(2025, 8, 3), 395_000_000, "kettle-new-name"),
        ]
    )
    await db_session.flush()
    await seed_concept_mappings(db_session)

    await canonicalize_issuer(db_session, CPB)

    rows = (
        await db_session.execute(
            select(CanonicalMemberFact).where(
                CanonicalMemberFact.canonical_concept == "brand_intangible_carrying_value",
                CanonicalMemberFact.superseded.is_(False),
            )
        )
    ).scalars().all()
    assert {r.member_key for r in rows} == {"kettle"}, "a rename must not split one brand in two"
    assert {r.fiscal_year for r in rows} == {2022, 2025}
    assert {r.member_as_filed for r in rows} == {
        "cpb:TradeNamesKettleMember",
        "cpb:TrademarksKettleBrandMember",
    }, "each row must keep the name its own filing carried (AD-19)"


@requires_db
async def test_an_unmapped_member_is_skipped_never_guessed(db_session) -> None:
    """A brand the spec has not been extended for resolves to nothing at all.

    Silence is the correct answer: admitting it would invent a canonical meaning
    for a member nobody live-verified, which is the failure the per-year member
    verification exists to prevent.
    """
    await _issuer(db_session, CPB, "CPB")
    await _filing(db_session, CPB, FY2025_ACCN, 2025, date(2025, 8, 3))
    db_session.add(
        _fact(FY2025_ACCN, CARRYING, "cpb:TrademarksNotYetMappedMember",
              date(2025, 8, 3), 1_000_000, "unmapped-member")
    )
    await db_session.flush()
    await seed_concept_mappings(db_session)

    counts = await canonicalize_issuer(db_session, CPB)

    assert counts["member_facts_added"] == 0
    assert (
        await db_session.execute(select(CanonicalMemberFact))
    ).scalars().all() == []


@requires_db
async def test_zts_impairment_never_reaches_the_member_store(db_session) -> None:
    """The `issuers` allow-list, end to end.

    ZTS tags impairment consolidated-only (live-verified FY2020-FY2025, never
    with a member). Were this fact to resolve, a company-level write-down would
    be charged against one brand — the specific misstatement the allow-list
    exists to prevent. Its carrying value still resolves, so the suppression is
    concept-scoped, not a filer-wide blackout.
    """
    await _issuer(db_session, ZTS, "ZTS")
    await _filing(db_session, ZTS, "0001555280-26-000011", 2025, date(2025, 12, 31))
    db_session.add_all(
        [
            _fact("0001555280-26-000011", IMPAIRMENT, "zts:BrandsMember",
                  date(2025, 12, 31), 5_000_000, "zts-impair"),
            _fact("0001555280-26-000011", CARRYING, "zts:BrandsMember",
                  date(2025, 12, 31), 900_000_000, "zts-carrying"),
        ]
    )
    await db_session.flush()
    await seed_concept_mappings(db_session)

    await canonicalize_issuer(db_session, ZTS)

    concepts = {
        r.canonical_concept
        for r in (
            await db_session.execute(
                select(CanonicalMemberFact).where(CanonicalMemberFact.superseded.is_(False))
            )
        ).scalars()
    }
    assert concepts == {"brand_intangible_carrying_value"}


@requires_db
async def test_member_selection_is_idempotent(db_session) -> None:
    """`pipeline/run.py` is a daily cron over the same facts: a writer without an
    idempotency key accumulates a row per night."""
    await _cpb_two_years(db_session)

    first = await canonicalize_issuer(db_session, CPB)
    second = await canonicalize_issuer(db_session, CPB)

    assert first["member_facts_added"] == 3
    assert second["member_facts_added"] == 0
    assert second["member_facts_superseded"] == 0


@requires_db
async def test_a_restated_member_value_supersedes_rather_than_mutates(db_session) -> None:
    """An amendment restating a brand's carrying value follows canonical_facts'
    supersession contract one dimension deeper: a NEW row becomes current and the
    prior row is kept, so earlier provenance still resolves (AD-2, AD-6, AD-19).
    """
    await _cpb_two_years(db_session)
    await canonicalize_issuer(db_session, CPB)

    amendment = "0000016732-25-000999"
    await _filing(db_session, CPB, amendment, 2025, date(2025, 8, 3), form_type="10-K/A")
    db_session.add(
        _fact(amendment, CARRYING, "cpb:TrademarksKettleBrandMember",
              date(2025, 8, 3), 370_000_000, "kettle-restated")
    )
    await db_session.flush()

    counts = await canonicalize_issuer(db_session, CPB)
    assert counts["member_facts_superseded"] == 1

    rows = (
        await db_session.execute(
            select(CanonicalMemberFact).where(
                CanonicalMemberFact.member_key == "kettle",
                CanonicalMemberFact.fiscal_year == 2025,
            )
        )
    ).scalars().all()
    current = [r for r in rows if not r.superseded]
    retired = [r for r in rows if r.superseded]
    assert len(current) == 1 and current[0].value == 370_000_000
    assert len(retired) == 1 and retired[0].superseded_by == current[0].id


@requires_db
async def test_member_facts_never_leak_into_canonical_facts(db_session) -> None:
    """AD-3 rule 0 still holds now that the member path is live: these concepts
    exist only in the member store, never in the undimensioned one."""
    await _cpb_two_years(db_session)
    await canonicalize_issuer(db_session, CPB)

    undimensioned = {
        f.canonical_concept
        for f in (await db_session.execute(select(CanonicalFact))).scalars()
    }
    assert not {c for c in undimensioned if c.startswith(("brand_", "trade_names_"))}


@requires_db
async def test_the_audit_projection_records_the_axis(db_session) -> None:
    """concept_mappings is what lets a stored fact be traced to its rule. A
    dimensioned rule whose axis is missing there cannot be told apart from the
    undimensioned rule sharing its source concept."""
    await _cpb_two_years(db_session)

    rows = (
        await db_session.execute(
            select(ConceptMapping).where(
                ConceptMapping.canonical_concept == "brand_intangible_impairment"
            )
        )
    ).scalars().all()
    assert rows, "the dimensioned rules must be projected, not only the undimensioned ones"
    assert all(r.axis == AXIS for r in rows)
