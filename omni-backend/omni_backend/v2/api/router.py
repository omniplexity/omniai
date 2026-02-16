"""V2 API router — aggregates all v2 endpoint modules."""

from __future__ import annotations

from fastapi import APIRouter

from .health import router as health_router
from .runs import router as runs_router
from .sse import router as sse_router

router = APIRouter()
router.include_router(health_router)
router.include_router(runs_router)
router.include_router(sse_router)
