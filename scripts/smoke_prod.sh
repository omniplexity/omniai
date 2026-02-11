#!/usr/bin/env bash
set -euo pipefail

# Production smoke checks for OmniAI public API.
# Required env:
#   SMOKE_USERNAME
#   SMOKE_PASSWORD
# Optional env:
#   SMOKE_BASE_URL (default: https://omniplexity.duckdns.org)
#   SMOKE_ORIGIN   (default: https://omniplexity.github.io)
#   SMOKE_STRICT_BUILD=1 (fail if /health reports production with unknown build metadata)

BASE_URL="${SMOKE_BASE_URL:-https://omniplexity.duckdns.org}"
ORIGIN="${SMOKE_ORIGIN:-https://omniplexity.github.io}"
USERNAME="${SMOKE_USERNAME:-}"
PASSWORD="${SMOKE_PASSWORD:-}"
STRICT_BUILD="${SMOKE_STRICT_BUILD:-0}"

if [[ -z "${USERNAME}" || -z "${PASSWORD}" ]]; then
  echo "FAIL: SMOKE_USERNAME and SMOKE_PASSWORD must be set" >&2
  exit 2
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cookie_jar="${tmp_dir}/cookies.txt"
headers_opts="${tmp_dir}/opts.headers"
headers_login="${tmp_dir}/login.headers"
body_health="${tmp_dir}/health.json"
body_me="${tmp_dir}/me.json"
payload_file="${tmp_dir}/login.payload.json"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

echo "== Smoke: ${BASE_URL} =="

# 1) GET /health
code="$(curl -sS -o "${body_health}" -w "%{http_code}" "${BASE_URL}/health")"
[[ "${code}" == "200" ]] || fail "GET /health returned ${code}"
pass "GET /health -> 200"
if [[ "${STRICT_BUILD}" == "1" || "${STRICT_BUILD}" == "true" || "${STRICT_BUILD}" == "yes" || "${STRICT_BUILD}" == "on" ]]; then
  if grep -Eqi '"environment"\s*:\s*"production"' "${body_health}"; then
    grep -Eqi '"build_sha"\s*:\s*"[^"]+"' "${body_health}" || fail "Strict build check failed: build_sha missing in production"
    grep -Eqi '"build_time"\s*:\s*"[^"]+"' "${body_health}" || fail "Strict build check failed: build_time missing in production"
    if grep -Eqi '"build_sha"\s*:\s*"unknown"' "${body_health}"; then
      fail "Strict build check failed: build_sha is unknown in production"
    fi
    if grep -Eqi '"build_time"\s*:\s*"unknown"' "${body_health}"; then
      fail "Strict build check failed: build_time is unknown in production"
    fi
  fi
  pass "Strict build metadata check passed"
fi

# 2) OPTIONS /v1/auth/login
code="$(curl -sS -D "${headers_opts}" -o /dev/null -w "%{http_code}" \
  -X OPTIONS "${BASE_URL}/v1/auth/login" \
  -H "Origin: ${ORIGIN}" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-csrf-token")"
[[ "${code}" == "200" ]] || fail "OPTIONS /v1/auth/login returned ${code}"

grep -Eqi "^Access-Control-Allow-Origin: ${ORIGIN}\r?$" "${headers_opts}" || fail "Missing/invalid Access-Control-Allow-Origin"
grep -Eqi "^Access-Control-Allow-Credentials: true\r?$" "${headers_opts}" || fail "Missing Access-Control-Allow-Credentials: true"
grep -Eqi "^Vary: .*Origin\r?$" "${headers_opts}" || fail "Missing Vary: Origin"
grep -Eqi "^Access-Control-Allow-Methods: .*POST.*OPTIONS\r?$" "${headers_opts}" || fail "Allow-Methods missing POST/OPTIONS"
grep -Eqi "^Access-Control-Allow-Headers: .*content-type\r?$" "${headers_opts}" || fail "Allow-Headers missing content-type"
grep -Eqi "^Access-Control-Allow-Headers: .*x-csrf-token\r?$" "${headers_opts}" || fail "Allow-Headers missing x-csrf-token"
pass "OPTIONS /v1/auth/login headers validated"

# 3) POST /v1/auth/login -> must set both cookies
payload="$(printf '{"username":"%s","password":"%s"}' "${USERNAME}" "${PASSWORD}")"
printf '%s' "${payload}" > "${payload_file}"
code="$(curl -sS -D "${headers_login}" -o /dev/null -w "%{http_code}" \
  -c "${cookie_jar}" \
  -X POST "${BASE_URL}/v1/auth/login" \
  -H "Origin: ${ORIGIN}" \
  -H "Content-Type: application/json" \
  --data-binary "@${payload_file}")"
[[ "${code}" == "200" ]] || fail "POST /v1/auth/login returned ${code}"

grep -qi "^Set-Cookie: omni_session=.*HttpOnly;.*SameSite=None; Secure" "${headers_login}" || fail "Missing/invalid omni_session Set-Cookie"
grep -qi "^Set-Cookie: omni_csrf=.*SameSite=None; Secure" "${headers_login}" || fail "Missing/invalid omni_csrf Set-Cookie"
pass "POST /v1/auth/login emitted both cookies"

# 4) GET /v1/auth/me with cookie jar
code="$(curl -sS -o "${body_me}" -w "%{http_code}" \
  -b "${cookie_jar}" \
  -H "Origin: ${ORIGIN}" \
  "${BASE_URL}/v1/auth/me")"
[[ "${code}" == "200" ]] || fail "GET /v1/auth/me returned ${code}"
pass "GET /v1/auth/me with cookie jar -> 200"

echo "Smoke PASS"
