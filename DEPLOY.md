# OmniAI Deployment Guide

## Configuration Reference

### CORS_ORIGINS vs ALLOWED_HOSTS

These two settings serve different purposes and are often confused:

| Setting | Purpose | Values |
|---------|---------|--------|
| `CORS_ORIGINS` | Browser CORS - frontend origins only | `https://omniplexity.github.io` (prod), `http://localhost:3000` (dev) |
| `ALLOWED_HOSTS` | Host header validation - API hostnames | `localhost,127.0.0.1,my-app.ngrok-free.dev` |

**CORS_ORIGINS**: The browser Origin header must match one of these values. This is the frontend's domain (GitHub Pages). Never add tunnel domains (ngrok, cloudflare) here - the browser Origin is always the frontend, not the tunnel.

**ALLOWED_HOSTS**: The Host header in HTTP requests must match one of these values. This includes tunnel domains when using ngrok or cloudflared, plus localhost for local development.

### Environment Modes

| Mode | Purpose | TestServer Required |
|------|---------|-------------------|
| `development` | Local development | No |
| `test` | pytest runs | **Yes** - TestClient requires this |
| `staging` | Pre-production testing | No |
| `production` | Live deployment | No |

**Important**: When running pytest, always set `ENVIRONMENT=test`. The TestClient requires this for deterministic behavior and test isolation.

### OpenAPI Docs

For security, OpenAPI docs (`/docs`, `/redoc`) are automatically disabled in production when `ENVIRONMENT=production`. Use `development` or `staging` if you need access to these endpoints.

---

## Overview

This guide covers deploying OmniAI with:
- **Frontend**: GitHub Pages (static hosting) at `omniplexity.github.io`
- **Backend**: Docker Desktop with ngrok tunnel

---

## Prerequisites

- Docker Desktop installed and running
- ngrok account with authtoken
- GitHub access to both repositories

---

## Step 1: Deploy Frontend to GitHub Pages

The frontend is a static SPA (vanilla JS, no build step). It will be live at:
**https://omniplexity.github.io**

### Frontend Structure

```
omniplexity.github.io/      # Separate repo: omniplexity/omniplexity.github.io
  index.html                # Auth gate
  chat.html                 # Chat UI
  login.html                # Login page
  runtime-config.json       # Backend URL configuration
  assets/css/style.css      # Styles
  js/
    config.js               # Runtime config loader
    api.js                  # Fetch wrapper + SSE helper
    auth.js                 # Session bootstrap, login/logout
    app.js                  # Chat orchestration
    sse.js                  # Server-Sent Events streaming
    state.js                # Client state management
    ui.js                   # DOM render helpers
```

### To update the frontend:

```bash
cd omniplexity.github.io    # Separate repo, not inside OmniAI
# Edit files as needed (no build step required)
git add -A
git commit -m "Update: <description of changes>"
git push origin main
```

GitHub Pages will automatically update within a few minutes.

### CSP Configuration

The frontend includes a CSP meta tag in `index.html` for defense-in-depth:

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
  font-src 'self' https://fonts.gstatic.com;
  prefetch-src 'self' https://fonts.googleapis.com;
">
```

The backend enforces additional CSP via `Content-Security-Policy` response headers.

---

## Step 2: Configure Backend Environment

### 2.1 Create the .env file

Navigate to `OmniAI-backend/backend/` and create a `.env` file:

```bash
cd OmniAI-backend/backend
copy .env.example .env
```

### 2.2 Edit the .env file

Open `.env` in your editor and set these required values:

```env
# =============================================================================
# SERVER
# =============================================================================
ENVIRONMENT=development
# SECURITY: Bind to 127.0.0.1 for localhost-only access.
# In Docker containers, use 0.0.0.0. Docker Compose publishes ports as
# 127.0.0.1:8000:8000 to prevent LAN exposure.
HOST=127.0.0.1
PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# =============================================================================
# SECURITY
# =============================================================================
# Generate a secure random key:
# python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=your-secure-secret-key-here

# CORS - Must include ONLY your GitHub Pages domain
# NOTE: Do NOT add tunnel domains (ngrok, cloudflare) here. The browser
# Origin is always the frontend domain (GitHub Pages). Tunnel domains handle
# TLS termination but don't participate in CORS.
CORS_ORIGINS=https://omniplexity.github.io

