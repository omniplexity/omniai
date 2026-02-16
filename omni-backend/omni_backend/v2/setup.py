"""V2 setup: mount V2 as a separate FastAPI sub-app.

V2 is mounted via app.mount() (not include_router) so it gets its own
middleware stack, avoiding V1's BaseHTTPMiddleware which breaks SSE
StreamingResponse async generators.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .api.router import router as v2_router
from .core.eventbus import MemoryEventBus
from .core.settings import V2Settings
from .db.models import Base
from .db.session import make_engine, make_session_factory

logger = logging.getLogger("omni_backend.v2")


def _create_v2_app(settings: V2Settings) -> FastAPI:
    """Create the V2 FastAPI sub-application with its own middleware."""
    v2_app = FastAPI(title="OmniAI V2", version="0.1.0")

    # CORS — ASGI-native middleware, safe for streaming
    origins = settings.cors_origins
    if origins:
        v2_app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=["Content-Type", "Last-Event-ID"],
        )

    v2_app.include_router(v2_router)
    return v2_app


async def setup_v2(app) -> None:
    """Initialize V2 subsystem and mount as sub-application.

    Creates a separate FastAPI instance for V2 so SSE streaming works
    without interference from V1's BaseHTTPMiddleware.
    """
    settings = V2Settings()

    engine = make_engine(settings.database_url, echo=(settings.env == "dev"))
    session_factory = make_session_factory(engine)
    eventbus = MemoryEventBus(backlog_size=settings.eventbus_backlog)

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

    # Create and configure V2 sub-app
    v2_app = _create_v2_app(settings)
    v2_app.state.v2_settings = settings
    v2_app.state.v2_engine = engine
    v2_app.state.v2_session_factory = session_factory
    v2_app.state.v2_eventbus = eventbus

    # Store ref on parent for teardown
    app.state.v2_engine = engine
    app.state.v2_app = v2_app

    # Mount as sub-app — bypasses V1 middleware entirely
    app.mount("/v2", v2_app)

    logger.info("V2 subsystem initialized (env=%s)", settings.env)


async def teardown_v2(app) -> None:
    """Shutdown V2 subsystem — dispose async engine."""
    engine = getattr(app.state, "v2_engine", None)
    if engine:
        await engine.dispose()
        logger.info("V2 engine disposed")
