<#
duckdns_update.ps1 - Robust DuckDNS updater (PowerShell 5.1+ / 7+)

Security + reliability goals:
- Deterministic writable defaults under ProgramData for scheduled task contexts
- Token never printed/logged
- Stable exit codes for automation
- Local state file to avoid redundant updates unless -Force is set

Exit codes:
  0  OK / no-op (already current)
  2  Misconfiguration (missing/invalid token or subdomain)
  3  DuckDNS returned KO (token/subdomain rejected)
  4  Network/IP discovery failure
  5  Unexpected DuckDNS response or internal failure
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $false)]
  [ValidateNotNullOrEmpty()]
  [string]$Subdomain = "omniplexity",

  [Parameter(Mandatory = $false)]
  [string]$Token = $env:DUCKDNS_TOKEN,

  [Parameter(Mandatory = $false)]
  [string]$Ip,

  [Parameter(Mandatory = $false)]
  [string]$LogPath = "",

  [Parameter(Mandatory = $false)]
  [string]$StatePath = "",

  [Parameter(Mandatory = $false)]
  [switch]$Force,

  [Parameter(Mandatory = $false)]
  [ValidateRange(0, 20)]
  [int]$MaxRetries = 3,

  [Parameter(Mandatory = $false)]
  [ValidateRange(1, 60)]
  [int]$TimeoutSec = 15
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ResolvedLogPath = $null
$script:ResolvedStatePath = $null

function Get-DefaultDataRoot {
  # ProgramData works for SYSTEM/service accounts used by Task Scheduler.
  $programData = $env:ProgramData
  if (-not [string]::IsNullOrWhiteSpace($programData)) {
    return (Join-Path $programData "OmniAI")
  }
  # Fallback for unusual environments.
  return (Join-Path $PSScriptRoot "data")
}

function Resolve-PathOrDefault([string]$RequestedPath, [string]$DefaultName) {
  if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
    return $RequestedPath
  }
  $root = Get-DefaultDataRoot
  return (Join-Path $root $DefaultName)
}

