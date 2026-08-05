"""Story 5.7 — year-by-year debt maturity profile.

Enrichment, not a metric: it shows a filer's own published repayment schedule
where one exists, and shows nothing at all where one does not.

The tests that matter most here are the ones stopping this from being quietly
merged with the near-term debt share. The two are DIFFERENT MEASUREMENTS — the
ladder is undiscounted contractual principal, `total_debt` is balance-sheet
carrying amount — and the numbers are close enough that a wrong presentation
looks right. Verified live 2026-08-05: QSR FY2023's complete ladder sums to
13,043M against a filed total of 12,921M.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import yaml

from canonicalization.mappings import SOURCE_TO_CANONICAL
from debt.profile import (
    PROFILE_CONCEPTS,
    SPEC_PATH,
    MaturityProfile,
    load_profile_spec,
    profile_for_facts,
)

LADDER_TAGS = {
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths": "debt_maturity_year_1",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo": "debt_maturity_year_2",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree": "debt_maturity_year_3",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour": "debt_maturity_year_4",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive": "debt_maturity_year_5",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive": "debt_maturity_thereafter",
}


class _F:
    """Minimal stand-in for a CanonicalFact row."""

    def __init__(self, concept, fiscal_year, value, unit="USD", accession="0000000000-00-000000"):
        self.canonical_concept = concept
        self.fiscal_year = fiscal_year
        self.value = value
        self.unit = unit
        self.accession_number = accession


def _full_ladder(fy=2023, **overrides):
    base = {
        "debt_maturity_year_1": 67_000_000,
        "debt_maturity_year_2": 706_000_000,
        "debt_maturity_year_3": 84_000_000,
        "debt_maturity_year_4": 115_000_000,
        "debt_maturity_year_5": 3_505_000_000,
        "debt_maturity_thereafter": 8_566_000_000,
    }
    base.update(overrides)
    return [_F(c, fy, v) for c, v in base.items() if v is not None]


# --- mapping: the ladder is mapped, but never to the share's operands --------


def test_ladder_tags_map_to_their_own_concepts():
    for tag, expected in LADDER_TAGS.items():
        assert SOURCE_TO_CANONICAL.get(("us-gaap", tag)) == expected, f"{tag} not mapped to {expected}"


def test_ladder_never_feeds_the_near_term_share():
    """The refined form of Story 5.6's `test_maturity_ladder_tags_are_not_mapped`.

    That guard asserted the ladder was unmapped ENTIRELY, which this story makes
    false. Its real invariant survives: the ladder is a different measurement
    basis, so it must never reach `near_term_debt` or `total_debt`. Verified live
    that they genuinely differ — 11 of 15 shared years for CP, 10 of 10 for OTEX.
    """
    for tag in LADDER_TAGS:
        assert SOURCE_TO_CANONICAL.get(("us-gaap", tag)) not in ("near_term_debt", "total_debt"), (
            f"{tag} feeds the near-term share. The ladder is undiscounted contractual "
            "principal; the share's operands are balance-sheet carrying amounts."
        )


def test_no_ifrs_ladder_is_mapped():
    """Under IFRS the maturity analysis is a dimensional disclosure, and the
    company-facts API exposes only non-dimensional facts — structurally
    unreachable, not merely absent. Re-confirmed live 2026-08-05: none of Cameco,
    BCE or Suncor carries any maturity-analysis concept."""
    ifrs_mapped = {c for (tax, _), c in SOURCE_TO_CANONICAL.items() if tax == "ifrs-full"}
    assert not (ifrs_mapped & set(PROFILE_CONCEPTS)), "an ifrs-full tag was mapped to a profile concept"


# --- the profile itself ------------------------------------------------------


def test_complete_ladder_yields_an_untruncated_profile():
    profile = profile_for_facts(_full_ladder())[2023]
    assert isinstance(profile, MaturityProfile)
    assert profile.truncated is False
    assert [b.label for b in profile.buckets] == [
        "Within 1 year", "Year 2", "Year 3", "Year 4", "Year 5", "After year 5",
    ]
    assert profile.buckets[0].value == Decimal("67000000")
    assert profile.buckets[-1].value == Decimal("8566000000")


def test_missing_thereafter_is_reported_as_truncated():
    """CP FY2010-2021 is this case, and the gap is not cosmetic: FY2021's buckets
    sum to 7,376M against a filed total debt of 20,127M."""
    profile = profile_for_facts(_full_ladder(debt_maturity_thereafter=None))[2023]
    assert profile.truncated is True
    assert [b.label for b in profile.buckets] == [
        "Within 1 year", "Year 2", "Year 3", "Year 4", "Year 5",
    ]


def test_no_middle_years_yields_no_profile_at_all():
    """OTEX tags a next-twelve-months bucket and a thereafter bucket but NEVER
    years 2-5 (confirmed live 2026-08-05). Rendering those two alone would imply
    a schedule with a hole in it. There is no profile, not an empty one."""
    facts = [
        _F("debt_maturity_year_1", 2023, 10_000_000),
        _F("debt_maturity_thereafter", 2023, 600_000_000),
    ]
    assert profile_for_facts(facts) == {}


def test_a_filer_with_no_ladder_yields_no_profile():
    assert profile_for_facts([]) == {}
    assert profile_for_facts([_F("total_debt", 2023, 1)]) == {}


def test_years_are_independent():
    facts = _full_ladder(2023) + _full_ladder(2022, debt_maturity_thereafter=None)
    out = profile_for_facts(facts)
    assert out[2023].truncated is False
    assert out[2022].truncated is True


def test_values_are_decimal_never_float():
    """AD-15: financial figures are NUMERIC/DECIMAL only."""
    for bucket in profile_for_facts(_full_ladder())[2023].buckets:
        assert isinstance(bucket.value, Decimal)


def test_buckets_carry_provenance():
    """AD-19: a value with no resolvable provenance is not displayed as fact."""
    for bucket in profile_for_facts(_full_ladder())[2023].buckets:
        assert bucket.canonical_concept.startswith("debt_maturity_")
        assert bucket.accession_number
        assert bucket.fiscal_year == 2023


def test_profile_carries_the_unit_it_was_filed_in():
    """CP files in CAD and this story shows ABSOLUTE amounts, unlike the
    near-term share which sidesteps currency by being a ratio."""
    facts = [_F(c, 2023, 1, unit="CAD") for c in PROFILE_CONCEPTS]
    assert profile_for_facts(facts)[2023].unit == "CAD"


def test_profile_never_reports_a_total_or_a_share_of_total_debt():
    """AC 4. Even a COMPLETE ladder does not reconcile to total_debt — QSR FY2023
    sums to 13,043M against a filed 12,921M — so exposing a total, or a
    percentage of one, would assert a reconciliation that does not hold."""
    profile = profile_for_facts(_full_ladder())[2023]
    forbidden = {"total", "sum", "share", "pct", "percent", "of_total", "total_debt"}
    for attr in vars(profile):
        assert not any(f in attr.lower() for f in forbidden), (
            f"MaturityProfile exposes {attr!r}. The ladder is undiscounted contractual "
            "principal and does not reconcile to total_debt; do not offer a total."
        )
    for bucket in profile.buckets:
        for attr in vars(bucket):
            assert not any(f in attr.lower() for f in forbidden), f"bucket exposes {attr!r}"


# --- the spec ----------------------------------------------------------------


def test_spec_is_a_thesistrace_presentation_rule():
    assert load_profile_spec()["kind"] == "thesistrace_presentation_rule"


def test_basis_warning_is_machine_readable_not_a_comment():
    """This trap has now recurred three times — D8's `derivations_v2`, Story 5.5's
    `trajectory_v1`, and it was called out in this story's Dev Notes. A YAML
    comment is not a published field; nobody downstream can read it."""
    spec = load_profile_spec()
    basis = yaml.safe_dump(spec.get("basis", {})).lower()
    assert "undiscounted" in basis
    assert "carrying amount" in basis
    assert spec["basis"]["reconciles_to_total_debt"] is False


def test_attribution_defuses_both_misreadings():
    """The attribution travels with every rendering, and it has TWO jobs.

    The second was only visible in a browser: CP FY2023 renders "3.1B of 22.5B"
    in the near-term share card and "3.13B" as the first row of the schedule
    immediately beneath it. Those are different measurements — 3,143M carrying
    amount vs 3,133M undiscounted principal — but at display precision they read
    as one figure restated. Saying only "does not add up to the total" leaves
    that confusion untouched.
    """
    attribution = load_profile_spec()["attribution"].lower()
    assert "does not add up to the total" in attribution, "must defuse the reconciliation misreading"
    assert "near-term debt share" in attribution, "must defuse the first-bucket misreading"


def test_spec_file_parses_and_declares_its_concepts():
    data = yaml.safe_load(SPEC_PATH.read_text())
    assert data["rule"] == "debt_maturity_profile"
    assert list(data["buckets"]) == list(PROFILE_CONCEPTS)


@pytest.mark.parametrize("concept", PROFILE_CONCEPTS)
def test_every_profile_concept_is_mapped_somewhere(concept):
    assert concept in set(SOURCE_TO_CANONICAL.values()), f"{concept} declared but never mapped"
