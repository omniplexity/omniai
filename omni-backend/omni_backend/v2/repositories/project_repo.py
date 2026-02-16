"""Project repository."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Project, ProjectMember
from ..db.types import GUID


@runtime_checkable
class ProjectRepository(Protocol):
    async def get_by_id(self, id: str) -> Project | None: ...
    async def create(self, name: str, created_by: str | None = None) -> Project: ...
    async def update(self, id: str, **kwargs: Any) -> Project | None: ...
    async def delete(self, id: str) -> bool: ...
    async def list_for_user(self, user_id: str, limit: int = 100) -> list[Project]: ...
    async def add_member(self, project_id: str, user_id: str, role: str) -> ProjectMember: ...
    async def remove_member(self, project_id: str, user_id: str) -> bool: ...
    async def get_members(self, project_id: str) -> list[ProjectMember]: ...


class SQLAlchemyProjectRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: str) -> Project | None:
        return await self._session.get(Project, id)

    async def create(self, name: str, created_by: str | None = None) -> Project:
        project = Project(id=GUID.new(), name=name, created_by=created_by)
        self._session.add(project)
        await self._session.flush()
        return project

    async def update(self, id: str, **kwargs: Any) -> Project | None:
        project = await self.get_by_id(id)
        if not project:
            return None
        for key, value in kwargs.items():
            if hasattr(project, key):
                setattr(project, key, value)
        await self._session.flush()
        return project

    async def delete(self, id: str) -> bool:
        project = await self.get_by_id(id)
        if not project:
            return False
        await self._session.delete(project)
        await self._session.flush()
        return True

    async def list_for_user(self, user_id: str, limit: int = 100) -> list[Project]:
        result = await self._session.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user_id, Project.archived_at.is_(None))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_member(self, project_id: str, user_id: str, role: str) -> ProjectMember:
        member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        self._session.add(member)
        await self._session.flush()
        return member

    async def remove_member(self, project_id: str, user_id: str) -> bool:
        result = await self._session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return False
        await self._session.delete(member)
        await self._session.flush()
        return True

    async def get_members(self, project_id: str) -> list[ProjectMember]:
        result = await self._session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        )
        return list(result.scalars().all())
