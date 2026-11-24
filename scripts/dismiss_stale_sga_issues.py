"""Ops 5: dismiss `sga` ambiguity issues that describe the retired G&A fallback.

Through concepts_v20, `sga` fell back to GeneralAndAdministrativeExpense, so a
G&A conflict was raised as an `sga` ambiguity. concepts_v21 never selects sga
from G&A; the same conflict is now raised under `general_and_administrative`.
Data-quality issues are write-only (project-context 2026-09-17, "a dedup is not
a retraction"), so the old row would stay open and show the conflict twice, once
under a label that no longer describes any selection.

Stale, by rule rather than by id: an OPEN `ambiguous_selection` on `sga` whose
EVERY listed value equals a GeneralAndAdministrativeExpense fact the same issuer
filed for a period ending in that fiscal year. A genuine conflict on the filed SG&A
total (NKE FY2009, NVDA FY2014) fails that test and is left alone.

    make py F=scripts/dismiss_stale_sga_issues.py           # dry run: lists only
    make py F=scripts/dismiss_stale_sga_issues.py ARGS=--apply

Runs against DATABASE_URL. Status goes to `dismissed` with the reason recorded in
`detail.resolution`; nothing is deleted.
"""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import text

from app.db import get_sessionmaker

FIND = text(
    """
    select q.id, i.ticker, q.detail
    from data_quality_issues q
    join filings f on f.accession_number = q.accession_number
    join issuers i on i.cik = f.issuer_cik
    where q.issue_type = 'ambiguous_selection'
      and q.status <> 'dismissed'
      and q.detail->>'canonical_concept' = 'sga'
      and not exists (
        select 1 from jsonb_array_elements_text(q.detail->'values') v
        where not exists (
          select 1 from raw_facts r join filings rf on rf.accession_number = r.accession_number
          where rf.issuer_cik = f.issuer_cik
            and r.concept = 'GeneralAndAdministrativeExpense'
            and r.value = v::numeric
            and extract(year from r.period_end) between (q.detail->>'fiscal_year')::int - 1
                                                    and (q.detail->>'fiscal_year')::int + 1
        )
      )
    order by i.ticker, q.detail->>'fiscal_year'
    """
)

RESOLUTION = (
    "Ops 5 (concepts_v21): every value in this conflict is a G&A figure, raised while "
    "sga fell back to GeneralAndAdministrativeExpense. sga no longer selects from G&A; "
    "the same conflict is raised under general_and_administrative instead."
)


async def run(apply: bool) -> None:
    async with get_sessionmaker()() as session:
        rows = (await session.execute(FIND)).all()
        for issue_id, ticker, detail in rows:
            print(f"{'DISMISS' if apply else 'would dismiss'} {ticker} FY{detail['fiscal_year']} sga {detail['values']}")
            if apply:
                await session.execute(
                    text(
                        "update data_quality_issues set status = 'dismissed', updated_at = now(), "
                        "detail = detail || cast(:extra as jsonb) where id = :id"
                    ),
                    {"id": issue_id, "extra": json.dumps({"resolution": RESOLUTION})},
                )
        if apply:
            await session.commit()
        print(f"{len(rows)} stale sga issue(s){'' if apply else ' (dry run; pass --apply to write)'}")


if __name__ == "__main__":
    asyncio.run(run("--apply" in sys.argv[1:]))
