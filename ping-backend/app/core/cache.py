"""A small in-process TTL + LRU cache.

Per process, so each API worker warms its own. Entries are keyed by the bot's
knowledge version as well, so a change to a bot's sources makes its old
entries unreachable straight away; they then age out.
"""

import threading
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, max_entries: int, ttl_seconds: float):
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < time.monotonic():
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: Any, value: Any) -> None:
        if self.max_entries <= 0 or self.ttl <= 0:
            return
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


def normalise(text: str) -> str:
    """Case, spacing and trailing punctuation don't change what was asked."""
    return " ".join(text.lower().split()).rstrip("?!. ")
