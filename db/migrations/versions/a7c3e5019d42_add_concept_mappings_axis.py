"""concept_mappings.axis — project the dimensioned rules too (Story 13.3)

`concept_mappings` is the audit projection of the mapping spec: it exists so a
stored canonical fact can be traced back to the rule set that produced it. Story
13.3 adds rules that only apply to facts carrying an XBRL member, and without an
axis column the projection cannot represent them — it would show one row for
IndefiniteLivedIntangibleAssetsExcludingGoodwill and no way to see that the same
source concept resolves per-brand carrying value under one member and CPB's
within-10%-coverage aggregate under another.

NULL means undimensioned, which is every rule written before this story, so the
column is nullable and existing rows stay correct without a backfill.

Member ALIASES are deliberately not projected: they are per-filer and per-era
(CPB renames its own members between filings), and the versioned spec file is
what reproduces them under AD-2 — the same reasoning that keeps fallback
priority as list position in the spec rather than a second stored copy.

Revision ID: a7c3e5019d42
Revises: e91b7c4d2a05
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c3e5019d42'
down_revision: Union[str, None] = 'e91b7c4d2a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('concept_mappings', sa.Column('axis', sa.String(length=256), nullable=True))


def downgrade() -> None:
    # Safe to drop: the column is additive metadata for the projection, and the
    # rules themselves live in the versioned spec files, not here.
    op.drop_column('concept_mappings', 'axis')
