"""Reverse DCF — what growth today's price implies (Story 6.3).

Runs a discounted cash flow BACKWARDS. Instead of assuming a growth rate and
producing a value, it takes the market's own enterprise value as given and solves
for the constant growth rate that would justify it. The output is an assumption,
not a valuation.

Three things here are decided by the spec rather than by this module, and all three
are the kind of judgement a reader is entitled to dispute:

  * IT PRODUCES NO FAIR VALUE AND NO TARGET PRICE, ever. The natural thing to do
    with a DCF is print what the company is "worth", and doing that would turn an
    assumption-exposing tool into a price target with ThesisTrace's name on it. A
    test asserts no such attribute exists — the same guard the maturity profile has
    against exposing a total.

  * THE DISCOUNT RATE IS AN INPUT, NOT A DERIVATION. Computing a WACC needs a beta
    and an equity risk premium; neither is in EDGAR and both are judgements. The
    default exists to give the page a starting point, not to be authoritative.

  * THE SEARCH BOUNDS ARE NOT A CLAMP. A price implying growth outside the declared
    range yields `insufficient_data` naming the bound it exceeded. Returning the
    bound would present a search limit as a finding.

Every figure is `Decimal` (AD-15). The bisection is deterministic: fixed bounds, a
fixed tolerance and a fixed iteration cap, so the same inputs give the same digits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from functools import lru_cache
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "formulas" / "specs" / "reverse_dcf_v1.yaml"


class ReverseDcfSpecError(Exception):
    """The spec is missing, malformed, or is not a presentation rule."""


@lru_cache(maxsize=1)
def load_spec() -> dict:
    """Load the versioned rule, rejecting anything that is not explicitly a
    ThesisTrace presentation rule so this loader can never be pointed at one of the
    four academic model specs."""
    if not SPEC_PATH.exists():
        raise ReverseDcfSpecError(f"Reverse DCF spec not found: {SPEC_PATH}")
    data = yaml.safe_load(SPEC_PATH.read_text())
    if data.get("kind") != "thesistrace_presentation_rule":
        raise ReverseDcfSpecError(
            f"{SPEC_PATH.name} is not a thesistrace_presentation_rule; refusing to load it "
            "as one. Academic model specs must not be applied as presentation rules."
        )
    for required in ("assumptions", "solver", "output", "attribution", "spec_version", "authorship"):
        if required not in data:
            raise ReverseDcfSpecError(f"Reverse DCF spec missing {required!r}")

    # Shape checks, not just presence — a malformed spec must fail at load rather
    # than on whichever filer-year happens to exercise the missing field.
    if data["output"].get("exposes_fair_value") is not False:
        raise ReverseDcfSpecError(
            "output.exposes_fair_value must be declared false — running the model "
            "backwards exists precisely to avoid producing a valuation"
        )
    if data["authorship"].get("is_published_academic_model") is not False:
        raise ReverseDcfSpecError(
            "authorship.is_published_academic_model must be declared false — every "
            "parameter here is a ThesisTrace choice and the methodology page says so"
        )
    for assumption in ("forecast_horizon", "terminal_value_method", "discount_rate", "solve_target"):
        block = data["assumptions"].get(assumption)
        if not isinstance(block, dict) or not block.get("rationale"):
            raise ReverseDcfSpecError(
                f"assumptions.{assumption} needs a `rationale` — it is published verbatim "
                "and an assumption nobody can explain should not be applied"
            )
    return data


_SPEC = load_spec()

HORIZON_YEARS: int = int(_SPEC["assumptions"]["forecast_horizon"]["years"])
DEFAULT_DISCOUNT_RATE: Decimal = Decimal(_SPEC["assumptions"]["discount_rate"]["default"])
DEFAULT_TERMINAL_GROWTH: Decimal = Decimal(
    _SPEC["assumptions"]["terminal_value_method"]["default_terminal_growth"]
)
LOWER_BOUND: Decimal = Decimal(_SPEC["solver"]["lower_bound"])
UPPER_BOUND: Decimal = Decimal(_SPEC["solver"]["upper_bound"])
TOLERANCE: Decimal = Decimal(_SPEC["solver"]["tolerance"])
MAX_ITERATIONS: int = int(_SPEC["solver"]["max_iterations"])
DECIMAL_PRECISION = 50
ATTRIBUTION: str = _SPEC["attribution"].strip()
SPEC_VERSION: str = _SPEC["spec_version"]

#: caveat id -> published rationale. Stored as DATA on the result rather than
#: inferred downstream from a shared enum — the recurring bug class where
#: model-specific display logic gets applied to another model.
CAVEATS: dict[str, str] = {c["id"]: c["rationale"].strip() for c in _SPEC["caveats"]}


@dataclass(frozen=True)
class ReverseDcf:
    """One filer-year's implied growth rate, or the reason there isn't one.

    Deliberately carries NO fair value, target price, or "upside" field. See the
    module docstring; `test_reverse_dcf.py` asserts their absence.
    """

    fiscal_year: int
    implied_growth: Decimal | None
    insufficient_data: bool
    reason: str | None
    # Operands, exposed so the result can be independently recomputed (finding 3.5).
    enterprise_value: Decimal | None
    free_cash_flow: Decimal | None
    market_cap: Decimal | None
    total_debt: Decimal | None
    cash_and_equivalents: Decimal | None
    # The assumptions that produced it. Without these the number means nothing.
    discount_rate: Decimal
    terminal_growth: Decimal
    horizon_years: int
    #: Reasons the figure is annotated. NEVER alters the value — the Cameco
    #: out-of-calibration precedent: a caveat may annotate a score, never change one.
    caveats: tuple[str, ...]
    attribution: str
    spec_version: str
    # The overview attaches the exact persisted market/FX rows used to derive
    # market capitalisation. The pure solver leaves these unset.
    market_price_date: date | None = None
    market_price_source: str | None = None
    fx_rate: Decimal | None = None
    fx_rate_date: date | None = None
    fx_rate_source: str | None = None


def _insufficient(fiscal_year: int, reason: str, rate: Decimal, terminal: Decimal, **operands) -> ReverseDcf:
    return ReverseDcf(
        fiscal_year=fiscal_year,
        implied_growth=None,
        insufficient_data=True,
        reason=reason,
        enterprise_value=operands.get("enterprise_value"),
        free_cash_flow=operands.get("free_cash_flow"),
        market_cap=operands.get("market_cap"),
        total_debt=operands.get("total_debt"),
        cash_and_equivalents=operands.get("cash_and_equivalents"),
        discount_rate=rate,
        terminal_growth=terminal,
        horizon_years=HORIZON_YEARS,
        caveats=operands.get("caveats", ()),
        attribution=ATTRIBUTION,
        spec_version=SPEC_VERSION,
    )


def present_value(
    free_cash_flow: Decimal, growth: Decimal, discount_rate: Decimal, terminal_growth: Decimal
) -> Decimal:
    """Enterprise value implied by a growth rate — the forward direction of the model.

    Free cash flow grows at `growth` for the horizon, then forever at
    `terminal_growth`. Because the free-cash-flow margin is held constant (A-4),
    growing revenue at g and growing free cash flow at g are the same statement.

    Exposed rather than private so tests can verify the solver's answer by feeding
    it back through the forward model, which is a real check rather than a
    restatement of the solver's own arithmetic.
    """
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        total = Decimal(0)
        discount = Decimal(1) + discount_rate
        for year in range(1, HORIZON_YEARS + 1):
            total += free_cash_flow * (Decimal(1) + growth) ** year / discount**year
        terminal_flow = (
            free_cash_flow
            * (Decimal(1) + growth) ** HORIZON_YEARS
            * (Decimal(1) + terminal_growth)
        )
        terminal_value = terminal_flow / (discount_rate - terminal_growth)
        return +(total + terminal_value / discount**HORIZON_YEARS)


def compute(
    *,
    fiscal_year: int,
    free_cash_flow: Decimal | None,
    market_cap: Decimal | None,
    total_debt: Decimal | None,
    cash_and_equivalents: Decimal | None,
    discount_rate: Decimal = DEFAULT_DISCOUNT_RATE,
    terminal_growth: Decimal = DEFAULT_TERMINAL_GROWTH,
    interest_outside_operating: bool = False,
    is_capital_intensive: bool = False,
) -> ReverseDcf:
    """Solve for the constant growth rate that makes the model reproduce enterprise value.

    Returns `insufficient_data` with a stated reason rather than a defaulted,
    clamped or extrapolated number in every case the model does not apply. All five
    of those cases are reachable in the current universe.
    """
    caveats = tuple(
        CAVEATS[key]
        for key, applies in (
            ("interest_classification", interest_outside_operating),
            ("capital_intensity", is_capital_intensive),
        )
        if applies
    )

    fail = lambda reason, **kw: _insufficient(  # noqa: E731 - local shorthand, one use per branch
        fiscal_year, reason, discount_rate, terminal_growth, caveats=caveats, **kw
    )

    if terminal_growth >= discount_rate:
        return fail(
            "the perpetuity diverges unless terminal growth is strictly below the discount rate"
        )

    operands = {
        "free cash flow": free_cash_flow,
        "market capitalisation": market_cap,
        "total debt": total_debt,
        "cash and equivalents": cash_and_equivalents,
    }
    missing = sorted(name for name, value in operands.items() if value is None)
    if missing:
        return fail(f"no {', '.join(missing)} for this fiscal year")

    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        enterprise_value = market_cap + total_debt - cash_and_equivalents
    carried = {
        "enterprise_value": enterprise_value,
        "free_cash_flow": free_cash_flow,
        "market_cap": market_cap,
        "total_debt": total_debt,
        "cash_and_equivalents": cash_and_equivalents,
    }

    if free_cash_flow <= 0:
        return fail(
            "free cash flow is zero or negative, so there is no positive stream to grow "
            "and no growth rate justifies the price",
            **carried,
        )
    if enterprise_value <= 0:
        return fail(
            "enterprise value is zero or negative — net cash exceeds market capitalisation "
            "plus debt",
            **carried,
        )

    # The present value is strictly increasing in growth for a positive cash flow,
    # so a sign change across the declared range brackets exactly one root. Keep
    # the whole bisection in a fixed context; otherwise a caller changing the
    # process-wide Decimal precision could change the stored implied rate.
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        low, high = LOWER_BOUND, UPPER_BOUND
        if present_value(free_cash_flow, low, discount_rate, terminal_growth) > enterprise_value:
            return fail(
                f"the implied growth is below the search range ({low}) — the price is lower than "
                "even that rate would justify",
                **carried,
            )
        if present_value(free_cash_flow, high, discount_rate, terminal_growth) < enterprise_value:
            return fail(
                f"the implied growth is above the search range ({high}) — the price implies more "
                "growth than this model will search for",
                **carried,
            )

        for _ in range(MAX_ITERATIONS):
            midpoint = (low + high) / 2
            if high - low < TOLERANCE:
                break
            if present_value(free_cash_flow, midpoint, discount_rate, terminal_growth) < enterprise_value:
                low = midpoint
            else:
                high = midpoint
        implied_growth = +(low + high) / 2

    return ReverseDcf(
        fiscal_year=fiscal_year,
        implied_growth=implied_growth,
        insufficient_data=False,
        reason=None,
        **carried,
        discount_rate=discount_rate,
        terminal_growth=terminal_growth,
        horizon_years=HORIZON_YEARS,
        caveats=caveats,
        attribution=ATTRIBUTION,
        spec_version=SPEC_VERSION,
    )
