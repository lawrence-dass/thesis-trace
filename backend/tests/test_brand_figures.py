"""Per-brand carrying value, materialized on the write path (Story 13.4c).

Every DB test seeds real-shaped `canonical_member_facts` rows (contexts copied from
the dev store at concepts_v19) and asserts the ROW COUNT before anything about the
rows — a query over an empty table passes every per-row assertion
(a_vacuous_test_can_pass_a_mutation_audit, Story 13.4a).
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import brands.store as store
from app.models import BrandFigure, CanonicalMemberFact, Filing, Issuer
from brands.store import (
    INSUFFICIENT,
    PRE_ACQUISITION,
    load_carrying_value_spec,
    materialize_brand_carrying_values,
    parse_spec,
)
from canonicalization.mappings import MAPPING_VERSION
from canonicalization.canonicalize import _supersede_member
from formulas.engine import load_spec, round_ratio
from tests.conftest import requires_db

CPB = "0000016732"
QSR = "0001618756"
ZTS = "0001555280"
CLASS_AXIS = "us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis"
SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"
FV_AXIS = "us-gaap:FairValueByMeasurementFrequencyAxis"
NONRECURRING = "us-gaap:FairValueMeasurementsNonrecurringMember"
CARRYING = "brand_intangible_carrying_value"
RESIDUAL = "brand_intangible_carrying_value_residual"
TOTAL = "brand_intangible_carrying_value_total"
M = 1_000_000


async def _issuer(db_session, cik: str, ticker: str) -> None:
    db_session.add(Issuer(cik=cik, ticker=ticker, name=f"{ticker} Inc", sector="Consumer"))
    await db_session.flush()


async def _filing(db_session, cik: str, accn: str, fiscal_year: int) -> None:
    db_session.add(
        Filing(
            accession_number=accn,
            issuer_cik=cik,
            form_type="10-K",
            filing_date=date(fiscal_year, 9, 20),
            fiscal_year=fiscal_year,
            fiscal_year_end=date(fiscal_year, 7, 31),
        )
    )
    await db_session.flush()


def _row(
    cik: str,
    accn: str,
    concept: str,
    member_key: str,
    year: int,
    value: float | Decimal,
    *,
    as_filed: str = "cpb:SomeMember",
    extra: dict[str, str] | None = None,
    mapping_version: str = MAPPING_VERSION,
    superseded: bool = False,
) -> CanonicalMemberFact:
    """A stored member row shaped like the dev store's (mapped axis normalized)."""
    context = {CLASS_AXIS: member_key, **(extra or {})}
    dimensions = {CLASS_AXIS: as_filed, **(extra or {})}
    return CanonicalMemberFact(
        issuer_cik=cik,
        accession_number=accn,
        canonical_concept=concept,
        member_key=member_key,
        member_as_filed=as_filed,
        axis_as_filed=CLASS_AXIS,
        dimensions=dimensions,
        context_key=context,
        fiscal_year=year,
        period_end=date(year, 7, 31),
        value=value,
        unit="USD",
        mapping_version=mapping_version,
        superseded=superseded,
    )


async def _cpb(db_session, years=(2021,)) -> dict[int, str]:
    await _issuer(db_session, CPB, "CPB")
    accns = {}
    for year in years:
        accns[year] = f"0000016732-{year % 100:02d}-000100"
        await _filing(db_session, CPB, accns[year], year)
    return accns


async def _figures(db_session, cik: str | None = None) -> list[BrandFigure]:
    query = select(BrandFigure).order_by(BrandFigure.brand_key, BrandFigure.fiscal_year)
    if cik:
        query = query.where(BrandFigure.issuer_cik == cik)
    return list((await db_session.execute(query)).scalars().all())


# --- the spec (AC 4) -------------------------------------------------------


def test_the_spec_loads_and_its_inputs_are_the_three_concepts() -> None:
    spec = load_carrying_value_spec()
    assert spec.inputs == (CARRYING, RESIDUAL, TOTAL)
    assert spec.formula.missing_data_policy == "insufficient_data"
    assert spec.basis.precedence == ("carrying_value", "nonrecurring_fair_value")
    assert spec.basis.qualifiers == {(FV_AXIS, NONRECURRING): "nonrecurring_fair_value"}
    assert spec.caveats == {PRE_ACQUISITION}


