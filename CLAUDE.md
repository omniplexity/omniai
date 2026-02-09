# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OmniAI is a privacy-first AI chat platform with a **static frontend (GitHub Pages)** and **local backend (FastAPI)**. The architecture enforces security through invite-only access, HttpOnly cookies, CSRF protection, and server-side validation of all client requests.

**Critical Security Principle:** The frontend is untrusted. All security policy, tool authorization, rate limits, and provider validation are enforced server-side. Frontend settings are UI preferences that the backend validates before execution.

## Repository Structure

```
OmniAI/
├── backend/              # Canonical FastAPI backend (Python 3.11+)
│   ├── api/             # API routers (/api/* legacy, /v1/* canonical)
│   ├── auth/            # Invite-only auth, sessions, CSRF
│   ├── config/          # Settings via Pydantic (get_settings())
│   ├── core/            # Middleware, exceptions, logging, startup_checks
│   ├── db/              # SQLAlchemy models, Alembic migrations
│   ├── providers/       # LLM provider abstraction (LM Studio, Ollama, OpenAI-compatible)
│   ├── services/        # Business logic
│   ├── agents/          # Agent implementations
│   ├── tests/           # 40+ pytest tests with security/csrf markers
│   └── main.py          # FastAPI app entrypoint
├── deploy/              # Docker Compose + Kubernetes configs
├── contracts/           # OpenAPI spec, JSON schemas
└── docs/                # Architecture, security, deployment
```

## Development Commands

### Backend Setup

```powershell
# Install dependencies
python -m pip install -r backend\requirements.txt

# Run database migrations
python backend\scripts\run_migrations.py upgrade

# Start development server
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Health check
curl http://127.0.0.1:8000/health
```

### Testing

```powershell
# Run all tests (from backend/ directory)
cd backend
python -m pytest

# Run security tests only
python -m pytest -m "security or csrf" -v

# Run with coverage
python -m pytest --cov=. --cov-report=term -v

# Run single test file
python -m pytest tests/test_chat_api.py -v

# Run specific test
python -m pytest tests/test_chat_api.py::test_chat_stream_requires_auth -v
```

**Important:** Always set `ENVIRONMENT=test` when running pytest. The TestClient requires this for deterministic behavior.

### Docker Deployment

```powershell
# Start full stack (postgres + redis + backend)
cd deploy
docker compose up -d

# With ngrok tunnel for external access
docker compose --profile tunnel up -d

# View logs
docker compose logs -f backend

# Restart backend after code changes
docker compose up -d --build backend

# Stop all services
docker compose down
```

### Database Management

```powershell
# Run migrations
python backend\scripts\run_migrations.py upgrade

# Check current migration version
python backend\scripts\run_migrations.py current

# View migration history
python backend\scripts\run_migrations.py history

# Rollback one migration
python backend\scripts\run_migrations.py downgrade
```

### Code Quality

```powershell
# Format and lint with ruff
cd backend
ruff format .
ruff check .

# Security audit
bandit -r backend/
pip-audit -r requirements.txt
```

## Architecture Patterns

### Agent-Based Architecture

OmniAI uses an agent pattern to decompose responsibilities:

- **Chat Agent**: Manages conversation flow, streaming responses (SSE), message history
- **Provider Agent**: Abstracts LLM providers (LM Studio, Ollama, OpenAI-compatible) via `ProviderRegistry`
- **Authentication Agent**: Invite-only registration, session cookies, CSRF validation
- **Conversation Agent**: Persists conversations/messages with branching support
- **Memory Agent**: Long-term storage for user-saved content
- **Knowledge Agent**: RAG integration with vector search
- **Voice Agent**: Audio transcription and TTS via `/api/voice/*`
- **Tool Agent**: Mediates access to plugins (web browsing, code execution, file search)
- **Admin Agent**: User management, audit logs, invite codes

See `AGENTS.md` for detailed agent responsibilities and data flows.

