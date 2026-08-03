"""D8 step 6 — BCE and Suncor on real 40-F/ifrs-full data.

Cameco proved the happy path (4 of 4 models from directly-filed tags). These two
prove the DEGRADED paths, which is the point of adding them: coverage varies per
filer, not per taxonomy, and a gap must surface as insufficient_data rather than as
a substituted or guessed number.

Every expectation below was confirmed live against data.sec.gov on 2026-08-02, and
the fixtures are trimmed copies of those real payloads.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, Model, ScoreRun
from canonicalization.mappings import MAPPING_VERSION
from pipeline.run import run_issuer
from pipeline.universe import PHASE1_UNIVERSE
from tests.conftest import requires_db

BCE_FIXTURE = Path(__file__).parent / "fixtures" / "bce_company_facts.json"
SUNCOR_FIXTURE = Path(__file__).parent / "fixtures" / "suncor_company_facts.json"
BCE_CIK = "0000718940"
SUNCOR_CIK = "0000311337"


def _concepts(facts: list[CanonicalFact]) -> set[str]:
    return {f.canonical_concept for f in facts}


async def _canonical(db_session, cik: str) -> list[CanonicalFact]:
    return list(
        (
            await db_session.execute(
                select(CanonicalFact).where(
                    CanonicalFact.issuer_cik == cik,
                    CanonicalFact.mapping_version == MAPPING_VERSION,
                )
            )
        ).scalars()
    )


def test_universe_includes_both_new_ifrs_filers() -> None:
    by_ticker = {e.ticker: e for e in PHASE1_UNIVERSE}
    assert by_ticker["BCE"].cik == BCE_CIK
    assert by_ticker["SU"].cik == SUNCOR_CIK
    # Both carry the D6 Altman caveat for the same reason CP does — heavy PP&E.
    assert by_ticker["BCE"].capital_intensive is True
    assert by_ticker["SU"].capital_intensive is True
    assert by_ticker["BCE"].is_financial_sector is False
    assert by_ticker["SU"].is_financial_sector is False


# --- BCE ---------------------------------------------------------------------


@requires_db
async def test_bce_scores_end_to_end(db_session) -> None:
    payload = json.loads(BCE_FIXTURE.read_text())
    summary = await run_issuer(db_session, payload, ticker="BCE", is_capital_intensive=True)

    assert summary["cik"] == BCE_CIK
    assert summary["scored_years"], "no scoreable years resolved from BCE's 40-F payload"

    runs = (
        await db_session.execute(select(ScoreRun).where(ScoreRun.issuer_cik == BCE_CIK))
    ).scalars().all()
    assert {r.model for r in runs} >= {Model.piotroski, Model.sloan}


@requires_db
async def test_bce_ppe_spans_all_nine_years_via_the_rightofuse_fallback(db_session) -> None:
    """The regression this fallback exists for.

    BCE's plain `PropertyPlantAndEquipment` tag stops after FY2022 and
    `PropertyPlantAndEquipmentIncludingRightofuseAssets` carries FY2023-2025
    (confirmed live 2026-08-02). Without the ifrs-full_v2 fallback BCE silently
    loses 3 of its 9 years and Beneish's AQI/DEPI degrade for exactly the recent
    years a user is most likely to look at — the same shape as CP's mid-history
    switch under us-gaap, which was a real bug.
    """
    payload = json.loads(BCE_FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="BCE", is_capital_intensive=True)

    years = sorted(
        f.fiscal_year for f in await _canonical(db_session, BCE_CIK) if f.canonical_concept == "ppe_net"
    )
    assert years, "BCE resolved no ppe_net at all"
    assert max(years) >= 2023, f"ppe_net stops at {max(years)} — the fallback did not fire"
    assert len(years) >= 8, f"expected near-full coverage, got {years}"


@requires_db
async def test_bce_has_no_sga_and_beneish_does_not_invent_one(db_session) -> None:
    """IAS 1 by-nature presentation: BCE tags no SG&A line at all. SGAI must stay
    unresolvable rather than borrow a proxy — the same treatment as CP's missing
    COGS under us-gaap."""
    payload = json.loads(BCE_FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="BCE", is_capital_intensive=True)

    assert "sga" not in _concepts(await _canonical(db_session, BCE_CIK))


# --- Suncor ------------------------------------------------------------------


@requires_db
async def test_suncor_scores_end_to_end(db_session) -> None:
    payload = json.loads(SUNCOR_FIXTURE.read_text())
    summary = await run_issuer(db_session, payload, ticker="SU", is_capital_intensive=True)

    assert summary["cik"] == SUNCOR_CIK
    assert summary["scored_years"], "no scoreable years resolved from Suncor's 40-F payload"

    runs = (
        await db_session.execute(select(ScoreRun).where(ScoreRun.issuer_cik == SUNCOR_CIK))
    ).scalars().all()
    assert Model.sloan in {r.model for r in runs}


@requires_db
async def test_suncor_total_liabilities_is_derived_not_filed(db_session) -> None:
    """Suncor tags no `Liabilities` total (confirmed live 2026-08-02). The
    taxonomy-blind assets-minus-equity identity covers it, and the resulting fact
    must be marked derived so it never wears a filed-line citation."""
    payload = json.loads(SUNCOR_FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="SU", is_capital_intensive=True)

    facts = [
        f for f in await _canonical(db_session, SUNCOR_CIK) if f.canonical_concept == "total_liabilities"
    ]
    assert facts, "expected a derived total_liabilities for Suncor"
    assert all(f.derivation == "assets_minus_equity" for f in facts), [
        (f.fiscal_year, f.derivation) for f in facts
    ]


@requires_db
async def test_suncor_has_no_retained_earnings_so_altman_cannot_resolve(db_session) -> None:
    """The honest hard case. Suncor tags NO retained-earnings concept anywhere in
    its 40-F payload, and Altman's X2 is retained earnings / total assets. There is
    no defensible substitute — accumulated profit is not disclosed as a tagged fact
    — so the score must be absent rather than computed from a stand-in."""
    payload = json.loads(SUNCOR_FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="SU", is_capital_intensive=True)

    assert "retained_earnings" not in _concepts(await _canonical(db_session, SUNCOR_CIK))

    altman = (
        await db_session.execute(
            select(ScoreRun).where(ScoreRun.issuer_cik == SUNCOR_CIK, ScoreRun.model == Model.altman)
        )
    ).scalars().all()
    assert all(r.aggregate_value is None for r in altman), [
        (r.fiscal_year, r.aggregate_value) for r in altman
    ]


@requires_db
async def test_suncor_resolves_its_by_nature_variant_tags(db_session) -> None:
    """Four concepts reach Suncor ONLY through a priority-1 by-nature variant tag
    (verified live 2026-08-02: it tags none of the primaries). This pins that the
    fallbacks actually fire — if a future spec edit drops one as "unused", Suncor
    loses the concept outright.

    These variants are NOT like-for-like with a by-function filer's — pre-interest
    operating cash flow, impairment-inclusive D&A, inventories-only cost of sales.
    That mismatch is documented in ifrs-full_v2.yaml's footer and is a pending
    product decision, not a mapping error.
    """
    payload = json.loads(SUNCOR_FIXTURE.read_text())
    await run_issuer(db_session, payload, ticker="SU", is_capital_intensive=True)

    resolved = _concepts(await _canonical(db_session, SUNCOR_CIK))
    for concept in ("cash_from_operations", "cogs", "depreciation", "receivables"):
        assert concept in resolved, f"{concept} lost — its by-nature fallback stopped firing"


# --- both --------------------------------------------------------------------


@requires_db
async def test_neither_filer_fabricates_an_ebit(db_session) -> None:
    """Neither BCE nor Suncor tags an operating-profit line — IFRS does not mandate
    one (Cameco voluntarily tags it, which is why Cameco reaches 4 of 4). Until the
    D8 consequence-3 decision is made in a versioned formula spec, `ebit` stays
    unresolved for both. `ProfitLossBeforeTax + InterestExpense` and
    `ProfitLossBeforeTax - FinanceIncomeCost` are both defensible and give different
    numbers, so choosing one silently inside canonicalization would be ThesisTrace
    originating a methodology.
    """
    for fixture, ticker, cik in (
        (BCE_FIXTURE, "BCE", BCE_CIK),
        (SUNCOR_FIXTURE, "SU", SUNCOR_CIK),
    ):
        payload = json.loads(fixture.read_text())
        await run_issuer(db_session, payload, ticker=ticker, is_capital_intensive=True)
        assert "ebit" not in _concepts(await _canonical(db_session, cik)), ticker
