from __future__ import annotations

import json
import math
import os
from array import array
from dataclasses import dataclass
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.belief import entropy as bernoulli_entropy
from app.core.config import settings
from app.core.costlog import CostEvent, append_cost_event, now_iso_utc
from app.core.openai_compat import OpenAICompatClient
from app.models import MatchCache, Profile, User


class RerankClient(Protocol):
    chat_model: str

    def rerank(
        self, *, user_summary: str, candidates: list[tuple[int, float, str]]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        ...


@dataclass(frozen=True)
class OpenAICompatRerankClient:
    base_url: str
    api_key: str
    chat_model: str = "gpt-5.2"

    def rerank(
        self, *, user_summary: str, candidates: list[tuple[int, float, str]]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        # 候选过多会让 JSON 超出 token 上限被截断：只把余弦相似度最高的前 20 个交给 LLM 重排
        candidates = list(candidates)[:20]

        client = OpenAICompatClient(base_url=self.base_url, api_key=self.api_key)
        system = (
            "你是中文匹配推荐助手。任务：对候选人进行重排，并给出每位候选人的匹配分与理由。"
            "要求：理由必须引用双方画像中的具体表述（用中文引号「」原样引用）。"
            "输出必须是严格 JSON："
            '{"ranked":[{"user_id":<int>,"score":<0-1 float>,"reasons":[<string>,...]},...]}'
            "不要输出任何额外文本。每个 reasons 建议 2-4 条。ranked 必须只包含输入 candidates 中的 user_id，且保持从高到低排序。"
        )
        cand_lines = []
        for uid, sim, summary in candidates:
            cand_lines.append(
                {
                    "user_id": uid,
                    "retrieval_cosine": round(float(sim), 6),
                    "profile": summary,
                }
            )
        user_msg = json.dumps(
            {"user_profile": user_summary, "candidates": cand_lines},
            ensure_ascii=False,
        )
        result = client.chat_completions(
            model=self.chat_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            temperature=0.2,
            max_tokens=4000,
        )

        usage = {
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
        }
        data = _parse_ranked(result.content)
        ranked = list(data)
        return ranked, usage


def _parse_ranked(text: str) -> list[dict[str, Any]]:
    """容错解析 rerank 输出：去 markdown 围栏；被截断时抢救已完整的对象。"""
    import re

    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    parsed: list[dict[str, Any]] | None = None
    try:
        data = json.loads(raw)
        ranked = data["ranked"]
        if isinstance(ranked, list):
            parsed = list(ranked)
    except (json.JSONDecodeError, KeyError, TypeError):
        parsed = None
    if parsed is not None:
        return parsed
    salvaged: list[dict[str, Any]] = []
    pattern = re.compile(r'\{\s*"user_id"\s*:\s*\d+.*?"reasons"\s*:\s*\[.*?\]\s*\}', re.DOTALL)
    for m in pattern.finditer(raw):
        try:
            salvaged.append(json.loads(m.group(0)))
        except json.JSONDecodeError:
            continue
    if salvaged:
        return salvaged
    raise ValueError(f"rerank 输出无法解析为 JSON（长度 {len(text)}）：{text[:200]}")


def build_rerank_client_from_env() -> OpenAICompatRerankClient:
    base_url = os.getenv("OPENAI_BASE_URL") or settings.openai_base_url
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    chat_model = os.getenv("OPENAI_MODEL") or settings.openai_model or "gpt-5.2"
    if not base_url or not api_key:
        raise RuntimeError("OPENAI_BASE_URL and OPENAI_API_KEY must be set to call reranker.")
    return OpenAICompatRerankClient(base_url=base_url, api_key=api_key, chat_model=chat_model)


def _bytes_to_f32_list(buf: bytes) -> list[float]:
    arr = array("f")
    arr.frombytes(buf)
    return list(arr)


def cosine_similarity(a: bytes, b: bytes) -> float:
    af = _bytes_to_f32_list(a)
    bf = _bytes_to_f32_list(b)
    if not af or not bf or len(af) != len(bf):
        raise ValueError("embedding vectors must have same non-zero length")

    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(af, bf, strict=True):
        dot += float(x) * float(y)
        na += float(x) * float(x)
        nb += float(y) * float(y)
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def recall_top_k(
    *,
    user_id: int,
    session: Session,
    k: int = 50,
) -> list[tuple[int, float, str]]:
    user_profile = session.get(Profile, user_id)
    if user_profile is None or user_profile.embedding is None:
        raise ValueError("user profile embedding is missing")

    rows = (
        session.execute(
            sa.select(Profile.user_id, Profile.embedding, Profile.summary)
            .where(Profile.user_id != user_id)
            .where(Profile.embedding.is_not(None))
        )
        .all()
    )

    scored: list[tuple[int, float, str]] = []
    for uid, emb, summary in rows:
        try:
            sim = cosine_similarity(user_profile.embedding, emb)
        except ValueError:
            continue
        scored.append((int(uid), float(sim), str(summary)))

    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:k]


def match_user(
    *,
    user_id: int,
    session: Session,
    client: RerankClient | None = None,
    recall_k: int = 50,
) -> dict[str, Any]:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("user not found")
    if not user.consent:
        raise PermissionError("user has not consented")

    user_profile = session.get(Profile, user_id)
    if user_profile is None or not user_profile.summary or user_profile.embedding is None:
        raise ValueError("user profile is missing")

    candidates = recall_top_k(user_id=user_id, session=session, k=recall_k)
    if not candidates:
        raise ValueError("no candidates with embeddings")

    if client is None:
        client = build_rerank_client_from_env()

    # Cache check per pair (user_id, candidate_id) to avoid repeated reranks.
    by_id: dict[int, tuple[float, str]] = {cid: (sim, summary) for cid, sim, summary in candidates}
    missing: list[tuple[int, float, str]] = []
    cached_results: list[tuple[int, float, float, list[str]]] = []

    user_hash = user_profile.source_hash or ""
    for cid, sim, summary in candidates:
        other = session.get(Profile, cid)
        other_hash = (other.source_hash if other is not None else "") or ""
        a, b = (user_id, cid) if user_id < cid else (cid, user_id)
        cache = session.get(MatchCache, (a, b))
        expected_a_hash = user_hash if a == user_id else other_hash
        expected_b_hash = other_hash if b == cid else user_hash
        if cache is not None and cache.profile_hash_a == expected_a_hash and cache.profile_hash_b == expected_b_hash:
            cached_results.append((cid, float(cache.score), float(cache.entropy), list(cache.reasons)))
        else:
            missing.append((cid, sim, summary))

    if not missing and cached_results:
        cached_results.sort(key=lambda x: (-x[1], x[0]))
        best_id, score, h, reasons = cached_results[0]
        return {"user_id": best_id, "score": score, "entropy": h, "reasons": reasons}

    ranked, usage = client.rerank(user_summary=user_profile.summary, candidates=candidates)

    append_cost_event(
        CostEvent(
            ts=now_iso_utc(),
            endpoint="chat.completions",
            model=getattr(client, "chat_model", "unknown"),
            input_chars=len(user_profile.summary) + sum(len(c[2]) for c in candidates),
            output_chars=sum(len(item.get("reasons", [])) for item in ranked),
            usage=usage,
            meta={"user_id": user_id, "recall_k": len(candidates)},
        )
    )

    # Write cache for all ranked entries we can validate.
    results: list[tuple[int, float, float, list[str]]] = []
    for item in ranked:
        try:
            cid = int(item["user_id"])
            score = float(item["score"])
            reasons = list(item.get("reasons") or [])
        except (KeyError, TypeError, ValueError):
            continue
        if cid not in by_id:
            continue
        score = max(0.0, min(1.0, score))
        h = bernoulli_entropy(score)

        other_profile = session.get(Profile, cid)
        other_hash = (other_profile.source_hash if other_profile is not None else "") or ""

        a, b = (user_id, cid) if user_id < cid else (cid, user_id)
        entry = MatchCache(
            user_id_a=a,
            user_id_b=b,
            profile_hash_a=user_hash if a == user_id else other_hash,
            profile_hash_b=other_hash if b == cid else user_hash,
            score=score,
            entropy=h,
            reasons=reasons,
        )
        session.merge(entry)
        results.append((cid, score, h, reasons))

    session.commit()

    if not results:
        # Fallback: best by cosine if LLM output invalid.
        cid, sim, _summary = candidates[0]
        score = max(0.0, min(1.0, (sim + 1.0) / 2.0))
        return {"user_id": cid, "score": score, "entropy": bernoulli_entropy(score), "reasons": []}

    results.sort(key=lambda x: (-x[1], x[0]))
    best_id, score, h, reasons = results[0]
    return {"user_id": best_id, "score": score, "entropy": h, "reasons": reasons}
