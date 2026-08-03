"""Concept-mapping spec layer (AD-2, AD-3, D8).

Guards the YAML rules themselves and the loader's invariants. Behaviour of the
rules against real filings is covered end to end by test_golden_dataset.py; what
is checked here is that the specs stay structurally sound and that the fallback
chains which cost real live-data debugging keep their exact order.
"""

from __future__ import annotations

from collections import defaultdict

import pytest
import yaml

from canonicalization import mappings
from canonicalization.mappings.engine import (
    SPECS_DIR,
    DerivationRule,
    _load_derivations,
    _load_taxonomy_rules,
    load_mapping_spec,
)
from canonicalization.taxonomies import FINANCIAL_TAXONOMIES


def _by_taxonomy_concept() -> dict[tuple[str, str], list[mappings.MappingRule]]:
    grouped: dict[tuple[str, str], list[mappings.MappingRule]] = defaultdict(list)
    for rule in mappings.MAPPING_RULES:
        grouped[(rule.source_taxonomy, rule.canonical_concept)].append(rule)
    return grouped


def test_every_supported_taxonomy_has_a_spec() -> None:
    """taxonomies.py declares which regimes the pipeline understands; a regime
    declared there but never mapped would ingest raw facts that silently canonicalize
    to nothing."""
    registry = yaml.safe_load((SPECS_DIR / "registry.yaml").read_text())
    assert set(registry["taxonomies"]) == set(FINANCIAL_TAXONOMIES)


def test_mapping_version_is_the_registry_version() -> None:
    registry = yaml.safe_load((SPECS_DIR / "registry.yaml").read_text())
    assert mappings.MAPPING_VERSION == registry["mapping_version"]


def test_rule_counts_per_taxonomy() -> None:
    """30 us-gaap + 30 ifrs-full, covering the same 18 canonical concepts. A change
    here is legitimate only alongside a new spec version (see registry.yaml)."""
    per_taxonomy: dict[str, int] = defaultdict(int)
    concepts: dict[str, set[str]] = defaultdict(set)
    for rule in mappings.MAPPING_RULES:
        per_taxonomy[rule.source_taxonomy] += 1
        concepts[rule.source_taxonomy].add(rule.canonical_concept)

    assert per_taxonomy == {"us-gaap": 30, "ifrs-full": 30}
    assert len(concepts["us-gaap"]) == 18
    assert concepts["us-gaap"] == concepts["ifrs-full"]


def test_priorities_are_contiguous_from_zero() -> None:
    """Priority comes from list position, so a chain must always read 0,1,2… — the
    ordering IS the fallback preference that canonicalize.rank() applies."""
    for (taxonomy, concept), rules in _by_taxonomy_concept().items():
        priorities = sorted(r.priority for r in rules)
        assert priorities == list(range(len(rules))), f"{taxonomy}:{concept} -> {priorities}"


def test_source_concept_maps_to_exactly_one_canonical_concept() -> None:
    """canonicalize.py looks up (taxonomy, concept); a duplicate would make the
    winner depend on spec load order."""
    seen: dict[tuple[str, str], str] = {}
    for rule in mappings.MAPPING_RULES:
        key = (rule.source_taxonomy, rule.source_concept)
        assert seen.get(key, rule.canonical_concept) == rule.canonical_concept
        seen[key] = rule.canonical_concept
    assert len(seen) == len(mappings.MAPPING_RULES)


def test_lookup_tables_agree_with_the_rules() -> None:
    for rule in mappings.MAPPING_RULES:
        key = (rule.source_taxonomy, rule.source_concept)
        assert mappings.SOURCE_TO_CANONICAL[key] == rule.canonical_concept
        assert mappings.SOURCE_PRIORITY[key] == rule.priority


@pytest.mark.parametrize(
    ("taxonomy", "concept", "expected"),
    [
        # Each chain below exists because a specific filer resolved to
        # insufficient_data (or to a wrong value) without it — verified live against
        # data.sec.gov. Reordering one silently breaks that filer, so the order is
        # pinned here as well as in the spec. See the `note` on each for the story.
        (
            "us-gaap",
            "shares_outstanding",
            ["CommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"],
        ),
        (
            "us-gaap",
            "receivables",
            [
                "AccountsReceivableNetCurrent",
                "AccountsNotesAndLoansReceivableNetCurrent",
                "AccountsAndOtherReceivablesNetCurrent",
            ],
        ),
        (
            "us-gaap",
            "ppe_net",
            [
                "PropertyPlantAndEquipmentNet",
                "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
            ],
        ),
        (
            "us-gaap",
            "depreciation",
            ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation"],
        ),
        ("ifrs-full", "revenue", ["Revenue", "RevenueFromContractsWithCustomers"]),
        (
            "ifrs-full",
            "shares_outstanding",
            ["NumberOfSharesOutstanding", "NumberOfSharesIssued", "WeightedAverageShares"],
        ),
    ],
)
def test_hard_won_fallback_chains_keep_their_order(
    taxonomy: str, concept: str, expected: list[str]
) -> None:
    rules = sorted(_by_taxonomy_concept()[(taxonomy, concept)], key=lambda r: r.priority)
    assert [r.source_concept for r in rules] == expected


