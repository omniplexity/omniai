"""RunService: create runs and append events with monotonic seq."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db.models import Run, RunEvent


class RunService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def create_run(self, status: str = "active") -> dict:
        """Create a new run. Returns dict with id, status, created_at_utc."""
        run = Run(id=str(uuid4()), status=status, created_at_utc=datetime.now(UTC))
        async with self._sf() as session:
            async with session.begin():
                session.add(run)
        return {"id": run.id, "status": run.status, "created_at_utc": run.created_at_utc.isoformat()}

    async def get_run(self, run_id: str) -> dict | None:
        async with self._sf() as session:
            result = await session.get(Run, run_id)
            if not result:
                return None
            return {"id": result.id, "status": result.status, "created_at_utc": result.created_at_utc.isoformat()}

    async def append_event(self, run_id: str, type: str, data: dict[str, Any] | None = None) -> dict:
        """Append an event to a run with monotonic seq.

        Uses SELECT MAX(seq) + 1 inside a transaction for safety.
        Returns dict with id, run_id, seq, type, data, created_at_utc, cursor.
        """
        data = data or {}
        async with self._sf() as session:
            async with session.begin():
                # Get next seq atomically within this transaction
                result = await session.execute(
                    select(func.coalesce(func.max(RunEvent.seq), 0)).where(RunEvent.run_id == run_id)
                )
                next_seq = result.scalar_one() + 1

                event = RunEvent(
                    id=str(uuid4()),
                    run_id=run_id,
                    seq=next_seq,
                    type=type,
                    data=data,
                    created_at_utc=datetime.now(UTC),
                )
                session.add(event)

        cursor = f"{run_id}:{next_seq}"
        return {
            "id": event.id,
            "run_id": event.run_id,
            "seq": event.seq,
            "type": event.type,
            "data": event.data,
            "created_at_utc": event.created_at_utc.isoformat(),
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
                    "type": e.type,
                    "data": e.data,
                    "created_at_utc": e.created_at_utc.isoformat(),
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
