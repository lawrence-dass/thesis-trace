"""Load canonical facts into a per-(concept, fiscal_year) lookup for scoring."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, RawFact
from canonicalization.mappings import SOURCE_MISMATCH


class FactLookup:
    """Canonical values keyed by (canonical_concept, fiscal_year)."""

    def __init__(
        self,
        values: dict[tuple[str, int], Decimal],
        fact_ids: dict[tuple[str, int], object],
        units: dict[tuple[str, int], str | None],
        mismatches: dict[tuple[str, int], str] | None = None,
    ):
        self._values = values
        self._fact_ids = fact_ids
        self._units = units
        self._mismatches = mismatches or {}

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

    def mismatch_reasons(self, concepts, fiscal_years) -> list[str]:
        """Distinct reasons why the given inputs are not strictly comparable across
        filers (see `like_for_like` in the mapping specs).

        Used to ANNOTATE a score, never to alter or suppress one — the same posture
        as Beneish's out-of-calibration guard. A value from a by-nature variant tag
        is correct for its filer; what it is not is directly comparable to a
        by-function filer's, and ThesisTrace shows models side by side.
        """
        reasons: list[str] = []
        for concept in concepts:
            for fiscal_year in fiscal_years:
                reason = self._mismatches.get((concept, fiscal_year))
                if reason and reason not in reasons:
                    reasons.append(reason)
        return reasons


async def load_facts(session: AsyncSession, issuer_cik: str, *, mapping_version: str) -> FactLookup:
    rows = (
        await session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == issuer_cik,
                CanonicalFact.mapping_version == mapping_version,
                CanonicalFact.superseded.is_(False),  # current facts only (AD-6)
            )
        )
    ).scalars().all()
    values = {(r.canonical_concept, r.fiscal_year): Decimal(str(r.value)) for r in rows}
    fact_ids = {(r.canonical_concept, r.fiscal_year): r.id for r in rows}
    units = {(r.canonical_concept, r.fiscal_year): r.unit for r in rows}

    # Which selected facts came from a source tag that measures something different
    # from the concept's primary source. Only resolved when some rule declares one,
    # so the common case costs no extra query.
    mismatches: dict[tuple[str, int], str] = {}
    if SOURCE_MISMATCH:
        raw_ids = {r.selected_from_raw_fact_id for r in rows if r.selected_from_raw_fact_id}
        if raw_ids:
            source_of = {
                raw_id: (taxonomy, concept)
                for raw_id, taxonomy, concept in (
                    await session.execute(
                        select(RawFact.id, RawFact.taxonomy, RawFact.concept).where(
                            RawFact.id.in_(raw_ids)
                        )
                    )
                ).all()
            }
            for r in rows:
                key = source_of.get(r.selected_from_raw_fact_id)
                reason = SOURCE_MISMATCH.get(key) if key else None
                if reason:
                    mismatches[(r.canonical_concept, r.fiscal_year)] = reason

    return FactLookup(values, fact_ids, units, mismatches)
