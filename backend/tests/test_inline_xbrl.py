"""Story 13.2 — Inline XBRL instance ingestion for dimensional facts (AD-4).

The expected values here are not invented. Every one was recorded live on
2026-09-08 by the three gate spikes that scoped Epic 13, and re-confirmed against
fresh fetches on 2026-09-10 before these fixtures were trimmed. That is the point
of asserting them: a parser regression shows up as a DIFF AGAINST A RECORDED
ANSWER rather than as a plausible-looking empty result, which is the failure mode
this project keeps hitting (a 12 KB amendment instance is visually identical to a
failed download).

Sources: `segment_data_reachable_but_raos_is_not_a_segment`,
`cpb_segment_members_stable_but_tags_switch`,
`segment_and_brand_intangible_tagging_across_filers`,
`acquisition_epic_scoped_to_us_gaap_filers`.

FIXTURE HONESTY (Story 13.6's standing warning applies to this story too). These
fixtures are TRIMMED: every numeric fact on the four dimensional axes below is
kept, plus at most 12 undimensioned contexts per filer. Dropped: TextBlock
elements (one CPB footnote alone is 295 KB of embedded HTML), non-numeric facts,
and undimensioned contexts beyond the cap. So they CAN exercise segment and
brand-intangible parsing, member recovery, and dimension identity; they CANNOT
exercise full-coverage per-year canonicalization, which is not this story's job.
"""

from __future__ import annotations

import pathlib
from datetime import date

import pytest
from sqlalchemy import select

from ingestion.inline_xbrl import parse_contexts, parse_instance
from tests.conftest import requires_db
from xml.etree import ElementTree

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"

#: Context counts in the FULL instances as fetched live (2026-09-08, re-confirmed
#: 2026-09-10). Asserted against the untrimmed documents only — kept here as the
#: recorded answer a future live re-fetch should still produce.
LIVE_CONTEXT_COUNTS = {"cpb": 601, "qsr": 562, "zts": 473, "shop": 333, "cp": 640}

#: Segment members per filer, verbatim. The KIND differs per filer and that is
#: the finding, not an accident: CPB reports product categories, ZTS geographies,
#: QSR individual acquired BRANDS. Cross-filer segment comparison is therefore
#: meaningless, which is why Story 13.5 is within-filer only.
EXPECTED_SEGMENT_MEMBERS = {
    "cpb": {"cpb:MealsBeveragesMember", "cpb:SnacksMember", "us-gaap:CorporateAndOtherMember"},
    "qsr": {
        "qsr:BurgerKingMember",
        "qsr:TimHortonsMember",
        "qsr:PopeyesLouisianaKitchenMember",
        "qsr:FirehouseSubsMember",
        "qsr:FirehouseSubsRestaurantsMember",
        "qsr:InternationalSegmentMember",
        "qsr:RestaurantHoldingsMember",
    },
    "zts": {
        "zts:UnitedStatesSegmentMember",
        "zts:InternationalSegmentMember",
        "zts:ManufacturingResearchCorporateMember",
        "us-gaap:AllOtherSegmentsMember",
    },
    # Single-segment filers. NOT a parse failure — verified live: SHOP and CP
    # have no StatementBusinessSegmentsAxis at all. The epic resolves
    # insufficient_data for them by design (AD-16), so an empty set here is the
    # correct answer and must stay distinguishable from a broken parse.
    "shop": set(),
    "cp": set(),
}


def _facts(name: str):
    return parse_instance(
        (FIXTURES / f"{name}_instance.xml").read_text(),
        accession_number="0000000000-00-000000",
        fiscal_year=2025,
    )


def _members(facts, axis: str) -> set[str]:
    return {f.dimensions[axis] for f in facts if f.dimensions and axis in f.dimensions}


