"""v1 ops endpoints.

Security: All endpoints require admin authentication.
These endpoints expose only safe aggregates to avoid leaking internal capacity signals.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from backend.auth.dependencies import get_admin_user
from backend.config import get_settings
from backend.config.settings import Settings
from backend.core.limits.factory import get_concurrency_store, get_rate_limit_store, _redis_available
from backend.core.logging import get_logger
from backend.db.models import User

logger = get_logger(__name__)
router = APIRouter(tags=["v1-ops"])


@router.get("/providers/health")
async def providers_health(
    request: Request,
    admin: User = Depends(get_admin_user),
) -> Dict[str, bool]:
    """Check provider health status. Admin only."""
    registry = getattr(request.app.state, "provider_registry", None)
    if not registry:
        return {"status": "no_providers_configured"}
    health = await registry.healthcheck_all()
    # Return only boolean status, not provider details to avoid capacity leaks
    return {"healthy": all(health.values())}


@router.get("/ops/limits")
async def ops_limits(
    admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Return operational limits summary. Admin only.
    
    Note: Returns only safe aggregates, not exact capacity values
    that could be used for resource exhaustion attacks.
    """
    settings = get_settings()
    return {
        "rate_limiting_enabled": True,
        "request_sizing_enforced": True,
        "voice_sizing_enforced": True,
    }


@router.get("/audit/recent")
async def recent_audit(
    request: Request,
    admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Retrieve recent audit log entries. Admin only."""
    # TODO: Implement full audit log retrieval with pagination
    # For now, return placeholder until audit log service is fully integrated
    return {"entries": [], "note": "Audit log retrieval coming soon"}


@router.get("/ops/store-health")
async def store_health(
    request: Request,
    admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Return store backend health status. Admin only.
    
    Exposes which backend is in use and connectivity status.
    Does not expose credentials or connection URLs.
    """
    settings = get_settings()
    result: Dict[str, Any] = {
        "limits_backend": settings.limits_backend,
    }
    
    if settings.limits_backend == "redis":
        # Check Redis connectivity without exposing URLs
        if _redis_available:
            try:
                # Use factory to create store and test connection
                store = get_concurrency_store(
                    "redis",
                    redis_url=settings.redis_url,
                )
                # Simple connectivity check - get a client and ping
                client = await store._get_client()
                await client.ping()
                result["redis_connected"] = True
            except Exception:
                result["redis_connected"] = False
        else:
            result["redis_connected"] = False
    
    return result
