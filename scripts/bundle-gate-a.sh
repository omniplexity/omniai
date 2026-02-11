#!/usr/bin/env bash
set -euo pipefail

ARTIFACTS_DIR="${1:-artifacts/launch-gate-a}"
STAMP="${2:-$(date -u +"%Y%m%dT%H%M%SZ")}"
OUT_FILE="${ARTIFACTS_DIR}/gate-a-bundle-${STAMP}.zip"

if [[ ! -d "${ARTIFACTS_DIR}" ]]; then
  echo "Artifacts directory not found: ${ARTIFACTS_DIR}" >&2
  exit 1
fi

LATEST_MATRIX="$(ls -1t "${ARTIFACTS_DIR}"/matrix-*.md 2>/dev/null | head -n1 || true)"
if [[ -z "${LATEST_MATRIX}" ]]; then
  echo "No matrix file found under ${ARTIFACTS_DIR}" >&2
  exit 1
fi

SUMMARY_FILE="${ARTIFACTS_DIR}/env-summary-${STAMP}.txt"
{
  echo "timestamp=${STAMP}"
  echo "API_BASE_URL=${API_BASE_URL:-${BASE_URL:-}}"
  echo "ORIGINS=${ORIGINS:-${ORIGINS_CSV:-}}"
  echo "ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-}"
  echo "GATE_A_MODE=${GATE_A_MODE:-preflight}"
} > "${SUMMARY_FILE}"

LOGS=()
while IFS= read -r line; do
  LOGS+=("$line")
done < <(ls -1 "${ARTIFACTS_DIR}"/smoke-* 2>/dev/null || true)

if [[ "${#LOGS[@]}" -eq 0 ]]; then
  echo "No smoke logs found under ${ARTIFACTS_DIR} (expected smoke-* files)." >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "zip is required to create bundle archives." >&2
  exit 1
fi

zip -j -q "${OUT_FILE}" "${LATEST_MATRIX}" "${SUMMARY_FILE}" "${LOGS[@]}"
echo "Wrote ${OUT_FILE}"
