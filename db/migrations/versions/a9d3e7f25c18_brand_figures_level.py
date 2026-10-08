"""brand_figures.level — the level a filing supports a figure at (Story 13.4d)

Impairment is charged per brand by CPB, only company-wide by ZTS, and not at all
by QSR. That level is stored as data beside each impairment row, never inferred
from which figure or table a row sits in. NULL for figures where level is not a
question (13.4c's carrying value).

Revision ID: a9d3e7f25c18
Revises: f3a8c2d61b47
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9d3e7f25c18"
down_revision: Union[str, None] = "f3a8c2d61b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("brand_figures", sa.Column("level", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_brand_figures_level",
        "brand_figures",
        "level IS NULL OR level IN ('brand', 'filer_only', 'none')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_brand_figures_level", "brand_figures", type_="check")
    op.drop_column("brand_figures", "level")
