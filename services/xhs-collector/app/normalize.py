from __future__ import annotations

import re
from dataclasses import dataclass

HEX24_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{24}(?![0-9a-fA-F])")
PROFILE_UID_RE = re.compile(r"/user/profile/([0-9a-fA-F]{24})", re.I)
RED_ID_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff，。！？；：、（）【】《》\"'<>]+", re.I)

LABEL_PREFIXES = ("小红书号", "小红书", "red_id", "redid", "xhs_id", "xhsid", "user_id", "uid")


@dataclass(frozen=True)
class ParsedIdentifier:
    type: str  # user_id | share_text | red_id | unknown
    value: str
    user_id: str | None = None
    share_text: str | None = None


def _strip_trailing_punctuation(text: str) -> str:
    return text.rstrip(",.;:，。；：、)）】」》>\"']")


def _extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in URL_RE.findall(text):
        cleaned = _strip_trailing_punctuation(match)
        if cleaned:
            urls.append(cleaned)
    return urls


def _extract_uid_from_url(url: str) -> str | None:
    match = PROFILE_UID_RE.search(url)
    return match.group(1) if match else None


def _strip_label(text: str) -> str:
    lower = text.lower()
    for label in LABEL_PREFIXES:
        prefix = label.lower()
        if lower.startswith(prefix):
            rest = text[len(label):].lstrip("：: \t")
            return rest.strip()
    return text


def parse_line(line: str) -> list[ParsedIdentifier]:
    cleaned = line.strip()
    if not cleaned:
        return []

    urls = _extract_urls(cleaned)
    if urls:
        results: list[ParsedIdentifier] = []
        for url in urls:
            uid = _extract_uid_from_url(url)
            if uid:
                results.append(
                    ParsedIdentifier(type="user_id", value=uid, user_id=uid, share_text=url)
                )
            else:
                results.append(ParsedIdentifier(type="share_text", value=url, share_text=url))
        return results

    candidate = cleaned.strip("\"'`")
    candidate = _strip_label(candidate).strip()

    if HEX24_RE.fullmatch(candidate):
        return [ParsedIdentifier(type="user_id", value=candidate, user_id=candidate)]

    if RED_ID_RE.fullmatch(candidate):
        return [ParsedIdentifier(type="red_id", value=candidate)]

    return [ParsedIdentifier(type="unknown", value=cleaned[:1024])]