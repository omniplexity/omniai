# DuckDNS Scheduled Task Setup
# Creates a Windows scheduled task to update DuckDNS every 5 minutes

$taskName = "DuckDNS Update"
$scriptPath = "$PSScriptRoot\duckdns_update.ps1"
$description = "Updates DuckDNS IP every 5 minutes"

# Create action
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

# Create trigger - repeat every 5 minutes, indefinitely
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

# Register the task
$principal = New-ScheduledTaskPrincipal -RunLevel Highest

Write-Host "Creating scheduled task '$taskName'..."
Write-Host "Script: $scriptPath"
Write-Host "Schedule: Every 5 minutes"

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Description $description `
    -Force

Write-Host ""
Write-Host "Task created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "To view task status:"
Write-Host "  Get-ScheduledTask -TaskName '$taskName' | Get-ScheduledTaskInfo"
Write-Host ""
Write-Host "To run manually:"
Write-Host "  Start-ScheduledTask -TaskName '$taskName'"
Write-Host ""
Write-Host "To delete:"
Write-Host "  Unregister-ScheduledTask -TaskName '$taskName' -Confirm"
