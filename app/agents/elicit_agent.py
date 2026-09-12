from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.belief import BetaPosterior, Evidence, entropy as bernoulli_entropy, update as beta_update
from app.core.config import settings
from app.core.costlog import CostEvent, append_cost_event, now_iso_utc
from app.core.openai_compat import OpenAICompatClient
from app.models import Belief, Elicitation, ElicitationKind, Profile, Response, User


class ElicitClient(Protocol):
    chat_model: str

    def generate_cards(self, *, user_profile: str, belief_p: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        ...


@dataclass(frozen=True)
class OpenAICompatElicitClient:
    base_url: str
    api_key: str
    chat_model: str = "gpt-5.2"

    def generate_cards(self, *, user_profile: str, belief_p: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        client = OpenAICompatClient(base_url=self.base_url, api_key=self.api_key)
        system = (
            "你是中文交互式引导卡（elicitations）写作助手。"
            "目标：用“措辞可错、可冒犯但不过界”的猜测，引导用户表态以降低不确定性。"
            "每张卡需要：question(一句话)、options(2-4个)、evidence_weight(1-3的整数，表示信号强度)。"
            "约束：不要包含任何个人信息；不要歧视/仇恨/违法内容；不要提及系统/模型。"
            "输出必须是严格 JSON："
            '{"cards":[{"question":<str>,"options":[<str>,...],"evidence_weight":<int>},...]}'
            "必须输出 3 张卡。"
        )
        user = json.dumps(
            {"user_profile": user_profile, "belief_p": round(float(belief_p), 4)},
            ensure_ascii=False,
        )
        result = client.chat_completions(
            model=self.chat_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.7,
            max_tokens=450,
        )
        usage = {
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
        }
        data = json.loads(result.content)
        cards = list(data["cards"])
        return cards, usage


def build_elicit_client_from_env() -> OpenAICompatElicitClient:
    base_url = os.getenv("OPENAI_BASE_URL") or settings.openai_base_url
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    chat_model = os.getenv("OPENAI_MODEL") or settings.openai_model or "gpt-5.2"
    if not base_url or not api_key:
        raise RuntimeError("OPENAI_BASE_URL and OPENAI_API_KEY must be set to call elicitations generator.")
    return OpenAICompatElicitClient(base_url=base_url, api_key=api_key, chat_model=chat_model)


@dataclass(frozen=True)
class GuessCard:
    elicitation_id: int
    question: str
    options: list[str]
    kind: str
    expected_information_gain: float
    evidence_weight: float


def expected_information_gain(posterior: BetaPosterior, *, evidence_weight: float = 1.0) -> float:
    """
    Expected reduction in Bernoulli entropy after observing one binary signal.

    Model: with probability p (current mean) we observe supporting evidence; otherwise disconfirming evidence.
    """
    if evidence_weight <= 0.0:
        raise ValueError("evidence_weight must be > 0")

    p = posterior.mean
    h0 = bernoulli_entropy(p)

    pos = beta_update(posterior, Evidence(positive=evidence_weight, negative=0.0)).mean
    neg = beta_update(posterior, Evidence(positive=0.0, negative=evidence_weight)).mean

    h1 = p * bernoulli_entropy(pos) + (1.0 - p) * bernoulli_entropy(neg)
    return max(0.0, h0 - h1)


def _fallback_cards() -> list[dict[str, Any]]:
    return [
        {
            "question": "我猜：你更在意“被认真对待”，而不是单纯的浪漫。",
            "options": ["同意", "不同意", "不确定"],
            "evidence_weight": 1,
        },
        {
            "question": "我可能错了：你会把暧昧拖久，是因为怕承担不匹配的后果。",
            "options": ["同意", "不同意", "不确定"],
            "evidence_weight": 2,
        },
        {
            "question": "大胆猜测：你宁愿错过，也不想降低标准去“将就”。",
            "options": ["同意", "不同意", "不确定"],
            "evidence_weight": 3,
        },
    ]


def generate_guess_cards(
    *,
    user_id: int,
    posterior: BetaPosterior,
    session: Session,
    client: ElicitClient | None = None,
) -> list[GuessCard]:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("user not found")
    if not user.consent:
        raise PermissionError("user has not consented")

    profile = session.get(Profile, user_id)
    if profile is None or not profile.summary:
        raise ValueError("user profile is missing")

    if client is None:
        client = build_elicit_client_from_env()

    cards: list[dict[str, Any]]
    usage: dict[str, Any] | None = None
    try:
        cards, usage = client.generate_cards(user_profile=profile.summary, belief_p=posterior.mean)
    except Exception:
        cards = _fallback_cards()

    # Normalize to exactly 3 cards.
    cards = (cards or [])[:3]
    while len(cards) < 3:
        cards.append(_fallback_cards()[len(cards)])

    out: list[GuessCard] = []
    for card in cards:
        question = str(card.get("question") or "").strip()
        options = list(card.get("options") or [])
        options = [str(o).strip() for o in options if str(o).strip()]
        if not question:
            continue
        if len(options) < 2:
            options = ["同意", "不同意", "不确定"]

        weight_raw = card.get("evidence_weight", 1)
        try:
            weight = float(int(weight_raw))
        except Exception:
            weight = 1.0
        weight = max(1.0, min(3.0, weight))

        elicitation = Elicitation(
            question=question,
            options=options,
            kind=ElicitationKind.SINGLE_CHOICE,
        )
        session.add(elicitation)
        session.flush()

        ig = expected_information_gain(posterior, evidence_weight=weight)
        out.append(
            GuessCard(
                elicitation_id=int(elicitation.id),
                question=question,
                options=options,
                kind=ElicitationKind.SINGLE_CHOICE.value,
                expected_information_gain=float(ig),
                evidence_weight=float(weight),
            )
        )

    session.commit()

    if usage is not None:
        append_cost_event(
            CostEvent(
                ts=now_iso_utc(),
                endpoint="chat.completions",
                model=getattr(client, "chat_model", "unknown"),
                input_chars=len(profile.summary),
                output_chars=sum(len(c.question) for c in out),
                usage=usage,
                meta={"user_id": user_id, "cards": len(out)},
            )
        )

    return out


def _choice_to_evidence(choice: str, *, weight: float = 1.0) -> Evidence:
    normalized = choice.strip().lower()
    # Allow a bit of flexibility for future option variants.
    positives = {"同意", "是", "更像a", "a", "agree", "yes"}
    negatives = {"不同意", "否", "更像b", "b", "disagree", "no"}
    unsure = {"不确定", "都不是", "不知道", "unsure", "unknown", "skip"}

    if normalized in positives:
        return Evidence(positive=weight, negative=0.0)
    if normalized in negatives:
        return Evidence(positive=0.0, negative=weight)
    if normalized in unsure:
        return Evidence(positive=0.0, negative=0.0)
    # Default: treat as uncertain to avoid over-updating on unknown labels.
    return Evidence(positive=0.0, negative=0.0)


def apply_guess_response(
    *,
    user_id: int,
    elicitation_id: int,
    posterior: BetaPosterior,
    choice: str,
    reaction_time_ms: int,
    session: Session,
    hypothesis: str = "match",
    evidence_weight: float = 1.0,
) -> BetaPosterior:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("user not found")
    if not user.consent:
        raise PermissionError("user has not consented")
    if reaction_time_ms < 0:
        raise ValueError("reaction_time_ms must be >= 0")
    if evidence_weight <= 0:
        raise ValueError("evidence_weight must be > 0")

    elicitation = session.get(Elicitation, elicitation_id)
    if elicitation is None:
        raise ValueError("elicitation not found")

    ev = _choice_to_evidence(choice, weight=evidence_weight)
    new_posterior = beta_update(posterior, ev)

    session.add(
        Response(
            user_id=user_id,
            elicitation_id=elicitation_id,
            choice=choice,
            reaction_time_ms=reaction_time_ms,
        )
    )

    belief = session.execute(
        sa.select(Belief).where(Belief.user_id == user_id, Belief.hypothesis == hypothesis)
    ).scalar_one_or_none()
    if belief is None:
        belief = Belief(user_id=user_id, hypothesis=hypothesis, confidence=float(new_posterior.mean))
        session.add(belief)
    else:
        belief.confidence = float(new_posterior.mean)

    profile = session.get(Profile, user_id)
    if profile is None:
        raise ValueError("profile not found")

    snippet = f"猜测卡反馈：我问「{elicitation.question}」，你选「{choice}」。"
    combined = (profile.summary or "").strip()
    if combined:
        combined = f"{combined}\n{snippet}"
    else:
        combined = snippet
    # Keep summary reasonably short (last 600 chars).
    if len(combined) > 600:
        combined = combined[-600:]
    profile.summary = combined

    session.commit()
    return new_posterior

