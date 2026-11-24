"""Ops 5: dismiss `sga` ambiguity issues that describe the retired G&A fallback.

Through concepts_v20, `sga` had exactly TWO sources: the filed SG&A total
(SellingGeneralAndAdministrativeExpense), then GeneralAndAdministrativeExpense. A
G&A conflict was therefore raised as an `sga` ambiguity. concepts_v21 never selects
sga from G&A; the same conflict is now raised under `general_and_administrative`.
Data-quality issues are write-only (project-context 2026-09-17, "a dedup is not a
retraction"), so the old row would stay open and show the conflict twice.

An issue records only its values, fiscal year and concept, never the source tags of
its candidates, so staleness has to be PROVEN from the raw facts, not matched by
coincidence (the Ops 5 review built a counterexample against a value-only rule). An
issue is stale only when ALL of these hold:

  1. It is `needs_review`. A `resolved` issue already carries someone's evidence and
     is never touched; a `dismissed` one is already closed.
  2. The issuer files NO annual SG&A total for a period ending in that fiscal year.
     With only two sources, every candidate then came from G&A. This is the proof,
     and it is what preserves a genuine conflict on filed totals.
  3. Every listed value equals an annual (350-380 day) USD G&A fact of that issuer
     whose period ends IN that fiscal year (canonicalization buckets on the period
     end's year). Corroboration that the conflict is the G&A one, exactly.

    make py F=scripts/dismiss_stale_sga_issues.py           # dry run: lists only
    make py F=scripts/dismiss_stale_sga_issues.py ARGS=--apply

Runs against DATABASE_URL. Status goes to `dismissed` with the reason added as
`detail.resolution`; an issue that already has one is skipped, never overwritten.
Nothing is deleted.
"""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ANNUAL = "(r.period_end - r.period_start) between 350 and 380 and r.unit = 'USD'"

FIND = text(
    f"""
    select q.id, i.ticker, q.detail
    from data_quality_issues q
    join filings f on f.accession_number = q.accession_number
    join issuers i on i.cik = f.issuer_cik
    where q.issue_type = 'ambiguous_selection'
      and q.status = 'needs_review'
      and q.detail->>'canonical_concept' = 'sga'
      and q.detail->'resolution' is null
      and jsonb_array_length(q.detail->'values') > 0
      -- 2. no filed SG&A total for that fiscal year: every candidate was G&A
      and not exists (
        select 1 from raw_facts r join filings rf on rf.accession_number = r.accession_number
        where rf.issuer_cik = f.issuer_cik
          and r.concept = 'SellingGeneralAndAdministrativeExpense'
          and {_ANNUAL}
          and extract(year from r.period_end) = (q.detail->>'fiscal_year')::int
      )
      -- 3. every value is a filed G&A figure for exactly that fiscal year
      and not exists (
        select 1 from jsonb_array_elements_text(q.detail->'values') v
        where not exists (
          select 1 from raw_facts r join filings rf on rf.accession_number = r.accession_number
          where rf.issuer_cik = f.issuer_cik
            and r.concept = 'GeneralAndAdministrativeExpense'
            and {_ANNUAL}
            and extract(year from r.period_end) = (q.detail->>'fiscal_year')::int
            and r.value = v::numeric
        )
      )
    order by i.ticker, q.detail->>'fiscal_year'
    """
)

RESOLUTION = (
    "Ops 5 (concepts_v21): this issuer files no SG&A total for the year, so every "
    "candidate came from the GeneralAndAdministrativeExpense fallback, and each value "
    "is a filed G&A figure. sga no longer selects from G&A; the same conflict is "
    "raised under general_and_administrative instead."
)


async def find_stale(session: AsyncSession) -> list[tuple]:
    return list((await session.execute(FIND)).all())


async def dismiss(session: AsyncSession, rows: list[tuple]) -> None:
    for issue_id, _ticker, _detail in rows:
        await session.execute(
            text(
                "update data_quality_issues set status = 'dismissed', updated_at = now(), "
                "detail = detail || cast(:extra as jsonb) "
                "where id = :id and status = 'needs_review' and detail->'resolution' is null"
            ),
            {"id": issue_id, "extra": json.dumps({"resolution": RESOLUTION})},
        )


async def run(apply: bool) -> None:
    from app.db import get_sessionmaker

    async with get_sessionmaker()() as session:
        rows = await find_stale(session)
        for _id, ticker, detail in rows:
            print(f"{'DISMISS' if apply else 'would dismiss'} {ticker} FY{detail['fiscal_year']} sga {detail['values']}")
        if apply:
            await dismiss(session, rows)
            await session.commit()
        print(f"{len(rows)} stale sga issue(s){'' if apply else ' (dry run; pass --apply to write)'}")


if __name__ == "__main__":
    asyncio.run(run("--apply" in sys.argv[1:]))
