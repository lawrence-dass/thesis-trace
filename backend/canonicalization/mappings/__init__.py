"""Concept mappings — see `engine.py` for the loader and `specs/` for the rules.

Re-exported here so call sites keep importing `canonicalization.mappings`, which
is the seam the pipeline, scoring and the tests already depend on. Whether the
rules live in Python or YAML is an implementation detail behind this name.
"""

from canonicalization.mappings.engine import (
    DERIVATION_RULES,
    MAPPING_RULES,
    MAPPING_VERSION,
    NON_NEGATIVE_CONCEPTS,
    SOURCE_EXCLUDED_ACCESSIONS,
    SOURCE_EXCLUDED_ISSUERS,
    SOURCE_MISMATCH,
    SOURCE_PRIORITY,
    SOURCE_TO_CANONICAL,
    DerivationRule,
    MappingRule,
    MappingSpec,
    load_mapping_spec,
    seed_concept_mappings,
)

__all__ = [
    "DERIVATION_RULES",
    "MAPPING_RULES",
    "MAPPING_VERSION",
    "NON_NEGATIVE_CONCEPTS",
    "SOURCE_EXCLUDED_ACCESSIONS",
    "SOURCE_EXCLUDED_ISSUERS",
    "SOURCE_MISMATCH",
    "SOURCE_PRIORITY",
    "SOURCE_TO_CANONICAL",
    "DerivationRule",
    "MappingRule",
    "MappingSpec",
    "load_mapping_spec",
    "seed_concept_mappings",
]
