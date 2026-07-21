"""Story 1.9 — golden-dataset regression harness (SM-1, NFR-1).

Asserts computed scores match the golden values for every ACTIVE company, and
that the active + pending sets together cover the whole Phase-1 universe so no
company is silently dropped. Golden values are placeholders pending OQ1
verification (see phase1_golden.yaml); the harness machinery is what's real here,
and it already accepts the remaining companies + Altman/Beneish (Epic 2).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import yaml

from app.models import Model, SignalStatus
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from scoring.runner import score_piotroski, score_sloan
from sqlalchemy import select
from app.models import ScoreResult
from tests.conftest import requires_db

GOLDEN = yaml.safe_load((Path(__file__).parent / "golden" / "phase1_golden.yaml").read_text())
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_universe_fully_partitioned() -> None:
    """No company silently dropped: active + pending == the declared universe."""
    listed = {c["ticker"] for c in GOLDEN["companies"]}
    assert listed == set(GOLDEN["universe"])
    pending = [c["ticker"] for c in GOLDEN["companies"] if c["status"] == "pending_fixture"]
    if pending:
        warnings.warn(f"Golden coverage pending for: {', '.join(pending)} (need fixtures + OQ1 values).")


async def _run_pipeline(db_session, fixture_name: str, fiscal_year: int) -> str:
    parsed = parse_company_facts(json.loads((FIXTURES_DIR / fixture_name).read_text()))
    await persist_company_facts(db_session, parsed, ticker=parsed.entity_name[:8])
    await seed_concept_mappings(db_session)
    await canonicalize_issuer(db_session, parsed.cik)
    await score_piotroski(db_session, parsed.cik, fiscal_year)
    await score_sloan(db_session, parsed.cik, fiscal_year)
    return parsed.cik


@requires_db
async def test_active_companies_match_golden(db_session) -> None:
    active = [c for c in GOLDEN["companies"] if c["status"] == "active"]
    assert active, "expected at least one active golden company"

    for company in active:
        await _run_pipeline(db_session, company["fixture"], company["fiscal_year"])
        expected = company["expected"]

        # Piotroski F-Score = count of passing signals.
        piotroski_results = (
            await db_session.execute(select(ScoreResult).where(ScoreResult.model == Model.piotroski))
        ).scalars().all()
        f_score = sum(1 for r in piotroski_results if r.status == SignalStatus.pass_)
        assert f_score == expected["piotroski"]["f_score"], f"{company['ticker']} Piotroski"

        # Sloan accruals ratio + band.
        sloan_result = (
            await db_session.execute(select(ScoreResult).where(ScoreResult.model == Model.sloan))
        ).scalars().one()
        assert abs(float(sloan_result.value) - expected["sloan"]["accruals_ratio"]) < 1e-4, f"{company['ticker']} Sloan ratio"
        assert sloan_result.band_label == expected["sloan"]["band"], f"{company['ticker']} Sloan band"
