from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Awaitable, Callable, Generic, Hashable, TypeVar

T = TypeVar("T")


class AsyncTTLCache(Generic[T]):
    """LRU cache with per-entry TTL and single-flight for concurrent misses."""

    __slots__ = ("_ttl", "_max", "_data", "_locks", "_lock")

    def __init__(self, *, ttl: float, max_size: int = 512) -> None:
        self._ttl = ttl
        self._max = max_size
        self._data: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        self._locks: dict[Hashable, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    def peek(self, key: Hashable) -> T | None:
        """Return a fresh cached value or ``None``; bumps LRU order on hit."""
        entry = self._data.get(key)
        if entry is None:
            return None
        expires, value = entry
        if expires < time.monotonic():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: Hashable, value: T) -> None:
        self._data[key] = (time.monotonic() + self._ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    async def get_or_set(self, key: Hashable, producer: Callable[[], Awaitable[T]]) -> T:
        cached = self.peek(key)
        if cached is not None:
            return cached

        async with self._lock:
            lock = self._locks.setdefault(key, asyncio.Lock())

        async with lock:
            cached = self.peek(key)
            if cached is not None:
                return cached
            value = await producer()
            self.set(key, value)
            async with self._lock:
                self._locks.pop(key, None)
            return value

    def invalidate(self, key: Hashable) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()
