# OmniAI DuckDNS + Caddy Production Deployment

## Architecture

```
Internet → Router (port 80/443) → Caddy (:443) → Backend (127.0.0.1:8000)
                                    ↓
                          PostgreSQL + Redis (Docker)
```

**Security Properties:**
- ✅ Backend binds to `127.0.0.1:8000` (not publicly exposed)
- ✅ Caddy handles TLS termination (Let's Encrypt)
- ✅ DuckDNS keeps hostname synced to dynamic IP
- ✅ Cross-site cookies: `SameSite=None; Secure`

---

## Prerequisites

1. **DuckDNS account** - https://www.duckdns.org
2. **Domain created** - `omniplexity.duckdns.org`
3. **Public WAN IP** (not CGNAT) - verify at whatismyip.com
4. **Router access** for port forwarding
5. **Docker Desktop** running

---

## Step 1: DuckDNS Setup

### Create scheduled task to update IP every 5 minutes:

```powershell
cd C:\Users\storm\Desktop\OmniAI\deploy\duckdns
.\setup_scheduled_task.ps1
```

### Verify immediate update:
```powershell
.\duckdns_update.ps1
```

Check logs:
```powershell
Get-Content .\duckdns.log -Tail 10
```

---

## Step 2: Router Port Forwarding

Forward to your PC's LAN IP (reserve it first in DHCP):

| External Port | Protocol | Internal IP (your PC) | Internal Port |
|---------------|----------|----------------------|---------------|
| 80 | TCP | 192.168.x.x | 80 |
| 443 | TCP | 192.168.x.x | 443 |

**Note:** Find your LAN IP with `ipconfig` and reserve it in router DHCP settings.

---

## Step 3: Windows Firewall

```powershell
cd C:\Users\storm\Desktop\OmniAI\deploy\duckdns
.\firewall_rules.ps1
```

---

## Step 4: Configure .env

Edit `C:\Users\storm\Desktop\OmniAI\.env`:

```env
# Generate a strong SECRET_KEY:
# python -c "import secrets; print(secrets.token_urlsafe(64))"

SECRET_KEY=your-generated-key-here
BOOTSTRAP_ADMIN_PASSWORD=your-secure-admin-password
```

---

## Step 5: Start Docker Services

```powershell
cd C:\Users\storm\Desktop\OmniAI\deploy
docker compose up -d
```

Check status:
```powershell
docker compose ps
docker compose logs -f
```

---

## Step 6: Verify

### Local tests:
```powershell
# Backend health
curl http://127.0.0.1:8000/health

# Check Caddy is listening
curl http://localhost:80
```

### External test (from phone on cellular):
```bash
curl -i https://omniplexity.duckdns.org/health
```

Expected: `{"status":"ok"}`

---

## Step 7: First-Time Admin Setup

1. Visit https://omniplexity.duckdns.org
2. Sign up with bootstrap admin credentials
3. After login, disable bootstrap mode:

Edit `.env`:
```env
BOOTSTRAP_ADMIN_ENABLED=false
```

Restart:
```powershell
docker compose restart backend
```

---

## Smoke Test Commands

```bash
# 1. Public health check
curl -i https://omniplexity.duckdns.org/health

# 2. CORS sanity (from GitHub Pages origin)
curl -i https://omniplexity.duckdns.org/v1/meta \
  -H "Origin: https://omniplexity.github.io"

# 3. Preflight (CSRF headers)
curl -i -X OPTIONS https://omniplexity.duckdns.org/api/auth/login \
  -H "Origin: https://omniplexity.github.io" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-csrf-token"
```

Expected responses:
- ✅ 200 OK for health
- ✅ CORS headers: `Access-Control-Allow-Origin: https://omniplexity.github.io`
- ✅ CORS headers: `Access-Control-Allow-Credentials: true`

---

## Troubleshooting

### Cert issuance fails
```bash
# Verify ports 80/443 are reachable
curl -v http://omniplexity.duckdns.org
```

### Works locally but not externally
- Verify DuckDNS resolves: `nslookup omniplexity.duckdns.org`
- Check router port forwards are active
- Confirm firewall allows inbound 80/443

### Login/session issues
- Verify CORS includes `https://omniplexity.github.io`
- Check cookies use `SameSite=None; Secure`

---

## Useful Commands

```powershell
# Stop all services
docker compose down

# Restart backend only
docker compose restart backend

# View all logs
docker compose logs -f

# Shell into backend
docker compose exec backend sh

# Database migrations
docker compose exec backend alembic upgrade head
```

---

## Security Checklist

- [ ] Backend binds to `127.0.0.1:8000` (not LAN-exposed)
- [ ] Caddy handles TLS on `:443`
- [ ] DuckDNS updates IP every 5 minutes
- [ ] Router forwards 80/443 to Caddy
- [ ] Firewall allows 80/443 inbound
- [ ] CORS allows only `https://omniplexity.github.io`
- [ ] Cookies are `SameSite=None; Secure`
- [ ] Bootstrap admin disabled after setup
- [ ] Strong `SECRET_KEY` set
