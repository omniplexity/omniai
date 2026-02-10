# OmniAI v1 Smoke Test Checklist

Run this manual smoke test after every deployment to GitHub Pages.

## Quick Verification (5 min)

### 1. Boot ✅
- [ ] Navigate to `https://omniplexity.github.io`
- [ ] No startup error overlay
- [ ] Login page or error banner visible (not blank)

### 2. Auth ✅
- [ ] Login with test credentials
- [ ] Verify session cookie set (DevTools > Application > Cookies)
- [ ] Logout
- [ ] Protected routes bounce to /login

### 3. Conversations ✅
- [ ] List loads
- [ ] Create new thread → appears in list
- [ ] Click thread → navigates to `/#/chat/{id}`
- [ ] Rename → reflected in list
- [ ] Delete → removed from list

### 4. Streaming ✅
- [ ] Send message → assistant bubble appears
- [ ] Content fills with deltas
- [ ] Stop button aborts immediately
- [ ] Retry resends same payload

### 5. Settings ✅
- [ ] Provider/model dropdown works
- [ ] Temperature/topP/maxTokens persist after reload

---

## Full Acceptance Path (15 min)

### Boot
| Check | Expected | Actual |
|-------|----------|--------|
| runtime-config.json loads | No error banner | |
| UI renders | Visible, not blank | |
| Error banner (if backend down) | Shows message | |

### Authentication
| Check | Expected | Actual |
|-------|----------|--------|
| Login POST | 200, sets cookie | |
| /v1/meta authenticated | `{authenticated: true}` | |
| Logout POST | Clears session | |
| Protected route redirect | /#/login | |

### Conversations
| Check | Expected | Actual |
|-------|----------|--------|
| GET /v1/conversations | 200, list | |
| POST creates | Returns new conv | |
| PATCH renames | Name updated | |
| DELETE removes | Gone from list | |
| Thread click | /#/chat/{id} | |

### Streaming (with LLM provider running)
| Check | Expected | Actual |
|-------|----------|--------|
| POST /v1/chat | Creates run, returns run_id | |
| GET /v1/chat/stream | SSE events stream | |
| Stop | Stream aborts, UI updates | |
| Retry | Same payload resends | |

### Settings Persistence
| Check | Expected | Actual |
|-------|----------|--------|
| Temperature set | Persists after reload | |
| TopP set | Persists after reload | |
| MaxTokens set | Persists after reload | |
| Provider selected | Persists after reload | |

---

## Failure Mode Verification

### Backend Down
```
Expected: Error banner "Cannot connect to backend"
Not: Blank page or crash
```

### 401/403
```
Expected: Redirect to /login
Not: 500 error or blank page
```

### 429 Rate Limit
```
Expected: "Too many requests" message
Not: Crash or cryptic error
```

### SSE Disconnect
```
Expected: "Connection lost" + Retry button
Not: Infinite hang or crash
```

---

## Deployment Verification Commands

### Frontend Build
```bash
cd frontend
npm run build
ls -la dist/
```

### Deploy to Pages
```bash
# From OmniAI root
cp -r frontend/dist/* ../omniplexity.github.io/
cd ../omniplexity.github.io
git add -A && git commit -m "Deploy $(date)"
git push origin main
```

### Verify Deploy
```bash
# Check Pages URL
curl -sf https://omniplexity.github.io | head -20

# Check runtime-config.json accessible
curl -sf "https://omniplexity.github.io/runtime-config.json?ts=$(date +%s)"
```

### Backend Security Check
```bash
API_URL="https://omniplexity.duckdns.org"

# Health
curl -sf $API_URL/health

# CORS - allowed origin
curl -sf -o /dev/null -w "%{http_code}" \
  -H "Origin: https://omniplexity.github.io" \
  -X OPTIONS $API_URL/v1/chat
# Expected: 200

# CORS - evil origin  
curl -sf -o /dev/null -w "%{http_code}" \
  -H "Origin: https://evil.example.com" \
  -X OPTIONS $API_URL/v1/chat
# Expected: 403

# Host header injection
curl -sf -o /dev/null -w "%{http_code}" \
  -H "Host: evil.example.com" $API_URL/v1/health
# Expected: 403
```

---

## Automated Tests

### Unit Tests
```bash
cd frontend
npm run test
```

### E2E Tests
```bash
cd frontend
npm run test:e2e:install  # One-time
npm run test:e2e
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Blank page on load | runtime-config.json missing or invalid | Check browser console |
| Login fails (no cookie) | SameSite=None issue | Verify COOKIE_SECURE=true |
| CORS errors | CORS_ORIGINS missing frontend | Add origin to backend .env |
| SSE timeout | Provider not running | Start LM Studio/Ollama |
| 403 on API calls | CSRF token missing | Check X-CSRF-Token header |
