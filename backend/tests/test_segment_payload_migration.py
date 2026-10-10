"""The production segment_payloads schema equals the model, on the guarded test DB."""

from sqlalchemy import inspect, select

from app.models import CanonicalMemberFact, SegmentPayload
from segments.store import materialize_segment_payloads
from tests.conftest import requires_db
from tests.test_brand_figure_migration import _load
from tests.test_brand_figures import _cpb
from tests.test_segment_payloads import REVENUE, _payloads, _seg

MIGRATION = ("c4e8b1d93f27_add_segment_payloads.py", "a9d3e7f25c18")


@requires_db
async def test_alembic_roundtrip_matches_the_model_and_keeps_filed_facts(db_session) -> None:
    accns = await _cpb(db_session, years=(2025,))
    source = _seg(accns[2025], REVENUE, "snacks", 2025, 100)
    db_session.add(source)
    await db_session.flush()
    source_id = source.id
    await materialize_segment_payloads(db_session, "0000016732")
    assert len(await _payloads(db_session)) == 1

    migration = _load(*MIGRATION)
    connection = await db_session.connection()

    def roundtrip(sync_connection):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        migration.op = Operations(MigrationContext.configure(sync_connection))
        migration.downgrade()
        assert "segment_payloads" not in inspect(sync_connection).get_table_names()
        migration.upgrade()
        inspector = inspect(sync_connection)
        table = SegmentPayload.__table__
        columns = inspector.get_columns("segment_payloads")
        assert len(columns) == len(table.columns)
        for column in columns:
            model = table.columns[column["name"]]
            assert column["nullable"] == model.nullable
            assert str(column["type"].compile(dialect=sync_connection.dialect)) == str(
                model.type.compile(dialect=sync_connection.dialect)
            )
        assert {c["name"] for c in inspector.get_check_constraints("segment_payloads")} == {
            c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"
        } == {"ck_segment_payloads_status"}
        assert {c["name"] for c in inspector.get_unique_constraints("segment_payloads")} == {
            "uq_segment_payloads_key"
        }
        assert {
            fk["referred_table"] for fk in inspector.get_foreign_keys("segment_payloads")
        } == {"issuers", "canonical_member_facts", "filings"}

    await connection.run_sync(roundtrip)
    assert len(await _payloads(db_session)) == 0  # derived: recomputable, so dropped
    sources = list((await db_session.execute(select(CanonicalMemberFact))).scalars().all())
    assert len(sources) == 1 and sources[0].id == source_id
