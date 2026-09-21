"""Re-run canonicalization over the raw facts already stored, with no network.

    make py F=scripts/recanonicalize.py                 # every issuer
    make py F=scripts/recanonicalize.py ARGS=0000016732 # one or more CIKs

What it is for: a mapping_version bump writes new rows from the SAME raw facts,
and the question that has to be answered before a bump ships is whether the new
version reproduces the old one. `make pipeline` cannot answer it — that path
fetches live from EDGAR, which is both a permission ask and a different question.

Prints a per-issuer count and then a comparison of the two most recent mapping
versions in `canonical_member_facts`, so "the bump moved nothing" is something
you read off the output rather than assume. Idempotent: running it twice adds
nothing the second time (`canonicalize_issuer` skips a key already written while
the same raw fact still wins its selection).
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from app.db import get_sessionmaker
from app.models import CanonicalMemberFact, Issuer
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import MAPPING_VERSION, seed_concept_mappings


async def _current_rows(session, version: str) -> dict[tuple, float]:
    """(issuer, concept, member, context, year) -> value, for one version."""
    rows = (
        await session.execute(
            select(CanonicalMemberFact).where(
                CanonicalMemberFact.mapping_version == version,
                CanonicalMemberFact.superseded.is_(False),
            )
        )
    ).scalars()
    return {
        (
            row.issuer_cik,
            row.canonical_concept,
            row.member_key,
            tuple(sorted((row.context_key or {}).items())),
            row.fiscal_year,
        ): float(row.value)
        for row in rows
    }


async def _compare(session, previous: str, current: str) -> None:
    before = await _current_rows(session, previous)
    after = await _current_rows(session, current)

    print(f"\n{previous}: {len(before)} current rows")
    print(f"{current}: {len(after)} current rows")

    added = sorted(set(after) - set(before))
    dropped = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])

    for label, keys in (("only in " + current, added), ("only in " + previous, dropped)):
        if keys:
            print(f"\n{label} ({len(keys)}):")
            for key in keys[:20]:
                print(f"  {key}")
    if changed:
        print(f"\nVALUE CHANGED ({len(changed)}):")
        for key in changed[:20]:
            print(f"  {key}: {before[key]} -> {after[key]}")

    if not (added or dropped or changed):
        print("\nIDENTICAL — same rows, same values. The bump moved no figure.")


async def main() -> None:
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise SystemExit("DATABASE_URL is not configured.")

    requested = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    async with sessionmaker() as session:
        if requested:
            ciks = requested
        else:
            ciks = list(
                (await session.execute(select(Issuer.cik).order_by(Issuer.cik))).scalars()
            )

        await seed_concept_mappings(session)
        print(f"mapping_version: {MAPPING_VERSION}")
        for cik in ciks:
            counts = await canonicalize_issuer(session, cik)
            interesting = {k: v for k, v in counts.items() if v}
            print(f"  {cik}: {interesting or 'no change'}")
        await session.commit()

        versions = list(
            (
                await session.execute(
                    select(CanonicalMemberFact.mapping_version)
                    .where(CanonicalMemberFact.superseded.is_(False))
                    .group_by(CanonicalMemberFact.mapping_version)
                    .order_by(func.max(CanonicalMemberFact.created_at))
                )
            ).scalars()
        )
        if len(versions) >= 2:
            await _compare(session, versions[-2], versions[-1])


if __name__ == "__main__":
    asyncio.run(main())
