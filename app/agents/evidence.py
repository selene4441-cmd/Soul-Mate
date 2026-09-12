"""证据解析的公开入口：把"用户对某张猜测卡的作答"映射为贝叶斯证据。

本模块是 elicit_agent 内部私有实现（极性元数据优先 + 关键词前缀兜底）的稳定门面，
供 API 层、信念回放等外部调用方复用，避免依赖下划线私有函数。
"""

from __future__ import annotations

from typing import Any

from app.core.belief import Evidence


def resolve_choice_evidence(
    elicitation_options: Any,
    choice: str,
    *,
    weight: float = 1.0,
) -> Evidence:
    """把一次作答解析为证据。

    规则（与卡片生成契约一致）：
    1. 若选项携带极性元数据（``confirm`` / ``disconfirm`` / ``uncertain``），按极性取证据；
    2. 否则回退到关键词前缀匹配（"是…"/"不是…"/"一半…"），兼容旧数据；
    3. 无法判定时返回零证据（保守，避免误更新）。
    """
    # 延迟导入：elicit_agent 依赖 belief，此处避免模块级循环导入。
    from app.agents.elicit_agent import (
        _choice_to_evidence_fallback,
        _polarity_to_evidence,
        _resolve_choice_polarity,
    )

    polarity = _resolve_choice_polarity(elicitation_options, choice)
    if polarity is not None:
        return _polarity_to_evidence(polarity, weight=weight)
    return _choice_to_evidence_fallback(choice, weight=weight)


def option_polarities(elicitation_options: Any) -> dict[str, str]:
    """返回 ``{选项文本: 极性}``，供前端在选项旁标注 confirm/disconfirm/uncertain。"""
    from app.agents.elicit_agent import _normalize_options

    return {o["text"]: o["polarity"] for o in _normalize_options(elicitation_options)}
