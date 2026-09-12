"""Concept mappings — see `engine.py` for the loader and `specs/` for the rules.

Re-exported here so call sites keep importing `canonicalization.mappings`, which
is the seam the pipeline, scoring and the tests already depend on. Whether the
rules live in Python or YAML is an implementation detail behind this name.
"""

from canonicalization.mappings.engine import (
    BRAND_MEMBERS,
    DERIVATION_RULES,
    DIMENSIONED_RULES,
    MAPPING_RULES,
    MAPPING_VERSION,
    MEMBER_LABELS,
    MEMBER_PERIOD_POLICIES,
    MEMBER_RESOLUTION,
    MEMBER_SOURCE_PRIORITY,
    NON_NEGATIVE_CONCEPTS,
    SOURCE_EXCLUDED_ACCESSIONS,
    SOURCE_EXCLUDED_ISSUERS,
    SOURCE_MISMATCH,
    SOURCE_PRIORITY,
    SOURCE_TO_CANONICAL,
    BrandMember,
    DerivationRule,
    DimensionedRule,
    MappingRule,
    MappingSpec,
    load_mapping_spec,
    seed_concept_mappings,
)

__all__ = [
    "BRAND_MEMBERS",
    "DERIVATION_RULES",
    "DIMENSIONED_RULES",
    "MAPPING_RULES",
    "MAPPING_VERSION",
    "MEMBER_LABELS",
    "MEMBER_PERIOD_POLICIES",
    "MEMBER_RESOLUTION",
    "MEMBER_SOURCE_PRIORITY",
    "NON_NEGATIVE_CONCEPTS",
    "SOURCE_EXCLUDED_ACCESSIONS",
    "SOURCE_EXCLUDED_ISSUERS",
    "SOURCE_MISMATCH",
    "SOURCE_PRIORITY",
    "SOURCE_TO_CANONICAL",
    "BrandMember",
    "DerivationRule",
    "DimensionedRule",
    "MappingRule",
    "MappingSpec",
    "load_mapping_spec",
    "seed_concept_mappings",
]
