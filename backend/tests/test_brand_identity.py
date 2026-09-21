"""Which brand a stored member row is about (Story 13.4a).

test_brand_member_mapping.py proves the spec RESOLVES a member to a canonical
concept. This file proves the layer a consumer reads: given a row that landed,
which brand is it, what kind of thing is it, and what happens when the answer is
not known.

Every context below is a real one, copied out of the dev store's current rows
(`mapping_version = concepts_v18`, the same 96 rows concepts_v17 produced), not
invented to match the resolver. The QSR contexts in particular are the finding
this story exists for: all 30 of its rows carry `member_key = "trade_names"` and
the brand is the SEGMENT member inside the same context
(story_13_3_multi_axis_member_identity_verified).
"""

from __future__ import annotations

import shutil

import pytest
import yaml
from sqlalchemy import select

from app.models import CanonicalMemberFact
from canonicalization.mappings.brand_identity import (
    BrandIdentity,
    BrandUnresolved,
    resolve_brand_identity,
)
from canonicalization.mappings.engine import (
    MEMBER_LABELS,
    SEGMENT_BRAND_MEMBERS,
    SPECS_DIR,
    BrandMember,
    SegmentBrandMember,
    _check_brand_identity,
    load_mapping_spec,
)
from tests.conftest import requires_db

CPB, ZTS, QSR = "0000016732", "0001555280", "0001618756"
CLASS_AXIS = "us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis"
SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"
FAIR_VALUE_AXIS = "us-gaap:FairValueByMeasurementFrequencyAxis"
NONRECURRING = "us-gaap:FairValueMeasurementsNonrecurringMember"

# QSR's four stored contexts, verbatim.
QSR_CONTEXTS = {
    "qsr:BurgerKingMember": "Burger King",
    "qsr:TimHortonsMember": "Tim Hortons",
    "qsr:PopeyesLouisianaKitchenMember": "Popeyes Louisiana Kitchen",
    "qsr:FirehouseSubsMember": "Firehouse Subs",
}


def _qsr_row(segment_member: str) -> dict:
    return {SEGMENT_AXIS: segment_member, CLASS_AXIS: "trade_names"}


# --- The multi-axis finding (AC 2) ------------------------------------------


def test_qsr_rows_resolve_to_four_distinct_brands() -> None:
    """The whole reason this module exists.

    All 30 QSR rows share member_key "trade_names". A consumer reading member_key
    alone shows four rows called "Trade names" and loses which brand each is
    (story_13_3_multi_axis_member_identity_verified). These are the four segment
    members the dev store actually holds.
    """
    resolved = [
        resolve_brand_identity(QSR, "trade_names", _qsr_row(member))
        for member in QSR_CONTEXTS
    ]

    assert all(isinstance(r, BrandIdentity) for r in resolved), resolved
    assert {r.label for r in resolved} == set(QSR_CONTEXTS.values())
    assert len({r.brand_key for r in resolved}) == 4, "four brands, four stable keys"
    assert {r.source_axis for r in resolved} == {SEGMENT_AXIS}, (
        "QSR's identity comes off the segment axis, not the intangible-class axis"
    )
    assert {r.kind for r in resolved} == {"named_brand"}


@pytest.mark.parametrize(("member", "label"), sorted(QSR_CONTEXTS.items()))
def test_each_qsr_segment_member_carries_its_own_brand(member: str, label: str) -> None:
    identity = resolve_brand_identity(QSR, "trade_names", _qsr_row(member))
    assert isinstance(identity, BrandIdentity)
    assert identity.label == label
    assert identity.label != "Trade names", (
        "the member's own label must never stand in for the brand"
    )


def test_cpb_and_zts_read_the_brand_off_the_member_itself() -> None:
    """The other shape: for these two filers the member IS the brand, and the
    resolution has to answer for both without the caller knowing which is which."""
    kettle = resolve_brand_identity(CPB, "kettle", {CLASS_AXIS: "kettle"})
    assert isinstance(kettle, BrandIdentity)
    assert (kettle.label, kettle.kind, kettle.source_axis) == (
        "Kettle Brand",
        "named_brand",
        CLASS_AXIS,
    )


# --- A member key is not a brand name (AC 4) --------------------------------


