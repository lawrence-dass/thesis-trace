"""Story 13.5a evidence: per-FILING first appearance, overlap-year equality, members per year.

From the dev store's stored Inline XBRL (no fetch). Answers three questions:
  1. In which ORIGINAL 10-K does each switched tag first appear (vs its period years)?
  2. In the overlap years, do old and new tags carry identical values per member?
     Equal values in every overlap year prove the switch is a relabel.
  3. Which segment members appear in each period year (CPB)?

Run: make py F=scripts/segment_switch_evidence.py
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Filing, Issuer, RawFact

AXIS = "us-gaap:StatementBusinessSegmentsAxis"
PAIRS = {
    "CPB": [("OperatingIncomeLoss", "SegmentOperatingEarnings"),
            ("PaymentsToAcquirePropertyPlantAndEquipment", "SegmentExpenditureAdditionToPPE")],
    "QSR": [("PaymentsToAcquirePropertyPlantAndEquipment", "SegmentExpenditureAdditionToLongLivedAssets")],
}
FIRST_SEEN = {
    "CPB": ["SegmentOperatingEarnings", "SegmentExpenditureAdditionToPPE",
            "CostOfGoodsAndServicesSold", "SegmentReportingOtherItemAmount"],
    "QSR": ["SegmentExpenditureAdditionToLongLivedAssets", "CostOfGoodsAndServicesSold"],
    "ZTS": ["CostOfGoodsAndServicesSold"],
}


async def facts(session, ticker):
    issuer = (await session.execute(select(Issuer).where(Issuer.ticker == ticker))).scalar_one()
    return (await session.execute(
        select(RawFact.concept, RawFact.period_start, RawFact.period_end, RawFact.value,
               RawFact.dimensions, Filing.accession_number, Filing.fiscal_year)
        .join(Filing, Filing.accession_number == RawFact.accession_number)
        .where(Filing.issuer_cik == issuer.cik, RawFact.source == "inline_xbrl",
               Filing.form_type == "10-K")
    )).all()


def annual_on_axis(rows, single_axis=True):
    for concept, start, end, value, dims, accn, filing_fy in rows:
        if not dims or AXIS not in dims or (single_axis and len(dims) != 1):
            continue
        if start is not None and (end - start).days < 300:
            continue
        yield concept, end.year, dims[AXIS], value, accn, filing_fy


async def main() -> None:
    async with get_sessionmaker()() as session:
        for ticker in ("CPB", "QSR", "ZTS"):
            raw = await facts(session, ticker)
            rows = list(annual_on_axis(raw))
            any_axis = list(annual_on_axis(raw, single_axis=False))
            print(f"\n== {ticker}")
            for concept in FIRST_SEEN[ticker]:
                filings = sorted({(fy, accn) for c, _, _, _, accn, fy in any_axis if c == concept})
                periods = sorted({y for c, y, *_ in any_axis if c == concept})
                first = filings[0] if filings else None
                print(f"  {concept}: first in filing FY{first[0] if first else '-'} "
                      f"({first[1] if first else '-'}); period years {periods}")
            for old, new in PAIRS.get(ticker, []):
                values = defaultdict(lambda: defaultdict(set))  # (year, member) -> concept -> values
                for c, y, member, value, *_ in rows:
                    if c in (old, new):
                        values[(y, member)][c].add(value)
                overlap = sorted(k for k, v in values.items() if old in v and new in v)
                equal = [k for k in overlap if values[k][old] == values[k][new]]
                print(f"  overlap {old} vs {new}: {len(overlap)} (year, member) pairs, "
                      f"{len(equal)} equal")
                for k in overlap:
                    if k not in equal:
                        print(f"    DIFF {k}: {old}={sorted(values[k][old])} {new}={sorted(values[k][new])}")
            if ticker == "CPB":
                by_year = defaultdict(set)
                for c, y, member, *_ in rows:
                    if c == "Revenues":
                        by_year[y].add(member)
                for y in sorted(by_year):
                    print(f"  Revenues members {y}: {sorted(by_year[y])}")


if __name__ == "__main__":
    asyncio.run(main())