def test_rounding_is_the_identity_on_a_filed_amount() -> None:
    """Values are copied through the shared engine; storage scale must survive it."""
    spec = load_carrying_value_spec()
    for raw in ("1470000000.000000", "28000000.123456", "0.000000", "2549000000.5"):
        assert round_ratio(Decimal(raw), spec.formula) == Decimal(raw)


def _spec_variant(**changes):
    formula = load_spec("brand_carrying_value_v1")
    raw = copy.deepcopy(formula.raw)
    for path, value in changes.items():
        target = raw
        *parents, leaf = path.split(".")
        for parent in parents:
            target = target[parent]
        target[leaf] = value
    return formula.__class__(**{**formula.__dict__, "raw": raw})


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"inputs": []}, "declares no inputs"),
        ({"inputs": [CARRYING, "an_unproduced_concept"]}, "produced by no dimensioned rule"),
        (
            {"basis.qualifiers": [{"axis": CLASS_AXIS, "member": "x", "basis": "b"}]},
            "is an identity axis",
        ),
        (
            {"basis.qualifiers": [{"axis": SEGMENT_AXIS, "member": "x", "basis": "b"}]},
            "is an identity axis",
        ),
        ({"basis.precedence": ["carrying_value"]}, "must order every declared basis"),
        ({"caveats": {"invented_caveat": {}}}, "applied by no code"),
        ({"missing_data_policy": "impute_zero"}, "missing_data_policy"),
        ({"missing_data_policy": None}, "missing_data_policy"),
    ],
)
def test_the_spec_loader_rejects_what_the_code_would_not_execute(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        parse_spec(_spec_variant(**changes))


def test_the_spec_loader_rejects_a_policy_that_disagrees_with_the_loaded_formula() -> None:
    formula = replace(load_spec("brand_carrying_value_v1"), missing_data_policy="impute_zero")
    with pytest.raises(ValueError, match="missing_data_policy"):
        parse_spec(formula)


@requires_db
async def test_materialization_preserves_a_filed_fractional_amount(db_session) -> None:
    accns = await _cpb(db_session, years=(2024,))
    filed = _row(CPB, accns[2024], CARRYING, "pace", 2024, Decimal("28000000.123456"))
    db_session.add(filed)
    await db_session.flush()
    await materialize_brand_carrying_values(db_session, CPB)
    db_session.expire_all()
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert rows[0].value == Decimal("28000000.123456")


@requires_db
async def test_only_declared_inputs_are_read(db_session, monkeypatch) -> None:
    """The query filter IS the spec's inputs list — drop one and it stops being read."""
    accns = await _cpb(db_session)
    db_session.add_all([
        _row(CPB, accns[2021], CARRYING, "kettle", 2021, 318 * M),
        _row(CPB, accns[2021], TOTAL, "all_trademarks", 2021, 2549 * M),
        # Mapped, stored, and NOT an input: must never become a carrying value.
        _row(CPB, accns[2021], "brand_intangible_impairment", "kettle", 2021, 9 * M),
    ])
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts["written"] == 2, counts
    rows = await _figures(db_session)
    assert len(rows) == 2
    assert {(r.brand_key, r.value) for r in rows} == {
        ("kettle", 318 * M), ("all_trademarks", 2549 * M),
    }

    narrowed = _spec_variant(inputs=[CARRYING])
    monkeypatch.setattr(store, "load_carrying_value_spec", lambda *_: parse_spec(narrowed))
    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts == {"written": 1, "removed": 1, "unresolved": 0, "insufficient": 0}
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert rows[0].brand_key == "kettle"


# --- idempotency and stale rows (AC 3) ---------------------------------------


@requires_db
async def test_a_second_run_writes_the_same_rows(db_session) -> None:
    accns = await _cpb(db_session, years=(2021, 2022))
    db_session.add_all([
        _row(CPB, accns[2021], CARRYING, "kettle", 2021, 318 * M),
        _row(CPB, accns[2022], CARRYING, "kettle", 2022, 318 * M),
        _row(CPB, accns[2022], CARRYING, "lance", 2022, 350 * M),
    ])
    await db_session.flush()

    first = await materialize_brand_carrying_values(db_session, CPB)
    rows = await _figures(db_session)
    assert len(rows) == 3
    before = [(r.id, r.brand_key, r.fiscal_year, r.value) for r in rows]
    second = await materialize_brand_carrying_values(db_session, CPB)
    db_session.expire_all()
    after = [(r.id, r.brand_key, r.fiscal_year, r.value) for r in await _figures(db_session)]

    assert first == second == {"written": 3, "removed": 0, "unresolved": 0, "insufficient": 0}
    assert len(after) == 3
    assert after == before  # same ids: updated in place, never duplicated


@requires_db
async def test_a_brand_year_that_stops_resolving_is_removed(db_session) -> None:
    accns = await _cpb(db_session, years=(2021, 2022))
    lance = _row(CPB, accns[2022], CARRYING, "lance", 2022, 350 * M)
    db_session.add_all([_row(CPB, accns[2021], CARRYING, "kettle", 2021, 318 * M), lance])
    await db_session.flush()
    await materialize_brand_carrying_values(db_session, CPB)
    assert len(await _figures(db_session)) == 2

    lance.superseded = True  # superseded with no replacement
    await db_session.flush()
    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts["removed"] == 1, counts
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert rows[0].brand_key == "kettle"


@requires_db
async def test_recomputation_refreshes_value_source_and_computed_at(db_session) -> None:
    accns = await _cpb(db_session, years=(2024,))
    old = _row(CPB, accns[2024], CARRYING, "pace", 2024, 100)
    db_session.add(old)
    await db_session.flush()
    await materialize_brand_carrying_values(db_session, CPB)
    rows = await _figures(db_session)
    assert len(rows) == 1
    figure_id = rows[0].id
    sentinel = datetime(2000, 1, 1, tzinfo=timezone.utc)
    await db_session.execute(update(BrandFigure).where(BrandFigure.id == figure_id).values(computed_at=sentinel))

    new = _row(CPB, accns[2024], CARRYING, "pace", 2024, 200)
    await _supersede_member(db_session, old, new)
    await db_session.flush()
    new_id = new.id
    await materialize_brand_carrying_values(db_session, CPB)
    db_session.expire_all()
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert rows[0].id == figure_id
    assert rows[0].value == 200 and rows[0].source_member_fact_id == new_id
    assert rows[0].computed_at > sentinel


@requires_db
@pytest.mark.parametrize("has_current_input", [True, False])
async def test_stale_deletion_preserves_other_figures_formulas_and_issuers(
    db_session, has_current_input
) -> None:
    accns = await _cpb(db_session, years=(2019, 2024))
    current = _row(CPB, accns[2024], CARRYING, "pace", 2024, 100)
    historical = _row(CPB, accns[2019], CARRYING, "lance", 2019, M, superseded=True)
    impairment = _row(CPB, accns[2019], "brand_intangible_impairment", "lance", 2019, M)
    await _issuer(db_session, ZTS, "ZTS")
    zts_accn = "0001555280-19-000100"
    await _filing(db_session, ZTS, zts_accn, 2019)
    zts = _row(ZTS, zts_accn, CARRYING, "brands", 2019, M, as_filed="zts:BrandsMember")
    db_session.add_all([current, historical, impairment, zts])
    await db_session.flush()
    await materialize_brand_carrying_values(db_session, CPB)
    await materialize_brand_carrying_values(db_session, ZTS)
    for source, figure, formula_version in (
        (historical, "carrying_value", "future_v2"),
        (impairment, "impairment", "brand_carrying_value_v1"),
    ):
        db_session.add(BrandFigure(
            issuer_cik=CPB, brand_key="lance", figure=figure, fiscal_year=2019,
            formula_version=formula_version, mapping_version=MAPPING_VERSION,
            kind="named_brand", source_axis=CLASS_AXIS, basis="carrying_value",
            period_end=source.period_end, value=source.value, unit=source.unit,
            status="ok", caveats=[], source_member_fact_id=source.id,
        ))
    await db_session.flush()
    before = await _figures(db_session)
    assert len(before) == 4
    retained = {r.id for r in before if r.issuer_cik != CPB or r.brand_key == "lance"}
    if not has_current_input:
        current.superseded = True
        await db_session.flush()
    counts = await materialize_brand_carrying_values(db_session, CPB)
    db_session.expire_all()
    rows = await _figures(db_session)
    assert len(rows) == (4 if has_current_input else 3)
    assert retained <= {r.id for r in rows}
    assert counts == {
        "written": int(has_current_input), "removed": int(not has_current_input),
        "unresolved": 0, "insufficient": 0,
    }


@requires_db
async def test_rows_under_another_version_pair_are_never_touched(db_session) -> None:
    accns = await _cpb(db_session)
    db_session.add(_row(CPB, accns[2021], CARRYING, "kettle", 2021, 318 * M))
    # A brand-year tonight's run does NOT produce — otherwise the "not in what was
    # written" half of the delete would spare it whatever its version, and this test
    # would pass with the version scope removed (caught by the mutation audit).
    db_session.add(
        BrandFigure(
            issuer_cik=CPB, brand_key="lance", figure="carrying_value", fiscal_year=2019,
            formula_version="brand_carrying_value_v1", mapping_version="concepts_v1",
            kind="named_brand", source_axis=CLASS_AXIS, basis="carrying_value",
            value=1 * M, status="ok", caveats=[],
        )
    )
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts["removed"] == 0, counts
    rows = await _figures(db_session)
    assert len(rows) == 2
    assert {(r.brand_key, r.mapping_version, r.value) for r in rows} == {
        ("lance", "concepts_v1", 1 * M), ("kettle", MAPPING_VERSION, 318 * M),
    }


# --- basis (AC 5) and precedence (AC 6) --------------------------------------


@requires_db
async def test_basis_is_recorded_from_the_context(db_session) -> None:
    accns = await _cpb(db_session, years=(2024,))
    db_session.add_all([
        _row(CPB, accns[2024], CARRYING, "kettle", 2024, 318 * M),
        _row(CPB, accns[2024], CARRYING, "allied_brands", 2024, 43 * M,
             extra={FV_AXIS: NONRECURRING}),
        _row(CPB, accns[2024], CARRYING, "pace", 2024, 292 * M,
             extra={"us-gaap:RangeAxis": "us-gaap:MaximumMember"}),
    ])
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts == {"written": 3, "removed": 0, "unresolved": 0, "insufficient": 1}
    rows = {r.brand_key: r for r in await _figures(db_session)}
    assert len(rows) == 3
    assert (rows["kettle"].basis, rows["kettle"].status) == ("carrying_value", "ok")
    assert (rows["allied_brands"].basis, rows["allied_brands"].value) == (
        "nonrecurring_fair_value", 43 * M,
    )
    assert rows["pace"].status == INSUFFICIENT
    assert rows["pace"].value is None
    assert "us-gaap:RangeAxis" in rows["pace"].reason


@requires_db
async def test_carrying_value_beats_fair_value_for_one_brand_year(db_session) -> None:
    accns = await _cpb(db_session, years=(2024,))
    carrying = _row(CPB, accns[2024], CARRYING, "pop_secret", 2024, 30 * M)
    db_session.add_all([
        carrying,
        _row(CPB, accns[2024], CARRYING, "pop_secret", 2024, 28 * M,
             extra={FV_AXIS: NONRECURRING}),
    ])
    await db_session.flush()

    await materialize_brand_carrying_values(db_session, CPB)
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert (rows[0].basis, rows[0].value, rows[0].source_member_fact_id) == (
        "carrying_value", 30 * M, carrying.id,
    )


@requires_db
async def test_an_undeclared_qualifier_blocks_a_declared_row(db_session) -> None:
    """AC 5: an unknown qualifier makes the whole brand-year insufficient."""
    accns = await _cpb(db_session, years=(2024,))
    declared = _row(CPB, accns[2024], CARRYING, "pace", 2024, 292 * M)
    db_session.add_all([
        declared,
        _row(CPB, accns[2024], CARRYING, "pace", 2024, 290 * M,
             extra={"us-gaap:RangeAxis": "us-gaap:MaximumMember"}),
    ])
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts == {"written": 1, "removed": 0, "unresolved": 0, "insufficient": 1}
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert (rows[0].status, rows[0].value, rows[0].source_member_fact_id) == (
        INSUFFICIENT, None, None,
    )
    assert "us-gaap:RangeAxis" in rows[0].reason
    assert "us-gaap:MaximumMember" in rows[0].reason


@requires_db
async def test_two_unqualified_rows_with_different_values_are_insufficient(
    db_session, monkeypatch
) -> None:
    accns = await _cpb(db_session, years=(2024,))
    a = _row(CPB, accns[2024], CARRYING, "pace", 2024, 292 * M)
    b = _row(CPB, accns[2024], CARRYING, "pace", 2024, 290 * M,
             extra={"cpb:EraAxis": "cpb:RestatedMember"})
    db_session.add_all([a, b])
    await db_session.flush()
    # Declare the era axis as a SECOND unqualified-equivalent basis is not allowed by
    # the spec, so treat it as an identity axis for this filer: both rows then read
    # as unqualified carrying values that disagree.
    real = store._identity_axes
    monkeypatch.setattr(
        store, "_identity_axes",
        lambda cik=None: real(cik) | {"cpb:EraAxis"},
    )

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts["insufficient"] == 1, counts
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert rows[0].status == INSUFFICIENT
    assert rows[0].value is None
    assert rows[0].source_member_fact_id is None
    assert str(a.id) in rows[0].reason and str(b.id) in rows[0].reason


# --- identity and version (AC 7) ---------------------------------------------


@requires_db
async def test_qsr_segment_rows_land_under_their_brands(db_session) -> None:
    await _issuer(db_session, QSR, "QSR")
    accn = "0001618756-22-000018"
    await _filing(db_session, QSR, accn, 2021)
    for segment, value in [
        ("qsr:BurgerKingMember", 2126), ("qsr:TimHortonsMember", 6695),
        ("qsr:PopeyesLouisianaKitchenMember", 1355), ("qsr:FirehouseSubsMember", 768),
    ]:
        db_session.add(_row(QSR, accn, CARRYING, "trade_names", 2021, value * M,
                            as_filed="us-gaap:TradeNamesMember",
                            extra={SEGMENT_AXIS: segment}))
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, QSR)
    assert counts == {"written": 4, "removed": 0, "unresolved": 0, "insufficient": 0}
    rows = await _figures(db_session)
    assert len(rows) == 4
    assert {(r.brand_key, r.kind, r.source_axis, r.basis, r.value) for r in rows} == {
        ("burger_king", "named_brand", SEGMENT_AXIS, "carrying_value", 2126 * M),
        ("tim_hortons", "named_brand", SEGMENT_AXIS, "carrying_value", 6695 * M),
        ("popeyes", "named_brand", SEGMENT_AXIS, "carrying_value", 1355 * M),
        ("firehouse_subs", "named_brand", SEGMENT_AXIS, "carrying_value", 768 * M),
    }