# Rate limiting
RATE_LIMIT_RPM=200

# Max request body size
MAX_REQUEST_BYTES=10485760
VOICE_MAX_REQUEST_BYTES=26214400

# =============================================================================
# AUTHENTICATION
# =============================================================================
SESSION_COOKIE_NAME=omni_session
SESSION_TTL_SECONDS=604800
COOKIE_SECURE=true
COOKIE_SAMESITE=none
COOKIE_DOMAIN=
```

> **Cookie SameSite Decision Matrix:**
>
> | Deployment Architecture | Frontend | Backend | `COOKIE_SAMESITE` | Why |
> |------------------------|----------|---------|-------------------|-----|
> | **Cross-site** (default) | `omniplexity.github.io` | `*.ngrok-free.dev` / `*.trycloudflare.com` | `none` | Different eTLD+1 → browser blocks cookies unless SameSite=None |
> | **Same-site** (custom domain) | `chat.yourdomain.com` | `api.yourdomain.com` | `lax` | Same eTLD+1 → Lax cookies work for top-level navigation + XHR |
> | **Local development** | `localhost:3000` | `localhost:8000` | `lax` | Same-site by definition |
>
> **Symptom of wrong setting:** Login succeeds (POST sets cookie) but subsequent API calls are unauthenticated (browser doesn't send the cookie back).
>
> `startup_checks.py` enforces `COOKIE_SAMESITE=none` in production because the default architecture is cross-site (GitHub Pages → tunnel).
>
> **CORS must allow credentials:** The backend sets `allow_credentials=True` in CORS middleware (`main.py`). This is required for browsers to include cookies in cross-origin requests. Without it, `SameSite=None` + `Secure=true` alone won't work.

```env

CSRF_HEADER_NAME=X-CSRF-Token
CSRF_COOKIE_NAME=omni_csrf
INVITE_REQUIRED=true

# Bootstrap admin (enable for first-time setup)
BOOTSTRAP_ADMIN_ENABLED=true
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=your-secure-admin-password

# =============================================================================
# DATABASE
# =============================================================================
# Docker Compose uses PostgreSQL automatically
DATABASE_URL=sqlite:///./data/omniai.db
DATABASE_URL_POSTGRES=postgresql://omniai:omniai_secure_2024@postgres:5432/omniai

# =============================================================================
# MEDIA
# =============================================================================
MEDIA_STORAGE_PATH=./data/uploads

# =============================================================================
# PROVIDERS
# =============================================================================
PROVIDER_DEFAULT=lmstudio
PROVIDERS_ENABLED=lmstudio
PROVIDER_TIMEOUT_SECONDS=60
PROVIDER_MAX_RETRIES=3
SSE_PING_INTERVAL_SECONDS=30
READINESS_CHECK_PROVIDERS=false

# LM Studio running on host machine
LMSTUDIO_BASE_URL=http://host.docker.internal:1234
OLLAMA_BASE_URL=http://127.0.0.1:11434

# =============================================================================
# EMBEDDINGS
# =============================================================================
EMBEDDINGS_ENABLED=false
EMBEDDINGS_MODEL=
EMBEDDINGS_PROVIDER_PREFERENCE=openai_compat,ollama,lmstudio

# =============================================================================
# VOICE
# =============================================================================
VOICE_PROVIDER_PREFERENCE=whisper,openai_compat
VOICE_WHISPER_MODEL=base
VOICE_WHISPER_DEVICE=cpu
VOICE_OPENAI_AUDIO_MODEL=whisper-1

# =============================================================================
# REDIS
# =============================================================================
REDIS_URL=redis://redis:6379/0

# =============================================================================
# NGROK (for docker-compose.yml)
# =============================================================================
NGROK_DOMAIN=rossie-chargeful-plentifully.ngrok-free.dev
NGROK_AUTHTOKEN=your-ngrok-authtoken-here
```

**Important:** Replace these placeholders:
- `your-secure-secret-key-here` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- `your-secure-admin-password` - Your chosen admin password
- `your-ngrok-authtoken-here` - Your ngrok authtoken from https://dashboard.ngrok.com

---

## Step 3: Start the Backend with Docker Desktop

### 3.1 Open Docker Desktop
Ensure Docker Desktop is running.

### 3.2 Start the services

```bash
cd OmniAI-backend

