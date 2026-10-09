"""Live spot-check of Story 13.5a's segment rows against two CPB filings.

Fetches exactly two Inline XBRL instances from www.sec.gov (named before fetching):
CPB 0000016732-25-000112 (FY2025: the NEW tags) and 0000016732-23-000109 (FY2023:
the OLD tags). Each check requires exactly one matching filed fact and compares it
with the current concepts_v20 canonical_member_facts row.

Run: make py F=scripts/spot_check_segments.py
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import CanonicalMemberFact
from canonicalization.mappings import MAPPING_VERSION
from ingestion.edgar import fetch_instance_document
from ingestion.inline_xbrl import parse_instance

CPB = "0000016732"
SEG = "us-gaap:StatementBusinessSegmentsAxis"
# accession, filing FY -> [(taxonomy, concept, member, period_end, canonical, member_key, year)]
CHECKS = {
    ("0000016732-25-000112", 2025): [
        ("cpb", "SegmentOperatingEarnings", "cpb:MealsBeveragesMember", "2025-08-03",
         "segment_operating_earnings", "meals_beverages", 2025),
        ("cpb", "SegmentExpenditureAdditionToPPE", "cpb:SnacksMember", "2025-08-03",
         "segment_capex", "snacks", 2025),
        ("us-gaap", "Revenues", "cpb:SnacksMember", "2025-08-03",
         "segment_revenue", "snacks", 2025),
    ],
    ("0000016732-23-000109", 2023): [
        ("us-gaap", "OperatingIncomeLoss", "cpb:SnacksMember", "2023-07-30",
         "segment_operating_earnings", "snacks", 2023),
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", "cpb:MealsBeveragesMember",
         "2023-07-30", "segment_capex", "meals_beverages", 2023),
    ],
}


async def main() -> None:
    mismatches = 0
    async with get_sessionmaker()() as session:
        for (accession, fiscal_year), checks in CHECKS.items():
            facts = parse_instance(
                await fetch_instance_document(CPB, accession),
                accession_number=accession, fiscal_year=fiscal_year,
            )
            for taxonomy, concept, member, end, canonical, member_key, year in checks:
                filed = [
                    Decimal(str(f.value)) for f in facts
                    if f.taxonomy == taxonomy and f.concept == concept
                    and str(f.period_end)[:10] == end and (f.dimensions or {}) == {SEG: member}
                ]
                stored = (await session.execute(
                    select(CanonicalMemberFact.value, CanonicalMemberFact.accession_number).where(
                        CanonicalMemberFact.issuer_cik == CPB,
                        CanonicalMemberFact.canonical_concept == canonical,
                        CanonicalMemberFact.member_key == member_key,
                        CanonicalMemberFact.fiscal_year == year,
                        CanonicalMemberFact.mapping_version == MAPPING_VERSION,
                        CanonicalMemberFact.superseded.is_(False),
                    )
                )).all()
                ok = len(filed) == 1 and len(stored) == 1 and filed[0] == Decimal(str(stored[0].value))
                mismatches += not ok
                print(f"{'OK  ' if ok else 'DIFF'} {taxonomy}:{concept} {member} FY{year}: "
                      f"filed {filed} stored {[(str(s.value), s.accession_number) for s in stored]}")
    if mismatches:
        raise SystemExit(f"{mismatches} mismatch(es)")


if __name__ == "__main__":
    asyncio.run(main())
