"""match_cache

Revision ID: 0004_match_cache
Revises: 0003_profiles_source_hash
Create Date: 2026-09-12

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_match_cache"
down_revision = "0003_profiles_source_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_cache",
        sa.Column("user_id_a", sa.Integer(), nullable=False),
        sa.Column("user_id_b", sa.Integer(), nullable=False),
        sa.Column("profile_hash_a", sa.Text(), nullable=False),
        sa.Column("profile_hash_b", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("entropy", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id_a"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id_b"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id_a", "user_id_b"),
    )


def downgrade() -> None:
    op.drop_table("match_cache")