@pytest.mark.parametrize("filer", sorted(EXPECTED_SEGMENT_MEMBERS))
def test_segment_members_match_the_live_gate_findings(filer: str) -> None:
    """The member list per filer, exactly as recorded live on 2026-09-08."""
    assert _members(_facts(filer), SEGMENT_AXIS) == EXPECTED_SEGMENT_MEMBERS[filer]


def test_qsr_reports_each_acquired_brand_as_a_segment() -> None:
    """QSR is the epic's lead test case, and this is why.

    It reports Burger King, Tim Hortons, Popeyes and Firehouse Subs AS segments,
    so "how is this acquisition performing" is directly answerable. CPB is the
    motivating filer but buries Rao's inside Meals & Beverages, which is what
    redirected the epic onto the intangibles axis.
    """
    members = _members(_facts("qsr"), SEGMENT_AXIS)
    for brand in ("BurgerKing", "TimHortons", "PopeyesLouisianaKitchen", "FirehouseSubs"):
        assert any(brand in m for m in members), f"{brand} missing from QSR's segment axis"


def test_dimensions_are_preserved_verbatim_not_normalized() -> None:
    """Story 13.3 maps these; this story must not prettify them first.

    Both the axis and the member keep the filer's own qualified name, prefix
    included. A custom `cpb:` tag is filer-specific by construction, so stripping
    or normalizing the prefix would destroy exactly the information the per-filer
    mapping needs.
    """
    members = _members(_facts("cpb"), SEGMENT_AXIS)
    assert "cpb:MealsBeveragesMember" in members, "custom prefix was normalized away"
    assert "us-gaap:CorporateAndOtherMember" in members, "standard prefix was normalized away"


def test_brand_intangible_axis_is_recovered_for_cpb() -> None:
    """The axis the epic actually builds on: Rao's is here, not on the segment axis."""
    axis = "us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis"
    members = _members(_facts("cpb"), axis)
    assert members, "no brand-intangible members recovered"
    assert any("Raos" in m for m in members), f"Rao's trademark missing; got {sorted(members)}"


def test_a_context_can_carry_several_axes_at_once() -> None:
    """Dimensions are a dict, not a single axis/member pair.

    CPB pairs `srt:MajorCustomersAxis` with two concentration-risk axes on one
    context. A parser modelling dimensions as one pair would silently keep only
    the last, changing the fact's identity.
    """
    contexts = parse_contexts(
        ElementTree.fromstring((FIXTURES / "cpb_instance.xml").read_text())
    )
    multi = [c for c in contexts.values() if c.dimensions and len(c.dimensions) > 1]
    assert multi, "fixture carries no multi-axis context; it cannot exercise this"


def test_facts_differing_only_by_member_hash_differently_on_real_filings() -> None:
    """Story 13.1's identity contract, exercised on a real filing.

    Two members reporting an equal value must remain two facts. Before 13.1 they
    collided on (accession_number, content_hash) and one was silently dropped.

    Deliberately NOT "every fact has a unique hash". An instance document tags
    the same value repeatedly — QSR's Carrols goodwill appears three times, once
    each in a statement, a footnote and a reconciliation, all on one contextRef
    and identical in every field. Those ARE one fact, and hashing them
    identically is what makes ingestion idempotent. The contract is that facts
    differing in their DIMENSIONS differ in hash, not that no hash repeats.
    """
    facts = [f for f in _facts("qsr") if f.dimensions]
    by_identity: dict[tuple, set[str]] = {}
    for f in facts:
        key = (f.taxonomy, f.concept, f.unit, f.period_start, f.period_end, f.value)
        by_identity.setdefault(key, set()).add(f.content_hash)

    # Where the same concept/period/value appears under DIFFERENT members, the
    # hashes must differ — one per distinct dimension map, never fewer.
    collisions = []
    for key, hashes in by_identity.items():
        members = {
            tuple(sorted(f.dimensions.items()))
            for f in facts
            if (f.taxonomy, f.concept, f.unit, f.period_start, f.period_end, f.value) == key
        }
        if len(hashes) != len(members):
            collisions.append((key, len(members), len(hashes)))
    assert not collisions, f"distinct member sets sharing a hash: {collisions[:3]}"


