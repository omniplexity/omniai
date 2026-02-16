from __future__ import annotations

import json
import logging
from typing import Any

SENSITIVE_KEYS = {"api_key", "token", "secret", "password"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload["extra"] = redact_dict(record.extra)
        return json.dumps(payload, ensure_ascii=True)


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_KEYS:
            out[key] = "***"
        elif isinstance(value, dict):
            out[key] = redact_dict(value)
        else:
            out[key] = value
    return out


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)