def test_every_rule_carries_its_verification_note() -> None:
    """A fallback (priority > 0) exists only because live data forced it. Losing the
    note that says which filer and when is how the next session re-derives it the
    hard way, or deletes it as dead weight."""
    unexplained = [
        (r.source_taxonomy, r.canonical_concept, r.source_concept)
        for r in mappings.MAPPING_RULES
        if r.priority > 0 and not r.note
    ]
    assert unexplained == []


# --- derivations -------------------------------------------------------------


def test_assets_minus_equity_derivation_is_declared() -> None:
    by_rule = {d.rule: d for d in mappings.DERIVATION_RULES}
    rule = by_rule["assets_minus_equity"]
    assert rule.canonical_concept == "total_liabilities"
    assert rule.operation == "subtract"
    assert rule.operands == ("total_assets", "stockholders_equity")
    assert rule.provenance_from == "total_assets"


def test_derivations_never_target_a_concept_they_consume() -> None:
    """A rule whose output is also its input would be self-referential; a rule
    consuming another rule's output would compound weak provenance invisibly, and
    _apply_derivations deliberately does not chain."""
    produced = {d.canonical_concept for d in mappings.DERIVATION_RULES}
    for derivation in mappings.DERIVATION_RULES:
        assert not produced.intersection(derivation.operands)


def test_derivation_operands_are_real_canonical_concepts() -> None:
    mapped = {r.canonical_concept for r in mappings.MAPPING_RULES}
    for derivation in mappings.DERIVATION_RULES:
        assert set(derivation.operands) <= mapped, derivation.rule


# --- loader guardrails -------------------------------------------------------


def _write_spec(tmp_path, name: str, body: dict, monkeypatch) -> None:
    (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(body))
    monkeypatch.setattr("canonicalization.mappings.engine.SPECS_DIR", tmp_path)
    load_mapping_spec.cache_clear()


def test_loader_rejects_a_concept_with_no_sources(tmp_path, monkeypatch) -> None:
    _write_spec(
        tmp_path,
        "bad_v1",
        {"taxonomy": "us-gaap", "spec_version": "bad_v1", "concepts": {"revenue": {"sources": []}}},
        monkeypatch,
    )
    with pytest.raises(ValueError, match="declares no sources"):
        _load_taxonomy_rules("bad_v1")


def test_loader_rejects_one_source_tag_mapped_to_two_canonical_concepts(
    tmp_path, monkeypatch
) -> None:
    """The failure mode this prevents: canonicalization silently picking whichever
    concept the spec files happened to load first."""
    _write_spec(
        tmp_path,
        "dupes_v1",
        {
            "taxonomy": "us-gaap",
            "spec_version": "dupes_v1",
            "concepts": {
                "revenue": {"sources": [{"concept": "Revenues"}]},
                "gross_profit": {"sources": [{"concept": "Revenues"}]},
            },
        },
        monkeypatch,
    )
    (tmp_path / "registry.yaml").write_text(
        yaml.safe_dump(
            {
                "mapping_version": "test_v1",
                "taxonomies": {"us-gaap": "dupes_v1"},
                "derivations": "none_v1",
            }
        )
    )
    (tmp_path / "none_v1.yaml").write_text(yaml.safe_dump({"spec_version": "none_v1", "derivations": []}))

    with pytest.raises(ValueError, match="may map to only one canonical concept"):
        load_mapping_spec()
    load_mapping_spec.cache_clear()


def test_loader_rejects_an_unknown_derivation_operation(tmp_path, monkeypatch) -> None:
    _write_spec(
        tmp_path,
        "badop_v1",
        {
            "spec_version": "badop_v1",
            "derivations": [
                {
                    "rule": "made_up",
                    "canonical_concept": "ebit",
                    "operation": "interpolate",
                    "operands": ["revenue", "cogs"],
                    "provenance_from": "revenue",
                }
            ],
        },
        monkeypatch,
    )
    with pytest.raises(ValueError, match="unknown derivation operation"):
        _load_derivations("badop_v1")


def test_loader_rejects_provenance_anchored_outside_the_operands(tmp_path, monkeypatch) -> None:
    """A derived fact must cite a filing it was actually built from — anchoring it to
    an unrelated concept's accession would put a real accession number on a number
    that filing does not support."""
    _write_spec(
        tmp_path,
        "badanchor_v1",
        {
            "spec_version": "badanchor_v1",
            "derivations": [
                {
                    "rule": "made_up",
                    "canonical_concept": "gross_profit",
                    "operation": "subtract",
                    "operands": ["revenue", "cogs"],
                    "provenance_from": "total_assets",
                }
            ],
        },
        monkeypatch,
    )
    with pytest.raises(ValueError, match="is not one of the operands"):
        _load_derivations("badanchor_v1")


def test_derivation_rule_is_frozen() -> None:
    rule = mappings.DERIVATION_RULES[0]
    assert isinstance(rule, DerivationRule)
    with pytest.raises(Exception):
        rule.operation = "add"  # type: ignore[misc]
