"""Structured diff between two points in a company's score history (FR-22).

Read-only per AD-1: this module queries materialized rows and nothing else. It
imports nothing from `scoring` or `formulas` — deliberately, and the constraint
is load-bearing rather than stylistic. A diff that recomputed a score would
report a *formula* change as if it were a *filing* change, and would drift from
what the overview page actually shows the moment a spec version moved. Every
value here is a value the pipeline already stored.

Supersession (AD-6) is the only history: a new run for
(issuer, model, fiscal_year) marks the prior one superseded rather than mutating
it, so "what was current at time T" is recoverable without a mutable
previous-value column.

WHY THE PIVOT IS A TIMESTAMP, NOT THE SUPERSESSION CHAIN
--------------------------------------------------------
`pipeline/run.py` is a *daily* cron that rescores every scoreable year
unconditionally, so a fresh run supersedes the prior one every night whether or
not anything changed. Walking one link back down the chain would therefore
almost always compare against last night and report nothing. The meaningful
question is "what changed since I last looked", so the engine pins a `since`
timestamp and selects, per (model, fiscal_year), the run that was current at
that instant.
"""

from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

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
    SignalStatus,
)


class ChangeKind(str, enum.Enum):
    """What kind of movement a change represents.

    `coverage_gained`/`coverage_lost` are deliberately NOT directional quality
    judgements. A signal going insufficient_data -> a real value means the data
    arrived, not that the company improved; the reverse means we lost an input,
    not that the company declined. Collapsing either into an ordinary value
    change would let the UI draw an arrow that asserts something the filing
    never said.
    """

    band_change = "band_change"
    aggregate_change = "aggregate_change"
    signal_status_change = "signal_status_change"
    signal_value_change = "signal_value_change"
    coverage_gained = "coverage_gained"
    coverage_lost = "coverage_lost"
    fact_change = "fact_change"
    applicability_change = "applicability_change"
    scored_year_added = "scored_year_added"
    data_quality_opened = "data_quality_opened"
    data_quality_closed = "data_quality_closed"


@dataclass(frozen=True)
class Provenance:
    """Where one endpoint of a change came from."""

    accession_number: str | None
    canonical_concept: str | None = None
    fiscal_year: int | None = None
    period_end: str | None = None
    source_filing_form: str | None = None
    derivation: str | None = None


@dataclass(frozen=True)
class SignalChange:
    kind: ChangeKind
    signal_key: str
    prior_status: str | None
    current_status: str | None
    prior_value: Decimal | None
    current_value: Decimal | None
    prior_band_label: str | None = None
    current_band_label: str | None = None


@dataclass(frozen=True)
class FactChange:
    """A canonical input behind a signal now resolves to a different fact."""

    kind: ChangeKind
    signal_key: str
    canonical_concept: str
    prior_value: Decimal | None
    current_value: Decimal | None
    prior_provenance: Provenance | None
    current_provenance: Provenance | None


@dataclass(frozen=True)
class DataQualityChange:
    kind: ChangeKind
    issue_type: str
    status: str
    raised_by: str
    accession_number: str | None
    detail: dict | None


@dataclass
class RunDiff:
    """All movement for one (model, fiscal_year) between the two endpoints."""

    model: str
    fiscal_year: int
    prior_run_id: str | None
    current_run_id: str
    prior_computed_at: datetime | None
    current_computed_at: datetime
    prior_accession_number: str | None
    current_accession_number: str
    prior_aggregate: Decimal | None = None
    current_aggregate: Decimal | None = None
    prior_band_label: str | None = None
    current_band_label: str | None = None
    prior_applicability: str | None = None
    current_applicability: str | None = None
    kinds: list[ChangeKind] = field(default_factory=list)
    signal_changes: list[SignalChange] = field(default_factory=list)
    fact_changes: list[FactChange] = field(default_factory=list)
    version_caveat: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.kinds)


@dataclass
class CompanyDiff:
    cik: str
    ticker: str
    name: str
    since: datetime
    #: True when the company has no run predating `since`, so there is nothing
    #: to compare against. Distinct from "compared, found nothing" — the API
    #: layer must not render the two identically.
    no_prior_state: bool = False
    run_diffs: list[RunDiff] = field(default_factory=list)
    data_quality_changes: list[DataQualityChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.run_diffs or self.data_quality_changes)


def _run_band_label(results: list[ScoreResult]) -> str | None:
    """The run's headline band.

    Mirrors `api/repository.get_company_overview` exactly — first non-null
    `band_label` over results ordered by `signal_key` — so the diff reports the
    same band the overview page displays. `test_diff_engine.py` pins the two
    against each other; if the overview's rule changes, that test fails rather
    than the two silently disagreeing.
    """
    for r in sorted(results, key=lambda x: x.signal_key):
        if r.band_label:
            return r.band_label
    return None


