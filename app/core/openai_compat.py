from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ChatUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ChatResult:
    content: str
    usage: ChatUsage


@dataclass(frozen=True)
class EmbeddingUsage:
    total_tokens: int | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    usage: EmbeddingUsage


class OpenAICompatClient:
    def __init__(self, *, base_url: str, api_key: str, timeout_s: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s

    def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> ChatResult:
        url = f"{self._base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=self._timeout_s) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = (data["choices"][0]["message"]["content"] or "").strip()
        usage_data = data.get("usage") or {}
        usage = ChatUsage(
            prompt_tokens=usage_data.get("prompt_tokens"),
            completion_tokens=usage_data.get("completion_tokens"),
            total_tokens=usage_data.get("total_tokens"),
        )
        return ChatResult(content=content, usage=usage)

    def embeddings(self, *, model: str, text: str) -> EmbeddingResult:
        url = f"{self._base_url}/v1/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload: dict[str, Any] = {"model": model, "input": text}
        with httpx.Client(timeout=self._timeout_s) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        vector = list(data["data"][0]["embedding"])
        usage_data = data.get("usage") or {}
        usage = EmbeddingUsage(total_tokens=usage_data.get("total_tokens"))
        return EmbeddingResult(vector=vector, usage=usage)

