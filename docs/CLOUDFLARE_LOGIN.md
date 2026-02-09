# Cloudflare Tunnel Authentication Guide

## Step 1: Authenticate with Cloudflare

Run in PowerShell as Administrator:

```powershell
cloudflared login
```

This will:
1. Open your default browser to Cloudflare
2. Sign in with your Cloudflare account
3. Select the domain: `omniplexity.ai`
4. Click "Authorize"

## Step 2: Download Certificate

After authorization, cloudflared automatically downloads `cert.pem` to:
- Windows: `C:\Users\<you>\.cloudflared\cert.pem`

## Step 3: Create Tunnel

```powershell
cloudflared tunnel create omniai
```

This creates:
- Tunnel UUID
- Credentials file: `C:\Users\<you>\.cloudflared\<UUID>.json`

## Step 4: Copy Files to OmniAI

```powershell
# Copy credentials
copy $env:USERPROFILE\.cloudflared\*.json deploy\cloudflared\credentials.json

# Copy certificate
copy $env:USERPROFILE\.cloudflared\cert.pem deploy\cloudflared\cert.pem
```

## Step 5: Route DNS

```powershell
cloudflared tunnel route dns omniai api.omniplexity.ai
```

## Step 6: Create Config

Create `deploy/cloudflared/config.yml`:

```yaml
tunnel: omniai
credentials-file: /etc/cloudflared/credentials.json
origin-cert: /etc/cloudflared/cert.pem

ingress:
  - hostname: api.omniplexity.ai
    service: http://backend:8000
  - service: http_status:404
```

## Step 7: Deploy

```powershell
cd deploy
docker compose up -d
```

## Troubleshooting

### "Cannot determine default origin certificate path"

Make sure you've run `cloudflared login` first. The certificate is required.

### Credentials file not found

Check: `dir $env:USERPROFILE\.cloudflared`

### Tunnel already exists

```powershell
cloudflared tunnel list
cloudflared tunnel delete <name-or-uuid>
```
