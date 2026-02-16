"""V2 health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    db_ok = False
    try:
        session_factory = request.app.state.v2_session_factory
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    status = "ok" if db_ok else "degraded"
    return {"status": status, "db_ok": db_ok}
