"""Canonical API error envelope helpers."""

from __future__ import annotations

from typing import Any


def http_status_to_code(status_code: int) -> str:
    """Map HTTP status to legacy-compatible error code."""
    return f"E{status_code}0"


def build_error_envelope(
    *,
    code: str,
    message: str,
    request_id: str | None,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build canonical `/v1/*` error payload."""
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    if detail is not None:
        payload["error"]["detail"] = detail
    if extra:
        payload.update(extra)
    return payload
