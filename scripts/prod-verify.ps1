param(
  [string]$LocalBaseUrl = "http://127.0.0.1:8000",
  [string]$PublicBaseUrl = "https://omniplexity.duckdns.org",
  [string]$Origin = "https://omniplexity.github.io"
)

$ErrorActionPreference = "Stop"
$failures = 0

function Run-Check {
  param(
    [string]$Name,
    [string]$Url,
    [string]$Method = "GET",
    [hashtable]$Headers = @{},
    [int]$ExpectedStatus = 200,
    [hashtable]$RequiredHeaders = @{}
  )

  try {
    $res = Invoke-WebRequest -Uri $Url -Method $Method -Headers $Headers -SkipHttpErrorCheck -TimeoutSec 20
  } catch {
    Write-Host "[FAIL] $Name - request error: $($_.Exception.Message)" -ForegroundColor Red
    $script:failures += 1
    return
  }

  $ok = $true
  if ($res.StatusCode -ne $ExpectedStatus) {
    $ok = $false
    Write-Host "[FAIL] $Name - expected status $ExpectedStatus got $($res.StatusCode)" -ForegroundColor Red
  }

  foreach ($key in $RequiredHeaders.Keys) {
    $expected = $RequiredHeaders[$key]
    $actual = $res.Headers[$key]
    if ([string]::IsNullOrWhiteSpace($actual)) {
      $ok = $false
      Write-Host "[FAIL] $Name - missing header '$key'" -ForegroundColor Red
      continue
    }
    if ($actual -ne $expected) {
      $ok = $false
      Write-Host "[FAIL] $Name - header '$key' expected '$expected' got '$actual'" -ForegroundColor Red
    }
  }

  if ($ok) {
    Write-Host "[PASS] $Name ($($res.StatusCode))" -ForegroundColor Green
  } else {
    $script:failures += 1
  }
}

Write-Host "Running production verification..." -ForegroundColor Cyan
Write-Host "Local:  $LocalBaseUrl"
Write-Host "Public: $PublicBaseUrl"
Write-Host "Origin: $Origin"
Write-Host ""

Run-Check -Name "Local /health" -Url "$LocalBaseUrl/health"
Run-Check -Name "Local /v1/meta" -Url "$LocalBaseUrl/v1/meta"
Run-Check -Name "Public /health" -Url "$PublicBaseUrl/health"
Run-Check -Name "Public /v1/meta" -Url "$PublicBaseUrl/v1/meta"
Run-Check -Name "Public /v1/meta (Origin)" -Url "$PublicBaseUrl/v1/meta" -Headers @{ Origin = $Origin } -RequiredHeaders @{
  "Access-Control-Allow-Origin" = $Origin
  "Access-Control-Allow-Credentials" = "true"
}
Run-Check -Name "Public /v1/auth/csrf/bootstrap (Origin)" -Url "$PublicBaseUrl/v1/auth/csrf/bootstrap" -Headers @{ Origin = $Origin } -RequiredHeaders @{
  "Access-Control-Allow-Origin" = $Origin
  "Access-Control-Allow-Credentials" = "true"
}

# Vary can include multiple values; check it contains Origin.
try {
  $varyRes = Invoke-WebRequest -Uri "$PublicBaseUrl/v1/meta" -Method GET -Headers @{ Origin = $Origin } -SkipHttpErrorCheck -TimeoutSec 20
  $vary = $varyRes.Headers["Vary"]
  if ([string]::IsNullOrWhiteSpace($vary) -or ($vary -notmatch "(^|,\s*)Origin(\s*,|$)")) {
    Write-Host "[FAIL] Public /v1/meta (Origin) - Vary header does not include Origin" -ForegroundColor Red
    $failures += 1
  } else {
    Write-Host "[PASS] Public /v1/meta (Origin) - Vary includes Origin" -ForegroundColor Green
  }
} catch {
  Write-Host "[FAIL] Public /v1/meta (Origin) - error checking Vary: $($_.Exception.Message)" -ForegroundColor Red
  $failures += 1
}

Write-Host ""
if ($failures -gt 0) {
  Write-Host "Verification FAILED ($failures check(s))." -ForegroundColor Red
  exit 1
}

Write-Host "Verification PASSED." -ForegroundColor Green
exit 0
