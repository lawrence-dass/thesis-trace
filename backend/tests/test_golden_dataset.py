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
from datetime import date
from pathlib import Path

import yaml

from app.models import CanonicalFact, Model, ScoreResult, ScoreRun, SignalStatus
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from debt.engine import compute
from ingestion.company_facts import parse_company_facts
from raw_store.fx_rates import upsert_fx_rate
from raw_store.market_prices import upsert_fye_close
from raw_store.repository import persist_company_facts
from scoring.runner import score_altman, score_beneish, score_piotroski, score_sloan
from sqlalchemy import select
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


async def _run_pipeline(db_session, company: dict) -> str:
    fiscal_year = company["fiscal_year"]
    parsed = parse_company_facts(json.loads((FIXTURES_DIR / company["fixture"]).read_text()))
    await persist_company_facts(db_session, parsed, ticker=parsed.entity_name[:8])
    await seed_concept_mappings(db_session)
    await canonicalize_issuer(db_session, parsed.cik)
    await score_piotroski(db_session, parsed.cik, fiscal_year)
    await score_sloan(db_session, parsed.cik, fiscal_year)
    await score_beneish(db_session, parsed.cik, fiscal_year)
    if "fye_close" in company:
        # fye_date must be the issuer's OWN fiscal-year-end, not assumed Dec 31 —
        # OTEX's is June 30. score_altman looks up the price by the canonical
        # fact's real period_end, so a hardcoded date(fiscal_year, 12, 31) would
        # silently miss for any non-calendar-FYE filer and Altman would come back
        # insufficient_data instead of matching the hand-verified golden value.
        fye_date = date.fromisoformat(company["fye_date"])
        await upsert_fye_close(
            db_session, issuer_cik=parsed.cik, price_date=fye_date, close_price=company["fye_close"]
        )
        # Non-USD reporting filers (e.g. CP, in CAD) need the FX rate too, or X4
        # silently divides a USD price by a CAD denominator (AD-11 currency fix).
        if "fx_rate" in company:
            await upsert_fx_rate(
                db_session,
                currency_pair=company["fx_rate"]["currency_pair"],
                rate_date=fye_date,
                rate=company["fx_rate"]["rate"],
            )
        await score_altman(db_session, parsed.cik, fiscal_year)
    return parsed.cik


