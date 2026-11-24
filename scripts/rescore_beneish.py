"""Re-score Beneish from the canonical facts already stored, with no network.

A mapping change that moves a Beneish input (Ops 5: sga) leaves the stored
score runs on the old figures until the nightly pipeline runs, and the pipeline
fetches live from EDGAR. This re-runs only `score_beneish` over every scoreable
year, reading the current mapping version's facts.

    make py F=scripts/rescore_beneish.py                 # every issuer
    make py F=scripts/rescore_beneish.py ARGS=0001594805 # one or more CIKs

Prints the latest year's M-score per issuer, so the change is read off the
output rather than assumed.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Issuer
from pipeline.run import scoreable_years
from scoring.runner import score_beneish


async def run(ciks: list[str]) -> None:
    async with get_sessionmaker()() as session:
        issuers = (await session.execute(select(Issuer).order_by(Issuer.ticker))).scalars().all()
        for issuer in issuers:
            if ciks and issuer.cik not in ciks:
                continue
            latest = None
            for year in await scoreable_years(session, issuer.cik):
                latest = (year, await score_beneish(session, issuer.cik, year))
            await session.commit()
            if latest:
                year, run_ = latest
                print(f"{issuer.ticker:5} FY{year} M={run_.aggregate_value}")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
