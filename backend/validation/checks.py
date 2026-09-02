"""Accounting-identity validation (AD-3, AD-17).

Runs basic consistency checks over canonical facts and writes a
`data_quality_issues` row (raised_by='validation') on any failure — surfaced as
a warning, never silently hidden (FR-8). The exact rule set is an implementation
detail per the spine's Deferred list; this is the Phase-1 starter set.

Idempotent, like `canonicalize_issuer`: the batch pipeline re-runs daily over the
same canonical facts, so a violation that is still present must NOT accumulate a
fresh row every night. An issue is keyed by (rule, fiscal_year) per issuer, and a
key that already exists is left alone regardless of its status — re-raising a
`dismissed` issue would resurrect a warning a human deliberately cleared.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, DataQualityIssue, Filing, IssueStatus
from canonicalization.mappings import MAPPING_VERSION


async def _existing_issue_keys(session: AsyncSession, issuer_cik: str) -> set[tuple[str, int | None]]:
    """(issue_type, fiscal_year) already recorded by validation for this issuer.

    Scoped through filings because data_quality_issues has no issuer column of
    its own — it points at an accession.
    """
    rows = (
        await session.execute(
            select(DataQualityIssue.issue_type, DataQualityIssue.detail)
            .join(Filing, Filing.accession_number == DataQualityIssue.accession_number)
            .where(Filing.issuer_cik == issuer_cik, DataQualityIssue.raised_by == "validation")
        )
    ).all()
    return {(issue_type, (detail or {}).get("fiscal_year")) for issue_type, detail in rows}


async def run_validation(session: AsyncSession, issuer_cik: str) -> dict[str, int]:
    """Validate an issuer's canonical facts.

    Returns `issues_raised` (new rows written this pass) and `issues_existing`
    (violations still present that were already on record, so not re-raised).
    """
    counts = {"issues_raised": 0, "issues_existing": 0}

    facts = (
        await session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == issuer_cik,
                CanonicalFact.mapping_version == MAPPING_VERSION,
                CanonicalFact.superseded.is_(False),
            )
        )
    ).scalars().all()

    seen = await _existing_issue_keys(session, issuer_cik)

    by_year: dict[int, dict[str, CanonicalFact]] = defaultdict(dict)
    for f in facts:
        by_year[f.fiscal_year][f.canonical_concept] = f

    for fiscal_year, concepts in by_year.items():
        def raise_issue(rule: str, detail: dict) -> None:
            issue_type = f"identity_violation:{rule}"
            key = (issue_type, fiscal_year)
            if key in seen:
                counts["issues_existing"] += 1
                return
            session.add(
                DataQualityIssue(
                    accession_number=next(iter(concepts.values())).accession_number,
                    issue_type=issue_type,
                    detail={"fiscal_year": fiscal_year, **detail},
                    status=IssueStatus.needs_review,
                    raised_by="validation",
                )
            )
            # Guard within this pass too, not just across passes.
            seen.add(key)
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
