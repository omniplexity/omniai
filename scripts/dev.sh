#!/usr/bin/env bash
# Local dev server — starts backend on 127.0.0.1:8000 with auto-reload
set -e
cd "$(dirname "$0")/../omni-backend"

export OMNI_ENV=dev
export OMNI_HOST=127.0.0.1
export OMNI_PORT=8000

echo "Starting OmniAI backend (dev mode)..."
echo "  Backend: http://127.0.0.1:8000"
echo "  V2 health: http://127.0.0.1:8000/v2/health"
echo ""

python -m uvicorn omni_backend.main:app --host 127.0.0.1 --port 8000 --reload
