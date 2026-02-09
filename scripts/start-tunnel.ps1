# scripts/start-tunnel.ps1
# Starts ngrok bound to the stable dev domain.

$ErrorActionPreference = "Stop"

$Domain = "rossie-chargeful-plentifully.ngrok-free.dev"
$Port = 8000

Write-Host "Starting ngrok for http://127.0.0.1:$Port -> https://$Domain"

# Ensure ngrok exists
$ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrok) {
  throw "ngrok not found in PATH. Install ngrok and restart your terminal."
}

# Start tunnel (keeps this window attached)
ngrok http --domain=$Domain $Port