def _provenance(fact: CanonicalFact | None, form_type: str | None) -> Provenance | None:
    if fact is None:
        return None
    return Provenance(
        accession_number=fact.accession_number,
        canonical_concept=fact.canonical_concept,
        fiscal_year=fact.fiscal_year,
        period_end=fact.period_end.isoformat() if fact.period_end else None,
        source_filing_form=form_type,
        derivation=fact.derivation,
    )


async def _runs_current_at(
    session: AsyncSession, cik: str, at: datetime
) -> dict[tuple[str, int], ScoreRun]:
    """The run that was current for each (model, fiscal_year) at instant `at`.

    DISTINCT ON keeps this one query rather than dragging back every historical
    run — the daily cron accumulates one row per model/year/night, so an
    unfiltered fetch grows without bound.
    """
    rows = (
        await session.execute(
            select(ScoreRun)
            .where(ScoreRun.issuer_cik == cik, ScoreRun.computed_at <= at)
            .order_by(ScoreRun.model, ScoreRun.fiscal_year, ScoreRun.computed_at.desc())
            .distinct(ScoreRun.model, ScoreRun.fiscal_year)
        )
    ).scalars().all()
    return {(r.model.value, r.fiscal_year): r for r in rows}


async def _current_runs(session: AsyncSession, cik: str) -> dict[tuple[str, int], ScoreRun]:
    rows = (
        await session.execute(
            select(ScoreRun).where(
                ScoreRun.issuer_cik == cik, ScoreRun.superseded.is_(False)
            )
        )
    ).scalars().all()
    return {(r.model.value, r.fiscal_year): r for r in rows}


async def _results_by_run(
    session: AsyncSession, run_ids: list
) -> dict[object, list[ScoreResult]]:
    if not run_ids:
        return {}
    rows = (
        await session.execute(
            select(ScoreResult).where(ScoreResult.score_run_id.in_(run_ids))
        )
    ).scalars().all()
    out: dict[object, list[ScoreResult]] = defaultdict(list)
    for r in rows:
        out[r.score_run_id].append(r)
    return out


async def _facts_by_run(
    session: AsyncSession, run_ids: list
) -> dict[object, dict[str, tuple[CanonicalFact, str | None]]]:
    """Canonical facts behind each run's inputs, keyed by run then signal_key.

    A signal can consume several facts (Beneish's indices span two years); they
    are keyed by `signal_key` + `canonical_concept` so a two-year input does not
    overwrite itself.
    """
    if not run_ids:
        return {}
    rows = (
        await session.execute(
            select(ScoreInput.score_run_id, ScoreInput.signal_key, CanonicalFact, Filing.form_type)
            .join(CanonicalFact, ScoreInput.canonical_fact_id == CanonicalFact.id)
            .join(Filing, Filing.accession_number == CanonicalFact.accession_number)
            .where(ScoreInput.score_run_id.in_(run_ids))
        )
    ).all()
    out: dict[object, dict[str, tuple[CanonicalFact, str | None]]] = defaultdict(dict)
    for run_id, signal_key, fact, form_type in rows:
        out[run_id][f"{signal_key}|{fact.canonical_concept}|{fact.fiscal_year}"] = (fact, form_type)
    return out


def _classify_signal(prior: ScoreResult | None, current: ScoreResult | None) -> SignalChange | None:
    """Compare one signal across the two endpoints.

    Coverage transitions are checked BEFORE value/status equality so that
    insufficient_data <-> value never falls through into a directional
    "status changed" reading.
    """
    if prior is None or current is None:
        return None

    p_insufficient = prior.status == SignalStatus.insufficient_data
    c_insufficient = current.status == SignalStatus.insufficient_data

    if p_insufficient and not c_insufficient:
        kind = ChangeKind.coverage_gained
    elif c_insufficient and not p_insufficient:
        kind = ChangeKind.coverage_lost
    elif prior.status != current.status:
        kind = ChangeKind.signal_status_change
    elif prior.band_label != current.band_label:
        kind = ChangeKind.band_change
    elif prior.value != current.value:
        kind = ChangeKind.signal_value_change
    else:
        return None

    return SignalChange(
        kind=kind,
        signal_key=current.signal_key,
        prior_status=prior.status.value,
        current_status=current.status.value,
        prior_value=prior.value,
        current_value=current.value,
        prior_band_label=prior.band_label,
        current_band_label=current.band_label,
    )


