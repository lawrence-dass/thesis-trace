"""Axis/member-aware mapping and its store (Story 13.3).

Story 13.1 established the dimensional-fact CONTRACT (AD-3 rule 0: a dimensioned
fact is never a candidate for an undimensioned canonical concept) and
test_dimensional_fact_contract.py guards it. This file guards the layer above:
which canonical concept a dimensioned fact resolves to, for which filer, and
where it can be stored.

Every expectation here is pinned to a value read out of a real filing during
story_13_3_brand_member_live_verification (CPB, ZTS and QSR, four original 10-K
instances each, FY2022-FY2025), not to the shape of the spec file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models import CanonicalMemberFact
from canonicalization.mappings.engine import (
    BRAND_MEMBERS,
    DIMENSIONED_RULES,
    MEMBER_LABELS,
    MEMBER_RESOLUTION,
    BrandMember,
    DimensionedRule,
    _resolve_members,
)

CPB, ZTS, QSR = "0000016732", "0001555280", "0001618756"
AXIS = "us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis"
CARRYING = "IndefiniteLivedIntangibleAssetsExcludingGoodwill"
IMPAIRMENT = "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill"
ACQUIRED = "IndefinitelivedIntangibleAssetsAcquired"
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db/migrations/versions/e91b7c4d2a05_add_canonical_member_facts.py"
)


def resolve(cik: str, concept: str, member: str) -> tuple[str, str] | None:
    return MEMBER_RESOLUTION.get((cik, "us-gaap", concept, AXIS, member))


# --- the rename finding ------------------------------------------------------


def test_a_filers_renamed_members_collapse_to_one_stable_key() -> None:
    """CPB renames its own members between filings, so a brand is only one brand
    if the mapping says so.

    Kettle carries three different member names across four CPB filings —
    TradeNamesKettleMember (FY2022), TrademarkssKettleMember (FY2023 only, the
    filer's own double-s typo) and TrademarksKettleBrandMember (FY2024-FY2025),
    all three read out of the filings that contain them. Mapping by the newest
    name alone silently loses the earlier years, which is the class the original
    shares_outstanding bug belonged to.
    """
    aliases = [
        "cpb:TradeNamesKettleMember",
        "cpb:TrademarkssKettleMember",
        "cpb:TrademarksKettleBrandMember",
    ]
    assert len(set(aliases)) == 3, "the aliases must actually differ or this proves nothing"
    resolved = {resolve(CPB, CARRYING, alias) for alias in aliases}
    assert resolved == {("brand_intangible_carrying_value", "kettle")}


def test_pacific_foods_singular_and_plural_spellings_are_the_same_brand() -> None:
    """One character apart: cpb:TradeNamePacificFoodsMember (FY2022) vs
    cpb:TrademarksPacificFoodsMember. A pattern-based rule would miss it."""
    assert resolve(CPB, CARRYING, "cpb:TradeNamePacificFoodsMember") == resolve(
        CPB, CARRYING, "cpb:TrademarksPacificFoodsMember"
    ) == ("brand_intangible_carrying_value", "pacific_foods")


# --- one source concept, two meanings ---------------------------------------


def test_the_within_ten_percent_member_is_never_a_brands_carrying_value() -> None:
    """CPB's early-warning disclosure shares its SOURCE CONCEPT with per-brand
    carrying value and is told apart only by its member. It is an aggregate over
    whichever trade names qualify, so attributing it to a brand would invent a
    figure the filing does not state. Both of the filer's spellings are checked."""
    for member in (
        "cpb:TradeNamesCarryingValueWith10OrLessExcessFairValueCoverageMember",
        "cpb:TradeNamesCarryingValueWithTenPercentOrLessExcessFairValueCoverageMember",
    ):
        concept, member_key = resolve(CPB, CARRYING, member)
        assert concept == "trade_names_within_ten_percent_of_impairment"
        assert member_key == "within_ten_percent_coverage"

    # ...and the redirect does not leak the other way: a brand must not resolve
    # the aggregate concept.
    assert resolve(CPB, CARRYING, "cpb:TrademarksAlliedBrandsMember") == (
        "brand_intangible_carrying_value",
        "allied_brands",
    )


# --- per-filer truth, enforced rather than described -------------------------


def test_per_brand_impairment_resolves_for_cpb_only() -> None:
    """Live-verified 2026-09-11: CPB tags impairment per member; ZTS tags it
    consolidated-only under a different concept; QSR tags none at all in four
    filings. Resolving it for ZTS or QSR would charge a company-level write-down
    against a single brand. The spec said so in prose and the engine ignored it
    until `issuers` made the claim executable."""
    assert resolve(CPB, IMPAIRMENT, "cpb:TrademarksSnydersOfHanoverMember") == (
        "brand_intangible_impairment",
        "snyders_of_hanover",
    )
    assert resolve(ZTS, IMPAIRMENT, "zts:BrandsMember") is None
    assert resolve(QSR, IMPAIRMENT, "us-gaap:TradeNamesMember") is None


def test_acquisition_mapping_is_allow_listed_to_the_live_verified_filer() -> None:
    """A generic brand member must not invent acquisition facts for another filer."""
    assert resolve(CPB, ACQUIRED, "cpb:TrademarksRaosMember") == (
        "brand_intangible_acquired",
        "raos",
    )
    assert resolve(ZTS, ACQUIRED, "zts:BrandsMember") is None
    assert resolve(CPB, ACQUIRED, "cpb:TrademarksOtherMember") is None


def test_suppressing_impairment_does_not_suppress_the_filer_entirely() -> None:
    """The allow-list is per CONCEPT, not per filer: ZTS and QSR still resolve
    carrying value per member, which is what Stories 13.4/13.7 present for them."""
    assert resolve(ZTS, CARRYING, "zts:BrandsMember") == (
        "brand_intangible_carrying_value",
        "brands",
    )
    assert resolve(QSR, CARRYING, "us-gaap:FranchiseRightsMember") == (
        "brand_intangible_carrying_value",
        "franchise_rights",
    )


def test_raos_is_mapped_even_though_it_has_never_been_impaired() -> None:
    """Rao's carries value with no impairment through FY2025 — the answer the CPB
    decision packet asked for. The mapping must still admit an impairment for it,
    or a future write-down would silently fail to resolve."""
    assert resolve(CPB, IMPAIRMENT, "cpb:TrademarksRaosMember") == (
        "brand_intangible_impairment",
        "raos",
    )
    assert MEMBER_LABELS["raos"] == "Rao's"


# --- loader guards actually fire --------------------------------------------


def _rule(concept: str) -> DimensionedRule:
    return DimensionedRule(
        canonical_concept=concept,
        source_taxonomy="us-gaap",
        source_concept=CARRYING,
        axis=AXIS,
    )


def test_maps_to_must_name_a_declared_concept() -> None:
    member = BrandMember(
        issuer_cik=CPB, member_key="x", label="X", aliases=("cpb:XMember",), maps_to="nonexistent"
    )
    with pytest.raises(ValueError, match="maps_to"):
        _resolve_members((_rule("brand_intangible_carrying_value"),), (member,))


def test_one_member_name_cannot_belong_to_two_brands() -> None:
    shared = ("cpb:SharedMember",)
    members = (
        BrandMember(issuer_cik=CPB, member_key="first", label="First", aliases=shared),
        BrandMember(issuer_cik=CPB, member_key="second", label="Second", aliases=shared),
    )
    with pytest.raises(ValueError, match="one member name is one brand"):
        _resolve_members((_rule("brand_intangible_carrying_value"),), members)


def test_every_alias_is_unique_within_its_filer() -> None:
    seen: dict[tuple[str, str], str] = {}
    for member in BRAND_MEMBERS:
        for alias in member.aliases:
            key = (member.issuer_cik, alias)
            assert key not in seen, f"{alias} claimed by {seen.get(key)} and {member.member_key}"
            seen[key] = member.member_key


def test_every_dimensioned_rule_declares_an_axis() -> None:
    """Without an axis a dimensioned rule cannot be told apart from an
    undimensioned one, which is the collision AD-3 rule 0 exists to prevent."""
    assert DIMENSIONED_RULES
    assert all(rule.axis for rule in DIMENSIONED_RULES)


# --- the store ---------------------------------------------------------------


def test_the_store_key_carries_the_member() -> None:
    """CPB impaired three brands in FY2025. A key without the member holds one of
    them and loses two — which is precisely why these facts cannot live in
    canonical_facts."""
    index = next(
        arg for arg in CanonicalMemberFact.__table_args__ if getattr(arg, "name", "") ==
        "uq_canonical_member_facts_key"
    )
    assert [column.name for column in index.columns] == [
        "issuer_cik",
        "canonical_concept",
        "member_key",
        "fiscal_year",
        "mapping_version",
    ]
    assert index.unique


def test_both_member_columns_survive() -> None:
    """`member_key` is the stable identity across the filer's renames;
    `member_as_filed` is what the fact actually carried, which AD-19 provenance
    needs. Dropping either one looks like a simplification and is not: without
    the first a rename splits one brand into three, without the second a citation
    cannot say which tag produced the figure."""
    columns = set(CanonicalMemberFact.__table__.columns.keys())
    assert {"member_key", "member_as_filed", "axis_as_filed"} <= columns


def test_model_and_migration_do_not_drift() -> None:
    """conftest builds the schema with Base.metadata.create_all, never by running
    migrations, so a column added to the model without a migration would pass
    every other test in this suite and then fail against a real database."""
    migration = MIGRATION.read_text()
    for column in CanonicalMemberFact.__table__.columns.keys():
        assert f"'{column}'" in migration, (
            f"{column} is on the model but not in {MIGRATION.name} — create_all hides this"
        )
    assert "uq_canonical_member_facts_key" in migration
    assert "postgresql_where" in migration, "the partial unique index must survive the migration"
