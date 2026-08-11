"""Story 6.5 — guards on the reverse-DCF read surface.

Two kinds of test here. The pure ones pin the growth-history window, which is the
comparison A-4 exists for and the easiest thing to quietly get wrong. The schema
ones pin what the API must never expose — the same no-fair-value and no-midpoint
rules the engine carries, asserted again at the boundary because that is where a
future field would actually be added.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from api.schemas import CompanyOverviewOut, ReverseDcfOut, SensitivityCellOut
from explanation.methodology import get_methodology
from valuation.overview import DCF_CONCEPTS, historical_revenue_cagr


@dataclass
class _Fact:
    """The function reads the revenue value and its reporting unit."""

    value: Decimal
    unit: str = "USD"


def _years(**revenue_by_year: str) -> dict[int, dict[str, _Fact]]:
    return {int(y): {"revenue": _Fact(Decimal(v))} for y, v in revenue_by_year.items()}


# --- the growth history the implied rate is compared against -------------------


def test_cagr_window_adapts_to_the_filers_actual_history() -> None:
    """THE POINT OF A-4. The window is reported, never promised: IFRS 40-F filers
    start around FY2017 while OTEX runs from FY2007, so a fixed decade-long claim
    would be false for half the universe."""
    cagr, first, last = historical_revenue_cagr(
        _years(**{"2020": "100", "2021": "110", "2022": "121", "2023": "133.1"})
    )
    assert (first, last) == (2020, 2023)
    assert abs(cagr - Decimal("0.10")) < Decimal("0.0001")


def test_a_shorter_history_reports_its_own_shorter_window() -> None:
    cagr, first, last = historical_revenue_cagr(_years(**{"2023": "100", "2024": "150", "2025": "225"}))
    assert (first, last) == (2023, 2025)
    assert abs(cagr - Decimal("0.50")) < Decimal("0.0001")


def test_fewer_than_three_years_is_not_a_trend() -> None:
    """Two points is a single year-over-year change. Reporting it as a CAGR would
    dress one year's move up as a trend the implied rate could be judged against."""
    assert historical_revenue_cagr(_years(**{"2024": "100", "2025": "150"})) == (None, None, None)
    assert historical_revenue_cagr({}) == (None, None, None)


def test_a_non_positive_starting_revenue_yields_no_cagr() -> None:
    """A CAGR from zero or negative revenue is not a growth rate — it is a division
    artefact. Refused rather than returned as a very large number."""
    assert historical_revenue_cagr(_years(**{"2023": "0", "2024": "50", "2025": "100"})) == (
        None,
        None,
        None,
    )


def test_a_non_positive_ending_revenue_yields_no_cagr() -> None:
    """A fractional root of a negative endpoint is not a real CAGR.

    This also guards the AD-15 implementation: the calculation must refuse the
    case rather than falling through to Python's float/complex arithmetic.
    """
    assert historical_revenue_cagr(_years(**{"2023": "100", "2024": "50", "2025": "-25"})) == (
        None,
        None,
        None,
    )


def test_a_shrinking_filer_reports_negative_growth_not_an_absent_one() -> None:
    """Decline is a real answer and must not be confused with missing data — the
    reader comparing an implied 20% against an actual -8% needs the -8%."""
    cagr, _, _ = historical_revenue_cagr(_years(**{"2023": "100", "2024": "90", "2025": "81"}))
    assert cagr < 0


def test_a_long_decline_keeps_the_decimal_root_bounded() -> None:
    """Newton's initial guess must not turn a long decline into explosive growth."""
    cagr, first, last = historical_revenue_cagr(
        _years(**{"2010": "100", "2015": "90", "2020": "80"})
    )
    assert (first, last) == (2010, 2020)
    assert cagr < 0
    assert abs(cagr - Decimal("-0.022067")) < Decimal("0.00001")


