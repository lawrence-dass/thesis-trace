"""Story 6.2 — guards on the free-cash-flow operands behind the reverse DCF.

Each test here pins a finding from the live EDGAR verification of 2026-08-07
(`sprint-status.yaml` -> `story_6_2_live_verification`). They are guards on
JUDGEMENTS, not on arithmetic: every one of them encodes a tag that was considered
and deliberately accepted or rejected, so a later edit cannot quietly reverse the
decision without the reasoning resurfacing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from canonicalization.mappings import DERIVATION_RULES, MAPPING_RULES

SPECS = Path(__file__).resolve().parents[1] / "canonicalization" / "mappings" / "specs"

#: Tags a filer files that LOOK like the concept and are not it.
REJECTED_CAPEX_TAGS = {"CapitalExpendituresIncurredButNotYetPaid"}


def _sources(concept: str, taxonomy: str | None = None) -> list[str]:
    return [
        r.source_concept
        for r in MAPPING_RULES
        if r.canonical_concept == concept and (taxonomy is None or r.source_taxonomy == taxonomy)
    ]


@pytest.mark.parametrize("tag", sorted(REJECTED_CAPEX_TAGS))
def test_accrual_capex_tags_are_never_a_capex_source(tag: str) -> None:
    """`CapitalExpendituresIncurredButNotYetPaid` is capex INCURRED BUT UNPAID at the
    balance-sheet date — an accrual disclosure, not a cash outflow. Free cash flow
    subtracts capex from `cash_from_operations`, a cash figure, so admitting it would
    mix bases and double-count.

    Load-bearing rather than theoretical: confirmed live 2026-08-07 that SHOP tags it
    for 8 years and QSR for 4, so it is genuinely present and genuinely tempting."""
    assert tag not in _sources("capex"), (
        f"{tag} is an accrual disclosure, not cash capex — see us-gaap_v7.yaml"
    )


def test_otex_capex_variant_is_mapped() -> None:
    """OTEX has NEVER tagged PaymentsToAcquirePropertyPlantAndEquipment. Its only
    capex tag is PaymentsToAcquireProductiveAssets (FY2007-2026, 20 years, live
    2026-08-07). Checking the common tag alone reports OTEX as having no capex —
    the documented 'filers use different variants' trap."""
    assert "PaymentsToAcquireProductiveAssets" in _sources("capex", "us-gaap")


def test_cash_excludes_restricted_cash_by_priority() -> None:
    """The unrestricted tag must win outright wherever a filer files it. The
    restricted-inclusive tag is a FALLBACK for QSR's post-FY2018 years only, and
    priority is list position — so an ordering flip would silently switch every
    filer onto the wrong basis."""
    us_gaap = _sources("cash_and_equivalents", "us-gaap")
    assert us_gaap[0] == "CashAndCashEquivalentsAtCarryingValue"
    assert us_gaap.index("CashAndCashEquivalentsAtCarryingValue") < us_gaap.index(
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    )


def test_suncor_has_no_capex_source_and_that_is_not_a_coverage_bug() -> None:
    """Suncor tags no PP&E purchase FLOW at all — only intangibles additions and
    balance-sheet PP&E stock (live 2026-08-07). It is therefore insufficient_data for
    the whole reverse-DCF capability, and the intangibles tag is deliberately NOT a
    fallback: a partial base against a full one, the error the QSR gross-profit
    re-verification refused.

    Pinned so the absence is never later mistaken for a mapping gap and 'fixed'."""
    ifrs_capex = _sources("capex", "ifrs-full")
    assert ifrs_capex == ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"]
    assert not any("Intangible" in s for s in ifrs_capex), (
        "an intangibles-additions tag would understate capex and overstate free cash flow"
    )


def test_bce_cash_comes_from_a_derivation_not_a_fallback() -> None:
    """BCE tags `Cash` and `CashEquivalents` separately and the combined concept
    never, so its cash figure is COMPUTED. The rule must be an identity — cash and
    equivalents is defined as exactly those two components — and must anchor its
    provenance, because a derived value may never wear a filed-line citation
    (AD-19)."""
    rule = next((r for r in DERIVATION_RULES if r.rule == "cash_plus_cash_equivalents"), None)
    assert rule is not None, "BCE has no cash figure at all without this rule"
    assert rule.canonical_concept == "cash_and_equivalents"
    assert rule.operation == "add"
    assert list(rule.operands) == ["cash", "cash_equivalents"]
    assert rule.provenance_from == "cash"


def test_the_operand_concepts_are_ifrs_only_and_never_us_gaap() -> None:
    """`cash` and `cash_equivalents` are halves, not figures. Mapping either under
    us-gaap would let a filer that tags the combined concept resolve a partial value
    and read as though it were the company's cash."""
    assert _sources("cash", "us-gaap") == []
    assert _sources("cash_equivalents", "us-gaap") == []
    assert _sources("cash", "ifrs-full") == ["Cash"]
    assert _sources("cash_equivalents", "ifrs-full") == ["CashEquivalents"]


def test_cash_tags_agree_wherever_a_filer_files_both() -> None:
    """THE GUARD BEHIND THE RESTRICTED-CASH FALLBACK, and the one that matters most.

    Admitting CashCashEquivalentsRestrictedCash... rests on a FILER-SPECIFIC proof:
    QSR files both tags in FY2016-2018 and they are identical to the dollar
    (1,476M / 1,097M / 913M, difference exactly 0), so QSR carries no restricted cash
    and the fallback IS its unrestricted cash.

    That proof does not generalise. For a filer with real restricted cash the fallback
    overstates cash, which understates enterprise value, which understates the implied
    growth rate — a silent error in the FLATTERING direction.

    This test pins the recorded evidence so the assumption is visible and dated. The
    live equality check belongs in the golden dataset (Story 6.7), which has real
    stored values to compare; here we assert that the fallback is documented as
    conditional rather than presented as equivalent."""
    spec = yaml.safe_load((SPECS / "us-gaap_v7.yaml").read_text())
    sources = spec["concepts"]["cash_and_equivalents"]["sources"]
    fallback = next(
        s for s in sources
        if s["concept"] == "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    )
    note = fallback.get("note", "")
    assert "FILER-SPECIFIC" in note, (
        "the restricted-inclusive fallback must state that its equality proof is "
        "filer-specific — a future filer with real restricted cash breaks it"
    )
    assert "1,476M" in note, "the note must carry the overlap-year evidence it rests on"


def test_mapping_version_bumped_for_a_real_mapping_change() -> None:
    """AD-2: new concepts are a mapping CHANGE, so the version must move and the
    stored facts under earlier versions must stay addressable by their own specs."""
    registry = yaml.safe_load((SPECS / "registry.yaml").read_text())
    assert registry["mapping_version"] == "concepts_v8"
    assert registry["taxonomies"]["us-gaap"] == "us-gaap_v7"
    assert registry["taxonomies"]["ifrs-full"] == "ifrs-full_v4"
    assert registry["derivations"] == "derivations_v4"
    for superseded in ("us-gaap_v6.yaml", "ifrs-full_v3.yaml", "derivations_v3.yaml"):
        assert (SPECS / superseded).exists(), (
            f"{superseded} was deleted — stored facts under earlier mapping versions "
            "still point at it (AD-2)"
        )
