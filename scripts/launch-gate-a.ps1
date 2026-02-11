param(
  [string]$BaseUrl = $(if ($env:BASE_URL) { $env:BASE_URL } elseif ($env:API_BASE_URL) { $env:API_BASE_URL } else { "https://omniplexity.duckdns.org" }),
  [string]$Mode = $(if ($env:GATE_A_MODE) { $env:GATE_A_MODE } else { "preflight" }),
  [string]$Username = $(if ($env:SMOKE_USERNAME) { $env:SMOKE_USERNAME } elseif ($env:E2E_USERNAME) { $env:E2E_USERNAME } else { "" }),
  [string]$Password = $(if ($env:SMOKE_PASSWORD) { $env:SMOKE_PASSWORD } elseif ($env:E2E_PASSWORD) { $env:E2E_PASSWORD } else { "" }),
  [string]$OriginsCsv = $(if ($env:ORIGINS_CSV) { $env:ORIGINS_CSV } elseif ($env:ORIGINS) { $env:ORIGINS } else { "https://omniplexity.github.io" }),
  [string]$AllowedOrigins = $(if ($env:ALLOWED_ORIGINS) { $env:ALLOWED_ORIGINS } else { "https://omniplexity.github.io" }),
  [string]$OutDir = $(if ($env:OUT_DIR) { $env:OUT_DIR } else { "artifacts/launch-gate-a" })
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$matrixFile = Join-Path $OutDir "matrix-$stamp.md"
$healthLog = Join-Path $OutDir "health-$stamp.log"

@(
  "# Gate A Matrix ($stamp)",
  "",
  "Mode: ``$Mode``",
  "",
  "| Origin | Expected | Preflight | Login/Smoke | Notes | Overall | Log |",
  "| --- | --- | --- | --- | --- | --- | --- |"
) | Set-Content $matrixFile

try {
  $health = Invoke-WebRequest -Uri "$BaseUrl/health" -Method GET -TimeoutSec 15 -ErrorAction Stop
  $health.Content | Set-Content $healthLog
  Add-Content $matrixFile "Health check: PASS (``$BaseUrl/health``)"
} catch {
  $_ | Out-String | Set-Content $healthLog
  Add-Content $matrixFile "Health check: FAIL (``$BaseUrl/health``) - see ``$healthLog``"
}
Add-Content $matrixFile ""

$allowedSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$AllowedOrigins.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ } | ForEach-Object { [void]$allowedSet.Add($_) }
$origins = $OriginsCsv.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
foreach ($origin in $origins) {
  $safeName = ($origin -replace '^https?://', '' -replace '[^A-Za-z0-9._-]', '_')
  $logFile = Join-Path $OutDir "smoke-$safeName-$stamp.log"
  $preflightPass = $false
  $smokeResult = "SKIP"
  $notes = New-Object System.Collections.Generic.List[string]
  $expected = if ($allowedSet.Contains($origin)) { "allowed" } else { "disallowed" }

  $statusCode = 0
  $acao = $null
  $acac = $null
  $vary = $null

  try {
    $resp = Invoke-WebRequest -Uri "$BaseUrl/v1/auth/login" -Method OPTIONS -Headers @{
      Origin = $origin
      "Access-Control-Request-Method" = "POST"
      "Access-Control-Request-Headers" = "content-type,x-csrf-token"
    } -ErrorAction Stop
    $statusCode = [int]$resp.StatusCode
    $acao = $resp.Headers["Access-Control-Allow-Origin"]
    $acac = $resp.Headers["Access-Control-Allow-Credentials"]
    $vary = $resp.Headers["Vary"]
  } catch {
    $response = $_.Exception.Response
    if ($response) {
      $statusCode = [int]$response.StatusCode
      $acao = $response.Headers["Access-Control-Allow-Origin"]
      $acac = $response.Headers["Access-Control-Allow-Credentials"]
      $vary = $response.Headers["Vary"]
    } else {
      $notes.Add("Preflight request failed before HTTP response")
    }
  }

  if ($expected -eq "allowed") {
    if ($statusCode -ge 200 -and $statusCode -lt 300 -and $acao -eq $origin -and "$acac".ToLowerInvariant() -eq "true" -and "$vary".ToLowerInvariant().Contains("origin")) {
      $preflightPass = $true
    } else {
      $notes.Add("Allowed CORS headers/status mismatch")
    }
  } else {
    if ([string]::IsNullOrWhiteSpace($acao) -and [string]::IsNullOrWhiteSpace($acac)) {
      $preflightPass = $true
    } else {
      $notes.Add("Disallowed origin unexpectedly received credentialed CORS headers")
    }
  }

  if ($Mode -eq "smoke" -and $expected -eq "allowed") {
    if ([string]::IsNullOrWhiteSpace($Username) -or [string]::IsNullOrWhiteSpace($Password)) {
      $smokeResult = "FAIL"
      $notes.Add("Missing SMOKE_USERNAME/SMOKE_PASSWORD")
    } else {
      try {
        $env:ORIGIN = $origin
        $env:BASE_URL = $BaseUrl
        $env:E2E_USERNAME = $Username
        $env:E2E_PASSWORD = $Password
        & "$PSScriptRoot/smoke-frontend.ps1" *>&1 | Tee-Object -FilePath $logFile | Out-Null
        $smokeResult = "PASS"
      } catch {
        $smokeResult = "FAIL"
      }
    }
  }

  $preflightLabel = if ($preflightPass) { "PASS" } else { "FAIL" }
  $overall = if ($preflightPass -and ($smokeResult -eq "SKIP" -or $smokeResult -eq "PASS")) { "PASS" } else { "FAIL" }
  $noteText = if ($notes.Count -gt 0) { ($notes -join "; ") } else { "-" }
  Add-Content $matrixFile "| $origin | $expected | $preflightLabel | $smokeResult | $noteText | $overall | ``$logFile`` |"
}

Write-Host "Wrote $matrixFile"
