param(
  [string]$BaseUrl = $(if ($env:BASE_URL) { $env:BASE_URL } else { "http://127.0.0.1:8000" }),
  [string]$Username = $(if ($env:E2E_USERNAME) { $env:E2E_USERNAME } else { "ci_e2e_user" }),
  [string]$Password = $(if ($env:E2E_PASSWORD) { $env:E2E_PASSWORD } else { "ci_e2e_pass" }),
  [string]$Origin = $(if ($env:ORIGIN) { $env:ORIGIN } else { "http://127.0.0.1:4173" })
)

$ErrorActionPreference = "Stop"

function Step($text) { Write-Host $text -ForegroundColor Cyan }

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

Step "[1/7] CSRF bootstrap"
$csrfResp = Invoke-RestMethod -Method Get -Uri "$BaseUrl/v1/auth/csrf/bootstrap" -Headers @{ Origin = $Origin } -WebSession $session
$csrf = $csrfResp.csrf_token
if (-not $csrf) { throw "Missing csrf_token" }
if (-not ($session.Cookies.GetCookies($BaseUrl) | Where-Object { $_.Name -eq "omni_csrf" })) {
  throw "Missing omni_csrf cookie after bootstrap"
}

Step "[2/7] Login"
Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/auth/login" -WebSession $session -Headers @{
  Origin = $Origin
  "X-CSRF-Token" = $csrf
  "Content-Type" = "application/json"
} -Body (@{ username = $Username; password = $Password } | ConvertTo-Json)

Step "[3/7] Create conversation"
$conv = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/conversations" -WebSession $session -Headers @{
  Origin = $Origin
  "X-CSRF-Token" = $csrf
  "Content-Type" = "application/json"
} -Body (@{ title = "Smoke Conversation" } | ConvertTo-Json)
if (-not $conv.id) { throw "Missing conversation id" }

Step "[4/7] Create run"
$run = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/chat" -WebSession $session -Headers @{
  Origin = $Origin
  "X-CSRF-Token" = $csrf
  "Content-Type" = "application/json"
} -Body (@{ conversation_id = $conv.id; input = "smoke test"; stream = $true } | ConvertTo-Json)
if (-not $run.run_id) { throw "Missing run_id" }

Step "[5/7] Stream run"
$streamResp = Invoke-WebRequest -Method Get -Uri "$BaseUrl/v1/chat/stream?run_id=$($run.run_id)" -WebSession $session -Headers @{
  Origin = $Origin
  Accept = "text/event-stream"
}
if ($streamResp.Content -notmatch "data:") { throw "Missing SSE data" }
if ($streamResp.Content -notmatch "\[DONE\]|event:\s*done|`"status`":`"completed`"") {
  throw "Missing SSE terminal marker"
}

Step "[6/7] Create long run for cancel"
$run2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/chat" -WebSession $session -Headers @{
  Origin = $Origin
  "X-CSRF-Token" = $csrf
  "Content-Type" = "application/json"
} -Body (@{ conversation_id = $conv.id; input = "please stream a long answer"; stream = $true } | ConvertTo-Json)
if (-not $run2.run_id) { throw "Missing run_id for cancel path" }

Step "[7/7] Cancel run"
Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/chat/cancel" -WebSession $session -Headers @{
  Origin = $Origin
  "X-CSRF-Token" = $csrf
  "Content-Type" = "application/json"
} -Body (@{ run_id = $run2.run_id } | ConvertTo-Json) | Out-Null

Write-Host "Smoke test passed." -ForegroundColor Green
