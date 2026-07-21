"""Story 1.5 — formula-spec engine + shared decimal engine (AD-5, AD-15)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from formulas.engine import (
    InsufficientData,
    divide,
    load_spec,
    round_ratio,
    to_decimal,
)


def test_load_piotroski_spec() -> None:
    spec = load_spec("piotroski_v1")
    assert spec.model == "piotroski"
    assert spec.formula_version == "piotroski_v1"
    assert spec.rounding_mode == "ROUND_HALF_EVEN"
    assert len(spec.signal_keys) == 9
    assert "roa_positive" in spec.signal_keys


def test_load_sloan_spec() -> None:
    spec = load_spec("sloan_v1")
    assert spec.model == "sloan"
    assert spec.signal_keys == ("accruals_ratio",)
    assert spec.raw["threshold"]["high_accrual_above"] == 0.10


def test_missing_spec_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_spec("does_not_exist_v9")


def test_banker_rounding_half_even() -> None:
    spec = load_spec("piotroski_v1")
    # ROUND_HALF_EVEN: 2.5 -> 2, 3.5 -> 4 at zero places.
    assert round_ratio(Decimal("2.5"), spec).quantize(Decimal(1)) == Decimal("2")
    assert round_ratio(Decimal("3.5"), spec).quantize(Decimal(1)) == Decimal("4")


def test_divide_normal_and_rounding() -> None:
    spec = load_spec("piotroski_v1")
    # 1/3 rounded to 6 places, half-even.
    assert divide(1, 3, spec) == Decimal("0.333333")


def test_divide_by_zero_is_insufficient() -> None:
    spec = load_spec("piotroski_v1")
    with pytest.raises(InsufficientData):
        divide(10, 0, spec)


def test_missing_input_is_insufficient() -> None:
    with pytest.raises(InsufficientData):
        to_decimal(None)
