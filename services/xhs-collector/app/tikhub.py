from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings
from .normalize import ParsedIdentifier

SUCCESS_CODES = {0, 200}

FIELD_ALIASES: dict[str, list[str]] = {
    "user_id": ["user_id", "userid", "uid"],
    "red_id": ["red_id", "redid", "xhs_id", "xhsid"],
    "nickname": ["nickname", "nick_name", "name"],
    "avatar": ["avatar", "avatar_url", "image_url", "images"],
    "description": ["desc", "description", "bio", "introduction", "signature"],
    "gender": ["gender", "sex"],
    "ip_location": ["ip_location", "ip_location_name", "location", "region", "area"],
    "followers_count": ["fans", "fans_count", "follower_count", "followers"],
    "following_count": ["follows", "following_count", "following", "follow_count"],
    "notes_count": ["notes", "note_count", "notes_count", "posted_notes_count"],
    "interaction_count": ["interaction_count", "interactions", "liked_count", "total_interaction"],
}


class TikhubError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _coerce(value: Any) -> Any:
    if isinstance(value, list):
        return _coerce(value[0]) if value else None
    if isinstance(value, dict):
        for key in ("url", "original", "default", "image_url", "avatar_url"):
            if value.get(key):
                return _coerce(value[key])
        return None
    return value


def _deep_first(payload: Any, key: str) -> Any:
    for node in _walk(payload):
        if key in node and node[key] not in (None, "", []):
            return node[key]
    return None


def _extract_interaction_count(payload: Any) -> Any:
    interactions = _deep_first(payload, "interactions")
    if isinstance(interactions, list):
        for item in interactions:
            if isinstance(item, dict) and item.get("type") == "interaction":
                return item.get("count")
    return _deep_first(payload, "liked")


def _extract_notes_count(payload: Any) -> Any:
    stat = _deep_first(payload, "note_num_stat")
    if isinstance(stat, dict) and stat.get("posted") is not None:
        return stat.get("posted")
    return _deep_first(payload, "posted")


def extract_user_fields(payload: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    nodes = list(_walk(payload))

    for field, aliases in FIELD_ALIASES.items():
        for node in nodes:
            for alias in aliases:
                if alias in node:
                    value = _coerce(node[alias])
                    if value not in (None, "", [], {}):
                        fields[field] = value
                        break
            if field in fields:
                break

    if "notes_count" not in fields:
        fields["notes_count"] = _extract_notes_count(payload)
    if "interaction_count" not in fields:
        fields["interaction_count"] = _extract_interaction_count(payload)

    for field in ("followers_count", "following_count", "notes_count", "interaction_count"):
        if field in fields and fields[field] is not None:
            try:
                fields[field] = int(fields[field])
            except (TypeError, ValueError):
                fields[field] = None

    return fields


def _find_error(payload: Any) -> tuple[bool, str | None]:
    for node in _walk(payload):
        code = node.get("code") if isinstance(node, dict) else None
        if isinstance(code, int) and code not in SUCCESS_CODES:
            message = node.get("message") or node.get("msg") or f"code={code}"
            return True, str(message)
    return False, None


class TikhubClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        headers = (
            {"Authorization": f"Bearer {settings.tikhub_api_key}"}
            if settings.tikhub_api_key
            else {}
        )
        self._client = httpx.Client(
            base_url=settings.tikhub_base_url,
            headers=headers,
            timeout=30.0,
        )

    def fetch_user(self, identifier: ParsedIdentifier) -> dict[str, Any]:
        params: dict[str, str] = {}
        if identifier.user_id:
            params["user_id"] = identifier.user_id
        elif identifier.share_text:
            params["share_text"] = identifier.share_text
        else:
            raise TikhubError("没有可用的 user_id 或 share_text")

        try:
            response = self._client.get(
                "/api/v1/xiaohongshu/app_v2/get_user_info",
                params=params,
            )
        except httpx.HTTPError as exc:
            raise TikhubError(f"请求失败: {exc}") from exc

        if response.status_code == 401:
            raise TikhubError("Tikhub API Key 无效或未配置", status_code=401)
        if response.status_code == 402:
            raise TikhubError("Tikhub 余额不足，请先充值", status_code=402)
        if response.status_code >= 400:
            raise TikhubError(
                f"Tikhub 返回 HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise TikhubError("Tikhub 返回了非 JSON 响应") from exc

        is_error, message = _find_error(payload)
        if is_error:
            raise TikhubError(f"Tikhub 返回错误: {message}")

        fields = extract_user_fields(payload)
        if not fields.get("user_id") and not fields.get("nickname") and not fields.get("red_id"):
            raise TikhubError("未能从响应中解析出用户信息（标识符可能无效或账号不存在）")
        fields["raw_json"] = json.dumps(payload, ensure_ascii=False)
        return fields

    def close(self) -> None:
        self._client.close()