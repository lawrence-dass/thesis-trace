"""CPB's segment concepts, mapped across both tag switches (Story 13.5a).

DB tests run the real `canonicalize_issuer` over seeded raw facts shaped like the
dev store's (single-axis segment contexts; cpb: custom tags under taxonomy `cpb`)
and assert the ROW COUNT before anything about the rows.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
import yaml
from sqlalchemy import select

import canonicalization.mappings.engine as mapping_engine
from app.models import CanonicalMemberFact, DataQualityIssue, Filing, Issuer, RawFact
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import (
    BRAND_MEMBERS,
    MEMBER_RESOLUTION,
    SEGMENT_MEMBERS,
    is_excluded,
    resolve_brand_identity,
    seed_concept_mappings,
)
from tests.conftest import requires_db
from tests.test_brand_member_mapping import registered_exclusion_spec  # noqa: F401 — fixture

CPB = "0000016732"
SEG = "us-gaap:StatementBusinessSegmentsAxis"
MEALS = "cpb:MealsBeveragesMember"
SNACKS = "cpb:SnacksMember"
CORPORATE = "us-gaap:CorporateAndOtherMember"
FYE = {2023: date(2023, 7, 30), 2024: date(2024, 7, 28), 2025: date(2025, 8, 3)}
ACCN = {2023: "0000016732-23-000109", 2024: "0000016732-24-000130", 2025: "0000016732-25-000112"}


# --- the declarations (AC 1, AC 2, AC 3) -------------------------------------


def test_cpb_segments_are_declared_as_segments_never_as_brands() -> None:
    segments = {(m.issuer_cik, m.member_key): m for m in SEGMENT_MEMBERS}
    assert set(segments) == {(CPB, "meals_beverages"), (CPB, "snacks")}
    assert {m.kind for m in segments.values()} == {"segment"}
    assert {m.axis for m in segments.values()} == {SEG}
    brand_keys = {(m.issuer_cik, m.member_key) for m in BRAND_MEMBERS}
    assert not set(segments) & brand_keys
    # 13.4a's resolver never sees a segment: it is not a brand, it is unresolved.
    assert not resolve_brand_identity(CPB, "snacks", {SEG: "snacks"})


@pytest.mark.parametrize(
    "taxonomy, concept, member, expected",
    [
        ("us-gaap", "Revenues", MEALS, ("segment_revenue", "meals_beverages")),
        ("us-gaap", "OperatingIncomeLoss", SNACKS, ("segment_operating_earnings", "snacks")),
        ("cpb", "SegmentOperatingEarnings", MEALS, ("segment_operating_earnings", "meals_beverages")),
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", SNACKS, ("segment_capex", "snacks")),
        ("cpb", "SegmentExpenditureAdditionToPPE", MEALS, ("segment_capex", "meals_beverages")),
    ],
)
def test_both_eras_of_each_switch_resolve_to_one_concept(taxonomy, concept, member, expected) -> None:
    assert MEMBER_RESOLUTION[(CPB, taxonomy, concept, SEG, member)] == expected


def test_a_custom_tag_resolves_only_under_its_own_taxonomy() -> None:
    assert (CPB, "us-gaap", "SegmentOperatingEarnings", SEG, MEALS) not in MEMBER_RESOLUTION


def test_no_brand_member_resolves_on_cpbs_segment_axis() -> None:
    on_segment_axis = {v for k, v in MEMBER_RESOLUTION.items() if k[0] == CPB and k[3] == SEG}
    assert len(on_segment_axis) == 6  # 3 concepts x 2 segments
    assert {member_key for _, member_key in on_segment_axis} == {"meals_beverages", "snacks"}


def test_corporate_and_reconciling_members_are_excluded_on_the_segment_axis_only() -> None:
    assert is_excluded(CPB, "Revenues", SEG, CORPORATE)
    assert is_excluded(CPB, "OperatingIncomeLoss", SEG, "us-gaap:CorporateNonSegmentMember")
    assert is_excluded(CPB, "OperatingIncomeLoss", SEG, "us-gaap:RestructuringChargesMember")
    # Scoped: the reconciling exclusion was observed on operating earnings only.
    assert not is_excluded(CPB, "Revenues", SEG, "us-gaap:RestructuringChargesMember")
    assert not is_excluded(CPB, "Revenues", "us-gaap:SomeOtherAxis", CORPORATE)


# --- the loader (AC 2) -------------------------------------------------------


def _with_segments(spec_file, data, members) -> None:
    data["segment_members"][CPB]["members"].update(members)
    spec_file.write_text(yaml.safe_dump(data, sort_keys=False))


def test_the_loader_rejects_a_segment_that_is_also_a_brand(registered_exclusion_spec) -> None:  # noqa: F811
    spec_file, data = registered_exclusion_spec
    _with_segments(spec_file, data, {"kettle": {"label": "Kettle", "aliases": ["cpb:KettleSegMember"]}})
    with pytest.raises(ValueError, match="also declared a brand member"):
        mapping_engine.load_mapping_spec()


def test_the_loader_rejects_a_segment_on_an_axis_no_rule_reads(registered_exclusion_spec) -> None:  # noqa: F811
    spec_file, data = registered_exclusion_spec
    data["segment_members"]["0001555280"] = {
        "axis": SEG, "members": {"us": {"label": "United States", "aliases": ["zts:USMember"]}},
    }
    spec_file.write_text(yaml.safe_dump(data, sort_keys=False))
    with pytest.raises(ValueError, match="no dimensioned rule reads"):
        mapping_engine.load_mapping_spec()


def test_the_loader_rejects_an_alias_both_segment_and_excluded(registered_exclusion_spec) -> None:  # noqa: F811
    spec_file, data = registered_exclusion_spec
    _with_segments(spec_file, data, {"corporate": {"label": "Corporate", "aliases": [CORPORATE]}})
    with pytest.raises(ValueError, match="both mapped"):
        mapping_engine.load_mapping_spec()


# --- canonicalization (AC 1, AC 3) -------------------------------------------


def _raw(year_filed: int, taxonomy: str, concept: str, member: str, year: int, value: float) -> RawFact:
    return RawFact(
        accession_number=ACCN[year_filed],
        taxonomy=taxonomy,
        concept=concept,
        unit="USD",
        period_start=date(year - 1, 8, 1),
        period_end=FYE[year],
        value=value,
        dimensions={SEG: member},
        source="inline_xbrl",
        content_hash=f"{concept[:20]}-{member[-14:]}-{year}-f{year_filed}",
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@requires_db
async def test_canonicalization_lands_each_segment_year_once_across_the_switch(db_session) -> None:
    db_session.add(Issuer(cik=CPB, ticker="CPB", name="CPB Inc", sector="Consumer"))
    await db_session.flush()
    for year in (2023, 2024, 2025):
        db_session.add(Filing(accession_number=ACCN[year], issuer_cik=CPB, form_type="10-K",
                              filing_date=date(year, 9, 20), fiscal_year=year,
                              fiscal_year_end=FYE[year]))
    await db_session.flush()
    db_session.add_all([
        # Operating earnings: the old tag as originally filed for FY2023-24 ...
        _raw(2023, "us-gaap", "OperatingIncomeLoss", MEALS, 2023, 1_000),
        _raw(2024, "us-gaap", "OperatingIncomeLoss", MEALS, 2024, 1_100),
        # ... and the new tag in FY2025's 10-K: two equal comparatives + its own year.
        _raw(2025, "cpb", "SegmentOperatingEarnings", MEALS, 2023, 1_000),
        _raw(2025, "cpb", "SegmentOperatingEarnings", MEALS, 2024, 1_100),
        _raw(2025, "cpb", "SegmentOperatingEarnings", MEALS, 2025, 1_200),
        _raw(2025, "us-gaap", "Revenues", SNACKS, 2025, 4_000),
        # Corporate on the same axis: known, excluded, silent.
        _raw(2025, "us-gaap", "Revenues", CORPORATE, 2025, 5),
    ])
    await db_session.flush()
    await seed_concept_mappings(db_session)

    counts = await canonicalize_issuer(db_session, CPB)
    rows = (await db_session.execute(
        select(CanonicalMemberFact).where(CanonicalMemberFact.superseded.is_(False))
        .order_by(CanonicalMemberFact.canonical_concept, CanonicalMemberFact.fiscal_year)
    )).scalars().all()
    assert len(rows) == 4, counts
    assert [(r.canonical_concept, r.member_key, r.fiscal_year, r.value) for r in rows] == [
        ("segment_operating_earnings", "meals_beverages", 2023, 1_000),
        ("segment_operating_earnings", "meals_beverages", 2024, 1_100),
        ("segment_operating_earnings", "meals_beverages", 2025, 1_200),
        ("segment_revenue", "snacks", 2025, 4_000),
    ]
    # In each overlap year the ORIGINALLY FILED old-tag fact wins (AD-3)...
    by_year = {r.fiscal_year: r for r in rows if r.canonical_concept == "segment_operating_earnings"}
    assert by_year[2023].accession_number == ACCN[2023]
    assert by_year[2024].accession_number == ACCN[2024]
    assert by_year[2025].member_as_filed == MEALS
    # ...and neither the equal pair nor Corporate raises any issue.
    issues = (await db_session.execute(select(DataQualityIssue))).scalars().all()
    assert [i.issue_type for i in issues] == []
