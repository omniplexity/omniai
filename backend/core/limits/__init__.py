"""Rate limit and concurrency store abstractions.

This module provides pluggable backends for rate limiting and SSE concurrency
control. The interfaces allow swapping between in-memory (current behavior)
and distributed stores (Redis) without changing handler logic.

Usage:
    from backend.core.limits import get_rate_limit_store, get_concurrency_store

    # In app lifespan:
    rate_store = get_rate_limit_store(settings.limits_backend)
    conc_store = get_concurrency_store(settings.limits_backend)

    # In handlers:
    result = await rate_store.hit("user:123", limit=60, window_s=60)
    acquired = await conc_store.acquire("stream:123", limit=3, ttl_s=3600)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

__all__ = [
    "RateLimitResult",
    "RateLimitStore",
    "ConcurrencyStore",
    "InMemoryRateLimitStore",
    "InMemoryConcurrencyStore",
]


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is allowed.
        remaining: Number of requests remaining in the window.
        reset_epoch_s: Unix timestamp when the window resets.
    """
    allowed: bool
    remaining: int
    reset_epoch_s: int


class RateLimitStore(Protocol):
    """Protocol for rate limit backends.

    Implementations should be atomic where possible to prevent race conditions
    in multi-worker deployments.
    """

    async def hit(self, key: str, limit: int, window_s: int) -> RateLimitResult:
        """Record a request and check rate limit.

        Args:
            key: Unique identifier for the rate limit bucket (e.g., "ip:1.2.3.4")
            limit: Maximum requests allowed in the window.
            window_s: Window duration in seconds.

        Returns:
            RateLimitResult with allowed/remaining/reset info.
        """
        ...


class ConcurrencyStore(Protocol):
    """Protocol for SSE/concurrent connection limiting.

    Used to prevent resource exhaustion from long-lived streaming connections.
    Implementations should use TTLs to prevent leaks if a worker dies.

    Security: acquire() and release() should use token-based ownership to prevent
    one worker releasing another worker's slot (e.g., during race condition).
    """

    async def acquire(self, key: str, limit: int, ttl_s: int) -> tuple[bool, str | None]:
        """Try to acquire a concurrent slot.

        Args:
            key: Unique identifier (e.g., "stream:user:123")
            limit: Maximum concurrent slots for this key.
            ttl_s: Time-to-live for the slot (prevents stale entries).

        Returns:
            Tuple of (success, token). If success is True, token must be
            passed to release() to verify ownership. Token is None if acquire failed.
        """
        ...

    async def release(self, key: str, token: str) -> bool:
        """Release a concurrent slot using token verification.

        Args:
            key: The same key used in acquire().
            token: The token returned from acquire() to verify ownership.

        Returns:
            True if released, False if token didn't match (slot may have expired).
        """
        ...
