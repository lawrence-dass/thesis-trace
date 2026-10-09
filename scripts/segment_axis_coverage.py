"""Per-year coverage of concepts tagged on the segment axis, from stored Inline XBRL.

Story 13.5a's coverage check. Company Facts carries no dimensions
(company_facts_api_carries_no_segment_dimensions), so the source is the dev
store's own `raw_facts` with source = 'inline_xbrl' — instances already fetched
from EDGAR by the pipeline. Buckets on the fact's own period end, never `fy`.

Run: make py F=scripts/segment_axis_coverage.py [ARGS="CPB QSR ZTS"]
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Filing, Issuer, RawFact

SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"


async def main(tickers: list[str]) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        for ticker in tickers:
            issuer = (await session.execute(select(Issuer).where(Issuer.ticker == ticker))).scalar_one()
            rows = (await session.execute(
                select(RawFact.taxonomy, RawFact.concept, RawFact.period_start, RawFact.period_end,
                       RawFact.dimensions, Filing.form_type)
                .join(Filing, Filing.accession_number == RawFact.accession_number)
                .where(Filing.issuer_cik == issuer.cik, RawFact.source == "inline_xbrl")
            )).all()
            # concept -> set of period-end years where it appears on the segment axis
            years: dict[str, set[int]] = defaultdict(set)
            members: set[str] = set()
            for taxonomy, concept, start, end, dims, form in rows:
                if form != "10-K" or not dims or SEGMENT_AXIS not in dims:
                    continue
                if start is not None and (end - start).days < 300:
                    continue  # annual figures only
                years[f"{taxonomy}:{concept}"].add(end.year)
                members.add(dims[SEGMENT_AXIS])
            print(f"\n== {ticker} ({issuer.cik}) — {len(years)} concepts on {SEGMENT_AXIS}")
            print(f"   members: {sorted(members)}")
            for concept in sorted(years):
                print(f"   {concept:<70} {sorted(years[concept])}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["CPB", "QSR", "ZTS"]))
