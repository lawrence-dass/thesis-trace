"""add canonical_facts.derivation

Records HOW a canonical fact was obtained: NULL when read directly from a filed
XBRL tag, otherwise the name of the rule that computed it. Needed so the read
API can distinguish a filed figure from one ThesisTrace derived — previously
indistinguishable, which let a computed value carry a filed-number citation
(live for SHOP's total_liabilities, and multiplied by IFRS filers under D8).

Revision ID: a1c4e7b9f012
Revises: bd927201da21
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c4e7b9f012'
down_revision: Union[str, None] = 'bd927201da21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing rows are all directly-filed selections (the only prior
    # derivation, total_liabilities, is recomputed on the next canonicalization
    # pass under a new mapping_version rather than backfilled in place — AD-2
    # forbids mutating canonical facts).
    op.add_column('canonical_facts', sa.Column('derivation', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('canonical_facts', 'derivation')
