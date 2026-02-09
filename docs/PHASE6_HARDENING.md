# Phase 6 Hardening Blueprint

This document describes the security hardening changes implemented in Phase 6.

## 6.1 Frontend CSP Enforcement

**Location**: `omniplexity.github.io` repository (frontend)

Add the following CSP meta tag to `index.html` inside `<head>`, above any scripts:

### Development CSP (for ngrok/cloudflared)
```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  img-src 'self' data: blob:;
  style-src 'self' 'unsafe-inline';
  script-src 'self';
  connect-src 'self' https:;
">
```

### Production CSP (once stable API domain is available)
```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  img-src 'self' data: blob:;
  style-src 'self' 'unsafe-inline';
  script-src 'self';
  connect-src 'self' https://chat.yourdomain.com;
">
```

**Note**: The frontend is in a separate repository (`omniplexity.github.io`). You must apply CSP changes there.

---

## 6.2 Pluggable Rate Limit + Concurrency Store

### Architecture

```
backend/core/limits/
├── __init__.py       # Protocols: RateLimitStore, ConcurrencyStore
├── memory.py         # InMemoryRateLimitStore, InMemoryConcurrencyStore
├── factory.py        # get_rate_limit_store(), get_concurrency_store()
└── redis.py          # Optional Redis implementations
```

### Protocols

```python
class RateLimitStore(Protocol):
    async def hit(self, key: str, limit: int, window_s: int) -> RateLimitResult: ...

class ConcurrencyStore(Protocol):
    async def acquire(self, key: str, limit: int, ttl_s: int) -> bool: ...
    async def release(self, key: str) -> None: ...
```

### Settings

New environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LIMITS_BACKEND` | `memory` | Backend: `memory` or `redis` |
| `REDIS_URL` | `` | Redis connection URL (required for `redis` backend) |

### Usage in SSE Handlers

```python
# Acquire slot at start
acquired = await request.app.state.concurrency_store.acquire(
    key=f"stream:{user_id}",
    limit=settings.sse_max_concurrent_per_user,
    ttl_s=settings.sse_max_duration_seconds + 60
)
if not acquired:
    return JSONResponse(status_code=429, content={"detail": "Too many streams"})

try:
    async for event in stream_events():
        yield event
finally:
    await request.app.state.concurrency_store.release(f"stream:{user_id}")
```

### Switching to Redis

1. Set `LIMITS_BACKEND=redis`
2. Set `REDIS_URL=redis://localhost:6379/0`
3. Restart the application

---

## 6.3 Lockfile Strategy (uv)

### Files Changed

| File | Purpose |
|------|---------|
| `backend/pyproject.toml` | Project metadata and dependencies |
| `backend/uv.lock` | Locked dependency versions (generated) |

### Generating uv.lock

```bash
cd backend
uv lock
```

### CI Enforcement

The CI workflow includes a `lockfile` job that:
1. Verifies `uv.lock` exists
2. Runs `uv lock --check` to ensure lockfile matches `pyproject.toml`
3. Runs `uv sync --frozen` to verify reproducible installs
4. Runs `uv pip audit` for vulnerability scanning

### Local Development

```bash
# Install uv if not already installed
pip install uv

# Sync dependencies from lockfile
uv sync

# Add a new dependency
uv add package-name

# This automatically updates uv.lock
```

---

## Summary of Changes

### New Files
- `backend/core/limits/__init__.py` - Store protocols
- `backend/core/limits/memory.py` - In-memory implementations
- `backend/core/limits/factory.py` - Factory functions with Redis backends
- `backend/pyproject.toml` - Project configuration

### Modified Files
- `backend/config/settings.py` - Added `LIMITS_BACKEND` and `REDIS_URL`
- `backend/main.py` - Initialize stores in lifespan
- `.github/workflows/backend-ci.yml` - Added lockfile verification job

### Environment Variables
```bash
# Optional: Use Redis for distributed rate limiting
LIMITS_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
```

---

## Migration Steps

### 1. Generate uv.lock
```bash
cd backend
uv lock
```

### 2. Test the application
```bash
uv sync
uv run uvicorn main:app --reload
```

### 3. Apply frontend CSP
Add the CSP meta tag to `omniplexity.github.io/index.html`

### 4. (Optional) Enable Redis for multi-worker
```bash
export LIMITS_BACKEND=redis
export REDIS_URL=redis://localhost:6379/0
```

---

## Rollback Plan

If issues arise:
1. `LIMITS_BACKEND=memory` reverts to in-memory (current behavior)
2. Remove CSP meta tag from frontend to restore pre-CSP state
3. Revert `uv.lock` if dependency issues occur
