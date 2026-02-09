"""In-memory rate limit and concurrency store implementations.

These implementations match the current behavior of RateLimitMiddleware
and HotPathRateLimitMiddleware. They are per-process and should only be
used when running a single worker.

For multi-worker deployments, use Redis-based implementations.
"""

from __future__ import annotations

import secrets
import time
from asyncio import Lock
from collections import deque
from typing import AsyncGenerator

from backend.core.limits import (
    ConcurrencyStore,
    RateLimitResult,
    RateLimitStore,
)


class InMemoryRateLimitStore(RateLimitStore):
    """In-memory fixed-window rate limiting.

    Uses a deque per key with cleanup of expired entries on each access.
    This is the current behavior of RateLimitMiddleware.

    Note: This implementation is NOT atomic across multiple processes.
    Use RedisRateLimitStore for distributed deployments.
    """

    def __init__(self, window_seconds: int = 60):
        """Initialize the rate limit store.

        Args:
            window_seconds: Default window duration in seconds.
        """
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    async def hit(self, key: str, limit: int, window_s: int | None = None) -> RateLimitResult:
        """Record a request and check rate limit.

        Args:
            key: Unique identifier for the rate limit bucket.
            limit: Maximum requests allowed in the window.
            window_s: Window duration in seconds. Defaults to constructor value.

        Returns:
            RateLimitResult with allowed/remaining/reset info.
        """
        ws = window_s or self._window_seconds
        now = time.monotonic()
        cutoff = now - ws

        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            # Remove expired entries
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            # Calculate reset time (start of next window)
            window_start = int(now // ws) * ws
            reset_epoch_s = window_start + ws

            if len(bucket) >= limit:
                # Rate limited
                remaining = 0
                allowed = False
            else:
                # Record this request
                bucket.append(now)
                remaining = limit - len(bucket)
                allowed = True

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_epoch_s=reset_epoch_s,
        )


class InMemoryConcurrencyStore(ConcurrencyStore):
    """In-memory semaphore-like concurrency control with TTL.

    Used for limiting concurrent SSE streams per user.
    Entries expire after TTL to prevent leaks if a worker dies.

    Note: This implementation is NOT atomic across multiple processes.
    Use RedisConcurrencyStore for distributed deployments.

    Uses token-based release for compatibility with Redis store.
    """

    def __init__(self, default_ttl_seconds: int = 3600):
        """Initialize the concurrency store.

        Args:
            default_ttl_seconds: Default TTL for slots in seconds.
        """
        self._default_ttl = default_ttl_seconds
        # Slots: key -> {token: (expires_at, count)}
        self._slots: dict[str, dict[str, tuple[float, int]]] = {}
        self._lock = Lock()

    async def acquire(self, key: str, limit: int, ttl_s: int | None = None) -> tuple[bool, str | None]:
        """Try to acquire a concurrent slot.

        Args:
            key: Unique identifier for the concurrent operation.
            limit: Maximum concurrent slots for this key.
            ttl_s: TTL for the slot. Defaults to constructor value.

        Returns:
            Tuple of (success, token). Token must be passed to release().
        """
        ttl = ttl_s or self._default_ttl
        now = time.monotonic()
        expires_at = now + ttl

        async with self._lock:
            # Ensure key dict exists
            if key not in self._slots:
                self._slots[key] = {}

            # Clean expired entries
            expired_tokens = [
                token for token, (exp, _) in self._slots[key].items() if exp < now
            ]
            for token in expired_tokens:
                del self._slots[key][token]

            # Count active slots
            current_count = len(self._slots[key])

            if current_count >= limit:
                # Limit reached
                return (False, None)

            # Acquire slot with unique token
            token = secrets.token_hex(8)
            self._slots[key][token] = (expires_at, current_count + 1)
            return (True, token)

    async def release(self, key: str, token: str) -> bool:
        """Release a concurrent slot using token verification.

        Args:
            key: The same key used in acquire().
            token: The token returned from acquire().

        Returns:
            True if released, False if token didn't match.
        """
        async with self._lock:
            if key not in self._slots:
                return False
            if token not in self._slots[key]:
                return False

            del self._slots[key][token]
            # Clean up empty key dict
            if not self._slots[key]:
                del self._slots[key]
            return True
