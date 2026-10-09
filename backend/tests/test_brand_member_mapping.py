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
import shutil

import pytest
import yaml

from app.models import CanonicalMemberFact
import canonicalization.mappings.engine as mapping_engine
from canonicalization.mappings.engine import (
    BRAND_MEMBERS,
    DIMENSIONED_RULES,
    EXCLUDED_MEMBERS,
    MEMBER_LABELS,
    MEMBER_RESOLUTION,
    BrandMember,
    DimensionedRule,
    ExcludedMember,
    _check_exclusions,
    _parse_excluded_members,
    _resolve_members,
    build_exclusion_index,
    is_excluded,
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
DIMENSIONS_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db/migrations/versions/d4f61a2b9c30_member_dimensions_identity.py"
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
    assert resolve(QSR, CARRYING, "us-gaap:TradeNamesMember") == (
        "brand_intangible_carrying_value",
        "trade_names",
    )


def test_raos_is_mapped_even_though_it_has_never_been_impaired() -> None:
    """Rao's carries value with no impairment through FY2025 — the answer the CPB
    decision packet asked for. The mapping must still admit an impairment for it,
    or a future write-down would silently fail to resolve."""
    assert resolve(CPB, IMPAIRMENT, "cpb:TrademarksRaosMember") == (
        "brand_intangible_impairment",
        "raos",
    )
    assert MEMBER_LABELS[(CPB, "raos")] == "Rao's"


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
        "context_key",
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
    dimensions_migration = DIMENSIONS_MIGRATION.read_text()
    for column in CanonicalMemberFact.__table__.columns.keys():
        assert f"'{column}'" in migration or f'"{column}"' in dimensions_migration, (
            f"{column} is on the model but not in the migrations — create_all hides this"
        )
    assert "uq_canonical_member_facts_key" in migration
    assert "postgresql_where" in migration and "context_key" in dimensions_migration, (
        "the partial unique index and its normalized context identity must survive the migrations"
    )


# --- The filer's own total (story_13_3_first_live_pipeline_run) --------------


def test_cpb_aggregate_trademark_member_resolves_to_the_total_not_a_brand() -> None:
    """us-gaap:TrademarksMember is CPB's class total, and must not be a brand.

    Identified by VALUE, not by name: in FY2023 and FY2025 it equals the sum of
    the mapped per-brand rows to the dollar (2,541M and 3,678M). Before it was
    mapped it was simply unknown to the engine, so the unmapped_member guard
    raised six permanent needs_review warnings on CPB's report — one per year —
    for something the spec had already recorded as a decision in a comment that
    nothing executed.
    """
    key = (
        "0000016732",
        "us-gaap",
        "IndefiniteLivedIntangibleAssetsExcludingGoodwill",
        "us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis",
        "us-gaap:TrademarksMember",
    )
    resolved = MEMBER_RESOLUTION.get(key)
    assert resolved is not None, "the aggregate member must resolve, or it flags as unmapped"
    canonical_concept, member_key = resolved
    assert canonical_concept == "brand_intangible_carrying_value_total"
    # The hazard the spec's own note names: it double-counts the members it
    # contains, so it must never share a concept with them.
    assert canonical_concept != "brand_intangible_carrying_value"
    assert member_key != "other_trade_names"


def test_the_total_concept_is_reachable_only_through_the_aggregate_member() -> None:
    """A brand must not also claim the total, or the total is triple-written.

    Same guard shape as the within-10%-coverage member: `maps_to` makes the
    concept a redirect target, which `_resolve_members` then excludes from every
    member that does NOT redirect to it.
    """
    claimants = {
        member_key
        for (_cik, _tax, _concept, _axis, _alias), (canonical, member_key)
        in MEMBER_RESOLUTION.items()
        if canonical == "brand_intangible_carrying_value_total"
    }
    assert claimants == {"all_trademarks"}


# --- brand means brand (story_13_3_zts_non_brand_intangibles_land_as_brand_value)


def test_zts_non_brand_intangible_classes_never_resolve_as_brand_value() -> None:
    """IPR&D and product rights are tagged on the SAME indefinite-lived axis as
    zts:BrandsMember (live dev store: 8 rows each, FY2018-FY2025). Resolving them
    stored in-process R&D as brand value, which Story 13.4 would then have
    reported as brand performance."""
    assert resolve(ZTS, CARRYING, "us-gaap:InProcessResearchAndDevelopmentMember") is None
    assert resolve(ZTS, CARRYING, "zts:ProductRightsMember") is None
    assert resolve(ZTS, CARRYING, "us-gaap:DevelopedTechnologyRightsMember") is None
    assert resolve(ZTS, CARRYING, "us-gaap:OtherIntangibleAssetsMember") is None
    assert resolve(ZTS, CARRYING, "zts:BrandsMember") == (
        "brand_intangible_carrying_value",
        "brands",
    )


def test_qsr_franchise_intangibles_are_not_brands() -> None:
    assert resolve(QSR, CARRYING, "us-gaap:FranchiseRightsMember") is None
    assert resolve(QSR, CARRYING, "qsr:FranchiseAgreementMember") is None
    assert resolve(QSR, CARRYING, "us-gaap:TradeNamesMember") == (
        "brand_intangible_carrying_value",
        "trade_names",
    )


def test_every_brand_member_is_a_brand_or_an_explicit_aggregate() -> None:
    """A member with no routing resolves brand_intangible_carrying_value, so it is
    asserting "this is a brand". The only non-brand members allowed on the spec
    are routed ones (maps_to / canonical_concepts), whose notes say what they
    are instead."""
    non_brand_words = ("research", "r&d", "product rights", "technology", "franchise",
                       "customer", "lease", "other intangible")
    for member in BRAND_MEMBERS:
        if member.maps_to or member.canonical_concepts:
            continue
        label = member.label.lower()
        assert not any(word in label for word in non_brand_words), (
            f"{member.issuer_cik}/{member.member_key} ({member.label}) would land as a "
            "brand; declare it under excluded_members instead"
        )


def test_every_exclusion_states_why_and_is_not_also_mapped() -> None:
    """Story 13.4b: and every one is REACHABLE. us-gaap_v17 shipped nine exclusions
    of which seven were tagged only on the finite-lived axis (or not at all), so
    they suppressed nothing while reading exactly like enforced decisions. The two
    that survive are the ZTS members tagged on the indefinite-lived axis beside
    zts:BrandsMember, 14 rows each FY2018-FY2025 in the dev store's Inline XBRL.
    Story 13.5a added three CPB exclusions on the SEGMENT axis (its Corporate and
    reconciling members), asserted in tests/test_segment_mapping.py."""
    assert len(EXCLUDED_MEMBERS) == 5, [e.member_key for e in EXCLUDED_MEMBERS]
    assert {(e.issuer_cik, e.member_key) for e in EXCLUDED_MEMBERS} == {
        (ZTS, "in_process_rnd"),
        (ZTS, "product_rights"),
        ("0000016732", "corporate_and_other"),
        ("0000016732", "corporate_non_segment"),
        ("0000016732", "restructuring_charges"),
    }
    mapped = {(m.issuer_cik, alias) for m in BRAND_MEMBERS for alias in m.aliases}
    for excluded in (e for e in EXCLUDED_MEMBERS if e.issuer_cik == ZTS):
        assert excluded.reason.strip(), f"{excluded.member_key} has no reason"
        assert excluded.axis == AXIS
        assert excluded.source_concepts == (CARRYING,)
        for alias in excluded.aliases:
            assert (excluded.issuer_cik, alias) not in mapped
            assert is_excluded(ZTS, CARRYING, AXIS, alias)


def _excluded(**overrides) -> ExcludedMember:
    fields = dict(
        issuer_cik=ZTS,
        member_key="in_process_rnd",
        aliases=("us-gaap:InProcessResearchAndDevelopmentMember",),
        reason="not a brand",
        axis=AXIS,
    )
    fields.update(overrides)
    return ExcludedMember(**fields)


def _axis_rule(**overrides) -> DimensionedRule:
    fields = dict(
        canonical_concept="brand_intangible_carrying_value",
        source_taxonomy="us-gaap",
        source_concept=CARRYING,
        axis=AXIS,
    )
    fields.update(overrides)
    return DimensionedRule(**fields)


def test_a_member_cannot_be_both_mapped_and_excluded() -> None:
    brand = BrandMember(issuer_cik=ZTS, member_key="x", label="X", aliases=("zts:XMember",))
    excluded = _excluded(member_key="x_excluded", aliases=("zts:XMember",))
    with pytest.raises(ValueError, match="both mapped .* and excluded"):
        _check_exclusions((brand,), (excluded,), (_axis_rule(),))


def test_an_exclusion_without_a_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="reason"):
        _check_exclusions((), (_excluded(reason="  "),), (_axis_rule(),))


