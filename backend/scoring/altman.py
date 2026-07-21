"""Altman Z-Score computation (FR-4).

All 5 weighted ratios computed individually (AD-16 tri-state on missing inputs).
Market value of equity = FYE close x shares outstanding, never a book-value
substitute (AD-11). Financial-sector firms are excluded; capital-intensive firms
carry a caveat (AD-20, D6). All arithmetic via the shared decimal engine (AD-15).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models import Applicability, SignalStatus
from formulas.engine import FormulaSpec, InsufficientData, divide, round_ratio, to_decimal
from scoring.facts import FactLookup
from scoring.piotroski import SignalOutcome


@dataclass
class AltmanResult:
    components: list[SignalOutcome]
    z_score: float | None
    band: str | None
    applicability: Applicability


def _coeff(spec: FormulaSpec, key: str) -> Decimal:
    return Decimal(str(spec.raw["coefficients"][key]))


def altman_band(z: Decimal, spec: FormulaSpec) -> str:
    for cls in spec.raw["bands"]["classes"]:
        if "above" in cls and z > Decimal(str(cls["above"])):
            return cls["label"]
        if "below" in cls and z < Decimal(str(cls["below"])):
            return cls["label"]
        if "min" in cls and "max" in cls and Decimal(str(cls["min"])) <= z <= Decimal(str(cls["max"])):
            return cls["label"]
    return "Grey"


def compute_altman(
    facts: FactLookup,
    fiscal_year: int,
    spec: FormulaSpec,
    *,
    market_close: Decimal | None,
    is_financial_sector: bool,
    is_capital_intensive: bool,
) -> AltmanResult:
    y = fiscal_year

    if is_financial_sector:
        # Undefined capital structure — never show a misleading number (D6, AD-20).
        components = [SignalOutcome(s, SignalStatus.insufficient_data) for s in spec.signal_keys]
        return AltmanResult(components, None, None, Applicability.excluded_out_of_scope)

    ta = facts.get("total_assets", y)
    components: list[SignalOutcome] = []
    weighted: dict[str, Decimal | None] = {}

    def component(key: str, numerator, denominator) -> None:
        try:
            ratio = divide(numerator, denominator, spec)
            weighted[key] = round_ratio(ratio * _coeff(spec, key), spec)
            components.append(SignalOutcome(key, SignalStatus.pass_, value=float(weighted[key])))
        except InsufficientData:
            weighted[key] = None
            components.append(SignalOutcome(key, SignalStatus.insufficient_data))

    # X1 working capital / TA
    try:
        wc = to_decimal(facts.get("current_assets", y)) - to_decimal(facts.get("current_liabilities", y))
        component("x1_working_capital", wc, ta)
    except InsufficientData:
        weighted["x1_working_capital"] = None
        components.append(SignalOutcome("x1_working_capital", SignalStatus.insufficient_data))

    component("x2_retained_earnings", facts.get("retained_earnings", y), ta)
    component("x3_ebit", facts.get("ebit", y), ta)

    # X4 market value of equity / total liabilities
    try:
        shares = to_decimal(facts.get("shares_outstanding", y))
        if market_close is None:
            raise InsufficientData("no market price")
        mve = market_close * shares
        component("x4_market_value_equity", mve, facts.get("total_liabilities", y))
    except InsufficientData:
        weighted["x4_market_value_equity"] = None
        components.append(SignalOutcome("x4_market_value_equity", SignalStatus.insufficient_data))

    component("x5_sales", facts.get("revenue", y), ta)

    if any(v is None for v in weighted.values()):
        applic = Applicability.computed_with_caveat if is_capital_intensive else Applicability.computed
        return AltmanResult(components, None, None, applic)

    z = round_ratio(sum(weighted.values()), spec)
    band = altman_band(z, spec)
    applic = Applicability.computed_with_caveat if is_capital_intensive else Applicability.computed
    return AltmanResult(components, float(z), band, applic)
