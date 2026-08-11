"""Assembles the reverse DCF for the company overview (Story 6.5).

Kept out of `api/repository.py` because it needs three things the debt cards do not
— a market price, an FX rate, and the filer's own growth history — and folding that
into an already-long function would bury it.

TWO BOUNDED QUERIES, NOT AN N+1. The canonical facts arrive from the caller's
existing single pass; only the fiscal-year-end close and the FX rate for ONE year
are fetched here, because the reverse DCF is shown for the latest resolvable year
rather than as a per-year series (a 35-cell grid per year is a different cost class
from a ratio per year).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, Filing
from raw_store.fx_rates import get_fx_rate_on_or_before
from raw_store.market_prices import get_fye_close
from valuation.reverse_dcf import ReverseDcf, compute
from valuation.sensitivity import SensitivityGrid, grid_for

#: Everything the reverse DCF reads, so the caller can widen its single fact query
#: rather than issuing a second one.
DCF_CONCEPTS: tuple[str, ...] = (
    "cash_from_operations",
    "capex",
    "total_debt",
    "cash_and_equivalents",
    "shares_outstanding",
    "revenue",
    "total_assets",
)


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
    revenues = {
        year: Decimal(str(concepts["revenue"].value))
        for year, concepts in facts_by_year.items()
        if "revenue" in concepts
    }
    if len(revenues) < 3:
        return None, None, None
    first, last = min(revenues), max(revenues)
    if revenues[first] <= 0:
        return None, None, None
    growth = revenues[last] / revenues[first]
    years = Decimal(last - first)
    # Decimal has no fractional power, and the exponent is 1/years — so this goes
    # through float deliberately and ONLY here. It is a contextual comparison shown
    # beside the implied rate, never an operand of the deterministic solve (AD-15
    # governs the computed figure, which this is not).
    cagr = Decimal(str(float(growth) ** (1.0 / float(years)) - 1.0))
    return cagr, first, last


async def _market_cap(
    session: AsyncSession,
    *,
    issuer_cik: str,
    fiscal_year: int,
    shares_outstanding: Decimal,
    reporting_currency: str | None,
) -> Decimal | None:
    """Shares x the fiscal-year-end close, converted into the filer's own currency.

    Mirrors `scoring/runner.py`'s Altman X4 handling rather than reimplementing it:
    Tiingo's price is always USD, so a filer reporting in CAD needs the Bank of
    Canada rate for its own year end, or a USD market cap would be measured against
    a CAD balance sheet (the AD-11 currency fix). Returns None rather than an
    unconverted figure when the rate is unavailable — a wrong number here would
    silently distort enterprise value and therefore the implied growth.
    """

    filing = (
        await session.execute(
            select(Filing).where(
                Filing.issuer_cik == issuer_cik, Filing.fiscal_year == fiscal_year
            )
        )
    ).scalars().first()
    if filing is None:
        return None
    close = await get_fye_close(session, issuer_cik, filing.fiscal_year_end)
    if close is None:
        return None
    price = Decimal(str(close.close_price))
    if reporting_currency and reporting_currency != "USD":
        rate = await get_fx_rate_on_or_before(
            session, f"USD{reporting_currency}", filing.fiscal_year_end
        )
        if rate is None:
            return None
        price = price * Decimal(str(rate.rate))
    return shares_outstanding * price


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

    fiscal_year = max(by_year)
    concepts = by_year[fiscal_year]

    def value(name: str) -> Decimal | None:
        fact = concepts.get(name)
        return Decimal(str(fact.value)) if fact is not None else None

    operating_cash, capex = value("cash_from_operations"), value("capex")
    free_cash_flow = (
        operating_cash - capex if operating_cash is not None and capex is not None else None
    )

    anchor = concepts.get("total_assets")
    market_cap = await _market_cap(
        session,
        issuer_cik=issuer_cik,
        fiscal_year=fiscal_year,
        shares_outstanding=value("shares_outstanding") or Decimal(0),
        reporting_currency=anchor.unit if anchor is not None else None,
    ) if value("shares_outstanding") is not None else None

    # Interest classification is a filer property Story 6.2 verified live; it is not
    # yet a canonical concept, so the caveat it drives is wired in Story 6.6 where
    # the issuer record is to hand. Capital intensity IS on the issuer already.
    base = compute(
        fiscal_year=fiscal_year,
        free_cash_flow=free_cash_flow,
        market_cap=market_cap,
        total_debt=value("total_debt"),
        cash_and_equivalents=value("cash_and_equivalents"),
        is_capital_intensive=is_capital_intensive,
    )
    grid = grid_for(base, is_capital_intensive=is_capital_intensive)
    return base, grid, historical_revenue_cagr(by_year)
