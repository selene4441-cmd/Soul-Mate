from __future__ import annotations

from app.core.extensions import extensions


def get_prompt(*, key: str, default: str) -> str:
    """
    Returns prompt override from active skills, falling back to `default`.
    """
    return extensions.get_prompt(key) or default

