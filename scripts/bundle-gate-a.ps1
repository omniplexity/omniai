param(
  [string]$ArtifactsDir = "artifacts/launch-gate-a"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ArtifactsDir)) {
  throw "Artifacts directory not found: $ArtifactsDir"
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$matrix = Get-ChildItem -Path $ArtifactsDir -Filter "matrix-*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $matrix) {
  throw "No matrix file found under $ArtifactsDir"
}

$summaryPath = Join-Path $ArtifactsDir "env-summary-$stamp.txt"
$apiBase = if ($env:API_BASE_URL) { $env:API_BASE_URL } elseif ($env:BASE_URL) { $env:BASE_URL } else { "" }
$origins = if ($env:ORIGINS) { $env:ORIGINS } elseif ($env:ORIGINS_CSV) { $env:ORIGINS_CSV } else { "" }
$mode = if ($env:GATE_A_MODE) { $env:GATE_A_MODE } else { "preflight" }

@(
  "timestamp=$stamp"
  "API_BASE_URL=$apiBase"
  "ORIGINS=$origins"
  "ALLOWED_ORIGINS=$($env:ALLOWED_ORIGINS)"
  "GATE_A_MODE=$mode"
) | Set-Content $summaryPath

$logs = Get-ChildItem -Path $ArtifactsDir -Filter "smoke-*" | Select-Object -ExpandProperty FullName
if (-not $logs -or $logs.Count -eq 0) {
  throw "No smoke logs found under $ArtifactsDir (expected smoke-* files)."
}
$bundle = Join-Path $ArtifactsDir "gate-a-bundle-$stamp.zip"
$paths = @($matrix.FullName, $summaryPath) + $logs
Compress-Archive -Path $paths -DestinationPath $bundle -Force

Write-Host "Wrote $bundle"
