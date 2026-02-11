# OmniAI Deployment Guide

## Architecture
- Frontend source: `OmniAI/frontend` (Vite/Preact SPA)
- Frontend deploy target: `omniplexity.github.io` (static artifacts only)
- Backend: `OmniAI/backend` (FastAPI)
- Runtime config: `runtime-config.json` loaded by browser at runtime (no secrets)

## Frontend Deployment (GitHub Pages)

### Canonical flow
1. Build SPA from `OmniAI/frontend`.
2. Deploy `frontend/dist` into `omniplexity.github.io`.
3. Keep only static artifacts in Pages repo:
- `index.html`
- `404.html`
- `assets/*`
- `.nojekyll`
- `icons/*`
- `runtime-config.json`
- `CNAME` (if used)

### Workflow
`OmniAI/.github/workflows/deploy-pages.yml`:
- Uses `JamesIves/github-pages-deploy-action@v4`
- `folder: frontend/dist`
- `clean: true`
- `clean-exclude`:
- `runtime-config.json`
- `icons/**`
- `CNAME`
- `.nojekyll`

### Runtime config
`omniplexity.github.io/runtime-config.json` must contain only runtime-safe values:

```json
{
  "BACKEND_BASE_URL": "https://<your-backend-domain>",
  "FEATURE_FLAGS": {}
}
```

Do not commit secrets into `runtime-config.json`.

Operational rule (prevent config drift):
- Whenever the backend public origin changes, update `runtime-config.json` in the Pages repo **in the same release**.
- The value must always be the externally reachable API origin (for current production: `https://omniplexity.duckdns.org`).

## Backend Deployment

### Security baseline
- All policy enforced server-side.
- Cookie auth + CSRF for state-changing endpoints.
- SSE Origin validation enabled for `/v1/chat/stream`.
- CORS restricted to trusted frontend origins.

### Minimum required env
- `ENVIRONMENT=production`
- `SECRET_KEY=<strong random value>`
- `CORS_ORIGINS=https://omniplexity.github.io` (or your custom frontend origin)
- `COOKIE_SECURE=true`
- `COOKIE_SAMESITE=none` for cross-site Pages -> API deployments
- `BOOTSTRAP_ADMIN_ENABLED=false` after initial setup

### Running backend
Use your existing stack (Docker/Caddy/systemd). If reverse proxying with Caddy, include unbuffered SSE handling for:
- `/api/chat/stream*`
- `/v1/chat/stream*`

## Domain Routing
Canonical production routing:
- UI SPA domain: `https://omniplexity.github.io`
- API domain: `https://omniplexity.duckdns.org`

DuckDNS domain behavior:
- `GET /` redirects to `https://omniplexity.github.io/`
- `GET /ops` and `GET /ops/` redirect to `https://omniplexity.github.io/#/ops`
- Backend APIs stay on DuckDNS:
- `/health`, `/readyz`
- `/api/auth/*`
- `/v1/*`

Endpoint policy (canonical vs compatibility):
- Canonical application API surface is `/v1/*`.
- Frontend should call `/v1/*` by default for auth/chat/providers/ops.
- `/api/auth/*` remains compatibility-only during migration and should not be used for new frontend paths.

Notes:
- Do not use same-host hash redirects like `/ops -> /#/ops`; URL fragments are client-side only and can cause redirect loops at the proxy.
- For cross-origin auth (Pages UI -> DuckDNS API), keep cookie policy + CORS aligned:
- `COOKIE_SAMESITE=none`
- `COOKIE_SECURE=true`
- `CORS_ORIGINS` must include `https://omniplexity.github.io`

## DuckDNS reliability + security
Use the hardened updater + task setup scripts:
- `deploy/duckdns/duckdns_update.ps1`
- `deploy/duckdns/setup_duckdns_task.ps1`

Token requirements:
- `DUCKDNS_TOKEN` must be set at **Machine scope** on Windows host.
- Token is never returned by API and never logged.

Quick setup (elevated PowerShell):

```powershell
[Environment]::SetEnvironmentVariable("DUCKDNS_TOKEN", "<your_token>", "Machine")
cd deploy/duckdns
.\setup_duckdns_task.ps1 -Subdomain omniplexity -EveryMinutes 5
```

Default runtime files:
- `C:\ProgramData\OmniAI\duckdns.log`
- `C:\ProgramData\OmniAI\duckdns_state.json`

Detailed runbook:
- `docs/OPS_DUCKDNS.md`

## Ops Console
Ops UI is role-gated and feature-flagged in SPA (`/#/ops`):
- Admin session required (`/v1/auth/me` role check)
- POST actions require CSRF token
- Backend validates origin/referer and session cookie
- No shell/REPL/file browser features exposed

DuckDNS ops APIs:
- `GET /v1/ops/duckdns/status`
- `GET /v1/ops/duckdns/logs?limit=200`
- `POST /v1/ops/duckdns/test`
- `POST /v1/ops/duckdns/update`

## CI expectations

### Frontend CI
`OmniAI/.github/workflows/frontend-ci.yml`:
- Builds frontend
- Starts backend (mock provider mode)
- Starts frontend preview server
- Runs Playwright against preview URL
- Uploads Playwright artifacts on failure

### Security CI
`OmniAI/.github/workflows/security-audit.yml` includes secret scanning (`gitleaks`).

## Post-deploy checks

### Frontend
```bash
cd frontend
npm run test
npm run test:e2e
```

### Backend
```bash
cd backend
pytest -q
```

### Chat contract smoke
1. `POST /v1/chat` -> returns `run_id`
2. `GET /v1/chat/stream?run_id=...` -> emits `message` then `done|stopped|error`
3. `POST /v1/chat/cancel` -> emits `stopped`
4. `POST /v1/chat/retry` -> returns new `run_id` and streams events

### DuckDNS ops smoke
```bash
curl -i https://omniplexity.duckdns.org/v1/ops/duckdns/status
curl -i https://omniplexity.duckdns.org/v1/ops/duckdns/logs?limit=20
```
