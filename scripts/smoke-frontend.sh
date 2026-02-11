#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-${1:-http://127.0.0.1:8000}}"
USERNAME="${E2E_USERNAME:-${2:-ci_e2e_user}}"
PASSWORD="${E2E_PASSWORD:-${3:-ci_e2e_pass}}"
ORIGIN="${ORIGIN:-http://127.0.0.1:4173}"

COOKIE_JAR="$(mktemp)"
cleanup() { rm -f "$COOKIE_JAR"; }
trap cleanup EXIT

echo "[1/7] CSRF bootstrap"
CSRF_JSON="$(curl -fsS -c "$COOKIE_JAR" -b "$COOKIE_JAR" -H "Origin: ${ORIGIN}" "${BASE_URL}/v1/auth/csrf/bootstrap")"
CSRF_TOKEN="$(python -c 'import json,sys; print(json.loads(sys.stdin.read()).get("csrf_token",""))' <<<"$CSRF_JSON")"
test -n "$CSRF_TOKEN"
if ! grep -q 'omni_csrf' "$COOKIE_JAR"; then
  echo "Missing omni_csrf cookie after bootstrap" >&2
  exit 1
fi

echo "[2/7] Login"
curl -fsS -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H "Origin: ${ORIGIN}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}" \
  "${BASE_URL}/v1/auth/login" >/dev/null

echo "[3/7] Create conversation"
CONV_JSON="$(curl -fsS -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H "Origin: ${ORIGIN}" -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke Conversation"}' \
  "${BASE_URL}/v1/conversations")"
CONV_ID="$(python -c 'import json,sys; print(json.loads(sys.stdin.read()).get("id",""))' <<<"$CONV_JSON")"
test -n "$CONV_ID"

echo "[4/7] Create run"
RUN_JSON="$(curl -fsS -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H "Origin: ${ORIGIN}" -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"${CONV_ID}\",\"input\":\"smoke test\",\"stream\":true}" \
  "${BASE_URL}/v1/chat")"
RUN_ID="$(python -c 'import json,sys; print(json.loads(sys.stdin.read()).get("run_id",""))' <<<"$RUN_JSON")"
test -n "$RUN_ID"

echo "[5/7] Stream run"
STREAM_BODY="$(curl -fsS -N -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H "Origin: ${ORIGIN}" \
  -H "Accept: text/event-stream" \
  "${BASE_URL}/v1/chat/stream?run_id=${RUN_ID}")"
grep -q "data:" <<<"$STREAM_BODY"
grep -Eq "\[DONE\]|event: done|\"status\":\"completed\"" <<<"$STREAM_BODY"

echo "[6/7] Create long run for cancel"
RUN2_JSON="$(curl -fsS -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H "Origin: ${ORIGIN}" -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"${CONV_ID}\",\"input\":\"please stream a long answer\",\"stream\":true}" \
  "${BASE_URL}/v1/chat")"
RUN2_ID="$(python -c 'import json,sys; print(json.loads(sys.stdin.read()).get("run_id",""))' <<<"$RUN2_JSON")"
test -n "$RUN2_ID"

echo "[7/7] Cancel run"
curl -fsS -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H "Origin: ${ORIGIN}" -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"run_id\":\"${RUN2_ID}\"}" \
  "${BASE_URL}/v1/chat/cancel" >/dev/null

echo "Smoke test passed."