def test_the_amendment_is_distinguishable_from_a_failed_download() -> None:
    """The trap that bit twice in one session on 2026-09-08.

    SHOP's 0001594805-26-000011 is a 10-K/A whose instance carries only the
    amended portion: ~12 KB, 7 contexts, and it makes the filer look like it
    reports nothing. Selecting by `max(accession_number)` over '10-K%' returns
    exactly this document instead of the real 10-K (0001594805-26-000007).

    The assertion is comparative on purpose: an amendment parsing to "almost
    nothing" is correct behaviour, so the guard has to be that the ORIGINAL
    parses to substantially more, which is what distinguishes the two.
    """
    original = _facts("shop")
    amendment = _facts("shop_amendment")
    assert len(amendment) < len(original) / 10, (
        f"amendment ({len(amendment)} facts) is not clearly distinguishable from the "
        f"original ({len(original)} facts) — the max(accession_number) trap is undetectable"
    )


def test_undimensioned_facts_are_parsed_too_not_dropped() -> None:
    """AD-4's source reconciliation needs both sides present to compare.

    Dimensioned facts are never compared to their undimensioned counterparts
    (AD-3 rule 0), but an undimensioned INLINE fact overlapping a Company Facts
    fact is a genuine same-identity conflict, and it cannot be detected if this
    parser silently discards undimensioned facts.
    """
    facts = _facts("cpb")
    assert any(f.dimensions is None for f in facts), "undimensioned facts were dropped"
    assert any(f.dimensions for f in facts), "dimensioned facts were dropped"


# --- AD-4 same-identity source reconciliation --------------------------------


async def _seed_filing(db_session, accn: str = "0000016732-25-000112"):
    from app.models import Filing, Issuer
    from datetime import date as _date

    db_session.add(Issuer(cik="0000016732", ticker="CPB", name="Campbell's"))
    await db_session.flush()
    db_session.add(
        Filing(
            accession_number=accn,
            issuer_cik="0000016732",
            form_type="10-K",
            filing_date=_date(2025, 9, 1),
            fiscal_year=2025,
            fiscal_year_end=_date(2025, 8, 3),
        )
    )
    await db_session.flush()
    return accn


def _fact(**kw):
    from ingestion.company_facts import ParsedFact, _content_hash

    base = dict(
        accession_number=kw.pop("accession_number"),
        taxonomy="us-gaap",
        concept="Revenues",
        unit="USD",
        period_start="2024-07-29",
        period_end="2025-08-03",
        value=10_253_000_000.0,
        fiscal_year=2025,
        source="inline_xbrl",
        dimensions=None,
    )
    base.update(kw)
    return ParsedFact(
        **base,
        content_hash=_content_hash(
            base["taxonomy"],
            base["concept"],
            base["unit"],
            base["period_start"],
            base["period_end"],
            base["value"],
            base["dimensions"],
        ),
    )


@requires_db
async def test_company_facts_wins_a_same_identity_conflict_and_raises_source_conflict(db_session):
    """AD-4: Inline supplies what Company Facts omits; it never silently overrides.

    `issue_type = 'source_conflict'` has been a declared value in app/models.py
    since Epic 1 with no writer anywhere — another declared-but-dead mechanism.
    This is its first emitter.
    """
    from app.models import DataQualityIssue, RawFact
    from raw_store.repository import persist_inline_facts

    accn = await _seed_filing(db_session)
    primary = _fact(accession_number=accn, source="company_facts")
    db_session.add(
        RawFact(
            accession_number=accn,
            taxonomy=primary.taxonomy,
            concept=primary.concept,
            unit=primary.unit,
            period_start=date(2024, 7, 29),
            period_end=date(2025, 8, 3),
            value=primary.value,
            source="company_facts",
            content_hash=primary.content_hash,
        )
    )
    await db_session.flush()

    # Same identity, DIFFERENT value, from Inline.
    counts = await persist_inline_facts(
        db_session, [_fact(accession_number=accn, value=9_999_000_000.0)], accession_number=accn
    )

    assert counts["source_conflicts"] == 1
    assert counts["raw_facts_added"] == 0, "the Inline value must not be written"

    issue = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.issue_type == "source_conflict")
        )
    ).scalars().one()
    assert issue.detail["company_facts_value"] == 10_253_000_000.0
    assert issue.detail["inline_xbrl_value"] == 9_999_000_000.0

    stored = (
        await db_session.execute(select(RawFact).where(RawFact.source == "company_facts"))
    ).scalars().all()
    assert len(stored) == 1 and float(stored[0].value) == 10_253_000_000.0