def _mapping_versions(facts: dict[str, tuple[CanonicalFact, str | None]]) -> set[str]:
    """Concept-mapping versions behind a run's inputs.

    `mapping_version` is stamped on `canonical_facts`, not on `score_runs` — a
    run has no single one, so this collects the set actually consumed. A run
    spanning two versions is possible and is worth surfacing rather than
    flattening to one.
    """
    return {fact.mapping_version for fact, _form in facts.values() if fact.mapping_version}


def _version_caveat(
    prior: ScoreRun,
    current: ScoreRun,
    prior_mappings: set[str],
    current_mappings: set[str],
) -> str | None:
    """Flag when a change may reflect OUR rule change rather than a filing change.

    Not cosmetic: if the formula spec or the concept mapping moved between the
    two endpoints, a moved number may be entirely our doing. Presenting that as
    news about the company would be the engine asserting something the filing
    did not say. Both versions matter and they move independently — MAPPING_VERSION
    bumps on a real mapping rule change (see `mappings/specs/registry.yaml`),
    formula_version on a spec change, and either can move a number on its own.
    """
    parts = []
    if prior.formula_version != current.formula_version:
        parts.append(f"formula_version {prior.formula_version} -> {current.formula_version}")
    if prior_mappings and current_mappings and prior_mappings != current_mappings:
        parts.append(
            f"mapping_version {'+'.join(sorted(prior_mappings))} -> "
            f"{'+'.join(sorted(current_mappings))}"
        )
    if not parts:
        return None
    return (
        "Comparison spans a rule change (" + "; ".join(parts) + "), so a difference here may "
        "reflect a change in how ThesisTrace computes this score rather than a change in the "
        "company's filings."
    )


