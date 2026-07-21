"""Load canonical facts into a per-(concept, fiscal_year) lookup for scoring."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact


class FactLookup:
    """Canonical values keyed by (canonical_concept, fiscal_year)."""

    def __init__(self, values: dict[tuple[str, int], Decimal], fact_ids: dict[tuple[str, int], object]):
        self._values = values
        self._fact_ids = fact_ids

    def get(self, concept: str, fiscal_year: int) -> Decimal | None:
        return self._values.get((concept, fiscal_year))

    def fact_id(self, concept: str, fiscal_year: int):
        return self._fact_ids.get((concept, fiscal_year))

    def fiscal_years(self) -> set[int]:
        return {fy for (_concept, fy) in self._values}


async def load_facts(session: AsyncSession, issuer_cik: str, *, mapping_version: str) -> FactLookup:
    rows = (
        await session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == issuer_cik,
                CanonicalFact.mapping_version == mapping_version,
            )
        )
    ).scalars().all()
    values = {(r.canonical_concept, r.fiscal_year): Decimal(str(r.value)) for r in rows}
    fact_ids = {(r.canonical_concept, r.fiscal_year): r.id for r in rows}
    return FactLookup(values, fact_ids)
