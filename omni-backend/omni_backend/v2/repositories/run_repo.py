"""Run + RunEvent repository."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Run, RunEvent
from ..db.types import GUID


@runtime_checkable
class RunRepository(Protocol):
    async def get_by_id(self, id: str) -> Run | None: ...
    async def create(self, thread_id: str, status: str = "active", created_by: str | None = None) -> Run: ...
    async def update_status(self, id: str, status: str) -> Run | None: ...
    async def list_for_thread(self, thread_id: str, limit: int = 100) -> list[Run]: ...
    async def append_event(self, run_id: str, kind: str, payload: dict, actor: str, **kwargs: Any) -> RunEvent: ...
    async def get_events(self, run_id: str, after_seq: int = 0, limit: int = 500) -> list[RunEvent]: ...


class SQLAlchemyRunRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: str) -> Run | None:
        return await self._session.get(Run, id)

    async def create(self, thread_id: str, status: str = "active", created_by: str | None = None) -> Run:
        run = Run(id=GUID.new(), thread_id=thread_id, status=status, created_by=created_by)
        self._session.add(run)
        await self._session.flush()
        return run

    async def update_status(self, id: str, status: str) -> Run | None:
        run = await self.get_by_id(id)
        if not run:
            return None
        run.status = status
        await self._session.flush()
        return run

    async def list_for_thread(self, thread_id: str, limit: int = 100) -> list[Run]:
        result = await self._session.execute(
            select(Run)
            .where(Run.thread_id == thread_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def append_event(
        self,
        run_id: str,
        kind: str,
        payload: dict,
        actor: str = "system",
        parent_event_id: str | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> RunEvent:
        """Append event with monotonic seq (MAX+1 in transaction)."""
        result = await self._session.execute(
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
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_events(self, run_id: str, after_seq: int = 0, limit: int = 500) -> list[RunEvent]:
        result = await self._session.execute(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
            .order_by(RunEvent.seq)
            .limit(limit)
        )
        return list(result.scalars().all())
