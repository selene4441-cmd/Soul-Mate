from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.agents.elicit_agent import (
    GuessCard,
    apply_guess_response,
    generate_guess_cards,
)
from app.agents.match_agent import RerankClient, match_user
from app.agents.profile_agent import LLMClient as ProfileLLMClient
from app.agents.profile_agent import update_user_profile_from_events
from app.core.belief import BetaPosterior
from app.core.belief import entropy as bernoulli_entropy
from app.models import Profile


class FeedbackProvider(Protocol):
    def choose(self, *, cards: list[GuessCard]) -> tuple[int, str, int]:
        """
        Returns: (card_index, choice, reaction_time_ms)
        """


def _now_iso_utc() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _sum_tokens(usage: dict[str, Any] | None) -> int:
    if not usage:
        return 0
    for key in ("total_tokens",):
        val = usage.get(key)
        if isinstance(val, int):
            return val
    total = 0
    for key in ("prompt_tokens", "completion_tokens"):
        val = usage.get(key)
        if isinstance(val, int):
            total += val
    return total


@dataclass(frozen=True)
class RoundResult:
    round_index: int
    user_id: int
    entropy_before: float
    entropy_after: float
    token_cost: int
    match: dict[str, Any]
    explanation: str


def profile_read(*, session: Session, user_id: int) -> Profile:
    profile = session.get(Profile, user_id)
    if profile is None:
        raise ValueError("profile not found")
    return profile


def elicit_generate(
    *,
    session: Session,
    user_id: int,
    posterior: BetaPosterior,
    client: Any | None = None,
) -> list[GuessCard]:
    return generate_guess_cards(user_id=user_id, posterior=posterior, session=session, client=client)


def belief_update(
    *,
    session: Session,
    user_id: int,
    elicitation_id: int,
    posterior: BetaPosterior,
    choice: str,
    reaction_time_ms: int,
    hypothesis: str,
    evidence_weight: float,
) -> BetaPosterior:
    return apply_guess_response(
        user_id=user_id,
        elicitation_id=elicitation_id,
        posterior=posterior,
        choice=choice,
        reaction_time_ms=reaction_time_ms,
        session=session,
        hypothesis=hypothesis,
        evidence_weight=evidence_weight,
    )


def match_search(
    *,
    session: Session,
    user_id: int,
    client: RerankClient | None = None,
    recall_k: int = 50,
) -> dict[str, Any]:
    return match_user(user_id=user_id, session=session, client=client, recall_k=recall_k)


def explain_match(*, session: Session, user_id: int, match: dict[str, Any]) -> str:
    """
    Produces a short explanation without additional LLM cost.
    """
    other_id = int(match["user_id"])
    p1 = profile_read(session=session, user_id=user_id)
    p2 = profile_read(session=session, user_id=other_id)
    reasons = match.get("reasons") or []
    reasons_txt = "\n".join([f"- {r}" for r in reasons]) if reasons else "- （无）"
    return (
        f"匹配对象：{other_id}\n"
        f"分数：{match.get('score')}\n"
        f"匹配不确定性：{match.get('entropy')}\n"
        f"你的画像：{p1.summary}\n"
        f"TA的画像：{p2.summary}\n"
        f"理由：\n{reasons_txt}"
    )


class Orchestrator:
    """
    Main loop: 探测 → 反馈 → 更新 → 匹配 → 解释
    """

    def __init__(
        self,
        *,
        logs_dir: str = "logs",
        belief_hypothesis: str = "match",
        profile_client: ProfileLLMClient | None = None,
        elicit_client: Any | None = None,
        match_client: RerankClient | None = None,
    ) -> None:
        self._logs_dir = logs_dir
        self._belief_hypothesis = belief_hypothesis
        self._profile_client = profile_client
        self._elicit_client = elicit_client
        self._match_client = match_client

    def run_round(
        self,
        *,
        round_index: int,
        session: Session,
        user_id: int,
        posterior: BetaPosterior,
        feedback: FeedbackProvider,
    ) -> tuple[RoundResult, BetaPosterior]:
        entropy_before = bernoulli_entropy(posterior.mean)

        # 探测：确保画像最新（可缓存跳过），并生成猜测卡
        token_cost = 0
        if self._profile_client is not None:
            # profile_agent internally writes cost logs; we only track tokens when the injected client provides it.
            update_user_profile_from_events(user_id=user_id, session=session, client=self._profile_client)

        cards = elicit_generate(
            session=session,
            user_id=user_id,
            posterior=posterior,
            client=self._elicit_client,
        )
        # feedback
        card_index, choice, reaction_time_ms = feedback.choose(cards=cards)
        if card_index < 0 or card_index >= len(cards):
            raise ValueError("feedback card_index out of range")
        card = cards[card_index]

        # 更新：belief + responses + profile.summary append
        posterior2 = belief_update(
            session=session,
            user_id=user_id,
            elicitation_id=card.elicitation_id,
            posterior=posterior,
            choice=choice,
            reaction_time_ms=reaction_time_ms,
            hypothesis=self._belief_hypothesis,
            evidence_weight=card.evidence_weight,
        )
        entropy_after = bernoulli_entropy(posterior2.mean)

        # 匹配：向量召回 + LLM 重排（内部缓存）
        match = match_search(session=session, user_id=user_id, client=self._match_client, recall_k=50)

        # 解释：不额外调用 LLM，直接拼接 reasons + 双方画像引用
        explanation = explain_match(session=session, user_id=user_id, match=match)

        # token cost (best-effort): sum usage fields on injected clients if they expose last_usage.
        for maybe_client in (self._profile_client, self._elicit_client, self._match_client):
            usage = getattr(maybe_client, "last_usage", None)
            token_cost += _sum_tokens(usage)

        result = RoundResult(
            round_index=round_index,
            user_id=user_id,
            entropy_before=entropy_before,
            entropy_after=entropy_after,
            token_cost=token_cost,
            match=match,
            explanation=explanation,
        )
        self._log_round(result)
        return result, posterior2

    def _log_round(self, result: RoundResult) -> None:
        _ensure_dir(self._logs_dir)
        path = os.path.join(self._logs_dir, "orchestrator.jsonl")
        payload = {
            "ts": _now_iso_utc(),
            "round_index": result.round_index,
            "user_id": result.user_id,
            "entropy_before": result.entropy_before,
            "entropy_after": result.entropy_after,
            "delta_entropy": result.entropy_after - result.entropy_before,
            "token_cost": result.token_cost,
            "match": result.match,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
