"""Segment payloads, materialized into their own store (Story 13.5b).

DB tests seed `canonical_member_facts` rows shaped like the dev store's segment
rows (single-axis contexts on CPB's segment axis, concepts_v20) and assert the ROW
COUNT before anything about the rows.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalMemberFact, SegmentPayload
from canonicalization.mappings import MAPPING_VERSION
from segments.store import INSUFFICIENT, OK, materialize_segment_payloads, segment_inputs
from tests.conftest import requires_db
from tests.test_brand_figures import QSR, SEGMENT_AXIS, _cpb, _filing, _issuer

CPB = "0000016732"
MEALS = "cpb:MealsBeveragesMember"
SNACKS = "cpb:SnacksMember"
REVENUE = "segment_revenue"
EARNINGS = "segment_operating_earnings"
CAPEX = "segment_capex"
# CPB's FY2025 10-K fixture: 3 concepts x 2 segments x FY2023-2025 (current year
# plus two comparatives) — derived from 13.5a's per-period evidence, not the run.
EXPECTED_PIPELINE_PAYLOADS = 18


def _seg(
    accn: str,
    concept: str,
    member_key: str,
    year: int,
    value,
    *,
    as_filed: str = MEALS,
    extra: dict[str, str] | None = None,
    mapping_version: str = MAPPING_VERSION,
    superseded: bool = False,
    cik: str = CPB,
) -> CanonicalMemberFact:
    """A stored segment row shaped like the dev store's (mapped axis normalized)."""
    return CanonicalMemberFact(
        issuer_cik=cik,
        accession_number=accn,
        canonical_concept=concept,
        member_key=member_key,
        member_as_filed=as_filed,
        axis_as_filed=SEGMENT_AXIS,
        dimensions={SEGMENT_AXIS: as_filed, **(extra or {})},
        context_key={SEGMENT_AXIS: member_key, **(extra or {})},
        fiscal_year=year,
        period_end=date(year, 7, 31),
        value=value,
        unit="USD",
        mapping_version=mapping_version,
        superseded=superseded,
    )


async def _payloads(session, cik: str | None = CPB) -> list[SegmentPayload]:
    query = select(SegmentPayload).order_by(
        SegmentPayload.canonical_concept, SegmentPayload.member_key, SegmentPayload.fiscal_year,
        SegmentPayload.mapping_version,
    )
    if cik:
        query = query.where(SegmentPayload.issuer_cik == cik)
    return list((await session.execute(query)).scalars().all())


# --- inputs come from executed declarations (AC 2) ---------------------------


def test_cpbs_inputs_are_its_segment_rules_and_members() -> None:
    inputs = segment_inputs(CPB)
    assert list(inputs) == [SEGMENT_AXIS]
    concepts, members = inputs[SEGMENT_AXIS]
    assert concepts == {REVENUE, EARNINGS, CAPEX}
    assert members == {"meals_beverages", "snacks"}


def test_a_filer_whose_segment_axis_carries_brands_has_no_segment_inputs() -> None:
    # QSR files brands on the segment axis (segment_brand_members): never payloads.
    assert segment_inputs(QSR) == {}


# --- materialization (AC 1, 3) -----------------------------------------------


@requires_db
async def test_each_filed_segment_year_lands_once_with_its_provenance(db_session) -> None:
    accns = await _cpb(db_session, years=(2024, 2025))
    sources = [
        _seg(accns[2025], REVENUE, "meals_beverages", 2025, Decimal("4567.123456")),
        _seg(accns[2025], REVENUE, "snacks", 2025, 4_000, as_filed=SNACKS),
        _seg(accns[2024], EARNINGS, "meals_beverages", 2024, -12),
        _seg(accns[2025], CAPEX, "snacks", 2025, 0, as_filed=SNACKS),
    ]
    db_session.add_all(sources)
    await db_session.flush()

    counts = await materialize_segment_payloads(db_session, CPB)
    assert counts == {"written": 4, "removed": 0, "insufficient": 0}
    rows = await _payloads(db_session)
    assert len(rows) == 4
    by_source = {s.id: s for s in sources}
    for row in rows:
        source = by_source[row.source_member_fact_id]
        assert row.status == OK and row.reason is None
        assert (row.axis, row.member_key, row.canonical_concept, row.fiscal_year) == (
            SEGMENT_AXIS, source.member_key, source.canonical_concept, source.fiscal_year,
        )
        # Carried exactly — a fractional, a negative and a zero all survive.
        assert Decimal(str(row.value)) == Decimal(str(source.value))
        assert (row.accession_number, row.member_as_filed, row.period_end, row.unit) == (
            source.accession_number, source.member_as_filed, source.period_end, "USD",
        )
        assert row.mapping_version == MAPPING_VERSION