async def latest_filing_pivot(session: AsyncSession, cik: str) -> tuple[datetime, str] | None:
    """When the most recent filing was ingested, and which one it was.

    The default pivot for FR-22, and the reason is in the FR's own name: the
    question "latest-filing change detection" asks what THE NEW FILING changed,
    so the natural comparison point is the instant before it landed. Runs
    computed at or before this timestamp reflect the pre-filing state.

    Deliberately NOT "the immediately superseded run" — the daily cron makes
    that last night, which is almost never what a reader means. See the module
    docstring.
    """
    row = (
        await session.execute(
            select(Filing.created_at, Filing.accession_number)
            .where(Filing.issuer_cik == cik, Filing.created_at.is_not(None))
            .order_by(Filing.created_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return row[0], row[1]


async def diff_company_since(
    session: AsyncSession, ticker: str, since: datetime
) -> CompanyDiff | None:
    """Structured diff of a company's stored scores between `since` and now.

    Returns None when the ticker is not in the universe. A company that exists
    but has no run predating `since` returns a CompanyDiff with
    `no_prior_state=True` — the caller must keep that distinct from an empty
    diff, which means "compared, nothing moved".
    """
    issuer = (
        await session.execute(select(Issuer).where(Issuer.ticker == ticker.upper()))
    ).scalars().first()
    if issuer is None:
        return None

    current = await _current_runs(session, issuer.cik)
    prior = await _runs_current_at(session, issuer.cik, since)

    diff = CompanyDiff(
        cik=issuer.cik, ticker=issuer.ticker, name=issuer.name, since=since
    )
    if not prior:
        diff.no_prior_state = True
        return diff

    all_ids = [r.id for r in current.values()] + [r.id for r in prior.values()]
    results_by_run = await _results_by_run(session, all_ids)
    facts_by_run = await _facts_by_run(session, all_ids)

    for key in sorted(current):
        model, fiscal_year = key
        cur_run = current[key]
        prior_run = prior.get(key)

        # A (model, fiscal_year) with no counterpart at `since` is a newly
        # scored year — a new filing was ingested. Reported as its own kind
        # rather than as a change from nothing.
        if prior_run is None:
            cur_results = results_by_run.get(cur_run.id, [])
            diff.run_diffs.append(
                RunDiff(
                    model=model,
                    fiscal_year=fiscal_year,
                    prior_run_id=None,
                    current_run_id=str(cur_run.id),
                    prior_computed_at=None,
                    current_computed_at=cur_run.computed_at,
                    prior_accession_number=None,
                    current_accession_number=cur_run.accession_number,
                    current_aggregate=cur_run.aggregate_value,
                    current_band_label=_run_band_label(cur_results),
                    current_applicability=cur_run.applicability.value,
                    kinds=[ChangeKind.scored_year_added],
                )
            )
            continue

        if prior_run.id == cur_run.id:
            continue  # unchanged since `since` — same row is still current

        prior_results = results_by_run.get(prior_run.id, [])
        cur_results = results_by_run.get(cur_run.id, [])
        prior_band = _run_band_label(prior_results)
        cur_band = _run_band_label(cur_results)
        prior_facts = facts_by_run.get(prior_run.id, {})
        cur_facts = facts_by_run.get(cur_run.id, {})

        rd = RunDiff(
            model=model,
            fiscal_year=fiscal_year,
            prior_run_id=str(prior_run.id),
            current_run_id=str(cur_run.id),
            prior_computed_at=prior_run.computed_at,
            current_computed_at=cur_run.computed_at,
            prior_accession_number=prior_run.accession_number,
            current_accession_number=cur_run.accession_number,
            prior_aggregate=prior_run.aggregate_value,
            current_aggregate=cur_run.aggregate_value,
            prior_band_label=prior_band,
            current_band_label=cur_band,
            prior_applicability=prior_run.applicability.value,
            current_applicability=cur_run.applicability.value,
            version_caveat=_version_caveat(
                prior_run, cur_run, _mapping_versions(prior_facts), _mapping_versions(cur_facts)
            ),
        )

        # Band first, and kept separate from the aggregate: crossing Grey ->
        # Distress is a different event from the Z-score moving within Grey,
        # and the UI has to be able to tell them apart (FR-22).
        if prior_band != cur_band:
            rd.kinds.append(ChangeKind.band_change)
        if prior_run.aggregate_value != cur_run.aggregate_value:
            rd.kinds.append(ChangeKind.aggregate_change)
        if prior_run.applicability != cur_run.applicability:
            rd.kinds.append(ChangeKind.applicability_change)

        prior_by_key = {r.signal_key: r for r in prior_results}
        cur_by_key = {r.signal_key: r for r in cur_results}
        for signal_key in sorted(set(prior_by_key) | set(cur_by_key)):
            change = _classify_signal(prior_by_key.get(signal_key), cur_by_key.get(signal_key))
            if change is not None:
                rd.signal_changes.append(change)
                if change.kind not in rd.kinds:
                    rd.kinds.append(change.kind)

        for fact_key in sorted(set(prior_facts) | set(cur_facts)):
            p = prior_facts.get(fact_key)
            c = cur_facts.get(fact_key)
            p_fact = p[0] if p else None
            c_fact = c[0] if c else None
            if p_fact is not None and c_fact is not None and p_fact.value == c_fact.value:
                continue
            if p_fact is None and c_fact is None:
                continue
            signal_key, concept = fact_key.split("|")[0], fact_key.split("|")[1]
            rd.fact_changes.append(
                FactChange(
                    kind=ChangeKind.fact_change,
                    signal_key=signal_key,
                    canonical_concept=concept,
                    prior_value=p_fact.value if p_fact else None,
                    current_value=c_fact.value if c_fact else None,
                    prior_provenance=_provenance(p_fact, p[1] if p else None),
                    current_provenance=_provenance(c_fact, c[1] if c else None),
                )
            )
        if rd.fact_changes and ChangeKind.fact_change not in rd.kinds:
            rd.kinds.append(ChangeKind.fact_change)

        if rd.has_changes:
            diff.run_diffs.append(rd)

    diff.data_quality_changes = await _data_quality_changes(session, issuer.cik, since)
    return diff


async def _data_quality_changes(
    session: AsyncSession, cik: str, since: datetime
) -> list[DataQualityChange]:
    """Data-quality rows opened or closed since `since`.

    STATED LIMITATION: `data_quality_issues` rows are mutable (AD-17 gives them
    a status and an `updated_at`), so unlike score runs they carry no history.
    Transitions are therefore inferred from timestamps, not reconstructed: a row
    created before `since` and now resolved/dismissed with a later `updated_at`
    is reported closed, but if it were resolved and then reopened between the
    two points, only the net current state is visible. Reporting the inference
    honestly is better than implying a history the table cannot support.
    """
    rows = (
        await session.execute(
            select(DataQualityIssue, Filing.issuer_cik)
            .join(Filing, Filing.accession_number == DataQualityIssue.accession_number)
            .where(Filing.issuer_cik == cik)
        )
    ).all()

    changes: list[DataQualityChange] = []
    for dq, _cik in rows:
        opened = dq.created_at is not None and dq.created_at > since
        closed = (
            dq.status in (IssueStatus.resolved, IssueStatus.dismissed)
            and dq.updated_at is not None
            and dq.updated_at > since
            and not opened
        )
        if not (opened or closed):
            continue
        changes.append(
            DataQualityChange(
                kind=ChangeKind.data_quality_opened if opened else ChangeKind.data_quality_closed,
                issue_type=dq.issue_type,
                status=dq.status.value,
                raised_by=dq.raised_by,
                accession_number=dq.accession_number,
                detail=dq.detail,
            )
        )
    return changes
