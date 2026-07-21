"""Story 1.10 — pipeline orchestration + universe (AD-1, AD-13; D6)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.models import Model, ScoreRun
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
    assert models == {Model.piotroski, Model.sloan}


@requires_db
async def test_run_issuer_is_idempotent_scores_current(db_session) -> None:
    payload = json.loads(FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="SHOP")
    await run_issuer(db_session, payload, ticker="SHOP")

    # Two runs per model exist (append-only), but only one current per model (AD-6).
    runs = (await db_session.execute(select(ScoreRun).where(ScoreRun.model == Model.piotroski))).scalars().all()
    current = [r for r in runs if not r.superseded]
    assert len(current) == 1
