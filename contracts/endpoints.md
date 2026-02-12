# OmniAI Endpoint Map (Phase 0 Baseline)

## UI Lane (Canonical)

Prefix: `/v1/*`  
Auth: Cookie session + CSRF for mutating methods  
CORS: strict allowlist (`CORS_ORIGINS`)

- `/v1/meta`
- `/v1/auth/*`
- `/v1/status`
- `/v1/models`
- `/v1/providers/*`
- `/v1/chat*`
- `/v1/conversations*`
- `/v1/memory*`
- `/v1/tools*`
- `/v1/voice*`
- `/v1/presets*`
- `/v1/ops*` (admin role required)

## Public Lane (Planned / Disabled in Phase 0)

Prefix: `/v1/public/*`  
Auth: bearer tokens (no cookie session)  
CORS: off by default

## Dev/Admin Lane (Planned / Disabled in Phase 0)

Prefix: `/v1/dev/*`  
Auth: cookie session + CSRF + role checks

## Legacy Lane (Deprecated Compat Only)

Prefix: `/api/*`  
Status: deprecated compatibility surface only.  
Rule: no new `/api/*` routes.

Current legacy routers include:

- `/api/auth/*`
- `/api/admin/*`
- `/api/diag/*`
- `/api/media/*`
- `/api/knowledge/*`
- `/api/projects/*`
- `/api/context-blocks/*`
- `/api/artifacts/*`
- `/api/workflows/*`
