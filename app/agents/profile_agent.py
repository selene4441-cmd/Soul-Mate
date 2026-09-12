from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from array import array
from statistics import mean, median
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.costlog import CostEvent, append_cost_event, now_iso_utc
from app.core.openai_compat import OpenAICompatClient
from app.models import BehaviorEvent, Profile, User


class LLMClient(Protocol):
    def summarize_hidden_traits(self, *, text: str) -> tuple[str, dict]:
        ...

    def embed(self, *, text: str) -> tuple[list[float], dict]:
        ...


@dataclass(frozen=True)
class OpenAICompatProfileClient:
    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str

    def summarize_hidden_traits(self, *, text: str) -> tuple[str, dict]:
        client = OpenAICompatClient(base_url=self.base_url, api_key=self.api_key)
        system = (
            "你是中文人格画像写作助手。"
            "只输出一段描述性段落，不要标题、不要列表、不要标签、不要引用。"
            "不包含姓名/联系方式/地址等个人信息。长度不超过200个中文字符。"
        )
        user = (
            "根据用户的行为事件统计与样本，归纳其“隐性特质”画像。"
            "要求：具体、自然、可观察的偏好与互动风格，避免空泛。"
            "\n\n"
            f"{text}"
        )
        result = client.chat_completions(
            model=self.chat_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.6,
            max_tokens=240,
        )
        usage = {
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
        }
        return result.content.strip(), usage

    def embed(self, *, text: str) -> tuple[list[float], dict]:
        client = OpenAICompatClient(base_url=self.base_url, api_key=self.api_key)
        result = client.embeddings(model=self.embedding_model, text=text)
        usage = {"total_tokens": result.usage.total_tokens}
        return result.vector, usage


def build_profile_client_from_env() -> OpenAICompatProfileClient:
    base_url = os.getenv("OPENAI_BASE_URL") or settings.openai_base_url
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    chat_model = os.getenv("OPENAI_MODEL") or settings.openai_model or "gpt-5.2"
    embedding_model = (
        os.getenv("OPENAI_EMBEDDING_MODEL")
        or settings.openai_embedding_model
        or "text-embedding-3-small"
    )
    if not base_url or not api_key:
        raise RuntimeError("OPENAI_BASE_URL and OPENAI_API_KEY must be set to call LLM/embeddings.")
    return OpenAICompatProfileClient(
        base_url=base_url,
        api_key=api_key,
        chat_model=chat_model,
        embedding_model=embedding_model,
    )


def _events_digest(events: list[BehaviorEvent]) -> str:
    payload = [
        {
            "id": e.id,
            "t": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
            "target": e.target_id,
            "dur": e.duration_ms,
            "at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _render_behavior_snapshot(events: list[BehaviorEvent]) -> str:
    if not events:
        return "行为事件：无。"

    total = len(events)
    by_type: dict[str, int] = {}
    dwell_ms: list[int] = []
    targets: dict[str, int] = {}
    for e in events:
        t = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
        by_type[t] = by_type.get(t, 0) + 1
        if e.duration_ms is not None and t == "dwell":
            dwell_ms.append(int(e.duration_ms))
        if e.target_id:
            targets[e.target_id] = targets.get(e.target_id, 0) + 1

    top_targets = sorted(targets.items(), key=lambda x: (-x[1], x[0]))[:5]
    top_targets_str = ", ".join([f"{k}×{v}" for k, v in top_targets]) if top_targets else "无"

    dwell_stats = "无"
    if dwell_ms:
        sorted_ms = sorted(dwell_ms)

        def pctl(p: float) -> int:
            if len(sorted_ms) == 1:
                return int(sorted_ms[0])
            pos = (len(sorted_ms) - 1) * p
            lo = int(pos)
            hi = min(lo + 1, len(sorted_ms) - 1)
            frac = pos - lo
            return int(round(sorted_ms[lo] * (1 - frac) + sorted_ms[hi] * frac))

        dwell_stats = f"均值{int(mean(sorted_ms))}ms，中位{int(median(sorted_ms))}ms，P90 {pctl(0.9)}ms"

    oldest = min(events, key=lambda e: (e.created_at, e.id)).created_at
    newest = max(events, key=lambda e: (e.created_at, e.id)).created_at

    return (
        "行为事件摘要："
        f"总数{total}；类型分布{by_type}；"
        f"dwell停留({dwell_stats})；"
        f"常见target {top_targets_str}；"
        f"时间跨度{oldest.isoformat()} ~ {newest.isoformat()}。"
    )


def update_user_profile_from_events(
    *,
    user_id: int,
    session: Session,
    client: LLMClient | None = None,
    force: bool = False,
    max_events: int = 2000,
) -> bool:
    """
    Returns True if profile was updated, False if skipped (cache hit).
    """
    user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"user_id={user_id} not found")
    if not user.consent:
        raise PermissionError("user has not consented")

    events = (
        session.execute(
            sa.select(BehaviorEvent)
            .where(BehaviorEvent.user_id == user_id)
            .order_by(BehaviorEvent.created_at.asc(), BehaviorEvent.id.asc())
            .limit(max_events)
        )
        .scalars()
        .all()
    )
    digest = _events_digest(events)

    profile = session.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, summary="", embedding=None, source_hash="")
        session.add(profile)
        session.commit()

    if not force and profile.source_hash == digest:
        return False

    if client is None:
        client = build_profile_client_from_env()

    snapshot = _render_behavior_snapshot(events)
    summary, usage_chat = client.summarize_hidden_traits(text=snapshot)
    summary = " ".join(summary.split())
    if len(summary) > 200:
        summary = summary[:200]

    append_cost_event(
        CostEvent(
            ts=now_iso_utc(),
            endpoint="chat.completions",
            model=getattr(client, "chat_model", "unknown"),
            input_chars=len(snapshot),
            output_chars=len(summary),
            usage=usage_chat,
            meta={"user_id": user_id, "events": len(events)},
        )
    )

    vector, usage_emb = client.embed(text=summary)
    append_cost_event(
        CostEvent(
            ts=now_iso_utc(),
            endpoint="embeddings",
            model=getattr(client, "embedding_model", "unknown"),
            input_chars=len(summary),
            output_chars=None,
            usage=usage_emb,
            meta={"user_id": user_id, "dims": len(vector)},
        )
    )

    profile.summary = summary
    profile.embedding = array("f", vector).tobytes()
    profile.source_hash = digest
    session.commit()
    return True
