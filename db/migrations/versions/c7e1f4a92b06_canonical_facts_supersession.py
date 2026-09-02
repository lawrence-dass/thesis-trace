"""canonical_facts supersession (amendment gap)

A 10-K/A that restated a fiscal year's figures never reached canonical_facts:
the table was UNIQUE on (issuer_cik, canonical_concept, fiscal_year,
mapping_version) and canonicalize_issuer skipped any key already present, so
the first value written for a year was permanent. AD-6 requires an amendment
to trigger a new score_run "referencing the new canonical_facts" — impossible
while the facts themselves could not change.

Fix mirrors score_runs (AD-6) one layer down: a restated value is a NEW row and
the prior row is marked superseded, never deleted or mutated, so score_inputs
from earlier runs still resolve to the exact value they were computed from
(AD-2, AD-19). The unique constraint becomes a PARTIAL unique index over
non-superseded rows — one CURRENT fact per key, any number of superseded ones.

Tracked as `canonical_facts_amendment_gap` in engineering-findings.yaml.

Revision ID: c7e1f4a92b06
Revises: b43d7bd6fe33
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c7e1f4a92b06'
down_revision: Union[str, None] = 'b43d7bd6fe33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'canonical_facts',
        sa.Column('superseded', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'canonical_facts',
        sa.Column('superseded_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'canonical_facts_superseded_by_fkey',
        'canonical_facts', 'canonical_facts',
        ['superseded_by'], ['id'],
    )
    # Same name, different shape: the constraint becomes a partial unique index
    # so a superseded row may share its key with the row that replaced it.
    op.drop_constraint('uq_canonical_facts_key', 'canonical_facts', type_='unique')
    op.create_index(
        'uq_canonical_facts_key',
        'canonical_facts',
        ['issuer_cik', 'canonical_concept', 'fiscal_year', 'mapping_version'],
        unique=True,
        postgresql_where=sa.text('NOT superseded'),
    )


def downgrade() -> None:
    # Refuse before dropping the partial index. A superseded row may have no
    # replacement (for example, a derived fact invalidated because an amended
    # operand no longer satisfies its source constraint), so relying on the
    # full unique constraint to fail would not catch every history-bearing
    # database. Dropping these columns would make the old row look current to
    # the pre-migration readers, violating AD-2/AD-19.
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT 1 FROM canonical_facts WHERE superseded LIMIT 1")
    ).scalar() is not None:
        raise RuntimeError(
            "Cannot downgrade canonical_facts supersession while superseded rows exist; "
            "preserve the append-only history and migrate deliberately"
        )
    op.drop_index('uq_canonical_facts_key', table_name='canonical_facts')
    op.create_unique_constraint(
        'uq_canonical_facts_key',
        'canonical_facts',
        ['issuer_cik', 'canonical_concept', 'fiscal_year', 'mapping_version'],
    )
    op.drop_constraint('canonical_facts_superseded_by_fkey', 'canonical_facts', type_='foreignkey')
    op.drop_column('canonical_facts', 'superseded_by')
    op.drop_column('canonical_facts', 'superseded')
