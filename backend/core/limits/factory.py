"""Factory functions for rate limit and concurrency stores.

This module provides factory functions that return the appropriate store
implementation based on the configured backend (memory|redis).

Usage:
    from backend.core.limits.factory import get_rate_limit_store, get_concurrency_store

    rate_store = get_rate_limit_store(settings.limits_backend, redis_url=settings.redis_url)
    conc_store = get_concurrency_store(settings.limits_backend, redis_url=settings.redis_url)
"""

from __future__ import annotations

from backend.config.settings import Settings
from backend.core.limits import (
    ConcurrencyStore,
    RateLimitStore,
)
from backend.core.limits.memory import (
    InMemoryConcurrencyStore,
    InMemoryRateLimitStore,
)

# Lazy imports for Redis (optional dependency)
_redis_available = True
try:
    import redis.asyncio as redis
except ImportError:
    _redis_available = False


def get_rate_limit_store(
    backend: str = "memory",
    *,
    redis_url: str = "",
    window_seconds: int = 60,
) -> RateLimitStore:
    """Get a rate limit store implementation.

    Args:
        backend: Backend type ("memory" or "redis")
        redis_url: Redis connection URL (required for redis backend)
        window_seconds: Default window duration for in-memory store

    Returns:
        RateLimitStore implementation

    Raises:
        ValueError: If redis backend selected but redis_url not provided
        ImportError: If redis backend selected but redis package not installed
    """
    if backend == "memory":
        return InMemoryRateLimitStore(window_seconds=window_seconds)

    if backend == "redis":
        if not _redis_available:
            raise ImportError(
                "redis package is required for redis backend. "
                "Install with: pip install redis>=5.0.0"
            )
        if not redis_url:
            raise ValueError(
                "redis_url is required when limits_backend=redis"
            )
        return _RedisRateLimitStore(redis_url=redis_url, window_seconds=window_seconds)

    raise ValueError(f"Unknown limits_backend: {backend}. Use 'memory' or 'redis'")


def get_concurrency_store(
    backend: str = "memory",
    *,
    redis_url: str = "",
    default_ttl_seconds: int = 3600,
) -> ConcurrencyStore:
    """Get a concurrency store implementation.

    Args:
        backend: Backend type ("memory" or "redis")
        redis_url: Redis connection URL (required for redis backend)
        default_ttl_seconds: Default TTL for slots

    Returns:
        ConcurrencyStore implementation

    Raises:
        ValueError: If redis backend selected but redis_url not provided
        ImportError: If redis backend selected but redis package not installed
    """
    if backend == "memory":
        return InMemoryConcurrencyStore(default_ttl_seconds=default_ttl_seconds)

    if backend == "redis":
        if not _redis_available:
            raise ImportError(
                "redis package is required for redis backend. "
                "Install with: pip install redis>=5.0.0"
            )
        if not redis_url:
            raise ValueError(
                "redis_url is required when limits_backend=redis"
            )
        return _RedisConcurrencyStore(redis_url=redis_url, default_ttl_seconds=default_ttl_seconds)

    raise ValueError(f"Unknown limits_backend: {backend}. Use 'memory' or 'redis'")


def get_stores_from_settings(settings: Settings) -> tuple[RateLimitStore, ConcurrencyStore]:
    """Get rate limit and concurrency stores from settings.

    This is a convenience function for app startup.

    Args:
        settings: Settings instance

    Returns:
        Tuple of (rate_limit_store, concurrency_store)
    """
    rate_store = get_rate_limit_store(
        settings.limits_backend,
        redis_url=settings.redis_url,
    )
    conc_store = get_concurrency_store(
        settings.limits_backend,
        redis_url=settings.redis_url,
    )
    return rate_store, conc_store


