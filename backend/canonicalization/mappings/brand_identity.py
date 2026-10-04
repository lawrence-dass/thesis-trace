"""Which brand is a stored member row about? (Story 13.4a)

`canonical_member_facts` holds one row per (concept, member, year, context). Story
13.3 proved that the member alone does not answer "which brand is this": CPB and
ZTS carry the brand in `member_key`, while all 30 of QSR's rows share
`member_key: "trade_names"` and the brand is the segment member inside
`context_key` (story_13_3_multi_axis_member_identity_verified). A consumer reading
`member_key` alone shows four rows all labelled "Trade names" and loses which
brand each is.

This module is the single place that answers the question, for every filer. It is
READ-TIME only: it computes no figure, and canonicalization neither imports nor
runs it. Every later story in Epic 13 that names a brand reads through here rather
than re-deriving identity from a tag.

Two rules it exists to enforce:

  * A label is the spec's own words. Nothing here parses a tag name — no
    `split(":")`, no stripping `Member`, no camel-case-to-words. A brand the spec
    has not declared is unresolved, never a label invented from its tag.
  * Unresolved is AD-16 `insufficient_data`, and it is a DIFFERENT TYPE from a
    resolved identity. Reading `.label` off an unresolved result raises, rather
    than yielding a member key, a blank string or a plausible-looking guess.
"""

from __future__ import annotations

from dataclasses import dataclass

from canonicalization.mappings.engine import (
    BRAND_MEMBERS,
    SEGMENT_BRAND_MEMBERS,
    BrandMember,
    SegmentBrandMember,
)


@dataclass(frozen=True)
class BrandIdentity:
    """A resolved identity. Only ever constructed when the brand is known.

    `kind` is the spec's declaration of what this row is ABOUT, not a guess from
    the label: `named_brand` for a real acquired brand, and `aggregate`,
    `residual` or `disclosure` for rows that carry filed brand value without
    naming a brand. A consumer that wants per-brand figures filters on
    `named_brand`; one that renders a total reads `aggregate`. Neither has to
    pattern-match a label — ZTS's aggregate is labelled "Brands", which no word
    blacklist would ever catch.

    `source_axis` is the axis the identity was read from, kept because it differs
    per filer and a provenance citation (AD-19) has to be able to say which
    dimension of which context named the brand.
    """

    issuer_cik: str
    brand_key: str
    label: str
    kind: str
    source_axis: str


@dataclass(frozen=True)
class BrandUnresolved:
    """AD-16 `insufficient_data` for one stored row.

    A separate type rather than a None or an empty `BrandIdentity` on purpose: a
    caller that forgets to check cannot read a label off this, it gets an
    AttributeError at the point of the mistake. `reason` is for the developer
    reading a test failure or a log; it is not user-facing copy.
    """

    issuer_cik: str
    reason: str
    status: str = "insufficient_data"


# (issuer_cik, member_key) -> the declared member. Keyed by issuer because a
# member key is unique only within its filer.
_MEMBERS: dict[tuple[str, str], BrandMember] = {
    (m.issuer_cik, m.member_key): m for m in BRAND_MEMBERS
}

# (issuer_cik, axis, member AS FILED) -> the declared segment brand. The member
# goes in as the filer wrote it that year and the stable brand key comes out,
# which is what makes a rename invisible to everything downstream — the same
# shape as MEMBER_RESOLUTION.
_SEGMENT_BRANDS: dict[tuple[str, str, str], SegmentBrandMember] = {
    (s.issuer_cik, s.axis, alias): s for s in SEGMENT_BRAND_MEMBERS for alias in s.aliases
}


def resolve_brand_identity(
    issuer_cik: str, member_key: str, context_key: dict | None
) -> BrandIdentity | BrandUnresolved:
    """Resolve one `canonical_member_facts` row to the brand it is about.

    Pass the row's own `issuer_cik`, `member_key` and `context_key` — the
    NORMALIZED context, not `dimensions`: `context_key` carries the stable
    `member_key` on the mapped axis (`_dimension_identity`), which is what lets
    the mapped axis be found without knowing which axis it is for this filer.
    """
    member = _MEMBERS.get((issuer_cik, member_key))
    if member is None:
        return BrandUnresolved(
            issuer_cik=issuer_cik,
            reason=f"no member {member_key!r} declared for issuer {issuer_cik}",
        )

    if member.kind == "segment_scoped":
        return _resolve_on_segment_axis(issuer_cik, member, context_key)

    # CPB and ZTS: the member names the brand. The axis it was read from is the
    # one whose value IS the member key — every other axis in the context is a
    # qualifier and must not change the identity. CPB's allied_brands and
    # pop_secret carrying values also carry
    # us-gaap:FairValueByMeasurementFrequencyAxis (a nonrecurring remeasurement
    # context); they are the same brand as their unqualified siblings, and
    # keying identity on the whole context would make them extra brands.
    source_axis = _axis_carrying(context_key, member_key)
    if source_axis is None:
        return BrandUnresolved(
            issuer_cik=issuer_cik,
            reason=(
                f"member {member_key!r} is declared, but no axis in the stored context "
                f"carries it: {sorted((context_key or {}))}"
            ),
        )
    return BrandIdentity(
        issuer_cik=issuer_cik,
        brand_key=member.member_key,
        label=member.label,
        kind=member.kind,
        source_axis=source_axis,
    )


def _resolve_on_segment_axis(
    issuer_cik: str, member: BrandMember, context_key: dict | None
) -> BrandIdentity | BrandUnresolved:
    """QSR: the member defers, and the brand is on `member.brand_axis`."""
    axis = member.brand_axis
    as_filed = (context_key or {}).get(axis)
    if as_filed is None:
        return BrandUnresolved(
            issuer_cik=issuer_cik,
            reason=(
                f"member {member.member_key!r} defers identity to {axis}, which this row's "
                f"context does not carry: {sorted((context_key or {}))}"
            ),
        )

    segment = _SEGMENT_BRANDS.get((issuer_cik, axis, str(as_filed)))
    if segment is None:
        # The live case this guards: a filer adds a segment nobody has checked.
        # Falling back to the member key would label it "Trade names"; falling
        # back to the tag would invent a brand name out of a string.
        return BrandUnresolved(
            issuer_cik=issuer_cik,
            reason=(
                f"{as_filed!r} on {axis} is not a declared segment brand for issuer "
                f"{issuer_cik}"
            ),
        )
    return BrandIdentity(
        issuer_cik=issuer_cik,
        brand_key=segment.brand_key,
        label=segment.label,
        kind=segment.kind,
        source_axis=axis,
    )


def _axis_carrying(context_key: dict | None, member_key: str) -> str | None:
    """The axis whose normalized value is `member_key`, or None."""
    for axis, value in (context_key or {}).items():
        if value == member_key:
            return str(axis)
    return None