@requires_db
async def test_active_companies_match_golden(db_session) -> None:
    active = [c for c in GOLDEN["companies"] if c["status"] == "active"]
    assert active, "expected at least one active golden company"

    for company in active:
        cik = await _run_pipeline(db_session, company)
        expected = company["expected"]

        # Piotroski F-Score = count of passing signals. Scoped to this company's own
        # run — an unscoped query would double-count once a second active golden
        # company exists in the same session (caught 2026-07-23 when QSR was added:
        # SHOP's 7 + QSR's 6 leaked together into a bogus F-score of 13).
        piotroski_results = (
            await db_session.execute(
                select(ScoreResult)
                .join(ScoreRun, ScoreRun.id == ScoreResult.score_run_id)
                .where(ScoreResult.model == Model.piotroski, ScoreRun.issuer_cik == cik)
            )
        ).scalars().all()
        f_score = sum(1 for r in piotroski_results if r.status == SignalStatus.pass_)
        assert f_score == expected["piotroski"]["f_score"], f"{company['ticker']} Piotroski"

        # Sloan accruals ratio + band. Same scoping fix as Piotroski above.
        sloan_result = (
            await db_session.execute(
                select(ScoreResult)
                .join(ScoreRun, ScoreRun.id == ScoreResult.score_run_id)
                .where(ScoreResult.model == Model.sloan, ScoreRun.issuer_cik == cik)
            )
        ).scalars().one()
        assert abs(float(sloan_result.value) - expected["sloan"]["accruals_ratio"]) < 1e-4, f"{company['ticker']} Sloan ratio"
        assert sloan_result.band_label == expected["sloan"]["band"], f"{company['ticker']} Sloan band"

        # Altman Z + band. The band assertion was missing before 2026-07-25 — the
        # `band` field in phase1_golden.yaml existed but nothing checked it.
        altman_run = (
            await db_session.execute(
                select(ScoreRun).where(ScoreRun.model == Model.altman, ScoreRun.issuer_cik == cik)
            )
        ).scalars().one()

        # A null expected z_score asserts the model genuinely CANNOT compute, the
        # same contract Beneish has below. Suncor tags no retained-earnings concept
        # anywhere, so X2 and therefore Z are unresolvable — and its golden entry
        # still supplies a real price, so this confirms the missing input rather
        # than withheld market data. Without this branch the entry could not be
        # expressed at all, and the gap would have stayed silent.
        if expected["altman"]["z_score"] is None:
            assert altman_run.aggregate_value is None, f"{company['ticker']} Altman expected insufficient_data"
            no_band = (
                await db_session.execute(
                    select(ScoreResult).where(
                        ScoreResult.score_run_id == altman_run.id, ScoreResult.band_label.is_not(None)
                    )
                )
            ).scalars().all()
            assert not no_band, f"{company['ticker']} Altman banded an unresolved Z"
        else:
            assert abs(float(altman_run.aggregate_value) - expected["altman"]["z_score"]) < 1e-3, (
                f"{company['ticker']} Altman Z"
            )
            altman_band_result = (
                await db_session.execute(
                    select(ScoreResult).where(
                        ScoreResult.score_run_id == altman_run.id, ScoreResult.band_label.is_not(None)
                    )
                )
            ).scalars().one()
            assert altman_band_result.band_label == expected["altman"]["band"], (
                f"{company['ticker']} Altman band"
            )

        # Beneish M. A null expected m_score means the golden entry asserts the
        # model genuinely CANNOT compute for this company (e.g. CP has no COGS/SGA
        # tags at all, a real railroad reporting characteristic, not a bug) — the
        # ScoreRun still exists (score_beneish always writes one) but its aggregate
        # stays None, which must be confirmed rather than silently skipped.
        beneish_run = (
            await db_session.execute(
                select(ScoreRun).where(ScoreRun.model == Model.beneish, ScoreRun.issuer_cik == cik)
            )
        ).scalars().one()
        if expected["beneish"]["m_score"] is None:
            assert beneish_run.aggregate_value is None, f"{company['ticker']} Beneish expected insufficient_data"
        else:
            assert abs(float(beneish_run.aggregate_value) - expected["beneish"]["m_score"]) < 1e-3, f"{company['ticker']} Beneish M"

        # Near-term debt share (Story 5.6). Not a model — a ThesisTrace presentation
        # rule computed from two canonical facts — so it is checked from the facts
        # the pipeline canonicalized rather than from a ScoreRun. Both operands are
        # asserted, not just the ratio: the D8 pass showed that comparing only the
        # aggregate lets a wrong component hide behind a right-looking total.
        await _assert_near_term_debt_share(db_session, cik, company)


async def _assert_near_term_debt_share(db_session, cik: str, company: dict) -> None:
    expected = company["expected"].get("near_term_debt_share")
    assert expected is not None, (
        f"{company['ticker']} has no near_term_debt_share golden entry. SM-1 is a claim "
        "about the universe: every active company needs one, even if it is insufficient_data."
    )
    ticker, fiscal_year = company["ticker"], company["fiscal_year"]

    facts = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == cik,
                CanonicalFact.fiscal_year == fiscal_year,
                CanonicalFact.canonical_concept.in_(("near_term_debt", "total_debt")),
            )
        )
    ).scalars().all()
    by_concept = {f.canonical_concept: f for f in facts}

    share = compute(
        fiscal_year=fiscal_year,
        near_term_debt=by_concept["near_term_debt"].value if "near_term_debt" in by_concept else None,
        total_debt=by_concept["total_debt"].value if "total_debt" in by_concept else None,
    )

    if expected.get("insufficient_data"):
        assert share.insufficient_data, (
            f"{ticker} FY{fiscal_year}: expected insufficient_data ({expected['reason']}) but got {share.value}"
        )
        return

    assert not share.insufficient_data, f"{ticker} FY{fiscal_year}: expected a share, got insufficient_data"
    assert float(by_concept["near_term_debt"].value) == expected["near_term_debt"], f"{ticker} near_term_debt"
    assert float(by_concept["total_debt"].value) == expected["total_debt"], f"{ticker} total_debt"
    assert abs(float(share.value) - expected["share"]) < 1e-6, f"{ticker} near-term debt share"
    assert share.label == expected["band"], f"{ticker} near-term debt share band"

    # The denominator's provenance is part of the claim: a filed total and a derived
    # one are different provenance classes, and the golden entry names which applies.
    derived = by_concept["total_debt"].derivation
    if expected["total_source"].startswith("derived:"):
        assert derived == expected["total_source"].split("derived:")[1].strip(), f"{ticker} total_debt derivation"
    else:
        assert derived is None, f"{ticker} total_debt should be filed, not derived"
