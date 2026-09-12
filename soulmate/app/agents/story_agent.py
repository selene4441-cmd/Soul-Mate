from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents.belief_store import load_posterior
from app.models import Profile

READY_MESSAGE = "我们好像已经有点了解你了"

BANNED_WORDS: tuple[str, ...] = (
    "人格报告",
    "MBTI",
    "标签",
    "画像",
    "评分",
    "百分比",
)


@dataclass(frozen=True)
class StoryResult:
    message: str
    story: str
    strength: float


def _trim(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    return (text or "").strip()[:max_chars]


def _safe_quote(summary: str, *, max_chars: int = 16) -> str:
    raw = (summary or "").strip()
    if not raw:
        return ""
    return _trim(raw.replace("\n", " ").replace("\r", " "), max_chars=max_chars)


def _build_story_text(*, profile_summary: str, max_chars: int = 150) -> str:
    quoted = _safe_quote(profile_summary, max_chars=16)
    hint = f"「{quoted}」" if quoted else "「你的小习惯」"

    story = (
        "How I See You："
        f"我听见你在{hint}里把在意藏得很轻。"
        "你不急着表态，却会用行动把答案写出来；"
        "有人稳稳回应时，你会慢慢放松，把温柔留给值得的人。"
    )
    story = _trim(story, max_chars=max_chars)
    for w in BANNED_WORDS:
        story = story.replace(w, "")
    story = _trim(story, max_chars=max_chars)
    if "我" not in story:
        story = _trim("How I See You：我会更愿意先听你把话说完，再陪你把路走稳。", max_chars=max_chars)
    return story


def generate_story(*, session: Session, user_id: int, min_strength: float = 8.0) -> StoryResult:
    posterior = load_posterior(session, user_id=user_id)
    if posterior.strength < min_strength:
        raise ValueError("not_ready")

    profile = session.get(Profile, user_id)
    if profile is None or not profile.summary:
        raise ValueError("profile_missing")

    story = _build_story_text(profile_summary=profile.summary, max_chars=150)
    return StoryResult(message=READY_MESSAGE, story=story, strength=posterior.strength)

