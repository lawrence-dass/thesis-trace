"""Sensitivity grid for the reverse DCF (Story 6.4).

The single implied growth rate from `reverse_dcf.compute` is one point in a space of
defensible assumptions. This solves the same question across a declared grid of
discount rates and terminal growth rates so the answer reads as a band rather than
a fact.

Two design rules, both enforced by tests:

  * THE RANGE IS THE ANSWER. There is no midpoint, central estimate or "most likely"
    cell, because any such field becomes the headline and undoes the reason for
    showing a range. Same reasoning that keeps a fair value off the single result.

  * A CELL THAT FAILS IS SHOWN, NOT DROPPED. Omitting it would let the grid imply
    its own coverage is complete. Failures are real here: a higher discount rate
    demands more growth to justify the same price, which pushes some filers past the
    solver's search range.

Computed deterministically in Python on the write path (AD-1) — a read never
triggers 35 solves.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from valuation.reverse_dcf import SPEC_VERSION, ReverseDcf, compute, load_spec


def _axis(block: dict) -> tuple[Decimal, ...]:
    """Inclusive range from the spec's from/to/step. Decimal throughout so the axis
    values are exact — a float axis would produce 0.30000000000000004 style labels."""
    start, stop, step = Decimal(block["from"]), Decimal(block["to"]), Decimal(block["step"])
    values, current = [], start
    while current <= stop:
        values.append(current)
        current += step
    return tuple(values)


_GRID = load_spec()["sensitivity_grid"]
DISCOUNT_RATES: tuple[Decimal, ...] = _axis(_GRID["discount_rate"])
TERMINAL_GROWTHS: tuple[Decimal, ...] = _axis(_GRID["terminal_growth"])


@dataclass(frozen=True)
class SensitivityCell:
    """One (discount rate, terminal growth) pair and what it implied — or why not."""

    discount_rate: Decimal
    terminal_growth: Decimal
    implied_growth: Decimal | None
    reason: str | None


@dataclass(frozen=True)
class SensitivityGrid:
    """The band of implied growth across the declared assumption space.

    Deliberately carries NO midpoint, central or modal value. See the module
    docstring; `test_sensitivity.py` asserts their absence.
    """

    fiscal_year: int
    cells: tuple[SensitivityCell, ...]
    #: The band. `None` when no cell resolved at all.
    low: Decimal | None
    high: Decimal | None
    resolved_cells: int
    total_cells: int
    discount_rates: tuple[Decimal, ...]
    terminal_growths: tuple[Decimal, ...]
    spec_version: str

    @property
    def fully_resolved(self) -> bool:
        """True when every combination produced an answer. False is not a defect —
        it is information about where the assumptions stop working for this filer."""
        return self.resolved_cells == self.total_cells


def grid_for(base: ReverseDcf, **operands) -> SensitivityGrid | None:
    """Solve the grid around an already-computed base result.

    Returns None when the base itself is `insufficient_data`: if the model does not
    apply at the default assumptions it does not apply at any of them, and a grid of
    35 identical refusals is noise rather than information.

    `operands` are the same values the base was computed from — passed rather than
    re-derived so this cannot silently disagree with the figure it is a range around.
    """
    if base.insufficient_data:
        return None

    cells: list[SensitivityCell] = []
    for discount_rate in DISCOUNT_RATES:
        for terminal_growth in TERMINAL_GROWTHS:
            result = compute(
                fiscal_year=base.fiscal_year,
                free_cash_flow=base.free_cash_flow,
                market_cap=base.market_cap,
                total_debt=base.total_debt,
                cash_and_equivalents=base.cash_and_equivalents,
                discount_rate=discount_rate,
                terminal_growth=terminal_growth,
                **operands,
            )
            cells.append(
                SensitivityCell(
                    discount_rate=discount_rate,
                    terminal_growth=terminal_growth,
                    implied_growth=result.implied_growth,
                    reason=result.reason,
                )
            )

    resolved = [c.implied_growth for c in cells if c.implied_growth is not None]
    return SensitivityGrid(
        fiscal_year=base.fiscal_year,
        cells=tuple(cells),
        low=min(resolved) if resolved else None,
        high=max(resolved) if resolved else None,
        resolved_cells=len(resolved),
        total_cells=len(cells),
        discount_rates=DISCOUNT_RATES,
        terminal_growths=TERMINAL_GROWTHS,
        spec_version=SPEC_VERSION,
    )