# --- an exclusion speaks only for the axis it was verified on (Story 13.4b) ---

FINITE_AXIS = "us-gaap:FiniteLivedIntangibleAssetsByMajorClassAxis"
IPRD = "us-gaap:InProcessResearchAndDevelopmentMember"


def test_an_exclusion_does_not_suppress_its_member_on_another_axis() -> None:
    """ZTS's in-process R&D was verified on the indefinite-lived axis. The same
    standard member on a second mapped axis is a fact nobody has looked at, so it
    must be flagged like any unknown member — until 13.4b, suppression keyed on
    (issuer, member) alone and would have stayed silent."""
    index = build_exclusion_index((_excluded(),))
    assert is_excluded(ZTS, CARRYING, AXIS, IPRD, index=index)
    assert not is_excluded(ZTS, CARRYING, FINITE_AXIS, IPRD, index=index)
    assert not is_excluded(CPB, CARRYING, AXIS, IPRD, index=index)


def test_an_exclusion_with_source_concepts_does_not_suppress_another_concept() -> None:
    """Verified on carrying value is not verified on impairment: an IPR&D
    write-down tagged on the same axis is a new question for a human."""
    index = build_exclusion_index((_excluded(source_concepts=(CARRYING,)),))
    assert is_excluded(ZTS, CARRYING, AXIS, IPRD, index=index)
    assert not is_excluded(ZTS, IMPAIRMENT, AXIS, IPRD, index=index)


