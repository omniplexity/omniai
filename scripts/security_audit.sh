#!/usr/bin/env bash
# OmniAI Security Audit Script
# Run this locally to check for vulnerable dependencies

set -euo pipefail

echo "Installing pip-audit..."
python -m pip install --upgrade pip
pip install pip-audit

echo ""
echo "Running pip-audit..."

if [ -f backend/requirements.txt ]; then
    pip-audit -r backend/requirements.txt
elif [ -f requirements.txt ]; then
    pip-audit -r requirements.txt
else
    echo "No requirements.txt found."
fi
