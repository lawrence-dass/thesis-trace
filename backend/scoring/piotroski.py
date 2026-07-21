"""Piotroski F-Score computation (FR-3).

Each of the 9 signals is computed individually; a signal whose inputs are missing
or produce a zero denominator is `insufficient_data`, never a defaulted 0 (AD-16).
All arithmetic goes through the shared decimal engine (AD-15). Concepts absent
from the Phase-1 fixture (gross margin, long-term debt, revenue, prior-year shares)
resolve to insufficient_data until ingested.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import SignalStatus
from formulas.engine import FormulaSpec, InsufficientData, divide
from scoring.facts import FactLookup


@dataclass
class SignalOutcome:
    key: str
    status: SignalStatus
    value: float | None = None
    inputs: tuple[tuple[str, int], ...] = ()  # (concept, fiscal_year) used


def _bool_signal(key: str, condition: bool, inputs) -> SignalOutcome:
    return SignalOutcome(key, SignalStatus.pass_ if condition else SignalStatus.fail, inputs=inputs)


def compute_piotroski(facts: FactLookup, fiscal_year: int, spec: FormulaSpec) -> list[SignalOutcome]:
    y, p = fiscal_year, fiscal_year - 1
    outcomes: list[SignalOutcome] = []

    def insufficient(key: str) -> SignalOutcome:
        return SignalOutcome(key, SignalStatus.insufficient_data)

    # 1. roa_positive
    try:
        roa_y = divide(facts.get("net_income", y), facts.get("total_assets", y), spec)
        outcomes.append(_bool_signal("roa_positive", roa_y > 0, (("net_income", y), ("total_assets", y))))
    except InsufficientData:
        outcomes.append(insufficient("roa_positive"))
        roa_y = None

    # 2. cfo_positive
    cfo_y = facts.get("cash_from_operations", y)
    outcomes.append(insufficient("cfo_positive") if cfo_y is None else _bool_signal("cfo_positive", cfo_y > 0, (("cash_from_operations", y),)))

    # 3. roa_increasing
    try:
        roa_curr = divide(facts.get("net_income", y), facts.get("total_assets", y), spec)
        roa_prev = divide(facts.get("net_income", p), facts.get("total_assets", p), spec)
        outcomes.append(_bool_signal("roa_increasing", roa_curr > roa_prev, (("net_income", y), ("net_income", p))))
    except InsufficientData:
        outcomes.append(insufficient("roa_increasing"))

    # 4. accruals: CFO/TA > ROA
    try:
        cfo_ta = divide(facts.get("cash_from_operations", y), facts.get("total_assets", y), spec)
        roa_curr = divide(facts.get("net_income", y), facts.get("total_assets", y), spec)
        outcomes.append(_bool_signal("accruals", cfo_ta > roa_curr, (("cash_from_operations", y), ("net_income", y))))
    except InsufficientData:
        outcomes.append(insufficient("accruals"))

    # 5. leverage_decreasing — needs long-term debt (not yet ingested)
    outcomes.append(insufficient("leverage_decreasing"))

    # 6. current_ratio_increasing
    try:
        cr_y = divide(facts.get("current_assets", y), facts.get("current_liabilities", y), spec)
        cr_p = divide(facts.get("current_assets", p), facts.get("current_liabilities", p), spec)
        outcomes.append(_bool_signal("current_ratio_increasing", cr_y > cr_p, (("current_assets", y), ("current_liabilities", y))))
    except InsufficientData:
        outcomes.append(insufficient("current_ratio_increasing"))

    # 7. shares_not_diluted
    sh_y = facts.get("shares_outstanding", y)
    sh_p = facts.get("shares_outstanding", p)
    outcomes.append(
        insufficient("shares_not_diluted")
        if sh_y is None or sh_p is None
        else _bool_signal("shares_not_diluted", sh_y <= sh_p, (("shares_outstanding", y), ("shares_outstanding", p)))
    )

    # 8. gross_margin_increasing — needs revenue + COGS (not yet ingested)
    outcomes.append(insufficient("gross_margin_increasing"))

    # 9. asset_turnover_increasing — needs revenue (not yet ingested)
    outcomes.append(insufficient("asset_turnover_increasing"))

    return outcomes


def piotroski_score(outcomes: list[SignalOutcome]) -> int:
    """F-Score = count of passing signals (insufficient_data does not count)."""
    return sum(1 for o in outcomes if o.status == SignalStatus.pass_)


def piotroski_band(score: int, spec: FormulaSpec) -> str | None:
    for cls in spec.raw.get("bands", {}).get("classes", []):
        if cls.get("min", 0) <= score <= cls.get("max", 9):
            return cls["label"]
    return None
