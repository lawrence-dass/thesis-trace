"""Story 6.3 — guards on the reverse-DCF spec and solver.

The valuable tests here are the ones about what the model REFUSES to do. A DCF that
returns a number for everything is easy; the judgements worth pinning are the five
cases where it declines, and the fair value it must never produce.
"""

from __future__ import annotations

from dataclasses import fields
from decimal import Decimal, localcontext

import pytest

from valuation.reverse_dcf import (
    CAVEATS,
    DEFAULT_DISCOUNT_RATE,
    DEFAULT_TERMINAL_GROWTH,
    HORIZON_YEARS,
    LOWER_BOUND,
    UPPER_BOUND,
    ReverseDcf,
    compute,
    load_spec,
    present_value,
)

R = DEFAULT_DISCOUNT_RATE
G = DEFAULT_TERMINAL_GROWTH


def _solve(fcf="1000", ev=None, **kw):
    fcf = Decimal(fcf)
    return compute(
        fiscal_year=2025,
        free_cash_flow=fcf,
        market_cap=Decimal(ev) if ev is not None else present_value(fcf, Decimal("0.05"), R, G),
        total_debt=Decimal(0),
        cash_and_equivalents=Decimal(0),
        **kw,
    )


# --- the solver is right, checked against the forward model -------------------


@pytest.mark.parametrize("target", ["-0.20", "0", "0.03", "0.08", "0.25", "0.60"])
def test_solved_growth_reproduces_enterprise_value(target: str) -> None:
    """Verified by feeding the answer back through `present_value`, not by
    re-running the solver's own arithmetic. Independent verification must not import
    the thing it verifies — the constraint that let the IFRS golden pass catch its
    own averaging error."""
    target_growth = Decimal(target)
    fcf = Decimal("1000")
    enterprise_value = present_value(fcf, target_growth, R, G)

    result = _solve(fcf=str(fcf), ev=str(enterprise_value))

    assert not result.insufficient_data
    assert abs(result.implied_growth - target_growth) < Decimal("0.000001")
    # And the round trip closes: the solved rate reproduces the price it was given.
    assert abs(present_value(fcf, result.implied_growth, R, G) - enterprise_value) < enterprise_value * Decimal("0.00001")


def test_the_solver_is_deterministic() -> None:
    """Fixed bounds, fixed tolerance, fixed iteration cap — the same inputs must give
    the same digits, or a stored figure could change without any input changing."""
    assert len({str(_solve().implied_growth) for _ in range(5)}) == 1


def test_the_solver_is_independent_of_process_decimal_precision() -> None:
    with localcontext() as context:
        context.prec = 6
        low_precision = _solve().implied_growth
    with localcontext() as context:
        context.prec = 40
        high_precision = _solve().implied_growth
    assert low_precision == high_precision


def test_every_figure_is_decimal_never_float() -> None:
    """AD-15. A float here would round differently across platforms and make a
    published figure irreproducible."""
    result = _solve()
    for field in fields(ReverseDcf):
        value = getattr(result, field.name)
        assert not isinstance(value, float), f"{field.name} is a float"
    assert isinstance(result.implied_growth, Decimal)
    assert isinstance(result.enterprise_value, Decimal)


# --- what it refuses to do ----------------------------------------------------


def test_it_never_exposes_a_fair_value_or_target_price() -> None:
    """THE GUARD THAT DEFINES WHAT THIS IS NOT, and the AC calls for it explicitly.

    The natural thing to do with a DCF is print what the company is worth. Doing so
    would turn an assumption-exposing tool into a price target carrying ThesisTrace's
    name — the opposite of why the model is run backwards. Mirrors the maturity
    profile's no-total guard, which exists for the same reason: the obvious rendering
    would be a lie.
    """
    banned = {"fair_value", "intrinsic_value", "target_price", "upside", "valuation", "price_target"}
    names = {f.name for f in fields(ReverseDcf)}
    assert not (names & banned), f"result exposes {sorted(names & banned)}"
    assert load_spec()["output"]["exposes_fair_value"] is False
    assert load_spec()["output"]["exposes_target_price"] is False


@pytest.mark.parametrize(
    "kwargs, expect",
    [
        (dict(free_cash_flow=None), "free cash flow"),
        (dict(market_cap=None), "market capitalisation"),
        (dict(total_debt=None), "total debt"),
        (dict(cash_and_equivalents=None), "cash and equivalents"),
    ],
)
def test_a_missing_operand_is_insufficient_data_naming_it(kwargs, expect) -> None:
    """AD-16: absence explains itself. A reader told only "unavailable" cannot tell a
    coverage gap from a broken pipeline."""
    base = dict(
        fiscal_year=2025,
        free_cash_flow=Decimal("100"),
        market_cap=Decimal("2000"),
        total_debt=Decimal("0"),
        cash_and_equivalents=Decimal("0"),
    )
    result = compute(**{**base, **kwargs})
    assert result.insufficient_data
    assert expect in result.reason


