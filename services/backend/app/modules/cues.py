from __future__ import annotations

from typing import Any

from app.schemas import CandidateLead, CueOption


def context_from_lead(lead: CandidateLead) -> dict[str, Any]:
    return {
        "headline": lead.headline,
        "common_signals": lead.common_signals,
        "differences": lead.differences,
        "unknowns": lead.unknowns,
        "how_to_continue": lead.how_to_continue,
        "evidence_ids": lead.evidence_ids,
    }


def suggest_cues(lead: CandidateLead) -> list[CueOption]:
    options: list[CueOption] = []
    for index, text in enumerate(lead.unknowns[:2]):
        options.append(CueOption(id=f"unknown-{index + 1}", cue_type="unknown", text=text))
    for index, text in enumerate(lead.differences[:1]):
        options.append(CueOption(id=f"difference-{index + 1}", cue_type="difference", text=text))
    for index, text in enumerate(lead.how_to_continue[:2]):
        options.append(CueOption(id=f"topic-{index + 1}", cue_type="boundary", text=text))
    for index, text in enumerate(lead.common_signals[:1]):
        options.append(CueOption(id=f"common-{index + 1}", cue_type="common", text=text))

    unique: list[CueOption] = []
    seen: set[str] = set()
    for option in options:
        if option.text in seen:
            continue
        seen.add(option.text)
        unique.append(option)
    return unique[:3]


def default_topic(lead: CandidateLead) -> tuple[str, str]:
    cues = suggest_cues(lead)
    if cues:
        return cues[0].cue_type, cues[0].text
    return "unknown", "想从真实相处中的一个小场景开始了解。"
