"""CPB's 10%-or-less disclosure, as the filer's own statement (Story 13.4e).

Seeds real-shaped rows (both member spellings as stored at concepts_v19) and
asserts the ROW COUNT before anything about the rows.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import brands.store as store
from app.models import BrandFigure
from brands.impairment import materialize_brand_impairments
from brands.store import (
    DISCLOSURE_FORMULA_VERSION,
    FILER_THRESHOLD,
    load_carrying_value_spec,
    materialize_brand_carrying_values,
    parse_spec,
)
from formulas.engine import load_spec
from tests.conftest import requires_db
from tests.test_brand_figures import CARRYING, CPB, M, _cpb, _row

DISCLOSURE = "trade_names_within_ten_percent_of_impairment"
FIGURE = "ten_percent_or_less_disclosure"
OLD = "cpb:TradeNamesCarryingValueWith10OrLessExcessFairValueCoverageMember"
NEW = "cpb:TradeNamesCarryingValueWithTenPercentOrLessExcessFairValueCoverageMember"


async def _rows(db_session, figure: str = FIGURE) -> list[BrandFigure]:
    return list((await db_session.execute(
        select(BrandFigure).where(BrandFigure.figure == figure)
        .order_by(BrandFigure.brand_key, BrandFigure.fiscal_year)
    )).scalars().all())


async def _disclose(db_session):
    return await materialize_brand_carrying_values(
        db_session, CPB, formula_version=DISCLOSURE_FORMULA_VERSION
    )


async def _seed_four_years(db_session) -> dict:
    accns = await _cpb(db_session, years=(2022, 2023, 2024, 2025))
    seeded = {
        2022: _row(CPB, accns[2022], DISCLOSURE, "within_ten_percent_coverage", 2022, 434 * M, as_filed=OLD),
        2023: _row(CPB, accns[2023], DISCLOSURE, "within_ten_percent_coverage", 2023, 434 * M, as_filed=OLD),
        2024: _row(CPB, accns[2024], DISCLOSURE, "within_ten_percent_coverage", 2024, 1293 * M, as_filed=NEW),
        2025: _row(CPB, accns[2025], DISCLOSURE, "within_ten_percent_coverage", 2025, 2587 * M, as_filed=NEW),
    }
    db_session.add_all(seeded.values())
    await db_session.flush()
    return seeded


# --- the spec (AC 1, AC 2) ---------------------------------------------------


def test_the_spec_stores_only_the_disclosure_kind_and_names_whose_threshold() -> None:
    spec = load_carrying_value_spec(DISCLOSURE_FORMULA_VERSION)
    assert spec.inputs == (DISCLOSURE,)
    assert spec.figure == FIGURE
    assert spec.allowed_kinds == {"disclosure"}
    assert spec.caveats == {FILER_THRESHOLD}
    # The carrying-value spec never reads this concept and stores any kind.
    carrying = load_carrying_value_spec()
    assert DISCLOSURE not in carrying.inputs
    assert carrying.allowed_kinds is None


def test_no_ten_percent_threshold_is_encoded_anywhere() -> None:
    """AC 1: the band is CPB's — nothing of ours computes or compares against it."""
    root = Path(store.__file__).parent
    for path in root.glob("*.py"):
        text = path.read_text()
        assert "0.1" not in text and "0.10" not in text and "10%" not in text.replace(
            "10%-or-less", ""
        ), path


def _variant(**changes):
    formula = load_spec(DISCLOSURE_FORMULA_VERSION)
    raw = copy.deepcopy(formula.raw)
    raw.update(changes)
    return formula.__class__(**{**formula.__dict__, "raw": raw})


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"allowed_kinds": ["brandish"]}, "allowed_kinds"),
        ({"allowed_kinds": []}, "allowed_kinds"),
    ],
)
def test_the_loader_rejects_a_kind_the_mapping_spec_does_not_declare(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        parse_spec(_variant(**changes))


# --- the rows (AC 1-3) -------------------------------------------------------


@requires_db
async def test_both_spellings_land_under_one_key_as_the_filers_statement(db_session) -> None:
    seeded = await _seed_four_years(db_session)

    counts = await _disclose(db_session)
    assert counts == {"written": 4, "removed": 0, "unresolved": 0, "insufficient": 0}
    rows = await _rows(db_session)
    assert len(rows) == 4
    assert {r.brand_key for r in rows} == {"within_ten_percent_coverage"}
    assert {r.kind for r in rows} == {"disclosure"}
    assert [(r.fiscal_year, r.value) for r in rows] == [
        (2022, 434 * M), (2023, 434 * M), (2024, 1293 * M), (2025, 2587 * M),
    ]
    for row in rows:
        assert row.status == "ok"
        assert row.caveats == [FILER_THRESHOLD]
        assert row.source_member_fact_id == seeded[row.fiscal_year].id  # each spelling, as filed


@requires_db
async def test_a_row_resolving_to_another_kind_is_never_stored_as_a_brand(
    db_session, monkeypatch
) -> None:
    accns = await _cpb(db_session, years=(2024,))
    db_session.add(_row(CPB, accns[2024], DISCLOSURE, "kettle", 2024, 318 * M))
    await db_session.flush()

    counts = await _disclose(db_session)
    assert counts == {"written": 1, "removed": 0, "unresolved": 0, "insufficient": 1}
    rows = await _rows(db_session)
    assert len(rows) == 1
    assert (rows[0].brand_key, rows[0].status, rows[0].value) == (
        "kettle", "insufficient_data", None,
    )
    assert "'named_brand'" in rows[0].reason


# --- isolation and idempotency (AC 4) ----------------------------------------


@requires_db
async def test_the_disclosure_stage_never_touches_carrying_or_impairment_rows(db_session) -> None:
    await _seed_four_years(db_session)  # also files CPB's FY2024 accession used below
    kettle = _row(CPB, "0000016732-24-000100", CARRYING, "kettle", 2024, 318 * M)
    db_session.add(kettle)
    await db_session.flush()

    await materialize_brand_carrying_values(db_session, CPB)
    await materialize_brand_impairments(db_session, CPB)
    await _disclose(db_session)
    before = {
        figure: [(r.id, r.value, r.status) for r in await _rows(db_session, figure)]
        for figure in ("carrying_value", "impairment", FIGURE)
    }
    assert [len(before[f]) for f in ("carrying_value", "impairment", FIGURE)] == [1, 1, 4]

    again = await _disclose(db_session)
    assert again == {"written": 4, "removed": 0, "unresolved": 0, "insufficient": 0}
    carrying_again = await materialize_brand_carrying_values(db_session, CPB)
    assert carrying_again["removed"] == 0
    db_session.expire_all()
    after = {
        figure: [(r.id, r.value, r.status) for r in await _rows(db_session, figure)]
        for figure in ("carrying_value", "impairment", FIGURE)
    }
    assert after == before


# --- wiring (AC 4) -----------------------------------------------------------


@requires_db
async def test_run_issuer_commits_the_disclosure_rows(db_session) -> None:
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
        rows = await _rows(committed)
        assert len(rows) == summary["brand_disclosures"]["written"] > 0
        assert {(r.brand_key, r.kind, r.status) for r in rows} == {
            ("within_ten_percent_coverage", "disclosure", "ok"),
        }
        assert all(r.caveats == [FILER_THRESHOLD] for r in rows)
