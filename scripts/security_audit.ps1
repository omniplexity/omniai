#!/usr/bin/env pwsh
# OmniAI Security Audit Script
# Run this locally to check for vulnerable dependencies

$ErrorActionPreference = "Stop"

Write-Host "Installing pip-audit..." -ForegroundColor Cyan
python -m pip install --upgrade pip
pip install pip-audit

Write-Host "`nRunning pip-audit..." -ForegroundColor Cyan

if (Test-Path "backend\requirements.txt") {
    pip-audit -r "backend\requirements.txt"
}
elseif (Test-Path "requirements.txt") {
    pip-audit -r "requirements.txt"
}
else {
    Write-Host "No requirements.txt found." -ForegroundColor Yellow
}