def test_an_exclusion_without_source_concepts_covers_every_concept_on_its_axis() -> None:
    index = build_exclusion_index((_excluded(),))
    assert is_excluded(ZTS, IMPAIRMENT, AXIS, IPRD, index=index)


def test_an_exclusion_on_an_axis_no_rule_reads_is_rejected() -> None:
    """QSR's franchise rights were the finding's example: tagged only on the
    finite-lived axis, which no dimensioned rule reads, so the exclusion could
    never fire. Inert, and indistinguishable from an enforced decision."""
    franchise = _excluded(
        issuer_cik=QSR, member_key="franchise_rights",
        aliases=("us-gaap:FranchiseRightsMember",), axis=FINITE_AXIS,
    )
    with pytest.raises(ValueError, match="franchise_rights.*unreachable"):
        _check_exclusions((), (franchise,), (_axis_rule(),))


def test_an_exclusion_is_unreachable_when_only_another_filers_rule_reads_its_axis() -> None:
    """Reachability is per issuer: a rule scoped to CPB does not read ZTS's facts."""
    with pytest.raises(ValueError, match="in_process_rnd.*unreachable"):
        _check_exclusions((), (_excluded(),), (_axis_rule(issuers=(CPB,)),))


def test_an_exclusion_naming_a_concept_no_rule_reads_is_rejected() -> None:
    with pytest.raises(ValueError, match="in_process_rnd.*unreachable"):
        _check_exclusions(
            (), (_excluded(source_concepts=(IMPAIRMENT,)),), (_axis_rule(),)
        )


