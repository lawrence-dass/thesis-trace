"""segment_payloads — derived per-segment figures (Story 13.5b)

The FILED segment facts land in `canonical_member_facts` (Story 13.5a). This
table carries them per (issuer, axis, member, concept, year, mapping_version) on
the write path (AD-1), the `brand_figures` pattern: `canonical_facts`' one-row-
per-concept-year key would let two segments collide.

Derived and fully recomputable, so the downgrade simply drops it.

Revision ID: c4e8b1d93f27
Revises: a9d3e7f25c18
Create Date: 2026-10-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4e8b1d93f27"
down_revision: Union[str, None] = "a9d3e7f25c18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "segment_payloads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer_cik", sa.String(length=10), nullable=False),
        sa.Column("axis", sa.String(length=256), nullable=False),
        sa.Column("member_key", sa.String(length=64), nullable=False),
        sa.Column("canonical_concept", sa.String(length=128), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("mapping_version", sa.String(length=32), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(precision=28, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("source_member_fact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accession_number", sa.String(length=25), nullable=True),
        sa.Column("member_as_filed", sa.String(length=256), nullable=True),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["issuer_cik"], ["issuers.cik"]),
        sa.ForeignKeyConstraint(["source_member_fact_id"], ["canonical_member_facts.id"]),
        sa.ForeignKeyConstraint(["accession_number"], ["filings.accession_number"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "issuer_cik", "axis", "member_key", "canonical_concept", "fiscal_year",
            "mapping_version",
            name="uq_segment_payloads_key",
        ),
        # A payload is either a value or an explained absence (AD-16), never neither.
        sa.CheckConstraint(
            "(status = 'ok' AND value IS NOT NULL) OR "
            "(status = 'insufficient_data' AND value IS NULL AND reason IS NOT NULL)",
            name="ck_segment_payloads_status",
        ),
    )
    op.create_index("ix_segment_payloads_issuer_cik", "segment_payloads", ["issuer_cik"])


def downgrade() -> None:
    op.drop_index("ix_segment_payloads_issuer_cik", table_name="segment_payloads")
    op.drop_table("segment_payloads")
