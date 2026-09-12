"""relationships and relationship_signals

Revision ID: 0006_relationships
Revises: 0005_match_cache_narrative
Create Date: 2026-09-12

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_relationships"
down_revision = "0005_match_cache_narrative"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_a", sa.Integer(), nullable=False),
        sa.Column("user_b", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("alpha", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("beta", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_a"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_b"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_a", "user_b", name="uq_relationships_pair"),
    )
    op.create_index(op.f("ix_relationships_user_a"), "relationships", ["user_a"], unique=False)
    op.create_index(op.f("ix_relationships_user_b"), "relationships", ["user_b"], unique=False)

    op.create_table(
        "relationship_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("relationship_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_relationship_signals_relationship_id"),
        "relationship_signals",
        ["relationship_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_relationship_signals_created_at"),
        "relationship_signals",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_relationship_signals_created_at"), table_name="relationship_signals")
    op.drop_index(op.f("ix_relationship_signals_relationship_id"), table_name="relationship_signals")
    op.drop_table("relationship_signals")
    op.drop_index(op.f("ix_relationships_user_b"), table_name="relationships")
    op.drop_index(op.f("ix_relationships_user_a"), table_name="relationships")
    op.drop_table("relationships")