def test_non_positive_free_cash_flow_has_no_answer() -> None:
    """Reachable: SHOP ran negative free cash flow for several years. Growing a
    negative number produces no positive stream, so "what growth justifies this
    price" is not a question with an answer — it is not a zero."""
    result = _solve(fcf="-50", ev="1000")
    assert result.insufficient_data
    assert "negative" in result.reason
    assert result.implied_growth is None


def test_net_cash_exceeding_market_cap_has_no_answer() -> None:
    """A company whose cash exceeds its market cap plus debt has a negative
    enterprise value. Reachable for a cash-rich filer after a drawdown."""
    result = compute(
        fiscal_year=2025,
        free_cash_flow=Decimal("100"),
        market_cap=Decimal("100"),
        total_debt=Decimal("0"),
        cash_and_equivalents=Decimal("500"),
    )
    assert result.insufficient_data
    assert "enterprise value" in result.reason


def test_terminal_growth_at_or_above_the_discount_rate_is_refused() -> None:
    """The perpetuity diverges. Refused rather than clamped, because clamping would
    silently substitute a different assumption than the one the reader chose."""
    result = compute(
        fiscal_year=2025,
        free_cash_flow=Decimal("100"),
        market_cap=Decimal("2000"),
        total_debt=Decimal("0"),
        cash_and_equivalents=Decimal("0"),
        discount_rate=Decimal("0.05"),
        terminal_growth=Decimal("0.05"),
    )
    assert result.insufficient_data
    assert "strictly below" in result.reason


def test_the_search_bounds_are_not_a_clamp() -> None:
    """A price outside the search range must yield insufficient_data NAMING the bound,
    never the bound itself — returning it would present a search limit as a finding."""
    above = _solve(fcf="1", ev="100000000")
    assert above.insufficient_data
    assert above.implied_growth is None
    assert str(UPPER_BOUND) in above.reason

    below = _solve(fcf="1000000", ev="1")
    assert below.insufficient_data
    assert below.implied_growth is None
    assert str(LOWER_BOUND) in below.reason


# --- caveats annotate, never alter --------------------------------------------


def test_a_caveat_annotates_the_figure_and_never_changes_it() -> None:
    """The Cameco out-of-calibration precedent, in the spec's own words: a caveat may
    annotate a score, it must never alter one. Verified by computing the same inputs
    with and without every caveat and asserting the value is identical."""
    plain = _solve()
    flagged = _solve(interest_outside_operating=True, is_capital_intensive=True)
    assert flagged.implied_growth == plain.implied_growth
    assert len(flagged.caveats) == 2
    assert plain.caveats == ()


def test_caveat_reasons_are_stored_as_data_not_inferred() -> None:
    """Model-specific display logic silently applied to another model is a recurring
    bug class here — `bandTone()` omitted Beneish, and the explanation template
    asserted capital intensity as the reason for every caveated run. The text comes
    from the spec, keyed by id, so a consumer never has to guess why."""
    assert set(CAVEATS) == {"interest_classification", "capital_intensity"}
    result = _solve(is_capital_intensive=True)
    assert result.caveats == (CAVEATS["capital_intensity"],)


# --- the spec is the authority ------------------------------------------------


def test_spec_declares_its_authorship_in_a_machine_readable_field() -> None:
    """Required by the AC, and stated as a FIELD rather than a comment for the reason
    this repository has now hit three times: a comment is not a published rationale,
    and the methodology page renders fields."""
    authorship = load_spec()["authorship"]
    assert authorship["is_published_academic_model"] is False
    assert set(authorship["thesistrace_chose"]) >= {
        "forecast_horizon",
        "terminal_value_method",
        "discount_rate_treatment",
        "solve_target",
    }


def test_the_discount_rate_default_declares_that_it_is_not_computed() -> None:
    """A-3. The most consequential number in the model is a SETTING, and the spec has
    to say so — a reader who thinks 10% was derived from this company's capital
    structure has been misled by silence."""
    block = load_spec()["assumptions"]["discount_rate"]
    assert block["treatment"] == "user_supplied"
    assert block["default_origin"] == "convention_not_computed"
    assert Decimal(block["default"]) == DEFAULT_DISCOUNT_RATE


def test_every_published_assumption_has_a_standalone_rationale() -> None:
    """`rationale` is rendered verbatim on /methodology, so it must stand alone for a
    reader who has never seen this repository — the two-audiences trap that shipped
    "DECISION, not an identity — recorded per D8 consequence 3" to end users."""
    for name, block in load_spec()["assumptions"].items():
        rationale = block.get("rationale", "")
        assert rationale.strip(), f"assumption {name} has no rationale"
        for leak in ("D8", "D9", "AD-", "epics.md", "sprint-status", ".yaml"):
            assert leak not in rationale, f"assumption {name} leaks internal reference {leak!r}"


def test_horizon_matches_the_declared_assumption() -> None:
    """The solver reads the horizon from the spec rather than hardcoding five, so the
    published assumption and the applied one cannot drift."""
    assert HORIZON_YEARS == load_spec()["assumptions"]["forecast_horizon"]["years"] == 5
