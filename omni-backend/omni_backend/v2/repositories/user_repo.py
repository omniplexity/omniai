"""User repository."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..db.types import GUID


@runtime_checkable
class UserRepository(Protocol):
    async def get_by_id(self, id: str) -> User | None: ...
    async def get_by_username(self, username: str) -> User | None: ...
    async def create(self, username: str, display_name: str, password_hash: str | None = None) -> User: ...
    async def update(self, id: str, **kwargs: Any) -> User | None: ...
    async def delete(self, id: str) -> bool: ...
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[User]: ...


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: str) -> User | None:
        return await self._session.get(User, id)

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def create(self, username: str, display_name: str, password_hash: str | None = None) -> User:
        user = User(
            id=GUID.new(),
            username=username,
            display_name=display_name,
            password_hash=password_hash,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def update(self, id: str, **kwargs: Any) -> User | None:
        user = await self.get_by_id(id)
        if not user:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self._session.flush()
        return user

    async def delete(self, id: str) -> bool:
        user = await self.get_by_id(id)
        if not user:
            return False
        await self._session.delete(user)
        await self._session.flush()
        return True

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        result = await self._session.execute(
            select(User).where(User.deleted_at.is_(None)).offset(offset).limit(limit)
        )
        return list(result.scalars().all())
