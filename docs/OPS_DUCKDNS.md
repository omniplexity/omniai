# DuckDNS Ops Runbook

## Purpose
Operational guidance for reliable DuckDNS updates in OmniAI on Windows 11.

## Security rules
- `DUCKDNS_TOKEN` is server-side only.
- Never put token in frontend, logs, screenshots, or issue comments.
- Ops endpoints are admin-only and require valid session + CSRF.

## 1) Configure token (Machine scope)
Run elevated PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("DUCKDNS_TOKEN", "<your_token>", "Machine")
```

Open a new elevated shell and verify presence only (not value):

```powershell
$tok = [Environment]::GetEnvironmentVariable("DUCKDNS_TOKEN", "Machine")
if ([string]::IsNullOrWhiteSpace($tok)) { "MISSING" } else { "PRESENT len=$($tok.Length)" }
```

## 2) Install/update scheduled task
From repo root:

```powershell
cd deploy/duckdns
.\setup_duckdns_task.ps1 -Subdomain omniplexity -EveryMinutes 5
```

Expected paths:
- Log: `C:\ProgramData\OmniAI\duckdns.log`
- State: `C:\ProgramData\OmniAI\duckdns_state.json`

## 3) Verify scheduled execution
```powershell
Get-ScheduledTask -TaskName "OmniAI DuckDNS Update" | Format-List
Get-ScheduledTaskInfo -TaskName "OmniAI DuckDNS Update" | Format-List
Start-ScheduledTask -TaskName "OmniAI DuckDNS Update"
Get-Content "C:\ProgramData\OmniAI\duckdns.log" -Tail 50
```

## 4) Manual updater checks
```powershell
.\duckdns_update.ps1 -Subdomain omniplexity -Force
echo $LASTEXITCODE
```

Exit codes:
- `0`: success/no-op
- `2`: config error (usually token missing/invalid)
- `3`: DuckDNS returned `KO` (token/subdomain mismatch)
- `4`: network/public IP discovery failed
- `5`: unexpected response or internal error

## 5) Ops Console usage
Open SPA as admin user and navigate to `/#/ops`.

Ops panel capabilities:
- View DuckDNS status and recent update events
- Run `Test DuckDNS now` (labeled as test source)
- Run `Force update now` for manual corrective update
- Copy redacted diagnostics bundle

## 6) Troubleshooting decision tree
1. `DUCKDNS_TOKEN_MISSING`
- Action: Set machine env token, restart backend service/task.
2. `DUCKDNS_KO`
- Action: Validate token and subdomain pair on duckdns.org.
3. `DUCKDNS_NETWORK`
- Action: Check outbound internet/DNS/proxy/firewall on host.
4. Last event is `OK` but domain still unreachable
- Action: Check router port forward, Caddy service status, and local backend health.
5. Domain resolves to old IP
- Action: Run force update from Ops Console, then wait DNS propagation.

## 7) Safe diagnostics for support
- Include only:
  - last 100 DuckDNS events from Ops page
  - task info (`Get-ScheduledTaskInfo`)
  - `nslookup omniplexity.duckdns.org`
  - `/health` JSON
- Exclude:
  - token values
  - full environment dumps
