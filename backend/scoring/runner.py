"""Persist score runs (append-only, AD-6) with results + inputs (AD-16, AD-18).

A new run for (issuer, model, fiscal_year) supersedes any prior non-superseded
run rather than mutating it. Per-signal results carry tri-state status; the run
carries the aggregate value and cited band label (computed backend, AD-8/AD-12)
and the sector applicability state (AD-20).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Applicability,
    Filing,
    Model,
    ScoreInput,
    ScoreResult,
    ScoreRun,
)
from canonicalization.mappings import MAPPING_VERSION
from formulas.engine import load_spec
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


async def _accession_for(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> str:
    filing = (
        await session.execute(
            select(Filing).where(Filing.issuer_cik == issuer_cik, Filing.fiscal_year == fiscal_year)
        )
    ).scalars().first()
    return filing.accession_number if filing else ""


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
