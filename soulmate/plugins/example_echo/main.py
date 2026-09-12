from __future__ import annotations

from typing import Any


def echo(**kwargs: Any) -> dict[str, Any]:
    return {"echo": kwargs}


def add(*, a: float, b: float) -> dict[str, float]:
    return {"sum": float(a) + float(b)}