@requires_db
async def test_a_dimensioned_fact_is_never_reconciled_against_its_undimensioned_peer(db_session):
    """AD-3 rule 0 at the ingestion boundary.

    A segment's revenue differs from consolidated revenue by design. Treating
    that as a source conflict would open a spurious issue for every segment of
    every filer — and suppress the segment fact, which is the whole point of
    this story.
    """
    from app.models import DataQualityIssue, RawFact
    from raw_store.repository import persist_inline_facts

    accn = await _seed_filing(db_session)
    primary = _fact(accession_number=accn, source="company_facts")
    db_session.add(
        RawFact(
            accession_number=accn,
            taxonomy=primary.taxonomy,
            concept=primary.concept,
            unit=primary.unit,
            period_start=date(2024, 7, 29),
            period_end=date(2025, 8, 3),
            value=primary.value,
            source="company_facts",
            content_hash=primary.content_hash,
        )
    )
    await db_session.flush()

    segment = _fact(
        accession_number=accn,
        value=4_100_000_000.0,  # a segment slice — smaller, and correctly so
        dimensions={SEGMENT_AXIS: "cpb:MealsBeveragesMember"},
    )
    counts = await persist_inline_facts(db_session, [segment], accession_number=accn)

    assert counts["source_conflicts"] == 0, "a segment fact is not a conflicting measurement"
    assert counts["raw_facts_added"] == 1, "the segment fact must be stored"
    assert not (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.issue_type == "source_conflict")
        )
    ).scalars().all()


@requires_db
async def test_reconciliation_is_idempotent_across_nightly_runs(db_session):
    """`pipeline/run.py` is a daily cron over the same inputs.

    A writer without an idempotency key accumulates one row per night, and the
    UI surfaces every non-dismissed issue — so the same warning would appear N
    times after N days. Dedup ignores STATUS so a dismissed conflict is not
    resurrected.
    """
    from app.models import DataQualityIssue
    from raw_store.repository import persist_inline_facts

    accn = await _seed_filing(db_session)
    from app.models import RawFact

    primary = _fact(accession_number=accn, source="company_facts")
    db_session.add(
        RawFact(
            accession_number=accn,
            taxonomy=primary.taxonomy,
            concept=primary.concept,
            unit=primary.unit,
            period_start=date(2024, 7, 29),
            period_end=date(2025, 8, 3),
            value=primary.value,
            source="company_facts",
            content_hash=primary.content_hash,
        )
    )
    await db_session.flush()

    inline = [
        _fact(accession_number=accn, value=9_999_000_000.0),
        _fact(accession_number=accn, dimensions={SEGMENT_AXIS: "cpb:SnacksMember"}),
    ]
    first = await persist_inline_facts(db_session, inline, accession_number=accn)
    second = await persist_inline_facts(db_session, inline, accession_number=accn)

    assert first["raw_facts_added"] == 1 and second["raw_facts_added"] == 0
    assert first["source_conflicts"] == 1 and second["source_conflicts"] == 0
    issues = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.issue_type == "source_conflict")
        )
    ).scalars().all()
    assert len(issues) == 1, f"one conflict accumulated into {len(issues)} rows"
