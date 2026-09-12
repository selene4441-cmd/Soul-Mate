"""profiles source_hash

Revision ID: 0003_profiles_source_hash
Revises: 0002_behavior_events_target_id
Create Date: 2026-09-12

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_profiles_source_hash"
down_revision = "0002_behavior_events_target_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("source_hash", sa.Text(), nullable=False, server_default=sa.text("''")),
    )


def downgrade() -> None:
    op.drop_column("profiles", "source_hash")

