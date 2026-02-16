#!/usr/bin/env bash
# Run all tests
set -e
cd "$(dirname "$0")/../omni-backend"
python -m pytest tests/ -v "$@"
