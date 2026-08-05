"""Story 5.6 — near-term debt share.

Covers the engine, the spec's own integrity, and the mapping decisions that the
live-EDGAR verification settled. The mapping assertions are deliberately concrete:
they are what stops a later spec edit from silently reintroducing a source whose
measurement basis was rejected for a reason.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import yaml

from canonicalization.mappings import DERIVATION_RULES, SOURCE_TO_CANONICAL
from debt.engine import SPEC_PATH, compute, load_spec, shares_for_facts


# --- the figure itself ------------------------------------------------------


def test_computes_the_share():
    result = compute(fiscal_year=2024, near_term_debt=250, total_debt=1000)
    assert result.value == Decimal("0.25")
    assert result.insufficient_data is False


@pytest.mark.parametrize(
    "near_term, total, expected_label",
    [
        (5, 1000, "Well spread"),
        (100, 1000, "Well spread"),  # boundary is inclusive
        (101, 1000, "Moderate near-term load"),
        (250, 1000, "Moderate near-term load"),
        (251, 1000, "Concentrated near term"),
        (1000, 1000, "Concentrated near term"),
    ],
)
def test_bands(near_term, total, expected_label):
    assert compute(fiscal_year=2024, near_term_debt=near_term, total_debt=total).label == expected_label


@pytest.mark.parametrize("near_term, total", [(None, 1000), (250, None), (None, None)])
def test_missing_operand_is_insufficient_data_never_zero(near_term, total):
    """AD-16: a missing input is insufficient_data, never a defaulted 0."""
    result = compute(fiscal_year=2024, near_term_debt=near_term, total_debt=total)
    assert result.insufficient_data is True
    assert result.value is None
    assert result.label == "Not disclosed"


def test_zero_total_debt_is_insufficient_data_not_zero_percent():
    """A company with no debt has no maturity profile. Reporting 0% would imply a
    well-spread schedule that does not exist."""
    result = compute(fiscal_year=2024, near_term_debt=0, total_debt=0)
    assert result.insufficient_data is True
    assert result.value is None


def test_a_filed_zero_numerator_is_a_real_value():
    """The other edge of AD-16, and a real case: Cameco files a current portion of
    exactly zero in FY2017, FY2019, FY2022 and FY2025 — no debt matured within
    twelve months. That is a genuine 0.0%, not missing data. Verified live
    2026-08-04."""
    result = compute(fiscal_year=2017, near_term_debt=0, total_debt=Decimal("1494471000"))
    assert result.insufficient_data is False
    assert result.value == Decimal("0")
    assert result.label == "Well spread"


def test_share_is_exact_not_float_rounded():
    result = compute(fiscal_year=2024, near_term_debt=Decimal("1"), total_debt=Decimal("3"))
    assert isinstance(result.value, Decimal)


def test_every_result_carries_attribution_and_spec_version():
    """A consumer must not be able to render the bands without saying whose
    judgment they are — including on the insufficient_data path."""
    for kwargs in ({"near_term_debt": 250, "total_debt": 1000}, {"near_term_debt": None, "total_debt": None}):
        result = compute(fiscal_year=2024, **kwargs)
        assert "ThesisTrace" in result.attribution
        assert result.spec_version == "near_term_debt_share_v1"


def test_shares_for_facts_pairs_operands_by_year():
    class F:
        def __init__(self, concept, fy, value):
            self.canonical_concept, self.fiscal_year, self.value = concept, fy, value

    facts = [
        F("near_term_debt", 2024, 100),
        F("total_debt", 2024, 1000),
        F("near_term_debt", 2023, 500),  # no total_debt for 2023
        F("total_assets", 2024, 99999),  # unrelated concept, must be ignored
    ]
    out = shares_for_facts(facts)
    assert out[2024].value == Decimal("0.1")
    assert out[2023].insufficient_data is True


# --- the spec is ours, and says so ------------------------------------------


def test_spec_is_a_presentation_rule_not_a_model():
    spec = load_spec()
    assert spec["kind"] == "thesistrace_presentation_rule"
    assert spec["authored_by"] == "thesistrace"


def test_model_specs_cannot_be_loaded_as_this_rule(monkeypatch, tmp_path):
    """The inverse guard: pointing this loader at an academic model spec must fail
    loudly rather than applying Piotroski's thresholds as if they were ours."""
    import debt.engine as engine

    fake = tmp_path / "piotroski_like.yaml"
    fake.write_text(yaml.safe_dump({"model": "piotroski", "bands": []}))
    monkeypatch.setattr(engine, "SPEC_PATH", fake)
    engine.load_spec.cache_clear()
    with pytest.raises(engine.NearTermDebtShareSpecError, match="not a thesistrace_presentation_rule"):
        engine.load_spec()
    engine.load_spec.cache_clear()


def test_bands_are_declared_as_thesistrace_not_published():
    """The D8 `derivations_v2` trap and the 5.5 `trajectory_v1` trap were the same
    shape: the disclaimer lived in a YAML comment, which is not a field any reader
    sees. It has to be in the machine-readable note."""
    note = load_spec()["bands"]["note"]
    assert "ThesisTrace" in note
    assert "not published" in note.lower()


def test_attribution_states_the_short_term_borrowings_exclusion():
    """The limitation is the single most likely way to misread the figure, so it
    travels with every rendering of it, not just with the methodology page."""
    attribution = load_spec()["attribution"]
    assert "short-term" in attribution.lower()


def test_final_band_is_open_ended():
    assert load_spec()["bands"]["tiers"][-1]["max"] is None


