"""v1 auth/consents/claims/recommendations/matches

Revision ID: 0008_v1_auth_claims_matches
Revises: 0007_conversations_messages_consent_scopes
Create Date: 2026-09-12

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_v1_auth_claims_matches"
down_revision = "0007_conversations_messages_consent_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email", sa.String(length=320), nullable=True))
        batch.add_column(sa.Column("display_name", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("birth_year", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("region", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("role", sa.Text(), nullable=False, server_default="user"))
        batch.add_column(sa.Column("status", sa.Text(), nullable=False, server_default="active"))
        batch.add_column(sa.Column("password_salt", sa.Text(), nullable=True))
        batch.add_column(sa.Column("password_hash", sa.Text(), nullable=True))
        batch.create_index("ix_users_email", ["email"], unique=True)

    op.create_table(
        "session_tokens",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_session_tokens_user_id"), "session_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_session_tokens_created_at"), "session_tokens", ["created_at"], unique=False)
    op.create_index(op.f("ix_session_tokens_expires_at"), "session_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_session_tokens_revoked_at"), "session_tokens", ["revoked_at"], unique=False)

    op.create_table(
        "consents",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "scope", name="uq_consents_user_scope"),
    )
    op.create_index(op.f("ix_consents_user_id"), "consents", ["user_id"], unique=False)
    op.create_index(op.f("ix_consents_scope"), "consents", ["scope"], unique=False)
    op.create_index(op.f("ix_consents_revoked_at"), "consents", ["revoked_at"], unique=False)
    op.create_index("ix_consents_active", "consents", ["scope", "revoked_at"], unique=False)

    op.create_table(
        "evidences",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidences_user_id"), "evidences", ["user_id"], unique=False)
    op.create_index(op.f("ix_evidences_created_at"), "evidences", ["created_at"], unique=False)

    op.create_table(
        "claims",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.Text(), nullable=False, server_default="preference"),
        sa.Column("evidence_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sensitivity", sa.Text(), nullable=False, server_default="L1"),
        sa.Column("user_editable", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("correction_state", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claims_user_id"), "claims", ["user_id"], unique=False)
    op.create_index(op.f("ix_claims_dimension"), "claims", ["dimension"], unique=False)
    op.create_index(op.f("ix_claims_observed_at"), "claims", ["observed_at"], unique=False)
    op.create_index(op.f("ix_claims_expires_at"), "claims", ["expires_at"], unique=False)
    op.create_index("ix_claims_user_dimension", "claims", ["user_id", "dimension"], unique=False)

    op.create_table(
        "recommendation_sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_recommendation_sessions_user_id"),
        "recommendation_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recommendation_sessions_generated_at"),
        "recommendation_sessions",
        ["generated_at"],
        unique=False,
    )

    op.create_table(
        "recommendation_items",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False, server_default=""),
        sa.Column("common_signals", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("differences", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("unknowns", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("how_to_continue", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["recommendation_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "candidate_id", name="uq_reco_item_session_candidate"),
    )
    op.create_index(
        op.f("ix_recommendation_items_session_id"),
        "recommendation_items",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recommendation_items_user_id"),
        "recommendation_items",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recommendation_items_candidate_id"),
        "recommendation_items",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_reco_items_user_candidate",
        "recommendation_items",
        ["user_id", "candidate_id"],
        unique=False,
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_user_id", "to_user_id", name="uq_invitations_from_to"),
    )
    op.create_index(op.f("ix_invitations_from_user_id"), "invitations", ["from_user_id"], unique=False)
    op.create_index(op.f("ix_invitations_to_user_id"), "invitations", ["to_user_id"], unique=False)
    op.create_index("ix_invitations_pair", "invitations", ["from_user_id", "to_user_id"], unique=False)
    op.create_index(op.f("ix_invitations_created_at"), "invitations", ["created_at"], unique=False)

    op.create_table(
        "matches",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_a_id", sa.Integer(), nullable=False),
        sa.Column("user_b_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_a_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_b_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_a_id", "user_b_id", name="uq_matches_pair"),
    )
    op.create_index(op.f("ix_matches_user_a_id"), "matches", ["user_a_id"], unique=False)
    op.create_index(op.f("ix_matches_user_b_id"), "matches", ["user_b_id"], unique=False)

    op.create_table(
        "match_messages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("match_id", sa.Text(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("client_message_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id", "sender_id", "client_message_id", name="uq_match_messages_idempotent"
        ),
    )
    op.create_index(op.f("ix_match_messages_match_id"), "match_messages", ["match_id"], unique=False)
    op.create_index(op.f("ix_match_messages_sender_id"), "match_messages", ["sender_id"], unique=False)
    op.create_index(op.f("ix_match_messages_created_at"), "match_messages", ["created_at"], unique=False)
    op.create_index("ix_match_messages_match_created", "match_messages", ["match_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_match_messages_match_created", table_name="match_messages")
    op.drop_index(op.f("ix_match_messages_created_at"), table_name="match_messages")
    op.drop_index(op.f("ix_match_messages_sender_id"), table_name="match_messages")
    op.drop_index(op.f("ix_match_messages_match_id"), table_name="match_messages")
    op.drop_table("match_messages")

    op.drop_index(op.f("ix_matches_user_b_id"), table_name="matches")
    op.drop_index(op.f("ix_matches_user_a_id"), table_name="matches")
    op.drop_table("matches")

    op.drop_index(op.f("ix_invitations_created_at"), table_name="invitations")
    op.drop_index("ix_invitations_pair", table_name="invitations")
    op.drop_index(op.f("ix_invitations_to_user_id"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_from_user_id"), table_name="invitations")
    op.drop_table("invitations")

    op.drop_index("ix_reco_items_user_candidate", table_name="recommendation_items")
    op.drop_index(op.f("ix_recommendation_items_candidate_id"), table_name="recommendation_items")
    op.drop_index(op.f("ix_recommendation_items_user_id"), table_name="recommendation_items")
    op.drop_index(op.f("ix_recommendation_items_session_id"), table_name="recommendation_items")
    op.drop_table("recommendation_items")

    op.drop_index(op.f("ix_recommendation_sessions_generated_at"), table_name="recommendation_sessions")
    op.drop_index(op.f("ix_recommendation_sessions_user_id"), table_name="recommendation_sessions")
    op.drop_table("recommendation_sessions")

    op.drop_index("ix_claims_user_dimension", table_name="claims")
    op.drop_index(op.f("ix_claims_expires_at"), table_name="claims")
    op.drop_index(op.f("ix_claims_observed_at"), table_name="claims")
    op.drop_index(op.f("ix_claims_dimension"), table_name="claims")
    op.drop_index(op.f("ix_claims_user_id"), table_name="claims")
    op.drop_table("claims")

    op.drop_index(op.f("ix_evidences_created_at"), table_name="evidences")
    op.drop_index(op.f("ix_evidences_user_id"), table_name="evidences")
    op.drop_table("evidences")

    op.drop_index("ix_consents_active", table_name="consents")
    op.drop_index(op.f("ix_consents_revoked_at"), table_name="consents")
    op.drop_index(op.f("ix_consents_scope"), table_name="consents")
    op.drop_index(op.f("ix_consents_user_id"), table_name="consents")
    op.drop_table("consents")

    op.drop_index(op.f("ix_session_tokens_revoked_at"), table_name="session_tokens")
    op.drop_index(op.f("ix_session_tokens_expires_at"), table_name="session_tokens")
    op.drop_index(op.f("ix_session_tokens_created_at"), table_name="session_tokens")
    op.drop_index(op.f("ix_session_tokens_user_id"), table_name="session_tokens")
    op.drop_table("session_tokens")

    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email")
        batch.drop_column("password_hash")
        batch.drop_column("password_salt")
        batch.drop_column("status")
        batch.drop_column("role")
        batch.drop_column("region")
        batch.drop_column("birth_year")
        batch.drop_column("display_name")
        batch.drop_column("email")

