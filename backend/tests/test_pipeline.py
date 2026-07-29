"""Story 1.10 — pipeline orchestration + universe (AD-1, AD-13; D6)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, DataQualityIssue, IssueStatus, Model, ScoreRun
from pipeline.run import run_issuer, scoreable_years
from pipeline.universe import PHASE1_UNIVERSE
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


def test_universe_is_phase1_four() -> None:
    tickers = {e.ticker for e in PHASE1_UNIVERSE}
    assert tickers == {"SHOP", "CP", "QSR", "OTEX"}  # D6
    shop = next(e for e in PHASE1_UNIVERSE if e.ticker == "SHOP")
    assert shop.cik == "0001594805"
    # CP is flagged capital-intensive (Altman caveat in Epic 2).
    assert next(e for e in PHASE1_UNIVERSE if e.ticker == "CP").capital_intensive is True


@requires_db
async def test_run_issuer_scores_all_scoreable_years(db_session) -> None:
    payload = json.loads(FIXTURE.read_text())
    summary = await run_issuer(db_session, payload, ticker="SHOP")
    # Fixture has FY2023 + FY2024, so only FY2024 has a prior year -> scoreable.
    assert summary["scored_years"] == [2024]

    years = await scoreable_years(db_session, summary["cik"])
    assert years == [2024]

    runs = (
        await db_session.execute(select(ScoreRun).where(ScoreRun.issuer_cik == summary["cik"]))
    ).scalars().all()
    models = {r.model for r in runs}
    # No market price provided -> Altman not scored; the three EDGAR-only models are.
    assert models == {Model.piotroski, Model.sloan, Model.beneish}


@requires_db
async def test_run_issuer_is_idempotent_scores_current(db_session) -> None:
    payload = json.loads(FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="SHOP")
    await run_issuer(db_session, payload, ticker="SHOP")

    # Two runs per model exist (append-only), but only one current per model (AD-6).
    runs = (await db_session.execute(select(ScoreRun).where(ScoreRun.model == Model.piotroski))).scalars().all()
    current = [r for r in runs if not r.superseded]
    assert len(current) == 1


@requires_db
async def test_run_issuer_runs_the_validate_stage(db_session) -> None:
    """The pipeline must actually invoke validation between canonicalize and score."""
    payload = json.loads(FIXTURE.read_text())
    summary = await run_issuer(db_session, payload, ticker="SHOP")
    # Clean fixture -> stage ran and found nothing, rather than never running.
    assert summary["validation"] == {"issues_raised": 0, "issues_existing": 0}


@requires_db
async def test_pipeline_raises_validation_issue_and_does_not_duplicate(db_session) -> None:
    """A violation is flagged once, and a re-run does not append a second row.

    The cron runs daily over the same canonical facts; without an idempotency
    guard a persistent violation would accumulate one row per night and the read
    API would surface the same warning N times.
    """
    payload = json.loads(FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="SHOP")

    # Corrupt a canonical fact so current_assets > total_assets for FY2024.
    ca = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "current_assets",
                CanonicalFact.fiscal_year == 2024,
            )
        )
    ).scalars().one()
    ca.value = 99_000_000_000
    await db_session.flush()

    second = await run_issuer(db_session, payload, ticker="SHOP")
    assert second["validation"]["issues_raised"] == 1

    third = await run_issuer(db_session, payload, ticker="SHOP")
    assert third["validation"]["issues_raised"] == 0
    assert third["validation"]["issues_existing"] == 1

    issues = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.raised_by == "validation")
        )
    ).scalars().all()
    assert len(issues) == 1
    assert issues[0].issue_type == "identity_violation:current_assets_gt_total_assets"
    assert issues[0].detail["fiscal_year"] == 2024


@requires_db
async def test_validation_does_not_resurrect_a_dismissed_issue(db_session) -> None:
    """Dismissing a warning must stick across nightly re-runs."""
    payload = json.loads(FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="SHOP")

    ca = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "current_assets",
                CanonicalFact.fiscal_year == 2024,
            )
        )
    ).scalars().one()
    ca.value = 99_000_000_000
    await db_session.flush()
    await run_issuer(db_session, payload, ticker="SHOP")

    issue = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.raised_by == "validation")
        )
    ).scalars().one()
    issue.status = IssueStatus.dismissed
    await db_session.flush()

    await run_issuer(db_session, payload, ticker="SHOP")

    issues = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.raised_by == "validation")
        )
    ).scalars().all()
    assert len(issues) == 1
    assert issues[0].status is IssueStatus.dismissed
