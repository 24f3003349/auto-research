"""In-process event bus.

Subscribers are async functions. Synchronous handlers are also accepted and
wrapped. The bus keeps a bounded history so new connections can replay
recent events (useful for UI).
"""
from __future__ import annotations

import asyncio
import collections
from typing import Awaitable, Callable, Union

Subscriber = Union[Callable[[dict], None], Callable[[dict], Awaitable[None]]]


class EventBus:
    def __init__(self, max_history: int = 200):
        self._subs: list[tuple[int, Subscriber]] = []
        self._next_id = 1
        self._max_history = max_history
        self._history: collections.deque[dict] = collections.deque(maxlen=max_history)

    def subscribe(self, handler: Subscriber) -> int:
        sub_id = self._next_id
        self._next_id += 1
        self._subs.append((sub_id, handler))
        return sub_id

    def unsubscribe(self, sub_id: int) -> None:
        self._subs = [(i, h) for (i, h) in self._subs if i != sub_id]

    async def publish(self, event: dict) -> None:
        self._history.append(event)
        for _, handler in list(self._subs):
            try:
                res = handler(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                # Never let one handler break the chain.
                pass

    def history(self) -> list[dict]:
        return list(self._history)