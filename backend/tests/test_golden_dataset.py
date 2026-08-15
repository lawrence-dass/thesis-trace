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
from canonicalization.mappings import MAPPING_VERSION, seed_concept_mappings
from debt.engine import compute
from debt.profile import PROFILE_CONCEPTS, profile_for_facts
from ingestion.company_facts import parse_company_facts
from raw_store.fx_rates import upsert_fx_rate
from raw_store.market_prices import upsert_fye_close
from raw_store.observation_dates import previous_trading_day
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
        # THE FISCAL-YEAR-END AND THE OBSERVATION DATE ARE DIFFERENT THINGS, and
        # this fixture used to conflate them — seeding the quote AT the year end.
        # Three golden years end on a Sunday (QSR and CP FY2023, OTEX FY2019), so
        # it was storing closes on days the market was shut, which is the same
        # defect the live store carried. The close itself is unchanged: it is the
        # last trading day's close either way, and `get_fye_close` resolves it for
        # the year end because that lookup takes the latest row within seven days.
        observed_on = previous_trading_day(fye_date)
        await upsert_fye_close(
            db_session,
            issuer_cik=parsed.cik,
            price_date=observed_on,
            close_price=company["fye_close"],
        )
        # Non-USD reporting filers (e.g. CP, in CAD) need the FX rate too, or X4
        # silently divides a USD price by a CAD denominator (AD-11 currency fix).
        if "fx_rate" in company:
            await upsert_fx_rate(
                db_session,
                currency_pair=company["fx_rate"]["currency_pair"],
                rate_date=observed_on,
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
        await _assert_maturity_profile(db_session, cik, company)
        await _assert_reverse_dcf(db_session, cik, company)


# --- Story 6.7: reverse DCF -------------------------------------------------
#
# THE INDEPENDENCE CONSTRAINT IS THE POINT OF THIS SECTION. The two functions
# below implement the discounted cash flow from the SPEC TEXT, and deliberately
# import nothing from backend/valuation, backend/scoring or backend/formulas. A
# golden value produced by calling the code under test asserts only that the code
# agrees with itself; it was an independent reimplementation that caught the IFRS
# golden pass's own averaging error, and the same discipline applies here.
#
# Consequence accepted: if the spec's assumptions change, this must be updated by
# hand. That is the cost of the guard, not an oversight — a version that imported
# the solver's constants would drift silently WITH it and guard nothing.


def _present_value(fcf0: float, growth: float, discount: float, terminal: float, years: int) -> float:
    """PV of `years` explicit cash flows plus a perpetuity, per reverse_dcf_v1.

    Free cash flow grows at exactly the revenue growth rate because the spec holds
    the free-cash-flow margin constant (A-4), so one rate drives both.
    """
    explicit = sum(fcf0 * (1 + growth) ** t / (1 + discount) ** t for t in range(1, years + 1))
    terminal_value = fcf0 * (1 + growth) ** years * (1 + terminal) / (discount - terminal)
    return explicit + terminal_value / (1 + discount) ** years


def _solve_implied_growth(
    fcf0: float, enterprise_value: float, discount: float, terminal: float, years: int
) -> float | None:
    """Bisection over the spec's DECLARED search range (-0.50..1.00).

    Returns None when the root lies outside the range rather than the nearest
    bound — the spec is explicit that the bounds are a search range and never a
    clamp, because returning a bound would present a search limit as a finding.
    """
    low, high = -0.50, 1.00
    if _present_value(fcf0, low, discount, terminal, years) > enterprise_value:
        return None
    if _present_value(fcf0, high, discount, terminal, years) < enterprise_value:
        return None
    for _ in range(200):
        mid = (low + high) / 2
        if _present_value(fcf0, mid, discount, terminal, years) < enterprise_value:
            low = mid
        else:
            high = mid
        if high - low < 1e-7:
            break
    return (low + high) / 2


REVERSE_DCF_CONCEPTS = (
    "cash_from_operations",
    "capex",
    "total_debt",
    "cash_and_equivalents",
    "shares_outstanding",
)


async def _assert_reverse_dcf(db_session, cik: str, company: dict) -> None:
    """Story 6.7 (SM-1 over the reverse DCF).

    EVERY operand is asserted, not only the implied rate: two wrong operands can
    agree on an aggregate, which is the failure the D8 pass found for the debt
    share and the reason that entry pins its numerator and denominator separately.
    """
    expected = company["expected"].get("reverse_dcf")
    assert expected is not None, (
        f"{company['ticker']} has no reverse_dcf golden entry. SM-1 is a claim about "
        "the universe: every active company needs one, even if it is insufficient_data."
    )
    ticker, fiscal_year = company["ticker"], company["fiscal_year"]

    facts = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == cik,
                CanonicalFact.fiscal_year == fiscal_year,
                CanonicalFact.mapping_version == MAPPING_VERSION,
                CanonicalFact.canonical_concept.in_(REVERSE_DCF_CONCEPTS),
            )
        )
    ).scalars().all()
    by_concept = {f.canonical_concept: float(f.value) for f in facts}

    if expected["insufficient_data"]:
        # Names WHICH operand is absent, so a filer that later gains the concept
        # fails this test loudly instead of quietly starting to resolve.
        missing = [c for c in REVERSE_DCF_CONCEPTS if c not in by_concept]
        assert missing, (
            f"{ticker} FY{fiscal_year}: golden says insufficient_data ({expected['reason_contains']}) "
            f"but every operand is present — the entry is now wrong, or coverage improved."
        )
        return

    for concept, want in (
        ("cash_from_operations", expected["operands"]["cash_from_operations"]),
        ("capex", expected["operands"]["capex"]),
        ("total_debt", expected["operands"]["total_debt"]),
        ("cash_and_equivalents", expected["operands"]["cash_and_equivalents"]),
        ("shares_outstanding", expected["operands"]["shares_outstanding"]),
    ):
        assert concept in by_concept, f"{ticker} FY{fiscal_year}: missing {concept}"
        assert by_concept[concept] == want, f"{ticker} FY{fiscal_year} {concept}"

    # market_price is the filer's own close in its REPORTING currency: a non-USD
    # filer's USD close is converted first, so market_cap's two factors share a
    # currency (AD-11, the same handling Altman's X4 uses).
    close = float(company["fye_close"])
    rate = company.get("fx_rate", {}).get("rate")
    market_price = close * float(rate) if rate else close
    assert abs(market_price - expected["operands"]["market_price"]) < 1e-6, f"{ticker} market_price"

    free_cash_flow = by_concept["cash_from_operations"] - by_concept["capex"]
    market_cap = by_concept["shares_outstanding"] * market_price
    enterprise_value = market_cap + by_concept["total_debt"] - by_concept["cash_and_equivalents"]

    assert free_cash_flow == expected["operands"]["free_cash_flow"], f"{ticker} free_cash_flow"
    assert abs(market_cap - expected["operands"]["market_cap"]) < 1e-2, f"{ticker} market_cap"
    assert abs(enterprise_value - expected["operands"]["enterprise_value"]) < 1e-2, (
        f"{ticker} enterprise_value"
    )

    assumptions = expected["assumptions"]
    implied = _solve_implied_growth(
        free_cash_flow,
        enterprise_value,
        assumptions["discount_rate"],
        assumptions["terminal_growth"],
        assumptions["horizon_years"],
    )
    assert implied is not None, f"{ticker} FY{fiscal_year}: expected a root, found none in range"
    assert abs(implied - expected["implied_growth"]) < 1e-6, (
        f"{ticker} FY{fiscal_year} implied growth: independent solve gave {implied!r}, "
        f"golden says {expected['implied_growth']!r}"
    )


