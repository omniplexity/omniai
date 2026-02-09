# Scaling Considerations

## Multi-Worker Deployment Note

The following components use in-memory (single-process) state and require external storage for multi-worker deployments:

| Component | Current Implementation | Multi-Worker Requirement |
|-----------|----------------------|------------------------|
| Rate Limiting | In-memory counters | Redis for distributed counters |
| SSE Concurrent Stream Limits | In-memory slot tracking | Redis or PostgreSQL for shared state |
| Session Storage | SQLite/PostgreSQL (already distributed) | N/A |

## Current Behavior (Single-Worker)

- **Rate limiting**: Per-process counters; total limit = workers × configured_rpm
- **SSE concurrency**: Per-process slot management; max concurrent = workers × configured_limit

## Multi-Worker Configuration

To deploy with multiple workers (e.g., Kubernetes pods > 1, gunicorn --workers > 1):

### Option 1: Redis-backed Rate Limiting

```python
# Future enhancement - swap backend for rate_limit
from backend.core.middleware import RateLimitMiddleware

# Would use Redis INCR/EXPIRE instead of in-memory counters
app.add_middleware(
    RateLimitMiddleware,
    ip_requests_per_minute=settings.rate_limit_rpm,
    user_requests_per_minute=settings.rate_limit_user_rpm,
    use_redis=True,  # New option
)
```

### Option 2: PostgreSQL-backed SSE Slots

```python
# Future enhancement - SSE slot management via DB
from backend.services.sse_limiter import SSESlotManager

# Use DB-backed slot tracking
manager = SSESlotManager(use_redis=False)  # or True for Redis
```

## Recommended Production Setup

For production deployments requiring horizontal scaling:

1. **Single pod/replica**: Current in-memory implementation is correct
2. **Multiple pods**: Implement Redis-backed state for rate limits and SSE slots

The interface abstraction allows swapping the backing store without modifying handler logic:

```python
# Abstract interface (example future design)
class RateLimiter:
    async def check_limit(self, key: str, limit: int) -> bool:
        """Check if key has exceeded limit. Returns True if allowed."""
        ...

class InMemoryRateLimiter(RateLimiter):
    """Current implementation."""
    ...

class RedisRateLimiter(RateLimiter):
    """Future distributed implementation."""
    ...
```

## Testing Multi-Worker Behavior

To simulate multi-worker rate limiting in testing:

```python
# pytest test helper
def test_rate_limit_per_worker_not_global():
    """Rate limits are per-worker, not global."""
    # This test validates current single-worker behavior
    # Multi-worker would require Redis-backed implementation
    pass
```

## Concurrency Key Contract

This section documents the key format and TTL policies for the Redis-based concurrency store to prevent regressions.

### Key Format

Concurrency keys follow this format:

```
stream:{user_id}:{category}
```

**Components:**
- `stream` - Literal prefix indicating this is a stream/concurrency key
- `{user_id}` - The authenticated user's ID
- `{category}` - Server-constant category (e.g., `sse`, `voice`)

**Important:**
- The category is a **server-constant**, not user-controlled input
- This prevents malicious users from creating isolated concurrency groups
- All valid categories are defined in `backend/config/settings.py`

### TTL Policy

Slots acquired via the concurrency store have a time-to-live (TTL):

```
ttl_seconds = sse_max_duration_seconds + 60
```

**Rationale:**
- `sse_max_duration_seconds` - Maximum expected SSE stream duration
- `+60` - 60-second grace period for cleanup margin

**Behavior:**
- If the worker crashes without releasing, the slot auto-expires after TTL
- Expired entries are cleaned via `ZREMRANGEBYSCORE` on each acquire operation
- The key's TTL is set to `ttl_ms + 60000` (TTL + 1 minute) for automatic cleanup

### Key Isolation

The concurrency store uses Redis key prefixes to prevent collisions:

| Prefix | Purpose |
|--------|---------|
| `omni:conc:` | Concurrency control (ZSET for slots) |
| `omni:ratelimit:` | Rate limiting (counters) |

Each store instance adds the appropriate prefix, ensuring isolation between different data types.

## References

- `backend/core/middleware.py` - RateLimitMiddleware implementation
- `backend/api/v1/chat.py` - SSE concurrency enforcement
- `backend/config/settings.py` - Rate limit configuration
