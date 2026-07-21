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

MAPPING_VERSION = "concepts_v1"


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
    MappingRule("shares_outstanding", "dei", "EntityCommonStockSharesOutstanding"),
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
