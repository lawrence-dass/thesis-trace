"""Story 1.4 — canonicalization selection + validation (AD-2, AD-3, AD-17)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, DataQualityIssue, IssueStatus, RawFact
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from validation.checks import run_validation
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


async def _ingest(db_session) -> str:
    parsed = parse_company_facts(json.loads(FIXTURE.read_text()))
    await persist_company_facts(db_session, parsed, ticker="SHOP")
    await seed_concept_mappings(db_session)
    return parsed.cik


@requires_db
async def test_canonicalize_maps_and_selects(db_session) -> None:
    cik = await _ingest(db_session)
    counts = await canonicalize_issuer(db_session, cik)
    assert counts["canonical_facts_added"] > 0
    assert counts["ambiguities_flagged"] == 0

    facts = {
        (f.canonical_concept, f.fiscal_year): f
        for f in (await db_session.execute(select(CanonicalFact))).scalars()
    }
    # total_assets FY2024 = 13.1B, mapped from us-gaap:Assets.
    assert facts[("total_assets", 2024)].value == 13100000000
    assert facts[("net_income", 2023)].value == 132000000


@requires_db
async def test_canonicalize_is_idempotent(db_session) -> None:
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)
    second = await canonicalize_issuer(db_session, cik)
    assert second["canonical_facts_added"] == 0


@requires_db
async def test_conflicting_values_flag_ambiguity_not_guess(db_session) -> None:
    cik = await _ingest(db_session)
    # Inject a SECOND originally-filed Assets fact for FY2024 with a different value
    # under the same filing — the rules cannot separate them, so it must be flagged.
    db_session.add(
        RawFact(
            accession_number="0001594805-25-000010",
            taxonomy="us-gaap",
            concept="Assets",
            unit="USD",
            period_end=date(2024, 12, 31),
            value=99999999999,
            source="inline_xbrl",
            content_hash="conflict-hash",
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()

    counts = await canonicalize_issuer(db_session, cik)
    assert counts["ambiguities_flagged"] >= 1

    issue = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.issue_type == "ambiguous_selection")
        )
    ).scalars().first()
    assert issue is not None
    assert issue.status == IssueStatus.needs_review
    # No canonical total_assets FY2024 row was created for the ambiguous case.
    ta_2024 = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "total_assets", CanonicalFact.fiscal_year == 2024
            )
        )
    ).scalars().first()
    assert ta_2024 is None


@requires_db
async def test_validation_flags_identity_violation(db_session) -> None:
    cik = await _ingest(db_session)
    await canonicalize_issuer(db_session, cik)
    # Corrupt a canonical fact so current_assets > total_assets for FY2024.
    ca = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.canonical_concept == "current_assets", CanonicalFact.fiscal_year == 2024
            )
        )
    ).scalars().one()
    ca.value = 99000000000  # > total_assets
    await db_session.flush()

    counts = await run_validation(db_session, cik)
    assert counts["issues_raised"] >= 1
    issue = (
        await db_session.execute(
            select(DataQualityIssue).where(DataQualityIssue.raised_by == "validation")
        )
    ).scalars().first()
    assert issue is not None and "identity_violation" in issue.issue_type