def test_a_reachable_exclusion_loads() -> None:
    _check_exclusions((), (_excluded(source_concepts=(CARRYING,)),), (_axis_rule(),))
    _check_exclusions((), (_excluded(),), (_axis_rule(issuers=(ZTS,)),))


def test_an_exclusion_without_an_axis_is_rejected_at_load() -> None:
    data = {"excluded_members": {ZTS: {"in_process_rnd": {
        "reason": "not a brand", "aliases": [IPRD],
    }}}}
    with pytest.raises(ValueError, match="in_process_rnd.*axis"):
        _parse_excluded_members("us-gaap_vX", data)


def test_an_exclusion_with_scalar_source_concepts_is_rejected_at_load() -> None:
    """A scalar would be read character by character and match nothing — the
    same inert-declaration trap 13.4a closed for segment aliases."""
    data = {"excluded_members": {ZTS: {"in_process_rnd": {
        "reason": "not a brand", "aliases": [IPRD], "axis": AXIS,
        "source_concepts": CARRYING,
    }}}}
    with pytest.raises(ValueError, match="in_process_rnd.*source_concepts"):
        _parse_excluded_members("us-gaap_vX", data)


@pytest.fixture
def registered_exclusion_spec(tmp_path, monkeypatch):
    """Use the full loader while keeping shipped specs and its cache isolated."""
    specs = tmp_path / "specs"
    shutil.copytree(mapping_engine.SPECS_DIR, specs)
    monkeypatch.setattr(mapping_engine, "SPECS_DIR", specs)
    registry = yaml.safe_load((specs / "registry.yaml").read_text())
    spec_file = specs / f"{registry['taxonomies']['us-gaap']}.yaml"
    data = yaml.safe_load(spec_file.read_text())
    mapping_engine.load_mapping_spec.cache_clear()
    try:
        yield spec_file, data
    finally:
        mapping_engine.load_mapping_spec.cache_clear()


@pytest.mark.parametrize(
    "invalid_scope, message",
    [
        ("axis", "in_process_rnd.*unreachable"),
        ("issuer", "in_process_rnd.*unreachable"),
        ("concept", "in_process_rnd.*unreachable"),
        ("missing_axis", "in_process_rnd.*axis"),
        ("scalar_concepts", "in_process_rnd.*source_concepts"),
    ],
)
def test_the_loader_rejects_an_invalid_exclusion(
    registered_exclusion_spec, invalid_scope, message
) -> None:
    spec_file, data = registered_exclusion_spec
    exclusion = data["excluded_members"][ZTS]["in_process_rnd"]
    if invalid_scope in {"axis", "issuer"}:
        exclusion["axis"] = FINITE_AXIS
        if invalid_scope == "issuer":
            # This axis IS read, but only for CPB. All other declarations remain
            # valid so skipping the exclusion validator would accept this spec.
            data["dimensioned_concepts"]["exclusion_scope_probe"] = {
                "axis": FINITE_AXIS,
                "issuers": [CPB],
                "sources": [{"concept": CARRYING}],
            }
    elif invalid_scope == "concept":
        exclusion["source_concepts"] = ["AnUnreadSourceConcept"]
    elif invalid_scope == "missing_axis":
        del exclusion["axis"]
    else:
        exclusion["source_concepts"] = CARRYING
    spec_file.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(ValueError, match=message):
        mapping_engine.load_mapping_spec()


@pytest.mark.parametrize("reverse", [False, True])
def test_the_exclusion_index_rejects_colliding_concept_scopes(reverse) -> None:
    first = _excluded(source_concepts=(CARRYING,))
    second = _excluded(member_key="duplicate_in_process_rnd", source_concepts=(IMPAIRMENT,))
    entries = (second, first) if reverse else (first, second)

    with pytest.raises(ValueError, match="exclusion.*claimed by both") as error:
        build_exclusion_index(entries)
    assert first.member_key in str(error.value)
    assert second.member_key in str(error.value)
    assert ZTS in str(error.value)
    assert AXIS in str(error.value)
    assert IPRD in str(error.value)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("scoped", [False, True], ids=["wildcard", "concept_scoped"])