# Start backend + database + ngrok tunnel
docker compose --profile tunnel up -d
```

This will start:
- PostgreSQL database
- Redis cache
- FastAPI backend (port 8000)
- ngrok tunnel (public HTTPS URL)

### 3.3 Check service status

```bash
# View all running containers
docker compose ps

# View logs
docker compose logs -f

# Check health
curl http://localhost:8000/health
```

### 3.4 Verify ngrok tunnel

Once running, your backend will be accessible at:
**https://rossie-chargeful-plentifully.ngrok-free.dev**

You can verify by visiting:
```
https://rossie-chargeful-plentifully.ngrok-free.dev/health
```

---

## Step 4: First-Time Setup

### 4.1 Access the frontend

Open your browser to:
**https://omniplexity.github.io**

### 4.2 Create the admin account

1. Click "Sign Up" tab
2. Enter the bootstrap admin credentials you set in `.env`:
   - Email: `admin@example.com`
   - Username: `admin`
   - Password: (your bootstrap password)
   - Invite code: `admin` (or any value if invite_required is false)

3. After login, disable bootstrap mode in `.env`:
   ```env
   BOOTSTRAP_ADMIN_ENABLED=false
   ```
4. Restart the backend: `docker compose restart backend`

---

## Step 5: Verify Full Deployment

### Check these URLs:

| Service | URL | Expected Result |
|---------|-----|-----------------|
| Frontend | https://omniplexity.github.io | Login page loads |
| Backend Health | https://rossie-chargeful-plentifully.ngrok-free.dev/health | `{"status":"ok"}` |
| Backend API | https://rossie-chargeful-plentifully.ngrok-free.dev/api/auth/check | `{"authenticated":false}` |

### Test login:

1. Go to https://omniplexity.github.io
2. Enter your admin username and password
3. You should be logged in successfully

---

## Useful Commands

```bash
# Start all services with ngrok
cd OmniAI-backend
docker compose --profile tunnel up -d

# Stop all services
docker compose down

# Restart backend only
docker compose restart backend

# View logs
docker compose logs -f backend
docker compose logs -f ngrok

# Update backend after code changes
git pull
docker compose up -d --build backend

# Shell into backend container
docker compose exec backend sh

# Database migrations (inside container)
docker compose exec backend alembic upgrade head
```

---

## Security Testing

OmniAI's security architecture uses **defense-in-depth** with multiple layers:

| Layer | Component | Purpose |
|-------|-----------|---------|
| Startup validation | `startup_checks.py` | Validates production config before allowing startup |
| Origin validation | `ChatCSRFMiddleware` | Enforces Origin headers on SSE endpoints (`/v1/chat/stream`, `/api/runs/`) |
| CSRF protection | `ChatCSRFMiddleware` | Validates CSRF tokens on state-changing requests |
| Security headers | `SecurityHeadersMiddleware` | Sets HSTS, X-Content-Type-Options, Referrer-Policy, etc. |
| Rate limiting | Middleware | Per-IP and per-user request limits |
| Login protection | `login_limiter.py` | Account lockout after repeated failed login attempts |
| Host validation | `TrustedHostMiddleware` | Validates Host header against ALLOWED_HOSTS |
| Forward headers | `ForwardedHeadersMiddleware` | Validates X-Forwarded-* headers from trusted proxies only |

---

## Production Security Validation

**OmniAI automatically validates production configuration at startup** via `backend/core/startup_checks.py`. If validation fails, the backend refuses to start and lists all violations.

**Startup checks enforce:**

| Check | Requirement | Rationale |
|-------|-------------|-----------|
| `COOKIE_SECURE` | Must be `true` | Prevents cookie theft over HTTP |
| `COOKIE_SAMESITE` | Must be `'none'` | Required for cross-site cookies (GitHub Pages → API) |
| `CORS_ORIGINS` | Must contain required frontend origins | Default: `https://omniplexity.github.io` |
| `CORS_ORIGINS` | No wildcard (`*`) allowed | Prevents credential exposure to any origin |
| `CORS_ORIGINS` | HTTPS-only (no `http://`) | Prevents downgrade attacks |
| `ALLOWED_HOSTS` | No wildcard (`*`) allowed | Prevents Host header injection |

