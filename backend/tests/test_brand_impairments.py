"""Impairment at the level the filing supports (Story 13.4d).

Seeds real-shaped rows (contexts as stored at concepts_v19) and asserts the ROW
COUNT before anything about the rows (a_vacuous_test_can_pass_a_mutation_audit).
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import brands.impairment as impairment
from app.models import BrandFigure, CanonicalMemberFact
from brands.impairment import (
    load_impairment_spec,
    materialize_brand_impairments,
    parse_impairment_spec,
)
from brands.store import materialize_brand_carrying_values
from canonicalization.mappings import MAPPING_VERSION
from formulas.engine import load_spec
from tests.conftest import requires_db
from tests.test_brand_figures import (
    CARRYING,
    CPB,
    M,
    QSR,
    SEGMENT_AXIS,
    ZTS,
    _cpb,
    _filing,
    _issuer,
    _row,
)

IMPAIRMENT = "brand_intangible_impairment"


async def _impairments(db_session, cik: str | None = None) -> list[BrandFigure]:
    from sqlalchemy import select

    query = (
        select(BrandFigure)
        .where(BrandFigure.figure == "impairment")
        .order_by(BrandFigure.brand_key, BrandFigure.fiscal_year)
    )
    if cik:
        query = query.where(BrandFigure.issuer_cik == cik)
    return list((await db_session.execute(query)).scalars().all())


async def _both(db_session, cik: str):
    carrying = await materialize_brand_carrying_values(db_session, cik)
    charges = await materialize_brand_impairments(db_session, cik)
    return carrying, charges


# --- the spec (AC 2, AC 6) ---------------------------------------------------


def test_the_spec_declares_each_filers_level() -> None:
    spec = load_impairment_spec()
    assert spec.common.inputs == (IMPAIRMENT,)
    assert spec.row_set_from == "brand_carrying_value_v1"
    assert spec.levels == {CPB: "brand", ZTS: "filer_only", QSR: "none"}


def _variant(mutate):
    formula = load_spec("brand_impairment_v1")
    raw = copy.deepcopy(formula.raw)
    mutate(raw)
    return formula.__class__(**{**formula.__dict__, "raw": raw})


@pytest.mark.parametrize(
    "mutate, message",
    [
        # The mapped filer (CPB) declared below `brand`.
        (lambda raw: raw["levels"][CPB].update(level="filer_only"), "not 'brand'"),
        # The mapped filer left out entirely.
        (lambda raw: raw["levels"].pop(CPB), "not 'brand'"),
        # A filer declared `brand` that no rule maps (it would never resolve a charge).
        (lambda raw: raw["levels"][ZTS].update(level="brand"), "no dimensioned rule maps"),
        (lambda raw: raw["levels"][QSR].update(level="partial"), "unknown level"),
        (lambda raw: raw["reasons"].pop("filer_tags_no_impairment"), "undeclared"),
        (lambda raw: raw["reasons"].update(invented_reason="x"), "unapplied"),
        (lambda raw: raw.update(missing_data_policy="impute_zero"), "missing_data_policy"),
        (lambda raw: raw.pop("row_set_from"), "row_set_from"),
        # Codex round, F1: a non-impairment concept passed every check and stored
        # Rao's 2.8bn ACQUISITION value as a write-down.
        (lambda raw: raw.update(inputs=["brand_intangible_acquired"]), "brand_intangible_impairment"),
        (lambda raw: raw.update(inputs=["brand_intangible_impairment", "brand_intangible_acquired"]),
         "brand_intangible_impairment"),
        # Codex round, F2: the impairment spec is "loadable" too, so pointing the row
        # set at itself made last night's output tonight's input — a stale row could
        # never be removed.
        (lambda raw: raw.update(row_set_from="brand_impairment_v1"), "carrying-value"),
    ],
)
def test_the_loader_rejects_a_level_or_reason_the_pipeline_contradicts(mutate, message) -> None:
    with pytest.raises((ValueError, FileNotFoundError), match=message):
        parse_impairment_spec(_variant(mutate))


# --- levels and reasons (AC 3, AC 4) -----------------------------------------


@requires_db
async def test_cpb_charges_land_per_brand_and_uncharged_years_are_not_zero(db_session) -> None:
    accns = await _cpb(db_session, years=(2024, 2025))
    allied_2024 = _row(CPB, accns[2024], IMPAIRMENT, "allied_brands", 2024, 53 * M)
    db_session.add_all([
        _row(CPB, accns[2024], CARRYING, "allied_brands", 2024, 43 * M),
        _row(CPB, accns[2024], CARRYING, "kettle", 2024, 318 * M),
        allied_2024,
        # A charge on a brand-year with NO carrying value (Late July, FY2025).
        _row(CPB, accns[2025], IMPAIRMENT, "late_july", 2025, 11 * M),
    ])
    await db_session.flush()

    _, counts = await _both(db_session, CPB)
    assert counts == {"written": 3, "removed": 0, "unresolved": 0, "insufficient": 1}
    rows = {(r.brand_key, r.fiscal_year): r for r in await _impairments(db_session)}
    assert len(rows) == 3
    assert {r.level for r in rows.values()} == {"brand"}

    allied = rows[("allied_brands", 2024)]
    assert (allied.status, allied.value, allied.source_member_fact_id) == (
        "ok", 53 * M, allied_2024.id,
    )
    late = rows[("late_july", 2025)]
    assert (late.status, late.value, late.kind) == ("ok", 11 * M, "named_brand")
    # D-e: no derived zero, even though CPB's per-brand set is complete.
    kettle = rows[("kettle", 2024)]
    assert (kettle.status, kettle.value, kettle.reason) == (
        "insufficient_data", None, "no_impairment_disclosed_for_brand",
    )


@requires_db
async def test_zts_rows_are_filer_only_and_carry_no_figure(db_session) -> None:
    await _issuer(db_session, ZTS, "ZTS")
    accn = "0001555280-25-000010"
    await _filing(db_session, ZTS, accn, 2025)
    db_session.add(_row(ZTS, accn, CARRYING, "brands", 2025, 67 * M, as_filed="zts:BrandsMember"))
    await db_session.flush()

    _, counts = await _both(db_session, ZTS)
    assert counts == {"written": 1, "removed": 0, "unresolved": 0, "insufficient": 1}
    rows = await _impairments(db_session)
    assert len(rows) == 1
    assert (rows[0].level, rows[0].status, rows[0].value, rows[0].reason) == (
        "filer_only", "insufficient_data", None, "impairment_reported_only_at_filer_level",
    )


@requires_db
async def test_qsr_rows_say_the_filer_tags_no_impairment(db_session) -> None:
    await _issuer(db_session, QSR, "QSR")
    accn = "0001618756-22-000018"
    await _filing(db_session, QSR, accn, 2021)
    for segment in ("qsr:BurgerKingMember", "qsr:FirehouseSubsMember"):
        db_session.add(_row(QSR, accn, CARRYING, "trade_names", 2021, 5 * M,
                            as_filed="us-gaap:TradeNamesMember", extra={SEGMENT_AXIS: segment}))
    await db_session.flush()

    _, counts = await _both(db_session, QSR)
    assert counts["written"] == 2, counts
    rows = await _impairments(db_session)
    assert len(rows) == 2
    assert {(r.brand_key, r.level, r.reason) for r in rows} == {
        ("burger_king", "none", "filer_tags_no_impairment"),
        ("firehouse_subs", "none", "filer_tags_no_impairment"),
    }


@requires_db
async def test_an_undeclared_filer_gets_no_guessed_level(db_session, monkeypatch) -> None:
    accns = await _cpb(db_session, years=(2024,))
    db_session.add(_row(CPB, accns[2024], CARRYING, "kettle", 2024, 318 * M))
    await db_session.flush()
    real = load_impairment_spec()
    monkeypatch.setattr(
        impairment, "load_impairment_spec",
        lambda *_: real.__class__(**{**real.__dict__, "levels": {}}),
    )

    _, counts = await _both(db_session, CPB)
    assert counts["insufficient"] == 1, counts
    rows = await _impairments(db_session)
    assert len(rows) == 1
    assert (rows[0].level, rows[0].reason) == (None, "impairment_level_undeclared")


@requires_db
async def test_two_disagreeing_charges_are_insufficient_never_a_pick(
    db_session, monkeypatch
) -> None:
    accns = await _cpb(db_session, years=(2025,))
    db_session.add_all([
        _row(CPB, accns[2025], IMPAIRMENT, "snyders_of_hanover", 2025, 150 * M),
        _row(CPB, accns[2025], IMPAIRMENT, "snyders_of_hanover", 2025, 140 * M,
             extra={"cpb:EraAxis": "cpb:RestatedMember"}),
    ])
    await db_session.flush()
    real = impairment._identity_axes
    monkeypatch.setattr(impairment, "_identity_axes", lambda cik=None: real(cik) | {"cpb:EraAxis"})

    _, counts = await _both(db_session, CPB)
    assert counts["insufficient"] == 1, counts
    rows = await _impairments(db_session)
    assert len(rows) == 1
    assert (rows[0].status, rows[0].value) == ("insufficient_data", None)
    assert "disagree" in rows[0].reason


# --- isolation and idempotency (AC 5) ----------------------------------------


@requires_db
async def test_each_stage_never_deletes_the_others_rows(db_session) -> None:
    accns = await _cpb(db_session, years=(2024,))
    db_session.add_all([
        _row(CPB, accns[2024], CARRYING, "kettle", 2024, 318 * M),
        _row(CPB, accns[2024], IMPAIRMENT, "pop_secret", 2024, 76 * M),
    ])
    await db_session.flush()
    await _both(db_session, CPB)
    assert len(await _impairments(db_session)) == 2

    # Re-running carrying value alone must leave every impairment row in place...
    again = await materialize_brand_carrying_values(db_session, CPB)
    assert again["removed"] == 0, again
    assert len(await _impairments(db_session)) == 2
    # ...and impairment alone must leave every carrying row in place.
    charges = await materialize_brand_impairments(db_session, CPB)
    assert charges == {"written": 2, "removed": 0, "unresolved": 0, "insufficient": 1}
    from sqlalchemy import select

    carrying = (await db_session.execute(
        select(BrandFigure).where(BrandFigure.figure == "carrying_value")
    )).scalars().all()
    assert [r.brand_key for r in carrying] == ["kettle"]


@requires_db
async def test_an_impairment_row_whose_brand_year_vanished_is_removed(db_session) -> None:
    accns = await _cpb(db_session, years=(2024,))
    kettle = _row(CPB, accns[2024], CARRYING, "kettle", 2024, 318 * M)
    db_session.add(kettle)
    await db_session.flush()
    await _both(db_session, CPB)
    assert len(await _impairments(db_session)) == 1

    kettle.superseded = True
    await db_session.flush()
    _, counts = await _both(db_session, CPB)
    assert counts["removed"] == 1, counts
    assert await _impairments(db_session) == []


@requires_db
async def test_a_second_run_changes_nothing(db_session) -> None:
    accns = await _cpb(db_session, years=(2024,))
    db_session.add_all([
        _row(CPB, accns[2024], CARRYING, "kettle", 2024, 318 * M),
        _row(CPB, accns[2024], IMPAIRMENT, "pop_secret", 2024, 76 * M),
    ])
    await db_session.flush()
    _, first = await _both(db_session, CPB)
    before = [(r.id, r.brand_key, r.status, r.value) for r in await _impairments(db_session)]
    _, second = await _both(db_session, CPB)
    db_session.expire_all()
    after = [(r.id, r.brand_key, r.status, r.value) for r in await _impairments(db_session)]
    assert first == second
    assert len(after) == 2
    assert after == before


# --- wiring (AC 5) -----------------------------------------------------------


@requires_db
async def test_run_issuer_commits_impairment_rows_after_carrying_value(db_session) -> None:
    """A real offline CPB run; a second connection must see every committed row."""
    from sqlalchemy import func, select

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
        filed = (await committed.execute(
            select(func.count()).select_from(CanonicalMemberFact).where(
                CanonicalMemberFact.canonical_concept == IMPAIRMENT,
                CanonicalMemberFact.mapping_version == MAPPING_VERSION,
                CanonicalMemberFact.superseded.is_(False),
            )
        )).scalar_one()
        rows = await _impairments(committed, CPB)
        assert filed > 0
        assert len(rows) == summary["brand_impairments"]["written"] > 0
        ok = [r for r in rows if r.status == "ok"]
        assert len(ok) == filed  # every filed charge, and nothing else, has a value
        for row in ok:
            source = await committed.get(CanonicalMemberFact, row.source_member_fact_id)
            assert source.canonical_concept == IMPAIRMENT
            assert Decimal(str(row.value)) == Decimal(str(source.value))
        assert {r.level for r in rows} == {"brand"}
        # Every carrying-value brand-year has its impairment row (D-g).
        carrying = {
            (r.brand_key, r.fiscal_year)
            for r in (await committed.execute(
                select(BrandFigure).where(BrandFigure.figure == "carrying_value")
            )).scalars()
        }
        assert carrying and carrying <= {(r.brand_key, r.fiscal_year) for r in rows}