@requires_db
async def test_an_unresolvable_row_writes_nothing_and_is_counted(db_session) -> None:
    await _issuer(db_session, QSR, "QSR")
    accn = "0001618756-22-000018"
    await _filing(db_session, QSR, accn, 2021)
    db_session.add_all([
        _row(QSR, accn, CARRYING, "trade_names", 2021, 2126 * M,
             extra={SEGMENT_AXIS: "qsr:BurgerKingMember"}),
        # A segment nobody declared: identity is insufficient_data, not "Trade names".
        _row(QSR, accn, CARRYING, "trade_names", 2021, 5 * M,
             extra={SEGMENT_AXIS: "qsr:NewConceptMember"}),
    ])
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, QSR)
    assert counts == {"written": 1, "removed": 0, "unresolved": 1, "insufficient": 0}
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert rows[0].brand_key == "burger_king"


@requires_db
async def test_only_the_running_mapping_version_is_read(db_session) -> None:
    accns = await _cpb(db_session)
    db_session.add_all([
        _row(CPB, accns[2021], CARRYING, "kettle", 2021, 318 * M),
        _row(CPB, accns[2021], CARRYING, "lance", 2021, 350 * M,
             mapping_version="concepts_v17"),
    ])
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts["written"] == 1, counts
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert (rows[0].brand_key, rows[0].mapping_version) == ("kettle", MAPPING_VERSION)


