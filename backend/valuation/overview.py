"""Assembles the reverse DCF for the company overview (Story 6.5).

Kept out of `api/repository.py` because it needs three things the debt cards do not
— a market price, an FX rate, and the filer's own growth history — and folding that
into an already-long function would bury it.

TWO BOUNDED QUERIES, NOT AN N+1. The canonical facts arrive from the caller's
existing single pass; market prices and FX rows for candidate fiscal years are loaded
in two bounded queries, then resolved in memory. The reverse DCF is shown for the
latest fully reproducible year rather than as a per-year series (a 35-cell grid per
year is a different cost class from a ratio per year).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact
from pipeline.universe import PHASE1_UNIVERSE
from raw_store.market_prices import resolve_fye_price, resolve_fye_prices
from valuation.reverse_dcf import ReverseDcf, compute
from valuation.sensitivity import SensitivityGrid, grid_for

INTEREST_OUTSIDE_OPERATING_CIKS = frozenset(
    entry.cik for entry in PHASE1_UNIVERSE if entry.cik and entry.interest_outside_operating
)

#: Everything the reverse DCF reads, so the caller can widen its single fact query
#: rather than issuing a second one.
DCF_CONCEPTS: tuple[str, ...] = (
    "cash_from_operations",
    "capex",
    "total_debt",
    "cash_and_equivalents",
    # Keep derivation leaves in the single read too.  The API exposes these so a
    # reader can recompute a derived debt/cash operand instead of trusting it.
    "near_term_debt",
    "long_term_debt",
    "cash",
    "cash_equivalents",
    "shares_outstanding",
    "revenue",
    "total_assets",
)

REQUIRED_DCF_CONCEPTS = frozenset(
    {
        "cash_from_operations",
        "capex",
        "total_debt",
        "cash_and_equivalents",
        "shares_outstanding",
    }
)

_CURRENCY_REQUIRED_CONCEPTS = REQUIRED_DCF_CONCEPTS - {"shares_outstanding"}


@dataclass(frozen=True)
class MarketCapResolution:
    """Market capitalisation plus the context needed for an honest failure."""

    value: Decimal | None
    price: Decimal | None
    reporting_currency: str | None
    reason: str | None = None
    price_date: date | None = None
    price_source: str | None = None
    fx_rate: Decimal | None = None
    fx_rate_date: date | None = None
    fx_rate_source: str | None = None


def _decimal_nth_root(value: Decimal, n: int) -> Decimal:
    """Return ``value ** (1 / n)`` without leaving Decimal arithmetic.

    Decimal deliberately has no fractional-power operator.  Converting a
    financial ratio to float makes the result platform-dependent and can even
    produce a complex number for a negative endpoint.  Newton's method is
    deterministic here: a fixed precision margin and an iteration cap are used,
    and every intermediate value remains Decimal (AD-15).
    """
    if not value.is_finite() or value <= 0 or n <= 0:
        raise ValueError("nth root requires a positive value and a positive integer degree")
    if n == 1:
        return value

    with localcontext() as context:
        # Use a fixed precision rather than inheriting the caller's mutable
        # Decimal context. A read must reproduce the same result regardless of
        # which code happened to set the process-wide context first.
        context.prec = 50
        # ``adjusted`` gives the base-10 exponent of the first significant digit.
        # Decimal's power implementation keeps this fractional exponent inside
        # Decimal arithmetic and, unlike integer floor division, gives a useful
        # starting magnitude for ratios just below one (for example 0.8 ** 0.1).
        guess = Decimal(10) ** (Decimal(value.adjusted()) / Decimal(n))
        for _ in range(max(64, context.prec * 2)):
            next_guess = (
                Decimal(n - 1) * guess + value / (guess ** (n - 1))
            ) / Decimal(n)
            if next_guess == guess:
                break
            guess = next_guess
        return +guess


def _as_decimal(value) -> Decimal | None:
    """Convert persisted/test input without letting malformed data crash a read."""
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def historical_revenue_cagr(
    facts_by_year: dict[int, dict[str, CanonicalFact]],
) -> tuple[Decimal | None, int | None, int | None]:
    """The filer's OWN achieved revenue growth over whatever history it actually has.

    The window ADAPTS and is reported, never promised: IFRS 40-F filers start around
    FY2017 (~9 years) against OTEX's 20+ under us-gaap, so a fixed decade-long claim
    would be false for half the universe.

    Returns (cagr, from_year, to_year), or (None, None, None) with fewer than three
    years — two points is a single year-over-year change, not a trend.
    """
    revenue_facts = {
        year: concepts["revenue"]
        for year, concepts in facts_by_year.items()
        if "revenue" in concepts
    }
    units = {getattr(fact, "unit", None) for fact in revenue_facts.values()}
    if not units or None in units or len(units) != 1:
        return None, None, None
    revenues: dict[int, Decimal] = {}
    for year, fact in revenue_facts.items():
        value = _as_decimal(getattr(fact, "value", None))
        if value is None:
            return None, None, None
        revenues[year] = value
    if len(revenues) < 3:
        return None, None, None
    first, last = min(revenues), max(revenues)
    if any(not value.is_finite() or value <= 0 for value in revenues.values()):
        return None, None, None
    years = last - first
    # Keep the division and final subtraction in the same fixed context as the
    # root. Otherwise a caller's process-wide Decimal precision would still change
    # this comparison figure even though the root itself is isolated.
    with localcontext() as context:
        context.prec = 50
        growth = revenues[last] / revenues[first]
        cagr = _decimal_nth_root(growth, years) - Decimal(1)
    return cagr, first, last


async def _market_cap(
    session: AsyncSession,
    *,
    issuer_cik: str,
    fiscal_year_end: date,
    shares_outstanding: Decimal | None,
    reporting_currency: str | None,
) -> MarketCapResolution:
    """Shares x the fiscal-year-end close, converted into the filer's own currency.

    Shares are a filed count, while the price is resolved from the persisted market
    store and converted by the shared Tiingo/FX rule. Missing shares, currency,
    price, or FX is represented as a reason rather than as a zero/default.
    """
    if shares_outstanding is None:
        return MarketCapResolution(None, None, reporting_currency, "no shares outstanding")
    if shares_outstanding <= 0:
        return MarketCapResolution(
            None,
            None,
            reporting_currency,
            "shares outstanding is zero or negative",
        )

    resolution = await resolve_fye_price(
        session,
        issuer_cik=issuer_cik,
        fiscal_year_end=fiscal_year_end,
        reporting_currency=reporting_currency,
    )
    if resolution.price is None:
        return MarketCapResolution(
            None,
            None,
            resolution.reporting_currency,
            resolution.reason,
            resolution.price_date,
            resolution.price_source,
            resolution.fx_rate_value,
            resolution.fx_rate_date,
            resolution.fx_rate_source,
        )
    return MarketCapResolution(
        _multiply_decimal(shares_outstanding, resolution.price),
        resolution.price,
        resolution.reporting_currency,
        price_date=resolution.price_date,
        price_source=resolution.price_source,
        fx_rate=resolution.fx_rate_value,
        fx_rate_date=resolution.fx_rate_date,
        fx_rate_source=resolution.fx_rate_source,
    )


def _multiply_decimal(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return +(left * right)


def _subtract_decimal(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return +(left - right)


async def reverse_dcf_for_issuer(
    session: AsyncSession,
    *,
    issuer_cik: str,
    is_capital_intensive: bool,
    facts: list[CanonicalFact],
) -> tuple[ReverseDcf, SensitivityGrid | None, tuple[Decimal | None, int | None, int | None]] | None:
    """The latest resolvable year's reverse DCF, its grid, and the growth history.

    Returns None only when the filer has no canonical facts at all. A filer whose
    model does not apply still returns a result carrying `insufficient_data` and the
    reason — absence explains itself (AD-16).
    """
    by_year: dict[int, dict[str, CanonicalFact]] = {}
    for fact in facts:
        by_year.setdefault(fact.fiscal_year, {})[fact.canonical_concept] = fact
    if not by_year:
        return None

    def fact_value(concepts: dict[str, CanonicalFact], name: str) -> Decimal | None:
        fact = concepts.get(name)
        if fact is None:
            return None
        return _as_decimal(getattr(fact, "value", None))

    def is_positive_candidate(concepts: dict[str, CanonicalFact]) -> bool:
        if not REQUIRED_DCF_CONCEPTS.issubset(concepts):
            return False
        if any(fact_value(concepts, name) is None for name in REQUIRED_DCF_CONCEPTS):
            return False
        operating_cash = fact_value(concepts, "cash_from_operations")
        capex = fact_value(concepts, "capex")
        shares = fact_value(concepts, "shares_outstanding")
        if operating_cash is None or capex is None or shares is None:
            return False
        return _subtract_decimal(operating_cash, capex) > 0 and shares > 0

    positive_years = sorted(
        (year for year, concepts in by_year.items() if is_positive_candidate(concepts)),
        reverse=True,
    )
    complete_years = sorted(
        (
            year
            for year, concepts in by_year.items()
            if REQUIRED_DCF_CONCEPTS.issubset(concepts)
        ),
        reverse=True,
    )

    def currency_for(concepts: dict[str, CanonicalFact]) -> tuple[str | None, str | None]:
        # Revenue is only the contextual CAGR and derivation leaves are exposed
        # evidence; neither should block a DCF whose actual solver operands have
        # valid units. Currency validation belongs to the monetary inputs consumed
        # by enterprise value and FCF.
        monetary_facts = [
            fact
            for name, fact in concepts.items()
            if name in _CURRENCY_REQUIRED_CONCEPTS
        ]
        currencies = {
            fact.unit.strip().upper()
            for fact in monetary_facts
            if fact.unit and fact.unit.strip()
        }
        missing_currency = any(
            not fact.unit or not fact.unit.strip() for fact in monetary_facts
        )
        if len(currencies) > 1:
            return None, "inconsistent reporting currencies across reverse-DCF inputs"
        if missing_currency or not currencies:
            return None, "reporting currency is unavailable for a reverse-DCF input"
        return next(iter(currencies)), None

    # Resolve all positive candidates in one bounded market/FX pass. Picking the
    # newest positive FCF year before checking external inputs can hide an older
    # year that is fully reproducible when a quote or FX row is missing.
    candidate_ends: dict[int, date] = {}
    candidate_currencies: dict[int, str | None] = {}
    candidate_currency_reasons: dict[int, str | None] = {}
    for year in positive_years:
        candidate = by_year[year]
        anchor = candidate.get("total_assets") or candidate.get("shares_outstanding")
        if anchor is None:
            continue
        currency, reason = currency_for(candidate)
        candidate_ends[year] = anchor.period_end
        candidate_currencies[year] = currency
        candidate_currency_reasons[year] = reason
    candidate_prices = await resolve_fye_prices(
        session,
        issuer_cik=issuer_cik,
        fiscal_year_ends=candidate_ends,
        reporting_currencies=candidate_currencies,
    )
    fiscal_year = next(
        (
            year
            for year in positive_years
            if candidate_currency_reasons.get(year) is None
            and candidate_prices.get(year) is not None
            and candidate_prices[year].price is not None
        ),
        complete_years[0] if complete_years else max(by_year),
    )
    concepts = by_year[fiscal_year]

    def value(name: str) -> Decimal | None:
        return fact_value(concepts, name)

    operating_cash, capex = value("cash_from_operations"), value("capex")
    with localcontext() as context:
        context.prec = 50
        free_cash_flow = (
            _subtract_decimal(operating_cash, capex)
            if operating_cash is not None and capex is not None
            else None
        )

    # A balance-sheet date and reporting currency are taken from materialized
    # facts, not Filing.fiscal_year. Comparative facts can live only in a later
    # filing (for example a restatement), so a Filing lookup by fiscal year is not
    # reliable here.
    anchor = concepts.get("total_assets") or concepts.get("shares_outstanding")
    if anchor is None:
        anchor = next(iter(concepts.values()))

    reporting_currency, currency_reason = currency_for(concepts)
    market_resolution = None
    if currency_reason is None and fiscal_year in candidate_prices:
        price_resolution = candidate_prices[fiscal_year]
        shares = value("shares_outstanding")
        market_resolution = MarketCapResolution(
            value=_multiply_decimal(shares, price_resolution.price)
            if shares is not None and price_resolution.price is not None
            else None,
            price=price_resolution.price,
            reporting_currency=price_resolution.reporting_currency,
            reason=price_resolution.reason,
            price_date=price_resolution.price_date,
            price_source=price_resolution.price_source,
            fx_rate=price_resolution.fx_rate_value,
            fx_rate_date=price_resolution.fx_rate_date,
            fx_rate_source=price_resolution.fx_rate_source,
        )
    if market_resolution is None:
        market_resolution = (
            MarketCapResolution(None, None, reporting_currency, currency_reason)
            if currency_reason
            else await _market_cap(
                session,
                issuer_cik=issuer_cik,
                fiscal_year_end=anchor.period_end,
                shares_outstanding=value("shares_outstanding"),
                reporting_currency=reporting_currency,
            )
        )

    # Interest classification is issuer source data verified in Story 6.2, not a
    # numeric canonical concept. It is carried from the universe metadata so the
    # reverse-DCF caveat is attached at computation time without altering the value.
    base = compute(
        fiscal_year=fiscal_year,
        free_cash_flow=free_cash_flow,
        market_cap=market_resolution.value,
        total_debt=value("total_debt"),
        cash_and_equivalents=value("cash_and_equivalents"),
        interest_outside_operating=issuer_cik in INTEREST_OUTSIDE_OPERATING_CIKS,
        is_capital_intensive=is_capital_intensive,
    )
    base = replace(
        base,
        market_price_date=market_resolution.price_date,
        market_price_source=market_resolution.price_source,
        fx_rate=market_resolution.fx_rate,
        fx_rate_date=market_resolution.fx_rate_date,
        fx_rate_source=market_resolution.fx_rate_source,
    )
    if base.insufficient_data and market_resolution.reason and market_resolution.value is None:
        reason = base.reason or "reverse DCF cannot be resolved"
        base = replace(base, reason=f"{reason}; {market_resolution.reason}")
    grid = grid_for(
        base,
        interest_outside_operating=issuer_cik in INTEREST_OUTSIDE_OPERATING_CIKS,
        is_capital_intensive=is_capital_intensive,
    )
    # Do not compare an older implied-growth year with revenue that was reported
    # after that year when the newest complete year was rejected. The comparison
    # history ends at the same fiscal year as the DCF operands.
    history = {year: values for year, values in by_year.items() if year <= fiscal_year}
    return base, grid, historical_revenue_cagr(history)
