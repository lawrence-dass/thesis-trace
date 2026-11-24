"""Beneish GMI's unvalidated-gross-margin guard (ThesisTrace presentation guard).

Beneish defines gross margin as (Sales - COGS) / Sales. That is only a margin when
COGS covers the cost base matching the revenue in the denominator. For a franchisor
like QSR, or a by-nature IFRS filer like Suncor, it does not — a partial cost base
against a full revenue base, from the revenue and cost sides respectively.

The formula stays exactly as Beneish specified. The M-score is annotated, never
altered — the same posture as the out-of-calibration guard alongside it.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.models import Applicability, Model, ScoreRun
from pipeline.run import run_issuer
from tests.conftest import requires_db

FIXTURES = Path(__file__).parent / "fixtures"


async def _beneish_runs(db_session, cik: str) -> list[ScoreRun]:
    return list(
        (
            await db_session.execute(
                select(ScoreRun).where(ScoreRun.issuer_cik == cik, ScoreRun.model == Model.beneish)
            )
        ).scalars()
    )


def _margin_caveats(runs: list[ScoreRun]) -> list[ScoreRun]:
    return [r for r in runs if r.caveat_reason and "gross profit line" in r.caveat_reason]


@requires_db
async def test_zts_beneish_is_flagged_for_an_unvalidated_gross_margin(db_session) -> None:
    """ZTS never files a gross profit line (Story 12.1 finding 2), so its margin is
    unvalidated. QSR was this test's subject until Ops 5: its fixture years now
    resolve no SG&A (see the QSR test below), so it produces no M-score to flag."""
    payload = json.loads((FIXTURES / "zts_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="ZTS")

    runs = await _beneish_runs(db_session, "0001555280")
    resolved = [r for r in runs if r.aggregate_value is not None]
    assert resolved, "ZTS should produce an M-score"

    flagged = _margin_caveats(resolved)
    assert flagged, "ZTS's Beneish should be flagged for an unvalidated gross margin"
    assert all(r.applicability is Applicability.computed_with_caveat for r in flagged)


@requires_db
async def test_the_guard_annotates_without_altering_the_m_score(db_session) -> None:
    """The load-bearing property. A caveat may annotate a score; it must never alter
    one. ZTS's hand-verified golden M-score must survive the guard untouched."""
    payload = json.loads((FIXTURES / "zts_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="ZTS")

    runs = await _beneish_runs(db_session, "0001555280")
    fy2025 = [r for r in runs if r.fiscal_year == 2025 and r.aggregate_value is not None]
    assert fy2025, "expected a resolved FY2025 M-score for ZTS"
    assert _margin_caveats(fy2025), "the guard must have fired on the score it leaves unaltered"
    assert float(fy2025[0].aggregate_value) == -2.447666, "golden M-score changed"


@requires_db
async def test_qsr_beneish_is_insufficient_without_a_whole_sga(db_session) -> None:
    """Ops 5. QSR's fixture years resolve SG&A from nothing: from FY2021 QSR reports
    G&A and advertising as separate lines, and G&A alone is not SG&A (us-gaap_v20).
    Insufficient, never a partial figure (AD-16), until QSR's own story."""
    payload = json.loads((FIXTURES / "qsr_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="QSR")

    runs = await _beneish_runs(db_session, "0001618756")
    assert runs, "QSR's Beneish runs must exist, so their emptiness means something"
    assert all(r.aggregate_value is None for r in runs)


@requires_db
async def test_shop_is_not_flagged_because_it_reports_gross_profit(db_session) -> None:
    """The negative case that keeps the flag meaningful.

    SHOP files a GrossProfit line AND revenue - cogs reproduces it to the dollar, so
    its margin is validated. Note the guard is filer-level on purpose: SHOP's fixture
    carries the tag for FY2024 only, and a year-level test would wrongly flag it.
    """
    payload = json.loads((FIXTURES / "shop_real_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="SHOP")

    runs = await _beneish_runs(db_session, "0001594805")
    assert not _margin_caveats(runs), [(r.fiscal_year, r.caveat_reason) for r in _margin_caveats(runs)]


@requires_db
async def test_otex_is_not_flagged_because_it_reports_gross_profit(db_session) -> None:
    payload = json.loads((FIXTURES / "otex_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="OTEX")

    runs = await _beneish_runs(db_session, "0001002638")
    assert not _margin_caveats(runs), [(r.fiscal_year, r.caveat_reason) for r in _margin_caveats(runs)]


@requires_db
async def test_suncor_beneish_does_not_resolve_at_all(db_session) -> None:
    """Documents why Suncor cannot exercise this guard end to end, so a later reader
    doesn't mistake its absence for a coverage bug: Suncor reports expenses by nature
    and tags no SG&A line, so SGAI never resolves and no M-score is produced. Its
    unvalidated margin is real but never reaches a score."""
    payload = json.loads((FIXTURES / "suncor_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="SU", is_capital_intensive=True)

    runs = await _beneish_runs(db_session, "0000311337")
    assert runs, "expected Beneish runs to exist even though none resolve"
    assert all(r.aggregate_value is None for r in runs)


def test_both_guards_accumulate_rather_than_overwrite() -> None:
    """A run can be both out of calibration and built on an unvalidated margin, and
    one explanation must never silently replace the other.

    No real filer currently hits both (Cameco is out of calibration but reports gross
    profit; QSR has the unvalidated margin but normal indices), so this is exercised
    with constructed facts rather than left untested.
    """
    from decimal import Decimal

    from scoring.beneish import compute_beneish
    from scoring.facts import FactLookup
    from formulas.engine import load_spec

    # Gross margin collapses 10% -> 0.1%, so GMI = 100, far past the spec's bound of
    # 10. gross_profit is deliberately absent, so the margin guard fires as well.
    base = {
        "revenue": 1000, "receivables": 100, "current_assets": 500, "ppe_net": 300,
        "total_assets": 1000, "depreciation": 50, "sga": 100, "current_liabilities": 200,
        "long_term_debt": 300, "net_income": 50, "cash_from_operations": 40,
    }
    values = {(c, y): Decimal(str(v)) for y in (2022, 2023) for c, v in base.items()}
    values[("cogs", 2022)] = Decimal("900")
    values[("cogs", 2023)] = Decimal("999")

    result = compute_beneish(
        FactLookup(values, {}, {}), 2023, load_spec("beneish_v1"), is_financial_sector=False
    )

    assert result.m_score is not None, "expected a resolved M-score"
    assert result.applicability.value == "computed_with_caveat"
    assert "far outside its normal range" in result.caveat_reason, "calibration reason lost"
    assert "gross profit line" in result.caveat_reason, "margin-guard reason lost"