def test_corrupting_a_golden_implied_growth_fails() -> None:
    """The guard bites (Story 6.7's last AC).

    Without this, every assertion above could be comparing a value to itself
    through some accidental identity and nothing would notice. Corrupts an
    expected rate by one part in ten thousand — far smaller than any real
    revision — and confirms the comparison rejects it.
    """
    resolved = [
        c
        for c in GOLDEN["companies"]
        if c["status"] == "active" and not c["expected"]["reverse_dcf"]["insufficient_data"]
    ]
    assert resolved, "expected at least one filer with a resolved golden implied growth"

    for company in resolved:
        expected = company["expected"]["reverse_dcf"]
        operands = expected["operands"]
        assumptions = expected["assumptions"]

        honest = _solve_implied_growth(
            operands["free_cash_flow"],
            operands["enterprise_value"],
            assumptions["discount_rate"],
            assumptions["terminal_growth"],
            assumptions["horizon_years"],
        )
        assert honest is not None
        assert abs(honest - expected["implied_growth"]) < 1e-6, (
            f"{company['ticker']}: golden implied growth does not reproduce from its own operands"
        )

        corrupted = expected["implied_growth"] + 1e-4
        assert not abs(honest - corrupted) < 1e-6, (
            f"{company['ticker']}: a corrupted expected value still passed the comparison — "
            "the guard does not bite"
        )


async def _assert_maturity_profile(db_session, cik: str, company: dict) -> None:
    """Story 5.7. Every bucket is pinned individually, and the ABSENCE of a profile
    is pinned too — five of seven filers have none, and that is a fact about the
    universe worth guarding rather than an untested gap."""
    expected = company["expected"].get("debt_maturity_profile")
    assert expected is not None, (
        f"{company['ticker']} has no debt_maturity_profile golden entry. SM-1 is a claim "
        "about the universe: every active company needs one, even if it is 'no profile'."
    )
    ticker, fiscal_year = company["ticker"], company["fiscal_year"]

    facts = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == cik,
                # The production read path filters on mapping_version; without it
                # here the guard would keep passing against facts canonicalized
                # under a stale version — exactly the risk a version bump creates.
                CanonicalFact.mapping_version == MAPPING_VERSION,
                CanonicalFact.canonical_concept.in_(PROFILE_CONCEPTS),
            )
        )
    ).scalars().all()
    profiles = profile_for_facts(facts)

    if expected.get("no_profile"):
        # Asserts the recorded reason, which is a claim about EVERY year, not just
        # the golden one — "never years 2-5 in any year" is not tested by checking
        # one year. A spurious profile in any other year must fail too.
        assert profiles == {}, (
            f"{ticker}: expected NO profile in any year ({expected['reason']}) but got "
            f"{sorted(profiles)}"
        )
        return

    assert fiscal_year in profiles, f"{ticker} FY{fiscal_year}: expected a profile, got none"
    profile = profiles[fiscal_year]
    assert profile.truncated == expected["truncated"], f"{ticker} truncated flag"
    assert profile.unit == expected["unit"], f"{ticker} unit — CP files in CAD and these are absolute amounts"

    actual = {b.canonical_concept: float(b.value) for b in profile.buckets}
    assert actual == expected["buckets"], f"{ticker} FY{fiscal_year} maturity buckets"

    # The profile must not offer a total. Its buckets are undiscounted contractual
    # principal and do not reconcile to total_debt — asserted here against the real
    # pipeline output, not just the dataclass shape.
    assert not any("total" in a.lower() for a in vars(profile)), f"{ticker} profile exposes a total"


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
