<#
setup_duckdns_task.ps1 - Create/update DuckDNS scheduled task for OmniAI.

Requirements:
- Run elevated PowerShell (Administrator) for machine env + task registration.
- DUCKDNS_TOKEN must exist at Machine scope.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $false)]
  [string]$TaskName = "OmniAI DuckDNS Update",

  [Parameter(Mandatory = $false)]
  [string]$Subdomain = "omniplexity",

  [Parameter(Mandatory = $false)]
  [ValidateRange(1, 60)]
  [int]$EveryMinutes = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
  Write-Host "[INFO] $Message"
}

function Write-ErrorLine([string]$Message) {
  Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Get-MachineDuckDnsToken {
  return [Environment]::GetEnvironmentVariable("DUCKDNS_TOKEN", "Machine")
}

$scriptPath = Join-Path $PSScriptRoot "duckdns_update.ps1"
if (-not (Test-Path -LiteralPath $scriptPath)) {
  Write-ErrorLine "Updater script not found: $scriptPath"
  exit 1
}

$token = Get-MachineDuckDnsToken
if ([string]::IsNullOrWhiteSpace($token)) {
  Write-ErrorLine "DUCKDNS_TOKEN is missing at Machine scope."
  Write-Host ""
  Write-Host "Set it (run elevated PowerShell):"
  Write-Host '  [Environment]::SetEnvironmentVariable("DUCKDNS_TOKEN", "<your_token>", "Machine")'
  Write-Host ""
  Write-Host "Then restart PowerShell and rerun this setup script."
  exit 2
}

if ($token.Trim().Length -lt 16) {
  Write-ErrorLine "DUCKDNS_TOKEN appears too short. Validate the configured token."
  exit 2
}

$dataRoot = Join-Path $env:ProgramData "OmniAI"
$logPath = Join-Path $dataRoot "duckdns.log"
$statePath = Join-Path $dataRoot "duckdns_state.json"

if (-not (Test-Path -LiteralPath $dataRoot)) {
  New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
}

$actionArgs = @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-File", "`"$scriptPath`"",
  "-Subdomain", "`"$Subdomain`"",
  "-LogPath", "`"$logPath`"",
  "-StatePath", "`"$statePath`""
) -join " "

$taskCommand = "powershell.exe $actionArgs"

Write-Info "Registering scheduled task '$TaskName'"
$schtasksArgs = @(
  "/Create",
  "/TN", $TaskName,
  "/TR", $taskCommand,
  "/SC", "MINUTE",
  "/MO", "$EveryMinutes",
  "/RU", "SYSTEM",
  "/F"
)

$null = & schtasks.exe $schtasksArgs
if ($LASTEXITCODE -ne 0) {
  Write-ErrorLine "Failed to register scheduled task (exit code $LASTEXITCODE). Run PowerShell as Administrator."
  exit 3
}

Write-Host ""
Write-Info "Task configured."
Write-Info "Script: $scriptPath"
Write-Info "Log:    $logPath"
Write-Info "State:  $statePath"
Write-Host ""
Write-Host "Verify commands:"
Write-Host "  Get-ScheduledTask -TaskName `"$TaskName`" | Format-List"
Write-Host "  Get-ScheduledTaskInfo -TaskName `"$TaskName`" | Format-List"
Write-Host "  Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "  Get-Content -Path `"$logPath`" -Tail 40"
