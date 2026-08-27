"""Read-only queries against materialized Postgres (AD-1, AD-10).

Never computes a score, never calls EDGAR/Tiingo. Assembles the current
(non-superseded) score runs for an issuer with per-signal results and the
provenance of each input.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_, select
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
    FundamentalsFigureOut,
    FundamentalsOut,
    LensScoreOut,
    MaturityBucketOut,
    MaturityProfileOut,
    NearTermDebtShareOut,
    Provenance,
    RewardRiskItemOut,
    TrajectoryOut,
    RunChangeOut,
    SignalChangeOut,
    SignalOut,
    VerdictItem,
    ReverseDcfOperandOut,
    ReverseDcfOut,
    SensitivityCellOut,
    WaterfallBarOut,
)
from canonicalization.mappings import DERIVATION_RULES, MAPPING_VERSION
from debt.engine import DENOMINATOR_CONCEPT, NUMERATOR_CONCEPT, shares_for_facts
from debt.profile import PROFILE_CONCEPTS, profile_for_facts
from fundamentals.engine import FUNDAMENTALS_CONCEPTS, FundamentalsFigure, fundamentals_for_facts
from raw_store.market_prices import resolve_fye_price
from valuation.overview import DCF_CONCEPTS
from valuation.store import load_reverse_dcf
from diff.engine import diff_company_since, latest_filing_pivot
from trajectory.engine import trajectories_for_scores
from rewards_risks.engine import rewards_risks_for_overview

_DERIVATION_OPERANDS = {rule.rule: rule.operands for rule in DERIVATION_RULES}
_DERIVATION_OPERATIONS = {rule.rule: rule.operation for rule in DERIVATION_RULES}


def _append_reverse_dcf_fact_operand(
    operands: list[ReverseDcfOperandOut],
    facts_by_name: dict[str, CanonicalFact],
    name: str,
    fiscal_year: int,
    seen: set[str],
) -> None:
    """Append one canonical operand and recursively expose its dependencies.

    CanonicalFact keeps an accession as an internal provenance anchor even for a
    derived value. That anchor is useful for the scoring audit trail, but it must
    not be emitted as though the filing contained the derived line item (AD-19).
    The public reverse-DCF surface therefore carries the actual spec operands and
    only filed leaves carry an accession.
    """
    if name in seen:
        return
    fact = facts_by_name.get(name)
    if fact is None or fact.fiscal_year != fiscal_year:
        return
    seen.add(name)
    dependencies = (
        _DERIVATION_OPERANDS.get(fact.derivation, ()) if fact.derivation is not None else ()
    )
    operands.append(
        ReverseDcfOperandOut(
            name=name,
            value=float(Decimal(str(fact.value))),
            accession_number=fact.accession_number if fact.derivation is None else None,
            derived_from=list(dependencies),
            derivation=fact.derivation,
            operation=_DERIVATION_OPERATIONS.get(fact.derivation),
            unit=fact.unit,
            period_end=fact.period_end.isoformat() if fact.period_end else None,
        )
    )
    for dependency in dependencies:
        _append_reverse_dcf_fact_operand(operands, facts_by_name, dependency, fiscal_year, seen)


def _fundamentals_figure_out(
    figure: FundamentalsFigure, *, derived_concept: str, anchor: CanonicalFact
) -> FundamentalsFigureOut:
    """One fundamentals headline figure or waterfall bar (Story 10.4).

    A filed figure cites its own fact directly. A derived one (gross profit
    from revenue minus cost, or the catch-all "other" bucket) cites `anchor` —
    always the revenue fact, which is present whenever this module produces
    anything at all — as the provenance root, the same "correct root, no such
    line item" reasoning `CanonicalFact.derivation` already documents for a
    canonicalization-time derivation (AD-19). An absent figure carries its
    reason instead of a citation.
    """
    if figure.value is None:
        return FundamentalsFigureOut(value=None, reason=figure.reason)
    if figure.fact is not None:
        f = figure.fact
        provenance = Provenance(
            accession_number=f.accession_number,
            canonical_concept=f.canonical_concept,
            fiscal_year=f.fiscal_year,
            period_end=f.period_end.isoformat() if f.period_end else None,
            derivation=None,
        )
    else:
        provenance = Provenance(
            accession_number=anchor.accession_number,
            canonical_concept=derived_concept,
            fiscal_year=anchor.fiscal_year,
            period_end=anchor.period_end.isoformat() if anchor.period_end else None,
            derivation=figure.derivation,
        )
    return FundamentalsFigureOut(value=_f(figure.value), provenance=provenance)

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


async def _results_for_runs(
    session: AsyncSession, run_ids: list
) -> dict[uuid.UUID, list[ScoreResult]]:
    """Every run's signal rows, in ONE query rather than one per run.

    Part of the Track P batching. The overview previously issued a query per run —
    80 of them for OTEX's 20 fiscal years across four models.
    """
    if not run_ids:
        return {}
    rows = (
        await session.execute(
            select(ScoreResult)
            .where(ScoreResult.score_run_id.in_(run_ids))
            .order_by(ScoreResult.score_run_id, ScoreResult.signal_key)
        )
    ).scalars().all()
    grouped: dict[uuid.UUID, list[ScoreResult]] = {}
    for row in rows:
        grouped.setdefault(row.score_run_id, []).append(row)
    return grouped


async def _provenance_for_runs(
    session: AsyncSession, run_ids: list
) -> dict[tuple, list[Provenance]]:
    """Every signal's provenance for every run, in ONE query.

    THE EXPENSIVE HALF of the old N+1: this was a query per (run, signal), which is
    where 400 of OTEX's 486 went. The join is unchanged — only the `where` widens
    from one run to all of them, and the grouping key moves into the projection.

    Ordered explicitly. The per-signal version had no ORDER BY at all, so its row
    order was whatever Postgres happened to return; grouping without one would make
    the ordering depend on the plan for a much larger scan. Verified against the
    live store that the emitted provenance lists are byte-identical either way.
    """
    if not run_ids:
        return {}
    rows = (
        await session.execute(
            select(ScoreInput.score_run_id, ScoreInput.signal_key, CanonicalFact, Filing.form_type)
            .join(ScoreInput, ScoreInput.canonical_fact_id == CanonicalFact.id)
            .join(Filing, Filing.accession_number == CanonicalFact.accession_number)
            .where(ScoreInput.score_run_id.in_(run_ids))
            .order_by(
                ScoreInput.score_run_id,
                ScoreInput.signal_key,
                # Newest fiscal year first, matching how the runs themselves are
                # ordered and — verified against the live store — what the
                # unordered per-signal query already emitted. A year-over-year
                # signal cites two facts, and reversing them would silently
                # relabel which one a reader takes as "current".
                CanonicalFact.fiscal_year.desc(),
                CanonicalFact.canonical_concept,
            )
        )
    ).all()
    grouped: dict[tuple, list[Provenance]] = {}
    for run_id, signal_key, cf, form in rows:
        grouped.setdefault((run_id, signal_key), []).append(
            Provenance(
                accession_number=cf.accession_number,
                canonical_concept=cf.canonical_concept,
                fiscal_year=cf.fiscal_year,
                period_end=cf.period_end.isoformat() if cf.period_end else None,
                source_filing_form=form,
                derivation=cf.derivation,
            )
        )
    return grouped


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

    # TRACK P: two bounded queries instead of one per run and one per signal.
    # The overview issued 486 queries for OTEX (20 fiscal years x 4 models, with
    # each run's signals fetched individually and each signal's provenance fetched
    # individually) and the cost grew linearly with history — 16 queries per fiscal
    # year, forever. Both loads are now single `IN` queries resolved in memory.
    run_ids = [run.id for run in runs]
    results_by_run = await _results_for_runs(session, run_ids)
    provenance_by_signal = await _provenance_for_runs(session, run_ids)

    scores: list[LensScoreOut] = []
    for run in runs:
        results = results_by_run.get(run.id, [])
        signals = [
            SignalOut(
                signal_key=r.signal_key,
                status=r.status.value,
                value=float(r.value) if r.value is not None else None,
                band_label=r.band_label,
                provenance=provenance_by_signal.get((run.id, r.signal_key), []),
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

    # ONE fetch serving both debt presentation rules — the near-term share (Story
    # 5.6) and the maturity profile (Story 5.7). They read disjoint concepts out of
    # the same rows, so a second query would double the read for nothing. Each rule
    # is then a pure computation over the already-fetched facts, the same shape as
    # the trajectory pass above, so neither can become an N+1 (AD-1).
    #
    # Both are ThesisTrace presentation rules: they stand beside the scores and
    # never adjust one.
    debt_facts = (
        await session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == issuer.cik,
                CanonicalFact.mapping_version == MAPPING_VERSION,
                CanonicalFact.canonical_concept.in_(
                    (
                        NUMERATOR_CONCEPT,
                        DENOMINATOR_CONCEPT,
                        *PROFILE_CONCEPTS,
                        *DCF_CONCEPTS,
                        *FUNDAMENTALS_CONCEPTS,
                    )
                ),
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

    # Year-by-year maturity profile (Story 5.7). Folded into the SAME query as the
    # near-term share above rather than issuing a second one — both read
    # canonical_facts for this issuer at the current mapping version, so one pass
    # serves both (AD-1).
    #
    # Empty for most of the universe, and that is not a gap: the profile is
    # supplementary disclosure detail, not a signal, so the frontend renders
    # NOTHING rather than an insufficient_data affordance.
    debt_maturity_profile = [
        MaturityProfileOut(
            fiscal_year=p.fiscal_year,
            buckets=[
                MaturityBucketOut(
                    canonical_concept=b.canonical_concept,
                    label=b.label,
                    value=float(b.value),
                    accession_number=b.accession_number,
                    fiscal_year=b.fiscal_year,
                )
                for b in p.buckets
            ],
            truncated=p.truncated,
            truncation_message=p.truncation_message,
            unit=p.unit,
            attribution=p.attribution,
            spec_version=p.spec_version,
        )
        for _, p in sorted(profile_for_facts(debt_facts).items(), reverse=True)
    ]

    # Fundamentals summary and earnings waterfall (Story 10.4). Same single
    # fact pass as the debt cards above (AD-1) — `debt_facts` was widened with
    # FUNDAMENTALS_CONCEPTS for exactly this. The one extra query below is a
    # single persisted market-price lookup for market value, mirroring the
    # reverse-DCF market-cap resolution but scoped to fundamentals' OWN latest
    # complete fiscal year — not necessarily the same year reverse DCF resolves,
    # which additionally requires cash-flow and debt operands.
    fundamentals = None
    fund = fundamentals_for_facts(debt_facts)
    if fund is not None:
        anchor = fund.revenue.fact  # always filed when `fund` is not None
        waterfall = [
            WaterfallBarOut(
                stage=bar.stage,
                bar_type=bar.bar_type,
                figure=_fundamentals_figure_out(bar.figure, derived_concept=bar.stage, anchor=anchor),
            )
            for bar in fund.waterfall
        ]

        market_value = FundamentalsFigureOut(value=None, reason="No shares outstanding on file for this fiscal year")
        shares_fact = next(
            (
                f
                for f in debt_facts
                if f.canonical_concept == "shares_outstanding" and f.fiscal_year == fund.fiscal_year
            ),
            None,
        )
        if shares_fact is not None:
            shares_value = Decimal(str(shares_fact.value))
            if shares_value <= 0:
                market_value = FundamentalsFigureOut(
                    value=None, reason="Shares outstanding is zero or negative for this fiscal year"
                )
            else:
                price_resolution = await resolve_fye_price(
                    session,
                    issuer_cik=issuer.cik,
                    fiscal_year_end=shares_fact.period_end,
                    reporting_currency=anchor.unit,
                )
                if price_resolution.price is not None:
                    market_value = FundamentalsFigureOut(
                        value=_f(shares_value * price_resolution.price),
                        as_of=price_resolution.price_date.isoformat() if price_resolution.price_date else None,
                        source=price_resolution.price_source,
                    )
                else:
                    market_value = FundamentalsFigureOut(
                        value=None, reason=price_resolution.reason or "No market price available for this fiscal year"
                    )

        fundamentals = FundamentalsOut(
            fiscal_year=fund.fiscal_year,
            revenue=_fundamentals_figure_out(fund.revenue, derived_concept="revenue", anchor=anchor),
            earnings=_fundamentals_figure_out(fund.earnings, derived_concept="net_income", anchor=anchor),
            market_value=market_value,
            waterfall=waterfall,
        )

    # Reverse DCF (Epic 6). READS THE MATERIALIZED ROW — it does not solve (AD-1).
    # This previously called `reverse_dcf_for_issuer` here, so every page load
    # re-solved the DCF and all 35 sensitivity cells; `pipeline/run.py` now computes
    # and upserts it, and this is two bounded queries.
    #
    # The operand assembly below still projects `debt_facts` (widened by
    # DCF_CONCEPTS above) — those rows are already in memory from the single pass,
    # so building the evidence list stays projection rather than computation.
    #
    # LATEST RESOLVABLE YEAR ONLY, not a per-year series: the grid is 35 solves, a
    # different cost class from the ratio-per-year the debt cards compute.
    reverse_dcf = None
    dcf = await load_reverse_dcf(session, issuer.cik)
    if dcf is not None:
        base, grid, (cagr, cagr_from, cagr_to) = dcf
        facts_by_name = {
            fact.canonical_concept: fact
            for fact in debt_facts
            if fact.fiscal_year == base.fiscal_year
        }
        operands: list[ReverseDcfOperandOut] = []
        seen_operands: set[str] = set()
        reporting_currency = next(
            (
                facts_by_name[concept].unit.strip().upper()
                for concept in (
                    "total_assets",
                    "cash_and_equivalents",
                    "cash",
                    "revenue",
                    "cash_from_operations",
                    "capex",
                    "total_debt",
                )
                if concept in facts_by_name and facts_by_name[concept].unit
            ),
            None,
        )
        if base.free_cash_flow is not None:
            cash_from_operations_fact = facts_by_name.get("cash_from_operations")
            capex_fact = facts_by_name.get("capex")
            operands.append(
                ReverseDcfOperandOut(
                    name="free_cash_flow",
                    value=float(base.free_cash_flow),
                    derived_from=["cash_from_operations", "capex"],
                    derivation="reverse_dcf_v1.free_cash_flow",
                    operation="subtract",
                    unit=(cash_from_operations_fact or capex_fact).unit
                    if cash_from_operations_fact or capex_fact
                    else None,
                    period_end=(cash_from_operations_fact or capex_fact).period_end.isoformat()
                    if cash_from_operations_fact or capex_fact
                    else None,
                )
            )
            _append_reverse_dcf_fact_operand(
                operands, facts_by_name, "cash_from_operations", base.fiscal_year, seen_operands
            )
            _append_reverse_dcf_fact_operand(
                operands, facts_by_name, "capex", base.fiscal_year, seen_operands
            )
        else:
            # Preserve whichever filed leaves existed even when the aggregate is
            # insufficient; hiding available evidence behind a generic reason makes
            # an honest failure impossible to audit.
            for name in ("cash_from_operations", "capex"):
                _append_reverse_dcf_fact_operand(
                    operands, facts_by_name, name, base.fiscal_year, seen_operands
                )
        if base.market_cap is not None:
            operands.append(
                ReverseDcfOperandOut(
                    name="market_cap",
                    value=float(base.market_cap),
                    derived_from=["shares_outstanding", "market_price"],
                    derivation="reverse_dcf_v1.market_cap",
                    operation="multiply",
                    unit=reporting_currency,
                    observed_on=base.market_price_date.isoformat()
                    if base.market_price_date
                    else None,
                    source=base.market_price_source or "persisted market_prices",
                )
            )
            shares_fact = facts_by_name.get("shares_outstanding")
            shares_value = (
                Decimal(str(shares_fact.value)) if shares_fact is not None else None
            )
            if shares_value is not None and shares_value > 0:
                # This is the converted price actually used by market cap. Keeping
                # it in the response makes the market-cap multiplication
                # independently reproducible for both USD and CAD filers.
                market_price = base.market_cap / shares_value
                operands.append(
                    ReverseDcfOperandOut(
                        name="market_price",
                        value=float(market_price),
                        unit=reporting_currency,
                        source=base.market_price_source or "persisted market_prices",
                        observed_on=base.market_price_date.isoformat()
                        if base.market_price_date
                        else None,
                        conversion_rate=float(base.fx_rate) if base.fx_rate is not None else None,
                        conversion_rate_date=base.fx_rate_date.isoformat()
                        if base.fx_rate_date
                        else None,
                        conversion_rate_source=base.fx_rate_source,
                    )
                )
        _append_reverse_dcf_fact_operand(
            operands, facts_by_name, "shares_outstanding", base.fiscal_year, seen_operands
        )

        # These values may be filed directly or computed by a versioned canonical
        # derivation. In the latter case the helper emits the rule's real leaves,
        # never the internal accession anchor (AD-19).
        for name, value in (
            ("total_debt", base.total_debt),
            ("cash_and_equivalents", base.cash_and_equivalents),
        ):
            if value is None:
                continue
            _append_reverse_dcf_fact_operand(
                operands, facts_by_name, name, base.fiscal_year, seen_operands
            )
        if base.enterprise_value is not None:
            operands.append(
                ReverseDcfOperandOut(
                    name="enterprise_value",
                    value=float(base.enterprise_value),
                    derived_from=["market_cap", "total_debt", "cash_and_equivalents"],
                    derivation="reverse_dcf_v1.enterprise_value",
                    operation="add_then_subtract",
                    unit=reporting_currency,
                )
            )
        reverse_dcf = ReverseDcfOut(
            fiscal_year=base.fiscal_year,
            implied_growth=float(base.implied_growth) if base.implied_growth is not None else None,
            insufficient_data=base.insufficient_data,
            reason=base.reason,
            range_low=float(grid.low) if grid is not None and grid.low is not None else None,
            range_high=float(grid.high) if grid is not None and grid.high is not None else None,
            sensitivity=[
                SensitivityCellOut(
                    discount_rate=float(c.discount_rate),
                    terminal_growth=float(c.terminal_growth),
                    implied_growth=float(c.implied_growth) if c.implied_growth is not None else None,
                    reason=c.reason,
                )
                for c in (grid.cells if grid is not None else ())
            ],
            resolved_cells=grid.resolved_cells if grid is not None else 0,
            total_cells=grid.total_cells if grid is not None else 0,
            discount_rate=float(base.discount_rate),
            terminal_growth=float(base.terminal_growth),
            horizon_years=base.horizon_years,
            operands=operands,
            historical_revenue_cagr=float(cagr) if cagr is not None else None,
            historical_from_fiscal_year=cagr_from,
            historical_to_fiscal_year=cagr_to,
            caveats=list(base.caveats),
            attribution=base.attribution,
            spec_version=base.spec_version,
        )

    # Open data-quality warnings for this issuer (AD-17, FR-8) — never hidden.
    # Most rows point at a filing; keep canonical-fact-only issues visible too,
    # since both foreign keys are nullable on the quality-issue table.
    dq_rows = (
        await session.execute(
            select(DataQualityIssue, Filing.issuer_cik)
            .outerjoin(Filing, Filing.accession_number == DataQualityIssue.accession_number)
            .outerjoin(CanonicalFact, CanonicalFact.id == DataQualityIssue.canonical_fact_id)
            .where(
                or_(Filing.issuer_cik == issuer.cik, CanonicalFact.issuer_cik == issuer.cik),
                DataQualityIssue.status == IssueStatus.needs_review,
            )
            .order_by(DataQualityIssue.issue_type, DataQualityIssue.accession_number, DataQualityIssue.id)
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

    # Rewards and risks (Story 10.3). Computed from `verdict` and
    # `data_quality`, both already built above — no extra query, same shape
    # as the trajectory pass (AD-1).
    rewards_risks = [
        RewardRiskItemOut(
            kind=item.kind.value,
            text=item.text,
            section=item.section,
            model=item.model,
            fiscal_year=item.fiscal_year,
            accession_number=item.accession_number,
            attribution=item.attribution,
            spec_version=item.spec_version,
        )
        for item in rewards_risks_for_overview(verdict, data_quality)
    ]

    return CompanyOverviewOut(
        cik=issuer.cik,
        ticker=issuer.ticker,
        name=issuer.name,
        lenses_live=lenses_live,
        lenses_pending=PENDING_LENSES,
        verdict=verdict,
        scores=scores,
        near_term_debt_share=near_term_debt_share,
        debt_maturity_profile=debt_maturity_profile,
        reverse_dcf=reverse_dcf,
        data_quality=data_quality,
        rewards_risks=rewards_risks,
        fundamentals=fundamentals,
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
