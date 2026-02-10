<#
.SYNOPSIS
    OmniAI Deployment Verification Script (Windows PowerShell)
.DESCRIPTION
    Run this after deploying to GitHub Pages to verify the deployment.
.PARAMETER PagesRepoPath
    Path to the Pages repository (default: ../omniplexity.github.io)
.PARAMETER ApiUrl
    Backend API URL (default: https://omniplexity.duckdns.org)
.EXAMPLE
    .\deploy-verify.ps1
#>
param(
    [string]$PagesRepoPath = "../omniplexity.github.io",
    [string]$ApiUrl = "https://omniplexity.duckdns.org"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ScriptDir "../frontend"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "OmniAI Deployment Verification" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Test-Pass { param([string]$Message) Write-Host "✓ $Message" -ForegroundColor Green }
function Test-Fail { param([string]$Message) Write-Host "✗ $Message" -ForegroundColor Red }
function Test-Warn { param([string]$Message) Write-Host "⚠ $Message" -ForegroundColor Yellow }
function Test-Info { param([string]$Message) Write-Host "  $Message" -ForegroundColor Gray }

# ==========================================
# 1. Check frontend build artifacts
# ==========================================
Write-Host "1. Checking frontend build artifacts..." -ForegroundColor White
$DistPath = Join-Path $FrontendDir "dist"

Test-Info "Build directory: $DistPath"
if (Test-Path $DistPath -PathType Container) {
    Test-Pass "Build directory exists"
} else {
    Test-Fail "Build directory missing - run 'npm run build' first"
    exit 1
}

Test-Info "index.html exists"
if (Test-Path (Join-Path $DistPath "index.html") -PathType Leaf) {
    Test-Pass "index.html exists"
} else {
    Test-Fail "index.html missing from build"
    exit 1
}

Test-Info "404.html exists"
if (Test-Path (Join-Path $DistPath "404.html") -PathType Leaf) {
    Test-Pass "404.html exists"
} else {
    Test-Fail "404.html missing - SPA routing won't work"
}

# ==========================================
# 2. Check Pages repo
# ==========================================
Write-Host ""
Write-Host "2. Checking Pages repository..." -ForegroundColor White
$PagesPath = Resolve-Path $PagesRepoPath -ErrorAction SilentlyContinue

Test-Info "Pages repo path: $($PagesPath.Path)"
if ($PagesPath) {
    Test-Pass "Pages repo exists"
} else {
    Test-Warn "Pages repo not found at $PagesRepoPath"
}

Test-Info "Frontend files in Pages repo"
$PagesIndex = Join-Path $PagesPath.Path "index.html" -ErrorAction SilentlyContinue
if ($PagesPath -and (Test-Path $PagesIndex -PathType Leaf)) {
    Test-Pass "Frontend files in Pages repo"
} else {
    Test-Fail "Frontend not copied to Pages repo"
}

Test-Info "runtime-config.json in repo root"
$RuntimeConfig = Join-Path $PagesPath.Path "runtime-config.json" -ErrorAction SilentlyContinue
if ($PagesPath -and (Test-Path $RuntimeConfig -PathType Leaf)) {
    Test-Pass "runtime-config.json in repo root"
    
    $content = Get-Content $RuntimeConfig -Raw -ErrorAction SilentlyContinue
    if ($content -match '"BACKEND_BASE_URL"\s*:\s*"([^"]+)"') {
        $backendUrl = $Matches[1]
        Test-Pass "BACKEND_BASE_URL set: $backendUrl"
    } else {
        Test-Fail "BACKEND_BASE_URL not set"
    }
} else {
    Test-Fail "runtime-config.json missing from repo root"
}

# ==========================================
# 3. Check backend security
# ==========================================
Write-Host ""
Write-Host "3. Verifying backend security..." -ForegroundColor White

Test-Info "Health check: $ApiUrl/health"
try {
    $health = Invoke-RestMethod -Uri "$ApiUrl/health" -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($health.status -eq "ok") {
        Test-Pass "Backend healthy"
    } else {
        Test-Warn "Backend returned: $($health | ConvertTo-Json)"
    }
} catch {
    Test-Fail "Backend health check failed"
}

Test-Info "CORS preflight (allowed origin)"
try {
    $cors = Invoke-WebRequest -Uri "$ApiUrl/v1/chat" -Method Options -Headers @{
        "Origin" = "https://omniplexity.github.io"
        "Access-Control-Request-Method" = "POST"
    } -TimeoutSec 5 -ErrorAction SilentlyContinue
    Test-Pass "CORS preflight OK ($($cors.StatusCode))"
} catch {
    Test-Warn "CORS preflight failed"
}

Test-Info "CORS rejection (evil origin)"
try {
    $corsReject = Invoke-WebRequest -Uri "$ApiUrl/v1/chat" -Method Options -Headers @{
        "Origin" = "https://evil.example.com"
        "Access-Control-Request-Method" = "POST"
    } -TimeoutSec 5 -ErrorAction SilentlyContinue
    Test-Warn "CORS should be rejected but got: $($corsReject.StatusCode)"
} catch {
    $status = [int]$_.Exception.Response.StatusCode
    if ($status -eq 403) {
        Test-Pass "CORS rejection OK (403)"
    } else {
        Test-Warn "Unexpected status: $status"
    }
}

# ==========================================
# Summary
# ==========================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Checklist" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend:" -ForegroundColor White
Write-Host "  [ ] npm run build"
Write-Host "  [ ] cp -r frontend/dist/* ../omniplexity.github.io/"
Write-Host "  [ ] Set BACKEND_BASE_URL in runtime-config.json"
Write-Host ""
Write-Host "GitHub Pages:" -ForegroundColor White
Write-Host "  [ ] Repository: omniplexity/omniplexity.github.io"
Write-Host "  [ ] Branch: main"
Write-Host "  [ ] Actions: Deployment succeeded"
Write-Host ""
Write-Host "Tests:" -ForegroundColor White
Write-Host "  [ ] npm run test (unit tests)"
Write-Host "  [ ] npm run test:e2e (E2E tests - requires backend)"
Write-Host ""