**Environment override:**
```env
# Customize required frontend origins for your deployment
REQUIRED_FRONTEND_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

**Failure behavior:**
If validation fails, the backend logs all violations and exits with status code 1. This prevents accidental deployment with insecure configuration.

**Example validation error:**
```
Production security validation failed:
  ✗ CORS_ORIGINS does not include required origin: https://omniplexity.github.io
  ✗ ALLOWED_HOSTS contains wildcard '*' which is not allowed in production
Fix these issues in .env before deploying to production.
```

This ensures that production deployments are secure by default and cannot run with dangerous configuration.

---

## Post-Deployment Verification

**Quick check (run all security tests + smoke test):**

```bash
# Security & CSRF tests (from backend/)
pytest -m "security or csrf" -v

# Smoke test: health + CORS + Origin gate
API=https://<api-host>
curl -sf $API/health && echo "✓ health"
curl -sf -o /dev/null -w "%{http_code}" -H "Host: evil.example" $API/v1/health | grep -q 403 && echo "✓ host rejection"
curl -sf -o /dev/null -w "%{http_code}" -X OPTIONS -H "Origin: https://evil.example" $API/v1/chat | grep -q 403 && echo "✓ CORS rejection"
```

Run the detailed checks below after every production deployment:

### 1. Host Header Rejection
```bash
curl -i https://<api-host>/v1/health -H "Host: evil.example"
```
**Expected**: `403 Forbidden`

### 2. CORS Preflight - Allowed Origin
```bash
curl -i -X OPTIONS https://<api-host>/v1/chat \
  -H "Origin: https://omniplexity.github.io" \
  -H "Access-Control-Request-Method: POST"
```
**Expected**: `200 OK` with CORS headers (`Access-Control-Allow-Origin: https://omniplexity.github.io`)

### 3. CORS Preflight - Disallowed Origin
```bash
curl -i -X OPTIONS https://<api-host>/v1/chat \
  -H "Origin: https://evil.example" \
  -H "Access-Control-Request-Method: POST"
```
**Expected**: `403 Forbidden`

### 4. SSE Origin Gate (with valid session)
```bash
# First login to get cookies, then test origin
curl -i https://<api-host>/v1/chat/stream \
  -H "Origin: https://evil.example" \
  -c cookies.txt -b cookies.txt
```
**Expected**: `403 Forbidden` (cookie-auth with bad origin)

### 5. SSE Origin Validation (Authenticated Stream)

Test that SSE streaming endpoints validate Origin headers for CSRF protection:

```bash
# Step 1: Login first to get valid session cookie
curl -i -X POST https://<api-host>/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  -c cookies.txt

# Step 2: Try SSE stream with valid session but wrong origin (should fail)
curl -i https://<api-host>/v1/chat/stream \
  -H "Origin: https://evil.example.com" \
  -b cookies.txt
```

**Expected:** `403 Forbidden` with message about invalid or missing origin

**Why this works:**
- `ChatCSRFMiddleware` validates Origin headers on `GET_DATA_PATHS` (includes `/v1/chat/stream`)
- Even with a valid session cookie, requests from disallowed origins are rejected
- Prevents CSRF attacks on Server-Sent Events endpoints
- Defense-in-depth: SSE streams require both authentication AND valid origin

This test verifies that an attacker who tricks a user into visiting a malicious site cannot establish SSE streams using the victim's session.

---

## Troubleshooting

### CORS errors in browser

- Ensure `CORS_ORIGINS` in `.env` includes only your **stable frontend origins**:
  - Production: `https://omniplexity.github.io` (or your custom domain)
  - Local development: `http://localhost:3000`

- **⚠️ Do NOT add ngrok/tunnel domains to CORS_ORIGINS**
  - Tunnel URLs (e.g., `xyz.ngrok-free.app`) are temporary and change on every restart
  - Adding them to CORS_ORIGINS defeats the security purpose
  - Instead, use `ENVIRONMENT=development` to relax validation for local testing
  - For production tunnels (ngrok paid, cloudflared), use a stable custom domain

- **Why tunnels are different:**
  - CORS_ORIGINS is for **where the frontend is hosted**
  - Tunnels are for **how the backend is accessed**
  - The frontend stays on GitHub Pages; tunnels just proxy backend requests

- Restart backend after changes: `docker compose restart backend`

### Cannot connect to backend
- Check ngrok tunnel: `docker compose logs ngrok`
- Verify backend health: `curl http://localhost:8000/health`
- Check ngrok authtoken is set correctly in `.env`

