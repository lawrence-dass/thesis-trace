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

from decimal import Decimal

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import CanonicalMemberFact, Issuer
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import MAPPING_VERSION, seed_concept_mappings


def _version_sort_key(version: str) -> tuple[int, str]:
    """`concepts_v9` sorts before `concepts_v18`, which a string sort gets wrong."""
    head, _, tail = version.rpartition("_v")
    return (int(tail), head) if tail.isdigit() else (-1, version)


async def _current_rows(session, version: str) -> dict[tuple, tuple]:
    """(issuer, concept, member, context, year) -> the row's value AND provenance.

    The compared payload carries everything a reader of the row would rely on,
    not just the figure. An earlier version compared `float(row.value)` alone and
    reported IDENTICAL, which was a weaker claim than it sounded:

    * `float()` on a NUMERIC(28,6) loses precision past ~15 significant digits,
      so two genuinely different Decimals could compare equal (AD-15 exists to
      keep these out of binary floats in the first place).
    * Omitting accession_number, period_end, unit, member_as_filed, axis_as_filed
      and dimensions meant a row whose FIGURE was unchanged but whose provenance
      had moved — a different filing selected, a different member spelling
      recorded — read as identical. AD-19 makes provenance part of the fact.
    """
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
        ): (
            Decimal(str(row.value)),
            row.accession_number,
            row.period_end,
            row.unit,
            row.member_as_filed,
            row.axis_as_filed,
            tuple(sorted((row.dimensions or {}).items())),
        )
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
        print(f"\nCHANGED ({len(changed)}):")
        for key in changed[:20]:
            print(f"  {key}:\n    {previous}: {before[key]}\n    {current}: {after[key]}")

    if not (added or dropped or changed):
        print(
            "\nIDENTICAL — same rows, same values, same provenance "
            "(value as Decimal, plus accession, period end, unit, member/axis as filed, "
            "dimensions). The bump moved no figure."
        )


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

        # Ordered by VERSION IDENTITY, not by created_at. Re-running an older
        # version writes rows with a fresh created_at, which used to make it sort
        # as "latest" and compare the wrong pair — silently answering a different
        # question than the one asked.
        versions = sorted(
            (
                await session.execute(
                    select(CanonicalMemberFact.mapping_version)
                    .where(CanonicalMemberFact.superseded.is_(False))
                    .group_by(CanonicalMemberFact.mapping_version)
                )
            )
            .scalars()
            .all(),
            key=_version_sort_key,
        )
        if MAPPING_VERSION not in versions:
            print(f"\n{MAPPING_VERSION} wrote no current rows — nothing to compare.")
        elif len(versions) >= 2:
            current = MAPPING_VERSION
            previous = versions[versions.index(current) - 1]
            await _compare(session, previous, current)


if __name__ == "__main__":
    asyncio.run(main())
