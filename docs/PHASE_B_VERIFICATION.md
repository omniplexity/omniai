# Phase B Cross-Site Browser Verification Checklist

**Purpose:** Verify cross-site operation between GitHub Pages frontend and ngrok tunnel backend.

**Prerequisites:**
- Backend running with cross-site cookies enabled
- Frontend deployed to https://omniplexity.github.io
- Ngrok tunnel active (or production domain)

---

## Required Backend Environment Variables

```bash
# Cross-site cookies require SameSite=None and Secure
COOKIE_SECURE=true
COOKIE_SAMESITE=none

# CORS must include GitHub Pages origin
CORS_ORIGINS=https://omniplexity.github.io

# Required for tunnel deployments
ALLOWED_HOSTS=localhost,127.0.0.1,*.ngrok-free.dev

# Optional: lock to specific frontend origin (security hardening)
REQUIRED_FRONTEND_ORIGINS=https://omniplexity.github.io
```

**Critical:** After changing `COOKIE_SAMESITE` from `lax` to `none`, **restart the backend server**.

---

## B1) CSP Verification ☐

**Steps:**
1. Open https://omniplexity.github.io (hard refresh: Ctrl+Shift+R)
2. Open DevTools → Console
3. Open DevTools → Elements → Check `<head>` for CSP meta tag

**PASS Criteria:**
- [ ] No "Refused to..." CSP violation messages in Console
- [ ] CSP meta tag exists in `<head>` before any `<script>` tags

**Expected CSP (from docs/CSP_PATCH.md):**
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

**Fixes if failing:**
- Remove inline `<script>` tags or add `'unsafe-inline'` to `script-src`
- Add external CDN domains to `script-src`, `style-src`, `img-src`, `connect-src`

---

## B2) CORS + Credentials ☐

**Steps:**
1. DevTools → Network (enable "Preserve log")
2. Attempt login
3. Click the first request to backend (login endpoint)
4. Check Request and Response headers

**PASS Criteria:**

**Request Headers:**
- [ ] `Origin: https://omniplexity.github.io` present

**Response Headers:**
- [ ] `Access-Control-Allow-Origin: https://omniplexity.github.io` (exact match, no wildcard)
- [ ] `Access-Control-Allow-Credentials: true`

**Preflight (OPTIONS) Request:**
- [ ] Status: 200 or 204 (not 4xx)
- [ ] `Access-Control-Allow-Headers` includes `X-CSRF-Token`
- [ ] `Access-Control-Allow-Methods` includes POST, OPTIONS

**Common Failures:**
- CORS error in console → Origin not in `CORS_ORIGINS` allowlist
- Login works but subsequent calls fail → Missing `Access-Control-Allow-Credentials`

---

## B3) Cookies ☐

**Steps:**
1. After login, DevTools → Application → Cookies
2. Select backend domain (e.g., `https://your-ngrok-domain.ngrok-free.dev`)
3. Check session cookie properties:
   - [ ] `Secure` ✓
   - [ ] `SameSite` = `None` (capital N!)
   - [ ] `HttpOnly` ✓
4. Refresh page, make another backend call
5. Network tab → Any backend request → Request Headers
6. Verify:
   - [ ] `Cookie: omni_session=...` header present

**Expected Cookie Properties (from backend/api/auth.py):**
```python
response.set_cookie(
    key="omni_session",
    value=session_token,
    httponly=True,        # Not accessible via JavaScript
    secure=True,           # HTTPS only
    samesite="None",       # Cross-site allowed (capital N!)
    path="/",
    max_age=604800,        # 7 days
)
```

**Common Failures:**
- Cookie exists but not sent → SameSite=Lax/Strict, or Secure missing, or domain mismatch

---

## B4) SSE Streaming ☐

**Steps:**
1. DevTools → Network
2. Send a chat message that triggers streaming
3. Locate stream request (`/v1/chat/stream` or `/api/chat/stream`)
4. Click to inspect

**PASS Criteria:**
- [ ] Status: `200`
- [ ] Response Headers: `Content-Type: text/event-stream`
- [ ] Stream stays open and incremental events/data visible
- [ ] UI updates live with streaming content