# --- the pre-acquisition comparative (AC 8) ----------------------------------


@requires_db
async def test_pre_acquisition_zero_is_annotated_and_never_altered(db_session) -> None:
    accns = await _cpb(db_session, years=(2023, 2024, 2025))
    db_session.add_all([
        # Rao's: filed 0 in its first stored year, positive after -> caveat.
        _row(CPB, accns[2024], CARRYING, "raos", 2023, 0),
        _row(CPB, accns[2024], CARRYING, "raos", 2024, 1470 * M),
        # A zero AFTER a positive year is not this rule's business.
        _row(CPB, accns[2023], CARRYING, "pace", 2023, 292 * M),
        _row(CPB, accns[2024], CARRYING, "pace", 2024, 0),
        # A zero with no later positive is not either.
        _row(CPB, accns[2025], CARRYING, "lance", 2025, 0),
    ])
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts["written"] == 5, counts
    rows = {(r.brand_key, r.fiscal_year): r for r in await _figures(db_session)}
    assert len(rows) == 5
    assert (rows[("raos", 2023)].value, rows[("raos", 2023)].status) == (0, "ok")
    assert rows[("raos", 2023)].caveats == [PRE_ACQUISITION]
    assert rows[("raos", 2024)].caveats == []
    assert rows[("pace", 2024)].caveats == []
    assert rows[("lance", 2025)].caveats == []


