"""Resolve every stored member row to a brand, against the real dev store.

    make py F=scripts/verify_brand_identity.py

Story 13.4a's verification. The DB test in `tests/test_brand_identity.py` runs
against a seeded test database that holds only the rows its fixtures create; this
runs the same resolution over what is actually stored, which is the only place a
filer's real tagging shows up.

Prints one line per (filer, brand), plus every row that resolves to nothing. A
row in the unresolved list is not automatically a defect — AD-16 says an unknown
brand is `insufficient_data` — but it IS a row no consumer can name, so each one
has to be a decision somebody made rather than a gap nobody saw.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import CanonicalMemberFact
from canonicalization.mappings import MAPPING_VERSION
from canonicalization.mappings.brand_identity import BrandUnresolved, resolve_brand_identity


async def main() -> None:
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise SystemExit("DATABASE_URL is not configured.")

    async with sessionmaker() as session:
        rows = list(
            (
                await session.execute(
                    select(CanonicalMemberFact).where(
                        CanonicalMemberFact.mapping_version == MAPPING_VERSION,
                        CanonicalMemberFact.superseded.is_(False),
                    )
                )
            ).scalars()
        )

    resolved: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    unresolved: list[str] = []
    for row in rows:
        identity = resolve_brand_identity(row.issuer_cik, row.member_key, row.context_key)
        if isinstance(identity, BrandUnresolved):
            unresolved.append(
                f"{row.issuer_cik} {row.canonical_concept} FY{row.fiscal_year}: {identity.reason}"
            )
            continue
        resolved[(identity.issuer_cik, identity.label, identity.kind)].append(row.fiscal_year)

    print(f"{MAPPING_VERSION}: {len(rows)} current member rows\n")
    print(f"{'filer':<12} {'brand':<36} {'kind':<12} years")
    for (cik, label, kind), years in sorted(resolved.items()):
        span = f"FY{min(years)}-FY{max(years)}" if min(years) != max(years) else f"FY{years[0]}"
        plural = "row" if len(years) == 1 else "rows"
        print(f"{cik:<12} {label:<36} {kind:<12} {span} ({len(years)} {plural})")

    named = sum(len(y) for (_, _, kind), y in resolved.items() if kind == "named_brand")
    print(f"\nresolved: {len(rows) - len(unresolved)}/{len(rows)} rows, {named} on a named brand")
    if unresolved:
        print(f"\nUNRESOLVED ({len(unresolved)}):")
        for line in unresolved:
            print(f"  {line}")
    else:
        print("unresolved: none — every stored row can be named")


if __name__ == "__main__":
    asyncio.run(main())
