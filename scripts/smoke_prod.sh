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
headers_boot="${tmp_dir}/boot.headers"
headers_login="${tmp_dir}/login.headers"
headers_stream="${tmp_dir}/stream.headers"
body_health="${tmp_dir}/health.json"
body_boot="${tmp_dir}/boot.json"
body_login="${tmp_dir}/login.json"
body_conv="${tmp_dir}/conv.json"
body_run="${tmp_dir}/run.json"
body_stream="${tmp_dir}/stream.txt"
body_run2="${tmp_dir}/run2.json"
body_cancel="${tmp_dir}/cancel.json"

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

# 2) GET /v1/auth/csrf/bootstrap
code="$(curl -sS -D "${headers_boot}" -o "${body_boot}" -w "%{http_code}" \
  -c "${cookie_jar}" -b "${cookie_jar}" \
  -H "Origin: ${ORIGIN}" \
  "${BASE_URL}/v1/auth/csrf/bootstrap")"
[[ "${code}" == "200" ]] || fail "GET /v1/auth/csrf/bootstrap returned ${code}"

CSRF_TOKEN="$(python -c 'import json,sys; print(json.loads(sys.stdin.read()).get("csrf_token",""))' <"${body_boot}")"
[[ -n "${CSRF_TOKEN}" ]] || fail "csrf_token missing in bootstrap response"

grep -Eqi "^Set-Cookie: omni_csrf=.*SameSite=None;.*Secure;.*Partitioned\r?$" "${headers_boot}" || \
  fail "Bootstrap omni_csrf cookie missing SameSite=None; Secure; Partitioned"
pass "Bootstrap sets partitioned omni_csrf cookie"

# 3) POST /v1/auth/login
payload="$(printf '{"username":"%s","password":"%s"}' "${USERNAME}" "${PASSWORD}")"
code="$(curl -sS -D "${headers_login}" -o "${body_login}" -w "%{http_code}" \
  -c "${cookie_jar}" -b "${cookie_jar}" \
  -X POST "${BASE_URL}/v1/auth/login" \
  -H "Origin: ${ORIGIN}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  --data-binary "${payload}")"
[[ "${code}" == "200" ]] || fail "POST /v1/auth/login returned ${code}"

grep -Eqi "^Set-Cookie: omni_session=.*HttpOnly;.*SameSite=None;.*Secure;.*Partitioned\r?$" "${headers_login}" || \
  fail "Login omni_session cookie missing SameSite=None; Secure; Partitioned"
grep -Eqi "^Set-Cookie: omni_csrf=.*SameSite=None;.*Secure;.*Partitioned\r?$" "${headers_login}" || \
  fail "Login omni_csrf cookie missing SameSite=None; Secure; Partitioned"
pass "Login emits partitioned omni_session + omni_csrf cookies"

# Prefer csrf_token from login response when present (session-bound token).
CSRF_LOGIN="$(python -c 'import json,sys; d=json.loads(sys.stdin.read()); print(d.get("csrf_token",""))' <"${body_login}" 2>/dev/null || true)"
if [[ -n "${CSRF_LOGIN}" ]]; then
  CSRF_TOKEN="${CSRF_LOGIN}"
fi

# 4) POST /v1/conversations
code="$(curl -sS -o "${body_conv}" -w "%{http_code}" \
  -c "${cookie_jar}" -b "${cookie_jar}" \
  -X POST "${BASE_URL}/v1/conversations" \
  -H "Origin: ${ORIGIN}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke Conversation"}')"
[[ "${code}" == "200" || "${code}" == "201" ]] || fail "POST /v1/conversations returned ${code}"
CONV_ID="$(python -c 'import json,sys; d=json.loads(sys.stdin.read()); print(d.get("id") or d.get("conversation_id") or "")' <"${body_conv}")"
[[ -n "${CONV_ID}" ]] || fail "conversation id missing"
pass "Conversation created"

# 5) POST /v1/chat (stream run creation)
code="$(curl -sS -o "${body_run}" -w "%{http_code}" \
  -c "${cookie_jar}" -b "${cookie_jar}" \
  -X POST "${BASE_URL}/v1/chat" \
  -H "Origin: ${ORIGIN}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"${CONV_ID}\",\"input\":\"smoke test\",\"stream\":true}")"
[[ "${code}" == "200" ]] || fail "POST /v1/chat returned ${code}"
RUN_ID="$(python -c 'import json,sys; print(json.loads(sys.stdin.read()).get("run_id",""))' <"${body_run}")"
[[ -n "${RUN_ID}" ]] || fail "run_id missing"
pass "Chat run created"

# 6) GET /v1/chat/stream
code="$(curl -sS -N -D "${headers_stream}" -o "${body_stream}" -w "%{http_code}" \
  -c "${cookie_jar}" -b "${cookie_jar}" \
  -H "Origin: ${ORIGIN}" \
  -H "Accept: text/event-stream" \
  "${BASE_URL}/v1/chat/stream?run_id=${RUN_ID}")"
[[ "${code}" == "200" ]] || fail "GET /v1/chat/stream returned ${code}"
grep -Eqi "^Content-Type: text/event-stream" "${headers_stream}" || fail "Stream content-type is not text/event-stream"
grep -q "data:" "${body_stream}" || fail "Stream missing SSE data frames"
grep -Eq "event: done|event: stopped|\\[DONE\\]|\"status\":\"completed\"" "${body_stream}" || fail "Stream missing terminal marker"
pass "SSE stream validated"

# 7) POST /v1/chat/cancel
code="$(curl -sS -o "${body_run2}" -w "%{http_code}" \
  -c "${cookie_jar}" -b "${cookie_jar}" \
  -X POST "${BASE_URL}/v1/chat" \
  -H "Origin: ${ORIGIN}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"${CONV_ID}\",\"input\":\"please stream a long answer\",\"stream\":true}")"
[[ "${code}" == "200" ]] || fail "POST /v1/chat (cancel path) returned ${code}"
RUN_ID_2="$(python -c 'import json,sys; print(json.loads(sys.stdin.read()).get("run_id",""))' <"${body_run2}")"
[[ -n "${RUN_ID_2}" ]] || fail "run_id missing for cancel path"

code="$(curl -sS -o "${body_cancel}" -w "%{http_code}" \
  -c "${cookie_jar}" -b "${cookie_jar}" \
  -X POST "${BASE_URL}/v1/chat/cancel" \
  -H "Origin: ${ORIGIN}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"run_id\":\"${RUN_ID_2}\"}")"
[[ "${code}" == "200" ]] || fail "POST /v1/chat/cancel returned ${code}"
pass "Cancel endpoint validated"

echo "Smoke PASS"
