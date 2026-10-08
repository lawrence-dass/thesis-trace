"""Per-brand carrying value, materialized on the write path (Story 13.4c).

Every DB test seeds real-shaped `canonical_member_facts` rows (contexts copied from
the dev store at concepts_v19) and asserts the ROW COUNT before anything about the
rows — a query over an empty table passes every per-row assertion
(a_vacuous_test_can_pass_a_mutation_audit, Story 13.4a).
"""

from __future__ import annotations

import copy
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

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
    value: float,
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
    ],
)
def test_the_spec_loader_rejects_what_the_code_would_not_execute(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        parse_spec(_spec_variant(**changes))


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
    assert [r.brand_key for r in await _figures(db_session)] == ["kettle"]


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
    before = [(r.id, r.brand_key, r.fiscal_year, r.value) for r in await _figures(db_session)]
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
    assert [r.brand_key for r in await _figures(db_session)] == ["kettle"]


@requires_db
async def test_rows_under_another_version_pair_are_never_touched(db_session) -> None:
    accns = await _cpb(db_session)
    db_session.add(_row(CPB, accns[2021], CARRYING, "kettle", 2021, 318 * M))
    db_session.add(
        BrandFigure(
            issuer_cik=CPB, brand_key="kettle", figure="carrying_value", fiscal_year=2021,
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
    assert {(r.mapping_version, r.value) for r in rows} == {
        ("concepts_v1", 1 * M), (MAPPING_VERSION, 318 * M),
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
async def test_an_undeclared_qualifier_does_not_block_a_declared_row(db_session) -> None:
    """A row whose basis is unknown never wins, and never vetoes a row whose is."""
    accns = await _cpb(db_session, years=(2024,))
    declared = _row(CPB, accns[2024], CARRYING, "pace", 2024, 292 * M)
    db_session.add_all([
        declared,
        _row(CPB, accns[2024], CARRYING, "pace", 2024, 290 * M,
             extra={"us-gaap:RangeAxis": "us-gaap:MaximumMember"}),
    ])
    await db_session.flush()

    counts = await materialize_brand_carrying_values(db_session, CPB)
    assert counts == {"written": 1, "removed": 0, "unresolved": 0, "insufficient": 0}
    rows = await _figures(db_session)
    assert len(rows) == 1
    assert (rows[0].status, rows[0].value, rows[0].source_member_fact_id) == (
        "ok", 292 * M, declared.id,
    )


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
async def test_run_issuer_calls_the_stage_and_reports_it(db_session, monkeypatch) -> None:
    """The stage runs inside the write-path pipeline, and its summary surfaces."""
    import json

    from pipeline import run
    from tests.test_pipeline import FIXTURE

    calls: list[str] = []

    async def spy(session, issuer_cik):
        calls.append(issuer_cik)
        return {"written": 7, "removed": 0, "unresolved": 0, "insufficient": 0}

    monkeypatch.setattr(run, "materialize_brand_carrying_values", spy)
    summary = await run.run_issuer(db_session, json.loads(FIXTURE.read_text()), ticker="SHOP")

    assert calls == [summary["cik"]]
    assert summary["brands"]["written"] == 7
