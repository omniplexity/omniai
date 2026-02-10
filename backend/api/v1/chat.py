"""v1 chat endpoints.

These endpoints use the Chat Agent for chat operations.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from backend.agents.chat import ChatAgent
from backend.agents.conversation import ConversationAgent
from backend.agents.provider import ProviderAgent
from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.core.logging import get_logger
from backend.db import get_db
from backend.db.models import ChatRun, ChatRunEvent, Conversation, User
from backend.streaming.sse import format_sse_event

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["v1-chat"])

# Event type constants for canonical SSE contract
_CANONICAL_EVENT_MESSAGE = "message"
_CANONICAL_EVENT_DONE = "done"
_CANONICAL_EVENT_ERROR = "error"
_CANONICAL_EVENT_STOPPED = "stopped"


def _map_event_to_canonical(evt: ChatRunEvent) -> Optional[tuple[str, Dict[str, Any]]]:
    """Map internal event types to canonical SSE events.
    
    Returns:
        Tuple of (canonical_event_type, canonical_payload) or None if event should be skipped
    """
    # Extract payload - already parsed as dict
    payload = evt.payload_json or {}
    role = payload.get("role", "")
    
    # Internal event type mapping to canonical SSE events
    event_map = {
        # message.delta -> message with delta type (always assistant)
        "message.delta": (
            _CANONICAL_EVENT_MESSAGE,
            {"type": "delta", "content": payload.get("delta", "")}
        ),
        # message.final -> message with full type + usage
        "message.final": (
            _CANONICAL_EVENT_MESSAGE,
            {
                "type": "full",
                "content": payload.get("content", ""),
                "message_id": payload.get("message_id", ""),
                "usage": payload.get("provider_meta", {}).get("tokens", {}) or {}
            }
        ),
    }
    
    mapped = event_map.get(evt.type)
    if mapped:
        canonical_type, canonical_payload = mapped
        if canonical_type is not None:
            return (canonical_type, canonical_payload)
    
    # Handle message.created specially - only emit for assistant role
    if evt.type == "message.created":
        if role == "user":
            # Skip user message creation - not part of canonical assistant stream
            return None
        
        # Assistant message - emit as full message
        return (
            _CANONICAL_EVENT_MESSAGE,
            {
                "type": "full",
                "content": payload.get("content", ""),
                "message_id": payload.get("id", "") or payload.get("message_id", ""),
                "usage": payload.get("provider_meta", {}).get("tokens", {}) or payload.get("tokens", {}) or {}
            }
        )
    
    # receipt -> message with full type (final message)
    if evt.type == "receipt":
        return (
            _CANONICAL_EVENT_MESSAGE,
            {
                "type": "full",
                "content": payload.get("content", ""),
                "message_id": payload.get("message_id", ""),
                "usage": payload.get("provider_meta", {}).get("tokens", {}) or {}
            }
        )
    
    # error -> error
    if evt.type == "error":
        return (
            _CANONICAL_EVENT_ERROR,
            {"error": payload.get("message", payload.get("error", "Unknown error")), "code": payload.get("code", "")}
        )
    
    # run.status=completed -> done
    # run.status=cancelled -> stopped
    # run.status=running -> skip (intermediate status not part of canonical contract)
    if evt.type == "run.status" and payload.get("status") in ("completed", "cancelled"):
        if payload.get("status") == "completed":
            return (
                _CANONICAL_EVENT_DONE,
                {
                    "status": "completed",
                    "message_id": payload.get("message_id", ""),
                    "run_id": payload.get("run_id", "")
                }
            )
        else:
            return (
                _CANONICAL_EVENT_STOPPED,
                {
                    "run_id": payload.get("run_id", "")
                }
            )
    
    # run.started, run.metrics, etc. - skip these internal events
    return None


class ChatRequest(BaseModel):
    """Chat request."""
    conversation_id: str
    input: Optional[str] = Field(default=None)
    provider: Optional[str] = None
    model: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    stream: bool = False
    retry_from_message_id: Optional[str] = None


class ChatRetryRequest(BaseModel):
    """Retry chat request."""
    conversation_id: str
    message_id: str
    provider: Optional[str] = None
    model: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ChatCancelRequest(BaseModel):
    """Cancel chat request."""
    run_id: str


def _create_chat_agent(db: DBSession, request: Request) -> ChatAgent:
    """Create a Chat Agent instance."""
    registry = getattr(request.app.state, "provider_registry", None)
    provider_agent = ProviderAgent(get_settings(), registry)
    conversation_agent = ConversationAgent(db)
    return ChatAgent(db, provider_agent, conversation_agent)


@router.post("")
async def create_chat_run(
    body: ChatRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat run (streaming or non-streaming)."""
    registry = getattr(request.app.state, "provider_registry", None)
    if not registry:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No providers available")

    conversation = db.query(Conversation).filter(
        Conversation.id == body.conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    chat_agent = _create_chat_agent(db, request)

    if body.stream:
        if not body.input and not body.retry_from_message_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input required")

        run = chat_agent.create_run(
            conversation=conversation,
            user=current_user,
            input_text=body.input or "",
            provider_name=body.provider,
            model=body.model,
            retry_from_message_id=body.retry_from_message_id,
        )
        
        # Start event generation in background
        # Use request.state to get event loop or create new task
        async def start_streaming():
            # Create a new session for the background task
            from backend.db import get_db
            from backend.db.database import engine
            from sqlalchemy.orm import sessionmaker
            
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            try:
                agent = _create_chat_agent(db, request)
                # Re-fetch conversation with new session
                convo = db.query(Conversation).filter(Conversation.id == conversation.id).first()
                if convo:
                    await _run_and_emit_events(db, agent, run, convo, current_user, body.input or "")
            finally:
                db.close()
        
        # Schedule the background task
        asyncio.create_task(start_streaming())
        
        return {"run_id": run.id, "status": run.status}

    if not body.input:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input required")

    try:
        result = await chat_agent.send_message(
            conversation=conversation,
            user=current_user,
            content=body.input,
            provider_name=body.provider,
            model=body.model,
            stream=False,
        )
    except Exception as exc:
        logger.error("Chat completion failed", data={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return result


@router.post("/retry")
async def retry_chat_run(
    body: ChatRetryRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retry a message in a conversation."""
    registry = getattr(request.app.state, "provider_registry", None)
    if not registry:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No providers available")

    conversation = db.query(Conversation).filter(
        Conversation.id == body.conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    chat_agent = _create_chat_agent(db, request)

    run = chat_agent.retry_message(
        conversation=conversation,
        user=current_user,
        message_id=body.message_id,
        provider_name=body.provider,
        model=body.model,
    )
    return {"run_id": run.id, "status": run.status}


@router.post("/cancel")
async def cancel_chat_run(
    body: ChatCancelRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a running chat."""
    chat_agent = _create_chat_agent(db, request)

    run = chat_agent.get_run(body.run_id, current_user)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    chat_agent.cancel_run(run)
    return {"status": "cancelled", "run_id": run.id}


@router.get("/stream")
async def stream_chat_run(
    run_id: str,
    request: Request,
    after: Optional[int] = None,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream events from a chat run.
    
    Enforces concurrent stream limits per user using the concurrency store.
    """
    run = db.query(ChatRun).filter(ChatRun.id == run_id, ChatRun.user_id == current_user.id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # Acquire concurrency slot for this stream
    conc_store = getattr(request.app.state, "concurrency_store", None)
    settings = get_settings()
    conc_token = None

    if conc_store:
        # Key format: stream:{user_id}:{endpoint}
        conc_key = f"stream:{current_user.id}:v1"
        acquired, token = await conc_store.acquire(
            key=conc_key,
            limit=settings.sse_max_concurrent_per_user,
            ttl_s=settings.sse_max_duration_seconds + 60,  # TTL > max duration
        )
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many concurrent streams. Maximum: {settings.sse_max_concurrent_per_user}",
            )
        conc_token = token

    last_event_id = after
    if last_event_id is None:
        header = request.headers.get("Last-Event-ID")
        if header and header.isdigit():
            last_event_id = int(header)
        else:
            last_event_id = 0

    ping_interval = settings.sse_ping_interval_seconds
    max_duration = settings.sse_max_duration_seconds
    idle_timeout = settings.sse_idle_timeout_seconds

    async def event_stream():
        nonlocal last_event_id
        try:
            last_ping = time.monotonic()
            start_time = time.monotonic()
            last_activity = last_ping
            terminal_event_emitted = False
            
            while True:
                # Enforce max duration
                elapsed = time.monotonic() - start_time
                if elapsed >= max_duration:
                    logger.info("SSE stream exceeded max duration", data={"run_id": run.id, "elapsed": elapsed})
                    break

                events = (
                    db.query(ChatRunEvent)
                    .filter(ChatRunEvent.run_id == run.id, ChatRunEvent.seq > last_event_id)
                    .order_by(ChatRunEvent.seq.asc())
                    .limit(200)
                    .all()
                )
                for evt in events:
                    last_event_id = evt.seq
                    
                    # Map internal event to canonical SSE event
                    mapped = _map_event_to_canonical(evt)
                    if mapped:
                        canonical_type, canonical_payload = mapped
                        yield format_sse_event(evt.seq, canonical_type, canonical_payload)
                        
                        # Track if we emitted a terminal event
                        if canonical_type in (_CANONICAL_EVENT_DONE, _CANONICAL_EVENT_STOPPED, _CANONICAL_EVENT_ERROR):
                            terminal_event_emitted = True
                    
                    last_activity = time.monotonic()

                # Check if run reached terminal state and we have no more events to process
                refreshed = db.query(ChatRun).filter(ChatRun.id == run.id).first()
                if refreshed and refreshed.status in {"completed", "cancelled", "error"} and not events:
                    # Emit terminal event if not already emitted via run.status
                    if not terminal_event_emitted and refreshed.status == "completed":
                        # Emit done event
                        last_event_id += 1
                        yield format_sse_event(last_event_id, _CANONICAL_EVENT_DONE, {"status": "completed", "run_id": run.id})
                    elif not terminal_event_emitted and refreshed.status == "cancelled":
                        # Emit stopped event
                        last_event_id += 1
                        yield format_sse_event(last_event_id, _CANONICAL_EVENT_STOPPED, {"run_id": run.id})
                    elif not terminal_event_emitted and refreshed.status == "error":
                        # Emit error event
                        last_event_id += 1
                        error_msg = refreshed.error_message or "Unknown error"
                        yield format_sse_event(last_event_id, _CANONICAL_EVENT_ERROR, {"error": error_msg})
                    break

                if await request.is_disconnected():
                    break

                now = time.monotonic()
                # Enforce idle timeout
                if now - last_activity >= idle_timeout:
                    logger.info("SSE stream idle timeout", data={"run_id": run.id, "idle_seconds": now - last_activity})
                    break

                if ping_interval and (now - last_ping) >= ping_interval:
                    last_ping = now
                    yield ": ping\n\n"
                    last_activity = now

                await asyncio.sleep(0.5)
        finally:
            # Release concurrency slot on stream end
            if conc_store and conc_token:
                await conc_store.release(key=f"stream:{current_user.id}:v1", token=conc_token)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )


async def _run_and_emit_events(
    db: DBSession,
    chat_agent: ChatAgent,
    run: ChatRun,
    conversation: Conversation,
    user: User,
    content: str,
) -> None:
    """Run chat streaming and persist events to the database.
    
    This is called after a run is created to actually execute the chat
    and persist events that will be streamed via SSE.
    """
    # Reset event sequence for this run
    chat_agent._event_seq = 0
    
    try:
        # Emit run started event
        chat_agent._emit_event(run.id, "run.started", {"status": "running"})
        
        async for event in chat_agent.stream_message(
            conversation=conversation,
            user=user,
            content=content,
            provider_name=run.provider,
            model=run.model,
        ):
            # Persist each event
            chat_agent._emit_event(run.id, event["event"], event.get("data", {}))
            db.commit()
            
            # Check for completion signals
            if event["event"] == "error":
                run.status = "error"
                run.error_message = event.get("data", {}).get("error", "Unknown error")
                db.commit()
                return
            
            if event["event"] == "message.created":
                data = event.get("data", {})
                # Check if this is the assistant message completion
                if data.get("role") == "assistant":
                    run.status = "completed"
                    db.commit()
                    return
        
        # Fallback: mark as completed if we exit normally
        if run.status == "running":
            run.status = "completed"
            db.commit()
            
    except asyncio.CancelledError:
        # Run was cancelled
        run.status = "cancelled"
        run.cancelled_at = datetime.utcnow()
        chat_agent._emit_event(run.id, "run.status", {"status": "cancelled"})
        db.commit()
        raise
    except Exception as exc:
        logger.error("Error in run event generation", data={"run_id": run.id, "error": str(exc)})
        run.status = "error"
        run.error_message = str(exc)
        chat_agent._emit_event(run.id, "error", {"message": str(exc)})
        db.commit()