def test_cagr_is_not_affected_by_the_process_decimal_context() -> None:
    facts = _years(**{"2010": "120", "2020": "100", "2025": "80"})
    with localcontext() as context:
        context.prec = 6
        low_precision = historical_revenue_cagr(facts)[0]
    with localcontext() as context:
        context.prec = 40
        high_precision = historical_revenue_cagr(facts)[0]
    assert low_precision == high_precision


# --- the read surface ----------------------------------------------------------


def test_the_api_never_exposes_a_fair_value_or_target_price() -> None:
    """Asserted at the boundary as well as on the engine result, because the schema
    is where a well-meaning "and show what it's worth" field would actually be
    added. Same guard the maturity profile has against exposing a total."""
    banned = {"fair_value", "intrinsic_value", "target_price", "upside", "valuation", "price_target"}
    assert not (set(ReverseDcfOut.model_fields) & banned)


def test_the_api_never_exposes_a_midpoint_of_the_band() -> None:
    """A central estimate becomes the headline and undoes the reason for showing a
    range — every real band is ~30 percentage points wide and two cross zero."""
    banned = {"midpoint", "central", "central_estimate", "most_likely", "best_estimate", "mean", "median"}
    assert not (set(ReverseDcfOut.model_fields) & banned)


def test_the_band_and_the_assumptions_travel_with_the_figure() -> None:
    """An implied growth rate without the discount rate that produced it is
    meaningless, and without the band it reads as precise."""
    for field in (
        "range_low",
        "range_high",
        "discount_rate",
        "terminal_growth",
        "horizon_years",
        "attribution",
        "spec_version",
        "caveats",
    ):
        assert field in ReverseDcfOut.model_fields, f"{field} must travel with the figure"


def test_an_unresolved_cell_can_carry_its_reason() -> None:
    """A grid with holes silently implies its own coverage is complete, so the cell
    shape must be able to say why it failed."""
    cell = SensitivityCellOut(
        discount_rate=0.13, terminal_growth=0.015, implied_growth=None, reason="above the search range"
    )
    assert cell.implied_growth is None
    assert cell.reason


def test_insufficient_data_still_carries_a_reason() -> None:
    """AD-16. Three of seven filers are insufficient today — Suncor has no capex,
    SHOP and BCE no total debt — and each reason is different and actionable."""
    assert "reason" in ReverseDcfOut.model_fields
    assert "insufficient_data" in ReverseDcfOut.model_fields


def test_the_overview_carries_the_block_optionally() -> None:
    """None for a filer with no canonical facts at all, rather than an empty object
    the frontend has to interrogate."""
    assert CompanyOverviewOut.model_fields["reverse_dcf"].default is None


def test_the_authored_rule_publishes_its_default_and_origin() -> None:
    """The reverse DCF is not academic, but its assumptions are still public."""
    methodology = get_methodology("reverse_dcf")
    assert methodology is not None
    assert methodology["formula_version"] == "reverse_dcf_v1"
    assert methodology["assumptions"]["discount_rate"]["default"] == "0.10"
    assert methodology["assumptions"]["discount_rate"]["default_origin"] == "convention_not_computed"


def test_public_methodology_does_not_leak_maintainer_notes() -> None:
    methodology = get_methodology("reverse_dcf")
    assert "note" not in str(methodology)
    assert "Story 6.3" not in str(methodology)
    assert "AD-" not in str(methodology)


def test_the_dcf_reads_only_concepts_the_single_fact_query_can_widen_to() -> None:
    """AD-1: the block reuses the caller's existing fact pass rather than issuing its
    own query. If a new operand were added here without widening that query, the
    figure would silently go insufficient_data in production while tests that build
    facts directly kept passing."""
    assert set(DCF_CONCEPTS) == {
        "cash_from_operations",
        "capex",
        "total_debt",
        "cash_and_equivalents",
        "near_term_debt",
        "long_term_debt",
        "cash",
        "cash_equivalents",
        "shares_outstanding",
        "revenue",
        "total_assets",
    }