@requires_db
async def test_an_insufficient_earliest_year_does_not_shift_the_caveat(db_session) -> None:
    accns = await _cpb(db_session, years=(2022, 2023, 2024))
    db_session.add_all([
        _row(CPB, accns[2022], CARRYING, "pace", 2022, 292 * M,
             extra={"us-gaap:RangeAxis": "us-gaap:MaximumMember"}),
        _row(CPB, accns[2023], CARRYING, "pace", 2023, 0),
        _row(CPB, accns[2024], CARRYING, "pace", 2024, 292 * M),
    ])
    await db_session.flush()
    await materialize_brand_carrying_values(db_session, CPB)
    rows = await _figures(db_session)
    assert len(rows) == 3
    assert rows[0].fiscal_year == 2022 and rows[0].status == INSUFFICIENT
    assert rows[1].value == 0
    assert all(r.caveats == [] for r in rows)


@requires_db
async def test_status_transitions_clear_and_restore_all_source_fields(db_session) -> None:
    accns = await _cpb(db_session, years=(2023, 2024))
    old = _row(CPB, accns[2023], CARRYING, "raos", 2023, 0)
    db_session.add_all([old, _row(CPB, accns[2024], CARRYING, "raos", 2024, 1470 * M)])
    await db_session.flush()
    await materialize_brand_carrying_values(db_session, CPB)
    rows = await _figures(db_session)
    assert len(rows) == 2
    figure_id = rows[0].id
    assert rows[0].caveats == [PRE_ACQUISITION]

    unknown = _row(CPB, accns[2023], CARRYING, "raos", 2023, 0,
                   extra={"us-gaap:RangeAxis": "us-gaap:MaximumMember"})
    old.superseded = True
    await db_session.flush()
    db_session.add(unknown)
    await db_session.flush()
    unknown_id = unknown.id
    await materialize_brand_carrying_values(db_session, CPB)
    db_session.expire_all()
    rows = await _figures(db_session)
    assert len(rows) == 2
    insufficient = rows[0]
    assert insufficient.id == figure_id and insufficient.status == INSUFFICIENT
    assert (insufficient.basis, insufficient.period_end, insufficient.value,
            insufficient.unit, insufficient.source_member_fact_id) == (None,) * 5
    assert insufficient.caveats == [] and "RangeAxis" in insufficient.reason

    unknown = await db_session.get(CanonicalMemberFact, unknown_id)
    new = _row(CPB, accns[2023], CARRYING, "raos", 2023, 5)
    unknown.superseded = True
    await db_session.flush()
    db_session.add(new)
    await db_session.flush()
    new_id = new.id
    await materialize_brand_carrying_values(db_session, CPB)
    db_session.expire_all()
    rows = await _figures(db_session)
    assert len(rows) == 2
    restored = rows[0]
    assert restored.id == figure_id and restored.status == "ok"
    assert (restored.basis, restored.period_end, restored.value, restored.unit,
            restored.source_member_fact_id) == ("carrying_value", date(2023, 7, 31), 5, "USD", new_id)
    assert restored.reason is None and restored.caveats == []


