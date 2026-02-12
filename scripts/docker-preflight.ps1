param(
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Fail($msg) {
  Write-Host "[FAIL] $msg" -ForegroundColor Red
  exit 1
}

function Info($msg) {
  if (-not $Quiet) {
    Write-Host "[INFO] $msg" -ForegroundColor Cyan
  }
}

function Pass($msg) {
  Write-Host "[PASS] $msg" -ForegroundColor Green
}

Info "Checking Docker CLI..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Fail "Docker CLI not found. Install Docker Desktop and reopen PowerShell."
}
Pass "Docker CLI found."

Info "Checking Docker engine availability..."
$serverVersion = (docker version --format '{{.Server.Version}}' 2>$null).Trim()
if ([string]::IsNullOrWhiteSpace($serverVersion)) {
  Fail "Docker engine is not reachable. Start Docker Desktop (Linux containers mode) and retry."
}
Pass "Docker engine reachable."

Info "Checking Docker engine OS type..."
$osType = (docker info --format '{{.OSType}}' 2>$null).Trim()
if ($osType -ne "linux") {
  Fail "Docker engine OSType='$osType'. Switch Docker Desktop to Linux containers."
}
Pass "Docker engine is using Linux containers."

Info "Checking docker compose plugin..."
try {
  $null = docker compose version 2>$null
} catch {
  Fail "docker compose plugin not available. Install/enable Docker Compose v2."
}
Pass "docker compose plugin available."

Info "Checking deploy entrypoint file..."
if (-not (Test-Path "deploy/docker-compose.yml")) {
  Fail "Missing deploy/docker-compose.yml in current repository root."
}
Pass "deploy/docker-compose.yml present."

Write-Host ""
Write-Host "Preflight complete. Recommended production command:" -ForegroundColor Yellow
Write-Host "  cd deploy; docker compose up -d --build"
