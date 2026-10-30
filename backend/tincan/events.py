"""In-process pub/sub feeding GET /api/events (Server-Sent Events)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

log = logging.getLogger(__name__)


class Broadcaster:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[tuple[str, dict[str, Any]]]] = set()
        self.history: list[tuple[str, dict[str, Any]]] = []

    def publish(self, event: str, data: dict[str, Any]) -> None:
        self.history.append((event, data))
        del self.history[:-200]
        for q in list(self._subs):
            try:
                q.put_nowait((event, data))
            except asyncio.QueueFull:
                log.warning("dropping SSE event for a slow subscriber")

    async def subscribe(self, keepalive: float = 15.0) -> AsyncIterator[str]:
        q: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=100)
        self._subs.add(q)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event, data = await asyncio.wait_for(q.get(), timeout=keepalive)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        finally:
            self._subs.discard(q)
