"""add score_runs.caveat_reason

Records WHY a run is computed_with_caveat, so the explanation layer renders the
right reason per model instead of hardcoding Altman's capital-intensity wording
for every caveated run.

Revision ID: b2d5f8c1a334
Revises: a1c4e7b9f012
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d5f8c1a334'
down_revision: Union[str, None] = 'a1c4e7b9f012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing runs keep their applicability; score_runs is append-only
    # (AD-6) so prior rows are superseded by new runs rather than backfilled.
    op.add_column('score_runs', sa.Column('caveat_reason', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('score_runs', 'caveat_reason')