def test_published_formula_matches_what_the_engine_computes():
    """A declarative field that drives runtime behaviour needs something enforcing
    that it matches the code — the `piotroski_v1.yaml` inputs lesson."""
    formula = load_spec()["formula"]
    result = compute(fiscal_year=2024, near_term_debt=200, total_debt=800)
    assert formula["expression"] == "near_term_debt / total_debt"
    assert result.value == Decimal("200") / Decimal("800")


# --- the mapping decisions the live verification settled --------------------


def test_maturity_ladder_never_feeds_the_near_term_share():
    """Story 5.6 was specified on the premise that a ladder's first bucket and a
    current-portion tag are the same concept. Live EDGAR (2026-08-04) disproved it:
    they differ in 11 of 15 shared years for CP, 10 of 10 for OTEX, 2 of 12 for
    QSR — undiscounted contractual principal vs balance-sheet carrying amount.
    Mapping either into near_term_debt would mix the two bases.

    REFINED by Story 5.7 (2026-08-05), which maps these tags for the year-by-year
    maturity profile. The original assertion was that they were unmapped
    ENTIRELY — the strongest form available when nothing needed them — and 5.7
    makes that false. The invariant it was actually protecting is unchanged and
    still live: whatever else the ladder feeds, it must never reach the share's
    operands. Narrowed rather than deleted, so the guard survives the thing that
    would otherwise have retired it.
    """
    ladder_tags = [
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalRemainderOfFiscalYear",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive",
    ]
    for tag in ladder_tags:
        assert SOURCE_TO_CANONICAL.get(("us-gaap", tag)) not in ("near_term_debt", "total_debt"), (
            f"{tag} feeds the near-term share. The ladder is a different measurement "
            "basis from the current-portion tag; see us-gaap_v6.yaml's Story 5.6 header."
        )


def test_remainder_of_fiscal_year_stays_unmapped():
    """OTEX uses this as a near-term stub, not a tail bucket, and it belongs to
    neither the share (wrong basis) nor the profile (wrong position in the
    ladder). It has no home, and that is the correct answer."""
    assert ("us-gaap", "LongTermDebtMaturitiesRepaymentsOfPrincipalRemainderOfFiscalYear") not in SOURCE_TO_CANONICAL


def test_ifrs_borrowings_total_is_not_mapped():
    """Suncor's filed `Borrowings` includes short-term borrowings — verified live
    2026-08-04, the gap against CurrentPortion + Longterm equals its
    ShorttermBorrowings to the dollar in FY2016-2018. Using it would put short-term
    debt in Suncor's denominator while every other filer's excludes it."""
    assert ("ifrs-full", "Borrowings") not in SOURCE_TO_CANONICAL


def test_wider_ifrs_current_borrowings_tag_is_not_mapped():
    """BCE's CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings exceeds its
    CurrentPortionOfLongtermBorrowings by 1.4-4.1bn in every shared year — that
    difference is commercial paper and securitization, which the denominator
    excludes."""
    assert ("ifrs-full", "CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings") not in SOURCE_TO_CANONICAL


def test_near_term_and_total_debt_are_mapped_in_both_regimes():
    canonical = set(SOURCE_TO_CANONICAL.values())
    assert "near_term_debt" in canonical
    assert "total_debt" in canonical
    regimes = {tax for (tax, _), concept in SOURCE_TO_CANONICAL.items() if concept == "near_term_debt"}
    assert regimes == {"us-gaap", "ifrs-full"}


def test_cp_resolves_its_near_term_from_the_capital_lease_variant():
    """The spike concluded CP tags no current/noncurrent split and built the whole
    ladder design on it. CP tags no `LongTermDebtCurrent`, but has tagged the
    capital-lease variant for 17 consecutive years (FY2009-2025)."""
    assert SOURCE_TO_CANONICAL[("us-gaap", "LongTermDebtAndCapitalLeaseObligationsCurrent")] == "near_term_debt"


def test_qsr_prefers_the_pure_long_term_debt_tag_over_the_lease_variant():
    """QSR tags both, and they differ by the finance-lease component in all 12
    shared years. Priority must give it the figure that matches its LongTermDebt
    denominator, or numerator and denominator would sit on different bases."""
    from canonicalization.mappings import SOURCE_PRIORITY

    pure = SOURCE_PRIORITY[("us-gaap", "LongTermDebtCurrent")]
    lease_inclusive = SOURCE_PRIORITY[("us-gaap", "LongTermDebtAndCapitalLeaseObligationsCurrent")]
    assert pure < lease_inclusive


def test_total_debt_derivation_is_an_identity_over_the_two_halves():
    rule = next(r for r in DERIVATION_RULES if r.canonical_concept == "total_debt")
    assert rule.kind == "identity"
    assert rule.operation == "add"
    assert set(rule.operands) == {"near_term_debt", "long_term_debt"}
    # The near-term half anchors provenance: a filer can carry long_term_debt in a
    # year where it tags no current portion at all (Cameco FY2020-2021).
    assert rule.provenance_from == "near_term_debt"
    assert rule.rationale and rule.note


def test_spec_file_is_valid_yaml_and_self_describing():
    """`sprint-status.yaml` sat unparseable for two days because nothing ever
    parsed it. A spec that only humans read has the same failure mode."""
    data = yaml.safe_load(SPEC_PATH.read_text())
    assert data["rule"] == "near_term_debt_share"
    assert data["scope"]["excludes_short_term_borrowings"] is True
