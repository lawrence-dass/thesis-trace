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
    DIMENSIONED_RULES,
    SEGMENT_AXES,
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

    FALSY, which the first version was not. A dataclass is truthy by default, so
    `if identity:` passed for an unresolved row and the AD-16 guarantee held only
    against `.label` access — the Codex round on `ff1e1d1` found the hole. The
    idiomatic check and the explicit one now agree.
    """

    issuer_cik: str
    reason: str
    status: str = "insufficient_data"

    def __bool__(self) -> bool:
        return False


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


def _declared_axes() -> dict[str, frozenset[str]]:
    """Every axis the spec declares as identity-bearing, per filer.

    Identity may be read ONLY from one of these. Without it, `_axis_carrying`
    accepted any axis whose value happened to equal the member key, so a context
    carrying `{"custom:QualifierAxis": "kettle"}` resolved to Kettle Brand with
    `source_axis="custom:QualifierAxis"` — a label that is right by accident and
    an AD-19 provenance citation that is simply false. Found by the Codex round
    on `ff1e1d1`.
    """
    filers = {m.issuer_cik for m in BRAND_MEMBERS} | {
        s.issuer_cik for s in SEGMENT_BRAND_MEMBERS
    }
    axes: dict[str, set[str]] = {cik: set() for cik in filers}
    for rule in DIMENSIONED_RULES:
        # An empty `issuers` means the rule applies to every filer.
        for cik in rule.issuers or filers:
            # A filer's segment axis names a segment, never a brand (13.5a).
            if (cik, rule.axis) not in SEGMENT_AXES:
                axes.setdefault(cik, set()).add(rule.axis)
    for segment in SEGMENT_BRAND_MEMBERS:
        axes.setdefault(segment.issuer_cik, set()).add(segment.axis)
    return {cik: frozenset(found) for cik, found in axes.items()}


_DECLARED_AXES: dict[str, frozenset[str]] = _declared_axes()


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

    # The row must carry its own member on a declared axis, whichever filer it is
    # and whether or not the brand itself lives elsewhere. A context that does not
    # is not a row this resolution describes: the segment path used to accept
    # `{SEGMENT_AXIS: "qsr:BurgerKingMember"}` with no `trade_names` anywhere in
    # it, which is not a shape `canonicalize_issuer` can produce.
    declared = _DECLARED_AXES.get(issuer_cik, frozenset())
    mapped_axis, reason = _axis_carrying(context_key, member_key, declared)
    if mapped_axis is None:
        return BrandUnresolved(issuer_cik=issuer_cik, reason=reason or "unresolved")

    if member.kind == "segment_scoped":
        return _resolve_on_segment_axis(issuer_cik, member, context_key)

    # CPB and ZTS: the member names the brand. The axis it was read from is the
    # one whose value IS the member key — every other axis in the context is a
    # qualifier and must not change the identity. CPB's allied_brands and
    # pop_secret carrying values also carry
    # us-gaap:FairValueByMeasurementFrequencyAxis (a nonrecurring remeasurement
    # context); they are the same brand as their unqualified siblings, and
    # keying identity on the whole context would make them extra brands.
    return BrandIdentity(
        issuer_cik=issuer_cik,
        brand_key=member.member_key,
        label=member.label,
        kind=member.kind,
        source_axis=mapped_axis,
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

    # A member name is a string. Coercing with `str()` meant a context value of
    # `1` matched an alias of `"1"`, so a malformed context could resolve a brand
    # instead of reporting insufficient_data.
    if not isinstance(as_filed, str):
        return BrandUnresolved(
            issuer_cik=issuer_cik,
            reason=(
                f"{axis} carries {as_filed!r} ({type(as_filed).__name__}), not a member "
                "name — a non-string context value is malformed, not a brand"
            ),
        )

    segment = _SEGMENT_BRANDS.get((issuer_cik, axis, as_filed))
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


def _axis_carrying(
    context_key: dict | None, member_key: str, declared: frozenset[str]
) -> tuple[str | None, str | None]:
    """The DECLARED axis whose normalized value is `member_key`.

    Returns `(axis, None)` on a single unambiguous match, or `(None, reason)`.

    Two rules, both added after the Codex round on `ff1e1d1` found them missing:

    * The axis must be one the spec declares for this filer (see
      `_declared_axes`). Matching any axis whose value happened to equal the
      member key made `source_axis` — the thing an AD-19 citation would print —
      false whenever an undeclared axis carried the same string.
    * Two matching axes are an ERROR, not a pick. The original returned the first
      match in dict iteration order, so the same row could resolve differently
      depending on how its context was built. A row whose identity is genuinely
      ambiguous is `insufficient_data` (AD-16); it is not a coin toss.
    """
    matches = [
        str(axis)
        for axis, value in (context_key or {}).items()
        if value == member_key and str(axis) in declared
    ]
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        undeclared = [
            str(axis) for axis, value in (context_key or {}).items() if value == member_key
        ]
        if undeclared:
            return None, (
                f"member {member_key!r} appears only on undeclared axes "
                f"{sorted(undeclared)}; declared for this filer: {sorted(declared)}"
            )
        return None, (
            f"member {member_key!r} is declared, but no axis in the stored context "
            f"carries it: {sorted((context_key or {}))}"
        )
    return None, (
        f"member {member_key!r} is carried by more than one declared axis "
        f"{sorted(matches)} — the identity is ambiguous, not a choice"
    )
