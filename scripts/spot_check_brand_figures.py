"""Live spot-check of Story 13.4c's materialized figures against the filings.

Fetches exactly two Inline XBRL instance documents from www.sec.gov (approved by
Lawrence 2026-10-08, named before fetching) and compares four brand-years with
what `brand_figures` holds. Run with ``make py F=scripts/spot_check_brand_figures.py``.

Company Facts carries no dimensions, so the instance document is the only live
source that can confirm a per-member value.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import BrandFigure
from ingestion.edgar import fetch_instance_document
from ingestion.inline_xbrl import parse_instance

CONCEPT = "IndefiniteLivedIntangibleAssetsExcludingGoodwill"
CLASS_AXIS = "us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis"
SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"
FV_AXIS = "us-gaap:FairValueByMeasurementFrequencyAxis"

# (cik, accession, filing fiscal year) -> [(brand_key, fiscal_year, period_end, dims)]
CHECKS = {
    ("0000016732", "0000016732-24-000130", 2024): [
        ("raos", 2024, "2024-07-28", {CLASS_AXIS: "cpb:TrademarksRaosMember"}),
        ("pop_secret", 2024, "2024-07-28", {
            CLASS_AXIS: "cpb:TrademarksPopSecretMember",
            FV_AXIS: "us-gaap:FairValueMeasurementsNonrecurringMember",
        }),
    ],
    ("0001618756", "0001618756-22-000018", 2021): [
        ("firehouse_subs", 2021, "2021-12-31", {
            CLASS_AXIS: "us-gaap:TradeNamesMember", SEGMENT_AXIS: "qsr:FirehouseSubsMember",
        }),
        ("firehouse_subs", 2020, "2020-12-31", {
            CLASS_AXIS: "us-gaap:TradeNamesMember", SEGMENT_AXIS: "qsr:FirehouseSubsMember",
        }),
    ],
}


async def main() -> None:
    sessionmaker = get_sessionmaker()
    mismatches = 0
    async with sessionmaker() as session:
        for (cik, accession, fiscal_year), checks in CHECKS.items():
            document = await fetch_instance_document(cik, accession)
            facts = parse_instance(document, accession_number=accession, fiscal_year=fiscal_year)
            for brand_key, year, period_end, dims in checks:
                filed = {
                    Decimal(str(f.value))
                    for f in facts
                    if f.concept == CONCEPT
                    and str(f.period_end)[:10] == period_end
                    and (f.dimensions or {}) == dims
                }
                stored = (
                    await session.execute(
                        select(BrandFigure.value, BrandFigure.basis, BrandFigure.caveats).where(
                            BrandFigure.issuer_cik == cik,
                            BrandFigure.brand_key == brand_key,
                            BrandFigure.fiscal_year == year,
                        )
                    )
                ).one()
                ok = filed == {Decimal(str(stored.value))}
                mismatches += not ok
                print(
                    f"{'OK  ' if ok else 'DIFF'} {cik} {brand_key} FY{year}: filed {sorted(filed)} "
                    f"stored {stored.value} basis={stored.basis} caveats={stored.caveats}"
                )
    if mismatches:
        raise SystemExit(f"{mismatches} mismatch(es)")


if __name__ == "__main__":
    asyncio.run(main())
