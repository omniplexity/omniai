"""V2 runs + events endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.eventbus import BusEvent, MemoryEventBus
from ..services.run_service import RunService, parse_cursor

router = APIRouter(prefix="/runs")


class CreateRunRequest(BaseModel):
    thread_id: str
    status: str = "active"


class AppendEventRequest(BaseModel):
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "system"
    parent_event_id: str | None = None
    correlation_id: str | None = None


def _get_run_service(request: Request) -> RunService:
    return RunService(request.app.state.v2_session_factory)


@router.post("")
async def create_run(body: CreateRunRequest, request: Request):
    svc = _get_run_service(request)
    run = await svc.create_run(thread_id=body.thread_id, status=body.status)
    return run


@router.get("/{run_id}")
async def get_run(run_id: str, request: Request):
    svc = _get_run_service(request)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/events")
async def append_event(run_id: str, body: AppendEventRequest, request: Request):
    svc = _get_run_service(request)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    event = await svc.append_event(
        run_id,
        kind=body.kind,
        payload=body.payload,
        actor=body.actor,
        parent_event_id=body.parent_event_id,
        correlation_id=body.correlation_id,
    )

    # Publish to eventbus for live SSE subscribers
    eventbus: MemoryEventBus = request.app.state.v2_eventbus
    await eventbus.publish(
        f"run:{run_id}",
        BusEvent(channel=f"run:{run_id}", event_id=event["cursor"], data=event),
    )

    return event


@router.get("/{run_id}/events")
async def list_events(run_id: str, request: Request, after: str | None = None, limit: int = 500):
    svc = _get_run_service(request)
    after_seq = 0
    if after:
        try:
            _, after_seq = parse_cursor(after)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor format")
    events = await svc.get_events(run_id, after_seq=after_seq, limit=limit)
    return {"events": events}
