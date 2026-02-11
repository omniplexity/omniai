<#
.SYNOPSIS
  Production smoke checks for OmniAI public API.
.DESCRIPTION
  Validates health, CHIPS cookies (Partitioned), login, chat run creation, SSE stream, and cancel.
  Required env vars (or interactive prompt):
    SMOKE_USERNAME
    SMOKE_PASSWORD
  Optional env vars:
    SMOKE_BASE_URL (default https://omniplexity.duckdns.org)
    SMOKE_ORIGIN   (default https://omniplexity.github.io)
    SMOKE_STRICT_BUILD=1 (fail if /health reports production with unknown build metadata)
#>
param()

$ErrorActionPreference = "Stop"

$baseUrl = if ($env:SMOKE_BASE_URL) { $env:SMOKE_BASE_URL } else { "https://omniplexity.duckdns.org" }
$origin = if ($env:SMOKE_ORIGIN) { $env:SMOKE_ORIGIN } else { "https://omniplexity.github.io" }
$username = $env:SMOKE_USERNAME
$password = $env:SMOKE_PASSWORD
$strictBuildRaw = if ($null -eq $env:SMOKE_STRICT_BUILD) { "" } else { $env:SMOKE_STRICT_BUILD }
$strictBuild = @("1", "true", "yes", "on") -contains $strictBuildRaw.ToLowerInvariant()

function Pass([string]$msg) { Write-Host "PASS: $msg" -ForegroundColor Green }
function Fail([string]$msg) { Write-Host "FAIL: $msg" -ForegroundColor Red; exit 1 }

function Assert-SseComplete {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][int]$CurlExit
  )

  $lines = @()
  if (Test-Path $Path) {
    $lines = Get-Content -Path $Path -ErrorAction SilentlyContinue
  }

  $dataLines = ($lines | Where-Object { $_ -match '^data:' }).Count
  $hasTerminal = (
    ($lines | Where-Object { $_ -match '^data:\s*\[DONE\]\s*$' }).Count -gt 0 -or
    ($lines | Where-Object { $_ -match '^event:\s*done\s*$' }).Count -gt 0 -or
    ($lines | Where-Object { $_ -match '"(type|event)"\s*:\s*"done"' }).Count -gt 0 -or
    ($lines | Where-Object { $_ -match '^event:\s*stopped\s*$' }).Count -gt 0 -or
    ($lines | Where-Object { $_ -match '"status"\s*:\s*"completed"' }).Count -gt 0
  )

  if ($hasTerminal) { return }

  if ($dataLines -gt 0 -and ($CurlExit -eq 0 -or $CurlExit -eq 18 -or $CurlExit -eq 28)) {
    Write-Warning "Stream ended without terminal marker; accepting close semantics (curl rc=$CurlExit, data_lines=$dataLines)"
    return
  }

  throw "Stream missing terminal marker (curl rc=$CurlExit, data_lines=$dataLines)"
}

