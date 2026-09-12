"""Agent API：把画像 / 匹配 / 诱导卡片 / 信念更新暴露为 HTTP 接口。

设计说明
--------
* 与 ``events`` 路由共用会话依赖、限流依赖（``app.api.events`` 是当前唯一来源）。
* **昂贵接口严格限流**：画像刷新、匹配、卡片生成都会真实调用 LLM 并产生费用，
  因此使用独立的 6 次/分钟额度；纯本地计算与读接口额度宽松。
* **后验无状态**：每次请求都从 ``responses`` 历史重建 Beta 后验
  （见 ``app.agents.belief_store``），因此无需在进程内保存会话状态，重启不丢证据。
* **熵语义分离**：返回里 ``belief_entropy`` 是"信念的伯努利熵"（我们关心的不确定性），
  ``match_uncertainty`` 是重排模型给出的匹配不确定性，两者不再混用同一个名字。
* 测试可用 ``app.state.agent_profile_client`` / ``agent_match_client`` / ``agent_elicit_client``
  注入假客户端，避免测试触发真实 LLM 调用（与 ``app.state.rate_limiter`` 同一惯例）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.belief_store import (
    DEFAULT_HYPOTHESIS,
    PRIOR,
    load_posterior,
    sync_belief_row,
)
from app.agents.elicit_agent import apply_guess_response, generate_guess_cards
from app.agents.evidence import option_polarities
from app.agents.match_agent import match_user
from app.agents.orchestrator import explain_match
from app.agents.profile_agent import update_user_profile_from_events
from app.agents.story_agent import READY_MESSAGE, generate_story
from app.api.events import SessionDep, enforce_rate_limit
from app.core.belief import confidence_interval, entropy
from app.core.ratelimit import RateLimit
from app.models import Elicitation, Profile, User

router = APIRouter(prefix="/users", tags=["agent"])

#: 会真实调用 LLM 的接口：额度收紧，防止刷爆账单。
LLM_LIMIT = RateLimit(limit=6, window_s=60)
#: 纯本地计算 / 落库的接口。
WRITE_LIMIT = RateLimit(limit=30, window_s=60)
#: 只读接口。
READ_LIMIT = RateLimit(limit=120, window_s=60)


# --------------------------------------------------------------------------- #
# 依赖与守卫
# --------------------------------------------------------------------------- #
def _client_override(request: Request, name: str) -> Any | None:
    """读取测试/宿主注入的专用客户端；未注入时返回 None，让 agent 走真实实现。"""
    return getattr(request.app.state, name, None)


def _require_consented_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
    if not user.consent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_consent")
    return user


def _require_profile(session: Session, user_id: int) -> Profile:
    profile = session.get(Profile, user_id)
    if profile is None or not profile.summary:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="profile_missing")
    return profile


# --------------------------------------------------------------------------- #
# 响应模型
# --------------------------------------------------------------------------- #
class ProfileOut(BaseModel):
    user_id: int
    summary: str
    embedding_dims: int
    source_hash: str
    updated_at: datetime


class ProfileRefreshOut(BaseModel):
    user_id: int
    updated: bool = Field(..., description="False 表示事件序列未变化、命中了缓存")
    summary: str
    summary_chars: int
    embedding_dims: int


class MatchNarrativeOut(BaseModel):
    shared: list[str]
    differences: list[str]
    rare_common: list[str]
    worldviews: list[str]
    why_this_person: str


class MatchOut(BaseModel):
    user_id: int
    matched_user_id: int
    score: float = Field(exclude=True)
    match_uncertainty: float | None = Field(
        exclude=True,
        default=None, description="重排模型给出的匹配不确定性（与信念熵不是同一个量）"
    )
    belief_entropy: float = Field(..., description="当前用户信念的伯努利熵，越小越确定")
    narrative: MatchNarrativeOut
    reasons: list[str]
    explanation: str


class OptionOut(BaseModel):
    text: str
    polarity: str = Field(..., description="confirm / disconfirm / uncertain")


class CardOut(BaseModel):
    elicitation_id: int
    question: str
    kind: str
    options: list[OptionOut]
    expected_information_gain: float
    evidence_weight: float


class ElicitOut(BaseModel):
    user_id: int
    belief_entropy_before: float
    cards: list[CardOut]


class StoryOut(BaseModel):
    user_id: int
    message: str
    story: str


class RespondIn(BaseModel):
    elicitation_id: int = Field(..., ge=1)
    choice: str = Field(..., min_length=1, max_length=500)
    reaction_time_ms: int = Field(..., ge=0, le=600_000)


class RespondOut(BaseModel):
    user_id: int
    hypothesis: str
    choice: str
    alpha: float
    beta: float
    belief_mean: float
    entropy_before: float
    entropy_after: float
    entropy_delta: float = Field(..., description="负值表示不确定性下降")


class BeliefOut(BaseModel):
    user_id: int
    hypothesis: str
    alpha: float
    beta: float
    mean: float
    strength: float
    entropy: float
    ci_low: float
    ci_high: float
    responses_counted: int


# --------------------------------------------------------------------------- #
# 接口
# --------------------------------------------------------------------------- #
@router.get(
    "/{user_id}/profile",
    response_model=ProfileOut,
    dependencies=[Depends(enforce_rate_limit(READ_LIMIT))],
)
def get_profile(session: SessionDep, user_id: int = Path(..., ge=1)) -> ProfileOut:
    _require_consented_user(session, user_id)
    profile = session.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile_not_found")
    return ProfileOut(
        user_id=user_id,
        summary=profile.summary,
        embedding_dims=len(profile.embedding or b"") // 4,
        source_hash=profile.source_hash or "",
        updated_at=profile.updated_at,
    )


@router.post(
    "/{user_id}/profile/refresh",
    response_model=ProfileRefreshOut,
    dependencies=[Depends(enforce_rate_limit(LLM_LIMIT))],
)
def refresh_profile(
    request: Request,
    session: SessionDep,
    user_id: int = Path(..., ge=1),
    force: bool = Query(default=False, description="True 时忽略事件哈希缓存强制重算（会真实扣费）"),
) -> ProfileRefreshOut:
    """按行为事件重算画像（真实 LLM + embeddings，费用会计入 costlog）。

    默认遵循 agent 的缓存语义：事件序列未变化时直接返回 ``updated=False``，不产生调用费用。
    """
    _require_consented_user(session, user_id)
    try:
        updated = update_user_profile_from_events(
            user_id=user_id,
            session=session,
            client=_client_override(request, "agent_profile_client"),
            force=force,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"profile_refresh_failed: {exc.__class__.__name__}",
        ) from exc

    profile = session.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="profile_missing")
    return ProfileRefreshOut(
        user_id=user_id,
        updated=bool(updated),
        summary=profile.summary,
        summary_chars=len(profile.summary or ""),
        embedding_dims=len(profile.embedding or b"") // 4,
    )


@router.post(
    "/{user_id}/match",
    response_model=MatchOut,
    dependencies=[Depends(enforce_rate_limit(LLM_LIMIT))],
)
def post_match(request: Request, session: SessionDep, user_id: int = Path(..., ge=1)) -> MatchOut:
    """向量召回 + LLM 重排，返回最佳匹配、理由与解释。"""
    _require_consented_user(session, user_id)
    _require_profile(session, user_id)

    try:
        result = match_user(
            user_id=user_id,
            session=session,
            client=_client_override(request, "agent_match_client"),
        )
        explanation = explain_match(session=session, user_id=user_id, match=result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"match_failed: {exc.__class__.__name__}",
        ) from exc

    posterior = load_posterior(session, user_id=user_id)
    reasons = [str(r) for r in (result.get("reasons") or [])]
    raw_narrative = result.get("narrative")
    if not isinstance(raw_narrative, dict):
        raw_narrative = {}
    if not raw_narrative:
        # Best-effort fallback: keep API contract stable even if rerank output is invalid.
        raw_narrative = {
            "shared": reasons or ["（暂无可用共同点）"],
            "differences": ["（暂无可用差异）"],
            "rare_common": ["（暂无可用罕见共同点）"],
            "worldviews": ["（暂无可用世界观差异）"],
            "why_this_person": (reasons[0] if reasons else "暂无法生成“为什么是TA”叙事"),
        }

    return MatchOut(
        user_id=user_id,
        matched_user_id=int(result["user_id"]),
        score=float(result["score"]),
        match_uncertainty=(float(result["entropy"]) if result.get("entropy") is not None else None),
        belief_entropy=entropy(posterior.mean),
        narrative=MatchNarrativeOut(**raw_narrative),
        reasons=reasons,
        explanation=explanation,
    )


@router.post(
    "/{user_id}/story",
    response_model=StoryOut,
    dependencies=[Depends(enforce_rate_limit(READ_LIMIT))],
)
def post_story(session: SessionDep, user_id: int = Path(..., ge=1)) -> StoryOut:
    """当信念强度足够（α+β≥8）时返回一段“How I See You”口吻的第一人称叙事。"""
    _require_consented_user(session, user_id)
    _require_profile(session, user_id)

    try:
        result = generate_story(session=session, user_id=user_id, min_strength=8.0)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return StoryOut(user_id=user_id, message=READY_MESSAGE, story=result.story)


@router.post(
    "/{user_id}/elicit",
    response_model=ElicitOut,
    dependencies=[Depends(enforce_rate_limit(LLM_LIMIT))],
)
def post_elicit(request: Request, session: SessionDep, user_id: int = Path(..., ge=1)) -> ElicitOut:
    """生成"猜测卡"（措辞可错、以用户选择换取信息），并附带每个选项的极性。"""
    _require_consented_user(session, user_id)
    _require_profile(session, user_id)

    posterior = load_posterior(session, user_id=user_id)
    try:
        cards = generate_guess_cards(
            user_id=user_id,
            posterior=posterior,
            session=session,
            client=_client_override(request, "agent_elicit_client"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"elicit_failed: {exc.__class__.__name__}",
        ) from exc

    out: list[CardOut] = []
    for card in cards:
        elicitation = session.get(Elicitation, card.elicitation_id)
        polarities = option_polarities(elicitation.options) if elicitation is not None else {}
        out.append(
            CardOut(
                elicitation_id=card.elicitation_id,
                question=card.question,
                kind=str(getattr(card.kind, "value", card.kind)),
                options=[
                    OptionOut(text=text, polarity=polarities.get(text, "uncertain"))
                    for text in card.options
                ],
                expected_information_gain=float(card.expected_information_gain),
                evidence_weight=float(card.evidence_weight),
            )
        )
    return ElicitOut(
        user_id=user_id,
        belief_entropy_before=entropy(posterior.mean),
        cards=out,
    )


@router.post(
    "/{user_id}/respond",
    response_model=RespondOut,
    dependencies=[Depends(enforce_rate_limit(WRITE_LIMIT))],
)
def post_respond(
    payload: RespondIn, session: SessionDep, user_id: int = Path(..., ge=1)
) -> RespondOut:
    """提交一次作答：写入 response、更新信念，并返回熵的变化。

    证据权重固定按 1.0 处理，与 ``belief_store.load_posterior`` 的回放口径保持一致，
    使"写入的后验"和"回放出的后验"始终相等。
    """
    _require_consented_user(session, user_id)
    _require_profile(session, user_id)
    if session.get(Elicitation, payload.elicitation_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="elicitation_not_found")

    before = load_posterior(session, user_id=user_id)
    try:
        apply_guess_response(
            user_id=user_id,
            elicitation_id=payload.elicitation_id,
            posterior=before,
            choice=payload.choice,
            reaction_time_ms=payload.reaction_time_ms,
            session=session,
            hypothesis=DEFAULT_HYPOTHESIS,
            evidence_weight=1.0,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_consent") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    after = load_posterior(session, user_id=user_id)
    sync_belief_row(
        session, user_id=user_id, hypothesis=DEFAULT_HYPOTHESIS, posterior=after
    )

    entropy_before = entropy(before.mean)
    entropy_after = entropy(after.mean)
    return RespondOut(
        user_id=user_id,
        hypothesis=DEFAULT_HYPOTHESIS,
        choice=payload.choice,
        alpha=after.alpha,
        beta=after.beta,
        belief_mean=after.mean,
        entropy_before=entropy_before,
        entropy_after=entropy_after,
        entropy_delta=entropy_after - entropy_before,
    )


@router.get(
    "/{user_id}/belief",
    response_model=BeliefOut,
    dependencies=[Depends(enforce_rate_limit(READ_LIMIT))],
)
def get_belief(session: SessionDep, user_id: int = Path(..., ge=1)) -> BeliefOut:
    """当前信念状态：完整 α/β（由历史回放得来）、均值、熵与 95% 可信区间。"""
    _require_consented_user(session, user_id)
    posterior = load_posterior(session, user_id=user_id)
    ci_low, ci_high = confidence_interval(posterior)
    return BeliefOut(
        user_id=user_id,
        hypothesis=DEFAULT_HYPOTHESIS,
        alpha=posterior.alpha,
        beta=posterior.beta,
        mean=posterior.mean,
        strength=posterior.strength,
        entropy=entropy(posterior.mean),
        ci_low=ci_low,
        ci_high=ci_high,
        responses_counted=int(posterior.strength - PRIOR.strength),
    )
