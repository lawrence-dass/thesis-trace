"""Materialize the reverse DCF on the write path, and read it back (AD-1).

`valuation/overview.py` COMPUTES the reverse DCF; this module decides where the
computation happens. AD-1 is a structural rule — "all computation runs in the
scheduled batch pipeline; the read path only queries materialized Postgres and never
computes a score" (epics.md:60), and "no request can trigger scoring, ingestion, or
recomputation" (epics.md:614). Until this module existed, `reverse_dcf_for_issuer`
had exactly one caller and it was on the read path, so every page load re-solved the
DCF and all 35 sensitivity cells.

THE WRITE IS AN UPSERT, DELIBERATELY. `pipeline/run.py` is a daily cron over the
same canonical facts. `run_validation` is the precedent this repo already paid for:
implemented, tested, and then appending a duplicate row every night once the cron
actually ran. A writer here without an idempotency key would do the same, and
`get_company_overview` would surface whichever duplicate it happened to order first.

`load_reverse_dcf` returns the SAME tuple shape as `reverse_dcf_for_issuer` so the
read path's operand assembly — which projects already-loaded canonical facts and
computes nothing — needs no changes at all.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, ReverseDcfCell, ReverseDcfRun
from canonicalization.mappings import MAPPING_VERSION
from valuation.overview import DCF_CONCEPTS, reverse_dcf_for_issuer
from valuation.reverse_dcf import SPEC_VERSION, ReverseDcf
from valuation.sensitivity import SensitivityCell, SensitivityGrid

#: What `reverse_dcf_for_issuer` returns and what `load_reverse_dcf` reconstructs.
ReverseDcfBundle = tuple[
    ReverseDcf, SensitivityGrid | None, tuple[Decimal | None, int | None, int | None]
]


async def _dcf_facts(session: AsyncSession, issuer_cik: str) -> list[CanonicalFact]:
    """The canonical facts the reverse DCF reads, in one bounded query.

    The read path gets these for free from its existing single pass; the pipeline
    has no such pass, so it asks for exactly `DCF_CONCEPTS` and nothing more.
    """
    return list(
        (
            await session.execute(
                select(CanonicalFact).where(
                    CanonicalFact.issuer_cik == issuer_cik,
                    CanonicalFact.mapping_version == MAPPING_VERSION,
                    CanonicalFact.superseded.is_(False),
                    CanonicalFact.canonical_concept.in_(DCF_CONCEPTS),
                )
            )
        )
        .scalars()
        .all()
    )


async def materialize_reverse_dcf(
    session: AsyncSession,
    issuer_cik: str,
    *,
    is_capital_intensive: bool,
) -> int | None:
    """Compute this issuer's reverse DCF and store it. Returns the fiscal year, or
    None when the filer has no canonical facts at all.

    A filer whose model does not apply still stores a row carrying
    `insufficient_data` and the reason (AD-16) — absence explains itself, and a
    missing row would be indistinguishable from a pipeline that never ran.
    """
    facts = await _dcf_facts(session, issuer_cik)
    computed = await reverse_dcf_for_issuer(
        session,
        issuer_cik=issuer_cik,
        is_capital_intensive=is_capital_intensive,
        facts=facts,
    )
    if computed is None:
        return None
    base, grid, (cagr, cagr_from, cagr_to) = computed

    values = {
        "issuer_cik": issuer_cik,
        "fiscal_year": base.fiscal_year,
        "spec_version": base.spec_version,
        "implied_growth": base.implied_growth,
        "insufficient_data": base.insufficient_data,
        "reason": base.reason,
        "enterprise_value": base.enterprise_value,
        "free_cash_flow": base.free_cash_flow,
        "market_cap": base.market_cap,
        "total_debt": base.total_debt,
        "cash_and_equivalents": base.cash_and_equivalents,
        "discount_rate": base.discount_rate,
        "terminal_growth": base.terminal_growth,
        "horizon_years": base.horizon_years,
        "caveats": list(base.caveats),
        "attribution": base.attribution,
        "market_price_date": base.market_price_date,
        "market_price_source": base.market_price_source,
        "fx_rate": base.fx_rate,
        "fx_rate_date": base.fx_rate_date,
        "fx_rate_source": base.fx_rate_source,
        "has_grid": grid is not None,
        "grid_low": grid.low if grid is not None else None,
        "grid_high": grid.high if grid is not None else None,
        "resolved_cells": grid.resolved_cells if grid is not None else 0,
        "total_cells": grid.total_cells if grid is not None else 0,
        "historical_revenue_cagr": cagr,
        "historical_from_fiscal_year": cagr_from,
        "historical_to_fiscal_year": cagr_to,
    }

    statement = pg_insert(ReverseDcfRun).values(**values)
    # Every non-key column is refreshed. A partial update would let a filer that
    # stops resolving keep last night's implied growth beside tonight's reason.
    statement = statement.on_conflict_do_update(
        constraint="uq_reverse_dcf_runs_key",
        set_={
            key: statement.excluded[key]
            for key in values
            if key not in ("issuer_cik", "fiscal_year", "spec_version")
        },
    ).returning(ReverseDcfRun.id)
    run_id = (await session.execute(statement)).scalar_one()

    # The solver picks the fiscal year, and a later run can pick an EARLIER one when
    # newer data stops resolving. Without this the superseded newer row would linger
    # and `load_reverse_dcf`, which takes the latest stored year, would return it.
    await session.execute(
        delete(ReverseDcfRun).where(
            ReverseDcfRun.issuer_cik == issuer_cik,
            ReverseDcfRun.spec_version == base.spec_version,
            ReverseDcfRun.fiscal_year != base.fiscal_year,
        )
    )

    # Replace rather than upsert the cells: the grid's axes come from the spec, so a
    # spec whose axes narrowed would otherwise leave orphaned cells behind that were
    # never recomputed.
    await session.execute(
        delete(ReverseDcfCell).where(ReverseDcfCell.reverse_dcf_run_id == run_id)
    )
    if grid is not None and grid.cells:
        await session.execute(
            ReverseDcfCell.__table__.insert(),
            [
                {
                    "reverse_dcf_run_id": run_id,
                    "discount_rate": cell.discount_rate,
                    "terminal_growth": cell.terminal_growth,
                    "implied_growth": cell.implied_growth,
                    "reason": cell.reason,
                }
                for cell in grid.cells
            ],
        )
    return base.fiscal_year


async def load_reverse_dcf(
    session: AsyncSession, issuer_cik: str
) -> ReverseDcfBundle | None:
    """The stored reverse DCF for this issuer, or None when the pipeline has not
    materialized one.

    TWO BOUNDED QUERIES AND NO SOLVING. Returns the same tuple
    `reverse_dcf_for_issuer` returns, so the caller cannot tell the difference —
    which is the point: the read path's job is projection, not computation.

    Filtered to the CURRENT `SPEC_VERSION`. A spec bump makes the old row invisible
    rather than silently presenting figures computed under assumptions the
    methodology page no longer publishes.
    """
    run = (
        await session.execute(
            select(ReverseDcfRun)
            .where(
                ReverseDcfRun.issuer_cik == issuer_cik,
                ReverseDcfRun.spec_version == SPEC_VERSION,
            )
            .order_by(ReverseDcfRun.fiscal_year.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        return None

    base = ReverseDcf(
        fiscal_year=run.fiscal_year,
        implied_growth=run.implied_growth,
        insufficient_data=run.insufficient_data,
        reason=run.reason,
        enterprise_value=run.enterprise_value,
        free_cash_flow=run.free_cash_flow,
        market_cap=run.market_cap,
        total_debt=run.total_debt,
        cash_and_equivalents=run.cash_and_equivalents,
        discount_rate=run.discount_rate,
        terminal_growth=run.terminal_growth,
        horizon_years=run.horizon_years,
        caveats=tuple(run.caveats or ()),
        attribution=run.attribution,
        spec_version=run.spec_version,
        market_price_date=run.market_price_date,
        market_price_source=run.market_price_source,
        fx_rate=run.fx_rate,
        fx_rate_date=run.fx_rate_date,
        fx_rate_source=run.fx_rate_source,
    )

    grid = None
    if run.has_grid:
        cell_rows = (
            (
                await session.execute(
                    select(ReverseDcfCell)
                    .where(ReverseDcfCell.reverse_dcf_run_id == run.id)
                    .order_by(
                        ReverseDcfCell.discount_rate, ReverseDcfCell.terminal_growth
                    )
                )
            )
            .scalars()
            .all()
        )
        cells = tuple(
            SensitivityCell(
                discount_rate=row.discount_rate,
                terminal_growth=row.terminal_growth,
                implied_growth=row.implied_growth,
                reason=row.reason,
            )
            for row in cell_rows
        )
        # Axes are recovered from the stored cells, not re-read from the spec: the
        # grid must describe the assumptions it was actually solved under, even if
        # the spec's axes have since changed.
        grid = SensitivityGrid(
            fiscal_year=run.fiscal_year,
            cells=cells,
            low=run.grid_low,
            high=run.grid_high,
            resolved_cells=run.resolved_cells,
            total_cells=run.total_cells,
            discount_rates=tuple(sorted({c.discount_rate for c in cells})),
            terminal_growths=tuple(sorted({c.terminal_growth for c in cells})),
            spec_version=run.spec_version,
        )

    return base, grid, (
        run.historical_revenue_cagr,
        run.historical_from_fiscal_year,
        run.historical_to_fiscal_year,
    )
