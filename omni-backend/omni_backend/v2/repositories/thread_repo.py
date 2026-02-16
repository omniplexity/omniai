"""Thread repository."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Thread
from ..db.types import GUID


@runtime_checkable
class ThreadRepository(Protocol):
    async def get_by_id(self, id: str) -> Thread | None: ...
    async def create(self, project_id: str, title: str) -> Thread: ...
    async def update(self, id: str, **kwargs: Any) -> Thread | None: ...
    async def delete(self, id: str) -> bool: ...
    async def list_for_project(self, project_id: str, limit: int = 100, offset: int = 0) -> list[Thread]: ...


class SQLAlchemyThreadRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: str) -> Thread | None:
        return await self._session.get(Thread, id)

    async def create(self, project_id: str, title: str) -> Thread:
        thread = Thread(id=GUID.new(), project_id=project_id, title=title)
        self._session.add(thread)
        await self._session.flush()
        return thread

    async def update(self, id: str, **kwargs: Any) -> Thread | None:
        thread = await self.get_by_id(id)
        if not thread:
            return None
        for key, value in kwargs.items():
            if hasattr(thread, key):
                setattr(thread, key, value)
        await self._session.flush()
        return thread

    async def delete(self, id: str) -> bool:
        thread = await self.get_by_id(id)
        if not thread:
            return False
        await self._session.delete(thread)
        await self._session.flush()
        return True

    async def list_for_project(self, project_id: str, limit: int = 100, offset: int = 0) -> list[Thread]:
        result = await self._session.execute(
            select(Thread)
            .where(Thread.project_id == project_id, Thread.archived_at.is_(None))
            .order_by(Thread.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
