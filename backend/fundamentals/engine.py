"""Fundamentals summary and earnings waterfall (Story 10.4, D12).

Presents canonical facts only — revenue, cost of revenue, gross profit and net
income for the latest fiscal year that resolves both revenue and net income.
Unlike `rewards_risks` or `debt`, this module applies no threshold, band, or
selection judgment of its own: gross profit is either the filer's own filed
`GrossProfit` tag, or plain subtraction (revenue - cost of revenue) when only
the leaves are filed — the same class of arithmetic as reverse DCF's
`free_cash_flow = cash_from_operations - capex` (AD-1/AD-19: the derivation is
named and carried in provenance, never presented as a filed line item). No
versioned presentation-rule spec is needed because nothing here is a
ThesisTrace-authored classification.

DEGRADATION IS PER-FILER, NOT PER-YEAR, AND STRUCTURAL. CP (railroad) tags no
COGS or GrossProfit concept at all — it reports functional expense categories
instead — so the cost-of-revenue and gross-profit bars are both ABSENT with a
stated reason, never rendered as zero (AD-16). Suncor (IFRS, by-nature expense
presentation) tags COGS but no GrossProfit line, so its gross-profit bar is
DERIVED rather than absent. Verified live against real canonical_facts rows,
2026-08-27: CP/QSR carry neither cogs nor gross_profit for any year; Suncor
carries cogs but not gross_profit; BCE/CCJ/OTEX/SHOP carry both, and in every
observed year revenue - cogs equals the filed gross_profit exactly.

The "other" bar (gross profit, or revenue when gross profit is absent, down to
net income) is ALWAYS computable — revenue and net income are the two required
inputs for this module to produce anything at all — so the waterfall always
closes on the filed earnings figure regardless of how much cost detail a
filer's taxonomy exposes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

REVENUE_CONCEPT = "revenue"
COST_CONCEPT = "cogs"
GROSS_PROFIT_CONCEPT = "gross_profit"
EARNINGS_CONCEPT = "net_income"

#: Every canonical concept this module reads. Declared here (not just used
#: inline) so the caller can widen its single fact query without a second
#: round trip — same shape as `debt.engine`'s NUMERATOR_CONCEPT/DENOMINATOR_CONCEPT
#: and `valuation.overview`'s DCF_CONCEPTS.
FUNDAMENTALS_CONCEPTS: tuple[str, ...] = (
    REVENUE_CONCEPT,
    COST_CONCEPT,
    GROSS_PROFIT_CONCEPT,
    EARNINGS_CONCEPT,
)

DERIVATION_GROSS_PROFIT = "fundamentals_v1.gross_profit_from_revenue_minus_cogs"
DERIVATION_OTHER_FROM_GROSS_PROFIT = "fundamentals_v1.other_from_gross_profit_minus_earnings"
DERIVATION_OTHER_FROM_REVENUE = "fundamentals_v1.other_from_revenue_minus_earnings"

NO_COST_DETAIL_REASON = (
    "Not disclosed — this filer reports functional expense categories rather "
    "than a cost-of-revenue or gross-profit line."
)


@dataclass(frozen=True)
class FundamentalsFigure:
    """One headline figure or waterfall bar value.

    `fact` carries the CanonicalFact this value came from (for provenance) when
    the value is a filed tag; `derivation` names the rule when it is computed
    from other facts instead (AD-19 — a derived figure must never be presented
    as though a line item in the filing states it). Exactly one of
    (`value` is None) or (`fact`/`derivation` populated) holds for a present
    bar; an absent bar carries `reason` instead of `value`.
    """

    value: Decimal | None
    fact: object | None  # CanonicalFact | None — duck-typed to avoid an app.models import here
    derivation: str | None
    reason: str | None


@dataclass(frozen=True)
class WaterfallBar:
    stage: str  # "revenue" | "cost_of_revenue" | "gross_profit" | "other" | "earnings"
    #: "total" bars are drawn from zero (revenue, gross profit, earnings);
    #: "decrease" bars float between the previous and next total.
    bar_type: str
    figure: FundamentalsFigure


@dataclass(frozen=True)
class Fundamentals:
    fiscal_year: int
    revenue: FundamentalsFigure
    earnings: FundamentalsFigure
    waterfall: list[WaterfallBar]


def _as_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _filed(fact) -> FundamentalsFigure:
    return FundamentalsFigure(value=_as_decimal(fact.value), fact=fact, derivation=None, reason=None)


def _derived(value: Decimal, derivation: str) -> FundamentalsFigure:
    return FundamentalsFigure(value=value, fact=None, derivation=derivation, reason=None)


def _absent(reason: str) -> FundamentalsFigure:
    return FundamentalsFigure(value=None, fact=None, derivation=None, reason=reason)


def fundamentals_for_facts(facts) -> Fundamentals | None:
    """The fundamentals summary and waterfall for the latest fiscal year that
    resolves both revenue and net income.

    Takes facts the caller has already fetched (`facts` items need
    `.canonical_concept`, `.fiscal_year`, `.value`, plus whatever the caller
    wants surfaced as provenance) rather than issuing a query of its own — the
    read path stays one pass over materialized rows (AD-1).

    Returns None when no fiscal year resolves both required figures — there is
    nothing honest to show, not even an empty waterfall.
    """
    by_year: dict[int, dict[str, object]] = {}
    for fact in facts:
        if fact.canonical_concept in FUNDAMENTALS_CONCEPTS:
            by_year.setdefault(fact.fiscal_year, {})[fact.canonical_concept] = fact

    candidate_years = [
        year
        for year, concepts in by_year.items()
        if REVENUE_CONCEPT in concepts and EARNINGS_CONCEPT in concepts
    ]
    if not candidate_years:
        return None
    fiscal_year = max(candidate_years)
    concepts = by_year[fiscal_year]

    revenue_fact = concepts[REVENUE_CONCEPT]
    earnings_fact = concepts[EARNINGS_CONCEPT]
    revenue_value = _as_decimal(revenue_fact.value)
    earnings_value = _as_decimal(earnings_fact.value)
    if revenue_value is None or earnings_value is None:
        return None

    revenue_figure = _filed(revenue_fact)
    earnings_figure = _filed(earnings_fact)

    cost_fact = concepts.get(COST_CONCEPT)
    cost_value = _as_decimal(cost_fact.value) if cost_fact is not None else None
    gross_profit_fact = concepts.get(GROSS_PROFIT_CONCEPT)
    gross_profit_value = _as_decimal(gross_profit_fact.value) if gross_profit_fact is not None else None

    if cost_fact is not None and cost_value is not None:
        cost_figure = _filed(cost_fact)
    else:
        cost_figure = _absent(NO_COST_DETAIL_REASON)

    if gross_profit_fact is not None and gross_profit_value is not None:
        gross_profit_figure = _filed(gross_profit_fact)
    elif cost_value is not None:
        gross_profit_value = revenue_value - cost_value
        gross_profit_figure = _derived(gross_profit_value, DERIVATION_GROSS_PROFIT)
    else:
        gross_profit_value = None
        gross_profit_figure = _absent(NO_COST_DETAIL_REASON)

    if gross_profit_value is not None:
        other_value = gross_profit_value - earnings_value
        other_figure = _derived(other_value, DERIVATION_OTHER_FROM_GROSS_PROFIT)
    else:
        other_value = revenue_value - earnings_value
        other_figure = _derived(other_value, DERIVATION_OTHER_FROM_REVENUE)

    waterfall = [
        WaterfallBar("revenue", "total", revenue_figure),
        WaterfallBar("cost_of_revenue", "decrease", cost_figure),
        WaterfallBar("gross_profit", "total", gross_profit_figure),
        WaterfallBar("other", "decrease", other_figure),
        WaterfallBar("earnings", "total", earnings_figure),
    ]

    return Fundamentals(
        fiscal_year=fiscal_year,
        revenue=revenue_figure,
        earnings=earnings_figure,
        waterfall=waterfall,
    )
