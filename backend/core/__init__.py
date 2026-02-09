"""Core module with logging, middleware, and exception handling."""

from backend.core.logging import get_logger, setup_logging
from backend.core.middleware import (
    ChatCSRFMiddleware,
    ForwardedHeadersMiddleware,
    HotPathRateLimitMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
    get_client_ip,
)
from backend.core.exceptions import setup_exception_handlers

__all__ = [
    "get_logger",
    "setup_logging",
    "ChatCSRFMiddleware",
    "ForwardedHeadersMiddleware",
    "HotPathRateLimitMiddleware",
    "RateLimitMiddleware",
    "RequestContextMiddleware",
    "RequestSizeLimitMiddleware",
    "SecurityHeadersMiddleware",
    "TrustedHostMiddleware",
    "get_client_ip",
    "setup_exception_handlers",
]
