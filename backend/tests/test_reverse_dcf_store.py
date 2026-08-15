"""The reverse DCF is materialized on the write path and only READ on the read path.

AD-1 is a structural CQRS rule — "all computation runs in the scheduled batch
pipeline; the read path only queries materialized Postgres and never computes a
score" (epics.md:60) and "no request can trigger scoring, ingestion, or
recomputation" (epics.md:614). Story 6.4's AC already said the sensitivity grid was
stored. It was not: `reverse_dcf_for_issuer` had exactly one caller and it was
`api/repository.py` on the read path, so every page load re-solved the DCF and all
35 grid cells.

Four things are guarded, and the first two carry the weight:

  1. THE READ PATH DOES NOT SOLVE. Enforced by breaking the solver and asserting the
     overview still renders its figures. A test that merely counted queries would
     pass just as happily if the 35 in-process solves came back.
  2. A SECOND PIPELINE RUN LEAVES ONE ROW. `run_validation` is the precedent this
     repo already paid for: implemented, tested, and then appending a duplicate row
     every night once the cron actually ran.
  3. The stored row round-trips to the same result the solver produced.
  4. A superseded fiscal year does not linger.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import func, select

from api.repository import get_company_overview
from app.models import (
    CanonicalFact,
    Filing,
    Issuer,
    MarketPrice,
    ReverseDcfCell,
    ReverseDcfRun,
)
from canonicalization.mappings import MAPPING_VERSION
from valuation.overview import reverse_dcf_for_issuer
from valuation.reverse_dcf import SPEC_VERSION
from valuation.store import load_reverse_dcf, materialize_reverse_dcf
from tests.conftest import requires_db

CIK = "0000000777"
TICKER = "RDCF"
ACCN = "0000000777-25-000001"
FYE = date(2025, 12, 31)
LATEST_YEAR = 2025

#: A filer whose reverse DCF actually resolves. Enterprise value is 110M against 8M
#: of free cash flow, which implies a low-single-digit growth rate — comfortably
#: inside the solver's declared search bounds, so this fixture exercises the stored
#: path rather than the insufficient_data one.
FACTS: dict[str, str] = {
    "cash_from_operations": "12000000",
    "capex": "4000000",
    "total_debt": "20000000",
    "cash_and_equivalents": "10000000",
    "shares_outstanding": "1000000",
    "total_assets": "150000000",
}
CLOSE_PRICE = Decimal("100")

#: Three years of revenue, because fewer than three is not a trend and the growth
#: history would come back empty — leaving the CAGR columns untested.
REVENUE_BY_YEAR = {2023: "80000000", 2024: "90000000", 2025: "100000000"}

#: The scale of every rate column. The solver runs at `prec=50` and returns ~26
#: significant digits, but its DECLARED TOLERANCE IS 1e-7 (reverse_dcf_v1.yaml), so
#: everything past the eighth decimal is an artefact of where bisection halted
#: rather than accuracy. Ten decimals keeps three orders more than the figure is
#: actually good for; storing all 26 would be persisting noise as though it were
#: signal.
RATE_SCALE = Decimal("1E-10")
#: The solver's own tolerance, asserted against separately below.
SOLVER_TOLERANCE = Decimal("0.0000001")


def _stored_rate(value: Decimal | None) -> Decimal | None:
    """What the NUMERIC(18, 10) column holds for `value`.

    ROUND_HALF_UP, not Python's default ROUND_HALF_EVEN: Postgres rounds halves away
    from zero. The two agree on every value that is not an exact tie, so a test using
    the default would pass indefinitely and then disagree on the first tie it ever
    saw — precisely the kind of environment-dependent green this repo has been bitten
    by before.
    """
    if value is None:
        return None
    return value.quantize(RATE_SCALE, rounding=ROUND_HALF_UP)


async def _seed(db_session) -> None:
    db_session.add(Issuer(cik=CIK, ticker=TICKER, name="Reverse DCF Test Co"))
    db_session.add(
        Filing(
            accession_number=ACCN,
            issuer_cik=CIK,
            form_type="10-K",
            filing_date=date(2026, 2, 1),
            fiscal_year=LATEST_YEAR,
            fiscal_year_end=FYE,
        )
    )
    await db_session.flush()

    for concept, value in FACTS.items():
        db_session.add(
            CanonicalFact(
                issuer_cik=CIK,
                accession_number=ACCN,
                canonical_concept=concept,
                fiscal_year=LATEST_YEAR,
                period_end=FYE,
                value=Decimal(value),
                unit="USD",
                mapping_version=MAPPING_VERSION,
            )
        )
    for year, revenue in REVENUE_BY_YEAR.items():
        db_session.add(
            CanonicalFact(
                issuer_cik=CIK,
                accession_number=ACCN,
                canonical_concept="revenue",
                fiscal_year=year,
                period_end=date(year, 12, 31),
                value=Decimal(revenue),
                unit="USD",
                mapping_version=MAPPING_VERSION,
            )
        )
    db_session.add(
        MarketPrice(
            issuer_cik=CIK, price_date=FYE, close_price=CLOSE_PRICE, source="tiingo"
        )
    )
    await db_session.commit()


def _break_the_solver(monkeypatch) -> None:
    """Make any attempt to solve raise, in every module that can reach one.

    Patched per-module rather than once at the source because both `overview` and
    `sensitivity` do `from valuation.reverse_dcf import compute`, which binds the
    function at import time — patching only `valuation.reverse_dcf.compute` would
    leave those two references pointing at the real solver and the guard would pass
    without ever being tested.
    """

    def _explode(*args, **kwargs):  # pragma: no cover — the point is it never runs
        raise AssertionError(
            "the read path solved a reverse DCF; AD-1 requires it to read the "
            "materialized row instead"
        )

    for module in ("valuation.reverse_dcf", "valuation.overview", "valuation.sensitivity"):
        monkeypatch.setattr(f"{module}.compute", _explode, raising=False)


# --- 0. the guard above must actually bite ------------------------------------


@requires_db
async def test_the_broken_solver_really_does_intercept_a_solve(
    db_session, monkeypatch
) -> None:
    """CONFIRMS THE NEXT TEST IS NOT INERT.

    `test_the_overview_renders_the_reverse_dcf_without_solving` proves its point by
    breaking the solver and seeing the page still render. If the patching missed —
    say `overview` binds `compute` at import time and only the source module were
    patched — that test would pass while asserting nothing at all, which is the
    exact shape of the OTEX golden entry that pinned an outcome for months without
    being able to reproduce its own stated reason.

    So: run the OLD read path (a direct solve) with the same patch applied, and
    require it to blow up.
    """
    await _seed(db_session)
    facts = (
        (
            await db_session.execute(
                select(CanonicalFact).where(CanonicalFact.issuer_cik == CIK)
            )
        )
        .scalars()
        .all()
    )
    _break_the_solver(monkeypatch)

    with pytest.raises(AssertionError, match="the read path solved a reverse DCF"):
        await reverse_dcf_for_issuer(
            db_session, issuer_cik=CIK, is_capital_intensive=False, facts=list(facts)
        )


# --- 1. the read path does not compute ---------------------------------------


@requires_db
async def test_the_overview_renders_the_reverse_dcf_without_solving(
    db_session, monkeypatch
) -> None:
    """THE WHOLE POINT OF THE CHANGE.

    The solver is broken before the read, so the overview can only produce these
    figures from the materialized row. If someone reintroduces a solve on the read
    path — directly or through a helper — this fails loudly rather than showing up
    as a slow page.
    """
    await _seed(db_session)
    await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False)
    await db_session.commit()

    _break_the_solver(monkeypatch)

    overview = await get_company_overview(db_session, TICKER)

    assert overview is not None
    dcf = overview.reverse_dcf
    assert dcf is not None
    assert dcf.fiscal_year == LATEST_YEAR
    assert dcf.insufficient_data is False
    assert dcf.implied_growth is not None
    # The grid is the expensive half — 35 solves — so its presence is asserted
    # explicitly rather than inferred from the base result resolving.
    assert dcf.total_cells == 35
    assert len(dcf.sensitivity) == 35
    assert dcf.range_low is not None and dcf.range_high is not None
    assert dcf.range_low <= dcf.implied_growth <= dcf.range_high
    # The comparison the implied rate exists to be judged against.
    assert dcf.historical_revenue_cagr is not None
    assert (dcf.historical_from_fiscal_year, dcf.historical_to_fiscal_year) == (2023, 2025)


@requires_db
async def test_an_unmaterialized_issuer_shows_no_reverse_dcf_rather_than_computing_one(
    db_session, monkeypatch
) -> None:
    """A filer the pipeline has not reached yet renders nothing.

    The tempting fallback — solve it on the fly when the row is missing — would
    reintroduce exactly the violation this change removes, and would do it on the
    rarest path, where nobody would notice the latency.
    """
    await _seed(db_session)
    _break_the_solver(monkeypatch)

    overview = await get_company_overview(db_session, TICKER)

    assert overview is not None
    assert overview.reverse_dcf is None


# --- 2. the daily cron must not accumulate rows -------------------------------


@requires_db
async def test_materializing_twice_leaves_exactly_one_run_and_one_grid(db_session) -> None:
    """`pipeline/run.py` is a DAILY cron over the same canonical facts.

    `run_validation` shipped implemented and tested and still appended a duplicate
    row every night once the cron ran, because nothing asserted the second call.
    This is that assertion.
    """
    await _seed(db_session)

    await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False)
    await db_session.commit()
    await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False)
    await db_session.commit()

    runs = (await db_session.execute(select(func.count()).select_from(ReverseDcfRun))).scalar_one()
    cells = (await db_session.execute(select(func.count()).select_from(ReverseDcfCell))).scalar_one()

    assert runs == 1, "a second pipeline run appended a row instead of upserting"
    assert cells == 35, "the grid accumulated cells across runs"


@requires_db
async def test_a_superseded_fiscal_year_does_not_linger(db_session) -> None:
    """The SOLVER picks the fiscal year, and a later run can pick an EARLIER one when
    the newest year stops resolving.

    Keyed on (issuer, fiscal_year, spec_version), the upsert alone would leave the
    stale newer row in place — and `load_reverse_dcf` takes the latest stored year,
    so the read would keep serving the superseded one indefinitely.
    """
    await _seed(db_session)
    db_session.add(
        ReverseDcfRun(
            issuer_cik=CIK,
            fiscal_year=LATEST_YEAR + 1,
            spec_version=SPEC_VERSION,
            insufficient_data=True,
            reason="stale row from a run that resolved a later year",
            discount_rate=Decimal("0.10"),
            terminal_growth=Decimal("0.025"),
            horizon_years=10,
            attribution="stale",
        )
    )
    await db_session.commit()

    await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False)
    await db_session.commit()

    years = (
        (await db_session.execute(select(ReverseDcfRun.fiscal_year))).scalars().all()
    )
    assert years == [LATEST_YEAR]


# --- 3. the stored row is the computed one ------------------------------------


@requires_db
async def test_the_stored_row_round_trips_to_the_computed_result(db_session) -> None:
    """Persistence must not change the answer.

    This deliberately compares against the solver's own output, which would be
    circular for a test of the MATHS — but the claim here is narrower and is exactly
    what circularity cannot hide: that writing the result to Postgres and reading it
    back yields the same figures. `test_reverse_dcf.py` verifies the arithmetic
    independently.

    Rates are compared against the value QUANTIZED to the column's scale, which is
    the actual storage contract, rather than against the solver's raw ~26-digit
    output. Asserting raw equality would be asserting that Postgres preserves digits
    the solver's own 1e-7 tolerance says are noise. The gap that quantization
    introduces is asserted to be far below that tolerance, so this cannot quietly
    become a licence for a coarse column.
    """
    await _seed(db_session)

    facts = (
        (
            await db_session.execute(
                select(CanonicalFact).where(CanonicalFact.issuer_cik == CIK)
            )
        )
        .scalars()
        .all()
    )
    computed = await reverse_dcf_for_issuer(
        db_session, issuer_cik=CIK, is_capital_intensive=False, facts=list(facts)
    )
    assert computed is not None
    base, grid, (cagr, cagr_from, cagr_to) = computed

    await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False)
    await db_session.commit()
    db_session.expunge_all()

    loaded = await load_reverse_dcf(db_session, CIK)
    assert loaded is not None
    stored_base, stored_grid, (stored_cagr, stored_from, stored_to) = loaded

    assert stored_base.fiscal_year == base.fiscal_year
    assert stored_base.implied_growth == _stored_rate(base.implied_growth)
    # The storage contract is only defensible if what it discards is below the
    # accuracy the solver claims. Asserted, not assumed.
    assert abs(stored_base.implied_growth - base.implied_growth) < SOLVER_TOLERANCE
    assert stored_base.insufficient_data == base.insufficient_data
    assert stored_base.reason == base.reason
    assert stored_base.enterprise_value == base.enterprise_value
    assert stored_base.free_cash_flow == base.free_cash_flow
    assert stored_base.market_cap == base.market_cap
    assert stored_base.total_debt == base.total_debt
    assert stored_base.cash_and_equivalents == base.cash_and_equivalents
    assert stored_base.discount_rate == _stored_rate(base.discount_rate)
    assert stored_base.terminal_growth == _stored_rate(base.terminal_growth)
    assert stored_base.horizon_years == base.horizon_years
    assert stored_base.caveats == base.caveats
    assert stored_base.attribution == base.attribution
    assert stored_base.spec_version == base.spec_version
    assert stored_base.market_price_date == base.market_price_date
    assert stored_base.market_price_source == base.market_price_source

    assert (stored_cagr, stored_from, stored_to) == (
        _stored_rate(cagr),
        cagr_from,
        cagr_to,
    )

    assert grid is not None and stored_grid is not None
    assert stored_grid.low == _stored_rate(grid.low)
    assert stored_grid.high == _stored_rate(grid.high)
    assert stored_grid.resolved_cells == grid.resolved_cells
    assert stored_grid.total_cells == grid.total_cells
    # The axes are recovered from the stored cells rather than re-read from the
    # spec, so this also pins that every axis value survived the round trip.
    assert stored_grid.discount_rates == tuple(
        _stored_rate(rate) for rate in grid.discount_rates
    )
    assert stored_grid.terminal_growths == tuple(
        _stored_rate(rate) for rate in grid.terminal_growths
    )

    # Cell-by-cell, not just the band: the band is two numbers and would still match
    # if the interior of the grid were scrambled or truncated.
    assert len(stored_grid.cells) == len(grid.cells)
    by_assumption = {
        (c.discount_rate, c.terminal_growth): c for c in stored_grid.cells
    }
    for cell in grid.cells:
        key = (_stored_rate(cell.discount_rate), _stored_rate(cell.terminal_growth))
        stored_cell = by_assumption[key]
        assert stored_cell.implied_growth == _stored_rate(cell.implied_growth)
        # A cell that failed keeps its reason — dropping it would let the grid
        # imply its own coverage is complete.
        assert stored_cell.reason == cell.reason


@requires_db
async def test_a_filer_whose_model_does_not_apply_still_stores_a_row(db_session) -> None:
    """AD-16: absence explains itself.

    A missing row and an unresolvable filer must not look the same — otherwise
    Suncor, which genuinely has no capex tag in any year, would be indistinguishable
    from a filer the pipeline failed on.
    """
    db_session.add(Issuer(cik=CIK, ticker=TICKER, name="No Capex Co"))
    db_session.add(
        Filing(
            accession_number=ACCN,
            issuer_cik=CIK,
            form_type="10-K",
            filing_date=date(2026, 2, 1),
            fiscal_year=LATEST_YEAR,
            fiscal_year_end=FYE,
        )
    )
    await db_session.flush()
    # Everything the DCF needs EXCEPT capex — the real Suncor shape.
    for concept, value in FACTS.items():
        if concept == "capex":
            continue
        db_session.add(
            CanonicalFact(
                issuer_cik=CIK,
                accession_number=ACCN,
                canonical_concept=concept,
                fiscal_year=LATEST_YEAR,
                period_end=FYE,
                value=Decimal(value),
                unit="USD",
                mapping_version=MAPPING_VERSION,
            )
        )
    await db_session.commit()

    year = await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False)
    await db_session.commit()

    assert year == LATEST_YEAR
    run = (await db_session.execute(select(ReverseDcfRun))).scalar_one()
    assert run.insufficient_data is True
    assert run.reason, "an unresolvable filer must say why, not just be absent"
    assert run.implied_growth is None
    # No grid: `grid_for` returns None when the operands are unavailable, and that
    # is distinct from a grid in which no cell resolved.
    assert run.has_grid is False
    assert run.total_cells == 0


@requires_db
async def test_a_filer_with_no_canonical_facts_stores_nothing(db_session) -> None:
    """Nothing to compute from is not the same as computed-and-unresolvable."""
    db_session.add(Issuer(cik=CIK, ticker=TICKER, name="Empty Co"))
    await db_session.commit()

    assert await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False) is None
    assert (await db_session.execute(select(ReverseDcfRun))).first() is None


# --- 4. a spec bump hides rows computed under the old assumptions -------------


@requires_db
async def test_a_row_from_another_spec_version_is_not_served(db_session) -> None:
    """A stored figure must never outlive the assumptions the methodology page
    publishes for it. A spec bump makes the old row invisible rather than presenting
    it under the new spec's name."""
    await _seed(db_session)
    await materialize_reverse_dcf(db_session, CIK, is_capital_intensive=False)
    await db_session.execute(
        ReverseDcfRun.__table__.update().values(spec_version="reverse_dcf_v0")
    )
    await db_session.commit()

    assert await load_reverse_dcf(db_session, CIK) is None
