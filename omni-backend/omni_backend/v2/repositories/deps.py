"""FastAPI dependency factories for repository injection."""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .user_repo import SQLAlchemyUserRepository
from .project_repo import SQLAlchemyProjectRepository
from .thread_repo import SQLAlchemyThreadRepository
from .message_repo import SQLAlchemyMessageRepository
from .run_repo import SQLAlchemyRunRepository
from .artifact_repo import SQLAlchemyArtifactRepository


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session from the V2 session factory."""
    session_factory = request.app.state.v2_session_factory
    async with session_factory() as session:
        async with session.begin():
            yield session


async def get_user_repo(session: AsyncSession = Depends(get_session)) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)


async def get_project_repo(session: AsyncSession = Depends(get_session)) -> SQLAlchemyProjectRepository:
    return SQLAlchemyProjectRepository(session)


async def get_thread_repo(session: AsyncSession = Depends(get_session)) -> SQLAlchemyThreadRepository:
    return SQLAlchemyThreadRepository(session)


async def get_message_repo(session: AsyncSession = Depends(get_session)) -> SQLAlchemyMessageRepository:
    return SQLAlchemyMessageRepository(session)


async def get_run_repo(session: AsyncSession = Depends(get_session)) -> SQLAlchemyRunRepository:
    return SQLAlchemyRunRepository(session)


async def get_artifact_repo(session: AsyncSession = Depends(get_session)) -> SQLAlchemyArtifactRepository:
    return SQLAlchemyArtifactRepository(session)
