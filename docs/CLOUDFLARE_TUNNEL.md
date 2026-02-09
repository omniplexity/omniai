# Cloudflare Tunnel Setup (Docker-Native, OmniAI)

## Purpose

**Replaces ngrok** as the official tunnel solution for OmniAI.

### Why Cloudflare Tunnel?

| Feature | ngrok (free) | Cloudflare Tunnel |
|---------|--------------|-------------------|
| Preserves cookies | ❌ | ✅ |
| Stable hostname | ❌ | ✅ |
| HttpOnly + Secure + SameSite=None | ❌ | ✅ |
| No rate limit surprises | ❌ | ✅ |
| Origin lock | ❌ | ✅ |

**ngrok is deprecated** for OmniAI production use due to cookie stripping issues.

---

## Goals

- ✅ Fix cross-site auth (Cloudflare does not strip Set-Cookie)
- ✅ Preserve HttpOnly + Secure + SameSite=None cookies
- ✅ Keep backend private (no public port exposure)
- ✅ Work cleanly with GitHub Pages frontend
- ✅ Integrate into existing docker-compose stack

---

## High-Level Architecture

```
GitHub Pages (https://omniplexity.github.io)
        │
        │ HTTPS (cookies preserved)
        ▼
Cloudflare Tunnel (cloudflared)
        │
        │ internal Docker network
        ▼
FastAPI backend (backend:8000)
```

---

## Step 1 — Prerequisites (One-Time)

### 1. Cloudflare Account

- Domain added to Cloudflare (can be subdomain only)
- Example subdomain: `api.omniplexity.ai`

### 2. Install cloudflared Locally (for auth only)

**Windows (PowerShell):**
```powershell
winget install Cloudflare.cloudflared
```

---

## Step 2 — Create the Tunnel (Once)

```bash
# Login (opens browser → authorize Cloudflare)
cloudflared login

# Create tunnel
cloudflared tunnel create omniai
```

**Output:**
- Tunnel UUID
- Credentials JSON file, e.g.: `C:\Users\<you>\.cloudflared\<UUID>.json`

---

## Step 3 — DNS Route (Cloudflare-managed)

```bash
cloudflared tunnel route dns omniai api.omniplexity.ai
```

**Creates:** `https://api.omniplexity.ai`

No ports exposed. No firewall rules needed.

---

## Step 4 — Add cloudflared to Docker Compose

### Directory Layout (Recommended)

```
deploy/
├── docker-compose.yml
├── cloudflared/
│   ├── config.yml
│   └── credentials.json
```

### Copy Credentials

```powershell
# Windows
copy $env:USERPROFILE\.cloudflared\<UUID>.json deploy\cloudflared\credentials.json
```

### deploy/cloudflared/config.yml

```yaml
tunnel: omniai
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: api.omniplexity.ai
    service: http://backend:8000
  - service: http_status:404
```

### Update deploy/docker-compose.yml

```yaml
services:
  backend:
    image: omniai-backend
    container_name: omniai-backend
    env_file:
      - ../.env
    expose:
      - "8000"
    networks:
      - omniai

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: omniai-cloudflared
    command: tunnel run omniai
    volumes:
      - ./cloudflared/config.yml:/etc/cloudflared/config.yml:ro
      - ./cloudflared/credentials.json:/etc/cloudflared/credentials.json:ro
    depends_on:
      - backend
    networks:
      - omniai
    restart: unless-stopped

networks:
  omniai:
    driver: bridge
```

> ⚠️ **Important:** Do not publish backend ports (`ports:`). Use `expose:` to keep it internal only.

---

## Step 5 — Backend .env Changes

Update `.env`:

```bash
# Replace ngrok domain
CORS_ORIGINS=https://omniplexity.github.io,https://api.omniplexity.ai

# Cookies (already correct, verify)
COOKIE_SECURE=true
COOKIE_SAMESITE=none
COOKIE_DOMAIN=

# Optional hardening
ALLOWED_HOSTS=api.omniplexity.ai
```

> ⚠️ Leave `COOKIE_DOMAIN` empty unless you intentionally want shared subdomain cookies.

---

## Step 6 — Frontend Runtime Config

Update `runtime-config.json`:

```json
{
  "BACKEND_BASE_URL": "https://api.omniplexity.ai"
}
```

Push → GitHub Pages auto-deploys.

---

## Step 7 — Bring It Up

```bash
cd deploy
docker compose up -d
```

### Verify

```bash
curl https://api.omniplexity.ai/health
```

**Expected:**
```json
{"status":"ok"}
```

---

## Step 8 — Final Validation Checklist

### Auth (Critical)

| Check | Expected |
|-------|----------|
| Set-Cookie present on `/api/auth/login` | ✅ |
| HttpOnly | ✅ |
| Secure | ✅ |
| SameSite=None | ✅ |
| Session persists across refresh | ✅ |
| Logout clears session | ✅ |

### Browser DevTools

1. Open DevTools → Application → Cookies → `api.omniplexity.ai`
2. Verify cookie is visible and not blocked

### Security

- Backend not reachable via raw IP
- Only Cloudflare can reach it
- No secrets in frontend

---

## ngrok Deprecation Notice

**ngrok is deprecated** for OmniAI.

### Why ngrok Fails

- ngrok free tier **strips Set-Cookie headers**
- Cross-site authentication breaks
- HttpOnly cookies don't persist through tunnel

### Migration Path

1. Use Cloudflare Tunnel (this guide) → **supported**
2. Use paid ngrok plan → **unsupported** (cookie stripping may still apply)
3. Localhost development only → ngrok acceptable

---

## Optional (Later, Not Required)

- **Cloudflare Access** — email-based allowlist
- **Cloudflare WAF rules** — IP allowlisting
- **Bot mitigation**

---

## Next Steps

After validation:

1. ✅ Re-run Phase 4 (Auth Tests) — PASS expected
2. ✅ Re-run Playwright E2E — PASS expected
3. Begin frontend UX/feature development

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `cloudflared login` | Authorize Cloudflare |
| `cloudflared tunnel create omniai` | Create tunnel |
| `cloudflared tunnel route dns omniai api.omniplexity.ai` | DNS routing |
| `docker compose up -d` | Start stack |
| `curl https://api.omniplexity.ai/health` | Health check |
