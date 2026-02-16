"""Base repository protocol and helpers."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class BaseRepository(Protocol[T]):
    """Base repository interface."""

    async def get_by_id(self, id: str) -> T | None: ...
    async def create(self, **kwargs: Any) -> T: ...
    async def delete(self, id: str) -> bool: ...
