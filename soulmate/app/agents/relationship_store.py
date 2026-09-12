from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.belief import BetaPosterior, Evidence, update
from app.models import Relationship, RelationshipSignal

PRIOR = BetaPosterior(alpha=1.0, beta=1.0)


def _signal_to_evidence(signal: RelationshipSignal) -> Evidence:
    kind = (signal.kind or "").strip().lower()
    weight = float(signal.weight or 0.0)
    if kind == "conflict":
        return Evidence(positive=0.0, negative=abs(weight))
    if kind in {"repair", "shared_topic"}:
        return Evidence(positive=abs(weight), negative=0.0)
    if kind in {"message_tone", "response_latency"}:
        return (
            Evidence(positive=weight, negative=0.0)
            if weight >= 0.0
            else Evidence(positive=0.0, negative=abs(weight))
        )
    return Evidence(positive=0.0, negative=0.0)


def load_relationship_posterior(
    session: Session,
    *,
    relationship_id: int,
) -> BetaPosterior:
    """无状态回放 relationship_signals，重建某段关系的 Beta 后验。"""
    rows = session.execute(
        select(RelationshipSignal)
        .where(RelationshipSignal.relationship_id == relationship_id)
        .order_by(RelationshipSignal.id.asc())
    ).scalars()

    posterior = PRIOR
    for signal in rows:
        posterior = update(posterior, _signal_to_evidence(signal))
    return posterior


def update_relationship_from_signals(
    session: Session,
    *,
    relationship_id: int,
) -> Relationship:
    """回放 signals 更新 relationships.alpha/beta（relationships 作为可校验缓存）。"""
    relationship = session.get(Relationship, relationship_id)
    if relationship is None:
        raise ValueError("relationship_not_found")

    posterior = load_relationship_posterior(session, relationship_id=relationship_id)
    relationship.alpha = float(posterior.alpha)
    relationship.beta = float(posterior.beta)
    session.commit()
    return relationship
