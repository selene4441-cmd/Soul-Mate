"""conversations/messages + users.consent_scopes

Revision ID: 0007_conversations_messages_consent_scopes
Revises: 0006_relationships
Create Date: 2026-09-12

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_conversations_messages_consent_scopes"
down_revision = "0006_relationships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("consent_scopes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_a", sa.Integer(), nullable=False),
        sa.Column("user_b", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_a"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_b"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_a", "user_b", name="uq_conversations_pair"),
    )
    op.create_index(op.f("ix_conversations_user_a"), "conversations", ["user_a"], unique=False)
    op.create_index(op.f("ix_conversations_user_b"), "conversations", ["user_b"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_messages_sender_id"), "messages", ["sender_id"], unique=False)
    op.create_index(op.f("ix_messages_created_at"), "messages", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_created_at"), table_name="messages")
    op.drop_index(op.f("ix_messages_sender_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_conversations_user_b"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_user_a"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_column("users", "consent_scopes")