@requires_db
async def test_a_qualified_row_vetoes_its_segment_year(db_session) -> None:
    """D-l: a breakdown within the segment never sits silently beside its value."""
    accns = await _cpb(db_session, years=(2025,))
    db_session.add_all([
        _seg(accns[2025], REVENUE, "meals_beverages", 2025, 100),
        _seg(accns[2025], REVENUE, "meals_beverages", 2025, 60,
             extra={"srt:StatementGeographicalAxis": "country:US"}),
        _seg(accns[2025], REVENUE, "snacks", 2025, 200, as_filed=SNACKS),
    ])
    await db_session.flush()

    counts = await materialize_segment_payloads(db_session, CPB)
    assert counts == {"written": 2, "removed": 0, "insufficient": 1}
    rows = await _payloads(db_session)
    assert len(rows) == 2
    meals, snacks = rows
    assert (meals.member_key, meals.status, meals.value, meals.source_member_fact_id) == (
        "meals_beverages", INSUFFICIENT, None, None,
    )
    assert "srt:StatementGeographicalAxis" in meals.reason
    assert (meals.accession_number, meals.member_as_filed) == (None, None)
    assert (snacks.status, snacks.value) == (OK, 200)


@requires_db
async def test_only_segment_rows_of_the_running_version_become_payloads(db_session) -> None:
    accns = await _cpb(db_session, years=(2025,))
    await _issuer(db_session, QSR, "QSR")
    await _filing(db_session, QSR, "0001618756-25-000010", 2025)
    db_session.add_all([
        _seg(accns[2025], REVENUE, "meals_beverages", 2025, 100),
        # Superseded, another mapping version, a concept no segment rule makes, an
        # undeclared member key, and QSR's segment-axis BRAND: none is a payload.
        _seg(accns[2025], REVENUE, "snacks", 2025, 1, as_filed=SNACKS, superseded=True),
        _seg(accns[2025], EARNINGS, "snacks", 2025, 2, as_filed=SNACKS,
             mapping_version="concepts_v19"),
        _seg(accns[2025], "revenue", "meals_beverages", 2025, 3),
        _seg(accns[2025], REVENUE, "corporate", 2025, 4, as_filed="us-gaap:CorporateMember"),
        _seg("0001618756-25-000010", REVENUE, "tim_hortons", 2025, 5,
             as_filed="qsr:THMember", cik=QSR),
    ])
    await db_session.flush()

    assert await materialize_segment_payloads(db_session, QSR) == {
        "written": 0, "removed": 0, "insufficient": 0,
    }
    counts = await materialize_segment_payloads(db_session, CPB)
    assert counts == {"written": 1, "removed": 0, "insufficient": 0}
    rows = await _payloads(db_session, cik=None)
    assert len(rows) == 1
    assert (rows[0].member_key, rows[0].canonical_concept, rows[0].value) == (
        "meals_beverages", REVENUE, 100,
    )


# --- idempotency (AC 4) ------------------------------------------------------


@requires_db
async def test_a_second_run_writes_the_same_rows_and_changes_nothing(db_session) -> None:
    accns = await _cpb(db_session, years=(2025,))
    db_session.add_all([
        _seg(accns[2025], REVENUE, "meals_beverages", 2025, 100),
        _seg(accns[2025], CAPEX, "snacks", 2025, 7, as_filed=SNACKS),
    ])
    await db_session.flush()

    await materialize_segment_payloads(db_session, CPB)
    first = {(r.id, r.member_key, r.canonical_concept, r.value, r.source_member_fact_id)
             for r in await _payloads(db_session)}
    assert len(first) == 2
    counts = await materialize_segment_payloads(db_session, CPB)
    assert counts == {"written": 2, "removed": 0, "insufficient": 0}
    db_session.expire_all()
    second = {(r.id, r.member_key, r.canonical_concept, r.value, r.source_member_fact_id)
              for r in await _payloads(db_session)}
    assert second == first


@requires_db
async def test_a_segment_year_that_stops_resolving_is_removed(db_session) -> None:
    accns = await _cpb(db_session, years=(2024, 2025))
    gone = _seg(accns[2024], REVENUE, "meals_beverages", 2024, 90)
    db_session.add_all([gone, _seg(accns[2025], REVENUE, "meals_beverages", 2025, 100)])
    await db_session.flush()
    await materialize_segment_payloads(db_session, CPB)
    assert len(await _payloads(db_session)) == 2

    gone.superseded = True
    await db_session.flush()
    counts = await materialize_segment_payloads(db_session, CPB)
    assert counts == {"written": 1, "removed": 1, "insufficient": 0}
    rows = await _payloads(db_session)
    assert len(rows) == 1
    assert rows[0].fiscal_year == 2025


