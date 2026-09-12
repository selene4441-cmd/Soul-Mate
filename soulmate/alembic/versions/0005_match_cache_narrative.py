"""match_cache narrative

Revision ID: 0005_match_cache_narrative
Revises: 0004_match_cache
Create Date: 2026-09-12

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_match_cache_narrative"
down_revision = "0004_match_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("match_cache", sa.Column("narrative", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_cache", "narrative")

