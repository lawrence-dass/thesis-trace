"""Preserve all XBRL qualifiers on canonical member facts.

The member-aware selector previously grouped on the one mapped axis/member and
could therefore collapse two distinct multi-axis contexts into one current row.
The full context dimensions are provenance; a normalized context key is the
identity for this store so a same-year member rename cannot split one row.

Revision ID: d4f61a2b9c30
Revises: a7c3e5019d42
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4f61a2b9c30"
down_revision: Union[str, None] = "a7c3e5019d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "canonical_member_facts",
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "canonical_member_facts",
        sa.Column("context_key", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE canonical_member_facts AS cmf
            SET dimensions = rf.dimensions,
                context_key = jsonb_set(
                    rf.dimensions,
                    ARRAY[cmf.axis_as_filed],
                    to_jsonb(cmf.member_key),
                    false
                )
            FROM raw_facts AS rf
            WHERE cmf.selected_from_raw_fact_id = rf.id
              AND rf.dimensions IS NOT NULL
              AND rf.dimensions ? cmf.axis_as_filed
            """
        )
    )
    missing = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM canonical_member_facts "
            "WHERE dimensions IS NULL OR context_key IS NULL LIMIT 1"
        )
    ).scalar()
    if missing is not None:
        raise RuntimeError(
            "Cannot backfill canonical_member_facts context from its selected raw facts"
        )
    op.alter_column("canonical_member_facts", "dimensions", nullable=False)
    op.alter_column("canonical_member_facts", "context_key", nullable=False)
    op.drop_index("uq_canonical_member_facts_key", table_name="canonical_member_facts")
    op.create_index(
        "uq_canonical_member_facts_key",
        "canonical_member_facts",
        [
            "issuer_cik",
            "canonical_concept",
            "member_key",
            "fiscal_year",
            "mapping_version",
            "context_key",
        ],
        unique=True,
        postgresql_where=sa.text("NOT superseded"),
    )


def downgrade() -> None:
    # Dropping this column would discard AD-3/AD-19 provenance.  An empty
    # scratch database can reverse the migration; a populated database must
    # retain the historical qualifier data and migrate it deliberately.
    if op.get_bind().execute(
        sa.text("SELECT 1 FROM canonical_member_facts WHERE dimensions IS NOT NULL LIMIT 1")
    ).scalar() is not None:
        raise RuntimeError(
            "Cannot drop canonical_member_facts.dimensions while member history exists"
        )
    op.drop_index("uq_canonical_member_facts_key", table_name="canonical_member_facts")
    op.create_index(
        "uq_canonical_member_facts_key",
        "canonical_member_facts",
        ["issuer_cik", "canonical_concept", "member_key", "fiscal_year", "mapping_version"],
        unique=True,
        postgresql_where=sa.text("NOT superseded"),
    )
    op.drop_column("canonical_member_facts", "context_key")
    op.drop_column("canonical_member_facts", "dimensions")
