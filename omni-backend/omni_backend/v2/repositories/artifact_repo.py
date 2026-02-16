"""Artifact repository."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Artifact
from ..db.types import GUID


@runtime_checkable
class ArtifactRepository(Protocol):
    async def get_by_id(self, id: str) -> Artifact | None: ...
    async def create(self, kind: str, media_type: str, size_bytes: int, content_hash: str, storage_path: str, **kwargs: Any) -> Artifact: ...
    async def list_for_run(self, run_id: str, limit: int = 100) -> list[Artifact]: ...


class SQLAlchemyArtifactRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: str) -> Artifact | None:
        return await self._session.get(Artifact, id)

    async def create(
        self,
        kind: str,
        media_type: str,
        size_bytes: int,
        content_hash: str,
        storage_path: str,
        **kwargs: Any,
    ) -> Artifact:
        artifact = Artifact(
            id=GUID.new(),
            kind=kind,
            media_type=media_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            storage_path=storage_path,
            run_id=kwargs.get("run_id"),
            title=kwargs.get("title"),
            storage_kind=kwargs.get("storage_kind", "disk"),
            metadata_=kwargs.get("metadata", {}),
            created_by=kwargs.get("created_by"),
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def list_for_run(self, run_id: str, limit: int = 100) -> list[Artifact]:
        result = await self._session.execute(
            select(Artifact)
            .where(Artifact.run_id == run_id)
            .order_by(Artifact.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())
