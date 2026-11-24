"""Ops 5: `scripts/dismiss_stale_sga_issues.py` may dismiss only what it can PROVE.

The first version matched an issue's values against any G&A fact within +/-1
year. The Ops 5 review built a counterexample: a genuine conflict between two filed
SG&A TOTALS whose values coincide with G&A in neighbouring years was selected for
dismissal. The script runs against production, so each case below is a real shape,
with a positive control so the refusals cannot pass vacuously.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.models import DataQualityIssue, Filing, Issuer, IssueStatus, RawFact
from tests.conftest import requires_db

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dismiss_stale_sga_issues.py"


def _module():
    spec = importlib.util.spec_from_file_location("dismiss_stale_sga_issues", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _issuer(session, cik: str, facts: list[tuple[str, int, int]]) -> str:
    """facts: (concept, fiscal year, value in millions), each an annual Dec-31 fact."""
    session.add(Issuer(cik=cik, ticker=f"T{cik[-3:]}", name=f"Test {cik}"))
    accn = f"{cik}-25-000001"
    session.add(Filing(accession_number=accn, issuer_cik=cik, form_type="10-K",
                       filing_date=date(2026, 2, 1), fiscal_year=2025, fiscal_year_end=date(2025, 12, 31)))
    await session.flush()
    for i, (concept, fy, millions) in enumerate(facts):
        session.add(RawFact(accession_number=accn, taxonomy="us-gaap", concept=concept, unit="USD",
                            period_start=date(fy, 1, 1), period_end=date(fy, 12, 31),
                            value=Decimal(millions) * 1_000_000, source="company_facts",
                            content_hash=f"{cik}-{i}"))
    await session.flush()
    return accn


async def _issue(session, accn: str, fy: int, values: list[int], *, status=IssueStatus.needs_review,
                 resolution: str | None = None) -> DataQualityIssue:
    detail = {"canonical_concept": "sga", "fiscal_year": fy,
              "values": [f"{v * 1_000_000}.000000" for v in values]}
    if resolution:
        detail["resolution"] = resolution
    issue = DataQualityIssue(accession_number=accn, issue_type="ambiguous_selection", detail=detail,
                             status=status, raised_by="canonicalization")
    session.add(issue)
    await session.flush()
    return issue


@requires_db
async def test_only_a_proven_g_and_a_conflict_is_dismissed(db_session) -> None:
    mod = _module()
    ga = "GeneralAndAdministrativeExpense"
    total = "SellingGeneralAndAdministrativeExpense"

    # POSITIVE CONTROL: no SG&A total that year, both values are that year's G&A.
    stale_accn = await _issuer(db_session, "0000000901", [(ga, 2022, 707), (ga, 2022, 708)])
    stale = await _issue(db_session, stale_accn, 2022, [707, 708])

    # The review's counterexample: a genuine conflict between two filed TOTALS for
    # FY2024, whose values coincide with G&A in FY2023 and FY2025.
    totals_accn = await _issuer(db_session, "0000000902",
                                [(total, 2024, 100), (total, 2024, 120), (ga, 2023, 100), (ga, 2025, 120)])
    genuine = await _issue(db_session, totals_accn, 2024, [100, 120])

    # Totals conflict AND G&A coincides in the SAME year. Only the "no filed total"
    # proof saves this one; the exact-year match alone would select it.
    same_accn = await _issuer(db_session, "0000000905",
                              [(total, 2024, 200), (total, 2024, 210), (ga, 2024, 200), (ga, 2024, 210)])
    coincident = await _issue(db_session, same_accn, 2024, [200, 210])

    # G&A values exist, but only in a NEIGHBOURING year (the old +/-1 window).
    near_accn = await _issuer(db_session, "0000000903", [(ga, 2023, 50), (ga, 2023, 55)])
    neighbour = await _issue(db_session, near_accn, 2024, [50, 55])

    # Right shape, but already resolved by someone, or already carrying evidence.
    done_accn = await _issuer(db_session, "0000000904", [(ga, 2022, 30), (ga, 2022, 31)])
    resolved = await _issue(db_session, done_accn, 2022, [30, 31], status=IssueStatus.resolved,
                            resolution="checked by hand")
    noted = await _issue(db_session, done_accn, 2022, [30, 31], resolution="earlier evidence")

    rows = await mod.find_stale(db_session)
    assert [r[0] for r in rows] == [stale.id], "only the proven G&A conflict may be selected"

    await mod.dismiss(db_session, rows)
    await db_session.flush()
    for issue in (stale, genuine, coincident, neighbour, resolved, noted):
        await db_session.refresh(issue)

    assert stale.status is IssueStatus.dismissed and "Ops 5" in stale.detail["resolution"]
    assert genuine.status is IssueStatus.needs_review
    assert coincident.status is IssueStatus.needs_review
    assert neighbour.status is IssueStatus.needs_review
    assert resolved.status is IssueStatus.resolved and resolved.detail["resolution"] == "checked by hand"
    assert noted.status is IssueStatus.needs_review and noted.detail["resolution"] == "earlier evidence"
    remaining = (await db_session.execute(select(DataQualityIssue))).scalars().all()
    assert len(remaining) == 6, "nothing is deleted"
