"""otex_capex_sign_error_fy2007_fy2009 (engineering-findings.yaml).

OTEX's own FY2009 10-K tagged PaymentsToAcquireProductiveAssets with a
nonstandard negative sign for its own FY2009 (-12,150,000) and its FY2007
comparative (-5,260,000). AD-3's as-originally-filed tiebreak selected the
FY2009 value outright (no competing candidate); FY2007 had only that one lone
candidate at all. FY2008 had two later, sign-flipped, magnitude-identical
comparative candidates and was correctly flagged `ambiguous_selection` rather
than guessed. `capex`'s `non_negative: true` flag (us-gaap_v10.yaml, concepts_v11)
fixes both shapes: canonicalize.py takes abs(value) before both the ambiguity
check and the final write.

Uses the real EDGAR fixture (`otex_company_facts.json`, not the synthetic SHOP
one) — it is the fixture live-verification against data.sec.gov found this bug
in, so it is the one fixture guaranteed to exercise it (this project's own
recurring "fixture can't reproduce its own reason" trap).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, DataQualityIssue, IssueStatus
from pipeline.run import run_issuer
from tests.conftest import requires_db

FIXTURES = Path(__file__).parent / "fixtures"
OTEX_CIK = "0001002638"


async def _capex_facts(db_session) -> dict[int, CanonicalFact]:
    facts = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == OTEX_CIK,
                CanonicalFact.canonical_concept == "capex",
                CanonicalFact.superseded.is_(False),
            )
        )
    ).scalars().all()
    return {f.fiscal_year: f for f in facts}


@requires_db
async def test_otex_capex_fy2007_and_fy2009_normalize_to_positive(db_session) -> None:
    payload = json.loads((FIXTURES / "otex_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="OTEX")

    capex = await _capex_facts(db_session)
    assert capex[2007].value == Decimal("5260000")
    assert capex[2009].value == Decimal("12150000")
    # Every canonical capex value is a magnitude — never negative, for any year.
    assert all(f.value >= 0 for f in capex.values()), {
        fy: f.value for fy, f in capex.items() if f.value < 0
    }


@requires_db
async def test_otex_capex_fy2008_recovers_instead_of_staying_ambiguous(db_session) -> None:
    """FY2008's two candidates (-6,895,000 / +6,895,000) agree on magnitude once
    normalized — the ambiguity was never a genuine value conflict, only a sign
    artifact, so it must resolve rather than stay flagged."""
    payload = json.loads((FIXTURES / "otex_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="OTEX")

    capex = await _capex_facts(db_session)
    assert 2008 in capex
    assert capex[2008].value == Decimal("6895000")

    issues = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.issue_type == "ambiguous_selection")
        )
    ).scalars().all()
    capex_2008_ambiguities = [
        i for i in issues
        if i.status == IssueStatus.needs_review
        and (i.detail or {}).get("canonical_concept") == "capex"
        and (i.detail or {}).get("fiscal_year") == 2008
    ]
    assert not capex_2008_ambiguities, capex_2008_ambiguities


@requires_db
async def test_otex_capex_fy2010_onward_unaffected(db_session) -> None:
    """The normalization must not perturb years that were already correct — only
    FY2007-2009 carried the sign defect; live-verified 2026-09-02 that FY2010
    onward is clean and positive."""
    payload = json.loads((FIXTURES / "otex_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="OTEX")

    capex = await _capex_facts(db_session)
    assert capex[2010].value == Decimal("19314000")