def test_zts_brands_is_an_aggregate_not_a_named_brand() -> None:
    """ZTS discloses ONE aggregate Brands member rather than naming individual
    acquired brands — its own spec note said so while the mapping filed it as a
    named brand. The only guard was a word-blacklist over the label, and "Brands"
    passes every blacklist. So the kind is data now."""
    identity = resolve_brand_identity(ZTS, "brands", {CLASS_AXIS: "brands"})
    assert isinstance(identity, BrandIdentity)
    assert identity.kind == "aggregate", (
        "per-brand granularity does not exist for ZTS however the mapping is written; "
        "a consumer filtering for named_brand must not pick this up"
    )
    assert identity.label == "Brands"


@pytest.mark.parametrize(
    ("member_key", "expected_kind"),
    [
        ("other_trade_names", "residual"),
        ("all_trademarks", "aggregate"),
        ("within_ten_percent_coverage", "disclosure"),
        ("raos", "named_brand"),
    ],
)
def test_cpb_non_brand_members_declare_what_they_are(
    member_key: str, expected_kind: str
) -> None:
    identity = resolve_brand_identity(CPB, member_key, {CLASS_AXIS: member_key})
    assert isinstance(identity, BrandIdentity)
    assert identity.kind == expected_kind


# --- Unresolved is insufficient_data, never a guess (AC 5) ------------------


def test_an_undeclared_segment_member_is_insufficient_data() -> None:
    """The live case: QSR adds a segment nobody has checked. Falling back to
    member_key would label it "Trade names"; falling back to the tag would invent
    a brand name out of a string. AD-16 says neither."""
    result = resolve_brand_identity(QSR, "trade_names", _qsr_row("qsr:SomeNewBrandMember"))

    assert isinstance(result, BrandUnresolved)
    assert result.status == "insufficient_data"
    assert "qsr:SomeNewBrandMember" in result.reason


def test_an_unresolved_result_has_no_label_to_read_by_accident() -> None:
    """A separate TYPE, not a None or an empty string: a caller that forgets to
    check raises at the point of the mistake instead of rendering a member key as
    though it were a brand."""
    result = resolve_brand_identity(QSR, "trade_names", _qsr_row("qsr:UnknownMember"))

    for attribute in ("label", "brand_key", "kind"):
        with pytest.raises(AttributeError):
            getattr(result, attribute)


def test_a_filer_with_no_declarations_resolves_nothing() -> None:
    result = resolve_brand_identity("0000320193", "kettle", {CLASS_AXIS: "kettle"})
    assert isinstance(result, BrandUnresolved)


def test_a_segment_scoped_row_without_its_axis_is_insufficient_data() -> None:
    """QSR's member defers identity to the segment axis. A row that does not carry
    that axis cannot name a brand, and must not fall back to "Trade names"."""
    result = resolve_brand_identity(QSR, "trade_names", {CLASS_AXIS: "trade_names"})
    assert isinstance(result, BrandUnresolved)
    assert SEGMENT_AXIS in result.reason


def test_no_label_is_derived_from_a_tag_name() -> None:
    """Every label the resolver can return is a string the spec wrote down. If one
    could be derived from a tag, an undeclared member would produce a plausible
    label instead of insufficient_data — which is the failure this asserts against.
    """
    declared = {m.label for m in SEGMENT_BRAND_MEMBERS} | set(MEMBER_LABELS.values())
    for member in QSR_CONTEXTS:
        identity = resolve_brand_identity(QSR, "trade_names", _qsr_row(member))
        assert identity.label in declared


# --- Identity is keyed per filer (AC 6) -------------------------------------


def test_member_labels_are_keyed_by_filer() -> None:
    """A member key is unique only WITHIN its filer. The spec's own comment warns
    that us-gaap:TradeNamesMember "can be used by two filers for different assets"
    — QSR already uses it. Keyed on member_key alone, the second filer to use a
    generic key silently overwrote the first one's label, and the collision showed
    up as a wrong brand name on a page rather than as an error."""
    assert MEMBER_LABELS[(CPB, "raos")] == "Rao's"
    assert MEMBER_LABELS[(QSR, "trade_names")] == "Trade names"
    assert ("raos", "Rao's") not in MEMBER_LABELS.items(), "not keyed by member alone"

    # Two filers, one key, two meanings — the shape the key protects against.
    collision = {
        (CPB, "trade_names"): "Campbell's trade names",
        (QSR, "trade_names"): "Trade names",
    }
    assert len(collision) == 2


