# DuckDNS + Caddy Deployment Guide

This guide covers deploying OmniAI with a static IP using DuckDNS for DNS and Caddy for TLS/reverse proxy.

## Prerequisites

### Network Requirements
- **Public WAN IP** (not CGNAT) - verify at [whatismyip.com](https://whatismyip.com)
- Router access for port forwarding
- Ability to forward ports 80/443 (some ISPs block these)

### Verification
```powershell
# Check your WAN IP
curl ifconfig.me

# Compare to what your router shows
# If router IP is in 100.64.0.0/10, 10.0.0.0/8, 192.168.0.0/16, or 172.16.0.0/12 → CGNAT
```

## Architecture

```
Internet → Router (port 80/443) → Windows Host (Caddy :80/:443) → Docker (127.0.0.1:8000) → Backend
```

**Key security properties:**
- Backend only binds to `127.0.0.1:8000` (not LAN-exposed)
- Caddy handles TLS termination
- DuckDNS keeps hostname synced to dynamic IP

## Step 1: Reserve LAN IP

Reserve your PC's IP in router DHCP:
- Find PC MAC address via `ipconfig /all`
- Reserve IP (e.g., `10.0.0.198`) for that MAC

## Step 2: Configure Docker Compose

Edit `deploy/docker-compose.yml` backend service:

```yaml
backend:
  # ...
  ports:
    - "127.0.0.1:8000:8000"  # localhost-only, not LAN-exposed
```

Restart Docker:
```powershell
cd deploy
docker compose down
docker compose up -d
```

Verify:
```powershell
curl http://127.0.0.1:8000/health
```

## Step 3: DuckDNS Setup

### Create Update Script

`C:\duckdns\duckdns_update.ps1`:
```powershell
$domain = "your-domain"
$token  = "your-duckdns-token"
$url = "https://www.duckdns.org/update?domains=$domain&token=$token&ip="
try {
  $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 20
  if ($r.Content -notmatch "OK") { throw "DuckDNS response: $($r.Content)" }
} catch {
  Add-Content -Path "C:\duckdns\duckdns.log" -Value "$(Get-Date -Format o) $_"
}
```

### Schedule Updates

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\duckdns\duckdns_update.ps1"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "DuckDNS Update" -Action $action -Trigger $trigger -RunLevel Highest -Description "Updates DuckDNS IP every 5 minutes"
```

## Step 4: Install Caddy

```powershell
choco install caddy -y
```

### Create Caddyfile

`C:\caddy\Caddyfile`:
```
your-domain.duckdns.org {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8000 {
        flush_interval -1
    }
}
```

### Create Startup Wrapper

`C:\caddy\run_caddy.cmd`:
```cmd
@echo off
"C:\ProgramData\chocolatey\bin\caddy.exe" run --config "C:\caddy\Caddyfile" --adapter caddyfile
```

### Schedule Startup Task

```powershell
schtasks /Create /SC ONSTART /TN "Caddy Server" /TR "C:\caddy\run_caddy.cmd" /RU SYSTEM /RL HIGHEST /F
```

## Step 5: Router Port Forwarding

Forward to your reserved LAN IP (e.g., `10.0.0.198`):

| External Port | Protocol | Internal IP     | Internal Port |
|---------------|----------|-----------------|---------------|
| 80            | TCP      | 10.0.0.198      | 80            |
| 443           | TCP      | 10.0.0.198      | 443           |

## Step 6: Windows Firewall

```powershell
New-NetFirewallRule -DisplayName "Caddy HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Caddy HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

Verify:
```powershell
Get-NetFirewallRule -DisplayName "Caddy HTTP","Caddy HTTPS" | Select DisplayName, Enabled, Direction, Action
```

## Step 7: Backend CORS Configuration

Ensure `backend/config/settings.py` includes:

```python
cors_origins: str = Field(default="https://your-github-pages.github.io")
allowed_hosts: str = Field(default="localhost,127.0.0.1,your-domain.duckdns.org")
```

## Step 8: GitHub Pages Config

Edit `runtime-config.json` in the Pages repo (`omniplexity.github.io`):

```json
{
  "BACKEND_BASE_URL": "https://your-domain.duckdns.org"
}
```

Deploy to GitHub Pages.

## Verification

### Local Tests
```powershell
# Verify backend
curl http://127.0.0.1:8000/health

# Verify Caddy admin API
curl http://127.0.0.1:2019/config/

# Check listening ports
netstat -ano | findstr ":80 "
netstat -ano | findstr ":443 "
netstat -ano | findstr ":8000 "
# :8000 should only show 127.0.0.1, not 0.0.0.0
```

### External Tests (from phone on cellular)
```bash
curl -i https://your-domain.duckdns.org/health
nslookup your-domain.duckdns.org
```

## Cookie/CORS Implications with GitHub Pages

Since frontend (`your-github-pages.github.io`) and API (`your-domain.duckdns.org`) are cross-site:

1. **Cookies must be `SameSite=None; Secure`**
2. **Backend CORS must allow frontend origin**
3. **Frontend fetch must use `credentials: "include"`**

Browser third-party cookie restrictions may affect this setup. For production, consider:
- Custom domain with subdomains (`app.example.com`, `api.example.com`)
- Cloudflare Tunnel (handles this differently)

## Troubleshooting

### Cert Issuance Fails
- Verify ports 80/443 are reachable from internet
- Check ISP doesn't block inbound 80/443
- Ensure router port forwards are active

### Works Locally But Not Externally
- Verify DuckDNS resolves to current WAN IP
- Check router port forwards point to correct LAN IP
- Confirm firewall allows inbound connections

### Login/Session Issues
- Verify CORS includes `https://your-github-pages.github.io`
- Check `allowed_hosts` includes your DuckDNS domain
- Ensure cookies use `SameSite=None` for cross-site

## Alternative: Cloudflare Tunnel

If port forwarding doesn't work (CGNAT, ISP blocks), use Cloudflare Tunnel instead:

```yaml
# In docker-compose.yml, the cloudflared service already exists
# Just ensure credentials are configured
```

See `docs/CLOUDFLARE_TUNNEL.md` for details.
