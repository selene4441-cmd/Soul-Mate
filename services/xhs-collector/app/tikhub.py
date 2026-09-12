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


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_list(payload: Any, key: str) -> list | None:
    for node in _walk(payload):
        if isinstance(node, dict) and isinstance(node.get(key), list):
            return node[key]
    return None


def _parse_note(node: dict) -> dict[str, Any]:
    note_id = node.get("id") or node.get("note_id")
    images: list[str] = []
    for img in node.get("images_list") or []:
        if isinstance(img, dict):
            url = img.get("url") or img.get("url_size_large") or img.get("medium") or img.get("original")
            if url:
                images.append(url)

    tags = [t.get("name") for t in (node.get("hash_tag") or []) if isinstance(t, dict) and t.get("name")]
    share_info = node.get("share_info") if isinstance(node.get("share_info"), dict) else {}

    return {
        "note_id": note_id,
        "title": node.get("title") or node.get("display_title") or "",
        "desc": node.get("desc") or "",
        "note_type": node.get("type") or "",
        "likes": _as_int(node.get("liked_count", node.get("likes"))),
        "comments_count": _as_int(node.get("comments_count")),
        "collected_count": _as_int(node.get("collected_count")),
        "share_count": _as_int(node.get("share_count")),
        "ip_location": node.get("ip_location") or "",
        "published_at": _as_int(node.get("create_time", node.get("time"))),
        "images": images,
        "tags": tags,
        "note_url": share_info.get("link")
        or (f"https://www.xiaohongshu.com/discovery/item/{note_id}" if note_id else ""),
        "raw_json": json.dumps(node, ensure_ascii=False),
    }


def _find_note_node(payload: Any) -> dict | None:
    notes = _find_list(payload, "note_list")
    if notes:
        for item in notes:
            if isinstance(item, dict) and (item.get("id") or item.get("note_id")):
                return item
    for node in _walk(payload):
        if isinstance(node, dict) and (node.get("id") or node.get("note_id")) and ("title" in node or "desc" in node):
            return node
    return None


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

    def _request_get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            response = self._client.get(path, params=params)
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
        return payload

    def fetch_user(self, identifier: ParsedIdentifier) -> dict[str, Any]:
        params: dict[str, str] = {}
        if identifier.user_id:
            params["user_id"] = identifier.user_id
        elif identifier.share_text:
            params["share_text"] = identifier.share_text
        else:
            raise TikhubError("没有可用的 user_id 或 share_text")

        payload = self._request_get("/api/v1/xiaohongshu/app_v2/get_user_info", params)
        fields = extract_user_fields(payload)
        if not fields.get("user_id") and not fields.get("nickname") and not fields.get("red_id"):
            raise TikhubError("未能从响应中解析出用户信息（标识符可能无效或账号不存在）")
        fields["raw_json"] = json.dumps(payload, ensure_ascii=False)
        return fields

    def fetch_posted_notes(self, user_id: str, max_notes: int = 100) -> dict[str, Any]:
        notes: list[dict[str, Any]] = []
        cursor = ""

        for _ in range(50):
            params: dict[str, Any] = {"user_id": user_id}
            if cursor:
                params["cursor"] = cursor

            payload = self._request_get(
                "/api/v1/xiaohongshu/app_v2/get_user_posted_notes", params
            )
            items = _find_list(payload, "notes") or []
            for item in items:
                if isinstance(item, dict):
                    parsed = _parse_note(item)
                    if parsed.get("note_id"):
                        notes.append(parsed)

            has_more = _deep_first(payload, "has_more")
            next_cursor = items[-1].get("cursor") if items and isinstance(items[-1], dict) else None
            if not has_more or not next_cursor or len(notes) >= max_notes:
                break
            cursor = next_cursor

        return {"notes": notes}

    def fetch_note_detail(self, note_id: str, note_type: str = "") -> dict[str, Any]:
        endpoint = "get_video_note_detail" if note_type == "video" else "get_image_note_detail"
        payload = self._request_get(
            f"/api/v1/xiaohongshu/app_v2/{endpoint}", {"note_id": note_id}
        )
        node = _find_note_node(payload)
        if node is None:
            raise TikhubError("未能从响应中解析出笔记正文")
        return _parse_note(node)

    def close(self) -> None:
        self._client.close()