def test_one_filers_member_does_not_resolve_for_another() -> None:
    """CPB's kettle is meaningless for ZTS. Resolving it anyway would attribute a
    Campbell's brand to a Zoetis row."""
    assert isinstance(
        resolve_brand_identity(ZTS, "kettle", {CLASS_AXIS: "kettle"}), BrandUnresolved
    )


# --- A qualifier axis does not create a brand (AC 7) ------------------------


@pytest.mark.parametrize("member_key", ["allied_brands", "pop_secret"])
def test_a_fair_value_qualifier_does_not_make_a_second_brand(member_key: str) -> None:
    """These two CPB carrying-value rows also carry a nonrecurring fair-value
    measurement axis — the post-impairment remeasurement context. Keying identity
    on the whole context would make them extra brands; they are the same brand as
    their unqualified siblings, and the qualifier stays on the row."""
    plain = resolve_brand_identity(CPB, member_key, {CLASS_AXIS: member_key})
    qualified = resolve_brand_identity(
        CPB, member_key, {CLASS_AXIS: member_key, FAIR_VALUE_AXIS: NONRECURRING}
    )

    assert isinstance(qualified, BrandIdentity)
    assert qualified == plain


def test_the_acquisition_axis_qualifier_does_not_change_the_brand() -> None:
    """CPB's Rao's acquisition row carries us-gaap:BusinessAcquisitionAxis beside
    the class axis — the Sovos deal it came in with."""
    identity = resolve_brand_identity(
        CPB,
        "raos",
        {
            "us-gaap:BusinessAcquisitionAxis": "cpb:SovosBrandsAcquisitionMember",
            CLASS_AXIS: "raos",
        },
    )
    assert isinstance(identity, BrandIdentity)
    assert identity.label == "Rao's"
    assert identity.source_axis == CLASS_AXIS


# --- The loader rejects a declaration nothing can reach (AC 3, 6, 8) --------


def _member(**kwargs) -> BrandMember:
    base = dict(issuer_cik=QSR, member_key="trade_names", label="Trade names", aliases=("x",))
    return BrandMember(**{**base, **kwargs})


def _segment(**kwargs) -> SegmentBrandMember:
    base = dict(
        issuer_cik=QSR,
        axis=SEGMENT_AXIS,
        brand_key="burger_king",
        label="Burger King",
        aliases=("qsr:BurgerKingMember",),
    )
    return SegmentBrandMember(**{**base, **kwargs})


def test_a_segment_scoped_member_must_name_its_axis() -> None:
    with pytest.raises(ValueError, match="names no brand_axis"):
        _check_brand_identity((_member(kind="segment_scoped"),), ())


def test_a_brand_axis_nothing_declares_is_rejected() -> None:
    """The conformance rule, enforced: a member pointing at an axis with no
    declarations resolves NO brand for every row through it, silently."""
    with pytest.raises(ValueError, match="declares no segment_brand_members"):
        _check_brand_identity(
            (_member(kind="segment_scoped", brand_axis=SEGMENT_AXIS),), ()
        )


def test_a_segment_block_nothing_defers_to_is_rejected() -> None:
    """The mirror image: declarations nothing reads. An inert declaration reads
    exactly like a working one — which is how `excluded_members` shipped three
    exclusions no rule could reach."""
    with pytest.raises(ValueError, match="no member of that filer is segment_scoped"):
        _check_brand_identity((_member(kind="named_brand"),), (_segment(),))


def test_only_a_segment_scoped_member_may_name_a_brand_axis() -> None:
    with pytest.raises(ValueError, match="only a segment_scoped member defers"):
        _check_brand_identity(
            (_member(kind="named_brand", brand_axis=SEGMENT_AXIS),), ()
        )


def test_an_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        _check_brand_identity((_member(kind="brandish"),), ())