function Get-NowTimestamp {
  (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}

function Ensure-ParentDirectory([string]$PathValue) {
  $dir = Split-Path -Parent $PathValue
  if (-not [string]::IsNullOrWhiteSpace($dir) -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
}

function Initialize-Paths {
  $script:ResolvedLogPath = Resolve-PathOrDefault -RequestedPath $LogPath -DefaultName "duckdns.log"
  $script:ResolvedStatePath = Resolve-PathOrDefault -RequestedPath $StatePath -DefaultName "duckdns_state.json"

  try {
    Ensure-ParentDirectory -PathValue $script:ResolvedLogPath
    Ensure-ParentDirectory -PathValue $script:ResolvedStatePath
    if (-not (Test-Path -LiteralPath $script:ResolvedLogPath)) {
      New-Item -ItemType File -Path $script:ResolvedLogPath -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $script:ResolvedStatePath)) {
      "{}" | Set-Content -LiteralPath $script:ResolvedStatePath -Encoding UTF8
    }
  } catch {
    # Last-resort fallback to script directory if ProgramData path is not writable.
    $script:ResolvedLogPath = Join-Path $PSScriptRoot "duckdns.log"
    $script:ResolvedStatePath = Join-Path $PSScriptRoot "duckdns_state.json"
    try {
      Ensure-ParentDirectory -PathValue $script:ResolvedLogPath
      Ensure-ParentDirectory -PathValue $script:ResolvedStatePath
      if (-not (Test-Path -LiteralPath $script:ResolvedLogPath)) {
        New-Item -ItemType File -Path $script:ResolvedLogPath -Force | Out-Null
      }
      if (-not (Test-Path -LiteralPath $script:ResolvedStatePath)) {
        "{}" | Set-Content -LiteralPath $script:ResolvedStatePath -Encoding UTF8
      }
    } catch { }
  }
}

function Write-LogEntry([string]$Message, [string]$Level = "INFO") {
  $line = "[{0}] [{1}] {2}" -f (Get-NowTimestamp), $Level, $Message
  Write-Host $line
  if ($null -ne $script:ResolvedLogPath) {
    try { Add-Content -Path $script:ResolvedLogPath -Value $line -Encoding UTF8 } catch { }
  }
}

function Set-Tls12 {
  try {
    [Net.ServicePointManager]::SecurityProtocol = `
      [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  } catch { }
}

function ConvertTo-Text {
  param([Parameter(Mandatory = $false)]$Value)

  if ($null -eq $Value) { return "" }

  if ($Value -is [string]) { return $Value }

  if ($Value -is [byte[]]) {
    return [System.Text.Encoding]::UTF8.GetString($Value)
  }

  if ($Value -is [char[]]) {
    return -join $Value
  }

  if ($Value -is [System.Array]) {
    # PowerShell casts arrays to space-separated strings; normalize into meaningful text.
    $chars = New-Object System.Collections.Generic.List[char]
    $allNumeric = $true

    foreach ($e in $Value) {
      if ($e -is [byte] -or $e -is [int] -or $e -is [long]) {
        $n = [int]$e
        if ($n -ge 0 -and $n -le 255) {
          $chars.Add([char]$n)
        } else {
          $allNumeric = $false
          break
        }
      } elseif ($e -is [char]) {
        $chars.Add([char]$e)
      } else {
        $allNumeric = $false
        break
      }
    }

    if ($allNumeric -and $chars.Count -gt 0) {
      return (-join $chars.ToArray())
    }

    # Fallback: join elements without spaces
    $parts = @()
    foreach ($e in $Value) { $parts += [string]$e }
    return ($parts -join "")
  }

  return [string]$Value
}

function Get-PublicIp([int]$Timeout) {
  $sources = @(
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://checkip.amazonaws.com"
  )

  foreach ($u in $sources) {
    try {
      $resp = Invoke-WebRequest -UseBasicParsing -Uri $u -Method Get -TimeoutSec $Timeout
      $candidate = ([string]$resp.Content).Trim()
      if ($candidate -match '^\d{1,3}(\.\d{1,3}){3}$') { return $candidate }
    } catch {
      Write-LogEntry ("IP source failed: {0} ({1})" -f $u, $_.Exception.Message) "WARN"
    }
  }

  return $null
}

function Get-State([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $null }
  try {
    $json = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($json)) { return $null }

    $obj = $json | ConvertFrom-Json
    if ($null -eq $obj) { return $null }

    # StrictMode-safe: treat empty object {} as "no state"
    if ($obj.PSObject.Properties.Count -eq 0) { return $null }

    return $obj
  } catch {
    return $null
  }
}

function Get-StateValue {
  param(
    [Parameter(Mandatory = $false)]$Obj,
    [Parameter(Mandatory = $true)][string]$Name
  )

  if ($null -eq $Obj) { return $null }
  $p = $Obj.PSObject.Properties[$Name]
  if ($null -eq $p) { return $null }
  return $p.Value
}

function Set-State([string]$PathValue, [string]$Sub, [string]$IpAddr, [string]$ResponseNorm) {
  try {
    $obj = [ordered]@{
      subdomain = $Sub
      ip        = $IpAddr
      response  = $ResponseNorm
      updatedAt = (Get-Date).ToString("o")
    }
    $obj | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $PathValue -Encoding UTF8
  } catch { }
}

function Invoke-DuckDnsUpdate([string]$Sub, [string]$Tok, [string]$IpAddr, [int]$Timeout, [int]$Retries) {
  # domains= must be the SUBDOMAIN ONLY
  $url = "https://www.duckdns.org/update?domains=$Sub&token=$Tok&ip=$IpAddr"

  for ($i = 0; $i -le $Retries; $i++) {
    try {
      # Invoke-RestMethod avoids the old parsing warning and usually returns a clean string.
      $raw = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $Timeout
      $txt = (ConvertTo-Text -Value $raw).Trim()
      return $txt
    } catch {
      $msg = $_.Exception.Message
      if ($i -lt $Retries) {
        Write-LogEntry ("DuckDNS call failed (attempt {0}/{1}): {2}" -f ($i + 1), ($Retries + 1), $msg) "WARN"
        Start-Sleep -Seconds ([Math]::Min(5, 1 + $i))
        continue
      }
      throw
    }
  }

  return ""
}

# --- Main ---
Set-Tls12
Initialize-Paths

# Single-instance guard (prevents overlapping scheduled task runs)
$mutexName = "Global\DuckDNSUpdate-$Subdomain"
$mutex = New-Object System.Threading.Mutex($false, $mutexName)
$hasLock = $false

try {
  $hasLock = $mutex.WaitOne(0)
  if (-not $hasLock) {
    Write-LogEntry "Another instance is running; exiting." "WARN"
    exit 0
  }

  $Subdomain = $Subdomain.Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($Subdomain)) {
    Write-LogEntry "Subdomain is empty." "ERROR"
    exit 2
  }

  if ($null -eq $Token) { $Token = "" }
  $Token = $Token.Trim()

  if ([string]::IsNullOrWhiteSpace($Token)) {
    Write-LogEntry "DUCKDNS_TOKEN is not set. Set env var DUCKDNS_TOKEN or pass -Token." "ERROR"
    exit 2
  }

  if ($Token.Length -lt 16) {
    Write-LogEntry "DUCKDNS_TOKEN looks too short; refusing to run." "ERROR"
    exit 2
  }

  $hostname = "$Subdomain.duckdns.org"
  Write-LogEntry "Starting DuckDNS update for $hostname"
  Write-LogEntry ("Using log path: {0}" -f $script:ResolvedLogPath)
  Write-LogEntry ("Using state path: {0}" -f $script:ResolvedStatePath)

  if ([string]::IsNullOrWhiteSpace($Ip)) {
    $Ip = Get-PublicIp -Timeout $TimeoutSec
    if ([string]::IsNullOrWhiteSpace($Ip)) {
      Write-LogEntry "Failed to discover public IP from all sources." "ERROR"
      exit 4
    }
  } else {
    $Ip = $Ip.Trim()
  }

  Write-LogEntry "Current public IP: $Ip"

  # Skip if unchanged (unless -Force)
  $state = Get-State -Path $script:ResolvedStatePath
  if (-not $Force -and $null -ne $state) {
    $stateSub = Get-StateValue -Obj $state -Name "subdomain"
    $stateIp  = Get-StateValue -Obj $state -Name "ip"

    if (-not [string]::IsNullOrWhiteSpace($stateSub) -and -not [string]::IsNullOrWhiteSpace($stateIp)) {
      if ($stateSub -eq $Subdomain -and $stateIp -eq $Ip) {
        Write-LogEntry "IP unchanged since last update; skipping (use -Force to override)."
        exit 0
      }
    } else {
      Write-LogEntry "State file present but missing fields; treating as no state." "WARN"
    }
  }

  Write-LogEntry "Calling DuckDNS API (domains=$Subdomain, token=***redacted***)"

  $respText = Invoke-DuckDnsUpdate -Sub $Subdomain -Tok $Token -IpAddr $Ip -Timeout $TimeoutSec -Retries $MaxRetries
  $respNorm = $respText.Trim().ToUpperInvariant()

  Write-LogEntry "DuckDNS response: $respNorm"

  if ($respNorm -eq "OK") {
    Write-LogEntry "DuckDNS update OK: $hostname -> $Ip"
    Set-State -PathValue $script:ResolvedStatePath -Sub $Subdomain -IpAddr $Ip -ResponseNorm $respNorm
    exit 0
  }

  if ($respNorm -eq "KO") {
    Write-LogEntry "DuckDNS returned KO. Token/subdomain mismatch." "ERROR"
    exit 3
  }

  Write-LogEntry ("DuckDNS returned unexpected response: '{0}'" -f $respNorm) "ERROR"
  exit 5
}
catch {
  Write-LogEntry ("Fatal error: {0}" -f $_.Exception.Message) "ERROR"
  exit 5
}
finally {
  if ($hasLock) { try { $mutex.ReleaseMutex() } catch { } }
  try { $mutex.Dispose() } catch { }
}
