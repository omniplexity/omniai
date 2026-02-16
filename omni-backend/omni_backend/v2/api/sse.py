"""V2 SSE endpoint for streaming run events with reconnect/resume."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

from ..core.eventbus import MemoryEventBus
from ..services.run_service import RunService, parse_cursor

logger = logging.getLogger("omni_backend.v2.sse")

router = APIRouter(prefix="/runs")


def _get_run_service(request: Request) -> RunService:
    return RunService(request.app.state.v2_session_factory)


def _get_eventbus(request: Request) -> MemoryEventBus:
    return request.app.state.v2_eventbus


def _get_heartbeat(request: Request) -> float:
    return request.app.state.v2_settings.sse_heartbeat_seconds


@router.get("/{run_id}/events/stream")
async def stream_events(run_id: str, request: Request, after: str | None = None):
    """SSE endpoint with backlog replay from DB + live events from EventBus.

    Supports:
      - ?after={cursor} query param
      - Last-Event-ID header (takes precedence)
    """
    svc = _get_run_service(request)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Determine resume point
    last_event_id = request.headers.get("Last-Event-ID")
    after_seq = 0
    if last_event_id:
        try:
            _, after_seq = parse_cursor(last_event_id)
        except ValueError:
            pass
    elif after:
        try:
            _, after_seq = parse_cursor(after)
        except ValueError:
            pass

    eventbus = _get_eventbus(request)
    heartbeat_s = _get_heartbeat(request)
    channel = f"run:{run_id}"
    max_replay = request.app.state.v2_settings.sse_max_replay

    async def event_generator():
        nonlocal after_seq

        # Phase 1: Replay from DB
        backlog = await svc.get_events(run_id, after_seq=after_seq, limit=max_replay)
        for ev in backlog:
            cursor = ev["cursor"]
            after_seq = ev["seq"]
            yield f"id: {cursor}\nevent: {ev['kind']}\ndata: {json.dumps(ev['payload'])}\n\n"

        # Phase 2: Live events from eventbus + heartbeat
        live_iter = eventbus.subscribe(channel, after_id=None)
        live_stream = live_iter.__aiter__()

        while True:
            try:
                bus_event = await asyncio.wait_for(live_stream.__anext__(), timeout=heartbeat_s)
                # Parse seq from event_id cursor
                try:
                    _, ev_seq = parse_cursor(bus_event.event_id)
                except ValueError:
                    continue
                if ev_seq <= after_seq:
                    continue  # already sent via backlog
                after_seq = ev_seq
                yield f"id: {bus_event.event_id}\nevent: {bus_event.data.get('kind', 'message')}\ndata: {json.dumps(bus_event.data.get('payload', bus_event.data))}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
            except StopAsyncIteration:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
