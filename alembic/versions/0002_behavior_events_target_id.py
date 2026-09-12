"""behavior_events target_id

Revision ID: 0002_behavior_events_target_id
Revises: 0001_init
Create Date: 2026-09-12

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_behavior_events_target_id"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("behavior_events", sa.Column("target_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("behavior_events", "target_id")

