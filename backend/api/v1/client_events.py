"""v1 client events endpoint (optional, metadata-only ingest)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.db.models import User
from backend.services.client_events import (
    log_client_events,
    parse_client_sample_rate,
    resolve_effective_sample_rate,
    sample_events,
    validate_event_type,
)

router = APIRouter(prefix="/client-events", tags=["v1-client-events"])


class ClientEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    run_id: str = Field(min_length=1)
    backend_run_id: str | None = None
    conversation_id: str | None = None
    code: str | None = None
    ts: str | None = None


class ClientEventsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[ClientEventIn]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_client_events(
    body: dict,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    if not settings.client_events_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        parsed = ClientEventsRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if len(parsed.events) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="events must not be empty")
    if len(parsed.events) > settings.client_events_max_batch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"events batch exceeds max {settings.client_events_max_batch}",
        )

    for event in parsed.events:
        if not validate_event_type(event.type):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid event type: {event.type}")

    rate_store = getattr(request.app.state, "rate_limit_store", None)
    if rate_store:
        result = await rate_store.hit(
            key=f"client-events:user:{current_user.id}",
            limit=settings.client_events_rpm,
            window_s=60,
        )
        if not result.allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    client_rate = parse_client_sample_rate(request.headers.get("X-Client-Events-Sample-Rate"))
    effective_rate = resolve_effective_sample_rate(
        client_reported_rate=client_rate,
        max_sample_rate=settings.client_events_max_sample_rate,
        force_sample_rate=settings.client_events_force_sample_rate,
    )
    sampled_events, dropped = sample_events(
        user_id=current_user.id,
        events=[event.model_dump() for event in parsed.events],
        effective_sample_rate=effective_rate,
        sampling_mode=settings.client_events_sampling_mode,
    )

    accepted = log_client_events(
        user=current_user,
        events=sampled_events,
        request_id=getattr(request.state, "request_id", None),
    )
    return {
        "status": "accepted",
        "accepted_count": accepted,
        "dropped_count": dropped,
        "effective_sample_rate": effective_rate,
        "sampling_mode": settings.client_events_sampling_mode,
    }
