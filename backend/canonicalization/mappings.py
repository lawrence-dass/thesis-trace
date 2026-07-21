"""Versioned concept mappings (AD-2, AD-3).

Maps source XBRL concepts to ThesisTrace canonical concepts. A mapping change
produces a new MAPPING_VERSION, never an in-place edit. Seeded into the
`concept_mappings` table so canonicalization is reproducible and auditable.
Phase-1 canonical concepts cover the Piotroski + Sloan inputs (extended for
Altman/Beneish in Epic 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConceptMapping

MAPPING_VERSION = "concepts_v2"


@dataclass(frozen=True)
class MappingRule:
    canonical_concept: str
    source_taxonomy: str
    source_concept: str
    priority: int = 0  # lower wins when multiple source concepts map to one canonical


# One canonical concept may accept several source tags; priority orders fallbacks.
MAPPING_RULES: tuple[MappingRule, ...] = (
    MappingRule("total_assets", "us-gaap", "Assets"),
    MappingRule("current_assets", "us-gaap", "AssetsCurrent"),
    MappingRule("current_liabilities", "us-gaap", "LiabilitiesCurrent"),
    MappingRule("net_income", "us-gaap", "NetIncomeLoss"),
    MappingRule("cash_from_operations", "us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
    # shares_outstanding: NOT sourced from dei:EntityCommonStockSharesOutstanding — that
    # cover-page fact is dated to the 10-K's filing date (commonly 45-75+ days after
    # fiscal year-end for a December filer), not FYE, so it lands in the wrong fiscal-year
    # bucket during canonicalization (grouped by rf.period_end.year) and silently starves
    # Altman's X4 and Piotroski's shares_not_diluted signal of real production data.
    # Verified live against SEC EDGAR (2026-07-21): us-gaap:CommonStockSharesOutstanding is
    # genuinely FYE-dated for single-class filers (CP, QSR, OTEX all confirmed). SHOP's
    # multi-class share structure means its 10-Ks don't tag that concept at all — its FYE-
    # dated fallback is the weighted-average basic count, also confirmed live.
    MappingRule("shares_outstanding", "us-gaap", "CommonStockSharesOutstanding", priority=0),
    MappingRule("shares_outstanding", "us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic", priority=1),
    # Altman (Story 2.2)
    MappingRule("total_liabilities", "us-gaap", "Liabilities"),
    MappingRule("retained_earnings", "us-gaap", "RetainedEarningsAccumulatedDeficit"),
    MappingRule("ebit", "us-gaap", "OperatingIncomeLoss"),
    MappingRule("revenue", "us-gaap", "Revenues"),
    # Beneish + Piotroski completeness (Story 2.3)
    MappingRule("cogs", "us-gaap", "CostOfRevenue"),
    MappingRule("sga", "us-gaap", "SellingGeneralAndAdministrativeExpense"),
    MappingRule("receivables", "us-gaap", "AccountsReceivableNetCurrent"),
    MappingRule("ppe_net", "us-gaap", "PropertyPlantAndEquipmentNet"),
    MappingRule("depreciation", "us-gaap", "DepreciationDepletionAndAmortization"),
    MappingRule("long_term_debt", "us-gaap", "LongTermDebtNoncurrent"),
    MappingRule("gross_profit", "us-gaap", "GrossProfit"),
)

# Source (taxonomy, concept) -> canonical concept, for quick lookup during canonicalization.
SOURCE_TO_CANONICAL: dict[tuple[str, str], str] = {
    (r.source_taxonomy, r.source_concept): r.canonical_concept for r in MAPPING_RULES
}

# Source (taxonomy, concept) -> priority, consulted by canonicalize.py's rank() so that
# when several source concepts map to the same canonical concept (e.g. the shares_outstanding
# fallback chain above), the lower-priority-number concept wins outright rather than being
# compared for value-ambiguity against a fundamentally different measurement.
SOURCE_PRIORITY: dict[tuple[str, str], int] = {
    (r.source_taxonomy, r.source_concept): r.priority for r in MAPPING_RULES
}


async def seed_concept_mappings(session: AsyncSession, *, version: str = MAPPING_VERSION) -> int:
    """Insert the mapping rules for `version` if not already present. Returns rows added."""
    existing = set(
        (
            await session.execute(
                select(ConceptMapping.canonical_concept, ConceptMapping.source_concept).where(
                    ConceptMapping.mapping_version == version
                )
            )
        ).all()
    )
    added = 0
    for rule in MAPPING_RULES:
        if (rule.canonical_concept, rule.source_concept) in existing:
            continue
        session.add(
            ConceptMapping(
                mapping_version=version,
                canonical_concept=rule.canonical_concept,
                source_taxonomy=rule.source_taxonomy,
                source_concept=rule.source_concept,
                priority=rule.priority,
            )
        )
        added += 1
    await session.flush()
    return added