def test_two_segment_brands_cannot_claim_one_alias() -> None:
    with pytest.raises(ValueError, match="claimed by both"):
        _check_brand_identity(
            (_member(kind="segment_scoped", brand_axis=SEGMENT_AXIS),),
            (_segment(), _segment(brand_key="tim_hortons", label="Tim Hortons")),
        )


def test_the_validation_is_wired_into_the_loader(tmp_path, monkeypatch) -> None:
    """The checks above call `_check_brand_identity` directly, which proves the
    function works and NOT that anything calls it.

    That gap is this project's recurring defect, not a hypothetical: AD-3's
    least-dimensioned clause and `raw_facts.dimensions` both sat declared and
    unexecuted for a year, and 13.3 shipped a mapping that resolved perfectly in
    unit tests and wrote zero rows because the guard sat after the lookup. A
    mutation run on 2026-09-20 confirmed it here too — deleting the call from
    `load_mapping_spec` left all six checks above green.

    So this one goes through the real loader, against a real spec directory.
    """
    specs = tmp_path / "specs"
    shutil.copytree(SPECS_DIR, specs)
    monkeypatch.setattr("canonicalization.mappings.engine.SPECS_DIR", specs)

    registry = yaml.safe_load((specs / "registry.yaml").read_text())
    spec_file = specs / f"{registry['taxonomies']['us-gaap']}.yaml"
    spec = spec_file.read_text()

    # Point QSR's segment_scoped member at an axis nothing declares. Every QSR row
    # would then resolve to no brand at all, silently.
    broken = spec.replace(
        "      brand_axis: us-gaap:StatementBusinessSegmentsAxis",
        "      brand_axis: us-gaap:AnAxisNobodyDeclares",
        1,
    )
    assert broken != spec, "the brand_axis anchor moved — update this test"
    spec_file.write_text(broken)

    # load_mapping_spec is lru_cached and the module already warmed it at import.
    # Clear it on the way in, and again on the way out so the broken spec cannot
    # leak into a later test through the cache.
    load_mapping_spec.cache_clear()
    try:
        with pytest.raises(ValueError, match="declares no segment_brand_members"):
            load_mapping_spec()
    finally:
        load_mapping_spec.cache_clear()


def test_every_declared_member_states_a_kind() -> None:
    """Read off the spec file rather than the loaded objects: the dataclass has a
    default, so a member that forgot to declare one would load as a named brand.
    """
    spec = yaml.safe_load((SPECS_DIR / "us-gaap_v17.yaml").read_text())
    missing = [
        f"{cik}/{key}"
        for cik, members in spec["brand_members"].items()
        for key, body in members.items()
        if "kind" not in body
    ]
    assert not missing, f"these members declare no kind: {missing}"


def test_every_segment_brand_states_the_years_it_was_checked_against() -> None:
    """AC 8: a declaration is grounded in rows that exist, not in a tag that looks
    right. The note is where that evidence lives, per the BCE-debt precedent."""
    for segment in SEGMENT_BRAND_MEMBERS:
        assert segment.note and "FY20" in segment.note, (
            f"{segment.brand_key} states no observed years"
        )


# --- Every stored row resolves, or says why not -----------------------------


@requires_db
async def test_every_current_member_row_resolves_or_declares_a_non_brand(
    db_session,
) -> None:
    """A unit test over a lookup structurally cannot catch a wiring fault — 13.3
    shipped a mapping that resolved perfectly in unit tests and wrote zero rows.
    This walks what is actually stored.

    Empty is a pass here only in the sense that a seeded test DB has no rows of its
    own; the same assertion run against the populated dev store is what closes the
    story's verification item.
    """
    rows = (
        await db_session.execute(
            select(CanonicalMemberFact).where(CanonicalMemberFact.superseded.is_(False))
        )
    ).scalars()

    unresolved = []
    for row in rows:
        identity = resolve_brand_identity(row.issuer_cik, row.member_key, row.context_key)
        if isinstance(identity, BrandUnresolved):
            unresolved.append(f"{row.issuer_cik}/{row.member_key}: {identity.reason}")

    assert not unresolved, (
        "stored rows whose brand cannot be named — each is a row a consumer would "
        f"have to render as insufficient_data: {unresolved}"
    )
