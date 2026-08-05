"""Story 5.2 — score-run diff engine (FR-22; AD-1, AD-6, AD-16, AD-19).

Builds score runs directly rather than through `scoring.runner`, so each test
pins exact values and `computed_at` instants. That independence is the point:
a diff engine verified by running the scorer would only prove the two agree,
not that the diff reports what actually changed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import (
    Applicability,
    CanonicalFact,
    DataQualityIssue,
    Filing,
    IssueStatus,
    Issuer,
    Model,
    ScoreInput,
    ScoreResult,
    ScoreRun,
    SignalStatus,
)
from diff.engine import ChangeKind, diff_company_since
from tests.conftest import requires_db

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)   # prior endpoint
SINCE = datetime(2026, 2, 1, tzinfo=timezone.utc)  # the "last looked" pivot
T1 = datetime(2026, 3, 1, tzinfo=timezone.utc)   # current endpoint

ACC_OLD = "0000000000-24-000001"
ACC_NEW = "0000000000-25-000001"


async def _seed_issuer(session) -> str:
    cik = "0001594805"
    session.add(Issuer(cik=cik, ticker="TEST", name="Test Corp"))
    for acc, fy in ((ACC_OLD, 2024), (ACC_NEW, 2025)):
        session.add(
            Filing(
                accession_number=acc,
                issuer_cik=cik,
                form_type="10-K",
                filing_date=date(fy + 1, 2, 1),
                fiscal_year=fy,
                fiscal_year_end=date(fy, 12, 31),
            )
        )
    await session.flush()
    return cik


async def _add_run(
    session,
    cik: str,
    *,
    model: Model = Model.altman,
    fiscal_year: int = 2024,
    aggregate: Decimal | None = Decimal("2.5"),
    band: str | None = "Grey",
    computed_at: datetime = T0,
    superseded: bool = False,
    formula_version: str = "altman_v1",
    accession: str = ACC_OLD,
    applicability: Applicability = Applicability.computed,
    signals: dict[str, tuple[SignalStatus, Decimal | None]] | None = None,
) -> ScoreRun:
    run = ScoreRun(
        id=uuid.uuid4(),
        issuer_cik=cik,
        model=model,
        fiscal_year=fiscal_year,
        formula_version=formula_version,
        accession_number=accession,
        aggregate_value=aggregate,
        applicability=applicability,
        superseded=superseded,
        computed_at=computed_at,
    )
    session.add(run)
    await session.flush()
    # `_run_band_label` takes the first non-null band over signal_key order, so
    # the band-carrying signal is named to sort first.
    session.add(
        ScoreResult(
            score_run_id=run.id,
            model=model,
            signal_key="aggregate",
            value=aggregate,
            status=SignalStatus.pass_ if aggregate is not None else SignalStatus.insufficient_data,
            band_label=band,
        )
    )
    for key, (status, value) in (signals or {}).items():
        session.add(
            ScoreResult(
                score_run_id=run.id,
                model=model,
                signal_key=key,
                value=value,
                status=status,
                band_label=None,
            )
        )
    await session.flush()
    return run


async def _add_fact_input(
    session, cik: str, run: ScoreRun, *, signal_key: str, concept: str,
    value: Decimal, accession: str, fiscal_year: int = 2024,
    mapping_version: str = "concepts_v5",
) -> CanonicalFact:
    fact = CanonicalFact(
        id=uuid.uuid4(),
        issuer_cik=cik,
        accession_number=accession,
        canonical_concept=concept,
        fiscal_year=fiscal_year,
        period_end=date(fiscal_year, 12, 31),
        value=value,
        unit="USD",
        mapping_version=mapping_version,
    )
    session.add(fact)
    await session.flush()
    session.add(
        ScoreInput(score_run_id=run.id, signal_key=signal_key, canonical_fact_id=fact.id)
    )
    await session.flush()
    return fact


@requires_db
async def test_band_change_is_reported_separately_from_within_band_movement(db_session) -> None:
    """Crossing Grey -> Distress is a different event from moving inside Grey."""
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, aggregate=Decimal("2.5"), band="Grey",
                   computed_at=T0, superseded=True)
    await _add_run(db_session, cik, aggregate=Decimal("1.2"), band="Distress", computed_at=T1)
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    rd = diff.run_diffs[0]
    assert ChangeKind.band_change in rd.kinds
    assert ChangeKind.aggregate_change in rd.kinds
    assert rd.prior_band_label == "Grey"
    assert rd.current_band_label == "Distress"


@requires_db
async def test_within_band_movement_does_not_report_a_band_change(db_session) -> None:
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, aggregate=Decimal("2.5"), band="Grey",
                   computed_at=T0, superseded=True)
    await _add_run(db_session, cik, aggregate=Decimal("2.7"), band="Grey", computed_at=T1)
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    rd = diff.run_diffs[0]
    assert ChangeKind.aggregate_change in rd.kinds
    assert ChangeKind.band_change not in rd.kinds


@requires_db
async def test_insufficient_to_value_is_coverage_gained_not_an_improvement(db_session) -> None:
    """AD-16: data arriving is not the company improving."""
    cik = await _seed_issuer(db_session)
    await _add_run(
        db_session, cik, computed_at=T0, superseded=True,
        signals={"roa": (SignalStatus.insufficient_data, None)},
    )
    await _add_run(
        db_session, cik, computed_at=T1,
        signals={"roa": (SignalStatus.pass_, Decimal("0.12"))},
    )
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    change = next(c for c in diff.run_diffs[0].signal_changes if c.signal_key == "roa")
    assert change.kind is ChangeKind.coverage_gained
    assert change.kind is not ChangeKind.signal_status_change


@requires_db
async def test_value_to_insufficient_is_coverage_lost_not_a_decline(db_session) -> None:
    cik = await _seed_issuer(db_session)
    await _add_run(
        db_session, cik, computed_at=T0, superseded=True,
        signals={"roa": (SignalStatus.pass_, Decimal("0.12"))},
    )
    await _add_run(
        db_session, cik, computed_at=T1,
        signals={"roa": (SignalStatus.insufficient_data, None)},
    )
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    change = next(c for c in diff.run_diffs[0].signal_changes if c.signal_key == "roa")
    assert change.kind is ChangeKind.coverage_lost


@requires_db
async def test_ordinary_pass_to_fail_is_a_status_change(db_session) -> None:
    """The coverage checks must not swallow a genuine pass -> fail."""
    cik = await _seed_issuer(db_session)
    await _add_run(
        db_session, cik, computed_at=T0, superseded=True,
        signals={"roa": (SignalStatus.pass_, Decimal("0.12"))},
    )
    await _add_run(
        db_session, cik, computed_at=T1,
        signals={"roa": (SignalStatus.fail, Decimal("-0.03"))},
    )
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    change = next(c for c in diff.run_diffs[0].signal_changes if c.signal_key == "roa")
    assert change.kind is ChangeKind.signal_status_change


@requires_db
async def test_newly_scored_year_is_its_own_kind(db_session) -> None:
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, fiscal_year=2024, computed_at=T0)
    await _add_run(db_session, cik, fiscal_year=2025, computed_at=T1, accession=ACC_NEW)
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    added = [rd for rd in diff.run_diffs if rd.fiscal_year == 2025]
    assert len(added) == 1
    assert added[0].kinds == [ChangeKind.scored_year_added]
    assert added[0].prior_run_id is None
    # FY2024 was current at `since` and is still the same row — not a change.
    assert not [rd for rd in diff.run_diffs if rd.fiscal_year == 2024]


@requires_db
async def test_no_prior_state_is_distinct_from_an_empty_diff(db_session) -> None:
    """FR-22: 'nothing to compare' must never render as 'nothing changed'."""
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, computed_at=T1)  # only run postdates `since`
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    assert diff.no_prior_state is True
    assert diff.has_changes is False


@requires_db
async def test_unchanged_company_reports_no_changes_but_has_prior_state(db_session) -> None:
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, computed_at=T0)
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    assert diff.no_prior_state is False
    assert diff.has_changes is False


@requires_db
async def test_nightly_rescore_with_identical_values_reports_nothing(db_session) -> None:
    """The daily cron supersedes every night; identical values are not news."""
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, aggregate=Decimal("2.5"), band="Grey",
                   computed_at=T0, superseded=True)
    await _add_run(db_session, cik, aggregate=Decimal("2.5"), band="Grey", computed_at=T1)
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    assert diff.has_changes is False


@requires_db
async def test_formula_version_change_raises_a_caveat(db_session) -> None:
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, aggregate=Decimal("2.5"), formula_version="altman_v1",
                   computed_at=T0, superseded=True)
    await _add_run(db_session, cik, aggregate=Decimal("2.9"), formula_version="altman_v2",
                   computed_at=T1)
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    caveat = diff.run_diffs[0].version_caveat
    assert caveat is not None
    assert "altman_v1 -> altman_v2" in caveat


@requires_db
async def test_mapping_version_change_raises_a_caveat(db_session) -> None:
    """mapping_version lives on canonical_facts, not on the run — still caveated."""
    cik = await _seed_issuer(db_session)
    prior = await _add_run(db_session, cik, aggregate=Decimal("2.5"),
                           computed_at=T0, superseded=True)
    await _add_fact_input(db_session, cik, prior, signal_key="x1", concept="total_assets",
                          value=Decimal("100"), accession=ACC_OLD, mapping_version="concepts_v4")
    current = await _add_run(db_session, cik, aggregate=Decimal("2.9"), computed_at=T1)
    await _add_fact_input(db_session, cik, current, signal_key="x1", concept="total_assets",
                          value=Decimal("100"), accession=ACC_OLD, mapping_version="concepts_v5")
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    caveat = diff.run_diffs[0].version_caveat
    assert caveat is not None
    assert "concepts_v4 -> concepts_v5" in caveat


@requires_db
async def test_fact_change_carries_both_endpoints_with_provenance(db_session) -> None:
    """AD-19: a reported change must be auditable to both source filings.

    The two facts differ by `mapping_version`, which is currently the ONLY way
    a run's canonical inputs can differ at all — see
    `test_restatement_under_one_mapping_version_yields_no_fact_change` for why.
    """
    cik = await _seed_issuer(db_session)
    prior = await _add_run(db_session, cik, computed_at=T0, superseded=True)
    await _add_fact_input(db_session, cik, prior, signal_key="x1", concept="total_assets",
                          value=Decimal("1000"), accession=ACC_OLD,
                          mapping_version="concepts_v4")
    current = await _add_run(db_session, cik, computed_at=T1, accession=ACC_NEW)
    await _add_fact_input(db_session, cik, current, signal_key="x1", concept="total_assets",
                          value=Decimal("1250"), accession=ACC_NEW,
                          mapping_version="concepts_v5")
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    fc = next(f for f in diff.run_diffs[0].fact_changes if f.canonical_concept == "total_assets")
    assert fc.prior_value == Decimal("1000")
    assert fc.current_value == Decimal("1250")
    assert fc.prior_provenance.accession_number == ACC_OLD
    assert fc.current_provenance.accession_number == ACC_NEW
    assert fc.prior_provenance.source_filing_form == "10-K"


@requires_db
async def test_restatement_under_one_mapping_version_yields_no_fact_change(db_session) -> None:
    """Pins a KNOWN GAP in canonicalization, discovered building this engine.

    `canonical_facts` is UNIQUE on (issuer_cik, canonical_concept, fiscal_year,
    mapping_version), and `canonicalize_issuer` skips any key already present
    under the current mapping_version (`canonicalize.py`, "keep the pass
    idempotent"). That guard ignores the accession entirely, so once a fiscal
    year's facts are written from the original 10-K, a later 10-K/A restating
    those figures is skipped and the restated values never reach the canonical
    layer.

    AD-6 and PRD OQ2 say an amendment triggers a new append-only score_run
    "referencing the new canonical_facts" — the run is new, but the facts it
    references are the stale ones. The consequence for THIS engine is that
    `fact_change` is unreachable within a single mapping_version.

    This test asserts the current behaviour so the gap is visible in code rather
    than only in a tracker. When canonicalization learns to supersede facts on
    amendment, this test SHOULD fail — that is the signal to revisit it, not a
    regression. Tracked in sprint-status.yaml as `canonical_facts_amendment_gap`.
    """
    cik = await _seed_issuer(db_session)
    prior = await _add_run(db_session, cik, computed_at=T0, superseded=True)
    await _add_fact_input(db_session, cik, prior, signal_key="x1", concept="total_assets",
                          value=Decimal("1000"), accession=ACC_OLD)
    current = await _add_run(db_session, cik, computed_at=T1, accession=ACC_NEW)

    # The restated fact cannot be inserted under the same mapping_version.
    with pytest.raises(Exception) as excinfo:
        await _add_fact_input(db_session, cik, current, signal_key="x1",
                              concept="total_assets", value=Decimal("1250"),
                              accession=ACC_NEW)
    assert "uq_canonical_facts_key" in str(excinfo.value)


@requires_db
async def test_data_quality_opened_and_closed_are_distinguished(db_session) -> None:
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, computed_at=T0)
    db_session.add(
        DataQualityIssue(
            accession_number=ACC_NEW, issue_type="identity_violation",
            status=IssueStatus.needs_review, raised_by="validation",
            created_at=T1, updated_at=T1,
        )
    )
    db_session.add(
        DataQualityIssue(
            accession_number=ACC_OLD, issue_type="ambiguous_selection",
            status=IssueStatus.resolved, raised_by="canonicalization",
            created_at=T0, updated_at=T1,
        )
    )
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    kinds = {c.issue_type: c.kind for c in diff.data_quality_changes}
    assert kinds["identity_violation"] is ChangeKind.data_quality_opened
    assert kinds["ambiguous_selection"] is ChangeKind.data_quality_closed


@requires_db
async def test_data_quality_untouched_since_the_pivot_is_not_reported(db_session) -> None:
    cik = await _seed_issuer(db_session)
    await _add_run(db_session, cik, computed_at=T0)
    db_session.add(
        DataQualityIssue(
            accession_number=ACC_OLD, issue_type="source_conflict",
            status=IssueStatus.needs_review, raised_by="validation",
            created_at=T0, updated_at=T0,
        )
    )
    await db_session.commit()

    diff = await diff_company_since(db_session, "TEST", SINCE)
    assert diff.data_quality_changes == []


@requires_db
async def test_unknown_ticker_returns_none(db_session) -> None:
    await _seed_issuer(db_session)
    await db_session.commit()
    assert await diff_company_since(db_session, "NOPE", SINCE) is None


@requires_db
async def test_engine_band_matches_what_the_overview_page_shows(db_session) -> None:
    """Pins `_run_band_label` against the repository's own rule.

    Both derive the run's headline band as 'first non-null band_label over
    signal_key order'. If the overview's rule ever changes, this fails rather
    than the diff and the page silently disagreeing about the same run.
    """
    from api.repository import get_company_overview

    cik = await _seed_issuer(db_session)
    await _add_run(
        db_session, cik, model=Model.piotroski, aggregate=Decimal("7"), band="Strong",
        computed_at=T1, signals={"zz_last": (SignalStatus.pass_, Decimal("1"))},
    )
    await db_session.commit()

    overview = await get_company_overview(db_session, "TEST")
    page_band = next(s.band_label for s in overview.scores if s.model == "piotroski")

    from diff.engine import _run_band_label
    from sqlalchemy import select

    run = (await db_session.execute(select(ScoreRun))).scalars().first()
    results = (
        await db_session.execute(select(ScoreResult).where(ScoreResult.score_run_id == run.id))
    ).scalars().all()
    assert _run_band_label(results) == page_band


def test_engine_never_imports_scoring_or_formulas() -> None:
    """AD-1 / FR-22: the diff reads stored values, it never recomputes.

    A structural guard, not a style check. If the engine ever imported the
    scorer, a formula change would surface as a filing change and the diff
    would drift from what the overview page shows.
    """
    from pathlib import Path

    source = (Path(__file__).parent.parent / "diff" / "engine.py").read_text()
    for banned in ("from scoring", "import scoring", "from formulas", "import formulas"):
        assert banned not in source, f"diff/engine.py must not import: {banned}"


def test_coverage_kinds_are_not_directional() -> None:
    """Guards the vocabulary itself against a well-meaning future rename.

    `coverage_gained`/`coverage_lost` must never acquire improvement/decline
    wording — that would assert something the filing did not say.
    """
    for kind in (ChangeKind.coverage_gained, ChangeKind.coverage_lost):
        assert not any(
            word in kind.value for word in ("improve", "decline", "better", "worse", "up", "down")
        )
