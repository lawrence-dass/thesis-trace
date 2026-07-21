"""Sloan accruals ratio computation (FR-7).

Balance-sheet approach: accruals = net_income - cash_from_operations;
ratio = accruals / average_total_assets over two consecutive fiscal years.
A ratio above the spec threshold is a high-accrual (lower-quality) warning,
represented as status=fail; below is status=pass. Missing inputs -> insufficient_data
(AD-16). All arithmetic via the shared decimal engine (AD-15).
"""

from __future__ import annotations

from decimal import Decimal

from app.models import SignalStatus
from formulas.engine import FormulaSpec, InsufficientData, divide, round_ratio, to_decimal
from scoring.facts import FactLookup
from scoring.piotroski import SignalOutcome


def compute_sloan(facts: FactLookup, fiscal_year: int, spec: FormulaSpec) -> SignalOutcome:
    y, p = fiscal_year, fiscal_year - 1
    try:
        net_income = to_decimal(facts.get("net_income", y))
        cfo = to_decimal(facts.get("cash_from_operations", y))
        ta_y = to_decimal(facts.get("total_assets", y))
        ta_p = to_decimal(facts.get("total_assets", p))
    except InsufficientData:
        return SignalOutcome("accruals_ratio", SignalStatus.insufficient_data)

    accruals = net_income - cfo
    avg_total_assets = round_ratio((ta_y + ta_p) / 2, spec)
    try:
        ratio = divide(accruals, avg_total_assets, spec)
    except InsufficientData:
        return SignalOutcome("accruals_ratio", SignalStatus.insufficient_data)

    threshold = Decimal(str(spec.raw["threshold"]["high_accrual_above"]))
    high_accrual = ratio > threshold
    return SignalOutcome(
        "accruals_ratio",
        SignalStatus.fail if high_accrual else SignalStatus.pass_,
        value=float(ratio),
        inputs=(("net_income", y), ("cash_from_operations", y), ("total_assets", y), ("total_assets", p)),
    )


def sloan_band(outcome: SignalOutcome, spec: FormulaSpec) -> str | None:
    if outcome.status == SignalStatus.insufficient_data:
        return None
    return "High accruals (lower quality)" if outcome.status == SignalStatus.fail else "Low accruals (higher quality)"
