"""Story 6.4 — guards on the reverse-DCF sensitivity grid.

The grid exists to stop a single implied growth rate reading as a fact. Most of
these tests therefore pin what it must NOT do: collapse to a headline number, or
hide the cells where the assumptions stop working.
"""

from __future__ import annotations

from dataclasses import fields
from decimal import Decimal

from valuation.reverse_dcf import (
    DEFAULT_DISCOUNT_RATE as R,
)
from valuation.reverse_dcf import (
    DEFAULT_TERMINAL_GROWTH as G,
)
from valuation.reverse_dcf import (
    compute,
    load_spec,
    present_value,
)
from valuation.sensitivity import (
    DISCOUNT_RATES,
    TERMINAL_GROWTHS,
    SensitivityGrid,
    grid_for,
)


def _base(growth="0.06", fcf="1000"):
    fcf = Decimal(fcf)
    return compute(
        fiscal_year=2025,
        free_cash_flow=fcf,
        market_cap=present_value(fcf, Decimal(growth), R, G),
        total_debt=Decimal(0),
        cash_and_equivalents=Decimal(0),
    )


# --- the range is the answer --------------------------------------------------


def test_the_grid_exposes_no_midpoint_or_central_estimate() -> None:
    """THE GUARD THAT KEEPS THIS A RANGE. Any midpoint, central or "most likely"
    field becomes the headline and undoes the reason for showing a band — the same
    failure the no-fair-value rule prevents on the single result."""
    banned = {"midpoint", "central", "central_estimate", "most_likely", "best_estimate", "mean", "median"}
    names = {f.name for f in fields(SensitivityGrid)}
    assert not (names & banned), f"grid exposes {sorted(names & banned)}"
    assert load_spec()["sensitivity_grid"]["exposes_midpoint"] is False
    assert load_spec()["sensitivity_grid"]["leads_with"] == "range"


def test_the_band_is_the_extremes_of_what_resolved() -> None:
    grid = grid_for(_base())
    resolved = [c.implied_growth for c in grid.cells if c.implied_growth is not None]
    assert grid.low == min(resolved)
    assert grid.high == max(resolved)
    assert grid.low < grid.high, "a one-point band would defeat the purpose"


def test_the_band_is_materially_wider_than_the_base_figure() -> None:
    """Not a tautology — it is the finding. A 6% base spans roughly -10% to +17%
    across defensible assumptions, which is why publishing the single number without
    the band would overstate what is known."""
    base = _base(growth="0.06")
    grid = grid_for(base)
    assert grid.low < base.implied_growth < grid.high
    assert grid.high - grid.low > Decimal("0.10")


# --- failures are shown, never dropped ----------------------------------------


def test_unresolved_cells_are_kept_with_a_reason_not_omitted() -> None:
    """A grid with holes silently implies its own coverage is complete. Reachable:
    a high discount rate demands more growth to justify the same price, which pushes
    some filers past the solver's search range."""
    grid = grid_for(_base(growth="0.90"))
    unresolved = [c for c in grid.cells if c.implied_growth is None]

    assert unresolved, "expected some cells to fail at a 90% base"
    assert not grid.fully_resolved
    assert len(grid.cells) == grid.total_cells == len(DISCOUNT_RATES) * len(TERMINAL_GROWTHS)
    assert grid.resolved_cells < grid.total_cells
    assert all(c.reason for c in unresolved), "an unresolved cell must say why"


def test_a_fully_resolved_grid_reports_itself_as_such() -> None:
    grid = grid_for(_base())
    assert grid.fully_resolved
    assert grid.resolved_cells == grid.total_cells
    assert all(c.reason is None for c in grid.cells)


def test_no_grid_when_the_base_does_not_resolve() -> None:
    """If the model does not apply at the default assumptions it does not apply at
    any of them, and 35 identical refusals is noise rather than information."""
    base = compute(
        fiscal_year=2025,
        free_cash_flow=Decimal("-10"),
        market_cap=Decimal("1000"),
        total_debt=Decimal(0),
        cash_and_equivalents=Decimal(0),
    )
    assert base.insufficient_data
    assert grid_for(base) is None


def test_grid_keeps_cells_when_only_default_growth_is_out_of_range() -> None:
    """A search-bound failure at the default assumptions is not missing data.

    Lower discount rates can bring the same enterprise value back into the search
    range, so discarding the grid would hide exactly the sensitivity evidence the
    feature exists to show.
    """
    base = _base(growth="1.20")
    assert base.insufficient_data
    grid = grid_for(base)
    assert grid is not None
    assert grid.resolved_cells > 0


# --- the axes are the spec's, not the code's ----------------------------------


def test_axes_come_from_the_declared_spec_bounds() -> None:
    """Bounds and step are published so a reader who thinks 7-13% is the wrong band
    for this company can say so precisely."""
    spec = load_spec()["sensitivity_grid"]
    assert DISCOUNT_RATES[0] == Decimal(spec["discount_rate"]["from"])
    assert DISCOUNT_RATES[-1] == Decimal(spec["discount_rate"]["to"])
    assert TERMINAL_GROWTHS[0] == Decimal(spec["terminal_growth"]["from"])
    assert TERMINAL_GROWTHS[-1] == Decimal(spec["terminal_growth"]["to"])
    assert len(DISCOUNT_RATES) == 7
    assert len(TERMINAL_GROWTHS) == 5


def test_every_combination_keeps_terminal_growth_below_the_discount_rate() -> None:
    """The spec claims no cell fails on the divergence condition. Asserted rather
    than trusted — widening either axis could silently break it, and the failure
    would look like an ordinary unresolved cell."""
    for rate in DISCOUNT_RATES:
        for terminal in TERMINAL_GROWTHS:
            assert terminal < rate, f"terminal {terminal} >= discount {rate} diverges"


def test_axis_values_are_exact_decimals() -> None:
    """A float axis produces 0.30000000000000004-style labels and makes a stored
    grid irreproducible (AD-15)."""
    for value in (*DISCOUNT_RATES, *TERMINAL_GROWTHS):
        assert isinstance(value, Decimal)
    assert str(DISCOUNT_RATES[3]) == "0.10"


# --- behaviour that should hold, and would signal a real bug if it did not -----


def test_a_higher_discount_rate_demands_more_implied_growth() -> None:
    """Directional sanity: discounting harder means the same price requires a bigger
    stream to justify it. If this ever inverted, the solver or the axis order would
    be wrong and every rendered band would be misleading."""
    grid = grid_for(_base())
    at_terminal = {
        c.discount_rate: c.implied_growth
        for c in grid.cells
        if c.terminal_growth == G and c.implied_growth is not None
    }
    rates = sorted(at_terminal)
    values = [at_terminal[r] for r in rates]
    assert values == sorted(values), "implied growth must rise with the discount rate"


def test_the_grid_is_deterministic() -> None:
    """Computed once on the write path and stored (AD-1), so the same inputs must
    give the same digits or a stored band could change without any input changing."""
    signatures = {
        tuple(str(c.implied_growth) for c in grid_for(_base()).cells) for _ in range(3)
    }
    assert len(signatures) == 1
