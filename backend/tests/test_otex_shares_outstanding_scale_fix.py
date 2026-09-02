"""otex_shares_outstanding_scale_error_fy2007_fy2009 (engineering-findings.yaml).

OTEX's FY2009 10-K (its first-ever XBRL filing, accession
0001193125-09-179839 — the same filing behind
otex_capex_sign_error_fy2007_fy2009) also mis-scaled
WeightedAverageNumberOfSharesOutstandingBasic by 1000x for the years it
originally reports: FY2007 49,393 (should be 49,393,000) and FY2009 (its own
just-ended year) 52,030 (should be 52,030,000). Self-corrected in every
later filing's comparative column with no formal amendment. Live-verified
impact: the wrong FY2009 share count understated market value of equity by
1000x, flipping the stored Altman Z-Score from 3.189 (Safe) to 0.927
(Distress) — a live misclassification on the Overview page, not a latent
data-layer risk.

`excludes_accessions` (concepts_v13, us-gaap_v12.yaml) removes this one
filing's contribution to shares_outstanding. Uses the real
otex_company_facts.json fixture — it already carries the bug's exact values
(confirmed against live data.sec.gov). It does NOT carry
us-gaap:CommonStockSharesOutstanding at FY2009 (the trimmed-fixture trap
again), so this test injects that one additional real, live-verified fact —
OTEX's actual FY2010 10-K value, 52,716,751 at period_end 2009-06-30 — to
prove FY2009 correctly falls through to it once the bad accession is
excluded. That Filing row already exists after the standard fixture ingest
(the FY2010 10-K appears in the fixture under other concepts), so only the
RawFact needs adding.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, RawFact
from canonicalization.canonicalize import canonicalize_issuer
from pipeline.run import run_issuer
from tests.conftest import requires_db

FIXTURES = Path(__file__).parent / "fixtures"
OTEX_CIK = "0001002638"

# OTEX's real FY2010 10-K, accession 0001193125-10-193608 (already a Filing
# after the fixture's own ingest — see module docstring), tagging FY2009's
# comparative CommonStockSharesOutstanding correctly. Confirmed live
# 2026-09-02 against data.sec.gov's company-facts JSON for CIK 0001002638.
_FY2010_10K_ACCESSION = "0001193125-10-193608"
_FY2009_CORRECT_SHARES = Decimal("52716751")


async def _inject_fy2009_common_stock_shares(db_session) -> None:
    db_session.add(
        RawFact(
            accession_number=_FY2010_10K_ACCESSION,
            taxonomy="us-gaap",
            concept="CommonStockSharesOutstanding",
            unit="shares",
            period_end=date(2009, 6, 30),
            value=_FY2009_CORRECT_SHARES,
            source="company_facts",
            content_hash="otex-fy2009-common-stock-shares",
            fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()


async def _shares_outstanding_facts(db_session) -> dict[int, CanonicalFact]:
    facts = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == OTEX_CIK,
                CanonicalFact.canonical_concept == "shares_outstanding",
                CanonicalFact.superseded.is_(False),
            )
        )
    ).scalars().all()
    return {f.fiscal_year: f for f in facts}


@requires_db
async def test_otex_fy2007_shares_outstanding_becomes_insufficient_data(db_session) -> None:
    """No other candidate exists for FY2007 once the bad accession is excluded —
    it must become honestly insufficient_data, not silently wrong."""
    payload = json.loads((FIXTURES / "otex_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="OTEX")

    facts = await _shares_outstanding_facts(db_session)
    assert 2007 not in facts, (
        f"FY2007 should be insufficient_data (no other source), got {facts.get(2007)}"
    )


@requires_db
async def test_otex_fy2009_shares_outstanding_falls_through_to_common_stock_tag(db_session) -> None:
    payload = json.loads((FIXTURES / "otex_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="OTEX")

    await _inject_fy2009_common_stock_shares(db_session)
    await canonicalize_issuer(db_session, OTEX_CIK)

    facts = await _shares_outstanding_facts(db_session)
    assert 2009 in facts
    assert facts[2009].value == _FY2009_CORRECT_SHARES


@requires_db
async def test_otex_fy2010_onward_unaffected(db_session) -> None:
    """The exclusion must not perturb years the bad filing never touches."""
    payload = json.loads((FIXTURES / "otex_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="OTEX")

    facts = await _shares_outstanding_facts(db_session)
    assert facts[2010].value == Decimal("56280000")
