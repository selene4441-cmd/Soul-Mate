"""add conversation v0.1 lifecycle

Revision ID: 7c9b1f2a4d6e
Revises: 4a54ef1b0a3e
Create Date: 2026-09-12 15:30:00.000000
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "7c9b1f2a4d6e"
down_revision: str | None = "4a54ef1b0a3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pair_key(left: str, right: str) -> str:
    first, second = sorted((left, right))
    return f"{first}:{second}"


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    op.add_column("matches", sa.Column("pair_key", sa.String(length=65), nullable=True))
    op.add_column("matches", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("matches", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("matches", sa.Column("closed_by", sa.String(length=32), nullable=True))
    op.add_column("matches", sa.Column("close_reason", sa.String(length=80), nullable=True))
    rows = bind.execute(sa.text("SELECT id, user_a_id, user_b_id, created_at FROM matches")).mappings()
    seen: set[str] = set()
    for row in rows:
        key = _pair_key(row["user_a_id"], row["user_b_id"])
        if key in seen:
            raise RuntimeError(f"duplicate active match pair requires manual merge: {key}")
        seen.add(key)
        bind.execute(
            sa.text(
                "UPDATE matches SET pair_key=:pair_key, accepted_at=:accepted_at, "
                "status=CASE WHEN status='connected' THEN 'active' ELSE status END WHERE id=:id"
            ),
            {"pair_key": key, "accepted_at": row["created_at"], "id": row["id"]},
        )
    with op.batch_alter_table("matches") as batch:
        batch.alter_column("pair_key", existing_type=sa.String(length=65), nullable=False)
        batch.create_unique_constraint("uq_matches_pair_key", ["pair_key"])
        batch.create_foreign_key("fk_matches_closed_by", "users", ["closed_by"], ["id"], ondelete="SET NULL")

    op.add_column(
        "conversations",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("conversations", sa.Column("context_snapshot", sa.JSON(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("conversations", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
    )
    bind.execute(sa.text("UPDATE conversations SET context_snapshot='{}', opened_at=created_at"))
    with op.batch_alter_table("conversations") as batch:
        batch.alter_column("context_snapshot", existing_type=sa.JSON(), nullable=False)
        batch.alter_column("opened_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.create_index("ix_conversations_status", ["status"], unique=False)
        batch.create_index("ix_conversations_last_message_at", ["last_message_at"], unique=False)

    op.add_column(
        "messages",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="text"),
    )
    op.add_column("messages", sa.Column("reply_to_id", sa.String(length=32), nullable=True))
    op.add_column("messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "messages",
        sa.Column("moderation_status", sa.String(length=20), nullable=False, server_default="normal"),
    )
    with op.batch_alter_table("messages") as batch:
        batch.create_foreign_key("fk_messages_reply_to", "messages", ["reply_to_id"], ["id"], ondelete="SET NULL")

    op.add_column("safety_events", sa.Column("conversation_id", sa.String(length=32), nullable=True))
    op.add_column("safety_events", sa.Column("message_id", sa.String(length=32), nullable=True))
    op.add_column("safety_events", sa.Column("details_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_safety_events_conversation_id", "safety_events", ["conversation_id"])
    op.create_index("ix_safety_events_message_id", "safety_events", ["message_id"])
    with op.batch_alter_table("safety_events") as batch:
        batch.create_foreign_key(
            "fk_safety_events_conversation",
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_safety_events_message",
            "messages",
            ["message_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.add_column("outbox_events", sa.Column("event_key", sa.String(length=80), nullable=True))
    op.add_column(
        "outbox_events",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("outbox_events", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("locked_by", sa.String(length=80), nullable=True))
    op.add_column("outbox_events", sa.Column("last_error", sa.String(length=500), nullable=True))
    bind.execute(
        sa.text(
            "UPDATE outbox_events SET event_key=id, available_at=created_at "
            "WHERE event_key IS NULL OR available_at IS NULL"
        )
    )
    with op.batch_alter_table("outbox_events") as batch:
        batch.alter_column("event_key", existing_type=sa.String(length=80), nullable=False)
        batch.alter_column(
            "available_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch.create_unique_constraint("uq_outbox_events_event_key", ["event_key"])

    op.create_table(
        "connection_requests",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("pair_key", sa.String(length=65), nullable=False),
        sa.Column("requester_id", sa.String(length=32), nullable=False),
        sa.Column("recipient_id", sa.String(length=32), nullable=False),
        sa.Column("recommendation_id", sa.String(length=32), nullable=True),
        sa.Column("recommendation_session_id", sa.String(length=64), nullable=True),
        sa.Column("source_feature_ids", sa.JSON(), nullable=False),
        sa.Column("source_versions", sa.JSON(), nullable=False),
        sa.Column("cue_type", sa.String(length=20), nullable=False),
        sa.Column("topic_text", sa.String(length=300), nullable=False),
        sa.Column("personal_message", sa.String(length=300), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason_private", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connection_requests_pair_key", "connection_requests", ["pair_key"])
    op.create_index("ix_connection_requests_requester_id", "connection_requests", ["requester_id"])
    op.create_index("ix_connection_requests_recipient_id", "connection_requests", ["recipient_id"])
    op.create_index("ix_connection_requests_status", "connection_requests", ["status"])
    op.create_index("ix_connection_requests_expires_at", "connection_requests", ["expires_at"])
    op.create_index(
        "uq_connection_request_pending_pair",
        "connection_requests",
        ["pair_key"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "conversation_members",
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_state", sa.String(length=20), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("conversation_id", "user_id"),
    )
    op.create_index("ix_conversation_members_user_id", "conversation_members", ["user_id"])
    match_rows = bind.execute(sa.text("SELECT id, match_id FROM conversations")).mappings()
    for row in match_rows:
        members = bind.execute(
            sa.text(
                "SELECT user_a_id, user_b_id FROM matches WHERE id=:match_id"
            ),
            {"match_id": row["match_id"]},
        ).mappings().first()
        if not members:
            continue
        for user_id in (members["user_a_id"], members["user_b_id"]):
            bind.execute(
                sa.text(
                    "INSERT INTO conversation_members "
                    "(conversation_id, user_id, notification_state, created_at, updated_at) "
                    "VALUES (:conversation_id, :user_id, 'normal', :now, :now)"
                ),
                {"conversation_id": row["id"], "user_id": user_id, "now": now},
            )

    op.create_table(
        "conversation_cues",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("connection_request_id", sa.String(length=32), nullable=True),
        sa.Column("cue_type", sa.String(length=20), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("source_feature_ids", sa.JSON(), nullable=False),
        sa.Column("source_versions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_request_id"], ["connection_requests.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_cues_conversation_id", "conversation_cues", ["conversation_id"])
    op.create_index("ix_conversation_cues_status", "conversation_cues", ["status"])

    op.create_table(
        "blocks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("blocker_id", sa.String(length=32), nullable=False),
        sa.Column("blocked_id", sa.String(length=32), nullable=False),
        sa.Column("pair_key", sa.String(length=65), nullable=False),
        sa.Column("reason_private", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_blocks_blocker_id", "blocks", ["blocker_id"])
    op.create_index("ix_blocks_blocked_id", "blocks", ["blocked_id"])
    op.create_index("ix_blocks_pair_key", "blocks", ["pair_key"])
    op.create_index(
        "uq_block_active_pair",
        "blocks",
        ["blocker_id", "blocked_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_dedupe_key"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_kind", "notifications", ["kind"])
    op.create_index("ix_notifications_entity_id", "notifications", ["entity_id"])
    op.create_index("ix_notifications_state", "notifications", ["state"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("blocks")
    op.drop_table("conversation_cues")
    op.drop_table("conversation_members")
    op.drop_table("connection_requests")

    with op.batch_alter_table("outbox_events") as batch:
        batch.drop_constraint("uq_outbox_events_event_key", type_="unique")
        batch.drop_column("last_error")
        batch.drop_column("locked_by")
        batch.drop_column("locked_at")
        batch.drop_column("available_at")
        batch.drop_column("event_key")

    op.drop_index("ix_safety_events_message_id", table_name="safety_events")
    op.drop_index("ix_safety_events_conversation_id", table_name="safety_events")
    with op.batch_alter_table("safety_events") as batch:
        batch.drop_constraint("fk_safety_events_message", type_="foreignkey")
        batch.drop_constraint("fk_safety_events_conversation", type_="foreignkey")
        batch.drop_column("details_hash")
        batch.drop_column("message_id")
        batch.drop_column("conversation_id")

    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("fk_messages_reply_to", type_="foreignkey")
        batch.drop_column("moderation_status")
        batch.drop_column("deleted_at")
        batch.drop_column("reply_to_id")
        batch.drop_column("kind")

    with op.batch_alter_table("conversations") as batch:
        batch.drop_index("ix_conversations_last_message_at")
        batch.drop_index("ix_conversations_status")
        batch.drop_column("last_message_at")
        batch.drop_column("closed_at")
        batch.drop_column("opened_at")
        batch.drop_column("context_snapshot")
        batch.drop_column("status")

    with op.batch_alter_table("matches") as batch:
        batch.drop_constraint("fk_matches_closed_by", type_="foreignkey")
        batch.drop_constraint("uq_matches_pair_key", type_="unique")
        batch.drop_column("close_reason")
        batch.drop_column("closed_by")
        batch.drop_column("closed_at")
        batch.drop_column("accepted_at")
        batch.drop_column("pair_key")
