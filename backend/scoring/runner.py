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
    CanonicalFact,
    Issuer,
    Model,
    ScoreInput,
    ScoreResult,
    ScoreRun,
)
from canonicalization.mappings import MAPPING_VERSION
from formulas.engine import load_spec
from raw_store.market_prices import resolve_fye_price
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
            .where(
                CanonicalFact.issuer_cik == issuer_cik,
                CanonicalFact.fiscal_year == fiscal_year,
                CanonicalFact.mapping_version == MAPPING_VERSION,
                CanonicalFact.superseded.is_(False),
            )
            .order_by(CanonicalFact.canonical_concept)
            .limit(1)
        )
    ).scalars().first()


async def _accession_for(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> str:
    fact = await _canonical_fact_for_year(session, issuer_cik, fiscal_year)
    return fact.accession_number if fact else ""



def _applicability(spec, facts, fiscal_year: int, base_applicability, base_reason=None):
    """Layer the cross-filer comparability caveat onto a model's own verdict.

    Inputs come from the spec's own `inputs` list, so a newly flagged source tag
    reaches all four models without a per-model edit. Year t-1 is included because
    Beneish and Piotroski are year-over-year models.

    Never alters a score — the same posture as Beneish's out-of-calibration guard.
    An existing caveat is kept and this one appended, so one reason cannot silently
    replace another, and an excluded_out_of_scope verdict is never downgraded to a
    mere caveat.
    """
    reasons = facts.mismatch_reasons(spec.raw.get("inputs", []), (fiscal_year, fiscal_year - 1))
    if not reasons or base_applicability is Applicability.excluded_out_of_scope:
        return base_applicability, base_reason
    combined = " ".join(reasons)
    if base_reason:
        combined = f"{base_reason} {combined}"
    return Applicability.computed_with_caveat, combined[:512]

def _as_run_fields(pair) -> dict:
    applicability, caveat_reason = pair
    return {"applicability": applicability, "caveat_reason": caveat_reason}


async def score_piotroski(session: AsyncSession, issuer_cik: str, fiscal_year: int) -> ScoreRun:
    spec = load_spec("piotroski_v1")
    facts = await load_facts(session, issuer_cik, mapping_version=MAPPING_VERSION)
    outcomes = compute_piotroski(facts, fiscal_year, spec)
    score = piotroski_score(outcomes)
    applicability, caveat_reason = _applicability(spec, facts, fiscal_year, Applicability.computed)

    run = ScoreRun(
        issuer_cik=issuer_cik,
        model=Model.piotroski,
        fiscal_year=fiscal_year,
        formula_version=spec.formula_version,
        accession_number=await _accession_for(session, issuer_cik, fiscal_year),
        aggregate_value=score,
        applicability=applicability,
        caveat_reason=caveat_reason,
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
        # Tiingo is USD while some filers report in CAD.  Keep this conversion in
        # one shared resolver so Altman and reverse DCF cannot drift apart.
        resolution = await resolve_fye_price(
            session,
            issuer_cik=issuer_cik,
            fiscal_year_end=fact.period_end,
            reporting_currency=facts.unit("total_assets", fiscal_year),
        )
        if resolution.price is not None:
            market_close = resolution.price
            market_price_id = resolution.market_price.id if resolution.market_price else None
            fx_rate_id = resolution.fx_rate.id if resolution.fx_rate else None

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
        **_as_run_fields(_applicability(spec, facts, fiscal_year, result.applicability, result.caveat_reason)),
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
        **_as_run_fields(_applicability(spec, facts, fiscal_year, result.applicability, result.caveat_reason)),
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

    applicability, caveat_reason = _applicability(spec, facts, fiscal_year, Applicability.computed)
    run = ScoreRun(
        issuer_cik=issuer_cik,
        model=Model.sloan,
        fiscal_year=fiscal_year,
        formula_version=spec.formula_version,
        accession_number=await _accession_for(session, issuer_cik, fiscal_year),
        aggregate_value=outcome.value,
        applicability=applicability,
        caveat_reason=caveat_reason,
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