### Security Layers (Defense-in-Depth)

**Middleware order in `main.py` matters** (last added = first executed):

1. **TrustedHostMiddleware** - Validates Host header against `ALLOWED_HOSTS` (includes tunnel domains)
2. **ForwardedHeadersMiddleware** - Validates `X-Forwarded-*` headers from trusted proxies only
3. **RequestSizeLimitMiddleware** - Rejects oversized requests early (10MB default, 25MB for voice)
4. **RateLimitMiddleware** - Per-IP + per-user rate limiting
5. **HotPathRateLimitMiddleware** - Stricter limits for auth/chat endpoints
6. **RequestContextMiddleware** - Injects request ID, logs requests
7. **SecurityHeadersMiddleware** - Sets HSTS, X-Content-Type-Options, Referrer-Policy, CSP
8. **ChatCSRFMiddleware** - Validates CSRF tokens on state-changing requests + Origin headers on SSE streams
9. **CORSMiddleware** - Allowlist-based CORS (GitHub Pages frontend only)

### Configuration Architecture

Settings are loaded via Pydantic from `.env` files. **Never commit secrets.**

**Critical Settings:**

- `ENVIRONMENT`: Controls strict validation (`production|staging|development|test`)
- `CORS_ORIGINS`: Frontend origins only (e.g., `https://omniplexity.github.io`)
- `ALLOWED_HOSTS`: API hostnames including tunnel domains (e.g., `localhost,127.0.0.1,*.ngrok-free.dev`)
- `COOKIE_SAMESITE`: Must be `none` for cross-site (GitHub Pages → tunnel), `lax` for same-site
- `COOKIE_SECURE`: Must be `true` in production
- `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`

**Startup Validation:** `backend/core/startup_checks.py` enforces production security requirements. The backend refuses to start if validation fails.

### API Structure

**Canonical v1 API** (`/v1/*` - preferred):
- `GET /v1/meta` - API metadata & auth status
- `GET /v1/conversations` - List conversations
- `POST /v1/conversations` - Create conversation
- `POST /v1/chat` - Send message (SSE streaming)
- `GET /v1/providers` - List LLM providers

**Legacy API** (`/api/*` - deprecated):
- Disabled by default in production via `LEGACY_API_ENABLED=false`
- Use v1 API for all new development

### SSE Streaming Security

Server-Sent Events endpoints (`/v1/chat/stream`) validate Origin headers via `ChatCSRFMiddleware`:

- Only requests from allowed `CORS_ORIGINS` can establish streams
- Even with valid session cookies, disallowed origins are rejected (403 Forbidden)
- Prevents CSRF attacks on streaming endpoints
- Defense-in-depth: SSE requires authentication + valid origin

## Common Development Patterns

### Adding a New API Endpoint

1. Create router in `backend/api/your_feature.py`
2. Define route with proper dependencies (e.g., `get_current_user`)
3. Add security markers to tests: `@pytest.mark.security` or `@pytest.mark.csrf`
4. Register router in `backend/main.py`
5. Update `backend/api/__init__.py` exports

### Adding Database Models

1. Create model in `backend/db/models.py` using SQLAlchemy 2.0 style
2. Generate migration: `alembic revision --autogenerate -m "Add your_table"`
3. Review migration in `backend/migrations/versions/`
4. Run migration: `python backend/scripts/run_migrations.py upgrade`

### Adding a New Provider

1. Implement provider interface in `backend/providers/your_provider.py`:
   - `list_models()` - Return available models
   - `chat_stream(request)` - Yield SSE chunks
   - `chat_once(request)` - Return single response
   - `healthcheck()` - Return provider status
   - `capabilities()` - Describe features (vision, tools, etc.)
2. Register in `backend/providers/__init__.py`
3. Add settings in `backend/config/settings.py`
4. Add tests in `backend/tests/test_your_provider.py`

### Adding Middleware

Add in `backend/main.py` in the correct order (see Security Layers above). Remember: **last added = first executed**.

