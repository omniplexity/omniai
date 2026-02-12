param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$BackendUrl = "http://127.0.0.1:8000",
  [string]$FrontendUrl = "http://127.0.0.1:5173",
  [string]$TestDbUrl = "sqlite:///./.test/omniai_e2e.sqlite3",
  [string]$E2EUsername = "e2e@example.com",
  [string]$E2EPassword = "e2e-password"
)

$ErrorActionPreference = "Stop"

$backendProc = $null
$frontendProc = $null
$runtimeConfigPath = Join-Path $RepoRoot "frontend/public/runtime-config.json"
$runtimeConfigBackup = $null

function Stop-IfRunning {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn) {
    Stop-Process -Id $conn.OwningProcess -Force
    Start-Sleep -Seconds 1
  }
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [int]$Seconds = 60
  )
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $res = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 2 -SkipHttpErrorCheck
      if ($res.StatusCode -ge 200 -and $res.StatusCode -lt 500) {
        return
      }
    } catch {
      Start-Sleep -Milliseconds 500
      continue
    }
    Start-Sleep -Milliseconds 500
  }
  throw "Timeout waiting for $Url"
}

try {
  New-Item -ItemType Directory -Path (Join-Path $RepoRoot ".test") -Force | Out-Null

  Push-Location (Join-Path $RepoRoot "backend")
  $env:PYTHONPATH = ".."
  $env:DATABASE_URL = "sqlite:///./../.test/omniai_e2e.sqlite3"
  $env:DATABASE_URL_POSTGRES = ""
  alembic upgrade head
  Pop-Location

  Stop-IfRunning -Port 8000
  Stop-IfRunning -Port 5173

  $env:ENVIRONMENT = "test"
  $env:E2E_SEED_USER = "1"
  $env:E2E_USERNAME = $E2EUsername
  $env:E2E_PASSWORD = $E2EPassword
  $env:COOKIE_SECURE = "false"
  $env:COOKIE_SAMESITE = "lax"
  $env:CORS_ORIGINS = "https://omniplexity.github.io"
  $env:LIMITS_BACKEND = "memory"
  $env:DATABASE_URL = $TestDbUrl
  $env:DATABASE_URL_POSTGRES = ""

  $backendProc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $RepoRoot `
    -PassThru

  Wait-HttpOk -Url "$BackendUrl/health"

  Push-Location (Join-Path $RepoRoot "frontend")
  if (Test-Path $runtimeConfigPath) {
    $runtimeConfigBackup = Get-Content $runtimeConfigPath -Raw
  }
  node ../scripts/inject-build-info.js public/runtime-config.json --backend-base-url $BackendUrl
  $frontendProc = Start-Process -FilePath "npm" `
    -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173" `
    -WorkingDirectory (Get-Location).Path `
    -PassThru
  Pop-Location

  Wait-HttpOk -Url $FrontendUrl

  Push-Location (Join-Path $RepoRoot "frontend")
  $env:FRONTEND_URL = $FrontendUrl
  $env:E2E_BASE_URL = $BackendUrl
  npx playwright test tests/e2e/workspace-smoke.spec.ts --project=chromium
  Pop-Location
}
finally {
  if ($runtimeConfigBackup -ne $null) {
    Set-Content -Path $runtimeConfigPath -Value $runtimeConfigBackup -Encoding utf8
  }
  if ($frontendProc -and -not $frontendProc.HasExited) {
    Stop-Process -Id $frontendProc.Id -Force
  }
  if ($backendProc -and -not $backendProc.HasExited) {
    Stop-Process -Id $backendProc.Id -Force
  }
}
