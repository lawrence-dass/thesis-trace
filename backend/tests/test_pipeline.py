"""Story 1.10 — pipeline orchestration + universe (AD-1, AD-13; D6)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.models import (
    CanonicalFact,
    DataQualityIssue,
    Filing,
    IssueStatus,
    Model,
    RawFact,
    ScoreResult,
    ScoreRun,
)
from pipeline.run import run_issuer, scoreable_years
from pipeline.universe import PHASE1_UNIVERSE
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


def test_universe_covers_both_reporting_regimes() -> None:
    """D6's four us-gaap filers, plus D8's IFRS filers (Canada-first)."""
    tickers = {e.ticker for e in PHASE1_UNIVERSE}
    assert {"SHOP", "CP", "QSR", "OTEX"} <= tickers, "D6 universe must not shrink"
    assert "CCJ" in tickers, "D8 added at least one 40-F/ifrs-full filer"
    shop = next(e for e in PHASE1_UNIVERSE if e.ticker == "SHOP")
    assert shop.cik == "0001594805"
    # CP and Cameco are both capital-intensive (Altman caveat, Epic 2 / D6).
    assert next(e for e in PHASE1_UNIVERSE if e.ticker == "CP").capital_intensive is True
    # Every entry carries a confirmed, zero-padded CIK — none left as None.
    assert all(e.cik and len(e.cik) == 10 for e in PHASE1_UNIVERSE)
    # No financial-sector filers: Beneish/Altman would be out of scope (D6).
    assert not any(e.is_financial_sector for e in PHASE1_UNIVERSE)


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


# --- D8: 40-F / ifrs-full regime, end to end on real Cameco EDGAR data ---

IFRS_FIXTURE = Path(__file__).parent / "fixtures" / "cameco_company_facts.json"


def test_universe_includes_the_ifrs_filer() -> None:
    ccj = next(e for e in PHASE1_UNIVERSE if e.ticker == "CCJ")
    assert ccj.cik == "0001009001"
    assert ccj.is_financial_sector is False  # Beneish/Altman remain in scope
    assert ccj.capital_intensive is True  # mining -> Altman caveat, as with CP


@requires_db
async def test_ifrs_filer_scores_end_to_end(db_session) -> None:
    """Real 40-F/ifrs-full data flows ingest -> canonicalize -> validate -> score.

    Cameco resolves 17 of 18 canonical concepts from directly-filed tags; the
    18th (total_liabilities) comes from the existing assets-minus-equity identity
    derivation, which is taxonomy-blind because it works on canonical concepts.
    """
    payload = json.loads(IFRS_FIXTURE.read_text())
    summary = await run_issuer(db_session, payload, ticker="CCJ", is_capital_intensive=True)

    assert summary["cik"] == "0001009001"
    assert summary["scored_years"], "no scoreable years resolved from the 40-F payload"

    # The three EDGAR-only models must resolve (no market price supplied here,
    # so Altman is legitimately absent - same as the us-gaap fixtures).
    runs = (
        await db_session.execute(select(ScoreRun).where(ScoreRun.issuer_cik == "0001009001"))
    ).scalars().all()
    assert {r.model for r in runs} >= {Model.piotroski, Model.sloan, Model.beneish}

    # Facts really came from the IFRS taxonomy, not an accidental us-gaap path.
    taxonomies = (
        await db_session.execute(
            select(RawFact.taxonomy).join(Filing, Filing.accession_number == RawFact.accession_number)
            .where(Filing.issuer_cik == "0001009001").distinct()
        )
    ).scalars().all()
    assert "ifrs-full" in taxonomies

    # And the filings really are 40-F.
    forms = (
        await db_session.execute(
            select(Filing.form_type).where(Filing.issuer_cik == "0001009001").distinct()
        )
    ).scalars().all()
    assert all(f.startswith("40-F") for f in forms), forms


@requires_db
async def test_ifrs_beneish_resolves_a_real_value(db_session) -> None:
    """Beneish must produce an actual M-score for Cameco, not insufficient_data.

    This is the claim that justified D8: coverage varies per FILER, not per
    taxonomy. Cameco files a by-function AdministrativeExpense line, so SGAI
    resolves - unlike Suncor, which reports expenses by nature under IAS 1.
    """
    payload = json.loads(IFRS_FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="CCJ", is_capital_intensive=True)

    beneish = (
        await db_session.execute(
            select(ScoreRun).where(
                ScoreRun.issuer_cik == "0001009001",
                ScoreRun.model == Model.beneish,
                ScoreRun.superseded.is_(False),
            )
        )
    ).scalars().all()
    assert beneish, "no Beneish run at all"
    resolved = [r for r in beneish if r.aggregate_value is not None]
    assert resolved, (
        "Beneish resolved no M-score for Cameco; expected at least one year "
        f"(runs: {[(r.fiscal_year, r.applicability, r.aggregate_value) for r in beneish]})"
    )


@requires_db
async def test_beneish_gmi_explodes_when_gross_margin_approaches_zero(db_session) -> None:
    """Characterization test for a REAL model limitation, not a mapping bug.

    Cameco FY2021: gross profit fell to $1.934M on $1.475bn revenue (0.13% margin,
    down from 5.91%) after the Cigar Lake production suspension - costs stayed
    level while revenue fell. GMI is gross_margin(t-1)/gross_margin(t), so a
    near-zero denominator makes it explode: 0.0591/0.00131 = 45.1, and with
    Beneish's 0.528 coefficient that alone contributes ~+23.8, pushing M to
    +20.84 against a -1.78 threshold.

    Every input is a correctly-mapped, directly-filed value and the arithmetic is
    right - so the pipeline is behaving as specified. What is wrong is the
    INTERPRETATION: the UI would label this "Manipulation risk flagged" when the
    real story is a collapsed-margin year, not manipulation. Beneish's model was
    calibrated on firms with normal margins and this input is outside that range.

    This is taxonomy-independent - it could happen to any filer under us-gaap
    too - so it is recorded here rather than treated as an IFRS issue. Whether
    the Verdict needs an out-of-calibration guard is a methodology decision for
    the product owner, and deliberately NOT invented here: silently clamping or
    suppressing the value would be ThesisTrace originating methodology, which the
    deterministic/LLM boundary forbids just as much for our own code as for an LLM.
    """
    payload = json.loads(IFRS_FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="CCJ", is_capital_intensive=True)

    run = (
        await db_session.execute(
            select(ScoreRun).where(
                ScoreRun.issuer_cik == "0001009001",
                ScoreRun.model == Model.beneish,
                ScoreRun.fiscal_year == 2021,
                ScoreRun.superseded.is_(False),
            )
        )
    ).scalars().first()
    assert run is not None and run.aggregate_value is not None

    gmi = (
        await db_session.execute(
            select(ScoreResult).where(
                ScoreResult.score_run_id == run.id, ScoreResult.signal_key == "gmi"
            )
        )
    ).scalars().one()

    # GMI is far outside any plausible calibration range, and drives the aggregate.
    assert float(gmi.value) > 10, f"expected an exploded GMI, got {gmi.value}"
    assert float(run.aggregate_value) > 0, "expected the outlier to dominate M"
