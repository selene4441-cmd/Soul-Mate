from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.belief import BetaPosterior, Evidence
from app.core.belief import entropy as bernoulli_entropy
from app.core.belief import update as beta_update
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
            "options": [
                {"text": "同意", "polarity": "confirm"},
                {"text": "不同意", "polarity": "disconfirm"},
                {"text": "不确定", "polarity": "uncertain"},
            ],
            "evidence_weight": 1,
        },
        {
            "question": "我可能错了：你会把暧昧拖久，是因为怕承担不匹配的后果。",
            "options": [
                {"text": "同意", "polarity": "confirm"},
                {"text": "不同意", "polarity": "disconfirm"},
                {"text": "不确定", "polarity": "uncertain"},
            ],
            "evidence_weight": 2,
        },
        {
            "question": "大胆猜测：你宁愿错过，也不想降低标准去“将就”。",
            "options": [
                {"text": "同意", "polarity": "confirm"},
                {"text": "不同意", "polarity": "disconfirm"},
                {"text": "不确定", "polarity": "uncertain"},
            ],
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
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError):
        cards = _fallback_cards()

    # Normalize to exactly 3 cards.
    cards = (cards or [])[:3]
    while len(cards) < 3:
        cards.append(_fallback_cards()[len(cards)])

    out: list[GuessCard] = []
    for card in cards:
        question = str(card.get("question") or "").strip()
        options_raw = card.get("options")
        options_struct = _normalize_options(options_raw)
        options_text = [o["text"] for o in options_struct]
        if not question:
            continue
        if len(options_struct) < 2:
            options_struct = _normalize_options(_fallback_cards()[0]["options"])
            options_text = [o["text"] for o in options_struct]

        weight_raw = card.get("evidence_weight", 1)
        try:
            weight = float(int(weight_raw))
        except (TypeError, ValueError):
            weight = 1.0
        weight = max(1.0, min(3.0, weight))

        elicitation = Elicitation(
            question=question,
            options=options_struct,
            kind=ElicitationKind.SINGLE_CHOICE,
        )
        session.add(elicitation)
        session.flush()

        ig = expected_information_gain(posterior, evidence_weight=weight)
        out.append(
            GuessCard(
                elicitation_id=int(elicitation.id),
                question=question,
                options=options_text,
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


def _polarity_to_evidence(polarity: str, *, weight: float) -> Evidence:
    p = polarity.strip().lower()
    if p == "confirm":
        return Evidence(positive=weight, negative=0.0)
    if p == "disconfirm":
        return Evidence(positive=0.0, negative=weight)
    return Evidence(positive=0.0, negative=0.0)


def _choice_to_evidence_fallback(choice: str, *, weight: float = 1.0) -> Evidence:
    """
    Backward-compatibility fallback when elicitation.options does not carry polarity metadata.
    Uses keyword prefix matching (not exact equality) to support long option sentences.
    """
    raw = choice.strip()
    lowered = raw.lower()

    positive_prefixes = ("同意", "是", "赞同", "确认", "agree", "yes")
    negative_prefixes = ("不同意", "不是", "否", "反对", "disagree", "no")
    unsure_prefixes = ("不确定", "跳过", "不知道", "都不是", "unsure", "unknown", "skip")

    if raw.startswith(positive_prefixes) or lowered.startswith(positive_prefixes):
        return Evidence(positive=weight, negative=0.0)
    if raw.startswith(negative_prefixes) or lowered.startswith(negative_prefixes):
        return Evidence(positive=0.0, negative=weight)
    if raw.startswith(unsure_prefixes) or lowered.startswith(unsure_prefixes):
        return Evidence(positive=0.0, negative=0.0)
    return Evidence(positive=0.0, negative=0.0)


def _normalize_options(options_raw: Any) -> list[dict[str, str]]:
    """
    Returns list of {text, polarity} where polarity in {confirm, disconfirm, uncertain}.
    """
    allowed = {"confirm", "disconfirm", "uncertain"}

    def clean_text(x: Any) -> str:
        return str(x or "").strip()

    if isinstance(options_raw, list) and options_raw and all(isinstance(o, dict) for o in options_raw):
        out: list[dict[str, str]] = []
        for o in options_raw:
            text = clean_text(o.get("text"))
            pol = clean_text(o.get("polarity")).lower()
            if not text:
                continue
            if pol not in allowed:
                pol = "uncertain"
            out.append({"text": text, "polarity": pol})
        return out

    # Legacy: list[str]
    if isinstance(options_raw, list):
        texts = [clean_text(o) for o in options_raw if clean_text(o)]
        out: list[dict[str, str]] = []
        for t in texts:
            pol = "uncertain"
            if t.startswith(("同意", "是")):
                pol = "confirm"
            elif t.startswith(("不同意", "不是", "否")):
                pol = "disconfirm"
            elif t.startswith(("不确定", "跳过")):
                pol = "uncertain"
            out.append({"text": t, "polarity": pol})

        # If we failed to infer, provide a sane default mapping for the common 2/3-option cases.
        if out and all(o["polarity"] == "uncertain" for o in out):
            if len(out) == 2:
                out[0]["polarity"] = "confirm"
                out[1]["polarity"] = "disconfirm"
            elif len(out) >= 3:
                out[0]["polarity"] = "confirm"
                out[1]["polarity"] = "disconfirm"
                out[2]["polarity"] = "uncertain"
        return out

    # Legacy: dict options -> treat keys as options
    if isinstance(options_raw, dict):
        keys = [clean_text(k) for k in options_raw if clean_text(k)]
        return _normalize_options(keys)

    return []


def _resolve_choice_polarity(elicitation_options: Any, choice: str) -> str | None:
    normalized_choice = (choice or "").strip()
    if not normalized_choice:
        return None

    options = _normalize_options(elicitation_options)
    if not options:
        return None

    # 1) Exact match
    for o in options:
        if o["text"] == normalized_choice:
            return o["polarity"]

    # 2) Prefix match (supports long sentences starting with a short canonical prefix)
    for o in options:
        t = o["text"]
        if normalized_choice.startswith(t) or t.startswith(normalized_choice):
            return o["polarity"]

    return None


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

    polarity = _resolve_choice_polarity(elicitation.options, choice)
    if polarity is not None:
        ev = _polarity_to_evidence(polarity, weight=evidence_weight)
    else:
        ev = _choice_to_evidence_fallback(choice, weight=evidence_weight)
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
