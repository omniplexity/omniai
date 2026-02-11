"""
Health check endpoints.

Provides liveness and readiness probes for monitoring.
"""

from datetime import UTC, datetime
import os
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.db import verify_database_connection
from backend.db.database import get_session_local
from backend.db.models import DuckDnsUpdateEvent
from backend.services.capabilities_service import compute_service_capabilities

router = APIRouter(tags=["health"])


def _safe_env_string(name: str) -> str:
    raw = (os.getenv(name) or "").strip()
    return raw if raw else "unknown"


def _duckdns_scheduler_stale() -> bool:
    settings = get_settings()
    if not settings.ops_scheduler_enabled:
        return False

    db = None
    try:
        session_local = get_session_local()
        db = session_local()
        last = (
            db.query(DuckDnsUpdateEvent)
            .order_by(DuckDnsUpdateEvent.created_at.desc())
            .first()
        )
        if not last or not last.created_at:
            return True
        age_seconds = int(datetime.now(UTC).timestamp() - last.created_at.timestamp())
        return age_seconds > (10 * 60)
    except Exception:
        # Conservative health signal: if scheduler state can't be read, mark stale.
        return True
    finally:
        if db is not None:
            db.close()


@router.get("/health")
@router.get("/healthz")
async def healthcheck() -> dict[str, Any]:
    """
    Health check endpoint.

    Returns basic service health status. Used by load balancers,
    orchestrators, and monitoring systems.
    """
    settings = get_settings()
    environment = (
        (os.getenv("OMNIAI_ENV") or "").strip()
        or (os.getenv("ENVIRONMENT") or "").strip()
        or (settings.environment or "").strip()
        or "unknown"
    )

    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.now(UTC).isoformat(),
        "build_sha": _safe_env_string("BUILD_SHA"),
        "build_time": _safe_env_string("BUILD_TIME"),
        "environment": environment,
        "debug": settings.debug,
        "duckdns_token_present": bool((os.getenv("DUCKDNS_TOKEN") or settings.duckdns_token or "").strip()),
        "duckdns_scheduler_stale": _duckdns_scheduler_stale(),
    }


@router.get("/readyz")
async def readiness(request: Request) -> JSONResponse:
    """
    Readiness check endpoint.

    Returns service readiness status. Checks that all required
    dependencies are available. Used by orchestrators to determine
    if the service should receive traffic.
    """
    checks: dict[str, bool] = {
        "database": verify_database_connection(),
        "config": True,
    }
    details: dict[str, Any] = {}

    settings = get_settings()
    if settings.readiness_check_providers:
        providers_ok = True
        provider_checks: dict[str, bool] = {}
        registry = getattr(request.app.state, "provider_registry", None)
        if registry is not None:
            for provider_id, provider in registry.providers.items():
                try:
                    ok = await provider.healthcheck()
                except Exception:  # pragma: no cover - defensive
                    ok = False
                provider_checks[provider_id] = bool(ok)
                if not ok:
                    providers_ok = False
        else:
            providers_ok = False
        checks["providers"] = providers_ok
        details["providers"] = provider_checks

    all_ready = all(checks.values())
    payload: dict[str, Any] = {
        "status": "ready" if all_ready else "not_ready",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }
    if details:
        payload["details"] = details

    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )


@router.get("/capabilities")
async def get_capabilities(request: Request) -> dict[str, Any]:
    """
    Get service capabilities.
    
    Returns feature flags and capabilities that the frontend can use
    to enable/disable features dynamically.
    """
    registry = getattr(request.app.state, "provider_registry", None)
    return await compute_service_capabilities(registry)