### Database connection errors
- Ensure PostgreSQL is healthy: `docker compose ps`
- Check logs: `docker compose logs postgres`

### Login not working
- Check browser console for errors
- Verify cookies are being set (check Application > Cookies in DevTools)
- Ensure `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` for cross-site cookies

---

## Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│   GitHub Pages      │         │   Docker Desktop    │
│   (Static Frontend) │◄────────┤   (Backend Stack)   │
│                     │  HTTPS  │                     │
│ omniplexity.github  │         │ ┌───────────────┐   │
│     .io             │         │ │   FastAPI     │   │
└─────────────────────┘         │ │   Backend     │   │
                                │ │   :8000       │   │
                                │ └───────┬───────┘   │
                                │         │           │
                                │ ┌───────▼───────┐   │
                                │ │     ngrok     │   │
                                │ │    Tunnel     │   │
                                │ └───────┬───────┘   │
                                │         │           │
                                │    Public HTTPS     │
                                │    ngrok-free.dev   │
                                └─────────────────────┘
```

---

## Production Deployment Checklist

Complete this checklist before going live. All items are validated by `startup_checks.py` at startup.

### Required Environment Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `ENVIRONMENT` | `production` | Enables strict validation |
| `SECRET_KEY` | 64+ char random string | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `CORS_ORIGINS` | `https://omniplexity.github.io` | Your frontend origin(s), comma-separated |
| `ALLOWED_HOSTS` | `your-api-domain.com,localhost` | API hostnames (include tunnel domain) |
| `COOKIE_SECURE` | `true` | Required for HTTPS cookies |
| `COOKIE_SAMESITE` | `none` | Required for cross-site (GitHub Pages → API) |
| `BOOTSTRAP_ADMIN_ENABLED` | `false` | Disable after first admin creation |

### Cookie SameSite Decision

| Architecture | `COOKIE_SAMESITE` | Example |
|-------------|-------------------|---------|
| Cross-site (GitHub Pages → tunnel) | `none` | `omniplexity.github.io` → `*.ngrok-free.dev` |
| Same-site (custom domain) | `lax` | `chat.example.com` → `api.example.com` |

### Multi-Worker / Scaling

| Variable | Value | When Needed |
|----------|-------|-------------|
| `LIMITS_BACKEND` | `redis` | Multiple workers or containers |
| `REDIS_URL` | `redis://redis:6379/0` | When `LIMITS_BACKEND=redis` |

### Optional Overrides

| Variable | Default | Purpose |
|----------|---------|---------|
| `REQUIRED_FRONTEND_ORIGINS` | `https://omniplexity.github.io` | Custom required CORS origins |
| `RATE_LIMIT_RPM` | `200` | Requests per minute per IP |
| `MAX_REQUEST_BYTES` | `10485760` (10MB) | Max request body size |

---

## CI Security Gates

### Required (run on every PR)

```bash
# All security and CSRF tests (pytest markers: security, csrf)
pytest -m "security or csrf" -v

# Full test suite with coverage
pytest --cov=. --cov-report=term -v
```

These tests validate:

- Cookie SameSite normalization and cross-field constraints
- CSRF token validation on state-changing endpoints
- SSE Origin header validation on streaming endpoints
- Host header rejection for unlisted hosts
- Forwarded header validation (trusted proxy only)
- Production config validation (startup_checks.py)
- Privilege escalation hardening (session rotation/revocation)

### Optional (weekly / manual trigger)

```bash
# Integration tests (requires Redis)
pytest -m integration -v

# Dependency vulnerability audit
pip-audit -r requirements.txt
```

### CI Workflow Reference

| Workflow | Trigger | What It Does |
|----------|---------|-------------|
| `backend-ci.yml` | Every push/PR | Lint + typecheck + full test suite + Docker build |
| `integration-tests.yml` | Weekly + manual | Integration tests with Redis |
| `security-audit.yml` | Weekly + PRs | `pip-audit` dependency scan |

---

## Next Steps

1. ✅ Set up your `.env` file with real values
2. ✅ Start Docker Desktop
3. ✅ Run `docker compose --profile tunnel up -d`
4. ✅ Visit https://omniplexity.github.io
5. ✅ Log in with your admin credentials

Happy deploying! 🚀
