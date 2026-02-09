# DuckDNS Update Script
# Updates DuckDNS with current public IP every 5 minutes
#
# Usage:
#   - Run manually: .\duckdns_update.ps1
#   - Or schedule with: .\setup_scheduled_task.ps1
#
# Logs are written to: .\duckdns.log

$ErrorActionPreference = "Stop"

# Configuration
$domain = "omniplexity"
$token = "REDACTED_DUCKDNS_TOKEN"
$logFile = "$PSScriptRoot\duckdns.log"

# Build the update URL
$url = "https://www.duckdns.org/update?domains=$domain&token=$token&ip="

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Write-Host $logEntry
    Add-Content -Path $logFile -Value $logEntry
}

try {
    Write-Log "Starting DuckDNS update for $domain.duckdns.org"
    
    # Get current public IP
    $publicIP = (Invoke-WebRequest -Uri "https://api.ipify.org" -TimeoutSec 10).Content.Trim()
    Write-Log "Current public IP: $publicIP"
    
    # Update DuckDNS
    $updateUrl = "$url$publicIP"
    Write-Log "Calling DuckDNS API..."
    
    $response = Invoke-WebRequest -UseBasicParsing -Uri $updateUrl -TimeoutSec 30
    
    Write-Log "DuckDNS response: $($response.Content)"
    
    if ($response.Content -match "^OK") {
        Write-Log "DuckDNS update successful"
    } else {
        throw "DuckDNS returned unexpected response: $($response.Content)"
    }
}
catch {
    Write-Log "ERROR: $_"
    throw
}

Write-Log "DuckDNS update completed"
