"""Accounting-identity validation (AD-3, AD-17).

Runs basic consistency checks over canonical facts and writes a
`data_quality_issues` row (raised_by='validation') on any failure — surfaced as
a warning, never silently hidden (FR-8). The exact rule set is an implementation
detail per the spine's Deferred list; this is the Phase-1 starter set.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, DataQualityIssue, IssueStatus


async def run_validation(session: AsyncSession, issuer_cik: str) -> dict[str, int]:
    """Validate an issuer's canonical facts. Returns count of issues raised."""
    counts = {"issues_raised": 0}

    facts = (
        await session.execute(
            select(CanonicalFact).where(CanonicalFact.issuer_cik == issuer_cik)
        )
    ).scalars().all()

    by_year: dict[int, dict[str, CanonicalFact]] = defaultdict(dict)
    for f in facts:
        by_year[f.fiscal_year][f.canonical_concept] = f

    for fiscal_year, concepts in by_year.items():
        def raise_issue(rule: str, detail: dict) -> None:
            session.add(
                DataQualityIssue(
                    accession_number=next(iter(concepts.values())).accession_number,
                    issue_type=f"identity_violation:{rule}",
                    detail={"fiscal_year": fiscal_year, **detail},
                    status=IssueStatus.needs_review,
                    raised_by="validation",
                )
            )
            counts["issues_raised"] += 1

        total_assets = concepts.get("total_assets")
        current_assets = concepts.get("current_assets")
        current_liabilities = concepts.get("current_liabilities")

        # Current assets cannot exceed total assets.
        if total_assets and current_assets and current_assets.value > total_assets.value:
            raise_issue(
                "current_assets_gt_total_assets",
                {"current_assets": str(current_assets.value), "total_assets": str(total_assets.value)},
            )
        # Current liabilities cannot exceed total assets (a coarse solvency sanity check).
        if total_assets and current_liabilities and current_liabilities.value > total_assets.value:
            raise_issue(
                "current_liabilities_gt_total_assets",
                {
                    "current_liabilities": str(current_liabilities.value),
                    "total_assets": str(total_assets.value),
                },
            )

    await session.flush()
    return counts
