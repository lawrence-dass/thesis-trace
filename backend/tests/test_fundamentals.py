"""Story 10.4 — fundamentals summary and earnings waterfall (D12).

No versioned presentation-rule spec backs this module (unlike rewards_risks or
debt) because nothing here is a ThesisTrace classification — every value is
either a filed canonical fact or plain subtraction between two of them. The
tests therefore focus on three things: the waterfall always closes on the
filed earnings figure regardless of how much cost detail a filer's taxonomy
exposes, a structural gap degrades honestly (absent, never zero), and the
latest-year selection requires BOTH revenue and net income, not just either.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fundamentals.engine import (
    DERIVATION_GROSS_PROFIT,
    DERIVATION_OTHER_FROM_GROSS_PROFIT,
    DERIVATION_OTHER_FROM_REVENUE,
    NO_COST_DETAIL_REASON,
    fundamentals_for_facts,
)


@dataclass
class FakeFact:
    canonical_concept: str
    fiscal_year: int
    value: Decimal
    accession_number: str = "0001-25-000001"
    period_end: date = date(2025, 12, 31)
    unit: str = "USD"


def _bar(fundamentals, stage: str):
    return next(b for b in fundamentals.waterfall if b.stage == stage)


def test_a_filer_with_filed_cogs_and_gross_profit_uses_the_filed_gross_profit() -> None:
    facts = [
        FakeFact("revenue", 2025, Decimal("1000")),
        FakeFact("cogs", 2025, Decimal("400")),
        FakeFact("gross_profit", 2025, Decimal("600")),
        FakeFact("net_income", 2025, Decimal("150")),
    ]
    fund = fundamentals_for_facts(facts)
    assert fund is not None
    assert fund.fiscal_year == 2025

    gross_profit = _bar(fund, "gross_profit")
    assert gross_profit.figure.value == Decimal("600")
    assert gross_profit.figure.derivation is None  # filed, not derived
    assert gross_profit.figure.fact is not None

    cost = _bar(fund, "cost_of_revenue")
    assert cost.figure.value == Decimal("400")
    assert cost.figure.reason is None

    other = _bar(fund, "other")
    assert other.figure.derivation == DERIVATION_OTHER_FROM_GROSS_PROFIT
    assert other.figure.value == Decimal("450")  # 600 - 150

    # The waterfall closes on the filed earnings figure: revenue - cost - other == earnings.
    assert Decimal("1000") - cost.figure.value - other.figure.value == Decimal("150")


def test_a_filer_with_cogs_but_no_filed_gross_profit_derives_it() -> None:
    """Suncor's shape: IFRS by-nature presentation tags cost of sales but no
    separate gross-profit line (verified live 2026-08-27)."""
    facts = [
        FakeFact("revenue", 2025, Decimal("52377")),
        FakeFact("cogs", 2025, Decimal("36100")),
        FakeFact("net_income", 2025, Decimal("5918")),
    ]
    fund = fundamentals_for_facts(facts)
    assert fund is not None

    gross_profit = _bar(fund, "gross_profit")
    assert gross_profit.figure.derivation == DERIVATION_GROSS_PROFIT
    assert gross_profit.figure.value == Decimal("52377") - Decimal("36100")
    assert gross_profit.figure.fact is None  # derived, not filed — AD-19

    other = _bar(fund, "other")
    assert other.figure.derivation == DERIVATION_OTHER_FROM_GROSS_PROFIT


def test_a_filer_with_no_cost_detail_at_all_degrades_honestly_never_zero() -> None:
    """CP's shape: a railroad tags neither cogs nor gross_profit, reporting
    functional expense categories instead (verified live 2026-08-27)."""
    facts = [
        FakeFact("revenue", 2025, Decimal("15078")),
        FakeFact("net_income", 2025, Decimal("4141")),
    ]
    fund = fundamentals_for_facts(facts)
    assert fund is not None

    cost = _bar(fund, "cost_of_revenue")
    assert cost.figure.value is None
    assert cost.figure.reason == NO_COST_DETAIL_REASON

    gross_profit = _bar(fund, "gross_profit")
    assert gross_profit.figure.value is None
    assert gross_profit.figure.reason == NO_COST_DETAIL_REASON

    other = _bar(fund, "other")
    assert other.figure.derivation == DERIVATION_OTHER_FROM_REVENUE
    assert other.figure.value == Decimal("15078") - Decimal("4141")

    # An absent bar contributes nothing (never a defaulted zero-that-lies): the
    # waterfall still closes treating the absent cost bar as a no-op.
    earnings = _bar(fund, "earnings")
    assert Decimal("15078") - other.figure.value == earnings.figure.value


def test_no_year_with_both_revenue_and_net_income_returns_none() -> None:
    facts = [FakeFact("revenue", 2025, Decimal("100"))]
    assert fundamentals_for_facts(facts) is None
    assert fundamentals_for_facts([]) is None


def test_picks_the_latest_year_where_both_revenue_and_net_income_resolve() -> None:
    facts = [
        FakeFact("revenue", 2024, Decimal("900")),
        FakeFact("net_income", 2024, Decimal("100")),
        # 2025 has revenue but net income has not been filed for it yet.
        FakeFact("revenue", 2025, Decimal("1000")),
    ]
    fund = fundamentals_for_facts(facts)
    assert fund is not None
    assert fund.fiscal_year == 2024


def test_revenue_and_earnings_are_filed_not_derived() -> None:
    facts = [
        FakeFact("revenue", 2025, Decimal("1000")),
        FakeFact("net_income", 2025, Decimal("150")),
    ]
    fund = fundamentals_for_facts(facts)
    assert fund is not None
    assert fund.revenue.derivation is None
    assert fund.revenue.fact is not None
    assert fund.earnings.derivation is None
    assert fund.earnings.fact is not None
