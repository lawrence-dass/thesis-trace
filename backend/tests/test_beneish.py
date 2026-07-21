"""Story 2.3 — Beneish M-Score (FR-6; AD-16, AD-20)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.models import Applicability, ScoreResult, SignalStatus
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from scoring.runner import score_beneish
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"

EIGHT_INDICES = {"dsri", "gmi", "aqi", "sgi", "depi", "sgai", "tata", "lvgi"}


async def _prepare(db_session, *, is_financial=False) -> str:
    parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
    await persist_company_facts(db_session, parsed, ticker="SHOP", is_financial_sector=is_financial)
    await seed_concept_mappings(db_session)
    await canonicalize_issuer(db_session, parsed.cik)
    return parsed.cik


@requires_db
async def test_beneish_eight_indices_and_m_score(db_session) -> None:
    cik = await _prepare(db_session)
    run = await score_beneish(db_session, cik, 2024)

    results = (await db_session.execute(select(ScoreResult).where(ScoreResult.score_run_id == run.id))).scalars().all()
    assert {r.signal_key for r in results} == EIGHT_INDICES
    assert all(r.status == SignalStatus.pass_ for r in results)  # all inputs present in fixture
    assert run.aggregate_value is not None
    assert run.applicability == Applicability.computed
    band = next(r.band_label for r in results if r.band_label)
    assert band in {"Manipulation risk flagged", "No manipulation flag"}


@requires_db
async def test_beneish_excluded_for_financial_sector(db_session) -> None:
    cik = await _prepare(db_session, is_financial=True)
    run = await score_beneish(db_session, cik, 2024)
    assert run.applicability == Applicability.excluded_out_of_scope
    assert run.aggregate_value is None
    results = (await db_session.execute(select(ScoreResult).where(ScoreResult.score_run_id == run.id))).scalars().all()
    assert all(r.status == SignalStatus.insufficient_data for r in results)
