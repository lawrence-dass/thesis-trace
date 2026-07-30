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

MAPPING_VERSION = "concepts_v4"  # v4: adds ifrs-full (40-F) rules — D8


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
    # net_income: CP tags us-gaap:ProfitLoss for years its NetIncomeLoss tag omits
    # (confirmed live 2026-07-22 — CP is missing NetIncomeLoss for FY2014-2021).
    MappingRule("net_income", "us-gaap", "NetIncomeLoss", priority=0),
    MappingRule("net_income", "us-gaap", "ProfitLoss", priority=1),
    # cash_from_operations: QSR's FY2016 10-K tags the ContinuingOperations variant
    # instead of the plain concept (confirmed live 2026-07-23) — without this fallback,
    # the originally-filed FY2016 value never enters the candidate pool at all, leaving
    # only two later, mutually-conflicting comparative copies (1,269M vs 1,250M) and a
    # spurious ambiguous_selection where a clean originally-filed figure should win.
    MappingRule("cash_from_operations", "us-gaap", "NetCashProvidedByUsedInOperatingActivities", priority=0),
    MappingRule(
        "cash_from_operations", "us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", priority=1
    ),
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
    # total_liabilities: SHOP never tags us-gaap:Liabilities at all (confirmed live
    # 2026-07-22) — its balance sheet reports LiabilitiesAndStockholdersEquity and
    # StockholdersEquity instead. stockholders_equity is mapped below so
    # canonicalize.py can derive total_liabilities = total_assets - stockholders_equity
    # (the basic accounting identity, verified exactly against SHOP's real FY2024/2025
    # figures) as a last-resort fallback when the direct tag is genuinely absent.
    MappingRule("total_liabilities", "us-gaap", "Liabilities"),
    MappingRule("stockholders_equity", "us-gaap", "StockholdersEquity"),
    MappingRule("retained_earnings", "us-gaap", "RetainedEarningsAccumulatedDeficit"),
    MappingRule("ebit", "us-gaap", "OperatingIncomeLoss"),
    # revenue: CP's us-gaap:Revenues tag doesn't cover FY2014-2021 (confirmed live
    # 2026-07-22) even though it exists as a concept overall; RevenueFromContract...
    # is the ASC-606-era tag most filers (including CP) switched some years to.
    MappingRule("revenue", "us-gaap", "Revenues", priority=0),
    MappingRule("revenue", "us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax", priority=1),
    # Beneish + Piotroski completeness (Story 2.3)
    # cogs/sga/long_term_debt: none of these 3 concepts ever resolved for any of the
    # 4 companies under the original single-tag mapping (confirmed live 2026-07-22 —
    # zero canonical_facts rows existed for any of them). Fallback tags verified live
    # per company; a company with neither tag (e.g. CP for cogs/sga — a railroad,
    # plausibly reports functional expense categories instead of a single COGS/SGA
    # line) correctly resolves to insufficient_data rather than a guess (AD-3).
    MappingRule("cogs", "us-gaap", "CostOfRevenue", priority=0),
    MappingRule("cogs", "us-gaap", "CostOfGoodsAndServicesSold", priority=1),
    MappingRule("sga", "us-gaap", "SellingGeneralAndAdministrativeExpense", priority=0),
    MappingRule("sga", "us-gaap", "GeneralAndAdministrativeExpense", priority=1),
    # receivables: QSR tags AccountsNotesAndLoansReceivableNetCurrent (a combined
    # notes+accounts tag), never AccountsReceivableNetCurrent — confirmed live
    # 2026-07-23, this made QSR's Beneish insufficient_data for every year, not
    # just the 2024-2025 window the cogs gap alone would explain. SHOP tags
    # AccountsAndOtherReceivablesNetCurrent instead — also confirmed live, SHOP's
    # Beneish never resolved at all under the original single-tag mapping.
    MappingRule("receivables", "us-gaap", "AccountsReceivableNetCurrent", priority=0),
    MappingRule("receivables", "us-gaap", "AccountsNotesAndLoansReceivableNetCurrent", priority=1),
    MappingRule("receivables", "us-gaap", "AccountsAndOtherReceivablesNetCurrent", priority=2),
    # ppe_net: CP switched to a combined PP&E + finance-lease right-of-use-asset
    # tag starting with its FY2021 10-K (confirmed live 2026-07-29) — its own
    # originally-filed FY2021/2024/2025 accessions never tag the plain
    # PropertyPlantAndEquipmentNet concept at all for those balance-sheet dates,
    # which was silently starving Beneish's AQI/DEPI indices of a real value.
    MappingRule("ppe_net", "us-gaap", "PropertyPlantAndEquipmentNet", priority=0),
    MappingRule(
        "ppe_net", "us-gaap",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
        priority=1,
    ),
    # depreciation: QSR never tags the combined DepreciationDepletionAndAmortization
    # concept — it tags the plain Depreciation/DepreciationAndAmortization line
    # instead (confirmed live 2026-07-23). OTEX switches away from a single total
    # D&A tag entirely after FY2019 (splits into DepreciationNonproduction +
    # OtherDepreciationAndAmortization + several Amortization* line items with no
    # single combined tag) — deriving a total by summing an assumed subset would be
    # a guess (AD-3), so OTEX's Beneish correctly stays insufficient_data for
    # FY2020 onward rather than being forced with an unverified derivation.
    MappingRule("depreciation", "us-gaap", "DepreciationDepletionAndAmortization", priority=0),
    MappingRule("depreciation", "us-gaap", "DepreciationAndAmortization", priority=1),
    MappingRule("depreciation", "us-gaap", "Depreciation", priority=2),
    MappingRule("long_term_debt", "us-gaap", "LongTermDebtNoncurrent", priority=0),
    # CP: verified live 2026-07-22 — no "...Noncurrent" variant exists; the actual
    # tag CP uses is LongTermDebtAndCapitalLeaseObligations (total, not split into
    # current/noncurrent), reported in CAD (see the currency note on total_liabilities
    # above — CP's financials are entirely CAD-denominated).
    MappingRule("long_term_debt", "us-gaap", "LongTermDebtAndCapitalLeaseObligations", priority=1),
    MappingRule("gross_profit", "us-gaap", "GrossProfit"),

    # --- ifrs-full (Form 40-F, Canadian MJDS filers) -- D8 -------------------
    #
    # Verified live against data.sec.gov 2026-07-29. Cameco (CIK 0001009001)
    # resolves 17 of 18 canonical concepts from directly-filed tags, every one
    # with the full FY2017-2025 span. `total_liabilities` is the single gap and
    # needs no new code: canonicalize._derive_total_liabilities already covers it
    # via the accounting identity (assets - equity) and is taxonomy-blind, since
    # it operates on canonical concepts rather than source tags.
    #
    # Two IFRS naming traps worth stating, both of which cost real coverage if
    # the obvious tag is taken first (confirmed live on Suncor):
    #   * revenue — `Revenue` exists but can carry only a single year, while
    #     `RevenueFromContractsWithCustomers` (IFRS 15, mandatory from 2018)
    #     carries the rest. Both are mapped, priority-ordered.
    #   * shares_outstanding — `NumberOfSharesOutstanding` can be sparse;
    #     `NumberOfSharesIssued` / `WeightedAverageShares` are the deeper
    #     fallbacks. Same trap class as the us-gaap dei/shares bug.
    #
    # Presentation-driven gaps are deliberately NOT papered over. IAS 1 permits
    # expenses by nature instead of by function, so a by-nature filer (Suncor)
    # has no SG&A line at all and Beneish's SGAI correctly stays
    # insufficient_data — the same treatment as CP's missing COGS under us-gaap.
    MappingRule("total_assets", "ifrs-full", "Assets"),
    MappingRule("current_assets", "ifrs-full", "CurrentAssets"),
    MappingRule("current_liabilities", "ifrs-full", "CurrentLiabilities"),
    MappingRule("total_liabilities", "ifrs-full", "Liabilities"),
    MappingRule("stockholders_equity", "ifrs-full", "Equity", priority=0),
    MappingRule("stockholders_equity", "ifrs-full", "EquityAttributableToOwnersOfParent", priority=1),
    MappingRule("retained_earnings", "ifrs-full", "RetainedEarnings"),
    MappingRule("net_income", "ifrs-full", "ProfitLoss", priority=0),
    MappingRule("net_income", "ifrs-full", "ProfitLossAttributableToOwnersOfParent", priority=1),
    # IFRS mandates no operating-profit line, but a filer MAY tag one. Where it
    # does (Cameco, all 9 years) ebit is read as filed, not derived — so no
    # judgment enters the number. Filers that omit it get insufficient_data
    # until the derivation decision is made in a versioned spec (D8 consequence 3).
    MappingRule("ebit", "ifrs-full", "ProfitLossFromOperatingActivities"),
    MappingRule("cash_from_operations", "ifrs-full", "CashFlowsFromUsedInOperatingActivities", priority=0),
    MappingRule("cash_from_operations", "ifrs-full", "CashFlowsFromUsedInOperations", priority=1),
    MappingRule("revenue", "ifrs-full", "Revenue", priority=0),
    MappingRule("revenue", "ifrs-full", "RevenueFromContractsWithCustomers", priority=1),
    MappingRule("cogs", "ifrs-full", "CostOfSales", priority=0),
    MappingRule("cogs", "ifrs-full", "CostOfInventoriesRecognisedAsExpenseDuringPeriod", priority=1),
    MappingRule("gross_profit", "ifrs-full", "GrossProfit"),
    MappingRule("sga", "ifrs-full", "AdministrativeExpense", priority=0),
    MappingRule("sga", "ifrs-full", "SellingGeneralAndAdministrativeExpense", priority=1),
    MappingRule("ppe_net", "ifrs-full", "PropertyPlantAndEquipment"),
    MappingRule("depreciation", "ifrs-full", "DepreciationAndAmortisationExpense", priority=0),
    MappingRule(
        "depreciation", "ifrs-full",
        "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss",
        priority=1,
    ),
    MappingRule("receivables", "ifrs-full", "TradeAndOtherCurrentReceivables", priority=0),
    MappingRule("receivables", "ifrs-full", "CurrentTradeReceivables", priority=1),
    MappingRule("long_term_debt", "ifrs-full", "LongtermBorrowings", priority=0),
    MappingRule("long_term_debt", "ifrs-full", "NoncurrentPortionOfLongtermBorrowings", priority=1),
    MappingRule("shares_outstanding", "ifrs-full", "NumberOfSharesOutstanding", priority=0),
    MappingRule("shares_outstanding", "ifrs-full", "NumberOfSharesIssued", priority=1),
    MappingRule("shares_outstanding", "ifrs-full", "WeightedAverageShares", priority=2),
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