def test_the_loader_rejects_colliding_exclusions(registered_exclusion_spec, reverse, scoped) -> None:
    spec_file, data = registered_exclusion_spec
    entries = data["excluded_members"][ZTS]
    original = entries["in_process_rnd"]
    duplicate = dict(original)
    if scoped:
        duplicate["source_concepts"] = [IMPAIRMENT]
        data["dimensioned_concepts"]["brand_intangible_impairment"]["issuers"].append(ZTS)
    else:
        del duplicate["source_concepts"]
    entries["duplicate_in_process_rnd"] = duplicate
    if reverse:
        data["excluded_members"][ZTS] = dict(reversed(list(entries.items())))
    spec_file.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(ValueError, match="exclusion.*claimed by both"):
        mapping_engine.load_mapping_spec()


def test_exclusion_aliases_can_repeat_for_different_issuers_or_axes() -> None:
    entries = (
        _excluded(source_concepts=(CARRYING,)),
        _excluded(issuer_cik=CPB, source_concepts=(IMPAIRMENT,)),
        _excluded(axis=FINITE_AXIS, source_concepts=(IMPAIRMENT,)),
    )
    index = build_exclusion_index(entries)
    assert len(index) == 3
    assert is_excluded(ZTS, CARRYING, AXIS, IPRD, index=index)
    assert not is_excluded(ZTS, IMPAIRMENT, AXIS, IPRD, index=index)
    assert is_excluded(CPB, IMPAIRMENT, AXIS, IPRD, index=index)
    assert is_excluded(ZTS, IMPAIRMENT, FINITE_AXIS, IPRD, index=index)


# --- the residual bucket is not a brand either (Codex round, PR #138) --------

RESIDUAL = "brand_intangible_carrying_value_residual"


def test_cpb_residual_bucket_is_not_stored_as_a_brand() -> None:
    """us-gaap_v15 answered "is everything in this concept a brand" for ZTS and left
    CPB's own residual behind: 9 raw facts over two per-era aliases resolving into
    brand_intangible_carrying_value while the spec note called it "not a brand".
    Its original justification — reconciling the per-brand rows against the total —
    was disproved by arithmetic in v14."""
    for alias in ("cpb:TradeNamesOtherMember", "cpb:TrademarksOtherMember"):
        assert resolve(CPB, CARRYING, alias) == (RESIDUAL, "other_trade_names")


def test_the_residual_concept_is_reachable_only_through_the_residual_member() -> None:
    """Same guard the aggregate total has: were a named brand able to resolve it,
    the residual would double-count brands it does not contain."""
    reachable = {
        member for (_, _, _, _, member), (concept, _) in MEMBER_RESOLUTION.items()
        if concept == RESIDUAL
    }
    assert reachable == {"cpb:TradeNamesOtherMember", "cpb:TrademarksOtherMember"}


def test_a_routed_member_does_not_claim_the_brands_concept() -> None:
    """Every member that resolves brand_intangible_carrying_value must be a NAMED
    brand — no aggregate, no residual, no other asset class. The assertion the
    concept's name makes, checked against the resolution table rather than against
    the spec's prose."""
    brands = {
        key for key, (concept, _) in MEMBER_RESOLUTION.items()
        if concept == "brand_intangible_carrying_value"
    }
    # ANY routing, not just maps_to: us-gaap_v15 kept the residual out of the brands
    # concept's way with a `canonical_concepts` allow-list that still named the brands
    # concept, so a maps_to-only check passes against the very bug this guards.
    routed_keys = {
        member.member_key
        for member in BRAND_MEMBERS
        if member.maps_to or member.canonical_concepts
    }
    landed = {MEMBER_RESOLUTION[k][1] for k in brands}
    assert not (landed & routed_keys), (
        f"routed members {sorted(landed & routed_keys)} still land in the brands concept"
    )
