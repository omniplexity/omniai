"""RunService: create runs and append events with monotonic seq."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db.models import Run, RunEvent
from ..db.types import GUID


class RunService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def create_run(self, thread_id: str, status: str = "active", created_by: str | None = None) -> dict:
        """Create a new run. Returns dict with id, thread_id, status, created_at."""
        run = Run(
            id=GUID.new(),
            thread_id=thread_id,
            status=status,
            created_by=created_by,
        )
        async with self._sf() as session:
            async with session.begin():
                session.add(run)
        return {
            "id": run.id,
            "thread_id": run.thread_id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
        }

    async def get_run(self, run_id: str) -> dict | None:
        async with self._sf() as session:
            result = await session.get(Run, run_id)
            if not result:
                return None
            return {
                "id": result.id,
                "thread_id": result.thread_id,
                "status": result.status,
                "created_at": result.created_at.isoformat(),
            }

    async def append_event(
        self,
        run_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
        actor: str = "system",
        parent_event_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """Append an event to a run with monotonic seq.

        Uses SELECT MAX(seq) + 1 inside a transaction for safety.
        """
        payload = payload or {}
        async with self._sf() as session:
            async with session.begin():
                result = await session.execute(
                    select(func.coalesce(func.max(RunEvent.seq), 0)).where(RunEvent.run_id == run_id)
                )
                next_seq = result.scalar_one() + 1

                event = RunEvent(
                    id=GUID.new(),
                    run_id=run_id,
                    seq=next_seq,
                    kind=kind,
                    payload=payload,
                    actor=actor,
                    parent_event_id=parent_event_id,
                    correlation_id=correlation_id,
                )
                session.add(event)

        cursor = f"{run_id}:{next_seq}"
        return {
            "id": event.id,
            "run_id": event.run_id,
            "seq": event.seq,
            "kind": event.kind,
            "payload": event.payload,
            "actor": event.actor,
            "created_at": event.created_at.isoformat(),
            "cursor": cursor,
        }

    async def get_events(
        self, run_id: str, after_seq: int = 0, limit: int = 500
    ) -> list[dict]:
        """Get events for a run after a given seq, ordered by seq."""
        async with self._sf() as session:
            result = await session.execute(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
                .order_by(RunEvent.seq)
                .limit(limit)
            )
            events = result.scalars().all()
            return [
                {
                    "id": e.id,
                    "run_id": e.run_id,
                    "seq": e.seq,
                    "kind": e.kind,
                    "payload": e.payload,
                    "actor": e.actor,
                    "created_at": e.created_at.isoformat(),
                    "cursor": f"{e.run_id}:{e.seq}",
                }
                for e in events
            ]


def parse_cursor(cursor: str) -> tuple[str, int]:
    """Parse '{run_id}:{seq}' cursor. Returns (run_id, seq)."""
    parts = cursor.rsplit(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid cursor format: {cursor}")
    return parts[0], int(parts[1])
