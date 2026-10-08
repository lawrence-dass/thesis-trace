"""`make brands`: materialize per-brand figures for every stored issuer.

Reads only what the database already holds — no EDGAR fetch — so it is safe to
run against the dev store and right after a deploy, when the feature is otherwise
absent until the 06:00 cron (AD-1's standing consequence). Idempotent.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Issuer
from brands.store import materialize_brand_carrying_values


async def main() -> None:
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("DATABASE_URL is not configured.")
    async with sessionmaker() as session:
        issuers = (await session.execute(select(Issuer).order_by(Issuer.ticker))).scalars().all()
        for issuer in issuers:
            summary = await materialize_brand_carrying_values(session, issuer.cik)
            if any(summary.values()):
                print(f"{issuer.ticker}: {summary}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
