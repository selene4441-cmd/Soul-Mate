from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import Block, Match, pair_key_for


def relationship_pair_key(user_a_id: str, user_b_id: str) -> str:
    return pair_key_for(user_a_id, user_b_id)


def has_active_block(db: Session, user_a_id: str, user_b_id: str) -> bool:
    key = relationship_pair_key(user_a_id, user_b_id)
    return (
        db.scalar(
            select(Block.id).where(
                Block.pair_key == key,
                Block.revoked_at.is_(None),
            )
        )
        is not None
    )


def find_match(db: Session, user_a_id: str, user_b_id: str) -> Match | None:
    return db.scalar(
        select(Match).where(
            Match.pair_key == relationship_pair_key(user_a_id, user_b_id),
        )
    )


def find_pair_conversation_ids(db: Session, user_a_id: str, user_b_id: str) -> list[str]:
    from app.models import Conversation

    match = find_match(db, user_a_id, user_b_id)
    if not match:
        return []
    return list(
        db.scalars(select(Conversation.id).where(Conversation.match_id == match.id)).all()
    )


def pair_filter(user_a_id: str, user_b_id: str):
    return or_(
        and_(Match.user_a_id == user_a_id, Match.user_b_id == user_b_id),
        and_(Match.user_a_id == user_b_id, Match.user_b_id == user_a_id),
    )
