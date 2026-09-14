"""canonical_member_facts — per-member canonical store (Story 13.3)

Dimensioned facts have had nowhere to live since Story 13.2 began ingesting
them. `canonical_facts` is keyed (issuer_cik, canonical_concept, fiscal_year,
mapping_version) with no member, so CPB's three FY2025 brand impairments all
collide on one key and two are lost; AD-3 rule 0 therefore keeps dimensioned
facts out of that table entirely. This is where they land instead.

Two member columns on purpose (story_13_3_brand_member_live_verification):
`member_key` is the spec's stable identity for a brand, so one brand stays one
row per year across the filer's renames (Kettle carries three different member
names across four CPB filings); `member_as_filed` keeps the qualified name the
fact actually carried, because AD-19 provenance has to reach the member and a
stable key cannot say which tag a figure came from.

Supersession mirrors canonical_facts (c7e1f4a92b06) one dimension deeper rather
than inventing a second pattern: a partial unique index over non-superseded
rows, so a restated value is a new row and the prior one is kept.

Revision ID: e91b7c4d2a05
Revises: c7e1f4a92b06
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e91b7c4d2a05'
down_revision: Union[str, None] = 'c7e1f4a92b06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'canonical_member_facts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issuer_cik', sa.String(length=10), nullable=False),
        sa.Column('accession_number', sa.String(length=25), nullable=False),
        sa.Column('canonical_concept', sa.String(length=128), nullable=False),
        sa.Column('member_key', sa.String(length=64), nullable=False),
        sa.Column('member_as_filed', sa.String(length=256), nullable=False),
        sa.Column('axis_as_filed', sa.String(length=256), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('value', sa.Numeric(precision=28, scale=6), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('mapping_version', sa.String(length=32), nullable=False),
        sa.Column('selected_from_raw_fact_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('superseded', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('superseded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['issuer_cik'], ['issuers.cik']),
        sa.ForeignKeyConstraint(['accession_number'], ['filings.accession_number']),
        sa.ForeignKeyConstraint(['selected_from_raw_fact_id'], ['raw_facts.id']),
        sa.ForeignKeyConstraint(['superseded_by'], ['canonical_member_facts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_canonical_member_facts_issuer_cik', 'canonical_member_facts', ['issuer_cik']
    )
    op.create_index(
        'ix_canonical_member_facts_canonical_concept',
        'canonical_member_facts', ['canonical_concept'],
    )
    op.create_index(
        'ix_canonical_member_facts_member_key', 'canonical_member_facts', ['member_key']
    )
    op.create_index(
        'ix_canonical_member_facts_fiscal_year', 'canonical_member_facts', ['fiscal_year']
    )
    # One CURRENT fact per (issuer, concept, member, year, version); any number
    # of superseded ones. Same shape as uq_canonical_facts_key, one dimension
    # deeper — deliberately not a second supersession design.
    op.create_index(
        'uq_canonical_member_facts_key',
        'canonical_member_facts',
        ['issuer_cik', 'canonical_concept', 'member_key', 'fiscal_year', 'mapping_version'],
        unique=True,
        postgresql_where=sa.text('NOT superseded'),
    )


def downgrade() -> None:
    # Refuse while history exists, for the reason c7e1f4a92b06 gives: a
    # superseded row may have no replacement, so relying on a constraint
    # violation to stop the drop would not catch every history-bearing database,
    # and dropping the table would discard append-only provenance (AD-2, AD-19).
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT 1 FROM canonical_member_facts WHERE superseded LIMIT 1")
    ).scalar() is not None:
        raise RuntimeError(
            "Cannot drop canonical_member_facts while superseded rows exist; "
            "preserve the append-only history and migrate deliberately"
        )
    op.drop_index('uq_canonical_member_facts_key', table_name='canonical_member_facts')
    op.drop_index('ix_canonical_member_facts_fiscal_year', table_name='canonical_member_facts')
    op.drop_index('ix_canonical_member_facts_member_key', table_name='canonical_member_facts')
    op.drop_index(
        'ix_canonical_member_facts_canonical_concept', table_name='canonical_member_facts'
    )
    op.drop_index('ix_canonical_member_facts_issuer_cik', table_name='canonical_member_facts')
    op.drop_table('canonical_member_facts')
