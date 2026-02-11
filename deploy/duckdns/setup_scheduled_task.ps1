# Backward-compatible wrapper.
# Use setup_duckdns_task.ps1 for current secure configuration.

$target = Join-Path $PSScriptRoot "setup_duckdns_task.ps1"
if (-not (Test-Path -LiteralPath $target)) {
    Write-Host "[ERROR] Missing target script: $target" -ForegroundColor Red
    exit 1
}

& $target @args
exit $LASTEXITCODE
