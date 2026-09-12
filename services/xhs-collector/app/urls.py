from __future__ import annotations

PROFILE_URL_PREFIX = "https://www.xiaohongshu.com/user/profile/"


def profile_url_for(user_id: str | None) -> str | None:
    """Return the canonical Xiaohongshu profile URL for a 24-hex user_id."""
    if not user_id:
        return None
    return f"{PROFILE_URL_PREFIX}{user_id}"
