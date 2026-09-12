from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class RateLimit:
    limit: int
    window_s: int


class RateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[str, list[float]] = {}

    def allow(self, *, key: str, rule: RateLimit) -> bool:
        now = time.monotonic()
        window_start = now - rule.window_s
        with self._lock:
            timestamps = self._buckets.get(key, [])
            timestamps = [t for t in timestamps if t >= window_start]
            if len(timestamps) >= rule.limit:
                self._buckets[key] = timestamps
                return False
            timestamps.append(now)
            self._buckets[key] = timestamps
            return True

