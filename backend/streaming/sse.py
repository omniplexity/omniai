"""SSE (Server-Sent Events) formatting utilities."""

import json
from typing import Any, Dict


def format_sse_event(seq: int, event_type: str, payload: Dict[str, Any]) -> str:
    """Format a single SSE event string.
    
    Args:
        seq: Sequence number for the event
        event_type: Type of the event (e.g., 'message', 'error', 'done')
        payload: Dictionary of data to send
        
    Returns:
        Formatted SSE event string ready for streaming
    """
    return f"id: {seq}\nevent: {event_type}\ndata: {json.dumps(payload)}\n\n"
