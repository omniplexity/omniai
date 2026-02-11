"""Client telemetry validation + logging service."""

from __future__ import annotations

import hashlib
import random
from typing import Iterable

from backend.core.logging import get_logger
from backend.db.models import User

logger = get_logger(__name__)

ALLOWED_EVENT_TYPES = {
    "run_start",
    "run_first_delta",
    "run_done",
    "run_cancel",
    "run_error",
}


def validate_event_type(event_type: str) -> bool:
    return event_type in ALLOWED_EVENT_TYPES


def parse_client_sample_rate(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw.strip())
    except (TypeError, ValueError):
        return None
    if value < 0 or value > 1:
        return None
    return value


def resolve_effective_sample_rate(
    *,
    client_reported_rate: float | None,
    max_sample_rate: float,
    force_sample_rate: float | None,
) -> float:
    if force_sample_rate is not None:
        return force_sample_rate
    requested = 1.0 if client_reported_rate is None else client_reported_rate
    return min(requested, max_sample_rate)


def sample_events(
    *,
    user_id: str,
    events: list[dict],
    effective_sample_rate: float,
    sampling_mode: str,
) -> tuple[list[dict], int]:
    accepted: list[dict] = []
    dropped = 0
    for event in events:
        keep = should_keep_event(
            user_id=user_id,
            event=event,
            effective_sample_rate=effective_sample_rate,
            sampling_mode=sampling_mode,
        )
        if keep:
            accepted.append(event)
        else:
            dropped += 1
    return accepted, dropped


def should_keep_event(
    *,
    user_id: str,
    event: dict,
    effective_sample_rate: float,
    sampling_mode: str,
) -> bool:
    if effective_sample_rate >= 1.0:
        return True
    if effective_sample_rate <= 0.0:
        return False

    if sampling_mode == "random":
        return random.random() < effective_sample_rate

    key = (
        f"{user_id}:{event.get('type', '')}:{event.get('run_id', '')}:"
        f"{event.get('ts', '')}:{event.get('event_seq', '')}"
    )
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    probe = int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF + 1)
    return probe < effective_sample_rate


def log_client_events(*, user: User, events: Iterable[dict], request_id: str | None = None) -> int:
    count = 0
    for event in events:
        count += 1
        logger.info(
            "Client event ingested",
            data={
                "user_id": user.id,
                "request_id": request_id,
                "event_type": event.get("type"),
                "run_id": event.get("run_id"),
                "backend_run_id": event.get("backend_run_id"),
                "conversation_id": event.get("conversation_id"),
                "code": event.get("code"),
                "ts": event.get("ts"),
            },
        )
    return count
