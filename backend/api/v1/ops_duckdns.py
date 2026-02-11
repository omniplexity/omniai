"""Admin DuckDNS ops endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from backend.agents.ops.duckdns_service import DuckDnsError, DuckDnsOpsService
from backend.auth.dependencies import get_admin_user
from backend.config import get_settings
from backend.db import get_db
from backend.db.models import User
from backend.services.audit_service import audit_log_event

router = APIRouter(prefix="/ops/duckdns", tags=["v1-ops-duckdns"])


class DuckDnsUpdateRequest(BaseModel):
    force: bool = Field(default=False)


class DuckDnsTestRequest(BaseModel):
    ip: Optional[str] = Field(default=None)


def _error_response(error: DuckDnsError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "detail": error.message,
            "error": {
                "code": error.code,
                "message": error.message,
            },
        },
    )


@router.get("/status")
async def duckdns_status(
    request: Request,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    settings = get_settings()
    service = DuckDnsOpsService(db=db, settings=settings)
    payload = service.get_status(scheduler_interval_minutes=settings.ops_scheduler_interval_minutes)
    audit_log_event(
        db,
        event_type="ops.duckdns.status",
        user_id=admin.id,
        request=request,
        data={"scheduler_enabled": payload["scheduler_enabled"]},
    )
    return payload


@router.get("/logs")
async def duckdns_logs(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    service = DuckDnsOpsService(db=db)
    payload = service.get_logs(limit=limit)
    audit_log_event(
        db,
        event_type="ops.duckdns.logs",
        user_id=admin.id,
        request=request,
        data={"limit": limit},
    )
    return payload


@router.post("/update")
async def duckdns_update(
    body: DuckDnsUpdateRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    service = DuckDnsOpsService(db=db)
    try:
        result = await service.update(
            force=body.force,
            test=False,
            actor_user_id=admin.id,
            source="manual",
        )
        audit_log_event(
            db,
            event_type="ops.duckdns.update",
            user_id=admin.id,
            request=request,
            data={"force": bool(body.force), "success": True},
        )
        return result
    except DuckDnsError as err:
        audit_log_event(
            db,
            event_type="ops.duckdns.update",
            user_id=admin.id,
            request=request,
            data={"force": bool(body.force), "success": False, "error_code": err.code},
        )
        return _error_response(err)


@router.post("/test")
async def duckdns_test(
    body: DuckDnsTestRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    service = DuckDnsOpsService(db=db)
    try:
        result = await service.update(
            force=True,
            test=True,
            ip=body.ip,
            actor_user_id=admin.id,
            source="test",
        )
        audit_log_event(
            db,
            event_type="ops.duckdns.test",
            user_id=admin.id,
            request=request,
            data={"ip_supplied": body.ip is not None, "success": True},
        )
        return result
    except DuckDnsError as err:
        audit_log_event(
            db,
            event_type="ops.duckdns.test",
            user_id=admin.id,
            request=request,
            data={"ip_supplied": body.ip is not None, "success": False, "error_code": err.code},
        )
        return _error_response(err)
