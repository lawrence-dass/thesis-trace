"""Load canonical facts into a per-(concept, fiscal_year) lookup for scoring."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact


class FactLookup:
    """Canonical values keyed by (canonical_concept, fiscal_year)."""

    def __init__(
        self,
        values: dict[tuple[str, int], Decimal],
        fact_ids: dict[tuple[str, int], object],
        units: dict[tuple[str, int], str | None],
    ):
        self._values = values
        self._fact_ids = fact_ids
        self._units = units

    def get(self, concept: str, fiscal_year: int) -> Decimal | None:
        return self._values.get((concept, fiscal_year))

    def fact_id(self, concept: str, fiscal_year: int):
        return self._fact_ids.get((concept, fiscal_year))

    def unit(self, concept: str, fiscal_year: int) -> str | None:
        """The reporting currency/unit of a canonical fact (e.g. 'USD', 'CAD') —
        used to detect a non-USD filer before combining with a USD market price
        (AD-11 currency fix, 2026-07-23)."""
        return self._units.get((concept, fiscal_year))

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
    units = {(r.canonical_concept, r.fiscal_year): r.unit for r in rows}
    return FactLookup(values, fact_ids, units)
