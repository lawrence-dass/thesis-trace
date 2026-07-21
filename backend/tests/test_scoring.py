"""Stories 1.6 & 1.7 — Piotroski + Sloan scoring (FR-3, FR-7; AD-6, AD-16, AD-18)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from app.models import Model, ScoreResult, ScoreRun, SignalStatus
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from scoring.runner import score_piotroski, score_sloan
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


async def _prepare(db_session) -> str:
    parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
    await persist_company_facts(db_session, parsed, ticker="SHOP")
    await seed_concept_mappings(db_session)
    await canonicalize_issuer(db_session, parsed.cik)
    return parsed.cik


@requires_db
async def test_piotroski_signals_and_tristate(db_session) -> None:
    cik = await _prepare(db_session)
    run = await score_piotroski(db_session, cik, 2024)

    results = {
        r.signal_key: r
        for r in (await db_session.execute(select(ScoreResult).where(ScoreResult.score_run_id == run.id))).scalars()
    }
    # All 9 signals stored individually (FR-3).
    assert len(results) == 9
    # With the fixture: these are computable and pass.
    assert results["roa_positive"].status == SignalStatus.pass_
    assert results["cfo_positive"].status == SignalStatus.pass_
    assert results["roa_increasing"].status == SignalStatus.pass_
    # accruals: CFO/TA (0.1229) > ROA (0.154) is false -> fail.
    assert results["accruals"].status == SignalStatus.fail
    # Concepts absent from the fixture -> insufficient_data, never a defaulted 0 (AD-16).
    assert results["gross_margin_increasing"].status == SignalStatus.insufficient_data
    assert results["leverage_decreasing"].status == SignalStatus.insufficient_data
    # Aggregate = count of pass signals.
    passes = sum(1 for r in results.values() if r.status == SignalStatus.pass_)
    assert run.aggregate_value == passes


@requires_db
async def test_piotroski_supersedes_prior_run(db_session) -> None:
    cik = await _prepare(db_session)
    first = await score_piotroski(db_session, cik, 2024)
    second = await score_piotroski(db_session, cik, 2024)

    await db_session.refresh(first)
    assert first.superseded is True
    assert first.superseded_by == second.id
    assert second.superseded is False
    # Both runs retained (append-only, AD-6).
    total = (await db_session.execute(select(func.count()).select_from(ScoreRun).where(ScoreRun.model == Model.piotroski))).scalar_one()
    assert total == 2


@requires_db
async def test_sloan_ratio_and_band(db_session) -> None:
    cik = await _prepare(db_session)
    run = await score_sloan(db_session, cik, 2024)
    result = (await db_session.execute(select(ScoreResult).where(ScoreResult.score_run_id == run.id))).scalars().one()
    assert result.signal_key == "accruals_ratio"
    # accruals = 2.02B - 1.61B = 0.41B; avg TA = (13.1B + 11.393B)/2 = 12.2465B; ratio ~= 0.033.
    assert result.value is not None
    assert abs(float(result.value) - 0.033479) < 1e-4
    # Below the 0.10 threshold -> low accruals (pass), band label set.
    assert result.status == SignalStatus.pass_
    assert result.band_label == "Low accruals (higher quality)"
