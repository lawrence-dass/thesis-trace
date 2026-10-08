"""Exercise the production brand schema on the guarded test database, never dev."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import insert, inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import BrandFigure, CanonicalMemberFact
from brands.store import materialize_brand_carrying_values
from canonicalization.mappings import MAPPING_VERSION
from tests.conftest import requires_db
from tests.test_brand_figures import CARRYING, CLASS_AXIS, CPB, _cpb, _figures, _row


# Every revision that shapes brand_figures, oldest first. The round-trip replays
# the WHOLE chain, so a later revision (13.4d's `level`) is checked against the
# model too rather than leaving this test comparing a stale schema.
CHAIN = (
    ("f3a8c2d61b47_add_brand_figures.py", "d4f61a2b9c30"),
    ("a9d3e7f25c18_brand_figures_level.py", "f3a8c2d61b47"),
)


def _load(filename: str, down_revision: str):
    path = Path(__file__).resolve().parents[2] / "db/migrations/versions" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == down_revision
    return migration


async def _recreate_with_alembic(db_session):
    migrations = [_load(name, down) for name, down in CHAIN]
    connection = await db_session.connection()

    def roundtrip(sync_connection):
        op = Operations(MigrationContext.configure(sync_connection))
        for migration in migrations:
            migration.op = op
        for migration in reversed(migrations):
            migration.downgrade()
        tables = inspect(sync_connection).get_table_names()
        assert "brand_figures" not in tables
        assert "canonical_member_facts" in tables
        for migration in migrations:
            migration.upgrade()
        inspector = inspect(sync_connection)
        columns = inspector.get_columns("brand_figures")
        assert len(columns) == len(BrandFigure.__table__.columns)
        for column in columns:
            model = BrandFigure.__table__.columns[column["name"]]
            assert column["nullable"] == model.nullable
            assert str(column["type"].compile(dialect=sync_connection.dialect)) == str(
                model.type.compile(dialect=sync_connection.dialect)
            )
        checks = inspector.get_check_constraints("brand_figures")
        model_checks = {
            c.name for c in BrandFigure.__table__.constraints if c.__class__.__name__ == "CheckConstraint"
        }
        assert {c["name"] for c in checks} == model_checks == {
            "ck_brand_figures_status", "ck_brand_figures_level",
        }

    await connection.run_sync(roundtrip)


@requires_db
async def test_alembic_roundtrip_preserves_filed_member_facts(db_session):
    accns = await _cpb(db_session, years=(2024,))
    source = _row(CPB, accns[2024], CARRYING, "pace", 2024, 100)
    db_session.add(source)
    await db_session.flush()
    source_id = source.id
    await materialize_brand_carrying_values(db_session, CPB)
    figures = await _figures(db_session)
    assert len(figures) == 1
    assert figures[0].source_member_fact_id == source_id
    await _recreate_with_alembic(db_session)
    assert len(await _figures(db_session)) == 0
    sources = list((await db_session.execute(select(CanonicalMemberFact))).scalars().all())
    assert len(sources) == 1
    assert sources[0].id == source_id and sources[0].value == 100


@requires_db
@pytest.mark.parametrize("schema", ["model", "alembic"])
async def test_both_schemas_enforce_the_same_tri_state_constraint(db_session, schema):
    if schema == "alembic":
        await _recreate_with_alembic(db_session)
    accns = await _cpb(db_session, years=(2024,))
    source = _row(CPB, accns[2024], CARRYING, "pace", 2024, 0)
    db_session.add(source)
    await db_session.flush()
    base = dict(
        issuer_cik=CPB, brand_key="pace", figure="carrying_value", fiscal_year=2024,
        formula_version="brand_carrying_value_v1", mapping_version=MAPPING_VERSION,
        kind="named_brand", source_axis=CLASS_AXIS, basis="carrying_value",
        period_end=source.period_end, unit="USD", caveats=[], source_member_fact_id=source.id,
    )
    for status, value, reason in (
        ("ok", None, None), ("insufficient_data", 1, "missing"),
        ("insufficient_data", None, None), ("unknown", 1, None),
    ):
        with pytest.raises(IntegrityError, match="ck_brand_figures_status"):
            async with db_session.begin_nested():
                await db_session.execute(insert(BrandFigure).values(
                    **base, status=status, value=value, reason=reason,
                ))
    await db_session.execute(insert(BrandFigure).values(**base, status="ok", value=0))
    await db_session.execute(insert(BrandFigure).values(**(base | {
        "fiscal_year": 2023, "basis": None, "period_end": None, "unit": None,
        "source_member_fact_id": None, "status": "insufficient_data",
        "value": None, "reason": "missing",
    })))
    rows = await _figures(db_session)
    assert len(rows) == 2
    assert {(row.status, row.value) for row in rows} == {("ok", 0), ("insufficient_data", None)}