# Redis implementations (lazy-loaded to make redis optional)
class _RedisRateLimitStore(RateLimitStore):
    """Redis-based rate limiting using atomic INCR + EXPIRE.

    This implementation is atomic and works across multiple workers.
    Keys are prefixed with "omni:ratelimit:" to avoid collisions.
    """

    def __init__(self, redis_url: str, window_seconds: int = 60):
        """Initialize Redis rate limit store.

        Args:
            redis_url: Redis connection URL
            window_seconds: Window duration for rate limiting
        """
        self._redis_url = redis_url
        self._window_seconds = window_seconds
        self._prefix = "omni:ratelimit:"

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client (lazy initialization)."""
        if not hasattr(self, "_client"):
            self._client = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def hit(self, key: str, limit: int, window_s: int | None = None) -> RateLimitResult:
        """Record a request using Redis INCR + EXPIRE."""
        ws = window_s or self._window_seconds
        client = await self._get_client()

        # Create a time-bucketed key for fixed-window limiting
        now_s = await client.time()
        now_seconds = float(now_s[0]) + (float(now_s[1]) / 1_000_000)
        bucket = int(now_seconds // ws)
        redis_key = f"{self._prefix}{key}:{bucket}"

        # Calculate reset time (end of current bucket)
        reset_epoch_s = int((bucket + 1) * ws)

        # Use pipeline for atomic increment + expire
        pipe = client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, ws, nx=True)
        results = await pipe.execute()

        current_count = results[0]

        if current_count > limit:
            allowed = False
            remaining = 0
        else:
            allowed = True
            remaining = limit - current_count

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_epoch_s=reset_epoch_s,
        )


class _RedisConcurrencyStore(ConcurrencyStore):
    """Redis-based concurrency control with atomic slot reservation.

    Uses Lua scripts for atomicity across multiple workers:
    - acquire: Atomically counts active slots, cleans expired, and acquires
    - release: Verifies token ownership before releasing

    Uses ZSET for bounded cleanup:
    - Members: tokens (unique slot identifiers)
    - Scores: expiry timestamp (milliseconds since epoch)

    Keys are prefixed with "omni:conc:" to avoid collisions.
    """

    # Lua script for atomic acquire using ZSET:
    # 1. Get current Redis time
    # 2. Remove expired entries (ZREMRANGEBYSCORE)
    # 3. Count remaining active slots (ZCARD)
    # 4. If under limit, add new slot with expiry score
    # 5. Set key TTL based on slot expiry
    _ACQUIRE_SCRIPT = """
    local prefix = KEYS[1]
    local key = ARGV[1]
    local limit = tonumber(ARGV[2])
    local ttl_ms = tonumber(ARGV[3])
    local token = ARGV[4]
    local zset_key = prefix .. key

    -- Get current Redis time in milliseconds
    local time = redis.call('TIME')
    local now_ms = (tonumber(time[1]) * 1000) + (tonumber(time[2]) / 1000)

    -- Clean expired entries (score < now_ms)
    local removed = redis.call('ZREMRANGEBYSCORE', zset_key, '-inf', now_ms)
    
    -- Count active slots (exclude our own token if already present)
    local active_count = redis.call('ZCARD', zset_key)

    -- Check if we can acquire
    if active_count >= limit then
        return {0, active_count}  -- Failed, at limit
    end

    -- Acquire new slot: add token with expiry score
    local expiry_score = now_ms + ttl_ms
    redis.call('ZADD', zset_key, expiry_score, token)
    
    -- Set/refresh key TTL to slightly longer than slot TTL
    -- This ensures key is cleaned up when all slots expire
    redis.call('PEXPIRE', zset_key, ttl_ms + 60000)  -- +1 minute margin
    
    return {1, active_count + 1}  -- Success, new count
    """

    # Lua script for atomic release with token verification:
    # Only removes if the token exists in the ZSET
    _RELEASE_SCRIPT = """
    local prefix = KEYS[1]
    local key = ARGV[1]
    local token = ARGV[2]
    local zset_key = prefix .. key

    -- Check if token exists and remove it
    local removed = redis.call('ZREM', zset_key, token)
    
    if removed > 0 then
        return 1  -- Success
    end
    return 0  -- Not found
    """

    def __init__(self, redis_url: str, default_ttl_seconds: int = 3600):
        """Initialize Redis concurrency store.

        Args:
            redis_url: Redis connection URL
            default_ttl_seconds: Default TTL for acquired slots
        """
        self._redis_url = redis_url
        self._default_ttl = default_ttl_seconds
        self._prefix = "omni:conc:"
        self._acquire_sha: str | None = None
        self._release_sha: str | None = None

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client (lazy initialization)."""
        if not hasattr(self, "_client"):
            self._client = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Register Lua scripts once
            self._acquire_sha = await self._client.script_load(self._ACQUIRE_SCRIPT)
            self._release_sha = await self._client.script_load(self._RELEASE_SCRIPT)
        return self._client

    async def acquire(self, key: str, limit: int, ttl_s: int | None = None) -> tuple[bool, str | None]:
        """Atomically acquire a concurrent slot.

        Uses Lua script to ensure atomicity across multiple workers:
        - Counts active slots (removing expired via ZREMRANGEBYSCORE)
        - Only acquires if under limit
        - Returns unique token for release verification

        Args:
            key: Unique identifier (e.g., "stream:user:123")
            limit: Maximum concurrent slots
            ttl_s: TTL for the slot in seconds (auto-releases if worker dies)

        Returns:
            Tuple of (success, token). Token must be passed to release().
        """
        import secrets

        ttl = ttl_s or self._default_ttl
        ttl_ms = int(ttl * 1000)  # Convert to milliseconds
        client = await self._get_client()
        token = secrets.token_hex(8)

        try:
            # Execute atomic Lua script
            result = await client.evalsha(
                self._acquire_sha,
                1,  # number of keys
                self._prefix,
                key,
                str(limit),
                str(ttl_ms),
                token,
            )
            success = bool(result[0])
            if success:
                return (True, token)
            return (False, None)
        except redis.exceptions.NoScriptError:
            # Script was flushed, reload it
            self._acquire_sha = None
            self._release_sha = None
            client = await self._get_client()
            # Retry
            result = await client.evalsha(
                self._acquire_sha,
                1,
                self._prefix,
                key,
                str(limit),
                str(ttl_ms),
                token,
            )
            success = bool(result[0])
            if success:
                return (True, token)
            return (False, None)

    async def release(self, key: str, token: str) -> bool:
        """Release a concurrent slot using token verification.

        Only releases if the token exists in the ZSET, preventing
        one worker from releasing another's slot.

        Args:
            key: The same key used in acquire()
            token: The token returned from acquire()

        Returns:
            True if released, False if token didn't match.
        """
        client = await self._get_client()

        try:
            result = await client.evalsha(
                self._release_sha,
                1,
                self._prefix,
                key,
                token,
            )
            return bool(result)
        except redis.exceptions.NoScriptError:
            # Script was flushed, reload it
            self._acquire_sha = None
            self._release_sha = None
            client = await self._get_client()
            result = await client.evalsha(
                self._release_sha,
                1,
                self._prefix,
                key,
                token,
            )
            return bool(result)

    async def get_active_count(self, key: str) -> int:
        """Get the number of active slots for a key (for debugging/monitoring).

        Args:
            key: The concurrency key to check

        Returns:
            Number of active slots (may include expired if not cleaned)
        """
        client = await self._get_client()
        zset_key = f"{self._prefix}{key}"
        
        # Get current time
        time_result = await client.time()
        now_ms = (float(time_result[0]) * 1000) + (float(time_result[1]) / 1000)
        
        # Remove expired and count remaining
        await client.zremrangebyscore(zset_key, "-inf", now_ms)
        return await client.zcard(zset_key)
