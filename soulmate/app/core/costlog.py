from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CostEvent:
    ts: str
    endpoint: str
    model: str
    input_chars: int
    output_chars: int | None = None
    usage: dict[str, Any] | None = None
    cost_usd: float | None = None
    meta: dict[str, Any] | None = None


def append_cost_event(event: CostEvent, *, path: str = "data/llm_cost.jsonl") -> None:
    line = json.dumps(asdict(event), ensure_ascii=False)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        # Avoid breaking core flows if logging fails.
        pass


def now_iso_utc() -> str:
    return datetime.now(UTC).isoformat()

