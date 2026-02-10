#!/bin/bash
# OmniAI Deployment Verification Script
# Run this after deploying to GitHub Pages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"
PAGES_REPO_PATH="${PAGES_REPO_PATH:-../omniplexity.github.io}"
API_URL="${API_URL:-https://omniplexity.duckdns.org}"

echo "=========================================="
echo "OmniAI Deployment Verification"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo -e "  $1"; }

# ==========================================
# 1. Check frontend build artifacts
# ==========================================
echo ""
echo "1. Checking frontend build artifacts..."
info "Build directory exists: $FRONTEND_DIR/dist"
if [ -d "$FRONTEND_DIR/dist" ]; then
    pass "Build directory exists"
else
    fail "Build directory missing - run 'npm run build' first"
    exit 1
fi

info "index.html exists"
if [ -f "$FRONTEND_DIR/dist/index.html" ]; then
    pass "index.html exists"
else
    fail "index.html missing from build"
    exit 1
fi

info "404.html exists"
if [ -f "$FRONTEND_DIR/dist/404.html" ]; then
    pass "404.html exists"
else
    fail "404.html missing - SPA routing won't work"
fi

info "runtime-config.json not baked into build"
if ! grep -q "runtime-config.json" "$FRONTEND_DIR/dist/index.html" 2>/dev/null; then
    pass "runtime-config.json NOT in build (correct)"
else
    warn "runtime-config.json may be referenced in build"
fi

# ==========================================
# 2. Check Pages repo
# ==========================================
echo ""
echo "2. Checking Pages repository..."
info "Pages repo path: $PAGES_REPO_PATH"
if [ -d "$PAGES_REPO_PATH" ]; then
    pass "Pages repo exists"
else
    warn "Pages repo not found at $PAGES_REPO_PATH"
    info "Expected: $PAGES_REPO_PATH"
fi

info "Pages dist/ copied to repo root"
if [ -d "$PAGES_REPO_PATH/dist" ] || [ -f "$PAGES_REPO_PATH/index.html" ]; then
    pass "Frontend files in Pages repo"
else
    fail "Frontend not copied to Pages repo"
    info "Run: cp -r frontend/dist/* $PAGES_REPO_PATH/"
fi

info "runtime-config.json in repo root"
if [ -f "$PAGES_REPO_PATH/runtime-config.json" ]; then
    pass "runtime-config.json in repo root"
    
    # Check runtime-config has valid BACKEND_BASE_URL
    BACKEND_URL=$(grep -o '"BACKEND_BASE_URL"[[:space:]]*:[[:space:]]*"[^"]*"' "$PAGES_REPO_PATH/runtime-config.json" | cut -d'"' -f4)
    if [ -n "$BACKEND_URL" ]; then
        pass "BACKEND_BASE_URL set: $BACKEND_URL"
    else
        fail "BACKEND_BASE_URL not set in runtime-config.json"
    fi
else
    fail "runtime-config.json missing from repo root"
fi

# ==========================================
# 3. Check CORS/Cookie security headers
# ==========================================
echo ""
echo "3. Verifying backend security configuration..."

info "Testing health endpoint: $API_URL/health"
HEALTH_RESPONSE=$(curl -sf "$API_URL/health" 2>/dev/null || echo "FAILED")
if [ "$HEALTH_RESPONSE" != "FAILED" ]; then
    pass "Backend health check passed"
    echo "    Response: $HEALTH_RESPONSE"
else
    fail "Backend health check failed"
    info "Ensure backend is running at $API_URL"
fi

info "Testing CORS preflight from allowed origin"
CORS_RESPONSE=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X OPTIONS \
    -H "Origin: https://omniplexity.github.io" \
    -H "Access-Control-Request-Method: POST" \
    "$API_URL/v1/chat" 2>/dev/null || echo "FAILED")

if [ "$CORS_RESPONSE" = "200" ]; then
    pass "CORS preflight OK (200)"
else
    warn "CORS preflight returned: $CORS_RESPONSE"
fi

info "Testing CORS rejection from evil origin"
CORS_REJECT=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X OPTIONS \
    -H "Origin: https://evil.example.com" \
    -H "Access-Control-Request-Method: POST" \
    "$API_URL/v1/chat" 2>/dev/null || echo "FAILED")

if [ "$CORS_REJECT" = "403" ]; then
    pass "CORS rejection OK (403 for evil origin)"
else
    warn "CORS rejection returned: $CORS_REJECT (expected 403)"
fi

info "Testing Host header validation"
HOST_CHECK=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Host: evil.example.com" \
    "$API_URL/v1/health" 2>/dev/null || echo "FAILED")

if [ "$HOST_CHECK" = "403" ]; then
    pass "Host header rejection OK (403)"
else
    warn "Host header check returned: $HOST_CHECK (expected 403)"
fi

# ==========================================
# 4. SSE streaming test
# ==========================================
echo ""
echo "4. Testing SSE streaming..."
info "Testing /v1/chat/stream endpoint..."

# Note: Requires authentication - this is a basic connectivity test
SSE_CHECK=$(curl -sf -o /dev/null -w "%{http_code}" \
    "$API_URL/v1/chat/stream?run_id=test" 2>/dev/null || echo "FAILED")

if [ "$SSE_CHECK" = "404" ]; then
    pass "SSE endpoint responds (404 = no run found, which is OK)"
elif [ "$SSE_CHECK" = "401" ]; then
    pass "SSE endpoint requires auth (401 = OK)"
else
    info "SSE endpoint returned: $SSE_CHECK"
fi

# ==========================================
# Summary
# ==========================================
echo ""
echo "=========================================="
echo "Deployment Checklist Summary"
echo "=========================================="
echo ""
echo "Frontend:"
echo "  [ ] Build: npm run build"
echo "  [ ] Copy: cp -r frontend/dist/* ../omniplexity.github.io/"
echo "  [ ] runtime-config.json: BACKEND_BASE_URL set"
echo ""
echo "Backend:"
echo "  [ ] Health: $API_URL/health"
echo "  [ ] CORS: Origin validation working"
echo "  [ ] Host: Host header validation working"
echo ""
echo "GitHub Pages:"
echo "  [ ] Repository: omniplexity/omniplexity.github.io"
echo "  [ ] Branch: main (or gh-pages)"
echo "  [ ] Actions: Deployment succeeded"
echo ""
echo "Run smoke tests after deployment:"
echo "  npm run test           # Unit tests"
echo "  npm run test:e2e      # E2E tests (requires backend)"
echo ""
