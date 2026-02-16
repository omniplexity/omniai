"""EventBus interface + in-memory implementation with bounded backlog."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


@dataclass(frozen=True)
class BusEvent:
    channel: str
    event_id: str  # cursor string e.g. "{run_id}:{seq}"
    data: dict[str, Any]


class EventBus(Protocol):
    """Publish/subscribe interface for real-time event distribution."""

    async def publish(self, channel: str, event: BusEvent) -> None: ...

    def subscribe(self, channel: str, after_id: str | None = None) -> AsyncIterator[BusEvent]: ...


class MemoryEventBus:
    """In-process eventbus with bounded per-channel backlog and asyncio broadcast."""

    def __init__(self, backlog_size: int = 1000):
        self._backlog_size = backlog_size
        self._backlogs: dict[str, deque[BusEvent]] = defaultdict(lambda: deque(maxlen=backlog_size))
        self._subscribers: dict[str, list[asyncio.Queue[BusEvent]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: BusEvent) -> None:
        async with self._lock:
            self._backlogs[channel].append(event)
            for q in self._subscribers[channel]:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass  # slow consumer drops events; they can replay from DB

    async def subscribe(self, channel: str, after_id: str | None = None) -> AsyncIterator[BusEvent]:
        """Yield events from backlog (if after_id given) then live events."""
        q: asyncio.Queue[BusEvent] = asyncio.Queue(maxsize=256)

        async with self._lock:
            # Replay from backlog
            if after_id is not None:
                found = False
                for ev in self._backlogs[channel]:
                    if found:
                        yield ev
                    elif ev.event_id == after_id:
                        found = True
                # If after_id not found in backlog, caller should replay from DB
            self._subscribers[channel].append(q)

        try:
            while True:
                event = await q.get()
                yield event
        finally:
            async with self._lock:
                try:
                    self._subscribers[channel].remove(q)
                except ValueError:
                    pass