**Expected SSE Response Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Request-ID: (some-uuid)
```

**Common Failures:**
- Immediate disconnect → Check backend logs for E2003/E2004 (Origin validation failure)
- No events → Verify `Origin` header is sent (EventSource includes it automatically)

---

## B5) Cancel ☐

**Steps:**
1. Start a streaming chat
2. Click cancel button
3. Observe stream closure

**PASS Criteria:**
- [ ] Stream closes promptly (within a few seconds)
- [ ] UI indicates "canceled" state
- [ ] Backend stops processing (best-effort)

---

## Quick Self-Test (No DevTools)

Use the cross-site diagnostics endpoint:

```bash
# Test from browser (must be on https://omniplexity.github.io)
curl -H "Origin: https://omniplexity.github.io" \
     https://your-backend.ngrok-free.dev/api/diag/cross-site-check
```

Expected response includes:
```json
{
  "cors": {
    "origin_present": true,
    "allow_origin": "https://omniplexity.github.io",
    "allow_credentials": true
  },
  "cookies": {
    "session_cookie_configured": true,
    "samesite_none": true,
    "secure": true
  }
}
```

---

## Backend Configuration Summary

| Setting | Value | Purpose |
|---------|-------|---------|
| `COOKIE_SECURE` | `true` | Required for cross-site cookies |
| `COOKIE_SAMESITE` | `none` | Allows cross-site cookie sending |
| `CORS_ORIGINS` | `https://omniplexity.github.io` | GitHub Pages origin |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,*.ngrok-free.dev` | Host header validation |
| `REQUIRED_FRONTEND_ORIGINS` | `https://omniplexity.github.io` | Lock to specific frontend |

---

## Diagnostics Endpoint Security

The `/api/diag/*` endpoints are **gated** and optional. They are not required for normal operation.

### Access Control

Two authentication methods are supported:

1. **Admin session**: Valid session cookie (normal authenticated access)
2. **Token access**: `X-Diag-Token` header with `DIAG_TOKEN` env var

### Configuration

```bash
# In .env - leave empty to disable token-based access
DIAG_TOKEN=your-stable-token-here

# Default: diag_enabled=False in production/staging
# Default: diag_enabled=True in development/test
DIAG_ENABLED=true
```

**Security Properties:**
- `diag_token` defaults to `None` (disabled unless explicitly set)
- Token is sourced from environment variable (stable across restarts)
- In production/staging: `diag_enabled=false` by default (disabled)
- Token access is optional, not required for normal operation

### Quick Self-Test

```bash
# Test with token (replace YOUR_TOKEN with DIAG_TOKEN from .env)
curl -H "X-Diag-Token: YOUR_TOKEN" \
     https://your-backend.example.com/api/diag

# Expected: {"status": "ok", ...}
```

### Response Guarantees

The diagnostics response does **not** include:
- Secret keys (`SECRET_KEY`)
- API keys (`OPENAI_API_KEY`, etc.)
- Full connection strings (passwords masked)

The diagnostics response **may include** (for debugging):
- CORS origin list (boolean checks only)
- Cookie configuration (names, boolean flags)
- Version and uptime information

### Browser Verification Remains Authoritative

The `/api/diag/*` endpoints provide **server-side sanity checks only**. They cannot validate:
- Preflight behavior (CORS OPTIONS requests)
- Credentialed fetch (cookies sent with requests)
- Cookie acceptance (browser settings)
- SSE streaming behavior

**Always verify with browser DevTools** for complete cross-site validation.

---

## Troubleshooting Flow

❌ CORS error in console
    └─→ Check CORS_ORIGINS includes https://omniplexity.github.io
    └─→ Check backend restarted after config change
    └─→ Verify Origin header matches exactly (no trailing slash)

❌ Cookies not sent
    └─→ Check SameSite=None (capital N!)
    └─→ Check Secure=true
    └─→ Check domain matches (ngrok-free.dev vs subdomain)

❌ SSE disconnects immediately
    └─→ Check /v1/chat/stream Origin validation in logs
    └─→ Verify allowed_origins includes frontend origin
    └─→ Check concurrency limits not exceeded

❌ Login works but subsequent calls 401
    └─→ Check session cookie is being sent
    └──> Check CSRF token header matches cookie
```

---

## Related Documentation

- `docs/CSP_PATCH.md` - CSP implementation for frontend
- `docs/SECURITY.md` - Security hardening guidelines
- `docs/PHASE6_HARDENING.md` - Phase 6 hardening checklist
- `backend/api/diag.py` - Backend diagnostics API
