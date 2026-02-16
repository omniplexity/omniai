"""V2 setup: attach v2 router and async DB engine to the existing FastAPI app."""

from __future__ import annotations

import logging

from sqlalchemy import text

from .api.router import router as v2_router
from .core.eventbus import MemoryEventBus
from .core.settings import V2Settings
from .db.models import Base
from .db.session import make_engine, make_session_factory

logger = logging.getLogger("omni_backend.v2")


async def setup_v2(app) -> None:
    """Initialize V2 subsystem on the existing FastAPI app.

    Call this during app startup. Attaches:
      - app.state.v2_settings
      - app.state.v2_engine
      - app.state.v2_session_factory
      - app.state.v2_eventbus
    Mounts the /v2 router.
    """
    settings = V2Settings()
    app.state.v2_settings = settings
    app.state.v2_eventbus = MemoryEventBus(backlog_size=settings.eventbus_backlog)

    engine = make_engine(settings.database_url, echo=(settings.env == "dev"))
    app.state.v2_engine = engine
    app.state.v2_session_factory = make_session_factory(engine)

    # In dev mode, auto-create tables (no alembic needed)
    if settings.is_dev:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("V2 tables created (dev mode)")

    # Enable WAL for SQLite
    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))

    # Mount v2 router
    app.include_router(v2_router, prefix="/v2", tags=["v2"])

    logger.info("V2 subsystem initialized (env=%s)", settings.env)


async def teardown_v2(app) -> None:
    """Shutdown V2 subsystem — dispose async engine."""
    engine = getattr(app.state, "v2_engine", None)
    if engine:
        await engine.dispose()
        logger.info("V2 engine disposed")
