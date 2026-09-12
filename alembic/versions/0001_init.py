"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-09-12

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("consent", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "elicitations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "behavior_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_behavior_events_created_at", "behavior_events", ["created_at"])
    op.create_index("ix_behavior_events_user_id", "behavior_events", ["user_id"])

    op.create_table(
        "responses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("elicitation_id", sa.Integer(), nullable=False),
        sa.Column("choice", sa.Text(), nullable=False),
        sa.Column("reaction_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["elicitation_id"], ["elicitations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_responses_elicitation_id", "responses", ["elicitation_id"])
    op.create_index("ix_responses_user_id", "responses", ["user_id"])

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    op.create_table(
        "beliefs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_beliefs_confidence"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_beliefs_user_id", "beliefs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_beliefs_user_id", table_name="beliefs")
    op.drop_table("beliefs")
    op.drop_table("profiles")
    op.drop_index("ix_responses_user_id", table_name="responses")
    op.drop_index("ix_responses_elicitation_id", table_name="responses")
    op.drop_table("responses")
    op.drop_index("ix_behavior_events_user_id", table_name="behavior_events")
    op.drop_index("ix_behavior_events_created_at", table_name="behavior_events")
    op.drop_table("behavior_events")
    op.drop_table("elicitations")
    op.drop_table("users")

