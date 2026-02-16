"""V2 test fixtures — async SQLite in-memory database."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from omni_backend.v2.db.models import Base
from omni_backend.v2.db.types import GUID


@pytest_asyncio.fixture
async def engine():
    """Create an async in-memory SQLite engine for tests."""
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    """Provide an async session factory."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    """Provide a single async session for test use."""
    async with session_factory() as sess:
        async with sess.begin():
            yield sess
