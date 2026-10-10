"""Segment payloads: filed per-segment figures, keyed per segment (Story 13.5b).

13.5a lands each filed segment value in `canonical_member_facts`. This carries it
into `segment_payloads` on the write path (AD-1), one row per (issuer, axis,
member, concept, year, mapping_version) — the `brand_figures` pattern.

Nothing here is declared a second time (the conformance rule). Which concepts,
members and axis count as a filer's segments is read from what the pipeline
EXECUTES: `SEGMENT_MEMBERS` / `SEGMENT_AXES` and the dimensioned rules on that
axis. There is no formula spec because nothing is computed (decision D-k).
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalMemberFact, SegmentPayload
from canonicalization.mappings import (
    DIMENSIONED_RULES,
    MAPPING_VERSION,
    SEGMENT_AXES,
    SEGMENT_MEMBERS,
)

OK = "ok"
INSUFFICIENT = "insufficient_data"
_KEY_COLUMNS = frozenset(
    {"issuer_cik", "axis", "member_key", "canonical_concept", "fiscal_year", "mapping_version"}
)


def segment_inputs(issuer_cik: str) -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """axis -> (concepts its segment rules produce, declared segment member keys).

    Empty for a filer that declares no segments — QSR's segment-axis members are
    BRANDS (`segment_brand_members`) and never become payloads.
    """
    inputs: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for cik, axis in SEGMENT_AXES:
        if cik != issuer_cik:
            continue
        concepts = frozenset(
            rule.canonical_concept
            for rule in DIMENSIONED_RULES
            if rule.axis == axis and issuer_cik in rule.issuers
        )
        members = frozenset(
            m.member_key for m in SEGMENT_MEMBERS if m.issuer_cik == issuer_cik and m.axis == axis
        )
        inputs[axis] = (concepts, members)
    return inputs


def _qualifiers(row: CanonicalMemberFact, axis: str) -> list[str]:
    return sorted(f"{a}={m}" for a, m in (row.context_key or {}).items() if a != axis)


async def materialize_segment_payloads(session: AsyncSession, issuer_cik: str) -> dict[str, int]:
    """Write this issuer's segment payloads; return what happened."""
    groups: dict[tuple[str, str, str, int], list[CanonicalMemberFact]] = defaultdict(list)
    for axis, (concepts, members) in segment_inputs(issuer_cik).items():
        rows = (
            await session.execute(
                select(CanonicalMemberFact).where(
                    CanonicalMemberFact.issuer_cik == issuer_cik,
                    CanonicalMemberFact.axis_as_filed == axis,
                    CanonicalMemberFact.canonical_concept.in_(concepts),
                    CanonicalMemberFact.member_key.in_(members),
                    CanonicalMemberFact.mapping_version == MAPPING_VERSION,
                    CanonicalMemberFact.superseded.is_(False),
                )
            )
        ).scalars().all()
        for row in rows:
            groups[(axis, row.member_key, row.canonical_concept, row.fiscal_year)].append(row)

    written: list[tuple[str, str, str, int]] = []
    insufficient = 0
    for key, rows in sorted(groups.items()):
        axis, member_key, concept, year = key
        values = {
            "issuer_cik": issuer_cik,
            "axis": axis,
            "member_key": member_key,
            "canonical_concept": concept,
            "fiscal_year": year,
            "mapping_version": MAPPING_VERSION,
            "computed_at": func.now(),
        }
        qualified = sorted({q for row in rows for q in _qualifiers(row, axis)})
        if qualified or len(rows) != 1:
            # Never a pick (D-l): a breakdown within the segment is a different
            # measurement, so it vetoes the whole segment-year rather than sitting
            # silently beside the unqualified value.
            insufficient += 1
            reason = (
                f"context qualifier(s) {qualified} beside the segment value"
                if qualified
                else f"{len(rows)} unqualified rows for one segment-year"
            )
            values.update(
                period_end=None, value=None, unit=None, status=INSUFFICIENT,
                reason=reason[:512], source_member_fact_id=None,
                accession_number=None, member_as_filed=None,
            )
        else:
            (row,) = rows
            values.update(
                period_end=row.period_end,
                value=row.value,  # the filed amount, carried exactly
                unit=row.unit,
                status=OK,
                reason=None,
                source_member_fact_id=row.id,
                accession_number=row.accession_number,
                member_as_filed=row.member_as_filed,
            )
        statement = pg_insert(SegmentPayload).values(**values)
        # Refresh every non-key column, so a segment-year that turned insufficient
        # cannot keep yesterday's value beside today's reason.
        statement = statement.on_conflict_do_update(
            constraint="uq_segment_payloads_key",
            set_={c: statement.excluded[c] for c in values if c not in _KEY_COLUMNS},
        )
        await session.execute(statement)
        written.append(key)

    # A segment-year that stopped resolving under the SAME mapping version must not
    # linger. Other mapping versions are history and are never touched (AD-2).
    stale = delete(SegmentPayload).where(
        SegmentPayload.issuer_cik == issuer_cik,
        SegmentPayload.mapping_version == MAPPING_VERSION,
    )
    if written:
        stale = stale.where(
            tuple_(
                SegmentPayload.axis,
                SegmentPayload.member_key,
                SegmentPayload.canonical_concept,
                SegmentPayload.fiscal_year,
            ).not_in(written)
        )
    removed = (await session.execute(stale)).rowcount or 0
    return {"written": len(written), "removed": removed, "insufficient": insufficient}
