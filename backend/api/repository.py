"""Read-only queries against materialized Postgres (AD-1, AD-10).

Never computes a score, never calls EDGAR/Tiingo. Assembles the current
(non-superseded) score runs for an issuer with per-signal results and the
provenance of each input.
"""

from __future__ import annotations

from datetime import datetime

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
    ChangeProvenance,
    CompanyCardOut,
    CompanyChangesOut,
    CompanyOverviewOut,
    DataQualityChangeOut,
    DataQualityOut,
    FactChangeOut,
    LensScoreOut,
    NearTermDebtShareOut,
    Provenance,
    TrajectoryOut,
    RunChangeOut,
    SignalChangeOut,
    SignalOut,
    VerdictItem,
)
from canonicalization.mappings import MAPPING_VERSION
from debt.engine import DENOMINATOR_CONCEPT, NUMERATOR_CONCEPT, shares_for_facts
from diff.engine import diff_company_since, latest_filing_pivot
from trajectory.engine import trajectories_for_scores

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

    # Trajectory-over-level (PRD OQ9, Story 5.5). Computed from the runs already
    # fetched above — no extra query, so this cannot become an N+1. A ThesisTrace
    # presentation rule: it annotates each score with a direction and never
    # changes one, and `attribution` travels with it so the UI cannot render a
    # direction without saying whose judgment it is.
    traj = trajectories_for_scores(scores)
    for s_ in scores:
        t = traj.get((s_.model, s_.fiscal_year))
        if t is None:
            continue
        s_.trajectory = TrajectoryOut(
            direction=t.direction.value,
            label=t.label,
            from_fiscal_year=t.from_fiscal_year,
            to_fiscal_year=t.to_fiscal_year,
            from_value=float(t.from_value) if t.from_value is not None else None,
            to_value=float(t.to_value) if t.to_value is not None else None,
            attribution=t.attribution,
            spec_version=t.spec_version,
        )

    # Near-term debt share (PRD OQ9, Story 5.6). One query for both operands across
    # every fiscal year, then a pure computation — same shape as the trajectory pass
    # above, and it cannot become an N+1. A ThesisTrace presentation rule: it stands
    # beside the scores and never adjusts one.
    debt_facts = (
        await session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == issuer.cik,
                CanonicalFact.mapping_version == MAPPING_VERSION,
                CanonicalFact.canonical_concept.in_((NUMERATOR_CONCEPT, DENOMINATOR_CONCEPT)),
            )
        )
    ).scalars().all()
    near_term_debt_share = [
        NearTermDebtShareOut(
            fiscal_year=share.fiscal_year,
            share=float(share.value) if share.value is not None else None,
            band_label=share.label,
            tone=share.tone,
            near_term_debt=float(share.near_term_debt) if share.near_term_debt is not None else None,
            total_debt=float(share.total_debt) if share.total_debt is not None else None,
            insufficient_data=share.insufficient_data,
            attribution=share.attribution,
            spec_version=share.spec_version,
        )
        for _, share in sorted(shares_for_facts(debt_facts).items(), reverse=True)
    ]

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
        near_term_debt_share=near_term_debt_share,
        data_quality=data_quality,
    )


def _f(v) -> float | None:
    """Decimal -> float at the presentation boundary only.

    Computation and storage stay NUMERIC (AD-15); this conversion happens once,
    here, because the response is JSON. Consistent with the rest of this module.
    """
    return float(v) if v is not None else None


def _change_provenance(p) -> ChangeProvenance | None:
    if p is None:
        return None
    return ChangeProvenance(
        accession_number=p.accession_number,
        canonical_concept=p.canonical_concept,
        fiscal_year=p.fiscal_year,
        period_end=p.period_end,
        source_filing_form=p.source_filing_form,
        derivation=p.derivation,
    )


async def get_company_changes(
    session: AsyncSession, ticker: str, since: datetime | None = None
) -> CompanyChangesOut | None:
    """What moved for a company since `since` (FR-22).

    Read-only per AD-1: delegates to the Story 5.2 diff engine, which reads
    stored values only. No request on this path can trigger scoring, ingestion
    or recomputation.

    DEFAULT PIVOT. When `since` is omitted this does NOT compare against the
    immediately-superseded run, which the story text suggested — `pipeline/run.py`
    is a daily cron that supersedes every night, so that would compare against
    last night and report nothing. It defaults instead to the instant the most
    recent filing was ingested, so the endpoint answers the question FR-22 is
    named for: what did the latest filing change? `since_basis` tells the caller
    which rule produced the pivot, so the UI never has to guess.
    """
    issuer = await get_issuer_by_ticker(session, ticker)
    if issuer is None:
        return None

    since_accession: str | None = None
    if since is None:
        pivot = await latest_filing_pivot(session, issuer.cik)
        if pivot is None:
            # Company exists but has no ingested filing — nothing to pivot on.
            return CompanyChangesOut(
                cik=issuer.cik, ticker=issuer.ticker, name=issuer.name,
                since="", since_basis="latest_filing",
                comparison_state="no_prior_state",
            )
        since, since_accession = pivot
        basis = "latest_filing"
    else:
        basis = "explicit"

    diff = await diff_company_since(session, issuer.ticker, since)
    if diff is None:  # unreachable — issuer was resolved above
        return None

    if diff.no_prior_state:
        state = "no_prior_state"
    elif diff.has_changes:
        state = "changes"
    else:
        state = "no_change"

    return CompanyChangesOut(
        cik=diff.cik,
        ticker=diff.ticker,
        name=diff.name,
        since=since.isoformat(),
        since_basis=basis,
        since_accession=since_accession,
        comparison_state=state,
        run_changes=[
            RunChangeOut(
                model=rd.model,
                fiscal_year=rd.fiscal_year,
                kinds=[k.value for k in rd.kinds],
                prior_accession_number=rd.prior_accession_number,
                current_accession_number=rd.current_accession_number,
                prior_aggregate=_f(rd.prior_aggregate),
                current_aggregate=_f(rd.current_aggregate),
                prior_band_label=rd.prior_band_label,
                current_band_label=rd.current_band_label,
                prior_applicability=rd.prior_applicability,
                current_applicability=rd.current_applicability,
                version_caveat=rd.version_caveat,
                signal_changes=[
                    SignalChangeOut(
                        kind=sc.kind.value,
                        signal_key=sc.signal_key,
                        prior_status=sc.prior_status,
                        current_status=sc.current_status,
                        prior_value=_f(sc.prior_value),
                        current_value=_f(sc.current_value),
                        prior_band_label=sc.prior_band_label,
                        current_band_label=sc.current_band_label,
                    )
                    for sc in rd.signal_changes
                ],
                fact_changes=[
                    FactChangeOut(
                        kind=fc.kind.value,
                        signal_key=fc.signal_key,
                        canonical_concept=fc.canonical_concept,
                        prior_value=_f(fc.prior_value),
                        current_value=_f(fc.current_value),
                        prior_provenance=_change_provenance(fc.prior_provenance),
                        current_provenance=_change_provenance(fc.current_provenance),
                    )
                    for fc in rd.fact_changes
                ],
            )
            for rd in diff.run_diffs
        ],
        data_quality_changes=[
            DataQualityChangeOut(
                kind=dq.kind.value,
                issue_type=dq.issue_type,
                status=dq.status,
                raised_by=dq.raised_by,
                accession_number=dq.accession_number,
                detail=dq.detail,
            )
            for dq in diff.data_quality_changes
        ],
    )
