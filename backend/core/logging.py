"""Structured logging configuration for OmniAI."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional, Set

# Context variable for request-scoped data
request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})

# Headers that should be redacted in logs
SENSITIVE_HEADERS: Set[str] = {
    "authorization",
    "x-csrf-token",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
}

# Cookie names that should be redacted (partial match)
SENSITIVE_COOKIES: Set[str] = {
    "omni_session",
    "omni_csrf",
    "session",
    "csrf",
    "token",
}

# Regex patterns for redaction
# Short token pattern: fully mask tokens < 12 chars
_SHORT_TOKEN_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,11}$')
# Token with hash prefix: e.g., "sha256:abc123..."
_TOKEN_WITH_PREFIX = re.compile(r'^([a-f0-9]+:[a-zA-Z0-9_-]{4}).*([a-zA-Z0-9_-]{4})$')


def _is_token_like(value: str) -> bool:
    """Check if a string looks like a sensitive token."""
    if len(value) < 8:
        return False
    # Remove common prefixes and check if remaining is alphanumeric
    cleaned = value
    if ':' in value:
        cleaned = value.split(':', 1)[1]
    # Token-like: mostly alphanumeric with hyphens/underscores allowed
    return bool(cleaned.replace('-', '').replace('_', '').replace(':', '').isalnum())


def _redact_value(value: str) -> str:
    """Redact a sensitive value.
    
    Args:
        value: The value to redact
    """
    if not isinstance(value, str):
        return "[REDACTED]"

    # Short secrets (<12 chars): fully mask
    if len(value) < 12:
        return "<REDACTED>"

    # Token with hash prefix (e.g., "sha256:abcd1234..."): show prefix + first/last
    if ':' in value:
        prefix, rest = value.split(':', 1)
        rest = rest.strip()
        if rest and len(rest) >= 8:
            return f"{prefix}:{rest[:4]}***{rest[-4:]}"

    # Standard token: show first/last 3 chars if length permits
    if len(value) >= 12:
        return f"{value[:3]}***{value[-3:]}"

    # Very short: fully mask
    return "<REDACTED>"


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redact sensitive data from dictionaries or strings.
    
    Redacts:
    - Authorization header values
    - Cookie headers (masks cookie values)
    - CSRF token headers
    - Session cookies
    - Short secrets (<12 chars): fully masked
    - Long tokens: shows prefix+first/last chars, not middle
    """
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in SENSITIVE_HEADERS:
                # Authorization, X-CSRF-Token, etc. - redact value
                redacted[key] = _redact_value(value)
            elif key_lower == "cookie":
                # Cookie header - mask all cookie values
                if isinstance(value, str):
                    # Replace cookie values with redacted placeholder
                    redacted[key] = re.sub(r'=[^;]*', '=<REDACTED>', value)
                else:
                    redacted[key] = "[REDACTED]"
            elif "cookie" in key_lower:
                # Cookie-related keys
                if isinstance(value, str):
                    redacted[key] = re.sub(r'=[^;]*', '=<REDACTED>', value)
                else:
                    redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive_data(value)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        # Check if string looks like a sensitive token
        if _is_token_like(data):
            return _redact_value(data)
    return data


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context if available
        ctx = request_context.get()
        if ctx:
            log_data["request_id"] = ctx.get("request_id")
            log_data["path"] = ctx.get("path")

        # Add extra data if provided (with sensitive data redacted)
        if hasattr(record, "data") and record.data:
            log_data["data"] = redact_sensitive_data(record.data)

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",   # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console."""
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        ctx = request_context.get()
        request_id = ctx.get("request_id", "-")[:8] if ctx else "-"

        message = f"{timestamp} | {color}{record.levelname:8}{self.RESET} | {request_id} | {record.name} | {record.getMessage()}"

        if hasattr(record, "data") and record.data:
            message += f" | {record.data}"

        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that includes request context."""

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message with context."""
        extra = kwargs.get("extra", {})
        if "data" in kwargs:
            extra["data"] = kwargs.pop("data")
        kwargs["extra"] = extra
        return msg, kwargs


_loggers: Dict[str, ContextLogger] = {}


def get_logger(name: str) -> ContextLogger:
    """Get a context-aware logger."""
    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = ContextLogger(logger, {})
    return _loggers[name]


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """Configure application logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if json_output:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())
    root_logger.addHandler(console_handler)

    # File handler (always JSON)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)

    # Quiet noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
