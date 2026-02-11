#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-${API_BASE_URL:-https://omniplexity.duckdns.org}}"
MODE="${GATE_A_MODE:-preflight}"
USERNAME="${SMOKE_USERNAME:-${E2E_USERNAME:-}}"
PASSWORD="${SMOKE_PASSWORD:-${E2E_PASSWORD:-}}"
ORIGINS_CSV="${ORIGINS_CSV:-${ORIGINS:-https://omniplexity.github.io}}"
ALLOWED_CSV="${ALLOWED_ORIGINS:-https://omniplexity.github.io}"
OUT_DIR="${OUT_DIR:-artifacts/launch-gate-a}"

mkdir -p "${OUT_DIR}"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
MATRIX_FILE="${OUT_DIR}/matrix-${STAMP}.md"
HEALTH_LOG="${OUT_DIR}/health-${STAMP}.log"

echo "# Gate A Matrix (${STAMP})" > "${MATRIX_FILE}"
echo >> "${MATRIX_FILE}"
echo "Mode: \`${MODE}\`" >> "${MATRIX_FILE}"
echo >> "${MATRIX_FILE}"
echo "| Origin | Expected | Preflight | Login/Smoke | Notes | Overall | Log |" >> "${MATRIX_FILE}"
echo "| --- | --- | --- | --- | --- | --- | --- |" >> "${MATRIX_FILE}"

if curl -fsS "${BASE_URL}/health" > "${HEALTH_LOG}" 2>&1; then
  echo "Health check: PASS (\`${BASE_URL}/health\`)" >> "${MATRIX_FILE}"
else
  echo "Health check: FAIL (\`${BASE_URL}/health\`) - see \`${HEALTH_LOG}\`" >> "${MATRIX_FILE}"
fi
echo >> "${MATRIX_FILE}"

contains_origin() {
  local needle="$1"
  local csv="$2"
  IFS=',' read -r -a arr <<< "$csv"
  for entry in "${arr[@]}"; do
    local trimmed
    trimmed="$(echo "${entry}" | xargs)"
    if [[ "$trimmed" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

IFS=',' read -r -a ORIGIN_ARR <<< "${ORIGINS_CSV}"
for origin in "${ORIGIN_ARR[@]}"; do
  origin_trimmed="$(echo "${origin}" | xargs)"
  [[ -z "${origin_trimmed}" ]] && continue
  safe_name="$(echo "${origin_trimmed}" | sed 's#https\?://##; s#[^A-Za-z0-9._-]#_#g')"
  log_file="${OUT_DIR}/smoke-${safe_name}-${STAMP}.log"
  preflight_log="${OUT_DIR}/preflight-${safe_name}-${STAMP}.headers"

  expected="disallowed"
  if contains_origin "${origin_trimmed}" "${ALLOWED_CSV}"; then
    expected="allowed"
  fi

  if curl -sS -D "${preflight_log}" -o /dev/null -X OPTIONS \
    -H "Origin: ${origin_trimmed}" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: content-type,x-csrf-token" \
    "${BASE_URL}/v1/auth/login" >> "${log_file}" 2>&1; then
    :
  else
    :
  fi

  status="$(awk 'toupper($1) ~ /^HTTP\// {print $2; exit}' "${preflight_log}")"
  acao="$(awk -F': ' 'tolower($1)=="access-control-allow-origin" {gsub("\r","",$2); print $2; exit}' "${preflight_log}")"
  acac="$(awk -F': ' 'tolower($1)=="access-control-allow-credentials" {gsub("\r","",$2); print tolower($2); exit}' "${preflight_log}")"
  vary="$(awk -F': ' 'tolower($1)=="vary" {gsub("\r","",$2); print tolower($2); exit}' "${preflight_log}")"

  preflight_pass="FAIL"
  notes=""
  if [[ "${expected}" == "allowed" ]]; then
    if [[ "${status}" =~ ^2[0-9][0-9]$ ]] && [[ "${acao}" == "${origin_trimmed}" ]] && [[ "${acac}" == "true" ]] && [[ "${vary}" == *"origin"* ]]; then
      preflight_pass="PASS"
    else
      notes="Allowed CORS headers/status mismatch"
    fi
  else
    if [[ -z "${acao}" ]] && [[ -z "${acac}" ]]; then
      preflight_pass="PASS"
    else
      notes="Disallowed origin unexpectedly received credentialed CORS headers"
    fi
  fi

  smoke_result="SKIP"
  overall="${preflight_pass}"

  if [[ "${MODE}" == "smoke" ]] && [[ "${expected}" == "allowed" ]]; then
    if [[ -z "${USERNAME}" || -z "${PASSWORD}" ]]; then
      smoke_result="FAIL"
      notes="${notes:+$notes; }Missing SMOKE_USERNAME/SMOKE_PASSWORD"
      overall="FAIL"
    elif ORIGIN="${origin_trimmed}" BASE_URL="${BASE_URL}" E2E_USERNAME="${USERNAME}" E2E_PASSWORD="${PASSWORD}" \
      bash scripts/smoke-frontend.sh >>"${log_file}" 2>&1; then
      smoke_result="PASS"
      if [[ "${preflight_pass}" != "PASS" ]]; then
        overall="FAIL"
      fi
    else
      smoke_result="FAIL"
      overall="FAIL"
    fi
  fi

  if [[ -z "${notes}" ]]; then
    notes="-"
  fi

  echo "| ${origin_trimmed} | ${expected} | ${preflight_pass} | ${smoke_result} | ${notes} | ${overall} | \`${log_file}\` |" >> "${MATRIX_FILE}"
done

echo "Wrote ${MATRIX_FILE}"
