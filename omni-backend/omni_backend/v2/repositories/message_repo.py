"""Message repository."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Message
from ..db.types import GUID


@runtime_checkable
class MessageRepository(Protocol):
    async def get_by_id(self, id: str) -> Message | None: ...
    async def create(self, thread_id: str, role: str, content: str, **kwargs: Any) -> Message: ...
    async def list_for_thread(self, thread_id: str, limit: int = 100, offset: int = 0) -> list[Message]: ...


class SQLAlchemyMessageRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: str) -> Message | None:
        return await self._session.get(Message, id)

    async def create(self, thread_id: str, role: str, content: str, **kwargs: Any) -> Message:
        message = Message(
            id=GUID.new(),
            thread_id=thread_id,
            role=role,
            content=content,
            run_id=kwargs.get("run_id"),
            attachments=kwargs.get("attachments", []),
            metadata_=kwargs.get("metadata", {}),
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_for_thread(self, thread_id: str, limit: int = 100, offset: int = 0) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
