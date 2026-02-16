"""Async SQLAlchemy 2.0 engine + session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def make_engine(database_url: str, echo: bool = False):
    """Create an async engine. For SQLite, enable WAL and foreign keys."""
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_async_engine(
        database_url,
        echo=echo,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
