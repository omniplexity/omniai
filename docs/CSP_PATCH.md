# CSP Patch for omniplexity.github.io

**Status:** CSP implementation deferred until frontend rebuild.

**Context:** The frontend repository was consolidated into the main OmniAI repository. When the frontend is rebuilt in `OmniAI/frontend`, this CSP should be applied before deployment.

**Application script:** `scripts/apply_csp.ps1`

---

Apply this patch to the frontend `index.html` to add Content-Security-Policy headers.

## Development CSP (for ngrok/cloudflared)

Add this meta tag inside `<head>` before any `<script>` tags:

```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  img-src 'self' data: blob:;
  style-src 'self' 'unsafe-inline';
  script-src 'self';
  connect-src 'self' https:;
">
```

## Production CSP (once stable API domain is available)

Replace `connect-src` with your stable API origin:

```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  img-src 'self' data: blob:;
  style-src 'self' 'unsafe-inline';
  script-src 'self';
  connect-src 'self' https://chat.yourdomain.com;
">
```

## Example index.html after patch

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- ADD CSP HERE -->
    <meta http-equiv="Content-Security-Policy" content="
      default-src 'self';
      base-uri 'self';
      object-src 'none';
      frame-ancestors 'none';
      img-src 'self' data: blob:;
      style-src 'self' 'unsafe-inline';
      script-src 'self';
      connect-src 'self' https:;
    ">
    <title>OmniAI</title>
    <!-- scripts come after CSP -->
    <script src="..."></script>
</head>
<body>
    ...
</body>
</html>
```

## Verification

After applying:
1. Open browser DevTools (F12)
2. Check Console for CSP violations
3. Verify API calls still work (check Network tab)

## Troubleshooting

If you see CSP violations in console:
- For missing styles: add domain to `style-src` or use inline allowance
- For missing scripts: ensure all scripts have `src` attribute (no inline `<script>` blocks)
- For API calls: adjust `connect-src` as needed

## Common CSP Violations

These violations frequently appear when first applying CSP to a Preact/React SPA:

| Violation | Cause | Fix |
|-----------|-------|-----|
| `Refused to execute inline script` | `<script>` tag without `src` attribute | Move inline JS to external `.js` file |
| `Refused to apply inline style` | Framework injecting `<style>` tags | Already handled: `style-src 'unsafe-inline'` |
| `Refused to load font` | CDN fonts (Google Fonts, Font Awesome) | Add CDN to `style-src` and add `font-src` directive |
| `Refused to load image` | External image URLs | Add domain to `img-src` or proxy through backend |
| `Refused to connect` | API call to unlisted domain | Add domain to `connect-src` |
| `Refused to load worker` | Web Workers or Service Workers | Add `worker-src 'self'` directive |

### Preact/Vite Specific Notes

- Vite dev server uses WebSocket for HMR: add `ws://localhost:*` to `connect-src` in dev only
- Preact does NOT require `unsafe-eval` (unlike some React setups)
- CSS-in-JS libraries may need `style-src 'unsafe-inline'` (already included)

## Production: Tighten connect-src

When you have a stable production API domain, replace the development `https:` wildcard:

**Before (development):**
```
connect-src 'self' https:;
```

**After (production):**
```
connect-src 'self' https://api.yourdomain.com;
```

**Rollout strategy:**

1. Deploy with `Content-Security-Policy-Report-Only` first (observe violations without blocking)
2. Monitor browser console for unexpected violations for 24-48 hours
3. Switch to enforcing `Content-Security-Policy` once clean
4. Remove the Report-Only header

**Post-tightening verification:**

- [ ] Login flow works (POST to `/auth/login` sets cookies)
- [ ] SSE streaming works (`/v1/chat/stream` establishes EventSource connection)
- [ ] API calls succeed (check Network tab for blocked requests)
- [ ] No CSP violations in browser console

**Note:** On GitHub Pages you cannot set HTTP response headers. CSP is applied via `<meta>` tag, which does NOT support `report-uri`. Monitor violations via browser console only.
