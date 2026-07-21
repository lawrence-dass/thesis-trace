"""Versioned formula-spec loader + shared decimal engine (AD-5, AD-15).

Every model's arithmetic runs through ONE decimal engine using the rounding mode
declared in its spec (default ROUND_HALF_EVEN) — never a per-module choice — so
two independently-built evaluators cannot diverge at a threshold boundary. All
values are Decimal (never float) to match the NUMERIC storage contract.
"""

from __future__ import annotations

import decimal
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

SPECS_DIR = Path(__file__).parent / "specs"

_ROUNDING_MODES = {
    "ROUND_HALF_EVEN": decimal.ROUND_HALF_EVEN,
    "ROUND_HALF_UP": decimal.ROUND_HALF_UP,
    "ROUND_DOWN": decimal.ROUND_DOWN,
    "ROUND_FLOOR": decimal.ROUND_FLOOR,
}


class InsufficientData(Exception):
    """Raised when an input is missing or a denominator is zero (AD-16 propagation)."""


@dataclass(frozen=True)
class FormulaSpec:
    model: str
    formula_version: str
    rounding_mode: str
    ratio_places: int
    missing_data_policy: str
    divide_by_zero_policy: str
    signal_keys: tuple[str, ...]
    raw: dict

    def rounding(self) -> str:
        return _ROUNDING_MODES[self.rounding_mode]


@lru_cache(maxsize=None)
def load_spec(formula_version: str) -> FormulaSpec:
    """Load and cache a formula spec by its version string (e.g. 'piotroski_v1')."""
    path = SPECS_DIR / f"{formula_version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Formula spec not found: {path}")
    data = yaml.safe_load(path.read_text())
    signals = tuple(s["key"] for s in data.get("signals", []))
    rounding = data.get("rounding", {})
    return FormulaSpec(
        model=data["model"],
        formula_version=data["formula_version"],
        rounding_mode=rounding.get("mode", "ROUND_HALF_EVEN"),
        ratio_places=int(rounding.get("ratio_places", 6)),
        missing_data_policy=data.get("missing_data_policy", "insufficient_data"),
        divide_by_zero_policy=data.get("divide_by_zero_policy", "insufficient_data"),
        signal_keys=signals,
        raw=data,
    )


def to_decimal(value) -> Decimal:
    if value is None:
        raise InsufficientData("missing input")
    return Decimal(str(value))


def divide(numerator, denominator, spec: FormulaSpec) -> Decimal:
    """Divide with the spec's divide-by-zero policy, rounded by the shared engine."""
    num = to_decimal(numerator)
    den = to_decimal(denominator)
    if den == 0:
        raise InsufficientData("divide by zero")
    return round_ratio(num / den, spec)


def round_ratio(value: Decimal, spec: FormulaSpec) -> Decimal:
    quant = Decimal(1).scaleb(-spec.ratio_places)  # e.g. 1e-6
    return value.quantize(quant, rounding=spec.rounding())
