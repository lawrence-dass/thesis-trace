"""Read-only queries against materialized Postgres (AD-1, AD-10).

Never computes a score, never calls EDGAR/Tiingo. Assembles the current
(non-superseded) score runs for an issuer with per-signal results and the
provenance of each input.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CanonicalFact,
    DataQualityIssue,
    Filing,
    IssueStatus,
    Issuer,
    ScoreInput,
    ScoreResult,
    ScoreRun,
)
from api.schemas import (
    CompanyCardOut,
    CompanyOverviewOut,
    DataQualityOut,
    LensScoreOut,
    Provenance,
    SignalOut,
    VerdictItem,
)

# Lens category per model (FR-5 Quality/Health vs FR-8 Integrity).
LENS_CATEGORY = {
    "piotroski": "quality_health",
    "altman": "quality_health",
    "beneish": "integrity",
    "sloan": "integrity",
}

# Phase honesty (FR-9): the Value and Growth lenses are Phase-2, shown as pending.
PENDING_LENSES = ["value", "growth"]


async def list_companies(session: AsyncSession) -> list[CompanyCardOut]:
    issuers = (await session.execute(select(Issuer).order_by(Issuer.ticker))).scalars().all()
    return [
        CompanyCardOut(
            cik=i.cik,
            ticker=i.ticker,
            name=i.name,
            last_updated=i.updated_at.isoformat() if i.updated_at else None,
        )
        for i in issuers
    ]


async def get_issuer_by_ticker(session: AsyncSession, ticker: str) -> Issuer | None:
    return (
        await session.execute(select(Issuer).where(Issuer.ticker == ticker.upper()))
    ).scalars().first()


async def _provenance_for(session: AsyncSession, run_id, signal_key: str) -> list[Provenance]:
    rows = (
        await session.execute(
            select(CanonicalFact, Filing.form_type)
            .join(ScoreInput, ScoreInput.canonical_fact_id == CanonicalFact.id)
            .join(Filing, Filing.accession_number == CanonicalFact.accession_number)
            .where(ScoreInput.score_run_id == run_id, ScoreInput.signal_key == signal_key)
        )
    ).all()
    return [
        Provenance(
            accession_number=cf.accession_number,
            canonical_concept=cf.canonical_concept,
            fiscal_year=cf.fiscal_year,
            period_end=cf.period_end.isoformat() if cf.period_end else None,
            source_filing_form=form,
            derivation=cf.derivation,
        )
        for cf, form in rows
    ]


async def get_company_overview(session: AsyncSession, ticker: str) -> CompanyOverviewOut | None:
    issuer = await get_issuer_by_ticker(session, ticker)
    if issuer is None:
        return None

    runs = (
        await session.execute(
            select(ScoreRun).where(
                ScoreRun.issuer_cik == issuer.cik, ScoreRun.superseded.is_(False)
            ).order_by(ScoreRun.model, ScoreRun.fiscal_year.desc())
        )
    ).scalars().all()

    scores: list[LensScoreOut] = []
    for run in runs:
        results = (
            await session.execute(
                select(ScoreResult).where(ScoreResult.score_run_id == run.id).order_by(ScoreResult.signal_key)
            )
        ).scalars().all()
        signals = [
            SignalOut(
                signal_key=r.signal_key,
                status=r.status.value,
                value=float(r.value) if r.value is not None else None,
                band_label=r.band_label,
                provenance=await _provenance_for(session, run.id, r.signal_key),
            )
            for r in results
        ]
        scores.append(
            LensScoreOut(
                model=run.model.value,
                category=LENS_CATEGORY.get(run.model.value, "quality_health"),
                fiscal_year=run.fiscal_year,
                formula_version=run.formula_version,
                aggregate_value=float(run.aggregate_value) if run.aggregate_value is not None else None,
                band_label=next((s.band_label for s in signals if s.band_label), None),
                applicability=run.applicability.value,
                signals=signals,
                caveat_reason=run.caveat_reason,
            )
        )

    # Open data-quality warnings for this issuer's filings (AD-17, FR-8) — never hidden.
    dq_rows = (
        await session.execute(
            select(DataQualityIssue, Filing.issuer_cik)
            .join(Filing, Filing.accession_number == DataQualityIssue.accession_number)
            .where(Filing.issuer_cik == issuer.cik, DataQualityIssue.status != IssueStatus.dismissed)
        )
    ).all()
    data_quality = [
        DataQualityOut(
            issue_type=dq.issue_type,
            status=dq.status.value,
            raised_by=dq.raised_by,
            accession_number=dq.accession_number,
            detail=dq.detail,
        )
        for dq, _cik in dq_rows
    ]

    # Verdict: each live model's own classification for its latest fiscal year
    # WITH a usable value, side by side — never blended into one number
    # (AD-12). A model is scored every scoreable year regardless of whether
    # its inputs actually resolve (Beneish always gets a ScoreRun row, even
    # when insufficient_data), so naively taking the newest run per model
    # can hide real, valid results behind an unrelated later year that
    # happens to be missing an input. Confirmed live 2026-07-29: QSR has 7
    # real Beneish years (2017-2023) and OTEX has 9 (2011-2019) sitting in
    # the database, both hidden behind their unrelated FY2025 insufficient
    # run under the old "just take the newest" selection. Falls back to the
    # latest run's insufficient_data/excluded state only when NO year for
    # that model ever resolved (e.g. CP/SHOP's Beneish, which never
    # computes) so the model still appears in the Verdict rather than
    # silently vanishing.
    latest_valid_by_model: dict[str, LensScoreOut] = {}
    latest_any_by_model: dict[str, LensScoreOut] = {}
    for s in scores:
        cur_any = latest_any_by_model.get(s.model)
        if cur_any is None or s.fiscal_year > cur_any.fiscal_year:
            latest_any_by_model[s.model] = s
        if s.aggregate_value is not None:
            cur_valid = latest_valid_by_model.get(s.model)
            if cur_valid is None or s.fiscal_year > cur_valid.fiscal_year:
                latest_valid_by_model[s.model] = s
    latest_by_model = {
        model: latest_valid_by_model.get(model, latest_any_by_model[model])
        for model in latest_any_by_model
    }
    verdict = [
        VerdictItem(
            model=s.model,
            category=s.category,
            fiscal_year=s.fiscal_year,
            aggregate_value=s.aggregate_value,
            band_label=s.band_label,
            applicability=s.applicability,
            # Only meaningful when the aggregate never resolved for any year
            # (e.g. CP/SHOP's Beneish) — names which sub-signals are still
            # missing so the UI can explain why, not just show a bare dash.
            missing_signals=(
                [sig.signal_key for sig in s.signals if sig.status == "insufficient_data"]
                if s.aggregate_value is None
                else []
            ),
        )
        for s in sorted(latest_by_model.values(), key=lambda x: (x.category, x.model))
    ]

    lenses_live = sorted({s.model for s in scores})
    return CompanyOverviewOut(
        cik=issuer.cik,
        ticker=issuer.ticker,
        name=issuer.name,
        lenses_live=lenses_live,
        lenses_pending=PENDING_LENSES,
        verdict=verdict,
        scores=scores,
        data_quality=data_quality,
    )
