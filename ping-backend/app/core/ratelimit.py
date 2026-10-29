"""A small in-memory sliding-window rate limiter for the public widget API.

Per process only: behind several workers each enforces its own window, so
the effective limit is multiplied. Good enough to stop a runaway script;
move to Redis when Ping runs more than one process.
"""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimitedError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimitedError("Too many messages. Please wait a moment and try again.")
            hits.append(now)
            if len(self._hits) > 50_000:  # drop idle keys
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]


limiter = RateLimiter()
