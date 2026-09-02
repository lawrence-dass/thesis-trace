"""Versioned concept-mapping spec loader (AD-2, AD-3).

Maps source XBRL concepts to ThesisTrace canonical concepts. The rules themselves
are DATA in `specs/*.yaml`, one spec per taxonomy plus a shared derivations spec,
tied together by `specs/registry.yaml`. This mirrors `formulas/engine.py` +
`formulas/specs/`: adding a taxonomy or a fallback tag is a spec edit, not a code
edit, and the rules stay reviewable by someone who does not read Python.

A mapping change produces a NEW version, never an in-place edit (AD-2) — see the
procedure at the top of `specs/registry.yaml`. Rules are seeded into the
`concept_mappings` table so canonicalization is reproducible and auditable.

Priority is derived from LIST ORDER within a concept's `sources`, so a fallback
chain cannot drift out of sync with the priority numbers that order it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConceptMapping

SPECS_DIR = Path(__file__).parent / "specs"

# Operations a derivation may declare. Deliberately tiny: a derivation must be an
# identity that holds by definition, or a decision recorded with its rationale in
# the spec (see specs/derivations_v2.yaml). An unknown operation raises rather than
# silently skipping a concept the pipeline expects.
DERIVATION_OPERATIONS = frozenset({"subtract", "add"})

# How a derivation is characterised on the public methodology page. `decision` means
# ThesisTrace chose among defensible alternatives that give different numbers, which a
# user is entitled to see and disagree with (D8 consequence 3). `identity` means the
# rule is true by definition once its operands are the right measurements.
DERIVATION_KINDS = frozenset({"identity", "decision"})


@dataclass(frozen=True)
class MappingRule:
    canonical_concept: str
    source_taxonomy: str
    source_concept: str
    priority: int = 0  # lower wins when multiple source concepts map to one canonical
    note: str | None = None
    # False when this tag measures something meaningfully different from the concept's
    # primary source — an IAS 1 by-nature variant, say. The value is correct and used;
    # what it is not is strictly comparable to another filer's. Surfaced as a score
    # caveat rather than suppressed, since ThesisTrace shows models side by side.
    like_for_like: bool = True
    mismatch_reason: str | None = None
    # CIKs for which this source must NEVER resolve, even though the tag is a safe,
    # proven fallback for every OTHER issuer that files it. Distinct from
    # like_for_like/mismatch_reason, which ANNOTATES a value that is still correct to
    # use — this SUPPRESSES a value that would be wrong for the excluded issuer
    # specifically. First needed for ZTS (Story 12.3): the restricted-cash-inclusive
    # tag is proven equal to unrestricted cash for QSR (3 overlap years, exact match)
    # but ZTS discloses real restricted cash ($2-6M) in the same years the fallback
    # would otherwise fire, which the QSR proof does not cover and cannot extend to.
    excludes_issuers: tuple[str, ...] = ()
    # Accession numbers whose facts must NEVER resolve for this source, even though
    # the tag is a safe, proven source for every OTHER filing of this concept —
    # including every OTHER filing by the SAME issuer. Distinct from
    # excludes_issuers (which suppresses a tag for an issuer across its whole
    # history because the TAG itself measures the wrong thing for that issuer) —
    # this suppresses one SPECIFIC FILING whose own tagged data for this concept is
    # wrong, confirmed by comparing it against the issuer's own later, corrected
    # comparatives. First needed for OTEX's shares_outstanding (v12):
    # otex_shares_outstanding_scale_error_fy2007_fy2009 — its FY2009 10-K (its
    # first-ever XBRL filing, accession 0001193125-09-179839) mis-scaled
    # WeightedAverageNumberOfSharesOutstandingBasic by 1000x for the years it
    # originally reports, self-corrected in every later filing's comparative
    # column with no formal amendment.
    excludes_accessions: tuple[str, ...] = ()
    # A property of the CANONICAL CONCEPT, not of any one source tag — declared on
    # the concept body (`capex: {non_negative: true, ...}`) and copied onto every
    # source rule generated for it, same pattern as `note` falling back to the
    # body's own note. True for a concept that is definitionally a magnitude (a
    # cash outflow can never be negative) where a filer's own sign convention has
    # been found to disagree with that definition. canonicalize.py takes abs(value)
    # for these concepts at selection time. First needed for capex (v10):
    # otex_capex_sign_error_fy2007_fy2009.
    non_negative: bool = False


@dataclass(frozen=True)
class DerivationRule:
    """A canonical concept COMPUTED from other canonical concepts, not read from a
    filed tag. `rule` is the name recorded on CanonicalFact.derivation."""

    rule: str
    kind: str
    canonical_concept: str
    operation: str
    operands: tuple[str, ...]
    provenance_from: str
    # Maintainer-facing; may cite decision records and file paths.
    note: str | None = None
    # PUBLISHED verbatim on the public methodology page — must stand alone.
    rationale: str | None = None
    # operand -> source concepts it must have resolved from for this rule to fire.
    # An operand can be canonically correct yet measure the wrong thing: Suncor's
    # cogs comes from an inventories-only by-nature tag, so deriving gross profit
    # from it would OVERSTATE margin. Absent = the operand's source is unconstrained.
    requires_source: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def expression(self) -> str:
        """`a + b` / `a - b`, generated from the operands so the published formula
        cannot drift from the one actually applied."""
        symbol = {"add": "+", "subtract": "-"}[self.operation]
        return f" {symbol} ".join(self.operands)


@dataclass(frozen=True)
class MappingSpec:
    mapping_version: str
    rules: tuple[MappingRule, ...]
    derivations: tuple[DerivationRule, ...]
    source_to_canonical: dict[tuple[str, str], str]
    source_priority: dict[tuple[str, str], int]
    # (taxonomy, source concept) -> why a fact from it is not strictly comparable.
    source_mismatch: dict[tuple[str, str], str]
    # (taxonomy, source concept) -> CIKs for which this source must never resolve.
    source_excluded_issuers: dict[tuple[str, str], frozenset[str]]
    # (taxonomy, source concept) -> accession numbers whose facts must never resolve
    # for this source, regardless of issuer (an accession already implies one).
    source_excluded_accessions: dict[tuple[str, str], frozenset[str]]
    # Canonical concepts that are definitionally non-negative magnitudes — a filer's
    # own sign convention has been found to disagree with the definition for at
    # least one of them. Consulted by canonicalize.py to abs() the value at
    # selection time, before the ambiguity check.
    non_negative_concepts: frozenset[str]


def _load_taxonomy_rules(spec_version: str) -> tuple[MappingRule, ...]:
    path = SPECS_DIR / f"{spec_version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Mapping spec not found: {path}")
    data = yaml.safe_load(path.read_text())
    taxonomy = data["taxonomy"]

    rules: list[MappingRule] = []
    for canonical_concept, body in data["concepts"].items():
        sources = body["sources"]
        if not sources:
            raise ValueError(f"{path.name}: {canonical_concept} declares no sources")
        # List position is the priority — the fallback chain orders itself.
        for priority, source in enumerate(sources):
            rules.append(
                MappingRule(
                    canonical_concept=canonical_concept,
                    source_taxonomy=taxonomy,
                    source_concept=source["concept"],
                    priority=priority,
                    note=source.get("note") or body.get("note"),
                    like_for_like=source.get("like_for_like", True),
                    mismatch_reason=source.get("mismatch_reason"),
                    excludes_issuers=tuple(source.get("excludes_issuers") or ()),
                    excludes_accessions=tuple(source.get("excludes_accessions") or ()),
                    non_negative=body.get("non_negative", False),
                )
            )
    return tuple(rules)


def _load_derivations(spec_version: str) -> tuple[DerivationRule, ...]:
    path = SPECS_DIR / f"{spec_version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Derivation spec not found: {path}")
    data = yaml.safe_load(path.read_text())

    derivations: list[DerivationRule] = []
    for entry in data.get("derivations", []):
        operation = entry["operation"]
        if operation not in DERIVATION_OPERATIONS:
            raise ValueError(f"{path.name}: unknown derivation operation {operation!r}")
        kind = entry.get("kind")
        if kind not in DERIVATION_KINDS:
            raise ValueError(
                f"{path.name}: {entry['rule']!r} declares kind {kind!r}; must be one of "
                f"{sorted(DERIVATION_KINDS)} — a derivation has to say whether it is arithmetic "
                "or a judgment, because the methodology page presents them differently"
            )
        for field in ("note", "rationale"):
            if not entry.get(field):
                raise ValueError(
                    f"{path.name}: {entry['rule']!r} has no {field}. `note` explains the rule to "
                    "whoever maintains it; `rationale` is published verbatim on the public "
                    "methodology page. A derivation nobody can explain should not run."
                )
        operands = tuple(entry["operands"])
        if len(operands) != 2:
            raise ValueError(f"{path.name}: {operation!r} takes exactly 2 operands, got {len(operands)}")
        if entry["provenance_from"] not in operands:
            raise ValueError(
                f"{path.name}: provenance_from {entry['provenance_from']!r} is not one of "
                f"the operands {operands} — a derived fact must anchor to a fact it was built from"
            )
        requires_source = entry.get("requires_source") or {}
        unknown = set(requires_source) - set(operands)
        if unknown:
            raise ValueError(
                f"{path.name}: requires_source names {sorted(unknown)}, which are not operands "
                f"of {entry['rule']!r} — the constraint would never be checked"
            )
        derivations.append(
            DerivationRule(
                rule=entry["rule"],
                kind=kind,
                canonical_concept=entry["canonical_concept"],
                operation=operation,
                operands=operands,
                provenance_from=entry["provenance_from"],
                note=entry.get("note"),
                rationale=entry.get("rationale"),
                requires_source=tuple(
                    (operand, tuple(sources)) for operand, sources in sorted(requires_source.items())
                ),
            )
        )
    return tuple(derivations)


@lru_cache(maxsize=None)
def load_mapping_spec() -> MappingSpec:
    """Load and cache the mapping set named by specs/registry.yaml."""
    registry = yaml.safe_load((SPECS_DIR / "registry.yaml").read_text())

    rules: tuple[MappingRule, ...] = ()
    for spec_version in registry["taxonomies"].values():
        rules += _load_taxonomy_rules(spec_version)

    # One source tag must not map to two canonical concepts: canonicalization looks
    # up (taxonomy, concept) and a duplicate would make the winner load-order-dependent.
    seen: dict[tuple[str, str], str] = {}
    for rule in rules:
        key = (rule.source_taxonomy, rule.source_concept)
        if key in seen and seen[key] != rule.canonical_concept:
            raise ValueError(
                f"{key} maps to both {seen[key]!r} and {rule.canonical_concept!r} — "
                "one source concept may map to only one canonical concept"
            )
        seen[key] = rule.canonical_concept
        if not rule.like_for_like and not rule.mismatch_reason:
            raise ValueError(
                f"{key} is marked like_for_like: false without a mismatch_reason — "
                "the caveat shown to a user has to say what differs"
            )

    return MappingSpec(
        mapping_version=registry["mapping_version"],
        rules=rules,
        derivations=_load_derivations(registry["derivations"]),
        source_to_canonical=dict(seen),
        source_priority={(r.source_taxonomy, r.source_concept): r.priority for r in rules},
        source_mismatch={
            (r.source_taxonomy, r.source_concept): r.mismatch_reason
            for r in rules
            if not r.like_for_like and r.mismatch_reason
        },
        source_excluded_issuers={
            (r.source_taxonomy, r.source_concept): frozenset(r.excludes_issuers)
            for r in rules
            if r.excludes_issuers
        },
        source_excluded_accessions={
            (r.source_taxonomy, r.source_concept): frozenset(r.excludes_accessions)
            for r in rules
            if r.excludes_accessions
        },
        # A concept-level fact, not a per-taxonomy one — the union across whichever
        # taxonomy spec(s) declared it, so a concept flagged in only one taxonomy
        # (capex, us-gaap only as of v10) still normalizes consistently everywhere
        # it appears.
        non_negative_concepts=frozenset(r.canonical_concept for r in rules if r.non_negative),
    )


_SPEC = load_mapping_spec()

MAPPING_VERSION: str = _SPEC.mapping_version
MAPPING_RULES: tuple[MappingRule, ...] = _SPEC.rules
DERIVATION_RULES: tuple[DerivationRule, ...] = _SPEC.derivations

# Source (taxonomy, concept) -> canonical concept, for quick lookup during canonicalization.
SOURCE_TO_CANONICAL: dict[tuple[str, str], str] = _SPEC.source_to_canonical

# Source (taxonomy, concept) -> priority, consulted by canonicalize.py's rank() so that
# when several source concepts map to the same canonical concept (e.g. the shares_outstanding
# fallback chain) the lower-priority-number concept wins outright rather than being compared
# for value-ambiguity against a fundamentally different measurement.
SOURCE_PRIORITY: dict[tuple[str, str], int] = _SPEC.source_priority

# Source (taxonomy, concept) -> why a value from it is not strictly comparable across
# filers. Consulted by scoring to annotate a run, never to alter or suppress a number.
SOURCE_MISMATCH: dict[tuple[str, str], str] = _SPEC.source_mismatch

# Source (taxonomy, concept) -> CIKs for which canonicalize_issuer must never admit a
# fact from this source as a candidate — a proven-safe fallback for the filers it was
# added for can still be wrong for a specific other issuer (AD-16: never silently
# resolve a value known to be wrong for that issuer).
SOURCE_EXCLUDED_ISSUERS: dict[tuple[str, str], frozenset[str]] = _SPEC.source_excluded_issuers

# Source (taxonomy, concept) -> accession numbers whose facts must never be admitted
# as candidates for this source — one SPECIFIC FILING's own tagged data for this
# concept is wrong (confirmed by comparing it against the same issuer's later,
# corrected comparatives), not the tag itself. An accession number already implies
# its issuer, so no per-issuer keying is needed the way SOURCE_EXCLUDED_ISSUERS has.
SOURCE_EXCLUDED_ACCESSIONS: dict[tuple[str, str], frozenset[str]] = _SPEC.source_excluded_accessions

# Canonical concepts (e.g. "capex") that are definitionally non-negative magnitudes.
# canonicalize.py takes abs(value) for these at selection time, before the
# ambiguity check, so a filer's own sign-convention error doesn't get selected
# outright (a lone wrong-signed candidate) or flagged as an unresolvable conflict
# (two candidates agreeing on magnitude but disagreeing on sign).
NON_NEGATIVE_CONCEPTS: frozenset[str] = _SPEC.non_negative_concepts


async def seed_concept_mappings(session: AsyncSession, *, version: str = MAPPING_VERSION) -> int:
    """Insert the mapping rules for `version` if not already present. Returns rows added."""
    existing = set(
        (
            await session.execute(
                select(ConceptMapping.canonical_concept, ConceptMapping.source_concept).where(
                    ConceptMapping.mapping_version == version
                )
            )
        ).all()
    )
    added = 0
    for rule in MAPPING_RULES:
        if (rule.canonical_concept, rule.source_concept) in existing:
            continue
        session.add(
            ConceptMapping(
                mapping_version=version,
                canonical_concept=rule.canonical_concept,
                source_taxonomy=rule.source_taxonomy,
                source_concept=rule.source_concept,
                priority=rule.priority,
            )
        )
        added += 1
    await session.flush()
    return added
