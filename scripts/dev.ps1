# Local dev server — starts backend on 127.0.0.1:8000 with auto-reload
$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\omni-backend"

$env:OMNI_ENV = "dev"
$env:OMNI_HOST = "127.0.0.1"
$env:OMNI_PORT = "8000"

Write-Host "Starting OmniAI backend (dev mode)..."
Write-Host "  Backend: http://127.0.0.1:8000"
Write-Host "  V2 health: http://127.0.0.1:8000/v2/health"
Write-Host ""

python -m uvicorn omni_backend.main:app --host 127.0.0.1 --port 8000 --reload

Pop-Location
