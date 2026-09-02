"""Stories 1.6 & 1.7 — Piotroski + Sloan scoring (FR-3, FR-7; AD-6, AD-16, AD-18)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.models import CanonicalFact, Filing, Issuer, Model, ScoreResult, ScoreRun, SignalStatus
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import MAPPING_VERSION, seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from scoring.runner import _canonical_fact_for_year, score_piotroski, score_sloan
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
    # With the full fixture these now compute (Epic 2 completed the inputs).
    assert results["leverage_decreasing"].status == SignalStatus.pass_
    assert results["gross_margin_increasing"].status == SignalStatus.pass_
    assert results["asset_turnover_increasing"].status == SignalStatus.pass_
    # shares_not_diluted: 1.29B > 1.27B -> dilution -> fail.
    assert results["shares_not_diluted"].status == SignalStatus.fail
    # No signal is insufficient now that all inputs are present.
    assert all(r.status != SignalStatus.insufficient_data for r in results.values())
    # Aggregate = count of pass signals.
    passes = sum(1 for r in results.values() if r.status == SignalStatus.pass_)
    assert run.aggregate_value == passes
    assert run.aggregate_value == 7


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


@requires_db
async def test_score_run_representative_fact_uses_the_current_mapping_version(db_session) -> None:
    """A mapping-version rebuild keeps old and new canonical rows current by
    design; the score-run provenance root must select the version the scorer
    actually loaded."""
    cik = "0000000044"
    old_accession = "0000000044-24-000001"
    new_accession = "0000000044-25-000001"
    db_session.add(Issuer(cik=cik, ticker="SYN3", name="Synthetic Mapping Filer"))
    db_session.add_all(
        [
            Filing(
                accession_number=old_accession,
                issuer_cik=cik,
                form_type="10-K",
                filing_date=date(2024, 2, 15),
                fiscal_year=2023,
                fiscal_year_end=date(2023, 12, 31),
            ),
            Filing(
                accession_number=new_accession,
                issuer_cik=cik,
                form_type="10-K",
                filing_date=date(2025, 2, 15),
                fiscal_year=2023,
                fiscal_year_end=date(2023, 12, 31),
            ),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            CanonicalFact(
                issuer_cik=cik,
                accession_number=old_accession,
                canonical_concept="total_assets",
                fiscal_year=2023,
                period_end=date(2023, 12, 31),
                value=100,
                unit="USD",
                mapping_version="concepts_v9",
            ),
            CanonicalFact(
                issuer_cik=cik,
                accession_number=new_accession,
                canonical_concept="total_assets",
                fiscal_year=2023,
                period_end=date(2023, 12, 31),
                value=200,
                unit="USD",
                mapping_version=MAPPING_VERSION,
            ),
        ]
    )
    await db_session.flush()

    fact = await _canonical_fact_for_year(db_session, cik, 2023)
    assert fact is not None
    assert fact.mapping_version == MAPPING_VERSION
    assert fact.value == 200
