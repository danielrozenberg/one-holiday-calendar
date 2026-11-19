"""A least-recently-used cache bounded by the total size of its values."""

import collections
import threading
from collections.abc import Callable, Hashable


class ByteCache:
    """Keeps built byte strings until their total size exceeds a budget."""

    def __init__(self, budget_bytes: int) -> None:
        """Creates an empty cache holding at most `budget_bytes` of values."""
        self._budget = budget_bytes
        self._size = 0
        self._entries: collections.OrderedDict[Hashable, bytes] = (
            collections.OrderedDict()
        )
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        """The total size of the cached values, in bytes."""
        return self._size

    def get(self, key: Hashable, build: Callable[[], bytes]) -> bytes:
        """Returns the value for `key`, building and caching it when missing.

        Evicts the least recently used values until the cache fits its budget.
        A value larger than the whole budget is returned but not kept.
        """
        with self._lock:
            if (value := self._entries.get(key)) is not None:
                self._entries.move_to_end(key)
                return value
        value = build()
        if len(value) > self._budget:
            return value
        with self._lock:
            if key not in self._entries:
                self._entries[key] = value
                self._size += len(value)
            while self._size > self._budget:
                _, evicted = self._entries.popitem(last=False)
                self._size -= len(evicted)
        return value

    def clear(self) -> None:
        """Drops every cached value."""
        with self._lock:
            self._entries.clear()
            self._size = 0
