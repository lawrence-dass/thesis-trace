"""Story 13.1 — the dimensional-fact contract (AD-3 rule 0, AD-4 extension).

A DIMENSIONED fact is a different fact from its undimensioned counterpart. This
file pins both halves of that: dimensions are part of a fact's IDENTITY (the
content hash), and a dimensioned fact is never a CANDIDATE for an undimensioned
canonical concept.

None of this is reachable in production yet — the only live ingestion source,
the SEC Company Facts API, carries no dimensional data whatsoever (verified live,
`company_facts_api_carries_no_segment_dimensions`). That is precisely why it
needs pinning now: AD-3's original rule (2), "least-dimensioned/most-specific
member", sat in the architecture spine from 2026-07-19 and was never implemented,
because nothing ever produced a dimension to exercise it. It read as enforced for
over a year. Story 13.2 makes it reachable; this guard lands first.

Full analysis: `engineering-findings.yaml#dimensioned_facts_would_contaminate_
consolidated_canonical_facts`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, DataQualityIssue, RawFact
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import _content_hash, _serialize_dimensions, parse_company_facts
from raw_store.repository import persist_company_facts
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"

_SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"


async def _ingest(db_session) -> str:
    parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
    await persist_company_facts(db_session, parsed, ticker="SHOP")
    await seed_concept_mappings(db_session)
    return parsed.cik


# --- Identity: dimensions belong in the content hash -------------------------


def test_undimensioned_hashes_are_unchanged_by_this_story():
    """Adding dimensions to the hash must not re-key the existing raw store.

    `raw_facts` is unique on (accession_number, content_hash), so a shifted hash
    makes every already-ingested fact look new. The expected value here is
    computed from the payload format as it existed BEFORE this story, written out
    literally rather than copied from the new implementation — so this fails if
    the undimensioned payload ever changes shape, including by appending an empty
    dimensions segment.
    """
    legacy_payload = "us-gaap|Revenues|USD|2024-01-01|2024-12-31|100.0"
    expected = hashlib.sha256(legacy_payload.encode()).hexdigest()

    assert _content_hash("us-gaap", "Revenues", "USD", "2024-01-01", "2024-12-31", 100.0) == expected
    # Explicitly-empty dimensions must hash identically to absent ones.
    assert (
        _content_hash("us-gaap", "Revenues", "USD", "2024-01-01", "2024-12-31", 100.0, {})
        == expected
    )


def test_two_members_differing_only_by_member_hash_differently():
    """The collision this closes: same concept, period and VALUE, different member.

    Two segments reporting an identical figure is ordinary — equal goodwill, a
    round number, a small segment matching another. Before this story both rows
    produced one hash and the second was silently dropped on the unique
    constraint.
    """
    args = ("us-gaap", "Revenues", "USD", "2024-01-01", "2024-12-31", 100.0)
    meals = _content_hash(*args, {_SEGMENT_AXIS: "cpb:MealsBeveragesMember"})
    snacks = _content_hash(*args, {_SEGMENT_AXIS: "cpb:SnacksMember"})
    consolidated = _content_hash(*args)

    assert len({meals, snacks, consolidated}) == 3, (
        "identical values under different members must remain distinct facts"
    )


def test_dimension_serialization_is_order_independent():
    """An XBRL context's dimensions are a SET of axis/member pairs, not a sequence.

    Instance documents do not guarantee their order, so two parses of the same
    context must not produce two different facts.
    """
    a = {_SEGMENT_AXIS: "cpb:SnacksMember", "us-gaap:ProductOrServiceAxis": "cpb:SoupMember"}
    b = dict(reversed(list(a.items())))

    assert _serialize_dimensions(a) == _serialize_dimensions(b)
    assert _content_hash("us-gaap", "Revenues", "USD", None, "2024-12-31", 1.0, a) == _content_hash(
        "us-gaap", "Revenues", "USD", None, "2024-12-31", 1.0, b
    )


def test_dimension_serialization_does_not_collide_on_separator_characters():
    """Dimension identity must not depend on delimiters being absent from values."""
    base = {
        "taxonomy": "us-gaap",
        "concept": "Revenues",
        "unit": "USD",
        "start": "2024-01-01",
        "end": "2024-12-31",
        "value": 100.0,
    }
    dimensions_with_delimiters = {"axis": "member;other=member"}
    dimensions_as_two_entries = {"axis": "member", "other": "member"}

    assert _serialize_dimensions(dimensions_with_delimiters) != _serialize_dimensions(
        dimensions_as_two_entries
    )
    assert _content_hash(**base, dimensions=dimensions_with_delimiters) != _content_hash(
        **base, dimensions=dimensions_as_two_entries
    )


# --- Candidacy: the contamination guard, both failure modes ------------------


@requires_db
async def test_parsed_dimensions_survive_persistence(db_session) -> None:
    """The field must be LIVE, not merely declared.

    `persist_company_facts` did not map `dimensions` when this story began, so a
    parsed member would have been dropped at the DB boundary while the parse
    itself looked correct — Story 13.2 would then have ingested dimensioned facts
    into a NULL column and found nothing wrong. Exactly the
    declared-but-unexercised shape AD-3 rule 0 exists to close, so it is pinned
    rather than assumed.
    """
    from dataclasses import replace

    parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
    dims = {_SEGMENT_AXIS: "shop:MerchantSolutionsMember"}
    seed = parsed.facts[0]
    # The real hash for the dimensioned variant — `content_hash` is String(64),
    # exactly a sha256 hex digest, so a suffixed placeholder would not fit.
    dimensioned_hash = _content_hash(
        seed.taxonomy, seed.concept, seed.unit, seed.period_start, seed.period_end, seed.value, dims
    )
    assert dimensioned_hash != seed.content_hash
    parsed.facts.append(replace(seed, dimensions=dims, content_hash=dimensioned_hash))

    await persist_company_facts(db_session, parsed, ticker="SHOP")

    stored = (
        await db_session.execute(
            select(RawFact).where(RawFact.content_hash == dimensioned_hash)
        )
    ).scalars().one()
    assert stored.dimensions == dims, "dimensions were dropped between parse and persistence"


@requires_db
async def test_dimensioned_fact_does_not_raise_ambiguity_against_consolidated(db_session) -> None:
    """MODE A (loud): a dimensioned fact DISAGREEING with the consolidated total.

    Without the guard this lands in the same candidate group, the rules cannot
    separate two originally-filed candidates, and every affected filer-year opens
    an `ambiguous_selection` — which would also suppress the canonical fact
    entirely, so the consolidated figure disappears from the product.
    """
    cik = await _ingest(db_session)
    baseline = await canonicalize_issuer(db_session, cik)
    assert baseline["ambiguities_flagged"] == 0

    db_session.add(
        RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Revenues",
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            value=4_200_000_000,  # a segment's slice, smaller than consolidated
            dimensions={_SEGMENT_AXIS: "shop:MerchantSolutionsMember"},
            source="inline_xbrl",
            content_hash="segment-revenue-fy2024",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()

    counts = await canonicalize_issuer(db_session, cik)
    assert counts["ambiguities_flagged"] == 0, (
        "a segment-level fact must not compete with the consolidated total"
    )
    assert not (
        await db_session.execute(
            select(DataQualityIssue).where(
                DataQualityIssue.issue_type == "ambiguous_selection"
            )
        )
    ).scalars().all()

    total_revenue = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "revenue",
                CanonicalFact.fiscal_year == 2024,
                CanonicalFact.superseded.is_(False),
            )
        )
    ).scalars().one()
    assert total_revenue.value != 4_200_000_000, "segment value must never become consolidated"


@requires_db
async def test_dimensioned_fact_does_not_become_canonical_when_sole_candidate(db_session) -> None:
    """MODE B (silent) — the reason "it would just get flagged" is not an answer.

    The ambiguity check only fires when two candidates DISAGREE. A dimensioned
    fact that is the ONLY candidate for a (concept, fiscal_year) has nothing to
    disagree with, so it sails through and BECOMES the canonical consolidated
    value with no flag raised anywhere. Same shape as
    `otex_capex_sign_error_fy2007_fy2009`, where a lone wrong-signed candidate
    passed for the same reason.

    Uses a fiscal year the fixture does not cover, so the dimensioned row is
    genuinely alone in its group.
    """
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)

    orphan_year = 2019
    assert not (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "revenue",
                CanonicalFact.fiscal_year == orphan_year,
            )
        )
    ).scalars().all(), "fixture unexpectedly covers this year; pick another"

    db_session.add(
        RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Revenues",
            unit="USD",
            period_start=date(orphan_year, 1, 1),
            period_end=date(orphan_year, 12, 31),
            value=1_234_000_000,
            dimensions={_SEGMENT_AXIS: "shop:SubscriptionSolutionsMember"},
            source="inline_xbrl",
            content_hash="lone-segment-revenue-fy2019",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()

    counts = await canonicalize_issuer(db_session, cik)

    assert not (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "revenue",
                CanonicalFact.fiscal_year == orphan_year,
            )
        )
    ).scalars().all(), (
        "a lone dimensioned fact silently became the canonical consolidated value — "
        "no ambiguity is raised because it has nothing to disagree with"
    )
    assert counts["ambiguities_flagged"] == 0, "and it does so without raising any flag"
