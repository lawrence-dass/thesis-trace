"""Story 2.2 — Altman Z-Score (FR-4; AD-11, AD-14, AD-16, AD-20)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.models import Applicability, ScoreResult, SignalStatus
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.market_prices import upsert_fye_close
from raw_store.repository import persist_company_facts
from scoring.runner import score_altman
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


async def _prepare(db_session, *, is_financial=False, capital_intensive=False, with_price=True) -> str:
    parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
    await persist_company_facts(
        db_session, parsed, ticker="SHOP",
        is_financial_sector=is_financial, is_capital_intensive=capital_intensive,
    )
    await seed_concept_mappings(db_session)
    await canonicalize_issuer(db_session, parsed.cik)
    if with_price:
        await upsert_fye_close(db_session, issuer_cik=parsed.cik, price_date=date(2024, 12, 31), close_price=106.20)
    return parsed.cik


@requires_db
async def test_altman_computes_five_components_and_band(db_session) -> None:
    cik = await _prepare(db_session)
    run = await score_altman(db_session, cik, 2024)

    results = (await db_session.execute(select(ScoreResult).where(ScoreResult.score_run_id == run.id))).scalars().all()
    keys = {r.signal_key for r in results}
    assert keys == {
        "x1_working_capital", "x2_retained_earnings", "x3_ebit",
        "x4_market_value_equity", "x5_sales",
    }
    assert all(r.status == SignalStatus.pass_ for r in results)
    # Synthetic values make MVE >> liabilities -> a large, clearly-Safe Z.
    assert run.aggregate_value is not None and run.aggregate_value > 2.99
    assert run.applicability == Applicability.computed
    band = next(r.band_label for r in results if r.band_label)
    assert band == "Safe"


@requires_db
async def test_altman_excluded_for_financial_sector(db_session) -> None:
    cik = await _prepare(db_session, is_financial=True)
    run = await score_altman(db_session, cik, 2024)
    assert run.applicability == Applicability.excluded_out_of_scope
    assert run.aggregate_value is None
    results = (await db_session.execute(select(ScoreResult).where(ScoreResult.score_run_id == run.id))).scalars().all()
    assert all(r.status == SignalStatus.insufficient_data for r in results)


@requires_db
async def test_altman_caveat_for_capital_intensive(db_session) -> None:
    cik = await _prepare(db_session, capital_intensive=True)
    run = await score_altman(db_session, cik, 2024)
    assert run.applicability == Applicability.computed_with_caveat
    assert run.aggregate_value is not None


@requires_db
async def test_altman_insufficient_without_market_price(db_session) -> None:
    cik = await _prepare(db_session, with_price=False)
    run = await score_altman(db_session, cik, 2024)
    # No price -> X4 insufficient -> no aggregate Z (AD-16), but not excluded.
    assert run.aggregate_value is None
    assert run.applicability == Applicability.computed
    x4 = (
        await db_session.execute(
            select(ScoreResult).where(
                ScoreResult.score_run_id == run.id, ScoreResult.signal_key == "x4_market_value_equity"
            )
        )
    ).scalars().one()
    assert x4.status == SignalStatus.insufficient_data