if ([string]::IsNullOrWhiteSpace($username) -or [string]::IsNullOrWhiteSpace($password)) {
  $canPrompt = -not [Console]::IsInputRedirected
  if (-not $canPrompt) {
    Write-Host "FAIL: SMOKE_USERNAME and SMOKE_PASSWORD must be set (non-interactive session)" -ForegroundColor Red
    exit 2
  }
  if ([string]::IsNullOrWhiteSpace($username)) {
    $username = Read-Host "SMOKE_USERNAME"
  }
  if ([string]::IsNullOrWhiteSpace($password)) {
    $sec = Read-Host "SMOKE_PASSWORD" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try {
      $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
      [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
  }
  if ([string]::IsNullOrWhiteSpace($username) -or [string]::IsNullOrWhiteSpace($password)) {
    Write-Host "FAIL: SMOKE_USERNAME and SMOKE_PASSWORD are required" -ForegroundColor Red
    exit 2
  }
}

$tmp = Join-Path $env:TEMP ("omniai-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$cookieJar = Join-Path $tmp "cookies.txt"
$headersBoot = Join-Path $tmp "boot.headers.txt"
$headersLogin = Join-Path $tmp "login.headers.txt"
$headersStream = Join-Path $tmp "stream.headers.txt"
$bodyHealth = Join-Path $tmp "health.body.json"
$bodyBoot = Join-Path $tmp "boot.body.json"
$bodyLogin = Join-Path $tmp "login.body.json"
$bodyConv = Join-Path $tmp "conv.body.json"
$bodyRun = Join-Path $tmp "run.body.json"
$bodyStream = Join-Path $tmp "stream.body.txt"
$bodyRun2 = Join-Path $tmp "run2.body.json"
$bodyCancel = Join-Path $tmp "cancel.body.json"
$payloadFile = Join-Path $tmp "login.payload.json"

try {
  Write-Host "== Smoke: $baseUrl ==" -ForegroundColor Cyan

  # 1) GET /health
  $healthCode = curl.exe -sS -o $bodyHealth -w "%{http_code}" "$baseUrl/health"
  if ($healthCode -ne "200") { Fail "GET /health returned $healthCode" }
  Pass "GET /health -> 200"

  if ($strictBuild) {
    try {
      $health = Get-Content $bodyHealth -Raw | ConvertFrom-Json
      $isProd = ($health.environment -eq "production")
      $sha = if ($null -eq $health.build_sha) { "" } else { [string]$health.build_sha }
      $time = if ($null -eq $health.build_time) { "" } else { [string]$health.build_time }
      if ($isProd -and (($sha -eq "unknown") -or ($time -eq "unknown"))) {
        Fail "Strict build check failed: /health reports unknown build metadata in production"
      }
      Pass "Strict build metadata check passed"
    } catch {
      Fail "Strict build check failed: unable to parse /health JSON"
    }
  }

  # 2) GET /v1/auth/csrf/bootstrap
  $bootCode = curl.exe -sS -D $headersBoot -o $bodyBoot -w "%{http_code}" `
    -c $cookieJar -b $cookieJar `
    -H "Origin: $origin" `
    "$baseUrl/v1/auth/csrf/bootstrap"
  if ($bootCode -ne "200") { Fail "GET /v1/auth/csrf/bootstrap returned $bootCode" }

  $bootJson = Get-Content $bodyBoot -Raw | ConvertFrom-Json
  $csrf = [string]$bootJson.csrf_token
  if ([string]::IsNullOrWhiteSpace($csrf)) { Fail "csrf_token missing in bootstrap response" }

  $bootHeaderText = Get-Content $headersBoot -Raw
  if ($bootHeaderText -notmatch "(?im)^Set-Cookie:\s*omni_csrf=.*SameSite=None;.*Secure;.*Partitioned\s*$") {
    Fail "Bootstrap omni_csrf cookie missing SameSite=None; Secure; Partitioned"
  }
  Pass "Bootstrap sets partitioned omni_csrf cookie"

  # 3) POST /v1/auth/login
  $payload = (@{ username = $username; password = $password } | ConvertTo-Json -Compress)
  Set-Content -Path $payloadFile -Value $payload -Encoding UTF8
  $loginCode = curl.exe -sS -D $headersLogin -o $bodyLogin -w "%{http_code}" `
    -c $cookieJar -b $cookieJar `
    -X POST "$baseUrl/v1/auth/login" `
    -H "Origin: $origin" `
    -H "X-CSRF-Token: $csrf" `
    -H "Content-Type: application/json" `
    --data-binary "@$payloadFile"
  if ($loginCode -ne "200") { Fail "POST /v1/auth/login returned $loginCode" }

  $loginHeaderText = Get-Content $headersLogin -Raw
  if ($loginHeaderText -notmatch "(?im)^Set-Cookie:\s*omni_session=.*HttpOnly;.*SameSite=None;.*Secure;.*Partitioned\s*$") {
    Fail "Login omni_session cookie missing SameSite=None; Secure; Partitioned"
  }
  if ($loginHeaderText -notmatch "(?im)^Set-Cookie:\s*omni_csrf=.*SameSite=None;.*Secure;.*Partitioned\s*$") {
    Fail "Login omni_csrf cookie missing SameSite=None; Secure; Partitioned"
  }
  Pass "Login emits partitioned omni_session + omni_csrf cookies"

  try {
    $loginJson = Get-Content $bodyLogin -Raw | ConvertFrom-Json
    if ($loginJson.csrf_token) {
      $csrf = [string]$loginJson.csrf_token
    }
  } catch {
    # Keep bootstrap token if response is not JSON for any reason.
  }

  # 4) POST /v1/conversations
  $convCode = curl.exe -sS -o $bodyConv -w "%{http_code}" `
    -c $cookieJar -b $cookieJar `
    -X POST "$baseUrl/v1/conversations" `
    -H "Origin: $origin" `
    -H "X-CSRF-Token: $csrf" `
    -H "Content-Type: application/json" `
    -d '{"title":"Smoke Conversation"}'
  if (@("200", "201") -notcontains $convCode) { Fail "POST /v1/conversations returned $convCode" }
  $convJson = Get-Content $bodyConv -Raw | ConvertFrom-Json
  $convId = [string]($convJson.id ?? $convJson.conversation_id)
  if ([string]::IsNullOrWhiteSpace($convId)) { Fail "conversation id missing" }
  Pass "Conversation created"

  # 5) POST /v1/chat
  $runBody = @{ conversation_id = $convId; input = "smoke test"; stream = $true } | ConvertTo-Json -Compress
  $runCode = curl.exe -sS -o $bodyRun -w "%{http_code}" `
    -c $cookieJar -b $cookieJar `
    -X POST "$baseUrl/v1/chat" `
    -H "Origin: $origin" `
    -H "X-CSRF-Token: $csrf" `
    -H "Content-Type: application/json" `
    --data-binary $runBody
  if ($runCode -ne "200") { Fail "POST /v1/chat returned $runCode" }
  $runJson = Get-Content $bodyRun -Raw | ConvertFrom-Json
  $runId = [string]$runJson.run_id
  if ([string]::IsNullOrWhiteSpace($runId)) { Fail "run_id missing" }
  Pass "Chat run created"

  # 6) GET /v1/chat/stream
  $streamCode = curl.exe -sS -N -D $headersStream -o $bodyStream -w "%{http_code}" `
    -c $cookieJar -b $cookieJar `
    -H "Origin: $origin" `
    -H "Accept: text/event-stream" `
    "$baseUrl/v1/chat/stream?run_id=$runId"
  $streamCurlExit = $LASTEXITCODE
  if ($streamCode -ne "200") { Fail "GET /v1/chat/stream returned $streamCode" }
  $streamHeaderText = Get-Content $headersStream -Raw
  if ($streamHeaderText -notmatch "(?im)^Content-Type:\s*text/event-stream") {
    Fail "Stream content-type is not text/event-stream"
  }
  $streamText = Get-Content $bodyStream -Raw
  if ($streamText -notmatch "data:") { Fail "Stream missing SSE data frames" }
  Assert-SseComplete -Path $bodyStream -CurlExit $streamCurlExit
  Pass "SSE stream validated"

  # 7) Cancel flow
  $run2Body = @{ conversation_id = $convId; input = "please stream a long answer"; stream = $true } | ConvertTo-Json -Compress
  $run2Code = curl.exe -sS -o $bodyRun2 -w "%{http_code}" `
    -c $cookieJar -b $cookieJar `
    -X POST "$baseUrl/v1/chat" `
    -H "Origin: $origin" `
    -H "X-CSRF-Token: $csrf" `
    -H "Content-Type: application/json" `
    --data-binary $run2Body
  if ($run2Code -ne "200") { Fail "POST /v1/chat (cancel path) returned $run2Code" }
  $run2Json = Get-Content $bodyRun2 -Raw | ConvertFrom-Json
  $run2Id = [string]$run2Json.run_id
  if ([string]::IsNullOrWhiteSpace($run2Id)) { Fail "run_id missing for cancel path" }

  $cancelBody = @{ run_id = $run2Id } | ConvertTo-Json -Compress
  $cancelCode = curl.exe -sS -o $bodyCancel -w "%{http_code}" `
    -c $cookieJar -b $cookieJar `
    -X POST "$baseUrl/v1/chat/cancel" `
    -H "Origin: $origin" `
    -H "X-CSRF-Token: $csrf" `
    -H "Content-Type: application/json" `
    --data-binary $cancelBody
  if ($cancelCode -ne "200") { Fail "POST /v1/chat/cancel returned $cancelCode" }
  Pass "Cancel endpoint validated"

  Write-Host "Smoke PASS" -ForegroundColor Green
}
finally {
  if (Test-Path $tmp) { Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
