"""Persist score runs (append-only, AD-6) with results + inputs (AD-16, AD-18).

A new run for (issuer, model, fiscal_year) supersedes any prior non-superseded
run rather than mutating it. Per-signal results carry tri-state status; the run
carries the aggregate value and cited band label (computed backend, AD-8/AD-12)
and the sector applicability state (AD-20).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal

from app.models import (
    Applicability,
    CanonicalFact,
    Issuer,
    Model,
    ScoreInput,
    ScoreResult,
    ScoreRun,
)
from canonicalization.mappings import MAPPING_VERSION
from formulas.engine import load_spec
from raw_store.fx_rates import get_fx_rate_on_or_before
from raw_store.market_prices import get_fye_close
from scoring.altman import compute_altman
from scoring.beneish import compute_beneish
from scoring.facts import load_facts
from scoring.piotroski import compute_piotroski, piotroski_band, piotroski_score
from scoring.sloan import compute_sloan, sloan_band


async def _supersede_prior(session: AsyncSession, issuer_cik: str, model: Model, fiscal_year: int, new_run_id) -> None:
    prior = (
        await session.execute(
            select(ScoreRun).where(
                ScoreRun.issuer_cik == issuer_cik,
                ScoreRun.model == model,
                ScoreRun.fiscal_year == fiscal_year,
                ScoreRun.superseded.is_(False),
                ScoreRun.id != new_run_id,
            )
        )
    ).scalars().all()
    for run in prior:
        run.superseded = True
        run.superseded_by = new_run_id


async def _canonical_fact_for_year(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> CanonicalFact | None:
    """A representative canonical fact for (issuer, fiscal_year) — the correct
    provenance root for a score_run's accession_number and true fiscal-year-end.

    NOT derived from Filing.fiscal_year: that column is the accession's OWN
    primary year, which can differ from a fiscal year whose only canonical data
    is a restated comparative embedded in a LATER filing (e.g. SHOP's FY2023
    facts live only inside its FY2024 10-K's comparative column — there is no
    Filing row with fiscal_year=2023 at all). CanonicalFact.fiscal_year is the
    period the value actually describes, correctly resolved by AD-3 selection,
    so it is the reliable join key here."""
    return (
        await session.execute(
            select(CanonicalFact)
            .where(CanonicalFact.issuer_cik == issuer_cik, CanonicalFact.fiscal_year == fiscal_year)
            .order_by(CanonicalFact.canonical_concept)
            .limit(1)
        )
    ).scalars().first()


async def _accession_for(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> str:
    fact = await _canonical_fact_for_year(session, issuer_cik, fiscal_year)
    return fact.accession_number if fact else ""


async def score_piotroski(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> ScoreRun:
    spec = load_spec("piotroski_v1")
    facts = await load_facts(session, issuer_cik, mapping_version=MAPPING_VERSION)
    outcomes = compute_piotroski(facts, fiscal_year, spec)
    score = piotroski_score(outcomes)

    run = ScoreRun(
        issuer_cik=issuer_cik,
        model=Model.piotroski,
        fiscal_year=fiscal_year,
        formula_version=spec.formula_version,
        accession_number=await _accession_for(session, issuer_cik, fiscal_year),
        aggregate_value=score,
        applicability=Applicability.computed,
    )
    session.add(run)
    await session.flush()
    await _supersede_prior(session, issuer_cik, Model.piotroski, fiscal_year, run.id)

    for o in outcomes:
        session.add(
            ScoreResult(
                score_run_id=run.id,
                model=Model.piotroski,
                signal_key=o.key,
                value=o.value,
                status=o.status,
                band_label=piotroski_band(score, spec) if o.key == "roa_positive" else None,
                threshold_ref=spec.formula_version,
            )
        )
        for concept, fy in o.inputs:
            fid = facts.fact_id(concept, fy)
            if fid is not None:
                session.add(ScoreInput(score_run_id=run.id, signal_key=o.key, canonical_fact_id=fid))
    # Store the run-level band on the aggregate marker result for easy read.
    run.aggregate_value = score
    await session.flush()
    return run


async def score_altman(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> ScoreRun:
    spec = load_spec("altman_v1")
    facts = await load_facts(session, issuer_cik, mapping_version=MAPPING_VERSION)
    issuer = await session.get(Issuer, issuer_cik)

    fact = await _canonical_fact_for_year(session, issuer_cik, fiscal_year)
    market_close = None
    market_price_id = None
    fx_rate_id = None
    if fact is not None:
        mp = await get_fye_close(session, issuer_cik, fact.period_end)
        if mp is not None:
            market_close = Decimal(str(mp.close_price))
            market_price_id = mp.id

            # Currency fix (2026-07-23, confirmed live against real filings): Tiingo's
            # close price is always USD, but some filers (e.g. CP) report every
            # financial-statement figure in a different currency (CAD) — X1/X2/X3/X5
            # are automatically internally consistent (all raw XBRL facts share one
            # currency), but X4 would silently divide a USD numerator by a non-USD
            # denominator without this. Convert into the issuer's own reporting
            # currency using the Bank of Canada's own rate; if no rate is available
            # for the date, X4 is insufficient_data rather than silently wrong.
            reporting_currency = facts.unit("total_assets", fiscal_year)
            if reporting_currency and reporting_currency != "USD":
                fx = await get_fx_rate_on_or_before(session, f"USD{reporting_currency}", fact.period_end)
                if fx is not None:
                    market_close = market_close * Decimal(str(fx.rate))
                    fx_rate_id = fx.id
                else:
                    # No FX rate for this date — market_price_id must also clear, or
                    # the ScoreInput link below would misleadingly point to a USD
                    # price that was never actually used in the (insufficient_data) X4.
                    market_close = None
                    market_price_id = None

    result = compute_altman(
        facts,
        fiscal_year,
        spec,
        market_close=market_close,
        is_financial_sector=bool(issuer and issuer.is_financial_sector),
        is_capital_intensive=bool(issuer and issuer.is_capital_intensive),
    )

    run = ScoreRun(
        issuer_cik=issuer_cik,
        model=Model.altman,
        fiscal_year=fiscal_year,
        formula_version=spec.formula_version,
        accession_number=fact.accession_number if fact else "",
        aggregate_value=result.z_score,
        applicability=result.applicability,
    )
    session.add(run)
    await session.flush()
    await _supersede_prior(session, issuer_cik, Model.altman, fiscal_year, run.id)

    for i, comp in enumerate(result.components):
        session.add(
            ScoreResult(
                score_run_id=run.id,
                model=Model.altman,
                signal_key=comp.key,
                value=comp.value,
                status=comp.status,
                band_label=result.band if i == 0 else None,  # Z band on the first component
                threshold_ref=spec.formula_version,
            )
        )
    # Link the market price (and, if the issuer's currency required conversion,
    # the FX rate) actually used, if any.
    if market_price_id is not None:
        session.add(
            ScoreInput(
                score_run_id=run.id,
                signal_key="x4_market_value_equity",
                market_price_id=market_price_id,
                fx_rate_id=fx_rate_id,
            )
        )
    await session.flush()
    return run


async def score_beneish(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> ScoreRun:
    spec = load_spec("beneish_v1")
    facts = await load_facts(session, issuer_cik, mapping_version=MAPPING_VERSION)
    issuer = await session.get(Issuer, issuer_cik)
    result = compute_beneish(
        facts, fiscal_year, spec, is_financial_sector=bool(issuer and issuer.is_financial_sector)
    )

    run = ScoreRun(
        issuer_cik=issuer_cik,
        model=Model.beneish,
        fiscal_year=fiscal_year,
        formula_version=spec.formula_version,
        accession_number=await _accession_for(session, issuer_cik, fiscal_year),
        aggregate_value=result.m_score,
        applicability=result.applicability,
    )
    session.add(run)
    await session.flush()
    await _supersede_prior(session, issuer_cik, Model.beneish, fiscal_year, run.id)

    for i, comp in enumerate(result.components):
        session.add(
            ScoreResult(
                score_run_id=run.id,
                model=Model.beneish,
                signal_key=comp.key,
                value=comp.value,
                status=comp.status,
                band_label=result.band if i == 0 else None,
                threshold_ref=spec.formula_version,
            )
        )
    await session.flush()
    return run


async def score_sloan(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> ScoreRun:
    spec = load_spec("sloan_v1")
    facts = await load_facts(session, issuer_cik, mapping_version=MAPPING_VERSION)
    outcome = compute_sloan(facts, fiscal_year, spec)

    run = ScoreRun(
        issuer_cik=issuer_cik,
        model=Model.sloan,
        fiscal_year=fiscal_year,
        formula_version=spec.formula_version,
        accession_number=await _accession_for(session, issuer_cik, fiscal_year),
        aggregate_value=outcome.value,
        applicability=Applicability.computed,
    )
    session.add(run)
    await session.flush()
    await _supersede_prior(session, issuer_cik, Model.sloan, fiscal_year, run.id)

    session.add(
        ScoreResult(
            score_run_id=run.id,
            model=Model.sloan,
            signal_key=outcome.key,
            value=outcome.value,
            status=outcome.status,
            band_label=sloan_band(outcome, spec),
            threshold_ref=spec.formula_version,
        )
    )
    for concept, fy in outcome.inputs:
        fid = facts.fact_id(concept, fy)
        if fid is not None:
            session.add(ScoreInput(score_run_id=run.id, signal_key=outcome.key, canonical_fact_id=fid))
    await session.flush()
    return run
