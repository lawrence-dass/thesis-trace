"""brand_figures — derived per-brand series (Story 13.4c)

`canonical_member_facts` holds FILED per-member values and is owned by
canonicalization. This table holds the per-BRAND series derived from it on the
write path (AD-1): one row per (issuer, brand, figure, year, formula_version,
mapping_version). 13.4d and 13.4e add their figures under the same key.

Derived and fully recomputable from the canonical store, so unlike c7e1f4a92b06
and e91b7c4d2a05 the downgrade simply drops it: there is no append-only history
here to protect.

Revision ID: f3a8c2d61b47
Revises: d4f61a2b9c30
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f3a8c2d61b47"
down_revision: Union[str, None] = "d4f61a2b9c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brand_figures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer_cik", sa.String(length=10), nullable=False),
        sa.Column("brand_key", sa.String(length=64), nullable=False),
        sa.Column("figure", sa.String(length=64), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("mapping_version", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source_axis", sa.String(length=256), nullable=False),
        sa.Column("basis", sa.String(length=32), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(precision=28, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column(
            "caveats", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source_member_fact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["issuer_cik"], ["issuers.cik"]),
        sa.ForeignKeyConstraint(["source_member_fact_id"], ["canonical_member_facts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "issuer_cik", "brand_key", "figure", "fiscal_year",
            "formula_version", "mapping_version",
            name="uq_brand_figures_key",
        ),
        # A figure is either a value or an explained absence (AD-16), never neither.
        sa.CheckConstraint(
            "(status = 'ok' AND value IS NOT NULL) OR "
            "(status = 'insufficient_data' AND value IS NULL AND reason IS NOT NULL)",
            name="ck_brand_figures_status",
        ),
    )
    op.create_index("ix_brand_figures_issuer_cik", "brand_figures", ["issuer_cik"])
    op.create_index("ix_brand_figures_brand_key", "brand_figures", ["brand_key"])


def downgrade() -> None:
    op.drop_index("ix_brand_figures_brand_key", table_name="brand_figures")
    op.drop_index("ix_brand_figures_issuer_cik", table_name="brand_figures")
    op.drop_table("brand_figures")
