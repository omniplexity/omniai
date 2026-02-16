"""Async SQLAlchemy 2.0 engine + session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def make_engine(database_url: str, echo: bool = False):
    """Create an async engine with dialect-specific configuration.

    - PostgreSQL (asyncpg): connection pooling with pre-ping
    - SQLite (aiosqlite): check_same_thread=False, no pool sizing
    """
    connect_args: dict = {}
    kwargs: dict = {
        "echo": echo,
        "pool_pre_ping": True,
    }

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif database_url.startswith("postgresql"):
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    kwargs["connect_args"] = connect_args
    return create_async_engine(database_url, **kwargs)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
