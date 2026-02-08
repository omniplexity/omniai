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