# --- residual and total stay separate (AC 9) ---------------------------------


@requires_db
async def test_the_total_is_the_filed_total_never_a_sum(db_session) -> None:
    """CPB FY2021: filed total 2,549m; named brands + residual reach 2,867m."""
    accns = await _cpb(db_session)
    named = {"kettle": 318, "lance": 350, "pace": 292, "pacific_foods": 280,
             "snyders_of_hanover": 620}
    for brand, value in named.items():
        db_session.add(_row(CPB, accns[2021], CARRYING, brand, 2021, value * M))
    db_session.add_all([
        _row(CPB, accns[2021], RESIDUAL, "other_trade_names", 2021, 1007 * M),
        _row(CPB, accns[2021], TOTAL, "all_trademarks", 2021, 2549 * M),
    ])
    await db_session.flush()

    await materialize_brand_carrying_values(db_session, CPB)
    rows = {r.brand_key: r for r in await _figures(db_session)}
    assert len(rows) == 7
    assert sum(named.values()) + 1007 == 2867  # the overshoot that disproved summing
    assert (rows["all_trademarks"].kind, rows["all_trademarks"].value) == ("aggregate", 2549 * M)
    assert (rows["other_trade_names"].kind, rows["other_trade_names"].value) == (
        "residual", 1007 * M,
    )
    assert {r.kind for k, r in rows.items() if k in named} == {"named_brand"}


