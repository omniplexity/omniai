<#
.SYNOPSIS
  Production smoke checks for OmniAI public API.
.DESCRIPTION
  Validates health, CORS preflight, cross-site auth cookies, and session readback.
  Required env vars:
    SMOKE_USERNAME
    SMOKE_PASSWORD
  Optional env vars:
    SMOKE_BASE_URL (default https://omniplexity.duckdns.org)
    SMOKE_ORIGIN   (default https://omniplexity.github.io)
#>
param()

$ErrorActionPreference = "Stop"

$baseUrl = if ($env:SMOKE_BASE_URL) { $env:SMOKE_BASE_URL } else { "https://omniplexity.duckdns.org" }
$origin = if ($env:SMOKE_ORIGIN) { $env:SMOKE_ORIGIN } else { "https://omniplexity.github.io" }
$username = $env:SMOKE_USERNAME
$password = $env:SMOKE_PASSWORD

function Pass([string]$msg) { Write-Host "PASS: $msg" -ForegroundColor Green }
function Fail([string]$msg) { Write-Host "FAIL: $msg" -ForegroundColor Red; exit 1 }

if ([string]::IsNullOrWhiteSpace($username) -or [string]::IsNullOrWhiteSpace($password)) {
  Write-Host "FAIL: SMOKE_USERNAME and SMOKE_PASSWORD must be set" -ForegroundColor Red
  exit 2
}

$tmp = Join-Path $env:TEMP ("omniai-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$cookieJar = Join-Path $tmp "cookies.txt"
$headersOpts = Join-Path $tmp "opts.headers.txt"
$headersLogin = Join-Path $tmp "login.headers.txt"

try {
  Write-Host "== Smoke: $baseUrl ==" -ForegroundColor Cyan

  # 1) GET /health
  $healthCode = curl.exe -sS -o NUL -w "%{http_code}" "$baseUrl/health"
  if ($healthCode -ne "200") { Fail "GET /health returned $healthCode" }
  Pass "GET /health -> 200"

  # 2) OPTIONS /v1/auth/login
  $optsCode = curl.exe -sS -D $headersOpts -o NUL -w "%{http_code}" `
    -X OPTIONS "$baseUrl/v1/auth/login" `
    -H "Origin: $origin" `
    -H "Access-Control-Request-Method: POST" `
    -H "Access-Control-Request-Headers: content-type,x-csrf-token"
  if ($optsCode -ne "200") { Fail "OPTIONS /v1/auth/login returned $optsCode" }

  $optsHeaderText = Get-Content $headersOpts -Raw
  if ($optsHeaderText -notmatch "(?im)^Access-Control-Allow-Origin:\s*$([regex]::Escape($origin))\s*$") { Fail "Missing/invalid Access-Control-Allow-Origin" }
  if ($optsHeaderText -notmatch "(?im)^Access-Control-Allow-Credentials:\s*true\s*$") { Fail "Missing Access-Control-Allow-Credentials: true" }
  if ($optsHeaderText -notmatch "(?im)^Vary:\s*.*Origin") { Fail "Missing Vary: Origin" }
  if ($optsHeaderText -notmatch "(?im)^Access-Control-Allow-Methods:\s*.*POST.*OPTIONS") { Fail "Allow-Methods missing POST/OPTIONS" }
  if ($optsHeaderText -notmatch "(?im)^Access-Control-Allow-Headers:\s*.*content-type") { Fail "Allow-Headers missing content-type" }
  if ($optsHeaderText -notmatch "(?im)^Access-Control-Allow-Headers:\s*.*x-csrf-token") { Fail "Allow-Headers missing x-csrf-token" }
  Pass "OPTIONS /v1/auth/login headers validated"

  # 3) POST /v1/auth/login
  $payload = (@{ username = $username; password = $password } | ConvertTo-Json -Compress)
  $loginCode = curl.exe -sS -D $headersLogin -o NUL -w "%{http_code}" `
    -c $cookieJar `
    -X POST "$baseUrl/v1/auth/login" `
    -H "Origin: $origin" `
    -H "Content-Type: application/json" `
    --data $payload
  if ($loginCode -ne "200") { Fail "POST /v1/auth/login returned $loginCode" }

  $loginHeaderText = Get-Content $headersLogin -Raw
  if ($loginHeaderText -notmatch "(?im)^Set-Cookie:\s*omni_session=.*HttpOnly;.*SameSite=None;\s*Secure") { Fail "Missing/invalid omni_session Set-Cookie" }
  if ($loginHeaderText -notmatch "(?im)^Set-Cookie:\s*omni_csrf=.*SameSite=None;\s*Secure") { Fail "Missing/invalid omni_csrf Set-Cookie" }
  Pass "POST /v1/auth/login emitted both cookies"

  # 4) GET /v1/auth/me with cookie jar
  $meCode = curl.exe -sS -o NUL -w "%{http_code}" `
    -b $cookieJar `
    -H "Origin: $origin" `
    "$baseUrl/v1/auth/me"
  if ($meCode -ne "200") { Fail "GET /v1/auth/me returned $meCode" }
  Pass "GET /v1/auth/me with cookie jar -> 200"

  Write-Host "Smoke PASS" -ForegroundColor Green
}
finally {
  if (Test-Path $tmp) { Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}

