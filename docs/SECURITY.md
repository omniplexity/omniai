# OmniAI Security Documentation

## Content Security Policy (CSP)

CSP provides an additional layer of defense against XSS attacks and data injection. It restricts which resources can be loaded and where requests can be sent.

### Frontend CSP Configuration

Add the following to the `<head>` section of `frontend/index.html`:

**Development / Tunnel Environment (ngrok, cloudflared):**
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

**Production (stable API domain):**
```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  img-src 'self' data: blob:;
  style-src 'self' 'unsafe-inline';
  script-src 'self';
  connect-src 'self' https://api.yourdomain.com;
">
```

### CSP Directives Explained

| Directive | Value | Purpose |
|-----------|-------|---------|
| `default-src` | `'self'` | Default fallback - only allow same-origin resources |
| `base-uri` | `'self'` | Prevent `<base>` tag injection |
| `object-src` | `'none'` | Block Flash/plugin content |
| `frame-ancestors` | `'none'` | Prevent clickjacking via iframes |
| `img-src` | `'self' data: blob:` | Allow same-origin images and data URIs |
| `style-src` | `'self' 'unsafe-inline'` | Allow inline styles (required for UI frameworks) |
| `script-src` | `'self'` | Only allow same-origin JavaScript |
| `connect-src` | `'self' https:` (dev) or specific domain (prod) | Restrict API calls |

### Testing CSP

Before deploying to production, test CSP in staging:

1. Report-Only mode (for testing):
```html
<meta http-equiv="Content-Security-Policy-Report-Only" content="... directives ...">
```

2. Violations will be reported to the URL specified in `report-uri` (if configured)

3. Check browser console for CSP violations

4. Adjust directives as needed before enforcing

### Production Migration Checklist

When migrating from GitHub Pages to custom domain:

- [ ] Update `connect-src` to specific API domain
- [ ] Remove `https:` wildcard
- [ ] Test all API calls are still functional
- [ ] Verify no inline scripts are blocked
- [ ] Document the approved domain in this file

---

## Security Headers

The backend automatically adds security headers via `SecurityHeadersMiddleware`:

| Header | Value | Protection |
|--------|-------|------------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `Referrer-Policy` | `no-referrer` | Controls referrer information |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disables sensitive browser features |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |

---

## Authentication & Cookie Security

### Password Hashing

- Argon2id (preferred) with automatic bcrypt migration path
- Configurable via backend password utilities

### Session Cookies

- **HttpOnly:** Prevents JavaScript access (XSS mitigation)
- **Secure:** Cookies only sent over HTTPS
- **SameSite:** Controls cross-site cookie behavior (see matrix below)

### Cookie SameSite Configuration

| Deployment | Frontend | Backend | `COOKIE_SAMESITE` | Reason |
|------------|----------|---------|-------------------|--------|
| Cross-site (default) | `omniplexity.github.io` | `*.ngrok-free.dev` | `none` | Different eTLD+1 |
| Same-site (custom) | `chat.yourdomain.com` | `api.yourdomain.com` | `lax` | Same eTLD+1 |
| Local development | `localhost:3000` | `localhost:8000` | `lax` | Same-site |

**Symptom of wrong setting:** Login succeeds but subsequent API calls return 401 (browser silently drops the cookie).

**Enforcement:** `startup_checks.py` enforces `COOKIE_SAMESITE=none` in production because the default architecture is cross-site.

### CSRF Protection

- Double-submit cookie pattern: CSRF token in cookie + header
- All state-changing requests (POST/PUT/DELETE) validated
- SSE streaming endpoints validate Origin header via `ChatCSRFMiddleware`
- Invite-only registration

### CORS Validation (Production)

- `CORS_ORIGINS` must contain your frontend origin(s)
- No wildcards (`*`) allowed
- HTTPS-only (no `http://`)
- Override default with: `REQUIRED_FRONTEND_ORIGINS=https://yourdomain.com`

See `backend/core/startup_checks.py` for complete validation rules.
See [AGENTS.md](../AGENTS.md) for detailed agent security architecture.