## Testing Patterns

### Test Markers

```python
@pytest.mark.security      # Security feature tests
@pytest.mark.csrf         # CSRF and origin validation tests
@pytest.mark.slow         # Slow-running tests
@pytest.mark.integration  # Integration tests (requires Redis)
```

### Test Environment Setup

```python
# In conftest.py or test file
@pytest.fixture
def test_settings():
    return Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        secret_key="test-secret-key",
        cors_origins="http://localhost:3000",
    )
```

### Testing Authenticated Endpoints

```python
def test_requires_auth(test_client):
    response = test_client.get("/v1/conversations")
    assert response.status_code == 401

def test_with_auth(test_client, auth_headers):
    response = test_client.get("/v1/conversations", headers=auth_headers)
    assert response.status_code == 200
```

## Environment Constraints

### Cookie SameSite Decision Matrix

| Deployment | Frontend | Backend | `COOKIE_SAMESITE` | Why |
|-----------|----------|---------|-------------------|-----|
| **Cross-site (default)** | `omniplexity.github.io` | `*.ngrok-free.dev` | `none` | Different eTLD+1 → requires SameSite=None |
| **Same-site (custom domain)** | `chat.yourdomain.com` | `api.yourdomain.com` | `lax` | Same eTLD+1 → Lax works for navigation + XHR |
| **Local development** | `localhost:3000` | `localhost:8000` | `lax` | Same-site by definition |

**Symptom of wrong setting:** Login succeeds but subsequent API calls are unauthenticated (browser doesn't send cookie).

### CORS vs ALLOWED_HOSTS

| Setting | Purpose | Values |
|---------|---------|--------|
| `CORS_ORIGINS` | Browser CORS - frontend origins only | `https://omniplexity.github.io` (prod), `http://localhost:3000` (dev) |
| `ALLOWED_HOSTS` | Host header validation - API hostnames | `localhost,127.0.0.1,my-app.ngrok-free.dev` |

**Never add tunnel domains to CORS_ORIGINS.** The browser Origin is always the frontend (GitHub Pages), not the tunnel.

## Git Workflow

### Commit Message Format

Follow conventional commits style based on `git log`:

```
type: Brief description (70 chars max)

Longer explanation of the change if needed.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `security`, `deploy`, `chore`

### Branch Protection

- **main**: Production-ready code
- Feature branches: `feature/description`
- Bugfix branches: `fix/description`
- Security branches: `security/description`

## Production Deployment Checklist

Before deploying to production:

1. Set `ENVIRONMENT=production` in `.env`
2. Generate secure `SECRET_KEY` (64+ chars)
3. Set `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none`
4. Configure `CORS_ORIGINS` with exact frontend domains (HTTPS only)
5. Configure `ALLOWED_HOSTS` with API hostnames + tunnel domain
6. Disable `BOOTSTRAP_ADMIN_ENABLED=false` after first admin creation
7. Run security tests: `pytest -m "security or csrf" -v`
8. Verify startup checks pass (backend will refuse to start if not)

## Key Files Reference

- `backend/main.py` - FastAPI app + middleware stack
- `backend/config/settings.py` - All environment configuration
- `backend/core/startup_checks.py` - Production security validation
- `backend/core/middleware.py` - Custom middleware implementations
- `backend/auth/bootstrap.py` - Initial admin account creation
- `backend/db/models.py` - SQLAlchemy database models
- `deploy/docker-compose.yml` - Full stack deployment
- `DEPLOY.md` - Complete deployment guide
- `AGENTS.md` - Agent architecture and responsibilities
- `docs/SECURITY.md` - Security architecture details

## Additional Resources

- API Documentation (dev only): `http://localhost:8000/docs`
- Health Check: `GET /health`
- Provider Health: `GET /v1/providers` (requires auth)
- Bootstrap Admin: Set `BOOTSTRAP_ADMIN_ENABLED=true` for first-time setup
