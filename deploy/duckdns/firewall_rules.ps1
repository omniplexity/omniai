# Windows Firewall Rules for OmniAI Caddy Reverse Proxy
# Opens ports 80 and 443 for Caddy to receive HTTPS traffic

# Caddy HTTP port
New-NetFirewallRule `
    -DisplayName "OmniAI Caddy HTTP" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 80 `
    -Action Allow `
    -Enabled True

# Caddy HTTPS port
New-NetFirewallRule `
    -DisplayName "OmniAI Caddy HTTPS" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 443 `
    -Action Allow `
    -Enabled True

Write-Host ""
Write-Host "Firewall rules created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Current rules:" -ForegroundColor Yellow
Get-NetFirewallRule -DisplayName "OmniAI*" | Format-Table DisplayName, Enabled, Direction, Action