@requires_db
async def test_a_value_that_turns_insufficient_loses_every_source_field(db_session) -> None:
    accns = await _cpb(db_session, years=(2025,))
    db_session.add(_seg(accns[2025], REVENUE, "meals_beverages", 2025, 100))
    await db_session.flush()
    await materialize_segment_payloads(db_session, CPB)

    db_session.add(_seg(accns[2025], REVENUE, "meals_beverages", 2025, 60,
                        extra={"srt:ProductOrServiceAxis": "cpb:SoupMember"}))
    await db_session.flush()
    await materialize_segment_payloads(db_session, CPB)
    db_session.expire_all()
    rows = await _payloads(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert (row.status, row.value, row.unit, row.period_end) == (INSUFFICIENT, None, None, None)
    assert (row.source_member_fact_id, row.accession_number, row.member_as_filed) == (
        None, None, None,
    )


@requires_db
async def test_rows_under_another_mapping_version_are_never_touched(db_session) -> None:
    accns = await _cpb(db_session, years=(2019, 2025))
    db_session.add(_seg(accns[2025], REVENUE, "meals_beverages", 2025, 100))
    await db_session.flush()
    # A historical payload at a DIFFERENT segment-year than the run writes, so the
    # test cannot pass merely because the upsert key differs (13.4c's lesson).
    await db_session.execute(insert(SegmentPayload).values(
        issuer_cik=CPB, axis=SEGMENT_AXIS, member_key="snacks", canonical_concept=REVENUE,
        fiscal_year=2019, mapping_version="concepts_v19", status=OK, value=1,
    ))

    counts = await materialize_segment_payloads(db_session, CPB)
    assert counts == {"written": 1, "removed": 0, "insufficient": 0}
    rows = await _payloads(db_session)
    assert len(rows) == 2
    assert {(r.mapping_version, r.fiscal_year) for r in rows} == {
        ("concepts_v19", 2019), (MAPPING_VERSION, 2025),
    }


# --- the table's own guarantees (AC 1) ---------------------------------------


@requires_db
async def test_the_table_refuses_a_value_without_status_or_an_absence_without_reason(
    db_session,
) -> None:
    await _cpb(db_session, years=(2025,))
    base = dict(issuer_cik=CPB, axis=SEGMENT_AXIS, member_key="snacks",
                canonical_concept=REVENUE, fiscal_year=2025, mapping_version=MAPPING_VERSION)
    for status, value, reason in (
        (OK, None, None), (INSUFFICIENT, 1, "x"), (INSUFFICIENT, None, None), ("unknown", 1, None),
    ):
        with pytest.raises(IntegrityError, match="ck_segment_payloads_status"):
            async with db_session.begin_nested():
                await db_session.execute(insert(SegmentPayload).values(
                    **base, status=status, value=value, reason=reason,
                ))
    await db_session.execute(insert(SegmentPayload).values(**base, status=OK, value=0))
    with pytest.raises(IntegrityError, match="uq_segment_payloads_key"):
        async with db_session.begin_nested():
            await db_session.execute(insert(SegmentPayload).values(**base, status=OK, value=1))
    assert len(await _payloads(db_session)) == 1


# --- wiring (AC 5) -----------------------------------------------------------


@requires_db
async def test_run_issuer_materializes_filed_segment_rows_before_commit(db_session) -> None:
    """The real stage over the real CPB instance fixture, committed."""
    from ingestion.inline_xbrl import parse_instance
    from pipeline import run

    fixtures = Path(__file__).parent / "fixtures"
    accn = "0000016732-25-000112"
    inline_facts = parse_instance(
        (fixtures / "cpb_instance.xml").read_text(), accession_number=accn, fiscal_year=2025,
    )
    summary = await run.run_issuer(
        db_session, json.loads((fixtures / "cpb_company_facts.json").read_text()),
        ticker="CPB", inline_facts=inline_facts, inline_accession_number=accn,
    )
    async with AsyncSession(bind=db_session.bind) as committed:
        rows = await _payloads(committed)
        assert len(rows) == EXPECTED_PIPELINE_PAYLOADS
        assert summary["segments"] == {
            "written": EXPECTED_PIPELINE_PAYLOADS, "removed": 0, "insufficient": 0,
        }
        for row in rows:
            source = await committed.get(CanonicalMemberFact, row.source_member_fact_id)
            assert source is not None
            assert row.status == OK and row.value == source.value
            assert (row.accession_number, row.member_as_filed) == (
                source.accession_number, source.member_as_filed,
            )
            # Independent of canonicalization: the value is a fact in the instance.
            assert any(
                fact.dimensions == {SEGMENT_AXIS: row.member_as_filed}
                and Decimal(str(fact.value)) == Decimal(str(row.value))
                and fact.period_end == row.period_end.isoformat()
                for fact in inline_facts
            )