@requires_db
async def test_zts_brands_is_an_aggregate_not_a_brand(db_session) -> None:
    await _issuer(db_session, ZTS, "ZTS")
    accn = "0001555280-25-000010"
    await _filing(db_session, ZTS, accn, 2025)
    db_session.add(_row(ZTS, accn, CARRYING, "brands", 2025, 67 * M, as_filed="zts:BrandsMember"))
    await db_session.flush()

    await materialize_brand_carrying_values(db_session, ZTS)
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert (rows[0].brand_key, rows[0].kind) == ("brands", "aggregate")


# --- wiring (AC 2) -----------------------------------------------------------


@requires_db
async def test_run_issuer_materializes_filed_brand_rows_before_commit(db_session) -> None:
    """Exercise the real stage, its source facts, and its committed summary offline."""
    from pipeline import run
    from ingestion.inline_xbrl import parse_instance

    fixtures = Path(__file__).parent / "fixtures"
    accn = "0000016732-25-000112"
    inline_facts = parse_instance(
        (fixtures / "cpb_instance.xml").read_text(), accession_number=accn, fiscal_year=2025,
    )
    summary = await run.run_issuer(
        db_session, json.loads((fixtures / "cpb_company_facts.json").read_text()),
        ticker="CPB", inline_facts=inline_facts, inline_accession_number=accn,
    )
    # A second connection must see the rows: reading through the writer would
    # also pass if the stage moved AFTER commit and left its figures uncommitted.
    async with AsyncSession(bind=db_session.bind) as committed:
        # Carrying value only: since 13.4d the same run also writes impairment rows,
        # which tests/test_brand_impairments.py asserts on their own.
        rows = [r for r in await _figures(committed, CPB) if r.figure == "carrying_value"]
        assert len(rows) == 18
        assert summary["brands"] == {"written": 18, "removed": 0, "unresolved": 0, "insufficient": 0}
        for row in rows:
            source = await committed.get(CanonicalMemberFact, row.source_member_fact_id)
            assert source is not None
            assert row.status == "ok" and row.value == source.value
            assert source.accession_number == accn
            assert source.dimensions[source.axis_as_filed] == source.member_as_filed
            assert any(
                fact.dimensions == source.dimensions and Decimal(str(fact.value)) == source.value
                and fact.period_end == source.period_end.isoformat() for fact in inline_facts
            )
